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
        },
        "documents": {
            "encoding": "utf-8",
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

    def find_local_config(self, file_path: Path) -> Optional[Path]:
        """Find convertext.yaml starting from file's directory, searching up to home.

        Args:
            file_path: Path to the file being converted

        Returns:
            Path to convertext.yaml if found, None otherwise
        """
        # Start from file's parent directory
        search_dir = file_path.parent.resolve()
        home_dir = Path.home()

        # Search up through parent directories
        while True:
            config_path = search_dir / "convertext.yaml"
            if config_path.exists():
                return config_path

            # Stop at home directory (don't go to root)
            if search_dir == home_dir or search_dir.parent == search_dir:
                break

            search_dir = search_dir.parent

        return None

    def load_file_config(self, file_path: Path):
        """Load and merge config file specific to the file being converted.

        Searches for convertext.yaml from file's directory up to home directory.
        This allows directory-specific configurations that are inherited by subdirectories.

        Args:
            file_path: Path to the file being converted
        """
        local_config = self.find_local_config(file_path)
        if local_config:
            self._merge_config(self._load_yaml(local_config))

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
