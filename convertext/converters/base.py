"""Base converter classes and intermediate document representation."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional


class Document:
    """Intermediate document representation for conversion."""

    def __init__(self):
        self.metadata: Dict[str, Any] = {}
        self.content: List[Dict[str, Any]] = []
        self.images: Dict[str, Dict[str, Any]] = {}
        self.styles: Dict[str, Any] = {}
        self.toc: List[Dict[str, Any]] = []

    def add_text(self, text: str, style: Optional[str] = None):
        """Add text content."""
        self.content.append({"type": "text", "data": text, "style": style})

    def add_heading(self, text: str, level: int):
        """Add heading."""
        self.content.append({"type": "heading", "data": text, "level": level})

    def add_image(self, name: str, data: bytes, format: str):
        """Add image."""
        self.images[name] = {"data": data, "format": format}
        self.content.append({"type": "image", "name": name})

    def add_paragraph(self, text: str):
        """Add paragraph."""
        self.content.append({"type": "paragraph", "data": text})

    def add_run(
        self,
        text: str,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        color: Optional[str] = None,
        font_name: Optional[str] = None,
        font_size: Optional[int] = None,
    ):
        """Add inline text run with formatting."""
        run_block = {
            "type": "run",
            "text": text,
            "bold": bold,
            "italic": italic,
            "underline": underline,
        }
        if color:
            run_block["color"] = color
        if font_name:
            run_block["font"] = font_name
        if font_size:
            run_block["size"] = font_size
        self.content.append(run_block)

    def add_table(
        self, rows: List[List[str]], headers: Optional[List[str]] = None
    ):
        """Add table block."""
        table_block = {"type": "table", "rows": rows}
        if headers:
            table_block["headers"] = headers
        self.content.append(table_block)

    def add_list(self, items: List[str], ordered: bool = False):
        """Add list block (ordered or unordered)."""
        self.content.append({"type": "list", "items": items, "ordered": ordered})

    def add_link(self, text: str, url: str):
        """Add hyperlink."""
        self.content.append({"type": "link", "text": text, "url": url})


class BaseConverter(ABC):
    """Abstract base class for all format converters."""

    @property
    @abstractmethod
    def input_formats(self) -> List[str]:
        """List of supported input formats (lowercase extensions)."""
        pass

    @property
    @abstractmethod
    def output_formats(self) -> List[str]:
        """List of supported output formats (lowercase extensions)."""
        pass

    @abstractmethod
    def can_convert(self, source_format: str, target_format: str) -> bool:
        """Check if this converter can handle the conversion."""
        pass

    @abstractmethod
    def convert(
        self,
        source_path: Path,
        target_path: Path,
        config: Dict[str, Any]
    ) -> bool:
        """
        Convert source file to target format.

        Args:
            source_path: Path to source file
            target_path: Path to output file
            config: Configuration dictionary

        Returns:
            True if conversion succeeded, False otherwise
        """
        pass

    def validate_input(self, source_path: Path) -> bool:
        """Validate that input file is readable and correct format."""
        if not source_path.exists():
            return False
        if not source_path.is_file():
            return False
        return True

    def extract_metadata(self, source_path: Path) -> Dict[str, Any]:
        """Extract metadata from source file."""
        return {}
