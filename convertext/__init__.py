"""ConverText - Lightweight universal text converter."""

from pathlib import Path
from typing import Union, Optional

__version__ = "0.2.0"


def convert(source: Union[str, Path], format: str, output: Optional[str] = None, **kwargs) -> bool:
    """Convert file to target format.

    Args:
        source: Source file path
        format: Target format (epub, mobi, pdf, html, etc.)
        output: Output directory (optional)
        **kwargs: overwrite, keep_intermediate, etc.

    Returns:
        True if successful

    Example:
        >>> import convertext
        >>> convertext.convert('book.pdf', 'epub')
        >>> convertext.convert('doc.md', 'html', output='./out/', overwrite=True)
    """
    from convertext.config import Config
    from convertext.core import ConversionEngine
    from convertext.converters.loader import load_converters

    load_converters()
    cfg = Config()

    if output:
        cfg.override({'output': {'directory': output}})
    if kwargs.get('overwrite'):
        cfg.override({'output': {'overwrite': True}})

    engine = ConversionEngine(cfg, keep_intermediate=kwargs.get('keep_intermediate', False))
    result = engine.convert(Path(source), format)

    return result.success


__all__ = ['convert', '__version__']
