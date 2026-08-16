"""AZW3/KF8 format converter - native KF8 implementation for Kindle."""

import html as _html
import random
import struct
import time
from collections import namedtuple
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

from convertext.converters.readers import read_html, read_markdown, read_txt
from convertext.converters.base import BaseConverter, Document
from convertext.converters.ebooks.palmdoc import (
    palmdoc_compress as _palmdoc_compress, palmdoc_decompress,
    FLIS as _FLIS, EOF as _EOF,
)
from convertext.converters.ebooks.htmlbuild import block_to_html

ChunkInfo = namedtuple('ChunkInfo', 'pre_start pre_length insert_offset content_start content_length')

class Azw3Converter(BaseConverter):
    """Read AZW3/AZW/MOBI files - native PDB/MOBI parser."""

    @property
    def input_formats(self) -> List[str]:
        return ['azw3', 'azw', 'mobi']

    @property
    def output_formats(self) -> List[str]:
        return ['txt', 'html', 'md']

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        doc = self._read_azw3(source_path, config)
        self._apply_metadata_overrides(doc, source_path, config)

        target_fmt = target_path.suffix.lstrip('.').lower()
        if target_fmt == 'txt':
            return self._write_txt(doc, target_path)
        elif target_fmt == 'html':
            return self._write_html(doc, target_path)
        elif target_fmt == 'md':
            return self._write_md(doc, target_path)

        return False

    def _read_azw3(self, path: Path, config: Dict[str, Any]) -> Document:
        """Read AZW3/MOBI file - native PDB parser."""
        doc = Document()

        with open(path, 'rb') as f:
            f.seek(76)
            num_records = struct.unpack('>H', f.read(2))[0]

            f.seek(78)
            records = []
            for _ in range(num_records):
                offset = struct.unpack('>I', f.read(4))[0]
                records.append(offset)
                f.read(4)

            f.seek(records[0])
            rec0_size = records[1] - records[0] if len(records) > 1 else 1024
            rec0 = f.read(rec0_size)

            compression = struct.unpack('>H', rec0[0:2])[0]
            text_length = struct.unpack('>I', rec0[4:8])[0]
            num_text_records = struct.unpack('>H', rec0[8:10])[0]

            mobi_header_len = struct.unpack('>I', rec0[20:24])[0]
            encoding_val = struct.unpack('>I', rec0[28:32])[0]

            extra_data_flags = 0
            if mobi_header_len >= 228 and len(rec0) >= 244:
                extra_data_flags = struct.unpack('>I', rec0[240:244])[0]

            exth_flags = struct.unpack('>I', rec0[128:132])[0]
            if exth_flags & 0x40:
                exth_offset = 16 + mobi_header_len
                if exth_offset + 12 <= len(rec0) and rec0[exth_offset:exth_offset+4] == b'EXTH':
                    exth_len = struct.unpack('>I', rec0[exth_offset+4:exth_offset+8])[0]
                    exth_count = struct.unpack('>I', rec0[exth_offset+8:exth_offset+12])[0]
                    pos = exth_offset + 12
                    for _ in range(exth_count):
                        if pos + 8 > len(rec0):
                            break
                        rec_type = struct.unpack('>I', rec0[pos:pos+4])[0]
                        rec_len = struct.unpack('>I', rec0[pos+4:pos+8])[0]
                        rec_data = rec0[pos+8:pos+rec_len]
                        if rec_type == 100:
                            doc.metadata['author'] = rec_data.decode('utf-8', errors='ignore')
                        elif rec_type == 503:
                            doc.metadata['title'] = rec_data.decode('utf-8', errors='ignore')
                        pos += rec_len

            file_size = path.stat().st_size
            raw_parts = []
            for i in range(1, num_text_records + 1):
                if i >= len(records):
                    break

                start = records[i]
                end = records[i + 1] if i + 1 < len(records) else file_size
                f.seek(start)
                record_data = f.read(end - start)

                # Strip trailing bytes per extra_data_flags bits (sequential, high
                # bits first). Note: this stripper only handles up to 2-byte sizes.
                n = 0
                for bit in range(15, 0, -1):
                    if extra_data_flags & (1 << bit):
                        b = record_data[-1 - n]
                        sz = b & 0x7f
                        if not (b & 0x80):
                            sz = (sz << 7) | (record_data[-2 - n] & 0x7f)
                            n += 1
                        n += sz + 1
                if extra_data_flags & 1:
                    b = record_data[-1 - n]
                    n += (b & 3) + 1
                if n:
                    record_data = record_data[:-n]

                try:
                    if compression == 2:
                        raw_parts.append(self._palmdoc_decompress(record_data))
                    else:
                        raw_parts.append(record_data)
                except Exception:
                    continue

            html_content = b''.join(raw_parts).decode('utf-8', errors='ignore')
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            title_tag = soup.find('title')
            if title_tag and not doc.metadata.get('title'):
                doc.metadata['title'] = title_tag.get_text()

            for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                if element.name.startswith('h'):
                    level = int(element.name[1])
                    text = element.get_text().strip()
                    if text:
                        doc.add_heading(text, level)
                elif element.name == 'p':
                    text = element.get_text().strip()
                    if text:
                        doc.add_paragraph(text)

        return doc

    def _palmdoc_decompress(self, data: bytes) -> bytes:
        """Decompress PalmDOC compressed data."""
        return palmdoc_decompress(data)

    def _write_txt(self, doc: Document, path: Path) -> bool:
        with open(path, 'w', encoding='utf-8') as f:
            if doc.metadata.get('title'):
                f.write(doc.metadata['title'] + '\n')
                f.write('=' * len(doc.metadata['title']) + '\n\n')
            if doc.metadata.get('author'):
                f.write(f"By: {doc.metadata['author']}\n\n")

            for block in doc.content:
                if block['type'] in ['text', 'paragraph']:
                    f.write(block['data'] + '\n\n')
                elif block['type'] == 'heading':
                    f.write('\n' + block['data'].upper() + '\n')
                    f.write('-' * len(block['data']) + '\n\n')
        return True

    def _write_html(self, doc: Document, path: Path) -> bool:
        html_parts = [
            '<!DOCTYPE html>', '<html>', '<head>', '<meta charset="utf-8">',
        ]

        if doc.metadata.get('title'):
            html_parts.append(f"<title>{_esc(doc.metadata['title'])}</title>")
        else:
            html_parts.append('<title>Document</title>')

        html_parts.append('</head>')
        html_parts.append('<body>')

        if doc.metadata.get('title'):
            html_parts.append(f"<h1>{_esc(doc.metadata['title'])}</h1>")
        if doc.metadata.get('author'):
            html_parts.append(f"<p><em>By {_esc(doc.metadata['author'])}</em></p>")

        for block in doc.content:
            if block['type'] == 'paragraph':
                html_parts.append(f"<p>{_esc(block['data'])}</p>")
            elif block['type'] == 'heading':
                level = block['level']
                html_parts.append(f"<h{level}>{_esc(block['data'])}</h{level}>")

        html_parts.append('</body>')
        html_parts.append('</html>')

        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html_parts))

        return True

    def _write_md(self, doc: Document, path: Path) -> bool:
        with open(path, 'w', encoding='utf-8') as f:
            if doc.metadata.get('title'):
                f.write(f"# {doc.metadata['title']}\n\n")
            if doc.metadata.get('author'):
                f.write(f"**Author:** {doc.metadata['author']}\n\n")

            for block in doc.content:
                if block['type'] == 'paragraph':
                    f.write(block['data'] + '\n\n')
                elif block['type'] == 'heading':
                    f.write('#' * (block['level'] + 1) + ' ' + block['data'] + '\n\n')
        return True

