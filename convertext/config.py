"""Configuration management with priority merging."""

from pathlib import Path
from typing import Any, Dict, Optional
import yaml


class Config:
    """Configuration management with priority merging."""

    DEFAULT_CONFIG: Dict[str, Any] = {
        "output": {
            "directory": None,
            "filename_pattern": "{name}.{ext}",
            "overwrite": False,
            "preserve_structure": True,
            "create_backup": False,
        },
        "conversion": {
            "quality": "medium",
            "preserve_metadata": True,
            "preserve_formatting": True,
            "preserve_images": True,
            "extract_toc": True,
        },
        "documents": {
            "encoding": "utf-8",
            "embed_fonts": True,
            "font_fallback": "Liberation Sans",
            "image_quality": 85,
            "dpi": 300,
            "pdf": {
                "compression": True,
                "optimize": True,
                "linearize": False,
                "pdf_version": "1.7",
            },
            "docx": {
                "style_preservation": True,
                "embed_images": True,
            },
            "odt": {
                "style_preservation": True,
            },
        },
        "ebooks": {
            "epub": {
                "version": 3,
                "split_chapters": True,
                "toc_depth": 3,
                "cover_auto_detect": True,
                "stylesheet": None,
            },
            "mobi": {
                "compression_level": 1,
                "prefer_azw3": True,
            },
            "fb2": {
                "validation": True,
                "include_binary_images": True,
            },
        },
        "comics": {
            "image_format": "jpeg",
            "image_quality": 90,
            "max_image_width": 2048,
            "max_image_height": 2048,
            "preserve_order": True,
        },
        "processing": {
            "parallel": True,
            "max_workers": 4,
            "temp_dir": None,
            "cleanup_temp": True,
            "chunk_size": 4096,
        },
        "logging": {
            "level": "INFO",
            "file": None,
            "format": "%(levelname)s: %(message)s",
            "verbose": False,
            "show_progress": True,
        },
    }

    def __init__(self):
        self.config = self._deep_copy(self.DEFAULT_CONFIG)
        self._load_configs()

    def _deep_copy(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Deep copy a dictionary."""
        result = {}
        for key, value in d.items():
            if isinstance(value, dict):
                result[key] = self._deep_copy(value)
            else:
                result[key] = value
        return result

    def _load_configs(self):
        """Load configs in priority order."""
        user_config = Path.home() / ".convertext" / "config.yaml"
        if user_config.exists():
            self._merge_config(self._load_yaml(user_config))

        project_config = Path.cwd() / "convertext.yaml"
        if project_config.exists():
            self._merge_config(self._load_yaml(project_config))

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load YAML config file."""
        with open(path, 'r') as f:
            return yaml.safe_load(f) or {}

    def _merge_config(self, new_config: Dict[str, Any]):
        """Deep merge new config into existing."""
        def deep_merge(base: Dict[str, Any], update: Dict[str, Any]):
            for key, value in update.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_merge(base[key], value)
                else:
                    base[key] = value
        deep_merge(self.config, new_config)

    def override(self, overrides: Dict[str, Any]):
        """Override config with CLI arguments."""
        self._merge_config(overrides)

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get config value by dot-separated path (e.g., 'output.directory')."""
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    @classmethod
    def init_user_config(cls, path: Optional[Path] = None):
        """Initialize user config file with defaults."""
        if path is None:
            path = Path.home() / ".convertext" / "config.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            yaml.dump(cls.DEFAULT_CONFIG, f, default_flow_style=False, sort_keys=False)
