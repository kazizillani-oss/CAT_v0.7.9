"""
CAT Browser — graphical browser shell (replaces CLI browser).
A real browser UI: tab bar, navigation toolbar, address bar, viewport,
new-tab page, history/bookmarks/downloads, menu, fullscreen.

Uses the existing Chromium engine (browser/engine.py) for real HTML/CSS/JS
rendering via Playwright. Pages are rendered to screenshots, converted to
ANSI half-block art, and displayed directly in the terminal.

DESIGN: The viewport uses a single Static widget that gets updated with
the current content (newtab, loading, page screenshot, error). This avoids
fragile CSS display toggling.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os
import re
import time
import threading
import urllib.parse
from pathlib import Path
from typing import Optional

TEXTUAL_AVAILABLE = True
try:
    from textual.app import App, ComposeResult
    from textual.screen import Screen, ModalScreen
    from textual.containers import Horizontal, Vertical, VerticalScroll, Container
    from textual.widgets import Button, Input, Static, Label
    from textual.reactive import reactive
    from textual import work, on
    from textual.message import Message
    from textual.binding import Binding
    from rich.text import Text as RichText
except Exception:
    TEXTUAL_AVAILABLE = False
    App = object
    Screen = object

try:
    from ..browser.browser_state import BrowserState, BrowserTab
    from ..browser.engine import BrowserEngine, PLAYWRIGHT_AVAILABLE
except Exception:
    BrowserState = None
    BrowserTab = None
    PLAYWRIGHT_AVAILABLE = False

try:
    from .. import theme
except Exception:
    theme = None

_BROWSER_STATE = None
def get_state() -> "BrowserState":
    global _BROWSER_STATE
    if _BROWSER_STATE is None:
        _BROWSER_STATE = BrowserState()
    return _BROWSER_STATE

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
BROWSER_CSS = """
#cat-browser {
    width: 100%;
    height: 100%;
    background: $background;
}

/* TAB BAR — compact, minimal */
#browser-tabbar {
    width: 100%;
    height: 3;
    background: $surface;
    border-bottom: solid $border 50%;
    layout: horizontal;
    padding: 0 0 0 0;
}
.browser-tab {
    width: auto;
    min-width: 12;
    max-width: 24;
    height: 3;
    margin: 0;
    padding: 0 1;
    background: transparent;
    color: $text-muted;
    border: none;
    border-bottom: solid $accent 0%;
    content-align: left middle;
}
.browser-tab:hover { background: $surface-alt; color: $text; }
.browser-tab.-active {
    background: $surface-alt;
    color: $text;
    border-bottom: solid $accent 100%;
    text-style: bold;
}
.browser-tab.-loading { color: $warning; }
.browser-tab-favicon { width: 2; content-align: center middle; }
.browser-tab-title { width: 1fr; padding-left: 0; overflow: hidden; }
Button.browser-tab-close {
    width: 3; height: 1; min-height: 1; min-width: 3;
    background: transparent; border: none; color: $text-faint;
    content-align: center middle; padding: 0;
}
Button.browser-tab-close:hover { color: $error; background: transparent; }
Button#browser-newtab-btn {
    width: 3; height: 2; min-height: 1; min-width: 3;
    background: transparent; border: none; color: $text-muted;
    content-align: center middle; padding: 0;
}
Button#browser-newtab-btn:hover { color: $accent; }

/* TOOLBAR — compact single row */
#browser-toolbar {
    width: 100%;
    height: 3;
    background: $background;
    border-bottom: solid $border 50%;
    layout: horizontal;
    padding: 0 1;
}
Button.browser-nav-btn {
    width: 4; height: 1; min-height: 1; min-width: 4;
    background: transparent; border: none; color: $text-muted;
    content-align: center middle; margin-right: 0; padding: 0;
}
Button.browser-nav-btn:hover { color: $text; }
Button.browser-nav-btn:disabled { color: $text-faint; }
#browser-address-wrap {
    width: 1fr; height: 3; min-height: 3;
    background: $surface; border: round $border;
    layout: horizontal; padding: 0 1;
}
#browser-address-wrap:focus-within { border: round $accent; }
#browser-lock { width: 2; height: 3; content-align: center middle; color: $accent; }
#browser-lock.-insecure { color: $text-faint; }
#browser-address {
    width: 1fr; height: 3; min-height: 3;
    background: transparent; border: none; color: $text; padding: 0 1;
}
#browser-address:focus { border: none; }
Button.browser-toolbar-btn {
    width: 4; height: 1; min-height: 1; min-width: 4;
    background: transparent; border: none; color: $text-faint;
    content-align: center middle; margin-left: 0; padding: 0;
}
Button.browser-toolbar-btn:hover { color: $text; }
Button.browser-toolbar-btn.-starred { color: $warning; }

