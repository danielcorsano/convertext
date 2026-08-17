"""Structural inspector for MOBI/AZW3 output, optionally against a Calibre reference.

MOBI and AZW3 are undocumented binary formats, so changes are checked against a
file Calibre built from the same source rather than against assumptions. Calibre
is used to generate a reference only; no Calibre code is used.

Usage:
    poetry run python scripts/kindle_diff.py book.mobi              # inspect one file
    poetry run python scripts/kindle_diff.py book.epub --format mobi  # convert, then
                                                                      # diff vs Calibre
Options:
    --format mobi|azw3   output to build from a source document (default: mobi)
    --no-reference       skip the Calibre reference build
    --debug              show full tracebacks
"""

import argparse
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

# Calibre ships its CLI outside PATH on macOS and Windows, so check PATH first
# then the usual install locations. Absent Calibre only disables the reference.
_CALIBRE_CANDIDATES = [
    '/Applications/calibre.app/Contents/MacOS/ebook-convert',
    '/usr/bin/ebook-convert',
    '/usr/local/bin/ebook-convert',
    '/opt/homebrew/bin/ebook-convert',
    r'C:\Program Files\Calibre2\ebook-convert.exe',
    r'C:\Program Files (x86)\Calibre2\ebook-convert.exe',
]


def find_calibre():
    """Locate Calibre's ebook-convert, or None if it is not installed."""
    found = shutil.which('ebook-convert')
    if found:
        return Path(found)
    for candidate in _CALIBRE_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            return path
    return None


CALIBRE = find_calibre()

INDX_FIELDS = [(0x08, 'type'), (0x0C, 'gen'), (0x10, 'unk_0x10'), (0x14, 'idxt_offset'),
               (0x18, 'data_records'), (0x1C, 'encoding'), (0x24, 'entry_count'),
               (0x30, 'num_cncx'), (0xB4, 'tagx_offset')]

MARKUP = ['h1', 'h2', 'p', 'b', 'i', 'a', 'img', 'table', 'ul', 'ol', 'blockquote']


def records(data: bytes) -> list:
    """Split a PalmDB container into its records."""
    count = struct.unpack('>H', data[76:78])[0]
    offsets = [struct.unpack('>I', data[78 + 8 * i:82 + 8 * i])[0] for i in range(count)]
    offsets.append(len(data))
    return [data[offsets[i]:offsets[i + 1]] for i in range(count)]


