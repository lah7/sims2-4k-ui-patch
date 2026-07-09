"""
Perform tests on the patches module to ensure that an input
and output works as expected.
"""
# pylint: disable=protected-access
import io
import os
import shutil
import struct
import sys

import PIL.Image

# Our modules are in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from sims2patcher import dbpf, exe_patches, patches
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


def make_fake_exe() -> bytearray:
    """Create a minimal bytearray with correct original bytes at all patch offsets."""
    max_offset = max(
        max(o for o, _ in exe_patches._PIE_MENU_SECTOR_OFFSETS),
        exe_patches._PIE_MENU_FILD_SITE_2 + 9,
        exe_patches._PIE_MENU_CAVE_ADDR + 40,
    )
    data = bytearray(max_offset + 64)
    for offset, orig_val in exe_patches._PIE_MENU_SECTOR_OFFSETS:
        data[offset] = orig_val
    site1 = exe_patches._PIE_MENU_FILD_SITE_1
    data[site1:site1+8] = exe_patches._PIE_MENU_FILD_ORIG_1
    site2 = exe_patches._PIE_MENU_FILD_SITE_2
    data[site2:site2+9] = exe_patches._PIE_MENU_FILD_ORIG_2
    return data


class ExecutablePatchTest(BaseTestCase):
    """
    Test the pie menu binary patching for Sims2EP9.exe.
    Uses synthetic data — no real game executable needed.
    """
    def _make_fake_exe(self) -> bytearray:
        """Create a minimal bytearray with correct original bytes at all patch offsets."""
        return make_fake_exe()

    def test_verify_original_passes(self):
        """Verification passes for unmodified original bytes"""
        data = bytes(self._make_fake_exe())
        self.assertTrue(exe_patches.verify_exe_bytes(data))

    def test_verify_wrong_bytes_fails(self):
        """Verification fails when bytes don't match"""
        data = self._make_fake_exe()
        data[exe_patches._PIE_MENU_SECTOR_OFFSETS[0][0]] = 0xFF
        self.assertFalse(exe_patches.verify_exe_bytes(bytes(data)))

    def test_verify_wrong_fild_fails(self):
        """Verification fails when fild site bytes don't match"""
        data = self._make_fake_exe()
        data[exe_patches._PIE_MENU_FILD_SITE_1] = 0x00
        self.assertFalse(exe_patches.verify_exe_bytes(bytes(data)))

    def test_sector_offsets_scaled_2x(self):
        """Sector offsets are doubled at 2.0x scale"""
        data = bytes(self._make_fake_exe())
        result = exe_patches.build_pie_menu_patch(data, 2.0)
        for offset, orig_val in exe_patches._PIE_MENU_SECTOR_OFFSETS:
            expected = min(int(orig_val * 2.0), 127)
            self.assertEqual(result[offset], expected,
                f"Sector offset at 0x{offset:X}: expected {expected}, got {result[offset]}")

    def test_sector_offsets_scaled_1_5x(self):
        """Sector offsets are correctly scaled at 1.5x"""
        data = bytes(self._make_fake_exe())
        result = exe_patches.build_pie_menu_patch(data, 1.5)
        for offset, orig_val in exe_patches._PIE_MENU_SECTOR_OFFSETS:
            expected = min(int(orig_val * 1.5), 127)
            self.assertEqual(result[offset], expected)

    def test_sector_offset_capped_at_127(self):
        """Scaled values exceeding 127 are capped (signed byte limit)"""
        data = bytes(self._make_fake_exe())
        result = exe_patches.build_pie_menu_patch(data, 3.0)
        offset_48 = 0x001A6A62
        self.assertEqual(result[offset_48], 127, "48 * 3 = 144 should be capped to 127")

    def test_code_cave_written(self):
        """Code cave is written at the correct address with multiplier float"""
        data = bytes(self._make_fake_exe())
        result = exe_patches.build_pie_menu_patch(data, 2.0)
        cave = exe_patches._PIE_MENU_CAVE_ADDR
        stored_float = struct.unpack_from("<f", result, cave)[0]
        self.assertAlmostEqual(stored_float, 2.0, places=5, msg="Multiplier float not stored correctly")
        self.assertEqual(result[cave + 4], 0xDB, "Cave1 should start with fild opcode")
        self.assertEqual(result[cave + 4 + 14], 0xC3, "Cave1 should end with ret")
        self.assertEqual(result[cave + 19], 0xDB, "Cave2 should start with fild opcode")
        self.assertEqual(result[cave + 19 + 14], 0xC3, "Cave2 should end with ret")

    def test_call_site_1_redirected(self):
        """First fild+fmul site is replaced with call to cave + nops"""
        data = bytes(self._make_fake_exe())
        result = exe_patches.build_pie_menu_patch(data, 2.0)
        site1 = exe_patches._PIE_MENU_FILD_SITE_1
        self.assertEqual(result[site1], 0xE8, "Site 1 should have call opcode")
        self.assertEqual(result[site1+5:site1+8], bytes([0x90, 0x90, 0x90]), "Site 1 should be nop-padded")

    def test_call_site_2_redirected(self):
        """Second fild site is replaced with call + pop ecx + nops"""
        data = bytes(self._make_fake_exe())
        result = exe_patches.build_pie_menu_patch(data, 2.0)
        site2 = exe_patches._PIE_MENU_FILD_SITE_2
        self.assertEqual(result[site2], 0xE8, "Site 2 should have call opcode")
        self.assertEqual(result[site2+5], 0x59, "Site 2 should keep pop ecx")
        self.assertEqual(result[site2+6:site2+9], bytes([0x90, 0x90, 0x90]), "Site 2 should be nop-padded")

    def test_call_targets_are_correct(self):
        """Call instructions point to the correct cave addresses"""
        data = bytes(self._make_fake_exe())
        result = exe_patches.build_pie_menu_patch(data, 2.0)
        cave = exe_patches._PIE_MENU_CAVE_ADDR

        site1 = exe_patches._PIE_MENU_FILD_SITE_1
        rel1 = struct.unpack_from("<i", result, site1 + 1)[0]
        target1 = site1 + 5 + rel1
        self.assertEqual(target1, cave + 4, "Call site 1 should target cave1")

        site2 = exe_patches._PIE_MENU_FILD_SITE_2
        rel2 = struct.unpack_from("<i", result, site2 + 1)[0]
        target2 = site2 + 5 + rel2
        self.assertEqual(target2, cave + 19, "Call site 2 should target cave2")

    def test_unpatched_bytes_preserved(self):
        """Bytes outside patch areas remain unchanged"""
        data = bytes(self._make_fake_exe())
        result = exe_patches.build_pie_menu_patch(data, 2.0)
        patch_ranges = set()
        for offset, _ in exe_patches._PIE_MENU_SECTOR_OFFSETS:
            patch_ranges.add(offset)
        for i in range(exe_patches._PIE_MENU_FILD_SITE_1, exe_patches._PIE_MENU_FILD_SITE_1 + 8):
            patch_ranges.add(i)
        for i in range(exe_patches._PIE_MENU_FILD_SITE_2, exe_patches._PIE_MENU_FILD_SITE_2 + 9):
            patch_ranges.add(i)
        for i in range(exe_patches._PIE_MENU_CAVE_ADDR, exe_patches._PIE_MENU_CAVE_ADDR + 40):
            patch_ranges.add(i)
        for i in range(min(len(data), len(result))):
            if i not in patch_ranges:
                self.assertEqual(result[i], data[i],
                    f"Byte at 0x{i:X} was unexpectedly modified")


