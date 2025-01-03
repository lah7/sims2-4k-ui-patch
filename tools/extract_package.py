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
        path = os.path.join(output_dir, f"{hex(entry.type_id)}_{hex(entry.group_id)}_{hex(entry.instance_id)}")
        if package.header.index_version >= 7.2:
            path += f"_{hex(entry.resource_id)}"

        if entry.type_id == dbpf.TYPE_DIR:
            continue

        try:
            # Try reading the data, decompress if necessary
            entry.data
        except ValueError:
            print(f"Couldn't extract, dumping raw bytes: Type ID {hex(entry.type_id)}, Group ID {hex(entry.group_id)}, Instance ID {hex(entry.instance_id)}")
            if entry.decompressed_size:
                print(f"... should decompress to {entry.decompressed_size} bytes. Stored as {entry.file_size} bytes in index.")
            with open(os.path.join(path), "wb") as f:
                f.write(entry.raw)
                entry.clear_cache()
                continue

        # Append file extension (where known)
        if entry.type_id == dbpf.TYPE_IMAGE:
            image_format = patches.get_image_file_type(entry.data)
            image_ext = image_format.value.lower()
            if image_ext != patches.ImageFormat.UNKNOWN:
                path += "." + image_ext

        elif entry.type_id == dbpf.TYPE_UI_DATA:
            path += ".uidata"

        elif entry.type_id == dbpf.TYPE_ACCEL_DEF:
            path += ".acceldef"

        with open(os.path.join(path), "wb") as f:
            f.write(entry.data)
            entry.clear_cache()

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
