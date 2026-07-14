"""Markdown format converter."""

from pathlib import Path
from typing import Any, Dict, List

from convertext.converters.readers import read_markdown
from convertext.converters.utils import escape_html
from convertext.converters.base import BaseConverter, Document

class MarkdownConverter(BaseConverter):
    """Markdown format converter."""

    @property
    def input_formats(self) -> List[str]:
        return ['md', 'markdown']

    @property
    def output_formats(self) -> List[str]:
        return ['html', 'txt']

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert Markdown to target format."""
        doc = read_markdown(source_path, config)
        self._apply_metadata_overrides(doc, source_path, config)

        target_fmt = target_path.suffix.lstrip('.').lower()
        if target_fmt == 'html':
            return self._write_html(doc, target_path)
        elif target_fmt == 'txt':
            return self._write_txt(doc, target_path)

        return False

    def _write_html(self, doc: Document, path: Path) -> bool:
        """Write Document to HTML."""
        html_parts = [
            '<!DOCTYPE html>',
            '<html>',
            '<head>',
            '<meta charset="utf-8">',
            '<title>Document</title>',
            '</head>',
            '<body>'
        ]

        for block in doc.content:
            if block['type'] == 'paragraph':
                html_parts.append(f"<p>{escape_html(block['data'])}</p>")
            elif block['type'] == 'heading':
                level = block['level']
                html_parts.append(f"<h{level}>{escape_html(block['data'])}</h{level}>")

        html_parts.append('</body>')
        html_parts.append('</html>')

        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html_parts))

        return True

    def _write_txt(self, doc: Document, path: Path) -> bool:
        """Write Document to plain text."""
        with open(path, 'w', encoding='utf-8') as f:
            for block in doc.content:
                if block['type'] in ['text', 'paragraph']:
                    f.write(block['data'] + '\n\n')
                elif block['type'] == 'heading':
                    f.write(block['data'].upper() + '\n')
                    f.write('=' * len(block['data']) + '\n\n')
        return True

