import os
import sys
import pytest

# Add parent directory to path so we can import core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.engine import AnimeHeavenEngine


@pytest.mark.asyncio
async def test_search_and_resolve_selection():
    """Integration test: search for an anime and resolve an episode selection.

    Steps (assertions mark pass/fail):
    1) Engine starts
    2) Search returns non-empty results
    3) resolve_episode_selection returns at least one download item
    4) Each download item contains expected keys
    """
    engine = AnimeHeavenEngine(headless=True)
    await engine.start()

    try:
        # Step 1 & 2: Search
        results = await engine.search_anime("Slime")
        assert isinstance(results, list), "search_anime should return a list"
        assert len(results) > 0, "No search results returned for query 'Slime'"

        # Use first result's season/series url
        season_url = results[0].get('url')
        assert season_url, "First search result missing 'url'"

        # Step 3: Resolve Selection
        selection = "1-3,10"
        downloads = await engine.resolve_episode_selection(season_url, selection)
        assert isinstance(downloads, list), "resolve_episode_selection should return a list"
        assert len(downloads) > 0, "No downloads resolved for selection"

        # Step 4: Validate items
        for item in downloads:
            assert 'episode_number' in item, "Download item missing 'episode_number'"
            assert 'download_url' in item, "Download item missing 'download_url'"
            assert item['download_url'], "Empty 'download_url' in download item"

    finally:
        await engine.close()