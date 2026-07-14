"""RTF format output converter - native implementation."""

from pathlib import Path
from typing import Any, Dict, List

from convertext.converters.readers import read_html, read_txt
from convertext.converters.base import BaseConverter, Document
from convertext.converters.utils import escape_rtf, hex_to_rgb

class ToRtfConverter(BaseConverter):
    """Convert various formats to RTF using native implementation."""

    @property
    def input_formats(self) -> List[str]:
        return ['txt', 'html', 'md', 'pdf', 'docx', 'odt', 'epub', 'fb2']

    @property
    def output_formats(self) -> List[str]:
        return ['rtf']

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert to RTF."""
        from convertext.registry import get_registry

        registry = get_registry()
        source_fmt = source_path.suffix.lstrip('.').lower()

        converter = registry.get_converter(source_fmt, 'html')
        inter_fmt = 'html'
        if not converter:
            converter = registry.get_converter(source_fmt, 'txt')
            inter_fmt = 'txt'
        if not converter:
            return False

        from tempfile import NamedTemporaryFile
        with NamedTemporaryFile(mode='w', suffix=f'.{inter_fmt}', delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            if not converter.convert(source_path, tmp_path, config):
                return False

            if inter_fmt == 'html':
                doc = read_html(tmp_path, config)
            else:
                doc = read_txt(tmp_path, config)
            self._apply_metadata_overrides(doc, source_path, config)

            return self._create_rtf(doc, target_path, config)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

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