class ToAzw3Converter(BaseConverter):
    """Convert to KF8/AZW3 format for Kindle."""

    @property
    def input_formats(self) -> List[str]:
        return ['txt', 'html', 'htm', 'md', 'epub']

    @property
    def output_formats(self) -> List[str]:
        return ['azw3']

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        source_fmt = source_path.suffix.lstrip('.').lower()

        if source_fmt == 'txt':
            doc = read_txt(source_path, config)
        elif source_fmt in ['html', 'htm']:
            doc = read_html(source_path, config)
        elif source_fmt in ['md', 'markdown']:
            doc = read_markdown(source_path, config)
        elif source_fmt == 'epub':
            from convertext.converters.ebooks.epub import EpubConverter
            doc = EpubConverter()._read_epub(source_path, config)
        else:
            return False
        self._apply_metadata_overrides(doc, source_path, config)

        return self._create_kf8(doc, target_path, target_path.stem)

    def _create_kf8(self, doc: Document, path: Path, default_title: str) -> bool:
        """Create KF8/AZW3 file with proper skeleton/chunk INDX records."""
        title = doc.metadata.get('title', default_title)
        author = doc.metadata.get('author', 'Unknown')
        language = doc.metadata.get('language', 'en').split('-')[0]

        text_data, chunk_infos, toc_entries = _build_kf8_content(doc, title)
        text_length = len(text_data)

        raw_records = _split_text_records(text_data)
        num_text_records = len(raw_records)
        compressed_records = [_palmdoc_compress(rec) + b'\x00' for rec in raw_records]

        image_records, cover_off, thumb_off, _ = _prepare_image_records(doc)
        num_images = len(image_records)

        chunk_indx = _build_chunk_indx(chunk_infos, text_length)
        skel_indx = _build_skel_indx(chunk_infos)
        ncx_indx = _build_ncx_indx(toc_entries)
        guide_indx = _build_guide_indx(0)

        fdst = _build_fdst(text_length)
        fcis = _build_fcis_kf8(text_length)

        # Compute record layout
        layout = _kf8_record_layout(num_text_records, num_images,
                                     len(ncx_indx), len(guide_indx))

        exth = _build_exth(title, author, language, metadata=doc.metadata,
                           cover_offset=cover_off, thumb_offset=thumb_off,
                           num_images=num_images)

        rec0 = _build_record0_kf8(
            text_length, num_text_records, exth, title,
            layout['first_non_text'], layout['chunk_idx'], layout['skel_idx'],
            layout['fdst_idx'], layout['flis_idx'], layout['fcis_idx'],
            first_image=layout['first_image'], ncx_idx=layout['ncx_idx'],
            guide_idx=layout['guide_idx']
        )

        # Collect all records in order
        all_records = [rec0]
        all_records.extend(compressed_records)
        all_records.extend(image_records)
        all_records.extend(chunk_indx)
        all_records.extend(skel_indx)
        all_records.extend(ncx_indx)
        all_records.extend(guide_indx)
        all_records.extend([fdst, _FLIS, fcis, _EOF])

        assert len(all_records) == layout['total'], \
            f"Record count mismatch: {len(all_records)} != {layout['total']}"

        # Calculate record offsets
        base_offset = 78 + layout['total'] * 8 + 2
        offsets = []
        pos = base_offset
        for rec in all_records:
            offsets.append(pos)
            pos += len(rec)

        with open(path, 'wb') as f:
            _write_palmdb_header(f, title, layout['total'], offsets)
            for rec in all_records:
                f.write(rec)

        return True

    def _palmdoc_compress(self, data: bytes) -> bytes:
        return _palmdoc_compress(data)

