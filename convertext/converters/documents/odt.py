"""ODT (OpenDocument Text) format converter - native Python implementation."""

from pathlib import Path
from typing import Any, Dict, List
import zipfile
from lxml import etree

from convertext.converters.base import BaseConverter, Document


class OdtConverter(BaseConverter):
    """OpenDocument Text format converter."""

    @property
    def input_formats(self) -> List[str]:
        return ['odt']

    @property
    def output_formats(self) -> List[str]:
        return ['txt', 'html', 'md']

    def can_convert(self, source: str, target: str) -> bool:
        return source == 'odt' and target in self.output_formats

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert ODT to target format."""
        doc = self._read_odt(source_path, config)

        target_fmt = target_path.suffix.lstrip('.').lower()
        if target_fmt == 'txt':
            return self._write_txt(doc, target_path)
        elif target_fmt == 'html':
            return self._write_html(doc, target_path)
        elif target_fmt == 'md':
            return self._write_md(doc, target_path)

        return False

    def _read_odt(self, path: Path, config: Dict[str, Any]) -> Document:
        """Read ODT - native parser using zipfile + lxml."""
        doc = Document()

        with zipfile.ZipFile(path, 'r') as zf:
            # Parse metadata
            try:
                meta_xml = etree.fromstring(zf.read('meta.xml'))
                ns = {
                    'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
                    'meta': 'urn:oasis:names:tc:opendocument:xmlns:meta:1.0',
                    'dc': 'http://purl.org/dc/elements/1.1/'
                }

                title = meta_xml.find('.//dc:title', ns)
                if title is not None and title.text:
                    doc.metadata['title'] = title.text

                creator = meta_xml.find('.//dc:creator', ns)
                if creator is not None and creator.text:
                    doc.metadata['author'] = creator.text
            except:
                pass

            # Parse content
            content_xml = etree.fromstring(zf.read('content.xml'))
            ns = {
                'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
                'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0'
            }

            body = content_xml.find('.//office:body/office:text', ns)
            if body is not None:
                # Process headings and paragraphs in order
                for elem in body:
                    tag = elem.tag.replace('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}', '')

                    if tag == 'h':
                        # Heading
                        text = self._extract_text(elem).strip()
                        if text:
                            level_attr = elem.get('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}outline-level')
                            level = int(level_attr) if level_attr else 1
                            doc.add_heading(text, level)

                    elif tag == 'p':
                        # Paragraph
                        text = self._extract_text(elem).strip()
                        if text:
                            # Check if styled as heading
                            style = elem.get('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name', '')
                            if 'heading' in style.lower():
                                level = 1
                                if '2' in style:
                                    level = 2
                                elif '3' in style:
                                    level = 3
                                elif '4' in style:
                                    level = 4
                                doc.add_heading(text, level)
                            else:
                                doc.add_paragraph(text)

        return doc

    def _extract_text(self, element) -> str:
        """Extract all text from an XML element."""
        text_parts = []
        if element.text:
            text_parts.append(element.text)
        for child in element:
            text_parts.append(self._extract_text(child))
            if child.tail:
                text_parts.append(child.tail)
        return ''.join(text_parts)

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
