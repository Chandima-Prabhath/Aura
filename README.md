<div align="center">

<img src="images/logo-cropped.png" alt="Aura logo" style="max-width:420px; width:100%; height:auto;" />

<h1>Aura</h1>
<p><strong>A stealthy, modular Python scraper for AnimeHeaven.me — built with Playwright and managed with <code>uv</code>.</strong></p>

</div>

---

<p align="center">
    <a href="https://github.com/Chandima-Prabhath/Aura/actions/workflows/release-windows.yml"><img alt="Release" src="https://github.com/Chandima-Prabhath/Aura/actions/workflows/release-windows.yml/badge.svg"/></a>
    <a href="https://github.com/Chandima-Prabhath/Aura/actions/workflows/testing.yml"><img alt="Testing" src="https://github.com/Chandima-Prabhath/Aura/actions/workflows/testing.yml/badge.svg"/></a>
    <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"/></a>
    <a href="https://www.python.org"><img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue.svg"/></a>
</p>

Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Use as a Library](#use-as-a-library)
- [Debug & Logs](#debug--logs)
- [Project Layout](#project-layout)
- [Development](#development)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

## Overview

`Aura` extracts direct episode download links from AnimeHeaven.me while minimizing bandwidth and avoiding common bot-detection signals. It combines a resilient Playwright automation core with a small CLI and an optional GUI front-end.

## Key Features

- Stealthy Playwright automation with anti-detection techniques
- Modular design: search → episode data → download link resolution
- Bandwidth-aware (blocks video streaming during extraction)
- JSON debug output for reproducible troubleshooting
- Tested integration flow and development tooling via `uv`

## Requirements

- Python 3.11+
- `uv` (for development workflows): https://github.com/astral-sh/uv
- Playwright (installed by project tooling)

Note: The repository is developed on Windows but should work cross-platform where Playwright is supported.

## Installation

Recommended — download a release from the Releases page:

[Latest releases](https://github.com/Chandima-Prabhath/Aura/releases)

From source

PowerShell

```powershell
git clone https://github.com/Chandima-Prabhath/Aura.git
cd Aura
uv sync
```

Build (optional)

```powershell
uv run python build-cli.py
uv run python build-gui.py
```

## Quick Start

CLI (development run)

```powershell
uv run python cli\main.py
```

GUI (development run)

```powershell
uv run python src\main.py
```

CLI example (Windows executable builds provide `aura-cli.exe`):

```powershell
aura-cli.exe -u "https://animeheaven.me/anime.php?17c9p"
```

## Use as a Library

Embed the engine in your own async code:

```python
import asyncio
from core.engine import AnimeHeavenEngine

async def main():
    engine = AnimeHeavenEngine(headless=True)
    await engine.start()
    try:
        results = await engine.search_anime("Slime")
        downloads = await engine.resolve_episode_selection(results[0]["url"], "1-3,10")
        for item in downloads:
            print(f"Ep {item['episode_number']}: {item['download_url']}")
    finally:
        await engine.close()

asyncio.run(main())
```

## Debug & Logs

During runs, the tool persists structured debug files to the `debug_jsons/` directory for inspection:

- `search_results.json`
- `episode_list.json`
- `download_link.json`

## Project Layout

Top-level layout (important files and folders):

```
core/              # Core engine and download manager
cli/               # Command-line interface
src/               # GUI entry + assets
tests/             # Integration & unit tests
debug_jsons/       # Generated debug output
pyproject.toml
build-cli.py
build-gui.py
README.md
LICENSE
```

## Development

Install dependencies and synchronize the environment with `uv`:

```powershell
uv sync
```

Run tests:

```powershell
uv run python tests/integration_test.py
```

Recommended next steps

- Add CI to run tests on push (GitHub Actions)
- Add automated packaging for releases

## Roadmap

- ✅ Core engine
- ✅ CLI
- ⏳ PyQT6 GUI
- ⏳ Download engine & batch downloads
- ⏳ Resume support

## Contributing

Contributions are welcome. Please open issues for bugs or feature requests and submit pull requests for fixes. Follow standard GitHub flow: branch, test, PR.

## License

MIT — see [LICENSE](LICENSE) for details.

---

If you'd like, I can: add badges, create a short CONTRIBUTING.md, or wire up a basic GitHub Actions workflow for tests and linting.
