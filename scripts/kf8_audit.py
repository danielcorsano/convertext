"""Decode and validate KF8/AZW3 skeleton and chunk indices the way a reader does.

Written for the 2026-08-17 AZW3 audit (see plan/AZW3_AUDIT.md). Kept because the
findings are only reproducible with it: it decodes SKEL/CHUNK/NCX/guide indices,
then checks each chunk insert position against its own skeleton bounds - the
check that exposed the crash-class defect K1.

Usage:
    poetry run python scripts/kf8_audit.py book.azw3 [reference.azw3 ...]
"""
import re
import struct
import sys
from pathlib import Path


def records(data):
    n = struct.unpack('>H', data[76:78])[0]
    offs = [struct.unpack('>I', data[78 + 8 * i:82 + 8 * i])[0] for i in range(n)]
    offs.append(len(data))
    return [data[offs[i]:offs[i + 1]] for i in range(n)]


def palmdoc(data):
    out = bytearray(); i = 0
    while i < len(data):
        b = data[i]; i += 1
        if b == 0: out.append(0)
        elif b <= 8: out.extend(data[i:i + b]); i += b
        elif b <= 0x7F: out.append(b)
        elif b <= 0xBF:
            if i >= len(data): break
            v = ((b << 8) | data[i]) & 0x3FFF; i += 1
            dist, ln = v >> 3, (v & 7) + 3
            if not 0 < dist <= len(out): break
            for _ in range(ln): out.append(out[-dist])
        else:
            out.append(0x20); out.append(b & 0x7F)
    return bytes(out)


def strip_trailing(data, flags):
    for bit in range(15, 0, -1):
        if flags & (1 << bit):
            size = 0
            for i in range(1, 5):
                byte = data[-i]; size = (size << 7) | (byte & 0x7F)
                if byte & 0x80: break
            data = data[:-size]
    if flags & 1:
        data = data[:-((data[-1] & 3) + 1)]
    return data


def read_vwi(data, pos):
    """Forward variable-width integer; terminating byte has the high bit set."""
    value = 0
    while pos < len(data):
        byte = data[pos]; pos += 1
        value = (value << 7) | (byte & 0x7F)
        if byte & 0x80:
            break
    return value, pos


def parse_tagx(header):
    start = header.find(b'TAGX')
    length, control_bytes = struct.unpack('>II', header[start + 4:start + 12])
    tags = []
    for off in range(start + 12, start + length, 4):
        tag, num_values, mask, end = header[off:off + 4]
        tags.append((tag, num_values, mask, end))
    return tags, control_bytes


def parse_index(header_rec, data_rec):
    """Return list of (label, {tag: [values]}) for one INDX pair."""
    tags, control_bytes = parse_tagx(header_rec)
    idxt = struct.unpack('>I', data_rec[0x14:0x18])[0]
    count = struct.unpack('>I', data_rec[0x18:0x1C])[0]
    entries = []
    for i in range(count):
        pos = struct.unpack('>H', data_rec[idxt + 4 + 2 * i:idxt + 6 + 2 * i])[0]
        label_len = data_rec[pos]
        label = data_rec[pos + 1:pos + 1 + label_len].decode('ascii', 'replace')
        pos += 1 + label_len
        control = data_rec[pos:pos + control_bytes]
        pos += control_bytes
        values = {}
        for tag, num_values, mask, end in tags:
            if end & 0x01:
                continue
            if not (control[0] & mask):
                continue
            got = []
            for _ in range(num_values):
                v, pos = read_vwi(data_rec, pos)
                got.append(v)
            values[tag] = got
        entries.append((label, values))
    return entries


def audit(path):
    data = Path(path).read_bytes()
    recs = records(data)
    rec0 = recs[0]
    text_length, num_text = struct.unpack('>IH', rec0[4:10])
    hdr_len = struct.unpack('>I', rec0[20:24])[0]
    if hdr_len != 264:
        print(f"{Path(path).name}: not KF8 (header {hdr_len})"); return
    f = lambda o: struct.unpack('>I', rec0[16 + o:16 + o + 4])[0]
    flags = f(0xF0 - 16)
    chunk_idx, skel_idx = f(0xF8 - 16), f(0xFC - 16)
    ncx_idx, guide_idx = f(0xF4 - 16), f(0x104 - 16)

    raw = b''.join(palmdoc(strip_trailing(r, flags)) for r in recs[1:1 + num_text])
    print(f"\n########## {Path(path).name}")
    print(f"  rawml {len(raw)} (declared {text_length}) "
          f"{'OK' if len(raw) == text_length else '*** MISMATCH ***'}")
    print(f"  chunk_idx={chunk_idx} skel_idx={skel_idx} ncx={ncx_idx} guide={guide_idx} "
          f"extra_data_flags={flags}")

    for label, idx in (('CHUNK', chunk_idx), ('SKEL', skel_idx)):
        h = recs[idx]
        print(f"  {label} INDX header: num_cncx@0x30={struct.unpack('>I', h[0x30:0x34])[0]} "
              f"num_cncx@0x34={struct.unpack('>I', h[0x34:0x38])[0]} "
              f"type@0x08={struct.unpack('>I', h[0x08:0x0C])[0]} "
              f"total@0x24={struct.unpack('>I', h[0x24:0x28])[0]}")

    skel = parse_index(recs[skel_idx], recs[skel_idx + 1])
    chunk = parse_index(recs[chunk_idx], recs[chunk_idx + 1])
    print(f"  skeletons={len(skel)}  chunks={len(chunk)}")

    # Validate the way KindleUnpack does: insertpos comes from the chunk LABEL,
    # and must land inside its skeleton, before the closing tags.
    print("\n  --- skeleton table (tag1=chunk_count, tag6=[start,len])")
    for name, vals in skel[:4]:
        print(f"      {name}  chunk_count={vals.get(1)}  start/len={vals.get(6)}")
    print("  --- chunk table (label=insert_pos, tag3=file, tag4=seq, tag6=[start_in_skel,len])")
    bad = 0
    for label, vals in chunk[:6]:
        print(f"      insert_pos={label} file={vals.get(3)} seq={vals.get(4)} "
              f"tag6={vals.get(6)} cncx={vals.get(2)}")
    for label, vals in chunk:
        insert = int(label)
        fileno = (vals.get(3) or [0])[0]
        if fileno >= len(skel):
            bad += 1; continue
        s_start, s_len = skel[fileno][1][6]
        if not (s_start <= insert <= s_start + s_len):
            bad += 1
    print(f"\n  insert positions outside their skeleton: {bad}/{len(chunk)}")

    # What does the skeleton actually end with, and where does the label point?
    if skel and chunk:
        s_start, s_len = skel[0][1][6]
        print(f"  skeleton[0] spans [{s_start}, {s_start + s_len})  ends with "
              f"{raw[s_start + s_len - 16:s_start + s_len]!r}")
        print(f"  chunk[0] label says insert at {chunk[0][0]} -> byte context "
              f"{raw[int(chunk[0][0]) - 16:int(chunk[0][0]) + 8]!r}")

    aids = len(re.findall(rb'aid=', raw))
    print(f"  aid attributes in rawml: {aids}")
    lengths = [(v.get(6) or [0, 0])[1] for _, v in chunk]
    if lengths:
        print(f"  chunk content length: max={max(lengths)} mean={sum(lengths)//len(lengths)}")


for p in sys.argv[1:]:
    audit(p)
