"""Registry for all available converters."""

from typing import Dict, List, Optional
from convertext.converters.base import BaseConverter


class ConverterRegistry:
    """Registry for all available converters."""

    def __init__(self):
        self._converters: List[BaseConverter] = []
        self._format_map: Dict[str, List[str]] = {}

    def register(self, converter: BaseConverter):
        """Register a converter."""
        self._converters.append(converter)
        self._update_format_map(converter)

    def _update_format_map(self, converter: BaseConverter):
        """Update internal format compatibility map."""
        for src in converter.input_formats:
            if src not in self._format_map:
                self._format_map[src] = []
            self._format_map[src].extend(converter.output_formats)

    def get_converter(
        self,
        source_format: str,
        target_format: str
    ) -> Optional[BaseConverter]:
        """Find a converter that can handle this conversion."""
        source_format = source_format.lower().lstrip('.')
        target_format = target_format.lower().lstrip('.')

        for converter in self._converters:
            if converter.can_convert(source_format, target_format):
                return converter

        return None

    def list_supported_formats(self) -> Dict[str, List[str]]:
        """Return dict of source format -> list of target formats."""
        return self._format_map.copy()


_registry = ConverterRegistry()


def register_converter(converter: BaseConverter):
    """Register a converter with the global registry."""
    _registry.register(converter)


def get_registry() -> ConverterRegistry:
    """Get the global converter registry."""
    return _registry
