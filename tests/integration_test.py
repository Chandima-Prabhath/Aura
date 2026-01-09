import asyncio
import sys
import os

# Add parent directory to path so we can import core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.engine import AnimeHeavenEngine

async def main():
    engine = AnimeHeavenEngine(headless=False)
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