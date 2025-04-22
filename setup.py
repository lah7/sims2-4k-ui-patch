"""
For creating an application build using cx_Freeze.
For maintainer use only.

It is not needed to run the patcher from the repository.
"""
from cx_Freeze import Executable, setup

build_exe_options = {
    "build_exe": "dist",
    "excludes": [
        "email",
        "gzip",
        "tcl",
        "tk",
        "tkinter",
        "unittest",
        "xml",
    ],
    "includes": [
        "sims2patcher",
        "submodules",
    ],
    "include_files": [
        ("assets/banner@2x.png", "assets/banner@2x.png"),
        ("assets/icon.ico", "assets/icon.ico"),
        ("assets/status_default@2x.png", "assets/status_default@2x.png"),
        ("assets/status_green@2x.png", "assets/status_green@2x.png"),
        ("assets/status_grey@2x.png", "assets/status_grey@2x.png"),
        ("assets/status_red@2x.png", "assets/status_red@2x.png"),
        ("assets/status_yellow@2x.png", "assets/status_yellow@2x.png"),
    ],
    "optimize": "2",
}

setup(
    name="sims2_4k_ui_patcher",
    version="0.3.0",
    description="4K UI Patcher for The Sims 2",
    options={"build_exe": build_exe_options},
    executables=[Executable("sims2_4k_ui_patcher.py", base="gui", icon="assets/icon")],
)
