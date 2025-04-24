"""
Perform tests against ui.package files from the game to check real package scenarios.
This test is optional and will be skipped if the files are not found.

See the Testing section in DEVELOPMENT.md for a list of required files and expected filenames.
"""
import os
import sys

# Our modules are in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from sims2patcher import dbpf, patches, uiscript
from tests.test_base import BaseTestCase


class RealPackageTest(BaseTestCase):
    """
    Test 'real' package files from the game against the modules.
    """
    @classmethod
    def setUpClass(cls):
        os.chdir(os.path.join(os.path.dirname(__file__), ".."))
        cls._package_loaded = False
        cls.package_path = "tests/gamefiles/EP1_ui.package"
        cls.package = dbpf.DBPF() # Load later

        # Known compressed file (TGA Image)
        cls.tga_index = 16
        cls.tga_md5 = "d3e3ea50829e8386736eb614df260020"
        cls.tga_group_id = 0x499db772
        cls.tga_instance_id = 0xccb00305

        # Known uncompressed and incompressible file (Bitmap)
        cls.bmp_index = 85
        cls.bmp_md5 = "4d450dd3b45e2cebae3ef949bde06292"
        cls.bmp_group_id = 0x499db772
        cls.bmp_instance_id = 0xecdb3005

    def setUp(self) -> None:
        if not self._package_loaded:
            if not os.path.exists(self.package_path):
                self.skipTest(f"Missing test file: {self.package_path}")
            self.package = dbpf.DBPF(self.package_path)
            self._package_loaded = True
        return super().setUp()

    def test_change_uiscript(self):
        """Test a file is changed after patching"""
        entry = self.package.get_entry(dbpf.TYPE_UI_DATA, 0x8000600, 0x3c605f90)
        checksum_before = self.md5(entry.data)
        if checksum_before != "5a41f089015d0b2a3c5333661691044f":
            raise ValueError("Bad test file, checksum mismatch")

        new_data = patches._upscale_uiscript(entry) # pylint: disable=protected-access
        checksum_after = self.md5(new_data)

        self.assertEqual(checksum_after, "0d333c9741889560cca1236e6af681c5", "UI script was not modified as expected")

    def test_change_graphic_tga(self):
        """Test a Targa image is modified"""
        entry = self.package.get_entry(dbpf.TYPE_IMAGE, 0x499db772, 0xb1200)
        new_data = patches._upscale_graphic(entry) # pylint: disable=protected-access
        self.assertGreater(len(new_data), len(entry.data), "Targa image was not modified")

    def test_change_graphic_bmp(self):
        """Test a bitmap image is modified and at least double its size"""
        entry = self.package.get_entry(dbpf.TYPE_IMAGE, 0x499db772, 0xecdb3005)
        new_data = patches._upscale_graphic(entry) # pylint: disable=protected-access
        self.assertGreater(len(new_data), len(entry.data), "Bitmap image was not modified")

    def test_change_graphic_png(self):
        """Test a PNG image is modified"""
        entry = self.package.get_entry(dbpf.TYPE_IMAGE, 0x499db772, 0x8da3adfa)
        new_data = patches._upscale_graphic(entry) # pylint: disable=protected-access
        self.assertGreater(len(new_data), len(entry.data), "PNG image was not modified")

    def test_repack_new_package(self, test_compression=False):
        """Create a new package by importing all original data"""
        pkg1 = dbpf.DBPF()
        checksums = []
        for entry in self.package.entries:
            # Exclude compressed directory index
            if entry.type_id == dbpf.TYPE_DIR:
                continue

            checksums.append(self.md5(entry.data))
            pkg1.add_entry(entry.type_id, entry.group_id, entry.instance_id, entry.resource_id, entry.data, entry.compress and test_compression)

        pkg_path = self.mktemp()
        pkg1.save_package(pkg_path)

        # Re-open new package and verify checksums
        pkg2 = dbpf.DBPF(pkg_path)
        for entry in pkg2.entries:
            # Exclude compressed directory index
            if entry.type_id == dbpf.TYPE_DIR:
                continue

            md5 = self.md5(entry.data)

            try:
                checksums.remove(md5)
            except ValueError as e:
                raise ValueError(f"Checksum mismatch: {md5}. Type ID {hex(entry.type_id)}, Group ID {hex(entry.group_id)}, Instance ID {hex(entry.instance_id)}") from e

        # Should be left with no more checksums
        self.assertEqual(len(checksums), 0, "Checksums mismatch")

        # Index size should be the same
        self.assertEqual(pkg1.header.index_size, pkg2.header.index_size)

    def test_repack_compressed_package(self):
        """Verify the integrity of a new package when compression is used"""
        self.test_repack_new_package(test_compression=True)

    def test_repack_unmodified_package(self):
        """Create a new package by saving original package without any changes"""
        pkg1 = self.package
        checksums = []
        entry_integrity = []

        for entry in pkg1.entries:
            # Exclude compressed directory index
            if entry.type_id == dbpf.TYPE_DIR:
                continue

            checksums.append(self.md5(entry.data))
            entry_integrity.append((entry.type_id, entry.group_id, entry.instance_id, entry.resource_id, entry.decompressed_size, entry.file_size))

        pkg_path = self.mktemp()
        pkg1.save_package(pkg_path)

        # Re-open new package and verify checksums
        pkg2 = dbpf.DBPF(pkg_path)
        entry_integrity_2 = []
        for index, entry in enumerate(pkg2.entries):
            # Exclude compressed directory index
            if entry.type_id == dbpf.TYPE_DIR:
                continue

            md5 = self.md5(entry.data)
            entry_integrity_2.append((entry.type_id, entry.group_id, entry.instance_id, entry.resource_id, entry.decompressed_size, entry.file_size))

            try:
                checksums.remove(md5)
            except ValueError as e:
                raise ValueError(f"Integrity mismatch: {md5} for entry {index} with Type ID {hex(entry.type_id)}, Group ID {hex(entry.group_id)}, Instance ID {hex(entry.instance_id)}") from e

        # Should be left with no more checksums
        self.assertEqual(len(checksums), 0, "Checksums mismatch")
        self.assertEqual(entry_integrity, entry_integrity_2)

    def test_repack_modified_package(self):
        """Make a change in the original package but leave other files intact"""
        pkg1 = self.package
        checksums = []

        pkg1.entries[self.tga_index].data = b"AAAAAAAAAAABBBCCAAAAAAA"

        for entry in pkg1.entries:
            # Exclude compressed directory index
            if entry.type_id == dbpf.TYPE_DIR:
                continue

            checksums.append(self.md5(entry.data))

        pkg_path = self.mktemp()
        pkg1.save_package(pkg_path)

        # Re-open new package and verify checksums
        pkg2 = dbpf.DBPF(pkg_path)
        for index, entry in enumerate(pkg2.entries):
            # Exclude compressed directory index
            if entry.type_id == dbpf.TYPE_DIR:
                continue

            md5 = self.md5(entry.data)

            try:
                checksums.remove(md5)
            except ValueError as e:
                raise ValueError(f"Integrity mismatch: {md5} for entry {index} with Type ID {hex(entry.type_id)}, Group ID {hex(entry.group_id)}, Instance ID {hex(entry.instance_id)}") from e

        # Should be left with no more checksums
        self.assertEqual(len(checksums), 0, "Checksums mismatch")

    def test_uiscript_serialize(self):
        """Check serialization is accurate for a UI script file with 1 child"""
        entry = self.package.get_entry(dbpf.TYPE_UI_DATA, 0xa99d8a11, 0x8c159250)
        root = uiscript.serialize_uiscript(entry.data.decode("utf-8"))

        self.assertEqual(root.comments, ["# Generated by UI editor"])
        self.assertEqual(len(root.children), 1)
        self.assertEqual(len(root.children[0].children), 12)
        self.assertEqual(len(root.children[0].children[11].children), 4)

        last_element = root.children[0].children[11].children[3]
        self.assertEqual(last_element["clsid"], "GZWinText")
        self.assertEqual(last_element["textoffsets"], "(0,0)")

        last_child_first_element = root.children[0].children[11].children[0]
        self.assertEqual(last_child_first_element["font"], "0x00001318")
        self.assertEqual(last_child_first_element["caption"], "kFOV=10.0f")

        first_child_first_element = root.children[0].children[0]
        self.assertEqual(first_child_first_element["image"], "{499db772,a9b30210}")

    def test_uiscript_deserialize(self):
        """Check deserialization against all UI scripts in the package, ensuring 1:1 match"""
        for entry in self.package.entries:
            try:
                original = entry.data.decode("utf-8")
                root = uiscript.serialize_uiscript(original)
            except UnicodeDecodeError:
                # Binary UI Script file
                continue

            output = uiscript.deserialize_uiscript(root)

            # Skip known files that don't fit the pattern
            if entry.group_id == 0xa99d8a11 and entry.instance_id in [
                # Duplicate "style" attribute
                0xfffffff0, 0xfffffff1,
                0x49060f00,
                0x90617b7,

                # Attribute with no value: "transparent"
                0xa0000001, 0xa0000002,

                # EOL whitespace not preserved for multi-line caption
                0x49000010, 0x4906501b,
                0xeeca0006,

                # Attribute with an equals sign: "initvalue="
                0xed0aa720,

                # We assume initvalue is always quoting, but not these ("=0")
                0xcb980e51, 0xcb980e52,

                # Debugging dialogs
                0x8baff56f,

                # Early UI? Unused? comments* attributes
                0xffff8000,
            ]:
                continue

            if entry.group_id == 0x8000600 and entry.instance_id in [
                # We assume initvalue is always quoting, but not these ("=0")
                0xcb980e51, 0xcb980e52,

                # Whitespace not preserved for multi-line caption
                0xeeca0006,
            ]:
                continue

            self.assertEqual(output, original)

    def test_uiscript_multiline_strip(self):
        """Check a known file has its trailing whitespace striped at the end"""
        entry = self.package.get_entry(dbpf.TYPE_UI_DATA, 0xa99d8a11, 0x49000010)
        original = entry.data.decode("utf-8")
        root = uiscript.serialize_uiscript(original)
        output = uiscript.deserialize_uiscript(root)
        self.assertTrue(original.find(". \r\n") > -1)
        self.assertFalse(output.find(". \r\n") > -1)

    def test_uiscript_serialization_repeatability(self):
        """Check serialization followed by deserialization preserves the original content"""
        entry = self.package.get_entry(dbpf.TYPE_UI_DATA, 0xa99d8a11, 0x49000016)
        original = entry.data.decode("utf-8")

        root = uiscript.serialize_uiscript(original)
        result = uiscript.deserialize_uiscript(root)
        self.assertEqual(result, original)

        root2 = uiscript.serialize_uiscript(result)
        result2 = uiscript.deserialize_uiscript(root2)

        root3 = uiscript.serialize_uiscript(result2)
        result3 = uiscript.deserialize_uiscript(root3)

        self.assertEqual(result3, original)

    def test_uiscript_constants(self):
        """Test values in a "constants table" are doubled"""
        entry = self.package.get_entry(dbpf.TYPE_UI_DATA, 0xa99d8a11, 0x8c159244)

        before = uiscript.serialize_uiscript(entry.data.decode("utf-8"))
        self.assertEqual(len(before.get_elements_by_attribute("caption", "kListBoxRowHeight=20")), 1)

        data = patches._upscale_uiscript(entry) # pylint: disable=protected-access

        after = uiscript.serialize_uiscript(data.decode("utf-8"))
        self.assertEqual(len(after.get_elements_by_attribute("caption", "kListBoxRowHeight=40")), 1)