# --- KF8 helper functions ---

def _esc(text: str) -> str:
    return _html.escape(text, quote=True)

def _encint(value: int) -> bytes:
    """Encode integer as forward VWI (variable width integer). Last byte has bit 7 set."""
    byts = bytearray()
    while True:
        byts.append(value & 0x7F)
        value >>= 7
        if value == 0:
            break
    byts[0] |= 0x80
    byts.reverse()
    return bytes(byts)

def _to_base32(i: int) -> str:
    """Convert integer to 4-digit uppercase base-32 string."""
    digits = "0123456789ABCDEFGHIJKLMNOPQRSTUV"
    if i == 0:
        return "0000"
    result = []
    n = i
    while n > 0:
        result.append(digits[n % 32])
        n //= 32
    return ''.join(reversed(result)).rjust(4, '0')

def _align4(data: bytes) -> bytes:
    extra = len(data) % 4
    if extra == 0:
        return data
    return data + b'\x00' * (4 - extra)

def _to_jpeg(data: bytes, max_size: tuple, quality: int):
    """Re-encode image bytes as a Kindle-safe JPEG; None if unreadable."""
    try:
        from PIL import Image
        img = Image.open(BytesIO(data))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.thumbnail(max_size, Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, 'JPEG', quality=quality)
        return buf.getvalue()
    except Exception:
        return None

