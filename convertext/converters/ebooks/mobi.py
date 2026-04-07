"""MOBI v6 write-only converter."""

import html
import random
import struct
import time
from pathlib import Path
from typing import Any, Dict, List

from convertext.converters.base import BaseConverter, Document

_PALM_EPOCH = 2082844800  # seconds from 1904-01-01 to Unix epoch (1970-01-01)

_FLIS = (b'FLIS\x00\x00\x00\x08\x00\x41\x00\x00\x00\x00\x00\x00'
         b'\xff\xff\xff\xff\x00\x01\x00\x03\x00\x00\x00\x03'
         b'\x00\x00\x00\x01\xff\xff\xff\xff')

_EOF = b'\xe9\x8e\x0d\x0a'


def _build_fcis(text_length: int) -> bytes:
    """Build FCIS record."""
    return (b'FCIS\x00\x00\x00\x14\x00\x00\x00\x10'
            b'\x00\x00\x00\x01\x00\x00\x00\x00'
            + struct.pack('>I', text_length)
            + b'\x00\x00\x00\x00\x00\x00\x00\x20'
            b'\x00\x00\x00\x08\x00\x01\x00\x01\x00\x00\x00\x00')


class ToMobiConverter(BaseConverter):
    """Convert documents to MOBI v6 format for Kindle."""

    @property
    def input_formats(self) -> List[str]:
        return ['txt', 'html', 'md', 'epub']

    @property
    def output_formats(self) -> List[str]:
        return ['mobi']

    def can_convert(self, source: str, target: str) -> bool:
        return source in self.input_formats and target in self.output_formats

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        doc = self._read_source(source_path, config)
        self._apply_metadata_overrides(doc, source_path, config)
        return _write_mobi(doc, target_path)

    def _read_source(self, path: Path, config: Dict[str, Any]) -> Document:
        fmt = path.suffix.lstrip('.').lower()
        enc = config.get('documents', {}).get('encoding', 'utf-8')
        if fmt == 'txt':
            return _read_txt(path, enc)
        elif fmt in ('html', 'htm'):
            return _read_html(path, enc)
        elif fmt in ('md', 'markdown'):
            return _read_markdown(path, enc)
        elif fmt == 'epub':
            from convertext.converters.ebooks.epub import EpubConverter
            return EpubConverter()._read_epub(path, config)
        raise ValueError(f"Unsupported source format: {fmt}")


# ── Document readers ──────────────────────────────────────────────────────────

def _read_txt(path: Path, encoding: str) -> Document:
    doc = Document()
    with open(path, 'r', encoding=encoding) as f:
        content = f.read()
    lines = content.split('\n')
    i = 0
    if len(lines) >= 2 and lines[1].strip() and all(c == '=' for c in lines[1].strip()):
        doc.metadata['title'] = lines[0].strip()
        i = 2
        if i < len(lines) and lines[i].startswith('By:'):
            doc.metadata['author'] = lines[i][3:].strip()
            i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
    for para in '\n'.join(lines[i:]).split('\n\n'):
        if para.strip():
            doc.add_paragraph(para.strip())
    return doc


def _read_html(path: Path, encoding: str) -> Document:
    from bs4 import BeautifulSoup
    doc = Document()
    with open(path, 'r', encoding=encoding) as f:
        content = f.read()
    soup = BeautifulSoup(content, 'html.parser')
    t = soup.find('title')
    if t and t.get_text().strip():
        doc.metadata['title'] = t.get_text().strip()
    for el in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        if el.name.startswith('h'):
            doc.add_heading(el.get_text().strip(), int(el.name[1]))
        elif el.name == 'p' and el.get_text().strip():
            doc.add_paragraph(el.get_text().strip())
    return doc


def _read_markdown(path: Path, encoding: str) -> Document:
    import markdown
    from bs4 import BeautifulSoup
    doc = Document()
    with open(path, 'r', encoding=encoding) as f:
        content = f.read()
    soup = BeautifulSoup(markdown.markdown(content), 'html.parser')
    for el in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        if el.name.startswith('h'):
            doc.add_heading(el.get_text().strip(), int(el.name[1]))
        elif el.name == 'p' and el.get_text().strip():
            doc.add_paragraph(el.get_text().strip())
    return doc


