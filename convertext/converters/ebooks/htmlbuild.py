"""Kindle-safe HTML fragment rendering for Document content blocks.

One renderer shared by the MOBI v6, KF8/AZW3 and EPUB writers so every block
type is emitted the same way. Callers pass their own escape function (MOBI/KF8
use html.escape, EPUB uses converters.utils.escape_html) and interleave their
own structure (page breaks, chapters, TOC offsets). Images render only when the
caller supplies an ``img_ref`` resolver, since the recindex depends on the
writer's record layout.
"""

import html as _html


def _default_escape(s: str) -> str:
    return _html.escape(s, quote=True)


def _run_html(run: dict, escape) -> str:
    s = escape(run.get('text', ''))
    if run.get('bold'):
        s = f'<b>{s}</b>'
    if run.get('italic'):
        s = f'<i>{s}</i>'
    return s


def _runs_html(runs: list, escape, link_ref) -> str:
    """Render runs, wrapping consecutive runs that share an href in one anchor."""
    out = []
    i = 0
    while i < len(runs):
        href = runs[i].get('href')
        j = i
        while j < len(runs) and runs[j].get('href') == href:
            j += 1
        inner = ''.join(_run_html(r, escape) for r in runs[i:j])
        attr = link_ref(href) if href and link_ref else None
        out.append(f'<a {attr}>{inner}</a>' if attr else inner)
        i = j
    return ''.join(out)


def block_to_html(block: dict, escape=None, img_ref=None, link_ref=None) -> str:
    """Render one content block to a Kindle-safe HTML fragment ('' if empty).

    ``img_ref`` maps an image block's name to a complete ``<img>`` tag (each
    format spells the reference differently — MOBI uses ``recindex``, EPUB a
    ``src`` path) and ``link_ref`` maps a run's href to anchor attributes.
    Without them images and links render as before: dropped, and as plain text.
    """
    if escape is None:
        escape = _default_escape
    t = block.get('type')

    if t == 'image':
        return (img_ref(block.get('name')) or '') if img_ref else ''

    if t == 'heading':
        level = block.get('level', 1)
        return f'<h{level}>{escape(block.get("data", ""))}</h{level}>'

    if t in ('paragraph', 'text'):
        runs = block.get('runs')
        if runs:
            inner = _runs_html(runs, escape, link_ref)
        else:
            inner = escape(block.get('data', ''))
        return f'<p>{inner}</p>' if inner else ''

    if t == 'run':
        inner = _run_html(block, escape)
        return f'<p>{inner}</p>' if inner else ''

    if t == 'table':
        parts = ['<table>']
        headers = block.get('headers')
        if headers:
            parts.append('<tr>' + ''.join(f'<th>{escape(str(h))}</th>' for h in headers) + '</tr>')
        for row in block.get('rows', []):
            parts.append('<tr>' + ''.join(f'<td>{escape(str(c))}</td>' for c in row) + '</tr>')
        parts.append('</table>')
        return ''.join(parts)

    if t == 'list':
        tag = 'ol' if block.get('ordered') else 'ul'
        items = ''.join(f'<li>{escape(str(it))}</li>' for it in block.get('items', []))
        return f'<{tag}>{items}</{tag}>' if items else ''

    if t == 'link':
        return f'<p>{escape(block.get("text", ""))} ({escape(block.get("url", ""))})</p>'

    return ''  # unknown block type: no inline HTML