def _prepare_image_records(doc: Document, inline: bool = False) -> tuple:
    """Prepare cover, thumbnail and optionally inline image records.

    Returns (records, cover_offset, thumb_offset, recindex_by_name); the
    recindex is the 1-based MOBI image reference for each named inline image.
    """
    records = []
    cover_off = thumb_off = -1

    cover_info = doc.images.get('cover')
    if cover_info:
        cover_jpeg = _to_jpeg(cover_info['data'], (1600, 2400), 80)
        thumb_jpeg = _to_jpeg(cover_info['data'], (330, 470), 60)
        if cover_jpeg and thumb_jpeg:
            records.extend([cover_jpeg, thumb_jpeg])
            cover_off, thumb_off = 0, 1
        else:
            import warnings
            warnings.warn("Cover image could not be processed; book will have no cover")

    recindex = {}
    if inline:
        skipped = 0
        for name, info in doc.images.items():
            if name == 'cover':
                continue
            jpeg = _to_jpeg(info.get('data', b''), (1200, 1600), 75)
            if jpeg is None:
                skipped += 1
                continue
            recindex[name] = len(records) + 1  # MOBI recindex is 1-based
            records.append(jpeg)
        if skipped:
            import warnings
            warnings.warn(f"{skipped} inline image(s) could not be processed and were skipped")

    return records, cover_off, thumb_off, recindex

def _split_text_records(text_data: bytes) -> list:
    """Split text into 4096-byte records at UTF-8 character boundaries."""
    records = []
    i = 0
    while i < len(text_data):
        end = min(i + 4096, len(text_data))
        if end < len(text_data):
            while end > i and (text_data[end] & 0xC0) == 0x80:
                end -= 1
        records.append(text_data[i:end])
        i = end
    return records if records else [b'']

def _build_kf8_content(doc: Document, title: str):
    """Build KF8 text stream with skeleton/chunk structure.

    Each h1-delimited section becomes a separate chunk with its own skeleton.
    Returns (text_bytes, list_of_ChunkInfo, toc_entries).
    """
    # Split into chunks, tracking each chunk's chapter title (None for a
    # titleless preamble of blocks preceding the first h1).
    chunks = []
    current = []
    current_title = None
    for block in doc.content:
        if block['type'] == 'heading' and block['level'] == 1:
            if current:
                chunks.append((current_title, current))
            current = [block]
            current_title = block['data']
        else:
            current.append(block)
    if current:
        chunks.append((current_title, current))
    if not chunks:
        chunks = [(None, [{'type': 'paragraph', 'data': ' '}])]

    text_parts = []
    chunk_infos = []
    toc_entries = []
    offset = 0

    for i, (chapter_title, blocks) in enumerate(chunks):
        aid = _to_base32(i)
        skeleton = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<html xmlns="http://www.w3.org/1999/xhtml">'
            '<head>'
            '<meta content="text/html; charset=utf-8" http-equiv="Content-Type"/>'
            f'<title>{_esc(title)}</title>'
            '</head>'
            f'<body aid="{aid}">'
            '</body>'
            '</html>'
        ).encode('utf-8')

        body_parts = []
        for block in blocks:
            frag = block_to_html(block)
            if frag:
                body_parts.append(frag)
        body = ''.join(body_parts).encode('utf-8')

        pre_start = offset
        pre_length = len(skeleton)
        insert_offset = pre_length - len(b'</body></html>')
        content_start = offset + pre_length
        content_length = len(body)

        chunk_infos.append(ChunkInfo(pre_start, pre_length, insert_offset, content_start, content_length))
        if chapter_title is not None:
            toc_entries.append({'label': chapter_title, 'offset': pre_start,
                                'length': pre_length + content_length})
        text_parts.append(skeleton)
        text_parts.append(body)
        offset += pre_length + content_length

    return b''.join(text_parts), chunk_infos, toc_entries

def _build_tagx(tags: list, control_byte_count: int = 1) -> bytes:
    """Build TAGX block. tags: list of (tag_number, values_per_entry, bitmask, end_flag)."""
    tag_data = b''
    for tag, vpe, mask, end in tags:
        tag_data += struct.pack('BBBB', tag, vpe, mask, end)
    length = 12 + len(tag_data)
    return b'TAGX' + struct.pack('>II', length, control_byte_count) + tag_data

