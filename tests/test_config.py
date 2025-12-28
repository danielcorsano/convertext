"""Tests for configuration management."""

from pathlib import Path
from convertext.config import Config


def test_default_config():
    """Test default configuration."""
    config = Config()
    assert config.get('output.overwrite') is False
    assert config.get('output.directory') is None
    assert config.get('output.filename_pattern') == '{name}.{ext}'
    assert config.get('documents.encoding') == 'utf-8'


def test_config_get_nested():
    """Test nested config retrieval with dot notation."""
    config = Config()
    assert config.get('output.overwrite') is False
    assert config.get('documents.encoding') == 'utf-8'


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
        'output': {
            'directory': '/tmp/test'
        }
    })
    assert config.get('output.directory') == '/tmp/test'
    assert config.get('output.overwrite') is False
