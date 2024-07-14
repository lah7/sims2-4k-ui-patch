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

See patches.py for actual patching code.
"""
import glob
import os
import sys
import tkinter as tk
import webbrowser
from tkinter import filedialog, font, messagebox, ttk
from typing import Callable, List, Optional

import requests
from PIL import Image

import dbpf
import gamefile
import patches
from gamefile import GameFile

MAJOR = 0 # For new patches
MINOR = 1 # For fixed patches
PATCH = 0 # For trivial or UI fixes

VERSION = f"v{MAJOR}.{MINOR}.{PATCH}" # User-facing text
gamefile.FILE_PATCH_VERSION = float(f"{MAJOR}.{MINOR}") # Stored in file describing patch status

DEFAULT_PATHS = [
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


@staticmethod
def get_resource(relative_path):
    """
    Get a resource bundled with the application. When run as a Python script, use the current directory.
    """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path) # type: ignore # pylint: disable=protected-access
    return os.path.join(os.path.abspath("."), relative_path)


class Widgets():
    """
    UI abstraction for styled widgets for the application.
    """
    def __init__(self):
        # Prevent garbage collection from cleaning up
        self.refs = {}

        # Fonts
        self.font_name = "Calibri"
        self.font_size = 11

        # Colours
        self.colour_bg = "#394072"
        self.colour_bg_banner = "#5262c7"
        self.colour_bg_frame = "#282d50"

        self.colour_fg = "#FFFFFF"
        self.colour_fg_alt = "#7f90ff"

        self.button_bg = "#95a6de"
        self.button_fg = "#000d60"
        self.button_disabled_bg = "#5a6077"
        self.button_disabled_fg = "#373b50"

        self.progress_bg = "#7df251"

    def set_enabled(self, widget: tk.Button|tk.Label, enabled: bool):
        """Set the enabled/disabled state of a TK control."""
        if enabled:
            widget.configure(state=tk.NORMAL)
        else:
            widget.configure(state=tk.DISABLED)

        if isinstance(widget, tk.Button):
            if enabled:
                widget.configure(background=self.button_bg, foreground=self.button_fg)
            else:
                widget.configure(background=self.button_disabled_bg, foreground=self.button_disabled_fg)

    def make_frame(self, parent, row_no: int) -> tk.Frame:
        """Create a frame for separating controls"""
        frame = tk.Frame(parent, border=8, background=self.colour_bg_frame)
        frame.grid(row=row_no, padx=16, pady=8, sticky=tk.W + tk.N + tk.E)
        return frame

    def make_button(self, parent, label: str, command: Callable, width = 8) -> tk.Button:
        """Create a styled button"""
        button = tk.Button(parent, text=label, command=command, background=self.button_bg, foreground=self.button_fg, padx=16, border=1, highlightbackground=self.button_fg, highlightcolor=self.button_fg, disabledforeground=self.button_disabled_fg, width=width)

        def on_enter(e): # pylint: disable=unused-argument
            if button["state"] == tk.DISABLED:
                button.config(background=self.button_disabled_bg, foreground=self.button_disabled_fg)
            else:
                button.config(background=self.button_bg, foreground=self.button_fg)

        def on_leave(e): # pylint: disable=unused-argument
            if button["state"] == tk.DISABLED:
                button.config(background=self.button_disabled_bg, foreground=self.button_disabled_fg)
            else:
                button.config(background=self.button_bg, foreground=self.button_fg)

        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)

        return button

    def make_label(self, parent, text: str, font_size = 11, font_weight = "normal", colour: Optional[str] = None) -> tk.Label:
        """Make a label consisting of text"""
        return tk.Label(parent, text=text, background=self.colour_bg_frame, foreground=colour if colour else self.colour_fg, font=(self.font_name, font_size, font_weight), justify=tk.LEFT)

    def make_image(self, parent, image_path: str) -> tk.Label:
        """Make a label consisting of an image only"""
        image = tk.PhotoImage(file=get_resource(image_path))
        label = tk.Label(parent, border=0, image=image, background=self.colour_bg_frame)
        self.refs[label] = image
        return label

    def change_image(self, label: tk.Label, image_path: str):
        """Change an existing label to a new image"""
        image = tk.PhotoImage(file=get_resource(image_path))
        label.configure(image=image)
        self.refs[label] = image

    def make_link(self, parent, text: str, url: str) -> tk.Label:
        """Create a hyperlink label"""
        link = tk.Label(parent, text=text, cursor="hand2", background=self.colour_bg_frame, foreground=self.colour_fg_alt)
        link.bind("<Button-1>", lambda e: webbrowser.open(url))
        return link

    def make_input(self, parent) -> tk.Entry:
        """Create an input field"""
        return tk.Entry(parent, background=self.colour_bg_banner, foreground=self.colour_fg, font=(self.font_name, 11))

    def make_checkbox(self, parent, label: str, initial_state: bool) -> tk.Checkbutton:
        """Create a checkbox"""
        var = tk.BooleanVar(value=initial_state)
        checkbox = tk.Checkbutton(parent, text=label, variable=var, background=self.colour_bg_frame, foreground=self.colour_fg, activebackground=self.colour_bg_frame, activeforeground=self.colour_fg, selectcolor=self.colour_bg, font=(self.font_name, 11), border=0, highlightbackground=self.colour_bg_frame, highlightcolor=self.progress_bg, highlightthickness=0, anchor=tk.W, justify=tk.LEFT)
        self.refs[checkbox] = var
        return checkbox

    def is_checked(self, checkbox: tk.Checkbutton) -> bool:
        """Return the state of a checkbox"""
        return self.refs[checkbox].get()

    def set_checked(self, checkbox: tk.Checkbutton, state: bool):
        """Set the state of a checkbox"""
        self.refs[checkbox].set(state)

    def make_combo(self, parent, options: list[str]) -> tk.OptionMenu:
        """Create a combo box (drop down). Otherwise known as TK's option menu"""
        var = tk.StringVar()
        combo = tk.OptionMenu(parent, var, *options)
        combo.configure(background=self.colour_bg, foreground=self.colour_fg, activebackground=self.colour_bg, activeforeground=self.colour_fg, border=0, highlightbackground=self.colour_bg, highlightcolor=self.progress_bg, highlightthickness=0, anchor=tk.W, justify=tk.LEFT)
        var.set(options[0])
        self.refs[combo] = var
        return combo

    def get_combo_value(self, combo: tk.OptionMenu) -> str:
        """Get the current value of a combo box"""
        return self.refs[combo].get()

    def set_combo_value(self, combo: tk.OptionMenu, value: str):
        """Set the current value of a combo box"""
        self.refs[combo].set(value)


