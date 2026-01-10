import sys
import os
import webbrowser
import asyncio
import pyperclip
import argparse
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from textual.app import App, ComposeResult, Screen
from textual.containers import Horizontal, Vertical, Center
from textual.command import CommandPalette, Provider, Hit, Hits
from textual.widgets import (
    Header, Footer, Input, Button, ListView, 
    ListItem, Static, Label
)
from textual import on, work, log
from core.interface import core
from core.models import AnimeSearchResult, Episode

# ----------------------------------------------------------------------
# Command Palette Logic
# ----------------------------------------------------------------------

class AnimeCommandProvider(Provider):
    """Provides commands for the Palette (Ctrl+P)."""
    
    # FIX: Must accept match_style
    def __init__(self, screen, match_style):
        super().__init__(screen, match_style)
        # FIX: Store app in a custom variable to avoid conflict with read-only 'app' property
        self.application = screen.app

    async def search(self, query: str) -> Hits:
        """Called when user types in the command palette."""
        matcher = self.matcher(query)

        # Define all available commands in a list
        commands = [
            (
                "Search",
                lambda: self.application.switch_screen("main"),
                "Go to Search Screen"
            ),
            (
                "Home",
                lambda: self.application.switch_screen("main"),
                "Go to Home Screen"
            ),
            (
                "About",
                lambda: self.application.notify("AnimeHeaven CLI v1.0", title="Info"),
                "Show App Info"
            ),
            (
                "Quit",
                lambda: self.application.exit(),
                "Exit Application"
            )
        ]

        for name, action, help_text in commands:
            # If query is empty, show all commands immediately.
            # If query exists, filter using matcher.
            
            if not query:
                score = len(name)
                yield Hit(
                    score, 
                    matcher.highlight(name), 
                    action, 
                    help_text
                )
            else:
                if score := matcher.match(name):
                    yield Hit(
                        score, 
                        matcher.highlight(name), 
                        action, 
                        help_text
                    )

# ----------------------------------------------------------------------
# Custom List Items
# ----------------------------------------------------------------------

class SearchResultItem(ListItem):
    def __init__(self, title: str, url: str, image: str):
        super().__init__()
        self.title = title
        self.url = url
        self.image = image

    def compose(self) -> ComposeResult:
        yield Label(self.title)

class EpisodeItem(ListItem):
    """Represents an available episode to be selected."""
    def __init__(self, number: int, episode_name: str):
        super().__init__()
        self.number = number
        self.episode_name = episode_name

    def compose(self) -> ComposeResult:
        yield Label(f"Ep {self.number}: {self.episode_name}")

class QueueItem(ListItem):
    """Represents an episode selected for download."""
    def __init__(self, number: int, episode_name: str):
        super().__init__()
        self.number = number
        self.episode_name = episode_name

    def compose(self) -> ComposeResult:
        yield Label(f"Ep {self.number}: {self.episode_name}")

class ResultItem(ListItem):
    """Represents a successfully fetched download link."""
    def __init__(self, number: int, episode_name: str, url: str):
        super().__init__()
        self.number = number
        self.episode_name = episode_name
        self.url = url

    def compose(self) -> ComposeResult:
        with Horizontal(id="result_row"):
            yield Label(f"[bold]Ep {self.number}[/]: {self.episode_name}", id="res_label")
            yield Button("Copy", variant="primary", id="btn_copy", classes="compact")
            yield Button("Open", variant="success", id="btn_open", classes="compact")

# ----------------------------------------------------------------------
# Screens
# ----------------------------------------------------------------------

