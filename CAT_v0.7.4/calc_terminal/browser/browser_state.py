"""
CAT Browser state — tabs, history, bookmarks, downloads.
Graphical browser backend, not CLI.
"""

from __future__ import annotations

import json
import time
import uuid
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict

_HISTORY_PATH = Path.home() / ".cat_browser_history.json"
_BOOKMARKS_PATH = Path.home() / ".cat_browser_bookmarks.json"
_DOWNLOADS_PATH = Path.home() / ".cat_browser_downloads.json"
_TABS_PATH = Path.home() / ".cat_browser_tabs.json"

FAVICON_MAP = {
    "youtube.com": "▶",
    "github.com": "⬢",
    "google.com": "G",
    "duckduckgo.com": "◯",
    "gmail.com": "✉",
    "cat": "🐱",
}

def _favicon_for(url: str) -> str:
    url = (url or "").lower()
    for k, v in FAVICON_MAP.items():
        if k in url:
            return v
    if "localhost" in url:
        return "⬢"
    return "○"

@dataclass
class BrowserTab:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
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

@dataclass
class HistoryEntry:
    url: str
    title: str
    timestamp: float
    favicon: str = "○"

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

    def __init__(self):
        self.tabs: List[BrowserTab] = [BrowserTab()]
        self.active_tab_id: str = self.tabs[0].id
        self.history: List[HistoryEntry] = []
        self.bookmarks: List[Bookmark] = []
        self.downloads: List[DownloadItem] = []
        self.closed_tabs: List[BrowserTab] = []
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
                            title=d.get("title",""), url=d["url"],
                            favicon=d.get("favicon","○"),
                            created_at=d.get("created_at", time.time())
                        ))
        except Exception:
            pass
        try:
            if _HISTORY_PATH.exists():
                data = json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
                for d in data[-500:] if isinstance(data, list) else []:
                    if isinstance(d, dict) and d.get("url"):
                        self.history.append(HistoryEntry(
                            url=d["url"], title=d.get("title",""),
                            timestamp=d.get("fetched_at", d.get("timestamp", time.time())),
                            favicon=d.get("favicon", _favicon_for(d["url"]))
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
            if _TABS_PATH.exists():
                data = json.loads(_TABS_PATH.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.tabs = []
                    for d in data.get("tabs", []):
                        if isinstance(d, dict):
                            self.tabs.append(BrowserTab(
                                id=d.get("id", uuid.uuid4().hex[:8]),
                                title=d.get("title", "New Tab"),
                                url=d.get("url", "about:home"),
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
            _HISTORY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
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
            _TABS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
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
        tab = BrowserTab(url=url, title="New Tab" if url=="about:home" else "Loading…",
                         favicon=_favicon_for(url))
        if url != "about:home":
            tab.history = [url]
            tab.history_index = 0
        self.tabs.append(tab)
        self.active_tab_id = tab.id
        self._save_tabs()
        return tab

    def close_tab(self, tab_id: str):
        if len(self.tabs) <= 1:
            t = self.tabs[0]
            self.closed_tabs.append(BrowserTab(title=t.title, url=t.url, favicon=t.favicon))
            t.url = "about:home"
            t.title = "New Tab"
            t.favicon = "○"
            t.history = []
            t.history_index = -1
            t.loading = False
            self._save_tabs()
            return
        idx = next((i for i, t in enumerate(self.tabs) if t.id == tab_id), None)
        if idx is None:
            return
        closed = self.tabs.pop(idx)
        self.closed_tabs.append(closed)
        del self.closed_tabs[:-20]
        if self.active_tab_id == tab_id:
            new_idx = min(idx, len(self.tabs)-1)
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

    def update_active(self, url: str, title: str, loading: bool = False):
        t = self.active_tab
        t.url = url
        t.title = title or t.title
        t.favicon = _favicon_for(url)
        t.loading = loading
        # History for address bar navigation — not tab history
        # Push to global history if not about:home
        if url and url not in ("about:home","about:blank"):
            self.history.append(HistoryEntry(url=url, title=title, timestamp=time.time(), favicon=t.favicon))
            del self.history[:-500]
            self._save_history()

    def navigate_active(self, url: str):
        t = self.active_tab
        if t.history_index < len(t.history)-1:
            t.history = t.history[:t.history_index+1]
        t.history.append(url)
        t.history_index = len(t.history)-1
        t.url = url
        t.loading = True
        t.title = "Loading…"
        self.update_active(url, t.title, loading=True)
        self._save_tabs()

    def can_go_back(self) -> bool:
        t = self.active_tab
        return t.history_index > 0

    def can_go_forward(self) -> bool:
        t = self.active_tab
        return 0 <= t.history_index < len(t.history)-1

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
        if 0 <= t.history_index < len(t.history)-1:
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
    def history_grouped(self):
        """Return dict: Today / Yesterday / Earlier -> list[HistoryEntry]"""
        import datetime
        now = datetime.datetime.now()
        today = now.date()
        yest = today - datetime.timedelta(days=1)
        groups: Dict[str, List[HistoryEntry]] = {"Today": [], "Yesterday": [], "Earlier": []}
        for h in reversed(self.history):
            d = datetime.datetime.fromtimestamp(h.timestamp).date()
            if d == today:
                groups["Today"].append(h)
            elif d == yest:
                groups["Yesterday"].append(h)
            else:
                groups["Earlier"].append(h)
        return groups
