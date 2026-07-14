"""Direct PDF to EPUB converter.

Composes the shared PDF reader and the EPUB writer so the direct pdf->epub path
skips a temporary intermediate file without duplicating either implementation.
"""

from pathlib import Path
from typing import Any, Dict, List

from convertext.converters.readers import read_pdf
from convertext.converters.base import BaseConverter


class PdfToEpubConverter(BaseConverter):
    """Convert PDF directly to EPUB, preserving structure and metadata."""

    @property
    def input_formats(self) -> List[str]:
        return ['pdf']

    @property
    def output_formats(self) -> List[str]:
        return ['epub']

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert PDF to EPUB directly."""
        from convertext.converters.ebooks.epub import ToEpubConverter

        doc = read_pdf(source_path, config)
        self._apply_metadata_overrides(doc, source_path, config)
        if not doc.metadata.get('title'):
            doc.metadata['title'] = target_path.stem
        if not doc.metadata.get('author'):
            doc.metadata['author'] = 'Unknown'

        return ToEpubConverter()._create_epub(doc, target_path, config, target_path.stem)
