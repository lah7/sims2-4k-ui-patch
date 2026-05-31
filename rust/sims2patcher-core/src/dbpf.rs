use std::fs::File;
use std::io::{BufWriter, Seek, Write};
use std::path::Path;

use crate::error::{PatchError, Result};
use crate::patches::StorageMode;
use crate::qfs;

pub const TYPE_UI_DATA: u32 = 0;
pub const TYPE_IMAGE: u32 = 0x856d_dbac;
pub const TYPE_DIR: u32 = 0xe86b_1eef;

#[derive(Clone, Debug)]
pub struct Header {
    pub major_version: u32,
    pub minor_version: u32,
    pub index_version_major: u32,
    pub index_version_minor: u32,
    pub index_entry_count: u32,
    pub index_start_offset: u32,
    pub index_size: u32,
}

impl Header {
    pub fn dbpf_version(&self) -> f32 {
        format!("{}.{}", self.major_version, self.minor_version)
            .parse()
            .unwrap_or(0.0)
    }

    pub fn index_version(&self) -> f32 {
        format!("{}.{}", self.index_version_major, self.index_version_minor)
            .parse()
            .unwrap_or(0.0)
    }
}

#[derive(Clone, Debug)]
pub struct Entry {
    pub type_id: u32,
    pub group_id: u32,
    pub instance_id: u32,
    pub resource_id: u32,
    pub file_location: u32,
    pub file_size: u32,
    pub decompressed_size: u32,
    pub compressed: bool,
    pub raw: Vec<u8>,
    pub modified: Option<ModifiedEntry>,
}

#[derive(Clone, Debug)]
pub struct ModifiedEntry {
    pub data: Vec<u8>,
    pub force_uncompressed: bool,
}

impl Entry {
    pub fn key(&self) -> (u32, u32, u32, u32) {
        (
            self.type_id,
            self.group_id,
            self.instance_id,
            self.resource_id,
        )
    }

    pub fn data(&self) -> Result<Vec<u8>> {
        if self.compressed {
            qfs::decompress(&self.raw, self.decompressed_size as usize)
        } else {
            Ok(self.raw.clone())
        }
    }

    pub fn data_safe(&self) -> Vec<u8> {
        self.data().unwrap_or_else(|_| self.raw.clone())
    }

    pub fn set_modified(&mut self, data: Vec<u8>, force_uncompressed: bool) {
        self.modified = Some(ModifiedEntry {
            data,
            force_uncompressed,
        });
    }
}

#[derive(Clone, Debug)]
pub struct DirectoryInfo {
    pub group_id: u32,
    pub instance_id: u32,
    pub resource_id: u32,
}

#[derive(Clone, Debug)]
pub struct DbpfPackage {
    pub header: Header,
    pub entries: Vec<Entry>,
    pub dir_info: DirectoryInfo,
}

impl DbpfPackage {
    pub fn open(path: impl AsRef<Path>) -> Result<Self> {
        let bytes = std::fs::read(path)?;
        if bytes.len() < 96 || &bytes[0..4] != b"DBPF" {
            return Err(PatchError::InvalidDbpf("missing DBPF header".to_string()));
        }

        let header = Header {
            major_version: read_u32(&bytes, 4)?,
            minor_version: read_u32(&bytes, 8)?,
            index_version_major: read_u32(&bytes, 32)?,
            index_entry_count: read_u32(&bytes, 36)?,
            index_start_offset: read_u32(&bytes, 40)?,
            index_size: read_u32(&bytes, 44)?,
            index_version_minor: read_u32(&bytes, 60)?,
        };

        if header.dbpf_version() != 1.1 {
            return Err(PatchError::InvalidDbpf(format!(
                "unsupported DBPF version {}",
                header.dbpf_version()
            )));
        }

        let entry_stride = if header.index_version() >= 7.2 {
            24
        } else {
            20
        };
        let index_start = header.index_start_offset as usize;
        let mut entries = Vec::with_capacity(header.index_entry_count as usize);
        let mut offset = index_start;
        for _ in 0..header.index_entry_count {
            let type_id = read_u32(&bytes, offset)?;
            offset += 4;
            let group_id = read_u32(&bytes, offset)?;
            offset += 4;
            let instance_id = read_u32(&bytes, offset)?;
            offset += 4;
            let resource_id = if header.index_version() >= 7.2 {
                let value = read_u32(&bytes, offset)?;
                offset += 4;
                value
            } else {
                0
            };
            let file_location = read_u32(&bytes, offset)?;
            offset += 4;
            let file_size = read_u32(&bytes, offset)?;
            offset += 4;

            let start = file_location as usize;
            let end = start + file_size as usize;
            if end > bytes.len() {
                return Err(PatchError::InvalidDbpf(
                    "entry points outside package".to_string(),
                ));
            }

            entries.push(Entry {
                type_id,
                group_id,
                instance_id,
                resource_id,
                file_location,
                file_size,
                decompressed_size: 0,
                compressed: false,
                raw: bytes[start..end].to_vec(),
                modified: None,
            });
        }

        let expected_index_size = entry_stride * entries.len();
        if expected_index_size > header.index_size as usize {
            return Err(PatchError::InvalidDbpf(
                "index smaller than declared entries".to_string(),
            ));
        }

        let mut dir_info = DirectoryInfo {
            group_id: 0,
            instance_id: 0,
            resource_id: 0,
        };
        let mut compressed_records = Vec::new();
        for entry in &entries {
            if entry.type_id == TYPE_DIR {
                dir_info = DirectoryInfo {
                    group_id: entry.group_id,
                    instance_id: entry.instance_id,
                    resource_id: entry.resource_id,
                };
                compressed_records = parse_dir_file(&entry.raw, header.index_version())?;
                break;
            }
        }

        for entry in &mut entries {
            if let Some((_, _, _, _, decompressed_size)) = compressed_records
                .iter()
                .find(|(t, g, i, r, _)| (*t, *g, *i, *r) == entry.key())
            {
                entry.compressed = true;
                entry.decompressed_size = *decompressed_size;
            }
        }

        Ok(Self {
            header,
            entries,
            dir_info,
        })
    }

