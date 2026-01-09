# Aura

A stealthy Python scraper for **AnimeHeaven.me** built with Playwright and managed with UV. Designed to extract direct download links for anime episodes without triggering bot detection or wasting bandwidth on video streaming.

## Features

- 🕵️ **Stealth Mode**: Uses Playwright with anti-detection measures to mimic a real user.
- 🧩 **Modular Design**: Broken into logical steps (Search -> Season Data -> Download Link) for easy GUI integration.
- 💾 **Data Saving**: Automatically blocks video streams (`.mp4`) to save bandwidth while extracting links.
- 🧪 **Reproducible Environment**: Uses `uv` for fast, cross-platform dependency management.
- 📝 **JSON Logging**: Saves all fetched data (results, episodes, links) to `debug_jsons/` for easy debugging.
- 🧪 **Automated Tests**: Includes integration tests to verify system health.

## Prerequisites

- **Python**: 3.11 or higher.
- **UV**: The Python package manager (install from [github.com/astral-sh/uv](https://github.com/astral-sh/uv)).
- **OS**: Windows, macOS, or Linux.

## Project Structure

```
Aura/
├── core/                           # Core scraper module
│   ├── __init__.py
│   └── engine.py                   # Main AnimeHeavenModular class
├── cli/                            # CLI interface (future expansion)
│   └── __init__.py
├── gui/                            # Flet GUI application
│   ├── src/
│   │   ├── main.py                 # GUI entry point
│   │   └── assets/                 # GUI assets (images, icons, etc.)
│   └── README.md
├── tests/                          # Test suite
│   ├── __init__.py
│   └── integration_test.py         # Automated integration tests
├── debug_jsons/                    # Auto-generated JSON logs
├── pyproject.toml                  # Root project config (UV + dependencies)
├── uv.lock                         # Locked dependencies
├── README.md
└── LICENSE
```

**Key Notes:**
- `core/` contains the reusable core logic
- `gui/src/` is the Flet GUI application
- `cli/` is reserved for future CLI expansion
- All dependencies managed centrally by UV

## Installation

This project uses `uv` to manage the virtual environment and dependencies.

### 1. Clone or Navigate to Project
```powershell
cd D:\Works\Projects\Aura
```

### 2. Sync Environment
Run this command to create the virtual environment and install all dependencies listed in `pyproject.toml`.

```powershell
uv sync
```

### 3. Install Browser Binaries
Playwright requires browser binaries to operate. Install them via the CLI:

```powershell
uv run playwright install chromium
```

## Usage

### Running Tests
To verify everything is working correctly (Search, Parsing, Link Extraction), run the integration test:

```powershell
uv run python tests/integration_test.py
```

### Using in your Scripts

You can import the scraper class directly into your scripts or future GUI.

```python
import asyncio

from core.engine import AnimeHeavenEngine

async def main():
    engine = AnimeHeavenEngine(headless=True)
    await engine.start()

    try:
        # 1. Search
        results = await engine.search_anime("Slime")
        season_url = results[0]['url']
        
        # 2. Resolve Selection (The logic handles everything here)
        # This command: "Get me episodes 1 through 3, and episode 10"
        selection = "1-3,10"
        
        downloads = await engine.resolve_episode_selection(season_url, selection)
        
        print(f"Ready to download {len(downloads)} episodes:")
        for item in downloads:
            print(f" - Ep {item['episode_number']}: {item['download_url']}")

    finally:
        await engine.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## Debug Output

The scraper automatically saves data to the `debug_output/` folder during execution:
- `search_results.json`: List of anime found during search.
- `episode_list.json`: List of episodes and related shows for a specific season.
- `download_link.json`: The extracted direct download link for an episode.

Check these files if you encounter issues or need to inspect the raw data structure for your GUI.

## Future Roadmap
- **[✅] Core Engine**: Build the core engine for cli and gui to use.
- **[ -- ] Flet GUI**: Build a graphical user interface using `flet` to visualize search results and manage downloads.
- **[ -- ] Download Engine**: Build a fast and stable download engine.
- **[ -- ] Batch Downloading**: Add functionality to queue multiple episodes.
- **[ -- ] Resume Capability**: Check if downloaded files exist before re-downloading.

## License

This project is licensed under the **MIT License** – see the [LICENSE](LICENSE) file for details.