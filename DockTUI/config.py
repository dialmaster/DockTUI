"""Configuration management for DockTUI."""

import logging
import os
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger("DockTUI.config")

# Default configuration values
DEFAULT_CONFIG = {
    "app": {"refresh_interval": 5.0},
    "log": {"max_lines": 2000, "tail": 200, "since": "15m"},
}


class Config:
    """Configuration manager for DockTUI."""

    def __init__(self):
        self._config = None
        self._config_file = None
        self._loaded = False
        self._loading = False

    def _get_config_path(self) -> Path:
        """Get the configuration file path."""
        # Check for config file in order of preference:
        # 1. Environment variable
        if os.environ.get("DOCKTUI_CONFIG"):
            return Path(os.environ["DOCKTUI_CONFIG"])

        # 2. Current directory
        local_config = Path("./DockTUI.yaml")
        if local_config.exists():
            return local_config

        # 3. User config directory
        config_dir = Path.home() / ".config" / "DockTUI"
        config_file = config_dir / "DockTUI.yaml"

        # Create config directory if it doesn't exist
        if not config_dir.exists():
            config_dir.mkdir(parents=True, exist_ok=True)

        # Create default config if it doesn't exist
        if not config_file.exists():
            self._create_default_config(config_file)

        return config_file

    def _create_default_config(self, config_file: Path):
        """Create a default configuration file with comments."""
        default_config_content = """# DockTUI Configuration File
# This file controls various settings for the DockTUI application

# Application Settings
app:
  # Refresh interval in seconds for updating container status
  # Lower values update more frequently but use more resources
  # Default: 5.0
  refresh_interval: 5.0

# Log Display Settings
log:
  # Maximum number of log lines to keep in memory per container/stack
  # Higher values use more memory but allow viewing more history
  # Default: 2000
  max_lines: 2000

  # Number of log lines to initially fetch when viewing a container/stack
  # Lower values load faster but show less history
  # Default: 200
  tail: 200

  # Time range of logs to fetch (e.g., '15m', '1h', '24h')
  # Only logs from this time period will be shown initially
  # This significantly improves performance for long-running containers
  # Default: '15m'
  since: '15m'

# Note: You can also override these settings with environment variables:
# - DOCKTUI_APP_REFRESH_INTERVAL
# - DOCKTUI_LOG_MAX_LINES
# - DOCKTUI_LOG_TAIL
# - DOCKTUI_LOG_SINCE
"""
        try:
            config_file.write_text(default_config_content)
            logger.info(f"Created default configuration file at {config_file}")
        except Exception as e:
            logger.warning(f"Failed to create default config file: {e}")

    def _load_config(self):
        """Load configuration from file."""
        try:
            self._config_file = self._get_config_path()

            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    loaded_config = yaml.safe_load(f) or {}

                # Merge with defaults
                self._merge_config(self._config, loaded_config)
                logger.info(f"Loaded configuration from {self._config_file}")
        except Exception as e:
            logger.warning(f"Failed to load config file, using defaults: {e}")

    def _merge_config(self, base: Dict[str, Any], update: Dict[str, Any]):
        """Recursively merge configuration dictionaries."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def _ensure_loaded(self):
        """Ensure configuration is loaded (lazy loading)."""
        if not self._loaded and not self._loading:
            self._loading = True
            try:
                self._config = DEFAULT_CONFIG.copy()
                self._load_config()
                self._loaded = True
            finally:
                self._loading = False

    @property
    def config(self):
        """Get the configuration dictionary, loading it if needed."""
        self._ensure_loaded()
        return self._config

    @property
    def config_file(self):
        """Get the configuration file path."""
        self._ensure_loaded()
        return self._config_file

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation (e.g., 'log.max_lines')."""
        self._ensure_loaded()
        # Check environment variable override first
        env_key = f"DOCKTUI_{key.upper().replace('.', '_')}"
        if env_key in os.environ:
            value = os.environ[env_key]
            # Try to convert to appropriate type
            try:
                if value.isdigit():
                    return int(value)
                elif value.lower() in ("true", "false"):
                    return value.lower() == "true"
                elif "." in value:
                    try:
                        return float(value)
                    except ValueError:
                        pass
            except:
                pass
            return value

        # Navigate through nested config
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_config_info(self) -> str:
        """Get information about the current configuration."""
        self._ensure_loaded()
        return f"Config file: {self._config_file or 'Using defaults'}"


# Global config instance - lazy loaded
config = Config()
