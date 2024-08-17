#!/usr/bin/python3
"""
Extract all the contents of a .package file to a specified directory.
Useful for visually inspecting the contents.
"""
import os
import sys

# Our modules are in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from sims2patcher import dbpf, patches


def extract(package_path: str, output_dir: str):
    """Extract the decompresed contents of a .package file to a specified directory"""
    print("Extracting:", package_path)
    package = dbpf.DBPF(package_path)
    entries = package.get_entries()

    for entry in entries:
        path = os.path.join(output_dir, f"{entry.type_id}-{entry.group_id}-{entry.instance_id}")
        if package.header.index_version >= 7.2:
            path += f"-{entry.resource_id}"

        # Append file extension (where known)
        if entry.type_id == dbpf.TYPE_IMAGE:
            image_ext = patches.get_image_file_type(entry.data)
            if image_ext != patches.IMAGE_UNKNOWN:
                path += "." + image_ext.lower()

        elif entry.type_id == dbpf.TYPE_UI_DATA:
            path += ".uidata"

        elif entry.type_id == dbpf.TYPE_ACCEL_DEF:
            path += ".acceldef"

        elif entry.type_id == dbpf.TYPE_DIR:
            continue

        with open(os.path.join(path), "wb") as f:
            f.write(entry.data)

    print("Extracted", len(entries), "files.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: extract_package.py <package> <output directory>")
        sys.exit(1)

    INPUT_FILE = sys.argv[1]
    OUTPUT_DIR = sys.argv[2]

    if not os.path.exists(INPUT_FILE):
        print("File not found:", INPUT_FILE)
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    extract(INPUT_FILE, OUTPUT_DIR)
