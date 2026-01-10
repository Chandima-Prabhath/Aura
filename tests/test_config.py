
import pytest
import json
import os
from pathlib import Path
from core.config import SettingsManager

@pytest.fixture
def clean_settings(tmp_path):
    # Setup: Create a temporary settings file path
    settings_file = tmp_path / "settings.json"
    
    # Patch the SettingsManager to use this path
    # Since SettingsManager is a Singleton, we might need to reset it or subclass it for testing.
    # However, for simplicity, we can just instantiate it and mock the _get_project_root to return tmp_path.
    
    # Better approach: Modify the class to accept a path in __init__ (we partly did this for version loading?)
    # or just monkeypatch `_get_settings_path`.
    
    original_func = SettingsManager._get_settings_path
    SettingsManager._get_settings_path = lambda self: settings_file
    
    # Create fresh instance (Singleton workaround: if we access accessing single instance, we re-load)
    manager = SettingsManager()
    manager._data = {} # Clear data
    manager.load() 
    
    yield manager
    
    # Teardown
    SettingsManager._get_settings_path = original_func
    if settings_file.exists():
        settings_file.unlink()

def test_defaults(clean_settings):
    assert clean_settings.get("max_concurrent_downloads") == 3
    assert clean_settings.get("download_threads") == 5

def test_set_and_save(clean_settings):
    clean_settings.set("max_concurrent_downloads", 10)
    assert clean_settings.get("max_concurrent_downloads") == 10
    
    # Check persistence
    clean_settings.load() # Reload from file
    assert clean_settings.get("max_concurrent_downloads") == 10

def test_version_loading():
    # This tests reading pyproject.toml, which is real.
    manager = SettingsManager()
    # It should have read the version from real pyproject.toml
    version = manager.get_version()
    assert version != "0.0.0"
    assert "." in version
