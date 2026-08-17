"""Shared source readers producing the intermediate Document.

One implementation each for plain text, HTML and Markdown, used by every
converter that ingests these formats. Plain-text parsing understands the
``Title`` / ``=====`` / ``By: Author`` header; HTML and Markdown capture
paragraphs and headings (h1-h6).
"""

import base64
import hashlib
import posixpath
import re
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import unquote

from convertext.converters.base import Document


def _encoding(config: Optional[Dict[str, Any]]) -> str:
    return (config or {}).get('documents', {}).get('encoding', 'utf-8')


def read_txt(path: Path, config: Optional[Dict[str, Any]] = None) -> Document:
    """Read plain text, honoring an optional Title / By: header."""
    doc = Document()
    with open(path, 'r', encoding=_encoding(config)) as f:
        content = f.read()

    lines = content.split('\n')
    i = 0
    if len(lines) >= 2 and lines[1].strip() and all(c == '=' for c in lines[1].strip()):
        doc.metadata['title'] = lines[0].strip()
        i = 2
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i < len(lines) and lines[i].startswith('By:'):
            doc.metadata['author'] = lines[i][3:].strip()
            i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1

    for para in '\n'.join(lines[i:]).split('\n\n'):
        if para.strip():
            doc.add_paragraph(para.strip())
    return doc


def image_format(filename: str) -> str:
    """Normalise an image filename's extension to the format tag writers use."""
    fmt = Path(filename).suffix.lstrip('.').lower()
    return 'jpg' if fmt in ('', 'jpeg') else fmt


def file_image_resolver(base_dir: Path):
    """Return a resolver mapping an <img> src to (name, data, format).

    Handles both files beside the document and inline ``data:`` URIs, the two
    ways a standalone HTML page carries images.
    """
    def resolve(href: str):
        if href.startswith('data:'):
            header, _, payload = href.partition(',')
            if 'base64' not in header:
                return None
            try:
                data = base64.b64decode(payload)
            except Exception:
                return None
            subtype = header.split('/')[-1].split(';')[0]
            name = f'data:{hashlib.md5(data).hexdigest()[:12]}'
            return name, data, image_format(f'x.{subtype}')

        target = base_dir / unquote(href)
        try:
            data = target.read_bytes()
        except Exception:
            return None
        return str(target), data, image_format(target.name)

    return resolve


def read_html(path: Path, config: Optional[Dict[str, Any]] = None) -> Document:
    """Read HTML (or .htm), capturing title, paragraphs, headings and images."""
    from bs4 import BeautifulSoup
    doc = Document()
    with open(path, 'r', encoding=_encoding(config)) as f:
        content = f.read()
    soup = BeautifulSoup(content, 'html.parser')

    title_tag = soup.find('title')
    if title_tag and title_tag.get_text().strip():
        doc.metadata['title'] = title_tag.get_text().strip()
    else:
        h1 = soup.find('h1')
        if h1 and h1.get_text().strip():
            doc.metadata['title'] = h1.get_text().strip()

    collect_blocks(soup, doc, src=path.name,
                   resolve_image=file_image_resolver(path.parent))
    return doc


def read_markdown(path: Path, config: Optional[Dict[str, Any]] = None) -> Document:
    """Read Markdown, capturing paragraphs and headings."""
    import markdown
    from bs4 import BeautifulSoup
    doc = Document()
    with open(path, 'r', encoding=_encoding(config)) as f:
        content = f.read()
    html = markdown.markdown(content, extensions=['tables', 'fenced_code'])
    soup = BeautifulSoup(html, 'html.parser')
    collect_blocks(soup, doc)
    return doc


_PDF_MIN_IMAGE_BYTES = 4096  # below this it is a rule, bullet or scan artefact


def read_pdf(path: Path, config: Optional[Dict[str, Any]] = None) -> Document:
    """Read a PDF, grouping lines into paragraphs and detecting simple headings.

    Images are collected per page and emitted before that page's text: a PDF
    records text and images as separate streams, so their true position within
    the page's flow is not recoverable.
    """
    import pypdf
    doc = Document()
    with open(path, 'rb') as f:
        reader = pypdf.PdfReader(f)
        meta = reader.metadata
        if meta:
            for key, tag in (('title', '/Title'), ('author', '/Author'), ('subject', '/Subject')):
                val = meta.get(tag)
                if val and str(val).strip():
                    doc.metadata[key] = str(val).strip()
        for number, page in enumerate(reader.pages):
            _pdf_page_images(page, number, doc)
            _pdf_page_to_blocks(page.extract_text() or '', doc)
    return doc


def _pdf_page_images(page, number: int, doc: Document) -> None:
    """Add a page's embedded images, skipping decorations and unreadable ones."""
    try:
        images = list(page.images)
    except Exception:
        return
    for index, image in enumerate(images):
        try:
            data = image.data
        except Exception:
            continue
        if not data or len(data) < _PDF_MIN_IMAGE_BYTES:
            continue
        name = f'pdf:p{number}:{index}:{image.name or "image"}'
        doc.add_image(name, data, image_format(image.name or ''))


