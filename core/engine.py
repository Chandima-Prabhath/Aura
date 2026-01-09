import asyncio
import logging
import random
import re
import json
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urljoin
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class AnimeHeavenEngine:
    def __init__(self, headless=True):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        
        # Create output directory for JSONs
        self.output_dir = Path("debug_jsons")
        self.output_dir.mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # UTILS
    # ------------------------------------------------------------------
    def _save_json(self, filename: str, data):
        """Helper to save data to JSON file for inspection."""
        filepath = self.output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.info(f"Saved data to {filepath}")

    # ------------------------------------------------------------------
    # BROWSER MANAGEMENT
    # ------------------------------------------------------------------
    async def start(self):
        logger.info("Engine: Starting Browser...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        self.context = await self.browser.new_context(
            user_agent=self.user_agent,
            viewport={'width': 1920, 'height': 1080},
            locale='en-US'
        )
        
        # Block media and images to speed up scraping (except images we explicitly wait for if needed)
        async def block_media(route, request):
            if request.resource_type in ("media", "video", "audio", "font") or ".mp4" in request.url:
                await route.abort()
            else:
                await route.continue_()
        
        await self.context.route("**/*", block_media)
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        logger.info("Engine: Browser ready with media blocking.")

    async def close(self):
        logger.info("Engine: Closing browser...")
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    # ------------------------------------------------------------------
    # FEATURE: SEARCH
    # ------------------------------------------------------------------
    async def search_anime(self, query: str) -> List[Dict]:
        """
        Search for anime.
        Returns: List of dicts [{title, url, image}]
        """
        logger.info(f"Engine: Searching '{query}'...")
        page = await self.context.new_page()
        results = []

        try:
            await page.goto("https://animeheaven.me/", timeout=60000)
            await page.wait_for_load_state('domcontentloaded')
            
            # Fill search
            search_box = await page.query_selector('input[name="s"]')
            if search_box:
                await search_box.fill(query)
                await page.keyboard.press("Enter")
                
                # Wait for results to load (based on .info3 container in HTML)
                try:
                    await page.wait_for_selector('.info3', timeout=10000)
                except PlaywrightTimeoutError:
                    logger.warning("Engine: Search results container not found immediately.")

                # Extract data
                # Based on HTML Step 2: Items are in .similarimg
                items = await page.query_selector_all('.similarimg')
                for item in items:
                    try:
                        # The main link is usually the image link or the title link. 
                        # Both point to anime.php
                        link_elem = await item.query_selector('a[href*="anime.php"]')
                        img_elem = await item.query_selector('img.coverimg')
                        title_elem = await item.query_selector('.similarname a.c')

                        if link_elem:
                            href = await link_elem.get_attribute('href')
                            
                            # Title
                            title = "Unknown"
                            if title_elem:
                                title = await title_elem.inner_text()
                            else:
                                # Fallback to alt text or aria if needed
                                if img_elem:
                                    title = await img_elem.get_attribute('alt')

                            # Image
                            img_url = ""
                            if img_elem:
                                img_url = await img_elem.get_attribute('src')
                                img_url = urljoin("https://animeheaven.me/", img_url)
                            
                            results.append({
                                'title': title.strip(),
                                'url': urljoin("https://animeheaven.me/", href),
                                'image': img_url
                            })
                    except Exception as e:
                        logger.debug(f"Error parsing search item: {e}")
                        pass
        
        except Exception as e:
            logger.error(f"Engine: Search failed {e}")
        finally:
            await page.close()
        
        self._save_json("search_results.json", results)
        logger.info(f"Engine: Found {len(results)} search results.")
        return results

    # ------------------------------------------------------------------
    # FEATURE: GET SEASON DATA
    # ------------------------------------------------------------------
    async def get_season_data(self, season_url: str) -> Dict:
        """
        Fetch episodes and related shows.
        Returns: Dict {title, url, episodes: [{name, url, gate_id}], related: [...]}
        """
        logger.info(f"Engine: Fetching season data from {season_url}")
        page = await self.context.new_page()
        data = {
            'url': season_url,
            'title': '',
            'episodes': [],
            'related': []
        }

        try:
            await page.goto(season_url, timeout=60000)
            await page.wait_for_load_state('domcontentloaded')

            # Get Title
            title_elem = await page.query_selector('.infotitle')
            if title_elem:
                data['title'] = await title_elem.inner_text()

            # Get Episodes
            # Based on HTML Step 3: .linetitle2 contains the <a> tags.
            # We also need the ID from the onclick event: gate("HASH")
            ep_links = await page.query_selector_all('.linetitle2 a')
            for ep in ep_links:
                try:
                    raw_text = await ep.inner_text()
                    href = await ep.get_attribute('href')
                    onclick = await ep.get_attribute('onclick')
                    
                    if href:
                        # Extract ID from onclick="gate("...")"
                        gate_id = None
                        if onclick:
                            match = re.search(r'gate\("([^"]+)"\)', onclick)
                            if match:
                                gate_id = match.group(1)
                        
                        # Clean name
                        clean_name = self.clean_episode_name(raw_text)
                        
                        data['episodes'].append({
                            'name': clean_name,
                            'raw_name': raw_text.strip(),
                            'url': urljoin("https://animeheaven.me/", href),
                            'gate_id': gate_id # Crucial for download link generation
                        })
                except Exception as e:
                    logger.debug(f"Error parsing episode link: {e}")
                    pass
            
            # The list in HTML is usually high-to-low (24 to 1), reverse so it's 1 to 24
            data['episodes'].reverse()

            # Get Related Shows
            related_items = await page.query_selector_all('.similarimg')
            for item in related_items:
                try:
                    link_elem = await item.query_selector('a')
                    if link_elem:
                        r_title = await link_elem.inner_text()
                        r_href = await link_elem.get_attribute('href')
                        r_img_elem = await item.query_selector('img')
                        r_img = await r_img_elem.get_attribute('src') if r_img_elem else ""
                        
                        data['related'].append({
                            'title': r_title.strip(),
                            'url': urljoin("https://animeheaven.me/", r_href),
                            'image': urljoin("https://animeheaven.me/", r_img)
                        })
                except:
                    pass

        except Exception as e:
            logger.error(f"Engine: Season fetch failed {e}")
        finally:
            await page.close()
        
        self._save_json("episode_list.json", data)
        logger.info(f"Engine: Retrieved {len(data['episodes'])} episodes.")
        return data

    # ------------------------------------------------------------------
    # FEATURE: GET DOWNLOAD LINK (Low Level)
    # ------------------------------------------------------------------
    async def get_download_link(self, episode_url: str, gate_id: str = None) -> Optional[str]:
        """
        Returns the direct video URL for a single episode page.
        
        Args:
            episode_url: The URL (usually 'gate.php')
            gate_id: The hash ID extracted from the previous page's onclick event.
        """
        page = await self.context.new_page()
        dl_link = None

        try:
            # If we have the gate_id, set the cookie before navigating.
            # This mimics the JavaScript 'gate()' function.
            if gate_id:
                await page.context.add_cookies([{
                    'name': 'key',
                    'value': gate_id,
                    'domain': 'animeheaven.me',
                    'path': '/'
                }])
                logger.info(f"Engine: Set cookie 'key={gate_id}'")
            else:
                logger.warning("Engine: No gate_id provided. Download link might not load.")

            await page.goto(episode_url, timeout=60000)
            await page.wait_for_load_state('domcontentloaded')
            
            # Wait specifically for the Download button to appear
            # Based on HTML Step 4: Text "Download Episode X" or href containing "&d"
            try:
                await page.wait_for_selector('a:has-text("Download")', timeout=10000)
            except PlaywrightTimeoutError:
                logger.warning(f"Engine: Download button not found on {episode_url}")

            # Extract the link
            # Method A: Text "Download"
            try:
                link_elem = await page.query_selector("a:has-text('Download')")
                if link_elem:
                    dl_link = await link_elem.get_attribute('href')
            except:
                pass

            # Method B: Href check (fallback)
            if not dl_link:
                try:
                    link_elem = await page.query_selector('a[href*="&d"]')
                    if link_elem:
                        dl_link = await link_elem.get_attribute('href')
                except:
                    pass

        except Exception as e:
            logger.error(f"Engine: Error fetching download link for {episode_url}: {e}")
        finally:
            await page.close()
            # Small delay to be polite
            await asyncio.sleep(random.uniform(1.0, 2.0))
            return dl_link

    # ------------------------------------------------------------------
    # FEATURE: RESOLVE EPISODE SELECTION
    # ------------------------------------------------------------------
    async def resolve_episode_selection(self, season_url: str, selection: str) -> List[Dict]:
        """
        High-level method to handle user selection.
        """
        # 1. Get All Episodes
        season_data = await self.get_season_data(season_url)
        total_eps = len(season_data['episodes'])
        
        if total_eps == 0:
            logger.error("Engine: No episodes found in season.")
            return []

        # 2. Parse Range
        indices = self._parse_episode_range(selection, total_eps)
        logger.info(f"Engine: User selected {len(indices)} episodes out of {total_eps}.")
        
        # 3. Fetch Links for Selection
        results = []
        for index in indices:
            # 1-based index to 0-based
            if 0 < index <= total_eps:
                ep_data = season_data['episodes'][index - 1]
                
                logger.info(f"Engine: Fetching link for Ep {index} - {ep_data['name']}")
                
                # Pass the gate_id extracted from get_season_data
                dl_link = await self.get_download_link(ep_data['url'], ep_data.get('gate_id'))
                
                if dl_link:
                    results.append({
                        'episode_number': index,
                        'episode_name': ep_data['name'],
                        'download_url': dl_link
                    })
                else:
                    logger.warning(f"Engine: Skipped Ep {index} due to missing link.")
            else:
                logger.warning(f"Engine: Invalid index {index} requested.")
        
        self._save_json("download_links.json", results)
        return results

    # ------------------------------------------------------------------
    # HELPER: Range Parser
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_episode_range(range_str: str, total: int) -> List[int]:
        if not range_str or range_str.strip().lower() == "all":
            return list(range(1, total + 1))
        
        selected = set()
        parts = range_str.split(',')
        
        for part in parts:
            part = part.strip()
            if '-' in part:
                try:
                    start, end = part.split('-')
                    s, e = int(start), int(end)
                    if s < 1: s = 1
                    if e > total: e = total
                    selected.update(range(s, e + 1))
                except ValueError:
                    logger.warning(f"Skipping invalid range: {part}")
            else:
                try:
                    num = int(part)
                    if 1 <= num <= total:
                        selected.add(num)
                except ValueError:
                    logger.warning(f"Skipping invalid number: {part}")
        
        return sorted(list(selected))

    @staticmethod
    def clean_episode_name(text: str):
        lines = text.strip().split('\n')
        name = lines[0]
        # Handle the multi-line episode div structure
        # Line 0: "Episode", Line 1: "24", Line 2: "Time ago" -> "Episode 24"
        if len(lines) >= 2:
            # Filter out empty lines
            parts = [line.strip() for line in lines if line.strip()]
            if len(parts) >= 2:
                # Combine "Episode" and "24"
                name = f"{parts[0]} {parts[1]}"
        return name.strip()