def palmdoc_decompress(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        byte = data[i]
        i += 1
        if byte == 0:
            out.append(0)
        elif byte <= 8:
            out.extend(data[i:i + byte])
            i += byte
        elif byte <= 0x7F:
            out.append(byte)
        elif byte <= 0xBF:
            if i >= len(data):
                break
            pair = ((byte << 8) | data[i]) & 0x3FFF
            i += 1
            distance, length = pair >> 3, (pair & 7) + 3
            if not 0 < distance <= len(out):
                break
            for _ in range(length):
                out.append(out[-distance])
        else:
            out.append(0x20)
            out.append(byte & 0x7F)
    return bytes(out)


def strip_trailing(data: bytes, flags: int) -> bytes:
    """Remove the per-record trailing entries declared by extra_data_flags."""
    for bit in range(15, 0, -1):
        if flags & (1 << bit):
            size = 0
            for i in range(1, 5):
                byte = data[-i]
                size = (size << 7) | (byte & 0x7F)
                if byte & 0x80:
                    break
            data = data[:-size]
    if flags & 1:
        data = data[:-((data[-1] & 3) + 1)]
    return data


def exth(rec0: bytes) -> dict:
    """Map EXTH record codes to their integer or truncated string payloads."""
    start = rec0.find(b'EXTH')
    if start < 0:
        return {}
    count = struct.unpack('>I', rec0[start + 8:start + 12])[0]
    pos, out = start + 12, {}
    for _ in range(count):
        code, length = struct.unpack('>II', rec0[pos:pos + 8])
        payload = rec0[pos + 8:pos + length]
        out[code] = struct.unpack('>I', payload)[0] if length == 12 else payload[:40]
        pos += length
    return out


def inspect(path: Path) -> dict:
    """Collect the structural facts worth comparing between two Kindle files."""
    data = path.read_bytes()
    recs = records(data)
    rec0 = recs[0]
    text_length, num_text = struct.unpack('>IH', rec0[4:10])
    field = lambda off: struct.unpack('>I', rec0[16 + off:16 + off + 4])[0]  # noqa: E731
    kf8 = field(4) == 264

    flags = field(0xF0 - 16) if kf8 else field(224)
    raw = b''.join(palmdoc_decompress(strip_trailing(r, flags))
                   for r in recs[1:1 + num_text])
    text = raw.decode('utf-8', 'replace')

    info = {
        'file': path.name,
        'size': len(data),
        'records': len(recs),
        'text_records': num_text,
        'text_length': text_length,
        'rawml_matches_header': len(raw) == text_length,
        'kf8': kf8,
        'extra_data_flags': flags,
        'filepos': len(re.findall(r'filepos=', text)),
        'unresolved_filepos': len(re.findall(r'filepos=0{10}', text)),
        'guide': text.count('<guide'),
        'pagebreaks': text.count('mbp:pagebreak'),
        'exth_codes': sorted(exth(rec0)),
    }
    for tag in MARKUP:
        info[f'<{tag}>'] = len(re.findall(f'<{tag}[ >]', text))

    indx = [i for i, r in enumerate(recs) if r[:4] == b'INDX']
    info['indx_records'] = len(indx)
    if indx:
        header = recs[indx[0]]
        info['indx_header'] = {name: struct.unpack('>I', header[off:off + 4])[0]
                               for off, name in INDX_FIELDS if off + 4 <= len(header)}
    # Every filepos must land inside the text, or the link is dead on the device.
    targets = [int(m.group(1)) for m in re.finditer(r'filepos=(\d+)', text)]
    info['filepos_out_of_range'] = sum(1 for t in targets if t >= len(raw))
    return info


def build_reference(source: Path, fmt: str, out_dir: Path) -> Path:
    """Convert the source with Calibre to get a structural gold standard."""
    if CALIBRE is None:
        raise FileNotFoundError('Calibre CLI (ebook-convert) not found on this system')
    target = out_dir / f'reference.{fmt}'
    cmd = [str(CALIBRE), str(source), str(target)]
    if fmt == 'mobi':
        cmd.append('--mobi-file-type=old')
    print(f"  building Calibre reference ({fmt})...", flush=True)
    subprocess.run(cmd, check=True, capture_output=True)
    return target


def report(ours: dict, reference: dict = None) -> None:
    keys = [k for k in ours if k not in ('file', 'indx_header')]
    width = max(len(k) for k in keys) + 2
    print(f"\n{'':<{width}}{'OURS':>16}" + (f"{'CALIBRE':>16}" if reference else ''))
    print('-' * (width + (32 if reference else 16)))
    for key in keys:
        mine = ours[key]
        line = f"{key:<{width}}{str(mine):>16}"
        if reference:
            theirs = reference.get(key)
            line += f"{str(theirs):>16}"
            if isinstance(mine, int) and isinstance(theirs, int) and mine != theirs:
                line += '   <-- differs'
        print(line)

    if 'indx_header' in ours:
        print("\nINDX header fields")
        for name in ours['indx_header']:
            mine = ours['indx_header'][name]
            line = f"  {name:<{width - 2}}{mine:>16}"
            if reference and 'indx_header' in reference:
                theirs = reference['indx_header'].get(name)
                line += f"{str(theirs):>16}"
                if theirs is not None and mine != theirs:
                    line += '   <-- differs'
            print(line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('path', type=Path, help='a .mobi/.azw3 file, or a source document')
    parser.add_argument('--format', default='mobi', choices=['mobi', 'azw3'])
    parser.add_argument('--no-reference', action='store_true')
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    try:
        source = None
        if args.path.suffix.lower() in ('.mobi', '.azw3', '.azw'):
            ours_path = args.path
        else:
            from convertext.converters.loader import load_converters
            from convertext.registry import get_registry
            source = args.path
            tmp = Path(tempfile.mkdtemp())
            ours_path = tmp / f'ours.{args.format}'
            load_converters()
            converter = get_registry().get_converter(source.suffix.lstrip('.').lower(),
                                                     args.format)
            if converter is None:
                print(f"No converter for {source.suffix} -> {args.format}")
                return 1
            print(f"  converting {source.name} -> {args.format}...", flush=True)
            converter.convert(source, ours_path, {})

        ours = inspect(ours_path)
        reference = None
        if source and not args.no_reference and CALIBRE is not None:
            reference = inspect(build_reference(source, args.format, ours_path.parent))

        report(ours, reference)
        if not ours['rawml_matches_header']:
            print("\n*** rawml length disagrees with the header — the text layer is corrupt")
            return 1
        if ours['filepos_out_of_range'] or ours['unresolved_filepos']:
            print(f"\n*** {ours['unresolved_filepos']} unresolved and "
                  f"{ours['filepos_out_of_range']} out-of-range links")
            return 1
        return 0
    except Exception as exc:
        if args.debug:
            raise
        print(f"error: {exc}\n(re-run with --debug for a traceback)")
        return 1


if __name__ == '__main__':
    sys.exit(main())
