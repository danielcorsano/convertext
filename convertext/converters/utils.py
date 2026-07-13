"""Shared utility functions for all converters."""

from typing import Optional


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def escape_rtf(text: str) -> str:
    """Escape RTF special characters."""
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def hex_to_rgb(hex_color: str) -> Optional[tuple]:
    """
    Convert hex color string to RGB tuple.

    Args:
        hex_color: Color string like '#FF0000' or 'FF0000'

    Returns:
        (r, g, b) tuple or None if invalid
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return None
    try:
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None
