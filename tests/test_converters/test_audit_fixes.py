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


# ── P0.1 — KF8 TOC off-by-one when content precedes the first <h1> ─────────────

def test_kf8_toc_offsets_with_preamble():
    from convertext.converters.ebooks.azw3 import _build_kf8_content
    doc = Document()
    doc.add_paragraph('Front matter one.')
    doc.add_paragraph('Front matter two.')
    doc.add_heading('Chapter One', 1)
    doc.add_paragraph('Body of chapter one.')
    doc.add_heading('Chapter Two', 1)
    doc.add_paragraph('Body of chapter two.')
    _text, chunk_infos, toc = _build_kf8_content(doc, 'Title')

    assert len(chunk_infos) == 3  # preamble + 2 chapters
    assert [e['label'] for e in toc] == ['Chapter One', 'Chapter Two']
    # Each TOC entry points at its OWN chapter chunk, not one chunk early.
    assert toc[0]['offset'] == chunk_infos[1].pre_start
    assert toc[1]['offset'] == chunk_infos[2].pre_start
    assert toc[0]['offset'] > chunk_infos[0].pre_start  # past the preamble


# ── P0.6 — directory config isolation + CLI override precedence ───────────────

def test_directory_config_isolation_and_cli_precedence(tmp_path, monkeypatch):
    from convertext.config import Config
    from convertext.core import ConversionEngine
    monkeypatch.setattr(Path, 'home', staticmethod(lambda: tmp_path))

    dir_a = tmp_path / 'A'
    dir_b = tmp_path / 'B'
    out_a = tmp_path / 'out_a'
    out_cli = tmp_path / 'out_cli'
    for d in (dir_a, dir_b, out_a, out_cli):
        d.mkdir()
    (dir_a / 'convertext.yaml').write_text(f"output:\n  directory: {out_a}\n")
    file_a = dir_a / 'a.txt'
    file_a.write_text('A')
    file_b = dir_b / 'b.txt'
    file_b.write_text('B')

    engine = ConversionEngine(Config())
    cfg_a = engine._effective_config(file_a)
    cfg_b = engine._effective_config(file_b)
    # Directory config applies to A but does NOT leak into B.
    assert cfg_a.get('output.directory') == str(out_a)
    assert cfg_b.get('output.directory') is None
    assert engine._get_target_path(file_a, 'md', cfg_a).parent == out_a
    assert engine._get_target_path(file_b, 'md', cfg_b).parent == dir_b

    # CLI override beats directory config.
    engine2 = ConversionEngine(Config(), overrides={'output': {'directory': str(out_cli)}})
    cfg_a2 = engine2._effective_config(file_a)
    assert cfg_a2.get('output.directory') == str(out_cli)
    assert engine2._get_target_path(file_a, 'md', cfg_a2).parent == out_cli


# ── P1.6 — MOBI title defaults to filename stem; palm name is ASCII-safe ──────

def _rec0_bytes(data: bytes) -> bytes:
    num = struct.unpack('>H', data[76:78])[0]
    offs = [struct.unpack('>I', data[78 + i * 8:82 + i * 8])[0] for i in range(num)]
    return data[offs[0]:offs[1]]


def _exth_value(data: bytes, code: int):
    rec0 = _rec0_bytes(data)
    idx = rec0.index(b'EXTH')
    count = struct.unpack('>I', rec0[idx + 8:idx + 12])[0]
    pos = idx + 12
    for _ in range(count):
        t = struct.unpack('>I', rec0[pos:pos + 4])[0]
        ln = struct.unpack('>I', rec0[pos + 4:pos + 8])[0]
        if t == code:
            return rec0[pos + 8:pos + ln].decode('utf-8', errors='ignore')
        pos += ln
    return None


def test_mobi_title_defaults_to_filename_stem():
    from convertext.converters.ebooks.mobi import ToMobiConverter
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        txt = p / 'My Great Book.txt'
        txt.write_text('Just a paragraph with no title header.')
        out = p / 'My Great Book.mobi'
        assert ToMobiConverter().convert(txt, out, {}) is True
        assert _exth_value(out.read_bytes(), 503) == 'My Great Book'


