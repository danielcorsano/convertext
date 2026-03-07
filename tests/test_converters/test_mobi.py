"""Tests for MOBI v6 converter."""

import struct
from pathlib import Path
import pytest

from convertext.converters.ebooks.mobi import (
    ToMobiConverter, _palmdoc_compress, _doc_to_html, _build_record0, _write_mobi,
)
from convertext.converters.base import Document


def _decompress(data: bytes) -> bytes:
    """PalmDOC decompressor for test verification."""
    result = bytearray()
    i = 0
    while i < len(data):
        b = data[i]; i += 1
        if b == 0x00:
            result.append(0)
        elif b <= 0x08:
            result.extend(data[i:i + b]); i += b
        elif b <= 0x7F:
            result.append(b)
        elif b <= 0xBF:
            if i >= len(data):
                break
            b2 = data[i]; i += 1
            dist = ((b << 8 | b2) >> 3) & 0x7FF
            length = (b2 & 0x07) + 3
            if dist == 0:
                break
            for _ in range(length):
                result.append(result[-dist])
        else:
            result.append(0x20)
            result.append(b ^ 0x80)
    return bytes(result)


def _read_mobi_structure(path: Path) -> dict:
    """Parse key fields from a MOBI file for assertion."""
    data = path.read_bytes()
    num_records = struct.unpack('>H', data[76:78])[0]
    records = [struct.unpack('>I', data[78 + i * 8:82 + i * 8])[0] for i in range(num_records)]

    r0_start = records[0]
    r0_end = records[1] if len(records) > 1 else len(data)
    r0 = data[r0_start:r0_end]

    return {
        'db_type': data[60:64],
        'db_creator': data[64:68],
        'num_records': num_records,
        'compression': struct.unpack('>H', r0[0:2])[0],
        'text_length': struct.unpack('>I', r0[4:8])[0],
        'num_text_recs': struct.unpack('>H', r0[8:10])[0],
        'mobi_identifier': r0[16:20],
        'mobi_header_len': struct.unpack('>I', r0[20:24])[0],
        'file_version': struct.unpack('>I', r0[36:40])[0],
        'encoding': struct.unpack('>I', r0[28:32])[0],
        'records': records,
        'data': data,
    }


# ── Compression roundtrip ─────────────────────────────────────────────────────

def test_palmdoc_compress_roundtrip_ascii():
    text = b'Hello world. The quick brown fox jumps over the lazy dog.'
    assert _decompress(_palmdoc_compress(text)) == text


def test_palmdoc_compress_roundtrip_repetitive():
    text = b'XYZXYZXYZXYZ' * 10
    assert _decompress(_palmdoc_compress(text)) == text


def test_palmdoc_compress_roundtrip_html():
    html = '<html><head></head><body><h1>Title</h1><p>Content here.</p></body></html>'
    data = html.encode('utf-8')
    assert _decompress(_palmdoc_compress(data)) == data


def test_palmdoc_compress_roundtrip_utf8():
    text = 'Héllo Wörld — chapter 1\nSome content with "smart quotes" and em—dashes.'
    data = text.encode('utf-8')
    assert _decompress(_palmdoc_compress(data)) == data


# ── Document to HTML ─────────────────────────────────────────────────────────

def test_doc_to_html_basic():
    doc = Document()
    doc.add_heading('Chapter One', 1)
    doc.add_paragraph('First paragraph.')
    doc.add_paragraph('Second paragraph.')
    html = _doc_to_html(doc)
    assert '<h1>Chapter One</h1>' in html
    assert '<p>First paragraph.</p>' in html
    assert '<p>Second paragraph.</p>' in html
    assert html.startswith('<html>')
    assert html.endswith('</html>')


def test_doc_to_html_pagebreak_before_second_h1():
    doc = Document()
    doc.add_heading('Chapter One', 1)
    doc.add_paragraph('Text.')
    doc.add_heading('Chapter Two', 1)
    html = _doc_to_html(doc)
    assert '<mbp:pagebreak/>' in html
    # First h1 must NOT have a pagebreak before it
    assert html.index('<h1>Chapter One') < html.index('<mbp:pagebreak/>')


def test_doc_to_html_escaping():
    doc = Document()
    doc.add_paragraph('<b>bold</b> & "quotes"')
    html = _doc_to_html(doc)
    assert '&lt;b&gt;' in html
    assert '&amp;' in html
    assert '&quot;' in html


# ── Full file structure ───────────────────────────────────────────────────────

def test_mobi_valid_palmdb(tmp_path, sample_txt):
    out = tmp_path / 'out.mobi'
    c = ToMobiConverter()
    assert c.convert(sample_txt, out, {}) is True
    assert out.exists()

    s = _read_mobi_structure(out)
    assert s['db_type'] == b'BOOK'
    assert s['db_creator'] == b'MOBI'
    assert s['compression'] == 2              # PalmDOC
    assert s['mobi_identifier'] == b'MOBI'
    assert s['mobi_header_len'] == 232        # MOBI v6
    assert s['file_version'] == 6
    assert s['encoding'] == 65001             # UTF-8


def test_mobi_text_length_matches(tmp_path, sample_txt):
    out = tmp_path / 'out.mobi'
    ToMobiConverter().convert(sample_txt, out, {})

    s = _read_mobi_structure(out)
    data = s['data']
    records = s['records']
    num_text = s['num_text_recs']

    total = 0
    for i in range(1, num_text + 1):
        start = records[i]
        end = records[i + 1] if i + 1 < len(records) else len(data)
        total += len(_decompress(data[start:end]))

    assert total == s['text_length']


def test_mobi_content_readable(tmp_path, sample_txt):
    out = tmp_path / 'out.mobi'
    ToMobiConverter().convert(sample_txt, out, {})

    s = _read_mobi_structure(out)
    data = s['data']
    records = s['records']
    num_text = s['num_text_recs']

    all_text = b''.join(
        _decompress(data[records[i]:records[i + 1] if i + 1 < len(records) else len(data)])
        for i in range(1, num_text + 1)
    ).decode('utf-8')

    assert 'Hello World' in all_text or 'hello world' in all_text.lower()


def test_mobi_from_markdown(tmp_path, sample_md):
    out = tmp_path / 'out.mobi'
    assert ToMobiConverter().convert(sample_md, out, {}) is True
    assert out.exists() and out.stat().st_size > 100


def test_mobi_from_html(tmp_path, sample_html):
    out = tmp_path / 'out.mobi'
    assert ToMobiConverter().convert(sample_html, out, {}) is True

    s = _read_mobi_structure(out)
    data = s['data']
    records = s['records']
    num_text = s['num_text_recs']

    all_text = b''.join(
        _decompress(data[records[i]:records[i + 1] if i + 1 < len(records) else len(data)])
        for i in range(1, num_text + 1)
    ).decode('utf-8')

    assert 'Test Document' in all_text
