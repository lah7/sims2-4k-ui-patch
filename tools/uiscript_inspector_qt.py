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
# Copyright (C) 2022, 2024-2025 Luke Horwell <code@horwell.me>
#
"""
Qt interface for browsing and recreating user interfaces from
The Sims 2 by parsing .uiScript files and associated graphics.

Requires QWebEngineView.
"""
import base64
import io
import os
import re
import signal
import sys

import PIL.Image

# Our modules are in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # pylint: disable=wrong-import-position

from PyQt6.QtCore import QObject, Qt, QTimer, QUrl, pyqtSlot
from PyQt6.QtGui import QIcon
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (QAbstractScrollArea, QApplication, QDockWidget,
                             QFileDialog, QHBoxLayout, QMainWindow, QSplitter,
                             QStatusBar, QTreeWidget, QTreeWidgetItem, QWidget)

from sims2patcher import dbpf

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "inspector_data"))


def uiscript_to_html(orig: str) -> str:
    """
    Convert .uiscript files to plain HTML.
    UI Scripts are XML-like formats with unquoted attribute values.

    Example:
        <LEGACY clsid=GZWinGen iid=IGZWinGen area=(10,10,605,432) >

    Becomes:
        <div class="GZWinGen" id="IGZWinGen" x="10" y="10" width="605" height="432"></div>
    """
    output = ""
    for line in orig.split("\n"):
        if line.startswith("#"):
            continue
        output += line + "\n"

    # Replace <LEGACY> and <CHILDREN> tags with <div>
    output = output.replace("<LEGACY", "<div class=\"LEGACY\"")
    output = output.replace("<CHILDREN", "<div class=\"CHILDREN\"")
    output = output.replace("</LEGACY>", "</div>")
    output = output.replace("</CHILDREN>", "</div>")

    # <LEGACY> tags didn't have closing tags, add one if not present
    output = output.replace(" >", "></div>")

    return output


class State:
    """A collection of entries from a .package file"""
    def __init__(self):
        self.package = dbpf.DBPF()
        self.package_path = ""
        self.ui_files: list[dbpf.Entry] = []
        self.graphics: list[dbpf.Entry] = []


