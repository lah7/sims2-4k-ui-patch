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

class Helpers():
    def read_at_position(self, start, end):
        """
        From the beginning of the file stream, jump to the specified 'start'
        position, read the bytes until the end position and return an integer.
        """
        self.stream.seek(0)
        self.stream.seek(start)
        return int.from_bytes(self.stream.read(end - start), "little")


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


if __name__ == "__main__":
    package = DBPF("ui.package")
    print("Index version", str(package.header.index_version_major) + '.' + str(package.header.index_version_minor))
    print("Offset", package.header.index_start_offset)
    print("Size", package.header.index_size)
    print("Entries", package.header.index_entry_count)
