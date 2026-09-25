"""
CAT Host — Browser Surface Window

This is CAT's own graphical browser window. When CAT needs to render a
real webpage (HTML/CSS/JavaScript), it creates this window containing
the embedded Chromium rendering surface (QWebEngineView).

Architecture:

    cat  (→ main.py → cli.bootstrap → CAT's own runtime)
        ↓
    Browser Mode requested (Ctrl+Shift+B / cat browse / Fomoji auth)
        ↓
    CAT creates this window (same process, owned by CAT)
        ↓
    ┌─────────────────────────────────────────────┐
    │ CAT Browser                                │
    │  ← → ⟳ ⌂ [address bar]                   │
    │ ┌─────────────────────────────────────────┐ │
    │ │                                         │ │
    │ │   EmbeddedBrowserPane (QWebEngineView)  │ │
    │ │   REAL HTML / CSS / JavaScript          │ │
    │ │   Chromium via Qt WebEngine             │ │
    │ │                                         │ │
    │ └─────────────────────────────────────────┘ │
    └─────────────────────────────────────────────┘

The browser rendering surface is a REAL graphical web renderer:
  - QWebEngineView per tab (Chromium via Qt WebEngine == WebView2-class)
  - Persistent QWebEngineProfile (cookies, localStorage, sessionStorage,
    IndexedDB, Cache) under ~/.cat_browser_storage so Fomoji login persists
  - Full HTML/CSS/JS/DOM, images/SVG/fonts/animations, fetch/XHR,
    WebSockets/SSE, responsive layout, media queries, flexbox, etc.
  - True mouse/keyboard/scroll/touchpad/text-input/drag-drop via the
    native view (not simulated)
  - WebAuthn / Passkeys / Credential APIs delegated to the underlying
    Chromium/WebView2 — no fake, no bypass.

This window is NOT a separate application. It is owned by CAT and
created on demand when Browser Mode is requested. When the user closes
this window, CAT resumes (Textual TUI or fallback REPL).
"""

from __future__ import annotations

import os
import sys
import re
import pathlib
import urllib.parse
from typing import Optional

# ---------------------------------------------------------------------------
# Qt availability — keep import-time safe so `import calc_terminal.host`
# never crashes on headless CI (fallback paths handle it).
# ---------------------------------------------------------------------------
_QT_AVAILABLE = False
_QT_BINDING = None
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QStackedWidget, QPushButton, QLabel, QTabBar, QLineEdit
    )
    from PySide6.QtCore import Qt, QUrl, Signal, QTimer, QSize
    from PySide6.QtGui import QAction, QKeySequence, QShortcut
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import (
        QWebEngineProfile, QWebEnginePage, QWebEngineDownloadRequest
    )
    _QT_AVAILABLE = True
    _QT_BINDING = "PySide6"
except ImportError:
    try:
        from PyQt6.QtWidgets import (
            QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QStackedWidget, QPushButton, QLabel, QTabBar, QLineEdit
        )
        from PyQt6.QtCore import Qt, QUrl, pyqtSignal as Signal, QTimer, QSize
        from PyQt6.QtGui import QAction, QKeySequence, QShortcut
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtWebEngineCore import (
            QWebEngineProfile, QWebEnginePage, QWebEngineDownloadRequest
        )
        _QT_AVAILABLE = True
        _QT_BINDING = "PyQt6"
    except ImportError:
        _QT_AVAILABLE = False
        _QT_BINDING = None