class ResultsScreen(Screen):
    """Screen displaying the final download links."""
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def __init__(self, results: list):
        super().__init__()
        self.results = results

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="res_container"):
            yield Label(f"[bold cyan]Found {len(self.results)} Links[/bold cyan]", id="res_title")
            yield Static("Scroll down to copy or open links.", classes="hint")
            yield ListView(id="res_list")
        yield Footer()

    def on_mount(self) -> None:
        res_list = self.query_one("#res_list", ListView)
        if not self.results:
            res_list.append(ListItem(Label("No links retrieved or failed.")))
            return
        
        for item in self.results:
            res_list.append(ResultItem(
                number=item.get('episode_number'),
                episode_name=item.get('episode_name'),
                url=item.get('download_url')
            ))

    @on(Button.Pressed, ".compact")
    def on_button_press(self, event: Button.Pressed) -> None:
        # Traverse up: Button -> Horizontal -> ResultItem
        list_item = event.button.parent.parent
        
        if isinstance(list_item, ResultItem):
            if event.button.id == "btn_copy":
                try:
                    pyperclip.copy(list_item.url)
                    self.notify("Link copied to clipboard!")
                except:
                    self.notify("Clipboard error")
            elif event.button.id == "btn_open":
                webbrowser.open(list_item.url)


