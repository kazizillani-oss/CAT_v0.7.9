"""
CAT Browser state — tabs, history, bookmarks, downloads.
Graphical browser backend with persistent, deduplicated history
and unified AI search tracking.
"""

from __future__ import annotations

import json
import time
import uuid
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any

_HISTORY_PATH = Path.home() / ".cat_browser_history.json"
_BOOKMARKS_PATH = Path.home() / ".cat_browser_bookmarks.json"
_DOWNLOADS_PATH = Path.home() / ".cat_browser_downloads.json"
_TABS_PATH = Path.home() / ".cat_browser_tabs.json"
TABS_PATH = _TABS_PATH
TABS_FILE = _TABS_PATH

FAVICON_MAP = {
    "youtube.com": "▶",
    "github.com": "⬢",
    "google.com": "G",
    "duckduckgo.com": "◯",
    "gmail.com": "✉",
    "cat": "🐱",
    "wikipedia.org": "W",
}

# RFC 2606 / RFC 6761 reserved example domains
PLACEHOLDER_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "example.edu",
    "example.test",
    "example.localhost",
}


def _favicon_for(url: str) -> str:
    url = (url or "").lower()
    for k, v in FAVICON_MAP.items():
        if k in url:
            return v
    if "localhost" in url:
        return "⬢"
    return "○"


def is_placeholder_url(url: str) -> bool:
    """Returns True if the URL points specifically to an RFC 2606 example domain
    or an IANA documentation notice placeholder page.
    Does NOT match localhost, 127.0.0.1, or legitimate root/protocol pages on iana.org."""
    if not url:
        return False
    u = url.lower().strip()
    # Specific IANA example-domain documentation pages
    if "iana.org/help/example-domains" in u or "iana.org/domains/reserved" in u:
        return True
    for pd in PLACEHOLDER_DOMAINS:
        if f"://{pd}" in u or f"://www.{pd}" in u or u.startswith(f"{pd}/") or u == pd:
            return True
        if re.search(rf"://(?:[a-zA-Z0-9_-]+\.)*{re.escape(pd)}(?::\d+)?(?:/|$)", u):
            return True
    return False


def is_test_artifact_url(url: str) -> bool:
    """Detects leaked test fixture tabs like https://example.com/1, https://example.com/24."""
    if not url:
        return False
    u = url.lower().strip()
    return bool(re.search(r"^https?://(?:www\.)?example\.(?:com|org|net)/\d+", u))


@dataclass
class BrowserTab:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = "New Tab"
    url: str = "about:home"
    favicon: str = "○"
    loading: bool = False
    can_go_back: bool = False
    can_go_forward: bool = False
    history: List[str] = field(default_factory=list)
    history_index: int = -1  # -1 = new tab

    def display_title(self) -> str:
        if self.url == "about:home":
            return "New Tab"
        return self.title[:24] or "Untitled"


TabInfo = BrowserTab


@dataclass
class HistoryEntry:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    url: str = ""
    title: str = ""
    timestamp: float = field(default_factory=time.time)
    favicon: str = "○"
    entry_type: str = "visit"  # "visit" | "ai_search"
    query: str = ""
    provider: str = ""
    search_url: str = ""
    result_count: int = 0
    destination_urls: List[str] = field(default_factory=list)
    status: str = "success"  # "success" | "zero_results" | "failed" | "error" | "rate_limited"
    tab_id: str = ""
    search_results: List[Dict[str, Any]] = field(default_factory=list)

    def display_title(self) -> str:
        if self.entry_type == "ai_search":
            q = self.query or "Web Search"
            return f'AI Search: "{q}" ({self.result_count} results)'
        if self.url in ("about:home", "about:blank"):
            return "New Tab"
        return self.title or self.url or "Untitled"


@dataclass
class Bookmark:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    title: str = ""
    url: str = ""
    favicon: str = "○"
    created_at: float = field(default_factory=time.time)


@dataclass
class DownloadItem:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    filename: str = ""
    url: str = ""
    status: str = "downloading"  # downloading|completed|failed
    progress: int = 0
    path: str = ""


