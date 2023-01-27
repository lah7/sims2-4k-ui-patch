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
# Copyright (C) 2022-2023 Luke Horwell <code@horwell.me>
#
"""
Handles the reading of ui.package files for The Sims 2, with the ability
to create uncompressed DBPF files.

Based on DBPF 1.1 / Index v7.1 format.
"""
import qfs
import io


class Stream():
    """
    Base class for all file stream operations.
    """
    # Type IDs (as int)
    TYPE_UI_DATA = 0
    TYPE_IMAGE = 2238569388
    TYPE_ACCEL_DEF = 2732840243
    TYPE_DIR = 3899334383

    def __init__(self, stream: io.BufferedReader):
        self.stream = stream

    def read_at_position(self, start: int, end: int) -> int:
        """
        From the beginning of the file stream, jump to the specified 'start'
        position, read the bytes until the end position and return an integer.
        """
        self.stream.seek(0)
        self.stream.seek(start)
        return int.from_bytes(self.stream.read(end - start), "little")

    def read_next_dword(self) -> int:
        """
        Seek the next 4 bytes (DWORD) in the file stream and return an integer.
        """
        return int.from_bytes(self.stream.read(4), "little")

    def get_type(self, type_id: int) -> str:
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


class Header(Stream):
    """
    Describe a header for DBPF version 1.1 and 7.1 index.
    """
    def __init__(self, stream: io.BufferedReader):
        super().__init__(stream)
        self.major_version = self.read_at_position(4, 8)
        self.minor_version = self.read_at_position(8, 12)
        self.index_version_major = self.read_at_position(32, 36)
        self.index_version_minor = self.read_at_position(60, 64)
        self.index_entry_count = self.read_at_position(36, 40)
        self.index_start_offset = self.read_at_position(40, 44)
        self.index_size = self.read_at_position(44, 48)


class Index(Stream):
    class Entry(object):
        type_id = 0
        group_id = 0
        instance_id = 0
        file_location = 0
        file_size = 0
        compressed = False

        # Blob will be empty for existing files, use get_blob().
        blob = bytes()

    def __init__(self, stream, header):
        super().__init__(stream)
        self.start = header.index_start_offset
        self.end = self.start + header.index_size
        self.count = header.index_entry_count
        self.entries: list[Index.Entry] = []
        self.dir = DirectoryFile(stream, self.Entry())

        # Load entries from package
        self.stream.seek(0)
        self.stream.seek(self.start)
        for no in range(0, self.count):
            entry = self.Entry()
            entry.type_id = self.read_next_dword()
            entry.group_id = self.read_next_dword()
            entry.instance_id = self.read_next_dword()
            entry.file_location = self.read_next_dword()
            entry.file_size = self.read_next_dword()
            self.entries.append(entry)

        # Find DIR file in index, indicating some files are compressed
        self.stream.seek(0)
        for entry in self.entries:
            if entry.type_id == self.TYPE_DIR:
                self.stream.seek(entry.file_location)
                self.dir = DirectoryFile(self.stream, entry)

        # If DIR file exists, update entries
        if self.dir:
            for entry in self.entries:
                entry.compressed = False
                for c_entry in self.dir.entries:
                    if c_entry.type_id == entry.type_id and c_entry.group_id == entry.group_id and c_entry.instance_id == entry.instance_id:
                        entry.compressed = True


class DirectoryFile(Stream):
    """
    The directory file is included in the DBPF when there are compressed files.
    This type is 0xE86B1EEF.

    https://simswiki.info/index.php?title=E86B1EEF
    https://simswiki.info/index.php?title=DBPF_Compression
    """
    class CompressedEntry(object):
        type_id = 0
        group_id = 0
        instance_id = 0
        decompressed_size = 0

    def __init__(self, stream: io.BufferedReader, dir_entry: Index.Entry):
        super().__init__(stream)
        self.entries = []
        self.dir_entry = dir_entry

        # Found DIR file, read it
        compressed_count = int(self.dir_entry.file_size / 4)
        for no in range(0, compressed_count):
            entry = self.CompressedEntry()
            entry.type_id = self.read_next_dword()
            entry.group_id = self.read_next_dword()
            entry.instance_id = self.read_next_dword()
            entry.decompressed_size = self.read_next_dword()
            if entry.type_id == 0 and entry.group_id == 0 and entry.instance_id == 0:
                break
            self.entries.append(entry)

    def lookup_entry(self, entry: Index.Entry) -> CompressedEntry:
        for compress_entry in self.entries:
            if entry.type_id == compress_entry.type_id and entry.group_id == compress_entry.group_id and entry.instance_id == compress_entry.instance_id:
                return compress_entry
        return self.CompressedEntry()


