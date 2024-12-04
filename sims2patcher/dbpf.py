"""
Handles the reading of ui.package files for The Sims 2, utilising the
DBPF format to create, extract and compress packages.

Supports DBPF 1.1 and index versions 7.0, 7.1, 7.2.
"""
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
# Copyright (C) 2022-2024 Luke Horwell <code@horwell.me>
#
import io
from typing import Optional

from sims2patcher import qfs

# Known type IDs (represented as ints)
TYPE_UI_DATA = 0
TYPE_IMAGE = 2238569388 # 0x856ddbac
TYPE_ACCEL_DEF = 2732840243 # 0xa2e3d533
TYPE_DIR = 3899334383 # 0xe86b1eef

FILE_TYPES = {
    TYPE_UI_DATA: "UI Data",
    TYPE_IMAGE: "Image File",
    TYPE_ACCEL_DEF: "Accelerator Key Definitions",
    TYPE_DIR: "Directory of Compressed Files",
}


class Stream():
    """
    Base class used for other classes to handle file stream operations.
    """
    def __init__(self, stream: io.BytesIO):
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

    def get_type_as_string(self, type_id: int) -> str:
        """
        Return a string describing this Type ID.
        """
        try:
            return FILE_TYPES[type_id]
        except KeyError:
            return f"Unknown ({hex(type_id)})"


class Header(Stream):
    """
    Describe a header for the DBPF and its index.
    """
    def __init__(self, stream: io.BytesIO):
        super().__init__(stream)
        self.major_version = self.read_at_position(4, 8)
        self.minor_version = self.read_at_position(8, 12)
        self.index_version_major = self.read_at_position(32, 36)
        self.index_version_minor = self.read_at_position(60, 64)
        self.index_entry_count = self.read_at_position(36, 40)
        self.index_start_offset = self.read_at_position(40, 44)
        self.index_size = self.read_at_position(44, 48)

        # For initialising new packages
        if not self.major_version:
            self.major_version = 1
            self.minor_version = 1
            self.index_version_major = 7
            self.index_version_minor = 1

    @property
    def dbpf_version(self) -> float:
        """Return DBPF version as a decimal number, e.g. 1.1"""
        return float(f"{self.major_version}.{self.minor_version}")

    @property
    def index_version(self) -> float:
        """Return index version as a decimal number, e.g. 7.1"""
        return float(f"{self.index_version_major}.{self.index_version_minor}")


