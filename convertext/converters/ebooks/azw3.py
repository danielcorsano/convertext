"""AZW3/MOBI format reader - native PDB/MOBI parser."""

from pathlib import Path
from typing import Any, Dict, List
import struct

from convertext.converters.base import BaseConverter, Document


def _esc(text: str) -> str:
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))


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