class BrowserState:
    """Single source of truth for CAT Browser graphical shell."""

    TABS_PATH = _TABS_PATH
    TABS_FILE = _TABS_PATH

    def __init__(self, tabs_file: Optional[Path] = None, history_file: Optional[Path] = None):
        # Allow isolating tabs and history via parameters or env vars
        env_tabs = os.environ.get("CAT_BROWSER_TABS_FILE")
        env_hist = os.environ.get("CAT_BROWSER_HISTORY_FILE")

        self._tabs_file = Path(tabs_file) if tabs_file else (Path(env_tabs) if env_tabs else getattr(self.__class__, "TABS_FILE", _TABS_PATH))
        self._history_file = Path(history_file) if history_file else (Path(env_hist) if env_hist else _HISTORY_PATH)
        self.TABS_FILE = self._tabs_file
        self.TABS_PATH = self._tabs_file

        self.tabs: List[BrowserTab] = [BrowserTab()]
        self.active_tab_id: str = self.tabs[0].id
        self.session_restored = False
        self._initial_placeholder_pending = True
        self.history: List[HistoryEntry] = []
        self.bookmarks: List[Bookmark] = []
        self.downloads: List[DownloadItem] = []
        self.closed_tabs: List[BrowserTab] = []
        self.tab_position: str = "top"  # "top" | "left" | "right" | "bottom"
        self.sidebar_width: int = 240
        self._load()

    # ---- persistence -------------------------------------------------
    def _load(self):
        try:
            if _BOOKMARKS_PATH.exists():
                data = json.loads(_BOOKMARKS_PATH.read_text(encoding="utf-8"))
                for d in data if isinstance(data, list) else []:
                    if isinstance(d, dict) and d.get("url"):
                        self.bookmarks.append(Bookmark(
                            id=d.get("id", uuid.uuid4().hex[:8]),
                            title=d.get("title", ""), url=d["url"],
                            favicon=d.get("favicon", "○"),
                            created_at=d.get("created_at", time.time())
                        ))
        except Exception:
            pass

        try:
            h_path = self._history_file
            if h_path.exists():
                data = json.loads(h_path.read_text(encoding="utf-8"))
                for d in (data[-500:] if isinstance(data, list) else []):
                    if isinstance(d, dict) and (d.get("url") or d.get("query")):
                        self.history.append(HistoryEntry(
                            id=d.get("id", uuid.uuid4().hex[:12]),
                            url=d.get("url", ""),
                            title=d.get("title", ""),
                            timestamp=float(d.get("fetched_at", d.get("timestamp", time.time()))),
                            favicon=d.get("favicon", _favicon_for(d.get("url", ""))),
                            entry_type=d.get("entry_type", "visit"),
                            query=d.get("query", ""),
                            provider=d.get("provider", ""),
                            search_url=d.get("search_url", ""),
                            result_count=int(d.get("result_count", 0)),
                            destination_urls=list(d.get("destination_urls", [])),
                            status=d.get("status", "success"),
                            tab_id=d.get("tab_id", ""),
                            search_results=list(d.get("search_results", [])),
                        ))
        except Exception:
            pass

        try:
            if _DOWNLOADS_PATH.exists():
                data = json.loads(_DOWNLOADS_PATH.read_text(encoding="utf-8"))
                for d in data if isinstance(data, list) else []:
                    if isinstance(d, dict):
                        self.downloads.append(DownloadItem(**d))
        except Exception:
            pass

        try:
            tabs_file = self._tabs_file
            if tabs_file.exists():
                data = json.loads(tabs_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.session_restored = True
                    self._initial_placeholder_pending = False
                    self.tabs = []
                    seen_ids = set()
                    for d in data.get("tabs", []):
                        if isinstance(d, dict):
                            tab_url = d.get("url", "about:home")
                            # Sanitize placeholder notice and example tabs on restore
                            if is_placeholder_url(tab_url):
                                continue

                            tab_id = str(d.get("id") or uuid.uuid4().hex)
                            while tab_id in seen_ids:
                                tab_id = uuid.uuid4().hex
                            seen_ids.add(tab_id)
                            self.tabs.append(BrowserTab(
                                id=tab_id,
                                title=d.get("title", "New Tab"),
                                url=tab_url,
                                favicon=d.get("favicon", "○"),
                                loading=False,
                                history=d.get("history", []),
                                history_index=d.get("history_index", -1),
                            ))

                    if self.tabs:
                        self.active_tab_id = data.get("active_tab_id", self.tabs[0].id)
                    if not self.tabs:
                        self.tabs = [BrowserTab()]
                        self.active_tab_id = self.tabs[0].id
                    pos = data.get("tab_position", "top")
                    self.tab_position = pos if pos in ("top", "left", "right", "bottom") else "top"
                    sw = data.get("sidebar_width", 240)
                    try:
                        sw_int = int(sw)
                        self.sidebar_width = max(140, min(sw_int, 480))
                    except (ValueError, TypeError):
                        self.sidebar_width = 240
        except Exception:
            pass

    def _save_bookmarks(self):
        try:
            data = [asdict(b) for b in self.bookmarks]
            _BOOKMARKS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _save_history(self):
        try:
            # Keep last 500
            data = [asdict(h) for h in self.history[-500:]]
            self._history_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _save_downloads(self):
        try:
            data = [asdict(d) for d in self.downloads]
            _DOWNLOADS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _save_tabs(self):
        try:
            data = {
                "active_tab_id": self.active_tab_id,
                "tab_position": self.tab_position,
                "sidebar_width": getattr(self, "sidebar_width", 240),
                "tabs": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "url": t.url,
                        "favicon": t.favicon,
                        "history": t.history,
                        "history_index": t.history_index,
                    }
                    for t in self.tabs
                ],
            }
            self._tabs_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ---- tabs --------------------------------------------------------
    @property
    def active_tab(self) -> BrowserTab:
        for t in self.tabs:
            if t.id == self.active_tab_id:
                return t
        # Fallback
        self.active_tab_id = self.tabs[0].id if self.tabs else ""
        return self.tabs[0] if self.tabs else BrowserTab()

    def new_tab(self, url: str = "about:home") -> BrowserTab:
        if self._initial_placeholder_pending and len(self.tabs) == 1:
            # Reuse the default record for the first real browser view.
            tab = self.tabs[0]
            tab.url = url
            tab.title = "New Tab" if url == "about:home" else "Loading…"
            tab.favicon = _favicon_for(url)
            tab.loading = False
            tab.history = [url] if url != "about:home" else []
            tab.history_index = 0 if tab.history else -1
            self._initial_placeholder_pending = False
            self.active_tab_id = tab.id
            self._save_tabs()
            return tab

        self._initial_placeholder_pending = False
        tab = BrowserTab(url=url, title="New Tab" if url == "about:home" else "Loading…",
                         favicon=_favicon_for(url))
        if url != "about:home":
            tab.history = [url]
            tab.history_index = 0
        self.tabs.append(tab)
        self.active_tab_id = tab.id
        self._save_tabs()
        return tab

    def close_tab(self, tab_id: str):
        idx = next((i for i, t in enumerate(self.tabs) if t.id == tab_id), None)
        if idx is None:
            return
        closed = self.tabs.pop(idx)
        self.closed_tabs.append(closed)
        del self.closed_tabs[:-20]
        if not self.tabs:
            new_tab = BrowserTab(url="about:home", title="New Tab", favicon="○")
            self.tabs.append(new_tab)
            self.active_tab_id = new_tab.id
        elif self.active_tab_id == tab_id:
            new_idx = min(idx, len(self.tabs) - 1)
            self.active_tab_id = self.tabs[new_idx].id
        self._save_tabs()

    def switch_tab(self, tab_id: str):
        if any(t.id == tab_id for t in self.tabs):
            self.active_tab_id = tab_id
            self._save_tabs()

    def reopen_closed(self) -> Optional[BrowserTab]:
        if not self.closed_tabs:
            return None
        tab = self.closed_tabs.pop()
        tab.id = uuid.uuid4().hex[:8]
        self.tabs.append(tab)
        self.active_tab_id = tab.id
        self._save_tabs()
        return tab

    def add_visit(self, url: str, title: str = "", favicon: str = "○", tab_id: str = "") -> Optional[HistoryEntry]:
        """Record a visited URL into global browser history with deduplication."""
        url = (url or "").strip()
        if not url or url in ("about:home", "about:blank"):
            return None

        # Do not record placeholder documentation domains
        if is_placeholder_url(url):
            return None

        now = time.time()
        # Deduplicate: if last visit entry is same URL within 20s, update it
        for existing in reversed(self.history[-10:]):
            if existing.entry_type == "visit" and existing.url == url:
                if (now - existing.timestamp) < 20.0:
                    existing.title = title or existing.title
                    existing.timestamp = now
                    if tab_id:
                        existing.tab_id = tab_id
                    self._save_history()
                    return existing

        entry = HistoryEntry(
            id=uuid.uuid4().hex[:12],
            url=url,
            title=title or url,
            timestamp=now,
            favicon=favicon or _favicon_for(url),
            entry_type="visit",
            tab_id=tab_id,
        )
        self.history.append(entry)
        del self.history[:-500]
        self._save_history()
        return entry

    def add_ai_search(
        self,
        query: str,
        provider: str = "",
        search_url: str = "",
        result_count: int = 0,
        destination_urls: Optional[List[str]] = None,
        status: str = "success",
        tab_id: str = "",
        search_results: Optional[List[Dict[str, Any]]] = None,
    ) -> HistoryEntry:
        """Record an AI web search in the shared browser history with full result metadata."""
        query = (query or "").strip()
        if not query:
            return HistoryEntry()

        now = time.time()
        clean_dests = [u for u in (destination_urls or []) if not is_placeholder_url(u)]
        clean_results = [r for r in (search_results or []) if isinstance(r, dict) and not is_placeholder_url(r.get("url", ""))]
        if not clean_dests and clean_results:
            clean_dests = [r.get("url", "") for r in clean_results if r.get("url")]

        # Deduplicate consecutive identical searches within 15s
        for existing in reversed(self.history[-10:]):
            if existing.entry_type == "ai_search" and existing.query.lower() == query.lower():
                if (now - existing.timestamp) < 15.0:
                    existing.provider = provider or existing.provider
                    existing.search_url = search_url or existing.search_url
                    existing.result_count = result_count or len(clean_results) or len(clean_dests)
                    existing.destination_urls = clean_dests or existing.destination_urls
                    existing.search_results = clean_results or existing.search_results
                    existing.status = status
                    existing.timestamp = now
                    if tab_id:
                        existing.tab_id = tab_id
                    self._save_history()
                    return existing

        entry = HistoryEntry(
            id=uuid.uuid4().hex[:12],
            url=search_url or "",
            title=f'AI Search: "{query}"',
            timestamp=now,
            favicon="🔍",
            entry_type="ai_search",
            query=query,
            provider=provider or "CAT AI",
            search_url=search_url or "",
            result_count=result_count or len(clean_results) or len(clean_dests),
            destination_urls=clean_dests,
            status=status,
            tab_id=tab_id,
            search_results=clean_results,
        )
        self.history.append(entry)
        del self.history[:-500]
        self._save_history()
        return entry

    def remove_history_entry(self, entry_id: str) -> bool:
        """Remove a single history entry by its stable ID."""
        initial_len = len(self.history)
        self.history = [h for h in self.history if h.id != entry_id]
        if len(self.history) != initial_len:
            self._save_history()
            return True
        return False

    def clear_history(self) -> None:
        """Clear all browser history records."""
        self.history = []
        self._save_history()

    def search_history(self, term: str) -> List[HistoryEntry]:
        """Case-insensitive search across queries, titles, URLs, providers, and result articles."""
        term = (term or "").strip().lower()
        if not term:
            return list(self.history)
        results = []
        for h in self.history:
            matched = (
                term in h.query.lower() or
                term in h.title.lower() or
                term in h.url.lower() or
                term in h.provider.lower()
            )
            if not matched and getattr(h, "search_results", None):
                for r in h.search_results:
                    if (term in (r.get("title") or "").lower() or
                        term in (r.get("source") or "").lower() or
                        term in (r.get("snippet") or "").lower() or
                        term in (r.get("url") or "").lower()):
                        matched = True
                        break
            if matched:
                results.append(h)
        return results

    def update_active(self, url: str, title: str, loading: bool = False, tab_id: str = ""):
        t = self.active_tab
        t.url = url
        t.title = title or t.title
        t.favicon = _favicon_for(url)
        t.loading = loading
        # Push to global history with deduplication
        if url and url not in ("about:home", "about:blank"):
            self.add_visit(url=url, title=title, favicon=t.favicon, tab_id=tab_id or t.id)

    def navigate_active(self, url: str):
        t = self.active_tab
        if t.history_index < len(t.history) - 1:
            t.history = t.history[:t.history_index + 1]
        t.history.append(url)
        t.history_index = len(t.history) - 1
        t.url = url
        is_home = url in ("about:home", "about:blank")
        t.loading = not is_home
        t.title = "New Tab" if is_home else "Loading…"
        self.update_active(url, t.title, loading=not is_home, tab_id=t.id)
        self._save_tabs()

    def can_go_back(self) -> bool:
        t = self.active_tab
        return t.history_index > 0

    def can_go_forward(self) -> bool:
        t = self.active_tab
        return 0 <= t.history_index < len(t.history) - 1

    def go_back(self) -> Optional[str]:
        t = self.active_tab
        if t.history_index > 0:
            t.history_index -= 1
            t.url = t.history[t.history_index]
            self._save_tabs()
            return t.url
        return None

    def go_forward(self) -> Optional[str]:
        t = self.active_tab
        if 0 <= t.history_index < len(t.history) - 1:
            t.history_index += 1
            t.url = t.history[t.history_index]
            self._save_tabs()
            return t.url
        return None

    # ---- bookmarks ---------------------------------------------------
    def add_bookmark(self, title: str, url: str) -> Bookmark:
        # Deduplicate
        for b in self.bookmarks:
            if b.url == url:
                return b
        bm = Bookmark(title=title or url, url=url, favicon=_favicon_for(url))
        self.bookmarks.append(bm)
        self._save_bookmarks()
        return bm

    def remove_bookmark(self, bm_id: str):
        self.bookmarks = [b for b in self.bookmarks if b.id != bm_id]
        self._save_bookmarks()

    def is_bookmarked(self, url: str) -> bool:
        return any(b.url == url for b in self.bookmarks)

    # ---- downloads ---------------------------------------------------
    def add_download(self, filename: str, url: str, path: str) -> DownloadItem:
        d = DownloadItem(filename=filename, url=url, status="completed", progress=100, path=path)
        self.downloads.insert(0, d)
        del self.downloads[50:]
        self._save_downloads()
        return d

    # ---- history grouping --------------------------------------------
    def history_grouped(self) -> Dict[str, List[HistoryEntry]]:
        """Return dict: Today / Yesterday / Earlier -> list[HistoryEntry]"""
        import datetime
        now = datetime.datetime.now()
        today = now.date()
        yest = today - datetime.timedelta(days=1)
        groups: Dict[str, List[HistoryEntry]] = {"Today": [], "Yesterday": [], "Earlier": []}
        for h in reversed(self.history):
            try:
                d = datetime.datetime.fromtimestamp(h.timestamp).date()
            except Exception:
                d = today
            if d == today:
                groups["Today"].append(h)
            elif d == yest:
                groups["Yesterday"].append(h)
            else:
                groups["Earlier"].append(h)
        return groups