class Entry(object):
    """
    Metadata and data about an individual file in the index
    """
    def __init__(self, stream: io.BytesIO):
        self._stream: io.BytesIO = stream

        self.type_id = 0
        self.group_id = 0
        self.instance_id = 0
        self.resource_id = 0 # Index version >= 7.2 only
        self.file_location = 0
        self.file_size = 0
        self.decompressed_size = 0

        # Data as stored in the original source package, or new data for the package
        # This could be storing compressed or uncompressed data.
        self._bytes = bytes()
        self._bytes_compressed = False

        # Cached uncompressed data for this session (for compressed files only)
        self._cache_uncompressed_data = bytes()

        # Mark this file as compressed in the output package
        self.compress = False

    def populate_bytes(self):
        """
        Read the data as-is from the original package, if it hasn't already.
        The bytes could be compressed or uncompressed.
        """
        if self._bytes:
            return

        if not self.file_location or not self.file_size:
            raise ValueError(f"Missing file location or size, or empty file: Type ID {self.type_id}, Group ID {self.group_id}, Instance ID {self.instance_id}")

        self._stream.seek(0)
        self._stream.seek(self.file_location)
        self._bytes = self._stream.read(self.file_size)

    @property
    def data(self) -> bytes:
        """
        Return the bytes for a file's contents, uncompressed if necessary.
        This is suitable for reading a file for processing.

        An error is raised if the data is compressed but cannot be decompressed.
        Make sure the `_bytes_compressed` variable is set correctly.
        """
        if not self._bytes and self.file_location and self.file_size:
            self.populate_bytes()

        if self._bytes_compressed:
            if self._cache_uncompressed_data:
                return self._cache_uncompressed_data

            try:
                self._cache_uncompressed_data = qfs.decompress(bytearray(self._bytes), self.decompressed_size)
            except IndexError as e:
                raise ValueError(f"Decompression failed: Type ID {self.type_id}, Group ID {self.group_id}, Instance ID {self.instance_id}") from e

            return self._cache_uncompressed_data

        return self._bytes

    def _compress_data(self, data: bytes) -> bytes:
        """
        Return the bytes for how it will be stored in the resulting package.
        If the data cannot be compressed, it will be left uncompressed.
        """
        decompressed_size = len(data)
        compressed_data = bytes()

        try:
            compressed_data = qfs.compress(bytearray(data))

            # Did the compression actually make the file larger instead?
            if len(compressed_data) > self.decompressed_size:
                return bytes()

        except (IndexError, OverflowError):
            # Compression not possible
            return bytes()

        # Verify compression was successful
        try:
            expected_data = qfs.decompress(bytearray(compressed_data), decompressed_size)
            if expected_data != data:
                return bytes()
        except IndexError:
            return bytes()

        return compressed_data

    @data.setter
    def data(self, data: bytes):
        """
        Store the data for this file, and compress if necessary.
        This is suitable for storing the result of a processed file.

        If the data cannot be compressed, it will be left uncompressed.
        """
        self.decompressed_size = len(data)
        self._cache_uncompressed_data = bytes()

        if self.compress:
            compressed_data = self._compress_data(data)

            if compressed_data:
                self._bytes = compressed_data
                self._bytes_compressed = True
                self._cache_uncompressed_data = data
            else:
                self._bytes = data
                self._bytes_compressed = False
                self.compress = False
        else:
            self._bytes = data
            self._bytes_compressed = False

    @property
    def raw(self) -> bytes:
        """
        Return the bytes for how the file will be stored in the package.
        """
        if not self._bytes:
            self.populate_bytes()
        return self._bytes


class Index(Stream):
    """
    Represents the DBPF file index
    """
    def __init__(self, stream, header: Header):
        super().__init__(stream)
        self.start = header.index_start_offset
        self.end = self.start + header.index_size
        self.count = header.index_entry_count
        self.entries: list[Entry] = []
        self.dir = DirectoryFile(stream, header)

        # Load entries from package
        self.stream.seek(0)
        self.stream.seek(self.start)
        for _ in range(0, self.count):
            entry = Entry(self.stream)
            entry.type_id = self.read_next_dword()
            entry.group_id = self.read_next_dword()
            entry.instance_id = self.read_next_dword()
            if header.index_version >= 7.2:
                entry.resource_id = self.read_next_dword()
            entry.file_location = self.read_next_dword()
            entry.file_size = self.read_next_dword()
            self.entries.append(entry)

        # Find DIR file in index, indicating some files are compressed
        self.stream.seek(0)
        for entry in self.entries:
            if entry.type_id == TYPE_DIR:
                self.dir = DirectoryFile(self.stream, header, entry)

        # If DIR file exists, flag entries that were compressed
        compressed_index_lookup = {}
        if self.dir:
            for dir_entry in self.dir.files:
                assert isinstance(dir_entry, DirectoryFile.CompressedFile)
                compressed_index_lookup[(dir_entry.type_id, dir_entry.group_id, dir_entry.instance_id, dir_entry.resource_id)] = dir_entry

            for entry in self.entries:
                if (entry.type_id, entry.group_id, entry.instance_id, entry.resource_id) in compressed_index_lookup:
                    dir_entry: DirectoryFile.CompressedFile = compressed_index_lookup[(entry.type_id, entry.group_id, entry.instance_id, entry.resource_id)]
                    entry._bytes_compressed = True
                    entry.compress = True
                    entry.decompressed_size = dir_entry.decompressed_size


