"""Markdown format converter."""

from pathlib import Path
from typing import Any, Dict, List

import markdown
from bs4 import BeautifulSoup

from convertext.converters.base import BaseConverter, Document


class MarkdownConverter(BaseConverter):
    """Markdown format converter."""

    @property
    def input_formats(self) -> List[str]:
        return ['md', 'markdown']

    @property
    def output_formats(self) -> List[str]:
        return ['html', 'txt']

    def can_convert(self, source: str, target: str) -> bool:
        return source in self.input_formats and target in self.output_formats

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert Markdown to target format."""
        doc = self._read_markdown(source_path, config)

        target_fmt = target_path.suffix.lstrip('.').lower()
        if target_fmt == 'html':
            return self._write_html(doc, target_path)
        elif target_fmt == 'txt':
            return self._write_txt(doc, target_path)

        return False

    def _read_markdown(self, path: Path, config: Dict[str, Any]) -> Document:
        """Read Markdown into Document."""
        doc = Document()
        encoding = config.get('documents', {}).get('encoding', 'utf-8')

        with open(path, 'r', encoding=encoding) as f:
            content = f.read()

        html_content = markdown.markdown(content)
        soup = BeautifulSoup(html_content, 'html.parser')

        for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            if element.name.startswith('h'):
                level = int(element.name[1])
                doc.add_heading(element.get_text(), level)
            elif element.name == 'p':
                doc.add_paragraph(element.get_text())

        return doc

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
                html_parts.append(f"<p>{self._escape_html(block['data'])}</p>")
            elif block['type'] == 'heading':
                level = block['level']
                html_parts.append(f"<h{level}>{self._escape_html(block['data'])}</h{level}>")

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

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))
