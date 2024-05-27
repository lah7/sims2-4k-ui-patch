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
import os
import shutil

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
        self.game_name = self.get_game_name(path)
        self.name = os.path.basename(path)
        self.relative_path = self.file_path.split(self.game_name)[1][1:]

        self.backed_up = os.path.exists(self.backup_path)
        self.patched = False
        self.patch_outdated = False
        self.patched_version = 0.0

        self.read_meta_file()

    def __str__(self):
        return f"{os.path.basename(self.file_path)} [{self.game_name}]"

    def get_game_name(self, file_path) -> str:
        """
        Identify the game name by going up a directory until we find "filelist.txt",
        the root of the game installation, and take the name from this directory.
        """
        path = os.path.realpath(file_path)
        root_count = len(path.split(os.sep))
        while root_count > 2:
            if os.path.exists(os.path.join(path, "filelist.txt")):
                return path.split(os.sep)[-1]
            path = os.path.realpath(os.path.join(path, ".."))
            root_count = len(path.split(os.sep))
        return file_path

    def read_meta_file(self):
        """
        Read the file describing the patch status.
        Stored next to game file (and its backup) is a ".patched" text file containing:

        Line
        ----    -------------------------------------------------------
        1-3     Message for user
        4       Patcher version used (float, e.g. 1.2 ≈ major.minor)
        """
        if os.path.exists(self.meta_path):
            self.patched = True
            with open(self.meta_path, "r", encoding="utf-8") as f:
                try:
                    # Messages for user (ignored)
                    for _ in range(4):
                        f.readline()

                    self.patched_version = float(f.readline().strip())
                    self.patch_outdated = self.patched_version < FILE_PATCH_VERSION
                except ValueError:
                    print("Malformed metadata file:", self.meta_path)
                    self.patched = False

    def write_meta_file(self):
        """
        Write a file describing the patch for future use.
        """
        if not self.patched or not self.backed_up:
            raise RuntimeError("Not patched or backup file missing!")

        with open(self.meta_path, "w", encoding="utf-8") as f:
            f.write("# This file was patched by lah7/sims2-4k-ui-mod.\n")
            f.write("# It is recommended to keep this file (and the .bak) so you can update the patches or revert without reinstalling the game.\n")
            f.write("# Do not change the contents of this file!\n")
            f.write("\n")
            f.write(f"{FILE_PATCH_VERSION}\n")

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