# ---------------------------------------------------------------------------
# Global history management integration helpers
# ---------------------------------------------------------------------------

_SHARED_STATE_INSTANCE: Optional[BrowserState] = None


def get_browser_history_manager() -> BrowserState:
    """Returns the shared BrowserState from active browser window or persistent file."""
    global _SHARED_STATE_INSTANCE
    try:
        from ..browser_gui.qt_browser import get_active_browser_window
        win = get_active_browser_window()
        if win and hasattr(win, "state") and win.state is not None:
            return win.state
    except Exception:
        pass

    if _SHARED_STATE_INSTANCE is None:
        _SHARED_STATE_INSTANCE = BrowserState()
    return _SHARED_STATE_INSTANCE


def record_ai_search(
    query: str,
    provider: str = "",
    search_url: str = "",
    result_count: int = 0,
    destination_urls: Optional[List[str]] = None,
    status: str = "success",
    tab_id: str = "",
    search_results: Optional[List[Dict[str, Any]]] = None,
) -> Optional[HistoryEntry]:
    """Records an AI web search in CAT Browser's shared history system."""
    try:
        mgr = get_browser_history_manager()
        return mgr.add_ai_search(
            query=query,
            provider=provider,
            search_url=search_url,
            result_count=result_count,
            destination_urls=destination_urls,
            status=status,
            tab_id=tab_id,
            search_results=search_results,
        )
    except Exception:
        return None


def record_page_visit(
    url: str,
    title: str = "",
    favicon: str = "○",
    tab_id: str = ""
) -> Optional[HistoryEntry]:
    """Records a page visit in CAT Browser's shared history system."""
    try:
        mgr = get_browser_history_manager()
        return mgr.add_visit(url=url, title=title, favicon=favicon, tab_id=tab_id)
    except Exception:
        return None
