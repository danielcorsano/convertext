"""Kindle-safe HTML fragment rendering for Document content blocks.

One renderer shared by the MOBI v6, KF8/AZW3 and EPUB writers so every block
type is emitted the same way. Callers pass their own escape function (MOBI/KF8
use html.escape, EPUB uses converters.utils.escape_html) and interleave their
own structure (page breaks, chapters, TOC offsets). Images produce no inline
HTML here (inline image records are a separate feature); callers may count them.
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


def block_to_html(block: dict, escape=None) -> str:
    """Render one content block to a Kindle-safe HTML fragment ('' if empty)."""
    if escape is None:
        escape = _default_escape
    t = block.get('type')

    if t == 'heading':
        level = block.get('level', 1)
        return f'<h{level}>{escape(block.get("data", ""))}</h{level}>'

    if t in ('paragraph', 'text'):
        runs = block.get('runs')
        if runs:
            inner = ''.join(_run_html(r, escape) for r in runs)
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

    return ''  # image / unknown: no inline HTML
