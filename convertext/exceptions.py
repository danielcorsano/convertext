"""Custom exceptions for convertext."""


class ConvertextError(Exception):
    """Base exception for convertext."""
    pass


class ConversionError(ConvertextError):
    """Raised when a conversion fails."""
    pass


class UnsupportedFormatError(ConvertextError):
    """Raised when a format is not supported."""
    pass


class ConfigurationError(ConvertextError):
    """Raised when configuration is invalid."""
    pass


class ValidationError(ConvertextError):
    """Raised when file validation fails."""
    pass
