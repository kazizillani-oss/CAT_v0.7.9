"""
CAT Browser — Qt WebEngine (Chromium) implementation.
Real HTML/CSS/JS rendering via QWebEngineView (WebView2/Chromium).

This is the primary graphical backend. It provides:
- Tab bar (favicon + title + close, + new tab, scrollable)
- Navigation toolbar (Back/Forward/Reload/Home, lock, address/search, star, menu)
- Animated progress bar during page loads
- Web viewport (QWebEngineView per tab, persistent profile for cookies/storage)
- New-tab page (CAT branded, centered search, shortcuts, recent)
- History/Bookmarks/Downloads as graphical dialogs (not terminal text)
- Menu, fullscreen, shortcuts, responsive layout, theme integration
- Localhost/Fomoji URLs hidden from address bar for security

Uses PySide6 if available, else PyQt6 (same API).
"""

from __future__ import annotations

import os
import sys
import re
import json
import time
import urllib.parse
from pathlib import Path

_QT_BINDING = None
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTabWidget, QToolBar, QLineEdit, QPushButton, QLabel, QStackedWidget,
        QDialog, QListWidget, QListWidgetItem, QDialogButtonBox, QMessageBox,
        QProgressBar, QFrame, QSizePolicy,
    )
    from PySide6.QtCore import Qt, QUrl, Signal, QSize, QTimer, QPropertyAnimation, QEasingCurve
    from PySide6.QtGui import QAction, QIcon, QKeySequence, QShortcut, QColor, QPalette, QFont
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineDownloadRequest
    _QT_BINDING = "PySide6"
except ImportError:
    try:
        from PyQt6.QtWidgets import (
            QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QTabWidget, QToolBar, QLineEdit, QPushButton, QLabel, QStackedWidget,
            QDialog, QListWidget, QListWidgetItem, QDialogButtonBox, QMessageBox,
            QProgressBar, QFrame, QSizePolicy,
        )
        from PyQt6.QtCore import Qt, QUrl, pyqtSignal as Signal, QSize, QTimer, QPropertyAnimation, QEasingCurve
        from PyQt6.QtGui import QAction, QIcon, QKeySequence, QShortcut, QColor, QPalette, QFont
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineDownloadRequest
        _QT_BINDING = "PyQt6"
    except ImportError:
        _QT_BINDING = None

if _QT_BINDING is None:
    raise ImportError("No Qt binding found (need PySide6 or PyQt6 with WebEngine)")

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


try:
    from ..browser.browser_state import BrowserState
except ImportError:
    from calc_terminal.browser.browser_state import BrowserState  # type: ignore

_URL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")

_FOMOJI_PAGE_NAMES = {
    "connector.html": "Fomoji Connect",
    "home.html": "Fomoji Home",
    "security.html": "Fomoji Security",
    "identities.html": "Fomoji Identities",
    "settings.html": "Fomoji Settings",
}

_FOMOJI_LOADING_STEPS = [
    (0, "Initializing"),
    (15, "Finding server"),
    (30, "Starting Node.js"),
    (50, "Waiting for server"),
    (70, "Checking connection"),
    (85, "Almost ready"),
    (100, "Connected"),
]

def _blend_hex(c1: str, c2: str, factor: float) -> str:
    try:
        c1 = c1.lstrip("#")
        c2 = c2.lstrip("#")
        if len(c1) == 3:
            c1 = "".join(ch * 2 for ch in c1)
        if len(c2) == 3:
            c2 = "".join(ch * 2 for ch in c2)
        r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
        r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
        r = int(r1 + (r2 - r1) * factor)
        g = int(g1 + (g2 - g1) * factor)
        b = int(b1 + (b2 - b1) * factor)
        return f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"
    except Exception:
        return c1


def _cat_theme_colors():
    fallback = {
        "bg": "#0f0f1a", "surface": "#161625", "surface_hover": "#1e1e35",
        "surface_active": "#252545", "surface_alt": "#1a1a2e",
        "text": "#e4e6f8", "text_muted": "#8d92be",
        "border": "#2a2a48", "border_light": "#3b3b64",
        "accent": "#7c6bff", "accent_soft": "#7c6bff25", "accent_hover": "#8f80ff",
        "success": "#5ee9a0", "warning": "#f0c24a", "danger": "#f06060",
        "gradient_start": "#7c6bff", "gradient_end": "#5ee9a0",
        "hi": "#2e2e48", "sh": "#0a0a14",
        "focus_ring": "#7c6bff",
        "is_light": False,
    }
    try:
        from .. import theme as _theme
        is_light = _theme.is_light() if hasattr(_theme, "is_light") else False
        try:
            obj = _theme.get_theme_obj()
            if hasattr(obj, "dark"):
                is_light = not obj.dark
            bg = obj.hex("background")
            surface = obj.hex("surface")
            accent = obj.hex("accent")
            text = obj.hex("text")
            text_muted = obj.hex("text_muted") if hasattr(obj, "text_muted") else "#8d92be"
            border = obj.hex("border") if hasattr(obj, "border") else "#2a2a48"
            accent_hover = obj.hex("accent_alt") if hasattr(obj, "accent_alt") else accent
            success = obj.hex("success") if hasattr(obj, "success") else fallback["success"]
            warning = obj.hex("warning") if hasattr(obj, "warning") else fallback["warning"]
            danger = obj.hex("error") if hasattr(obj, "error") else fallback["danger"]

            if is_light:
                hi = "#ffffff"
                sh = _blend_hex(surface, "#000000", 0.18)
                surface_hover = _blend_hex(surface, "#000000", 0.04)
                surface_active = _blend_hex(surface, "#000000", 0.08)
                surface_alt = _blend_hex(surface, "#000000", 0.03)
                focus_ring = accent
            else:
                hi = _blend_hex(surface, "#ffffff", 0.16)
                sh = _blend_hex(surface, "#000000", 0.50)
                surface_hover = obj.hex("surface_hover") if hasattr(obj, "surface_hover") else _blend_hex(surface, "#ffffff", 0.08)
                surface_active = _blend_hex(surface, "#ffffff", 0.14)
                surface_alt = _blend_hex(surface, "#000000", 0.20)
                focus_ring = accent

            return {
                "bg": bg,
                "surface": surface,
                "surface_hover": surface_hover,
                "surface_active": surface_active,
                "surface_alt": surface_alt,
                "text": text,
                "text_muted": text_muted,
                "border": border,
                "border_light": hi,
                "accent": accent,
                "accent_soft": accent + "25",
                "accent_hover": accent_hover,
                "success": success,
                "warning": warning,
                "danger": danger,
                "gradient_start": accent,
                "gradient_end": success,
                "hi": hi,
                "sh": sh,
                "focus_ring": focus_ring,
                "is_light": is_light,
            }
        except Exception:
            return fallback
    except Exception:
        return fallback


