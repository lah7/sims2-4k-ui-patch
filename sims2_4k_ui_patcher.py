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
# Copyright (C) 2023-2025 Luke Horwell <code@horwell.me>
#
"""
Graphical patcher interface to apply and revert patches for rescaling
the The Sims 2 user interface for HiDPI resolutions.

The patcher keeps a backup of the original file to allow patches to
be reverted, to "uninstall" the modifcations, or for future patcher updates.
"""
import multiprocessing
import os
import signal
import sys
import time
import webbrowser
from concurrent.futures import Future, ProcessPoolExecutor
from enum import Enum
from multiprocessing.managers import DictProxy, SyncManager
from typing import Callable, List

import requests
from PIL import Image
from PyQt6.QtCore import Qt, QThread, QTimer
from PyQt6.QtGui import QCloseEvent, QIcon, QMouseEvent, QPixmap
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                             QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                             QHeaderView, QLabel, QLineEdit, QMainWindow,
                             QMessageBox, QProgressBar, QPushButton,
                             QSizePolicy, QSlider, QStatusBar, QStyle,
                             QTabWidget, QToolButton, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout, QWidget)

from sims2patcher import gamefile, patches
from sims2patcher.gamefile import GameFile

VERSION = "v0.3.0-dev"
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
    "EA GAMES",
]

PROJECT_URL = "https://github.com/lah7/sims2-4k-ui-patch"

# Labels for options
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
def get_resource(relative_path: str) -> str:
    """
    Get a resource bundled with the application or from the same directory as the program.
    """
    if getattr(sys, "frozen", False):
        data_dir = os.path.dirname(sys.executable)
    else:
        data_dir = os.path.dirname(__file__)
    return os.path.join(data_dir, relative_path)


class State:
    """
    Store details about the current patcher inputs.
    """
    def __init__(self):
        # Folder containing The Sims 2 installations
        self.game_install_dir = ""

        # List of game files that will be patched
        self.game_paths: List[str] = []
        self.game_files: List[GameFile] = []

        # This patcher program has a new update
        self.update_available = False

        # Session
        self.threads = os.cpu_count() or 1

        # Options
        self.scale: float = 2.0
        self.filter: int = Image.Resampling.NEAREST
        self.leave_uncompressed: bool = False

    def refresh_file_list(self):
        """
        Return a list of files that will be patched by this program.
        """
        self.game_paths = gamefile.get_patchable_paths(self.game_install_dir)
        self.game_files = gamefile.get_patchable_files(self.game_paths)

    def set_game_install_path(self, path: str):
        """
        Set the game installation folder and gather a list of patchable game files
        """
        self.game_install_dir = path
        self.refresh_file_list()

    def auto_detect_game_path(self):
        """
        Automatically detect the game installation folder
        """
        for path in DEFAULT_DIRS:
            if os.path.exists(path):
                self.set_game_install_path(path)
                return


class PatchThread(QThread):
    """
    A thread responsible for managing the subprocesses that perform the patching on a single file.
    """
    def __init__(self, state: State, worker_function: Callable, process_manager: SyncManager, progress_dict: DictProxy):
        super().__init__()
        self.state = state
        self.worker_function = worker_function
        self.process_manager = process_manager
        self.progress_dict = progress_dict

        self.futures: List[Future] = []
        self.terminate_event = multiprocessing.Event()

    def count_total_processes(self):
        """Return the number of running processes"""
        return len(self.futures)

    def count_running_processes(self):
        """Return the number of running processes"""
        return sum(not f.done() for f in self.futures)

    def count_done_processes(self):
        """Return the number of completed processes"""
        return sum(f.done() for f in self.futures)

    def count_pending_processes(self):
        """Return the number of remaining processes"""
        return max((sum(not f.done() for f in self.futures) - self.state.threads), 0)

    def run(self):
        """Start the thread responsible for patching each file in its own process without blocking the UI"""
        self.reset()
        with ProcessPoolExecutor(max_workers=self.state.threads) as executor:
            for file in self.state.game_files:
                self.futures.append(executor.submit(self.worker_function, file.file_path, self.state, self.progress_dict))

            while not all(f.done() for f in self.futures):
                if self.terminate_event.is_set():
                    for f in self.futures:
                        f.cancel()
                    break
                time.sleep(0.5)

    def reset(self):
        """Clear the thread, ready for new work"""
        self.futures = []
        self.progress_dict.clear()
        self.terminate_event.clear()

    def quit(self):
        """
        Gracefully stop by finishing current operations and cancel everything else.
        This sets an event to tell the loop to stop processing any more.
        """
        self.terminate_event.set()
        super().quit()