class PatcherApplication(tk.Tk):
    """
    A GUI application for patching The Sims 2 game files.
    """
    def __init__(self, *args, **kwargs):
        """Build the GUI using TKinter, a lightweight UI toolkit"""
        super().__init__(*args, **kwargs)

        # Variables
        self.game_install_dir = ""
        self.game_files = []
        self.update_available = False

        # Initialise UI & fonts
        self.widgets = Widgets()
        self.initial_options_set = False
        font.nametofont("TkDefaultFont").configure(family=self.widgets.font_name, size=10)

        # Create controls
        self.widgets = Widgets()
        self.configure(background=self.widgets.colour_bg)
        self.create_top_banner()
        self.create_folder_selector()
        self.create_options()
        self.create_patch_status()
        self.create_footer()
        self.columnconfigure(0, weight=1)

        # Set window properties
        self.title("UI Patcher for The Sims 2")
        self.eval('tk::PlaceWindow . center')

        if self.tk.call("tk", "windowingsystem") == 'win32':
            self.iconbitmap(get_resource("assets/icon.ico"))

        # A list of controls for selecting options
        self.options = [
            self.scale_label,
            self.scale_option,
            self.filter_label,
            self.filter_option,
            self.compress_option,
        ]

        # A list of controls that should be disabled when in progress
        self.controls = [
            self.input_dir,
            self.btn_browse,
            self.btn_patch,
        ] + self.options

        # Show time!
        for path in DEFAULT_PATHS:
            if os.path.exists(path):
                self.input_dir.insert(0, path)
                self.game_install_dir = path
                self.refresh_patch_state()
                break

        self.update()
        self._check_for_updates()

    def create_top_banner(self):
        """Create a banner with the project logo"""
        self.banner = tk.Frame(self)
        self.banner.grid(row=0, sticky=tk.N + tk.W + tk.E)
        self.banner.configure(background=self.widgets.colour_bg_banner)

        self.banner_image = self.widgets.make_image(self.banner, "assets/banner.png")
        self.banner_image.pack(side=tk.LEFT, padx=16, pady=8)
        self.banner_image.configure(background=self.widgets.colour_bg_banner)

    def create_folder_selector(self):
        """A frame for selecting the game files (typically "EA Games" folder)"""
        self.frame_dir = self.widgets.make_frame(self, 1)

        self.input_label = self.widgets.make_label(self.frame_dir, "Game installation folder:")
        self.input_label.grid(column=0, row=0, padx=8, pady=2, columnspan=2, sticky=tk.W)

        self.input_dir = self.widgets.make_input(self.frame_dir)
        self.input_dir.grid(column=0, row=1, padx=8, pady=2, sticky="ew")
        self.frame_dir.grid_columnconfigure(0, weight=1)

        self.btn_browse = self.widgets.make_button(self.frame_dir, "Browse", self._browse)
        self.btn_browse.grid(column=1, row=1, padx=0, pady=8)

    def create_options(self):
        """Create an expandable area to show options"""
        self.frame_options = self.widgets.make_frame(self, 2)
        self.grid_rowconfigure(3, weight=1)

        self.options_label = self.widgets.make_label(self.frame_options, "Options", colour=self.widgets.colour_fg_alt)
        self.options_label.grid(row=0, column=0, padx=8, pady=2, columnspan=2, sticky=tk.W)

        self.scale_label = self.widgets.make_label(self.frame_options, "Scale:")
        self.scale_option = self.widgets.make_combo(self.frame_options, list(LABELS_UI_SCALE.keys()))
        self.scale_label.grid(row=1, column=0, padx=8, pady=4, sticky=tk.W)
        self.scale_option.grid(row=1, column=1, padx=16, pady=4, sticky=tk.W)

        self.filter_label = self.widgets.make_label(self.frame_options, "Upscale filter:")
        self.filter_option = self.widgets.make_combo(self.frame_options, list(LABELS_UI_FILTER.keys()))
        self.filter_label.grid(row=2, column=0, padx=8, pady=4, sticky=tk.W)
        self.filter_option.grid(row=2, column=1, padx=16, pady=4, sticky=tk.W)

        self.compress_option = self.widgets.make_checkbox(self.frame_options, "Compress packages", True)
        self.compress_option.grid(row=4, column=0, padx=8, pady=4, columnspan=2, sticky=tk.W)

    def create_patch_status(self):
        """Create a view showing the overall patch status"""
        self.frame_status = self.widgets.make_frame(self, 3)

        self.patch_status_icon = self.widgets.make_image(self.frame_status, "assets/status_unpatched.png")
        self.patch_status_icon.grid(row=0, column=0, rowspan=2, padx=16, pady=0)

        self.patch_status_primary = self.widgets.make_label(self.frame_status, "Loading...", font_size=12, font_weight="bold")
        self.patch_status_primary.grid(row=0, column=1, padx=0, pady=0, sticky=tk.SW)

        self.patch_status_secondary = self.widgets.make_label(self.frame_status, "", colour=self.widgets.colour_fg_alt)
        self.patch_status_secondary.grid(row=1, column=1, padx=0, pady=0, sticky=tk.NW)

        self.btn_patch = self.widgets.make_button(self.frame_status, "Patch", self.start_patch)
        self.btn_patch.grid(row=0, column=2, padx=8, pady=8)
        self.btn_revert = self.widgets.make_button(self.frame_status, "Revert", self.start_revert)
        self.btn_revert.grid(row=1, column=2, padx=8, pady=8)

        self.widgets.set_enabled(self.btn_patch, False)
        self.widgets.set_enabled(self.btn_revert, False)
        self.frame_status.grid_columnconfigure(1, weight=1)

    def create_footer(self):
        """Create bottom footer showing the current version and project link"""
        self.frame_footer = tk.Frame(self, background=self.widgets.colour_bg_frame)
        self.frame_footer.grid(row=4, sticky=tk.S + tk.W + tk.E)
        self.grid_rowconfigure(4, weight=1)

        self.version = self.widgets.make_link(self.frame_footer, VERSION, f"{PROJECT_URL}/releases")
        self.version.grid(row=0, column=0, padx=8, pady=8, sticky=tk.W)

        self.link = self.widgets.make_link(self.frame_footer, PROJECT_URL, PROJECT_URL)
        self.link.configure(justify=tk.RIGHT)
        self.link.grid(row=0, column=1, padx=8, pady=8, sticky=tk.E)
        self.link.bind("<Button-1>", lambda e: self._open_homepage())

        self.frame_footer.grid_columnconfigure(0, weight=1)

    def _check_for_updates(self):
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
                    self.version.config(text=f"{VERSION} (New version available: v{latest_version})")
                    self.widgets.set_enabled(self.version, True)
                    self.update_available = True
            except (TypeError, ValueError):
                return

    def _open_homepage(self):
        if self.update_available:
            webbrowser.open(f"{PROJECT_URL}/releases/latest")
        else:
            webbrowser.open(PROJECT_URL)

    def _browse(self):
        """
        Open the file dialog to select the game's directory
        """
        initial_dir = "C:\\" if os.name == "nt" else ""
        for path in DEFAULT_PATHS:
            if os.path.exists(path):
                initial_dir = path
                break

        dirname = filedialog.askdirectory(initialdir=initial_dir, title="Select The Sims 2 installation folder", mustexist=True)

        if not dirname:
            return

        self.widgets.set_enabled(self.btn_patch, False)
        self.widgets.set_enabled(self.btn_revert, False)
        self.input_dir.delete(0, tk.END)
        dirname = dirname.replace("/", os.sep)
        self.input_dir.insert(0, dirname)
        self.game_install_dir = dirname
        self.refresh_patch_state()

    def set_status_primary(self, text: str, state: int = -1):
        """
        Update the main status of the patcher.

        "state" is optional and determines the icon:
            0   Unpatched
            1   Error
            2   Patched
            3   Patching/Busy
            4   Partial/Outdated
        """
        self.patch_status_primary.config(text=text)

        if state >= 0:
            icon = "status_unpatched"
            match state:
                case 0:
                    icon = "status_unpatched"
                case 1:
                    icon = "status_partial"
                case 2:
                    icon = "status_patched"
                case 3:
                    icon = "status_patching"
                case 4:
                    icon = "status_outdated"
            self.widgets.change_image(self.patch_status_icon, f"assets/{icon}.png")
        self.update()

    def set_status_secondary(self, text: str):
        """
        Update the secondary status of the patcher.
        See set_status_primary() for parameters.
        """
        self.patch_status_secondary.config(text=text)
        self.update()

    def _get_file_list(self) -> list:
        """
        Return a list of files that will be patched by this program.
        """
        files = []
        for filename in ["ui.package", "FontStyle.ini", "CaSIEUI.data"]:
            files += glob.glob(self.game_install_dir + f"/**/{filename}", recursive=True)
        return sorted(list(set(files)))

    def refresh_patch_state(self):
        """
        Check the game files and update the status.
        """
        self.game_files: List[GameFile] = []
        self.widgets.set_enabled(self.btn_patch, False)
        self.widgets.set_enabled(self.btn_revert, False)

        self.set_status_primary("Checking files...", 3)
        self.set_status_secondary("")
        patch_list = self._get_file_list()

        if not patch_list:
            self.set_status_primary("Not Selected", 0)
            self.set_status_secondary("Select game installation folder")
            messagebox.showerror("Wrong game installation folder", "Game files for The Sims 2 (or its expansion packs) was not found in this folder.")
            return

        self.set_status_primary("Checking for patches...", 3)

        for path in patch_list:
            file = GameFile(path)
            self.game_files.append(file)

            if not file.patched or file.patch_outdated:
                self.widgets.set_enabled(self.btn_patch, True)

            if file.backed_up:
                self.widgets.set_enabled(self.btn_revert, True)

            # Restore selected options by looking at first patched file
            if file.patched and not self.initial_options_set:
                self.initial_options_set = True

                self.widgets.set_checked(self.compress_option, file.compressed)

                try:
                    value = next(key for key, value in LABELS_UI_SCALE.items() if value == file.scale)
                    self.widgets.set_combo_value(self.scale_option, value)
                except StopIteration:
                    pass

                try:
                    value = next(key for key, value in LABELS_UI_FILTER.items() if value == file.upscale_filter)
                    self.widgets.set_combo_value(self.filter_option, value)
                except StopIteration:
                    pass

        count_patched = len([file for file in self.game_files if file.patched])
        count_outdated = len([file for file in self.game_files if file.patch_outdated])
        count_total = len(self.game_files)

        all_patched = count_patched == count_total
        all_backed_up = all(file.backed_up for file in self.game_files)
        any_backups = any(file.backed_up for file in self.game_files)
        any_outdated = any(file.patch_outdated for file in self.game_files)
        partially_patched = not all_patched and any(file.patched for file in self.game_files)

        for widget in self.options:
            # Disable options when files are patched, to avoid inconsistencies
            self.widgets.set_enabled(widget, count_patched == 0)

        if all_patched and all_backed_up:
            self.set_status_primary("Patched", 2)
            self.set_status_secondary(f"{count_patched} files patched")

        elif all_patched and not all_backed_up:
            self.set_status_primary("Patched", 1)
            self.set_status_secondary("Missing backup files!")

        if all_patched and any_outdated:
            self.set_status_primary("Ready to patch", 4)
            self.set_status_secondary(f"{count_outdated} files need updating")

        if partially_patched:
            self.set_status_primary("Incomplete", 1)
            self.set_status_secondary(f"{count_patched}/{count_total} files patched ({round((count_patched/count_total) * 100)}%)")

        if not all_patched and not partially_patched:
            self.set_status_primary("Ready to patch", 0)
            self.set_status_secondary(f"{count_total} files")
            if any_backups:
                self.set_status_secondary("Found backup files")

    def has_permission(self, file: GameFile):
        """
        Return a boolean to indicate we have permission to modify the files.
        """
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

    def start_patch(self):
        """
        Perform the patching process!
        """
        patches.COMPRESS_PACKAGE = self.widgets.is_checked(self.compress_option)
        patches.UI_MULTIPLIER = LABELS_UI_SCALE[self.widgets.get_combo_value(self.scale_option)]
        patches.UPSCALE_FILTER = LABELS_UI_FILTER[self.widgets.get_combo_value(self.filter_option)]

        self.set_status_primary("Checking permissions...", 3)
        self.set_status_secondary("")
        try:
            # 1. Check files/folders are writable
            for file in self.game_files:
                if not self.has_permission(file):
                    self.set_status_secondary(file.file_path)
                    messagebox.showerror("Insufficient File Permissions", "In order to modify the game files, please run this program as an administrator, or change the folder permissions for the game directories.")
                    self.refresh_patch_state()
                    return

            # Show detailed progress in a popup window
            window = ProgressWindow(self)
            for button in self.controls:
                self.widgets.set_enabled(button, False)
            self.set_status_primary("Patching...", 3)

            # 2. Process each patchable game file
            overall_current = 0
            overall_total = len(self.game_files)

            for file in self.game_files:
                overall_current += 1
                window.set_current_progress("Opening package...", 0)
                window.set_current_progress_max(1)
                window.set_total_progress(os.path.relpath(file.file_path, self.game_install_dir), overall_current / overall_total * 100)

                if file.patched and not file.patch_outdated:
                    # Skip files that are already up-to-date
                    continue

                if file.backed_up:
                    # Always assume the original file is stored as the backup
                    file.restore()
                elif file.patched and not file.backed_up:
                    # Can't do anything with this file!
                    continue

                # Always create a copy of the original before processing
                file.backup()

                if file.filename == "FontStyle.ini":
                    window.set_current_progress("Upscaling FontStyle.ini...", 0)
                    patches.upscale_fontstyle_ini(file)

                elif file.filename in ["ui.package", "CaSIEUI.data"]:
                    package = dbpf.DBPF(file.backup_path)
                    window.set_current_progress_max(len(package.get_entries()))
                    patches.upscale_package_contents(file, package, window.set_current_progress)

            window.in_progress = False
            window.destroy()
            self.set_status_primary("Done!", 2)
            messagebox.showinfo("Success!", "Patching completed successfully!")
            window.stop_patch()

        except PermissionError:
            messagebox.showerror("Permission Error", "The file might be in use by another program. Please close any processes using the file and try patching again.")
            window.in_progress = False
            window.destroy()
            window.stop_patch()

        except Exception as e: # pylint: disable=broad-except
            messagebox.showerror("Patch Failed", str(e))
            window.in_progress = False
            window.destroy()
            window.stop_patch()

    def start_revert(self):
        """Undo the patches by restoring the backup files."""
        confirmation = messagebox.askyesno("Revert", "This will undo modifications made by this patch program by restoring all backup files. Continue?")
        if not confirmation:
            return

        self.set_status_primary("Restoring backups...", 3)
        self.set_status_secondary("")
        try:
            for file in self.game_files:
                file.restore()
        except PermissionError:
            self.set_status_primary("Restore Error", 1)
            messagebox.showerror("Insufficient File Permissions", "In order to restore backup files, please run this program as an administrator, or change the folder permissions for the game directories.")
        except Exception as e: # pylint: disable=broad-except
            self.set_status_primary("Restore Error", 1)
            messagebox.showerror("Revert Failed", str(e))

        self.refresh_patch_state()


