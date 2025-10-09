"""Tests for configuration management."""

from pathlib import Path
from convertext.config import Config


def test_default_config():
    """Test default configuration."""
    config = Config()
    assert config.get('output.overwrite') is False
    assert config.get('conversion.quality') == 'medium'
    assert config.get('documents.encoding') == 'utf-8'


def test_config_get_nested():
    """Test nested config retrieval."""
    config = Config()
    assert config.get('documents.pdf.compression') is True
    assert config.get('ebooks.epub.version') == 3


def test_config_get_default():
    """Test config get with default value."""
    config = Config()
    assert config.get('nonexistent.key', 'default') == 'default'


def test_config_override():
    """Test config override."""
    config = Config()
    config.override({'output': {'overwrite': True}})
    assert config.get('output.overwrite') is True


def test_deep_merge():
    """Test deep config merging."""
    config = Config()
    config.override({
        'documents': {
            'pdf': {
                'compression': False
            }
        }
    })
    assert config.get('documents.pdf.compression') is False
    assert config.get('documents.pdf.optimize') is True
