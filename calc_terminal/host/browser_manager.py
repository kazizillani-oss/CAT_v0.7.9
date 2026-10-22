"""
CAT BrowserManager — internal browser controller owned by CAT.

Lifecycle belongs to CAT (no browser.exe, no separate app):

    CAT (calc_terminal/host/desktop.py CATDesktopWindow)
     └── BrowserManager
          ├── EmbeddedBrowserPane (QWebEngineView child)
          ├── BrowserState (tabs/history/bookmarks persistence)
          └── QWebEngineProfile (cookies/storage/WebAuthn)

API:

    createTab(), closeTab(), navigate(url), goBack(), goForward(),
    reload(), executeScript(js), setViewport(w,h), destroy()

The browser renderer (QWebEngineView) is the working Chromium-based
engine that renders real HTML/CSS/JavaScript. It is integrated directly
into CAT's browser window — not launched as a separate application.

All rendering is LIVE (Chromium via Qt WebEngine / WebView2), not
screenshots, not text extraction.
"""

from __future__ import annotations

from typing import Optional

try:
    from PySide6.QtCore import QSize, QUrl
    from PySide6.QtWebEngineCore import QWebEngineProfile
    _QT = True
except ImportError:
    try:
        from PyQt6.QtCore import QSize, QUrl  # type: ignore
        from PyQt6.QtWebEngineCore import QWebEngineProfile  # type: ignore
        _QT = True
    except ImportError:
        _QT = False


class BrowserManager:
    """
    CAT-owned browser controller. One instance per CAT process/host window.

    Wraps an EmbeddedBrowserPane (the graphical QWebEngineView surface) and
    exposes a stable API for CAT CLI, AI Agent, and Fomoji auth to drive.

    Example:
        mgr = BrowserManager(browser_pane)
        mgr.navigate("http://localhost:3000/connector.html")
        mgr.goBack()
        mgr.executeScript("document.title")
    """

    def __init__(self, browser_pane):
        """
        browser_pane: EmbeddedBrowserPane instance from desktop.py
        """
        self.pane = browser_pane

    # ------------------------------------------------------------------ tabs --

    def createTab(self, url: str = "about:home", switch: bool = True):
        """Create a new tab. Returns tab index."""
        return self.pane.new_tab(url)

    def closeTab(self, index: Optional[int] = None):
        """Close tab at index, or current tab if None."""
        if index is None:
            index = self.pane.tab_bar.currentIndex()
        self.pane._close_tab(index)

    def switchTab(self, index: int):
        self.pane.tab_bar.setCurrentIndex(index)
        self.pane.viewport_stack.setCurrentIndex(index)
        self.pane._sync_chrome()

    def tabCount(self) -> int:
        return self.pane.tab_bar.count()

    # --------------------------------------------------------------- navigation --

    def navigate(self, url: str):
        """Navigate current tab to url (real HTML/CSS/JS, not text)."""
        self.pane.navigate(url)

    def goBack(self):
        self.pane.go_back()

    def goForward(self):
        self.pane.go_forward()

    def reload(self):
        self.pane.reload()

    def home(self):
        self.pane.navigate("about:home")

    def currentUrl(self) -> str:
        try:
            idx = self.pane.tab_bar.currentIndex()
            w = self.pane._views[idx]
            if self.pane._is_newtab(w):
                return "about:home"
            return w.url().toString()  # type: ignore
        except Exception:
            return ""

    def currentTitle(self) -> str:
        try:
            idx = self.pane.tab_bar.currentIndex()
            w = self.pane._views[idx]
            if self.pane._is_newtab(w):
                return "New Tab"
            return w.title()  # type: ignore
        except Exception:
            return ""

    # -------------------------------------------------------------- scripting --

    def executeScript(self, js: str, callback=None):
        """
        Execute JavaScript in the current page's context (live DOM).
        callback receives the result (if any).
        """
        try:
            idx = self.pane.tab_bar.currentIndex()
            w = self.pane._views[idx]
            if not self.pane._is_newtab(w):
                page = w.page()  # type: ignore
                if callback:
                    page.runJavaScript(js, callback)
                else:
                    page.runJavaScript(js)
                return True
        except Exception:
            pass
        return False

    def setViewport(self, width: int, height: int):
        """Resize the web viewport — CSS sees real dimensions (vw/vh/media queries)."""
        try:
            idx = self.pane.tab_bar.currentIndex()
            w = self.pane._views[idx]
            if not self.pane._is_newtab(w):
                w.page().setViewportSize(QSize(int(width), int(height)))  # type: ignore
                return True
        except Exception:
            pass
        return False

    # -------------------------------------------------------------- lifecycle --

    def destroy(self):
        """Tear down browser with CAT (no orphan process)."""
        try:
            # Close all WebEngineViews; profile will be destroyed with parent
            for w in list(getattr(self.pane, "_views", [])):
                try:
                    w.deleteLater()
                except Exception:
                    pass
            self.pane._views.clear()  # type: ignore
        except Exception:
            pass

    # -------------------------------------------------------------- devtools / AI hooks --

    def getConsoleLogs(self):
        """Return recent console logs for AI Agent inspection (future)."""
        # EmbeddedBrowserPane could expose page console via QWebEnginePage.javaScriptConsoleMessage
        # For now return empty; hook point for AI integration.
        return []

    def screenshot(self, path: str) -> bool:
        """For AI analysis — capture viewport to file (not used for rendering)."""
        try:
            idx = self.pane.tab_bar.currentIndex()
            w = self.pane._views[idx]
            if not self.pane._is_newtab(w):
                # QWebEngineView grab
                pixmap = w.grab()  # type: ignore
                return pixmap.save(path)
        except Exception:
            pass
        return False