def test_mobi_palm_name_is_ascii_safe():
    from convertext.converters.ebooks.mobi import ToMobiConverter
    title = 'Café Déjà — Ω'
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        txt = p / 'x.txt'
        txt.write_text(f'{title}\n{"=" * 8}\n\nBody text.')
        out = p / 'x.mobi'
        assert ToMobiConverter().convert(txt, out, {}) is True
        palm_name = out.read_bytes()[:32].rstrip(b'\x00')
        palm_name.decode('ascii')  # ASCII-only: must not raise
        assert b' ' not in palm_name


# ── P3.5 — fb2/odt register without dependency guards ─────────────────────────

def test_fb2_and_odt_register_unconditionally():
    from convertext.registry import ConverterRegistry
    from convertext.converters.ebooks.fb2 import FB2Converter, ToFB2Converter
    from convertext.converters.documents.odt import OdtConverter
    r = ConverterRegistry()
    for c in (FB2Converter(), ToFB2Converter(), OdtConverter()):
        r.register(c)
    assert r.get_converter('fb2', 'txt') is not None
    assert r.get_converter('txt', 'fb2') is not None
    assert r.get_converter('odt', 'txt') is not None


# ── P3.1 — shared readers; txt Title/By: header survives to every writer ──────

def test_shared_read_txt_parses_header():
    from convertext.converters.readers import read_txt
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'a.txt'
        p.write_text('My Title\n========\nBy: Jane Doe\n\nBody paragraph.')
        doc = read_txt(p, {})
    assert doc.metadata.get('title') == 'My Title'
    assert doc.metadata.get('author') == 'Jane Doe'
    assert any(b.get('data') == 'Body paragraph.' for b in doc.content)


def test_txt_metadata_survives_conversions():
    import zipfile
    from convertext.converters.readers import read_txt
    from convertext.converters.documents.txt import TxtConverter
    from convertext.converters.ebooks.epub import ToEpubConverter
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        src = p / 'a.txt'
        src.write_text('My Title\n========\nBy: Jane Doe\n\nBody paragraph.')
        for fmt in ('txt', 'html', 'md'):
            out = p / f'out.{fmt}'
            assert TxtConverter().convert(src, out, {}) is True
            text = out.read_text()
            assert 'My Title' in text and 'Jane Doe' in text
        # round-trip: the txt writer's output must re-read with author intact
        rt = read_txt(p / 'out.txt', {})
        assert rt.metadata.get('author') == 'Jane Doe'
        # txt -> epub previously lost title/author (the P3.1 drift); both now survive
        epub = p / 'a.epub'
        assert ToEpubConverter().convert(src, epub, {}) is True
        with zipfile.ZipFile(epub) as z:
            name = next(n for n in z.namelist() if n.endswith('.opf'))
            opf = z.read(name).decode('utf-8', 'ignore')
        assert '<dc:title>My Title</dc:title>' in opf
        assert '<dc:creator>Jane Doe</dc:creator>' in opf


# ── P0.8 — a docx paragraph's runs stay in one paragraph (not one <p> each) ────

def test_docx_runs_grouped_into_single_paragraph():
    import docx as pydocx
    from convertext.converters.documents.docx import DocxConverter
    from convertext.converters.ebooks.mobi import _doc_to_html
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / 'in.docx'
        pd = pydocx.Document()
        para = pd.add_paragraph()
        para.add_run('The word ')
        para.add_run('bold').bold = True
        para.add_run(' is emphasized.')
        pd.save(str(path))

        doc = DocxConverter()._read_docx(path, {})
        paras = [b for b in doc.content if b['type'] == 'paragraph']
        assert not [b for b in doc.content if b['type'] == 'run']  # no standalone runs
        assert len(paras) == 1
        assert paras[0]['data'] == 'The word bold is emphasized.'
        assert 'runs' in paras[0]

        html, _ = _doc_to_html(doc)
        assert '<p>The word bold is emphasized.</p>' in html
        assert html.count('<p>') == 1  # one paragraph, not three
