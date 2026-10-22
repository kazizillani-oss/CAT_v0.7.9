"""CAT browser/ — navigation history (back / forward / reload).

Pure logic, no I/O — the controller asks this class where to go next
and then drives the engine. Duplicate consecutive entries are not
pushed (a reload must not create history), and pushing truncates the
forward branch exactly like every real browser.
"""

from typing import List, Optional


class NavigationHistory:
    """A bounded back/forward stack of URLs."""

    def __init__(self, limit: int = 100):
        self._limit = max(2, int(limit))
        self._entries: List[str] = []
        self._index = -1

    # ------------------------------------------------------------- state --
    @property
    def current(self) -> Optional[str]:
        if 0 <= self._index < len(self._entries):
            return self._entries[self._index]
        return None

    @property
    def index(self) -> int:
        return self._index

    def __len__(self):
        return len(self._entries)

    def can_back(self) -> bool:
        return self._index > 0

    def can_forward(self) -> bool:
        return self._index < len(self._entries) - 1

    # ------------------------------------------------------------ moves --
    def push(self, url: str) -> Optional[str]:
        """Record a navigation. Returns the URL that should be loaded
        (None when `url` is a duplicate of the current entry — nothing
        to do). Truncates any forward branch."""
        if not url:
            return None
        if self.current == url:
            return None
        # drop forward branch + enforce the cap
        self._entries = self._entries[:self._index + 1]
        self._entries.append(url)
        if len(self._entries) > self._limit:
            self._entries = self._entries[-self._limit:]
        self._index = len(self._entries) - 1
        return url

    def replace_current(self, url: str) -> None:
        """Rewrite the current entry in place (redirects)."""
        if not url:
            return
        if self._entries and self._index >= 0:
            self._entries[self._index] = url
        else:
            self.push(url)

    def back(self) -> Optional[str]:
        if not self.can_back():
            return None
        self._index -= 1
        return self._entries[self._index]

    def forward(self) -> Optional[str]:
        if not self.can_forward():
            return None
        self._index += 1
        return self._entries[self._index]

    def reload_url(self) -> Optional[str]:
        return self.current

    # ------------------------------------------------------------ reset --
    def clear(self) -> None:
        self._entries = []
        self._index = -1