class DirectoryFile(Stream):
    """
    The directory file is included in the DBPF when there are compressed files.
    This type is 0xE86B1EEF and describes what is compressed in this package.

    Directory file format:
    https://simswiki.info/index.php?title=E86B1EEF

    Compressed files use this header:
    https://simswiki.info/index.php?title=DBPF_Compression
    """
    class CompressedFile(object):
        """Metadata describing a compressed file in the index"""
        type_id = 0
        group_id = 0
        instance_id = 0
        resource_id = 0 # Index version >= 7.2 only
        decompressed_size = 0

    def __init__(self, stream: io.BytesIO, header: Header, dir_entry: Optional[Entry] = None):
        super().__init__(stream)
        self.header = header
        self.files = []
        self.group_id = 0
        self.instance_id = 0
        self.resource_id = 0

        if dir_entry:
            self.group_id = dir_entry.group_id
            self.instance_id = dir_entry.instance_id
            self.resource_id = dir_entry.resource_id

            # Found DIR file, read it
            self.stream.seek(dir_entry.file_location)
            compressed_count = int(dir_entry.file_size / 16) # (DWORD = 4 bytes) x 4
            for _ in range(0, compressed_count):
                entry = self.CompressedFile()
                entry.type_id = self.read_next_dword()
                entry.group_id = self.read_next_dword()
                entry.instance_id = self.read_next_dword()
                if self.header.index_version >= 7.2:
                    entry.resource_id = self.read_next_dword()
                entry.decompressed_size = self.read_next_dword()

                self.files.append(entry)

    def add_entry(self, type_id: int, group_id: int, instance_id: int, resource_id: int, decompressed_size: int):
        """
        Add to the record that a particular file is stored as compressed in the package.
        """
        entry = self.CompressedFile()
        entry.type_id = type_id
        entry.group_id = group_id
        entry.instance_id = instance_id
        entry.resource_id = resource_id
        entry.decompressed_size = decompressed_size
        self.files.append(entry)

    def get_bytes(self) -> bytes:
        """
        Return the raw bytes for the DIR file as it will be stored in the package.
        """
        blob = bytearray()
        for entry in self.files:
            assert isinstance(entry, DirectoryFile.CompressedFile)
            blob += entry.type_id.to_bytes(4, "little")
            blob += entry.group_id.to_bytes(4, "little")
            blob += entry.instance_id.to_bytes(4, "little")
            if self.header.index_version >= 7.2:
                blob += entry.resource_id.to_bytes(4, "little")
            blob += entry.decompressed_size.to_bytes(4, "little")

        return blob


