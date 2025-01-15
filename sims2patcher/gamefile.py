"""
Describes a game file and whether it is currently patched.
"""
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Copyright (C) 2023-2025 Luke Horwell <code@horwell.me>
#
import configparser
import glob
import os
import shutil
from typing import List

FILE_PATCH_VERSION: float = 0.0 # Set by main program


def get_patchable_paths(install_dir: str) -> list[str]:
    """
    Return a list of game files paths that can be patched.
    """
    paths: List[str] = []

    for filename in ["ui.package", "FontStyle.ini", "CaSIEUI.data"]:
        paths += glob.glob(install_dir + f"/**/{filename}", recursive=True)

    if not paths:
        raise ValueError("No patchable files found")

    return paths


def get_game_file(path: str) -> 'GameFile':
    """
    Return a game file object for patching.
    """
    if path.endswith("objects.package"):
        return GameFileOverride(path)
    return GameFileReplacement(path)


def get_patchable_files(files_to_patch: list[str]) -> list['GameFile']:
    """
    Return a list of game files objects for patching.
    """
    files: List['GameFile'] = []

    for path in files_to_patch:
        files.append(get_game_file(path))

    return files


class GameFile():
    """
    Base class describing a game file and its current patch state.
    """
    def __init__(self, path: str):
        self.file_path = path
        self.filename = os.path.basename(path)
        self._meta_path = path + ".patched"

        # Patch status
        self.patched = False
        self.outdated = False
        self.patch_version = 0.0

        # Patch settings
        self.uncompressed: bool = False
        self.scale: float = 2.0
        self.upscale_filter: int = 0 # Image.Resampling.NEAREST

        self.read_meta_file()

    def __str__(self):
        return self.filename

    def read_meta_file(self):
        """
        Read an INI-like file describing the patch status.
        This is stored next to game file (along with its backup, if necessary) with a ".patched" extension.
        """
        if os.path.exists(self._meta_path):
            config = configparser.ConfigParser()
            try:
                config.read(self._meta_path)
            except configparser.MissingSectionHeaderError:
                # v0.1.0 wrote lines directly with an expected order. Replaced since v0.2.0.
                with open(self._meta_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    if lines[4] == "0.1\n":
                        self.patched = True
                        self.patch_version = 0.1
                        self.outdated = True
                        return
            except configparser.ParsingError:
                return

            self.patched = True
            try:
                self.patch_version = float(config.get("patch", "version"))
                self.uncompressed = config.getboolean("patch", "uncompressed")
                self.scale = config.getfloat("patch", "scale")
                self.upscale_filter = config.getint("patch", "upscale_filter")
            except (configparser.NoOptionError, configparser.NoSectionError):
                self.patch_version = 0.0

            self.outdated = self.patch_version < FILE_PATCH_VERSION

    def write_meta_file(self):
        """
        Write an INI-like file describing the patch for future use.
        """
        if not self.patched or not self.backed_up:
            raise RuntimeError("Not patched or backup file missing!")

        # Generate checksums
        config = configparser.ConfigParser()
        config["patch"] = {
            "version": str(FILE_PATCH_VERSION),
            "uncompressed": str(self.uncompressed),
            "scale": str(self.scale),
            "upscale_filter": str(self.upscale_filter),
        }
        with open(self._meta_path, "w", encoding="utf-8") as f:
            config.write(f)

        # Prepend comment at the start of file
        with open(self._meta_path, "r+", encoding="utf-8") as f:
            content = f.read()
            f.seek(0, 0)
            f.write("#\n# File patched by lah7/sims2-4k-ui-patch program.\n")
            f.write("# Keep this file (and any backup files) so you can update or revert the patches\n")
            f.write("# without reinstalling the game.\n")
            f.write("#\n# ==============================\n")
            f.write("# === Do not edit this file! ===\n")
            f.write("# ==============================\n")
            f.write("#\n")
            f.write(content)

    @property
    def original_file_path(self) -> str:
        """
        Return the path to a streamable package file.
        """
        raise NotImplementedError("Implemented by subclass")

    @property
    def target_file_path(self) -> str:
        """
        Return the path to where the patched package file will be saved.
        """
        return self.file_path

    @property
    def backed_up(self) -> bool:
        """
        Whether the original game file has been backed up.
        """
        raise NotImplementedError("Implemented by subclass")

    def backup(self):
        """
        Create a backup of the original game file.
        """
        raise NotImplementedError("Implemented by subclass")

    def restore(self):
        """
        Restore the original game file from backup.
        """
        raise NotImplementedError("Implemented by subclass")


class GameFileReplacement(GameFile):
    """
    Describes a game file that will be replaced with a patched version in-place.

    The original file is backed up in order to undo modifications.
    Patches can be reverted (without game reinstallation), or be updated
    with a newer version of this program.
    """
    def __init__(self, path: str):
        super().__init__(path)
        self._backup_path = f"{self.file_path}.bak"

    @property
    def original_file_path(self) -> str:
        return self._backup_path

    @property
    def backed_up(self) -> bool:
        return os.path.exists(self._backup_path)

    def backup(self):
        if os.path.exists(self._backup_path):
            raise RuntimeError(f"Backup already exists: {self._backup_path}")
        shutil.copyfile(self.file_path, self._backup_path)

    def restore(self):
        if os.path.exists(self._backup_path):
            os.remove(self.file_path)
            shutil.move(self._backup_path, self.file_path)
            if os.path.exists(self._meta_path):
                os.remove(self._meta_path)


class GameFileOverride(GameFile):
    """
    Describes a game file that is saved to that installation's "Overrides" folder.

    The original package is left intact, and any patched files within the package
    is saved to a new one in the "Overrides" folder. The game loads the new
    changes provided the files use the same IDs.
    """
    def __init__(self, path: str):
        super().__init__(path)
        self._override_path = self._get_override_path()

    def _get_override_path(self) -> str:
        """
        Return path to the file current game's "Overrides" folder, from the "Res" folder.
        """
        parts = self.file_path.split(os.sep)
        try:
            while parts[-1] != "Res" and len(parts) > 0:
                parts.pop()
        except IndexError as e:
            raise RuntimeError(f"Couldn't find 'Res' folder for file: {self.file_path}") from e

        overrides_dir = os.path.join(os.sep.join(parts), "Overrides")
        if not os.path.exists(overrides_dir):
            os.makedirs(overrides_dir)

        return os.path.join(overrides_dir, f"hidpi-patches-{self.filename}")

    @property
    def original_file_path(self) -> str:
        return self.file_path

    @property
    def target_file_path(self) -> str:
        return self._override_path

    @property
    def backed_up(self) -> bool:
        # Technically, it's always backed up. Original file is left intact.
        # This response is for the current status UI:
        # - True  = File patched, revertable
        # - False = File to be patched
        return os.path.exists(self._override_path)

    def backup(self):
        pass

    def restore(self):
        if os.path.exists(self._override_path):
            os.remove(self._override_path)
        if os.path.exists(self._meta_path):
            os.remove(self._meta_path)
