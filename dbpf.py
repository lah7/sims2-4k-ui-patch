"""
Handles the reading of ui.package files for The Sims 2, utilising the
DBPF format to create, extract and compress packages.

Based on DBPF 1.1 / Index v7.1 format.
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

import qfs


class Stream():
    """
    Base class used for other classes to handle file stream operations.
    """
    # Type IDs (as int)
    TYPE_UI_DATA = 0
    TYPE_IMAGE = 2238569388
    TYPE_ACCEL_DEF = 2732840243
    TYPE_DIR = 3899334383

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

    def get_type(self, type_id: int) -> str:
        """
        Return a string describing this Type ID.
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
    def __init__(self, stream: io.BytesIO):
        super().__init__(stream)
        self.major_version = self.read_at_position(4, 8)
        self.minor_version = self.read_at_position(8, 12)
        self.index_version_major = self.read_at_position(32, 36)
        self.index_version_minor = self.read_at_position(60, 64)
        self.index_entry_count = self.read_at_position(36, 40)
        self.index_start_offset = self.read_at_position(40, 44)
        self.index_size = self.read_at_position(44, 48)


class Index(Stream):
    """Represents the DBPF file index"""
    class Entry(object):
        """Metadata and data about an individual file in the index"""
        type_id = 0
        group_id = 0
        instance_id = 0
        file_location = 0
        file_size = 0
        compress = False # Whether this file should be compressed in the package
        data = bytes() # Uncompressed bytes
        raw = bytes() # Bytes as stored in package, could be compressed or uncompressed

    def __init__(self, stream, header: Header):
        super().__init__(stream)
        self.start = header.index_start_offset
        self.end = self.start + header.index_size
        self.count = header.index_entry_count
        self.entries: list[Index.Entry] = []
        self.dir = DirectoryFile(stream)

        # Load entries from package
        self.stream.seek(0)
        self.stream.seek(self.start)
        for _ in range(0, self.count):
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
                self.dir = DirectoryFile(self.stream, entry)

        # If DIR file exists, flag entries that were compressed
        if self.dir:
            for entry in self.entries:
                for c_entry in self.dir.files:
                    assert isinstance(c_entry, DirectoryFile.CompressedFile)
                    if c_entry.type_id == entry.type_id and c_entry.group_id == entry.group_id and c_entry.instance_id == entry.instance_id:
                        entry.compress = True


