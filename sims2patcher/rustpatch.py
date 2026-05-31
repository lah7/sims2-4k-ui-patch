"""
Optional Rust acceleration bridge.

The compiled module is intentionally optional while the Rust implementation
reaches parity with the Python engine. The GUI calls this first; if the module
is absent or reports an unsupported package feature, the existing Python path
continues to handle the file.
"""
import os
from typing import Callable

from PIL import Image

from . import gamefile

DISABLE_ENV = "SIMS2PATCHER_DISABLE_RUST"
REQUIRE_ENV = "SIMS2PATCHER_REQUIRE_RUST"
ENTRY_THREADS_ENV = "SIMS2PATCHER_RUST_ENTRY_THREADS"


class RustPatchUnavailable(RuntimeError):
    """Raised when the Rust extension cannot be imported."""


class RustPatchUnsupported(RuntimeError):
    """Raised when the Rust extension cannot patch a file yet."""


def _load_extension():
    if os.environ.get(DISABLE_ENV):
        if os.environ.get(REQUIRE_ENV):
            raise RuntimeError("Rust patcher disabled by environment")
        raise RustPatchUnavailable("Rust patcher disabled by environment")

    try:
        import sims2patcher_rust  # type: ignore  # pylint: disable=import-outside-toplevel
    except ImportError as e:
        if os.environ.get(REQUIRE_ENV):
            raise
        raise RustPatchUnavailable(str(e)) from e

    return sims2patcher_rust


def available() -> bool:
    """Return whether the Rust extension can be imported."""
    try:
        _load_extension()
        return True
    except RustPatchUnavailable:
        return False


def patch_game_file(file: gamefile.GameFile, state, ui_update_progress: Callable[[int, int], None]):
    """
    Patch a prepared GameFile using the Rust extension.

    The caller remains responsible for backup/restore flow. This function only
    transforms file.original_file_path into file.target_file_path and writes the
    metadata marker on success.
    """
    extension = _load_extension()

    def _progress(current: int, total: int, _message: str = ""):
        ui_update_progress(current, max(total, 1))

    options = {
        "scale": float(state.scale),
        "storage": "fast" if state.leave_uncompressed else "compact",
        "image_filter": _filter_name(state.filter),
        "loading_screen_fps": int(state.loading_screen_fps),
        "threads": _entry_threads(),
        "qfs_level": 20,
        "verify_compression": False,
    }

    try:
        if file.filename == "FontStyle.ini":
            extension.patch_fontstyle(file.original_file_path, file.file_path, float(state.scale))  # pylint: disable=no-member
        elif file.filename in ["ui.package", "CaSIEUI.data", "objects.package"]:
            extension.patch_dbpf_package(  # pylint: disable=no-member
                file.original_file_path,
                file.target_file_path,
                file.filename,
                options,
                _progress,
            )
        else:
            raise RustPatchUnsupported(f"Unknown patch operation: {file.file_path}")
    except Exception as e:  # pylint: disable=broad-except
        message = str(e)
        if os.environ.get(REQUIRE_ENV):
            raise
        if "unsupported by Rust patcher" in message or "not yet implemented in Rust" in message:
            raise RustPatchUnsupported(message) from e
        raise

    file.patched = True
    file.write_meta_file()


def _filter_name(filter_value: int) -> str:
    if filter_value == Image.Resampling.HAMMING:
        return "hamming"
    if filter_value == Image.Resampling.BILINEAR:
        return "linear"
    if filter_value == Image.Resampling.BICUBIC:
        return "cubic"
    if filter_value == Image.Resampling.LANCZOS:
        return "lanczos"
    return "nearest"


def _entry_threads() -> int:
    """
    Keep GUI patching concurrency package-oriented.

    The GUI already runs several files at once using the Patch Threads setting.
    Letting every package also create a large Rayon pool can oversubscribe the
    machine badly during full-install patching.
    """
    if ENTRY_THREADS_ENV in os.environ:
        try:
            return max(int(os.environ[ENTRY_THREADS_ENV]), 1)
        except ValueError:
            return 1
    return 1
