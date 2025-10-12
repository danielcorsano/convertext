"""Registry for all available converters."""

from typing import Dict, List, Optional, Tuple
from collections import deque
from convertext.converters.base import BaseConverter


class ConverterRegistry:
    """Registry for all available converters."""

    def __init__(self):
        self._converters: List[BaseConverter] = []
        self._format_map: Dict[str, List[str]] = {}
        self._path_cache: Dict[Tuple[str, str], Optional[List[str]]] = {}

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

    def find_conversion_path(
        self,
        source_format: str,
        target_format: str,
        max_hops: int = 3
    ) -> Optional[List[str]]:
        """
        Find shortest conversion path from source to target format using BFS.

        Returns list of formats representing the path, e.g., ['pdf', 'html', 'epub']
        Returns None if no path exists within max_hops.
        Uses cache for performance.
        """
        source_format = source_format.lower().lstrip('.')
        target_format = target_format.lower().lstrip('.')

        if source_format == target_format:
            return [source_format]

        # Check cache
        cache_key = (source_format, target_format)
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]

        # Check direct conversion first
        if self.get_converter(source_format, target_format):
            path = [source_format, target_format]
            self._path_cache[cache_key] = path
            return path

        # BFS to find shortest path
        queue = deque([(source_format, [source_format])])
        visited = {source_format}

        while queue:
            current_format, path = queue.popleft()

            # Check hop limit
            if len(path) > max_hops + 1:
                continue

            # Get all possible next formats from current format
            next_formats = self._format_map.get(current_format, [])

            for next_format in next_formats:
                if next_format == target_format:
                    # Found path!
                    result_path = path + [next_format]
                    self._path_cache[cache_key] = result_path
                    return result_path

                if next_format not in visited:
                    visited.add(next_format)
                    queue.append((next_format, path + [next_format]))

        # No path found
        self._path_cache[cache_key] = None
        return None


_registry = ConverterRegistry()


def register_converter(converter: BaseConverter):
    """Register a converter with the global registry."""
    _registry.register(converter)


def get_registry() -> ConverterRegistry:
    """Get the global converter registry."""
    return _registry
