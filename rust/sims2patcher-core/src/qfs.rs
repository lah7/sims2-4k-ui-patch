use std::collections::HashMap;

use crate::error::{PatchError, Result};

const MAX_OFFSET: usize = 0x20000;
const MAX_COPY_COUNT: usize = 0x404;
pub const DEFAULT_MAX_ITER: usize = 20;

fn copy_array(
    src: &[u8],
    src_pos: usize,
    dest: &mut [u8],
    dest_pos: usize,
    length: usize,
) -> Result<()> {
    if src_pos + length > src.len() || dest_pos + length > dest.len() {
        return Err(PatchError::ArrayTooSmall);
    }
    dest[dest_pos..dest_pos + length].copy_from_slice(&src[src_pos..src_pos + length]);
    Ok(())
}

fn offset_copy(array: &mut [u8], offset: usize, dest_pos: usize, length: usize) -> Result<()> {
    let src_pos = dest_pos
        .checked_sub(offset)
        .ok_or(PatchError::ArrayTooSmall)?;
    if dest_pos + length > array.len() || src_pos >= array.len() {
        return Err(PatchError::ArrayTooSmall);
    }

    for i in 0..length {
        if src_pos + i >= array.len() || dest_pos + i >= array.len() {
            return Err(PatchError::ArrayTooSmall);
        }
        array[dest_pos + i] = array[src_pos + i];
    }
    Ok(())
}

pub fn decompress(compressed_data: &[u8], decompressed_size: usize) -> Result<Vec<u8>> {
    if compressed_data.len() < 9
        || u16::from_le_bytes([compressed_data[4], compressed_data[5]]) != 0xFB10
    {
        return Err(PatchError::InvalidMagicHeader);
    }

    let mut decompressed_data = vec![0_u8; decompressed_size];
    let mut dest_pos = 0_usize;
    let mut pos = 9_usize;
    let mut control1 = 0_u8;

    while control1 < 0xFC && pos < compressed_data.len() {
        control1 = compressed_data[pos];
        pos += 1;

        if control1 <= 127 {
            if pos >= compressed_data.len() {
                return Err(PatchError::ArrayTooSmall);
            }
            let control2 = compressed_data[pos];
            pos += 1;
            let num_plain_text = (control1 & 0x03) as usize;
            copy_array(
                compressed_data,
                pos,
                &mut decompressed_data,
                dest_pos,
                num_plain_text,
            )?;
            dest_pos += num_plain_text;
            pos += num_plain_text;
            let offset = (((control1 & 0x60) as usize) << 3) + control2 as usize + 1;
            let num_to_copy_from_offset = (((control1 & 0x1C) >> 2) as usize) + 3;
            offset_copy(
                &mut decompressed_data,
                offset,
                dest_pos,
                num_to_copy_from_offset,
            )?;
            dest_pos += num_to_copy_from_offset;
        } else if control1 <= 191 {
            if pos + 1 >= compressed_data.len() {
                return Err(PatchError::ArrayTooSmall);
            }
            let control2 = compressed_data[pos];
            pos += 1;
            let control3 = compressed_data[pos];
            pos += 1;
            let num_plain_text = ((control2 >> 6) & 0x03) as usize;
            copy_array(
                compressed_data,
                pos,
                &mut decompressed_data,
                dest_pos,
                num_plain_text,
            )?;
            dest_pos += num_plain_text;
            pos += num_plain_text;
            let offset = (((control2 & 0x3F) as usize) << 8) + control3 as usize + 1;
            let num_to_copy_from_offset = ((control1 & 0x3F) as usize) + 4;
            offset_copy(
                &mut decompressed_data,
                offset,
                dest_pos,
                num_to_copy_from_offset,
            )?;
            dest_pos += num_to_copy_from_offset;
        } else if control1 <= 223 {
            if pos + 2 >= compressed_data.len() {
                return Err(PatchError::ArrayTooSmall);
            }
            let num_plain_text = (control1 & 0x03) as usize;
            let control2 = compressed_data[pos];
            pos += 1;
            let control3 = compressed_data[pos];
            pos += 1;
            let control4 = compressed_data[pos];
            pos += 1;
            copy_array(
                compressed_data,
                pos,
                &mut decompressed_data,
                dest_pos,
                num_plain_text,
            )?;
            dest_pos += num_plain_text;
            pos += num_plain_text;
            let offset = (((control1 & 0x10) as usize) << 12)
                + ((control2 as usize) << 8)
                + control3 as usize
                + 1;
            let num_to_copy_from_offset =
                (((control1 & 0x0C) as usize) << 6) + control4 as usize + 5;
            offset_copy(
                &mut decompressed_data,
                offset,
                dest_pos,
                num_to_copy_from_offset,
            )?;
            dest_pos += num_to_copy_from_offset;
        } else if control1 <= 251 {
            let num_plain_text = (((control1 & 0x1F) as usize) << 2) + 4;
            copy_array(
                compressed_data,
                pos,
                &mut decompressed_data,
                dest_pos,
                num_plain_text,
            )?;
            dest_pos += num_plain_text;
            pos += num_plain_text;
        } else {
            let num_plain_text = (control1 & 0x03) as usize;
            copy_array(
                compressed_data,
                pos,
                &mut decompressed_data,
                dest_pos,
                num_plain_text,
            )?;
            dest_pos += num_plain_text;
            pos += num_plain_text;
        }
    }

    Ok(decompressed_data)
}