class Bridge(QObject):
    """Bridge between Python and JavaScript"""
    def __init__(self, state: State):
        super().__init__()
        self.state = state

    @pyqtSlot(str, bool, int, int, result=str) # type: ignore
    def get_image(self, image_attr: str, is_edge_image: bool, height: int, width: int) -> str:
        """
        Return a base64 encoded PNG image for a TGA graphic extracted from the package.

        Additional attributes will be read to determine whether post-processing
        is required (such as to render a dialog background).

        Expected:
            - image_attr: "{group_id, instance_id}"
            - wparam_attr: "0x0300d422,uint32,1"
            - is_edge_image: Whether edgeimage="yes" or "blttype="edge" is set
            - height and width of element (for post processing purposes)
        """
        try:
            _group_id, _instance_id = image_attr[1:-1].split(",")
            group_id = int(_group_id, 16)
            instance_id = int(_instance_id, 16)
        except ValueError:
            print(f"Invalid image group/instance ID: {image_attr}")
            return ""

        try:
            entry = self.state.package.get_entry(dbpf.TYPE_IMAGE, group_id, instance_id)
        except ValueError:
            print(f"Image not found: Group ID {group_id}, Instance ID {instance_id}")
            return ""

        # Convert to PNG as browser doesn't support TGA
        io_out = io.BytesIO()
        try:
            io_in = io.BytesIO(entry.data_safe)
            tga = PIL.Image.open(io_in)
            tga = tga.convert("RGBA") # Remove transparency
            tga.save(io_out, format="PNG")
        except dbpf.errors.QFSError:
            print(f"Image failed to extract: Group ID {group_id}, Instance ID {instance_id}")
            return ""

        # Post processing required?
        if is_edge_image:
            io_out = self._render_dialog_image(io_out, height, width)

        return base64.b64encode(io_out.getvalue()).decode("utf-8")

    def _render_dialog_image(self, data_io: io.BytesIO, height: int, width: int) -> io.BytesIO:
        """
        Generate a new image replicating how the game renders a dialog background image.
        """
        original = PIL.Image.open(data_io).convert("RGBA")

        def _copy_pixels(src_x: int, src_y: int, width: int, height: int, dst_x: int, dst_y: int):
            """Copy pixels from one image to another"""
            src = original.crop((src_x, src_y, src_x + width, src_y + height))
            canvas.paste(src, (dst_x, dst_y, dst_x + width, dst_y + height))

        def _tile_pixels(src_x: int, src_y: int, width: int, height: int, dst_x: int, dst_y: int, dst_x2: int, dst_y2: int):
            """Repeat an image from the source image to the destination (within boundaries)"""
            src = original.crop((src_x, src_y, src_x + width, src_y + height))
            for x in range(dst_x, dst_x2, width):
                for y in range(dst_y, dst_y2, height):
                    canvas.paste(src, (x, y, x + width, y + height))

        # Example image: Group 0x499db772, Instance 0xa9500615 (90x186 pixels)
        canvas = PIL.Image.new("RGBA", (width, height), (0, 0, 0, 0))

        # Handle the corners and edges of the dialog
        right_edge_starts = width - 30
        bottom_edge_starts = height - 62

        _tile_pixels(30, 30, 30, 30, 30, 30, right_edge_starts, bottom_edge_starts) # Center / Inner

        _tile_pixels(0, 30, 30, 30, 0, 30, 30, bottom_edge_starts)                                         # Left edge
        _tile_pixels(60, 30, 30, 30, right_edge_starts, 30, right_edge_starts + 30, bottom_edge_starts)    # Right edge
        _tile_pixels(30, 0, 30, 30, 30, 0, right_edge_starts, 30)                                          # Top edge
        _tile_pixels(30, 124, 30, 62, 30, bottom_edge_starts, right_edge_starts, bottom_edge_starts + 124) # Bottom edge

        _copy_pixels(0, 0, 30, 30, 0, 0)                                     # Top-left corner
        _copy_pixels(60, 0, 30, 30, right_edge_starts, 0)                    # Top-right corner
        _copy_pixels(0, 124, 30, 62, 0, bottom_edge_starts)                  # Bottom-left corner
        _copy_pixels(60, 124, 30, 62, right_edge_starts, bottom_edge_starts) # Bottom-right corner

        output = io.BytesIO()
        canvas.save(output, format="PNG")
        return output


