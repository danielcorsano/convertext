"""Plain text converter."""

from pathlib import Path
from typing import Any, Dict, List

from convertext.converters.readers import read_txt
from convertext.converters.utils import escape_html
from convertext.converters.base import BaseConverter, Document

class TxtConverter(BaseConverter):
    """Plain text format converter."""

    @property
    def input_formats(self) -> List[str]:
        return ['txt']

    @property
    def output_formats(self) -> List[str]:
        return ['txt', 'html', 'md']

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert plain text to target format."""
        doc = read_txt(source_path, config)
        self._apply_metadata_overrides(doc, source_path, config)

        target_fmt = target_path.suffix.lstrip('.').lower()
        if target_fmt == 'txt':
            return self._write_txt(doc, target_path)
        elif target_fmt == 'html':
            return self._write_html(doc, target_path)
        elif target_fmt == 'md':
            return self._write_md(doc, target_path)

        return False

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
                    f.write('#' * block['level'] + ' ' + block['data'] + '\n\n')
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
            html_parts.append(f"<title>{escape_html(doc.metadata['title'])}</title>")
        else:
            html_parts.append('<title>Document</title>')
        html_parts.append('</head>')
        html_parts.append('<body>')
        if doc.metadata.get('title'):
            html_parts.append(f"<h1>{escape_html(doc.metadata['title'])}</h1>")
        if doc.metadata.get('author'):
            html_parts.append(f"<p><em>By {escape_html(doc.metadata['author'])}</em></p>")

        for block in doc.content:
            if block['type'] == 'paragraph':
                html_parts.append(f"<p>{escape_html(block['data'])}</p>")
            elif block['type'] == 'heading':
                level = block['level']
                html_parts.append(f"<h{level}>{escape_html(block['data'])}</h{level}>")
            elif block['type'] == 'text':
                html_parts.append(f"<p>{escape_html(block['data'])}</p>")

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
                    f.write('#' * block['level'] + ' ' + block['data'] + '\n\n')
                elif block['type'] == 'text':
                    f.write(block['data'] + '\n\n')
        return True

