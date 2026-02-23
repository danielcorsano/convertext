"""AZW3/KF8 format converter - native KF8 implementation for Kindle."""

from pathlib import Path
from typing import Any, Dict, List
from collections import namedtuple
import struct
import random
import time

from convertext.converters.base import BaseConverter, Document

_FLIS = (b'FLIS\x00\x00\x00\x08\x00\x41\x00\x00\x00\x00\x00\x00'
         b'\xff\xff\xff\xff\x00\x01\x00\x03\x00\x00\x00\x03'
         b'\x00\x00\x00\x01\xff\xff\xff\xff')

_EOF = b'\xe9\x8e\x0d\x0a'

ChunkInfo = namedtuple('ChunkInfo', 'pre_start pre_length content_start content_length')


class Azw3Converter(BaseConverter):
    """Read AZW3/AZW/MOBI files - native PDB/MOBI parser."""

    @property
    def input_formats(self) -> List[str]:
        return ['azw3', 'azw', 'mobi']

    @property
    def output_formats(self) -> List[str]:
        return ['txt', 'html', 'md']

    def can_convert(self, source: str, target: str) -> bool:
        return source in self.input_formats and target in self.output_formats

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
            if len(rec0) >= 244:
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

            html_parts = []
            for i in range(1, num_text_records + 1):
                if i >= len(records) - 1:
                    break

                f.seek(records[i])
                record_data = f.read(records[i + 1] - records[i])

                # Strip trailing bytes per extra_data_flags bits (sequential, high bits first)
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
                        text = self._palmdoc_decompress(record_data)
                    else:
                        text = record_data
                    html_parts.append(text.decode('utf-8', errors='ignore'))
                except Exception:
                    continue

            html_content = ''.join(html_parts)
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
                    pair = ((c << 8) | c2) & 0x3FFF
                    length = (pair & 7) + 3
                    dist = (pair >> 3) + 1
                    start = len(result) - dist
                    if start >= 0:
                        for _ in range(length):
                            if start < len(result):
                                result.append(result[start])
                                start += 1

        return bytes(result)

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
        return ['txt', 'html', 'md', 'epub']

    @property
    def output_formats(self) -> List[str]:
        return ['azw3', 'mobi']

    def can_convert(self, source: str, target: str) -> bool:
        return source in self.input_formats and target in self.output_formats

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        source_fmt = source_path.suffix.lstrip('.').lower()

        if source_fmt == 'txt':
            doc = self._read_txt(source_path, config)
        elif source_fmt in ['html', 'htm']:
            doc = self._read_html(source_path, config)
        elif source_fmt in ['md', 'markdown']:
            doc = self._read_markdown(source_path, config)
        elif source_fmt == 'epub':
            from convertext.converters.ebooks.epub import EpubConverter
            doc = EpubConverter()._read_epub(source_path, config)
        else:
            return False
        self._apply_metadata_overrides(doc, source_path, config)

        return self._create_kf8(doc, target_path, target_path.stem)

    def _read_txt(self, path: Path, config: Dict[str, Any]) -> Document:
        doc = Document()
        encoding = config.get('documents', {}).get('encoding', 'utf-8')

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

        remaining = '\n'.join(lines[i:])
        for para in remaining.split('\n\n'):
            if para.strip():
                doc.add_paragraph(para.strip())

        return doc

    def _read_html(self, path: Path, config: Dict[str, Any]) -> Document:
        doc = Document()
        encoding = config.get('documents', {}).get('encoding', 'utf-8')

        with open(path, 'r', encoding=encoding) as f:
            content = f.read()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')

        title_tag = soup.find('title')
        if title_tag and title_tag.get_text().strip():
            doc.metadata['title'] = title_tag.get_text().strip()
        else:
            h1_tag = soup.find('h1')
            if h1_tag and h1_tag.get_text().strip():
                doc.metadata['title'] = h1_tag.get_text().strip()

        for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            if element.name.startswith('h'):
                level = int(element.name[1])
                doc.add_heading(element.get_text().strip(), level)
            elif element.name == 'p':
                text = element.get_text().strip()
                if text:
                    doc.add_paragraph(text)

        return doc

    def _read_markdown(self, path: Path, config: Dict[str, Any]) -> Document:
        doc = Document()
        encoding = config.get('documents', {}).get('encoding', 'utf-8')

        with open(path, 'r', encoding=encoding) as f:
            content = f.read()

        import markdown
        from bs4 import BeautifulSoup
        html_content = markdown.markdown(content)
        soup = BeautifulSoup(html_content, 'html.parser')

        for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            if element.name.startswith('h'):
                level = int(element.name[1])
                doc.add_heading(element.get_text(), level)
            elif element.name == 'p':
                doc.add_paragraph(element.get_text())

        return doc

    def _create_kf8(self, doc: Document, path: Path, default_title: str) -> bool:
        """Create KF8/AZW3 file with proper skeleton/chunk INDX records."""
        title = doc.metadata.get('title', default_title)
        author = doc.metadata.get('author', 'Unknown')
        language = doc.metadata.get('language', 'en').split('-')[0]  # normalize e.g. en-US → en

        text_data, chunk_infos = _build_kf8_content(doc, title)
        text_length = len(text_data)

        raw_records = _split_text_records(text_data)
        num_text_records = len(raw_records)

        compressed_records = []
        for rec in raw_records:
            compressed_records.append(_palmdoc_compress(rec) + b'\x00')

        chunk_indx = _build_chunk_indx(chunk_infos, text_length)
        skel_indx = _build_skel_indx(chunk_infos)

        fdst = _build_fdst(text_length)
        fcis = _build_fcis_kf8(text_length)
        exth = _build_exth(title, author, language)

        # Record layout: rec0 + text(N) + chunk_indx(3) + skel_indx(2) + fdst + flis + fcis + eof
        chunk_idx = num_text_records + 1
        skel_idx = num_text_records + 4
        fdst_idx = num_text_records + 6
        flis_idx = num_text_records + 7
        fcis_idx = num_text_records + 8
        first_non_text = num_text_records + 1
        total_records = num_text_records + 10

        rec0 = _build_record0_kf8(
            text_length, num_text_records, exth, title,
            first_non_text, chunk_idx, skel_idx, fdst_idx, flis_idx, fcis_idx
        )

        # Collect all records in order
        all_records = [rec0]
        all_records.extend(compressed_records)
        for r in chunk_indx:
            all_records.append(r)
        for r in skel_indx:
            all_records.append(r)
        all_records.extend([fdst, _FLIS, fcis, _EOF])

        assert len(all_records) == total_records, \
            f"Record count mismatch: {len(all_records)} != {total_records}"

        # Calculate record offsets
        base_offset = 78 + total_records * 8 + 2
        offsets = []
        pos = base_offset
        for rec in all_records:
            offsets.append(pos)
            pos += len(rec)

        with open(path, 'wb') as f:
            _write_palmdb_header(f, title, total_records, offsets)
            for rec in all_records:
                f.write(rec)

        return True

    def _palmdoc_compress(self, data: bytes) -> bytes:
        return _palmdoc_compress(data)


