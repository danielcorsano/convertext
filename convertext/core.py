"""Main conversion orchestrator."""

from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from convertext.config import Config
from convertext.registry import get_registry


@dataclass
class ConversionResult:
    """Result of a conversion operation."""
    success: bool
    source_path: Path
    target_path: Optional[Path]
    error: Optional[str] = None


class ConversionEngine:
    """Main conversion orchestrator."""

    def __init__(self, config: Config):
        self.config = config
        self.registry = get_registry()

    def convert(
        self,
        source_path: Path,
        target_format: str
    ) -> ConversionResult:
        """Convert a file to target format."""
        source_format = source_path.suffix.lstrip('.').lower()
        target_format = target_format.lstrip('.').lower()

        converter = self.registry.get_converter(source_format, target_format)
        if not converter:
            return ConversionResult(
                success=False,
                source_path=source_path,
                target_path=None,
                error=f"No converter found for {source_format} -> {target_format}"
            )

        target_path = self._get_target_path(source_path, target_format)

        if target_path.exists() and not self.config.get('output.overwrite', False):
            return ConversionResult(
                success=False,
                source_path=source_path,
                target_path=target_path,
                error="Target file already exists (use --overwrite)"
            )

        try:
            success = converter.convert(
                source_path,
                target_path,
                self.config.config
            )

            if success:
                return ConversionResult(
                    success=True,
                    source_path=source_path,
                    target_path=target_path
                )
            else:
                return ConversionResult(
                    success=False,
                    source_path=source_path,
                    target_path=target_path,
                    error="Conversion failed"
                )

        except Exception as e:
            return ConversionResult(
                success=False,
                source_path=source_path,
                target_path=target_path,
                error=str(e)
            )

    def _get_target_path(self, source_path: Path, target_format: str) -> Path:
        """Determine output file path based on config."""
        output_dir = self.config.get('output.directory')

        if output_dir:
            output_dir = Path(output_dir)
        else:
            output_dir = source_path.parent

        pattern = self.config.get('output.filename_pattern', '{name}.{ext}')
        filename = pattern.format(
            name=source_path.stem,
            ext=target_format
        )

        return output_dir / filename