class ProgressWindow(tk.Toplevel):
    """
    Show the patch progress in a pop up dialog.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.parent: tk.Tk = parent
        self.in_progress = True

        self.title("Patching in Progress")

        self.transient(parent)
        self.grab_set()

        # Current Progress
        self.current_progress_group = ttk.LabelFrame(self, text="Current Progress")
        self.current_progress_group.pack(padx=8, pady=8, fill=tk.BOTH)

        self.current_progress_text = tk.Label(self.current_progress_group, text="Preparing...")
        self.current_progress_text.pack(padx=8, pady=8, side=tk.TOP, fill=tk.BOTH, expand=True)

        self.current_progress_bar = ttk.Progressbar(self.current_progress_group, orient=tk.HORIZONTAL, length=100, mode="determinate")
        self.current_progress_bar.pack(padx=8, pady=8, side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        # Overall Progress
        self.total_progress_group = ttk.LabelFrame(self, text="Overall Progress")
        self.total_progress_group.pack(padx=8, pady=8, fill=tk.BOTH)

        self.total_progress_text = tk.Label(self.total_progress_group, text="The Sims 2")
        self.total_progress_text.pack(padx=8, pady=8, side=tk.TOP, fill=tk.BOTH, expand=True)

        self.total_progress_bar = ttk.Progressbar(self.total_progress_group, orient=tk.HORIZONTAL, length=100, mode="determinate")
        self.total_progress_bar.pack(padx=8, pady=8, side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        self.cancel_btn = ttk.Button(self, text="Cancel", command=self.stop_patch)
        self.cancel_btn.pack(padx=8, pady=8, side=tk.TOP)

        # Position dialog in the center of the screen
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = 550
        window_height = 265
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")

        self.protocol("WM_DELETE_WINDOW", self.stop_patch)

    def _reload_app(self):
        self.destroy()
        self.parent.destroy()
        os.execl(sys.executable, sys.executable, *sys.argv)

    def stop_patch(self):
        """
        Abort or patching finished. Restart the application.
        If patching was aborted while in progress, confirm with the user.

        The UI may be briefly unresponsive because we're not technically running in a separate thread.
        Files are safe, even if interrupting the middle of a file patch, as they are not overwritten until
        the processing of that file is completed.
        """
        if not self.in_progress:
            return self._reload_app()

        confirmed = messagebox.askyesno("Cancel Patching", "Abort patching?\n\nThe game will be left partially patched. You can resume later, or click \"Revert\" on the next screen to restore the original files.")
        if confirmed:
            return self._reload_app()

    def set_current_progress(self, text: str, value: int|float, total: Optional[int] = None):
        """Update the progress bar and text for the currently processed item"""
        self.current_progress_text.configure(text=text)
        self.current_progress_bar.configure(value=value)
        if total:
            return self.set_current_progress_max(total)
        self.update()

    def set_current_progress_max(self, value: int):
        """Update the maximum value of the progress bar for the currently processed item"""
        self.current_progress_bar.configure(maximum=value)
        self.update()

    def set_total_progress(self, text: str, value: int|float):
        """Update the progress bar and text for the overall progress"""
        self.total_progress_text.configure(text=text)
        self.total_progress_bar.configure(value=value)
        self.update()


if __name__ == "__main__":
    app = PatcherApplication()
    app.mainloop()
