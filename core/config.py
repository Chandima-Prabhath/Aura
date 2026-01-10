# core/config.py
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any
from core.logger import get_logger

logger = get_logger(__name__)

class SettingsManager:
    _instance = None
    SETTINGS_FILE = "settings.json"

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(SettingsManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
            
        self._data = {}
        self._initialized = True
        self.load()

    def _get_app_path(self) -> Path:
        """Get the directory where the application is running or exe is located."""
        if getattr(sys, 'frozen', False):
            # If running as compiled exe
            return Path(sys.executable).parent
        else:
            # If running as script (dev)
            return Path(os.getcwd())

    def _get_settings_path(self) -> Path:
        return self._get_app_path() / self.SETTINGS_FILE

    def _get_default_download_path(self) -> str:
        """Try to find the default Downloads folder."""
        # Windows: ~/Downloads
        return str(Path.home() / "Downloads" / "AnimeHeaven")

    def load(self):
        path = self._get_settings_path()
        if path.exists():
            try:
                with open(path, 'r') as f:
                    self._data = json.load(f)
                logger.info(f"Loaded settings from {path}")
            except Exception as e:
                logger.error(f"Failed to load settings: {e}")
                self._data = {}
        else:
            logger.info("No settings file found. Using defaults.")
            self._data = {}
            # Initialize defaults immediately if missing
            self.set("download_path", self._get_default_download_path(), save=True)

    def save(self):
        path = self._get_settings_path()
        try:
            with open(path, 'w') as f:
                json.dump(self._data, f, indent=4)
            logger.info(f"Saved settings to {path}")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any, save: bool = True):
        self._data[key] = value
        if save:
            self.save()

# Global instance
settings = SettingsManager()
