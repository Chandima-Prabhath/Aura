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

# Load Metadata
PYPROJECT_PATH = Path(__file__).parent / "pyproject.toml"
if not PYPROJECT_PATH.exists():
    sys.exit(f"ERROR: pyproject.toml not found at {PYPROJECT_PATH}")

data = load_pyproject_toml(PYPROJECT_PATH)
project_info = data.get("project", {})

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
UPX_PATH = BASE_PATH / "upx" # Folder containing upx.exe

def build_pyinstaller():
    print("=" * 60)
    print(f"PyInstaller: Building {APP_NAME} GUI...")
    print("=" * 60)

    if not GUI_PATH.exists():
        sys.exit(f"ERROR: GUI entry not found at {GUI_PATH}")

    # --------------------------------------------------------------
    # CLEANUP
    # --------------------------------------------------------------
    # We need to remove old .spec files or they might force inclusion
    # of browsers or webengine from previous builds.
    for spec_file in BASE_PATH.glob("*.spec"):
        print(f"Removing old spec file: {spec_file}")
        spec_file.unlink()

    for p in [BUILD_PATH, DIST_PATH]:
        if p.exists():
            print(f"Cleaning previous build: {p}")
            shutil.rmtree(p)

    # --------------------------------------------------------------
    # PYINSTALLER ARGS
    # --------------------------------------------------------------
    args = [
        str(GUI_PATH),
        "--name", APP_EXE_NAME.replace(".exe", ""),
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--add-data", f"{CORE_PATH}{os.pathsep}core",
    ]

    # UPX Compression
    if UPX_PATH.exists() and (UPX_PATH / "upx.exe").exists():
        args.extend(["--upx-dir", str(UPX_PATH)])
        print("INFO: UPX found. Compression enabled.")
    else:
        print("WARNING: UPX not found. Output will be larger.")

    # Icon
    if ICON_PATH.exists():
        args.extend(["--icon", str(ICON_PATH)])

    # --------------------------------------------------------------
    # EXCLUDE MODULES (CRITICAL FOR SIZE)
    # --------------------------------------------------------------
    exclude_modules = [
        # Data Science
        "matplotlib", "numpy", "pandas", "scipy",
        # Pillow
        "PIL", "PIL._imaging", "PIL._imagingtk",
        # GUI Toolkits (we only use standard PyQt6)
        "tkinter", "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebEngineCore", 
        "PyQt6.QtWebEngineQuick", "PyQt6.Qt3D", "PyQt6.QtPdf",
        # Standard Lib tests
        "test", "unittest", "pydoc", "doctest", "email",
    ]
    for mod in exclude_modules:
        args.extend(["--exclude-module", mod])

    # Environment Cleanup
    env = os.environ.copy()
    # Filter Conda from PATH to avoid conflicts
    if "PATH" in env:
        paths = env["PATH"].split(os.pathsep)
        filtered = [p for p in paths if "conda" not in p.lower()]
        env["PATH"] = os.pathsep.join(filtered)

    # Remove QT and CONDA env vars to ensure PyInstaller uses the bundled Qt
    for var in list(env.keys()):
        if "QT" in var.upper() or "CONDA" in var.upper():
            del env[var]

    # Run PyInstaller
    print("Running PyInstaller...")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller"] + args,
        cwd=str(BASE_PATH),
        env=env,
        check=True,
    )

    exe_path = DIST_PATH / APP_EXE_NAME
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / 1024 / 1024
        print("\n" + "=" * 60)
        print(f"PyInstaller build complete: {exe_path}")
        print(f"Size: {size_mb:.2f} MB")
        print("=" * 60)
        
        if size_mb > 150:
            print("\nWARNING: Size is still large (>150MB).")
            print("Ensure 'pyqt6-webengine' is removed from pyproject.toml and run 'uv sync'.")
    else:
        sys.exit(f"ERROR: Expected exe not found at {exe_path}")

if __name__ == "__main__":
    build_pyinstaller()