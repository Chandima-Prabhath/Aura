# core/interface.py
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any

from core.logger import get_logger
from core.config import settings
from core.models import DownloadTask, DownloadStatus, Episode, AnimeSearchResult
from core.engine import AnimeHeavenEngine
from core.download_manager import manager as download_manager

logger = get_logger(__name__)

class AuraCore:
    def __init__(self):
        self.engine = AnimeHeavenEngine(headless=True)
        self.dm = download_manager
        
        # Connect internal DM callbacks
        self.dm.add_refresh_callback(self._handle_refresh_request)
        
    async def initialize(self):
        """Initialize the core system (engine, etc)."""
        logger.info("Initializing Aura Core...")
        await self.engine.start()
        # Settings and DM are self-initializing on import/creation
        
    async def shutdown(self):
        """Shutdown the core system."""
        logger.info("Shutting down Aura Core...")
        await self.engine.close()

    # ------------------------------------------------------------------
    # Engine Proxies
    # ------------------------------------------------------------------
    async def search(self, query: str) -> List[Any]: # Returns List[Dict] or objects if Engine updated
        return await self.engine.search_anime(query)

    async def get_season(self, url: str) -> Dict[str, Any]:
        return await self.engine.get_season_data(url)

    async def resolve_episode_selection(self, season_url: str, selection: str) -> List[Any]:
        return await self.engine.resolve_episode_selection(season_url, selection)

    # ------------------------------------------------------------------
    # Download Logic
    # ------------------------------------------------------------------
    async def download_episode(self, episode_data: Dict, anime_title: str):
        """
        Orchestrate the download of an episode.
        1. Determine final path based on settings.
        2. Resolve download link.
        3. Add to Download Manager.
        """
        # 1. Configured Path
        base_path = Path(settings.get("download_path"))
        
        # 2. Anime Folder
        # Sanitize title for filesystem
        safe_title = "".join([c for c in anime_title if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()
        anime_folder = base_path / safe_title
        
        # Ensure folder exists
        if not anime_folder.exists():
            anime_folder.mkdir(parents=True, exist_ok=True)
            
        # 3. Resolve Link
        episode_url = episode_data.get('url')
        gate_id = episode_data.get('gate_id')
        name = episode_data.get('name', 'Unknown')
        
        logger.info(f"Resolving link for '{name}'...")
        dl_link = await self.engine.get_download_link(episode_url, gate_id)
        
        if not dl_link:
            logger.error(f"Failed to resolve link for {name}")
            return None

        # 4. Filename
        # Try to guess extension or default to .mp4
        filename = f"{name}.mp4" 
        # Note: PySmartDL might resolve better name, but we enforce consistent naming here if we want.
        
        # 5. Add to Manager
        # We pass episode_url and anime_title for context and refreshing
        task_id = self.dm.add_download(
            url=dl_link,
            dest_folder=str(anime_folder),
            filename=filename,
            episode_url=episode_url,
            anime_title=anime_title
        )
        return task_id

    # ------------------------------------------------------------------
    # Auto-Refresh Logic
    # ------------------------------------------------------------------
    def _handle_refresh_request(self, task_data: Dict):
        """Callback from DM when a task needs a link refresh."""
        task_id = task_data['id']
        episode_url = task_data.get('episode_url')
        
        if not episode_url:
            logger.error(f"Cannot refresh task {task_id}: No episode_url stored.")
            return

        logger.info(f"Triggering auto-refresh for task {task_id}...")
        
        # Since this is a callback from a thread (DM worker), and we need to use async engine,
        # we must schedule this on the event loop.
        # If we are in a GUI app, we might check if an event loop is running.
        # For now, we assume standard asyncio loop availability or spawn a new one if strictly necessary.
        
        # We start a background task to handle this refresh
        try:
             # Check for running loop
            loop = asyncio.get_running_loop()
            loop.create_task(self._refresh_task_logic(task_id, episode_url))
        except RuntimeError:
             # No running loop (e.g. CLI might be blocking elsewhere or structured differently)
             # Create a new loop for this op?
             asyncio.run(self._refresh_task_logic(task_id, episode_url))
             
    async def _refresh_task_logic(self, task_id: str, episode_url: str):
        # Resolve new link
        # Note: We might need gate_id? Usually gate_id is constant for the episode page session?
        # Re-fetching season data might be needed if gate_id expires, but usually just visiting the page is enough.
        
        # We don't have gate_id stored in task currently. 
        # Attempt to fetch without it, or we should store it too. 
        # Engine.get_download_link works better with it but might fallback.
        
        new_link = await self.engine.get_download_link(episode_url)
        
        if new_link:
            logger.info(f"Refreshed link for task {task_id}. Resuming...")
            self.dm.update_download_url(task_id, new_link)
            self.dm.resume_download(task_id)
        else:
            logger.error(f"Failed to refresh link for task {task_id}.")

# Global Instance
core = AuraCore()
