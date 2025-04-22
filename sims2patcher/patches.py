"""
Module containing that performs the patching to upscale user interface
elements for The Sims 2.

While graphic rules allow The Sims 2 to run at 4K, the user interface elements
are still at the original sizes. These modifications upscales the user
interface by doubling the density of graphics and fonts and adjusting UI geometry.
"""
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Copyright (C) 2022-2025 Luke Horwell <code@horwell.me>
#
import enum
import io
from typing import Callable

from PIL import Image

import submodules.SimsReiaParser.SimsReiaPy.sims_reia as sims_reia

from . import dbpf, errors, gamefile, uiscript

# Density to multiply the UI dialog geometry and graphics
UI_MULTIPLIER: float = 2.0

# Compression keeps the package files small, but takes longer to process
LEAVE_UNCOMPRESSED: bool = False

# Image upscaling filter
UPSCALE_FILTER: Image.Resampling = Image.Resampling.NEAREST


class ImageFormat(enum.Enum):
    """File extension for known image formats"""
    BMP = "BMP"
    JPEG = "JPEG"
    PNG = "PNG"
    TGA = "TGA"
    UNKNOWN = "Unknown"


def get_image_file_type(data: bytes) -> ImageFormat:
    """
    The file in the DBPF package is simply "Image File".
    Read the header to get the real file type.
    """
    # Check the first 4 bytes
    start = data[:4]

    if start[:3] in [b"\x00\x00\x02", b"\x00\x00\n"]:
        return ImageFormat.TGA
    elif start[:2] == b"BM":
        return ImageFormat.BMP
    elif start[:3] == b"\xff\xd8\xff":
        return ImageFormat.JPEG
    elif start[:4] == b"\x89PNG":
        return ImageFormat.PNG
    else:
        return ImageFormat.UNKNOWN


def _upscale_graphic(entry: dbpf.Entry) -> bytes:
    """
    Return binary data for an upscaled (or intact) image.

    Graphics could be a TGA, PNG, JPEG or BMP file. Most UI graphics are TGA (Targa).

    To upscale, multiply the width and height by UI_MULTIPLIER, so the UI
    is comfortably readable at double its original density.

    UPSCALE_FILTER may influence the resulting quality of the image.
    """
    file_type = get_image_file_type(entry.data_safe)

    if file_type == ImageFormat.UNKNOWN:
        raise errors.UnknownImageFormatError()

    # Skip images that are:
    # - Texture atlases ("spritesheet" / "9-slice") used by scalable UI elements
    # - Alpha masks with fixed dimensions, like overlays
    # - Images that seem to expect a fixed size
    graphic_id = (entry.group_id, entry.instance_id)
    if file_type == ImageFormat.TGA and graphic_id in [
        (0x499db772, 0xa9500615), # Dialog background (e.g. "Choose Lot Type", "Rename Lot")
        (0x499db772, 0xa9500630), # Dialog buttons
        (0x499db772, 0x14416190), # Tooltip background
        (0x499db772, 0x14416193), # Lot details popup background in neighbourhood
        # (0x499db772, 0x14500100), # Not sure
        (0x499db772, 0x14500140), # Assumed dialog button element
        (0x499db772, 0x14500145), # Assumed dialog button element
        (0x499db772, 0x14500157), # Assumed dialog button element
        (0x499db772, 0x14500150), # Not sure
    ]:
        return entry.data_safe

    original = Image.open(io.BytesIO(entry.data_safe), formats=[file_type.value])
    resized = original.resize((int(original.width * UI_MULTIPLIER), int(original.height * UI_MULTIPLIER)), resample=UPSCALE_FILTER)

    output = io.BytesIO()
    resized.save(output, format=file_type.value)
    return output.getvalue()


def _upscale_uiscript(entry: dbpf.Entry) -> bytes:
    """
    Return binary data for a modified .uiScript file.

    .uiScript is a modified XML file that specifies the dialog geometry and element positions.

    To upscale, multiply attributes with dimension/position values by UI_MULTIPLIER.
    """
    # Skip debugging UI
    script_id = (entry.group_id, entry.instance_id)
    if script_id in [
        (0xa99d8a11, 0xfffffff0), # Skin Browser
        (0xa99d8a11, 0xfffffff1), # Outfit Browser
        (0xa99d8a11, 0xfffffff3), # Cheat Object Browser
        (0xa99d8a11, 0x8baff56f), # UI Browser
    ]:
        return entry.data

    try:
        data: uiscript.UIScriptRoot = uiscript.serialize_uiscript(entry.data.decode("utf-8"))
    except UnicodeDecodeError:
        # Skip binary .uiScript file
        return entry.data

    def _patched_constant(caption: str):
        """
        The 'Constants Table' are text elements nested together holding
        key/value data in the "caption" attribute. Patch these to fix/improve
        dynamic UI controls, like listbox, notifications and pie menu.
        """
        key, value = caption.split("=")

        if key in [
            # List Box Items
            "kListBoxRowHeight",

            # Audio Options List / Radio Stations
            "kTrackSpacingY",

            # Object Catalog
            "kCollapsedThumbMarginX",
            "kCollapsedThumbMarginY",
            "kExpandedThumbMarginX",
            "kExpandedThumbMarginY",

            # Action Queue (0xa99d8a11 0xccd02691)
            "kIconMarginX",

            # Notifications (0xa99d8a11 0xccd02692)
            "kTopOffset",
            "kRightOffset",
            "kNotificationMargin",
            "kMaxWidth",

            # Family Tree (0xa99d8a11 0x49065190)
            "kVerticalSpacing",
            "kXMargin",
            "kYMargin",

            # Pie Menu (0xa99d8a11 0x90617b7)
            "kCancelBoundary",
            "kGesturePickBoundary",
            "kHeadAreaInflateForItemOverlap",
            "kItemRadius",
        ]:
            value = int(int(value) * UI_MULTIPLIER)

        return f"{key}={value}"

    for element in data.get_all_elements():
        for attrib, value in element.attributes.items():
            if attrib in ["area", "gutters", "imagerect"]:
                assert isinstance(value, str)
                parts = value.strip("()").split(",")
                parts = [str(int(int(p) * UI_MULTIPLIER)) for p in parts]
                element.attributes[attrib] = "(" + ",".join(parts) + ")"

            elif attrib == "caption" and isinstance(value, str) and value.startswith("k") and value.find("=") != -1:
                element.attributes[attrib] = _patched_constant(value)

    return uiscript.deserialize_uiscript(data).encode("utf-8")


