"""
Abstraction for the user interface widgets for TKinter.
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
# Copyright (C) 2024 Luke Horwell <code@horwell.me>
#
import os
import sys
import tkinter as tk
import webbrowser
from typing import Callable, Optional


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

    def on_change(self, widget: tk.Entry|tk.Checkbutton|tk.OptionMenu, callback: Callable):
        """Bind a callback to a widget's change event."""
        if isinstance(widget, tk.Entry):
            widget.bind("<FocusOut>", lambda e: callback())
        elif isinstance(widget, tk.Checkbutton):
            widget.bind("<ButtonRelease>", lambda e: callback())
        elif isinstance(widget, tk.OptionMenu):
            widget.bind("<Configure>", lambda e: callback())

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
