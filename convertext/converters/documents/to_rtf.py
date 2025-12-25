"""RTF format output converter - native implementation."""

from pathlib import Path
from typing import Any, Dict, List

from convertext.converters.base import BaseConverter, Document
from convertext.converters.utils import escape_rtf, hex_to_rgb


class ToRtfConverter(BaseConverter):
    """Convert various formats to RTF using native implementation."""

    @property
    def input_formats(self) -> List[str]:
        return ['txt', 'html', 'md', 'pdf', 'docx', 'odt', 'epub', 'mobi', 'fb2']

    @property
    def output_formats(self) -> List[str]:
        return ['rtf']

    def can_convert(self, source: str, target: str) -> bool:
        return source in self.input_formats and target == 'rtf'

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert to RTF."""
        from convertext.registry import get_registry

        registry = get_registry()
        source_fmt = source_path.suffix.lstrip('.').lower()

        converter = registry.get_converter(source_fmt, 'html')
        if not converter:
            converter = registry.get_converter(source_fmt, 'txt')
        if not converter:
            return False

        from tempfile import NamedTemporaryFile
        with NamedTemporaryFile(mode='w', suffix='.html', delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            if not converter.convert(source_path, tmp_path, config):
                return False

            if tmp_path.suffix == '.html':
                doc = self._read_html(tmp_path, config)
            else:
                doc = self._read_txt(tmp_path, config)

            return self._create_rtf(doc, target_path, config)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def _read_txt(self, path: Path, config: Dict[str, Any]) -> Document:
        """Read plain text into Document."""
        doc = Document()
        encoding = config.get('documents', {}).get('encoding', 'utf-8')

        with open(path, 'r', encoding=encoding) as f:
            content = f.read()
            for para in content.split('\n\n'):
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
        if title_tag:
            doc.metadata['title'] = title_tag.get_text()

        for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'ul', 'ol']):
            if element.name.startswith('h'):
                level = int(element.name[1])
                doc.add_heading(element.get_text().strip(), level)

            elif element.name == 'p':
                text = element.get_text().strip()
                if text:
                    doc.add_paragraph(text)

            elif element.name == 'table':
                rows = []
                headers = []
                thead = element.find('thead')
                if thead:
                    header_row = thead.find('tr')
                    if header_row:
                        headers = [th.get_text().strip() for th in header_row.find_all(['th', 'td'])]

                tbody = element.find('tbody') or element
                for row in tbody.find_all('tr'):
                    cells = [cell.get_text().strip() for cell in row.find_all(['td', 'th'])]
                    if cells:
                        rows.append(cells)

                if rows:
                    doc.add_table(rows=rows, headers=headers if headers else None)

            elif element.name in ['ul', 'ol']:
                items = [li.get_text().strip() for li in element.find_all('li')]
                if items:
                    doc.add_list(items=items, ordered=(element.name == 'ol'))

        return doc

    def _create_rtf(self, doc: Document, path: Path, config: Dict[str, Any]) -> bool:
        """Create RTF file - native implementation."""
        rtf_parts = [
            r'{\rtf1\ansi\deff0',
            r'{\info',
        ]

        if doc.metadata.get('title'):
            rtf_parts.append(
                r'{\title ' + escape_rtf(doc.metadata['title']) + '}'
            )
        if doc.metadata.get('author'):
            rtf_parts.append(
                r'{\author ' + escape_rtf(doc.metadata['author']) + '}'
            )
        if doc.metadata.get('subject'):
            rtf_parts.append(
                r'{\subject ' + escape_rtf(doc.metadata['subject']) + '}'
            )
        rtf_parts.append(r'}')

        rtf_parts.append(r'{\fonttbl{\f0\fswiss Arial;}{\f1\fmodern Courier New;}}')

        rtf_parts.append(
            r'{\colortbl;\red0\green0\blue0;\red255\green0\blue0;'
            r'\red0\green0\blue255;\red0\green128\blue0;}'
        )

        for block in doc.content:
            if block['type'] == 'heading':
                level = block.get('level', 1)
                size = 32 - (level * 4)
                rtf_parts.append(
                    f'\\pard\\fs{size}\\b {escape_rtf(block["data"])}\\b0\\fs24\\par'
                )

            elif block['type'] in ['paragraph', 'text']:
                rtf_parts.append(f'\\pard {escape_rtf(block["data"])}\\par')

            elif block['type'] == 'run':
                rtf_text = ''
                if block.get('bold'):
                    rtf_text += '\\b '
                if block.get('italic'):
                    rtf_text += '\\i '
                if block.get('underline'):
                    rtf_text += '\\ul '

                if block.get('color'):
                    rgb = hex_to_rgb(block['color'])
                    if rgb:
                        rtf_text += '\\cf1 '

                rtf_text += escape_rtf(block['text'])

                if block.get('bold'):
                    rtf_text += '\\b0 '
                if block.get('italic'):
                    rtf_text += '\\i0 '
                if block.get('underline'):
                    rtf_text += '\\ul0 '
                if block.get('color'):
                    rtf_text += '\\cf0 '

                rtf_parts.append(f'\\pard {rtf_text}\\par')

            elif block['type'] == 'table':
                headers = block.get('headers', [])
                rows = block['rows']

                if headers:
                    rtf_parts.append(self._create_rtf_table_row(headers, bold=True))

                for row in rows:
                    rtf_parts.append(self._create_rtf_table_row(row))

                rtf_parts.append('\\par')

            elif block['type'] == 'list':
                for i, item in enumerate(block['items'], 1):
                    if block.get('ordered'):
                        bullet = f'{i}.'
                    else:
                        bullet = '\\bullet'
                    rtf_parts.append(
                        f'\\pard {bullet}\\tab {escape_rtf(item)}\\par'
                    )
                rtf_parts.append('\\par')

            elif block['type'] == 'link':
                rtf_parts.append(
                    f'\\pard {escape_rtf(block["text"])} '
                    f'(\\cf2 {escape_rtf(block["url"])}\\cf0)\\par'
                )

        rtf_parts.append('}')

        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(rtf_parts))

        return True

    def _create_rtf_table_row(self, cells: List[str], bold: bool = False) -> str:
        """Create RTF table row."""
        cell_width = 2000
        row_parts = ['\\trowd']

        for i, cell in enumerate(cells, 1):
            row_parts.append(f'\\cellx{i * cell_width}')

        row_parts.append('\\pard\\intbl')

        for cell in cells:
            if bold:
                row_parts.append(f'\\b {escape_rtf(str(cell))}\\b0\\cell')
            else:
                row_parts.append(f'{escape_rtf(str(cell))}\\cell')

        row_parts.append('\\row')
        return ' '.join(row_parts)
