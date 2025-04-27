"""
Perform tests on the scripts in the tools directory to make sure they output data as expected.
"""
import os
import shutil
import subprocess
import sys

# Our modules are in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from sims2patcher import dbpf
from tests.test_base import BaseTestCase


class ToolsTest(BaseTestCase):
    """
    Test scripts from the tools directory.
    """
    def _run_tool(self, filename: str, args: list):
        """
        Run a script from the tools/ directory with the specified arguments.
        Raises an error if the exit code is not 0.
        """
        script_path = os.path.join("tools", filename)
        try:
            result = subprocess.run([sys.executable, script_path] + args, check=False, capture_output=True, text=True, timeout=8)
        except subprocess.TimeoutExpired as e:
            raise TimeoutError(f"{filename} took too long to execute") from e

        if result.returncode != 0:
            raise RuntimeError(f"{filename} failed with code {result.returncode}: {result.stderr}")

        return result.stdout

    def test_benchmark_qfs(self):
        """Test QFS benchmark works with expected differences in results"""
        # Script does not run on Windows due to multiprocessing
        if os.name == "nt":
            self.skipTest("Script not compatible with Windows.")

        tmp_path = self.mktemp()
        self._run_tool("benchmark_qfs.py", ["-o", tmp_path, "-f", self.package.path, "-s", "3", "-m", "2", "-x", "16"])

        with open(tmp_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 16, "Unexpected number of benchmark results")
            # QFS   MB      C. Time,  D. Time
            # 0,    0.027,  0.014,    0.0
            # 16,   0.007,  0.042,    0.001
            a_level, a_size, a_c_time, a_d_time = map(float, lines[1].split(","))
            b_level, b_size, b_c_time, b_d_time = map(float, lines[15].split(","))
            self.assertLess(a_level, b_level, "Expected results in ascending order")
            self.assertGreater(a_size, b_size, "Expected smaller size for higher QFS level")
            self.assertLess(a_c_time, b_c_time, "Expected longer compression time for higher QFS level")
            self.assertGreaterEqual(a_d_time, b_d_time, "Expected shorter decompression time for higher QFS level")

    def test_package_stats_csv(self):
        """Test package stats can be exported to CSV correctly"""
        csv_path = f"{self.package.path}.csv"
        self._run_tool("view_package_stats.py", ["--csv", self.package.path])
        self.assertTrue(os.path.exists(csv_path), "CSV file was not generated")

        with open(csv_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

            self.assertEqual(len(lines), len(self.package.entries) + 1, "Unexpected number of CSV lines")

            # First line should the TGA image
            real_file = "tests/files/src/image1.tga"
            with open(real_file, "rb") as f:
                real_md5 = self.md5(f.read())

            # File, 0x856ddbac, 0x1000, 0x1, 0x0, Yes, 2414, 16428, 25d19194bf5d17b6c439f1974cba4ee9, 4ff136c0acad717e113e121b9b265e57
            file_type, type_id, group_id, instance_id, resource_id, compressed, index_size, uncompressed_size, index_md5, data_md5 = lines[1].split(",") # pylint: disable=unused-variable

            self.assertEqual(file_type, dbpf.FILE_TYPES[dbpf.TYPE_IMAGE], "Unexpected file type")
            self.assertEqual(group_id, "0x1000", "Unexpected group ID")
            self.assertEqual(instance_id, "0x1", "Unexpected instance ID")
            self.assertEqual(resource_id, "0x0", "Test package does not use resource IDs")
            self.assertEqual(compressed, "Yes", "Unexpected compression status")
            self.assertEqual(int(uncompressed_size), os.path.getsize(real_file), "Unexpected uncompressed size")
            self.assertEqual(data_md5.strip(), real_md5, "Unexpected MD5 hash")

        os.remove(csv_path)

    def test_extract_file(self):
        """Test a file from the package can be extracted correctly via script"""
        tmp_dir = f"{self.mktemp()}_dir"
        self._run_tool("extract_package.py", [self.package.path, tmp_dir, "0x856ddbac", "0x1000", "0x1"])

        self.assertTrue(os.path.exists(tmp_dir), "Output folder could not be created")
        self.assertTrue(os.path.exists("tests/files/src/image1.tga"), "Expected source file does not exist")

        with open("tests/files/src/image1.tga", "rb") as f:
            expected_md5 = self.md5(f.read())

        with open(f"{tmp_dir}/0x856ddbac_0x1000_0x1.tga", "rb") as f:
            self.assertEqual(self.md5(f.read()), expected_md5, "Extracted file does not match expected MD5 hash")

        shutil.rmtree(tmp_dir)
