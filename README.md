<div align="center">

<img style="width: 500px;" src="images/logo-cropped.png"/>

*A stealthy Python scraper for AnimeHeaven.me*

</div>

---

A stealthy Python scraper for **AnimeHeaven.me** built with Playwright and managed with UV. Designed to extract direct download links for anime episodes without triggering bot detection or wasting bandwidth on video streaming.

## ✨ Features

- 🕵️ **Stealth Mode** – Uses Playwright with anti-detection measures to mimic real user behavior
- 🧩 **Modular Design** – Logical separation (Search → Season Data → Download Link) for seamless GUI integration
- 💾 **Bandwidth Optimization** – Automatically blocks video streams to save bandwidth while extracting links
- 🧪 **Reproducible Environment** – Fast, cross-platform dependency management with `uv`
- 📝 **JSON Logging** – Comprehensive debugging with saved data to `debug_jsons/`
- ✅ **Automated Tests** – Integration tests to verify system integrity

## 📋 Prerequisites

| Requirement | Details |
|---|---|
| **Python** | 3.11+ |
| **UV** | [github.com/astral-sh/uv](https://github.com/astral-sh/uv) |
| **OS** | Windows (For now)|

## 📁 Project Structure

```
Aura/
├── core/                    # Core scraper module
│   ├── engine.py
│   └── download_manager.py
├── cli/                     # CLI interface
│   └── main.py
├── gui/                     # PyQT6 GUI application
│   ├── src/
│   │   ├── main.py
│   │   └── assets/
│   └── README.md
├── tests/                   # Automated tests
│   ├── __init__.py
│   └── integration_test.py
├── debug_jsons/             # Auto-generated logs
├── pyproject.toml
├── README.md
└── LICENSE
```

## 🚀 Quick Start

### Installation

```powershell
cd D:\Works\Projects\Aura
uv sync
uv run playwright install chromium
```

### Running Tests

```powershell
uv run python tests/integration_test.py
```

### Basic Usage

```cli
aura-cli.exe 
```


### Using the engine directly

```python
import asyncio
from core.engine import AnimeHeavenEngine

async def main():
    engine = AnimeHeavenEngine(headless=True)
    await engine.start()

    try:
        results = await engine.search_anime("Slime")
        downloads = await engine.resolve_episode_selection(
            results[0]['url'], 
            "1-3,10"
        )
        
        for item in downloads:
            print(f"Ep {item['episode_number']}: {item['download_url']}")
    finally:
        await engine.close()

asyncio.run(main())
```

## 🐛 Debug Output

All data is logged to `debug_jsons/`:
- `search_results.json`
- `episode_list.json`
- `download_link.json`

## 📦 Roadmap

- ✅ Core Engine
- ⏳ Flet GUI
- ⏳ Download Engine
- ⏳ Batch Downloading
- ⏳ Resume Capability

## 📄 License

MIT License – see [LICENSE](LICENSE) for details.
