"""
Module containing upscaling patches and fixes for The Sims 2 executable.
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

import math
import struct


class ExecutablePatch():
    """
    Base class to organise a patch for The Sims 2 executable.
    """
    NAME = "Unknown Patch"

    def verify(self, data: bytes) -> bool:
        """
        Verify that the bytes at the expected locations match the original bytes.
        If this fails, that particular game version is not supported/unknown.
        """
        raise NotImplementedError()

    def patch(self, data: bytes, scale: float) -> bytes:
        """
        Apply the patch to the executable data and return the new executable bytes.
        """
        raise NotImplementedError()


class PieMenuPatch(ExecutablePatch):
    """
    Scale the pie menu sector offsets and item positions in Sims2EP9.exe.
    """
    NAME = "Fix pie menu item positions"

    SECTOR_OFFSETS: list[tuple[int, int]] = [
        (0x001A6A1E, 0x11),  # edx=17
        (0x001A6A21, 0x0E),  # eax=14
        (0x001A6A24, 0x15),  # ecx=21
        (0x001A6A27, 0x10),  # esi=16
        (0x001A6A62, 0x30),  # imm32=48
        (0x001A6A6C, 0x1A),  # imm32=26
        (0x001A6A9A, 0x1A),  # imm32=26
    ]

    # Two fild instructions load kItemRadius for the item position formula.
    # Scale these calculations without changing the zombie head that shares the field.
    FILD_SITE_1 = 0x001A90A9
    FILD_SITE_2 = 0x001A90C6
    CAVE_ADDR = 0x00DD2C19
    IMAGE_BASE = 0x00400000
    FILD_ORIG_1 = bytes([0xDB, 0x83, 0xF0, 0x01, 0x00, 0x00, 0xD8, 0xC9])
    FILD_ORIG_2 = bytes([0xDB, 0x83, 0xF0, 0x01, 0x00, 0x00, 0x59, 0xD8, 0xC9])

    def verify(self, data: bytes) -> bool:
        for offset, original_value in self.SECTOR_OFFSETS:
            if offset >= len(data) or data[offset] != original_value:
                return False

        if self.FILD_SITE_1 + 8 > len(data) or self.FILD_SITE_2 + 9 > len(data):
            return False
        if data[self.FILD_SITE_1:self.FILD_SITE_1 + 8] != self.FILD_ORIG_1:
            return False
        if data[self.FILD_SITE_2:self.FILD_SITE_2 + 9] != self.FILD_ORIG_2:
            return False
        return True

    def patch(self, data: bytes, scale: float) -> bytes:
        """Scale pie menu offsets and route item-radius calculations through a code cave."""
        patched = bytearray(data)
        cave = self.CAVE_ADDR
        cave_va = self.IMAGE_BASE + cave

        struct.pack_into("<f", patched, cave, scale)

        c1 = cave + 4
        patched[c1:c1 + 6] = bytes([0xDB, 0x83, 0xF0, 0x01, 0x00, 0x00])
        patched[c1 + 6:c1 + 12] = bytes([0xD8, 0x0D]) + struct.pack("<I", cave_va)
        patched[c1 + 12:c1 + 14] = bytes([0xD8, 0xC9])
        patched[c1 + 14] = 0xC3

        c2 = cave + 19
        patched[c2:c2 + 6] = bytes([0xDB, 0x83, 0xF0, 0x01, 0x00, 0x00])
        patched[c2 + 6:c2 + 12] = bytes([0xD8, 0x0D]) + struct.pack("<I", cave_va)
        patched[c2 + 12:c2 + 14] = bytes([0xD8, 0xC9])
        patched[c2 + 14] = 0xC3

        site1 = self.FILD_SITE_1
        rel1 = (c1 + self.IMAGE_BASE) - (site1 + self.IMAGE_BASE + 5)
        patched[site1] = 0xE8
        struct.pack_into("<i", patched, site1 + 1, rel1)
        patched[site1 + 5:site1 + 8] = bytes([0x90, 0x90, 0x90])

        site2 = self.FILD_SITE_2
        rel2 = (c2 + self.IMAGE_BASE) - (site2 + self.IMAGE_BASE + 5)
        patched[site2] = 0xE8
        struct.pack_into("<i", patched, site2 + 1, rel2)
        patched[site2 + 5] = 0x59
        patched[site2 + 6:site2 + 9] = bytes([0x90, 0x90, 0x90])

        for offset, original_value in self.SECTOR_OFFSETS:
            patched[offset] = min(int(original_value * scale), 127)

        return bytes(patched)


class TooltipPaddingPatch(ExecutablePatch):
    """
    Scale the padding of general UI tooltips in Sims2EP9.exe.
    """
    NAME = "General tooltip padding"

    # Immediates of "push 6; push 8" passed with the tooltip background image.
    PADDING_LITERAL_OFFSETS: list[tuple[int, int]] = [
        (0x0024E1F8, 0x06),
        (0x0024E1FA, 0x08),
    ]

    def verify(self, data: bytes) -> bool:
        for offset, original_value in self.PADDING_LITERAL_OFFSETS:
            if offset >= len(data) or data[offset] != original_value:
                return False
        return True

    def patch(self, data: bytes, scale: float) -> bytes:
        """Scale tooltip padding literals."""
        patched = bytearray(data)
        for offset, original_value in self.PADDING_LITERAL_OFFSETS:
            patched[offset] = min(int(original_value * scale), 127)
        return bytes(patched)


def is_securom_protected(data: bytes) -> bool:
    """
    Return True if this EXE has active SecuROM protection (encrypted code sections).

    SecuROM V7 encrypts the first several MB of the .text section at rest,
    decrypting them into RAM at runtime.  Patching encrypted bytes on disk
    would corrupt the code after decryption, so the patch cannot be applied.

    Detection works by:
      1. Checking for a '.securom' PE section (necessary but not sufficient -
         No-CD patched builds keep the section header but leave code decrypted).
      2. Measuring Shannon entropy of the first 4 KB of .text.  Encrypted code
         scores ~7.95/8; normal x86 code scores ~5-7.
    """
    # Threshold above which .text entropy indicates SecuROM-encrypted code.
    # Normal x86 code scores ~5–7; SecuROM V7 packs it to ~7.95.
    entropy_threshold = 7.5
    section_name = ".securom"
    text_sample_size = 4096  # bytes to sample from the start of .text for entropy check

    # --- Parse PE header ---
    if len(data) < 0x40:
        return False
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    if pe_off + 24 + 28 + 4 > len(data):
        return False
    if data[pe_off:pe_off+4] != b"PE\x00\x00":
        return False

    n_sections = struct.unpack_from("<H", data, pe_off + 6)[0]
    opt_size   = struct.unpack_from("<H", data, pe_off + 20)[0]
    sec_table  = pe_off + 24 + opt_size

    has_securom_section = False
    text_raw_off = None

    for i in range(n_sections):
        base = sec_table + i * 40
        if base + 40 > len(data):
            break
        name    = data[base:base+8].rstrip(b"\x00").decode("ascii", errors="replace")
        raw_off = struct.unpack_from("<I", data, base + 20)[0]
        if name == section_name:
            has_securom_section = True
        if name == ".text":
            text_raw_off = raw_off

    if not has_securom_section or text_raw_off is None:
        return False

    # --- Entropy check ---
    sample = data[text_raw_off : text_raw_off + text_sample_size]
    if not sample:
        return False

    counts: dict[int, int] = {}
    for b in sample:
        counts[b] = counts.get(b, 0) + 1
    entropy = 0.0
    n = len(sample)
    for c in counts.values():
        p = c / n
        entropy -= p * math.log2(p)

    return entropy > entropy_threshold


def get_exe_patches() -> list[ExecutablePatch]:
    """
    Return a list of supported executable patches and their descriptions.
    """
    return [PieMenuPatch(), TooltipPaddingPatch()]


def apply_exe_patches(data: bytes, scale: float) -> bytes:
    """
    Apply supported UI patches to the executable and return the bytes.
    """
    for patch in get_exe_patches():
        if patch.verify(data):
            data = patch.patch(data, scale)
        else:
            print(f"Skipping {patch.NAME}: unexpected bytes (unsupported version or already patched)")

    return data
