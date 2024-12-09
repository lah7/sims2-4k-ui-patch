#!/usr/bin/python3
"""
Open the contents of a .package file in memory and
print a summary to console.
"""
# pylint: disable=inconsistent-quotes
import datetime
import os
import sys

# Our modules are in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from sims2patcher import dbpf


def inspect(package_path: str):
    """Load a package and print details about its contents"""
    col = 24
    print(f"\n{package_path}\n{'=' * len(package_path)}")
    print("Reading...", end="\r")

    package = dbpf.DBPF(package_path)
    mtime = os.path.getmtime(package_path)

    print("Package Information")
    print("-" * (col - 2))
    print("Size:".ljust(col), os.path.getsize(package_path), "bytes")
    print("Modified:".ljust(col), datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"))

    print("\nTechnical Information")
    print("-" * (col - 2))
    print("DBPF Version:".ljust(col), f"{package.header.dbpf_version}")
    print("Index Version:".ljust(col), f"{package.header.index_version}")
    print("Index Offset:".ljust(col), f"{hex(package.header.index_start_offset)}")
    print("Index Size:".ljust(col), f"{package.header.index_size} bytes")
    print("")

    print("\nEntries Summary")
    print("-" * (col - 2))
    total_count = len(package.index.entries)
    compressed_count = len([e for e in package.get_entries() if e.compress])

    print("Compressed:".ljust(col), "Yes" if compressed_count > 0 else "No")
    print("Total files:".ljust(col), f"{total_count} files")
    if compressed_count > 0:
        print("Compressed files:".ljust(col), f"{compressed_count} files ({compressed_count / total_count:.1%})")
        print("Uncompressed files:".ljust(col), f"{total_count - compressed_count} files")

    data_types: dict[int, int] = {}
    avg_size: dict[int, list] = {}

    for entry in package.get_entries():
        try:
            data_types[entry.type_id] += 1
        except KeyError:
            data_types[entry.type_id] = 1

        try:
            avg_size[entry.type_id].append(entry.file_size)
        except KeyError:
            avg_size[entry.type_id] = [entry.file_size]

    print("")
    print("Type ID".ljust(10),
          "File Type".ljust(18),
          "File Count".ljust(16),
          "Average File Size"
    )
    print("-" * 10,
          "-" * 18,
          "-" * 16,
          "-" * 18
    )
    for type_id, count in data_types.items():
        match type_id:
            case dbpf.TYPE_DIR:
                type_name = "DIR Index"
            case dbpf.TYPE_ACCEL_DEF:
                type_name = "Accel. Key Def."
            case dbpf.TYPE_IMAGE:
                type_name = "Image File"
            case dbpf.TYPE_UI_DATA:
                type_name = "UI Data"
            case _:
                type_name = ""

        avg_file_size = sum(avg_size[type_id]) / len(avg_size[type_id])
        print(str(hex(type_id)).ljust(10),
              type_name.ljust(18),
              f"{count} file{'s' if count != 1 else ''}".ljust(16),
              f"{round(avg_file_size)} bytes"
        )
    print("")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: view_package_stats.py <package> [package2] ...")
        sys.exit(1)

    paths = sys.argv[1:]
    while paths:
        path = paths.pop(0)
        if not os.path.exists(path):
            print("File not found:", path)
            sys.exit(1)
        inspect(path)