def _build_indx_header(tagx: bytes, last_key: str, entry_count: int,
                        total_entries: int, num_cncx: int = 0) -> bytes:
    """Build INDX header record (192-byte header + TAGX + geometry + IDXT)."""
    header = bytearray(192)
    header[0:4] = b'INDX'
    struct.pack_into('>I', header, 4, 192)
    struct.pack_into('>I', header, 16, 2)            # index header marker (Calibre puts it here)
    struct.pack_into('>I', header, 24, 1)            # num data records = 1
    struct.pack_into('>I', header, 28, 65001)        # UTF-8
    struct.pack_into('>I', header, 32, 0xFFFFFFFF)
    struct.pack_into('>I', header, 36, total_entries)
    struct.pack_into('>I', header, 52, num_cncx)
    struct.pack_into('>I', header, 180, 192)         # tagx offset

    tagx_aligned = _align4(tagx)

    # Geometry: [1 byte len][key bytes][2 bytes entry count][padding]
    key_bytes = last_key.encode('utf-8')
    geo_entry = struct.pack('B', len(key_bytes)) + key_bytes + struct.pack('>H', entry_count)
    geo_aligned = _align4(geo_entry)

    # IDXT: "IDXT" + uint16 offset to geometry entry
    geo_offset = 192 + len(tagx_aligned)
    idxt = b'IDXT' + struct.pack('>H', geo_offset)
    idxt = _align4(idxt)

    # Fill idxt_offset
    idxt_offset = 192 + len(tagx_aligned) + len(geo_aligned)
    struct.pack_into('>I', header, 20, idxt_offset)

    return bytes(header) + tagx_aligned + geo_aligned + idxt

def _build_indx_data(entries: list) -> bytes:
    """Build INDX data record (192-byte header + entries + IDXT)."""
    header = bytearray(192)
    header[0:4] = b'INDX'
    struct.pack_into('>I', header, 4, 192)
    struct.pack_into('>I', header, 8, 0)             # type = data record
    struct.pack_into('>I', header, 24, len(entries))
    header[28:36] = b'\xFF' * 8

    # Entry data
    entry_data = b''.join(entries)
    entry_aligned = _align4(entry_data)

    # IDXT offsets
    idxt = b'IDXT'
    pos = 192
    for entry in entries:
        idxt += struct.pack('>H', pos)
        pos += len(entry)
    idxt = _align4(idxt)

    idxt_offset = 192 + len(entry_aligned)
    struct.pack_into('>I', header, 20, idxt_offset)

    return bytes(header) + entry_aligned + idxt

def _build_cncx(strings: list):
    """Build CNCX record. Returns (record_bytes, list_of_offsets)."""
    data = bytearray()
    offsets = []
    for s in strings:
        offsets.append(len(data))
        encoded = s.encode('utf-8')[:500]
        data += _encint(len(encoded))
        data += encoded
    return _align4(bytes(data)), offsets

def _build_skel_indx(chunk_infos: list) -> list:
    """Build skeleton INDX records: [header_record, data_record]."""
    skel_tags = [(1, 1, 1, 0), (6, 2, 2, 0), (0, 0, 0, 1)]
    tagx = _build_tagx(skel_tags)

    entries = []
    for i, ci in enumerate(chunk_infos):
        label = f'SKEL{i:010d}'
        label_enc = struct.pack('B', len(label)) + label.encode('ascii')
        cb = b'\x03'
        vals = (
            _encint(1) +                 # tag1: chunk_count
            _encint(ci.pre_start) +      # tag6: skeleton rawml offset
            _encint(ci.pre_length)       # tag6: skeleton rawml length
        )
        entries.append(label_enc + cb + vals)

    last_key = f'SKEL{len(chunk_infos)-1:010d}'
    header_rec = _build_indx_header(tagx, last_key, len(entries), len(entries), num_cncx=0)
    data_rec = _build_indx_data(entries)
    return [header_rec, data_rec]

