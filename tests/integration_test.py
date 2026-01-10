import os
import sys
import pytest
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.engine import AnimeHeavenEngine
from core.models import AnimeSearchResult, Episode

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.mark.asyncio
async def test_search_and_fetch_details():
    """
    Integration test for the core Engine:
    1. Search for an anime.
    2. Fetch season details (episodes).
    3. Verify data structures.
    """
    engine = AnimeHeavenEngine(headless=True)
    await engine.start()
    
    try:
        # 1. Search
        query = "Slime"
        results = await engine.search_anime(query)
        
        assert isinstance(results, list), "Search result must be a list"
        assert len(results) > 0, f"No results for '{query}'"
        assert isinstance(results[0], AnimeSearchResult), "Items must be AnimeSearchResult"
        assert results[0].url, "Result must have a URL"

        print(f"Found: {results[0].title}")

        # 2. Get Season Data
        season_url = results[0].url
        data = await engine.get_season_data(season_url)
        
        assert isinstance(data, dict)
        assert "episodes" in data
        assert len(data["episodes"]) > 0, "Season must have episodes"
        
        first_ep = data["episodes"][0]
        assert isinstance(first_ep, Episode)
        assert first_ep.url, "Episode must have a URL"
        
        print(f"Season Title: {data.get('title')}")
        print(f"First Episode: {first_ep.name}")
        
    finally:
        await engine.close()

@pytest.mark.asyncio
async def test_parse_episode_range():
    """Test the static helper methods."""
    total_episodes = 24
    
    # Range "1-3" -> [1, 2, 3]
    indices = AnimeHeavenEngine._parse_episode_range("1-3", total_episodes)
    assert indices == [1, 2, 3]
    
    # Comma "1, 5, 10" -> [1, 5, 10]
    indices = AnimeHeavenEngine._parse_episode_range("1, 5, 10", total_episodes)
    assert indices == [1, 5, 10]
    
    # "All" -> [1...24]
    indices = AnimeHeavenEngine._parse_episode_range("All", total_episodes)
    assert len(indices) == 24
    