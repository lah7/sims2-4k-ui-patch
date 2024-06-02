#!/usr/bin/python3
"""
Extract all the .package files that we patch to a specified directory.
Useful for visually inspecting everything.
"""
import glob
import os
import sys

# Our modules are in the parent directory
# pylint: disable=wrong-import-position
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from extract_package import extract

if len(sys.argv) < 3:
    print("Usage: extract_package.py <EA GAMES dir> <output directory> [--include-backup]")
    sys.exit(1)

EA_GAMES_DIR = sys.argv[1]
OUTPUT_DIR = sys.argv[2]
INCLUDE_BACKUP = sys.argv[3] == "--include-backup"

if not os.path.exists(EA_GAMES_DIR):
    print("Directory does not exist:", EA_GAMES_DIR)
    sys.exit(1)

os.makedirs(OUTPUT_DIR, exist_ok=True)

files = []
for filename in ["ui.package", "CaSIEUI.data"]:
    files += glob.glob(os.path.join(EA_GAMES_DIR, "*Sims 2*", "TSData") + f"/**/{filename}", recursive=True)
    if INCLUDE_BACKUP:
        files += glob.glob(os.path.join(EA_GAMES_DIR, "*Sims 2*", "TSData") + f"/**/{filename}.bak", recursive=True)

for package in files:
    output_path = package.replace(EA_GAMES_DIR, OUTPUT_DIR)
    os.makedirs(output_path, exist_ok=True)
    extract(package, output_path)
