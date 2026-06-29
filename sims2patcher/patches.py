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
import struct
from typing import Callable

from PIL import Image

import submodules.SimsReiaParser.SimsReiaPy.sims_reia as sims_reia

from . import dbpf, errors, gamefile, uiscript

# Density to multiply the UI dialog geometry and graphics
UI_MULTIPLIER: float = 2.0

# Compression keeps the package files small, but takes longer to process
LEAVE_UNCOMPRESSED: bool = False

# Fix pie menu item positioning in the game executable
FIX_PIE_MENU: bool = True

# Image upscaling filter
UPSCALE_FILTER: Image.Resampling = Image.Resampling.NEAREST

# Loading screen FPS
LOADING_SCREEN_FPS: int = 45 # Original: 30


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


def _fix_uiscript_element_attributes(script_id: tuple[int, int], attributes: dict) -> dict:
    """
    Apply fixes to UI script bugs from the original game for a specified element.
    """
    attributes2 = attributes.copy()

    # Missing font for "Needs" in newer expansions
    if script_id == (0xa99d8a11, 0x49064905):
        if "caption" in attributes and attributes["caption"] == "Needs":
            attributes2["font"] = "GenHeader"

    # Missing font for build mode browser titles in most expansions
    elif script_id == (0xa99d8a11, 0x49060003) or script_id == (0xa99d8a11, 0x49060004):
        if "caption" in attributes:
            if attributes["caption"] == "info text":
                attributes2["font"] = "DefaultFont14"
            elif attributes["caption"] == "Roof Angle Chooser":
                attributes2["font"] = "DefaultFont14"

    # Missing fonts for new baby/twins/pet/robot in newer expansions
    elif script_id == (0xa99d8a11, 0x2d91050a):
        if "area" in attributes:
            value = attributes["area"]
            if value in ["(18,12,315,46)", "(18,13,315,53)"]:
                attributes2["font"] = "GenHeader"
            elif value in ["(18,43,315,109)", "(18,63,315,133)", "(18,11,305,45)"]:
                attributes2["font"] = "GenSubHeader"
            elif value in ["(75,241,307,267)", "(75,291,307,317)", "(75,121,307,147)", "(75,141,307,167)", "(75,191,307,217)", "(31,74,289,101)"]:
                attributes2["font"] = "NeighborhoodButton"
            elif value in ["(105,123,147,156)"]:
                attributes2["font"] = "GenButton"

    # Missing fonts in "Game Options" in newer expansions
    elif script_id in [(0xa99d8a11, 0x49060f02), (0x8000600, 0x49060f02)]:
        if attributes.get("iid") in ["IGZWinText", "IGZWinBtn"] and "caption" in attributes:
            attributes2["font"] = "OptionsText"

        if attributes.get("caption", "") == "Game Options":
            attributes2["font"] = "OptionsHeader"

        if attributes.get("caption", "") in ["Lot View Options", "House-Specific Options"]:
            attributes2["font"] = "GenButton"

        # Improve padding in Game Options
        if attributes.get("area", "") == "(6,1,488,23)": # "Lot View Options"
            attributes2["area"] = "(6,9,488,31)" # +8 pixels down

        elif attributes.get("id", "") in [
            "0x000000a8", # "View Distance"
            "0x000000a7", # "Neighbors"
            "0x000000a6", # "Decorations"
            "0x000000aa", # "Fade Distance"
        ]:
            area = attributes.get("area", "(0,0,0,0)")
            parts = area.strip("()").split(",")
            x, y, width, height = map(int, parts)
            attributes2["area"] = f"({x},{y + 10},{width},{height})"

    # Missing fonts in "Game Tip Encyclopedia" in newer expansions
    elif script_id in [(0xa99d8a11, 0x49060f06), (0x8000600, 0x49060f06)]:
        if attributes.get("iid") in ["IGZWinText", "IGZWinTextEdit"] and "caption" in attributes:
            attributes2["font"] = "NeighborhoodBody"

        if attributes.get("caption", "") == "Game Tip Encyclopedia":
            attributes2["font"] = "OptionsHeader"

    # Missing fonts for pet employment panel
    elif script_id == (0xa99d8a11, 0xfeed2006):
        if attributes.get("id") in ["0x77e74b47", "0x2d0a50a7"]:
            attributes2["font"] = "LiveModePanelHeader"

        elif attributes.get("id") in ["0x27e74b64", "0x47e74b6d", "0xec2cfcfd", "0x0c1fc411", "0x0c1fc412", "0x0c1fc413", "0x0c1fc414", "0x0c1fc415", "0x0c1fc416", "0x0c1fc417", "0x2d0a50a6", "0x71ecc381", "0x71ecc38b"]:
            attributes2["font"] = "LiveModePanelBody"

        elif attributes.get("id") == "0x0000d0a1":
            attributes2["font"] = "LiveModePanelSmallBody"

        elif attributes.get("id") in ["0xccc728cd", "0x0c1fc419"]:
            attributes2["font"] = "DefaultFont14"

        elif attributes.get("id") == "0xabcd0002":
            attributes2["font"] = "OptionsText"

        if attributes.get("clsid") == "0x4ca92f03":
            attributes2["font"] = "LiveModePanelSubHeader"

        if attributes.get("captionres") in ["{7f96c284,00e80006}", "{7f96c284,00e80026}", "{7f96c284,00e80027}", "{7f96c284,00e80028}"]:
            attributes2["font"] = "OptionsText"

    # "Customise Novel" dialog never had fonts defined
    elif script_id == (0xa99d8a11, 0xbb40021):
        if attributes.get("iid") == "IGZWinText":
            attributes2["font"] = "GenHeader"
        elif attributes.get("id") == "0x00002002":
            attributes2["font"] = "GenSubHeader"
        elif attributes.get("id") == "0x00002003":
            attributes2["font"] = "NeighborhoodBody"

    # Increase list box height in Graphics Options
    elif script_id == (0xa99d8a11, 0x49060f03):
        if attributes.get("iid") == "IGZWinBMP":
            if attributes.get("area") == "(1,17,111,102)":
                attributes2["area"] = "(1,17,111,113)" # +11 pixels height for Screen Size
            elif attributes.get("area") == "(1,17,100,102)":
                attributes2["area"] = "(1,17,100,113)" # +11 pixels height for Refresh Rate

    return attributes2


