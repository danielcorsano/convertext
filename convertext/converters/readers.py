"""Shared source readers producing the intermediate Document.

One implementation each for plain text, HTML and Markdown, used by every
converter that ingests these formats. Plain-text parsing understands the
``Title`` / ``=====`` / ``By: Author`` header; HTML and Markdown capture
paragraphs and headings (h1-h6).
"""

from pathlib import Path
from typing import Any, Dict, Optional

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


def read_html(path: Path, config: Optional[Dict[str, Any]] = None) -> Document:
    """Read HTML (or .htm), capturing title, paragraphs and headings."""
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

    collect_blocks(soup, doc)
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


def _paragraph_runs(el):
    """Split a <p>-like element into inline runs carrying bold/italic flags."""
    from bs4 import NavigableString
    runs = []

    def walk(node, bold, italic):
        for child in node.children:
            if isinstance(child, NavigableString):
                s = str(child)
                if s:
                    runs.append({'text': s, 'bold': bold, 'italic': italic})
            else:
                name = (child.name or '').lower()
                walk(child, bold or name in ('b', 'strong'), italic or name in ('i', 'em'))

    walk(el, False, False)
    return runs


_HEADINGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
_CONTAINERS = ['ul', 'ol', 'table', 'blockquote']


def collect_blocks(soup, doc: Document) -> None:
    """Append content blocks from a parsed HTML tree.

    Captures headings, paragraphs (keeping <b>/<i>/<em>/<strong> as runs so rich
    writers preserve bold/italic), lists, tables, blockquotes and code blocks.
    Elements nested inside a captured container are skipped (rendered whole).
    """
    tags = ['p', 'pre', 'div', *_HEADINGS, *_CONTAINERS]
    for el in soup.find_all(tags):
        if el.find_parent(_CONTAINERS):
            continue  # rendered as part of its enclosing container
        name = el.name.lower()

        # Only leaf content <div>s become paragraphs; container divs are skipped,
        # so div-structured EPUBs survive and content is not double-captured.
        if name == 'div' and el.find(tags):
            continue

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
            if not text:
                continue
            runs = _paragraph_runs(el)
            if any(r['bold'] or r['italic'] for r in runs):
                doc.add_paragraph(text, runs=runs)
            else:
                doc.add_paragraph(text)
