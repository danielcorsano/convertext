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
