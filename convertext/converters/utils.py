"""Shared utility functions for all converters."""

import re
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


def sanitize_filename(name: str, replacement: str = "_") -> str:
    """
    Sanitize filename for cross-platform use.

    Removes or replaces invalid characters that aren't allowed in filenames
    on Windows, macOS, or Linux.
    """
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, replacement, name)
    sanitized = sanitized.strip(". ")
    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
    if sanitized.upper() in reserved_names:
        sanitized = f"{replacement}{sanitized}"

    return sanitized if sanitized else "unnamed"


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


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """
    Convert RGB values to hex color string.

    Args:
        r: Red (0-255)
        g: Green (0-255)
        b: Blue (0-255)

    Returns:
        Hex color string like '#FF0000'
    """
    return f"#{r:02x}{g:02x}{b:02x}"
