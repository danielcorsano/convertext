"""MOBI format converter - lightweight native Python implementation."""

from pathlib import Path
from typing import Any, Dict, List
import struct

from convertext.converters.base import BaseConverter, Document


class MobiConverter(BaseConverter):
    """Lightweight MOBI format converter (native Python)."""

    @property
    def input_formats(self) -> List[str]:
        return ['mobi', 'azw', 'azw3']

    @property
    def output_formats(self) -> List[str]:
        return ['txt', 'html', 'md']

    def can_convert(self, source: str, target: str) -> bool:
        return source in self.input_formats and target in self.output_formats

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert MOBI/AZW to target format."""
        doc = self._read_mobi(source_path, config)

        target_fmt = target_path.suffix.lstrip('.').lower()
        if target_fmt == 'txt':
            return self._write_txt(doc, target_path)
        elif target_fmt == 'html':
            return self._write_html(doc, target_path)
        elif target_fmt == 'md':
            return self._write_md(doc, target_path)

        return False

    def _read_mobi(self, path: Path, config: Dict[str, Any]) -> Document:
        """Read MOBI file - lightweight native parser."""
        doc = Document()

        with open(path, 'rb') as f:
            # Read PalmDB header
            f.seek(76)  # Skip to record count (at byte 76-77)
            num_records = struct.unpack('>H', f.read(2))[0]

            # Read record info list
            f.seek(78)  # Start of record list
            records = []
            for i in range(num_records):
                offset = struct.unpack('>I', f.read(4))[0]
                records.append(offset)
                f.read(4)  # Skip attributes and ID

            # Read MOBI header from record 0
            f.seek(records[0])
            mobi_header = f.read(records[1] - records[0] if len(records) > 1 else 1024)

            # Check compression type
            compression = struct.unpack('>H', mobi_header[0:2])[0]

            # Extract text records (usually records 1+)
            html_parts = []
            text_records = min(num_records - 1, 1000)  # Limit for safety

            for i in range(1, text_records + 1):
                if i >= len(records) - 1:
                    break

                f.seek(records[i])
                record_size = records[i + 1] - records[i]
                if record_size <= 0 or record_size > 100000:
                    continue

                record_data = f.read(record_size)

                try:
                    # Decompress if needed
                    if compression == 2:  # PalmDOC compression
                        text = self._palmdoc_decompress(record_data)
                    elif compression == 1:  # No compression
                        text = record_data
                    else:
                        text = record_data

                    # Try to decode as text
                    try:
                        decoded = text.decode('utf-8', errors='ignore')
                    except:
                        decoded = text.decode('latin-1', errors='ignore')

                    html_parts.append(decoded)

                except Exception:
                    continue

            # Combine HTML
            html_content = ''.join(html_parts)

            # Parse HTML content
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract metadata
            title_tag = soup.find('title')
            if title_tag:
                doc.metadata['title'] = title_tag.get_text()

            # Parse content
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
                continue
            elif c >= 1 and c <= 8:
                # Copy next c bytes
                result.extend(data[i:i + c])
                i += c
            elif c >= 0x80 and c <= 0xBF:
                # Space + char
                result.append(0x20)
                result.append(c ^ 0x80)
            elif c >= 0xC0:
                # Copy from output
                if i < len(data):
                    c2 = data[i]
                    i += 1
                    dist = ((c << 8) | c2) & 0x3FFF
                    length = (dist & 7) + 3
                    dist = (dist >> 3) + 1

                    # Copy from result
                    start = len(result) - dist
                    if start >= 0:
                        for _ in range(length):
                            if start < len(result):
                                result.append(result[start])
                                start += 1
            else:
                result.append(c)

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


class ToMobiConverter(BaseConverter):
    """Convert various formats to MOBI - native implementation."""

    @property
    def input_formats(self) -> List[str]:
        return ['txt', 'html', 'md']

    @property
    def output_formats(self) -> List[str]:
        return ['mobi']

    def can_convert(self, source: str, target: str) -> bool:
        return source in self.input_formats and target == 'mobi'

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert to MOBI - native implementation."""
        source_fmt = source_path.suffix.lstrip('.').lower()

        if source_fmt == 'txt':
            doc = self._read_txt(source_path, config)
        elif source_fmt in ['html', 'htm']:
            doc = self._read_html(source_path, config)
        elif source_fmt in ['md', 'markdown']:
            doc = self._read_markdown(source_path, config)
        else:
            return False

        return self._create_mobi(doc, target_path, target_path.stem)

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
            # Skip author line if present
            if i < len(lines) and lines[i].startswith('By:'):
                doc.metadata['author'] = lines[i][3:].strip()
                i += 1
            # Skip blank line after header
            while i < len(lines) and not lines[i].strip():
                i += 1

        # Process remaining content as paragraphs
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

    def _create_mobi(self, doc: Document, path: Path, default_title: str) -> bool:
        """Create MOBI file with PalmDOC compression for Kindle compatibility."""
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

        # Compress with PalmDOC (type 2) for Kindle
        compressed_records = []
        record_size = 4096
        for i in range(0, len(text_data), record_size):
            chunk = text_data[i:i + record_size]
            compressed = self._palmdoc_compress(chunk)
            compressed_records.append(compressed)

        num_text_records = len(compressed_records)

        # Build EXTH header
        exth = self._create_exth(title, author)

        # Build record 0 (PalmDOC + MOBI + EXTH + title)
        record0 = self._create_record0(title, text_length, num_text_records, exth)

        # Calculate offsets
        num_records = num_text_records + 1
        header_size = 78
        record_list_size = num_records * 8
        padding = 2
        record0_offset = header_size + record_list_size + padding

        record_offsets = [record0_offset]
        offset = record0_offset + len(record0)
        for rec in compressed_records:
            record_offsets.append(offset)
            offset += len(rec)

        # Write file
        with open(path, 'wb') as f:
            # PalmDB header
            f.write(palm_name.encode('utf-8')[:31].ljust(32, b'\x00'))
            f.write(struct.pack('>H', 0))  # attributes
            f.write(struct.pack('>H', 0))  # version
            ts = int(time.time()) + 2082844800
            f.write(struct.pack('>I', ts))  # creation
            f.write(struct.pack('>I', ts))  # modification
            f.write(struct.pack('>I', 0))   # backup
            f.write(struct.pack('>I', 0))   # modificationNumber
            f.write(struct.pack('>I', 0))   # appInfoID
            f.write(struct.pack('>I', 0))   # sortInfoID
            f.write(b'BOOK')
            f.write(b'MOBI')
            f.write(struct.pack('>I', 0))   # uniqueIDSeed
            f.write(struct.pack('>I', 0))   # nextRecordListID
            f.write(struct.pack('>H', num_records))

            # Record list
            for i, off in enumerate(record_offsets):
                f.write(struct.pack('>I', off))
                f.write(struct.pack('>I', i << 16))

            f.write(b'\x00\x00')  # padding

            # Record 0
            f.write(record0)

            # Text records
            for rec in compressed_records:
                f.write(rec)

        return True

    def _create_exth(self, title: str, author: str) -> bytes:
        """Create EXTH header with metadata."""
        records = []

        # Author (100)
        author_bytes = author.encode('utf-8')
        records.append(struct.pack('>II', 100, 8 + len(author_bytes)) + author_bytes)

        # Title (503)
        title_bytes = title.encode('utf-8')
        records.append(struct.pack('>II', 503, 8 + len(title_bytes)) + title_bytes)

        exth_data = b''.join(records)
        exth_len = 12 + len(exth_data)
        # Pad to 4-byte boundary
        padding = (4 - (exth_len % 4)) % 4

        header = b'EXTH'
        header += struct.pack('>I', exth_len + padding)
        header += struct.pack('>I', len(records))
        header += exth_data
        header += b'\x00' * padding

        return header

    def _create_record0(self, title: str, text_length: int, num_records: int, exth: bytes) -> bytes:
        """Create record 0 with PalmDOC, MOBI, and EXTH headers."""
        title_bytes = title.encode('utf-8')

        # MOBI header length (without PalmDOC header)
        mobi_len = 232

        # Full name comes after MOBI header + EXTH
        full_name_offset = 16 + mobi_len + len(exth)

        header = bytearray()

        # PalmDOC header (16 bytes)
        header.extend(struct.pack('>H', 2))      # compression = PalmDOC
        header.extend(struct.pack('>H', 0))      # unused
        header.extend(struct.pack('>I', text_length))
        header.extend(struct.pack('>H', num_records))
        header.extend(struct.pack('>H', 4096))   # record size
        header.extend(struct.pack('>H', 0))      # encryption
        header.extend(struct.pack('>H', 0))      # unknown

        # MOBI header
        header.extend(b'MOBI')
        header.extend(struct.pack('>I', mobi_len))
        header.extend(struct.pack('>I', 2))      # type = book
        header.extend(struct.pack('>I', 65001))  # encoding = UTF-8
        header.extend(struct.pack('>I', 0xffffffff))  # UID
        header.extend(struct.pack('>I', 6))      # version
        header.extend(b'\xff' * 40)              # indexes (all unused)
        header.extend(struct.pack('>I', num_records + 1))  # first non-book
        header.extend(struct.pack('>I', full_name_offset))
        header.extend(struct.pack('>I', len(title_bytes)))
        header.extend(struct.pack('>I', 1033))   # locale
        header.extend(struct.pack('>I', 0))      # input lang
        header.extend(struct.pack('>I', 0))      # output lang
        header.extend(struct.pack('>I', 6))      # min version
        header.extend(struct.pack('>I', 0))      # first image
        header.extend(struct.pack('>I', 0))      # huffman offset
        header.extend(struct.pack('>I', 0))      # huffman count
        header.extend(struct.pack('>I', 0))      # huffman table offset
        header.extend(struct.pack('>I', 0))      # huffman table len
        header.extend(struct.pack('>I', 0x50))   # EXTH flags (has EXTH)
        header.extend(b'\x00' * 32)              # unknown
        header.extend(struct.pack('>I', 0xffffffff))  # DRM
        header.extend(struct.pack('>I', 0))
        header.extend(struct.pack('>I', 0))
        header.extend(struct.pack('>I', 0))
        header.extend(b'\x00' * 8)
        header.extend(struct.pack('>H', 1))      # first content record
        header.extend(struct.pack('>H', num_records))  # last content record
        header.extend(struct.pack('>I', 1))
        header.extend(struct.pack('>I', 0))      # FCIS
        header.extend(struct.pack('>I', 0))
        header.extend(struct.pack('>I', 0))      # FLIS
        header.extend(struct.pack('>I', 0))
        header.extend(b'\x00' * 8)
        header.extend(struct.pack('>I', 0xffffffff))
        header.extend(struct.pack('>I', 0))
        header.extend(struct.pack('>I', 0xffffffff))
        header.extend(struct.pack('>I', 0xffffffff))
        header.extend(struct.pack('>I', 0))      # extra flags

        # Pad MOBI header to declared length
        while len(header) < 16 + mobi_len:
            header.append(0)

        # EXTH
        header.extend(exth)

        # Full title
        header.extend(title_bytes)

        # Pad to 4-byte boundary
        while len(header) % 4 != 0:
            header.append(0)

        return bytes(header)

    def _palmdoc_compress(self, data: bytes) -> bytes:
        """Compress data using simplified PalmDOC compression."""
        result = bytearray()
        i = 0

        while i < len(data):
            # Quick match search with limited window (optimized for speed)
            best_len = 0
            best_dist = 0

            if i >= 10:
                # Only search recent 256 bytes for speed
                search_len = min(256, i)
                search_start = i - search_len

                # Quick 4-byte match search
                if i + 3 < len(data):
                    pattern = data[i:i+4]
                    for dist in range(1, search_len + 1):
                        pos = i - dist
                        if data[pos:pos+4] == pattern:
                            # Found 4-byte match, extend it
                            match_len = 4
                            while (match_len < 10 and
                                   i + match_len < len(data) and
                                   pos + match_len < i and
                                   data[i + match_len] == data[pos + match_len]):
                                match_len += 1

                            if match_len > best_len:
                                best_len = match_len
                                best_dist = dist
                                break  # Use first good match

            # Use match if found
            if best_len >= 3:
                code = 0xC000 | ((best_dist - 1) << 3) | (best_len - 3)
                result.extend(struct.pack('>H', code))
                i += best_len
            else:
                # Simple encoding
                c = data[i]
                if c == 0x20 and i + 1 < len(data) and 0x40 <= data[i + 1] <= 0x7F:
                    # Space + ASCII optimization
                    result.append(data[i + 1] ^ 0x80)
                    i += 2
                else:
                    result.append(c)
                    i += 1

        return bytes(result)

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))
