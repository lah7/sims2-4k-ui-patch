#!/usr/bin/python3
"""
Extract all the contents of a .package file to a specified directory.
Useful for visually inspecting the contents.
"""
import os
import sys

# Our modules are in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from sims2patcher import dbpf, errors, patches


def extract(package_path: str, output_dir: str, type_id: int|None = None, group_id: int|None = None, instance_id: int|None = None):
    """Extract the decompresed contents of a .package file to a specified directory"""
    print("Extracting:", package_path)
    package = dbpf.DBPF(package_path)
    entries = package.entries
    extracted = 0

    for entry in entries:
        filename = f"{hex(entry.type_id)}_{hex(entry.group_id)}_{hex(entry.instance_id)}"
        if package.header.index_version >= 7.2:
            filename += f"_{hex(entry.resource_id)}"

        path = os.path.join(output_dir, filename)

        if entry.type_id == dbpf.TYPE_DIR:
            continue

        if type_id is not None and entry.type_id != type_id:
            continue

        if group_id is not None and entry.group_id != group_id:
            continue

        if instance_id is not None and entry.instance_id != instance_id:
            continue

        try:
            # Try reading the data, decompress if necessary
            entry.data
        except errors.QFSError as e:
            print(f"\nDecompress failed: {filename}\n- {e}")
            if entry.decompressed_size:
                print(f"- Should decompress to {entry.decompressed_size} bytes. Stored as {entry.file_size} bytes in index.")
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
            extracted += 1
            entry.clear_cache()

    print("\nExtracted", extracted, "of", len(entries), "files.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: extract_package.py <package> <output directory> [type_id] [group_id] [instance_id]")
        sys.exit(1)

    # Required parameters
    INPUT_FILE = sys.argv[1]
    OUTPUT_DIR = sys.argv[2]

    # Optional parameters
    try:
        TYPE_ID = int(sys.argv[3], 16)
    except IndexError:
        TYPE_ID = None

    try:
        GROUP_ID = int(sys.argv[4], 16)
    except IndexError:
        GROUP_ID = None

    try:
        INSTANCE_ID = int(sys.argv[5], 16)
    except IndexError:
        INSTANCE_ID = None

    if not os.path.exists(INPUT_FILE):
        print("File not found:", INPUT_FILE)
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    extract(INPUT_FILE, OUTPUT_DIR, TYPE_ID, GROUP_ID, INSTANCE_ID)