def _upscale_uiscript(entry: dbpf.Entry) -> bytes:
    """
    Return binary data for a modified UI Script.
    These files are modified XML files specifying the dialog geometry and element positions.

    To upscale, multiply attributes with dimension/position values by UI_MULTIPLIER.
    """
    # Skip debugging UI - they break!
    script_id = (entry.group_id, entry.instance_id)
    if script_id in [
        (0xa99d8a11, 0xfffffff0), # Skin Browser
        (0xa99d8a11, 0xfffffff1), # Outfit Browser
        (0xa99d8a11, 0xfffffff3), # Cheat Object Browser
        (0xa99d8a11, 0x8baff56f), # UI Browser
    ]:
        return entry.data

    # Skip 800x600 UI scripts in case the game resolution resets
    if entry.group_id == 0x8000600:
        return entry.data

    root: uiscript.UIScriptRoot = uiscript.serialize_uiscript(entry.data.decode("utf-8"))

    # Function for patching "Constants Table" later
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

    # Patch attributes as needed
    for element in root.get_all_elements():
        # Add new attributes
        element.attributes = _fix_uiscript_element_attributes(script_id, element.attributes)

        # Upscale existing attributes
        for attrib, value in element.attributes.items():
            if attrib in ["area", "gutters", "imagerect"]:
                assert isinstance(value, str)
                parts = value.strip("()").split(",")
                parts = [str(int(int(p) * UI_MULTIPLIER)) for p in parts]
                element.attributes[attrib] = "(" + ",".join(parts) + ")"

            elif attrib == "caption" and isinstance(value, str) and value.startswith("k") and value.find("=") != -1:
                element.attributes[attrib] = _patched_constant(value)

    return uiscript.deserialize_uiscript(root).encode("utf-8")


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
    reia_file.frames_per_second = LOADING_SCREEN_FPS

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


# Pie menu binary patch data for Sims2EP9.exe.
# The game hardcodes pixel offsets for pie menu item positions. These sector
# offsets and the item radius calculation need scaling to match the UI density.
_PIE_MENU_SECTOR_OFFSETS: list[tuple[int, int]] = [
    (0x001A6A1E, 0x11),  # edx=17
    (0x001A6A21, 0x0E),  # eax=14
    (0x001A6A24, 0x15),  # ecx=21
    (0x001A6A27, 0x10),  # esi=16
    (0x001A6A62, 0x30),  # imm32=48
    (0x001A6A6C, 0x1A),  # imm32=26
    (0x001A6A9A, 0x1A),  # imm32=26
]

# Two fild instructions load kItemRadius for the item position formula
# (radius * sin/cos). A code cave multiplies by UI_MULTIPLIER before
# the sin/cos multiplication, scaling item positions without affecting
# the zombie head (3D Sim portrait) which shares the same field.
_PIE_MENU_FILD_SITE_1 = 0x001A90A9  # fild+fmul for sin path (8 bytes)
_PIE_MENU_FILD_SITE_2 = 0x001A90C6  # fild+pop+fmul for cos path (9 bytes)
_PIE_MENU_CAVE_ADDR = 0x00DD2C19    # unused padding at end of .text section
_PIE_MENU_IMAGE_BASE = 0x00400000

# Expected original bytes at the fild sites for verification
_PIE_MENU_FILD_ORIG_1 = bytes([0xDB, 0x83, 0xF0, 0x01, 0x00, 0x00, 0xD8, 0xC9])
_PIE_MENU_FILD_ORIG_2 = bytes([0xDB, 0x83, 0xF0, 0x01, 0x00, 0x00, 0x59, 0xD8, 0xC9])