# ── MOBI v6 binary building ───────────────────────────────────────────────────

def _doc_to_html(doc: Document) -> str:
    """Convert Document to minimal MOBI-compatible HTML."""
    parts = ['<html><head><meta charset="utf-8"/></head><body>']
    first_h1 = True
    for block in doc.content:
        btype = block.get('type')
        if btype == 'heading':
            level = block.get('level', 1)
            text = html.escape(block.get('data', ''))
            if level == 1:
                if not first_h1:
                    parts.append('<mbp:pagebreak/>')
                first_h1 = False
            parts.append(f'<h{level}>{text}</h{level}>')
        elif btype in ('paragraph', 'text'):
            text = html.escape(block.get('data', ''))
            if text:
                parts.append(f'<p>{text}</p>')
        elif btype == 'run':
            text = html.escape(block.get('text', ''))
            if text:
                parts.append(f'<p>{text}</p>')
    parts.append('</body></html>')
    return '\n'.join(parts)


def _palmdoc_compress(data: bytes) -> bytes:
    """Compress bytes using PalmDOC LZ77 algorithm."""
    result = bytearray()
    i = 0
    while i < len(data):
        best_len = 0
        best_dist = 0
        if i >= 3:
            max_dist = min(2047, i)
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


def _build_exth(title: str, author: str, language: str) -> bytes:
    """Build EXTH header block with title, author, and language records."""
    def rec(code, payload):
        return struct.pack('>II', code, 8 + len(payload)) + payload

    records = [
        rec(100, author.encode('utf-8')),
        rec(503, title.encode('utf-8')),
        rec(524, language.encode('utf-8')),
    ]
    data = b''.join(records)
    raw_len = 12 + len(data)
    padding = (4 - (raw_len % 4)) % 4
    return (b'EXTH'
            + struct.pack('>II', raw_len + padding, len(records))
            + data
            + b'\x00' * padding)


def _build_record0(doc: Document, text_length: int, num_text_records: int,
                    flis_idx: int, fcis_idx: int) -> bytes:
    """Build PalmDB record 0: PalmDOC header + MOBI v6 header (232B) + EXTH + title."""
    title = doc.metadata.get('title', 'Unknown')
    author = doc.metadata.get('author', '')
    language = doc.metadata.get('language', 'en')

    title_bytes = title.encode('utf-8')
    exth = _build_exth(title, author, language)
    full_name_offset = 16 + 232 + len(exth)

    # PalmDOC header — 16 bytes
    palmdoc = struct.pack('>HHIHHI',
        2,                   # compression = PalmDOC
        0,                   # reserved
        text_length,         # uncompressed text length
        num_text_records,    # number of text records
        4096,                # max record size
        0,                   # current position
    )
    assert len(palmdoc) == 16

    # MOBI v6 header — 232 bytes (offsets from MOBI magic 'MOBI')
    FF = 0xFFFFFFFF
    unique_id = random.randint(1, 0xFFFFFFFF)
    first_non_book = num_text_records + 1

    mobi = b'MOBI'
    mobi += struct.pack('>I', 232)                           # +4: header_length
    mobi += struct.pack('>I', 2)                             # +8: mobi_type = book
    mobi += struct.pack('>I', 65001)                         # +12: text_encoding = UTF-8
    mobi += struct.pack('>I', unique_id)                     # +16
    mobi += struct.pack('>I', 6)                             # +20: file_version
    mobi += b'\xff' * 40                                     # +24-63: unused indices
    mobi += struct.pack('>I', first_non_book)                # +64
    mobi += struct.pack('>I', full_name_offset)              # +68: from record 0 start
    mobi += struct.pack('>I', len(title_bytes))              # +72
    mobi += struct.pack('>I', 0x0409)                        # +76: locale = en-US
    mobi += struct.pack('>II', 0, 0)                         # +80: input/output language
    mobi += struct.pack('>I', 6)                             # +88: min_version
    mobi += struct.pack('>I', FF)                            # +92: first_image_index (none)
    mobi += struct.pack('>IIII', 0, 0, 0, 0)                # +96-111: huffman fields
    mobi += struct.pack('>I', 0x40)                          # +112: exth_flags (has EXTH)
    mobi += b'\x00' * 32                                     # +116-147: unknown
    mobi += struct.pack('>I', FF)                            # +148: unknown
    mobi += struct.pack('>I', FF)                            # +152: drm_offset (none)
    mobi += struct.pack('>I', 0)                             # +156: drm_count
    mobi += struct.pack('>I', 0)                             # +160: drm_size
    mobi += struct.pack('>I', 0)                             # +164: drm_flags
    mobi += b'\x00' * 8                                      # +168-175: unknown
    mobi += struct.pack('>HH', 1, num_text_records)          # +176: first/last content record
    mobi += struct.pack('>I', 0)                             # +180: unknown
    mobi += struct.pack('>I', fcis_idx)                      # +184: FCIS record
    mobi += struct.pack('>I', 1)                             # +188: FCIS count
    mobi += struct.pack('>I', flis_idx)                      # +192: FLIS record
    mobi += struct.pack('>I', 1)                             # +196: FLIS count
    mobi += b'\x00' * 8                                      # +200-207: unknown
    mobi += struct.pack('>II', FF, 0)                        # +208: srcs_record/count (none)
    mobi += struct.pack('>II', FF, FF)                       # +216-223: unknown
    mobi += struct.pack('>I', 0)                             # +224: extra_data_flags
    mobi += struct.pack('>I', FF)                            # +228: INDX record (none)
    assert len(mobi) == 232

    record0 = palmdoc + mobi + exth + title_bytes
    pad = (4 - (len(record0) % 4)) % 4
    return record0 + b'\x00' * pad


