#!/usr/bin/python3
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
"""
Graphical patcher interface to apply and revert patches for rescaling
the The Sims 2 user interface for HiDPI resolutions.

The patcher keeps a backup of the original file to allow patches to
be reverted, to "uninstall" the modifcations, or for future patcher updates.
"""
import glob
import os
import signal
import sys
import webbrowser
from enum import Enum
from typing import List

import requests
from PIL import Image
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QMouseEvent, QPixmap
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog,
                             QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                             QLineEdit, QMainWindow, QMessageBox, QProgressBar,
                             QPushButton, QSizePolicy, QStatusBar, QStyle,
                             QToolButton, QVBoxLayout, QWidget)

from sims2patcher import dbpf, gamefile, patches
from sims2patcher.gamefile import GameFile

VERSION = "v0.2.0"
MAJOR = 0
MINOR = 2
PATCH = 0

gamefile.FILE_PATCH_VERSION = float(f"{MAJOR}.{MINOR}") # Stored in file describing patch status

DEFAULT_DIRS = [
    "C:\\Program Files\\EA GAMES",
    "C:\\Program Files (x86)\\EA GAMES",
    "C:\\Program Files\\The Sims 2 Ultimate Collection",
    "C:\\Program Files (x86)\\The Sims 2 Ultimate Collection",
    "C:\\Program Files\\Origin Games\\The Sims 2 Ultimate Collection",
    "C:\\Program Files (x86)\\Origin Games\\The Sims 2 Ultimate Collection",
    "C:\\Program Files\\The Sims 2 Starter Pack",
    "C:\\Program Files (x86)\\The Sims 2 Starter Pack",
    "C:\\Program Files\\Origin Games",
    "C:\\Program Files (x86)\\Origin Games",
    "EA GAMES",
]

PROJECT_URL = "https://github.com/lah7/sims2-4k-ui-patch"

# Options
LABELS_UI_SCALE = {
    "200% (4K / 2160p)": 2.0,
    "150% (2K / 1440p)": 1.5,
}

LABELS_UI_FILTER = {
    "Nearest Neighbour (Default)": Image.Resampling.NEAREST,
    "Hamming": Image.Resampling.HAMMING,
    "Linear": Image.Resampling.BILINEAR,
    "Cubic": Image.Resampling.BICUBIC,
    "Lanczos": Image.Resampling.LANCZOS,
}

class StatusIcon(Enum):
    """
    Plumbob icon indicating the overall patch status.
    """
    # String is substituted into "status_{}@2x.png"
    DEFAULT = "default"
    GREEN = "green"
    GREY = "grey"
    YELLOW = "yellow"
    RED = "red"


@staticmethod
def get_resource(relative_path):
    """
    Get a resource bundled with the application. When run as a Python script, use the current directory.
    """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path) # type: ignore # pylint: disable=protected-access
    return os.path.join(os.path.abspath("."), relative_path)


class State:
    """
    Store details about the current patcher inputs.
    """
    def __init__(self):
        # Parent folder containing The Sims 2 installations
        self.game_install_dir = ""

        # List of game files that will be patched
        self.game_paths: List[str] = []
        self.game_files: List[GameFile] = []

        # This patcher program has a new update
        self.update_available = False

        # Options
        self.scale: float = 2.0
        self.filter: int = Image.Resampling.NEAREST
        self.compress: bool = True

    def refresh_file_list(self):
        """
        Return a list of files that will be patched by this program.
        """
        files = []
        for filename in ["ui.package", "FontStyle.ini", "CaSIEUI.data"]:
            files += glob.glob(self.game_install_dir + f"/**/{filename}", recursive=True)

        self.game_paths = sorted(list(set(files)))
        if len(self.game_paths) == 0:
            raise ValueError("No patchable files found")

        self.game_files = [GameFile(path) for path in self.game_paths]

    def set_game_install_path(self, path: str):
        """
        Set the game installation folder and gather a list of patchable game files
        """
        self.game_install_dir = path
        self.refresh_file_list()

    def auto_detect_game_path(self):
        """Automatically detect the game installation folder"""
        for path in DEFAULT_DIRS:
            if os.path.exists(path):
                self.set_game_install_path(path)
                return


