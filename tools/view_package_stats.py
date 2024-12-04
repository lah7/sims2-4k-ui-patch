#!/usr/bin/python3
"""
Open the contents of a .package file in memory and
print a summary to console.
"""
# pylint: disable=inconsistent-quotes
import datetime
import hashlib
import os
import sys

# Our modules are in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from sims2patcher import dbpf

WRITE_CSV = False


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
            avg_size[entry.type_id].append(entry.decompressed_size or entry.file_size)
        except KeyError:
            avg_size[entry.type_id] = [entry.decompressed_size or entry.file_size]

    print("")
    print("Type ID".ljust(10),
          "File Type".ljust(30),
          "File Count".ljust(16),
          "Average File Size"
    )
    print("-" * 10,
          "-" * 30,
          "-" * 16,
          "-" * 18
    )
    for type_id, count in data_types.items():
        try:
            type_name = dbpf.FILE_TYPES[type_id]
        except KeyError:
            type_name = ""

        avg_file_size = sum(avg_size[type_id]) / len(avg_size[type_id])
        print(str(hex(type_id)).ljust(10),
              type_name.ljust(30),
              f"{count} file{'s' if count != 1 else ''}".ljust(16),
              f"{round(avg_file_size)} bytes",
        )
    print("")

    if WRITE_CSV:
        print(f"Exporting {os.path.basename(package_path)}.csv", end="")
        with open(f"{package_path}.csv", "w", encoding="utf-8") as f:
            f.write("File Type,Type ID,Group ID,Instance ID,Resource ID,Compressed,Size in index (bytes),Uncompressed (bytes),Index MD5,Data MD5\n")
            for entry in package.get_entries():
                print(".", end="", flush=True)
                md5_raw = hashlib.md5(entry.raw).hexdigest()
                md5_data = hashlib.md5(entry.data).hexdigest()
                f.write(f"{dbpf.FILE_TYPES.get(entry.type_id, "")},{entry.type_id},{entry.group_id},{entry.instance_id},"

                f.write(f"{dbpf.FILE_TYPES.get(entry.type_id, "")},{entry.type_id},{entry.group_id},{entry.instance_id},{entry.resource_id}," +
                        f"{'Yes' if entry.compress else 'No'},{entry.file_size},{entry.decompressed_size or ''},{md5_raw},{md5_data}\n")
                entry.clear_cache()
            print(" done!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: view_package_stats.py [--csv] <package> [package2] ...")
        sys.exit(1)

    paths = sys.argv[1:]

    while paths:
        path = paths.pop(0)

        if path == "--csv":
            WRITE_CSV = True
            continue

        if not os.path.exists(path):
            print("File not found:", path)
            sys.exit(1)

        inspect(path)
