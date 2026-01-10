# core/config.py
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

from core.logger import get_logger, setup_logging

logger = get_logger(__name__)

class SettingsManager:
    _instance = None
    SETTINGS_FILE = "settings.json"
    
    DEFAULTS = {
        "download_path": str(Path.home() / "Downloads" / "AnimeHeaven"),
        "max_concurrent_downloads": 3,
        "download_threads": 5, # pysmartdl threads per file
        "log_level": "INFO"
    }

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(SettingsManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
            
        self._data = {}
        self._version = "0.0.0"
        self._initialized = True
        self.load()
        self._load_version()

    def _get_app_path(self) -> Path:
        """Get the directory where the application is running or exe is located."""
        if getattr(sys, 'frozen', False):
            # If running as compiled exe
            return Path(sys.executable).parent
        else:
            # If running as script (dev)
            return Path(os.getcwd())

    def _get_project_root(self) -> Path:
        """Get the project root (dev) or app path (exe)."""
        app_path = self._get_app_path()
        # In dev, we might be in core or cli, so project root is likely current cwd
        return app_path

    def _get_settings_path(self) -> Path:
        return self._get_app_path() / self.SETTINGS_FILE

    def _load_version(self):
        """Attempt to load version from pyproject.toml."""
        try:
            # Try to find pyproject.toml
            # If dev: likely in CWD
            toml_path = self._get_project_root() / "pyproject.toml"
            
            if toml_path.exists() and tomllib:
                with open(toml_path, "rb") as f:
                    data = tomllib.load(f)
                    self._version = data.get("project", {}).get("version", "0.0.0")
            else:
                # Fallback or hardcoded if packaged without toml
                # For PyInstaller, we might bundle it or rely on this fallback
                self._version = "0.1.0" 
                
        except Exception as e:
            logger.debug(f"Could not load version from pyproject.toml: {e}")

    def load(self):
        path = self._get_settings_path()
        loaded_data = {}
        
        if path.exists():
            try:
                with open(path, 'r') as f:
                    loaded_data = json.load(f)
                logger.info(f"Loaded settings from {path}")
            except Exception as e:
                logger.error(f"Failed to load settings: {e}")
        else:
            logger.info("No settings file found. Using defaults.")
        
        # Merge with defaults
        self._data = self.DEFAULTS.copy()
        self._data.update(loaded_data)
        
        # If file didn't exist or was partial, save the complete set
        if not path.exists() or len(loaded_data) < len(self.DEFAULTS):
             self.save()
             
        # Configure logging based on settings
        setup_logging(self.get("log_level", "INFO"))

    def save(self):
        path = self._get_settings_path()
        try:
            with open(path, 'w') as f:
                json.dump(self._data, f, indent=4)
            logger.info(f"Saved settings to {path}")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        # If key is in DEFAULTS and not in _data (shouldn't happen due to merge), use default
        if default is None and key in self.DEFAULTS:
             return self._data.get(key, self.DEFAULTS[key])
        return self._data.get(key, default)

    def set(self, key: str, value: Any, save: bool = True):
        self._data[key] = value
        if save:
            self.save()
            
        if key == "log_level":
            setup_logging(value)

    def get_version(self) -> str:
        return self._version

# Global instance
settings = SettingsManager()