/* VIEWPORT — single content area */
#browser-viewport {
    width: 100%;
    height: 1fr;
    background: $surface;
    overflow-y: auto;
}
#browser-content {
    width: 100%;
    height: auto;
    min-height: 10;
    padding: 0;
    background: $surface;
    color: $text;
}

/* MENU */
#browser-menu {
    width: 24; height: auto; max-height: 70%;
    background: $surface; border: round $border;
    padding: 1 0; dock: right;
}
.browser-menu-item {
    width: 100%; height: 1; padding: 0 2;
    background: transparent; border: none; color: $text;
    content-align: left middle;
}
.browser-menu-item:hover { background: $surface-alt; color: $accent; }
.browser-menu-sep { width: 100%; height: 1; color: $border; }

/* PANELS (history/bookmarks/etc) */
.browser-panel {
    width: 100%; height: 100%;
    background: $background; padding: 2;
}
.browser-panel-title {
    width: 100%; height: 2;
    color: $text; text-style: bold;
    border-bottom: solid $border; margin-bottom: 1;
}
.browser-row {
    width: 100%; height: 1; layout: horizontal;
    padding: 0 1; color: $text;
}
.browser-row:hover { background: $surface-alt; }
.browser-row-favicon { width: 2; content-align: center middle; }
.browser-row-title { width: 1fr; padding-left: 1; overflow: hidden; }
.browser-row-url { width: auto; max-width: 30; color: $text-faint; overflow: hidden; }
.browser-row-time { width: auto; color: $text-faint; padding-left: 1; }
Button.browser-row-action {
    width: 4; height: 1; min-height: 1; min-width: 4;
    background: transparent; border: none; color: $text-faint; padding: 0;
}
Button.browser-row-action:hover { color: $error; }

/* Fullscreen */
#cat-browser.-fullscreen #browser-tabbar { display: none; }
"""

# ---------------------------------------------------------------------------
# NEWTAB HTML (rendered as Rich Text for display in Static widget)
# ---------------------------------------------------------------------------
_NEWTAB_HTML = """\
[bold cyan]  CAT Browser[/]

[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]

[bold] Type a URL or search query in the address bar above[/]
[dim]Press[/] [bold cyan]Ctrl+L[/] [dim]to focus the address bar[/]
[dim]Press[/] [bold cyan]Ctrl+T[/] [dim]for a new tab[/]
[dim]Press[/] [bold cyan]Ctrl+W[/] [dim]to close the tab[/]