def _write_palmdb(path: Path, all_records: List[bytes], title: str) -> bool:
    """Write PalmDB container with all records."""
    n = len(all_records)

    # palmdb_header(78) + record_list(8*n) + gap(2) + record data
    data_start = 78 + 8 * n + 2
    offsets = []
    pos = data_start
    for rec in all_records:
        offsets.append(pos)
        pos += len(rec)

    now = int(time.time()) + _PALM_EPOCH
    palm_name = title.encode('utf-8', errors='replace')[:31]
    palm_name = palm_name + b'\x00' * (32 - len(palm_name))

    header = palm_name                                        # 32
    header += struct.pack('>HH', 0, 0)                       # attributes, version → 36
    header += struct.pack('>III', now, now, 0)               # creation, modification, backup → 48
    header += struct.pack('>III', 0, 0, 0)                   # mod_num, app_info, sort_info → 60
    header += b'BOOKMOBI'                                     # type + creator → 68
    header += struct.pack('>II', random.randint(1, 0xFFFFFF), 0)  # unique_id_seed, next_list_id → 76
    header += struct.pack('>H', n)                            # num_records → 78
    assert len(header) == 78

    with open(path, 'wb') as f:
        f.write(header)
        for i, offset in enumerate(offsets):
            f.write(struct.pack('>I', offset))               # record data offset
            f.write(b'\x00')                                 # attributes
            f.write(i.to_bytes(3, 'big'))                    # unique ID (3 bytes)
        f.write(b'\x00\x00')                                 # gap
        for rec in all_records:
            f.write(rec)

    return True


def _write_mobi(doc: Document, path: Path) -> bool:
    """Orchestrate MOBI v6 file creation from a Document."""
    html_str = _doc_to_html(doc)
    html_bytes = html_str.encode('utf-8')

    chunks = [html_bytes[i:i + 4096] for i in range(0, max(len(html_bytes), 1), 4096)]
    compressed = [_palmdoc_compress(c) for c in chunks]

    num_text = len(compressed)
    flis_idx = num_text + 1
    fcis_idx = num_text + 2

    record0 = _build_record0(doc, len(html_bytes), num_text, flis_idx, fcis_idx)
    all_records = [record0] + compressed + [_FLIS, _build_fcis(len(html_bytes)), _EOF]

    title = doc.metadata.get('title', 'Unknown')
    return _write_palmdb(path, all_records, title)
