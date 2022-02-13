#!/usr/bin/python3
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
# Copyright (C) 2022 Luke Horwell <code@horwell.me>
#
"""
This script takes the files from an extracted ui.package (via SimPE),
upscales the fonts & graphics and produces a new package file.

While graphic rules can be defined to allow The Sims 2 to run a a 4K resolution,
the user interface elements are extremely tiny. This modification aims to fix
that, and it's as simple as doubling the density of the graphics and fonts.

See the README for instructions on using this script.
"""
import os
import glob
import shutil
import signal

# ==== OPTIONS ====
# The default options are tuned from 1920x1080 to 3840x2160 (4K, 2160p)

# -- How much to increase the UI dialog geometry and graphics.
# -- TODO: Test decimal
UI_ZOOM_FACTOR = 2

# -- How many points to increase the font size in addition to the UI_ZOOM_FACTOR
FONT_INCREASE_PT = 0

# Imagemagick executable name
IMAGEMAGICK = "convert"

# -- What quality to upscale images: point, linear, cubic
UPSCALE_FILTER = "point"


def filter_files_by_type(files):
    """
    The files extracted by SimPE are not actually JPGs. Most are Targa (TGA),
    bu could also be PNGs, Bitmap (.bmp) and JPEGs.

    This function checks for first few bytes of each file and returns a
    dictionary filtered by each known type.
    """
    print(f"Analyzing {len(files)} files...")
    tga = []
    bmp = []
    jpg = []
    png = []
    unknown = []

    for path in files:
        with open(path, "rb") as f:
            # Check the first 4 bytes
            start = f.read()[:4]

            if start[:3] in [b'\x00\x00\x02', b'\x00\x00\n']:
                tga.append(path)
            elif start[:2] == b'BM':
                bmp.append(path)
            elif start[:3] == b'\xff\xd8\xff':
                jpg.append(path)
            elif start[:4] == b'\x89PNG':
                png.append(path)
            else:
                unknown.append(path)

    return {
        "bmp": bmp,
        "jpg": jpg,
        "png": png,
        "tga": tga,
    }


def upscale_fontstyle_ini():
    """
    Parses FontStyle.ini from the input/Fonts folder and writes a new one
    with font sizes increased by the FONT_INCREASE_PT factor.
    """
    in_path = os.path.join(INPUT_DIR, "Fonts", "FontStyle.ini")
    out_path = os.path.join(OUTPUT_DIR, "Fonts", "FontStyle.ini")

    with open(in_path, "r") as f:
        lines = f.readlines()

    output = []
    for line in lines:
        parts = line.split('"')
        if len(parts) < 6:
            output.append(line)
            continue

        old_size = parts[3]
        new_size = int(parts[3]) + FONT_INCREASE_PT
        parts[3] = str(new_size)
        output.append('"'.join(parts))

    with open(out_path, "w") as f:
        f.writelines(output)

    print("Written new FontStyle.ini")


def upscale_uiscripts():
    """
    Parses *.uiScript (modified XML) files; multiplies the attribute's
    value (consisting of comma separated values) by UI_ZOOM_FACTOR and
    returns the new data.
    """
    print("Processing .uiScript files...")
    file_list = glob.glob(INPUT_DIR + "/**/*.uiScript", recursive=True)
    current = 0
    total = len(file_list)
    skipped = 0
    print(".", end="")

    for path in file_list:
        current += 1
        print(f"\r[{current}/{total}, {int(current/total * 100)}%] Writing: {path.split('/')[-1]}    ", end="")
        output_path = path.replace(INPUT_DIR, OUTPUT_DIR)

        try:
            with open(path, "r") as f:
                data = f.read()
        except UnicodeDecodeError:
            # Skip the handful of binary .uiScript files
            skipped += 1
            continue

        def _replace_coord_attribute(data, name):
            output = []
            parts = data.split(name + "=")
            for part in parts:
                if not part.startswith("("):
                    output.append(part)
                    continue

                new_values = []
                values = part.split("(")[1].split(")")[0]
                for number in values.split(","):
                    new_values.append(str(int(number) * UI_ZOOM_FACTOR))
                part = f"{name}={part.replace(values, ','.join(new_values))}"
                output.append(part)
            return "".join(output)

        data = _replace_coord_attribute(data, "area")
        data = _replace_coord_attribute(data, "gutters")

        with open(output_path, "w") as f:
            f.writelines(data)
    print(f"\n{skipped} binary file(s) were skipped.")


