#!/usr/bin/python3
"""
Graphical patcher interface to apply and revert patches for rescaling
the The Sims 2 user interface for HiDPI (4K) resolutions.

The patcher keeps a backup of the original file to allow patches to
be reverted, to "uninstall" the mod, or for future patcher updates.

See patches.py for actual patching code.
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
import glob
import os
import sys
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

import requests

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
    "C:\\Program Files\\Origin Games",
    "C:\\Program Files (x86)\\Origin Games",
    "EA GAMES",
]

PROJECT_URL = "https://github.com/lah7/sims2-4k-ui-patch"


class PatcherApplication(tk.Tk):
    """
    A GUI application for patching The Sims 2 game files.
    """
    update_available = False

    # A list of games/files to work with
    ea_games_dir = ""
    game_dir_names = []
    game_files = []

    def __init__(self, *args, **kwargs):
        """Build the GUI using TKinter"""
        super().__init__(*args, **kwargs)

        # Create top banner
        self.banner = tk.Frame(self)
        self.banner.pack(fill=tk.X)
        banner_bg = "#394072"
        self.banner.configure(background=banner_bg)

        def get_resource(relative_path):
            """Get a resource bundled with the application. When ran outside of PyInstaller, use the current directory"""
            if hasattr(sys, "_MEIPASS"):
                return os.path.join(sys._MEIPASS, relative_path) # type: ignore # pylint: disable=protected-access
            return os.path.join(os.path.abspath("."), relative_path)

        self.banner_photo = tk.PhotoImage(file=get_resource("assets/banner.png"))
        self.banner_image = ttk.Label(self.banner, image=self.banner_photo, border=0, background=banner_bg)
        self.banner_image.pack(side=tk.LEFT, padx=8, pady=8)

        # Create group box to select game files
        self.groupbox1 = ttk.LabelFrame(self, text="EA Games folder")
        self.groupbox1.pack(padx=8, pady=8, expand=True)
        self.input_dir = ttk.Entry(self.groupbox1, width=50)
        self.input_dir.grid(column=0, row=0, padx=8, pady=8)
        self.btn_browse = ttk.Button(self.groupbox1, text="Browse", command=self._browse)
        self.btn_browse.grid(column=1, row=0, padx=8, pady=8)

        # Create group box and treeview
        self.groupbox2 = ttk.LabelFrame(self, text="Patch Status")
        self.groupbox2.pack(padx=8, pady=8, fill=tk.BOTH, expand=True)
        self.treeview = ttk.Treeview(self.groupbox2, columns=("game", "status"), show="headings")
        self.treeview.heading("game", text="Game/Expansion")
        self.treeview.heading("status", text="Status")
        self.treeview.pack(fill=tk.BOTH, side=tk.LEFT, expand=True)
        vsb = ttk.Scrollbar(self.groupbox2, orient="vertical", command=self.treeview.yview)
        self.treeview.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Create bottom footer
        self.footer = tk.Frame(self, borderwidth=1, relief=tk.SUNKEN)
        self.footer.pack(fill=tk.BOTH, expand=True)

        self.info_frame = tk.Frame(self.footer, border=8)
        self.info_frame.pack(side=tk.LEFT, padx=0, pady=0)

        self.version = ttk.Label(self.info_frame, text=VERSION, justify=tk.LEFT)
        self.version.pack(fill=tk.X)
        self.set_enabled(self.version, False)

        self.link = tk.Label(self.info_frame, text=PROJECT_URL, fg="blue", cursor="hand2")
        self.link.pack()
        self.link.bind("<Button-1>", lambda e: self._open_homepage())

        self.btn_patch = ttk.Button(self.footer, text="Patch", command=self.start_patch)
        self.btn_patch.pack(side=tk.RIGHT, padx=4, pady=4)
        self.btn_revert = ttk.Button(self.footer, text="Revert", command=self.start_revert)
        self.btn_revert.pack(side=tk.RIGHT, padx=4, pady=4)
        self.set_enabled(self.btn_patch, False)
        self.set_enabled(self.btn_revert, False)

        # Create a status bar
        self.status_bar = ttk.Frame(self, borderwidth=1, relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Create a label inside the status bar
        self.status_bar_text = ttk.Label(self.status_bar, text="Ready")
        self.status_bar_text.pack(side=tk.LEFT, padx=2, pady=2)

        # Set window properties
        self.title("4K UI Patcher for The Sims 2")
        self.eval('tk::PlaceWindow . center')

        if self.tk.call("tk", "windowingsystem") == 'win32':
            self.iconbitmap(get_resource("assets/icon.ico"))

        # Try the default paths
        for path in DEFAULT_PATHS:
            if os.path.exists(path):
                self.input_dir.insert(0, path)
                self.ea_games_dir = path
                self.refresh_game_status()
                break

        self.controls = [self.btn_browse, self.btn_patch, self.btn_revert, self.input_dir]
        self.update()
        self._check_for_updates()

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
                    self.set_enabled(self.version, True)
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
        dirname = filedialog.askdirectory(initialdir=initial_dir, title="Select EA GAMES directory", mustexist=True)

        if not dirname:
            return

        self.set_enabled(self.btn_patch, False)
        self.set_enabled(self.btn_revert, False)
        self.input_dir.delete(0, tk.END)
        dirname = dirname.replace("/", os.sep)
        self.input_dir.insert(0, dirname)
        self.ea_games_dir = dirname
        self.refresh_game_status()

    def set_enabled(self, button: ttk.Button|ttk.Label, enabled: bool):
        """Set the enabled/disabled state of a TK control."""
        if enabled:
            button.configure(state=tk.NORMAL)
        else:
            button.configure(state=tk.DISABLED)

    def set_status_bar_text(self, text: str):
        """Update the text on the status bar"""
        self.status_bar_text.configure(text=text)
        self.update()

    def get_all_patchable_files(self) -> list:
        """
        Return a list of files that can be patched by this program.
        """
        files = []
        for filename in ["ui.package", "FontStyle.ini", "CaSIEUI.data"]:
            files += glob.glob(os.path.join(self.ea_games_dir, "*Sims 2*", "TSData") + f"/**/{filename}", recursive=True)
        return sorted(files)

    def refresh_game_status(self):
        """
        Check the game installations and update the status.
        """
        self.game_dir_names: List[str] = []
        self.game_files: List[GameFile] = []
        self.tree_view_items = []

        self.set_status_bar_text("Listing files...")
        patch_list = self.get_all_patchable_files()

        self.set_status_bar_text("Checking for patches...")
        self.treeview.delete(*self.treeview.get_children())
        self.set_enabled(self.btn_patch, False)
        self.set_enabled(self.btn_revert, False)

        # Make sure we have a valid game directory
        if not patch_list:
            messagebox.showerror("Wrong folder selected", "No installation of The Sims 2 (or its expansion packs) was found in this folder.")
            self.set_status_bar_text("Missing EA Games Folder")
            return

        # Gather list of game files
        for path in patch_list:
            file = GameFile(path)
            self.game_files.append(file)

            if not file.patched or file.patch_outdated:
                self.set_enabled(self.btn_patch, True)

            if file.backed_up:
                self.set_enabled(self.btn_revert, True)

        # Generate an overall summary for each game
        games_status = {}
        for file in self.game_files:
            if file.game_name not in games_status:
                games_status[file.game_name] = []
            games_status[file.game_name].append(file)

        for game_name, files in games_status.items():
            all_patched = all(file.patched for file in files)
            all_backed_up = all(file.backed_up for file in files)
            any_backups = any(file.backed_up for file in files)
            any_outdated = any(file.patch_outdated for file in files)
            partially_patched = not all_patched and any(file.patched for file in files)

            status = "Unknown"
            if all_patched and all_backed_up:
                status = "Patched"
            elif all_patched and not all_backed_up:
                status = "Patched, missing backups"

            if all_patched and any_outdated:
                status = "Update available"

            if partially_patched:
                status = "Incomplete"

            if not all_patched and not partially_patched:
                status = "Unpatched"
                if any_backups:
                    status = "Unsure (found backups)"

            # Append to treeview
            self.tree_view_items.append(self.treeview.insert("", "end", values=(game_name, status)))

        self.set_status_bar_text("Ready")

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
        try:
            # 1. Check files/folders are writable
            for file in self.game_files:
                if not self.has_permission(file):
                    messagebox.showerror("Insufficient File Permissions", "In order to patch the game files, please run this program as an administrator, or change the folder permissions for the game directories.")
                    return

            # Show detailed progress in a popup window
            window = ProgressWindow(self)
            for button in self.controls:
                self.set_enabled(button, False)
            self.set_status_bar_text("Patching...")

            # 2. Process each patchable game file
            overall_current = 0
            overall_total = len(self.game_files)

            for file in self.game_files:
                overall_current += 1
                window.set_current_progress(f"Opening: {file.relative_path}", 0)
                window.set_current_progress_max(1)
                window.set_total_progress(file.game_name, overall_current / overall_total * 100)

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

                if file.name == "FontStyle.ini":
                    window.set_current_progress("Upscaling FontStyle.ini...", 0)
                    patches.upscale_fontstyle_ini(file)

                elif file.name in ["ui.package", "CaSIEUI.data"]:
                    package = dbpf.DBPF(file.backup_path)
                    window.set_current_progress_max(len(package.get_entries()))
                    patches.upscale_package_contents(file, package, window.set_current_progress)

            window.in_progress = False
            window.destroy()
            self.set_status_bar_text("Done!")
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

        self.set_status_bar_text("Restoring backup files...")
        try:
            for file in self.game_files:
                file.restore()
        except PermissionError:
            messagebox.showerror("Insufficient File Permissions", "In order to revert the game files, please run this program as an administrator, or change the folder permissions for the game directories.")
        except Exception as e: # pylint: disable=broad-except
            messagebox.showerror("Revert Failed", str(e))

        self.refresh_game_status()


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

