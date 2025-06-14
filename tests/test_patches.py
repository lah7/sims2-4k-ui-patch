"""
Perform tests on the patches module to ensure that an input
and output works as expected.
"""
# pylint: disable=protected-access
import io
import os
import shutil
import sys

import PIL.Image

# Our modules are in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from sims2patcher import dbpf, patches
from sims2patcher.dbpf import TYPE_IMAGE, Entry
from sims2patcher.gamefile import GameFileReplacement
from tests.test_base import BaseTestCase


class FontsTest(BaseTestCase):
    """
    Test font styles upscale as expected.
    """
    def test_fontstyle_ini(self):
        """Test font sizes are doubled in INI file"""
        tmp_path = self.mktemp()
        shutil.copy(self.get_test_file_path("FontStyle-A.ini"), tmp_path)

        dummy_file = GameFileReplacement(tmp_path)
        dummy_file._backup_path = self.get_test_file_path("FontStyle-A.ini")
        patches.process_fontstyle_ini(dummy_file, write_meta_file=False)

        # Compare output with expected output
        expected = self.get_test_file_text("FontStyle-B.ini")
        with open(tmp_path, "r", encoding="utf-8") as f:
            actual = f.read()
        self.assertEqual(actual, expected, "FontStyle.ini file was not modified correctly")


class GraphicsTest(BaseTestCase):
    """
    Test graphics upscale as expected.
    """
    def _get_dimensions(self, data: bytes) -> tuple[int, int]:
        """Get the dimensions of the image"""
        with PIL.Image.open(io.BytesIO(data)) as img:
            return img.size

    def _get_test_image_entry(self, filename: str) -> Entry:
        """Get a placeholder entry for a test image"""
        entry = Entry(io.BytesIO())
        entry.type_id = TYPE_IMAGE
        entry.data = self.get_test_file_bytes(filename)
        return entry

    def _test_graphic_dimensions(self, filename: str, filetype: str):
        """Test a graphic image is modified and double its size"""
        entry = self._get_test_image_entry(filename)
        orig_width, orig_height = self._get_dimensions(entry.data)
        new_data = patches._upscale_graphic(entry)
        new_width, new_height = self._get_dimensions(new_data)
        self.assertGreater(len(new_data), len(entry.data), f"{filetype} was not modified")
        self.assertEqual(new_width, orig_width * 2, f"{filetype} width was not doubled")
        self.assertEqual(new_height, orig_height * 2, f"{filetype} height was not doubled")

    def test_graphic_patch_bmp(self):
        """Test a bitmap image is double its original dimensions"""
        self._test_graphic_dimensions("src/image5.bmp", "Bitmap")

    def test_graphic_patch_tga(self):
        """Test a targa image is double its original dimensions"""
        self._test_graphic_dimensions("src/image2.tga", "Targa")

    def test_graphic_patch_png(self):
        """Test a targa image is double its original dimensions"""
        self._test_graphic_dimensions("src/image3.png", "PNG")

    def test_graphic_patch_jpg(self):
        """Test a JPEG image is double its original dimensions"""
        self._test_graphic_dimensions("src/image4.jpg", "JPEG")


class UIScriptTest(BaseTestCase):
    """
    Test specific UI script patch scenarios.
    """
    def test_uiscript_patch_skipped(self):
        """Test a known debug UI script is not patched"""
        entry = Entry(io.BytesIO())
        entry.type_id = dbpf.TYPE_UI_DATA
        entry.group_id = 0xa99d8a11
        entry.instance_id = 0x8baff56f
        entry.data = b"12345678789"
        patches._upscale_uiscript(entry)
        self.assertEqual(entry.data, b"12345678789", "Known UI script should be skipped")

    def test_uiscript_attribute_new(self):
        """Test a specific UI script adds an additional attribute"""
        script_id = (0xa99d8a11, 0x49064905)
        attributes = {"caption": "Needs"}
        expected = {"caption": "Needs", "font": "GenHeader"}
        result = patches._fix_uiscript_element_attributes(script_id, attributes)
        self.assertEqual(result, expected, "UI script attribute was not added correctly")

    def test_uiscript_upscaled(self):
        """Test UI scripts are upscaled/fixed correctly"""
        entry = Entry(io.BytesIO())
        entry.type_id = dbpf.TYPE_UI_DATA
        entry.group_id = 0xa99d8a11
        entry.instance_id = 0x49064905
        entry.data = b"# Test\r\n<LEGACY iid=IGZWinGen area=(5,10,15,20) >\r\n<LEGACY iid=IGZWinText caption=\"Needs\" >\r\n"
        result = patches._upscale_uiscript(entry)
        expected = b"# Test\r\n<LEGACY iid=IGZWinGen area=(10,20,30,40) >\r\n<LEGACY iid=IGZWinText caption=\"Needs\" font=GenHeader >\r\n"
        self.assertEqual(result, expected, "UI script was not upscaled as expected")