def _build_chunk_indx(chunk_infos: list, text_length: int) -> list:
    """Build chunk INDX records: [header_record, data_record, cncx_record]."""
    chunk_tags = [(2, 1, 1, 0), (3, 1, 2, 0), (4, 1, 4, 0), (6, 2, 8, 0), (0, 0, 0, 1)]
    tagx = _build_tagx(chunk_tags)

    cncx_strings = [f"P-//*[@aid='{_to_base32(i)}']" for i in range(len(chunk_infos))]
    cncx_rec, cncx_offsets = _build_cncx(cncx_strings)

    entries = []
    for i, ci in enumerate(chunk_infos):
        label = f'{ci.content_start:010d}'
        label_enc = struct.pack('B', len(label)) + label.encode('ascii')
        # All 4 tags are single-bit masks, so 0x0F = all present with 1 entry each
        cb = b'\x0F'
        vals = (
            _encint(cncx_offsets[i]) +     # cncx_offset
            _encint(i) +                    # file_number (skeleton index)
            _encint(0) +                    # sequence_number (first chunk in skeleton)
            _encint(ci.insert_offset) +    # insertion point within skeleton
            _encint(ci.content_length)     # length of content to insert from rawml
        )
        entries.append(label_enc + cb + vals)

    last_key = f'{chunk_infos[-1].content_start:010d}'
    header_rec = _build_indx_header(tagx, last_key, len(entries), len(entries), num_cncx=1)
    data_rec = _build_indx_data(entries)
    return [header_rec, data_rec, cncx_rec]

def _build_fdst(text_length: int) -> bytes:
    """Build FDST record with single flow entry."""
    return b'FDST' + struct.pack('>III', 12, 1, 0) + struct.pack('>I', text_length)

def _build_fcis_kf8(text_length: int) -> bytes:
    """Build FCIS record for KF8 (52 bytes, matching Calibre's output exactly)."""
    return (b'FCIS\x00\x00\x00\x14\x00\x00\x00\x10'
            b'\x00\x00\x00\x02\x00\x00\x00\x00'
            + struct.pack('>I', text_length)
            + b'\x00\x00\x00\x00\x00\x00\x00\x28'
            b'\x00\x00\x00\x00\x00\x00\x00\x28'
            b'\x00\x00\x00\x08\x00\x01\x00\x01\x00\x00\x00\x00')

def _kf8_record_layout(num_text, num_images, ncx_count, guide_count):
    """Compute all record indices for KF8 file layout."""
    i = num_text + 1
    first_image = i if num_images else -1
    i += num_images
    chunk_idx = i; i += 3        # header + data + cncx
    skel_idx = i; i += 2         # header + data
    ncx_idx = i if ncx_count else -1
    i += ncx_count
    guide_idx = i if guide_count else -1
    i += guide_count
    fdst_idx = i; i += 1
    flis_idx = i; i += 1
    fcis_idx = i; i += 1
    total = i + 1                # +1 for EOF
    return {
        'first_non_text': num_text + 1, 'first_image': first_image,
        'chunk_idx': chunk_idx, 'skel_idx': skel_idx,
        'ncx_idx': ncx_idx, 'guide_idx': guide_idx,
        'fdst_idx': fdst_idx, 'flis_idx': flis_idx, 'fcis_idx': fcis_idx,
        'total': total,
    }

def _build_ncx_indx(toc_entries: list) -> list:
    """Build NCX INDX records for Kindle chapter navigation.
    Returns [header_rec, data_rec, cncx_rec] or [] if no entries."""
    if not toc_entries:
        return []

    ncx_tags = [
        (1, 1, 1, 0),   # byte offset in rawML
        (2, 1, 2, 0),   # section length
        (3, 1, 4, 0),   # CNCX label offset
        (4, 1, 8, 0),   # depth (always 0 for flat TOC)
        (0, 0, 0, 1),
    ]
    tagx = _build_tagx(ncx_tags)

    labels = [e['label'] for e in toc_entries]
    cncx_rec, cncx_offsets = _build_cncx(labels)

    entries = []
    for i, e in enumerate(toc_entries):
        key = f'{i:03d}'
        key_enc = struct.pack('B', len(key)) + key.encode('ascii')
        cb = b'\x0F'  # all 4 tags present
        vals = (
            _encint(e['offset']) +
            _encint(e['length']) +
            _encint(cncx_offsets[i]) +
            _encint(0)  # depth = 0
        )
        entries.append(key_enc + cb + vals)

    last_key = f'{len(toc_entries)-1:03d}'
    header_rec = _build_indx_header(tagx, last_key, len(entries), len(entries), num_cncx=1)
    data_rec = _build_indx_data(entries)
    return [header_rec, data_rec, cncx_rec]

