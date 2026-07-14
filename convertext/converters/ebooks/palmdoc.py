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
    """Compress data using PalmDOC LZ77 compression."""
    result = bytearray()
    i = 0

    while i < len(data):
        best_len = 0
        best_dist = 0

        if i >= 3:
            max_dist = min(2047, i, 256)  # 256-byte window: fast with minimal size cost
            for dist in range(1, max_dist + 1):
                pos = i - dist
                match_len = 0
                while (match_len < 10 and
                       i + match_len < len(data) and
                       data[pos + match_len] == data[i + match_len]):
                    match_len += 1
                    if pos + match_len >= i:
                        break
                if match_len >= 3 and match_len > best_len:
                    best_len = match_len
                    best_dist = dist
                    if best_len == 10:
                        break

        if best_len >= 3:
            code = 0x8000 | (best_dist << 3) | (best_len - 3)
            result.extend(struct.pack('>H', code))
            i += best_len
        elif 0x09 <= data[i] <= 0x7F:
            result.append(data[i])
            i += 1
        else:
            end = i + 1
            while end < len(data) and end - i < 8 and not (0x09 <= data[end] <= 0x7F):
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