def _pdf_is_heading(line: str) -> bool:
    if len(line) >= 60:
        return False
    if re.match(r'^(chapter|part)\s+(\d+|[ivxlcdm]+)\b', line, re.I):
        return True
    letters = [c for c in line if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def _pdf_page_to_blocks(text: str, doc: Document) -> None:
    """Split extracted page text into paragraphs, treating short caps/chapter
    lines as h1 headings."""
    para: list = []

    def flush():
        if para:
            doc.add_paragraph(' '.join(para).strip())
            para.clear()

    for raw in text.split('\n'):
        line = raw.strip()
        if not line:
            flush()
        elif _pdf_is_heading(line):
            flush()
            doc.add_heading(line, 1)
        else:
            para.append(line)
    flush()


def _paragraph_runs(el):
    """Split a <p>-like element into inline runs carrying bold/italic/href."""
    from bs4 import NavigableString
    runs = []

    def walk(node, bold, italic, href):
        for child in node.children:
            if isinstance(child, NavigableString):
                s = str(child)
                if s:
                    run = {'text': s, 'bold': bold, 'italic': italic}
                    if href:
                        run['href'] = href
                    runs.append(run)
            else:
                name = (child.name or '').lower()
                walk(child, bold or name in ('b', 'strong'), italic or name in ('i', 'em'),
                     child.get('href') if name == 'a' else href)

    walk(el, False, False, None)
    return runs


_HEADINGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
_CONTAINERS = ['ul', 'ol', 'table', 'blockquote']


def collect_blocks(soup, doc: Document, src: str = '', resolve_image=None) -> None:
    """Append content blocks from a parsed HTML tree.

    Captures headings, paragraphs (keeping <b>/<i>/<em>/<strong> as runs so rich
    writers preserve bold/italic, and <a href> as a run's href), lists, tables,
    blockquotes and code blocks. Elements nested inside a captured container are
    skipped (rendered whole).

    ``src`` names the source document so element ids become ``anchors`` on the
    next block, letting ebook writers resolve internal links. ``resolve_image``
    maps an <img> src to ``(name, data, format)`` (or None) to capture inline
    images; omitted, images are ignored as before.
    """
    for br in soup.find_all('br'):
        br.replace_with('\n')  # <br> yields no text, fusing the words around it

    tags = ['p', 'pre', 'div', *_HEADINGS, *_CONTAINERS]
    tagset = set(tags)
    pending = [src] if src else []
    seen_images = set()
    src_dir = posixpath.dirname(src)

    def anchor_key(href):
        """Rewrite a document-relative href to the same key space as ``anchors``."""
        if not href or '://' in href:
            return href
        href = unquote(href)  # hrefs are URIs; the paths they name are not encoded
        if href.startswith('#'):
            return f'{src}{href}'
        target, _, fragment = href.partition('#')
        target = posixpath.normpath(posixpath.join(src_dir, target)) if src_dir else target
        return f'{target}#{fragment}' if fragment else target

    def attach(index):
        """Point queued ids at the first block this element produced."""
        if pending and index < len(doc.content):
            doc.content[index].setdefault('anchors', []).extend(pending)
            pending.clear()

    def add_images(el):
        if resolve_image is None:
            return
        for img in ([el] if el.name == 'img' else el.find_all('img')):
            if id(img) in seen_images:
                continue
            seen_images.add(id(img))
            resolved = resolve_image(img.get('src')) if img.get('src') else None
            if resolved:
                doc.add_image(*resolved)

    for el in soup.find_all(lambda t: t.name in tagset or t.name == 'img' or t.has_attr('id')):
        if el.has_attr('id'):
            pending.append(f"{src}#{el['id']}")

        name = (el.name or '').lower()
        start = len(doc.content)

        if name == 'img':
            add_images(el)
            attach(start)
            continue
        if name not in tagset or el.find_parent(_CONTAINERS):
            continue  # unanchored tag, or rendered as part of its enclosing container

        # Only leaf content <div>s become paragraphs; container divs are skipped,
        # so div-structured EPUBs survive and content is not double-captured.
        if name == 'div' and el.find(tags):
            continue

        add_images(el)  # inline images precede the text they title or illustrate

        if name in _HEADINGS:
            text = el.get_text().strip()
            if text:
                doc.add_heading(text, int(name[1]))

        elif name in ('ul', 'ol'):
            items = [li.get_text().strip() for li in el.find_all('li', recursive=False)
                     if li.get_text().strip()]
            if items:
                doc.add_list(items, ordered=(name == 'ol'))

        elif name == 'table':
            rows = []
            for tr in el.find_all('tr'):
                cells = [c.get_text().strip() for c in tr.find_all(['td', 'th'])]
                if cells:
                    rows.append(cells)
            if rows:
                first = el.find('tr')
                if first is not None and first.find('th') is not None:
                    doc.add_table(rows=rows[1:], headers=rows[0])
                else:
                    doc.add_table(rows=rows)

        else:  # p, pre, blockquote, leaf div
            text = el.get_text().strip()
            if text:
                runs = _paragraph_runs(el)
                for run in runs:
                    if run.get('href'):
                        run['href'] = anchor_key(run['href'])
                if any(r['bold'] or r['italic'] or r.get('href') for r in runs):
                    doc.add_paragraph(text, runs=runs)
                else:
                    doc.add_paragraph(text)

        attach(start)