class MainInspectorWindow(QMainWindow):
    """Main interface for inspecting .uiScript files"""
    def __init__(self):
        super().__init__()

        # Variables
        self.state = State()
        self.items: list[QTreeWidgetItem] = []

        # Layout
        self.base_widget = QWidget()
        self.base_layout = QHBoxLayout()
        self.base_widget.setLayout(self.base_layout)
        self.setCentralWidget(self.base_widget)

        self.file_tree = QTreeWidget(self.base_widget)
        self.file_tree.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        self.file_tree.setHeaderLabels(["Group ID", "Instance ID", "Caption Hint"])
        self.file_tree.setColumnWidth(0, 100)
        self.file_tree.setColumnWidth(1, 100)
        self.file_tree.setColumnWidth(2, 150)
        self.file_tree.setSortingEnabled(True)
        self.file_tree.currentItemChanged.connect(self.open_ui_file)

        self.list_dock = QDockWidget("UI Files", self)
        self.list_dock.setMinimumWidth(400)
        self.list_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable | QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.list_dock.setWidget(self.file_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.list_dock)

        self.status_bar: QStatusBar = self.statusBar() # type: ignore
        self.status_bar.showMessage("Loading...")

        # UI Preview
        self._webview = QWidget()
        self._webview_layout = QHBoxLayout()
        self._webview_layout.setContentsMargins(0, 0, 0, 0)
        self._webview.setLayout(self._webview_layout)
        self.webview = QWebEngineView(self._webview)
        self._webview_layout.addWidget(self.webview)
        self.webview.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.webview.setHtml("<style>body { background: #003062; }</style>")

        # Inspector View
        self._inspector = QWidget()
        self._inspector_layout = QHBoxLayout()
        self._inspector_layout.setContentsMargins(0, 0, 0, 0)
        self._inspector.setLayout(self._inspector_layout)
        self.inspector = QWebEngineView(self._inspector)
        self._inspector_layout.addWidget(self.inspector)
        self.inspector.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        self.inspector.page().setInspectedPage(self.webview.page()) # type: ignore

        self.web_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.web_splitter.addWidget(self._webview)
        self.web_splitter.addWidget(self._inspector)
        self.web_splitter.setSizes([1000, 500])
        self.base_layout.addWidget(self.web_splitter)

        # The bridge allows the web view to communicate with Python
        self.channel = QWebChannel()
        self.webview.page().setWebChannel(self.channel) # type: ignore

        # Register bridge object
        self.bridge = Bridge(self.state)
        self.channel.registerObject("python", self.bridge)

        # Window properties
        self.resize(1424, 768)
        self.setWindowTitle("UI Inspector for The Sims 2 by lah7")
        self.setWindowIcon(QIcon(os.path.abspath(os.path.join(DATA_DIR, "..", "..", "assets", "status_default@2x.png"))))
        self.show()

        # Auto load package when passed as a command line argument
        if len(sys.argv) > 1:
            self.state.package_path = sys.argv[1]
            if os.path.exists(self.state.package_path):
                self.load_files()
        else:
            self.browse()

    def browse(self):
        """Show the file dialog to select a package file"""
        browser = QFileDialog(self)
        browser.setFileMode(QFileDialog.FileMode.ExistingFile)
        browser.setNameFilter("The Sims 2 Package Files (*.package CaSIEUI.data)")
        browser.setViewMode(QFileDialog.ViewMode.Detail)

        if browser.exec() == QFileDialog.DialogCode.Accepted:
            self.state.package_path = browser.selectedFiles()[0]
            self.load_files()
        else:
            sys.exit(130)

    def load_files(self):
        """Load the .uiScript files from the selected package"""
        self.status_bar.showMessage(f"Reading: {self.state.package_path}")
        self.setCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()

        self.state.package = dbpf.DBPF(self.state.package_path)
        self.state.ui_files = [entry for entry in self.state.package.entries if entry.type_id == dbpf.TYPE_UI_DATA]
        self.state.graphics = [entry for entry in self.state.package.entries if entry.type_id == dbpf.TYPE_IMAGE]
        total = len(self.state.ui_files)

        for entry in self.state.ui_files:
            item = QTreeWidgetItem(self.file_tree, [str(hex(entry.group_id)), str(hex(entry.instance_id)), ""])
            item.setData(0, Qt.ItemDataRole.UserRole, entry)
            self.items.append(item)

        self.status_bar.showMessage(f"Listed {total} UI files from {self.state.package_path}", 3000)
        self.setCursor(Qt.CursorShape.ArrowCursor)

        timer = QTimer(self)
        timer.singleShot(1, self.preload_files)

    def open_ui_file(self, item: QTreeWidgetItem):
        """Open the selected .uiScript file in the web view"""
        entry: dbpf.Entry = item.data(0, Qt.ItemDataRole.UserRole)
        try:
            html = uiscript_to_html(entry.data.decode("utf-8"))
        except UnicodeDecodeError:
            html = "Unable to decode. It may be binary data."
        with open(os.path.join(DATA_DIR, "inspector.html"), "r", encoding="utf-8") as f:
            html = f.read().replace("PLACEHOLDER", html)
        self.webview.setHtml(html, baseUrl=QUrl.fromLocalFile(f"{DATA_DIR}/"))

    def preload_files(self):
        """Continue loading files in the background to identify captions and binary files"""
        for item in self.items:
            entry: dbpf.Entry = item.data(0, Qt.ItemDataRole.UserRole)
            if entry.decompressed_size > 1024 * 1024: # Likely binary (over 1 MiB)
                item.setDisabled(True)
                item.setText(2, "Binary data")
                continue

            html = entry.data.decode("utf-8")
            matches = re.findall(r'\bcaption="([^"]+)"', html)

            # Use longest caption as the title
            if matches:
                # Exclude captions used for technical key/value pairs
                matches = [match for match in matches if not match.find("=") != -1 and not match.isupper()]

                item.setText(2, max(matches, key=len))
                item.setToolTip(2, "\n".join(matches))


if __name__ == "__main__":
    # CTRL+C to exit
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    window = MainInspectorWindow()
    app.exec()