class DirectoryFile(Stream):
    """
    The directory file is included in the DBPF when there are compressed files.
    This type is 0xE86B1EEF and describes what is compressed in this package.

    Directory file format:
    https://simswiki.info/index.php?title=E86B1EEF

    The index version of the original game packages is 7.1, but for some reason
    this doesn't match the documentation which says there should be a
    resource ID field too. As a result, this class will read/write under
    index version 7.0 so it is compatible with The Sims 2.

    Compressed files use this header:
    https://simswiki.info/index.php?title=DBPF_Compression
    """
    class CompressedFile(object):
        """Metadata describing a compressed file in the index"""
        type_id = 0
        group_id = 0
        instance_id = 0
        decompressed_size = 0

        # Index version 7.1 supposedly has this, but The Sims 2 (also index ver. 7.1) doesn't.
        resource_id = 0

    def __init__(self, stream: io.BytesIO, dir_entry: Optional[Index.Entry] = None):
        super().__init__(stream)
        self.files = []
        self.group_id = 0
        self.instance_id = 0

        if dir_entry:
            self.group_id = dir_entry.group_id
            self.instance_id = dir_entry.instance_id

            # Found DIR file, read it
            self.stream.seek(dir_entry.file_location)
            compressed_count = int(dir_entry.file_size / 16) # (DWORD = 4 bytes) x 4
            for _ in range(0, compressed_count):
                entry = self.CompressedFile()
                entry.type_id = self.read_next_dword()
                entry.group_id = self.read_next_dword()
                entry.instance_id = self.read_next_dword()
                entry.decompressed_size = self.read_next_dword()

                # Index version 7.1 supposedly has this, but The Sims 2 (also index ver. 7.1) doesn't.
                #entry.resource_id = self.read_next_dword()

                self.files.append(entry)

    def lookup_entry(self, entry: Index.Entry) -> CompressedFile:
        """
        Read the DIR records and return compressed metadata for this index entry.
        If not, return an empty record.
        """
        for compress_entry in self.files:
            assert isinstance(compress_entry, DirectoryFile.CompressedFile)
            if entry.type_id == compress_entry.type_id and entry.group_id == compress_entry.group_id and entry.instance_id == compress_entry.instance_id:
                return compress_entry
        return self.CompressedFile()

    def add_entry(self, type_id: int, group_id: int, instance_id: int, decompressed_size: int):
        """
        Add to the record that a particular file is stored as compressed in the package.
        """
        entry = self.CompressedFile()
        entry.type_id = type_id
        entry.group_id = group_id
        entry.instance_id = instance_id
        entry.decompressed_size = decompressed_size
        self.files.append(entry)

    def get_bytes(self) -> bytes:
        """
        Return the raw bytes for the DIR file as it is stored in the package.
        """
        blob = bytearray()
        for entry in self.files:
            assert isinstance(entry, DirectoryFile.CompressedFile)
            blob += entry.type_id.to_bytes(4, "little")
            blob += entry.group_id.to_bytes(4, "little")
            blob += entry.instance_id.to_bytes(4, "little")
            blob += entry.decompressed_size.to_bytes(4, "little")

            # Index version 7.1 supposedly has this, but The Sims 2 (also index ver. 7.1) doesn't.
            #blob += entry.resource_id.to_bytes(4, "little")
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
        Load an existing DBPF package into memory, or leave blank to create one.
        """
        super().__init__(io.BytesIO(bytearray(32)))
        if path:
            with open(path, "rb") as f:
                self.stream = io.BytesIO(f.read())

        self.header = Header(self.stream)
        self.index = Index(self.stream, self.header)
        for entry in self.index.entries:
            entry.raw = self._get_bytes(entry)
            if entry.compress:
                compressed_entry = self.index.dir.lookup_entry(entry)
                try:
                    entry.data = qfs.decompress(bytearray(entry.raw), compressed_entry.decompressed_size)
                except IndexError as e:
                    raise ValueError(f"Decompression failed. File corrupt: Type ID {entry.type_id}, Group ID {entry.group_id}, Instance ID {entry.instance_id}") from e
            else:
                entry.data = entry.raw

    def _get_bytes(self, entry: Index.Entry) -> bytes:
        """
        Returns the raw bytes as it is stored in the package.
        This data could be either compressed or uncompressed.
        """
        self.stream.seek(0)
        self.stream.seek(entry.file_location)
        return self.stream.read(entry.file_size)

    def _compress_entry(self, entry: Index.Entry) -> bool:
        """
        Compress the data for this file into its raw bytes. This is how it'll
        be stored in the package. To prevent corruption, the data will
        be decompressed in memory to verify the compression works.

        Returns a boolean to indicate whether this operation was successful.

        Successfully compressed data will:
        - Add to the DIR record.
        - Update the "raw" variable for the entry. The calling function should
        update the "compressed" variable to the boolean returned by this function.
        """
        output = bytearray()
        decompressed_size = len(entry.data)

        try:
            output = qfs.compress(bytearray(entry.data))
        except IndexError:
            return False

        # Did the compression actually make the file larger instead?
        if len(output) > decompressed_size:
            return False

        # Verify decompression
        # (For example, certain bitmaps might compress, but fail to decompress)
        try:
            expected_input = qfs.decompress(bytearray(output), decompressed_size)
            if expected_input != entry.data:
                return False
        except IndexError:
            return False

        # Add successful compressed file to DIR record
        entry.raw = output
        self.index.dir.add_entry(entry.type_id, entry.group_id, entry.instance_id, len(entry.data))

        return True

    @staticmethod
    def cb_save_progress_updated(text: str, value: int, total: int):
        """
        Callback function to update the user-facing view of progress, like a GUI or stdout.
        This can be optionally be overridden by the caller using the same parameters.

        Parameters required:
            text    (str)   An action word to describe the operation, e.g. "Writing" or "Compressing"
            value   (int)   Current entry number being processed
            total   (int)   Total entries in the package
        """
        # Example:
        # print(f"\r{status}: {value / total*100:.2f}%", end="}")

    def get_entries(self) -> list[Index.Entry]:
        """
        Return all the entries from the index.
        """
        return self.index.entries

    def get_entry(self, type_id: int, group_id: int, instance_id: int) -> Index.Entry:
        """
        Return a single entry from the index.
        """
        for entry in self.index.entries:
            if entry.type_id == type_id and entry.group_id == group_id and entry.instance_id == instance_id:
                return entry
        raise ValueError(f"Entry not found: Type ID {type_id}, Group ID {group_id}, Instance ID {instance_id}")

    def add_entry(self, type_id=0, group_id=0, instance_id=0, data=bytes(), compress=False) -> Index.Entry:
        """
        Add a new file to the index.
        """
        entry = self.index.Entry()
        entry.type_id = type_id
        entry.group_id = group_id
        entry.instance_id = instance_id
        entry.compress = compress
        entry.data = data
        entry.raw = data
        self.index.entries.append(entry)
        return entry

    def add_entry_from_file(self, type_id: int, group_id: int, instance_id: int, path: str, compress=False) -> Index.Entry:
        """
        Add a new file to the index, reading bytes from a file on disk.
        """
        with open(path, "rb") as f:
            data = f.read()
        return self.add_entry(type_id, group_id, instance_id, data, compress)

    def save_package(self, path: str):
        """
        Write a new DBPF package to disk.
        If the file at the destination path exists, it will be overwritten!

        Low-level data for the DBPF is handled here, like:
        - File location and file size within the package.
        - Generate the DIR record for compressed files.
        - Compress entries marked as "compress".
        """
        # Check the file is writable, and create if doesn't exist
        try:
            open(path, "wb").close()
        except PermissionError as e:
            raise PermissionError("Permission denied. Check the permissions and try again.") from e

        # Compress in-memory data (if applicable)
        self.index.dir.files = []
        needs_dir_record = False

        current_entry = -1
        total_entries = len(self.get_entries())
        for entry in self.get_entries():
            self.cb_save_progress_updated("Saving", current_entry, total_entries)
            current_entry += 1

            # Destroy old DIR record, a new one is created later
            if entry.type_id == self.TYPE_DIR:
                self.index.entries.remove(entry)
                continue

            # Entries should have at least one byte of data
            if not entry.raw or not entry.data:
                raise ValueError(f"Entry contains no data: Type ID {entry.type_id}, Group ID {entry.group_id}, Instance ID {entry.instance_id}")

            # Compress the file now (if applicable)
            entry.raw = entry.data
            if entry.compress:
                self.cb_save_progress_updated("Compressing", current_entry, total_entries)
                entry.compress = self._compress_entry(entry)
                if entry.compress:
                    needs_dir_record = True

        # Generate a new DIR record (if applicable)
        if needs_dir_record:
            dir_entry = self.index.Entry()
            dir_entry.type_id = self.TYPE_DIR
            dir_entry.group_id = self.index.dir.group_id
            dir_entry.instance_id = self.index.dir.instance_id
            dir_entry.raw = self.index.dir.get_bytes()
            self.index.entries.append(dir_entry)

        self.cb_save_progress_updated("Writing", 9999, 10000)

        # Write the bytes!
        f = open(path, "wb")

        # The header is 96 bytes
        f.write(bytes(96))

        def _write_int_at_pos(position: int, integer: int):
            f.seek(position)
            f.write(integer.to_bytes(integer.bit_length(), "little"))

        def _write_int_next_4_bytes(integer):
            f.tell()
            end = f.tell() + 4
            f.write(integer.to_bytes(integer.bit_length(), "little"))
            f.seek(end)

        # Start by writing file data (blobs) after the header
        f.seek(96)
        for entry in self.index.entries:
            entry.file_location = f.tell()
            f.write(entry.raw)
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

        f.close()
