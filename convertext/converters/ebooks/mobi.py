"""MOBI v6 write-only converter."""

import random
import re
import struct
import time
from html import escape as _escape
from pathlib import Path
from typing import Any, Dict, List, Optional

from convertext.converters.base import BaseConverter, Document
from convertext.converters.readers import read_source
from convertext.converters.ebooks.palmdoc import (
    palmdoc_compress as _palmdoc_compress, FLIS as _FLIS, EOF as _EOF,
)
from convertext.converters.ebooks.htmlbuild import block_to_html
from convertext.converters.ebooks.azw3 import (
    _prepare_image_records, _build_ncx_indx,
)

_PALM_EPOCH = 2082844800  # seconds from 1904-01-01 to Unix epoch (1970-01-01)

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
        return ['txt', 'html', 'htm', 'md', 'epub', 'docx', 'pdf']

    @property
    def output_formats(self) -> List[str]:
        return ['mobi']

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        doc = read_source(source_path, config)
        self._apply_metadata_overrides(doc, source_path, config)
        return _write_mobi(doc, target_path)

# ── MOBI v6 binary building ───────────────────────────────────────────────────

_PLACEHOLDER = 'filepos=0000000000'
_GENERATED_TOC = '\x00generated-toc'

def _toc_page_key(doc: Document, available: set):
    """Key of the book's own contents page, or a marker to generate one."""
    reachable = [e for e in doc.toc if _entry_key(e) in available]
    if not reachable:
        return None
    for entry in reachable:
        if re.fullmatch(r'\s*(table of )?contents\s*', entry.get('label') or '', re.I):
            return _entry_key(entry)
    return _GENERATED_TOC

def _entry_key(entry: dict) -> str:
    return f"{entry['src']}#{entry['fragment']}" if entry.get('fragment') else entry['src']

def _doc_to_html(doc: Document, img_ref=None) -> tuple:
    """Convert Document to MOBI-compatible HTML.

    Returns (html_str, toc_entries, text_start) where text_start is the rawml
    offset the Kindle opens the book at.

    Internal links resolve in a second pass: every ``filepos`` is written as a
    fixed-width placeholder first, so the byte offsets measured while building
    stay valid when the placeholders are patched with real targets.
    """
    link_targets: List[str] = []
    anchor_offsets: Dict[str, int] = {}
    pending_anchors: List[str] = []

    # Only link to targets that exist; anything else renders as plain text
    # rather than a tappable link that goes nowhere on the device.
    available = {a for block in doc.content for a in block.get('anchors', ())}

    def link_ref(href):
        """Register a reachable link target and return its placeholder."""
        if href not in available:
            return None
        link_targets.append(href)
        return _PLACEHOLDER

    toc_key = _toc_page_key(doc, available)
    if toc_key == _GENERATED_TOC:
        available.add(_GENERATED_TOC)
    head = '<html><head>'
    if toc_key:
        link_targets.append(toc_key)
        head += (f'<guide><reference type="toc" title="Table of Contents" '
                 f'{_PLACEHOLDER} /></guide>')
    head += '<meta charset="utf-8"/></head><body>'

    parts = [head]
    running = len(head.encode('utf-8'))  # bytes of '\n'.join(parts) so far
    headings = []
    first_section = True

    def emit_raw(frag):
        """Append a fragment without claiming the queued anchors."""
        nonlocal running
        parts.append(frag)
        running += 1 + len(frag.encode('utf-8'))

    def emit(frag):
        """Append a fragment, resolving any anchors queued for it."""
        offset = running + 1  # +1 for the \n that '\n'.join inserts
        for key in pending_anchors:
            anchor_offsets.setdefault(key, offset)
        pending_anchors.clear()
        emit_raw(frag)
        return offset

    # Sections come from the source's own top-level TOC; h1 headings are the
    # fallback for sources that carry no navigation (txt, md, standalone html).
    sections = {_entry_key(e): (e.get('label') or '') for e in reversed(doc.toc)
                if e.get('level', 0) == 0}

    for block in doc.content:
        pending_anchors.extend(block.get('anchors', ()))
        is_h1 = block.get('type') == 'heading' and block.get('level', 1) == 1
        if is_h1 and not sections:
            if not first_section:
                emit_raw('<mbp:pagebreak/>')
            first_section = False
            headings.append({'label': block.get('data', ''), 'offset': running + 1})

        frag = block_to_html(block, img_ref=img_ref, link_ref=link_ref)
        if not frag:
            continue

        if sections:
            label = next((sections[k] for k in pending_anchors if k in sections), None)
            if label is not None:
                if not first_section:
                    emit_raw('<mbp:pagebreak/>')
                first_section = False
                # A chapter titled by an image or its own heading needs no synthetic one.
                if block.get('type') not in ('heading', 'image'):
                    emit(f'<h1>{_escape(label)}</h1>')
        emit(frag)

    if toc_key == _GENERATED_TOC:
        pending_anchors.append(_GENERATED_TOC)
        emit('<mbp:pagebreak/><h1>Table of Contents</h1>')
        for entry in doc.toc:
            attr = link_ref(_entry_key(entry))
            label = _escape(entry.get('label') or '')
            emit(f'<p><a {attr}>{label}</a></p>' if attr else f'<p>{label}</p>')

    tail = '</body></html>'
    parts.append(tail)
    running += 1 + len(tail.encode('utf-8'))
    html_str = '\n'.join(parts)

    if link_targets:
        pos = iter(link_targets)
        html_str = re.sub(re.escape(_PLACEHOLDER),
                          lambda _m: f'filepos={anchor_offsets.get(next(pos), 0):010d}',
                          html_str)

    text_start = len(head.encode('utf-8')) + 1  # first fragment, past the head
    return html_str, _toc_entries(doc, anchor_offsets, headings, running), text_start

