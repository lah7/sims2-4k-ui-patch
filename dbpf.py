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
Handles the reading and creation of uncompressed ui.package files,
based on DBPF v1.1 format.
"""

# **Compression Incomplete!**
# - New .package files will not support compression.
# - SimPE is required for extracting the original files.

class Helpers():
    # Type IDs (as int)
    TYPE_UI_DATA = 0
    TYPE_IMAGE = 2238569388
    TYPE_ACCEL_DEF = 2732840243
    TYPE_DIR = 3899334383

    def read_at_position(self, start, end):
        """
        From the beginning of the file stream, jump to the specified 'start'
        position, read the bytes until the end position and return an integer.
        """
        self.stream.seek(0)
        self.stream.seek(start)
        return int.from_bytes(self.stream.read(end - start), "little")

    def read_next_dword(self):
        """
        Seek the next 4 bytes (DWORD) in the file stream and return an integer.
        """
        return int.from_bytes(self.stream.read(4), "little")

    def get_type(self, type_id):
        """
        Parse the Type ID into a string.
        """
        types = {
            self.TYPE_UI_DATA: "UI Data",
            self.TYPE_IMAGE: "Image File",
            self.TYPE_ACCEL_DEF: "Accelerator Key Definitions",
            self.TYPE_DIR: "Directory of Compressed Files",
        }
        try:
            return types[type_id]
        except KeyError:
            return f"Unknown ({hex(type_id)})"


class Header(Helpers):
    def __init__(self, stream):
        self.stream = stream
        self.major_version = self.read_at_position(4, 8)
        self.minor_version = self.read_at_position(8, 12)
        self.index_version_major = self.read_at_position(32, 36)
        self.index_version_minor = self.read_at_position(60, 64)
        self.index_entry_count = self.read_at_position(36, 40)
        self.index_start_offset = self.read_at_position(40, 44)
        self.index_size = self.read_at_position(44, 48)

        if not 1 in [self.major_version, self.minor_version, self.index_version_major, self.index_version_minor]:
            raise NotImplementedError("Incompatible package version!")


class Index(Helpers):
    class Entry(object):
        type_id = 0
        group_id = 0
        instance_id = 0
        file_location = 0
        file_size = 0

    def __init__(self, stream, header):
        self.stream = stream
        self.start = header.index_start_offset
        self.end = self.start + header.index_size
        self.count = header.index_entry_count
        self.entries = []

    def load(self):
        self.stream.seek(0)
        self.stream.seek(self.start)
        self.entries = []
        for no in range(0, self.count):
            entry = self.Entry()
            entry.type_id = self.read_next_dword()
            entry.group_id = self.read_next_dword()
            entry.instance_id = self.read_next_dword()
            entry.file_location = self.read_next_dword()
            entry.file_size = self.read_next_dword()
            self.entries.append(entry)

    def get_blob(self, entry):
        """
        Returns the bytes for the file from the specified entry.
        """
        self.stream.seek(0)
        self.stream.seek(entry.file_location)
        return self.stream.read(entry.file_size)


class Decompression(Helpers):
    """
    Handles the decompression of files from the .ui package, according to
    the "directory of compressed files" (0xE86B1EEF).

    <!> This implementation is incomplete! It can only list compressed files,
    ideally it can decompress so we don't need an external tool.
    """
    # https://simswiki.info/index.php?title=E86B1EEF
    # https://simswiki.info/index.php?title=DBPF_Compression

#    TODO: Checklist (at minimum, to be able to read)
    # ✔️ Read the DBPF header.
    # ✔️ Read the Index Tables.
    # ✔️ Check for a DIR record.
    #   Check for the file you want to extract.
    #   Is this file compressed? If so, decompress it.
    #   Read the file data and process accordingly.

    class CompressedEntry(object):
        type_id = 0
        group_id = 0
        instance_id = 0
        decompressed_size = 0

    def __init__(self, stream, index):
        self.stream = stream
        self.index = index
        self.entries = []

    def _seek_to_directory(self):
        """
        Jump to the position where the directory is located, and return the
        number of entries.
        """
        self.stream.seek(0)
        for entry in self.index.entries:
            if entry.type_id == self.TYPE_DIR:
                self.stream.seek(entry.file_location)
        return int(entry.file_size / 4)

    def load(self):
        total_compressed = self._seek_to_directory()
        self.entries = []
        for no in range(0, total_compressed):
            entry = self.CompressedEntry()
            entry.type_id = self.read_next_dword()
            entry.group_id = self.read_next_dword()
            entry.instance_id = self.read_next_dword()
            entry.decompressed_size = self.read_next_dword()
            self.entries.append(entry)

    def list_compressed(self):
        # TODO: Seems wrong, lots of unknown entries appear.
        print("Type ID", "Group ID", "Instance ID", "Decompressed Size")
        for index, entry in enumerate(self.entries):
            print("Compressed", index, "|",
                  self.get_type(entry.type_id),
                  hex(entry.group_id),
                  hex(entry.instance_id),
                  entry.decompressed_size)


class DBPF(Helpers):
    """
    Handles a DBPF Sims 2 ui.package file.
    """
    # https://www.wiki.sc4devotion.com/index.php?title=DBPF
    # https://www.wiki.sc4devotion.com/images/e/e8/DBPF_File_Format_v1.1.png
    def __init__(self, path):
        self.path = path
        self.stream = open(path, "rb")
        self.header = Header(self.stream)
        self.index = Index(self.stream, self.header)
        self.decompression = Decompression(self.stream, self.index)

    def list_entries(self):
        print("Type ID, Group ID, Instance ID, Location, Size")
        for index, entry in enumerate(self.index.entries):
            print("Entry", index, "|",
                  self.get_type(entry.type_id),
                  hex(entry.group_id),
                  hex(entry.instance_id),
                  hex(entry.file_location),
                  entry.file_size)


if __name__ == "__main__":
    # TODO: Add arguments to extract a DBPF file
    print("Test Mode")
    package = DBPF("ui.package")
    print("Index version", str(package.header.index_version_major) + '.' + str(package.header.index_version_minor))
    print("Offset", package.header.index_start_offset)
    print("Size", package.header.index_size)
    print("Entries", package.header.index_entry_count)
    package.index.load()
    package.decompression.load()
    package.list_entries()
    package.decompression.list_compressed()
