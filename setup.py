"""
For creating an application build using cx_Freeze.
For maintainer use only.

It is not needed to run the patcher from the repository.
"""
from cx_Freeze import Executable, setup

build_exe_options = {
    "build_exe": "dist",
    "excludes": ["unittest"],
    "include_files": [
        ("assets/banner.png", "assets/banner.png"),
        ("assets/icon.ico", "assets/icon.ico"),
        ("assets/status_outdated.png", "assets/status_outdated.png"),
        ("assets/status_partial.png", "assets/status_partial.png"),
        ("assets/status_patched.png", "assets/status_patched.png"),
        ("assets/status_patching.png", "assets/status_patching.png"),
        ("assets/status_unpatched.png", "assets/status_unpatched.png"),
    ],
    "optimize": "2",
}

setup(
    name="sims2_4k_ui_patcher",
    version="0.1.0",
    description="4K UI Patcher for The Sims 2",
    options={"build_exe": build_exe_options},
    executables=[Executable("sims2_4k_ui_patcher.py", base="gui", icon="assets/icon")],
)
