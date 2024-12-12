"""
Perform tests on the DBPF module to ensure that our mini library
works as expected to read and write valid ui.package files.
"""
import hashlib
import os
import sys
import tempfile
import time
import unittest

# Our modules are in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from sims2patcher import dbpf


class DBPFTest(unittest.TestCase):
    """
    Test our DBPF module to make sure it works as expected
    for reading and writing ui.package files.

    Requires files in the test directory (not included):
      - ui.package  (The Sims 2 University/TSData/Res/UI/ui.package)
    """
    tmp_files = []

    def _mktemp(self):
        tmp = tempfile.NamedTemporaryFile()
        self.tmp_files.append(tmp.name)
        return tmp.name

    @classmethod
    def setUpClass(cls):
        """Set up a test against package: The Sims 2 University (TSData/Res/UI/ui.package)"""
        cls.package = dbpf.DBPF("tests/files/ui.package") # DBPF 1.1, Index 7.1

        # Known compressed file (TGA Image)
        cls.tga_index = 16
        cls.tga_md5 = "d3e3ea50829e8386736eb614df260020"
        cls.tga_group_id = 0x499db772
        cls.tga_instance_id = 0xccb00305

        # Known uncompressed and incompressible file (Bitmap)
        cls.bmp_index = 85
        cls.bmp_md5 = "4d450dd3b45e2cebae3ef949bde06292"

    def tearDown(self) -> None:
        # Clean up temporary files
        for name in self.tmp_files:
            if os.path.exists(name):
                os.remove(name)
        return super().tearDown()

    def test_read_version_dbpf(self):
        """Read the DBPF version"""
        self.assertTrue(self.package.header.dbpf_version == 1.1, "Unexpected DBPF version")

    def test_read_version_index(self):
        """Read the index version"""
        self.assertTrue(self.package.header.index_version == 7.1, "Unexpected index version")

    def test_read_index(self):
        """Read a known file from the index"""
        entry = self.package.get_entries()[self.tga_index]
        results = [
            entry.group_id == self.tga_group_id,
            entry.instance_id == self.tga_instance_id,
            self.package.get_type_as_string(entry.type_id) == "Image File",
        ]
        self.assertTrue(all(results))

    def test_dir_index(self):
        """Check the DIR file references all the files in the index"""
        entries = self.package.get_entries()
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
        entry = self.package.get_entries()[self.tga_index]

        if not entry.compress:
            raise RuntimeError("Expected a compressed entry")

        md5 = hashlib.md5(entry.data).hexdigest()
        self.assertTrue(md5 == self.tga_md5)

    def test_extract_uncompressed(self):
        """Check uncompressed files can be read from original game package"""
        entry = self.package.get_entries()[self.bmp_index]

        if entry.compress:
            raise RuntimeError("Expected an uncompressed entry")

        md5 = hashlib.md5(entry.data).hexdigest()
        self.assertTrue(md5 == self.bmp_md5)

    def test_new_package_index_7_1(self):
        """Verify the integrity of a new package based on index version 7.1"""
        pkg = dbpf.DBPF()
        pkg_path = self._mktemp()
        group_id = 0x01
        instance_id = 0x02
        resource_id = 0
        type_id = dbpf.TYPE_IMAGE
        data = b"Hello World!"
        pkg.add_entry(type_id, group_id, instance_id, resource_id, data)
        pkg.save_package(pkg_path)

        # Read and check
        pkg = dbpf.DBPF(pkg_path)
        entry = pkg.get_entries()[0]

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
        pkg_path = self._mktemp()
        group_id = 0x01
        instance_id = 0x02
        resource_id = 0x03
        type_id = dbpf.TYPE_IMAGE
        data = b"Hello Resource!"
        pkg.add_entry(type_id, group_id, instance_id, resource_id, data)
        pkg.save_package(pkg_path)

        # Read and check
        pkg = dbpf.DBPF(pkg_path)
        entry = pkg.get_entries()[0]

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
        entry = self.package.get_entries()[self.tga_index]
        tga_path = self._mktemp()
        with open(tga_path, "wb") as f:
            f.write(entry.data)

        # Create a new package with one file
        pkg = dbpf.DBPF()
        pkg_path = self._mktemp()
        pkg.add_entry_from_file(dbpf.TYPE_IMAGE, 0x00, 0x00, 0x00, tga_path)
        pkg.save_package(pkg_path)

        # Read and verify checksum
        pkg = dbpf.DBPF(pkg_path)
        entry = pkg.get_entries()[0]
        md5 = hashlib.md5(entry.data).hexdigest()
        self.assertTrue(md5 == self.tga_md5)

    def test_new_package_with_compression(self):
        """Verify the integrity of a compressed file added to a new package"""
        # Extract a file from original package
        entry = self.package.get_entries()[self.tga_index]

        # Create package; add the file; compress
        pkg = dbpf.DBPF()
        pkg_path = self._mktemp()
        pkg.add_entry(dbpf.TYPE_IMAGE, 0x00, 0x00, 0x00, entry.data, compress=True)
        pkg.save_package(pkg_path)

        # Read and verify checksum
        pkg = dbpf.DBPF(pkg_path)
        entry = pkg.get_entries()[0]
        md5 = hashlib.md5(entry.data).hexdigest()

        self.assertTrue(md5 == self.tga_md5)

    def test_repack_new_package(self, test_compression=False):
        """Create a new package by extracting all data from the original"""
        pkg1 = dbpf.DBPF()
        checksums = []
        for entry in self.package.get_entries():
            # Exclude compressed directory index
            if entry.type_id == dbpf.TYPE_DIR:
                continue

            checksums.append(hashlib.md5(entry.data).hexdigest())
            pkg1.add_entry(entry.type_id, entry.group_id, entry.instance_id, entry.resource_id, entry.data, entry.compress and test_compression)

        pkg_path = self._mktemp()
        pkg1.save_package(pkg_path)

        # Re-open new package and verify checksums
        pkg2 = dbpf.DBPF(pkg_path)
        for entry in pkg2.get_entries():
            # Exclude compressed directory index
            if entry.type_id == dbpf.TYPE_DIR:
                continue

            md5 = hashlib.md5(entry.data).hexdigest()

            try:
                checksums.remove(md5)
            except ValueError as e:
                raise ValueError(f"Checksum mismatch: {md5}. Type ID {entry.type_id}, group ID {entry.group_id}, instance ID {entry.instance_id}") from e

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

        for entry in pkg1.get_entries():
            # Exclude compressed directory index
            if entry.type_id == dbpf.TYPE_DIR:
                continue

            checksums.append(hashlib.md5(entry.data).hexdigest())
            entry_integrity.append((entry.type_id, entry.group_id, entry.instance_id, entry.resource_id, entry.decompressed_size, entry.file_size))

        pkg_path = self._mktemp()
        pkg1.save_package(pkg_path)

        # Re-open new package and verify checksums
        pkg2 = dbpf.DBPF(pkg_path)
        entry_integrity_2 = []
        for index, entry in enumerate(pkg2.get_entries()):
            # Exclude compressed directory index
            if entry.type_id == dbpf.TYPE_DIR:
                continue

            md5 = hashlib.md5(entry.data).hexdigest()
            entry_integrity_2.append((entry.type_id, entry.group_id, entry.instance_id, entry.resource_id, entry.decompressed_size, entry.file_size))

            try:
                checksums.remove(md5)
            except ValueError as e:
                raise ValueError(f"Integrity mismatch: {md5} for entry {index} with type ID {entry.type_id}, group ID {entry.group_id}, instance ID {entry.instance_id}") from e

        # Should be left with no more checksums
        self.assertEqual(len(checksums), 0, "Checksums mismatch")
        self.assertEqual(entry_integrity, entry_integrity_2)

    def test_repack_modified_package(self):
        """Make a change in the original package but leave other files intact"""
        pkg1 = self.package
        checksums = []

        pkg1.get_entries()[self.tga_index].data = b"AAAAAAAAAAABBBCCAAAAAAA"

        for entry in pkg1.get_entries():
            # Exclude compressed directory index
            if entry.type_id == dbpf.TYPE_DIR:
                continue

            checksums.append(hashlib.md5(entry.data).hexdigest())

        pkg_path = self._mktemp()
        pkg1.save_package(pkg_path)

        # Re-open new package and verify checksums
        pkg2 = dbpf.DBPF(pkg_path)
        for index, entry in enumerate(pkg2.get_entries()):
            # Exclude compressed directory index
            if entry.type_id == dbpf.TYPE_DIR:
                continue

            md5 = hashlib.md5(entry.data).hexdigest()

            try:
                checksums.remove(md5)
            except ValueError as e:
                raise ValueError(f"Integrity mismatch: {md5} for entry {index} with type ID {entry.type_id}, group ID {entry.group_id}, instance ID {entry.instance_id}") from e

        # Should be left with no more checksums
        self.assertEqual(len(checksums), 0, "Checksums mismatch")

    def test_new_package_directory_index_exists(self):
        """Verify a package with compressed files contains a DIR entry"""
        pkg = dbpf.DBPF()
        pkg_path = self._mktemp()
        pkg.add_entry(dbpf.TYPE_UI_DATA, 0x00, 0x00, 0x00, b"AAABBBCCCAAAAAABBBCCCDDDAAABBBABABAB", compress=True)
        pkg.save_package(pkg_path)

        pkg2 = dbpf.DBPF(pkg_path)
        entries = pkg2.get_entries()
        self.assertTrue(len(entries) == 2)
        self.assertTrue(dbpf.TYPE_DIR in [entry.type_id for entry in entries])

    def test_new_package_directory_index_no_exists(self):
        """Verify a package with no compressed files doesn't have a DIR entry"""
        pkg = dbpf.DBPF()
        pkg_path = self._mktemp()
        pkg.add_entry(dbpf.TYPE_UI_DATA, 0x00, 0x00, 0x00, b"AAABBBCCCAAAAAABBBCCCDDDAAABBBABABAB", compress=False)
        pkg.save_package(pkg_path)

        pkg2 = dbpf.DBPF(pkg_path)
        entries = pkg2.get_entries()
        self.assertTrue(len(entries) == 1)
        self.assertTrue(entries[0].type_id == dbpf.TYPE_UI_DATA)

    def test_compressed_package_size(self):
        """Check the resulting package size is different when compression is used"""
        tga_entry = self.package.get_entries()[self.tga_index]

        pkg1_path = self._mktemp()
        pkg1 = dbpf.DBPF()
        pkg1.add_entry(tga_entry.type_id, tga_entry.group_id, tga_entry.instance_id, tga_entry.resource_id, tga_entry.data, compress=False)
        pkg1.save_package(pkg1_path)

        pkg2_path = self._mktemp()
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
        bmp_entry = self.package.get_entries()[self.bmp_index]
        tga_entry = self.package.get_entries()[self.tga_index]

        pkg_path = self._mktemp()
        pkg1 = dbpf.DBPF()
        pkg1.add_entry(bmp_entry.type_id, bmp_entry.group_id, bmp_entry.instance_id, bmp_entry.resource_id, bmp_entry.data, compress=False)
        pkg1.add_entry(tga_entry.type_id, tga_entry.group_id, tga_entry.instance_id, tga_entry.resource_id, tga_entry.data, compress=True)
        pkg1.save_package(pkg_path)

        pkg2 = dbpf.DBPF(pkg_path)
        new_bmp_entry = pkg2.get_entries()[0]
        new_tga_entry = pkg2.get_entries()[1]

        self.assertTrue(self.bmp_md5, hashlib.md5(new_bmp_entry.data).hexdigest())
        self.assertTrue(self.tga_md5, hashlib.md5(new_tga_entry.data).hexdigest())

    def test_resource_ids(self):
        """Check that resource IDs are correctly handled"""
        pkg = dbpf.DBPF("tests/files/index_7.2.package")
        entries = pkg.get_entries()

        self.assertTrue(len(entries) == 3)
        self.assertTrue(pkg.get_entry(0, 0x10, 0x20, 0x30).data == b"One")
        self.assertTrue(pkg.get_entry(0, 0x10, 0x20, 0x40).data == b"Two")
        self.assertTrue(pkg.get_entry(0, 0x10, 0x30, 0x40).data == b"Three")

    def test_resource_ids_compressed(self):
        """Check that resource IDs are correctly handled including compression"""
        pkg = dbpf.DBPF("tests/files/index_7.2_compressed.package")
        entries = pkg.get_entries()

        self.assertTrue(len(entries) == 4)
        self.assertTrue(dbpf.TYPE_DIR in [entry.type_id for entry in entries])
        self.assertTrue(pkg.get_entry(0, 0x10, 0x20, 0x30).data == b"OneOneOneOne")
        self.assertTrue(pkg.get_entry(0, 0x10, 0x20, 0x40).data == b"TwoTwoTwoTwo")
        self.assertTrue(pkg.get_entry(0, 0x10, 0x30, 0x40).data == b"ThreeThreeThreeThree")
        self.assertTrue(pkg.get_entry(0, 0x10, 0x30, 0x40).compress)

    def test_decompressed_cache(self):
        """Check that decompressed files are cached"""
        package = dbpf.DBPF("tests/files/ui.package")
        tga_entry = package.get_entries()[self.tga_index]
        if not tga_entry.compress:
            raise RuntimeError("Expected a compressed entry")

        # Sample the time taken to read
        times = []
        for _ in range(0, 100):
            start = time.time()
            tga_entry.data # pylint: disable=pointless-statement
            end = time.time()
            times.append(end - start)

        self.assertLess(max(times[1:]), times[0])

    def test_decompressed_size(self):
        """Check that an entry is correctly reporting its compressed/decompressed size"""
        entry = self.package.get_entries()[self.tga_index]
        if not entry.compress:
            raise RuntimeError("Expected a compressed entry")

        self.assertGreater(entry.decompressed_size, entry.file_size)