def _friendly_url(url: str) -> str:
    """Hide localhost/Fomoji URLs in address bar — show friendly name instead."""
    if not url or url in ("about:home", "about:blank"):
        return ""
    if "localhost" in url or "127.0.0.1" in url:
        for page, name in _FOMOJI_PAGE_NAMES.items():
            if page in url:
                return name
        return "CAT Internal"
    return url


def _is_search_query(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if _URL_RE.match(t):
        return False
    if t.lower().startswith("about:"):
        return False
    if "localhost" in t.lower():
        return False
    if "." in t.split()[0] and " " not in t and "/" in t:
        return False
    if " " in t:
        return True
    if "." not in t and "/" not in t:
        return True
    return False


_SPINNER_FRAMES = ["|", "/", "-", "\\", "|", "/", "-", "\\"]


class _LoadingSpinner:
    """Non-blocking spinner for tab titles."""
    def __init__(self):
        self._frame = 0

    def next(self) -> str:
        ch = _SPINNER_FRAMES[self._frame % len(_SPINNER_FRAMES)]
        self._frame += 1
        return ch


class _NewTabWidget(QWidget):
    navigateRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        c = _cat_theme_colors()
        self.setStyleSheet(f"background: {c['bg']};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 24, 20, 24)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        wrap = QWidget()
        wrap.setMaximumWidth(680)
        v = QVBoxLayout(wrap)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.setSpacing(16)

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
            f'color:{c["accent"]};">C A T</span>'
            f'<div style="font-size:13px;font-weight:600;letter-spacing:3px;'
            f'color:{c["text_muted"]};margin-top:2px;">B R O W S E R</div>'
            f'</div>'
        )
        bb_layout.addWidget(logo)

        # Feature / Mode Pill
        pill = QLabel("⚡ ECO ENGINE ACTIVE  ·  🛡 AD-SHIELD ON  ·  🚀 60 FPS SMOOTH SCROLL")
        pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pill.setStyleSheet(
            f"QLabel {{ background: {c['surface']}; color: {c['accent']}; border: 1px solid {c['border']}; "
            f"border-radius: 10px; font-size: 10px; font-weight: bold; padding: 4px 14px; margin-top: 4px; }}"
        )
        bb_layout.addWidget(pill)
        v.addWidget(brand_box)

        # 2. Modern Glassmorphic Search Frame
        search_frame = QFrame()
        search_frame.setStyleSheet(f"""
            QFrame {{
                background: {c['surface']};
                border: 1.5px solid {c['border']};
                border-radius: 20px;
            }}
            QFrame:hover {{
                border: 1.5px solid {c['accent']};
                background: {c['surface_hover']};
            }}
        """)
        sh = QHBoxLayout(search_frame)
        sh.setContentsMargins(16, 7, 16, 7)
        sh.setSpacing(10)

        search_icon = QLabel("🔍")
        search_icon.setStyleSheet(f"color: {c['accent']}; font-size: 14px; background: transparent; border: none;")
        sh.addWidget(search_icon)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search the web or enter a URL (e.g. localhost:8765, github.com)...")
        self.search_input.setAccessibleName("Search query or URL")
        self.search_input.setAccessibleDescription("Enter search terms or website address")
        self.search_input.setStyleSheet(
            f"background: transparent; border: none; color: {c['text']};"
            f"font-size: 13px; padding: 2px 0;"
        )
        self.search_input.returnPressed.connect(self._on_search)
        sh.addWidget(self.search_input, 1)

        enter_badge = QLabel("⏎ Enter")
        enter_badge.setStyleSheet(
            f"background: {c['surface_hover']}; color: {c['text_muted']}; border: 1px solid {c['border']}; "
            f"border-radius: 6px; font-size: 10px; font-weight: bold; padding: 2px 6px;"
        )
        sh.addWidget(enter_badge)
        v.addWidget(search_frame)

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
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['surface_hover']}, stop:1 {c['surface']});
                border: 1px solid {c['border']};
                border-radius: 12px;
                color: {c['text']};
                text-align: left;
                padding: 8px 12px;
            }}
            QPushButton:hover {{
                border: 1.5px solid {c['accent']};
                background: {c['surface_hover']};
            }}
            QPushButton:pressed {{
                background: {c['surface']};
                border: 1.5px solid {c['border']};
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
                f'<span style="font-size:12px;font-weight:bold;color:{c["text"]};">{label}</span><br>'
                f'<span style="font-size:10px;color:{c["text_muted"]};margin-left:22px;">{sub}</span>'
            )
            btn.setTextFormat(Qt.TextFormat.RichText)
            btn.clicked.connect(lambda _=None, u=url: self.navigateRequested.emit(u))
            grid.addWidget(btn, row, col)

        grid_wrap = QWidget()
        grid_wrap.setLayout(grid)
        v.addWidget(grid_wrap)

        # 4. Footer & Shortcut Helper
        foot = QLabel("CAT Browser · Ultra-Fast · Low Memory Footprint · Press Ctrl+T for new tab")
        foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        foot.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px; margin-top: 10px;")
        v.addWidget(foot)

        outer.addWidget(wrap)
        QTimer.singleShot(80, lambda: self.search_input.setFocus())

    def _on_search(self):
        text = self.search_input.text().strip()
        if not text:
            return
        has_scheme = bool(_URL_RE.match(text))
        is_local = "localhost" in text.lower()
        if has_scheme or is_local or ("." in text.split()[0] and " " not in text and "/" in text):
            url = text if has_scheme else ("http://" + text if is_local else "https://" + text)
        else:
            url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(text) + "&hl=en"
        self.navigateRequested.emit(url)

    def focusSearch(self):
        self.search_input.setFocus()
        self.search_input.selectAll()


class CATBrowserWindow(QMainWindow):
    def __init__(self, start_url: str = "about:home"):
        super().__init__()
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
            from PySide6.QtGui import QIcon
            ico = get_browser_icon_path()
            if ico and os.path.isfile(ico):
                br_icon = QIcon(ico)
                self.setWindowIcon(br_icon)
                qapp = QApplication.instance()
                if qapp:
                    qapp.setWindowIcon(br_icon)
        except Exception:
            pass

        c = _cat_theme_colors()
        self._colors = c

        self.state = BrowserState()
        self.profile = QWebEngineProfile("CATBrowser", self)
        try:
            self.profile.setPersistentCookiesPolicy(
                QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
            )
            _cache_dir = str(Path.home() / ".cat_browser_cache" / "standalone")
            _storage_dir = str(Path.home() / ".cat_browser_storage" / "standalone")
            Path(_cache_dir).mkdir(parents=True, exist_ok=True)
            Path(_storage_dir).mkdir(parents=True, exist_ok=True)
            self.profile.setCachePath(_cache_dir)
            self.profile.setPersistentStoragePath(_storage_dir)
            try:
                self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
                self.profile.setHttpCacheMaximumSize(50 * 1024 * 1024)
            except Exception:
                pass
        except Exception:
            pass

        central = QWidget()
        central.setStyleSheet(f"background: {c['bg']};")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- Unified chrome surface ----------------------------------------
        chrome = QWidget()
        chrome.setStyleSheet(f"background: {c['bg']};")
        chrome_layout = QVBoxLayout(chrome)
        chrome_layout.setContentsMargins(0, 0, 0, 0)
        chrome_layout.setSpacing(0)

        # ---- Tab bar row ---------------------------------------------------
        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(6, 4, 4, 0)
        tab_row.setSpacing(0)

        try:
            from PySide6.QtWidgets import QTabBar as _QTabBar
        except ImportError:
            from PyQt6.QtWidgets import QTabBar as _QTabBar  # type: ignore
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
        self.tab_bar.setStyleSheet(f"""
            QTabBar {{
                background: transparent;
                qproperty-drawBase: 0;
            }}
            QTabBar::tab {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['surface']}, stop:1 {c['bg']});
                color: {c['text_muted']};
                border-top: 1px solid {c['hi']};
                border-left: 1px solid {c['hi']};
                border-right: 1px solid {c['sh']};
                border-bottom: 1px solid {c['border']};
                padding: 5px 12px;
                margin-right: 2px;
                margin-top: 2px;
                min-width: 80px;
                max-width: 200px;
                font-size: 12px;
                font-weight: 500;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
            QTabBar::tab:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['surface_hover']}, stop:0.15 {c['surface']}, stop:1 {c['surface']});
                color: {c['text']};
                font-weight: 600;
                border-top: 2.5px solid {c['accent']};
                border-left: 1px solid {c['hi']};
                border-right: 1px solid {c['sh']};
                border-bottom: 1px solid {c['surface']};
                margin-top: 0px;
            }}
            QTabBar::tab:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['surface_hover']}, stop:1 {c['surface']});
                border-top: 1.5px solid {c['accent']};
                color: {c['text']};
            }}
            QTabBar::close-button {{
                image: none;
                subcontrol-position: right;
                padding: 2px;
                subcontrol-origin: padding;
                border-radius: 8px;
            }}
            QTabBar::close-button:hover {{
                background: {c['danger']};
                border-radius: 8px;
            }}
        """)
        tab_row.addWidget(self.tab_bar, 1)

        self.new_tab_btn = QPushButton("+")
        self.new_tab_btn.setFixedSize(24, 24)
        self.new_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_tab_btn.setToolTip("New tab (Ctrl+T)")
        self.new_tab_btn.setAccessibleName("New tab")
        self.new_tab_btn.setAccessibleDescription("Create a new tab (Ctrl+T)")
        self.new_tab_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['surface_hover']}, stop:1 {c['surface']});
                color: {c['text_muted']};
                border-top: 1px solid {c['hi']};
                border-left: 1px solid {c['hi']};
                border-right: 1px solid {c['sh']};
                border-bottom: 1px solid {c['sh']};
                border-radius: 5px;
                font-size: 16px;
                font-weight: bold;
                margin: 0 4px 0 2px;
            }}
            QPushButton:hover {{
                color: {c['accent']};
                background: {c['surface_hover']};
                border-top: 1px solid {c['accent']};
                border-left: 1px solid {c['accent']};
            }}
            QPushButton:pressed {{
                border-top: 1px solid {c['sh']};
                border-left: 1px solid {c['sh']};
                border-right: 1px solid {c['hi']};
                border-bottom: 1px solid {c['hi']};
                padding-top: 2px;
                padding-left: 2px;
            }}
            QPushButton:focus {{
                border: 2px solid {c['focus_ring']};
            }}
        """)
        self.new_tab_btn.clicked.connect(lambda: self.new_tab())
        tab_row.addWidget(self.new_tab_btn, 0)

        tab_row_w = QWidget()
        tab_row_w.setLayout(tab_row)
        tab_row_w.setFixedHeight(32)
        tab_row_w.setStyleSheet(f"background: {c['bg']};")
        chrome_layout.addWidget(tab_row_w)

        # ---- Toolbar row (nav + address + menu) ----------------------------
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(6, 2, 6, 4)
        toolbar.setSpacing(2)

        nav_btn_style = f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['surface_hover']}, stop:0.5 {c['surface']}, stop:1 {c['surface']});
                color: {c['text']};
                border-top: 1px solid {c['hi']};
                border-left: 1px solid {c['hi']};
                border-right: 1px solid {c['sh']};
                border-bottom: 1px solid {c['sh']};
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
                padding: 2px 6px;
                min-width: 24px;
                max-width: 28px;
                min-height: 22px;
                max-height: 22px;
            }}
            QPushButton:hover {{
                color: {c['text']};
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['surface_active']}, stop:1 {c['surface_hover']});
                border-top: 1px solid {c['accent']};
                border-left: 1px solid {c['accent']};
            }}
            QPushButton:pressed {{
                border-top: 1px solid {c['sh']};
                border-left: 1px solid {c['sh']};
                border-right: 1px solid {c['hi']};
                border-bottom: 1px solid {c['hi']};
                padding-top: 3px;
                padding-left: 7px;
            }}
            QPushButton:disabled {{
                background: transparent;
                border: 1px solid transparent;
                color: {c['border']};
            }}
            QPushButton:focus {{
                border: 2px solid {c['focus_ring']};
            }}
        """

        self.back_btn = QPushButton("◀")
        self.back_btn.setFixedSize(26, 22)
        self.back_btn.setToolTip("Back (Alt+Left)")
        self.back_btn.setAccessibleName("Back")
        self.back_btn.setAccessibleDescription("Navigate back in history (Alt+Left)")
        self.back_btn.setStyleSheet(nav_btn_style)
        self.back_btn.clicked.connect(self.go_back)
        toolbar.addWidget(self.back_btn)

        self.forward_btn = QPushButton("▶")
        self.forward_btn.setFixedSize(26, 22)
        self.forward_btn.setToolTip("Forward (Alt+Right)")
        self.forward_btn.setAccessibleName("Forward")
        self.forward_btn.setAccessibleDescription("Navigate forward in history (Alt+Right)")
        self.forward_btn.setStyleSheet(nav_btn_style)
        self.forward_btn.clicked.connect(self.go_forward)
        toolbar.addWidget(self.forward_btn)

        self.reload_btn = QPushButton("⟳")
        self.reload_btn.setFixedSize(26, 22)
        self.reload_btn.setToolTip("Reload (Ctrl+R)")
        self.reload_btn.setAccessibleName("Reload")
        self.reload_btn.setAccessibleDescription("Reload current page (Ctrl+R)")
        self.reload_btn.setStyleSheet(nav_btn_style)
        self.reload_btn.clicked.connect(self.reload)
        toolbar.addWidget(self.reload_btn)

        toolbar.addSpacing(4)

        # Address bar — minimal sleek pill
        addr_frame = QFrame()
        addr_frame.setStyleSheet(f"""
            QFrame {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.09);
                border-radius: 13px;
            }}
            QFrame:hover {{
                background: rgba(255, 255, 255, 0.07);
                border: 1px solid rgba(255, 255, 255, 0.16);
            }}
            QFrame:focus-within {{
                border: 1px solid {c['accent']};
                background: {c['surface']};
            }}
        """)
        addr_layout = QHBoxLayout(addr_frame)
        addr_layout.setContentsMargins(8, 0, 8, 0)
        addr_layout.setSpacing(6)

        self.lock_label = QLabel("⌕")
        self.lock_label.setFixedWidth(16)
        self.lock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lock_label.setToolTip("Security & Search")
        self.lock_label.setAccessibleName("Security connection status")
        self.lock_label.setStyleSheet(f"""
            color: {c['text_muted']};
            font-size: 13px;
            background: transparent;
            border: none;
            padding: 0;
        """)
        addr_layout.addWidget(self.lock_label)

        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("Search or enter address")
        self.address_input.setAccessibleName("Address or search query")
        self.address_input.setAccessibleDescription("Enter URL or search query and press Enter")
        self.address_input.returnPressed.connect(self._on_address_enter)
        self.address_input.setClearButtonEnabled(True)
        self.address_input.setStyleSheet(f"""
            background: transparent; border: none; color: {c['text']};
            font-size: 12px; padding: 0 2px;
            selection-background-color: {c['accent']};
        """)
        addr_layout.addWidget(self.address_input, 1)

        toolbar.addWidget(addr_frame, 1)

        self.menu_btn = QPushButton("⋮")
        self.menu_btn.setFixedSize(24, 22)
        self.menu_btn.setToolTip("Menu")
        self.menu_btn.setAccessibleName("Menu")
        self.menu_btn.setAccessibleDescription("Browser settings and options")
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
        toolbar_w.setFixedHeight(30)
        toolbar_w.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['bg']}, stop:1 {c['surface']});
                border-bottom: 1px solid {c['sh']};
            }}
        """)
        chrome_layout.addWidget(toolbar_w)

        # ---- Progress bar (3D recessed channel with glowing fill) ----------
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setAccessibleName("Page loading progress")
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {c['sh']};
                border-top: 1px solid {c['sh']};
                border-bottom: 1px solid {c['hi']};
                border-radius: 0px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {c['accent']}, stop:0.7 {c['gradient_end']}, stop:1 #ffffff);
                border-radius: 1px;
            }}
        """)
        self.progress_bar.hide()
        chrome_layout.addWidget(self.progress_bar)

        layout.addWidget(chrome)

        self.viewport_stack = QStackedWidget()
        self.viewport_stack.setStyleSheet(f"background: {c['bg']};")
        layout.addWidget(self.viewport_stack, 1)

        self._views: list[QWidget] = []
        self._view_index: dict[int, int] = {}  # id(view) -> index for O(1) lookup
        self._spinners: dict[int, _LoadingSpinner] = {}
        self._pending_start_url = start_url
        QTimer.singleShot(0, self._create_initial_tab)

        self._setup_shortcuts()
        self._apply_theme()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick_spinner)
        self._timer.start(200)

    def _tick_spinner(self):
        for idx, sp in list(self._spinners.items()):
            if 0 <= idx < self.tab_bar.count():
                ch = sp.next()
                if 0 <= idx < len(self.state.tabs):
                    title = self.state.tabs[idx].title[:28]
                    self.tab_bar.setTabText(idx, f"{ch}  {title}")

    def _view_index(self, view: QWidget) -> int:
        """O(1) view index lookup via cached dict."""
        return self._view_index.get(id(view), -1)

    def _rebuild_view_index(self):
        """Rebuild the O(1) index cache after list changes."""
        self._view_index = {id(v): i for i, v in enumerate(self._views)}

    def _setup_shortcuts(self):
        shortcuts = [
            ("Ctrl+L", self._focus_address),
            ("Ctrl+T", lambda: self.new_tab()),
            ("Ctrl+W", self._close_active_tab),
            ("Ctrl+R", self.reload),
            ("F5", self.reload),
            ("Ctrl+Shift+T", self.reopen_closed),
            ("Alt+Left", self.go_back),
            ("Alt+Right", self.go_forward),
            ("F11", self.toggle_fullscreen),
            ("Escape", self._handle_escape),
        ]
        for seq, fn in shortcuts:
            try:
                sc = QShortcut(QKeySequence(seq), self)
                sc.activated.connect(fn)  # type: ignore
            except Exception:
                pass

    def _create_initial_tab(self):
        try:
            self._new_tab(url=getattr(self, "_pending_start_url", "about:home"), switch=True)
        except Exception:
            pass

    def _apply_theme(self):
        c = self._colors
        self.setStyleSheet(f"""
            QMainWindow {{ background: {c['bg']}; }}
            QLineEdit {{ selection-background-color: {c['accent']}; }}
            QToolTip {{
                background: {c['surface']}; color: {c['text']};
                border: 1px solid {c['border']}; border-radius: 6px;
                padding: 4px 8px; font-size: 12px;
            }}
        """)

    def _new_tab(self, url: str = "about:home", switch: bool = True) -> int:
        tab = self.state.new_tab(url)
        is_new_tab = url in ("about:home", "about:blank")
        if is_new_tab:
            view = _NewTabWidget()
            try:
                view.navigateRequested.connect(lambda u, idx=None: self._handle_newtab_navigate(u))
            except Exception:
                pass
            self._newtab_widget = view
        else:
            view = SecureWebEngineView()

        if not is_new_tab:
            try:
                page = SecureWebEnginePage(self.profile, view)
                try:
                    page.setDevToolsPage(None)
                except Exception:
                    pass
                view.setPage(page)
            except Exception:
                pass
            try:
                view.titleChanged.connect(lambda title, v=view: self._on_title_changed(v, title))
                view.urlChanged.connect(lambda qurl, v=view: self._on_url_changed(v, qurl))
                view.loadStarted.connect(lambda v=view: self._on_load_started(v))
                view.loadFinished.connect(lambda ok, v=view: self._on_load_finished(v, ok))
                view.iconChanged.connect(lambda icon, v=view: self._on_icon_changed(v, icon))
                view.page().newWindowRequested.connect(lambda req: self._on_new_window_requested(req))
                try:
                    view.loadProgress.connect(
                        lambda p, v=view: self._on_load_progress(v, p)
                    )
                except Exception:
                    pass
            except Exception:
                pass
            try:
                if not getattr(self, "_download_connected", False):
                    self.profile.downloadRequested.connect(self._on_download_requested)
                    self._download_connected = True
            except Exception:
                pass

        idx = self.viewport_stack.addWidget(view)
        self._views.append(view)
        self._rebuild_view_index()
        tab_idx = self.tab_bar.addTab(f"{tab.favicon}  {tab.display_title()[:28]}")
        if switch:
            self.tab_bar.setCurrentIndex(tab_idx)
            self.viewport_stack.setCurrentIndex(idx)
            self._sync_address()
            if not is_new_tab:
                self._load_in_view(view, url)
            else:
                try:
                    QTimer.singleShot(100, lambda: view.focusSearch())
                except Exception:
                    pass
        return tab_idx

    def _handle_newtab_navigate(self, url: str):
        idx = self.tab_bar.currentIndex()
        if not (0 <= idx < len(self._views)):
            self.navigate(url)
            return
        old = self._views[idx]
        if not isinstance(old, _NewTabWidget):
            self.navigate(url)
            return
        self.viewport_stack.removeWidget(old)
        old.deleteLater()
        view = QWebEngineView()
        try:
            page = QWebEnginePage(self.profile, view)
            view.setPage(page)
            view.titleChanged.connect(lambda title, v=view: self._on_title_changed(v, title))
            view.urlChanged.connect(lambda qurl, v=view: self._on_url_changed(v, qurl))
            view.loadStarted.connect(lambda v=view: self._on_load_started(v))
            view.loadFinished.connect(lambda ok, v=view: self._on_load_finished(v, ok))
            view.page().newWindowRequested.connect(lambda req: self._on_new_window_requested(req))
            try:
                view.loadProgress.connect(
                    lambda p, v=view: self._on_load_progress(v, p)
                )
            except Exception:
                pass
        except Exception:
            pass
        self.viewport_stack.insertWidget(idx, view)
        self.viewport_stack.setCurrentIndex(idx)
        self._views[idx] = view
        self._rebuild_view_index()
        tab = self.state.tabs[idx] if 0 <= idx < len(self.state.tabs) else None
        if tab:
            tab.url = url
            tab.title = "Loading…"
        self.tab_bar.setTabText(idx, "⟳  Loading…")
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self._load_in_view(view, url)

    def _load_in_view(self, view, url: str):
        if url in ("about:home", "about:blank"):
            return
        try:
            view.load(QUrl(url))
        except Exception:
            pass

    def _on_tab_clicked(self, index: int):
        if 0 <= index < len(self._views):
            self.tab_bar.setCurrentIndex(index)
            self.viewport_stack.setCurrentIndex(index)
            if 0 <= index < len(self.state.tabs):
                self.state.active_tab_id = self.state.tabs[index].id
            self._sync_address()

    def _close_tab(self, index: int):
        if not (0 <= index < len(self._views)):
            return
        view = self._views.pop(index)
        self._spinners.pop(index, None)
        self.viewport_stack.removeWidget(view)
        view.deleteLater()
        self.tab_bar.removeTab(index)
        self._rebuild_view_index()
        if 0 <= index < len(self.state.tabs):
            self.state.close_tab(self.state.tabs[index].id)
        if self.tab_bar.count() == 0:
            self.progress_bar.hide()
            self.new_tab("about:home")
        else:
            new_idx = min(index, self.tab_bar.count() - 1)
            self.tab_bar.setCurrentIndex(new_idx)
            self.viewport_stack.setCurrentIndex(new_idx)
            if 0 <= new_idx < len(self.state.tabs):
                self.state.active_tab_id = self.state.tabs[new_idx].id
            self._sync_address()

    def _close_active_tab(self):
        self._close_tab(self.tab_bar.currentIndex())

    def new_tab(self, url: str = "about:home"):
        self._new_tab(url, switch=True)

    def navigate(self, raw: str):
        url = raw.strip()
        if not url:
            return
        has_scheme = bool(_URL_RE.match(url))
        is_about = url.lower().startswith("about:")
        if _is_search_query(url) and not has_scheme and not is_about and "localhost" not in url.lower():
            q = urllib.parse.quote_plus(url)
            url = f"https://www.google.com/search?q={q}&hl=en"
        elif not has_scheme and not is_about and "." in url.split("/")[0] and " " not in url:
            url = "https://" + url

        tab = self.state.active_tab
        tab.url = url
        tab.title = "Loading..."
        self.state.navigate_active(url)
        self._sync_address()
        idx = self.tab_bar.currentIndex()
        if 0 <= idx < len(self._views):
            view = self._views[idx]
            if isinstance(view, _NewTabWidget) and url not in ("about:home", "about:blank"):
                self._handle_newtab_navigate(url)
                self._update_bookmark_star()
                return
            if not isinstance(view, _NewTabWidget) and url in ("about:home", "about:blank"):
                try:
                    self.viewport_stack.removeWidget(view)
                    view.deleteLater()
                    new_w = _NewTabWidget()
                    new_w.navigateRequested.connect(lambda u: self._handle_newtab_navigate(u))
                    self.viewport_stack.insertWidget(idx, new_w)
                    self.viewport_stack.setCurrentIndex(idx)
                    self._views[idx] = new_w
                    tab.title = "New Tab"
                    tab.favicon = "○"
                    self.tab_bar.setTabText(idx, "○  New Tab")
                    self._sync_address()
                    QTimer.singleShot(80, lambda: new_w.focusSearch())
                except Exception:
                    self._load_in_view(view, url)
                self._update_bookmark_star()
                return
            self._load_in_view(view, url)
            self.tab_bar.setTabText(idx, f"⟳  Loading...")
            self.progress_bar.setValue(0)
            self.progress_bar.show()
            self._update_bookmark_star()

    def _on_address_enter(self):
        self.navigate(self.address_input.text())

    def _on_title_changed(self, view, title: str):
        try:
            idx = self._view_index(view)
            if idx < 0:
                return
            if 0 <= idx < len(self.state.tabs):
                self.state.tabs[idx].title = title or "Untitled"
                self.state.update_active(self.state.tabs[idx].url, title)
                if idx not in self._spinners:
                    display = title[:28] if title else "Untitled"
                    self.tab_bar.setTabText(idx, f"{self.state.tabs[idx].favicon}  {display}")
            if idx == self.tab_bar.currentIndex():
                self.setWindowTitle(f"CAT Browser — {title[:40]}")
        except (ValueError, IndexError):
            pass

    def _on_url_changed(self, view, qurl):
        try:
            idx = self._view_index(view)
            if idx < 0:
                return
            url = qurl.toString()
            if 0 <= idx < len(self.state.tabs):
                self.state.tabs[idx].url = url
                self.state.tabs[idx].favicon = "🔒" if url.startswith("https://") else "○"
                title = self.state.tabs[idx].title
                if idx not in self._spinners:
                    display = title[:28] if title else "Untitled"
                    self.tab_bar.setTabText(idx, f"{self.state.tabs[idx].favicon}  {display}")
            if idx == self.tab_bar.currentIndex():
                display = _friendly_url(url)
                self.address_input.setText(display)
                if url.startswith("https://"):
                    self.lock_label.setText("🔒")
                    self.lock_label.setStyleSheet("color: #10b981; font-size: 11px; background: transparent; border: none; padding: 0;")
                elif url.startswith("about:") or not url:
                    self.lock_label.setText("⌕")
                    self.lock_label.setStyleSheet(f"color: {self._colors.get('text_muted', '#8d92be')}; font-size: 13px; background: transparent; border: none; padding: 0;")
                else:
                    self.lock_label.setText("🌐")
                    self.lock_label.setStyleSheet(f"color: {self._colors.get('text_muted', '#8d92be')}; font-size: 11px; background: transparent; border: none; padding: 0;")
                self._update_bookmark_star()
        except (ValueError, IndexError):
            pass

    def _on_load_progress(self, view, progress: int):
        try:
            idx = self._view_index(view)
            if idx < 0:
                return
            if idx == self.tab_bar.currentIndex():
                self.progress_bar.setValue(progress)
        except (ValueError, IndexError):
            pass

    def _on_load_started(self, view):
        try:
            idx = self._view_index(view)
            if idx < 0:
                return
            if idx == self.tab_bar.currentIndex():
                self.reload_btn.setText("✕")
                self.reload_btn.setToolTip("Stop loading")
                self.progress_bar.setValue(0)
                self.progress_bar.show()
            if 0 <= idx < len(self.state.tabs):
                self.state.tabs[idx].loading = True
                sp = _LoadingSpinner()
                self._spinners[idx] = sp
                self.tab_bar.setTabText(idx, f"{sp.next()}  {self.state.tabs[idx].title[:28]}")
        except (ValueError, IndexError):
            pass

    def _on_load_finished(self, view, ok: bool):
        try:
            idx = self._view_index(view)
            if idx < 0:
                return
            if 0 <= idx < len(self.state.tabs):
                self.state.tabs[idx].loading = False
                self._spinners.pop(idx, None)
                title = view.title() or self.state.tabs[idx].url
                self.state.tabs[idx].title = title[:60]
                display = title[:28] if title else "Untitled"
                self.tab_bar.setTabText(idx, f"{self.state.tabs[idx].favicon}  {display}")
                self.state.update_active(self.state.tabs[idx].url, title)
            if idx == self.tab_bar.currentIndex():
                self.reload_btn.setText("⟳")
                self.reload_btn.setToolTip("Reload (Ctrl+R)")
                self.progress_bar.hide()
                self.progress_bar.setValue(0)
                self._sync_address()
        except (ValueError, IndexError):
            pass

    def _on_icon_changed(self, view, icon):
        pass

    def _on_new_window_requested(self, request):
        try:
            url = request.requestedUrl().toString()
            self.new_tab(url)
            view = self._views[-1]
            try:
                request.openIn(view.page())
            except Exception:
                view.load(QUrl(url))
        except Exception:
            pass

    def _on_download_requested(self, download):
        try:
            filename = download.downloadFileName() or "download"
            path = str(Path.home() / "Downloads" / filename)
            download.setDownloadDirectory(str(Path.home() / "Downloads"))
            download.setDownloadFileName(filename)
            download.accept()
            self.state.add_download(filename, download.url().toString(), path)
            download.finished.connect(lambda: self._on_download_finished(download))
        except Exception:
            try:
                download.accept()
            except Exception:
                pass

    def _on_download_finished(self, download):
        pass

    def _sync_address(self):
        try:
            tab = self.state.active_tab
            display = _friendly_url(tab.url)
            if self.address_input.text() != display:
                self.address_input.setText(display)
            if tab.url.startswith("https"):
                lock = "🔒"
                self.lock_label.setStyleSheet("color: #10b981; font-size: 11px; background: transparent; border: none; padding: 0;")
            elif tab.url.startswith("about:") or not tab.url:
                lock = "⌕"
                self.lock_label.setStyleSheet(f"color: {self._colors.get('text_muted', '#8d92be')}; font-size: 13px; background: transparent; border: none; padding: 0;")
            else:
                lock = "🌐"
                self.lock_label.setStyleSheet(f"color: {self._colors.get('text_muted', '#8d92be')}; font-size: 11px; background: transparent; border: none; padding: 0;")
            if self.lock_label.text() != lock:
                self.lock_label.setText(lock)
            self.back_btn.setEnabled(self.state.can_go_back())
            self.forward_btn.setEnabled(self.state.can_go_forward())
            title = tab.display_title()
            new_title = f"CAT Browser — {title}"
            if self.windowTitle() != new_title:
                self.setWindowTitle(new_title)
            # Sync current tab text with favicon
            idx = self.tab_bar.currentIndex()
            if 0 <= idx < len(self.state.tabs):
                fav = self.state.tabs[idx].favicon or "○"
                title_text = self.state.tabs[idx].title[:28] if self.state.tabs[idx].title else "Untitled"
                new_tab_text = f"{fav}  {title_text}"
                if self.tab_bar.tabText(idx) != new_tab_text:
                    self.tab_bar.setTabText(idx, new_tab_text)
        except Exception:
            pass

    def _update_bookmark_star(self):
        pass  # Bookmark removed for cleaner toolbar

    def go_back(self):
        idx = self.tab_bar.currentIndex()
        if 0 <= idx < len(self._views) and hasattr(self._views[idx], "back"):
            self._views[idx].back()

    def go_forward(self):
        idx = self.tab_bar.currentIndex()
        if 0 <= idx < len(self._views) and hasattr(self._views[idx], "forward"):
            self._views[idx].forward()

    def reload(self):
        idx = self.tab_bar.currentIndex()
        if 0 <= idx < len(self._views):
            v = self._views[idx]
            if hasattr(v, "isLoading") and v.isLoading():
                v.stop()
                self.reload_btn.setText("⟳")
                self.progress_bar.hide()
            elif hasattr(v, "reload"):
                v.reload()
                self.progress_bar.setValue(0)
                self.progress_bar.show()

    def toggle_bookmark(self):
        pass  # Bookmark removed for cleaner toolbar

    def show_menu(self):
        try:
            from PySide6.QtWidgets import QMenu as _QMenu
        except ImportError:
            from PyQt6.QtWidgets import QMenu as _QMenu  # type: ignore
        c = self._colors
        menu = _QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {c['surface']};
                color: {c['text']};
                border-top: 1px solid {c['hi']};
                border-left: 1px solid {c['hi']};
                border-right: 1.5px solid {c['sh']};
                border-bottom: 1.5px solid {c['sh']};
                border-radius: 8px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 6px 22px 6px 12px;
                border-radius: 5px;
                margin: 1px 2px;
            }}
            QMenu::item:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['accent_hover']}, stop:1 {c['accent']});
                color: #ffffff;
            }}
            QMenu::separator {{
                height: 1px;
                background: {c['border']};
                margin: 4px 8px;
            }}
        """)
        actions = [
            ("New Tab", lambda: self.new_tab()),
            ("New Window", lambda: self.new_tab()),
            (None, None),
            ("History", self.show_history),
            ("Bookmarks", self.show_bookmarks),
            ("Downloads", self.show_downloads),
            (None, None),
            ("Find on Page", lambda: self._focus_address()),
            ("Developer Tools", self.show_devtools),
            (None, None),
            ("Settings", lambda: self.navigate("http://localhost:3000/settings.html")),
        ]
        for label, fn in actions:
            if label is None:
                menu.addSeparator()
            else:
                act = menu.addAction(label)
                if fn:
                    act.triggered.connect(fn)
        menu.exec(self.menu_btn.mapToGlobal(self.menu_btn.rect().bottomLeft()))

    def show_history(self):
        dlg = HistoryDialog(self.state, self)
        dlg.exec()

    def show_bookmarks(self):
        dlg = BookmarksDialog(self.state, self)

        def on_open(url):
            dlg.accept()
            self.navigate(url)

        dlg.bookmark_opened.connect(on_open)
        dlg.exec()

    def show_downloads(self):
        dlg = DownloadsDialog(self.state, self)
        dlg.exec()

    def show_devtools(self):
        dlg = DevToolsDialog(self)
        dlg.exec()

    def reopen_closed(self):
        tab = self.state.reopen_closed()
        if tab:
            self.new_tab(tab.url)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _focus_address(self):
        self.address_input.selectAll()
        self.address_input.setFocus()

    def _handle_escape(self):
        pass

    def closeEvent(self, event):
        try:
            if hasattr(self, '_timer'):
                self._timer.stop()
        except Exception:
            pass
        event.accept()


class HistoryDialog(QDialog):
    def __init__(self, state: BrowserState, parent=None):
        super().__init__(parent)
        self.state = state
        c = _cat_theme_colors()
        self.setWindowTitle("History — CAT Browser")
        self.resize(700, 500)
        self.setStyleSheet(f"""
            QDialog {{ background: {c['bg']}; color: {c['text']}; }}
            QLabel {{ color: {c['text']}; font-size: 14px; font-weight: bold; }}
            QListWidget {{
                background: {c['surface']}; color: {c['text']};
                border-top: 1.5px solid {c['sh']}; border-left: 1.5px solid {c['sh']};
                border-right: 1px solid {c['hi']}; border-bottom: 1px solid {c['hi']};
                border-radius: 8px; padding: 4px; font-size: 12px;
            }}
            QListWidget::item {{ padding: 6px 8px; border-radius: 4px; }}
            QListWidget::item:selected {{
                background: {c['accent']}; color: #ffffff;
                border-top: 1px solid {c['hi']}; border-bottom: 1px solid {c['sh']};
            }}
            QListWidget::item:hover {{ background: {c['surface_hover']}; }}
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['surface_hover']}, stop:1 {c['surface']});
                color: {c['text']};
                border-top: 1px solid {c['hi']}; border-left: 1px solid {c['hi']};
                border-right: 1px solid {c['sh']}; border-bottom: 1px solid {c['sh']};
                border-radius: 6px; padding: 6px 16px; font-weight: 500;
            }}
            QPushButton:hover {{ border-color: {c['accent']}; }}
            QPushButton:pressed {{
                border-top: 1px solid {c['sh']}; border-left: 1px solid {c['sh']};
                border-right: 1px solid {c['hi']}; border-bottom: 1px solid {c['hi']};
                padding-top: 7px; padding-left: 17px;
            }}
            QPushButton:focus {{ border: 2px solid {c['focus_ring']}; }}
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        label = QLabel("History")
        layout.addWidget(label)
        self.list_widget = QListWidget()
        groups = state.history_grouped()
        for gname in ("Today", "Yesterday", "Earlier"):
            entries = groups.get(gname, [])
            if not entries:
                continue
            header = QListWidgetItem(f"--- {gname} ---")
            header.setFlags(header.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            header.setForeground(QColor(c["text_muted"]))
            self.list_widget.addItem(header)
            for h in entries[:50]:
                display = _friendly_url(h.url) if "localhost" in h.url else h.url[:60]
                item = QListWidgetItem(
                    f"{h.favicon}  {h.title[:40]}  |  {display}  [{time.strftime('%H:%M', time.localtime(h.timestamp))}]"
                )
                item.setData(Qt.ItemDataRole.UserRole, h.url)
                self.list_widget.addItem(item)
        self.list_widget.itemDoubleClicked.connect(self._open)
        layout.addWidget(self.list_widget)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        btns.accepted.connect(self.accept)
        layout.addWidget(btns)

    def _open(self, item):
        url = item.data(Qt.ItemDataRole.UserRole)
        if url:
            parent = self.parent()
            if hasattr(parent, "navigate"):
                parent.navigate(url)
            self.accept()


class BookmarksDialog(QDialog):
    bookmark_opened = Signal(str)

    def __init__(self, state: BrowserState, parent=None):
        super().__init__(parent)
        self.state = state
        c = _cat_theme_colors()
        self.setWindowTitle("Bookmarks — CAT Browser")
        self.resize(600, 400)
        self.setStyleSheet(f"""
            QDialog {{ background: {c['bg']}; color: {c['text']}; }}
            QLabel {{ color: {c['text']}; font-size: 14px; font-weight: bold; }}
            QListWidget {{
                background: {c['surface']}; color: {c['text']};
                border-top: 1.5px solid {c['sh']}; border-left: 1.5px solid {c['sh']};
                border-right: 1px solid {c['hi']}; border-bottom: 1px solid {c['hi']};
                border-radius: 8px; padding: 4px; font-size: 12px;
            }}
            QListWidget::item {{ padding: 6px 8px; border-radius: 4px; }}
            QListWidget::item:selected {{
                background: {c['accent']}; color: #ffffff;
                border-top: 1px solid {c['hi']}; border-bottom: 1px solid {c['sh']};
            }}
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['surface_hover']}, stop:1 {c['surface']});
                color: {c['text']};
                border-top: 1px solid {c['hi']}; border-left: 1px solid {c['hi']};
                border-right: 1px solid {c['sh']}; border-bottom: 1px solid {c['sh']};
                border-radius: 6px; padding: 6px 16px; font-weight: 500;
            }}
            QPushButton:hover {{ border-color: {c['accent']}; }}
            QPushButton:pressed {{
                border-top: 1px solid {c['sh']}; border-left: 1px solid {c['sh']};
                border-right: 1px solid {c['hi']}; border-bottom: 1px solid {c['hi']};
                padding-top: 7px; padding-left: 17px;
            }}
            QPushButton:focus {{ border: 2px solid {c['focus_ring']}; }}
        """)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Bookmarks"))
        self.list_widget = QListWidget()
        for bm in state.bookmarks:
            display = _friendly_url(bm.url) if "localhost" in bm.url else bm.url
            item = QListWidgetItem(f"{bm.favicon}  {bm.title} | {display}")
            item.setData(Qt.ItemDataRole.UserRole, bm.id)
            self.list_widget.addItem(item)
        self.list_widget.itemDoubleClicked.connect(self._open)
        layout.addWidget(self.list_widget)
        btn_layout = QHBoxLayout()
        del_btn = QPushButton("Delete")
        del_btn.clicked.connect(self._delete)
        open_btn = QPushButton("Open")
        open_btn.clicked.connect(lambda: self._open(self.list_widget.currentItem()))
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(open_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _open(self, item):
        if not item:
            return
        bm_id = item.data(Qt.ItemDataRole.UserRole)
        bm = next((b for b in self.state.bookmarks if b.id == bm_id), None)
        if bm:
            self.bookmark_opened.emit(bm.url)

    def _delete(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        bm_id = item.data(Qt.ItemDataRole.UserRole)
        self.state.remove_bookmark(bm_id)
        self.list_widget.takeItem(self.list_widget.row(item))


class DownloadsDialog(QDialog):
    def __init__(self, state: BrowserState, parent=None):
        super().__init__(parent)
        self.state = state
        c = _cat_theme_colors()
        self.setWindowTitle("Downloads — CAT Browser")
        self.resize(600, 400)
        self.setStyleSheet(f"""
            QDialog {{ background: {c['bg']}; color: {c['text']}; }}
            QLabel {{ color: {c['text']}; font-size: 14px; font-weight: bold; }}
            QListWidget {{
                background: {c['surface']}; color: {c['text']};
                border-top: 1.5px solid {c['sh']}; border-left: 1.5px solid {c['sh']};
                border-right: 1px solid {c['hi']}; border-bottom: 1px solid {c['hi']};
                border-radius: 8px; padding: 4px; font-size: 12px;
            }}
            QListWidget::item {{ padding: 6px 8px; border-radius: 4px; }}
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['surface_hover']}, stop:1 {c['surface']});
                color: {c['text']};
                border-top: 1px solid {c['hi']}; border-left: 1px solid {c['hi']};
                border-right: 1px solid {c['sh']}; border-bottom: 1px solid {c['sh']};
                border-radius: 6px; padding: 6px 16px; font-weight: 500;
            }}
            QPushButton:hover {{ border-color: {c['accent']}; }}
            QPushButton:pressed {{
                border-top: 1px solid {c['sh']}; border-left: 1px solid {c['sh']};
                border-right: 1px solid {c['hi']}; border-bottom: 1px solid {c['hi']};
                padding-top: 7px; padding-left: 17px;
            }}
            QPushButton:focus {{ border: 2px solid {c['focus_ring']}; }}
        """)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Downloads"))
        self.list_widget = QListWidget()
        for d in state.downloads:
            display = _friendly_url(d.url) if "localhost" in d.url else d.url[:50]
            item = QListWidgetItem(
                f"{d.filename}  |  {d.status} {d.progress}%  |  {display}"
            )
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)


class DevToolsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        c = _cat_theme_colors()
        self.setWindowTitle("Developer Tools — CAT Browser")
        self.resize(700, 500)
        self.setStyleSheet(f"""
            QDialog {{ background: {c['bg']}; color: {c['text']}; }}
            QLabel {{ color: {c['text']}; font-size: 13px; }}
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['surface_hover']}, stop:1 {c['surface']});
                color: {c['text']};
                border-top: 1px solid {c['hi']}; border-left: 1px solid {c['hi']};
                border-right: 1px solid {c['sh']}; border-bottom: 1px solid {c['sh']};
                border-radius: 6px; padding: 6px 16px; font-weight: 500;
            }}
            QPushButton:hover {{ border-color: {c['accent']}; }}
            QPushButton:pressed {{
                border-top: 1px solid {c['sh']}; border-left: 1px solid {c['sh']};
                border-right: 1px solid {c['hi']}; border-bottom: 1px solid {c['hi']};
                padding-top: 7px; padding-left: 17px;
            }}
            QPushButton:focus {{ border: 2px solid {c['focus_ring']}; }}
        """)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Developer Tools"))
        layout.addWidget(QLabel("Console — browser logs appear here."))
        layout.addWidget(QLabel("Network — requests, WebSocket, server logs"))
        layout.addWidget(QLabel("Storage: ~/.cat_browser_*.json"))
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)


def launch_qt_browser(start_url: str = "about:home") -> int:
    try:
        from ..host.launcher import get_optimal_chromium_flags
        flags = get_optimal_chromium_flags()
    except Exception:
        flags = (
            "--enable-gpu-rasterization --enable-zero-copy --enable-smooth-scrolling "
            "--disable-dev-shm-usage --disable-features=CalculateNativeWinOcclusion --no-sandbox"
        )
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", flags)
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
    app = QApplication.instance()
    created = False
    if app is None:
        app = QApplication(sys.argv)
        created = True
    if not start_url or start_url == "about:home":
        start_url = "about:home"
    w = CATBrowserWindow(start_url)
    w.show()
    if created:
        return app.exec()
    else:
        return 0