class SeasonScreen(Screen):
    """Screen for selecting episodes and ranges."""
    BINDINGS = [
        ("escape", "action_back_or_quit", "Back/Quit"),
        ("ctrl+p", "app.toggle_command_palette", "Palette")
    ]

    def __init__(self, anime_url: str, anime_title: str):
        super().__init__()
        self.anime_url = anime_url
        self.anime_title = anime_title
        self.all_episodes = [] 
        self.selected_indices = set()

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main_container"):
            
            # 1. Dashboard Header
            with Horizontal(id="dash_header"):
                yield Static(f"[bold]{self.anime_title}[/bold]", id="anime_header")
                yield Static("Queue: 0", id="queue_counter")

            # 2. Controls Dashboard
            with Vertical(id="controls_area"):
                with Horizontal(id="range_bar"):
                    yield Input(placeholder="Range (e.g. 1-5)", id="range_input", classes="input_dark")
                    yield Button("Add", id="btn_add_range", variant="default", classes="btn_small")
                    yield Button("Clear", id="btn_clear", variant="error", classes="btn_small")
                    yield Button("All", id="btn_select_all", variant="default", classes="btn_small")
                
                # Action Button
                yield Button("DOWNLOAD SELECTED", id="btn_fetch", variant="primary")

            # 3. Split Content
            with Horizontal(id="split_view"):
                with Vertical(id="col_available"):
                    yield Label("Available Episodes", classes="col_header")
                    yield ListView(id="ep_list")
                
                with Vertical(id="col_selected"):
                    yield Label("Selected Queue", classes="col_header")
                    yield ListView(id="sel_list")
        
        yield Footer()

    def on_mount(self) -> None:
        self.fetch_season_data()

    @work(exclusive=True)
    async def fetch_season_data(self) -> None:
        ep_list = self.query_one("#ep_list", ListView)
        ep_list.append(ListItem(Label("Loading episodes...")))
        
        try:
            data = await core.get_season(self.anime_url)
            
            ep_list.clear()
            if not data['episodes']:
                ep_list.append(ListItem(Label("No episodes found")))
                return

            self.all_episodes = data['episodes']
            for ep in self.all_episodes:
                idx = data['episodes'].index(ep) + 1
                ep_list.append(EpisodeItem(idx, ep.name))
                
        except Exception as e:
            log.error(f"Season load error: {e}")
            ep_list.clear()
            ep_list.append(ListItem(Label(f"Error: {e}")))

    # ----------------------------------------------------------------------
    # Interaction Logic
    # ----------------------------------------------------------------------

    def update_selection_list(self) -> None:
        sel_list = self.query_one("#sel_list", ListView)
        counter = self.query_one("#queue_counter", Static)
        
        sel_list.clear()
        sorted_indices = sorted(list(self.selected_indices))
        
        # Update counter text
        count = len(sorted_indices)
        counter.update(f"Queue: {count}")
        
        for idx in sorted_indices:
            if 1 <= idx <= len(self.all_episodes):
                ep_meta = self.all_episodes[idx - 1]
                sel_list.append(QueueItem(idx, ep_meta.name))

    @on(Button.Pressed, "#btn_add_range")
    def on_add_range(self) -> None:
        input_field = self.query_one("#range_input", Input)
        text = input_field.value.strip()
        
        if not text:
            self.notify("Enter a range first.", severity="warning")
            return

        total = len(self.all_episodes)
        total = len(self.all_episodes)
        # We need to access static method from Engine or use helper? 
        # Actually CoreInterface doesn't expose it. We can copy it or use engine directly as property of core.
        parsed_indices = core.engine._parse_episode_range(text, total)
        
        if not parsed_indices:
            self.notify("Invalid format.", severity="error")
            return

        added = 0
        for idx in parsed_indices:
            if idx not in self.selected_indices:
                self.selected_indices.add(idx)
                added += 1
        
        self.update_selection_list()
        self.notify(f"Added {added} episodes.")
        input_field.value = ""
        self.query_one("#ep_list", ListView).focus()

    @on(Button.Pressed, "#btn_select_all")
    def on_select_all(self) -> None:
        if not self.all_episodes: return
        for i in range(1, len(self.all_episodes) + 1):
            self.selected_indices.add(i)
        self.update_selection_list()
        self.notify("Added all episodes.")

    @on(Button.Pressed, "#btn_clear")
    def on_clear(self) -> None:
        self.selected_indices.clear()
        self.update_selection_list()
        self.notify("Selection cleared.")

    @on(ListView.Selected, "#ep_list")
    def on_episode_selected(self, event: ListView.Selected) -> None:
        if event.item and isinstance(event.item, EpisodeItem):
            if event.item.number not in self.selected_indices:
                self.selected_indices.add(event.item.number)
                self.update_selection_list()

    @on(ListView.Selected, "#sel_list")
    def on_queue_selected(self, event: ListView.Selected) -> None:
        if event.item and isinstance(event.item, QueueItem):
            self.selected_indices.discard(event.item.number)
            self.update_selection_list()

    @on(Button.Pressed, "#btn_fetch")
    def on_fetch_pressed(self) -> None:
        if not self.selected_indices:
            self.notify("Queue is empty.", severity="warning")
            return
        self.start_fetch_process()

    @work(exclusive=True)
    async def start_fetch_process(self) -> None:
        btn = self.query_one("#btn_fetch", Button)
        original_label = btn.label
        btn.disabled = True
        btn.label = "STARTING..."
        
        sorted_eps = sorted(list(self.selected_indices))
        
        started = 0
        failed = 0

        # We need to iterate and trigger downloads 1 by 1
        # To do this efficiently, we can use the existing resolution logic in interface?
        # Actually interface has download_episode(episode_data).
        # We have self.all_episodes which are dicts or objects? 
        # In SeasonScreen.fetch_season_data: self.all_episodes = data['episodes'] which is List[Episode].
        
        try:
             for idx in sorted_eps:
                if 1 <= idx <= len(self.all_episodes):
                    ep_obj = self.all_episodes[idx - 1]
                    # We must pass a dict to download_episode based on previous analysis of interface.py?
                    # Let's check interface.py again or assume vars() is safer.
                    # CoreInterface.download_episode accepts 'episode_data: Dict'.
                    
                    # Also we need to ensure the engine resolves the link internally if not refreshed?
                    # Wait, download_episode calls engine.get_download_link if not present.
                    # Yes, logic is: episode_url provided -> resolution -> download.
                    
                    try:
                         # We pass vars(ep_obj) to convert Episode to dict
                         await core.download_episode(vars(ep_obj), self.anime_title)
                         started += 1
                    except Exception as e:
                         log.error(f"Download failed for {ep_obj.name}: {e}")
                         failed += 1
            
             self.notify(f"Started {started} downloads. ({failed} failed)", timeout=5)
             self.selected_indices.clear()
             self.update_selection_list()
             
        except Exception as e:
            log.error(f"Batch start error: {e}")
            self.notify(f"Error: {str(e)}", severity="error")
        finally:
            btn.disabled = False
            btn.label = original_label

    # ----------------------------------------------------------------------
    # Smart Back/Quit Logic
    # ----------------------------------------------------------------------
    def action_back_or_quit(self) -> None:
        """
        If there is a screen behind us, go back.
        If this is the only screen (Direct URL mode), Quit app.
        """
        # Textual stack includes to current screen. 
        # If length is 1, it's the only screen.
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        else:
            self.app.exit()


