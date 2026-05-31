use std::io::{Cursor, Read};
use std::path::Path;

use image::imageops::FilterType;
use image::{DynamicImage, ImageFormat, Rgb, RgbImage};
use rayon::prelude::*;

use crate::dbpf::{DbpfPackage, Entry, TYPE_IMAGE, TYPE_UI_DATA};
use crate::error::{PatchError, Result};
use crate::qfs;
use crate::uiscript;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum StorageMode {
    FastCompatible,
    Compact,
    None,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ImageFilter {
    Nearest,
    Hamming,
    Linear,
    Cubic,
    Lanczos,
}

#[derive(Clone, Debug)]
pub struct PatchOptions {
    pub scale: f32,
    pub storage: StorageMode,
    pub image_filter: ImageFilter,
    pub loading_screen_fps: u32,
    pub threads: usize,
    pub qfs_level: usize,
    pub verify_compression: bool,
}

impl Default for PatchOptions {
    fn default() -> Self {
        Self {
            scale: 2.0,
            storage: StorageMode::FastCompatible,
            image_filter: ImageFilter::Nearest,
            loading_screen_fps: 45,
            threads: std::thread::available_parallelism()
                .map(|value| value.get())
                .unwrap_or(1),
            qfs_level: qfs::DEFAULT_MAX_ITER,
            verify_compression: cfg!(debug_assertions),
        }
    }
}

#[derive(Clone, Debug, Default)]
pub struct PatchStats {
    pub processed_entries: usize,
    pub modified_entries: usize,
    pub skipped_entries: usize,
    pub warnings: Vec<String>,
}

#[derive(Clone, Debug)]
pub struct ProgressEvent {
    pub current: usize,
    pub total: usize,
    pub message: String,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ImageKind {
    Bmp,
    Jpeg,
    Png,
    Tga,
    Unknown,
}

struct EntryPatchResult {
    index: usize,
    modified: Option<Vec<u8>>,
    force_uncompressed: bool,
    skipped: bool,
    warning: Option<String>,
}

pub fn patch_package(
    source_path: impl AsRef<Path>,
    target_path: impl AsRef<Path>,
    filename: &str,
    options: PatchOptions,
    mut progress: impl FnMut(ProgressEvent),
) -> Result<PatchStats> {
    let mut package = DbpfPackage::open(source_path)?;
    let indices = package.patchable_indices();
    let total = indices.len();
    progress(ProgressEvent {
        current: 0,
        total,
        message: "package opened".to_string(),
    });

    let tasks = indices
        .iter()
        .map(|index| (*index, package.entries[*index].clone()))
        .collect::<Vec<_>>();

    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(options.threads.max(1))
        .build()
        .map_err(|err| PatchError::Unsupported(format!("could not create worker pool: {err}")))?;

    let results = pool.install(|| {
        tasks
            .into_par_iter()
            .map(|(index, entry)| process_entry(index, entry, filename, options.clone()))
            .collect::<Vec<_>>()
    });

    let mut stats = PatchStats::default();
    for result in results {
        let result = result?;
        stats.processed_entries += 1;
        if let Some(warning) = result.warning {
            stats.warnings.push(warning);
        }
        if result.skipped {
            stats.skipped_entries += 1;
        }
        if let Some(data) = result.modified {
            package.entries[result.index].set_modified(data, result.force_uncompressed);
            stats.modified_entries += 1;
        }
        progress(ProgressEvent {
            current: stats.processed_entries,
            total,
            message: "entry processed".to_string(),
        });
    }

    let modified_only = filename.eq_ignore_ascii_case("objects.package");
    package.save(
        target_path,
        options.storage,
        options.qfs_level,
        options.verify_compression,
        modified_only,
    )?;

    progress(ProgressEvent {
        current: total,
        total,
        message: "package written".to_string(),
    });

    Ok(stats)
}

pub fn patch_fontstyle_ini(
    source_path: impl AsRef<Path>,
    target_path: impl AsRef<Path>,
    scale: f32,
) -> Result<()> {
    let input = std::fs::read_to_string(source_path)?;
    let mut output = String::new();

    for line in input.lines() {
        let mut parts = line.split('"').map(str::to_string).collect::<Vec<_>>();
        if parts.len() >= 6 {
            let old_size = parts[3].parse::<f32>()?;
            parts[3] = ((old_size * scale) as i32).to_string();
            output.push_str(&parts.join("\""));
        } else {
            output.push_str(line);
        }
        output.push('\n');
    }

    if input.ends_with('\n') {
        std::fs::write(target_path, output)?;
    } else {
        output.pop();
        std::fs::write(target_path, output)?;
    }
    Ok(())
}

fn process_entry(
    index: usize,
    entry: Entry,
    filename: &str,
    options: PatchOptions,
) -> Result<EntryPatchResult> {
    if entry.type_id == TYPE_UI_DATA {
        let data = entry.data_safe();
        if data.starts_with(b"RIFF") {
            let modified = upscale_loading_screen(
                &data,
                options.scale,
                options.image_filter,
                options.loading_screen_fps,
            )?;
            return Ok(EntryPatchResult {
                index,
                modified: Some(modified),
                force_uncompressed: false,
                skipped: false,
                warning: None,
            });
        }
        let modified = upscale_uiscript(&entry, options.scale)?;
        return Ok(EntryPatchResult {
            index,
            modified: Some(modified),
            force_uncompressed: false,
            skipped: false,
            warning: None,
        });
    }

    if entry.type_id == TYPE_IMAGE {
        let mut force_uncompressed = false;

        if filename.eq_ignore_ascii_case("objects.package") {
            match image_file_type(&entry.data_safe()) {
                ImageKind::Tga => force_uncompressed = true,
                ImageKind::Unknown => {
                    return Ok(EntryPatchResult {
                        index,
                        modified: None,
                        force_uncompressed: false,
                        skipped: true,
                        warning: Some(format!(
                            "skipping unknown objects.package image {:x}/{:x}",
                            entry.group_id, entry.instance_id
                        )),
                    });
                }
                _ => {
                    return Ok(EntryPatchResult {
                        index,
                        modified: None,
                        force_uncompressed: false,
                        skipped: true,
                        warning: None,
                    });
                }
            }
        }

        match upscale_graphic(&entry, options.scale, options.image_filter) {
            Ok(modified) => Ok(EntryPatchResult {
                index,
                modified: Some(modified),
                force_uncompressed,
                skipped: false,
                warning: None,
            }),
            Err(PatchError::Unsupported(message)) => Ok(EntryPatchResult {
                index,
                modified: None,
                force_uncompressed: false,
                skipped: true,
                warning: Some(message),
            }),
            Err(err) => Err(err),
        }
    } else {
        Ok(EntryPatchResult {
            index,
            modified: None,
            force_uncompressed: false,
            skipped: true,
            warning: None,
        })
    }
}

fn image_file_type(data: &[u8]) -> ImageKind {
    let start = &data[..data.len().min(4)];
    if start.starts_with(&[0x00, 0x00, 0x02]) || start.starts_with(&[0x00, 0x00, 0x0A]) {
        ImageKind::Tga
    } else if start.starts_with(b"BM") {
        ImageKind::Bmp
    } else if start.starts_with(&[0xff, 0xd8, 0xff]) {
        ImageKind::Jpeg
    } else if start.starts_with(b"\x89PNG") {
        ImageKind::Png
    } else {
        ImageKind::Unknown
    }
}

fn image_format(kind: ImageKind) -> Result<ImageFormat> {
    match kind {
        ImageKind::Bmp => Ok(ImageFormat::Bmp),
        ImageKind::Jpeg => Ok(ImageFormat::Jpeg),
        ImageKind::Png => Ok(ImageFormat::Png),
        ImageKind::Tga => Ok(ImageFormat::Tga),
        ImageKind::Unknown => Err(PatchError::Unsupported("unknown image header".to_string())),
    }
}

fn filter_type(filter: ImageFilter) -> FilterType {
    match filter {
        ImageFilter::Nearest => FilterType::Nearest,
        ImageFilter::Hamming => FilterType::Triangle,
        ImageFilter::Linear => FilterType::Triangle,
        ImageFilter::Cubic => FilterType::CatmullRom,
        ImageFilter::Lanczos => FilterType::Lanczos3,
    }
}

fn upscale_graphic(entry: &Entry, scale: f32, filter: ImageFilter) -> Result<Vec<u8>> {
    let data = entry.data_safe();
    let kind = image_file_type(&data);
    if kind == ImageKind::Unknown {
        return Err(PatchError::Unsupported(format!(
            "unknown image header for {:x}/{:x}/{:x}",
            entry.type_id, entry.group_id, entry.instance_id
        )));
    }

    let graphic_id = (entry.group_id, entry.instance_id);
    if kind == ImageKind::Tga
        && matches!(
            graphic_id,
            (0x499d_b772, 0xa950_0615)
                | (0x499d_b772, 0xa950_0630)
                | (0x499d_b772, 0x1441_6190)
                | (0x499d_b772, 0x1441_6193)
                | (0x499d_b772, 0x1450_0140)
                | (0x499d_b772, 0x1450_0145)
                | (0x499d_b772, 0x1450_0157)
                | (0x499d_b772, 0x1450_0150)
        )
    {
        return Ok(data);
    }

    let format = image_format(kind)?;
    let original = image::load_from_memory_with_format(&data, format)?;
    let resized = resize_image(original, scale, filter);
    let mut output = Cursor::new(Vec::new());
    resized.write_to(&mut output, format)?;
    Ok(output.into_inner())
}

fn resize_image(image: DynamicImage, scale: f32, filter: ImageFilter) -> DynamicImage {
    let width = ((image.width() as f32) * scale) as u32;
    let height = ((image.height() as f32) * scale) as u32;
    image.resize_exact(width, height, filter_type(filter))
}

struct ReiaVideo {
    width: u32,
    height: u32,
    frames_per_second: f32,
    frames: Vec<RgbImage>,
}

fn upscale_loading_screen(
    data: &[u8],
    scale: f32,
    filter: ImageFilter,
    frames_per_second: u32,
) -> Result<Vec<u8>> {
    let video = read_reia(data)?;
    let width = ((video.width as f32) * scale) as u32;
    let height = ((video.height as f32) * scale) as u32;
    let frames = video
        .frames
        .iter()
        .map(|frame| image::imageops::resize(frame, width, height, filter_type(filter)))
        .collect::<Vec<_>>();

    write_reia(&ReiaVideo {
        width,
        height,
        frames_per_second: frames_per_second as f32,
        frames,
    })
}

fn read_reia(data: &[u8]) -> Result<ReiaVideo> {
    let mut cursor = Cursor::new(data);
    expect_magic(&mut cursor, b"RIFF")?;
    let _file_size = read_u32(&mut cursor)?;
    expect_magic(&mut cursor, b"Reiahead")?;

    let metadata_size = read_u32(&mut cursor)?;
    if metadata_size != 24 {
        return Err(PatchError::Unsupported(format!(
            "unsupported REIA metadata size: {metadata_size}"
        )));
    }

    let always_one = read_u32(&mut cursor)?;
    if always_one != 1 {
        return Err(PatchError::Unsupported(format!(
            "unsupported REIA header marker: {always_one}"
        )));
    }

    let width = read_u32(&mut cursor)?;
    let height = read_u32(&mut cursor)?;
    let fps_numerator = read_u32(&mut cursor)?;
    let fps_denominator = read_u32(&mut cursor)?;
    if fps_denominator == 0 {
        return Err(PatchError::Unsupported(
            "REIA frame-rate denominator is zero".to_string(),
        ));
    }
    let frames_per_second = fps_numerator as f32 / fps_denominator as f32;
    let frame_count = read_u32(&mut cursor)?;

    let mut frames = Vec::with_capacity(frame_count as usize);
    let mut previous = None;
    for _ in 0..frame_count {
        if cursor.position() >= data.len() as u64 {
            break;
        }
        expect_magic(&mut cursor, b"frme")?;
        let frame_size = read_u32(&mut cursor)?;
        let frame = read_reia_frame(&mut cursor, width, height, previous.as_ref())?;
        if frame_size % 2 != 0 {
            let mut padding = [0; 1];
            cursor.read_exact(&mut padding)?;
        }
        previous = Some(frame.clone());
        frames.push(frame);
    }

    Ok(ReiaVideo {
        width,
        height,
        frames_per_second,
        frames,
    })
}

fn read_reia_frame(
    cursor: &mut Cursor<&[u8]>,
    width: u32,
    height: u32,
    previous: Option<&RgbImage>,
) -> Result<RgbImage> {
    let mut frame = RgbImage::new(width, height);
    let width_blocks = width.div_ceil(32);
    let height_blocks = height.div_ceil(32);

    for block_y in 0..height_blocks {
        for block_x in 0..width_blocks {
            let mut marker = [0; 1];
            cursor.read_exact(&mut marker)?;
            let x = block_x * 32;
            let y = block_y * 32;
            if marker[0] != 0 {
                let mut block = read_reia_block(cursor)?;
                if let Some(previous_frame) = previous {
                    let previous_block = crop_block(previous_frame, x, y);
                    block = add_modulo(&block, &previous_block);
                }
                paste_block(&mut frame, &block, x, y);
            } else {
                let Some(previous_frame) = previous else {
                    return Err(PatchError::Unsupported(
                        "REIA block references previous frame but no previous frame exists"
                            .to_string(),
                    ));
                };
                paste_block(&mut frame, &crop_block(previous_frame, x, y), x, y);
            }
        }
    }

    Ok(frame)
}

fn read_reia_block(cursor: &mut Cursor<&[u8]>) -> Result<RgbImage> {
    let mut image = RgbImage::new(32, 32);
    let mut pixel_index = 0usize;
    while pixel_index < 32 * 32 {
        let mut rle = [0; 1];
        cursor.read_exact(&mut rle)?;
        let rle_value = i8::from_ne_bytes(rle);
        if rle_value < 0 {
            let repeat_count = rle_value.unsigned_abs() as usize + 1;
            let pixel = read_bgr_pixel(cursor)?;
            for _ in 0..repeat_count {
                put_block_pixel(&mut image, pixel_index, pixel);
                pixel_index += 1;
            }
        } else {
            let unique_count = (rle_value as usize) + 1;
            for _ in 0..unique_count {
                let pixel = read_bgr_pixel(cursor)?;
                put_block_pixel(&mut image, pixel_index, pixel);
                pixel_index += 1;
            }
        }
    }
    Ok(image)
}

fn write_reia(video: &ReiaVideo) -> Result<Vec<u8>> {
    let mut output = Vec::new();
    output.extend_from_slice(b"RIFF");
    output.extend_from_slice(&0u32.to_le_bytes());
    output.extend_from_slice(b"Reiahead");
    output.extend_from_slice(&24u32.to_le_bytes());
    output.extend_from_slice(&1u32.to_le_bytes());
    output.extend_from_slice(&video.width.to_le_bytes());
    output.extend_from_slice(&video.height.to_le_bytes());

    let fps_numerator: u32 = if (video.frames_per_second - 10.0).abs() < f32::EPSILON {
        10
    } else {
        1_000_000
    };
    let fps_denominator = (fps_numerator as f32 / video.frames_per_second) as u32;
    output.extend_from_slice(&fps_numerator.to_le_bytes());
    output.extend_from_slice(&fps_denominator.to_le_bytes());
    output.extend_from_slice(&(video.frames.len() as u32).to_le_bytes());

    let mut previous = None;
    for frame in &video.frames {
        let encoded = write_reia_frame(frame, previous.as_ref());
        output.extend_from_slice(b"frme");
        output.extend_from_slice(&(encoded.len() as u32).to_le_bytes());
        output.extend_from_slice(&encoded);
        if encoded.len() % 2 != 0 {
            output.push(0);
        }
        previous = Some(frame.clone());
    }

    let file_size = (output.len() - 8) as u32;
    output[4..8].copy_from_slice(&file_size.to_le_bytes());
    Ok(output)
}

fn write_reia_frame(frame: &RgbImage, previous: Option<&RgbImage>) -> Vec<u8> {
    let mut output = Vec::new();
    let width_blocks = frame.width().div_ceil(32);
    let height_blocks = frame.height().div_ceil(32);
    for block_y in 0..height_blocks {
        for block_x in 0..width_blocks {
            let x = block_x * 32;
            let y = block_y * 32;
            let current_block = crop_block(frame, x, y);
            let previous_block = previous.map(|previous_frame| crop_block(previous_frame, x, y));
            output.extend(write_reia_block(&current_block, previous_block.as_ref()));
        }
    }
    output
}

fn write_reia_block(block: &RgbImage, previous: Option<&RgbImage>) -> Vec<u8> {
    if let Some(previous_block) = previous {
        if block.as_raw() == previous_block.as_raw() {
            return vec![0];
        }
    }

    let block = previous
        .map(|previous_block| subtract_modulo(block, previous_block))
        .unwrap_or_else(|| block.clone());
    let mut output = vec![1];

    let mut unique_pixels = Vec::with_capacity(128);
    let mut pixel_index = 0usize;
    while pixel_index < 32 * 32 {
        let color = block_pixel_bgr(&block, pixel_index);
        let mut run_length = 1usize;
        while pixel_index + run_length < 32 * 32
            && block_pixel_bgr(&block, pixel_index + run_length) == color
        {
            run_length += 1;
        }

        if run_length > 1 {
            emit_reia_unique_pixels(&mut output, &mut unique_pixels);
            emit_reia_repeated_pixel(&mut output, color, run_length);
            pixel_index += run_length;
        } else {
            unique_pixels.push(color);
            if unique_pixels.len() == 128 {
                emit_reia_unique_pixels(&mut output, &mut unique_pixels);
            }
            pixel_index += 1;
        }
    }
    emit_reia_unique_pixels(&mut output, &mut unique_pixels);

    output
}

fn block_pixel_bgr(block: &RgbImage, pixel_index: usize) -> [u8; 3] {
    let pixel = block.get_pixel((pixel_index % 32) as u32, (pixel_index / 32) as u32);
    [pixel[2], pixel[1], pixel[0]]
}

fn emit_reia_repeated_pixel(output: &mut Vec<u8>, color: [u8; 3], mut count: usize) {
    while count > 0 {
        let chunk = count.min(129);
        output.push((-(chunk as i16 - 1) as i8) as u8);
        output.extend_from_slice(&color);
        count -= chunk;
    }
}

fn emit_reia_unique_pixels(output: &mut Vec<u8>, unique_pixels: &mut Vec<[u8; 3]>) {
    for chunk in unique_pixels.chunks(128) {
        output.push((chunk.len() - 1) as u8);
        for color in chunk {
            output.extend_from_slice(color);
        }
    }
    unique_pixels.clear();
}

fn add_modulo(block: &RgbImage, previous: &RgbImage) -> RgbImage {
    combine_modulo(block, previous, u8::wrapping_add)
}

fn subtract_modulo(block: &RgbImage, previous: &RgbImage) -> RgbImage {
    combine_modulo(block, previous, u8::wrapping_sub)
}

fn combine_modulo(left: &RgbImage, right: &RgbImage, operation: fn(u8, u8) -> u8) -> RgbImage {
    let mut output = RgbImage::new(32, 32);
    for y in 0..32 {
        for x in 0..32 {
            let a = left.get_pixel(x, y);
            let b = right.get_pixel(x, y);
            output.put_pixel(
                x,
                y,
                Rgb([
                    operation(a[0], b[0]),
                    operation(a[1], b[1]),
                    operation(a[2], b[2]),
                ]),
            );
        }
    }
    output
}

fn crop_block(image: &RgbImage, x: u32, y: u32) -> RgbImage {
    let mut block = RgbImage::new(32, 32);
    for block_y in 0..32 {
        for block_x in 0..32 {
            let source_x = x + block_x;
            let source_y = y + block_y;
            if source_x < image.width() && source_y < image.height() {
                block.put_pixel(block_x, block_y, *image.get_pixel(source_x, source_y));
            }
        }
    }
    block
}

fn paste_block(image: &mut RgbImage, block: &RgbImage, x: u32, y: u32) {
    for block_y in 0..32 {
        for block_x in 0..32 {
            let target_x = x + block_x;
            let target_y = y + block_y;
            if target_x < image.width() && target_y < image.height() {
                image.put_pixel(target_x, target_y, *block.get_pixel(block_x, block_y));
            }
        }
    }
}

fn put_block_pixel(image: &mut RgbImage, pixel_index: usize, pixel: Rgb<u8>) {
    if pixel_index < 32 * 32 {
        image.put_pixel((pixel_index % 32) as u32, (pixel_index / 32) as u32, pixel);
    }
}

fn read_bgr_pixel(cursor: &mut Cursor<&[u8]>) -> Result<Rgb<u8>> {
    let mut pixel = [0; 3];
    cursor.read_exact(&mut pixel)?;
    Ok(Rgb([pixel[2], pixel[1], pixel[0]]))
}

fn read_u32(cursor: &mut Cursor<&[u8]>) -> Result<u32> {
    let mut bytes = [0; 4];
    cursor.read_exact(&mut bytes)?;
    Ok(u32::from_le_bytes(bytes))
}

fn expect_magic(cursor: &mut Cursor<&[u8]>, expected: &[u8]) -> Result<()> {
    let mut actual = vec![0; expected.len()];
    cursor.read_exact(&mut actual)?;
    if actual != expected {
        return Err(PatchError::Unsupported(format!(
            "invalid REIA magic: expected {:?}, got {:?}",
            String::from_utf8_lossy(expected),
            String::from_utf8_lossy(&actual)
        )));
    }
    Ok(())
}

fn upscale_uiscript(entry: &Entry, scale: f32) -> Result<Vec<u8>> {
    let script_id = (entry.group_id, entry.instance_id);
    if matches!(
        script_id,
        (0xa99d_8a11, 0xffff_fff0)
            | (0xa99d_8a11, 0xffff_fff1)
            | (0xa99d_8a11, 0xffff_fff3)
            | (0xa99d_8a11, 0x8baf_f56f)
    ) || entry.group_id == 0x0800_0600
    {
        return Ok(entry.data_safe());
    }

    let data = String::from_utf8(entry.data_safe())?;
    let mut root = uiscript::serialize(&data)?;
    root.visit_elements_mut(&mut |element| {
        fix_uiscript_element_attributes(script_id, element);

        for attribute in &mut element.attributes {
            if matches!(attribute.key.as_str(), "area" | "gutters" | "imagerect") {
                if let Some(new_value) = upscale_tuple(&attribute.value, scale) {
                    attribute.value = new_value;
                }
            } else if attribute.key == "caption"
                && attribute.value.starts_with('k')
                && attribute.value.contains('=')
            {
                attribute.value = patched_constant(&attribute.value, scale);
            }
        }
    });

    Ok(uiscript::deserialize(&root).into_bytes())
}

fn upscale_tuple(value: &str, scale: f32) -> Option<String> {
    let inner = value.strip_prefix('(')?.strip_suffix(')')?;
    let mut parts = Vec::new();
    for part in inner.split(',') {
        let number = part.trim().parse::<f32>().ok()?;
        parts.push(((number as i32) as f32 * scale) as i32);
    }
    Some(format!(
        "({})",
        parts
            .iter()
            .map(ToString::to_string)
            .collect::<Vec<_>>()
            .join(",")
    ))
}

fn patched_constant(caption: &str, scale: f32) -> String {
    let Some((key, value)) = caption.split_once('=') else {
        return caption.to_string();
    };

    const SCALED_KEYS: &[&str] = &[
        "kListBoxRowHeight",
        "kTrackSpacingY",
        "kCollapsedThumbMarginX",
        "kCollapsedThumbMarginY",
        "kExpandedThumbMarginX",
        "kExpandedThumbMarginY",
        "kIconMarginX",
        "kTopOffset",
        "kRightOffset",
        "kNotificationMargin",
        "kMaxWidth",
        "kVerticalSpacing",
        "kXMargin",
        "kYMargin",
        "kCancelBoundary",
        "kGesturePickBoundary",
        "kHeadAreaInflateForItemOverlap",
        "kItemRadius",
    ];

    if SCALED_KEYS.contains(&key) {
        if let Ok(number) = value.parse::<f32>() {
            return format!("{key}={}", (number * scale) as i32);
        }
    }

    caption.to_string()
}

fn fix_uiscript_element_attributes(script_id: (u32, u32), element: &mut uiscript::UiScriptElement) {
    if script_id == (0xa99d_8a11, 0x4906_4905) {
        if element.get("caption") == Some("Needs") {
            element.set("font", "GenHeader");
        }
    } else if script_id == (0xa99d_8a11, 0x4906_0003) || script_id == (0xa99d_8a11, 0x4906_0004) {
        if matches!(
            element.get("caption"),
            Some("info text" | "Roof Angle Chooser")
        ) {
            element.set("font", "DefaultFont14");
        }
    } else if script_id == (0xa99d_8a11, 0x2d91_050a) {
        match element.get("area") {
            Some("(18,12,315,46)" | "(18,13,315,53)") => element.set("font", "GenHeader"),
            Some("(18,43,315,109)" | "(18,63,315,133)" | "(18,11,305,45)") => {
                element.set("font", "GenSubHeader")
            }
            Some(
                "(75,241,307,267)" | "(75,291,307,317)" | "(75,121,307,147)" | "(75,141,307,167)"
                | "(75,191,307,217)" | "(31,74,289,101)",
            ) => element.set("font", "NeighborhoodButton"),
            Some("(105,123,147,156)") => element.set("font", "GenButton"),
            _ => {}
        }
    } else if matches!(
        script_id,
        (0xa99d_8a11, 0x4906_0f02) | (0x0800_0600, 0x4906_0f02)
    ) {
        if matches!(element.get("iid"), Some("IGZWinText" | "IGZWinBtn"))
            && element.get("caption").is_some()
        {
            element.set("font", "OptionsText");
        }
        if element.get("caption") == Some("Game Options") {
            element.set("font", "OptionsHeader");
        }
        if matches!(
            element.get("caption"),
            Some("Lot View Options" | "House-Specific Options")
        ) {
            element.set("font", "GenButton");
        }
        if element.get("area") == Some("(6,1,488,23)") {
            element.set("area", "(6,9,488,31)");
        } else if matches!(
            element.get("id"),
            Some("0x000000a8" | "0x000000a7" | "0x000000a6" | "0x000000aa")
        ) {
            if let Some(area) = element.get("area").and_then(offset_area_y) {
                element.set("area", area);
            }
        }
    } else if matches!(
        script_id,
        (0xa99d_8a11, 0x4906_0f06) | (0x0800_0600, 0x4906_0f06)
    ) {
        if matches!(element.get("iid"), Some("IGZWinText" | "IGZWinTextEdit"))
            && element.get("caption").is_some()
        {
            element.set("font", "NeighborhoodBody");
        }
        if element.get("caption") == Some("Game Tip Encyclopedia") {
            element.set("font", "OptionsHeader");
        }
    } else if script_id == (0xa99d_8a11, 0xfeed_2006) {
        if matches!(element.get("id"), Some("0x77e74b47" | "0x2d0a50a7")) {
            element.set("font", "LiveModePanelHeader");
        } else if matches!(
            element.get("id"),
            Some(
                "0x27e74b64"
                    | "0x47e74b6d"
                    | "0xec2cfcfd"
                    | "0x0c1fc411"
                    | "0x0c1fc412"
                    | "0x0c1fc413"
                    | "0x0c1fc414"
                    | "0x0c1fc415"
                    | "0x0c1fc416"
                    | "0x0c1fc417"
                    | "0x2d0a50a6"
                    | "0x71ecc381"
                    | "0x71ecc38b"
            )
        ) {
            element.set("font", "LiveModePanelBody");
        } else if element.get("id") == Some("0x0000d0a1") {
            element.set("font", "LiveModePanelSmallBody");
        } else if matches!(element.get("id"), Some("0xccc728cd" | "0x0c1fc419")) {
            element.set("font", "DefaultFont14");
        } else if element.get("id") == Some("0xabcd0002") {
            element.set("font", "OptionsText");
        }
        if element.get("clsid") == Some("0x4ca92f03") {
            element.set("font", "LiveModePanelSubHeader");
        }
        if matches!(
            element.get("captionres"),
            Some(
                "{7f96c284,00e80006}"
                    | "{7f96c284,00e80026}"
                    | "{7f96c284,00e80027}"
                    | "{7f96c284,00e80028}"
            )
        ) {
            element.set("font", "OptionsText");
        }
    } else if script_id == (0xa99d_8a11, 0x0bb4_0021) {
        if element.get("iid") == Some("IGZWinText") {
            element.set("font", "GenHeader");
        } else if element.get("id") == Some("0x00002002") {
            element.set("font", "GenSubHeader");
        } else if element.get("id") == Some("0x00002003") {
            element.set("font", "NeighborhoodBody");
        }
    } else if script_id == (0xa99d_8a11, 0x4906_0f03) && element.get("iid") == Some("IGZWinBMP") {
        if element.get("area") == Some("(1,17,111,102)") {
            element.set("area", "(1,17,111,113)");
        } else if element.get("area") == Some("(1,17,100,102)") {
            element.set("area", "(1,17,100,113)");
        }
    }
}

fn offset_area_y(area: &str) -> Option<String> {
    let inner = area.strip_prefix('(')?.strip_suffix(')')?;
    let mut parts = inner.split(',').map(str::trim);
    let x = parts.next()?.parse::<i32>().ok()?;
    let y = parts.next()?.parse::<i32>().ok()?;
    let width = parts.next()?.parse::<i32>().ok()?;
    let height = parts.next()?.parse::<i32>().ok()?;
    Some(format!("({x},{},{width},{height})", y + 10))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::dbpf::Entry;

    #[test]
    fn upscales_uiscript_and_adds_font() {
        let entry = Entry {
            type_id: TYPE_UI_DATA,
            group_id: 0xa99d_8a11,
            instance_id: 0x4906_4905,
            resource_id: 0,
            file_location: 0,
            file_size: 0,
            decompressed_size: 0,
            compressed: false,
            raw: b"# Test\r\n<LEGACY iid=IGZWinGen area=(5,10,15,20) >\r\n<LEGACY iid=IGZWinText caption=\"Needs\" >\r\n".to_vec(),
            modified: None,
        };
        let result = upscale_uiscript(&entry, 2.0).unwrap();
        assert_eq!(
            result,
            b"# Test\r\n<LEGACY iid=IGZWinGen area=(10,20,30,40) >\r\n<LEGACY iid=IGZWinText caption=\"Needs\" font=GenHeader >\r\n"
        );
    }

    #[test]
    fn detects_image_formats() {
        assert_eq!(image_file_type(b"BM1234"), ImageKind::Bmp);
        assert_eq!(image_file_type(b"\xff\xd8\xff\x00"), ImageKind::Jpeg);
        assert_eq!(image_file_type(b"\x89PNG"), ImageKind::Png);
        assert_eq!(image_file_type(b"\x00\x00\x02\x00"), ImageKind::Tga);
    }

    #[test]
    fn reia_loading_screen_round_trip_and_upscale() {
        let mut frame = RgbImage::new(16, 16);
        for y in 0..16 {
            for x in 0..16 {
                frame.put_pixel(x, y, Rgb([x as u8, y as u8, (x + y) as u8]));
            }
        }
        let mut second_frame = frame.clone();
        second_frame.put_pixel(3, 4, Rgb([200, 100, 50]));

        let encoded = write_reia(&ReiaVideo {
            width: 16,
            height: 16,
            frames_per_second: 10.0,
            frames: vec![frame.clone(), second_frame.clone()],
        })
        .unwrap();

        let decoded = read_reia(&encoded).unwrap();
        assert_eq!(decoded.width, 16);
        assert_eq!(decoded.height, 16);
        assert_eq!(decoded.frames.len(), 2);
        assert_eq!(decoded.frames[0].as_raw(), frame.as_raw());
        assert_eq!(decoded.frames[1].as_raw(), second_frame.as_raw());

        let upscaled = upscale_loading_screen(&encoded, 2.0, ImageFilter::Nearest, 45).unwrap();
        let decoded_upscaled = read_reia(&upscaled).unwrap();
        assert_eq!(decoded_upscaled.width, 32);
        assert_eq!(decoded_upscaled.height, 32);
        assert_eq!(decoded_upscaled.frames.len(), 2);
        assert!((decoded_upscaled.frames_per_second - 45.0).abs() < 0.01);
    }
}
