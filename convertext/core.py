"""Main conversion orchestrator."""

from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
import tempfile
import os

from convertext.config import Config
from convertext.registry import get_registry


@dataclass
class ConversionResult:
    """Result of a conversion operation."""
    success: bool
    source_path: Path
    target_path: Optional[Path]
    error: Optional[str] = None
    conversion_path: Optional[List[str]] = None  # Formats used in multi-hop
    hops: int = 1  # Number of conversion steps


class ConversionEngine:
    """Main conversion orchestrator."""

    def __init__(self, config: Config, keep_intermediate: bool = False):
        self.config = config
        self.registry = get_registry()
        self.keep_intermediate = keep_intermediate

    def convert(
        self,
        source_path: Path,
        target_format: str
    ) -> ConversionResult:
        """Convert a file to target format (supports multi-hop)."""
        # Load file-specific config (searches from file's dir up to home)
        self.config.load_file_config(source_path)

        source_format = source_path.suffix.lstrip('.').lower()
        target_format = target_format.lstrip('.').lower()

        # Try direct conversion first
        converter = self.registry.get_converter(source_format, target_format)
        if converter:
            return self._direct_convert(source_path, target_format, converter)

        # Try multi-hop conversion
        path = self.registry.find_conversion_path(source_format, target_format)
        if path and len(path) > 2:  # Multi-hop needed
            return self._multihop_convert(source_path, target_format, path)

        # No conversion path found
        return ConversionResult(
            success=False,
            source_path=source_path,
            target_path=None,
            error=f"No converter found for {source_format} -> {target_format}",
            conversion_path=None,
            hops=0
        )

    def _direct_convert(
        self,
        source_path: Path,
        target_format: str,
        converter
    ) -> ConversionResult:
        """Perform direct single-hop conversion."""
        target_path = self._get_target_path(source_path, target_format)

        if target_path.exists() and not self.config.get('output.overwrite', False):
            return ConversionResult(
                success=False,
                source_path=source_path,
                target_path=target_path,
                error="Target file already exists (use --overwrite)",
                conversion_path=[source_path.suffix.lstrip('.').lower(), target_format],
                hops=1
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
                    target_path=target_path,
                    conversion_path=[source_path.suffix.lstrip('.').lower(), target_format],
                    hops=1
                )
            else:
                return ConversionResult(
                    success=False,
                    source_path=source_path,
                    target_path=target_path,
                    error="Conversion failed",
                    conversion_path=[source_path.suffix.lstrip('.').lower(), target_format],
                    hops=1
                )

        except Exception as e:
            return ConversionResult(
                success=False,
                source_path=source_path,
                target_path=target_path,
                error=str(e),
                conversion_path=[source_path.suffix.lstrip('.').lower(), target_format],
                hops=1
            )

    def _multihop_convert(
        self,
        source_path: Path,
        target_format: str,
        path: List[str]
    ) -> ConversionResult:
        """Perform multi-hop conversion through intermediate formats."""
        target_path = self._get_target_path(source_path, target_format)

        if target_path.exists() and not self.config.get('output.overwrite', False):
            return ConversionResult(
                success=False,
                source_path=source_path,
                target_path=target_path,
                error="Target file already exists (use --overwrite)",
                conversion_path=path,
                hops=len(path) - 1
            )

        intermediate_files = []
        current_file = source_path

        try:
            # Execute each hop in the path
            for i in range(len(path) - 1):
                source_fmt = path[i]
                target_fmt = path[i + 1]

                # Get converter for this hop
                converter = self.registry.get_converter(source_fmt, target_fmt)
                if not converter:
                    raise Exception(f"Converter missing for {source_fmt} -> {target_fmt}")

                # Determine output path for this hop
                if i == len(path) - 2:  # Last hop
                    next_file = target_path
                else:  # Intermediate hop
                    if self.keep_intermediate:
                        # Save in source directory with descriptive name
                        next_file = source_path.parent / f"{source_path.stem}_intermediate.{target_fmt}"
                    else:
                        # Use temp file
                        fd, temp_path = tempfile.mkstemp(suffix=f".{target_fmt}")
                        os.close(fd)
                        next_file = Path(temp_path)
                    intermediate_files.append(next_file)

                # Perform conversion
                success = converter.convert(current_file, next_file, self.config.config)
                if not success:
                    raise Exception(f"Conversion failed: {source_fmt} -> {target_fmt}")

                current_file = next_file

            # Clean up intermediate files if not keeping them
            if not self.keep_intermediate:
                for intermediate_file in intermediate_files:
                    try:
                        if intermediate_file.exists():
                            intermediate_file.unlink()
                    except Exception:
                        pass  # Ignore cleanup errors

            return ConversionResult(
                success=True,
                source_path=source_path,
                target_path=target_path,
                conversion_path=path,
                hops=len(path) - 1
            )

        except Exception as e:
            # Clean up on error
            if not self.keep_intermediate:
                for intermediate_file in intermediate_files:
                    try:
                        if intermediate_file.exists():
                            intermediate_file.unlink()
                    except Exception:
                        pass

            return ConversionResult(
                success=False,
                source_path=source_path,
                target_path=target_path,
                error=str(e),
                conversion_path=path,
                hops=len(path) - 1
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