class ExecutableRoutingTest(BaseTestCase):
    """
    Test supported executables are routed through the pie menu patch,
    based on their filename.
    """
    def _patch_fake_exe(self, filename: str) -> str:
        """Write a synthetic executable and run it through patch_file(). Returns the patched path."""
        data = bytes(make_fake_exe())

        backup_path = self.mktemp()
        with open(backup_path, "wb") as f:
            f.write(data)

        tmp_path = os.path.join(os.path.dirname(backup_path), filename)
        with open(tmp_path, "wb") as f:
            f.write(data)
        self.tmp_files.append(tmp_path)
        self.tmp_files.append(tmp_path + ".patched")

        patches.UI_MULTIPLIER = 2.0
        patches.FIX_PIE_MENU = True

        dummy_file = GameFileReplacement(tmp_path)
        dummy_file._backup_path = backup_path
        patches.patch_file(dummy_file, lambda current, total: None)

        self.assertTrue(dummy_file.patched, f"{filename} was not patched")
        return tmp_path

    def test_exe_patched(self):
        """Sims2EP9.exe is patched with scaled sector offsets"""
        path = self._patch_fake_exe("Sims2EP9.exe")
        with open(path, "rb") as f:
            result = f.read()
        offset, orig_val = exe_patches._PIE_MENU_SECTOR_OFFSETS[0]
        self.assertEqual(result[offset], orig_val * 2, "Sector offset was not scaled")

    def test_rpc_exe_patched(self):
        """Sims2EP9RPC.exe (Sims 2 RPC launcher) is patched with scaled sector offsets"""
        path = self._patch_fake_exe("Sims2EP9RPC.exe")
        with open(path, "rb") as f:
            result = f.read()
        offset, orig_val = exe_patches._PIE_MENU_SECTOR_OFFSETS[0]
        self.assertEqual(result[offset], orig_val * 2, "Sector offset was not scaled")