pub fn compress(data: &[u8], max_iter: usize) -> Result<Vec<u8>> {
    if data.len() > 16 * 1024 * 1024 {
        return Err(PatchError::FileTooLarge(data.len()));
    }

    let mut cmpmap: HashMap<u32, Vec<usize>> = HashMap::new();
    let mut output = vec![0_u8; 9];
    let mut last_read_index = 0_usize;
    let mut copy_offset = 0_usize;
    let mut index: isize = -1;
    let mut end = false;

    while index < data.len() as isize - 3 {
        let index_list: Vec<usize>;
        loop {
            index += 1;
            if index as usize >= data.len().saturating_sub(2) {
                end = true;
                index_list = Vec::new();
                break;
            }

            let i = index as usize;
            let map_index =
                (data[i] as u32) | ((data[i + 1] as u32) << 8) | ((data[i + 2] as u32) << 16);
            let list = cmpmap.entry(map_index).or_default();
            list.push(i);
            if i >= last_read_index {
                index_list = list.clone();
                break;
            }
        }

        if end {
            break;
        }

        let i = index as usize;
        let mut offset_copy_count = 0_usize;
        let mut loop_index = 1_usize;
        while loop_index < index_list.len() && loop_index < max_iter {
            let found_index = index_list[index_list.len() - 1 - loop_index];
            if i - found_index >= MAX_OFFSET {
                break;
            }
            loop_index += 1;
            let mut copy_count = 3_usize;
            while data.len() > i + copy_count
                && data[i + copy_count] == data[found_index + copy_count]
                && copy_count < MAX_COPY_COUNT
            {
                copy_count += 1;
            }
            if copy_count > offset_copy_count {
                offset_copy_count = copy_count;
                copy_offset = i - found_index;
            }
        }

        if offset_copy_count > data.len() - i {
            offset_copy_count = data.len() - i;
        }
        if offset_copy_count <= 2 {
            offset_copy_count = 0;
        } else if offset_copy_count == 3 && copy_offset > 0x400 {
            offset_copy_count = 0;
        } else if offset_copy_count == 4 && copy_offset > 0x4000 {
            offset_copy_count = 0;
        }

        if offset_copy_count > 0 {
            while i - last_read_index >= 4 {
                let mut copy_count = (i - last_read_index) / 4 - 1;
                if copy_count > 0x1B {
                    copy_count = 0x1B;
                }

                output.push(0xE0 + copy_count as u8);
                copy_count = 4 * copy_count + 4;
                output.extend_from_slice(&data[last_read_index..last_read_index + copy_count]);
                last_read_index += copy_count;
            }

            let copy_count = i - last_read_index;
            let encoded_offset = copy_offset - 1;
            if offset_copy_count <= 0x0A && encoded_offset < 0x400 {
                output.push(
                    (((encoded_offset >> 8) << 5) + ((offset_copy_count - 3) << 2) + copy_count)
                        as u8,
                );
                output.push((encoded_offset & 0xff) as u8);
            } else if offset_copy_count <= 0x43 && encoded_offset < 0x4000 {
                output.push(0x80 + (offset_copy_count - 4) as u8);
                output.push(((copy_count << 6) + (encoded_offset >> 8)) as u8);
                output.push((encoded_offset & 0xff) as u8);
            } else if offset_copy_count <= MAX_COPY_COUNT && encoded_offset < MAX_OFFSET {
                output.push(
                    (0xC0
                        + ((encoded_offset >> 16) << 4)
                        + (((offset_copy_count - 5) >> 8) << 2)
                        + copy_count) as u8,
                );
                output.push(((encoded_offset >> 8) & 0xff) as u8);
                output.push((encoded_offset & 0xff) as u8);
                output.push(((offset_copy_count - 5) & 0xff) as u8);
            }

            output.extend_from_slice(&data[last_read_index..last_read_index + copy_count]);
            last_read_index += copy_count + offset_copy_count;
        }
    }

    let index = data.len();
    while index - last_read_index >= 4 {
        let mut copy_count = (index - last_read_index) / 4 - 1;
        if copy_count > 0x1B {
            copy_count = 0x1B;
        }
        output.push(0xE0 + copy_count as u8);
        copy_count = 4 * copy_count + 4;
        output.extend_from_slice(&data[last_read_index..last_read_index + copy_count]);
        last_read_index += copy_count;
    }

    let copy_count = index - last_read_index;
    output.push(0xFC + copy_count as u8);
    output.extend_from_slice(&data[last_read_index..last_read_index + copy_count]);

    let compressed_size = output.len() as u32;
    output[0..4].copy_from_slice(&compressed_size.to_le_bytes());
    output[4..6].copy_from_slice(&0xFB10_u16.to_le_bytes());
    let size = data.len() as u32;
    output[6] = ((size >> 16) & 0xff) as u8;
    output[7] = ((size >> 8) & 0xff) as u8;
    output[8] = (size & 0xff) as u8;

    if output.len() > data.len() {
        return Ok(data.to_vec());
    }

    Ok(output)
}

