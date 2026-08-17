"""Kindle navigation, inline images and formatting (see plan/kindle_nav_plan.md).

Covers the chapter-linking work plus regressions that lock the text layer and
record layout, which were already device-verified before these changes.
"""

import re
import struct
import tempfile
from pathlib import Path

from convertext.converters.base import Document
from convertext.converters.ebooks import mobi as M
from convertext.converters.ebooks.epub import EpubConverter
from convertext.converters.ebooks.htmlbuild import block_to_html
from convertext.converters.ebooks.palmdoc import palmdoc_decompress
from convertext.converters.readers import read_html

EPUB = Path(__file__).resolve().parents[2] / 'test_files' / 'test.epub'


def _rawml(path: Path) -> bytes:
    """Decompress a MOBI's text records back to the markup the Kindle parses."""
    data = path.read_bytes()
    count = struct.unpack('>H', data[76:78])[0]
    offsets = [struct.unpack('>I', data[78 + 8 * i:82 + 8 * i])[0] for i in range(count)]
    offsets.append(len(data))
    num_text = struct.unpack('>H', data[offsets[0] + 8:offsets[0] + 10])[0]
    return b''.join(palmdoc_decompress(data[offsets[i]:offsets[i + 1]])
                    for i in range(1, 1 + num_text))


def _exth(path: Path) -> dict:
    data = path.read_bytes()
    start = struct.unpack('>I', data[78:82])[0]
    rec0 = data[start:struct.unpack('>I', data[86:90])[0]]
    i = rec0.find(b'EXTH')
    count = struct.unpack('>I', rec0[i + 8:i + 12])[0]
    pos, out = i + 12, {}
    for _ in range(count):
        code, length = struct.unpack('>II', rec0[pos:pos + 8])
        out[code] = rec0[pos + 8:pos + length]
        pos += length
    return out


# ── Reader: the book's own navigation is what drives the TOC ──────────────────

def test_epub_toc_is_read():
    doc = EpubConverter()._read_epub(EPUB, {})
    assert doc.toc, "EPUB navigation was not read"
    assert doc.toc[0]['label'] == 'Document'
    assert doc.toc[0]['src'] == 'OEBPS/chapter.xhtml'


def test_toc_targets_resolve_to_anchors():
    doc = EpubConverter()._read_epub(EPUB, {})
    anchors = {a for b in doc.content for a in b.get('anchors', ())}
    for entry in doc.toc:
        key = M._entry_key(entry)
        assert key in anchors, f"TOC target {key} has nothing to point at"


def test_percent_encoded_hrefs_resolve_to_zip_paths():
    # NCX/OPF hrefs are URIs; zip entries are not encoded, so a path with a
    # space only matches once unquoted (real EPUBs from Calibre do this).
    from convertext.converters.ebooks.epub import _zpath
    assert _zpath('OEBPS', 'Some%20Book_split_004.htm') == 'OEBPS/Some Book_split_004.htm'
    assert _zpath('', 'plain.xhtml') == 'plain.xhtml'


def test_unreachable_links_render_as_text_not_dead_anchors():
    doc = Document()
    doc.metadata['title'] = 'T'
    doc.add_paragraph('x', runs=[{'text': 'nowhere', 'bold': False, 'italic': False,
                                  'href': 'missing.xhtml#gone'}])
    html, _toc, _start = M._doc_to_html(doc)
    assert '<a ' not in html and 'nowhere' in html


def test_br_separates_the_words_around_it():
    with tempfile.TemporaryDirectory() as d:
        page = Path(d) / 'title.html'
        page.write_text('<html><body><h2>Ursula K.<br/>Le Guin</h2></body></html>')
        doc = read_html(page)
    assert 'Ursula K.Le Guin' not in doc.content[0]['data']


# ── Writer: filepos links ──────────────────────────────────────────────────────

def _linked_doc():
    doc = Document()
    doc.metadata['title'] = 'T'
    doc.add_paragraph('Contents', runs=[{'text': 'Go to chapter', 'bold': False,
                                         'italic': False, 'href': 'c.xhtml#one'}])
    doc.add_paragraph('Body before the target.')
    doc.add_heading('Chapter One', 1)
    doc.content[-1]['anchors'] = ['c.xhtml#one']
    doc.add_paragraph('Chapter body.')
    return doc


def test_filepos_links_are_patched_and_land_on_target():
    html, _toc, _start = M._doc_to_html(_linked_doc())
    assert 'filepos=0000000000' not in html, "a link was left unresolved"
    offset = int(re.search(r'filepos=(\d+)', html).group(1))
    assert html.encode('utf-8')[offset:offset + 4] == b'<h1>'


def test_external_links_are_not_turned_into_filepos():
    doc = Document()
    doc.metadata['title'] = 'T'
    doc.add_paragraph('x', runs=[{'text': 'site', 'bold': False, 'italic': False,
                                  'href': 'https://example.com'}])
    html, _toc, _start = M._doc_to_html(doc)
    assert 'filepos' not in html


