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
        # Extract all files from original package
        files = []
        checksums = []

        for entry in self.package.index.entries:
            # Exclude compressed directory index
            if entry.type_id == dbpf.Stream.TYPE_DIR:
                continue

            checksum = hashlib.md5(entry.data).hexdigest()
            checksums.append(checksum)
            files.append({
                "type_id": entry.type_id,
                "group_id": entry.group_id,
                "instance_id": entry.instance_id,
                "data": entry.data,
                "compress": entry.compress,
                "checksum": checksum,
            })

        # Create new package with same contents
        pkg1 = dbpf.DBPF()
        pkg_path = self._mktemp()
        for file in files:
            pkg1.add_entry(file["type_id"], file["group_id"], file["instance_id"], file["data"], test_compression and file["compress"])
        pkg1.save_package(pkg_path)

        # Read and verify checksums in new package
        pkg2 = dbpf.DBPF(pkg_path)
        new_checksums = []
        for entry in pkg2.index.entries:
            md5 = hashlib.md5(entry.data).hexdigest()
            new_checksums.append(md5)

        self.assertTrue(checksums == new_checksums)