class SearchScreen(Screen):
    """Modern Hero Search Screen."""
    BINDINGS = [
        ("escape", "app.quit", "Quit"), 
        ("ctrl+p", "app.toggle_command_palette", "Palette")
    ]

    def __init__(self, auto_query: str = None):
        super().__init__()
        self.auto_query = auto_query

    def compose(self) -> ComposeResult:
        yield Header()
        
        with Vertical(id="hero_container"):
            with Center():
                yield Label("[bold cyan]ANIMEHEAVEN[/bold cyan]", id="app_logo")
                yield Label("CLI Downloader", id="app_subtitle")
            
            with Center():
                yield Input(placeholder="Search anime...", id="search_input", classes="hero_input")
                yield Button("Search", variant="primary", id="search_btn", classes="hero_btn")

            yield Static("Press 'Ctrl+P' for Commands", classes="mini_hint")

        with Vertical(id="results_wrapper"):
             yield ListView(id="results_list")
        
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "search_btn":
            self.perform_search()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.perform_search()

    def on_mount(self) -> None:
        if self.auto_query:
            search_input = self.query_one("#search_input", Input)
            search_input.value = self.auto_query
            self.perform_search()

    @work(exclusive=True)
    async def perform_search(self) -> None:
        query = self.query_one("#search_input", Input).value
        results_list = self.query_one("#results_list", ListView)
        results_list.clear()
        
        if not query:
            return
            
        results_list.append(ListItem(Label("Searching...")))
        
        try:
            results = await core.search(query)
            results_list.clear()
            
            if not results:
                results_list.append(ListItem(Label("No results found")))
                results_list.focus() 
                return

            for res in results:
                results_list.append(SearchResultItem(res.title, res.url, res.image))
                
            self.query_one("#app_logo").display = False
            self.query_one("#app_subtitle").display = False
            self.query_one("#search_input").placeholder = "Search again..."
            
            results_list.focus()
                
        except Exception as e:
            results_list.clear()
            results_list.append(ListItem(Label(f"Error: {e}")))
            results_list.focus()

    @on(ListView.Selected, "#results_list")
    def on_result_selected(self, event: ListView.Selected) -> None:
        if event.item and isinstance(event.item, SearchResultItem):
            self.app.push_screen(SeasonScreen(event.item.url, event.item.title))

# ----------------------------------------------------------------------
# Main App
# ----------------------------------------------------------------------

