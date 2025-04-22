"""
Custom exceptions when files or entries cannot be processed.
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
# Copyright (C) 2024-2025 Luke Horwell <code@horwell.me>
#
from . import dbpf


#########################
# QFS
#########################
class QFSError(Exception):
    """Base class when there is a problem compressing or decompressing data"""


class InvalidMagicHeader(QFSError):
    """The 'magic' bytes indicating it's QFS compressed are missing. Maybe data is not compressed?"""
    def __init__(self, data: bytearray):
        super().__init__(f"Expected '\\xFB\\x10' at offset 4, but got {str(data[4:6])[11:-1]}")
        #                                                              bytearray(b'\x00\x00')
        #                                                                         ^^^^^^^^^^


class ArrayTooSmall(QFSError):
    """Decompressed data is larger than the array provided."""
    def __init__(self):
        super().__init__("Array too small")


class FileTooLarge(QFSError):
    """File is too large to be compressed, as data wouldn't fit in the QFS header"""
    def __init__(self, size):
        super().__init__(f"File too large to compress: {int(size / 1024 / 1024)} MiB (max 16 MiB)")


#########################
# DBPF
#########################
class DBPFError(Exception):
    """Base class for all DBPF related errors."""


class InvalidRequest(DBPFError):
    """Cannot read data from original package due to missing metadata"""
    def __init__(self, entry: "dbpf.Entry"):
        super().__init__(f"Missing file location or size, or empty file: Type ID {hex(entry.type_id)}, Group ID {hex(entry.group_id)}, Instance ID {hex(entry.instance_id)}")


#########################
# Patches
#########################
class UnknownImageFormatError(ValueError):
    """
    A file describing itself as an image has an unknown image header.
    Raise this exception to skip the file.
    """
