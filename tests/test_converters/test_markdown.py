"""Tests for markdown converter."""

from convertext.converters.documents.markdown import MarkdownConverter


def test_markdown_to_html(sample_md, tmp_path):
    """Test Markdown to HTML conversion."""
    converter = MarkdownConverter()
    output = tmp_path / "output.html"

    result = converter.convert(sample_md, output, {})
    assert result is True
    assert output.exists()

    content = output.read_text()
    assert '<!DOCTYPE html>' in content
    assert 'Test Document' in content


def test_markdown_to_txt(sample_md, tmp_path):
    """Test Markdown to TXT conversion."""
    converter = MarkdownConverter()
    output = tmp_path / "output.txt"

    result = converter.convert(sample_md, output, {})
    assert result is True
    assert output.exists()

    content = output.read_text()
    assert 'TEST DOCUMENT' in content


def test_markdown_can_convert():
    """Test can_convert method."""
    converter = MarkdownConverter()
    assert converter.can_convert('md', 'html') is True
    assert converter.can_convert('markdown', 'txt') is True
    assert converter.can_convert('txt', 'md') is False
