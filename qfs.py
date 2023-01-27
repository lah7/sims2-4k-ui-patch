#
# Handles QFS compressed data in DBPF files as used by The Sims 2.
#
# Based on the work from:
#   jDBPFX: https://github.com/memo33/jDBPFX (jdbpfx/util/DBPFPackager.java)
#
# The original Java code and implementation of the algorithm was
# written by memo33.
#
# This code was ported from Java to Python with assistance from
# GitHub Copilot. Both the original Java code and this port are
# licensed under the General Public License version 3.
#


def _copy_array(src: bytearray, src_pos: int, dest: bytearray, dest_pos: int, length: int) -> bytearray:
    for i in range(length):
        dest[dest_pos + i] = src[src_pos + i]
    return dest


def _offset_copy(array: bytearray, offset: int, dest_pos: int, length: int) -> bytearray:
    src_pos = dest_pos - offset
    if (len(array) < dest_pos + length):
        raise ValueError("Error: array too small")

    for i in range(length):
        array[dest_pos + i] = array[src_pos + i]
    return array


def decompress(compressed_data: bytearray, decompressed_size: int) -> bytes:
    decompressed_data = bytearray(decompressed_size)
    dest_pos = 0
    pos = 9 # skip header
    control1 = 0

    while control1 < 0xFC and pos < len(compressed_data):
        control1 = compressed_data[pos]
        pos += 1
        if control1 >= 0 and control1 <= 127:
            control2 = compressed_data[pos]
            pos += 1
            num_plain_text = (control1 & 0x03)
            decompressed_data = _copy_array(compressed_data, pos, decompressed_data, dest_pos, num_plain_text)
            dest_pos += num_plain_text
            pos += num_plain_text
            offset = ((control1 & 0x60) << 3) + (control2) + 1
            num_to_copy_from_offset = ((control1 & 0x1C) >> 2) + 3
            decompressed_data = _offset_copy(decompressed_data, offset, dest_pos, num_to_copy_from_offset)
            dest_pos += num_to_copy_from_offset
        elif control1 >= 128 and control1 <= 191:
            control2 = compressed_data[pos]
            pos += 1
            control3 = compressed_data[pos]
            pos += 1
            num_plain_text = (control2 >> 6) & 0x03
            decompressed_data = _copy_array(compressed_data, pos, decompressed_data, dest_pos, num_plain_text)
            dest_pos += num_plain_text
            pos += num_plain_text
            offset = ((control2 & 0x3F) << 8) + (control3) + 1
            num_to_copy_from_offset = (control1 & 0x3F) + 4
            decompressed_data = _offset_copy(decompressed_data, offset, dest_pos, num_to_copy_from_offset)
            dest_pos += num_to_copy_from_offset
        elif control1 >= 192 and control1 <= 223:
            num_plain_text = (control1 & 0x03)
            control2 = compressed_data[pos]
            pos += 1
            control3 = compressed_data[pos]
            pos += 1
            control4 = compressed_data[pos]
            pos += 1
            decompressed_data = _copy_array(compressed_data, pos, decompressed_data, dest_pos, num_plain_text)
            dest_pos += num_plain_text
            pos += num_plain_text
            offset = ((control1 & 0x10) << 12) + (control2 << 8) + (control3) + 1
            num_to_copy_from_offset = ((control1 & 0x0C) << 6) + (control4) + 5
            decompressed_data = _offset_copy(decompressed_data, offset, dest_pos, num_to_copy_from_offset)
            dest_pos += num_to_copy_from_offset
        elif control1 >= 224 and control1 <= 251:
            num_plain_text = ((control1 & 0x1F) << 2) + 4
            decompressed_data = _copy_array(compressed_data, pos, decompressed_data, dest_pos, num_plain_text)
            dest_pos += num_plain_text
            pos += num_plain_text
        else:
            num_plain_text = (control1 & 0x03)
            decompressed_data = _copy_array(compressed_data, pos, decompressed_data, dest_pos, num_plain_text)
            dest_pos += num_plain_text
            pos += num_plain_text

    return decompressed_data
