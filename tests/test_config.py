
import sys
import os
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.config import settings

def test_config():
    print("Testing Config...")
    
    # Test Defaults
    print(f"Version: {settings.get_version()}")
    print(f"Log Level: {settings.get('log_level')}")
    print(f"Threads: {settings.get('download_threads')}")
    
    # Test Set/Get
    settings.set("test_key", "test_value", save=False)
    assert settings.get("test_key") == "test_value"
    
    print("Config Test Passed!")

if __name__ == "__main__":
    test_config()