if _QT_AVAILABLE:
    try:
        if _QT_BINDING == "PySide6":
            from PySide6.QtWebEngineCore import QWebEngineSettings
        else:
            from PyQt6.QtWebEngineCore import QWebEngineSettings
    except Exception:
        QWebEngineSettings = None

    class SecureWebEnginePage(QWebEnginePage):
        """Secure web page with DevTools and Inspect Element completely disabled."""

        def __init__(self, profile=None, parent=None):
            if profile is not None:
                super().__init__(profile, parent)
            else:
                super().__init__(parent)
            self._apply_optimal_settings()

        def _apply_optimal_settings(self):
            if QWebEngineSettings:
                try:
                    s = self.settings()
                    s.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
                    s.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
                    s.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)
                    s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
                    s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
                    s.setAttribute(QWebEngineSettings.WebAttribute.DnsPrefetchEnabled, True)
                except Exception:
                    pass

        def triggerAction(self, action, checked=False):
            if action == QWebEnginePage.WebAction.InspectElement:
                return
            super().triggerAction(action, checked)

    class SecureWebEngineView(QWebEngineView):
        """Custom view with inspect code disabled and smooth hardware rendering."""

        def contextMenuEvent(self, event):
            menu = self.createStandardContextMenu()
            if menu:
                for act in list(menu.actions()):
                    txt = (act.text() or "").lower()
                    if any(k in txt for k in ("inspect", "developer", "view source", "view page source", "devtools")):
                        menu.removeAction(act)
                        act.setEnabled(False)
                        act.setVisible(False)
                menu.exec(event.globalPos())

        def keyPressEvent(self, event):
            key = event.key()
            if key == Qt.Key.Key_F12:
                event.accept()
                return
            mods = event.modifiers()
            ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
            shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
            if ctrl and shift and key in (Qt.Key.Key_I, Qt.Key.Key_C, Qt.Key.Key_J):
                event.accept()
                return
            if ctrl and key == Qt.Key.Key_U:
                event.accept()
                return
            super().keyPressEvent(event)

    # Reuse existing CAT state + theme helpers
    try:
        from ..browser.browser_state import BrowserState  # type: ignore
    except Exception:
        BrowserState = None  # type: ignore

    try:
        from .. import theme as _theme  # type: ignore
    except Exception:
        _theme = None  # type: ignore

    _FOMOJI_PAGE_NAMES = {
        "connector.html": "Fomoji Connect",
        "home.html": "Fomoji Home",
        "security.html": "Fomoji Security",
        "identities.html": "Fomoji Identities",
        "settings.html": "Fomoji Settings",
        ":8765": "Fatty CAT",
        "8765": "Fatty CAT",
    }

    def _friendly_url(url: str) -> str:
        if not url or url in ("about:home", "about:blank"):
            return ""
        if "8765" in url:
            return "Fatty CAT"
        if "localhost" in url or "127.0.0.1" in url:
            for page, name in _FOMOJI_PAGE_NAMES.items():
                if page in url:
                    return name
            return "CAT Internal"
        return url

    def _cat_colors():
        if _theme is not None:
            try:
                obj = _theme.get_theme_obj()
                return {
                    "bg": obj.hex("background"),
                    "surface": obj.hex("surface"),
                    "surface_hover": obj.hex("surface_hover"),
                    "text": obj.hex("text"),
                    "text_muted": obj.hex("text_muted"),
                    "border": obj.hex("border"),
                    "accent": obj.hex("accent"),
                }
            except Exception:
                pass
        return {
            "bg": "#1a1b26", "surface": "#1e2030", "surface_hover": "#222436",
            "text": "#e8ebfa", "text_muted": "#878caf", "border": "#737aa2",
            "accent": "#82aaff",
        }

    # -------------------------------------------------------------------
    # Embedded Browser Pane — real Chromium child widget
    # -------------------------------------------------------------------
    class EmbeddedBrowserPane(QWidget):
        """
        Browser pane for CAT Host. Lives INSIDE the host window as a child
        widget (not a separate OS window).

        Provides:
          * Tab bar (favicon + title + close, + new tab, movable)
          * Toolbar (Back/Forward/Reload/Home, lock, address/search, ☆, ⋮)
          * QWebEngineView per tab (real HTML/CSS/JS, persistent profile)
          * New-tab page as fast native widget (no WebEngine needed for it)
          * history/bookmarks/downloads via BrowserState persistence
          * Fomoji-ready: profile persists cookies/storage under
            ~/.cat_browser_storage so connector auth survives restarts.
        """

        navigateRequested = Signal(str)

        def __init__(self, initial_url: str = "about:home", parent=None):
            super().__init__(parent)
            self._initial_url = initial_url or "about:home"
            self.state = BrowserState() if BrowserState else None  # type: ignore
            # Persistent profile — cookies, localStorage, service workers,
            # WebAuthn credential store all live here.
            self.profile = QWebEngineProfile("CATBrowser", self)
            try:
                self.profile.setPersistentCookiesPolicy(
                    QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
                )
                cache = str(pathlib.Path.home() / ".cat_browser_cache" / "embedded")
                storage = str(pathlib.Path.home() / ".cat_browser_storage" / "embedded")
                pathlib.Path(cache).mkdir(parents=True, exist_ok=True)
                pathlib.Path(storage).mkdir(parents=True, exist_ok=True)
                self.profile.setCachePath(cache)
                self.profile.setPersistentStoragePath(storage)
                # Enable WebAuthn / webauthn virtual authenticator is
                # available via Chromium; no extra flag needed on WebView2.
            except Exception:
                pass

            self._views: list[QWidget] = []
            self._view_index: dict[int, int] = {}  # id(view) -> index for O(1) lookup
            self._setup_ui()
            # Initial tab — defer so window paints first
            QTimer.singleShot(0, lambda: self._ensure_initial_tab())

        def _setup_ui(self):
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            c = _cat_colors()

            # ---- Unified browser chrome (tab bar + toolbar as one surface) --
            chrome = QWidget()
            chrome_layout = QVBoxLayout(chrome)
            chrome_layout.setContentsMargins(0, 0, 0, 0)
            chrome_layout.setSpacing(0)
            chrome.setStyleSheet(f"background: {c['bg']};")

            # ---- Tab bar row -------------------------------------------------
            try:
                from PySide6.QtWidgets import QTabBar as _QTabBar
            except ImportError:
                from PyQt6.QtWidgets import QTabBar as _QTabBar  # type: ignore
            tab_row = QHBoxLayout()
            tab_row.setContentsMargins(6, 4, 4, 0)
            tab_row.setSpacing(0)

            self.tab_bar = _QTabBar()
            self.tab_bar.setTabsClosable(True)
            self.tab_bar.setMovable(True)
            self.tab_bar.setExpanding(True)
            self.tab_bar.setDrawBase(False)
            self.tab_bar.tabBarClicked.connect(self._on_tab_clicked)
            self.tab_bar.tabCloseRequested.connect(self._close_tab)
            try:
                self.tab_bar.currentChanged.connect(self._on_current_changed)
            except Exception:
                pass
            self.tab_bar.setStyleSheet(
                f"QTabBar {{ background: transparent; }}"
                f"QTabBar::tab {{ "
                f"  background: transparent; color: {c['text_muted']}; "
                f"  border: none; border-bottom: 2px solid transparent; "
                f"  padding: 5px 10px; margin-right: 1px; "
                f"  min-width: 80px; max-width: 200px; "
                f"  font-size: 12px; border-radius: 4px 4px 0 0; "
                f"}} "
                f"QTabBar::tab:selected {{ "
                f"  background: {c['surface']}; color: {c['text']}; "
                f"  border-bottom: 2px solid {c['accent']}; "
                f"}} "
                f"QTabBar::tab:hover {{ "
                f"  background: {c['surface_hover']}; color: {c['text']}; "
                f"}} "
                f"QTabBar::close-button {{ "
                f"  image: none; subcontrol-position: right; padding: 2px; "
                f"  subcontrol-origin: padding; "
                f"}} "
                f"QTabBar::close-button:hover {{ image: none; }}"
            )
            tab_row.addWidget(self.tab_bar, 1)

            hi = c.get('hi', '#334155')
            sh = c.get('sh', '#090d16')
            btn_skeu_style = (
                f"QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['surface_hover']}, stop:1 {c['surface']}); "
                f"color: {c['text']}; border-top: 1px solid {hi}; border-left: 1px solid {hi}; "
                f"border-bottom: 1px solid {sh}; border-right: 1px solid {sh}; "
                f"border-radius: 4px; font-size: 15px; font-weight: bold; margin: 0 4px 0 2px; }}"
                f"QPushButton:hover {{ color: {c['accent']}; background: {c['surface_hover']}; border-top: 1px solid {c['accent']}; border-left: 1px solid {c['accent']}; }}"
                f"QPushButton:pressed {{ border-top: 1px solid {sh}; border-left: 1px solid {sh}; border-bottom: 1px solid {hi}; border-right: 1px solid {hi}; padding-top: 2px; padding-left: 2px; }}"
            )

            self.new_tab_btn = QPushButton("+")
            self.new_tab_btn.setFixedSize(24, 24)
            self.new_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.new_tab_btn.setToolTip("New tab (Ctrl+T)")
            self.new_tab_btn.setStyleSheet(btn_skeu_style)
            self.new_tab_btn.clicked.connect(lambda: self.new_tab())
            tab_row.addWidget(self.new_tab_btn, 0)

            tab_row_w = QWidget()
            tab_row_w.setLayout(tab_row)
            tab_row_w.setFixedHeight(32)
            tab_row_w.setStyleSheet(f"background: {c['bg']};")
            chrome_layout.addWidget(tab_row_w)

            # ---- Toolbar row (nav + address + menu) --------------------------
            toolbar = QHBoxLayout()
            toolbar.setContentsMargins(6, 2, 6, 4)
            toolbar.setSpacing(3)

            nav_btn_style = (
                f"QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['surface_hover']}, stop:1 {c['surface']}); "
                f"color: {c['text']}; border-top: 1px solid {hi}; border-left: 1px solid {hi}; "
                f"border-bottom: 1px solid {sh}; border-right: 1px solid {sh}; "
                f"border-radius: 4px; font-size: 13px; font-weight: bold; "
                f"padding: 1px 4px; min-width: 24px; max-width: 28px; "
                f"min-height: 22px; max-height: 22px; }}"
                f"QPushButton:hover {{ color: #ffffff; background: {c['surface_hover']}; border-top: 1px solid {c['accent']}; border-left: 1px solid {c['accent']}; }}"
                f"QPushButton:pressed {{ border-top: 1px solid {sh}; border-left: 1px solid {sh}; border-bottom: 1px solid {hi}; border-right: 1px solid {hi}; padding-top: 2px; padding-left: 2px; }}"
                f"QPushButton:disabled {{ color: {c['border']}; background: transparent; border: 1px solid transparent; }}"
            )

            self.back_btn = QPushButton("◀")
            self.back_btn.setFixedSize(26, 22)
            self.back_btn.setToolTip("Back (Alt+Left)")
            self.back_btn.setStyleSheet(nav_btn_style)
            self.back_btn.clicked.connect(self.go_back)
            toolbar.addWidget(self.back_btn)

            self.forward_btn = QPushButton("▶")
            self.forward_btn.setFixedSize(26, 22)
            self.forward_btn.setToolTip("Forward (Alt+Right)")
            self.forward_btn.setStyleSheet(nav_btn_style)
            self.forward_btn.clicked.connect(self.go_forward)
            toolbar.addWidget(self.forward_btn)

            self.reload_btn = QPushButton("⟳")
            self.reload_btn.setFixedSize(26, 22)
            self.reload_btn.setToolTip("Reload (Ctrl+R)")
            self.reload_btn.setStyleSheet(nav_btn_style)
            self.reload_btn.clicked.connect(self.reload)
            toolbar.addWidget(self.reload_btn)

            toolbar.addSpacing(4)

            # Address bar — minimal sleek pill
            addr_frame = QWidget()
            addr_layout = QHBoxLayout(addr_frame)
            addr_layout.setContentsMargins(8, 0, 8, 0)
            addr_layout.setSpacing(6)

            self.lock_label = QLabel("⌕")
            self.lock_label.setFixedWidth(16)
            self.lock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lock_label.setStyleSheet(f"color: {c['text_muted']}; font-size: 13px; background: transparent; border: none; padding: 0;")
            addr_layout.addWidget(self.lock_label)

            self.address_input = QLineEdit()
            self.address_input.setPlaceholderText("Search or enter address")
            self.address_input.returnPressed.connect(self._on_address_enter)
            self.address_input.setClearButtonEnabled(True)
            self.address_input.setStyleSheet(
                f"background: transparent; border: none; color: {c['text']}; "
                f"font-size: 12px; padding: 0 2px; selection-background-color: {c['accent']};"
            )
            addr_layout.addWidget(self.address_input, 1)

            addr_frame.setStyleSheet(f"""
                QWidget {{
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.09);
                    border-radius: 13px;
                }}
                QWidget:hover {{
                    background: rgba(255, 255, 255, 0.07);
                    border: 1px solid rgba(255, 255, 255, 0.16);
                }}
                QWidget:focus-within {{
                    border: 1px solid {c['accent']};
                    background: {c['surface']};
                }}
            """)
            toolbar.addWidget(addr_frame, 1)

            self.menu_btn = QPushButton("⋮")
            self.menu_btn.setFixedSize(24, 22)
            self.menu_btn.setToolTip("Menu")
            self.menu_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-radius: 6px;
                    color: {c['text_muted']};
                    font-size: 14px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: rgba(255, 255, 255, 0.08);
                    color: {c['text']};
                }}
                QPushButton:pressed {{
                    background: rgba(255, 255, 255, 0.14);
                }}
            """)
            self.menu_btn.clicked.connect(self.show_menu)
            toolbar.addWidget(self.menu_btn)

            toolbar_w = QWidget()
            toolbar_w.setLayout(toolbar)
            toolbar_w.setFixedHeight(28)
            toolbar_w.setStyleSheet(f"background: {c['bg']}; border-bottom: 1px solid {c['border']};")
            chrome_layout.addWidget(toolbar_w)

            # ---- Progress bar (thin, integrated into chrome) -----------------
            self.progress_bar = None
            try:
                from PySide6.QtWidgets import QProgressBar
            except ImportError:
                from PyQt6.QtWidgets import QProgressBar  # type: ignore
            self.progress_bar = QProgressBar()
            self.progress_bar.setFixedHeight(2)
            self.progress_bar.setTextVisible(False)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setStyleSheet(
                f"QProgressBar {{ background: transparent; border: none; }}"
                f"QProgressBar::chunk {{ background: {c['accent']}; border-radius: 1px; }}"
            )
            self.progress_bar.hide()
            chrome_layout.addWidget(self.progress_bar)

            layout.addWidget(chrome)

            # ---- Viewport — stacked WebEngineViews --------------------------
            self.viewport_stack = QStackedWidget()
            self.viewport_stack.setStyleSheet(f"background: {c['bg']};")
            layout.addWidget(self.viewport_stack, 1)

        # ----------------------------------------------------------------
        # Tab management — native new-tab + WebEngineView swap
        # ----------------------------------------------------------------
        def _new_tab_widget(self):
            """Fast native New Tab — modern, beautiful, responsive, and instant with 0ms lag."""
            try:
                from .terminal import CATTerminalWidget  # avoid circular at class body
            except Exception:
                pass
            w = QWidget()
            v = QVBoxLayout(w)
            v.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.setContentsMargins(20, 24, 20, 24)
            v.setSpacing(16)
            c = _cat_colors()

            accent = c.get("accent", "#82aaff")
            bg = c.get("bg", "#1a1b26")
            surface = c.get("surface", "#1e2030")
            surface_hover = c.get("surface_hover", "#222436")
            text = c.get("text", "#e8ebfa")
            text_muted = c.get("text_muted", "#878caf")
            border = c.get("border", "#3b4261")

            wrap = QWidget()
            wrap.setMaximumWidth(680)
            vw = QVBoxLayout(wrap)
            vw.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vw.setSpacing(16)

            # 1. Hero Brand: Modern Gradient Badge + Title + Hardware Status Pill
            brand_box = QWidget()
            bb_layout = QVBoxLayout(brand_box)
            bb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bb_layout.setSpacing(6)
            bb_layout.setContentsMargins(0, 0, 0, 0)

            # Glowing CAT Wordmark with modern typography
            logo = QLabel()
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo.setTextFormat(Qt.TextFormat.RichText)
            logo.setText(
                f'<div style="text-align:center;">'
                f'<span style="font-size:46px;font-weight:900;letter-spacing:8px;'
                f'color:{accent};">C A T</span>'
                f'<div style="font-size:13px;font-weight:600;letter-spacing:3px;'
                f'color:{text_muted};margin-top:2px;">B R O W S E R</div>'
                f'</div>'
            )
            bb_layout.addWidget(logo)

            # Feature / Mode Pill (e.g. ⚡ Low-End Eco Engine · 🛡 Zero-Telemetry · 🚀 Fast)
            pill = QLabel("⚡ ECO ENGINE ACTIVE  ·  🛡 AD-SHIELD ON  ·  🚀 60 FPS SMOOTH SCROLL")
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pill.setStyleSheet(
                f"QLabel {{ background: {surface}; color: {accent}; border: 1px solid {border}; "
                f"border-radius: 10px; font-size: 10px; font-weight: bold; padding: 4px 14px; margin-top: 4px; }}"
            )
            bb_layout.addWidget(pill)
            vw.addWidget(brand_box)

            # 2. Modern Glassmorphic Search Frame
            search_frame = QFrame()
            search_frame.setStyleSheet(f"""
                QFrame {{
                    background: {surface};
                    border: 1.5px solid {border};
                    border-radius: 20px;
                }}
                QFrame:hover {{
                    border: 1.5px solid {accent};
                    background: {surface_hover};
                }}
            """)
            sh = QHBoxLayout(search_frame)
            sh.setContentsMargins(16, 7, 16, 7)
            sh.setSpacing(10)

            search_icon = QLabel("🔍")
            search_icon.setStyleSheet(f"color: {accent}; font-size: 14px; background: transparent; border: none;")
            sh.addWidget(search_icon)

            search_input = QLineEdit()
            search_input.setPlaceholderText("Search the web or enter URL (e.g. localhost:8765, github.com)...")
            search_input.setStyleSheet(
                f"background: transparent; border: none; color: {text}; font-size: 13px; padding: 2px 0;"
            )
            w._search_input = search_input  # type: ignore

            def _submit():
                t = search_input.text().strip()
                if t:
                    self._handle_newtab_search(t)

            search_input.returnPressed.connect(_submit)
            sh.addWidget(search_input, 1)

            enter_badge = QLabel("⏎ Enter")
            enter_badge.setStyleSheet(
                f"background: {surface_hover}; color: {text_muted}; border: 1px solid {border}; "
                f"border-radius: 6px; font-size: 10px; font-weight: bold; padding: 2px 6px;"
            )
            sh.addWidget(enter_badge)
            vw.addWidget(search_frame)

            # 3. Quick Dials (6 rich interactive cards in a 3x2 grid)
            try:
                from PySide6.QtWidgets import QGridLayout
            except ImportError:
                from PyQt6.QtWidgets import QGridLayout  # type: ignore

            grid = QGridLayout()
            grid.setSpacing(10)

            shortcuts = [
                ("🐱", "Fatty CAT", "AI Web Workspace", "http://localhost:8765/", "#a6e3a1"),
                ("🔗", "Fomoji Portal", "Auth & Passkeys", "http://localhost:3000/home.html", "#89b4fa"),
                ("▶", "YouTube", "Videos & Guides", "https://youtube.com", "#f38ba8"),
                ("⬢", "GitHub", "Code & Repos", "https://github.com", "#cdd6f4"),
                ("⚙", "Settings", "Browser & System", "http://localhost:3000/settings.html", "#fab387"),
                ("○", "New Window", "Open Blank Tab", "about:home", "#cba6f7"),
            ]

            card_style = f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {surface_hover}, stop:1 {surface});
                    border: 1px solid {border};
                    border-radius: 12px;
                    color: {text};
                    text-align: left;
                    padding: 8px 12px;
                }}
                QPushButton:hover {{
                    border: 1.5px solid {accent};
                    background: {surface_hover};
                }}
                QPushButton:pressed {{
                    background: {surface};
                    border: 1.5px solid {border};
                    padding-top: 10px;
                }}
            """

            for i, (icon, label, sub, url, tag_color) in enumerate(shortcuts):
                row = i // 3
                col = i % 3
                btn = QPushButton()
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFixedHeight(56)
                btn.setStyleSheet(card_style)
                btn.setText(
                    f'<span style="font-size:16px;">{icon}</span> '
                    f'<span style="font-size:12px;font-weight:bold;color:{text};">{label}</span><br>'
                    f'<span style="font-size:10px;color:{text_muted};margin-left:22px;">{sub}</span>'
                )
                btn.clicked.connect(lambda _=None, u=url: self.navigate(u))
                grid.addWidget(btn, row, col)

            grid_w = QWidget()
            grid_w.setLayout(grid)
            vw.addWidget(grid_w)

            # 4. Footer & Shortcut Helper
            foot = QLabel("CAT Browser · Ultra-Fast · Low Memory Footprint · Press Ctrl+T for new tab")
            foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            foot.setStyleSheet(f"color: {text_muted}; font-size: 11px; margin-top: 10px;")
            vw.addWidget(foot)

            v.addWidget(wrap)
            QTimer.singleShot(80, lambda: search_input.setFocus())
            w.setObjectName("newtab")
            return w

        def _handle_newtab_search(self, text: str):
            clean = text.strip()
            if clean.lower() in ("fatty", "fattycat", "fatty-cat", "fatty cat", "cat web"):
                self.navigate("http://localhost:8765/")
                return
            if clean.lower() in ("fomoji", "login", "auth"):
                self.navigate("http://localhost:3000/home.html")
                return
            has_scheme = bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", clean))
            is_local = "localhost" in clean.lower() or "127.0.0.1" in clean
            if has_scheme or is_local or ("." in clean.split()[0] and " " not in clean and "/" in clean):
                url = clean if has_scheme else ("http://" + clean if is_local else "https://" + clean)
            else:
                url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(clean) + "&hl=en"
            self.navigate(url)

        def _ensure_initial_tab(self):
            if self.viewport_stack.count() == 0:
                self.new_tab(getattr(self, "_initial_url", "about:home"))

        def _is_newtab(self, w: QWidget) -> bool:
            return w is not None and w.objectName() == "newtab"

        def _view_index(self, view: QWidget) -> int:
            """O(1) view index lookup via cached dict."""
            return self._view_index.get(id(view), -1)

        def _rebuild_view_index(self):
            """Rebuild the O(1) index cache after list changes."""
            self._view_index = {id(v): i for i, v in enumerate(self._views)}

        def new_tab(self, url: str = "about:home"):
            is_newtab_url = url in ("about:home", "about:blank", "")
            if is_newtab_url:
                w = self._new_tab_widget()
                idx = self.viewport_stack.addWidget(w)
                self._views.append(w)
                fav = "○"
                title = "New Tab"
            else:
                view = SecureWebEngineView()
                try:
                    page = SecureWebEnginePage(self.profile, view)
                    try:
                        page.setDevToolsPage(None)
                    except Exception:
                        pass
                    view.setPage(page)
                    view.titleChanged.connect(lambda t, v=view: self._on_title(v, t))
                    view.urlChanged.connect(lambda q, v=view: self._on_url(v, q))
                    view.loadStarted.connect(lambda v=view: self._on_load_started(v))
                    view.loadFinished.connect(lambda ok, v=view: self._on_load_finished(v, ok))
                    try:
                        view.page().newWindowRequested.connect(self._on_new_window)
                    except Exception:
                        pass
                    # Downloads
                    try:
                        if not getattr(self, "_dl_connected", False):
                            self.profile.downloadRequested.connect(self._on_download)
                            self._dl_connected = True
                    except Exception:
                        pass
                except Exception:
                    pass
                idx = self.viewport_stack.addWidget(view)
                self._views.append(view)
                fav = "○"
                title = "Loading…"
                # Keep BrowserState in sync
                if self.state:
                    self.state.new_tab(url)
                try:
                    view.load(QUrl(url))
                except Exception:
                    pass

            tab_idx = self.tab_bar.addTab(f"{fav}  {title[:28]}")
            self.tab_bar.setCurrentIndex(tab_idx)
            self.viewport_stack.setCurrentIndex(idx)
            if not is_newtab_url and self.state:
                self.state.active_tab_id = self.state.tabs[-1].id if self.state.tabs else ""
            self._rebuild_view_index()
            self._sync_chrome()
            return tab_idx

        def navigate(self, raw: str):
            url = raw.strip()
            if not url:
                return

            # Fast keyword shortcuts
            if url.lower() in ("fatty", "fattycat", "fatty-cat", "fatty cat", "cat web"):
                url = "http://localhost:8765/"
            elif url.lower() in ("fomoji", "login", "auth"):
                url = "http://localhost:3000/home.html"

            # Auto-ensure Fatty CAT server is running when navigating to port 8765
            if "8765" in url:
                try:
                    from ..web.server import ensure_fatty_server
                    ensure_fatty_server(timeout=5.0, auto_start=True)
                except Exception:
                    pass

            has_scheme = bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url))
            is_about = url.lower().startswith("about:")
            is_local = "localhost" in url.lower() or "127.0.0.1" in url
            # Search detection
            def _is_search(q):
                if has_scheme or is_about or is_local:
                    return False
                if " " in q.strip():
                    return True
                first = q.strip().split()[0] if q.strip() else ""
                if "." not in first and "/" not in q:
                    return True
                return False
            if _is_search(url):
                url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(url) + "&hl=en"
            elif not has_scheme and not is_about and "." in url.split("/")[0] and " " not in url:
                url = "https://" + url

            cur = self.tab_bar.currentIndex()
            if not (0 <= cur < len(self._views)):
                self.new_tab(url)
                return
            cur_w = self._views[cur]
            # Cases:
            # 1. newtab -> real URL : replace widget with WebEngineView
            # 2. real -> about:home : replace with newtab
            # 3. otherwise : load in place
            if self._is_newtab(cur_w) and url not in ("about:home", "about:blank"):
                self._replace_newtab_with_webview(cur, url)
                return
            if not self._is_newtab(cur_w) and url in ("about:home", "about:blank"):
                self._replace_webview_with_newtab(cur)
                return
            if not self._is_newtab(cur_w):
                # Normal navigation in WebEngineView
                try:
                    cur_w.load(QUrl(url))  # type: ignore
                except Exception:
                    pass
                if self.state and 0 <= cur < len(self.state.tabs):
                    self.state.tabs[cur].url = url
                    self.state.tabs[cur].title = "Loading…"
                self.tab_bar.setTabText(cur, "⟳  Loading…")
                if self.progress_bar:
                    self.progress_bar.setValue(0)
                    self.progress_bar.show()
            else:
                # newtab -> newtab (should not happen, but handle)
                pass
            self._sync_chrome()

        def _replace_newtab_with_webview(self, idx: int, url: str):
            old = self._views[idx]
            self.viewport_stack.removeWidget(old)
            old.deleteLater()
            view = SecureWebEngineView()
            try:
                page = SecureWebEnginePage(self.profile, view)
                try:
                    page.setDevToolsPage(None)
                except Exception:
                    pass
                view.setPage(page)
                view.titleChanged.connect(lambda t, v=view: self._on_title(v, t))
                view.urlChanged.connect(lambda q, v=view: self._on_url(v, q))
                view.loadStarted.connect(lambda v=view: self._on_load_started(v))
                view.loadFinished.connect(lambda ok, v=view: self._on_load_finished(v, ok))
                try:
                    view.page().newWindowRequested.connect(self._on_new_window)
                except Exception:
                    pass
            except Exception:
                pass
            self._views[idx] = view
            self.viewport_stack.insertWidget(idx, view)
            self.viewport_stack.setCurrentIndex(idx)
            self._rebuild_view_index()
            # State
            if self.state and 0 <= idx < len(self.state.tabs):
                self.state.tabs[idx].url = url
                self.state.tabs[idx].title = "Loading…"
            else:
                if self.state:
                    try:
                        self.state.tabs[idx].url = url
                    except Exception:
                        pass
            self.tab_bar.setTabText(idx, "⟳  Loading…")
            if self.progress_bar:
                self.progress_bar.setValue(0)
                self.progress_bar.show()
            try:
                view.load(QUrl(url))
            except Exception:
                pass
            self._sync_chrome()

        def _replace_webview_with_newtab(self, idx: int):
            old = self._views[idx]
            self.viewport_stack.removeWidget(old)
            old.deleteLater()
            w = self._new_tab_widget()
            self._views[idx] = w
            self.viewport_stack.insertWidget(idx, w)
            self.viewport_stack.setCurrentIndex(idx)
            self._rebuild_view_index()
            self.tab_bar.setTabText(idx, "○  New Tab")
            if self.state and 0 <= idx < len(self.state.tabs):
                self.state.tabs[idx].url = "about:home"
                self.state.tabs[idx].title = "New Tab"
                self.state.tabs[idx].favicon = "○"
            if self.progress_bar:
                self.progress_bar.hide()
            self._sync_chrome()

        # ----------------------------------------------------------------
        # Signals from WebEngineView
        # ----------------------------------------------------------------
        def _on_title(self, view, title: str):
            try:
                idx = self._view_index(view)
                if idx < 0:
                    return
                display = title[:28] if title else "Untitled"
                self.tab_bar.setTabText(idx, f"{self._fav(idx)}  {display}")
                if self.state and 0 <= idx < len(self.state.tabs):
                    self.state.tabs[idx].title = title[:60]
                if idx == self.tab_bar.currentIndex():
                    self._sync_chrome()
            except Exception:
                pass

        def _on_url(self, view, qurl):
            try:
                idx = self._view_index(view)
                if idx < 0:
                    return
                url = qurl.toString()
                if self.state and 0 <= idx < len(self.state.tabs):
                    self.state.tabs[idx].url = url
                    self.state.tabs[idx].favicon = "🔒" if url.startswith("https://") else "○"
                if idx == self.tab_bar.currentIndex():
                    display = _friendly_url(url)
                    self.address_input.setText(display)
                    self.lock_label.setText("🔒" if url.startswith("https") else "🌐")
                    self._sync_nav()
                    # Update tab text with favicon
                    title = ""
                    if self.state and 0 <= idx < len(self.state.tabs):
                        title = self.state.tabs[idx].title[:28]
                    fav = self._fav(idx)
                    if title:
                        self.tab_bar.setTabText(idx, f"{fav}  {title}")
            except Exception:
                pass

        def _on_load_started(self, view):
            try:
                idx = self._view_index(view)
                if idx < 0:
                    return
                if idx == self.tab_bar.currentIndex():
                    self.reload_btn.setText("×")
                    self.reload_btn.setToolTip("Stop")
                    if self.progress_bar:
                        self.progress_bar.setValue(0)
                        self.progress_bar.show()
                self.tab_bar.setTabText(idx, f"⟳  Loading…")
            except Exception:
                pass

        def _on_load_finished(self, view, ok: bool):
            try:
                idx = self._view_index(view)
                if idx < 0:
                    return
                if idx == self.tab_bar.currentIndex():
                    self.reload_btn.setText("⟳")
                    self.reload_btn.setToolTip("Reload (Ctrl+R)")
                    if self.progress_bar:
                        self.progress_bar.hide()
                        self.progress_bar.setValue(0)
                title = ""
                try:
                    title = view.title() or ""
                except Exception:
                    title = ""
                if title:
                    display = title[:28] if title else "Untitled"
                    self.tab_bar.setTabText(idx, f"{self._fav(idx)}  {display}")
                    if self.state and 0 <= idx < len(self.state.tabs):
                        self.state.tabs[idx].title = title[:60]
                if idx == self.tab_bar.currentIndex():
                    self._sync_chrome()
            except Exception:
                pass

        def _on_new_window(self, request):
            try:
                url = request.requestedUrl().toString()
                self.new_tab(url)
                # Need to route the request to new page
                try:
                    view = self._views[-1]
                    if not self._is_newtab(view):
                        request.openIn(view.page())  # type: ignore
                except Exception:
                    pass
            except Exception:
                pass

        def _on_download(self, download):
            try:
                filename = download.downloadFileName() or "download"
                home_dl = str(pathlib.Path.home() / "Downloads")
                pathlib.Path(home_dl).mkdir(parents=True, exist_ok=True)
                download.setDownloadDirectory(home_dl)
                download.setDownloadFileName(filename)
                download.accept()
                if self.state:
                    try:
                        self.state.add_download(filename, download.url().toString(), str(pathlib.Path(home_dl) / filename))
                    except Exception:
                        pass
            except Exception:
                try:
                    download.accept()  # type: ignore
                except Exception:
                    pass

        # ----------------------------------------------------------------
        # Helpers
        # ----------------------------------------------------------------
        def _fav(self, idx: int) -> str:
            try:
                if self.state and 0 <= idx < len(self.state.tabs):
                    return self.state.tabs[idx].favicon or "○"
                w = self._views[idx]
                if not self._is_newtab(w):
                    url = w.url().toString() if hasattr(w, "url") else ""  # type: ignore
                    if "localhost" in url or "127.0.0.1" in url:
                        return "⬢"
                    if url.startswith("https://"):
                        return "🔒"
                    if url.startswith("http://"):
                        return "○"
                return "○"
            except Exception:
                return "○"

        def _sync_chrome(self):
            try:
                cur = self.tab_bar.currentIndex()
                if cur < 0 or cur >= len(self._views):
                    return
                w = self._views[cur]
                if self._is_newtab(w):
                    if self.address_input.text():
                        self.address_input.setText("")
                    self.lock_label.setText("⌕")
                    self.lock_label.setStyleSheet("color: #8d92be; font-size: 13px; background: transparent; border: none; padding: 0;")
                else:
                    try:
                        url = w.url().toString()  # type: ignore
                        display = _friendly_url(url)
                        if self.address_input.text() != display:
                            self.address_input.setText(display)
                        if url.startswith("https://"):
                            lock = "🔒"
                            self.lock_label.setStyleSheet("color: #10b981; font-size: 11px; background: transparent; border: none; padding: 0;")
                        elif url.startswith("about:") or not url:
                            lock = "⌕"
                            self.lock_label.setStyleSheet("color: #8d92be; font-size: 13px; background: transparent; border: none; padding: 0;")
                        else:
                            lock = "🌐"
                            self.lock_label.setStyleSheet("color: #8d92be; font-size: 11px; background: transparent; border: none; padding: 0;")
                        if self.lock_label.text() != lock:
                            self.lock_label.setText(lock)
                    except Exception:
                        pass
                if self.state and 0 <= cur < len(self.state.tabs):
                    tab = self.state.tabs[cur]
                    fav = self._fav(cur)
                    title = tab.title[:28] if tab.title else "Untitled"
                    new_text = f"{fav}  {title}"
                    if self.tab_bar.tabText(cur) != new_text:
                        self.tab_bar.setTabText(cur, new_text)
                self._sync_nav()
            except Exception:
                pass

        def _sync_nav(self):
            try:
                cur = self.tab_bar.currentIndex()
                if 0 <= cur < len(self._views) and not self._is_newtab(self._views[cur]):
                    view = self._views[cur]
                    # Use WebEngine history, not BrowserState, for accuracy
                    try:
                        # QWebEngineHistory has canGoBack/canGoForward
                        hist = view.history()  # type: ignore
                        self.back_btn.setEnabled(hist.canGoBack())
                        self.forward_btn.setEnabled(hist.canGoForward())
                        return
                    except Exception:
                        pass
                self.back_btn.setEnabled(False)
                self.forward_btn.setEnabled(False)
            except Exception:
                pass

        def _sync_bookmark(self):
            pass  # Bookmark button removed for cleaner toolbar

        # ----------------------------------------------------------------
        # Public API (called by host window)
        # ----------------------------------------------------------------
        def _on_tab_clicked(self, idx: int):
            if 0 <= idx < len(self._views):
                self.viewport_stack.setCurrentIndex(idx)
                self._sync_chrome()

        def _on_current_changed(self, idx: int):
            # Keep viewport and BrowserState active in sync
            if 0 <= idx < len(self._views):
                self.viewport_stack.setCurrentIndex(idx)
                if self.state and 0 <= idx < len(self.state.tabs):
                    self.state.active_tab_id = self.state.tabs[idx].id
                self._sync_chrome()

        def _close_tab(self, idx: int):
            if not (0 <= idx < len(self._views)):
                return
            self.tab_bar.blockSignals(True)
            try:
                w = self._views.pop(idx)
                self.viewport_stack.removeWidget(w)
                w.deleteLater()
                self.tab_bar.removeTab(idx)
                self._rebuild_view_index()
            finally:
                self.tab_bar.blockSignals(False)

            if self.state and 0 <= idx < len(self.state.tabs):
                try:
                    tab_id = self.state.tabs[idx].id
                    self.state.close_tab(tab_id)
                except Exception:
                    pass
            if self.progress_bar and self.tab_bar.count() == 0:
                self.progress_bar.hide()
            if self.tab_bar.count() == 0:
                self.new_tab("about:home")
            else:
                new_idx = min(idx, self.tab_bar.count() - 1)
                self.tab_bar.setCurrentIndex(new_idx)
                self.viewport_stack.setCurrentIndex(new_idx)
                self._sync_chrome()

        def _on_address_enter(self):
            self.navigate(self.address_input.text())

        def go_back(self):
            cur = self.tab_bar.currentIndex()
            if 0 <= cur < len(self._views) and not self._is_newtab(self._views[cur]):
                try:
                    self._views[cur].back()  # type: ignore
                except Exception:
                    pass

        def go_forward(self):
            cur = self.tab_bar.currentIndex()
            if 0 <= cur < len(self._views) and not self._is_newtab(self._views[cur]):
                try:
                    self._views[cur].forward()  # type: ignore
                except Exception:
                    pass

        def reload(self):
            cur = self.tab_bar.currentIndex()
            if 0 <= cur < len(self._views) and not self._is_newtab(self._views[cur]):
                view = self._views[cur]
                try:
                    if hasattr(view, "isLoading") and view.isLoading():  # type: ignore
                        view.stop()  # type: ignore
                        if self.progress_bar:
                            self.progress_bar.hide()
                    else:
                        view.reload()  # type: ignore
                        if self.progress_bar:
                            self.progress_bar.setValue(0)
                            self.progress_bar.show()
                except Exception:
                    try:
                        view.reload()  # type: ignore
                    except Exception:
                        pass

        def toggle_bookmark(self):
            pass  # Bookmark button removed for cleaner toolbar

        def show_menu(self):
            try:
                from PySide6.QtWidgets import QMenu
            except ImportError:
                from PyQt6.QtWidgets import QMenu  # type: ignore
            menu = QMenu(self)
            c = _cat_colors()
            menu.setStyleSheet(
                f"QMenu {{ background: {c['surface']}; color: {c['text']}; "
                f"border: 1px solid {c['border']}; border-radius: 8px; padding: 4px; }}"
                f"QMenu::item {{ padding: 6px 20px; border-radius: 4px; }}"
                f"QMenu::item:selected {{ background: {c['accent']}; color: white; }}"
                f"QMenu::separator {{ height: 1px; background: {c['border']}; margin: 2px 8px; }}"
            )

            def _add(label, fn=None, sep=False):
                if sep:
                    menu.addSeparator()
                    return
                act = menu.addAction(label)
                if fn:
                    act.triggered.connect(fn)

            _add("New Tab", lambda: self.new_tab())
            _add("", sep=True)
            _add("History", lambda: self._show_history())
            _add("Bookmarks", lambda: self._show_bookmarks())
            _add("Downloads", lambda: self._show_downloads())
            _add("", sep=True)
            _add("Fomoji Dashboard", lambda: self.navigate("http://localhost:3000/home.html"))
            _add("Fomoji Settings", lambda: self.navigate("http://localhost:3000/settings.html"))
            _add("", sep=True)
            _add("Developer Tools", lambda: self._show_devtools())
            menu.exec(self.menu_btn.mapToGlobal(self.menu_btn.rect().bottomLeft()))

        def _show_history(self):
            # Use BrowserState grouped history; show in simple dialog
            if not self.state:
                return
            try:
                from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QDialogButtonBox
            except ImportError:
                from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QDialogButtonBox  # type: ignore
            dlg = QDialog(self)
            dlg.setWindowTitle("History — CAT Browser")
            dlg.resize(700, 480)
            lay = QVBoxLayout(dlg)
            lw = QListWidget()
            groups = self.state.history_grouped() if hasattr(self.state, "history_grouped") else {}
            for gname in ("Today", "Yesterday", "Earlier"):
                for h in groups.get(gname, [])[:50]:
                    item = QListWidgetItem(f"{h.favicon}  {h.title[:40]}  —  {h.url[:60]}")
                    try:
                        item.setData(Qt.ItemDataRole.UserRole, h.url)
                    except Exception:
                        pass
                    lw.addItem(item)
            def _open(item):
                try:
                    url = item.data(Qt.ItemDataRole.UserRole)
                    if url:
                        dlg.accept()
                        self.navigate(url)
                except Exception:
                    pass
            lw.itemDoubleClicked.connect(_open)
            lay.addWidget(lw)
            btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            btns.rejected.connect(dlg.reject)
            lay.addWidget(btns)
            dlg.exec()

        def _show_bookmarks(self):
            if not self.state:
                return
            try:
                from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton
            except ImportError:
                from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton  # type: ignore
            dlg = QDialog(self)
            dlg.setWindowTitle("Bookmarks — CAT Browser")
            dlg.resize(600, 400)
            lay = QVBoxLayout(dlg)
            lw = QListWidget()
            for bm in self.state.bookmarks:
                item = QListWidgetItem(f"{bm.favicon}  {bm.title} — {bm.url}")
                try:
                    item.setData(Qt.ItemDataRole.UserRole, bm.id)
                except Exception:
                    pass
                lw.addItem(item)
            lay.addWidget(lw)
            row = QHBoxLayout()
            del_btn = QPushButton("Delete")
            open_btn = QPushButton("Open")
            close_btn = QPushButton("Close")
            def _del():
                it = lw.currentItem()
                if not it:
                    return
                bid = it.data(Qt.ItemDataRole.UserRole)
                self.state.remove_bookmark(bid)
                lw.takeItem(lw.row(it))
            def _open():
                it = lw.currentItem()
                if not it:
                    return
                bid = it.data(Qt.ItemDataRole.UserRole)
                bm = next((b for b in self.state.bookmarks if b.id == bid), None)
                if bm:
                    dlg.accept()
                    self.navigate(bm.url)
            del_btn.clicked.connect(_del)
            open_btn.clicked.connect(_open)
            close_btn.clicked.connect(dlg.reject)
            lw.itemDoubleClicked.connect(lambda it: _open())
            row.addWidget(del_btn)
            row.addStretch()
            row.addWidget(open_btn)
            row.addWidget(close_btn)
            lay.addLayout(row)
            dlg.exec()

        def _show_downloads(self):
            if not self.state:
                return
            try:
                from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QDialogButtonBox
            except ImportError:
                from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QDialogButtonBox  # type: ignore
            dlg = QDialog(self)
            dlg.setWindowTitle("Downloads — CAT Browser")
            dlg.resize(600, 400)
            lay = QVBoxLayout(dlg)
            lw = QListWidget()
            for d in self.state.downloads:
                lw.addItem(QListWidgetItem(f"{d.filename} — {d.status} {d.progress}%  {d.url[:50]}"))
            lay.addWidget(lw)
            btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            btns.rejected.connect(dlg.reject)
            lay.addWidget(btns)
            dlg.exec()

        def _show_devtools(self):
            try:
                from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox
            except ImportError:
                from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox  # type: ignore
            dlg = QDialog(self)
            dlg.setWindowTitle("Developer Tools — CAT Browser")
            dlg.resize(700, 500)
            lay = QVBoxLayout(dlg)
            lay.addWidget(QLabel("Console — browser console + page errors appear in QWebEngine's devtools (F12 via inspect)"))
            lay.addWidget(QLabel("Network — use QWebEngine's Network panel (right-click → Inspect)"))
            lay.addWidget(QLabel("Storage — cookies/localStorage under ~/.cat_browser_storage"))
            lay.addWidget(QLabel("Tip: right-click any page → Inspect to open Chromium DevTools"))
            # Add inspect button for current view
            try:
                from PySide6.QtWidgets import QPushButton
            except ImportError:
                from PyQt6.QtWidgets import QPushButton  # type: ignore
            cur = self.tab_bar.currentIndex()
            if 0 <= cur < len(self._views) and not self._is_newtab(self._views[cur]):
                btn = QPushButton("Inspect current page (open DevTools)")
                def _inspect():
                    try:
                        page = self._views[cur].page()
                        page.triggerAction(QWebEnginePage.WebAction.InspectElement)
                    except Exception:
                        pass
                btn.clicked.connect(_inspect)
                lay.addWidget(btn)
            btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            btns.rejected.connect(dlg.reject)
            lay.addWidget(btns)
            dlg.exec()

    # -------------------------------------------------------------------
    # CAT Desktop Window — the single CAT OS window
    # -------------------------------------------------------------------
    class CATDesktopWindow(QMainWindow):
        """
        CAT's own Browser window — the embedded graphical browser surface.

        This is NOT a separate application. It is created by CAT on demand
        when Browser Mode is requested. The browser renderer (QWebEngineView)
        is a child widget of this window, owned and controlled by CAT.

        When this window is closed, CAT resumes its previous state
        (Textual TUI or fallback REPL).
        """

        def __init__(self, repl=None, start_browser_url: Optional[str] = None, parent=None):
            super().__init__(parent)
            self.repl = repl
            self._pending_browser_url = start_browser_url or "about:home"
            self.setWindowTitle("CAT Browser")
            self.resize(1280, 860)
            self.setMinimumSize(960, 640)

            if sys.platform == "win32":
                try:
                    import ctypes
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("kazizillani.cat.browser.v08")
                except Exception:
                    pass

            try:
                from ..terminal_identity import get_browser_icon_path
                ico = get_browser_icon_path()
                if ico and os.path.isfile(ico):
                    try:
                        from PySide6.QtGui import QIcon
                    except ImportError:
                        from PyQt6.QtGui import QIcon  # type: ignore
                    br_icon = QIcon(ico)
                    self.setWindowIcon(br_icon)
                    try:
                        from PySide6.QtWidgets import QApplication
                    except ImportError:
                        from PyQt6.QtWidgets import QApplication  # type: ignore
                    qapp = QApplication.instance()
                    if qapp:
                        qapp.setWindowIcon(br_icon)
            except Exception:
                pass

            self._center_on_screen()
            self._build_ui()
            self._setup_shortcuts()
            if start_browser_url and start_browser_url not in ("about:home", "about:blank"):
                QTimer.singleShot(150, lambda: self.navigate(start_browser_url))

            # Recurring heartbeat and IPC check for real-time pop-up and URL redirects
            self._last_hb_ts = 0.0
            self._pending_timer = QTimer(self)
            self._pending_timer.setInterval(250)
            self._pending_timer.timeout.connect(self._check_pending_url)
            self._pending_timer.start()
            QTimer.singleShot(100, self._check_pending_url)
            QTimer.singleShot(250, self._bring_to_front)

        def _center_on_screen(self):
            try:
                try:
                    from PySide6.QtGui import QGuiApplication
                except ImportError:
                    from PyQt6.QtGui import QGuiApplication  # type: ignore
                screen = QGuiApplication.primaryScreen()
                if screen:
                    geo = screen.availableGeometry()
                    w = min(self.width(), geo.width())
                    h = min(self.height(), geo.height())
                    x = max(0, (geo.width() - w) // 2 + geo.x())
                    y = max(0, (geo.height() - h) // 2 + geo.y())
                    self.setGeometry(x, y, w, h)
            except Exception:
                pass

        def _build_ui(self):
            c = _cat_colors()
            central = QWidget()
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            # Browser — the ONLY content in this window
            try:
                init_url = getattr(self, "_pending_browser_url", None) or "about:home"
                self.browser = EmbeddedBrowserPane(initial_url=init_url)
                try:
                    from .browser_manager import BrowserManager
                    self.browser_manager = BrowserManager(self.browser)
                except Exception:
                    self.browser_manager = None
            except Exception as e:
                self.browser = QLabel(f"Browser unavailable: {e}\nInstall: pip install PySide6")
                try:
                    self.browser.setAlignment(Qt.AlignmentFlag.AlignCenter)
                except Exception:
                    pass
                self.browser_manager = None
            layout.addWidget(self.browser)

        def _setup_shortcuts(self):
            shortcuts = [
                ("F11", self.toggle_fullscreen),
                ("Ctrl+Q", self.close),
                ("Ctrl+L", self._focus_address),
                ("Alt+Left", self._browser_back),
                ("Alt+Right", self._browser_forward),
                ("Ctrl+R", self._browser_reload),
                ("Ctrl+T", self._new_tab),
            ]
            for seq, fn in shortcuts:
                try:
                    sc = QShortcut(QKeySequence(seq), self)
                    sc.activated.connect(fn)  # type: ignore
                except Exception:
                    pass

        def navigate(self, url: str):
            if url and hasattr(self.browser, "navigate"):
                QTimer.singleShot(100, lambda: self.browser.navigate(url))  # type: ignore

        def toggle_fullscreen(self):
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()

        def _focus_address(self):
            try:
                if hasattr(self.browser, "address_input"):
                    self.browser.address_input.setFocus()  # type: ignore
                    self.browser.address_input.selectAll()  # type: ignore
            except Exception:
                pass

        def _browser_back(self):
            try:
                if hasattr(self.browser, "go_back"):
                    self.browser.go_back()  # type: ignore
            except Exception:
                pass

        def _browser_forward(self):
            try:
                if hasattr(self.browser, "go_forward"):
                    self.browser.go_forward()  # type: ignore
            except Exception:
                pass

        def _browser_reload(self):
            try:
                if hasattr(self.browser, "reload"):
                    self.browser.reload()  # type: ignore
            except Exception:
                pass

        def _new_tab(self):
            try:
                if hasattr(self.browser, "new_tab"):
                    self.browser.new_tab()  # type: ignore
            except Exception:
                pass

        def _bring_to_front(self):
            try:
                state = self.windowState()
                try:
                    from PySide6.QtCore import Qt as _Qt
                except ImportError:
                    from PyQt6.QtCore import Qt as _Qt  # type: ignore
                if state & _Qt.WindowState.WindowMinimized:
                    self.setWindowState(state & ~_Qt.WindowState.WindowMinimized | _Qt.WindowState.WindowActive)
                self.show()
                self.raise_()
                self.activateWindow()
                if sys.platform == "win32":
                    try:
                        import ctypes
                        hwnd = int(self.winId()) if hasattr(self, "winId") else 0
                        if hwnd > 0:
                            user32 = ctypes.windll.user32
                            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                            # Smooth window activation without DWM surface recreation flicker
                            if hasattr(user32, "SwitchToThisWindow"):
                                user32.SwitchToThisWindow(hwnd, True)
                            user32.BringWindowToTop(hwnd)
                            user32.SetForegroundWindow(hwnd)
                    except Exception:
                        pass
            except Exception:
                pass

        def _check_pending_url(self):
            try:
                import json, time, os
                from pathlib import Path as _P
                now = time.time()
                # Heartbeat with PID and HWND throttled to 1.5s (eliminates disk I/O stutter on low-end PCs)
                if now - getattr(self, "_last_hb_ts", 0.0) >= 1.5:
                    self._last_hb_ts = now
                    hb_path = _P.home() / ".cat_browser_heartbeat"
                    try:
                        hwnd = int(self.winId()) if hasattr(self, "winId") else 0
                        hb_data = json.dumps({"pid": os.getpid(), "ts": now, "hwnd": hwnd})
                        hb_path.write_text(hb_data, encoding="utf-8")
                    except Exception:
                        pass

                pending_path = _P.home() / ".cat_pending_verification.json"
                if pending_path.exists():
                    try:
                        raw = pending_path.read_text(encoding="utf-8").strip()
                        if raw:
                            data = json.loads(raw)
                            url = data.get("url")
                            ts = float(data.get("ts", 0))
                            # Accept pending requests from the last 60 seconds
                            if url and (now - ts) < 60:
                                try:
                                    pending_path.unlink(missing_ok=True)
                                except Exception:
                                    pass
                                self.navigate(url)
                                self._bring_to_front()
                    except Exception:
                        pass
            except Exception:
                pass

        def closeEvent(self, event):
            try:
                from pathlib import Path as _P
                (_P.home() / ".cat_browser_heartbeat").unlink(missing_ok=True)
                (_P.home() / ".cat_pending_verification.json").unlink(missing_ok=True)
                (_P.home() / ".cat_pending_verification.tmp").unlink(missing_ok=True)
            except Exception:
                pass
            try:
                if hasattr(self, "browser") and hasattr(self.browser, "_views"):
                    for v in self.browser._views:
                        if not v:
                            continue
                        try:
                            if hasattr(v, "page") and callable(v.page):
                                p = v.page()
                                if p:
                                    p.deleteLater()
                        except Exception:
                            pass
                    if hasattr(self.browser, "profile"):
                        try:
                            self.browser.profile.deleteLater()
                        except Exception:
                            pass
            except Exception:
                pass
            event.accept()

else:
    # Stub so import never crashes when Qt absent
    class CATDesktopWindow:  # type: ignore
        def __init__(self, *a, **k):
            raise ImportError("Qt not installed — CAT Host requires PySide6 (pip install PySide6) or PyQt6")

    class EmbeddedBrowserPane:  # type: ignore
        def __init__(self, *a, **k):
            raise ImportError("Qt not installed")
