"""
Perform tests on the DBPF module to ensure that our mini library
works as expected to read and write valid ui.package files.
"""
import os
import sys
import time

# Our modules are in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from sims2patcher import dbpf
from tests.test_base import BaseTestCase


class DBPFTest(BaseTestCase):
    """
    Test our DBPF module to make sure it works as expected when reading and
    writing ui.package files.
    """
    def test_read_version_dbpf(self):
        """Read the DBPF version"""
        self.assertTrue(self.package.header.dbpf_version == 1.1, "Unexpected DBPF version")

    def test_read_version_index(self):
        """Read the index version"""
        self.assertTrue(self.package.header.index_version == 7.1, "Unexpected index version")

    def test_read_index(self):
        """Read a known file from the index"""
        entry = self.package.entries[self.tga_index]
        results = [
            entry.group_id == self.tga_group_id,
            entry.instance_id == self.tga_instance_id,
            self.package.get_type_as_string(entry.type_id) == "Image File",
        ]
        self.assertTrue(all(results))

    def test_dir_index(self):
        """Check the DIR file references all the files in the index"""
        entries = self.package.entries
        checksums = []

        for entry in self.package.index.dir.files:
            assert isinstance(entry, dbpf.DirectoryFile.CompressedFile)
            name = str(entry.type_id) + "_" + str(entry.group_id) + "_" + str(entry.instance_id)
            checksums.append(name)

        for entry in entries:
            assert isinstance(entry, dbpf.Entry)
            name = str(entry.type_id) + "_" + str(entry.group_id) + "_" + str(entry.instance_id)
            if name in checksums:
                checksums.remove(name)

        self.assertTrue(len(checksums) == 0, "DIR references files not found in index. Possible read error?")

    def test_extract_compressed(self):
        """Check compressed files can be read from original game package"""
        entry = self.package.entries[self.tga_index]

        if not entry.compress:
            raise RuntimeError("Expected a compressed entry")

        self.assertTrue(self.md5(entry.data) == self.tga_md5)

    def test_extract_uncompressed(self):
        """Check uncompressed files can be read from original game package"""
        entry = self.package.entries[self.png_index]

        if entry.compress:
            raise RuntimeError("Expected an uncompressed entry")

        self.assertTrue(self.md5(entry.data) == self.png_md5)

    def test_new_package_index_7_1(self):
        """Verify the integrity of a new package based on index version 7.1"""
        pkg = dbpf.DBPF()
        pkg_path = self.mktemp()
        group_id = 0x01
        instance_id = 0x02
        resource_id = 0
        type_id = dbpf.TYPE_IMAGE
        data = b"Hello World!"
        pkg.add_entry(type_id, group_id, instance_id, resource_id, data)
        pkg.save_package(pkg_path)

        # Read and check
        pkg = dbpf.DBPF(pkg_path)
        entry = pkg.entries[0]

        # Header data
        self.assertTrue(pkg.header.dbpf_version == 1.1)
        self.assertTrue(pkg.header.index_version == 7.1)

        # Entry data
        self.assertTrue(entry.group_id == group_id)
        self.assertTrue(entry.instance_id == instance_id)
        self.assertTrue(pkg.get_type_as_string(entry.type_id) == "Image File")
        self.assertTrue(entry.data == data)

    def test_new_package_index_7_2(self):
        """Verify the integrity of a new package based on index version 7.2"""
        pkg = dbpf.DBPF()
        pkg.header.index_version_minor = 2
        pkg_path = self.mktemp()
        group_id = 0x01
        instance_id = 0x02
        resource_id = 0x03
        type_id = dbpf.TYPE_IMAGE
        data = b"Hello Resource!"
        pkg.add_entry(type_id, group_id, instance_id, resource_id, data)
        pkg.save_package(pkg_path)

        # Read and check
        pkg = dbpf.DBPF(pkg_path)
        entry = pkg.entries[0]

        # Header data
        self.assertTrue(pkg.header.dbpf_version == 1.1)
        self.assertTrue(pkg.header.index_version == 7.2)

        # Entry data
        self.assertTrue(entry.type_id == type_id)
        self.assertTrue(entry.group_id == group_id)
        self.assertTrue(entry.instance_id == instance_id)
        self.assertTrue(entry.resource_id == resource_id)
        self.assertTrue(entry.data == data)

    def test_new_package_from_file(self):
        """Verify the integrity of a file added to a new package"""
        # Extract a file from original package
        entry = self.package.entries[self.tga_index]
        tga_path = self.mktemp()
        with open(tga_path, "wb") as f:
            f.write(entry.data)

        # Create a new package with one file
        pkg = dbpf.DBPF()
        pkg_path = self.mktemp()
        pkg.add_entry_from_file(dbpf.TYPE_IMAGE, 0x00, 0x00, 0x00, tga_path)
        pkg.save_package(pkg_path)

        # Read and verify checksum
        pkg = dbpf.DBPF(pkg_path)
        entry = pkg.entries[0]
        self.assertTrue(self.md5(entry.data) == self.tga_md5)

    def test_new_package_with_compression(self):
        """Verify the integrity of a compressed file added to a new package"""
        # Extract a file from original package
        entry = self.package.entries[self.tga_index]

        # Create package; add the file; compress
        pkg = dbpf.DBPF()
        pkg_path = self.mktemp()
        pkg.add_entry(dbpf.TYPE_IMAGE, 0x00, 0x00, 0x00, entry.data, compress=True)
        pkg.save_package(pkg_path)

        # Read and verify checksum
        pkg = dbpf.DBPF(pkg_path)
        entry = pkg.entries[0]

        self.assertTrue(self.md5(entry.data) == self.tga_md5)

    def test_new_package_directory_index_exists(self):
        """Verify a package with compressed files contains a DIR entry"""
        pkg = dbpf.DBPF()
        pkg_path = self.mktemp()
        pkg.add_entry(dbpf.TYPE_UI_DATA, 0x00, 0x00, 0x00, b"AAABBBCCCAAAAAABBBCCCDDDAAABBBABABAB", compress=True)
        pkg.save_package(pkg_path)

        pkg2 = dbpf.DBPF(pkg_path)
        entries = pkg2.entries
        self.assertTrue(len(entries) == 2)
        self.assertTrue(dbpf.TYPE_DIR in [entry.type_id for entry in entries])

    def test_new_package_directory_index_no_exists(self):
        """Verify a package with no compressed files doesn't have a DIR entry"""
        pkg = dbpf.DBPF()
        pkg_path = self.mktemp()
        pkg.add_entry(dbpf.TYPE_UI_DATA, 0x00, 0x00, 0x00, b"AAABBBCCCAAAAAABBBCCCDDDAAABBBABABAB", compress=False)
        pkg.save_package(pkg_path)

        pkg2 = dbpf.DBPF(pkg_path)
        entries = pkg2.entries
        self.assertTrue(len(entries) == 1)
        self.assertTrue(entries[0].type_id == dbpf.TYPE_UI_DATA)

    def test_compressed_package_size(self):
        """Check the resulting package size is different when compression is used"""
        tga_entry = self.package.entries[self.tga_index]

        pkg1_path = self.mktemp()
        pkg1 = dbpf.DBPF()
        pkg1.add_entry(tga_entry.type_id, tga_entry.group_id, tga_entry.instance_id, tga_entry.resource_id, tga_entry.data, compress=False)
        pkg1.save_package(pkg1_path)

        pkg2_path = self.mktemp()
        pkg1 = dbpf.DBPF()
        pkg1.add_entry(tga_entry.type_id, tga_entry.group_id, tga_entry.instance_id, tga_entry.resource_id, tga_entry.data, compress=True)
        pkg1.save_package(pkg2_path)

        self.assertLess(os.path.getsize(pkg2_path), os.path.getsize(pkg1_path))

    def test_incompressible_file(self):
        """Check incompressible file does not get compressed"""
        pkg = dbpf.DBPF()
        entry = pkg.add_entry(dbpf.TYPE_UI_DATA, 0x00, 0x00, 0x00, b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()", compress=True)
        self.assertFalse(entry.compress)

    def test_mixed_compressed_package(self):
        """Check package integrity with uncompressed bitmap and compressed TGA file"""
        bmp_entry = self.package.entries[self.png_index]
        tga_entry = self.package.entries[self.tga_index]

        pkg_path = self.mktemp()
        pkg1 = dbpf.DBPF()
        pkg1.add_entry(bmp_entry.type_id, bmp_entry.group_id, bmp_entry.instance_id, bmp_entry.resource_id, bmp_entry.data, compress=False)
        pkg1.add_entry(tga_entry.type_id, tga_entry.group_id, tga_entry.instance_id, tga_entry.resource_id, tga_entry.data, compress=True)
        pkg1.save_package(pkg_path)

        pkg2 = dbpf.DBPF(pkg_path)
        new_bmp_entry = pkg2.entries[0]
        new_tga_entry = pkg2.entries[1]

        self.assertTrue(self.png_md5, self.md5(new_bmp_entry.data))
        self.assertTrue(self.tga_md5, self.md5(new_tga_entry.data))

    def test_resource_ids(self):
        """Check that resource IDs are correctly handled"""
        pkg = dbpf.DBPF("tests/files/index_7.2.package")
        entries = pkg.entries

        self.assertTrue(len(entries) == 3)
        self.assertTrue(pkg.get_entry(0, 0x10, 0x20, 0x30).data == b"One")
        self.assertTrue(pkg.get_entry(0, 0x10, 0x20, 0x40).data == b"Two")
        self.assertTrue(pkg.get_entry(0, 0x10, 0x30, 0x40).data == b"Three")

    def test_resource_ids_compressed(self):
        """Check that resource IDs are correctly handled including compression"""
        pkg = dbpf.DBPF("tests/files/index_7.2_compressed.package")
        entries = pkg.entries

        self.assertTrue(len(entries) == 4)
        self.assertTrue(dbpf.TYPE_DIR in [entry.type_id for entry in entries])
        self.assertTrue(pkg.get_entry(0, 0x10, 0x20, 0x30).data == b"OneOneOneOne")
        self.assertTrue(pkg.get_entry(0, 0x10, 0x20, 0x40).data == b"TwoTwoTwoTwo")
        self.assertTrue(pkg.get_entry(0, 0x10, 0x30, 0x40).data == b"ThreeThreeThreeThree")
        self.assertTrue(pkg.get_entry(0, 0x10, 0x30, 0x40).compress)

    def test_decompressed_cache(self):
        """Check that decompressed files are cached"""
        package = dbpf.DBPF(self.package.path)
        tga_entry = package.entries[self.tga_index]
        if not tga_entry.compress:
            raise RuntimeError("Expected a compressed entry")

        # Sample the time taken to read
        times = []
        for _ in range(0, 100):
            start = time.perf_counter_ns()
            tga_entry.data # pylint: disable=pointless-statement
            end = time.perf_counter_ns()
            times.append(end - start)

        self.assertLess(max(times[1:]), times[0])

    def test_decompressed_size(self):
        """Check that an entry is correctly reporting its compressed/decompressed size"""
        entry = self.package.entries[self.tga_index]
        if not entry.compress:
            raise RuntimeError("Expected a compressed entry")

        self.assertGreater(entry.decompressed_size, entry.file_size)

    def test_large_file_compression(self):
        """Check that a file isn't marked as compressed if it's too large"""
        pkg = dbpf.DBPF()
        entry = pkg.add_entry(0x00, 0x10, 0x20, 0x30, bytearray(16 * 1024 * 1024), compress=True)
        self.assertFalse(entry.compress)

    def test_compression_bad_state(self):
        """Check a file incorrectly marked as compressed can still be extracted"""
        package = dbpf.DBPF(self.package.path)
        entry = package.entries[self.png_index]
        entry._bytes_compressed = True # pylint: disable=protected-access
        entry.compress = True

        with self.assertRaises(dbpf.errors.InvalidMagicHeader):
            entry.data # pylint: disable=pointless-statement
        self.assertIsInstance(entry.data_safe, bytes)

    def test_modified_flag(self):
        """Check that modifying an entry sets the modified flag"""
        package = dbpf.DBPF(self.package.path)
        entry = package.entries[self.tga_index]
        entry.data = b"Hello World!"
        self.assertTrue(entry.modified)

    def test_game_name(self):
        """Check we can determine suitable names for a package file"""
        def _test_path(path):
            package = dbpf.DBPF()
            package.path = path
            return package.game_name

        self.assertEqual(_test_path("/tmp/The Sims 2 Ultimate Collection/Double Deluxe/SP4/TSData/Res/UI/ui.package"), "SP4")
        self.assertEqual(_test_path("/tmp/The Sims 2 Ultimate Collection/Bon Voyage/TSData/Res/UI/CaSIEUI.data"), "Bon Voyage")
        self.assertEqual(_test_path("/tmp/The Sims 2 Legacy Collection/EP9/TSData/Res/UI/ui.package"), "EP9")
        self.assertEqual(_test_path("/tmp/The Sims 2 Legacy Collection/Base/TSData/Res/UI/ui.package"), "Base")
        self.assertEqual(_test_path("/tmp/The Sims 2/TSData/Res/UI/ui.package"), "Base")
        self.assertEqual(_test_path("/tmp/EA GAMES/The Sims 2 Apartment Life/TSData/Res/UI/ui.package"), "Apartment Life")
        self.assertEqual(_test_path("/tmp/EA GAMES/Die Sims 2 Apartment Life/TSData/Res/Locale/German/UI/ui.package"), "Apartment Life")
        self.assertEqual(_test_path("/tmp/EA GAMES/Les Sims 2 Apartment Life/TSData/Res/Locale/French/UI/ui.package"), "Apartment Life")
        self.assertEqual(_test_path("/tmp/ui.package"), "Unknown")

    def test_count_entries_by_type(self):
        """Check that we can filter entries by type"""
        self.assertEqual(len(self.package.get_entries_by_type(dbpf.TYPE_UI_DATA)), 3)
        self.assertEqual(len(self.package.get_entries_by_type(dbpf.TYPE_IMAGE)), 5)