class DBPF(Stream):
    """
    Handles a DBPF Sims 2 ui.package file.

    https://www.wiki.sc4devotion.com/index.php?title=DBPF
    https://www.wiki.sc4devotion.com/images/e/e8/DBPF_File_Format_v1.1.png
    """
    def __init__(self, path: str):
        self.path = path
        self.stream = open(path, "rb")
        self.header = Header(self.stream)
        self.index = Index(self.stream, self.header)

    def list_entries(self):
        print("        | Compressed | Type ID | Group ID | Instance ID | Location | Size | Label")
        for index, entry in enumerate(self.index.entries):
            print("Entry", index, "|",
                entry.compressed, "|",
                hex(entry.type_id), "|",
                hex(entry.group_id), "|",
                hex(entry.instance_id), "|",
                entry.file_location, "|",
                entry.file_size, "|",
                self.get_type(entry.type_id))

    def add_file(self, type_id=0, group_id=0, instance_id=0, data=bytes()):
        """
        Add new data to the index (for new packages)
        """
        entry = self.index.Entry()
        entry.type_id = type_id
        entry.group_id = group_id
        entry.instance_id = instance_id
        entry.blob = data
        self.index.entries.append(entry)

    def add_file_from_path(self, type_id: int, group_id: int, instance_id: int, path: str):
        """
        Read path and add the data into index (for new packages)
        """
        with open(path, "rb") as f:
            data = f.read()
        return self.add_file(type_id, group_id, instance_id, data)

    def get_blob(self, entry: Index.Entry) -> bytes:
        """
        Returns the bytes for the file from the specified entry.
        This data could be either compressed or uncompressed.
        """
        self.stream.seek(0)
        self.stream.seek(entry.file_location)
        return self.stream.read(entry.file_size)

    def extract(self, entry: Index.Entry, path: str):
        """
        Extracts a file described by an entry to the specified file path.
        If the data is compressed, it will be decompressed.
        """
        blob = self.get_blob(entry)
        if entry.compressed:
            compressed_entry = self.index.dir.lookup_entry(entry)
            data = qfs.decompress(bytearray(blob), compressed_entry.decompressed_size)
        else:
            data = blob
        with open(path, "wb") as file:
            file.write(data)

    def save(self, path: str):
        """
        Write a new DBPF to disk (for new packages). The destination file
        should be empty.

        Internally, the index's file location and size will be determined here.
        """
        open(path, "w").close()
        f = open(path, "wb")

        # The header is 96 bytes
        f.write(bytes(96))

        def _write_int_at_pos(position: int, integer: int):
            f.seek(position)
            f.write(integer.to_bytes(integer.bit_length(), "little"))

        def _write_int_next_4_bytes(integer):
            start = f.tell()
            end = f.tell() + 4
            f.write(integer.to_bytes(integer.bit_length(), "little"))
            f.seek(end)

        # Start by writing file data (blobs) after the header
        f.seek(96)
        for entry in self.index.entries:
            entry.file_location = f.tell()
            f.write(entry.blob)
            entry.file_size = f.tell() - entry.file_location

        # Write index after the blobs
        self.header.index_start_offset = f.tell()
        self.header.index_entry_count = len(self.index.entries)

        for entry in self.index.entries:
            _write_int_next_4_bytes(entry.type_id)
            _write_int_next_4_bytes(entry.group_id)
            _write_int_next_4_bytes(entry.instance_id)
            _write_int_next_4_bytes(entry.file_location)
            _write_int_next_4_bytes(entry.file_size)

        self.header.index_size = f.tell() - self.header.index_start_offset

        # Write header: DBPF
        f.seek(0)
        f.write(b'\x44\x42\x50\x46')

        # Write header: Major version
        _write_int_at_pos(4, 0x1)

        # Write header: Minor version
        _write_int_at_pos(8, 0x2)

        # Write header: Index version major
        _write_int_at_pos(32, 0x7)

        # Write header: Index entry count
        _write_int_at_pos(36, self.header.index_entry_count)

        # Write header: Index start offset
        _write_int_at_pos(40, self.header.index_start_offset)

        # Write header: Index entry size
        _write_int_at_pos(44, self.header.index_size)

        # Write header: Index version minor
        _write_int_at_pos(60, 0x1)


if __name__ == "__main__":
    # TODO: Add arguments to extract a DBPF file
    print("Test Mode")
    package = DBPF("ui.package")
    print("Index version", str(package.header.index_version_major) + '.' + str(package.header.index_version_minor))
    print("Offset", package.header.index_start_offset)
    print("Size", package.header.index_size)
    print("Entries", package.header.index_entry_count)
    package.list_entries()
