"""
Perform tests on the QFS module to ensure that the compression
algorithm works as expected.
"""
import os
import sys
import unittest

# Our modules are in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from sims2patcher import qfs


class QFSTest(unittest.TestCase):
    """
    Test our QFS module is able to handle Maxis' compression algorithm.
    """
    def test_compress(self):
        """Test data can be compressed"""
        original = b"AAABBBCCCAAAAAABBBCCCDDDAAABBBABABAB"
        output = qfs.compress(bytearray(original))
        self.assertTrue(output != original)

    def test_decompress(self):
        """Test data can be decompressed to its original binary"""
        expected = b"AAABBBCCCAAAAAABBBCCCDDDAAABBBABABAB"
        original = b" \x00\x00\x00\x10\xfb\x00\x00\x00\xe1AAABBBCC\x01\x08C\x18\x0b\x0f\x0bDDD\t\x01A\xfc"
        output = qfs.decompress(bytearray(original), len(expected))
        self.assertTrue(expected == output)

    def test_non_compressable(self):
        """Test uncompressible data cannot be compressed"""
        original = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()"
        output = qfs.compress(bytearray(original))
        self.assertTrue(output == original)

    def test_header_compressed_size(self):
        """Test the size of compressed data is read correctly"""
        original = b"AAABBBCCCAAAAAABBBCCCDDDAAABBBABABAB"
        output = qfs.compress(bytearray(original))
        got = int.from_bytes(output[0:4], byteorder="little")
        expected = len(bytes(output))
        self.assertTrue(got == expected)

    def test_header_compression_id(self):
        """Test the header of the binary when compressed is QFS"""
        original = b"AAABBBCCCAAAAAABBBCCCDDDAAABBBABABAB"
        output = qfs.compress(bytearray(original))
        got = int.from_bytes(output[4:6], byteorder="little")
        expected = 0xFB10
        self.assertTrue(got == expected)

    def test_header_uncompressed_size(self):
        """Test the size of the original data is read correctly"""
        original = b"AAABBBCCCAAAAAABBBCCCDDDAAABBBABABAB"
        output = qfs.compress(bytearray(original))
        got = int.from_bytes(output[6:9], byteorder="big")
        expected = len(bytes(original))
        self.assertTrue(got == expected)