pub fn compress_if_beneficial(
    data: &[u8],
    max_iter: usize,
    verify: bool,
) -> Result<Option<Vec<u8>>> {
    if data.len() >= 16 * 1024 * 1024 {
        return Ok(None);
    }

    let compressed = compress(data, max_iter)?;
    if compressed.len() >= data.len() || compressed.get(4..6) != Some(&[0x10, 0xFB][..]) {
        return Ok(None);
    }

    if verify && decompress(&compressed, data.len())? != data {
        return Ok(None);
    }

    Ok(Some(compressed))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn decompress_known_payload() {
        let expected = b"AAABBBCCCAAAAAABBBCCCDDDAAABBBABABAB";
        let original =
            b" \x00\x00\x00\x10\xfb\x00\x00\x00\xe1AAABBBCC\x01\x08C\x18\x0b\x0f\x0bDDD\t\x01A\xfc";
        assert_eq!(decompress(original, expected.len()).unwrap(), expected);
    }

    #[test]
    fn compress_round_trip() {
        let original = b"AAABBBCCCAAAAAABBBCCCDDDAAABBBABABAB";
        let output = compress(original, DEFAULT_MAX_ITER).unwrap();
        assert_ne!(output, original);
        assert_eq!(decompress(&output, original.len()).unwrap(), original);
    }

    #[test]
    fn incompressible_returns_original() {
        let original = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()";
        assert_eq!(compress(original, DEFAULT_MAX_ITER).unwrap(), original);
    }

    #[test]
    fn invalid_header() {
        assert!(matches!(
            decompress(b"abcdefghi", 8),
            Err(PatchError::InvalidMagicHeader)
        ));
    }
}
