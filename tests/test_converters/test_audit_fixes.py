"""Regression tests for audit fixes (see plan/AUDIT_HANDOUT.md)."""

import inspect
import struct
import tempfile
from pathlib import Path

from convertext.converters.base import Document
from convertext.converters.ebooks import mobi as M
from convertext.converters.ebooks.azw3 import Azw3Converter


def _readback_text(path: Path) -> str:
    doc = Azw3Converter()._read_azw3(path, {})
    return ' '.join(b.get('data', '') for b in doc.content)


def _exth_types(exth: bytes):
    assert exth[:4] == b'EXTH'
    count = struct.unpack('>I', exth[8:12])[0]
    pos, types = 12, []
    for _ in range(count):
        types.append(struct.unpack('>I', exth[pos:pos + 4])[0])
        pos += struct.unpack('>I', exth[pos + 4:pos + 8])[0]
    return types


# ── P0.2 — datetime.UTC crash on Python 3.9/3.10 ──────────────────────────────

def test_epub_datetime_uses_timezone_utc():
    import convertext.converters.ebooks.epub as epub_mod
    import convertext.converters.documents.pdf_to_epub as p2e_mod
    for mod in (epub_mod, p2e_mod):
        src = inspect.getsource(mod)
        assert 'dt.UTC' not in src, f"{mod.__name__} uses dt.UTC (crashes on <3.11)"
        assert 'dt.timezone.utc' in src


def test_txt_to_epub_succeeds():
    from convertext.converters.ebooks.epub import ToEpubConverter
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        txt = p / 'a.txt'
        txt.write_text('Title\n=====\nBy: Me\n\nHello world.')
        out = p / 'a.epub'
        assert ToEpubConverter().convert(txt, out, {}) is True
        assert out.stat().st_size > 0


# ── P0.3 — multi-byte char split across a 4096-byte record boundary ───────────

def test_reader_multibyte_across_record_boundary():
    # Locate the byte offset where the first paragraph's text begins.
    probe = Document()
    probe.metadata['title'] = 'T'
    probe.add_paragraph('MARK' + 'a' * 5000)
    html_bytes = M._doc_to_html(probe)[0].encode('utf-8')
    start = html_bytes.index(b'MARK')

    pad = 4095 - start  # place é's first byte at global offset 4095 → straddles 4096
    assert pad > 0
    doc = Document()
    doc.metadata['title'] = 'T'
    doc.add_paragraph('a' * pad + 'é' + 'b' * 300)

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / 'boundary.mobi'
        M._write_mobi(doc, path)
        assert 'é' in _readback_text(path)


# ── P0.5 — last text record with no trailing FLIS/FCIS/EOF ─────────────────────

def test_reader_reads_last_record_without_trailers():
    doc = Document()
    doc.metadata['title'] = 'T'
    html = ('<html><head></head><body>'
            '<p>ENDINGMARKER_UNIQUE</p></body></html>').encode('utf-8')
    compressed = [M._palmdoc_compress(html[i:i + 4096])
                  for i in range(0, len(html), 4096)]
    rec0 = M._build_record0(doc, len(html), len(compressed), 0, 0,
                            M._build_exth('T', 'A'))
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / 'no_trailers.mobi'
        M._write_palmdb(path, [rec0] + compressed, 'T')  # last record is text
        assert 'ENDINGMARKER_UNIQUE' in _readback_text(path)


# ── P0.10 — .htm sources route to ebook converters ────────────────────────────

def test_htm_input_accepted_by_ebook_converters():
    from convertext.converters.ebooks.mobi import ToMobiConverter
    from convertext.converters.ebooks.azw3 import ToAzw3Converter
    from convertext.converters.ebooks.epub import ToEpubConverter
    from convertext.converters.ebooks.fb2 import ToFB2Converter
    assert ToMobiConverter().can_convert('htm', 'mobi')
    assert ToAzw3Converter().can_convert('htm', 'azw3')
    assert ToEpubConverter().can_convert('htm', 'epub')
    assert ToFB2Converter().can_convert('htm', 'fb2')


def test_htm_converts_to_mobi():
    from convertext.converters.ebooks.mobi import ToMobiConverter
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        htm = p / 'test.htm'
        htm.write_text('<html><head><title>T</title></head><body>'
                       '<h1>Chapter</h1><p>Body text here.</p></body></html>')
        out = p / 'test.mobi'
        assert ToMobiConverter().convert(htm, out, {}) is True
        assert out.stat().st_size > 0


# ── P1.8 — EXTH 106 (date) only present when the source has a date ─────────────

def test_exth_omits_date_when_absent():
    from convertext.converters.ebooks.mobi import _build_exth as mobi_exth
    from convertext.converters.ebooks.azw3 import _build_exth as azw3_exth
    for build in (mobi_exth, azw3_exth):
        assert 106 not in _exth_types(build('T', 'A', metadata={}))
        assert 106 in _exth_types(build('T', 'A', metadata={'date': '2021-05-01'}))
