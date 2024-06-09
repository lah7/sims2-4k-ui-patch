"""
Perform tests on the patches module to ensure that an input
and output works as expected.
"""
# pylint: disable=protected-access
import hashlib
import os
import shutil
import tempfile
import unittest

import dbpf
import patches
from gamefile import GameFile


class PatchesTest(unittest.TestCase):
    """
    Test our "patches" module against test files.
    """
    tmp_files = []

    def _mktemp(self):
        tmp = tempfile.NamedTemporaryFile()
        self.tmp_files.append(tmp.name)
        return tmp.name

    @staticmethod
    def _get_test_file_path(filename):
        path = f"tests/files/{filename}"
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing test file: {path}")
        return path

    def _get_test_file_data(self, filename):
        with open(self._get_test_file_path(filename), "r", encoding="utf-8") as f:
            return f.read()

    @classmethod
    def setUpClass(cls):
        cls.ui_package = dbpf.DBPF(cls._get_test_file_path("ui.package"))
        return super().setUpClass()

    def tearDown(self) -> None:
        # Clean up temporary files
        for name in self.tmp_files:
            if os.path.exists(name):
                os.remove(name)
        return super().tearDown()

    def test_fontstyle_ini(self):
        """Test font sizes are doubled in INI file"""
        tmp_path = self._mktemp()
        shutil.copy(self._get_test_file_path("FontStyle-A.ini"), tmp_path)

        dummy_file = GameFile(tmp_path)
        dummy_file.backup_path = self._get_test_file_path("FontStyle-A.ini")
        patches.upscale_fontstyle_ini(dummy_file, write_meta_file=False)

        # Compare output with expected output
        expected = self._get_test_file_data("FontStyle-B.ini")
        with open(tmp_path, "r", encoding="utf-8") as f:
            actual = f.read()
        self.assertEqual(actual, expected, "FontStyle.ini file was not modified correctly")

    def test_uiscript_patch(self):
        """Test a known UI script doubled its geometry/positions"""
        entry = self.ui_package.get_entry(dbpf.TYPE_UI_DATA, 134219264, 1012948880)
        checksum_before = hashlib.md5(entry.data).hexdigest()
        if checksum_before != "5a41f089015d0b2a3c5333661691044f":
            raise ValueError("Bad test file, checksum mismatch")

        new_data = patches._upscale_uiscript(entry)
        checksum_after = hashlib.md5(new_data).hexdigest()

        self.assertEqual(checksum_after, "0d333c9741889560cca1236e6af681c5", "UI script was not modified as expected")

    def test_graphic_patch_bmp(self):
        """Test a bitmap image is modified and at least double its size"""
        entry = self.ui_package.get_entry(dbpf.TYPE_IMAGE, 1235072882, 3973787653)
        new_data = patches._upscale_graphic(entry)
        self.assertGreater(len(new_data), len(entry.data), "Bitmap image was not modified")

    def test_graphic_patch_tga(self):
        """Test a Targa image is modified"""
        entry = self.ui_package.get_entry(dbpf.TYPE_IMAGE, 1235072882, 725504)
        new_data = patches._upscale_graphic(entry)
        self.assertGreater(len(new_data), len(entry.data), "Targa image was not modified")

    def test_graphic_patch_png(self):
        """Test a PNG image is modified"""
        entry = self.ui_package.get_entry(dbpf.TYPE_IMAGE, 1235072882, 2376314362)
        new_data = patches._upscale_graphic(entry)
        self.assertGreater(len(new_data), len(entry.data), "PNG image was not modified")
