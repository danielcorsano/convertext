"""Tests for HTML converter."""

from convertext.converters.documents.html import HtmlConverter


def test_html_to_txt(sample_html, tmp_path):
    """Test HTML to TXT conversion."""
    converter = HtmlConverter()
    output = tmp_path / "output.txt"

    result = converter.convert(sample_html, output, {})
    assert result is True
    assert output.exists()

    content = output.read_text()
    assert 'Test Document' in content
    assert 'This is a test document' in content


def test_html_to_md(sample_html, tmp_path):
    """Test HTML to Markdown conversion."""
    converter = HtmlConverter()
    output = tmp_path / "output.md"

    result = converter.convert(sample_html, output, {})
    assert result is True
    assert output.exists()

    content = output.read_text()
    assert '# Test Document' in content
    assert '## Section 1' in content


def test_html_can_convert():
    """Test can_convert method."""
    converter = HtmlConverter()
    assert converter.can_convert('html', 'txt') is True
    assert converter.can_convert('htm', 'md') is True
    assert converter.can_convert('txt', 'html') is False
