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
# Copyright (C) 2022-2024 Luke Horwell <code@horwell.me>
#
import io
from typing import Callable

from PIL import Image

import dbpf
from gamefile import GameFile

# Density to multiply the UI dialog geometry and graphics
UI_MULTIPLIER: int = 2

# Compression keeps the package files small, but takes longer to process
COMPRESS_PACKAGE: bool = False

# Image upscaling filter
UPSCALE_FILTER: Image.Resampling = Image.Resampling.NEAREST # NEAREST, BOX, BILINEAR, HAMMING, BICUBIC, LANCZOS

# Image file types
IMAGE_FORMAT_BMP = "BMP"
IMAGE_FORMAT_JPG = "JPEG"
IMAGE_FORMAT_PNG = "PNG"
IMAGE_FORMAT_TGA = "TGA"
IMAGE_UNKNOWN = "Unknown"


def get_image_file_type(data: bytes) -> str:
    """
    The file in the DBPF package is simply "Image File".
    Read the header to get the real file type.
    """
    # Check the first 4 bytes
    start = data[:4]

    if start[:3] in [b'\x00\x00\x02', b'\x00\x00\n']:
        return IMAGE_FORMAT_TGA
    elif start[:2] == b'BM':
        return IMAGE_FORMAT_BMP
    elif start[:3] == b'\xff\xd8\xff':
        return IMAGE_FORMAT_JPG
    elif start[:4] == b'\x89PNG':
        return IMAGE_FORMAT_PNG
    else:
        return IMAGE_UNKNOWN


def _upscale_graphic(entry: dbpf.Entry) -> bytes:
    """
    Return binary data for an upscaled (or intact) image.

    Graphics could be a TGA, PNG, JPG or BMP file. Most UI graphics are TGA (Targa).

    To upscale, multiply the width and height by UI_MULTIPLIER, so the UI
    is comfortably readable at double its original density.

    UPSCALE_FILTER may influence the resulting quality of the image.
    """
    file_type = get_image_file_type(entry.data)

    if file_type == IMAGE_UNKNOWN:
        print(f"Unknown image format: Type ID {entry.type_id}, Group ID {entry.group_id}, Instance ID {entry.instance_id}")
        return entry.data

    original = Image.open(io.BytesIO(entry.data), formats=[file_type])
    resized = original.resize((original.width * UI_MULTIPLIER, original.height * UI_MULTIPLIER), resample=UPSCALE_FILTER)

    output = io.BytesIO()
    resized.save(output, format=file_type)
    return output.getvalue()


def _upscale_uiscript(entry: dbpf.Entry):
    """
    Return binary data for a modified .uiScript file.

    .uiScript is a modified XML file that specifies the dialog geometry and element positions.

    To upscale, multiply the attribute's value (which are comma separated values) by UI_MULTIPLIER.
    """
    try:
        data = entry.data.decode("utf-8")
    except UnicodeDecodeError:
        # Skip binary .uiScript file
        return entry.data

    def _update_attribute_coord(data, name):
        """
        Update an attribute that contains geometry in this format: (1,2,3,4)

        Examples:
        - area=(0,0,175,21)
        - area=(60,20,511,342)
        - gutters=(4,4)
        - gutters=(0,0,0,0)

        Useful documentation: https://www.wiki.sc4devotion.com/index.php?title=UI
        """
        output = []
        parts = data.split(name + "=")
        for part in parts:
            if not part.startswith("("):
                output.append(part)
                continue

            new_values = []
            values = part.split("(")[1].split(")")[0]
            for number in values.split(","):
                new_values.append(str(int(number) * UI_MULTIPLIER))
            part = f"{name}={part.replace(values, ','.join(new_values))}"
            output.append(part)
        return "".join(output)

    data = _update_attribute_coord(data, "area")
    data = _update_attribute_coord(data, "gutters")

    return data.encode("utf-8")


def upscale_package_contents(file: GameFile, package: dbpf.DBPF, ui_update_progress: Callable):
    """
    Processes a DBPF package and upscales the user interface resources.
    """
    new_package = dbpf.DBPF()
    entries = package.get_entries()
    completed = 0
    total = len(entries)
    for entry in entries:
        ui_update_progress(f"Upscaling: {completed}/{total}", completed)

        if entry.type_id == dbpf.TYPE_UI_DATA:
            data = _upscale_uiscript(entry)
            new_package.add_entry(entry.type_id, entry.group_id, entry.instance_id, entry.resource_id, data, entry.compress and COMPRESS_PACKAGE)

        elif entry.type_id == dbpf.TYPE_IMAGE:
            data = _upscale_graphic(entry)
            new_package.add_entry(entry.type_id, entry.group_id, entry.instance_id, entry.resource_id, data, entry.compress and COMPRESS_PACKAGE)

        elif entry.type_id == dbpf.TYPE_ACCEL_DEF:
            # No modifications necessary
            new_package.add_entry(entry.type_id, entry.group_id, entry.instance_id, entry.resource_id, entry.data, entry.compress and COMPRESS_PACKAGE)

        elif entry.type_id == dbpf.TYPE_DIR:
            # Discard compressed directory index. It'll be regenerated for the new package.
            continue

        else:
            # "What's this?"
            print(f"Unknown file in package: Type ID {entry.type_id}, Group ID {entry.group_id}, Instance ID {entry.instance_id}")
            new_package.add_entry(entry.type_id, entry.group_id, entry.instance_id, entry.resource_id, entry.data, entry.compress and COMPRESS_PACKAGE)

        completed += 1

    def _cb_save_progress_updated(text: str, value: int, total: int):
        ui_update_progress(f"{text}: {value / total*100:.2f}%", value, total)

    new_package.cb_save_progress_updated = _cb_save_progress_updated
    new_package.save_package(file.file_path)
    file.patched = True
    file.write_meta_file()


def upscale_fontstyle_ini(file: GameFile, write_meta_file=True):
    """
    Parses FontStyle.ini (from the Fonts folder) and writes a new one with
    new font sizes.

    The lines and values to change are:
    Default = "ITC Benguiat Gothic", "11", "bold|aa=bg", 0x68963c4c
                                      ^^
    """
    with open(file.backup_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    output = []
    for line in lines:
        parts = line.split('"')

        if len(parts) < 6:
            # Skip comment lines (starting with ";")
            output.append(line)
            continue

        old_size = int(parts[3])
        new_size = old_size * UI_MULTIPLIER
        parts[3] = str(new_size)
        output.append('"'.join(parts))

    with open(file.file_path, "w", encoding="utf-8") as f:
        f.writelines(output)

    file.patched = True
    if write_meta_file:
        file.write_meta_file()
