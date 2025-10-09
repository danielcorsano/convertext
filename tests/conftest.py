"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path


@pytest.fixture
def sample_txt(tmp_path):
    """Create a sample text file."""
    txt_file = tmp_path / "sample.txt"
    txt_file.write_text("Hello World\n\nThis is a test document.\n\nIt has multiple paragraphs.")
    return txt_file


@pytest.fixture
def sample_md(tmp_path):
    """Create a sample markdown file."""
    md_file = tmp_path / "sample.md"
    md_file.write_text("# Test Document\n\nThis is a **test** document.\n\n## Section 1\n\nSome content here.")
    return md_file


@pytest.fixture
def sample_html(tmp_path):
    """Create a sample HTML file."""
    html_file = tmp_path / "sample.html"
    html_file.write_text("""<!DOCTYPE html>
<html>
<head><title>Test Document</title></head>
<body>
<h1>Test Document</h1>
<p>This is a test document.</p>
<h2>Section 1</h2>
<p>Some content here.</p>
</body>
</html>""")
    return html_file
