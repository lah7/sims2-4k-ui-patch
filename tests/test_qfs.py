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