def _build_guide_indx(text_start_offset: int) -> list:
    """Build guide INDX with 'text' entry pointing to start of content."""
    guide_tags = [(1, 1, 1, 0), (0, 0, 0, 1)]
    tagx = _build_tagx(guide_tags)

    key = 'text'
    key_enc = struct.pack('B', len(key)) + key.encode('ascii')
    entry = key_enc + b'\x01' + _encint(text_start_offset)

    header_rec = _build_indx_header(tagx, key, 1, 1, num_cncx=0)
    data_rec = _build_indx_data([entry])
    return [header_rec, data_rec]

def _write_palmdb_header(f, title: str, total_records: int, offsets: list):
    """Write 78-byte PalmDB header + record info list + 2-byte gap."""
    name = ''.join(c if 32 <= ord(c) < 128 else '_' for c in title).replace(' ', '_')
    f.write(name[:31].encode('ascii').ljust(32, b'\x00'))

    now = int(time.time()) + 2082844800  # PalmOS epoch (1904-01-01)
    f.write(struct.pack('>HH', 0, 0))
    f.write(struct.pack('>III', now, now, 0))
    f.write(struct.pack('>III', 0, 0, 0))
    f.write(b'BOOKMOBI')
    f.write(struct.pack('>I', (2 * total_records) - 1))
    f.write(struct.pack('>IH', 0, total_records))

    for i, off in enumerate(offsets):
        f.write(struct.pack('>I', off))
        f.write(b'\x00' + struct.pack('>I', 2 * i)[1:])

    f.write(b'\x00\x00')

