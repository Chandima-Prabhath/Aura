# cli.py
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path to import core if running directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.engine import AnimeHeavenEngine

async def main():
    engine = AnimeHeavenEngine(headless=False)
    try:
        # This will trigger the browser detection logic
        await engine.start()
        
        query = "Naruto" # Test query
        print(f"\n[CLI] Searching for: {query}\n")
        
        results = await engine.search_anime(query)
        
        if results:
            print(f"[CLI] Found {len(results)} results:")
            for i, res in enumerate(results[:5], 1): # Print top 5
                print(f"{i}. {res['title']} - {res['url']}")
        else:
            print("[CLI] No results found.")
            
    except Exception as e:
        print(f"[CLI] Error: {e}")
    finally:
        await engine.close()

if __name__ == "__main__":
    asyncio.run(main())