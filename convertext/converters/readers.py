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
    soup = BeautifulSoup(markdown.markdown(content), 'html.parser')
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


def collect_blocks(soup, doc: Document) -> None:
    """Append paragraph/heading blocks from a parsed HTML tree.

    Paragraphs that contain <b>/<i>/<em>/<strong> keep their inline formatting
    as runs so rich writers can preserve bold/italic.
    """
    for el in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        text = el.get_text().strip()
        if not text:
            continue
        if el.name.startswith('h'):
            doc.add_heading(text, int(el.name[1]))
        else:
            runs = _paragraph_runs(el)
            if any(r['bold'] or r['italic'] for r in runs):
                doc.add_paragraph(text, runs=runs)
            else:
                doc.add_paragraph(text)