[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]
"""

# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------
if TEXTUAL_AVAILABLE:

    class TabWidget(Static):
        def __init__(self, tab: BrowserTab, active: bool = False):
            super().__init__("", classes="browser-tab" + (" -active" if active else "") + (" -loading" if tab.loading else ""))
            self.tab = tab
            self.active = active
            self.can_focus = True

        def compose(self):
            with Horizontal():
                yield Static(self.tab.favicon, classes="browser-tab-favicon")
                yield Static(self.tab.display_title(), classes="browser-tab-title")
                yield Button("×", classes="browser-tab-close", id=f"tab-close-{self.tab.id}")

        def on_mount(self):
            self.tooltip = self.tab.url

        def on_click(self, event):
            event.stop()
            self.post_message(BrowserSwitchTab(self.tab.id))

        def on_button_pressed(self, event):
            event.stop()
            if event.button.id and event.button.id.startswith("tab-close-"):
                tab_id = event.button.id.replace("tab-close-", "")
                self.post_message(BrowserCloseTab(tab_id))

    class TabBar(Horizontal):
        def __init__(self, **kwargs):
            super().__init__(id="browser-tabbar", **kwargs)

        def compose(self):
            state = get_state()
            for tab in state.tabs:
                yield TabWidget(tab, active=(tab.id == state.active_tab_id))
            yield Button("+", id="browser-newtab-btn")

        def refresh_tabs(self):
            for child in list(self.children):
                child.remove()
            state = get_state()
            for tab in state.tabs:
                self.mount(TabWidget(tab, active=(tab.id == state.active_tab_id)))
            self.mount(Button("+", id="browser-newtab-btn"))

        def on_button_pressed(self, event):
            if event.button.id == "browser-newtab-btn":
                self.post_message(BrowserNewTab())

    class AddressBar(Horizontal):
        def __init__(self, **kwargs):
            super().__init__(id="browser-toolbar", **kwargs)

        def compose(self):
            state = get_state()
            tab = state.active_tab
            can_back = tab.history_index > 0 if tab.history else False
            can_fwd = 0 <= tab.history_index < len(tab.history)-1 if tab.history else False
            yield Button("◀", id="browser-back", classes="browser-nav-btn", disabled=not can_back)
            yield Button("▶", id="browser-forward", classes="browser-nav-btn", disabled=not can_fwd)
            yield Button("⟳", id="browser-reload", classes="browser-nav-btn")
            with Horizontal(id="browser-address-wrap"):
                is_secure = tab.url.startswith("https://")
                yield Static("🔒" if is_secure else "○", id="browser-lock", classes="" if is_secure else "-insecure")
                yield Input(value=tab.url if tab.url != "about:home" else "", placeholder="Search or enter address", id="browser-address")
            yield Button("⋮", id="browser-menu-btn", classes="browser-toolbar-btn")

        def on_button_pressed(self, event):
            bid = event.button.id
            if bid == "browser-back":
                self.post_message(BrowserBack())
            elif bid == "browser-forward":
                self.post_message(BrowserForward())
            elif bid == "browser-reload":
                self.post_message(BrowserReload())
            elif bid == "browser-menu-btn":
                self.post_message(BrowserMenuToggle())

        def on_input_submitted(self, event):
            if event.input.id == "browser-address":
                self.post_message(BrowserNavigate(event.value))

    class BrowserViewport(VerticalScroll):
        """Viewport: single content area, updated via show_* methods."""
        def __init__(self, **kwargs):
            super().__init__(id="browser-viewport", **kwargs)
            self._current_mode = "newtab"

        def compose(self):
            yield Static(RichText.from_markup(_NEWTAB_HTML), id="browser-content")

        def show_newtab(self):
            self._set_content(RichText.from_markup(_NEWTAB_HTML))

        def show_loading(self, url: str):
            txt = RichText()
            txt.append(f"\n  ⟳ Loading {url[:70]}…\n", style="bold yellow")
            txt.append("  Please wait…\n", style="dim")
            self._set_content(txt)

        def show_page(self, title: str, url: str, content: str = "", links=None, ansi_image: str = None):
            if url == "about:home":
                self.show_newtab()
                return
            if content.startswith("ERROR:"):
                self.show_error(content[6:])
                return
            txt = RichText()
            if ansi_image:
                try:
                    ansi_rt = RichText.from_ansi(ansi_image)
                    txt.append_text(ansi_rt)
                except Exception:
                    txt.append(ansi_image[:2000])
            else:
                safe_title = title[:80] if title else "Untitled"
                safe_url = url[:80]
                body = content[:2000]
                txt.append(f"{safe_title}\n", style="bold")
                txt.append(f"{safe_url}\n", style="dim")
                txt.append("─" * 40 + "\n", style="dim")
                txt.append(body)
            if links:
                txt.append("\n\n── Links ──\n", style="bold")
                for idx, (href, text) in enumerate(links[:12]):
                    t = (text[:40] + "…") if len(text) > 40 else text
                    h = (href[:50] + "…") if len(href) > 50 else href
                    txt.append(f"  [{idx+1}] {t}  —  {h}\n", style="cyan")
            self._set_content(txt)
            self.scroll_home(animate=False)

        def show_error(self, msg: str):
            txt = RichText()
            txt.append("\n  ⚠ Can't reach this page\n\n", style="bold red")
            txt.append(f"  {msg[:200]}\n\n", style="dim")
            txt.append("  [Press Ctrl+R to reload or ⌂ for home]\n", style="cyan")
            self._set_content(txt)

        def _set_content(self, content):
            """Replace the viewport content widget."""
            try:
                w = self.query_one("#browser-content")
                if isinstance(content, str):
                    w.update(RichText.from_markup(content))
                else:
                    w.update(content)
            except Exception:
                pass

    # -------------------------------------------------------------------
    # Messages
    # -------------------------------------------------------------------
    class BrowserNavigate(Message):
        def __init__(self, url: str): super().__init__(); self.url = url
    class BrowserBack(Message): pass
    class BrowserForward(Message): pass
    class BrowserReload(Message): pass
    class BrowserHome(Message): pass
    class BrowserNewTab(Message): pass
    class BrowserCloseTab(Message):
        def __init__(self, tab_id: str): super().__init__(); self.tab_id = tab_id
    class BrowserSwitchTab(Message):
        def __init__(self, tab_id: str): super().__init__(); self.tab_id = tab_id
    class BrowserBookmark(Message): pass
    class BrowserMenuToggle(Message): pass

    # -------------------------------------------------------------------
    # Browser Shell
    # -------------------------------------------------------------------
    class BrowserShell(Vertical):
        def __init__(self, start_url: str = "about:home", **kwargs):
            super().__init__(id="cat-browser", **kwargs)
            self._start_url = start_url
            self._engine: Optional[BrowserEngine] = None
            self._loading_url: Optional[str] = None

        def compose(self):
            yield TabBar()
            yield AddressBar()
            yield BrowserViewport()

        def on_mount(self):
            state = get_state()
            tab = state.active_tab
            if self._start_url and self._start_url != "about:home":
                self.navigate(self._start_url)
            elif tab.url and tab.url != "about:home":
                self.navigate(tab.url)
            else:
                self.query_one(BrowserViewport).show_newtab()

        def navigate(self, raw_url: str, is_reload: bool = False):
            url = raw_url.strip()
            if not url:
                return
            has_scheme = bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url))
            is_about = url.lower().startswith("about:")
            is_localhost = "localhost" in url.lower()

            def is_search(q):
                if has_scheme or is_about or is_localhost:
                    return False
                if " " in q.strip():
                    return True
                first = q.split()[0] if q else ""
                if "." not in first and "/" not in q:
                    if ":" in first:
                        return False
                    return True
                return False

            if is_search(url):
                q = urllib.parse.quote_plus(url)
                url = f"https://www.google.com/search?q={q}&hl=en"
            elif not has_scheme and not is_about:
                if "." in url.split("/")[0]:
                    url = "https://" + url

            state = get_state()
            tab = state.active_tab
            should_push = not is_reload and (not tab.history or tab.history[-1] != url)
            if should_push:
                if tab.history_index < len(tab.history)-1:
                    tab.history = tab.history[:tab.history_index+1]
                tab.history.append(url)
                tab.history_index = len(tab.history)-1
            tab.url = url
            tab.loading = True
            tab.title = "Loading…"
            if should_push:
                state.update_active(url, "Loading…", loading=True)
            else:
                try:
                    tab.favicon = "G" if "google" in url.lower() else ("○" if not url.startswith("https://") else "🔒")
                except Exception:
                    pass
            self._refresh_chrome()
            vp = self.query_one(BrowserViewport)
            vp.show_loading(url)
            self._load_url(url)

        @work(thread=True, exclusive=True, group="browser-load")
        def _load_url(self, url: str):
            content = ""
            title = ""
            ansi_image = None
            links = None
            success = False
            try:
                if url in ("about:home", "about:blank"):
                    try:
                        self.app.call_from_thread(self._on_load_done, url, "New Tab", "", True, None, None)
                    except Exception:
                        pass
                    return
                if PLAYWRIGHT_AVAILABLE:
                    try:
                        if self._engine is None:
                            from ..browser.engine import BrowserEngine
                            eng = BrowserEngine(headless=True)
                            eng.start(timeout=10)
                            self._engine = eng
                        snap = self._engine.navigate(url, timeout=20)
                        if snap and snap.ok:
                            title = snap.title or url
                            lines = []
                            if snap.title:
                                lines.append(snap.title)
                            for ln in snap.outline_lines[:60]:
                                lines.append(ln)
                            if snap.console_tail:
                                lines.append("Console: " + " | ".join(snap.console_tail[:2]))
                            content = "\n".join(lines) or "Loaded."
                            try:
                                import tempfile
                                from pathlib import Path as _Path
                                from ..cat_browser import render_image_to_ansi
                                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                                    tmp = tf.name
                                ok = self._engine.screenshot(tmp)
                                if ok:
                                    data = _Path(tmp).read_bytes()
                                    term_w = 80
                                    try:
                                        if hasattr(self, 'size') and self.size.width:
                                            term_w = max(60, min(120, self.size.width))
                                    except Exception:
                                        pass
                                    ansi_image = render_image_to_ansi(data, term_width=term_w, max_height=28)
                                try:
                                    _Path(tmp).unlink(missing_ok=True)
                                except Exception:
                                    pass
                            except Exception:
                                ansi_image = None
                            success = True
                        else:
                            content = snap.error if snap else "Navigation failed"
                            title = "Error"
                            success = False
                    except Exception as e:
                        content = f"Chromium error: {e}"
                        title = "Error"
                        success = False
                else:
                    content = "Playwright/Chromium not available. Install with: pip install playwright && playwright install chromium"
                    title = "Error"
                    success = False
            except Exception as e:
                content = f"Load error: {e}"
                title = "Error"
                success = False
            try:
                self.app.call_from_thread(self._on_load_done, url, title, content, success, links, ansi_image)
            except Exception:
                try:
                    self.app.call_from_thread(self._on_load_done, url, title, content, success, links, ansi_image)
                except Exception:
                    pass

        def _on_load_done(self, url: str, title: str, content: str, success: bool, links=None, ansi_image=None):
            state = get_state()
            tab = state.active_tab
            tab.loading = False
            tab.title = title[:40] if title else "Untitled"
            tab.url = url
            if success and url not in ("about:home", "about:blank"):
                try:
                    if state.history and state.history[-1].url == url:
                        state.history[-1].title = tab.title
                except Exception:
                    pass
            self._refresh_chrome()
            vp = self.query_one(BrowserViewport)
            if not success:
                vp.show_error(content.replace("ERROR:", ""))
            else:
                vp.show_page(title, url, content, links, ansi_image)

        def _refresh_chrome(self):
            try:
                self.query_one(TabBar).refresh_tabs()
            except Exception:
                pass
            try:
                toolbar = self.query_one(AddressBar)
                state = get_state()
                tab = state.active_tab
                inp = toolbar.query_one("#browser-address", Input)
                inp.value = tab.url if tab.url != "about:home" else ""
                try:
                    back = toolbar.query_one("#browser-back", Button)
                    back.disabled = not (tab.history_index > 0)
                    fwd = toolbar.query_one("#browser-forward", Button)
                    fwd.disabled = not (0 <= tab.history_index < len(tab.history)-1)
                except Exception:
                    pass
            except Exception:
                pass

        def _load_current_tab(self, url: str):
            state = get_state()
            tab = state.active_tab
            tab.url = url
            tab.loading = True
            tab.title = "Loading…"
            self._refresh_chrome()
            self.query_one(BrowserViewport).show_loading(url)
            self._load_url(url)

        def on_browser_navigate(self, msg: BrowserNavigate):
            self.navigate(msg.url)

        def on_browser_switch_tab(self, msg: BrowserSwitchTab):
            state = get_state()
            state.switch_tab(msg.tab_id)
            self._refresh_chrome()
            tab = state.active_tab
            vp = self.query_one(BrowserViewport)
            if tab.url == "about:home":
                vp.show_newtab()
            else:
                if not tab.title or tab.title == "Loading…":
                    self._load_current_tab(tab.url)
                else:
                    vp.show_page(tab.title, tab.url, f"Switched to {tab.title}")

        def on_browser_back(self, msg: BrowserBack):
            state = get_state()
            url = state.go_back()
            if url:
                self._load_current_tab(url)

        def on_browser_forward(self, msg: BrowserForward):
            state = get_state()
            url = state.go_forward()
            if url:
                self._load_current_tab(url)

        def on_browser_reload(self, msg: BrowserReload):
            state = get_state()
            url = state.active_tab.url
            if url and url != "about:home":
                self._load_current_tab(url)

        def on_browser_new_tab(self, msg: BrowserNewTab):
            state = get_state()
            state.new_tab()
            self._refresh_chrome()
            self.query_one(BrowserViewport).show_newtab()
            try:
                self.query_one("#browser-address", Input).focus()
            except Exception:
                pass

        def on_browser_close_tab(self, msg: BrowserCloseTab):
            state = get_state()
            state.close_tab(msg.tab_id)
            self._refresh_chrome()
            tab = state.active_tab
            if tab.url == "about:home":
                self.query_one(BrowserViewport).show_newtab()
            else:
                self._load_current_tab(tab.url)

        def on_browser_bookmark(self, msg: BrowserBookmark):
            state = get_state()
            tab = state.active_tab
            if state.is_bookmarked(tab.url):
                bm = next((b for b in state.bookmarks if b.url == tab.url), None)
                if bm:
                    state.remove_bookmark(bm.id)
            else:
                state.add_bookmark(tab.title, tab.url)
            self._refresh_chrome()

        def on_browser_menu_toggle(self, msg: BrowserMenuToggle):
            try:
                self.app.push_screen(BrowserMenu())
            except Exception:
                pass

        def on_button_pressed(self, event):
            bid = event.button.id or ""
            if bid == "browser-error-reload":
                self.on_browser_reload(BrowserReload())
            elif bid == "browser-error-home":
                self.on_browser_home(BrowserHome())

    class BrowserMenu(ModalScreen):
        def compose(self):
            with Vertical(id="browser-menu"):
                for label, action in [
                    ("New Tab", "newtab"),
                    ("History", "history"),
                    ("Bookmarks", "bookmarks"),
                    ("Downloads", "downloads"),
                    ("Sign Out", "signout"),
                    ("Developer Tools", "devtools"),
                ]:
                    yield Button(label, id=f"menu-{action}", classes="browser-menu-item")
                yield Static("─", classes="browser-menu-sep")
                yield Button("Close", id="menu-close", classes="browser-menu-item")

        def on_button_pressed(self, event):
            bid = event.button.id or ""
            act = bid.replace("menu-", "")
            self.dismiss(None)
            if act == "newtab":
                try:
                    self.app.query_one(BrowserShell).on_browser_new_tab(BrowserNewTab())
                except Exception:
                    pass
            elif act == "history":
                self.app.push_screen(HistoryScreen())
            elif act == "bookmarks":
                self.app.push_screen(BookmarksScreen())
            elif act == "signout":
                try:
                    from ..fomoji_auth import logout
                    logout()
                except Exception:
                    pass

    class HistoryScreen(ModalScreen):
        def compose(self):
            state = get_state()
            groups = state.history_grouped()
            with Vertical(classes="browser-panel"):
                yield Static("History", classes="browser-panel-title")
                with VerticalScroll():
                    for gname in ("Today", "Yesterday", "Earlier"):
                        entries = groups.get(gname, [])
                        if not entries:
                            continue
                        yield Static(gname, style="bold dim")
                        for h in entries[:40]:
                            with Horizontal(classes="browser-row"):
                                yield Static(h.favicon, classes="browser-row-favicon")
                                yield Static(h.title[:36], classes="browser-row-title")
                                yield Static(h.url[:28], classes="browser-row-url")
                                yield Static(time.strftime("%H:%M", time.localtime(h.timestamp)), classes="browser-row-time")
                yield Button("Close", id="history-close")

        def on_button_pressed(self, event):
            if event.button.id == "history-close":
                self.dismiss(None)

    class BookmarksScreen(ModalScreen):
        def compose(self):
            state = get_state()
            with Vertical(classes="browser-panel"):
                yield Static("Bookmarks", classes="browser-panel-title")
                with VerticalScroll():
                    if not state.bookmarks:
                        yield Static("No bookmarks yet.", style="dim")
                    for bm in state.bookmarks:
                        with Horizontal(classes="browser-row"):
                            yield Static(bm.favicon, classes="browser-row-favicon")
                            yield Static(bm.title[:36], classes="browser-row-title")
                            yield Static(bm.url[:36], classes="browser-row-url")
                            yield Button("Open", classes="browser-row-action", id=f"bm-open-{bm.id}")
                            yield Button("×", classes="browser-row-action", id=f"bm-del-{bm.id}")
                yield Button("Close", id="bookmarks-close")

        def on_button_pressed(self, event):
            bid = event.button.id or ""
            if bid == "bookmarks-close":
                self.dismiss(None)
            elif bid.startswith("bm-open-"):
                bm_id = bid.replace("bm-open-", "")
                state = get_state()
                bm = next((b for b in state.bookmarks if b.id == bm_id), None)
                if bm:
                    self.dismiss(None)
                    try:
                        self.app.query_one(BrowserShell).navigate(bm.url)
                    except Exception:
                        pass
            elif bid.startswith("bm-del-"):
                bm_id = bid.replace("bm-del-", "")
                get_state().remove_bookmark(bm_id)
                self.dismiss(None)
                self.app.push_screen(BookmarksScreen())

    class DownloadsScreen(ModalScreen):
        def compose(self):
            state = get_state()
            with Vertical(classes="browser-panel"):
                yield Static("Downloads", classes="browser-panel-title")
                with VerticalScroll():
                    if not state.downloads:
                        yield Static("No downloads yet.", style="dim")
                    for d in state.downloads:
                        with Horizontal(classes="browser-row"):
                            yield Static("⬇", classes="browser-row-favicon")
                            yield Static(d.filename[:36], classes="browser-row-title")
                            yield Static(f"{d.progress}%", classes="browser-row-time")
                            yield Static(d.status, classes="browser-row-url")
                yield Button("Close", id="downloads-close")

        def on_button_pressed(self, event):
            if event.button.id == "downloads-close":
                self.dismiss(None)

    class DevToolsScreen(ModalScreen):
        def compose(self):
            with Vertical(classes="browser-panel"):
                yield Static("Developer Tools", classes="browser-panel-title")
                with VerticalScroll():
                    yield Static("Console", style="bold dim")
                    yield Static("No errors.", style="dim")
                    yield Static("Network", style="bold dim")
                    yield Static("Requests appear here.", style="dim")
                yield Button("Close", id="devtools-close")

        def on_button_pressed(self, event):
            if event.button.id == "devtools-close":
                self.dismiss(None)

    class BrowserScreen(Screen):
        """Full-screen browser that takes over CAT workspace."""
        BINDINGS = [
            Binding("ctrl+l", "focus_address", "Focus address"),
            Binding("ctrl+t", "new_tab", "New tab"),
            Binding("ctrl+w", "close_tab", "Close tab"),
            Binding("ctrl+r", "reload", "Reload"),
            Binding("ctrl+shift+t", "reopen_tab", "Reopen"),
            Binding("alt+left", "back", "Back"),
            Binding("alt+right", "forward", "Forward"),
            Binding("f11", "fullscreen", "Fullscreen"),
            Binding("escape", "close_browser", "Close browser"),
        ]

        def __init__(self, start_url: str = "about:home"):
            super().__init__()
            self._start_url = start_url

        def on_mount(self):
            try:
                from ..host.launcher import launch_cat_host, can_launch_host
                if can_launch_host():
                    launch_cat_host(start_browser_url=self._start_url or "about:home", start_mode="browser", block=False)
            except Exception:
                pass
            self.dismiss(None)

        def action_focus_address(self):
            pass

        def action_new_tab(self):
            pass

        def action_close_tab(self):
            pass

        def action_reload(self):
            pass

        def action_reopen_tab(self):
            pass

        def action_back(self):
            pass

        def action_forward(self):
            pass

        def action_fullscreen(self):
            pass

        def action_close_browser(self):
            self.dismiss(None)

else:
    BrowserShell = None
    BrowserScreen = None
    get_state = lambda: None
    BROWSER_CSS = ""

# ---------------------------------------------------------------------------
# Standalone launcher
# ---------------------------------------------------------------------------
def launch_browser_app(start_url: str = "about:home") -> int:
    """Launch CAT Browser app (real Chromium / QWebEngineView)."""
    try:
        from ..host.launcher import launch_cat_host, can_launch_host
        if can_launch_host():
            return launch_cat_host(start_browser_url=start_url, start_mode="browser", block=True)
    except Exception:
        pass
    print("CAT Browser requires PySide6. Install with: pip install PySide6")
    return 1
