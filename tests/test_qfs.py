import unittest

import qfs


class QFSTest(unittest.TestCase):
    """
    Test our QFS module is able to handle Maxis' compression algorithm.
    """
    def test_compress(self):
        input = b"AAABBBCCCAAAAAABBBCCCDDDAAABBBABABAB"
        output = qfs.compress(bytearray(input))
        self.assertTrue(output != input)

    def test_decompress(self):
        expected = b"AAABBBCCCAAAAAABBBCCCDDDAAABBBABABAB"
        input = b' \x00\x00\x00\x00\x00\x00\x00\x00\xe1AAABBBCC\x01\x08C\x18\x0b\x0f\x0bDDD\t\x01A\xfc'
        output = qfs.decompress(bytearray(input), len(expected))
        self.assertTrue(expected == output)

    def test_non_compressable(self):
        input = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()"
        output = qfs.compress(bytearray(input))
        self.assertTrue(output == input)

    def test_header_compressed_size(self):
        input = b"AAABBBCCCAAAAAABBBCCCDDDAAABBBABABAB"
        output = qfs.compress(bytearray(input))
        got = int.from_bytes(output[0:4], byteorder="little")
        expected = len(bytes(output))
        self.assertTrue(got == expected)

    def test_header_compression_id(self):
        input = b"AAABBBCCCAAAAAABBBCCCDDDAAABBBABABAB"
        output = qfs.compress(bytearray(input))
        got = int.from_bytes(output[4:6], byteorder="little")
        expected = 0xFB10
        self.assertTrue(got == expected)

    def test_header_uncompressed_size(self):
        input = b"AAABBBCCCAAAAAABBBCCCDDDAAABBBABABAB"
        output = qfs.compress(bytearray(input))
        got = int.from_bytes(output[6:9], byteorder="big")
        expected = len(bytes(input))
        self.assertTrue(got == expected)
