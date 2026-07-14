"""Shared PalmDOC (LZ77) compression and the optional MOBI trailing records.

Both the MOBI v6 writer and the KF8/AZW3 writer/reader use these, so they live
in one place. The compressor and decompressor are exact inverses; FLIS and EOF
are the standard optional trailing records (a Kindle reads a file without them).
"""

import struct

FLIS = (b'FLIS\x00\x00\x00\x08\x00\x41\x00\x00\x00\x00\x00\x00'
        b'\xff\xff\xff\xff\x00\x01\x00\x03\x00\x00\x00\x03'
        b'\x00\x00\x00\x01\xff\xff\xff\xff')

EOF = b'\xe9\x8e\x0d\x0a'


def palmdoc_compress(data: bytes) -> bytes:
    """Compress data using PalmDOC LZ77 compression.

    Anchors a 3-byte match with bytes.rfind over the full 2047-byte window
    (C-speed), then extends up to 10 bytes; falls back to a literal on a miss.
    """
    result = bytearray()
    i = 0
    n = len(data)

    while i < n:
        best_len = 0
        best_dist = 0

        if n - i >= 3 and i >= 1:
            window_start = max(0, i - 2047)
            found = data.rfind(data[i:i + 3], window_start, i + 2)
            if found != -1 and found < i:
                length = 3
                while (length < 10 and i + length < n
                       and data[found + length] == data[i + length]):
                    length += 1
                best_len = length
                best_dist = i - found

        if best_len >= 3:
            code = 0x8000 | (best_dist << 3) | (best_len - 3)
            result.extend(struct.pack('>H', code))
            i += best_len
        elif 0x09 <= data[i] <= 0x7F:
            result.append(data[i])
            i += 1
        else:
            end = i + 1
            while end < n and end - i < 8 and not (0x09 <= data[end] <= 0x7F):
                end += 1
            count = end - i
            result.append(count)
            result.extend(data[i:end])
            i = end
    return bytes(result)


def palmdoc_decompress(data: bytes) -> bytes:
    """Decompress PalmDOC compressed data."""
    result = []
    i = 0

    while i < len(data):
        c = data[i]
        i += 1

        if c == 0:
            result.append(0)
        elif 1 <= c <= 8:
            result.extend(data[i:i + c])
            i += c
        elif 0x09 <= c <= 0x7F:
            result.append(c)
        elif 0xC0 <= c:
            result.append(0x20)
            result.append(c ^ 0x80)
        else:
            if i < len(data):
                c2 = data[i]
                i += 1
                dist = ((c << 8 | c2) >> 3) & 0x7FF
                length = (c2 & 0x07) + 3
                start = len(result) - dist
                if start >= 0:
                    for _ in range(length):
                        if start < len(result):
                            result.append(result[start])
                            start += 1

    return bytes(result)
