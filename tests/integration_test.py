import asyncio
import sys
import os

# Add parent directory to path so we can import core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.scrapper import AnimeHeavenModular

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    END = '\033[0m'

async def run_tests():
    print(f"{Colors.GREEN}=== STARTING INTEGRATION TEST ==={Colors.END}")
    scraper = AnimeHeavenModular(headless=True)
    
    all_passed = True
    
    try:
        await scraper.start()
        
        # TEST 1: Search Functionality
        print("\n[TEST 1] Searching for 'Slime'...")
        results = await scraper.search_anime("Slime")
        if not results:
            print(f"{Colors.RED}[FAIL]{Colors.END} Search returned no results.")
            all_passed = False
        else:
            print(f"{Colors.GREEN}[PASS]{Colors.END} Found {len(results)} results.")
            # Save for debugging
            scraper.save_json(results, 'test_search_results.json')

        # TEST 2: Fetch Season Data
        print("\n[TEST 2] Fetching Season Data...")
        if results:
            season_url = results[0]['url']
            season_data = await scraper.get_season_data(season_url)
            
            if not season_data or 'episodes' not in season_data:
                print(f"{Colors.RED}[FAIL]{Colors.END} Season data missing.")
                all_passed = False
            else:
                print(f"{Colors.GREEN}[PASS]{Colors.END} Found {len(season_data['episodes'])} episodes.")
                scraper.save_json(season_data, 'test_season_data.json')

            # TEST 3: Clean Episode Name Method
            print("\n[TEST 3] Testing clean_episode_name()...")
            raw_text = "Episode\n1\n1051 d ago"
            expected_name = "Episode 1"
            expected_days = "1051 d ago"
            
            name, days = AnimeHeavenModular.clean_episode_name(raw_text)
            
            if name == expected_name and days == expected_days:
                print(f"{Colors.GREEN}[PASS]{Colors.END} Cleaner works correctly.")
            else:
                print(f"{Colors.RED}[FAIL]{Colors.END} Cleaner failed.")
                print(f"   Expected: ('{expected_name}', '{expected_days}')")
                print(f"   Got:      ('{name}', '{days}')")
                all_passed = False

            # TEST 4: Fetch Download Link
            print("\n[TEST 4] Fetching Download Link...")
            if season_data['episodes']:
                ep_url = season_data['episodes'][0]['url']
                dl_link = await scraper.get_download_link(ep_url)
                
                if dl_link and "animeheaven.me" in dl_link and ".mp4" in dl_link:
                    print(f"{Colors.GREEN}[PASS]{Colors.END} Download link extracted successfully.")
                else:
                    print(f"{Colors.RED}[FAIL]{Colors.END} Download link is invalid or missing.")
                    print(f"   Debug: Link was '{dl_link}'")
                    all_passed = False
        else:
            print(f"{Colors.RED}[SKIP]{Colors.END} Skipping Test 3 & 4 due to Test 1 failure.")

    except Exception as e:
        print(f"{Colors.RED}[FATAL ERROR]{Colors.END} {e}")
        all_passed = False
        
    finally:
        await scraper.close()
        print("\n" + "="*40)
        if all_passed:
            print(f"{Colors.GREEN}ALL TESTS PASSED. System is healthy.{Colors.END}")
        else:
            print(f"{Colors.RED}SOME TESTS FAILED. Check debug_output/.{Colors.END}")
        print("="*40)

if __name__ == "__main__":
    asyncio.run(run_tests())