    pub fn patchable_indices(&self) -> Vec<usize> {
        self.entries
            .iter()
            .enumerate()
            .filter_map(|(idx, entry)| {
                if entry.type_id == TYPE_UI_DATA || entry.type_id == TYPE_IMAGE {
                    Some(idx)
                } else {
                    None
                }
            })
            .collect()
    }

    pub fn save(
        &mut self,
        path: impl AsRef<Path>,
        storage: StorageMode,
        qfs_level: usize,
        verify_compression: bool,
        modified_only: bool,
    ) -> Result<()> {
        let path = path.as_ref();
        let mut writer = BufWriter::new(File::create(path)?);
        writer.write_all(&[0_u8; 96])?;

        let mut output_entries: Vec<EntryForWrite> = Vec::new();
        let mut dir_records: Vec<(u32, u32, u32, u32, u32)> = Vec::new();

        for entry in &self.entries {
            if entry.type_id == TYPE_DIR {
                continue;
            }
            if modified_only && entry.modified.is_none() {
                continue;
            }

            let (raw, compressed, decompressed_size) =
                entry_output(entry, storage, qfs_level, verify_compression)?;
            let file_location = writer.stream_position()? as u32;
            writer.write_all(&raw)?;
            let file_size = raw.len() as u32;

            if compressed {
                dir_records.push((
                    entry.type_id,
                    entry.group_id,
                    entry.instance_id,
                    entry.resource_id,
                    decompressed_size,
                ));
            }

            output_entries.push(EntryForWrite {
                type_id: entry.type_id,
                group_id: entry.group_id,
                instance_id: entry.instance_id,
                resource_id: entry.resource_id,
                file_location,
                file_size,
            });
        }

        if !dir_records.is_empty() {
            let file_location = writer.stream_position()? as u32;
            let dir_bytes = build_dir_file(&dir_records, self.header.index_version());
            writer.write_all(&dir_bytes)?;
            output_entries.push(EntryForWrite {
                type_id: TYPE_DIR,
                group_id: self.dir_info.group_id,
                instance_id: self.dir_info.instance_id,
                resource_id: self.dir_info.resource_id,
                file_location,
                file_size: dir_bytes.len() as u32,
            });
        }

        let index_start_offset = writer.stream_position()? as u32;
        for entry in &output_entries {
            write_u32(&mut writer, entry.type_id)?;
            write_u32(&mut writer, entry.group_id)?;
            write_u32(&mut writer, entry.instance_id)?;
            if self.header.index_version() >= 7.2 {
                write_u32(&mut writer, entry.resource_id)?;
            }
            write_u32(&mut writer, entry.file_location)?;
            write_u32(&mut writer, entry.file_size)?;
        }
        let index_size = writer.stream_position()? as u32 - index_start_offset;

        writer.flush()?;
        drop(writer);

        let mut bytes = std::fs::read(path)?;
        bytes[0..4].copy_from_slice(b"DBPF");
        write_u32_at(&mut bytes, 4, self.header.major_version)?;
        write_u32_at(&mut bytes, 8, self.header.minor_version)?;
        write_u32_at(&mut bytes, 32, self.header.index_version_major)?;
        write_u32_at(&mut bytes, 36, output_entries.len() as u32)?;
        write_u32_at(&mut bytes, 40, index_start_offset)?;
        write_u32_at(&mut bytes, 44, index_size)?;
        write_u32_at(&mut bytes, 60, self.header.index_version_minor)?;
        std::fs::write(path, bytes)?;

        Ok(())
    }
}