def _build_record0_kf8(text_length: int, num_text_records: int, exth: bytes,
                         title: str, first_non_text: int, chunk_idx: int,
                         skel_idx: int, fdst_idx: int, flis_idx: int,
                         fcis_idx: int, first_image: int = -1,
                         ncx_idx: int = -1, guide_idx: int = -1) -> bytes:
    """Build record 0: PalmDOC (16B) + KF8 MOBI header (264B) + EXTH + title."""
    title_bytes = title.encode('utf-8')
    mobi_len = 264
    title_offset = 16 + mobi_len + len(exth)
    uid = random.randint(0, 0xFFFFFFFF)

    h = bytearray()

    # PalmDOC header (16 bytes, offsets 0x00-0x0F)
    h += struct.pack('>H', 2)                           # 0x00: compression = PalmDOC
    h += struct.pack('>H', 0)                           # 0x02: unused
    h += struct.pack('>I', text_length)                 # 0x04: text length
    h += struct.pack('>H', num_text_records)            # 0x08: text record count
    h += struct.pack('>H', 4096)                        # 0x0A: record size
    h += struct.pack('>HH', 0, 0)                       # 0x0C: no encryption

    # MOBI KF8 header (264 bytes, offsets 0x10-0x117)
    h += b'MOBI'                                        # 0x10: magic
    h += struct.pack('>I', mobi_len)                    # 0x14: header length = 264
    h += struct.pack('>I', 2)                           # 0x18: type = book
    h += struct.pack('>I', 65001)                       # 0x1C: encoding = UTF-8
    h += struct.pack('>I', uid)                         # 0x20: unique ID
    h += struct.pack('>I', 8)                           # 0x24: version = 8 (KF8)
    h += b'\xff' * 40                                   # 0x28-0x4F: unused indices
    h += struct.pack('>I', first_non_text)              # 0x50: first non-book record
    h += struct.pack('>I', title_offset)                # 0x54: full name offset
    h += struct.pack('>I', len(title_bytes))            # 0x58: full name length
    h += struct.pack('>I', 9)                           # 0x5C: locale = English
    h += struct.pack('>II', 0, 0)                       # 0x60: input/output language
    h += struct.pack('>I', 8)                           # 0x68: min version = 8
    h += struct.pack('>I', first_image if first_image >= 0 else 0xFFFFFFFF)  # 0x6C: first image
    h += b'\x00' * 16                                   # 0x70-0x7F: huffman
    h += struct.pack('>I', 0x40)                        # 0x80: EXTH flags (has EXTH)
    h += b'\x00' * 32                                   # 0x84-0xA3: unknown
    h += struct.pack('>I', 0xFFFFFFFF)                  # 0xA4: unknown
    h += struct.pack('>I', 0xFFFFFFFF)                  # 0xA8: DRM offset (none)
    h += struct.pack('>I', 0)                           # 0xAC: DRM count
    h += struct.pack('>I', 0)                           # 0xB0: DRM size
    h += struct.pack('>I', 0)                           # 0xB4: DRM flags
    h += b'\x00' * 8                                    # 0xB8-0xBF: unknown
    # KF8-specific fields
    h += struct.pack('>I', fdst_idx)                    # 0xC0: FDST record index
    h += struct.pack('>I', 1)                           # 0xC4: FDST flow count
    h += struct.pack('>I', fcis_idx)                    # 0xC8: FCIS record
    h += struct.pack('>I', 1)                           # 0xCC: FCIS count
    h += struct.pack('>I', flis_idx)                    # 0xD0: FLIS record
    h += struct.pack('>I', 1)                           # 0xD4: FLIS count
    h += b'\x00' * 8                                    # 0xD8-0xDF: unknown
    h += struct.pack('>I', 0xFFFFFFFF)                  # 0xE0: SRCS (none)
    h += struct.pack('>I', 0)                           # 0xE4: SRCS count
    h += struct.pack('>II', 0xFFFFFFFF, 0xFFFFFFFF)     # 0xE8-0xEF: unknown
    h += struct.pack('>I', 1)                           # 0xF0: extra data flags (overlap byte per record)
    h += struct.pack('>I', ncx_idx if ncx_idx >= 0 else 0xFFFFFFFF)  # 0xF4: NCX index
    h += struct.pack('>I', chunk_idx)                   # 0xF8: chunk index
    h += struct.pack('>I', skel_idx)                    # 0xFC: skeleton index
    h += struct.pack('>I', 0xFFFFFFFF)                  # 0x100: DATP (none)
    h += struct.pack('>I', guide_idx if guide_idx >= 0 else 0xFFFFFFFF)  # 0x104: guide
    # 16 bytes of trailing unknowns to reach 264-byte MOBI header
    h += struct.pack('>I', 0xFFFFFFFF)                  # 0x108: unknown5
    h += struct.pack('>I', 0)                           # 0x10C: unknown6
    h += struct.pack('>I', 0xFFFFFFFF)                  # 0x110: unknown7
    h += struct.pack('>I', 0)                           # 0x114: unknown8

    assert len(h) == 16 + 264, f"Header size {len(h)}, expected {16 + 264}"

    h += exth
    h += title_bytes
    # Pad to 8192 bytes after title for Kindle firmware compatibility
    # (Calibre uses the same 8KB padding — firmware may assume minimum rec0 size)
    current_len = len(h)
    target_len = max(current_len, 16 + mobi_len) + 8192
    h += b'\x00' * (target_len - len(h))

    return bytes(h)

def _build_exth(title: str, author: str, language: str = 'en',
                metadata: dict = None, cover_offset: int = -1,
                thumb_offset: int = -1, num_images: int = 0) -> bytes:
    """Build EXTH header with KF8-compatible metadata."""
    metadata = metadata or {}

    def rec(code, payload):
        return struct.pack('>II', code, 8 + len(payload)) + payload

    records = [
        rec(100, author.encode('utf-8')),
        rec(204, struct.pack('>I', 202)),               # creator software = kindlegen Mac
        rec(205, struct.pack('>I', 2)),                 # creator major
        rec(206, struct.pack('>I', 9)),                 # creator minor
        rec(207, struct.pack('>I', 0)),                 # creator build
        rec(501, b'EBOK'),                              # CDE type
        rec(503, title.encode('utf-8')),
        rec(524, language.encode('utf-8')),
        rec(528, b'true'),                              # override_kindle_fonts
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

    data = b''.join(records)
    raw_len = 12 + len(data)
    padding = (4 - (raw_len % 4)) % 4

    result = b'EXTH'
    result += struct.pack('>I', raw_len + padding)
    result += struct.pack('>I', len(records))
    result += data
    result += b'\x00' * padding

    return result

