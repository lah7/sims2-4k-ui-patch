"""
Module to serialize UI Scripts used by The Sims 2 (and other Maxis games)
with their modified XML format into a more usable format for editing and
processing.
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
# Copyright (C) 2025 Luke Horwell <code@horwell.me>
#
import re

ALWAYS_QUOTED = ["caption", "tiptext", "wparam", "initvalue"]
NEWLINE_PLACEHOLDER = "$NEWLINE$"


class UIScriptRoot:
    """
    Serialised representation of a UI script file.
    Children in this context are the top-level elements in the UI script file.
    """
    def __init__(self):
        self.comments: list[str] = []
        self.children: list["UIScriptElement"] = []


class UIScriptElement:
    """
    Serialised representation of an element in a UI script file.
    """
    def __init__(self):
        self.attributes: dict[str, str] = {}
        self.children: list["UIScriptElement"] = []

    def __getitem__(self, key):
        return self.attributes[key]


def _read_element(line) -> UIScriptElement:
    """
    Process a line from a UI script file.
    """
    element = UIScriptElement()

    # Extract unquoted attributes
    for attrib, value in re.findall(r"(\w+)=(\S+)", line):
        element.attributes[attrib] = value

    # Extract quoted attributes
    for attrib, value in re.findall(r"(\w+)=(\".*?\")", line):
        element.attributes[attrib] = value.replace("\"", "")

    # Extract attributes with no values
    for attrib in re.findall(r' (\w+)(?=[^"]*(?:"[^"]*"[^"]*)*$) ', line):
        element.attributes[attrib] = ""

    return element


def serialize_uiscript(data: str) -> UIScriptRoot:
    """
    Parse a UI script file into a serialised representation.
    """
    root = UIScriptRoot()

    # Iterate over each line in the file
    lines = data.split("\n")
    hierarchy: list[UIScriptRoot|UIScriptElement] = [root]
    last_element: UIScriptRoot|UIScriptElement = root
    while lines:
        line = lines.pop(0).strip()

        # Ignore empty lines
        if not line:
            continue

        # Each line with an element is expected to be closed on the same line. If not, it might be a multi-line caption.
        if line.startswith("<") and not line.endswith(">"):
            _first_line = line
            new_line = [line]
            try:
                while not line.endswith(">"):
                    line = lines.pop(0).strip()
                    new_line.append(line)
            except IndexError as e:
                raise ValueError(f"Expected closing tag, but reached end of file instead: {_first_line}") from e
            line = NEWLINE_PLACEHOLDER.join(new_line)

        # Capture comments or random strings
        if line.startswith("#") or not line.startswith("<"):
            root.comments.append(line)
            continue

        if line == "<CHILDREN>":
            hierarchy.append(last_element)
            continue

        if line == "</CHILDREN>":
            hierarchy.pop()
            continue

        if line.startswith("<LEGACY"):
            element = _read_element(line)
            last_element = element
            hierarchy[-1].children.append(element)

    if len(hierarchy) != 1:
        raise ValueError("Expected to be at the root level. Perhaps a </CHILDREN> tag is missing?")

    return root


def deserialize_uiscript(root: UIScriptRoot) -> str:
    """
    Convert a serialised representation of a UI script file back into
    the XML-like Maxis format.
    """
    def _process_element(element: UIScriptElement, ident: int = 0):
        identation = "   " * ident
        elements = []
        for key, value in element.attributes.items():
            if not value and not ALWAYS_QUOTED:
                elements.append(key)
            elif " " in value or key in ALWAYS_QUOTED:
                elements.append(f"{key}=\"{value.replace(NEWLINE_PLACEHOLDER, "\r\n")}\"")
            else:
                elements.append(f"{key}={value}")

        lines.append(f"{identation}<LEGACY {' '.join(elements)} >")
        if element.children:
            lines.append(f"{identation}<CHILDREN>")
            for child in element.children:
                _process_element(child, ident + 1)
            lines.append(f"{identation}</CHILDREN>")

    lines = []

    for comment in root.comments:
        lines.append(comment)

    for child in root.children:
        _process_element(child)

    # Game originally used CR+LF (Windows) line endings
    return "\r\n".join(lines) + "\r\n"
