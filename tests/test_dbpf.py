"""
Perform tests on the DBPF module to ensure that our mini library
works as expected to read and write valid ui.package files.
"""
import hashlib
import os
import tempfile
import unittest

import dbpf


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

    def setUp(self):
        """Set up a test against package: The Sims 2 University (TSData/Res/UI/ui.package)"""
        self.package = dbpf.DBPF("tests/ui.package")

        # Known compressed file (TGA Image)
        self.tga_index = 16
        self.tga_md5 = "d3e3ea50829e8386736eb614df260020"
        self.tga_group_id = 0x499db772
        self.tga_instance_id = 0xccb00305

        # Known uncompressed file (Bitmap)
        self.bmp_index = 85
        self.bmp_md5 = "4d450dd3b45e2cebae3ef949bde06292"

    def tearDown(self) -> None:
        # Clean up temporary files
        for name in self.tmp_files:
            if os.path.exists(name):
                os.remove(name)
        return super().tearDown()

    def test_read_version(self):
        """Read the index version"""
        version = f"{self.package.header.index_version_major}.{self.package.header.index_version_minor}"
        self.assertTrue(version == "7.1")

    def test_read_index(self):
        """Read a known file from the index"""
        entry = self.package.get_entries()[self.tga_index]
        results = [
            entry.group_id == self.tga_group_id,
            entry.instance_id == self.tga_instance_id,
            self.package.get_type(entry.type_id) == "Image File",
        ]
        self.assertTrue(all(results))

    def test_extract_compressed(self):
        """Check compressed files can be read from the package"""
        entry = self.package.get_entries()[self.tga_index]

        if not entry.compress:
            raise RuntimeError("Expected a compressed entry")

        md5 = hashlib.md5(entry.data).hexdigest()
        self.assertTrue(md5 == self.tga_md5)

    def test_extract_uncompressed(self):
        """Check existing uncompressed files can be read from the package"""
        entry = self.package.get_entries()[85]

        if entry.compress:
            raise RuntimeError("Expected an uncompressed entry")

        md5 = hashlib.md5(entry.data).hexdigest()
        self.assertTrue(md5 == self.bmp_md5)

    def test_new_package(self):
        """Verify the integrity of a new package"""
        pkg = dbpf.DBPF()
        pkg_path = self._mktemp()
        group_id = 0x01
        instance_id = 0x02
        type_id = dbpf.Stream.TYPE_IMAGE
        data = b"Hello World!"
        pkg.add_entry(type_id, group_id, instance_id, data)
        pkg.save_package(pkg_path)

        # Read and check
        pkg = dbpf.DBPF(pkg_path)
        entry = pkg.get_entries()[0]

        results = [
            # Header data
            pkg.header.index_version_major == 7,
            pkg.header.index_version_minor == 1,

            # Entry data
            entry.group_id == group_id,
            entry.instance_id == instance_id,
            pkg.get_type(entry.type_id) == "Image File",
            entry.data == b"Hello World!",
        ]

        self.assertTrue(all(results))

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
        pkg.add_entry_from_file(dbpf.Stream.TYPE_IMAGE, 0x00, 0x00, tga_path)
        pkg.save_package(pkg_path)

        # Read and verify checksum
        pkg = dbpf.DBPF(pkg_path)
        entry = pkg.get_entries()[0]
        md5 = hashlib.md5(entry.data).hexdigest()
        self.assertTrue(md5 == self.tga_md5)

    def test_new_package_with_compression(self):
        """Verify the integrity of a file added to a new package with compression"""
        # Extract a file from original package
        entry = self.package.get_entries()[self.tga_index]
        tga_path = self._mktemp()
        with open(tga_path, "wb") as f:
            f.write(entry.data)

        # Create package; add the file; compress
        pkg = dbpf.DBPF()
        pkg_path = self._mktemp()
        with open(tga_path, "rb") as f:
            data = f.read()
        pkg.add_entry(dbpf.Stream.TYPE_IMAGE, 0x00, 0x00, data, compress=True)
        pkg.save_package(pkg_path)

        # Read and verify checksum
        pkg = dbpf.DBPF(pkg_path)
        entry = pkg.get_entries()[0]
        md5 = hashlib.md5(entry.data).hexdigest()

        self.assertTrue(md5 == self.tga_md5)

    def test_repack_package(self, test_compression=False):
        """Create a new package by taking all data from the original"""
        pkg1 = dbpf.DBPF()
        checksums = []
        for entry in self.package.get_entries():
            # Exclude compressed directory index
            if entry.type_id == self.package.TYPE_DIR:
                continue

            checksums.append(hashlib.md5(entry.data).hexdigest())
            pkg1.add_entry(entry.type_id, entry.group_id, entry.instance_id, entry.data, entry.compress and test_compression)

        pkg_path = self._mktemp()
        pkg1.save_package(pkg_path)

        # Re-open new package and verify checksums
        pkg2 = dbpf.DBPF(pkg_path)
        for entry in pkg2.get_entries():
            # Exclude compressed directory index
            if entry.type_id == self.package.TYPE_DIR:
                continue

            md5 = hashlib.md5(entry.data).hexdigest()

            try:
                checksums.remove(md5)
            except ValueError as e:
                raise ValueError(f"Checksum mismatch: {md5} for type ID {entry.type_id}, group ID {entry.group_id}, instance ID {entry.instance_id}") from e

        # Should be left with no more checksums
        self.assertEqual(len(checksums), 0, "Checksums mismatch")

    def test_repack_package_compressed(self):
        """Verify the integrity of a new package by reading files from the original, including compression"""
        self.test_repack_package(test_compression=True)

    def test_compression_bmp_file(self):
        """Check uncompressable bitmap file does not get compressed"""
        bmp_entry = self.package.get_entries()[self.bmp_index]

        pkg_path = self._mktemp()
        pkg1 = dbpf.DBPF()
        pkg1.add_entry(bmp_entry.type_id, bmp_entry.group_id, bmp_entry.instance_id, bmp_entry.data, compress=True)
        pkg1.save_package(pkg_path)

        pkg2 = dbpf.DBPF(pkg_path)
        entry = pkg2.get_entries()[0]
        self.assertEqual(bmp_entry.raw, entry.raw)

    def test_compression_bmp_tga_file(self):
        """Check package integrity with uncompressed bitmap and compressed TGA file"""
        bmp_entry = self.package.get_entries()[self.bmp_index]
        tga_entry = self.package.get_entries()[self.tga_index]

        pkg_path = self._mktemp()
        pkg1 = dbpf.DBPF()
        pkg1.add_entry(bmp_entry.type_id, bmp_entry.group_id, bmp_entry.instance_id, bmp_entry.data, compress=False)
        pkg1.add_entry(tga_entry.type_id, tga_entry.group_id, tga_entry.instance_id, tga_entry.data, compress=True)
        pkg1.save_package(pkg_path)

        pkg2 = dbpf.DBPF(pkg_path)
        new_bmp_entry = pkg2.get_entries()[0]
        new_tga_entry = pkg2.get_entries()[1]
        md5 = hashlib.md5(new_bmp_entry.data).hexdigest()
        md5 += hashlib.md5(new_tga_entry.data).hexdigest()

        self.assertEqual(md5, self.bmp_md5 + self.tga_md5)
