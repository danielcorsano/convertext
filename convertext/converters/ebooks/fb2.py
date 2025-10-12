"""FB2 (FictionBook) format converter."""

from pathlib import Path
from typing import Any, Dict, List
from lxml import etree

from convertext.converters.base import BaseConverter, Document


class FB2Converter(BaseConverter):
    """FictionBook 2.0 format converter."""

    @property
    def input_formats(self) -> List[str]:
        return ['fb2']

    @property
    def output_formats(self) -> List[str]:
        return ['txt', 'html', 'md']

    def can_convert(self, source: str, target: str) -> bool:
        return source == 'fb2' and target in self.output_formats

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert FB2 to target format."""
        doc = self._read_fb2(source_path, config)

        target_fmt = target_path.suffix.lstrip('.').lower()
        if target_fmt == 'txt':
            return self._write_txt(doc, target_path)
        elif target_fmt == 'html':
            return self._write_html(doc, target_path)
        elif target_fmt == 'md':
            return self._write_md(doc, target_path)

        return False

    def _read_fb2(self, path: Path, config: Dict[str, Any]) -> Document:
        """Read FB2 into intermediate Document."""
        doc = Document()

        # Parse FB2 XML
        tree = etree.parse(str(path))
        root = tree.getroot()

        # FB2 namespace
        ns = {'fb': 'http://www.gribuser.ru/xml/fictionbook/2.0'}

        # Extract metadata
        title_info = root.find('.//fb:title-info', ns)
        if title_info is not None:
            title = title_info.find('fb:book-title', ns)
            if title is not None and title.text:
                doc.metadata['title'] = title.text

            authors = title_info.findall('fb:author', ns)
            author_names = []
            for author in authors:
                first_name = author.find('fb:first-name', ns)
                last_name = author.find('fb:last-name', ns)
                if first_name is not None or last_name is not None:
                    name_parts = []
                    if first_name is not None and first_name.text:
                        name_parts.append(first_name.text)
                    if last_name is not None and last_name.text:
                        name_parts.append(last_name.text)
                    author_names.append(' '.join(name_parts))
            if author_names:
                doc.metadata['author'] = ', '.join(author_names)

            lang = title_info.find('fb:lang', ns)
            if lang is not None and lang.text:
                doc.metadata['language'] = lang.text

        # Extract body content
        bodies = root.findall('.//fb:body', ns)
        for body in bodies:
            self._parse_fb2_section(body, doc, ns)

        return doc

    def _parse_fb2_section(self, element, doc: Document, ns: Dict[str, str], level: int = 1):
        """Recursively parse FB2 sections."""
        for child in element:
            tag = child.tag.replace('{' + ns['fb'] + '}', '')

            if tag == 'title':
                # Section title
                for p in child.findall('fb:p', ns):
                    if p.text:
                        doc.add_heading(p.text.strip(), level)
            elif tag == 'section':
                # Nested section
                self._parse_fb2_section(child, doc, ns, level + 1)
            elif tag == 'p':
                # Paragraph
                text = self._extract_text(child)
                if text:
                    doc.add_paragraph(text)
            elif tag == 'poem' or tag == 'cite':
                # Poem or citation - treat as paragraph
                for p in child.findall('.//fb:p', ns):
                    text = self._extract_text(p)
                    if text:
                        doc.add_paragraph(text)

    def _extract_text(self, element) -> str:
        """Extract text from element including nested tags."""
        text_parts = []
        if element.text:
            text_parts.append(element.text)
        for child in element:
            text_parts.append(self._extract_text(child))
            if child.tail:
                text_parts.append(child.tail)
        return ''.join(text_parts).strip()

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


class ToFB2Converter(BaseConverter):
    """Convert various formats to FB2."""

    @property
    def input_formats(self) -> List[str]:
        return ['txt', 'html', 'md']

    @property
    def output_formats(self) -> List[str]:
        return ['fb2']

    def can_convert(self, source: str, target: str) -> bool:
        return source in self.input_formats and target == 'fb2'

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert to FB2."""
        source_fmt = source_path.suffix.lstrip('.').lower()

        if source_fmt == 'txt':
            doc = self._read_txt(source_path, config)
        elif source_fmt in ['html', 'htm']:
            doc = self._read_html(source_path, config)
        elif source_fmt in ['md', 'markdown']:
            doc = self._read_markdown(source_path, config)
        else:
            return False

        return self._create_fb2(doc, target_path, config, source_path.stem)

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

    def _create_fb2(self, doc: Document, path: Path, config: Dict[str, Any], default_title: str) -> bool:
        """Create FB2 from Document."""
        # FB2 namespace
        NS = "http://www.gribuser.ru/xml/fictionbook/2.0"
        NSMAP = {None: NS}

        # Create root element
        root = etree.Element("{%s}FictionBook" % NS, nsmap=NSMAP)

        # Description section
        description = etree.SubElement(root, "{%s}description" % NS)
        title_info = etree.SubElement(description, "{%s}title-info" % NS)

        # Add title
        book_title = etree.SubElement(title_info, "{%s}book-title" % NS)
        book_title.text = doc.metadata.get('title', default_title)

        # Add author
        author = etree.SubElement(title_info, "{%s}author" % NS)
        first_name = etree.SubElement(author, "{%s}first-name" % NS)
        first_name.text = doc.metadata.get('author', 'Unknown')

        # Add language
        lang = etree.SubElement(title_info, "{%s}lang" % NS)
        lang.text = doc.metadata.get('language', 'en')

        # Body section
        body = etree.SubElement(root, "{%s}body" % NS)

        # Add content
        current_section = body
        for block in doc.content:
            if block['type'] == 'heading':
                # Create new section for each heading
                current_section = etree.SubElement(body, "{%s}section" % NS)
                title = etree.SubElement(current_section, "{%s}title" % NS)
                p = etree.SubElement(title, "{%s}p" % NS)
                p.text = block['data']
            elif block['type'] == 'paragraph':
                p = etree.SubElement(current_section, "{%s}p" % NS)
                p.text = block['data']

        # Write to file
        tree = etree.ElementTree(root)
        tree.write(
            str(path),
            encoding='utf-8',
            xml_declaration=True,
            pretty_print=True
        )

        return True
