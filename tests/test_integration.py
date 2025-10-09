"""Integration tests for convertext."""

from pathlib import Path
import tempfile
import os


def test_markdown_to_html_conversion():
    """Test MD to HTML conversion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        md_file = tmppath / "test.md"
        md_file.write_text("# Test\n\nHello world")

        from convertext.converters.documents.markdown import MarkdownConverter
        converter = MarkdownConverter()

        html_file = tmppath / "test.html"
        result = converter.convert(md_file, html_file, {})

        assert result is True
        assert html_file.exists()
        content = html_file.read_text()
        assert "Test" in content
        assert "Hello world" in content


def test_txt_to_html_conversion():
    """Test TXT to HTML conversion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        txt_file = tmppath / "test.txt"
        txt_file.write_text("Hello\n\nWorld")

        from convertext.converters.documents.txt import TxtConverter
        converter = TxtConverter()

        html_file = tmppath / "test.html"
        result = converter.convert(txt_file, html_file, {})

        assert result is True
        assert html_file.exists()


def test_html_to_txt_conversion():
    """Test HTML to TXT conversion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        html_file = tmppath / "test.html"
        html_file.write_text("<html><body><h1>Title</h1><p>Content</p></body></html>")

        from convertext.converters.documents.html import HtmlConverter
        converter = HtmlConverter()

        txt_file = tmppath / "test.txt"
        result = converter.convert(html_file, txt_file, {})

        assert result is True
        assert txt_file.exists()
        content = txt_file.read_text()
        assert "Title" in content.upper()


def test_md_to_epub_conversion():
    """Test MD to EPUB conversion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        md_file = tmppath / "test.md"
        md_file.write_text("# Chapter 1\n\nContent here\n\n# Chapter 2\n\nMore content")

        from convertext.converters.ebooks.epub import ToEpubConverter
        converter = ToEpubConverter()

        epub_file = tmppath / "test.epub"
        result = converter.convert(md_file, epub_file, {})

        assert result is True
        assert epub_file.exists()