def _verify_exe_bytes(data: bytes) -> bool:
    """Check that the EXE contains expected original bytes at all patch offsets."""
    for offset, orig_val in _PIE_MENU_SECTOR_OFFSETS:
        if offset >= len(data) or data[offset] != orig_val:
            return False

    site1 = _PIE_MENU_FILD_SITE_1
    site2 = _PIE_MENU_FILD_SITE_2
    if site1 + 8 > len(data) or site2 + 9 > len(data):
        return False
    if data[site1:site1+8] != _PIE_MENU_FILD_ORIG_1:
        return False
    if data[site2:site2+9] != _PIE_MENU_FILD_ORIG_2:
        return False

    return True


def _build_pie_menu_patch(data: bytes, scale: float) -> bytes:
    """
    Apply pie menu positioning fix to the EXE binary data.

    Writes a code cave that multiplies kItemRadius by the scale factor
    before the sin/cos calculation, and scales sector fine-tuning offsets.
    """
    patched = bytearray(data)
    cave = _PIE_MENU_CAVE_ADDR
    cave_va = _PIE_MENU_IMAGE_BASE + cave

    # --- Write code cave ---
    # Layout: [float scale] [cave1: 15 bytes] [cave2: 15 bytes]

    # Float multiplier at cave_addr (4 bytes)
    struct.pack_into("<f", patched, cave, scale)

    # cave1 at cave+4: fild [ebx+0x1F0]; fmul [multiplier]; fmul st,st1; ret
    c1 = cave + 4
    patched[c1:c1+6] = bytes([0xDB, 0x83, 0xF0, 0x01, 0x00, 0x00])  # fild [ebx+0x1F0]
    patched[c1+6:c1+12] = bytes([0xD8, 0x0D]) + struct.pack("<I", cave_va)  # fmul [cave_va]
    patched[c1+12:c1+14] = bytes([0xD8, 0xC9])  # fmul st(0), st(1)
    patched[c1+14] = 0xC3  # ret

    # cave2 at cave+19: same structure
    c2 = cave + 19
    patched[c2:c2+6] = bytes([0xDB, 0x83, 0xF0, 0x01, 0x00, 0x00])  # fild [ebx+0x1F0]
    patched[c2+6:c2+12] = bytes([0xD8, 0x0D]) + struct.pack("<I", cave_va)  # fmul [cave_va]
    patched[c2+12:c2+14] = bytes([0xD8, 0xC9])  # fmul st(0), st(1)
    patched[c2+14] = 0xC3  # ret

    # --- Patch call site 1 (sin path, 8 bytes) ---
    site1 = _PIE_MENU_FILD_SITE_1
    rel1 = (c1 + _PIE_MENU_IMAGE_BASE) - (site1 + _PIE_MENU_IMAGE_BASE + 5)
    patched[site1] = 0xE8  # call
    struct.pack_into("<i", patched, site1 + 1, rel1)
    patched[site1+5:site1+8] = bytes([0x90, 0x90, 0x90])  # nop pad

    # --- Patch call site 2 (cos path, 9 bytes) ---
    # Keep the pop ecx at its original position
    site2 = _PIE_MENU_FILD_SITE_2
    rel2 = (c2 + _PIE_MENU_IMAGE_BASE) - (site2 + _PIE_MENU_IMAGE_BASE + 5)
    patched[site2] = 0xE8  # call
    struct.pack_into("<i", patched, site2 + 1, rel2)
    patched[site2+5] = 0x59  # pop ecx (stack cleanup, was at site2+6 originally)
    patched[site2+6:site2+9] = bytes([0x90, 0x90, 0x90])  # nop pad

    # --- Scale sector offsets ---
    for offset, orig_val in _PIE_MENU_SECTOR_OFFSETS:
        new_val = min(int(orig_val * scale), 127)
        patched[offset] = new_val

    return bytes(patched)


def process_executable(file: gamefile.GameFile):
    """
    Patches the game executable to fix pie menu item positioning.
    Applies a code cave to scale the item radius calculation and
    adjusts sector fine-tuning offsets.
    """
    if not FIX_PIE_MENU:
        return

    with open(file.original_file_path, "rb") as f:
        data = f.read()

    if not _verify_exe_bytes(data):
        print(f"Skipping pie menu fix: {file.filename} has unexpected bytes (unsupported version or already patched)")
        return

    patched_data = _build_pie_menu_patch(data, UI_MULTIPLIER)

    with open(file.target_file_path, "wb") as f:
        f.write(patched_data)

    file.patched = True
    file.write_meta_file()


def patch_file(file: gamefile.GameFile, ui_update_progress: Callable):
    """
    Patch a file with the appropriate function based on the filename.
    """
    if file.filename == "FontStyle.ini":
        process_fontstyle_ini(file)

    elif file.filename in ["ui.package", "CaSIEUI.data", "objects.package"]:
        process_package(file, ui_update_progress)

    elif file.filename.lower() == "sims2ep9.exe":
        process_executable(file)

    else:
        raise NotImplementedError(f"Unknown patch operation: {file.file_path}")
