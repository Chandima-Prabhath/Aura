import asyncio
import json
import logging
import random
from pathlib import Path
from urllib.parse import urljoin
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Setup Logging
logging.basicConfig(
    level=logging.INFO, # Changed to INFO to reduce noise in tests
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AnimeHeavenModular:
    def __init__(self, headless=True):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"

    async def start(self):
        logger.info("Starting Browser...")
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
        
        # Block media to save bandwidth
        async def block_media(route, request):
            if request.resource_type in ("media", "video", "audio") or ".mp4" in request.url:
                await route.abort()
            else:
                await route.continue_()
        
        await self.context.route("**/*", block_media)
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        logger.info("Browser started with media blocking enabled.")

    async def close(self):
        logger.info("Closing browser...")
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    # ------------------------------------------------------------------
    # STEP 1: SEARCH
    # ------------------------------------------------------------------
    async def search_anime(self, query):
        logger.info(f"Searching for: {query}")
        page = await self.context.new_page()
        results = []

        try:
            await page.goto("https://animeheaven.me/", timeout=60000)
            await page.wait_for_load_state('domcontentloaded')
            
            search_box = await page.query_selector('input[name="s"]')
            if search_box:
                await search_box.fill(query)
                await page.keyboard.press("Enter")
                
                try:
                    await page.wait_for_selector('.info3', timeout=5000)
                except PlaywrightTimeoutError:
                    pass

                items = await page.query_selector_all('.similarimg')
                for item in items:
                    try:
                        title_elem = await item.query_selector('a')
                        img_elem = await item.query_selector('img')
                        
                        if title_elem:
                            title = await title_elem.inner_text()
                            href = await title_elem.get_attribute('href')
                            full_url = urljoin("https://animeheaven.me/", href)
                            
                            img_url = ""
                            if img_elem:
                                img_url = await img_elem.get_attribute('src')
                                img_url = urljoin("https://animeheaven.me/", img_url)

                            results.append({
                                'title': title.strip(),
                                'url': full_url,
                                'image': img_url
                            })
                    except Exception as e:
                        logger.warning(f"Error parsing search result: {e}")
            else:
                logger.error("Search box not found.")

        except Exception as e:
            logger.error(f"Error during search: {e}")
        finally:
            await page.close()
            return results

    # ------------------------------------------------------------------
    # STEP 2: GET SEASON DATA
    # ------------------------------------------------------------------
    async def get_season_data(self, season_url):
        logger.info(f"Fetching season data from: {season_url}")
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

            title_elem = await page.query_selector('.infotitle')
            if title_elem:
                data['title'] = await title_elem.inner_text()

            ep_links = await page.query_selector_all('.linetitle2 a')
            for ep in ep_links:
                try:
                    text = await ep.inner_text()
                    href = await ep.get_attribute('href')
                    if href:
                        data['episodes'].append({
                            'name': text.strip(), # Raw name
                            'url': urljoin("https://animeheaven.me/", href)
                        })
                except:
                    pass
            
            data['episodes'].reverse()

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
            logger.error(f"Error fetching season data: {e}")
        finally:
            await page.close()
            return data

    # ------------------------------------------------------------------
    # STEP 3: GET DOWNLOAD LINK
    # ------------------------------------------------------------------
    async def get_download_link(self, episode_url):
        logger.info(f"Fetching download link for: {episode_url}")
        page = await self.context.new_page()
        dl_link = None

        try:
            await page.goto(episode_url, timeout=60000)
            try:
                await page.wait_for_selector('.linetitle2', timeout=5000)
            except PlaywrightTimeoutError:
                pass

            link_elem = await page.query_selector('a[href*="cv.animeheaven.me"]')
            if link_elem:
                dl_link = await link_elem.get_attribute('href')
            
            if not dl_link:
                link_elem = await page.query_selector("a:has-text('Download')")
                if link_elem:
                    dl_link = await link_elem.get_attribute('href')

        except Exception as e:
            logger.error(f"Error getting download link: {e}")
        finally:
            await page.close()
            await asyncio.sleep(random.uniform(1.0, 2.0))
            return dl_link

    # ------------------------------------------------------------------
    # HELPER: Clean Episode Name
    # ------------------------------------------------------------------
    @staticmethod
    def clean_episode_name(text):
        """
        Cleans episode text like "Episode\n1\n1051 d ago"
        Returns: ("Episode 1", "1051 d ago")
        """
        lines = text.strip().split('\n')
        name = lines[0]
        days_ago = ""
        
        # Heuristic to separate name and date
        # Input: ["Episode", "1", "1051 d ago"]
        if len(lines) >= 3:
            name = f"{lines[0]} {lines[1]}" # "Episode 1"
            days_ago = lines[2]            # "1051 d ago"
        elif len(lines) == 2:
            # If input is just "Episode 1"
            name = f"{lines[0]} {lines[1]}"
            days_ago = "Unknown"
            
        return name, days_ago

    def save_json(self, data, filename):
        try:
            out_dir = Path("debug_output")
            out_dir.mkdir(exist_ok=True)
            file_path = out_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save JSON: {e}")
