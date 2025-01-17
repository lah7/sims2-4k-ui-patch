"""
Perform tests on the game file module to ensure game files are handled as expected.
"""
# pylint: disable=protected-access
import os
import shutil
import sys
import tempfile
import unittest

# Our modules are in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from sims2patcher import gamefile


class GameFileTest(unittest.TestCase):
    """
    Test our "gamefile" module against a dummy installation.
    """
    @classmethod
    def _abspath(cls, path: str) -> str:
        """Return a path to the real file in our dummy installation"""
        return os.path.join(cls.game_dir, path.replace("/", os.sep))

    @classmethod
    def setUpClass(cls):
        """Create the files for the dummy installation"""
        gamefile.FILE_PATCH_VERSION = 3.0
        cls.game_dir = tempfile.mkdtemp()

        cls.file_structure = [
            #    <!> Do not change order! <!>  Indexes of files are used in the tests.

            # Replacements for Base Game
            cls._abspath("Test Games/The Sims 2/TSData/Res/UI/CaSIEUI.data"),                   ### 0
            cls._abspath("Test Games/The Sims 2/TSData/Res/Fonts/FontStyle.ini"),               ### 1
            cls._abspath("Test Games/The Sims 2/TSData/Res/UI/ui.package"),                     ### 2
            cls._abspath("Test Games/The Sims 2/TSData/Res/Locale/French/UI/CaSIEUI.data"),     ### 3
            cls._abspath("Test Games/The Sims 2/TSData/Res/Locale/French/UI/ui.package"),
            cls._abspath("Test Games/The Sims 2/TSData/Res/Locale/German/UI/CaSIEUI.data"),
            cls._abspath("Test Games/The Sims 2/TSData/Res/Locale/German/UI/ui.package"),

            # Replacements for Expansion Pack
            cls._abspath("Test Games/The Sims 2 University/TSData/Res/UI/CaSIEUI.data"),
            cls._abspath("Test Games/The Sims 2 University/TSData/Res/UI/ui.package"),
            cls._abspath("Test Games/The Sims 2 University/TSData/Res/Locale/French/UI/ui.package"),

            # Overrides
            cls._abspath("Test Games/The Sims 2/TSData/Res/Objects/objects.package"),           ### 10

            # Files that wouldn't be touched
            cls._abspath("Test Games/The Sims 2 University/TSData/Res/Sims3D/Objects.package"), ### 11
            cls._abspath("Test Games/The Sims 2 University/TSData/Res/Overrides/existing.package"), ### 12
            cls._abspath("Test Games/The Sims 2/TSData/Res/Sims3D/random.package"),             ### 13
        ]
        cls.total_files = len(cls.file_structure) - 4

        os.chdir(cls.game_dir)
        for path in cls.file_structure:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("")

        return super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        """Clean up our dummy installation"""
        if cls.game_dir:
            os.chdir("..")
            shutil.rmtree(cls.game_dir)
        return super().tearDownClass()

    def test_patchable_paths(self):
        """Check we read the correct count of patchable files"""
        paths = gamefile.get_patchable_paths(self.game_dir)
        self.assertEqual(len(paths), self.total_files)

        for path in self.file_structure[0:8]:
            self.assertTrue(path in paths, "Expected file to patch is missing")

        for path in self.file_structure[11:14]:
            self.assertFalse(path in paths, "Unexpected file found in patch list")

    def test_patchable_files(self):
        """Check we are able to process GameFile objects"""
        paths = gamefile.get_patchable_paths(self.game_dir)
        gamefile.get_patchable_files(paths)

    def test_game_file(self):
        """Check we create the correct kind of GameFile objects"""
        self.assertIsInstance(gamefile.get_game_file(self._abspath("Test Games/The Sims 2/TSData/Res/Objects/objects.package")), gamefile.GameFileOverride)
        self.assertIsInstance(gamefile.get_game_file(self._abspath("Test Games/The Sims 2/TSData/Res/UI/ui.package")), gamefile.GameFileReplacement)

    def test_legacy_meta_file(self):
        """Check files patched under version 0.1.0 are marked as outdated"""
        filename = self.file_structure[0] # CaSIEUI.data
        with open(f"{filename}.patched", "w", encoding="utf-8") as f:
            # v0.1.0
            f.write("# This file was patched by lah7/sims2-4k-ui-patch.\n")
            f.write("# It is recommended to keep this file (and the .bak) so you can update the patches or revert without reinstalling the game.\n")
            f.write("# Do not change the contents of this file!\n")
            f.write("\n")
            f.write("0.1\n")

        gf = gamefile.get_game_file(filename)
        self.assertEqual(gf.patch_version, 0.1)
        self.assertEqual(gf.patched, True)
        self.assertEqual(gf.outdated, True)

    def test_meta_file(self):
        """Check we correctly read and write meta files"""
        filename = self.file_structure[1] # FontStyle.ini
        gf = gamefile.get_game_file(filename)
        gf.patch_version = gamefile.FILE_PATCH_VERSION
        gf.uncompressed = True
        gf.scale = 3.0
        gf.upscale_filter = 2

        gf.patched = True
        gf.backup()
        gf.write_meta_file()

        gf2 = gamefile.get_game_file(filename)
        self.assertTrue(os.path.exists(f"{filename}.patched"))
        self.assertEqual(gf2.patch_version, gamefile.FILE_PATCH_VERSION)
        self.assertEqual(gf2.uncompressed, True)
        self.assertEqual(gf2.scale, 3.0)
        self.assertEqual(gf2.upscale_filter, 2)

    def test_outdated_patches(self):
        """Check users are notified of outdated patches based on version"""
        filename = self.file_structure[2] # ui.package
        gamefile.FILE_PATCH_VERSION = 1.5
        gf = gamefile.get_game_file(filename)
        gf.patched = True
        gf.backup()
        gf.write_meta_file()

        gamefile.FILE_PATCH_VERSION = 3.0
        gf2 = gamefile.get_game_file(filename)
        self.assertEqual(gf2.patch_version, 1.5)
        self.assertLess(gf2.patch_version, gamefile.FILE_PATCH_VERSION)
        self.assertEqual(gf2.outdated, True)

    def test_replacement_backup(self):
        """Check we correctly backup and restore files that we replace"""
        filename = self.file_structure[3] # Localised CaSIEUI.data
        gf = gamefile.get_game_file(filename)
        self.assertIsInstance(gf, gamefile.GameFileReplacement)

        gf.backup()
        self.assertTrue(gf.backed_up)
        self.assertTrue(os.path.exists(f"{filename}.bak"))

        gf.restore()
        self.assertFalse(gf.backed_up)
        self.assertFalse(os.path.exists(f"{filename}.bak"))

    def test_override_backup(self):
        """Check we correctly place files in the Overrides folder"""
        filename = self.file_structure[10] # objects.package
        gf = gamefile.get_game_file(filename)
        self.assertIsInstance(gf, gamefile.GameFileOverride)
        self.assertFalse(gf.backed_up)
        gf.backup()

        # Simulate the new package being created
        with open(gf.target_file_path, "w", encoding="utf-8") as f:
            f.write("")

        # Package exists in Overrides folder?
        self.assertTrue(gf.backed_up)
        self.assertTrue(gf.target_file_path)
        self.assertGreater(gf.target_file_path.find("Overrides"), 0)

        # Package removed from Overrides folder?
        gf.restore()
        self.assertTrue(os.path.exists(gf.file_path))
        self.assertFalse(gf.backed_up)
        self.assertFalse(os.path.exists(gf.target_file_path))

    def test_replacement_io(self):
        """Check we don't write to a file that we are reading"""
        gf = gamefile.get_game_file(self.file_structure[2]) # ui.package
        self.assertIsInstance(gf, gamefile.GameFileReplacement)
        self.assertTrue(gf.original_file_path.endswith(".bak")) # Read from backup (original)
        self.assertNotEqual(gf.original_file_path, gf.target_file_path) # Not same
        self.assertEqual(gf.target_file_path, gf.file_path)
        self.assertTrue(gf.target_file_path.endswith(".package")) # Write to original path

    def test_override_io(self):
        """Check we leave the original file intact and save to the Overrides folder"""
        gf = gamefile.get_game_file(self.file_structure[10]) # objects.package
        self.assertIsInstance(gf, gamefile.GameFileOverride)
        self.assertEqual(gf.original_file_path, gf.file_path) # Read from original
        self.assertTrue(gf.original_file_path.find("Overrides") == -1)
        self.assertTrue(gf.original_file_path.endswith(".package"))
        self.assertNotEqual(gf.original_file_path, gf.target_file_path) # Not same
        self.assertTrue(gf.target_file_path.endswith(".package")) # Write to Overrides folder
        self.assertTrue(gf.target_file_path.find("Overrides") > 0)
