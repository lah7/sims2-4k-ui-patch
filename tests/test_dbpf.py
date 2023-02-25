import hashlib
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
    def _mktemp(self):
        tmp = tempfile.NamedTemporaryFile()
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

    def test_read_version(self):
        """Read the index version"""
        version = f"{self.package.header.index_version_major}.{self.package.header.index_version_minor}"
        self.assertTrue(version == "7.1")

    def test_read_index(self):
        """Read a known file from the index"""
        entry = self.package.index.entries[self.tga_index]
        results = [
            entry.group_id == self.tga_group_id,
            entry.instance_id == self.tga_instance_id,
            self.package.get_type(entry.type_id) == "Image File",
        ]
        self.assertTrue(all(results))

    def test_extract_compressed(self):
        """Extract a file that uses QFS compression"""
        entry = self.package.index.entries[self.tga_index]

        if not entry.compressed:
            raise RuntimeError("Expected a compressed entry")

        path = self._mktemp()
        self.package.extract(entry, path)
        with open(path, "rb") as f:
            md5 = hashlib.md5(f.read()).hexdigest()
        self.assertTrue(md5 == self.tga_md5)

    def test_compress_size(self):
        """Check a compressed and uncompressed file have different contents"""
        entry1 = self.package.index.entries[85]
        if entry1.compressed:
            raise RuntimeError("Expected an uncompressed entry")
        uncompressed = entry1.blob
        uncompressed_md5 = hashlib.md5(uncompressed).hexdigest()

        entry2 = self.package.add_file(0, 0, 0, uncompressed, compress=True)
        compressed_md5 = hashlib.md5(entry2.blob).hexdigest()

        self.assertFalse(uncompressed_md5 == compressed_md5)

    def test_extract_uncompressed(self):
        """Extract an uncompressed file"""
        entry = self.package.index.entries[85]

        if entry.compressed:
            raise RuntimeError("Expected an uncompressed entry")

        path = self._mktemp()
        self.package.extract(entry, path)
        with open(path, "rb") as f:
            md5 = hashlib.md5(f.read()).hexdigest()
        self.assertTrue(md5 == self.bmp_md5)

    def test_new_package(self):
        """Verify the integrity of a new package"""
        pkg = dbpf.DBPF()
        pkg_path = self._mktemp()
        group_id = 0x01
        instance_id = 0x02
        type_id = dbpf.Stream.TYPE_IMAGE
        data = b"Hello World!"
        pkg.add_file(type_id, group_id, instance_id, data)
        pkg.save(pkg_path)

        # Read and check
        pkg = dbpf.DBPF(pkg_path)
        entry = pkg.index.entries[0]

        results = [
            # Header data
            pkg.header.index_version_major == 7,
            pkg.header.index_version_minor == 1,

            # Entry data
            entry.group_id == group_id,
            entry.instance_id == instance_id,
            pkg.get_type(entry.type_id) == "Image File",
            entry.blob == b"Hello World!",
        ]

        self.assertTrue(all(results))

    def test_new_package_from_file(self):
        """Verify the integrity of a file added to a new package"""
        # Extract a file from original package
        entry = self.package.index.entries[self.tga_index]
        tga_path = self._mktemp()
        self.package.extract(entry, tga_path)

        # Create a new package with one file
        pkg = dbpf.DBPF()
        pkg_path = self._mktemp()
        pkg.add_file_from_path(dbpf.Stream.TYPE_IMAGE, 0x00, 0x00, tga_path)
        pkg.save(pkg_path)

        # Read and verify checksum
        pkg = dbpf.DBPF(pkg_path)
        entry = pkg.index.entries[0]
        output_path = self._mktemp()
        pkg.extract(entry, output_path)
        with open(output_path, "rb") as f:
            md5 = hashlib.md5(f.read()).hexdigest()
        self.assertTrue(md5 == self.tga_md5)

    def test_new_package_with_compression(self):
        """Verify the integrity of a file using QFS compression"""
        # Extract a file from original package
        entry = self.package.index.entries[self.tga_index]
        tga_path = self._mktemp()
        self.package.extract(entry, tga_path)

        # Create package and add the file (and compress)
        pkg = dbpf.DBPF()
        pkg_path = self._mktemp()
        with open(tga_path, "rb") as f:
            input = f.read()
        pkg.add_file(dbpf.Stream.TYPE_IMAGE, 0x00, 0x00, input, compress=True)
        pkg.save(pkg_path)

        # Read and verify checksum
        pkg = dbpf.DBPF(pkg_path)
        entry = pkg.index.entries[0]
        output_path = self._mktemp()
        pkg.extract(entry, output_path)
        with open(output_path, "rb") as f:
            md5 = hashlib.md5(f.read()).hexdigest()

        self.assertTrue(md5 == self.tga_md5)
