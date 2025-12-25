"""Simple integration test."""

def test_basic():
    """Basic test to verify pytest works."""
    assert True

def test_imports():
    """Test that core modules can be imported."""
    from convertext import __version__
    from convertext.config import Config
    from convertext.core import ConversionEngine
    from convertext.registry import get_registry

    assert __version__ == "0.2.0"
    assert Config is not None
    assert ConversionEngine is not None
    assert get_registry is not None