class PatcherApplication(QMainWindow):
    """
    A GUI application for patching The Sims 2 game files. Powered by PyQt6.
    """
    def __init__(self):
        """Set up the application layout"""
        super().__init__()

        self.state = State()

        # Parallel processing for later
        self.patch_ui_timer = QTimer()
        self.patch_ui_timer.timeout.connect(self._update_patch_progress)
        self.process_manager = multiprocessing.Manager()
        self.progress_dict = self.process_manager.dict()
        self.patch_thread = PatchThread(self.state, self._patch_file, self.process_manager, self.progress_dict)
        self.queue_window = QueueWindow()
        self.stop_requested = False

        # Base Layout
        self.base_layout = QVBoxLayout()
        self.base_widget = QWidget()
        self.base_widget.setLayout(self.base_layout)
        self.setCentralWidget(self.base_widget)

        # Build UI controls
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

    def closeEvent(self, event: QCloseEvent): # type: ignore # pylint: disable=invalid-name
        """
        Handle the window close event.
        """
        if not self.patch_thread.isRunning():
            event.accept()
            return

        if self.abort_patching():
            event.accept()

        event.ignore()

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
            self.state.leave_uncompressed = self.compress_option.isChecked()
            self.refresh_patch_state()

        def _threads_changed():
            """Callback when the user adjusts the threads slider."""
            self.state.threads = self.threads_slider.value()

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setTabShape(QTabWidget.TabShape.Rounded)
        self.tabs.setEnabled(False)
        self.base_layout.addWidget(self.tabs)

        # Options Tab
        self.tab_options = QWidget()
        self.tab_options_layout = QFormLayout()
        self.tab_options.setLayout(self.tab_options_layout)

        self.scale_option = QComboBox()
        self.scale_option.addItems(list(LABELS_UI_SCALE.keys()))
        self.scale_option.setToolTip("The desired UI scaling in-game")
        self.scale_option.currentIndexChanged.connect(_scale_changed)
        self.tab_options_layout.addRow("Scale:", self.scale_option)

        self.threads_slider = QSlider(Qt.Orientation.Horizontal)
        self.threads_slider.setMinimum(1)
        self.threads_slider.setMaximum(os.cpu_count() or 8)
        self.threads_slider.setValue(self.state.threads)
        self.threads_slider.setTickInterval(1)
        self.threads_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.threads_slider.setToolTip("How many CPU cores/threads to use for parallel processing.\nHigher values require more memory and I/O throughput!")
        self.threads_slider.valueChanged.connect(_threads_changed)
        self.tab_options_layout.addRow("Patch Threads:", self.threads_slider)

        self.tabs.addTab(self.tab_options, "Options")

        # Advanced Tab
        self.tab_advanced = QWidget()
        self.tab_advanced_layout = QFormLayout()
        self.tab_advanced.setLayout(self.tab_advanced_layout)

        self.filter_option = QComboBox()
        self.filter_option.addItems(list(LABELS_UI_FILTER.keys()))
        self.filter_option.setToolTip("Recommended to leave as default.\nFor experimenting with image resampling filters")
        self.filter_option.currentIndexChanged.connect(_filter_changed)
        self.tab_advanced_layout.addRow("Upscale Filter:", self.filter_option)

        self.compress_option = QCheckBox("Uncompressed files")
        self.compress_option.setChecked(False)
        self.compress_option.setToolTip("Don't compress modified files. Faster, but uses significantly more disk space.")
        self.compress_option.stateChanged.connect(_compress_changed)
        self.tab_advanced_layout.addRow("Testing:", self.compress_option)

        self.tabs.addTab(self.tab_advanced, "Advanced")

        self.base_layout.addWidget(self.tabs)

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

        self.btn_details = QPushButton()
        self.btn_details.setText("Details")
        self.btn_details.setToolTip("Show current progress and file queue")
        self.btn_details.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)) # type: ignore
        self.btn_details.clicked.connect(self.queue_window.show)
        self.btn_details.clicked.connect(self.queue_window.raise_)
        self.layout_buttons.addWidget(self.btn_details)

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

        self.btn_cancel = QPushButton()
        self.btn_cancel.setText("Cancel")
        self.btn_cancel.setToolTip("Abort the patching progress")
        self.btn_cancel.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton)) # type: ignore
        self.btn_cancel.clicked.connect(self.abort_patching)
        self.layout_buttons.addWidget(self.btn_cancel)

        # Initial
        self.btn_details.setHidden(True)
        self.btn_cancel.setHidden(True)

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
        self.tabs.setEnabled(False)
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

            if file.scale != self.state.scale or file.upscale_filter != self.state.filter:
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
            self.status_text.setText(f"{patch_count} file{'s' if patch_count > 0 else ''} patched")

        if update_count > 0:
            self.update_status_icon(StatusIcon.YELLOW)
            self.status_text.setText(f"{update_count} file{' needs' if update_count == 1 else 's need'} updating")

        if missing_backups:
            QMessageBox.warning(self, "Missing backup files", "Backup files are missing from your game folder. Patching or reverting may not be possible. In the worst case, you will need to re-install the game.")

        if incomplete:
            self.update_status_icon(StatusIcon.RED)
            self.status_text.setText(f"{patch_count}/{total_count} file{'s' if patch_count != 0 else ''} patched")

        if patch_count == 0:
            self.tabs.setEnabled(True)
            self.update_status_icon(StatusIcon.GREY)
            self.status_text.setText(f"{total_count} file{'s' if patch_count != 1 else ''} ready to patch")

    def _check_file_permissions(self):
        """
        Check the files and folders are writable.
        Return a boolean to indicate overall status.
        """
        def _has_permission(file: GameFile) -> bool:
            """Return a boolean to indicate whether a file can be modified"""
            # For existing files, make sure they're not read-only.
            if os.path.exists(file.file_path) and not os.access(file.file_path, os.W_OK):
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

        self.status_text.setText("Checking permissions...")
        self.update_status_icon(StatusIcon.GREEN)
        self.status_progress.setValue(0)

        success = []
        for file in self.state.game_files:
            success.append(_has_permission(file))

        if not all(success):
            self.status_text.setText("Insufficient file permissions")
            self.update_status_icon(StatusIcon.RED)
            QMessageBox.critical(self, "Insufficient File Permissions", "In order to modify the game files, please run this program as an administrator, or change the folder permissions for the game directories.")

        return all(success)

    @staticmethod
    def _patch_file(file_path: str, state: State, progress_dict: DictProxy):
        """
        A separate process responsible for patching an individual file.
        UI update are saved in the dictionary which a timer on the main thread will read.
        """
        def _update_progress(value: int = 0, total: int = 0):
            """Update the progress (and optional %) for this file"""
            percent = round((value / total) * 100)
            progress_dict[file_path] = f"{percent}% (File {value} of {total})"

        def _clear_progress():
            """Remove the file from the progress dictionary"""
            progress_dict.pop(file_path)

        def _fail(reason: str):
            """Use the progress dictionary to pass an error message"""
            progress_dict[file_path] = f"Error: {reason}"

        # Sync state to module variables
        patches.UI_MULTIPLIER = state.scale
        patches.LEAVE_UNCOMPRESSED = state.leave_uncompressed
        patches.UPSCALE_FILTER = state.filter

        # Begin!
        _update_progress(0, 1)
        file = gamefile.get_game_file(file_path)
        file.scale = state.scale
        file.upscale_filter = state.filter
        file.uncompressed = state.leave_uncompressed

        try:
            # Skip file if already up-to-date
            if file.patched and not file.outdated:
                _clear_progress()
                return

            # Always assume the original file is stored as the backup
            if file.backed_up:
                file.restore()

            elif file.patched and not file.backed_up:
                # Can't do anything with this file!
                _fail(f"Missing backup file:\n{file.file_path}.\n\nThis file cannot be patched or restored. You may need to reinstall the game.")
                return

            # Always create a copy of the original before processing
            file.backup()

            # Patch the file!
            patches.patch_file(file, _update_progress)

        except PermissionError:
            _fail(f"Insufficient file permissions:\n{file.file_path}\n\nThe file might be in use by another program. Please close any processes using the file and try again.")
            return

        except Exception as e: # pylint: disable=broad-except
            _fail(f"An exception occurred while processing file:\n{file.file_path}\n\n{str(e)}\n\nPlease report this to the project's issue tracker.")
            return

        # File done!
        _clear_progress()

    def _update_patch_progress(self):
        """
        Update the progress of the patching process.
        Periodically ran to update the queue window and UI.
        """
        self.queue_window.table.clear()

        for file_path, value in self.patch_thread.progress_dict.items():
            item = QTreeWidgetItem([file_path, value])
            self.queue_window.table.addTopLevelItem(item)

            # Show an errors
            assert isinstance(value, str)
            if value.startswith("Error:"):
                QMessageBox(QMessageBox.Icon.Critical, "Error Patching File", value.replace("Error:", "").strip(), QMessageBox.StandardButton.Ok, self).exec()
                self.patch_thread.progress_dict.pop(file_path)

        pending = self.patch_thread.count_pending_processes()
        done = self.patch_thread.count_done_processes()
        total = self.patch_thread.count_total_processes()

        self.queue_window.remaining.setText(f"{pending} file{'s' if pending != 1 else ''} queued")
        self.queue_window.update_window_title(done, total)

        if not self.stop_requested:
            self.status_progress.setValue(done)
            self.status_text.setText(f"{done} of {total} files patched")

        if done == total:
            self.finished_patching()

    def start_patching(self):
        """
        Perform the patching process!
        """
        if not self._check_file_permissions():
            return

        # Swap buttons
        self.btn_patch.setHidden(True)
        self.btn_revert.setHidden(True)
        self.btn_details.setHidden(False)
        self.btn_cancel.setHidden(False)

        self.btn_patch.setEnabled(False)
        self.btn_revert.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.tabs.setEnabled(False)
        self.group_folders.setEnabled(False)

        total = len(self.state.game_files)
        self.update_status_icon(StatusIcon.YELLOW)
        self.status_text.setText(f"Preparing to patch {total} files...")
        self.status_progress.setValue(0)
        self.status_progress.setMaximum(total)

        self.patch_thread.start()
        self.patch_ui_timer.start(100)

    def abort_patching(self) -> bool:
        """
        Stop the patching process. This will gracefully stop via the main thread.
        Return a boolean to confirm it has been aborted.
        """
        # Already stopped?
        if not self.patch_thread.isRunning():
            return True

        # Only show prompt when user uses Cancel button or window close
        if not self.stop_requested and not QMessageBox.question(self, "Cancel Patching?", "Your game may be left partially patched and unplayable. You can resume patching later, or revert the patches to undo all changes. Cancel patching?", defaultButton=QMessageBox.StandardButton.Yes) == QMessageBox.StandardButton.Yes:
            return False

        self.stop_requested = True
        self.patch_thread.quit()

        self.update_status_icon(StatusIcon.RED)
        self.btn_cancel.setEnabled(False)
        self.status_text.setText("Waiting for current tasks to stop...")
        self.status_progress.setMaximum(self.patch_thread.count_total_processes())

        while self.patch_thread.isRunning():
            self.status_progress.setValue(self.patch_thread.count_done_processes())
            QApplication.processEvents()
            time.sleep(0.1)

        self.finished_patching()
        return True

    def finished_patching(self):
        """
        The patching process has completed or was cancelled.
        """
        self.stop_requested = False
        self.queue_window.hide()
        self.patch_ui_timer.stop()

        # Main window was closed?
        if not self.isVisible():
            return

        # Swap buttons
        self.btn_patch.setHidden(False)
        self.btn_revert.setHidden(False)
        self.btn_details.setHidden(True)
        self.btn_cancel.setHidden(True)

        self.state.refresh_file_list()
        self.refresh_patch_state()

        if not self.stop_requested and not self.btn_patch.isEnabled():
            QMessageBox.information(self, "UI Patching Complete", "Patching completed successfully!", QMessageBox.StandardButton.Ok)

    def revert_patches(self):
        """
        Undo the patches by restoring the backup files.
        """
        question = QMessageBox.question(self, "Revert Patches?", "This will undo all modifications made by this program by restoring backup files. Continue?")
        if question != QMessageBox.StandardButton.Yes:
            return

        self.btn_patch.setEnabled(False)
        self.btn_revert.setEnabled(False)
        self.tabs.setEnabled(False)
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