def test_toc_entries_come_from_document_toc_not_headings():
    doc = _linked_doc()
    doc.toc = [{'label': 'Chapter One', 'src': 'c.xhtml', 'fragment': 'one', 'level': 0}]
    _html, toc, _start = M._doc_to_html(doc)
    assert [e['label'] for e in toc] == ['Chapter One']
    assert toc[0]['length'] > 0


def test_headings_are_the_fallback_without_toc():
    _html, toc, _start = M._doc_to_html(_linked_doc())
    assert [e['label'] for e in toc] == ['Chapter One']


# ── Writer: inline images ──────────────────────────────────────────────────────

def test_image_block_renders_recindex_when_resolvable():
    block = {'type': 'image', 'name': 'ch1.jpg'}
    assert block_to_html(block, img_ref={'ch1.jpg': 6}.get) == '<img recindex="00006"></img>'
    assert block_to_html(block) == ''  # no resolver: dropped, as before


# ── Inline images from non-EPUB sources ───────────────────────────────────────

def _jpeg_bytes() -> bytes:
    """A genuinely encoded JPEG. The repo carries no image fixture, so Pillow
    (already a dependency) encodes one rather than checking book art in."""
    from io import BytesIO
    from PIL import Image
    buf = BytesIO()
    Image.new('RGB', (64, 48), (90, 120, 160)).save(buf, 'JPEG')
    return buf.getvalue()


def test_html_images_from_file_and_data_uri():
    import base64
    jpeg = _jpeg_bytes()
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        (base / 'pic.jpg').write_bytes(jpeg)
        page = base / 'page.html'
        page.write_text(
            '<html><body><h1>C</h1>'
            '<p><img src="pic.jpg"/>after file image</p>'
            f'<p><img src="data:image/jpeg;base64,{base64.b64encode(jpeg).decode()}"/>after data uri</p>'
            '</body></html>')
        doc = read_html(page)

    assert len(doc.images) == 2, "file-referenced and data-URI images both expected"
    assert [b['type'] for b in doc.content[:3]] == ['heading', 'image', 'paragraph']
    assert all(i['format'] == 'jpg' for i in doc.images.values())


def test_docx_images_are_read_in_paragraph_order():
    import docx as docx_lib
    from convertext.converters.documents.docx import DocxConverter
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        (base / 'pic.jpg').write_bytes(_jpeg_bytes())
        built = docx_lib.Document()
        built.add_heading('Chapter', 1)
        built.add_paragraph('before')
        built.add_picture(str(base / 'pic.jpg'))
        built.add_paragraph('after')
        source = base / 'doc.docx'
        built.save(str(source))
        doc = DocxConverter()._read_docx(source, {})

    assert [b['type'] for b in doc.content] == ['heading', 'paragraph', 'image', 'paragraph']
    assert len(doc.images) == 1


def test_inline_images_become_records_and_references():
    """A source image must reach the file as both a record and an <img> reference."""
    doc = Document()
    doc.metadata['title'] = 'T'
    doc.add_image('pic.jpg', _jpeg_bytes(), 'jpg')
    doc.add_paragraph('Body.')
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / 'book.mobi'
        assert M._write_mobi(doc, out) is True
        assert b'<img recindex="00001">' in _rawml(out)
        assert struct.unpack('>I', _exth(out)[125])[0] == 1  # image count


def test_image_format_normalisation():
    from convertext.converters.readers import image_format
    assert image_format('a/b/ch1.JPEG') == 'jpg'
    assert image_format('x.png') == 'png'
    assert image_format('') == 'jpg'  # unknown falls back to jpeg


def test_docx_and_pdf_reach_mobi_directly():
    # Any intermediate writer drops images, so these must not be multi-hop.
    from convertext.converters.loader import load_converters
    from convertext.registry import get_registry
    load_converters()
    for source in ('docx', 'pdf', 'html'):
        assert get_registry().find_conversion_path(source, 'mobi') == [source, 'mobi']


# ── End to end, and regressions on what already worked ────────────────────────

def test_epub_to_mobi_structure():
    doc = EpubConverter()._read_epub(EPUB, {})
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / 'book.mobi'
        assert M._write_mobi(doc, out) is True
        raw = _rawml(out)
        data = out.read_bytes()
        rec0 = struct.unpack('>I', data[78:82])[0]
        declared = struct.unpack('>I', data[rec0 + 4:rec0 + 8])[0]

        assert len(raw) == declared, "rawml length disagrees with the PalmDOC header"
        assert b'<guide>' in raw and b'type="toc"' in raw
        assert 116 in _exth(out), "EXTH 116 (start reading) missing"
        assert b'filepos=0000000000' not in raw, "unresolved link reached the file"
