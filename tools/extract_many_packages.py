#!/usr/bin/python3
"""
Extract many .package files (or a folder) to a specified directory.
Useful for visually inspecting many packages at once.
"""
import argparse
import glob
import os
import sys

# Our modules are in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from extract_package import extract

parser = argparse.ArgumentParser(description="Benchmark QFS compression levels")
parser.add_argument("-o", "--output-dir", type=str, required=True, help="Write extracted files (in subfolders) here", metavar="")
parser.add_argument("-i", "--input", nargs="*", required=True, help="Extract these package(s) or find packages in directories", metavar="FILE OR DIR")
parser.add_argument("-b", "--include-backup", action="store_true", help="Extract backups too")

args = parser.parse_args()

PACKAGES = []

for path in args.input:
    if os.path.isfile(path):
        PACKAGES.append(path)
        if args.include_backup and os.path.exists(f"{path}.bak"):
            PACKAGES.append(f"{path}.bak")

    elif os.path.isdir(path):
        PACKAGES += glob.glob(os.path.join(path, "**", "*.package"), recursive=True)
        if args.include_backup:
            PACKAGES += glob.glob(os.path.join(path, "**", "*.package.bak"), recursive=True)

for package in PACKAGES:
    output_path = os.path.join(args.output_dir, os.path.relpath(package, os.path.commonpath([package, args.input[0]])))
    print(f"\nExtract to: '{output_path}'")

    # FIXME: Don't attempt! Our library will cause system to run out of memory!
    if package.find("Sims3D") >= 0:
        print("Skipping Sims3D package, system will run out of memory!")
        continue

    os.makedirs(output_path, exist_ok=True)
    try:
        extract(package, output_path)
    except (IndexError, ValueError) as e:
        print(f"Extraction failed '{package}': {e}")