#[derive(Debug)]
struct EntryForWrite {
    type_id: u32,
    group_id: u32,
    instance_id: u32,
    resource_id: u32,
    file_location: u32,
    file_size: u32,
}

fn entry_output(
    entry: &Entry,
    storage: StorageMode,
    qfs_level: usize,
    verify: bool,
) -> Result<(Vec<u8>, bool, u32)> {
    let Some(modified) = &entry.modified else {
        return Ok((entry.raw.clone(), entry.compressed, entry.decompressed_size));
    };

    if modified.force_uncompressed
        || storage == StorageMode::FastCompatible
        || storage == StorageMode::None
    {
        return Ok((modified.data.clone(), false, 0));
    }

    if let Some(compressed) = qfs::compress_if_beneficial(&modified.data, qfs_level, verify)? {
        Ok((compressed, true, modified.data.len() as u32))
    } else {
        Ok((modified.data.clone(), false, 0))
    }
}

fn parse_dir_file(raw: &[u8], index_version: f32) -> Result<Vec<(u32, u32, u32, u32, u32)>> {
    let stride = if index_version >= 7.2 { 20 } else { 16 };
    let mut records = Vec::new();
    let mut offset = 0_usize;
    while offset + stride <= raw.len() {
        let type_id = read_u32(raw, offset)?;
        offset += 4;
        let group_id = read_u32(raw, offset)?;
        offset += 4;
        let instance_id = read_u32(raw, offset)?;
        offset += 4;
        let resource_id = if index_version >= 7.2 {
            let value = read_u32(raw, offset)?;
            offset += 4;
            value
        } else {
            0
        };
        let decompressed_size = read_u32(raw, offset)?;
        offset += 4;
        records.push((
            type_id,
            group_id,
            instance_id,
            resource_id,
            decompressed_size,
        ));
    }
    Ok(records)
}

fn build_dir_file(records: &[(u32, u32, u32, u32, u32)], index_version: f32) -> Vec<u8> {
    let mut bytes = Vec::new();
    for (type_id, group_id, instance_id, resource_id, decompressed_size) in records {
        bytes.extend_from_slice(&type_id.to_le_bytes());
        bytes.extend_from_slice(&group_id.to_le_bytes());
        bytes.extend_from_slice(&instance_id.to_le_bytes());
        if index_version >= 7.2 {
            bytes.extend_from_slice(&resource_id.to_le_bytes());
        }
        bytes.extend_from_slice(&decompressed_size.to_le_bytes());
    }
    bytes
}

fn read_u32(bytes: &[u8], offset: usize) -> Result<u32> {
    if offset + 4 > bytes.len() {
        return Err(PatchError::InvalidDbpf(
            "unexpected end of file".to_string(),
        ));
    }
    Ok(u32::from_le_bytes([
        bytes[offset],
        bytes[offset + 1],
        bytes[offset + 2],
        bytes[offset + 3],
    ]))
}

fn write_u32(writer: &mut impl Write, value: u32) -> Result<()> {
    writer.write_all(&value.to_le_bytes())?;
    Ok(())
}

fn write_u32_at(bytes: &mut [u8], offset: usize, value: u32) -> Result<()> {
    if offset + 4 > bytes.len() {
        return Err(PatchError::InvalidDbpf(
            "header write outside package".to_string(),
        ));
    }
    bytes[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_fixture_package() {
        let path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../tests/files/test.package"
        );
        let package = DbpfPackage::open(path).unwrap();
        assert_eq!(package.header.dbpf_version(), 1.1);
        assert_eq!(package.header.index_version(), 7.1);
        assert_eq!(package.entries.len(), 9);
        assert_eq!(
            package
                .entries
                .iter()
                .filter(|entry| entry.compressed)
                .count(),
            7
        );
    }

    #[test]
    fn reads_index_7_2_resource_ids() {
        let path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../tests/files/index_7.2_compressed.package"
        );
        let package = DbpfPackage::open(path).unwrap();
        assert_eq!(package.header.index_version(), 7.2);
        assert!(package
            .entries
            .iter()
            .any(|entry| entry.resource_id == 0x40 && entry.compressed));
    }
}
