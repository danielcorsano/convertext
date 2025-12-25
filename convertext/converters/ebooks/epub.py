"""EPUB format converter - native Python implementation."""

import datetime as dt
from pathlib import Path
from typing import Any, Dict, List
import zipfile
from lxml import etree
from bs4 import BeautifulSoup

from convertext.converters.base import BaseConverter, Document


class EpubConverter(BaseConverter):
    """Lightweight EPUB format converter (native Python)."""

    @property
    def input_formats(self) -> List[str]:
        return ['epub']

    @property
    def output_formats(self) -> List[str]:
        return ['txt', 'html', 'md']

    def can_convert(self, source: str, target: str) -> bool:
        return source == 'epub' and target in self.output_formats

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert EPUB to target format."""
        doc = self._read_epub(source_path, config)

        target_fmt = target_path.suffix.lstrip('.').lower()
        if target_fmt == 'txt':
            return self._write_txt(doc, target_path)
        elif target_fmt == 'html':
            return self._write_html(doc, target_path)
        elif target_fmt == 'md':
            return self._write_md(doc, target_path)

        return False

    def _read_epub(self, path: Path, config: Dict[str, Any]) -> Document:
        """Read EPUB - native parser using zipfile + lxml."""
        doc = Document()

        with zipfile.ZipFile(path, 'r') as zf:
            # Find OPF file location from container.xml
            container = etree.fromstring(zf.read('META-INF/container.xml'))
            opf_path = container.find('.//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile').get('full-path')

            # Parse OPF for metadata and spine
            opf = etree.fromstring(zf.read(opf_path))
            opf_dir = str(Path(opf_path).parent)

            # Extract metadata
            ns = {'opf': 'http://www.idpf.org/2007/opf', 'dc': 'http://purl.org/dc/elements/1.1/'}

            title = opf.find('.//dc:title', ns)
            if title is not None and title.text:
                doc.metadata['title'] = title.text

            creator = opf.find('.//dc:creator', ns)
            if creator is not None and creator.text:
                doc.metadata['author'] = creator.text

            lang = opf.find('.//dc:language', ns)
            if lang is not None and lang.text:
                doc.metadata['language'] = lang.text

            # Get spine order (reading order)
            manifest = {item.get('id'): item.get('href')
                       for item in opf.findall('.//opf:manifest/opf:item', ns)}

            spine_items = opf.findall('.//opf:spine/opf:itemref', ns)

            # Read content in spine order
            for itemref in spine_items:
                idref = itemref.get('idref')
                if idref in manifest:
                    content_path = manifest[idref]
                    if opf_dir and opf_dir != '.':
                        content_path = f"{opf_dir}/{content_path}"

                    try:
                        content = zf.read(content_path).decode('utf-8', errors='ignore')
                        soup = BeautifulSoup(content, 'html.parser')

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
                    except:
                        continue

        return doc

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


class ToEpubConverter(BaseConverter):
    """Convert various formats to EPUB."""

    @property
    def input_formats(self) -> List[str]:
        return ['txt', 'html', 'md']

    @property
    def output_formats(self) -> List[str]:
        return ['epub']

    def can_convert(self, source: str, target: str) -> bool:
        return source in self.input_formats and target == 'epub'

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert to EPUB."""
        source_fmt = source_path.suffix.lstrip('.').lower()

        if source_fmt == 'txt':
            doc = self._read_txt(source_path, config)
        elif source_fmt in ['html', 'htm']:
            doc = self._read_html(source_path, config)
        elif source_fmt in ['md', 'markdown']:
            doc = self._read_markdown(source_path, config)
        else:
            return False

        return self._create_epub(doc, target_path, config, source_path.stem)

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
        html_content = markdown.markdown(content)
        soup = BeautifulSoup(html_content, 'html.parser')

        for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            if element.name.startswith('h'):
                level = int(element.name[1])
                doc.add_heading(element.get_text(), level)
            elif element.name == 'p':
                doc.add_paragraph(element.get_text())

        return doc

    def _create_epub(self, doc: Document, path: Path, config: Dict[str, Any], default_title: str) -> bool:
        """Create EPUB from Document - native implementation."""
        import uuid

        title = doc.metadata.get('title', default_title)
        author = doc.metadata.get('author', 'Unknown')
        language = doc.metadata.get('language', 'en')
        uid = str(uuid.uuid4())

        # Split content into chapters
        chapters = []
        current_chapter = []
        chapter_titles = []

        for block in doc.content:
            if block['type'] == 'heading' and block['level'] == 1:
                if current_chapter:
                    chapters.append(current_chapter)
                    current_chapter = []
                chapter_titles.append(block['data'])
                current_chapter.append(f'<h1>{self._escape_html(block["data"])}</h1>')
            elif block['type'] == 'paragraph':
                current_chapter.append(f'<p>{self._escape_html(block["data"])}</p>')
            elif block['type'] == 'heading':
                level = block['level']
                current_chapter.append(f'<h{level}>{self._escape_html(block["data"])}</h{level}>')

        if current_chapter:
            chapters.append(current_chapter)

        if not chapters:
            chapters = [['<p>No content</p>']]
            chapter_titles = ['Content']

        if not chapter_titles:
            chapter_titles = [f'Chapter {i+1}' for i in range(len(chapters))]

        # Create EPUB ZIP structure
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # mimetype (must be uncompressed and first)
            zf.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)

            # container.xml
            container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>'''
            zf.writestr('META-INF/container.xml', container_xml)

            # Generate manifest and spine items
            manifest_items = []
            spine_items = []
            toc_items = []

            for i, (chapter, chapter_title) in enumerate(zip(chapters, chapter_titles), 1):
                filename = f'chap_{i:02d}.xhtml'
                manifest_items.append(f'    <item id="chapter{i}" href="{filename}" media-type="application/xhtml+xml"/>')
                spine_items.append(f'    <itemref idref="chapter{i}"/>')
                toc_items.append(f'    <navPoint id="navPoint-{i}" playOrder="{i}">\n      <navLabel><text>{self._escape_html(chapter_title)}</text></navLabel>\n      <content src="{filename}"/>\n    </navPoint>')

                # Write chapter XHTML
                xhtml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
  <title>{self._escape_html(chapter_title)}</title>
</head>
<body>
{''.join(chapter)}
</body>
</html>'''
                zf.writestr(f'OEBPS/{filename}', xhtml)

            # content.opf
            opf = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">{uid}</dc:identifier>
    <dc:title>{self._escape_html(title)}</dc:title>
    <dc:creator>{self._escape_html(author)}</dc:creator>
    <dc:language>{language}</dc:language>
    <meta property="dcterms:modified">{dt.datetime.now(dt.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}</meta>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
{''.join([item + '\n' for item in manifest_items])}
  </manifest>
  <spine toc="ncx">
{''.join([item + '\n' for item in spine_items])}
  </spine>
</package>'''
            zf.writestr('OEBPS/content.opf', opf)

            # toc.ncx (for EPUB 2 compatibility)
            ncx = f'''<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="{uid}"/>
    <meta name="dtb:depth" content="1"/>
  </head>
  <docTitle>
    <text>{self._escape_html(title)}</text>
  </docTitle>
  <navMap>
{''.join([item + '\n' for item in toc_items])}
  </navMap>
</ncx>'''
            zf.writestr('OEBPS/toc.ncx', ncx)

        return True

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))