def upscale_graphics():
    """
    Upscales the specified graphic using Imagemagick ('convert' command)
    with the UPSCALE_FILTER for quality.
    """
    file_list = glob.glob(INPUT_DIR + "/**/*.jpg", recursive=True)
    file_types = filter_files_by_type(file_list)
    print("Processing graphics...")
    print("    TGA:", len(file_types["tga"]))
    print("    JPG:", len(file_types["jpg"]))
    print("    PNG:", len(file_types["png"]))
    print("    BMP:", len(file_types["bmp"]))

    current = 0
    total = len(file_types["tga"]) + len(file_types["jpg"]) + len(file_types["png"]) + len(file_types["bmp"])
    print(".", end="")
    for ext in file_types.keys():
        for path in file_types[ext]:
            current += 1
            print(f"\r[{current}/{total}, {int(current/total * 100)}%] Converting {ext.upper()}: {path.split('/')[-1].split('.')[0]}    ", end="")

            # Create temporary file so input directory remains untouched
            tempin = path.replace(INPUT_DIR, OUTPUT_DIR).replace(".jpg", f".tmp.{ext}")
            shutil.copy(path, tempin)

            # Imagemagick uses the input/output file extension for conversion
            tempout = tempin.replace(f".tmp.{ext}", f".{ext}")
            os.system(f"convert '{tempin}' -filter {UPSCALE_FILTER} -resize {UI_ZOOM_FACTOR * 100}% '{tempout}'")
            os.remove(tempin)

            # Rename the file back to 'JPG'
            output = tempout.replace(f".{ext}", ".jpg")
            os.rename(tempout, output)

    print("\n")


def create_output_dir():
    """
    Replicate the input subdirectories and copy the XML files (which SimPE
    created and we need to reference later)
    """
    def ignore_files(dir, files):
        ignored = []
        for name in files:
            if os.path.isfile(os.path.join(dir, name)) and not name.endswith(".xml"):
                ignored.append(name)
        return ignored
    shutil.copytree(INPUT_DIR, OUTPUT_DIR, ignore=ignore_files)


def check_input_files(check_name, ext):
    """
    Perform a prelimitary check that we have everything required for processing.
    """
    if len(glob.glob(INPUT_DIR + "/**/*." + ext, recursive=True)) > 0:
        print("     OK |", check_name)
        return True
    print("MISSING |", check_name)
    return False


if __name__ == "__main__":
    # Allow CTRL+C to abort script
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Paths
    INPUT_DIR = os.path.join(os.path.dirname(__file__), "input")
    OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

    if not os.path.exists(INPUT_DIR):
        print("'input' directory does not exist! See README for instructions.")
        exit(1)

    if os.path.exists(OUTPUT_DIR):
        #print("'output' directory exists. Please delete this to continue.")
        #exit(1)
        print("Deleted old output directory:", OUTPUT_DIR)
        shutil.rmtree(OUTPUT_DIR)

    # Check files are found
    print("Performing preliminary checks...")
    check_input_files("UI Data (UI)", "uiScript")
    check_input_files("jpg/tga/png Image (IMG)", "jpg")

    # Write directories for output
    print("Preparing output directory...")
    create_output_dir()

    # 1. Adjust geometry in *.uiScript files
    upscale_uiscripts()

    # 2. Adjust font size in FontStyle.ini (base game)
    upscale_fontstyle_ini()

    # 3. Enlarge UI graphics (requires 'imagemagick' to be installed)
    upscale_graphics()

    print("Conversion has finished. Ready to create a new .package!\n")
