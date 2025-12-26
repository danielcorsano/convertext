"""Direct PDF to EPUB converter."""

import datetime as dt
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List

import pypdf

from convertext.converters.base import BaseConverter, Document


class PdfToEpubConverter(BaseConverter):
    """Convert PDF directly to EPUB preserving structure and metadata."""

    @property
    def input_formats(self) -> List[str]:
        return ['pdf']

    @property
    def output_formats(self) -> List[str]:
        return ['epub']

    def can_convert(self, source: str, target: str) -> bool:
        return source == 'pdf' and target == 'epub'

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert PDF to EPUB directly."""
        doc = self._read_pdf(source_path, config)

        # Use PDF metadata for title/author, fall back to filename
        if not doc.metadata.get('title'):
            doc.metadata['title'] = source_path.stem
        if not doc.metadata.get('author'):
            doc.metadata['author'] = 'Unknown'

        return self._create_epub(doc, target_path, config)

    def _read_pdf(self, path: Path, config: Dict[str, Any]) -> Document:
        """Read PDF into intermediate Document."""
        doc = Document()

        with open(path, 'rb') as f:
            reader = pypdf.PdfReader(f)

            # Extract metadata
            if reader.metadata:
                title = reader.metadata.get('/Title', '')
                author = reader.metadata.get('/Author', '')
                subject = reader.metadata.get('/Subject', '')

                if title and title.strip():
                    doc.metadata['title'] = title.strip()
                if author and author.strip():
                    doc.metadata['author'] = author.strip()
                if subject and subject.strip():
                    doc.metadata['subject'] = subject.strip()

            # Extract text content
            for page in reader.pages:
                text = page.extract_text()
                if text.strip():
                    # Split into paragraphs (each line is typically a paragraph or heading)
                    for line in text.split('\n'):
                        line = line.strip()
                        if line:
                            doc.add_paragraph(line)

        return doc

    def _create_epub(self, doc: Document, path: Path, config: Dict[str, Any]) -> bool:
        """Create EPUB from Document."""
        title = doc.metadata.get('title', 'Untitled')
        author = doc.metadata.get('author', 'Unknown')
        language = doc.metadata.get('language', 'en')
        uid = str(uuid.uuid4())

        # Split content into chapters (simple approach: one chapter)
        content_html = []
        for block in doc.content:
            if block['type'] == 'heading':
                level = block['level']
                content_html.append(f'<h{level}>{self._escape_html(block["data"])}</h{level}>')
            elif block['type'] in ['paragraph', 'text']:
                content_html.append(f'<p>{self._escape_html(block["data"])}</p>')

        if not content_html:
            content_html = ['<p>No content</p>']

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

            # Chapter XHTML
            xhtml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
  <title>{self._escape_html(title)}</title>
</head>
<body>
{''.join(content_html)}
</body>
</html>'''
            zf.writestr('OEBPS/chapter.xhtml', xhtml)

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
    <item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="chapter"/>
  </spine>
</package>'''
            zf.writestr('OEBPS/content.opf', opf)

            # toc.ncx
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
    <navPoint id="navPoint-1" playOrder="1">
      <navLabel><text>{self._escape_html(title)}</text></navLabel>
      <content src="chapter.xhtml"/>
    </navPoint>
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
