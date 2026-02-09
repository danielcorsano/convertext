"""AZW3/KF8 format converter - lightweight native Python implementation."""

from pathlib import Path
from typing import Any, Dict, List
import struct

from convertext.converters.base import BaseConverter, Document


class Azw3Converter(BaseConverter):
    """Read AZW3/AZW files - native PDB/KF8 parser."""

    @property
    def input_formats(self) -> List[str]:
        return ['azw3', 'azw']

    @property
    def output_formats(self) -> List[str]:
        return ['txt', 'html', 'md']

    def can_convert(self, source: str, target: str) -> bool:
        return source in self.input_formats and target in self.output_formats

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert AZW3/AZW to target format."""
        doc = self._read_azw3(source_path, config)

        target_fmt = target_path.suffix.lstrip('.').lower()
        if target_fmt == 'txt':
            return self._write_txt(doc, target_path)
        elif target_fmt == 'html':
            return self._write_html(doc, target_path)
        elif target_fmt == 'md':
            return self._write_md(doc, target_path)

        return False

    def _read_azw3(self, path: Path, config: Dict[str, Any]) -> Document:
        """Read AZW3 file - native PDB/KF8 parser."""
        doc = Document()

        with open(path, 'rb') as f:
            # PalmDB header: record count at byte 76-77
            f.seek(76)
            num_records = struct.unpack('>H', f.read(2))[0]

            # Record info list starting at byte 78
            f.seek(78)
            records = []
            for _ in range(num_records):
                offset = struct.unpack('>I', f.read(4))[0]
                records.append(offset)
                f.read(4)  # skip attributes + ID

            # Record 0: PalmDOC + MOBI headers
            f.seek(records[0])
            rec0_size = records[1] - records[0] if len(records) > 1 else 1024
            rec0 = f.read(rec0_size)

            # PalmDOC header (first 16 bytes of record 0)
            compression = struct.unpack('>H', rec0[0:2])[0]
            text_length = struct.unpack('>I', rec0[4:8])[0]
            num_text_records = struct.unpack('>H', rec0[8:10])[0]

            # MOBI header at offset 16
            mobi_header_len = struct.unpack('>I', rec0[20:24])[0]
            encoding_val = struct.unpack('>I', rec0[28:32])[0]

            # Extra data flags at offset 0xF0 (240) from record 0 start
            extra_data_flags = 0
            if len(rec0) >= 244:
                extra_data_flags = struct.unpack('>I', rec0[240:244])[0]

            # EXTH metadata
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

            # Decompress text records
            html_parts = []
            for i in range(1, num_text_records + 1):
                if i >= len(records) - 1:
                    break

                f.seek(records[i])
                record_data = f.read(records[i + 1] - records[i])

                # Strip trailing bytes per extra_data_flags
                if extra_data_flags & 1 and len(record_data) > 0:
                    trail_size = (record_data[-1] & 0b11) + 1
                    record_data = record_data[:-trail_size]

                try:
                    if compression == 2:
                        text = self._palmdoc_decompress(record_data)
                    else:
                        text = record_data
                    html_parts.append(text.decode('utf-8', errors='ignore'))
                except Exception:
                    continue

            # Parse HTML content into Document
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
                # LZ77 match (0x80-0xBF, two-byte pair)
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
        """Write Document to plain text."""
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
        """Write Document to HTML."""
        html_parts = [
            '<!DOCTYPE html>',
            '<html>',
            '<head>',
            '<meta charset="utf-8">',
        ]

        if doc.metadata.get('title'):
            html_parts.append(f"<title>{self._escape_html(doc.metadata['title'])}</title>")
        else:
            html_parts.append('<title>Document</title>')

        html_parts.append('</head>')
        html_parts.append('<body>')

        if doc.metadata.get('title'):
            html_parts.append(f"<h1>{self._escape_html(doc.metadata['title'])}</h1>")
        if doc.metadata.get('author'):
            html_parts.append(f"<p><em>By {self._escape_html(doc.metadata['author'])}</em></p>")

        for block in doc.content:
            if block['type'] == 'paragraph':
                html_parts.append(f"<p>{self._escape_html(block['data'])}</p>")
            elif block['type'] == 'heading':
                level = block['level']
                html_parts.append(f"<h{level}>{self._escape_html(block['data'])}</h{level}>")

        html_parts.append('</body>')
        html_parts.append('</html>')

        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html_parts))

        return True

    def _write_md(self, doc: Document, path: Path) -> bool:
        """Write Document to Markdown."""
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

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))


class ToAzw3Converter(BaseConverter):
    """Convert various formats to AZW3/KF8."""

    @property
    def input_formats(self) -> List[str]:
        return ['txt', 'html', 'md']

    @property
    def output_formats(self) -> List[str]:
        return ['azw3']

    def can_convert(self, source: str, target: str) -> bool:
        return source in self.input_formats and target == 'azw3'

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert to AZW3."""
        source_fmt = source_path.suffix.lstrip('.').lower()

        if source_fmt == 'txt':
            doc = self._read_txt(source_path, config)
        elif source_fmt in ['html', 'htm']:
            doc = self._read_html(source_path, config)
        elif source_fmt in ['md', 'markdown']:
            doc = self._read_markdown(source_path, config)
        else:
            return False

        return self._create_azw3(doc, target_path, target_path.stem)

    def _read_txt(self, path: Path, config: Dict[str, Any]) -> Document:
        """Read plain text into Document."""
        doc = Document()
        encoding = config.get('documents', {}).get('encoding', 'utf-8')

        with open(path, 'r', encoding=encoding) as f:
            content = f.read()

        lines = content.split('\n')
        i = 0

        # Check for title pattern: "Title\n=====" at start
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
        """Read HTML into Document."""
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
        """Read Markdown into Document."""
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

    def _create_azw3(self, doc: Document, path: Path, default_title: str) -> bool:
        """Create AZW3 file with KF8 structure."""
        import time

        title = doc.metadata.get('title', default_title)
        author = doc.metadata.get('author', 'Unknown')
        palm_name = title[:31]

        # Generate HTML content
        html_parts = ['<html><head><meta charset="utf-8"/></head><body>']
        if title:
            html_parts.append(f'<h1>{self._escape_html(title)}</h1>')
        if author and author != 'Unknown':
            html_parts.append(f'<p><em>{self._escape_html(author)}</em></p>')
        for block in doc.content:
            if block['type'] == 'paragraph':
                html_parts.append(f'<p>{self._escape_html(block["data"])}</p>')
            elif block['type'] == 'heading':
                level = block['level']
                html_parts.append(f'<h{level}>{self._escape_html(block["data"])}</h{level}>')
        html_parts.append('</body></html>')

        text_data = ''.join(html_parts).encode('utf-8')
        text_length = len(text_data)

        # Compress with PalmDOC and append trailing overlap byte per record
        compressed_records = []
        record_size = 4096
        for i in range(0, len(text_data), record_size):
            chunk = text_data[i:i + record_size]
            compressed = self._palmdoc_compress(chunk)
            compressed_records.append(compressed + b'\x00')

        num_text_records = len(compressed_records)

        # Record layout: record0 + text_records + FDST + FLIS + FCIS + EOF
        fdst_rec = num_text_records + 1
        flis_rec = num_text_records + 2
        fcis_rec = num_text_records + 3
        num_records = num_text_records + 5  # record0 + text + FDST + FLIS + FCIS + EOF

        exth = self._create_exth(title, author)
        record0 = self._create_record0(
            title, text_length, num_text_records, exth,
            flis_rec, fcis_rec, fdst_rec)

        # FDST record
        fdst_data = self._create_fdst(num_text_records, text_length, record_size)

        # FLIS record (fixed content per MOBI spec)
        flis_data = (b'FLIS\x00\x00\x00\x08\x00\x41\x00\x00\x00\x00\x00\x00'
                     b'\xff\xff\xff\xff\x00\x01\x00\x03\x00\x00\x00\x03'
                     b'\x00\x00\x00\x01\xff\xff\xff\xff')

        # FCIS record (contains text length)
        fcis_data = (b'FCIS\x00\x00\x00\x14\x00\x00\x00\x10'
                     b'\x00\x00\x00\x01\x00\x00\x00\x00'
                     + struct.pack('>I', text_length)
                     + b'\x00\x00\x00\x00\x00\x00\x00\x20'
                     b'\x00\x00\x00\x08\x00\x01\x00\x01\x00\x00\x00\x00')

        eof_record = b'\xe9\x8e\x0d\x0a'

        # Calculate record offsets
        header_size = 78
        record_list_size = num_records * 8
        record0_offset = header_size + record_list_size + 2

        record_offsets = [record0_offset]
        offset = record0_offset + len(record0)
        for rec in compressed_records:
            record_offsets.append(offset)
            offset += len(rec)
        record_offsets.append(offset)  # FDST
        offset += len(fdst_data)
        record_offsets.append(offset)  # FLIS
        offset += len(flis_data)
        record_offsets.append(offset)  # FCIS
        offset += len(fcis_data)
        record_offsets.append(offset)  # EOF

        # Write file
        with open(path, 'wb') as f:
            # PalmDB header
            f.write(palm_name.encode('utf-8')[:31].ljust(32, b'\x00'))
            f.write(struct.pack('>H', 0))   # attributes
            f.write(struct.pack('>H', 0))   # version
            ts = int(time.time()) + 2082844800
            f.write(struct.pack('>I', ts))  # creation date
            f.write(struct.pack('>I', ts))  # modification date
            f.write(struct.pack('>I', 0))   # backup date
            f.write(struct.pack('>I', 0))   # modification number
            f.write(struct.pack('>I', 0))   # app info
            f.write(struct.pack('>I', 0))   # sort info
            f.write(b'BOOK')                # type
            f.write(b'MOBI')                # creator
            f.write(struct.pack('>I', (2 * num_records) - 1))  # uniqueIDSeed
            f.write(struct.pack('>I', 0))   # next record list
            f.write(struct.pack('>H', num_records))

            # Record list
            for i, off in enumerate(record_offsets):
                f.write(struct.pack('>I', off))
                f.write(b'\x00' + struct.pack('>I', 2 * i)[1:])

            f.write(b'\x00\x00')  # 2-byte gap

            # Write records
            f.write(record0)
            for rec in compressed_records:
                f.write(rec)
            f.write(fdst_data)
            f.write(flis_data)
            f.write(fcis_data)
            f.write(eof_record)

        return True

    def _create_exth(self, title: str, author: str) -> bytes:
        """Create EXTH header with metadata."""
        records = []

        # Author (100)
        author_bytes = author.encode('utf-8')
        records.append(struct.pack('>II', 100, 8 + len(author_bytes)) + author_bytes)

        # Content type (501) = EBOK
        records.append(struct.pack('>II', 501, 12) + b'EBOK')

        # Title (503)
        title_bytes = title.encode('utf-8')
        records.append(struct.pack('>II', 503, 8 + len(title_bytes)) + title_bytes)

        exth_data = b''.join(records)
        exth_len = 12 + len(exth_data)
        padding = (4 - (exth_len % 4)) % 4

        header = b'EXTH'
        header += struct.pack('>I', exth_len + padding)
        header += struct.pack('>I', len(records))
        header += exth_data
        header += b'\x00' * padding

        return header

    def _create_record0(self, title: str, text_length: int, num_text_records: int,
                        exth: bytes, flis_rec: int, fcis_rec: int, fdst_rec: int) -> bytes:
        """Create record 0 with PalmDOC, MOBI v8, and EXTH headers."""
        title_bytes = title.encode('utf-8')
        mobi_len = 264  # KF8 header length
        full_name_offset = 16 + mobi_len + len(exth)

        header = bytearray()

        # PalmDOC header (16 bytes, 0x00-0x0F)
        header.extend(struct.pack('>H', 2))                        # 0x00: PalmDOC compression
        header.extend(struct.pack('>H', 0))                        # 0x02: unused
        header.extend(struct.pack('>I', text_length))              # 0x04: text length
        header.extend(struct.pack('>H', num_text_records))         # 0x08: record count
        header.extend(struct.pack('>H', 4096))                     # 0x0A: record size
        header.extend(struct.pack('>H', 0))                        # 0x0C: no encryption
        header.extend(struct.pack('>H', 0))                        # 0x0E: unused

        # MOBI header (264 bytes, 0x10-0x117)
        header.extend(b'MOBI')                                     # 0x10: identifier
        header.extend(struct.pack('>I', mobi_len))                 # 0x14: header length = 264
        header.extend(struct.pack('>I', 2))                        # 0x18: type = book
        header.extend(struct.pack('>I', 65001))                    # 0x1C: UTF-8
        header.extend(struct.pack('>I', 0))                        # 0x20: UID
        header.extend(struct.pack('>I', 8))                        # 0x24: version = 8 (KF8)
        header.extend(b'\xff' * 40)                                # 0x28-0x4F: index fields
        header.extend(struct.pack('>I', num_text_records + 1))     # 0x50: first non-book
        header.extend(struct.pack('>I', full_name_offset))         # 0x54: name offset
        header.extend(struct.pack('>I', len(title_bytes)))         # 0x58: name length
        header.extend(struct.pack('>I', 1033))                     # 0x5C: locale
        header.extend(struct.pack('>I', 0))                        # 0x60: input lang
        header.extend(struct.pack('>I', 0))                        # 0x64: output lang
        header.extend(struct.pack('>I', 8))                        # 0x68: min version = 8
        header.extend(struct.pack('>I', 0))                        # 0x6C: first image
        header.extend(b'\x00' * 16)                                # 0x70-0x7F: huffman
        header.extend(struct.pack('>I', 0x50))                     # 0x80: EXTH flags
        header.extend(b'\x00' * 32)                                # 0x84-0xA3: unknown
        header.extend(struct.pack('>I', 0xffffffff))               # 0xA4: DRM offset
        header.extend(struct.pack('>I', 0xffffffff))               # 0xA8: DRM count
        header.extend(struct.pack('>I', 0))                        # 0xAC: DRM size
        header.extend(struct.pack('>I', 0))                        # 0xB0: DRM flags
        header.extend(b'\x00' * 12)                                # 0xB4-0xBF: unknown
        header.extend(struct.pack('>H', 1))                        # 0xC0: first content
        header.extend(struct.pack('>H', num_text_records))         # 0xC2: last content
        header.extend(struct.pack('>I', 1))                        # 0xC4: unknown
        header.extend(struct.pack('>I', fcis_rec))                 # 0xC8: FCIS record
        header.extend(struct.pack('>I', 1))                        # 0xCC: FCIS count
        header.extend(struct.pack('>I', flis_rec))                 # 0xD0: FLIS record
        header.extend(struct.pack('>I', 1))                        # 0xD4: FLIS count
        header.extend(b'\x00' * 8)                                 # 0xD8-0xDF: unknown
        header.extend(struct.pack('>I', 0xffffffff))               # 0xE0
        header.extend(struct.pack('>I', 0))                        # 0xE4
        header.extend(struct.pack('>I', 0xffffffff))               # 0xE8
        header.extend(struct.pack('>I', 0xffffffff))               # 0xEC
        header.extend(struct.pack('>I', 1))                        # 0xF0: extra data flags
        header.extend(struct.pack('>I', 0xffffffff))               # 0xF4: INDX = none
        # KF8 extension fields (bytes 232-263, offsets 0xF8-0x117)
        header.extend(struct.pack('>I', fdst_rec))                 # 0xF8: FDST index
        header.extend(struct.pack('>I', num_text_records))         # 0xFC: FDST count
        header.extend(struct.pack('>I', 0xffffffff))               # 0x100: SKEL index
        header.extend(struct.pack('>I', 0xffffffff))               # 0x104: DATP index
        header.extend(struct.pack('>I', 0xffffffff))               # 0x108: guide index
        header.extend(b'\x00' * 12)                                # 0x10C-0x117: padding

        # EXTH header
        header.extend(exth)

        # Full title + pad to 4-byte boundary
        header.extend(title_bytes)
        while len(header) % 4 != 0:
            header.append(0)

        return bytes(header)

    def _create_fdst(self, num_text_records: int, text_length: int, record_size: int) -> bytes:
        """Create FDST (Flow/Data Section Table) record."""
        fdst = bytearray()
        fdst.extend(b'FDST')
        fdst.extend(struct.pack('>I', 12 + num_text_records * 8))  # length
        fdst.extend(struct.pack('>I', num_text_records))           # entry count

        # One offset pair per text record
        for i in range(num_text_records):
            start = i * record_size
            end = min((i + 1) * record_size, text_length)
            fdst.extend(struct.pack('>I', start))
            fdst.extend(struct.pack('>I', end))

        return bytes(fdst)

    def _palmdoc_compress(self, data: bytes) -> bytes:
        """Compress data using PalmDOC compression."""
        result = bytearray()
        i = 0

        while i < len(data):
            # LZ77 match search with limited window
            best_len = 0
            best_dist = 0

            if i >= 10:
                search_len = min(256, i)

                if i + 3 < len(data):
                    pattern = data[i:i+4]
                    for dist in range(1, search_len + 1):
                        pos = i - dist
                        if data[pos:pos+4] == pattern:
                            match_len = 4
                            while (match_len < 10 and
                                   i + match_len < len(data) and
                                   pos + match_len < i and
                                   data[i + match_len] == data[pos + match_len]):
                                match_len += 1

                            if match_len > best_len:
                                best_len = match_len
                                best_dist = dist
                                break

            if best_len >= 3:
                code = 0x8000 | ((best_dist - 1) << 3) | (best_len - 3)
                result.extend(struct.pack('>H', code))
                i += best_len
            elif 0x09 <= data[i] <= 0x7F:
                result.append(data[i])
                i += 1
            else:
                # Unsafe byte (0x00-0x08 or 0x80-0xFF) - escape via literal copy
                end = i + 1
                while end < len(data) and end - i < 8 and not (0x09 <= data[end] <= 0x7F):
                    end += 1
                count = end - i
                result.append(count)
                result.extend(data[i:end])
                i = end

        return bytes(result)

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))
