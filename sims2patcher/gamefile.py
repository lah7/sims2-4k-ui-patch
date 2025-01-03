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
# Copyright (C) 2023-2024 Luke Horwell <code@horwell.me>
#
import configparser
import os
import shutil
from hashlib import md5

FILE_PATCH_VERSION: float = 0.0 # Set by main program


class GameFile():
    """
    Describes a game file and whether it is currently patched.

    This tool will create these adjacent files:
        - *.bak         Backup of the original game file
        - *.patched     Details about patch (e.g. which version of this tool and checksums)

    Backup files (*.bak) are essential to undo modifications, such as to revert the patch back
    to the original, or to re-patch using newer versions of this program.
    """
    def __init__(self, path: str):
        self.file_path = path
        self.backup_path = path + ".bak"
        self.meta_path = path + ".patched"
        self.filename = os.path.basename(path)

        self.backed_up = os.path.exists(self.backup_path)
        self.patched = False
        self.outdated = False
        self.patch_version = 0.0

        self.uncompressed: bool = False
        self.scale: float = 2.0
        self.upscale_filter: int = 0 # Image.Resampling.NEAREST

        self.md5_checksum_backup = ""
        self.md5_checksum_patched = ""

        self.read_meta_file()

    def __str__(self):
        return os.path.basename(self.file_path)

    def read_meta_file(self):
        """
        Read an INI-like file describing the patch status.
        Stored next to game file (and its backup) is a ".patched" text file containing:
        """
        if os.path.exists(self.meta_path):
            config = configparser.ConfigParser()
            try:
                config.read(self.meta_path)
            except configparser.MissingSectionHeaderError:
                # v0.1.0 wrote lines directly with an expected order. Replaced since v0.2.0.
                with open(self.meta_path, "r", encoding="utf-8") as f:
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
                self.md5_checksum_backup = config.get("patch", "md5_checksum_backup")
                self.md5_checksum_patched = config.get("patch", "md5_checksum_patched")
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
        with open(self.file_path, "rb") as f:
            self.md5_checksum_patched = md5(f.read(), usedforsecurity=False).hexdigest()
        with open(self.backup_path, "rb") as f:
            self.md5_checksum_backup = md5(f.read(), usedforsecurity=False).hexdigest()

        config = configparser.ConfigParser()
        config["patch"] = {
            "version": str(FILE_PATCH_VERSION),
            "uncompressed": str(self.uncompressed),
            "scale": str(self.scale),
            "upscale_filter": str(self.upscale_filter),
            "md5_checksum_backup": self.md5_checksum_backup,
            "md5_checksum_patched": self.md5_checksum_patched,
        }
        with open(self.meta_path, "w", encoding="utf-8") as f:
            config.write(f)

        # Prepend comment at the start of file
        with open(self.meta_path, "r+", encoding="utf-8") as f:
            content = f.read()
            f.seek(0, 0)
            f.write("# File patched by lah7's sims2-4k-ui-patch program.\n")
            f.write("# Keep this file (and the backup) so you can update the patches or revert without reinstalling the game.\n")
            f.write("# === Do not edit this file! ===\n")
            f.write("\n")
            f.write(content)

    def backup(self):
        """
        Create a backup of the original game file.
        """
        if os.path.exists(self.backup_path):
            raise RuntimeError("Backup already exists: " + self.backup_path)
        shutil.copyfile(self.file_path, self.backup_path)
        self.backed_up = True

    def restore(self):
        """
        Restore the original game file from backup.
        """
        if os.path.exists(self.backup_path):
            os.remove(self.file_path)
            shutil.move(self.backup_path, self.file_path)
            if os.path.exists(self.meta_path):
                os.remove(self.meta_path)
            self.backed_up = False