# --- KF8 helper functions ---

def _esc(text: str) -> str:
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))


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
    Returns (text_bytes, list_of_ChunkInfo).
    """
    chunks_content = []
    current = []
    for block in doc.content:
        if block['type'] == 'heading' and block['level'] == 1:
            if current:
                chunks_content.append(current)
            current = [block]
        else:
            current.append(block)
    if current:
        chunks_content.append(current)
    if not chunks_content:
        chunks_content = [[{'type': 'paragraph', 'data': ' '}]]

    text_parts = []
    chunk_infos = []
    offset = 0

    for i, blocks in enumerate(chunks_content):
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
            if block['type'] in ('paragraph', 'text'):
                body_parts.append(f'<p>{_esc(block["data"])}</p>')
            elif block['type'] == 'heading':
                level = block['level']
                body_parts.append(f'<h{level}>{_esc(block["data"])}</h{level}>')
        body = ''.join(body_parts).encode('utf-8')

        pre_start = offset
        pre_length = len(skeleton)
        content_start = offset + pre_length
        content_length = len(body)

        chunk_infos.append(ChunkInfo(pre_start, pre_length, content_start, content_length))
        text_parts.append(skeleton)
        text_parts.append(body)
        offset += pre_length + content_length

    return b''.join(text_parts), chunk_infos


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
    struct.pack_into('>I', header, 16, 2)            # type = index header
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
    struct.pack_into('>I', header, 12, 1)            # header type = data
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
    skel_tags = [(1, 1, 3, 0), (6, 2, 12, 0), (0, 0, 0, 1)]
    tagx = _build_tagx(skel_tags)

    entries = []
    for i, ci in enumerate(chunk_infos):
        label = f'SKEL{i:010d}'
        label_enc = struct.pack('B', len(label)) + label.encode('ascii')
        cb = b'\x0F'
        vals = (
            _encint(1) + _encint(1) +                           # chunk_count doubled
            _encint(ci.pre_start) + _encint(ci.pre_length) +    # geometry doubled
            _encint(ci.pre_start) + _encint(ci.pre_length)
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
            _encint(i) +                    # sequence_number
            _encint(ci.content_start) +     # geometry start = absolute offset in rawML
            _encint(ci.content_length)      # geometry length
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


def _write_palmdb_header(f, title: str, total_records: int, offsets: list):
    """Write 78-byte PalmDB header + record info list + 2-byte gap."""
    name = ''.join(c if 32 <= ord(c) < 128 else '_' for c in title).replace(' ', '_')
    f.write(name[:31].encode('ascii').ljust(32, b'\x00'))

    now = int(time.time())
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
                         fcis_idx: int) -> bytes:
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
    h += struct.pack('>I', 1033)                        # 0x5C: locale = en-US
    h += struct.pack('>II', 0, 0)                       # 0x60: input/output language
    h += struct.pack('>I', 8)                           # 0x68: min version = 8
    h += struct.pack('>I', 0xFFFFFFFF)                  # 0x6C: first image (none)
    h += b'\x00' * 16                                   # 0x70-0x7F: huffman
    h += struct.pack('>I', 0x50)                        # 0x80: EXTH flags
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
    h += struct.pack('>I', 1)                           # 0xF0: extra data flags (bit 0 = trailing overlap byte)
    h += struct.pack('>I', 0xFFFFFFFF)                  # 0xF4: NCX index (none)
    h += struct.pack('>I', chunk_idx)                   # 0xF8: chunk index
    h += struct.pack('>I', skel_idx)                    # 0xFC: skeleton index
    h += struct.pack('>I', 0xFFFFFFFF)                  # 0x100: DATP (none)
    h += struct.pack('>I', 0xFFFFFFFF)                  # 0x104: guide (none)
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


def _build_exth(title: str, author: str, language: str = 'en') -> bytes:
    """Build EXTH header with KF8-compatible metadata."""
    def rec(code, payload):
        return struct.pack('>II', code, 8 + len(payload)) + payload

    records = [
        rec(100, author.encode('utf-8')),
        rec(106, b'2000-01-01'),                       # pubdate (required by some Kindle firmware)
        rec(204, struct.pack('>I', 202)),               # creator software = kindlegen Mac
        rec(205, struct.pack('>I', 2)),                 # creator major
        rec(206, struct.pack('>I', 9)),                 # creator minor
        rec(207, struct.pack('>I', 0)),                 # creator build
        rec(501, b'EBOK'),                              # CDE type
        rec(503, title.encode('utf-8')),
        rec(524, language.encode('utf-8')),             # language
        rec(528, b'true'),                              # override_kindle_fonts
        rec(125, struct.pack('>I', 0)),                 # num_of_resources
        rec(131, struct.pack('>I', 0)),                 # kf8_unknown_count
    ]

    data = b''.join(records)
    raw_len = 12 + len(data)
    padding = (4 - (raw_len % 4)) % 4

    result = b'EXTH'
    result += struct.pack('>I', raw_len + padding)
    result += struct.pack('>I', len(records))
    result += data
    result += b'\x00' * padding

    return result


def _palmdoc_compress(data: bytes) -> bytes:
    """Compress data using PalmDOC LZ77 compression."""
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
            code = 0x8000 | ((best_dist - 1) << 3) | (best_len - 3)
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
