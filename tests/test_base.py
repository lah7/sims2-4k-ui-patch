"""
Base class for shared functionality with other test modules.
"""
import hashlib
import os
import sys
import tempfile
import unittest

# Add the parent directory to the path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from sims2patcher import dbpf


class BaseTestCase(unittest.TestCase):
    """
    Base class for testing modules with a test (or real) DBPF package.
    """
    tmp_files = []

    @classmethod
    def setUpClass(cls):
        """
        Set up common test resources for all test methods.
        """
        # Change to the project root directory
        os.chdir(os.path.join(os.path.dirname(__file__), ".."))

        # Test package and its contents
        cls.package = dbpf.DBPF("tests/files/test.package")  # DBPF 1.1, Index 7.1

        # Compressed TGA graphic
        cls.tga_index = 0
        cls.tga_md5 = "4ff136c0acad717e113e121b9b265e57"
        cls.tga_group_id = 0x00001000
        cls.tga_instance_id = 0x00000001

        # Known uncompressed and incompressible PNG graphic
        cls.png_index = 2
        cls.png_md5 = "8cb89e702e8188fee04b0097f8aba9dc"
        cls.png_group_id = 0x00002000
        cls.png_instance_id = 0x00000003

    def tearDown(self) -> None:
        """Clean up temporary files"""
        for name in self.tmp_files:
            if os.path.exists(name):
                os.remove(name)
        return super().tearDown()

    def get_test_file_path(self, filename: str) -> str:
        """Return the path for a test file in tests/files/..."""
        path = f"tests/files/{filename}"
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing test file: {path}")
        return path

    def get_test_file_bytes(self, filename: str) -> bytes:
        """Return the text for a test file in tests/files/..."""
        with open(self.get_test_file_path(filename), "rb") as f:
            return f.read()

    def get_test_file_text(self, filename: str) -> str:
        """Return the text for a test file in tests/files/..."""
        with open(self.get_test_file_path(filename), "r", encoding="utf-8") as f:
            return f.read()

    def mktemp(self) -> str:
        """Create a temporary file and track it for cleanup."""
        tmp = tempfile.NamedTemporaryFile()
        self.tmp_files.append(tmp.name)
        return tmp.name

    @staticmethod
    def md5(data: bytes) -> str:
        """Return a MD5 checksum for comparison"""
        return hashlib.md5(data).hexdigest()
