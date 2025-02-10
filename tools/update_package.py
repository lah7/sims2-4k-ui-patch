#!/usr/bin/python3
"""
Update a specific file in a DBPF package.
"""
import os
import sys

# Our modules are in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from sims2patcher import dbpf

if not len(sys.argv) == 6:
    print(f"Usage: {sys.argv[0]} <package> <type_id> <group_id> <instance_id> <file>")
    print("IDs are represented in hexadecimal, for example: 0x856ddbac")
    sys.exit(1)

package_path = sys.argv[1]
type_id = int(sys.argv[2], 16)
group_id = int(sys.argv[3], 16)
instance_id = int(sys.argv[4], 16)
file_path = sys.argv[5]

if not os.path.exists(package_path):
    print(f"Package {package_path} does not exist.")
    sys.exit(1)

if not os.path.exists(file_path):
    print(f"File {file_path} does not exist.")
    sys.exit(1)

with open(file_path, "rb") as file:
    new_data = file.read()

package = dbpf.DBPF(package_path)
try:
    entry = package.get_entry(type_id, group_id, instance_id)
except ValueError:
    print(f"Entry with Type ID {type_id}, Group ID {group_id}, Instance ID {instance_id} not found.")
    sys.exit(1)

print(f"Updating entry: Type ID {type_id}, Group ID {group_id}, Instance ID {instance_id}")
entry.data = new_data
package.save_package(package_path)
print("Package saved.")
