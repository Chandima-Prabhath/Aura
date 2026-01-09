# Aura

A modular, stealthy Python scraper for **AnimeHeaven.me** built with Playwright and managed with UV. Designed to extract direct download links for anime episodes without triggering bot detection or wasting bandwidth on video streaming.

## Features

- 🕵️ **Stealth Mode**: Uses Playwright with anti-detection measures to mimic a real user.
- 🧩 **Modular Design**: Broken into logical steps (Search -> Season Data -> Download Link) for easy GUI integration.
- 💾 **Data Saving**: Automatically blocks video streams (`.mp4`) to save bandwidth while extracting links.
- 🧪 **Reproducible Environment**: Uses `uv` for fast, cross-platform dependency management.
- 📝 **JSON Logging**: Saves all fetched data (results, episodes, links) to `debug_output/` for easy debugging.
- 🧪 **Automated Tests**: Includes integration tests to verify system health.

## Prerequisites

- **Python**: 3.11 or higher.
- **UV**: The Python package manager (install from [github.com/astral-sh/uv](https://github.com/astral-sh/uv)).
- **OS**: Windows, macOS, or Linux.

## Project Structure

```
animeheaven/
├── core/
│   ├── __init__.py       # Package initializer
│   └── scrapper.py      # Main scraper class
├── tests/
│   ├── __init__.py       
│   └── integration_test.py # Automated testing suite
├── debug_output/         # Auto-generated folder for JSON logs
├── pyproject.toml        # UV project configuration
├── README.md
└── uv.lock
```

## Installation

This project uses `uv` to manage the virtual environment and dependencies.

### 1. Clone or Navigate to Project
```powershell
cd D:\Works\Projects\animeheaven
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
python tests/integration_test.py
```

### Using in your Scripts

You can import the scraper class directly into your scripts or future GUI.

```python
import asyncio
from core.scrapper import AnimeHeavenModular

async def main():
    # Initialize scraper (headless=True for background, False for debugging)
    scraper = AnimeHeavenModular(headless=True)
    await scraper.start()

    try:
        # Step 1: Search
        results = await scraper.search_anime("That Time I Got Reincarnated as a Slime")
        
        # Step 2: Get Season Data
        if results:
            season_url = results[0]['url']
            season_data = await scraper.get_season_data(season_url)
            
            # Step 3: Get Download Link for specific episode
            if season_data['episodes']:
                ep_url = season_data['episodes'][0]['url']
                dl_link = await scraper.get_download_link(ep_url)
                print(f"Download Link: {dl_link}")

    finally:
        await scraper.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## Debug Output

The scraper automatically saves data to the `debug_output/` folder during execution:
- `search_results.json`: List of anime found during search.
- `season_data.json`: List of episodes and related shows for a specific season.
- `download_link.json`: The extracted direct download link for an episode.

Check these files if you encounter issues or need to inspect the raw data structure for your GUI.

## Future Roadmap
- [ ] **Core Engine**: Build the core engine for cli and gui to use.
- [ ] **Flet GUI**: Build a graphical user interface using `flet` to visualize search results and manage downloads.
- [ ] **Download Engine**: Build a fast and stable download engine.
- [ ] **Batch Downloading**: Add functionality to queue multiple episodes.
- [ ] **Resume Capability**: Check if downloaded files exist before re-downloading.

## License

This project is licensed under the **MIT License** – see the [LICENSE](LICENSE) file for details.