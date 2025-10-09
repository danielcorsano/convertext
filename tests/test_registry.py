"""Tests for converter registry."""

from convertext.registry import ConverterRegistry
from convertext.converters.documents.txt import TxtConverter


def test_registry_register():
    """Test registering a converter."""
    registry = ConverterRegistry()
    converter = TxtConverter()
    registry.register(converter)

    assert len(registry._converters) == 1


def test_registry_get_converter():
    """Test getting a converter."""
    registry = ConverterRegistry()
    converter = TxtConverter()
    registry.register(converter)

    found = registry.get_converter('txt', 'html')
    assert found is not None
    assert isinstance(found, TxtConverter)


def test_registry_format_map():
    """Test format map."""
    registry = ConverterRegistry()
    converter = TxtConverter()
    registry.register(converter)

    formats = registry.list_supported_formats()
    assert 'txt' in formats
    assert 'html' in formats['txt']


def test_registry_no_converter():
    """Test when no converter exists."""
    registry = ConverterRegistry()
    found = registry.get_converter('xyz', 'abc')
    assert found is None