def _upscale_loading_screen(entry: dbpf.Entry) -> bytes:
    """
    Return binary data for a modified loading screen.
    These are reia files (a custom format) disguised with a RIFF header.

    Uses this library: https://github.com/ammaraskar/SimsReiaParser
    """
    raw = io.BytesIO(entry.data_safe)
    reia_file = sims_reia.read_from_file(raw)

    new_frames: list[sims_reia.ReiaFrame] = []
    new_width = int(reia_file.width * UI_MULTIPLIER)
    new_height = int(reia_file.height * UI_MULTIPLIER)
    new_fps = 45 # Original: 30

    for _, reia_frame in enumerate(reia_file.frames):
        assert isinstance(reia_frame, sims_reia.ReiaFrame)
        assert isinstance(reia_frame.image, Image.Image)

        new_image = Image.new("RGB", (new_width, new_height), (0, 0, 0, 0))
        new_image.paste(reia_frame.image.resize((new_width, new_height), UPSCALE_FILTER), (0, 0))

        new_frame = sims_reia.ReiaFrame(new_image)
        new_frames.append(new_frame)

    output = io.BytesIO()
    reia_file.frames = new_frames # type: ignore
    reia_file.height = new_height
    reia_file.width = new_width
    reia_file.frames_per_second = new_fps

    sims_reia.write_reia_file(reia_file, output)

    output.seek(0)
    return output.getvalue()


def process_package(file: gamefile.GameFile, ui_update_progress: Callable):
    """
    Processes a DBPF package and upscales the user interface resources.

    ui_update_progress() is a callback function that updates the UI details window.
    """
    package = dbpf.DBPF(file.original_file_path)

    ui_files = package.get_entries_by_type(dbpf.TYPE_UI_DATA)
    image_files = package.get_entries_by_type(dbpf.TYPE_IMAGE)
    total = len(ui_files) + len(image_files)
    current = 0

    for entry in ui_files:
        if LEAVE_UNCOMPRESSED:
            entry.compress = False

        ui_update_progress(current, total)

        if entry.data_safe[:4] == b"RIFF":
            entry.data = _upscale_loading_screen(entry)
        else:
            entry.data = _upscale_uiscript(entry)

        entry.clear_cache()
        current += 1

    for entry in image_files:
        if LEAVE_UNCOMPRESSED:
            entry.compress = False

        if file.filename == "objects.package":
            # These JPEGs are Sim portraits, don't touch them as the game crashes
            try:
                if get_image_file_type(entry.data_safe) != ImageFormat.TGA:
                    current += 1
                    continue
            except (errors.ArrayTooSmall, errors.UnknownImageFormatError):
                current += 1
                continue

            # Workaround: Leave TGAs uncompressed as they could become invisible if compressed (#54)
            entry.compress = False

        ui_update_progress(current, total)

        try:
            entry.data = _upscale_graphic(entry)
        except errors.ArrayTooSmall:
            print(f"Skipping file: Unknown image contents. Type ID {hex(entry.type_id)}, Group ID {hex(entry.group_id)}, Instance ID {hex(entry.instance_id)}")
        except errors.UnknownImageFormatError:
            print(f"Skipping file: Unknown image header. Type ID {hex(entry.type_id)}, Group ID {hex(entry.group_id)}, Instance ID {hex(entry.instance_id)}")

        entry.clear_cache()
        current += 1

    # For packages to be stored in "Overrides", only save changes
    if isinstance(file, gamefile.GameFileOverride):
        package = dbpf.DBPF()
        for file_group in [ui_files, image_files]:
            package.index.entries.extend(e for e in file_group if e.modified)

    package.save_package(file.target_file_path)
    file.patched = True
    file.write_meta_file()


def process_fontstyle_ini(file: gamefile.GameFile, write_meta_file=True):
    """
    Parses FontStyle.ini (from the Fonts folder) and writes a new one with
    new font sizes.

    The lines and values to change are:
    Default = "ITC Benguiat Gothic", "11", "bold|aa=bg", 0x68963c4c
                                      ^^
    """
    with open(file.original_file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    output = []
    for line in lines:
        parts = line.split('"')

        if len(parts) < 6:
            # Skip comment lines (starting with ";")
            output.append(line)
            continue

        old_size = int(parts[3])
        new_size = int(old_size * UI_MULTIPLIER)
        parts[3] = str(new_size)
        output.append('"'.join(parts))

    with open(file.file_path, "w", encoding="utf-8") as f:
        f.writelines(output)

    file.patched = True
    if write_meta_file:
        file.write_meta_file()


def patch_file(file: gamefile.GameFile, ui_update_progress: Callable):
    """
    Patch a file with the appropriate function based on the filename.
    """
    if file.filename == "FontStyle.ini":
        process_fontstyle_ini(file)

    elif file.filename in ["ui.package", "CaSIEUI.data", "objects.package"]:
        process_package(file, ui_update_progress)

    else:
        raise NotImplementedError(f"Unknown patch operation: {file.file_path}")