class DBPF(Stream):
    """
    Handles a DBPF Sims 2 ui.package file.
    This is the main interface to read and write DBPF files.

    DBPF Format Reference:
    https://www.wiki.sc4devotion.com/index.php?title=DBPF
    https://www.wiki.sc4devotion.com/images/e/e8/DBPF_File_Format_v1.1.png
    """
    def __init__(self, path: str = ""):
        """
        Read an existing DBPF package, or leave blank to create a new one.
        """
        super().__init__(io.BytesIO(bytearray(32)))
        if path:
            with open(path, "rb") as f:
                self.stream = io.BytesIO(f.read())

        self.header = Header(self.stream)
        self.index = Index(self.stream, self.header)

    def get_entries(self) -> list[Entry]:
        """
        Return all the entries from the index.
        """
        return self.index.entries

    def get_entry(self, type_id: int, group_id: int, instance_id: int, resource_id = 0) -> Entry:
        """
        Return a single entry from the index.
        """
        for entry in self.index.entries:
            if entry.type_id == type_id and entry.group_id == group_id and entry.instance_id == instance_id and entry.resource_id == resource_id:
                return entry
        raise ValueError(f"Entry not found: Type ID {type_id}, Group ID {group_id}, Instance ID {instance_id}, Resource ID {resource_id}")

    def add_entry(self, type_id: int, group_id: int, instance_id: int, resource_id: int, data: bytes, compress=False) -> Entry:
        """
        Add a new file to the index.
        """
        entry = Entry(self.stream)
        entry.type_id = type_id
        entry.group_id = group_id
        entry.instance_id = instance_id
        entry.resource_id = resource_id
        entry.compress = compress
        entry.data = data
        self.index.entries.append(entry)
        return entry

    def add_entry_from_file(self, type_id: int, group_id: int, instance_id: int, resource_id: int, path: str, compress=False) -> Entry:
        """
        Add a new file to the index, reading bytes from a file on disk.
        """
        with open(path, "rb") as f:
            data = f.read()
        return self.add_entry(type_id, group_id, instance_id, resource_id, data, compress)

    def save_package(self, path: str):
        """
        Write a new DBPF package to disk.
        If the file at the destination path exists, it will be overwritten!

        Low-level data for the DBPF is handled here, like:
        - File location and file size within the package.
        - Generate the DIR record for compressed files.
        - Compress entries marked as "compress".
        """
        def _write_int_at_pos(position: int, integer: int):
            f.seek(position)
            f.write(integer.to_bytes(integer.bit_length(), "little"))

        def _write_int_next_4_bytes(integer):
            f.tell()
            end = f.tell() + 4
            f.write(integer.to_bytes(integer.bit_length(), "little"))
            f.seek(end)

        # Before writing, read anything from the original package that hasn't been read yet
        for entry in self.get_entries():
            entry.populate_bytes()

        # Check the file is writable, and create if doesn't exist
        try:
            open(path, "wb").close()
        except PermissionError as e:
            raise PermissionError("Permission denied. Check the permissions and try again.") from e

        # Allocate bytes for header
        f = open(path, "wb")
        f.write(bytes(96))

        # Write file data after the header
        f.seek(96)

        # Discard any old DIR record from the index. A new one will be created later if we have compressed files.
        self.index.entries = [entry for entry in self.index.entries if entry.type_id != TYPE_DIR]
        self.index.dir.files = []
        needs_dir_record = False

        for entry in self.get_entries():
            entry.file_location = f.tell()
            f.write(entry.raw)

            if entry.compress:
                needs_dir_record = True
                self.index.dir.add_entry(entry.type_id, entry.group_id, entry.instance_id, entry.resource_id, entry.decompressed_size)

            entry.file_size = f.tell() - entry.file_location

        # Generate a new DIR record (for any compressed files)
        if needs_dir_record:
            entry = Entry(self.stream)
            entry.type_id = TYPE_DIR
            entry.group_id = self.index.dir.group_id
            entry.instance_id = self.index.dir.instance_id
            entry.resource_id = self.index.dir.resource_id

            entry.file_location = f.tell()
            f.write(self.index.dir.get_bytes())
            entry.file_size = f.tell() - entry.file_location

            self.index.entries.append(entry)

        # Write index after the file data
        self.header.index_start_offset = f.tell()
        self.header.index_entry_count = len(self.index.entries)

        for entry in self.index.entries:
            _write_int_next_4_bytes(entry.type_id)
            _write_int_next_4_bytes(entry.group_id)
            _write_int_next_4_bytes(entry.instance_id)
            if self.header.index_version >= 7.2:
                _write_int_next_4_bytes(entry.resource_id)
            _write_int_next_4_bytes(entry.file_location)
            _write_int_next_4_bytes(entry.file_size)

        self.header.index_size = f.tell() - self.header.index_start_offset

        # Write header: DBPF
        f.seek(0)
        f.write(b"\x44\x42\x50\x46")

        # Write header: Major version
        _write_int_at_pos(4, self.header.major_version)

        # Write header: Minor version
        _write_int_at_pos(8, self.header.minor_version)

        # Write header: Index version major
        _write_int_at_pos(32, self.header.index_version_major)

        # Write header: Index entry count
        _write_int_at_pos(36, self.header.index_entry_count)

        # Write header: Index start offset
        _write_int_at_pos(40, self.header.index_start_offset)

        # Write header: Index entry size
        _write_int_at_pos(44, self.header.index_size)

        # Write header: Index version minor
        _write_int_at_pos(60, self.header.index_version_minor)

        f.close()
