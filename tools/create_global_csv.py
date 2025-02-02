#!/usr/bin/python3
"""
Analyses all the named package files and generates a CSV file detailing where each resource is used.
"""
import glob
import hashlib
import os
import sys

# Our modules are in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from sims2patcher import dbpf, errors

GAME_NAMES = []


def conceptualize(game_dir: str, package_name: str) -> dict:
    """Map out what and where the resources are used: (type_id, group_id, instance_id) -> {game_name: checksum}"""
    mapping = {}

    paths = glob.glob(f"{game_dir}/**/{package_name}", recursive=True)
    if not paths:
        print("No packages found!")
        sys.exit(1)

    print("Analyzing packages...\n.", end="\r")
    for g_no, path in enumerate(paths):
        package = dbpf.DBPF(path)
        entries = [e for e in package.entries if e.type_id in [dbpf.TYPE_UI_DATA, dbpf.TYPE_IMAGE]]

        # Name of Game/EP/SP - expected 3 levels up
        game_name = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(path)))))
        game_name = game_name.split("2")[1].strip() if "2" in game_name and game_name != "The Sims 2" else game_name
        GAME_NAMES.append(game_name)

        for f_no, entry in enumerate(entries):
            print(f" ({g_no + 1}/{len(paths)}) {game_name}: {f_no + 1}/{len(entries)}".ljust(70), end="\r")

            file_id = (entry.type_id, entry.group_id, entry.instance_id)

            try:
                checksum = hashlib.md5(entry.data).hexdigest()[:8]
            except errors.QFSError:
                checksum = "????????"
            entry.clear_cache()

            if file_id not in mapping:
                mapping[file_id] = {}

            mapping[file_id][game_name] = checksum

    return mapping


def create_csv(game_dir: str, package_name: str):
    """Create a CSV file detailing where each resource is used"""
    mapping = conceptualize(game_dir, package_name)

    print("\nGenerating CSV...", end="")

    with open(f"global_{os.path.basename(package_name)}.csv", "w", encoding="utf-8") as f:
        # Header + each game
        f.write("Type ID,Group ID,Instance ID,")
        for name in GAME_NAMES:
            f.write(f"{name},")
        f.write("\n")

        for (type_id, group_id, instance_id), data in mapping.items():
            f.write(f"{hex(type_id)},{hex(group_id)},{hex(instance_id)},")
            for name in GAME_NAMES:
                if name in data:
                    f.write(f"{data[name]},")
                else:
                    f.write(",")
            f.write("\n")

    print(" done!")


if __name__ == "__main__":
    # Parse command line arguments
    if len(sys.argv) < 3:
        print("Usage: create_global_csv.py <package_name> <game_directory>")
        print("Example: create_global_csv.py \"Res/UI/ui.package\" \"/path/to/EA GAMES\"")
        sys.exit(1)

    PACKAGE_NAME = sys.argv[1]
    GAME_DIR = sys.argv[2]

    if not os.path.isdir(GAME_DIR):
        print("Directory not found:", GAME_DIR)
        sys.exit(1)

    create_csv(GAME_DIR, PACKAGE_NAME)