class PatcherApplication(QMainWindow):
    """
    A GUI application for patching The Sims 2 game files. Powered by PyQt6.
    """
    def __init__(self):
        """Set up the application layout"""
        super().__init__()

        self.state = State()

        self.base_layout = QVBoxLayout()
        self.base_widget = QWidget()
        self.base_widget.setLayout(self.base_layout)
        self.setCentralWidget(self.base_widget)

        # Build layout
        self._create_top_banner()
        self._create_folder_selector()
        self._create_options()
        self._create_patch_status()
        self._create_buttons()
        self._create_status_bar()

        self.base_layout.addStretch()

        # Set window properties
        self.setWindowTitle("UI Patcher for The Sims 2")
        self.setWindowIcon(QIcon(get_resource("assets/icon.ico")))
        self.show()

        # Place in the center
        self.move(QApplication.primaryScreen().geometry().center() - self.frameGeometry().center()) # type: ignore

        # Background check
        self.check_for_updates()

        # Initial state
        self.state.auto_detect_game_path()
        if self.state.game_install_dir:
            self.game_files_input.setText(self.state.game_install_dir)
            QApplication.processEvents()
            QTimer.singleShot(250, self.refresh_patch_state)

    def _create_top_banner(self):
        """Create a banner displaying the project logo"""
        self.banner = QWidget()
        self.banner_layout = QHBoxLayout()
        self.banner.setLayout(self.banner_layout)
        self.banner.setStyleSheet("background-color: #5262c7;")

        logo = QPixmap(get_resource("assets/banner@2x.png"))
        logo.setDevicePixelRatio(self.devicePixelRatio())

        self.banner_logo = QLabel()
        self.banner_logo.setPixmap(logo)
        self.banner_logo.setFixedHeight(70)
        self.banner_layout.addWidget(self.banner_logo)

        self.base_layout.addWidget(self.banner)

    def _create_folder_selector(self):
        """An area to select game files (typically "EA Games" folder)"""
        self.layout_folders = QHBoxLayout()

        self.group_folders = QGroupBox("Installation Folder")
        self.group_folders.setLayout(self.layout_folders)

        self.game_files_label = QLabel("Game Files:")
        self.layout_folders.addWidget(self.game_files_label)

        self.game_files_input = QLineEdit()
        self.game_files_input.setPlaceholderText(DEFAULT_DIRS[1])
        self.layout_folders.addWidget(self.game_files_input)

        self.browse_button = QToolButton()
        self.browse_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.browse_button.setText("Browse")
        self.browse_button.setToolTip("Browse")
        self.browse_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)) # type: ignore
        self.layout_folders.addWidget(self.browse_button)

        self.base_layout.addWidget(self.group_folders)

        def _wrong_dir():
            """
            Show a warning when the directory doesn't contain any patchable files.
            """
            QMessageBox.warning(self, "Wrong folder selected", "Game files for The Sims 2 (or its expansion packs) was not found in this folder.")

        def _browse():
            """
            Open the file dialog to select the game's directory.
            """
            dirname = QFileDialog.getExistingDirectory(self, "Select The Sims 2 installation folder", self.game_files_input.text(), QFileDialog.Option.ShowDirsOnly)

            if not dirname:
                return

            dirname = dirname.replace("/", os.sep)
            self.game_files_input.setText(dirname)
            try:
                self.state.set_game_install_path(dirname)
            except ValueError:
                _wrong_dir()
            self.refresh_patch_state()

        def _manual_entry():
            """
            Callback when the user manually types the game directory.
            """
            dirname = self.game_files_input.text()
            if not os.path.exists(dirname):
                QMessageBox.warning(self, "Directory not found", "The directory does not exist.")
                self.state.game_install_dir = ""
                self.state.game_files = []
                self.refresh_patch_state()
                return

            try:
                self.state.set_game_install_path(dirname)
                self.refresh_patch_state()
            except ValueError:
                _wrong_dir()
                return

        self.browse_button.clicked.connect(_browse)
        self.game_files_input.returnPressed.connect(_manual_entry)

    def _create_options(self):
        """An area to select patches/options"""
        def _scale_changed():
            """Callback when the user changes the scale option."""
            self.state.scale = LABELS_UI_SCALE[self.scale_option.currentText()]
            self.refresh_patch_state()

        def _filter_changed():
            """Callback when the user changes the filter option."""
            self.state.filter = LABELS_UI_FILTER[self.filter_option.currentText()]
            self.refresh_patch_state()

        def _compress_changed():
            """Callback when the user changes the compress option."""
            self.state.compress = self.compress_option.isChecked()
            self.refresh_patch_state()

        self.layout_options = QFormLayout()

        self.group_options = QGroupBox("Options")
        self.group_options.setLayout(self.layout_options)
        self.group_options.setEnabled(False)

        self.scale_option = QComboBox()
        self.scale_option.addItems(list(LABELS_UI_SCALE.keys()))
        self.layout_options.addRow("Scale:", self.scale_option)
        self.scale_option.currentIndexChanged.connect(_scale_changed)

        self.filter_option = QComboBox()
        self.filter_option.addItems(list(LABELS_UI_FILTER.keys()))
        self.layout_options.addRow("Upscale Filter:", self.filter_option)
        self.filter_option.currentIndexChanged.connect(_filter_changed)

        self.compress_option = QCheckBox("Compress packages")
        self.compress_option.setChecked(True)
        self.layout_options.addRow("Save disk space:", self.compress_option)
        self.compress_option.stateChanged.connect(_compress_changed)

        self.base_layout.addWidget(self.group_options)

    def _create_patch_status(self):
        """Create a view showing the overall patch status"""
        self.layout_status = QHBoxLayout()

        self.group_status = QGroupBox()
        self.group_status.setLayout(self.layout_status)

        self.status_icon = QPixmap(get_resource("assets/status_default@2x.png"))
        self.status_icon.setDevicePixelRatio(self.devicePixelRatio())

        self.status_icon_label = QLabel()
        self.status_icon_label.setPixmap(self.status_icon)
        self.layout_status.addWidget(self.status_icon_label)

        self.status_wrapper = QVBoxLayout()

        self.status_text = QLabel("To begin, select a folder")
        self.status_text.setStyleSheet("font-weight: bold;")
        self.status_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.status_text.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.status_wrapper.addWidget(self.status_text)

        self.status_progress = QProgressBar()
        self.status_progress.setHidden(True)
        self.status_wrapper.addWidget(self.status_progress)

        self.layout_status.addLayout(self.status_wrapper)
        self.base_layout.addWidget(self.group_status)

    def _create_buttons(self):
        """Create the primary action buttons"""
        self.layout_buttons = QHBoxLayout()

        self.layout_buttons.addStretch()

        self.btn_revert = QPushButton()
        self.btn_revert.setText("Revert")
        self.btn_revert.setToolTip("Undo patches by restoring original files")
        self.btn_revert.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton)) # type: ignore
        self.btn_revert.setEnabled(False)
        self.btn_revert.clicked.connect(self.revert_patches)
        self.layout_buttons.addWidget(self.btn_revert)

        self.btn_patch = QPushButton()
        self.btn_patch.setText("Patch")
        self.btn_patch.setToolTip("Begin the patching process")
        self.btn_patch.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)) # type: ignore
        self.btn_patch.setEnabled(False)
        self.btn_patch.clicked.connect(self.start_patching)
        self.layout_buttons.addWidget(self.btn_patch)

        self.base_layout.addLayout(self.layout_buttons)

    def _create_status_bar(self):
        """Create a footer showing the current version and project link"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.version_label = QLabel(VERSION)
        self.version_label.mousePressEvent = self._open_homepage # type: ignore
        self.version_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.version_label.setStyleSheet("color: #888;")
        self.status_bar.addWidget(self.version_label)

        self.project_url_label = QLabel(PROJECT_URL)
        self.project_url_label.mousePressEvent = self._open_homepage # type: ignore
        self.project_url_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.project_url_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.project_url_label.setStyleSheet("color: #888;")
        self.status_bar.addPermanentWidget(self.project_url_label)

    def _open_homepage(self, event: QMouseEvent): # pylint: disable=unused-argument
        if self.state.update_available:
            webbrowser.open(f"{PROJECT_URL}/releases/latest")
        else:
            webbrowser.open(PROJECT_URL)

    def update_status_icon(self, status: StatusIcon):
        """Update the status icon"""
        self.status_icon.load(get_resource(f"assets/status_{status.value}@2x.png"))
        self.status_icon_label.setPixmap(self.status_icon)

    def check_for_updates(self):
        """
        Check the GitHub repository for a newer version and quietly inform the user.
        """
        try:
            r = requests.get("https://raw.githubusercontent.com/lah7/sims2-4k-ui-patch/master/version.txt", timeout=3)
        except (requests.exceptions.RequestException, requests.exceptions.Timeout):
            return

        if r.status_code == 200:
            latest_version = r.text.split("\n")[0]
            latest_ver_parts = latest_version.split(".")
            try:
                if int(latest_ver_parts[0]) > MAJOR or int(latest_ver_parts[1]) > MINOR:
                    self.version_label.setText(f"{VERSION} (update available: v{latest_version})")
                    self.version_label.setStyleSheet("")
                    self.state.update_available = True
            except (TypeError, ValueError):
                return

    def refresh_patch_state(self):
        """
        Check the game files and update the UI to reflect the status.
        This is called when the game folder is changed, or options are updated.

        Prevent changing options when there are patched files, to avoid inconsistencies.
        """
        self.btn_patch.setEnabled(False)
        self.btn_revert.setEnabled(False)
        self.group_folders.setEnabled(True)
        self.group_options.setEnabled(False)
        self.status_progress.setHidden(True)

        if not self.state.game_install_dir:
            self.update_status_icon(StatusIcon.DEFAULT)
            self.status_text.setText("To begin, select a folder")
            return

        if not self.state.game_files:
            self.update_status_icon(StatusIcon.DEFAULT)
            self.status_text.setText("No game files found in this folder")
            return

        self.status_text.setText("Checking for patches...")
        self.status_progress.setValue(0)
        self.status_progress.setMinimum(0)
        self.status_progress.setMaximum(len(self.state.game_files))
        self.status_progress.setHidden(False)

        # Use the first patched file as the baseline for options
        for file in self.state.game_files:
            if file.patched and not file.outdated:
                self.state.compress = file.compressed
                self.compress_option.setChecked(file.compressed)

                self.state.scale = file.scale
                try:
                    self.scale_option.setCurrentIndex(self.scale_option.findText(next(key for key, value in LABELS_UI_SCALE.items() if value == file.scale)))
                except StopIteration:
                    self.state.scale = 2.0
                    self.scale_option.setCurrentIndex(0)

                self.state.filter = int(file.upscale_filter)
                try:
                    self.filter_option.setCurrentIndex(self.filter_option.findText(next(key for key, value in LABELS_UI_FILTER.items() if value == file.upscale_filter)))
                except StopIteration:
                    self.state.filter = Image.Resampling.NEAREST
                    self.filter_option.setCurrentIndex(0)
                break

        # Keep patches are consistent with options
        for file in self.state.game_files:
            if not file.patched:
                continue

            if file.compressed != self.state.compress or file.scale != self.state.scale or file.upscale_filter != self.state.filter:
                file.outdated = True

        # Counts
        patch_count = sum(file.patched for file in self.state.game_files)
        backup_count = sum(file.backed_up for file in self.state.game_files)
        update_count = sum(file.outdated for file in self.state.game_files)
        total_count = len(self.state.game_files)

        any_patches = patch_count > 0
        any_backups = backup_count > 0
        missing_backups = patch_count > 0 and backup_count < patch_count
        any_outdated = update_count > 0
        incomplete = patch_count > 0 and patch_count < total_count

        # Update UI presentation
        if not any_patches or any_outdated or incomplete:
            self.btn_patch.setEnabled(True)

        if any_backups:
            self.btn_revert.setEnabled(True)

        self.status_progress.setValue(patch_count - update_count)

        if patch_count == total_count:
            self.update_status_icon(StatusIcon.GREEN)
            self.status_text.setText(f"{patch_count} file{"s" if patch_count > 0 else ""} patched")

        if update_count > 0:
            self.update_status_icon(StatusIcon.YELLOW)
            self.status_text.setText(f"{update_count} file{" needs" if update_count == 1 else "s need"} updating")

        if missing_backups:
            QMessageBox.warning(self, "Missing backup files", "Backup files are missing from your game folder. Patching or reverting may not be possible. In the worst case, you will need to re-install the game.")

        if incomplete:
            self.update_status_icon(StatusIcon.RED)
            self.status_text.setText(f"{patch_count}/{total_count} file{"s" if patch_count > 0 else ""} patched")

        if patch_count == 0:
            self.group_options.setEnabled(True)
            self.update_status_icon(StatusIcon.GREY)
            self.status_text.setText(f"{total_count} file{"s" if patch_count > 0 else ""} ready to patch")

    def start_patching(self):
        """
        Perform the patching process!
        """
        def has_permission(file: GameFile):
            """Return a boolean to indicate we have permission to modify the files."""
            # For existing files, are they read only?
            for path in [file.file_path, file.backup_path, file.meta_path]:
                if os.path.exists(path):
                    if not os.access(path, os.W_OK):
                        return False

            # Is the folder writable?
            testfile = os.path.join(os.path.dirname(file.file_path), "test.tmp")
            try:
                with open(testfile, "w", encoding="utf-8") as f:
                    f.write("\n")
                os.remove(testfile)
            except PermissionError:
                return False

            return True

        self.btn_patch.setEnabled(False)
        self.btn_revert.setEnabled(False)
        self.group_options.setEnabled(False)
        self.group_folders.setEnabled(False)

        self.status_text.setText("Checking permissions...")
        self.update_status_icon(StatusIcon.GREEN)
        self.status_progress.setValue(0)

        try:
            # 1. Check files/folders are writable
            for file in self.state.game_files:
                if not has_permission(file):
                    self.status_text.setText("Insufficient file permissions")
                    self.update_status_icon(StatusIcon.RED)
                    QMessageBox.critical(self, "Insufficient File Permissions", "In order to modify the game files, please run this program as an administrator, or change the folder permissions for the game directories.")

                    self.state.refresh_file_list()
                    self.refresh_patch_state()
                    return

                self.status_progress.setValue(self.status_progress.value() + 1)

            # 2. Patch the files
            total = len(self.state.game_files)
            self.update_status_icon(StatusIcon.YELLOW)
            self.status_progress.setValue(0)

            for index, file in enumerate(self.state.game_files):
                assert isinstance(file, GameFile)
                assert isinstance(index, int)

                self.status_text.setText(f"Patching... {total - index} file{"s" if total - index > 1 else ""} remaining")
                self.status_progress.setValue(index)
                QApplication.processEvents()

                # Skip files that are already up-to-date
                if file.patched and not file.outdated:
                    continue

                if file.backed_up:
                    # Always assume the original file is stored as the backup
                    file.restore()

                elif file.patched and not file.backed_up:
                    # Can't do anything with this file!
                    msgbox = QMessageBox()
                    msgbox.setIcon(QMessageBox.Icon.Warning)
                    msgbox.setWindowTitle("Missing backup file")
                    msgbox.setText(f"The following file is missing the backup file. It cannot be patched or restored. If you have issues with the game, you may need to reinstall the game.\n\n{file.file_path}")
                    msgbox.setInformativeText("Patching cannot proceed without all the files.")
                    msgbox.setStandardButtons(QMessageBox.StandardButton.Abort)
                    msgbox.exec()

                    self.state.refresh_file_list()
                    self.refresh_patch_state()
                    return

                # TODO: Check for abort, i.e. window close or button press

                # Always create a copy of the original before processing
                file.backup()

                # TODO: Callback for queue window
                @staticmethod
                def _progress(text: str, value: int, total: int):
                    """Update the progress window"""
                    print("fixme: _progress", text, value, total)

                if file.filename == "FontStyle.ini":
                    patches.process_fontstyle_ini(file)

                elif file.filename in ["ui.package", "CaSIEUI.data"]:
                    package = dbpf.DBPF(file.backup_path)
                    patches.process_package(file, package, _progress)

            self.update_status_icon(StatusIcon.GREEN)
            self.status_text.setText("Patch complete!")
            self.status_progress.setValue(total)
            QMessageBox.information(self, "Game Patched", "Patching completed successfully!")

        except PermissionError:
            QMessageBox.critical(self, "Permission Error", "The file might be in use by another program. Please close any processes using the file and try patching again.")

        except Exception as e: # pylint: disable=broad-except
            QMessageBox.critical(self, "Patching Failed", "An exception occurred. Please report this to the project's issue tracker.\n\n" + str(e))

        self.state.refresh_file_list()
        self.refresh_patch_state()

    def revert_patches(self):
        """
        Undo the patches by restoring the backup files.
        """
        question = QMessageBox.question(self, "Revert Patches?", "This will undo all modifications made by this program by restoring backup files. Continue?")
        if question != QMessageBox.StandardButton.Yes:
            return

        self.btn_patch.setEnabled(False)
        self.btn_revert.setEnabled(False)
        self.group_options.setEnabled(False)
        self.group_folders.setEnabled(False)

        self.update_status_icon(StatusIcon.YELLOW)
        self.status_text.setText("Restoring backups...")
        self.status_progress.setValue(0)

        try:
            for index, file in enumerate(self.state.game_files):
                self.status_progress.setValue(index)
                file.restore()

        except PermissionError:
            self.update_status_icon(StatusIcon.RED)
            self.status_text.setText("Insufficient file permissions")
            QMessageBox.critical(self, "Insufficient File Permissions", "In order to restore backup files, please run this program as an administrator, or change the folder permissions for the game directories.")

        except Exception as e: # pylint: disable=broad-except
            QMessageBox.critical(self, "Restore Failed", "An exception occurred. Please report this to the project's issue tracker.\n\n" + str(e))

        self.state.refresh_file_list()
        self.refresh_patch_state()


if __name__ == "__main__":
    # Enable CTRL+C to quit application
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    window = PatcherApplication()
    app.exec()