class QueueWindow(QDialog):
    """
    Shows the current progress and queue of files to patch.
    """
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.table = QTreeWidget()
        self.table.setHeaderLabels(["File", "Status"])
        self.table.setColumnWidth(0, 650)
        self.table.setColumnWidth(1, 100)

        header: QHeaderView = self.table.header() # type: ignore
        header.setSectionsClickable(False)
        header.setSectionsMovable(False)
        layout.addWidget(self.table)

        self.bottom = QWidget()
        self.bottom_layout = QHBoxLayout()
        self.bottom_layout.setContentsMargins(0, 0, 0, 0)
        self.bottom.setLayout(self.bottom_layout)
        layout.addWidget(self.bottom)

        self.remaining = QLabel()
        self.remaining.setText("0 files queued")
        self.bottom_layout.addWidget(self.remaining)

        self.bottom_layout.addStretch()

        self.close_button = QPushButton()
        self.close_button.setText("Close")
        self.close_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton)) # type: ignore
        self.close_button.clicked.connect(self.close)
        self.bottom_layout.addWidget(self.close_button)

        self.update_window_title(0, 1)
        self.setWindowIcon(QIcon(get_resource("assets/icon.ico")))
        self.resize(900, 500)

    def update_window_title(self, completed: int, total: int):
        """Update the window title to show the current progress"""
        self.setWindowTitle(f"Patching in Progress ({int((completed/total) * 100)}%)")


if __name__ == "__main__":
    multiprocessing.freeze_support()  # Required for Windows

    if os.path.exists("version.txt") and os.path.exists("lib") and os.path.exists("share"):
        # Read version for dist builds
        VERSION = open("version.txt", "r", encoding="utf-8").read().strip()

    app = QApplication(sys.argv)
    window = PatcherApplication()

    # While the Qt event loop runs, periodically check for SIGINT (CTRL+C)
    signal_timer = QTimer()
    signal_timer.timeout.connect(lambda: None)
    signal_timer.start(250)

    def _handle_sigint(*args): # pylint: disable=unused-argument
        """
        Handle the SIGINT signal (CTRL+C).
        When there's no subprocesses running, quitting is easy.
        However, when the patching thread is running, it's more difficult.
        The best solution is to ask the user to close using the GUI so Qt and event loops are handled correctly.
        """
        if not window.patch_thread.isRunning():
            return QApplication.quit()
        print(" SIGINT received. but not supported. Close application using the GUI instead.")

    signal.signal(signal.SIGINT, _handle_sigint)

    app.exec()
