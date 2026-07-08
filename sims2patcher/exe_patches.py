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

# Sims2EP9.exe: # The game hardcodes pixel offsets for pie menu item
# positions. These sector offsets and the item radius calculation
# need scaling to match the UI density.
import struct

_PIE_MENU_SECTOR_OFFSETS: list[tuple[int, int]] = [
    (0x001A6A1E, 0x11),  # edx=17
    (0x001A6A21, 0x0E),  # eax=14
    (0x001A6A24, 0x15),  # ecx=21
    (0x001A6A27, 0x10),  # esi=16
    (0x001A6A62, 0x30),  # imm32=48
    (0x001A6A6C, 0x1A),  # imm32=26
    (0x001A6A9A, 0x1A),  # imm32=26
]

# Two fild instructions load kItemRadius for the item position formula
# (radius * sin/cos). A code cave multiplies by UI_MULTIPLIER before
# the sin/cos multiplication, scaling item positions without affecting
# the zombie head (3D Sim portrait) which shares the same field.
_PIE_MENU_FILD_SITE_1 = 0x001A90A9  # fild+fmul for sin path (8 bytes)
_PIE_MENU_FILD_SITE_2 = 0x001A90C6  # fild+pop+fmul for cos path (9 bytes)
_PIE_MENU_CAVE_ADDR = 0x00DD2C19    # unused padding at end of .text section
_PIE_MENU_IMAGE_BASE = 0x00400000

# Expected original bytes at the fild sites for verification
_PIE_MENU_FILD_ORIG_1 = bytes([0xDB, 0x83, 0xF0, 0x01, 0x00, 0x00, 0xD8, 0xC9])
_PIE_MENU_FILD_ORIG_2 = bytes([0xDB, 0x83, 0xF0, 0x01, 0x00, 0x00, 0x59, 0xD8, 0xC9])


def verify_exe_bytes(data: bytes) -> bool:
    """Check that the EXE contains expected original bytes at all patch offsets."""
    for offset, orig_val in _PIE_MENU_SECTOR_OFFSETS:
        if offset >= len(data) or data[offset] != orig_val:
            return False

    site1 = _PIE_MENU_FILD_SITE_1
    site2 = _PIE_MENU_FILD_SITE_2
    if site1 + 8 > len(data) or site2 + 9 > len(data):
        return False
    if data[site1:site1+8] != _PIE_MENU_FILD_ORIG_1:
        return False
    if data[site2:site2+9] != _PIE_MENU_FILD_ORIG_2:
        return False

    return True


def build_pie_menu_patch(data: bytes, scale: float) -> bytes:
    """
    Apply pie menu positioning fix to the EXE binary data.

    Writes a code cave that multiplies kItemRadius by the scale factor
    before the sin/cos calculation, and scales sector fine-tuning offsets.
    """
    patched = bytearray(data)
    cave = _PIE_MENU_CAVE_ADDR
    cave_va = _PIE_MENU_IMAGE_BASE + cave

    # --- Write code cave ---
    # Layout: [float scale] [cave1: 15 bytes] [cave2: 15 bytes]

    # Float multiplier at cave_addr (4 bytes)
    struct.pack_into("<f", patched, cave, scale)

    # cave1 at cave+4: fild [ebx+0x1F0]; fmul [multiplier]; fmul st,st1; ret
    c1 = cave + 4
    patched[c1:c1+6] = bytes([0xDB, 0x83, 0xF0, 0x01, 0x00, 0x00])  # fild [ebx+0x1F0]
    patched[c1+6:c1+12] = bytes([0xD8, 0x0D]) + struct.pack("<I", cave_va)  # fmul [cave_va]
    patched[c1+12:c1+14] = bytes([0xD8, 0xC9])  # fmul st(0), st(1)
    patched[c1+14] = 0xC3  # ret

    # cave2 at cave+19: same structure
    c2 = cave + 19
    patched[c2:c2+6] = bytes([0xDB, 0x83, 0xF0, 0x01, 0x00, 0x00])  # fild [ebx+0x1F0]
    patched[c2+6:c2+12] = bytes([0xD8, 0x0D]) + struct.pack("<I", cave_va)  # fmul [cave_va]
    patched[c2+12:c2+14] = bytes([0xD8, 0xC9])  # fmul st(0), st(1)
    patched[c2+14] = 0xC3  # ret

    # --- Patch call site 1 (sin path, 8 bytes) ---
    site1 = _PIE_MENU_FILD_SITE_1
    rel1 = (c1 + _PIE_MENU_IMAGE_BASE) - (site1 + _PIE_MENU_IMAGE_BASE + 5)
    patched[site1] = 0xE8  # call
    struct.pack_into("<i", patched, site1 + 1, rel1)
    patched[site1+5:site1+8] = bytes([0x90, 0x90, 0x90])  # nop pad

    # --- Patch call site 2 (cos path, 9 bytes) ---
    # Keep the pop ecx at its original position
    site2 = _PIE_MENU_FILD_SITE_2
    rel2 = (c2 + _PIE_MENU_IMAGE_BASE) - (site2 + _PIE_MENU_IMAGE_BASE + 5)
    patched[site2] = 0xE8  # call
    struct.pack_into("<i", patched, site2 + 1, rel2)
    patched[site2+5] = 0x59  # pop ecx (stack cleanup, was at site2+6 originally)
    patched[site2+6:site2+9] = bytes([0x90, 0x90, 0x90])  # nop pad

    # --- Scale sector offsets ---
    for offset, orig_val in _PIE_MENU_SECTOR_OFFSETS:
        new_val = min(int(orig_val * scale), 127)
        patched[offset] = new_val

    return bytes(patched)
