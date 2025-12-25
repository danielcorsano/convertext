"""Tests for new output converters (PDF, DOCX, RTF)."""

import tempfile
from pathlib import Path


def test_to_pdf_converter():
    """Test TXT to PDF conversion."""
    from convertext.converters.loader import load_converters
    load_converters()  # Ensure registry is populated

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        txt_file = tmppath / "test.txt"
        txt_file.write_text("Test Document\n\nThis is a test paragraph.")

        from convertext.converters.documents.to_pdf import ToPdfConverter
        converter = ToPdfConverter()

        pdf_file = tmppath / "test.pdf"
        result = converter.convert(txt_file, pdf_file, {})

        assert result is True
        assert pdf_file.exists()
        assert pdf_file.stat().st_size > 0


def test_to_docx_converter():
    """Test TXT to DOCX conversion."""
    from convertext.converters.loader import load_converters
    load_converters()  # Ensure registry is populated

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        txt_file = tmppath / "test.txt"
        txt_file.write_text("Test Document\n\nThis is a test paragraph.")

        from convertext.converters.documents.to_docx import ToDocxConverter
        converter = ToDocxConverter()

        docx_file = tmppath / "test.docx"
        result = converter.convert(txt_file, docx_file, {})

        assert result is True
        assert docx_file.exists()
        assert docx_file.stat().st_size > 0


def test_to_rtf_converter():
    """Test TXT to RTF conversion."""
    from convertext.converters.loader import load_converters
    load_converters()  # Ensure registry is populated

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        txt_file = tmppath / "test.txt"
        txt_file.write_text("Test Document\n\nThis is a test paragraph.")

        from convertext.converters.documents.to_rtf import ToRtfConverter
        converter = ToRtfConverter()

        rtf_file = tmppath / "test.rtf"
        result = converter.convert(txt_file, rtf_file, {})

        assert result is True
        assert rtf_file.exists()
        assert rtf_file.stat().st_size > 0

        content = rtf_file.read_text()
        assert r'{\rtf1' in content


def test_enhanced_document_model():
    """Test enhanced Document model with new methods."""
    from convertext.converters.base import Document

    doc = Document()

    doc.add_run("Bold text", bold=True)
    doc.add_run("Italic text", italic=True, color="#FF0000")
    doc.add_table([['A', 'B'], ['C', 'D']], headers=['Col1', 'Col2'])
    doc.add_list(['Item 1', 'Item 2'], ordered=True)
    doc.add_link("Example", "https://example.com")

    assert len(doc.content) == 5
    assert doc.content[0]['type'] == 'run'
    assert doc.content[0]['bold'] is True
    assert doc.content[1]['type'] == 'run'
    assert doc.content[1]['color'] == '#FF0000'
    assert doc.content[2]['type'] == 'table'
    assert doc.content[2]['headers'] == ['Col1', 'Col2']
    assert doc.content[3]['type'] == 'list'
    assert doc.content[3]['ordered'] is True
    assert doc.content[4]['type'] == 'link'


def test_pdf_can_convert():
    """Test PDF converter format support."""
    from convertext.converters.documents.to_pdf import ToPdfConverter
    converter = ToPdfConverter()

    assert converter.can_convert('txt', 'pdf')
    assert converter.can_convert('html', 'pdf')
    assert converter.can_convert('md', 'pdf')
    assert not converter.can_convert('pdf', 'txt')
    assert 'pdf' in converter.output_formats


def test_docx_can_convert():
    """Test DOCX converter format support."""
    from convertext.converters.documents.to_docx import ToDocxConverter
    converter = ToDocxConverter()

    assert converter.can_convert('txt', 'docx')
    assert converter.can_convert('html', 'docx')
    assert converter.can_convert('md', 'docx')
    assert 'docx' in converter.output_formats


def test_rtf_can_convert():
    """Test RTF converter format support."""
    from convertext.converters.documents.to_rtf import ToRtfConverter
    converter = ToRtfConverter()

    assert converter.can_convert('txt', 'rtf')
    assert converter.can_convert('html', 'rtf')
    assert converter.can_convert('md', 'rtf')
    assert 'rtf' in converter.output_formats


def test_html_to_pdf():
    """Test HTML to PDF conversion."""
    from convertext.converters.loader import load_converters
    load_converters()  # Ensure registry is populated

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        html_file = tmppath / "test.html"
        html_file.write_text("<html><body><h1>Title</h1><p>Paragraph</p></body></html>")

        from convertext.converters.documents.to_pdf import ToPdfConverter
        converter = ToPdfConverter()

        pdf_file = tmppath / "test.pdf"
        result = converter.convert(html_file, pdf_file, {})

        assert result is True
        assert pdf_file.exists()


def test_markdown_to_docx():
    """Test Markdown to DOCX conversion."""
    from convertext.converters.loader import load_converters
    load_converters()  # Ensure registry is populated

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        md_file = tmppath / "test.md"
        md_file.write_text("# Title\n\nParagraph text.")

        from convertext.converters.documents.to_docx import ToDocxConverter
        converter = ToDocxConverter()

        docx_file = tmppath / "test.docx"
        result = converter.convert(md_file, docx_file, {})

        assert result is True
        assert docx_file.exists()


def test_converter_registration():
    """Test that new converters are registered."""
    from convertext.converters.loader import load_converters
    from convertext.registry import get_registry

    load_converters()
    registry = get_registry()

    assert registry.get_converter('txt', 'pdf') is not None
    assert registry.get_converter('txt', 'docx') is not None
    assert registry.get_converter('txt', 'rtf') is not None

    formats = registry.list_supported_formats()
    assert 'pdf' in formats.get('txt', [])
    assert 'docx' in formats.get('txt', [])
    assert 'rtf' in formats.get('txt', [])
