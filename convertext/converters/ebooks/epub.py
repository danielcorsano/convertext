"""EPUB format converter - native Python implementation."""

import datetime as dt
import posixpath
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import unquote
import zipfile
from lxml import etree
from bs4 import BeautifulSoup

from convertext.converters.readers import read_html, read_markdown, read_txt, collect_blocks
from convertext.converters.ebooks.htmlbuild import block_to_html
from convertext.converters.utils import escape_html
from convertext.converters.base import BaseConverter, Document

class EpubConverter(BaseConverter):
    """Lightweight EPUB format converter (native Python)."""

    @property
    def input_formats(self) -> List[str]:
        return ['epub']

    @property
    def output_formats(self) -> List[str]:
        return ['txt', 'html', 'md']

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert EPUB to target format."""
        doc = self._read_epub(source_path, config)
        self._apply_metadata_overrides(doc, source_path, config)

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
            base_dir = '' if str(Path(opf_path).parent) in ('', '.') else str(Path(opf_path).parent)

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

            for tag, key in [('dc:description', 'description'), ('dc:publisher', 'publisher'),
                             ('dc:subject', 'subject'), ('dc:date', 'date')]:
                el = opf.find(f'.//{tag}', ns)
                if el is not None and el.text:
                    doc.metadata[key] = el.text.strip()

            # Get spine order (reading order)
            manifest = {item.get('id'): item.get('href')
                       for item in opf.findall('.//opf:manifest/opf:item', ns)}
            manifest_types = {item.get('id'): item.get('media-type', '')
                             for item in opf.findall('.//opf:manifest/opf:item', ns)}

            # Extract cover image
            cover_id = None
            cover_meta = opf.find('.//opf:metadata/opf:meta[@name="cover"]', ns)
            if cover_meta is not None:
                cover_id = cover_meta.get('content')
            if not cover_id:
                for item in opf.findall('.//opf:manifest/opf:item', ns):
                    if 'cover-image' in (item.get('properties') or ''):
                        cover_id = item.get('id')
                        break
            if cover_id and cover_id in manifest:
                cover_href = _zpath(base_dir, manifest[cover_id])
                try:
                    cover_data = zf.read(cover_href)
                    fmt = manifest_types.get(cover_id, '').split('/')[-1].replace('jpeg', 'jpg')
                    doc.images['cover'] = {'data': cover_data, 'format': fmt or 'jpg'}
                except Exception:
                    pass

            doc.toc = _read_toc(zf, opf, ns, manifest, base_dir)

            spine_items = opf.findall('.//opf:spine/opf:itemref', ns)

            # Read content in spine order
            for itemref in spine_items:
                idref = itemref.get('idref')
                if idref in manifest:
                    content_path = _zpath(base_dir, manifest[idref])

                    try:
                        content = zf.read(content_path).decode('utf-8', errors='ignore')
                        soup = BeautifulSoup(content, 'html.parser')
                        collect_blocks(soup, doc, src=content_path,
                                       resolve_image=_image_resolver(zf, content_path))
                    except Exception:
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

class ToEpubConverter(BaseConverter):
    """Convert various formats to EPUB."""

    @property
    def input_formats(self) -> List[str]:
        return ['txt', 'html', 'htm', 'md']

    @property
    def output_formats(self) -> List[str]:
        return ['epub']

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert to EPUB."""
        source_fmt = source_path.suffix.lstrip('.').lower()

        if source_fmt == 'txt':
            doc = read_txt(source_path, config)
        elif source_fmt in ['html', 'htm']:
            doc = read_html(source_path, config)
        elif source_fmt in ['md', 'markdown']:
            doc = read_markdown(source_path, config)
        else:
            return False
        self._apply_metadata_overrides(doc, source_path, config)

        return self._create_epub(doc, target_path, config, target_path.stem)

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
            if block['type'] == 'heading' and block.get('level', 1) == 1:
                if current_chapter:
                    chapters.append(current_chapter)
                    current_chapter = []
                chapter_titles.append(block['data'])
            frag = block_to_html(block, escape=escape_html)
            if frag:
                current_chapter.append(frag)

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
                toc_items.append(f'    <navPoint id="navPoint-{i}" playOrder="{i}">\n      <navLabel><text>{escape_html(chapter_title)}</text></navLabel>\n      <content src="{filename}"/>\n    </navPoint>')

                # Write chapter XHTML
                xhtml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
  <title>{escape_html(chapter_title)}</title>
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
    <dc:title>{escape_html(title)}</dc:title>
    <dc:creator>{escape_html(author)}</dc:creator>
    <dc:language>{language}</dc:language>
    <meta property="dcterms:modified">{dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}</meta>
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
    <text>{escape_html(title)}</text>
  </docTitle>
  <navMap>
{''.join([item + '\n' for item in toc_items])}
  </navMap>
