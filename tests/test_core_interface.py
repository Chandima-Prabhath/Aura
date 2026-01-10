import asyncio
import os
import sys
import shutil
import time

# Add parent dir to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.interface import core
from core.config import settings

async def main():
    print("--- Testing Core Interface ---")
    
    # 1. Setup Config
    test_dl_path = os.path.abspath("downloads_test_core")
    if os.path.exists(test_dl_path):
        shutil.rmtree(test_dl_path)
    
    settings.set("download_path", test_dl_path, save=False)
    print(f"Download Path set to: {test_dl_path}")
    
    # 2. Initialize
    await core.initialize()
    
    try:
        # 3. Search
        print("\n[Search] Searching for 'Naruto'...")
        results = await core.search("Naruto")
        if not results:
            print("FAILED: No results found.")
            return
        
        first_result = results[0]
        print(f"SUCCESS: Found {len(results)} results. First: {first_result.title}")
        
        # 4. Get Season
        print(f"\n[Season] Fetching data for {first_result.url}...")
        season_data = await core.get_season(first_result.url)
        episodes = season_data['episodes']
        if not episodes:
            print("FAILED: No episodes found.")
            return
        print(f"SUCCESS: Found {len(episodes)} episodes.")
        
        # 5. Download Episode
        # Pick the last one usually implies it's recent or short? 
        # Let's pick Ep 1 if available
        target_ep = episodes[0]
        anime_title = season_data['title'] or "TestAnime"
        
        print(f"\n[Download] Requesting download for: {target_ep.name}")
        # Need to convert Episode object to dict for download_episode? 
        # interface.download_episode takes Dict currently!
        # Let's check interface.py... 
        # Method signature: async def download_episode(self, episode_data: Dict, anime_title: str):
        # But we updated Engine to return Objects.
        # So we need to call vars() or adjust interface.py?
        # Let's verify interface.py behavior visually first...
        # It does: episode_url = episode_data.get('url')
        # If we pass an Object which doesn't have .get(), it will FAIL.
        # CORRECTIVE ACTION: We should have updated interface.py to accept models or dicts, or use vars() here.
        # I will use vars() here for now, but note to fix interface.py if strictly typed.
        
        task_id = await core.download_episode(vars(target_ep), anime_title)
        
        if not task_id:
            print("FAILED: Could not initiate download (link resolution failed).")
            return
            
        print(f"SUCCESS: Download started. Task ID: {task_id}")
        
        # 6. Monitor Loop
        print("\n[Monitor] Waiting for progress...")
        start_time = time.time()
        while True:
            task = core.dm.get_task(task_id)
            if not task:
                print("Task lost?")
                break
                
            print(f"Status: {task.status} | Progress: {task.progress:.2f}% | Speed: {task.speed}")
            
            if task.status == "Completed":
                print("SUCCESS: Download Completed!")
                break
            if task.status == "Error":
                print(f"FAILED: Download Error: {task.error_message}")
                break
            
            if time.time() - start_time > 60: # Timeout 60s
                print("TIMEOUT: Test took too long.")
                break
                
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await core.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