def _toc_entries(doc: Document, anchor_offsets: dict, headings: list, html_len: int) -> list:
    """Resolve the source's TOC to rawml offsets, falling back to h1 headings."""
    entries = []
    seen = set()
    for entry in doc.toc:
        offset = anchor_offsets.get(_entry_key(entry))
        if offset is None or offset in seen:
            continue
        seen.add(offset)
        entries.append({'label': entry.get('label') or 'Chapter', 'offset': offset})
    entries.sort(key=lambda e: e['offset'])

    if not entries:
        entries = headings
    for i, entry in enumerate(entries):
        next_offset = entries[i + 1]['offset'] if i + 1 < len(entries) else html_len
        entry['length'] = next_offset - entry['offset']
    return entries

def _build_exth(title: str, author: str, language: str = 'en',
                metadata: Optional[dict] = None, cover_offset: int = -1,
                thumb_offset: int = -1, num_images: int = 0,
                text_start: int = -1) -> bytes:
    """Build EXTH header block with metadata records."""
    metadata = metadata or {}

    def rec(code, payload):
        return struct.pack('>II', code, 8 + len(payload)) + payload

    records = [
        rec(100, author.encode('utf-8')),
        rec(503, title.encode('utf-8')),
        rec(524, language.encode('utf-8')),
        rec(125, struct.pack('>I', num_images)),
    ]
    for code, key in [(101, 'publisher'), (103, 'description'), (105, 'subject')]:
        val = metadata.get(key)
        if val:
            records.append(rec(code, val.encode('utf-8')[:500]))
    date = metadata.get('date')
    if date:
        records.append(rec(106, date.encode('utf-8')))
    if cover_offset >= 0:
        records.append(rec(201, struct.pack('>I', cover_offset)))
    if thumb_offset >= 0:
        records.append(rec(202, struct.pack('>I', thumb_offset)))
    if text_start >= 0:
        records.append(rec(116, struct.pack('>I', text_start)))  # where reading opens

    data = b''.join(records)
    raw_len = 12 + len(data)
    padding = (4 - (raw_len % 4)) % 4
    return (b'EXTH'
            + struct.pack('>II', raw_len + padding, len(records))
            + data
            + b'\x00' * padding)

def _mobi_record_layout(num_text, num_images, ncx_count):
    """Compute all record indices for MOBI v6 file layout."""
    i = num_text + 1
    first_image = i if num_images else -1
    i += num_images
    ncx_idx = i if ncx_count else -1
    i += ncx_count
    flis_idx = i; i += 1
    fcis_idx = i; i += 1
    total = i + 1  # +1 for EOF
    return {
        'first_image': first_image, 'ncx_idx': ncx_idx,
        'flis_idx': flis_idx, 'fcis_idx': fcis_idx, 'total': total,
    }

def _build_record0(doc: Document, text_length: int, num_text_records: int,
                    flis_idx: int, fcis_idx: int, exth: bytes,
                    first_image: int = -1, ncx_idx: int = -1) -> bytes:
    """Build PalmDB record 0: PalmDOC header + MOBI v6 header (232B) + EXTH + title."""
    title = doc.metadata.get('title', 'Unknown')
    title_bytes = title.encode('utf-8')
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
    mobi += struct.pack('>I', first_image if first_image >= 0 else FF)  # +92: first_image_index
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
    mobi += struct.pack('>I', ncx_idx if ncx_idx >= 0 else FF)  # +228: INDX record
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
    name = ''.join(c if 32 <= ord(c) < 128 else '_' for c in title).replace(' ', '_')
    palm_name = name[:31].encode('ascii').ljust(32, b'\x00')

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
    doc.metadata['title'] = doc.metadata.get('title') or path.stem

    image_records, cover_off, thumb_off, recindex = _prepare_image_records(doc, inline=True)
    num_images = len(image_records)

    def img_tag(name):
        """MOBI6 references an image by its 1-based index among the image records."""
        index = recindex.get(name)
        return f'<img recindex="{index:05d}"></img>' if index else None

    html_str, toc_entries, text_start = _doc_to_html(doc, img_ref=img_tag)
    html_bytes = html_str.encode('utf-8')

    chunks = [html_bytes[i:i + 4096] for i in range(0, max(len(html_bytes), 1), 4096)]
    compressed = [_palmdoc_compress(c) for c in chunks]
    num_text = len(compressed)

    ncx_indx = _build_ncx_indx(toc_entries)

    layout = _mobi_record_layout(num_text, num_images, len(ncx_indx))

    title = doc.metadata.get('title', 'Unknown')
    author = doc.metadata.get('author', '')
    language = doc.metadata.get('language', 'en')
    exth = _build_exth(title, author, language, metadata=doc.metadata,
                       cover_offset=cover_off, thumb_offset=thumb_off,
                       num_images=num_images, text_start=text_start)

    rec0 = _build_record0(doc, len(html_bytes), num_text,
                           layout['flis_idx'], layout['fcis_idx'], exth,
                           first_image=layout['first_image'],
                           ncx_idx=layout['ncx_idx'])

    all_records = [rec0]
    all_records.extend(compressed)
    all_records.extend(image_records)
    all_records.extend(ncx_indx)
    all_records.extend([_FLIS, _build_fcis(len(html_bytes)), _EOF])

    assert len(all_records) == layout['total'], \
        f"Record count mismatch: {len(all_records)} != {layout['total']}"

    return _write_palmdb(path, all_records, title)
