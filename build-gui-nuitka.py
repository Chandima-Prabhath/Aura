import os
import shutil
import subprocess
import sys
from pathlib import Path

# ------------------------------------------------------------------
# LOAD METADATA FROM pyproject.toml
# ------------------------------------------------------------------
def load_pyproject_toml(toml_path: Path) -> dict:
    """Loads pyproject.toml using tomllib (Py3.11+) or tomli (Py3.10)."""
    try:
        import tomllib
        with open(toml_path, "rb") as f:
            return tomllib.load(f)
    except ImportError:
        try:
            import tomli
            with open(toml_path, "rb") as f:
                return tomli.load(f)
        except ImportError:
            print("ERROR: Python < 3.11 detected. Please install 'tomli':")
            print("  uv pip install tomli")
            sys.exit(1)

# Load the file
PYPROJECT_PATH = Path(__file__).parent / "pyproject.toml"
if not PYPROJECT_PATH.exists():
    sys.exit(f"ERROR: pyproject.toml not found at {PYPROJECT_PATH}")

data = load_pyproject_toml(PYPROJECT_PATH)
project_info = data.get("project", {})

# Map variables
APP_NAME = project_info.get("name", "Aura")
APP_VERSION = project_info.get("version", "0.0.1")
APP_DESCRIPTION = project_info.get("description", "")
authors = project_info.get("authors", [])
APP_PUBLISHER = authors[0].get("name", APP_NAME) if authors else APP_NAME
APP_EXE_NAME = f"{APP_NAME.lower()}-gui.exe"

# Paths
BASE_PATH = Path(__file__).parent
GUI_PATH = BASE_PATH / "src" / "main.py"
CORE_PATH = BASE_PATH / "core"
DIST_PATH = BASE_PATH / "dist"
BUILD_PATH = BASE_PATH / "build"
ICON_PATH = BASE_PATH / "src" / "assets" / "icon.ico"

def build_nuitka():
    print("=" * 60)
    print(f"Nuitka: Building {APP_NAME} GUI...")
    print("=" * 60)
    
    if not GUI_PATH.exists():
        sys.exit(f"ERROR: GUI entry not found at {GUI_PATH}")
    if not CORE_PATH.exists():
        sys.exit(f"ERROR: core directory not found at {CORE_PATH}")

    # Clean previous builds
    for p in [BUILD_PATH, DIST_PATH]:
        if p.exists():
            print(f"Cleaning previous Nuitka build: {p}")
            shutil.rmtree(p)

    # Base Nuitka args
    args = [
        "--standalone",
        "--onefile",
        "--enable-plugin=pyqt6",  
        "--windows-console-mode=disable", 
        "--assume-yes-for-downloads", 
        f"--output-dir={DIST_PATH}",
        f"--output-filename={APP_EXE_NAME}",
        f"--include-data-dir={CORE_PATH}=core",
        "--msvc=latest", 
        str(GUI_PATH),
    ]

    # Optional icon
    if ICON_PATH.exists():
        args.append(f"--windows-icon-from-ico={ICON_PATH}")
    else:
        print(f"WARNING: Icon not found at {ICON_PATH}, building without icon.")

    args.append("--jobs=4")

    print("Running Nuitka...")
    try:
        subprocess.run(
            [sys.executable, "-m", "nuitka"] + args,
            cwd=str(BASE_PATH),
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print("\n" + "=" * 60)
        print("ERROR: Nuitka build failed.")
        print("=" * 60)
        # Re-raise so the user sees the full traceback from Nuitka
        raise 

    exe_path = DIST_PATH / APP_EXE_NAME
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / 1024 / 1024
        print("\n" + "=" * 60)
        print(f"Nuitka build complete: {exe_path}")
        print(f"Size: {size_mb:.2f} MB")
        print("=" * 60)
    else:
        sys.exit(f"ERROR: Expected exe not found at {exe_path}")

if __name__ == "__main__":
    build_nuitka()