</ncx>'''
            zf.writestr('OEBPS/toc.ncx', ncx)

        return True

# ── EPUB source helpers ───────────────────────────────────────────────────────

_NCX_NS = {'n': 'http://www.daisy.org/z3986/2005/ncx/'}

def _zpath(base: str, href: str) -> str:
    """Resolve an href against a directory inside the zip.

    Hrefs in the OPF and NCX are URIs, so they are percent-encoded while the zip
    entries are not; without unquoting, any path with a space never matches.
    """
    href = unquote(href)
    return posixpath.normpath(posixpath.join(base, href)) if base else href

def _image_resolver(zf, doc_path: str):
    """Return a resolver mapping an <img> src to (name, data, format)."""
    base = posixpath.dirname(doc_path)

    def resolve(href: str):
        try:
            path = _zpath(base, href)
            data = zf.read(path)
        except Exception:
            return None
        fmt = Path(path).suffix.lstrip('.').lower() or 'jpg'
        return path, data, 'jpg' if fmt == 'jpeg' else fmt

    return resolve

def _read_toc(zf, opf, ns: dict, manifest: dict, base_dir: str) -> List[Dict[str, Any]]:
    """Read the book's own navigation into flat entries (label, src, fragment, level)."""
    entries: List[Dict[str, Any]] = []

    spine = opf.find('.//opf:spine', ns)
    ncx_id = spine.get('toc') if spine is not None else None
    if not ncx_id:
        for item in opf.findall('.//opf:manifest/opf:item', ns):
            if item.get('media-type') == 'application/x-dtbncx+xml':
                ncx_id = item.get('id')
                break

    if ncx_id and ncx_id in manifest:
        ncx_path = _zpath(base_dir, manifest[ncx_id])
        ncx_dir = posixpath.dirname(ncx_path)
        try:
            nav_map = etree.fromstring(zf.read(ncx_path)).find('n:navMap', _NCX_NS)
        except Exception:
            nav_map = None

        def walk(node, level):
            for np in node.findall('n:navPoint', _NCX_NS):
                label = np.find('n:navLabel/n:text', _NCX_NS)
                content = np.find('n:content', _NCX_NS)
                src = content.get('src') if content is not None else None
                if label is not None and src:
                    target, _, fragment = src.partition('#')
                    entries.append({'label': (label.text or '').strip(),
                                    'src': _zpath(ncx_dir, target),
                                    'fragment': unquote(fragment), 'level': level})
                walk(np, level + 1)

        if nav_map is not None:
            walk(nav_map, 0)

    if entries:
        return entries

    # EPUB 3 navigation document
    for item in opf.findall('.//opf:manifest/opf:item', ns):
        if 'nav' not in (item.get('properties') or '').split():
            continue
        nav_path = _zpath(base_dir, item.get('href'))
        try:
            soup = BeautifulSoup(zf.read(nav_path).decode('utf-8', 'ignore'), 'html.parser')
        except Exception:
            break
        nav = soup.find('nav', attrs={'epub:type': 'toc'}) or soup.find('nav')
        if nav is None:
            break
        nav_dir = posixpath.dirname(nav_path)
        for a in nav.find_all('a', href=True):
            target, _, fragment = a['href'].partition('#')
            entries.append({'label': a.get_text().strip(),
                            'src': _zpath(nav_dir, target), 'fragment': unquote(fragment),
                            'level': max(len(a.find_parents('ol')) - 1, 0)})
        break

    return entries

