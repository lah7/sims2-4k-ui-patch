"""
Handles QFS compressed data in DBPF files as used by The Sims 2.
"""
#
# Based on the work from:
#   jDBPFX: https://github.com/memo33/jDBPFX (jdbpfx/util/DBPFPackager.java)
#
# The original Java code and implementation of this algorithm was
# written by memo33.
#
# This code was ported from Java to Python with assistance from
# GitHub Copilot. Both the original Java code and this port are
# licensed under the General Public License version 3.
#

# Compression constants
MAX_OFFSET = 0x20000
MAX_COPY_COUNT = 0x404

# Compression level (up to 255, higher = increased compression = longer processing)
QFS_MAXITER = 20


def _copy_array(src: bytearray, src_pos: int, dest: bytearray, dest_pos: int, length: int) -> bytearray:
    for i in range(length):
        dest[dest_pos + i] = src[src_pos + i]
    return dest


def _offset_copy(array: bytearray, offset: int, dest_pos: int, length: int) -> bytearray:
    src_pos = dest_pos - offset
    if len(array) < dest_pos + length:
        raise ValueError("Error: array too small")

    for i in range(length):
        array[dest_pos + i] = array[src_pos + i]
    return array


def decompress(compressed_data: bytearray, decompressed_size: int) -> bytes:
    """
    Return decompressed data as bytes.
    """
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
            num_plain_text = control1 & 0x03
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
            num_plain_text = control1 & 0x03
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
            num_plain_text = control1 & 0x03
            decompressed_data = _copy_array(compressed_data, pos, decompressed_data, dest_pos, num_plain_text)
            dest_pos += num_plain_text
            pos += num_plain_text

    return decompressed_data


def compress(data: bytearray) -> bytes:
    """
    Compresses data using the QFS algorithm and returns the data for
    inclusion in the DBPF package.

    Make sure to add an entry in the DIR file, and check if the
    data lengths are correct (in event there was nothing to compress)
    """
    # Contains the latest offset for a combination of two characters
    cmpmap2 = {}

    # Contains the compressed data (maximal size = uncompressedSize+MAX_COPY_COUNT)
    output = bytearray(len(data) + MAX_COPY_COUNT)

    write_index: int = 9 # reserved for header
    last_read_index: int = 0
    index_list: list = []
    copy_offset: int = 0
    copy_count: int = 0
    index: int = -1
    end = False

    # Begin main compression loop
    while index < len(data) - 3:
        # Get all compression candidates
        # (list of offsets for all occurrences of the current 3 bytes)
        while True:
            index += 1
            if index >= len(data) - 2:
                end = True
                break

            map_index: int = (data[index] & 0xFF) | ((data[index + 1] & 0xFF) << 8) | ((data[index + 2] & 0xFF) << 16)

            index_list: list = cmpmap2.get(map_index) or []
            if not index_list:
                cmpmap2[map_index] = index_list
            index_list.append(index)
            if index >= last_read_index:
                break
        if end:
            break

        # Find the longest repeating byte sequence in the index list (for offset copy)
        offset_copy_count = 0
        loop_index = 1
        while loop_index < len(index_list) and loop_index < QFS_MAXITER:
            found_index = index_list[len(index_list) - 1 - loop_index]
            if index - found_index >= MAX_OFFSET:
                break
            loop_index += 1
            copy_count = 3
            while (len(data) > index + copy_count
                    and data[index + copy_count] == data[found_index + copy_count]
                    and copy_count < MAX_COPY_COUNT):
                copy_count += 1
            if copy_count > offset_copy_count:
                offset_copy_count = copy_count
                copy_offset = index - found_index

        # Check if this can be compressed
        if offset_copy_count > len(data) - index:
            offset_copy_count = index - len(data)
        if offset_copy_count <= 2:
            offset_copy_count = 0
        elif (offset_copy_count == 3) and (copy_offset > 0x400): # 1024
            offset_copy_count = 0
        elif (offset_copy_count == 4) and (copy_offset > 0x4000): # 16384
            offset_copy_count = 0

        # Is this offset compressable?
        if offset_copy_count > 0:
            while index - last_read_index >= 4:
                copy_count = int((index - last_read_index) // 4 - 1)
                if copy_count > 0x1B:
                    copy_count = 0x1B

                output[write_index] = 0xE0 + copy_count
                write_index += 1

                copy_count = 4 * copy_count + 4
                output = _copy_array(data, last_read_index, output, write_index, copy_count)
                last_read_index += copy_count
                write_index += copy_count

            # Offset copy
            copy_count = index - last_read_index
            copy_offset -= 1
            if offset_copy_count <= 0x0A and copy_offset < 0x400:
                output[write_index] = ((((copy_offset >> 8) << 5) + ((offset_copy_count - 3) << 2) + copy_count)) & 0xFF
                write_index += 1
                output[write_index] = copy_offset & 0xff
                write_index += 1
            elif offset_copy_count <= 0x43 and copy_offset < 0x4000:
                output[write_index] = 0x80 + (offset_copy_count - 4)
                write_index += 1
                output[write_index] = (copy_count << 6) + (copy_offset >> 8)
                write_index += 1
                output[write_index] = copy_offset & 0xff
                write_index += 1
            elif offset_copy_count <= MAX_COPY_COUNT and copy_offset < MAX_OFFSET:
                output[write_index] = (0xC0 + (((copy_offset >> 16) << 4) + (((offset_copy_count - 5) >> 8) << 2) + copy_count))
                write_index += 1
                output[write_index] = (copy_offset >> 8) & 0xff
                write_index += 1
                output[write_index] = copy_offset & 0xff
                write_index += 1
                output[write_index] = (offset_copy_count - 5) & 0xff
                write_index += 1

            # Do the offset copy
            output = _copy_array(data, last_read_index, output, write_index, copy_count)
            write_index += copy_count
            last_read_index += copy_count
            last_read_index += offset_copy_count

    # Add the end record
    index = len(data)
    while index - last_read_index >= 4:
        copy_count = int((index - last_read_index) // 4 - 1)
        if copy_count > 0x1B:
            copy_count = 0x1B
        output[write_index] = 0xE0 + copy_count
        write_index += 1
        copy_count = 4 * copy_count + 4

        output = _copy_array(data, last_read_index, output, write_index, copy_count)
        last_read_index += copy_count
        write_index += copy_count

    copy_count = index - last_read_index
    output[write_index] = 0xFC + copy_count
    write_index += 1
    output = _copy_array(data, last_read_index, output, write_index, copy_count)
    write_index += copy_count
    last_read_index += copy_count

    # Write the header for the compressed data
    def _write_bytes(data, offset, value, count, endian):
        b = bytearray(value.to_bytes(count, byteorder=endian))
        for index, pos in enumerate(range(offset, offset + count)):
            data[pos] = b[index]
        return data

    # -- Offset 00 - Compressed file size
    compressed_size = write_index
    output = _write_bytes(output, 0, compressed_size, 4, "little")

    # -- Offset 04 - Compression ID (QFS)
    output = _write_bytes(output, 4, 0xFB10, 2, "little")

    # -- Offset 06 - Uncompressed file size
    output = _write_bytes(output, 6, len(data), 3, "big")

    # Did anything actually compress?
    if compressed_size > len(data):
        return data

    # Strip excess zeros from the end of the output
    del output[compressed_size:]

    return bytes(output)