class AnimeHeavenApp(App):
    """Professional TUI App."""
    
    # Global Bindings
    BINDINGS = [("ctrl+q", "app.quit", "Quit App")]
    
    # Register the Command Provider
    COMMANDS = {AnimeCommandProvider}

    def __init__(self, initial_query: str = None, initial_url: str = None):
        super().__init__()
        self.initial_query = initial_query
        self.initial_url = initial_url

    CSS = """
    App {
        background: #0f111a;
    }

    Screen {
        align: center middle;
    }

    /* Typography & Spacing */
    Label {
        text-align: center;
    }

    /* Hero Search Screen */
    #hero_container {
        height: 12;
        align: center middle;
    }

    #app_logo {
        text-align: center;
        text-style: bold;
        color: cyan;
        margin-bottom: 1;
    }

    #app_subtitle {
        text-style: dim;
        margin-bottom: 3;
    }

    .hero_input {
        width: 60;
        border: thick $primary;
    }

    .hero_btn {
        margin-left: 1;
    }

    #results_wrapper {
        height: 1fr;
        width: 90%;
        padding: 1;
    }

    .mini_hint {
        text-align: center;
        color: $text-muted;
        height: 2;
    }

    /* Season Dashboard */
    #main_container {
        height: 1fr; 
        width: 100%;
        padding: 1 2;
    }

    #dash_header {
        height: 3;
        margin-bottom: 1;
        border-bottom: solid $panel;
    }

    #anime_header {
        width: 3fr;
        height: 1fr;
        text-align: left;
        align: left middle;
    }

    #queue_counter {
        width: 1fr;
        height: 1fr;
        text-align: right;
        align: right middle;
        background: $panel;
        color: $accent;
        border: round $accent;
        padding: 0 1;
    }

    #controls_area {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        border: solid $panel;
        background: $panel;
    }

    #range_bar {
        height: 3;
        margin-bottom: 1;
        align: center middle;
    }

    .input_dark {
        width: 30;
    }

    .btn_small {
        min-width: 8;
        margin-left: 1;
    }

    #btn_fetch {
        height: 3;
        width: 1fr;
    }

    /* Lists */
    #split_view {
        height: 1fr;
    }

    #col_available, #col_selected {
        width: 1fr;
        height: 1fr;
    }
    
    #col_available {
        border-right: solid $panel;
        padding-right: 1;
    }

    .col_header {
        text-align: center;
        text-style: bold;
        height: 2;
        color: $text-muted;
        border-bottom: solid $panel;
    }

    ListView {
        height: 1fr;
        background: $background;
        border: solid $panel;
        scrollbar-gutter: stable;
    }

    ListItem {
        padding: 0 1;
        height: auto; 
    }
    
    ListItem:hover {
        background: $secondary;
    }
    
    /* Result Screen */
    #res_container {
        height: 1fr;
        padding: 0 2;
    }
    
    #res_title {
        text-align: center;
        height: 3;
    }

    .hint {
        text-align: center;
        color: $text-muted;
        height: 2;
        margin-bottom: 1;
    }

    #res_list {
        border: solid $primary;
        height: 1fr;
    }

    #res_list ListItem {
        height: 4;
        border-bottom: solid $panel;
    }

    #result_row {
        height: 1fr;
        width: 1fr;
    }

    .compact {
        margin-left: 1;
        min-width: 8;
    }
    """

    SCREENS = {
        "main": SearchScreen,
    }

    async def on_mount(self) -> None:
        self.app.notify("Initializing Aura Core...", timeout=2)
        try:
            await core.initialize()
            self.app.notify("Aura Core Ready!", severity="information", timeout=2)
            
            # Routing Logic
            if self.initial_url:
                self.notify("Loading direct season...", timeout=2)
                try:
                    data = await core.get_season(self.initial_url)
                    title = data.get('title', 'Unknown Season')
                    self.push_screen(SeasonScreen(self.initial_url, title))
                except Exception as e:
                    self.notify(f"Failed to load URL: {e}", severity="error")
                    self.push_screen("main")
            
            elif self.initial_query:
                search_screen = SearchScreen(auto_query=self.initial_query)
                self.push_screen(search_screen)
            
            else:
                await self.push_screen("main")
                
        except Exception as e:
            self.app.notify(f"Startup Error: {e}", severity="error")
            log.error(f"Engine startup error: {e}")

    async def on_unmount(self) -> None:
        try:
            await core.shutdown()
        except Exception:
            pass

# ----------------------------------------------------------------------
# Entry Point & Arg Parsing
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="AnimeHeaven CLI Downloader",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        "query", 
        nargs="?", 
        help="Anime name to search for directly (e.g., 'Naruto')"
    )
    
    parser.add_argument(
        "--url", "-u",
        help="Direct URL to anime season page (e.g., https://animeheaven.me/anime.php?id=123)"
    )
    
    args = parser.parse_args()
    
    app = AnimeHeavenApp(initial_query=args.query, initial_url=args.url)
    app.run()

if __name__ == "__main__":
    main()