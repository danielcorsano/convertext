"""Tests for text converter."""

from pathlib import Path
from convertext.converters.documents.txt import TxtConverter


def test_txt_to_html(sample_txt, tmp_path):
    """Test TXT to HTML conversion."""
    converter = TxtConverter()
    output = tmp_path / "output.html"

    result = converter.convert(sample_txt, output, {})
    assert result is True
    assert output.exists()

    content = output.read_text()
    assert '<!DOCTYPE html>' in content
    assert 'Hello World' in content


def test_txt_to_md(sample_txt, tmp_path):
    """Test TXT to Markdown conversion."""
    converter = TxtConverter()
    output = tmp_path / "output.md"

    result = converter.convert(sample_txt, output, {})
    assert result is True
    assert output.exists()

    content = output.read_text()
    assert 'Hello World' in content


def test_txt_can_convert():
    """Test can_convert method."""
    converter = TxtConverter()
    assert converter.can_convert('txt', 'html') is True
    assert converter.can_convert('txt', 'md') is True
    assert converter.can_convert('pdf', 'txt') is False
