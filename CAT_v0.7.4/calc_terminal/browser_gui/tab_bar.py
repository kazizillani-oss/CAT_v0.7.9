"""
CAT Browser Tabs — Hybrid Vertical / Horizontal Tab Controller.

Supports:
- Vertical Tabs when position is Left or Right (matching modern browser sidebars:
  readable horizontal text, full titles, favicon on left, close '✕' on right,
  header with tab count and '+' button).
- Sleek Horizontal Tabs when position is Top or Bottom (pill style, accent line).
- 100% drop-in API compatibility with QTabBar (addTab, removeTab, setTabText, etc.).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

try:
    from PySide6.QtCore import Qt, Signal, QSize
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTabBar, QScrollArea,
        QLabel, QPushButton, QSizePolicy, QFrame, QStyleOption, QStyle
    )
    from PySide6.QtGui import QColor, QFontMetrics, QCursor, QMouseEvent, QIcon, QPainter
except ImportError:
    from PyQt6.QtCore import Qt, pyqtSignal as Signal, QSize  # type: ignore
    from PyQt6.QtWidgets import (  # type: ignore
        QWidget, QVBoxLayout, QHBoxLayout, QTabBar, QScrollArea,
        QLabel, QPushButton, QSizePolicy, QFrame, QStyleOption, QStyle
    )
    from PyQt6.QtGui import QColor, QFontMetrics, QCursor, QMouseEvent, QIcon, QPainter  # type: ignore


def _default_colors() -> dict:
    return {
        "bg": "#14161b",
        "surface": "#1a1d24",
        "surface_hover": "#222630",
        "surface_active": "#2a2f3d",
        "accent": "#4f8cff",
        "text": "#e6eaf2",
        "text_muted": "#8d95a5",
        "border": "#2c313c",
    }


def _get_close_icons() -> dict[str, str]:
    base = Path(__file__).resolve().parent / "icons"
    return {
        "png": str(base / "tab_close.png").replace("\\", "/"),
        "png_hover": str(base / "tab_close_hover.png").replace("\\", "/"),
        "svg": str(base / "tab_close.svg").replace("\\", "/"),
        "svg_hover": str(base / "tab_close_hover.svg").replace("\\", "/"),
    }


class ElidedLabel(QLabel):
    """Flexible single-line label with clean ellipsis that never pushes layout beyond bounds."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self._raw_text = text
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setToolTip(text)

    def setText(self, text: str):
        self._raw_text = text
        self.setToolTip(text)
        self._update_elided()

    def fullText(self) -> str:
        return self._raw_text

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elided()

    def _update_elided(self):
        fm = self.fontMetrics()
        w = max(10, self.width() - 2)
        super().setText(fm.elidedText(self._raw_text, Qt.TextElideMode.ElideRight, w))

    def minimumSizeHint(self) -> QSize:
        return QSize(20, self.fontMetrics().height())

    def sizeHint(self) -> QSize:
        return QSize(100, self.fontMetrics().height() + 4)


class VerticalTabRow(QFrame):
    """A single tab row in the vertical tab sidebar."""

    def __init__(self, index: int, fav: str, title: str, colors: dict, pos: str = "left", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.index = index
        self.fav = fav
        self.title = title
        self.colors = colors
        self.pos = pos
        self.is_active = False

        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 2, 7, 2)
        layout.setSpacing(8)

        # Crisp dedicated vertical indicator bar (prevents border-radius clipping bugs)
        self.indicator = QWidget(self)
        self.indicator.setFixedWidth(3)
        self.indicator.setFixedHeight(18)
        self.indicator.setStyleSheet(f"background: {self.colors['accent']}; border-radius: 1.5px;")
        self.indicator.setVisible(False)

        # Favicon / Icon
        self.fav_lbl = QLabel(self.fav)
        self.fav_lbl.setFixedWidth(18)
        self.fav_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fav_lbl.setStyleSheet(f"color: {self.colors['accent']}; font-size: 13px; background: transparent; border: none;")
        self.fav_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # Title: flexible elided label that adapts to available space without clipping buttons
        self.title_lbl = ElidedLabel(self.title, self)
        self.setToolTip(self.title)
        self.title_lbl.setStyleSheet(f"color: {self.colors['text_muted']}; font-size: 12px; background: transparent; border: none;")

        # Close button with custom crisp icon
        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setToolTip("Close Tab")
        self.close_btn.setAccessibleName("Close Tab")
        self._icons = _get_close_icons()
        if self._icons["png"] and os.path.isfile(self._icons["png"]):
            self.close_btn.setIcon(QIcon(self._icons["png"]))
            self.close_btn.setIconSize(QSize(11, 11))
            self.close_btn.setText("")
        else:
            self.close_btn.setText("✕")
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                color: {self.colors['text_muted']};
                font-size: 11px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton:hover {{
                background: rgba(239, 68, 68, 0.22);
                border: 1px solid rgba(239, 68, 68, 0.35);
                color: #ef4444;
            }}
        """)
        def _cb_enter(e):
            if self._icons["png_hover"] and os.path.isfile(self._icons["png_hover"]):
                self.close_btn.setIcon(QIcon(self._icons["png_hover"]))
        def _cb_leave(e):
            if self._icons["png"] and os.path.isfile(self._icons["png"]):
                self.close_btn.setIcon(QIcon(self._icons["png"]))
        self.close_btn.enterEvent = _cb_enter
        self.close_btn.leaveEvent = _cb_leave

        # Consistent, predictable arrangement in BOTH left and right docked positions
        layout.addWidget(self.indicator, 0)
        layout.addWidget(self.fav_lbl, 0)
        layout.addWidget(self.title_lbl, 1)
        layout.addWidget(self.close_btn, 0)

        self.update_style()

    def update_data(self, fav: str, title: str):
        self.fav = fav
        self.title = title
        self.fav_lbl.setText(self.fav)
        self.title_lbl.setText(self.title)
        self.title_lbl.setToolTip(self.title)

    def set_active(self, active: bool):
        self.is_active = active
        self.indicator.setVisible(active)
        self.update_style()

    def update_style(self):
        c = self.colors
        accent = c.get("accent", "#4f8cff")
        surface_active = c.get("surface_active", c.get("surface_hover", "#2a2f3d"))
        surface_hover = c.get("surface_hover", "#222630")
        text_muted = c.get("text_muted", "#8d95a5")

        if self.is_active:
            self.setStyleSheet(f"""
                VerticalTabRow {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 rgba(210, 225, 255, 0.28), stop:0.12 rgba(119, 145, 202, 0.52),
                        stop:1 rgba(54, 68, 101, 0.52));
                    border-radius: 8px;
                    border: 1px solid rgba(202, 222, 255, 0.48);
                    border-top: 1px solid rgba(255, 255, 255, 0.64);
                }}
            """)
            self.title_lbl.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 600; background: transparent; border: none;")
            self.fav_lbl.setStyleSheet(f"color: {accent}; font-size: 13px; font-weight: bold; background: transparent; border: none;")
            self.indicator.setStyleSheet(f"background: {accent}; border-radius: 1.5px;")
            self.indicator.setVisible(True)
        else:
            self.setStyleSheet(f"""
                VerticalTabRow {{
                    background: transparent;
                    border: 1px solid transparent;
                    border-radius: 7px;
                }}
                VerticalTabRow:hover {{
                    background: rgba(178, 198, 242, 0.15);
                    border: 1px solid rgba(224, 235, 255, 0.24);
                }}
            """)
            self.title_lbl.setStyleSheet(f"color: {text_muted}; font-size: 12px; font-weight: normal; background: transparent; border: none;")
            self.fav_lbl.setStyleSheet(f"color: {text_muted}; font-size: 13px; background: transparent; border: none;")
            self.indicator.setVisible(False)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            parent_tabs = self.parentWidget()
            while parent_tabs and not isinstance(parent_tabs, CATBrowserTabs):
                parent_tabs = parent_tabs.parentWidget()
            if parent_tabs:
                parent_tabs._on_vertical_tab_clicked(self.index)
        elif event.button() == Qt.MouseButton.MiddleButton:
            parent_tabs = self.parentWidget()
            while parent_tabs and not isinstance(parent_tabs, CATBrowserTabs):
                parent_tabs = parent_tabs.parentWidget()
            if parent_tabs:
                parent_tabs._on_vertical_tab_close(self.index)
        super().mousePressEvent(event)


class CATBrowserTabs(QWidget):
    """
    Hybrid Tab Controller for CAT Browser.
    Seamlessly presents:
    - Horizontal tabs in Top or Bottom orientation.
    - Vertical tabs in Left or Right orientation (reference design).
    """

    tabBarClicked = Signal(int)
    tabCloseRequested = Signal(int)
    currentChanged = Signal(int)
    newTabRequested = Signal()
    sidebarResized = Signal(int)

    def __init__(self, colors: Optional[dict] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.colors = dict(colors or _default_colors())
        self._position = "top"
        self._sidebar_width: int = 224
        self._is_resizing_sidebar: bool = False
        self._drag_start_x: int = 0
        self._initial_w: int = 224
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._tabs: list[dict[str, str]] = []  # list of {"text": ..., "fav": ..., "title": ...}
        self._current_index: int = -1
        self._signals_blocked = False

        # Root layout for switching
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        # 1. Horizontal Mode: Native QTabBar with custom styling
        self._h_tab_bar = QTabBar(self)
        self._h_tab_bar.setTabsClosable(True)
        self._h_tab_bar.setExpanding(False)
        self._h_tab_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._h_tab_bar.setUsesScrollButtons(True)
        self._h_tab_bar.setElideMode(Qt.TextElideMode.ElideRight)
        self._h_tab_bar.setDrawBase(False)
        self._h_tab_bar.tabBarClicked.connect(self._on_h_tab_clicked)
        self._h_tab_bar.tabCloseRequested.connect(self._on_h_tab_close_requested)
        try:
            self._h_tab_bar.currentChanged.connect(self._on_h_current_changed)
        except Exception:
            pass
        self._h_tab_bar.installEventFilter(self)
        self._root_layout.addWidget(self._h_tab_bar)

        # 2. Vertical Mode: Container holding sidebar header and scroll area
        self._v_widget = QWidget(self)
        self._v_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._v_layout = QVBoxLayout(self._v_widget)
        self._v_layout.setContentsMargins(0, 0, 0, 0)
        self._v_layout.setSpacing(0)

        # Header for Vertical sidebar ("TABS" + count + "+" new tab button)
        self._v_header = QWidget(self._v_widget)
        self._v_header.setFixedHeight(36)
        vh_lay = QHBoxLayout(self._v_header)
        vh_lay.setContentsMargins(12, 6, 8, 6)
        vh_lay.setSpacing(8)

        self._v_title_lbl = QLabel("TABS")
        self._v_title_lbl.setStyleSheet(f"color: {self.colors['text_muted']}; font-size: 11px; font-weight: 800; letter-spacing: 1.5px; background: transparent; border: none;")
        vh_lay.addWidget(self._v_title_lbl, 0)

        self._v_count_badge = QLabel("0")
        self._v_count_badge.setStyleSheet(f"background: rgba(255, 255, 255, 0.08); color: {self.colors['text_muted']}; border-radius: 4px; padding: 1px 6px; font-size: 10px; font-weight: 700; border: none;")
        vh_lay.addWidget(self._v_count_badge, 0)

        vh_lay.addStretch(1)

        self._v_add_btn = QPushButton("+")
        self._v_add_btn.setFixedSize(22, 22)
        self._v_add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._v_add_btn.setToolTip("New tab (Ctrl+T)")
        self._v_add_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.08);
                color: {self.colors['text']};
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton:hover {{
                background: {self.colors['accent']};
                color: #ffffff;
                border: 1px solid {self.colors['accent']};
            }}
        """)
        self._v_add_btn.clicked.connect(lambda: self.newTabRequested.emit())
        vh_lay.addWidget(self._v_add_btn, 0)

        self._v_layout.addWidget(self._v_header, 0)

        # QScrollArea holding stacked VerticalTabRow items
        self._v_scroll = QScrollArea(self._v_widget)
        self._v_scroll.setWidgetResizable(True)
        self._v_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._v_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._v_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._v_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                width: 5px;
                background: transparent;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.15);
                border-radius: 2px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.3);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        self._v_container = QWidget()
        self._v_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._v_container.setStyleSheet("background: transparent;")
        self._v_row_layout = QVBoxLayout(self._v_container)
        self._v_row_layout.setContentsMargins(8, 6, 8, 6)
        self._v_row_layout.setSpacing(4)
        self._v_row_layout.setSpacing(3)
        self._v_row_layout.addStretch(1)  # Spacer at bottom
        self._v_scroll.setWidget(self._v_container)

        self._v_layout.addWidget(self._v_scroll, 1)
        self._root_layout.addWidget(self._v_widget)

        self._v_rows: list[VerticalTabRow] = []

        # Initial view sync
        self._sync_view_mode()
        self._update_styles()

    def set_theme(self, colors: dict):
        self.colors.update(colors)
        self._update_styles()
        for row in self._v_rows:
            row.colors = self.colors
            row.update_style()

    def set_position(self, pos: str):
        if pos not in ("top", "bottom", "left", "right"):
            pos = "top"
        if self._position == pos:
            return
        self._position = pos
        for row in self._v_rows:
            row.pos = pos
            row.update_style()
        self._sync_view_mode()
        self._update_styles()

    @property
    def is_vertical(self) -> bool:
        return self._position in ("left", "right")

    @property
    def position(self) -> str:
        return self._position

    @property
    def vertical_rows(self) -> list[VerticalTabRow]:
        return list(self._v_rows)

    @property
    def sidebar_width(self) -> int:
        return self._sidebar_width

    def set_sidebar_width(self, width: int):
        self._sidebar_width = max(140, min(480, int(width)))
        if self.is_vertical:
            # Keep the width flexible so the enclosing QSplitter can drag it.
            self.setMinimumWidth(140)
            self.setMaximumWidth(480)
            self.update()

    def setPosition(self, pos: str):
        self.set_position(pos)

    def setShape(self, shape):
        """No-op stub for code calling QTabBar.setShape."""
        pass

    def _is_on_resize_handle(self, pt_or_x) -> bool:
        if not self.is_vertical:
            return False
        if hasattr(pt_or_x, "x"):
            x = pt_or_x.x()
        else:
            x = float(pt_or_x)
        margin = 8
        if self._position == "left":
            return x >= (self.width() - margin)
        elif self._position == "right":
            return x <= margin
        return False

    @property
    def _is_resizing(self) -> bool:
        return getattr(self, "_is_resizing_sidebar", False)

    @_is_resizing.setter
    def _is_resizing(self, val: bool):
        self._is_resizing_sidebar = val

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.is_vertical:
            try:
                lx = event.position().x()
            except Exception:
                lx = event.x()
            try:
                gp = event.globalPosition()
                gx = gp.x()
            except Exception:
                try:
                    gx = event.globalPos().x()
                except Exception:
                    gx = lx
            if self._is_on_resize_handle(lx):
                self._is_resizing_sidebar = True
                self._drag_start_lx = lx
                self._drag_start_gx = gx
                self._initial_w = self.width()
                self.update()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.is_vertical:
            try:
                lx = event.position().x()
            except Exception:
                lx = event.x()
            try:
                gp = event.globalPosition()
                gx = gp.x()
            except Exception:
                try:
                    gx = event.globalPos().x()
                except Exception:
                    gx = lx

            if getattr(self, "_is_resizing_sidebar", False):
                start_gx = getattr(self, "_drag_start_gx", gx)
                start_lx = getattr(self, "_drag_start_lx", lx)
                if abs(gx - start_gx) > 0.001:
                    delta = (gx - start_gx) if self._position == "left" else (start_gx - gx)
                else:
                    delta = (lx - start_lx) if self._position == "left" else (start_lx - lx)

                new_w = max(140, min(int(self._initial_w + delta), 480))
                self.set_sidebar_width(new_w)
                self.sidebarResized.emit(new_w)
                self.update()
                event.accept()
                return
            elif self._is_on_resize_handle(lx):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                event.accept()
                return
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if getattr(self, "_is_resizing_sidebar", False):
            self._is_resizing_sidebar = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.sidebarResized.emit(self._sidebar_width)
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if self.is_vertical and event.button() == Qt.MouseButton.LeftButton:
            try:
                lx = event.position().x()
            except Exception:
                lx = event.x()
            if self._is_on_resize_handle(lx):
                self._sidebar_width = 150 if self.width() > 190 else 224
                self.set_sidebar_width(self._sidebar_width)
                self.sidebarResized.emit(self._sidebar_width)
                self.update()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def eventFilter(self, watched, event):
        try:
            from PySide6.QtCore import QEvent
        except ImportError:
            try:
                from PyQt6.QtCore import QEvent  # type: ignore
            except ImportError:
                QEvent = None
        if QEvent and watched is self._h_tab_bar and event.type() == QEvent.Type.Wheel:
            try:
                delta = event.angleDelta().y() or event.angleDelta().x()
                if delta != 0:
                    cur = self.currentIndex()
                    new_idx = cur - 1 if delta > 0 else cur + 1
                    if 0 <= new_idx < self.count():
                        self.setCurrentIndex(new_idx)
                    event.accept()
                    return True
            except Exception:
                pass
        return super().eventFilter(watched, event)

    def _sync_view_mode(self):
        is_vert = self._position in ("left", "right")
        self._h_tab_bar.setVisible(not is_vert)
        self._v_widget.setVisible(is_vert)
        self._v_scroll.setVisible(is_vert)
        if is_vert:
            self._h_tab_bar.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
            self._v_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
            # A fixed width disables QSplitter's native resize handle.
            # The sidebar width is instead bounded and initialized by the host.
            self.setMinimumWidth(140)
            self.setMaximumWidth(480)
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
            self._v_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            if self._position == "left":
                self._v_layout.setContentsMargins(0, 0, 4, 0)
            else:
                self._v_layout.setContentsMargins(4, 0, 0, 0)
        else:
            self._v_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
            self._h_tab_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.setFixedHeight(36)
            self.setMinimumWidth(0)
            self.setMaximumWidth(16777215)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._v_layout.setContentsMargins(0, 0, 0, 0)
            self._v_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

    def _update_styles(self):
        c = self.colors
        pos = self._position
        bg = c.get("bg", "#0e1018")
        surface = c.get("surface", "#161a26")
        surface_hover = c.get("surface_hover", "#202638")
        accent = c.get("accent", "#4f8cff")
        text = c.get("text", "#f1f5f9")
        text_muted = c.get("text_muted", "#94a3b8")

        icons = _get_close_icons()
        close_img = icons["png"] if os.path.isfile(icons["png"]) else ""
        close_hov = icons["png_hover"] if os.path.isfile(icons["png_hover"]) else ""
        close_css = f"image: url('{close_img}');" if close_img else ""
        close_hov_css = f"image: url('{close_hov}');" if close_hov else ""

        # Container styling — Liquid Glass translucent surface with reflective borders
        if pos == "left":
            self.setStyleSheet(f"""
                CATBrowserTabs {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(106, 130, 183, 0.62), stop:0.07 rgba(48, 59, 85, 0.60), stop:1 rgba(22, 28, 43, 0.58));
                    border-right: 1px solid rgba(225, 236, 255, 0.30);
                    border-left: 1px solid rgba(255, 255, 255, 0.10);
                    border-left: none;
                    border-top: none;
                    border-bottom: none;
                }}
            """)
            self._v_widget.setStyleSheet("background: transparent; border: none;")
            self._v_header.setStyleSheet("border-bottom: 1px solid rgba(255, 255, 255, 0.07); background: transparent;")
        elif pos == "right":
            self.setStyleSheet(f"""
                CATBrowserTabs {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(22, 28, 43, 0.58), stop:0.93 rgba(48, 59, 85, 0.60), stop:1 rgba(106, 130, 183, 0.62));
                    border-left: 1px solid rgba(225, 236, 255, 0.30);
                    border-right: 1px solid rgba(255, 255, 255, 0.10);
                    border-right: none;
                    border-top: none;
                    border-bottom: none;
                }}
            """)
            self._v_widget.setStyleSheet("background: transparent; border: none;")
            self._v_header.setStyleSheet("border-bottom: 1px solid rgba(255, 255, 255, 0.07); background: transparent;")
        elif pos == "bottom":
            self.setStyleSheet("CATBrowserTabs { background: rgba(24, 29, 44, 0.54); border-top: 1px solid rgba(225, 235, 255, 0.18); border-left: none; border-right: none; border-bottom: none; }")
            self._v_widget.setStyleSheet("background: transparent; border: none;")
        else:  # top
            self.setStyleSheet("CATBrowserTabs { background: rgba(24, 29, 44, 0.54); border-bottom: 1px solid rgba(225, 235, 255, 0.18); border-left: none; border-right: none; border-top: none; }")
            self._v_widget.setStyleSheet("background: transparent; border: none;")

        scroller_css = f"""
            QTabBar::scroller {{ width: 20px; }}
            QTabBar QToolButton {{
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                color: {text};
                margin: 2px;
            }}
            QTabBar QToolButton:hover {{
                background: {surface_hover};
                border-color: {accent};
                color: #ffffff;
            }}
        """

        if pos == "bottom":
            self._h_tab_bar.setStyleSheet(f"""
                QTabBar {{ background: transparent; }}
                {scroller_css}
                QTabBar::tab {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 255, 255, 0.03), stop:1 rgba(255, 255, 255, 0.06));
                    color: {c['text_muted']};
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-top: none;
                    border-radius: 0 0 8px 8px;
                    padding: 5px 14px 5px 12px;
                    margin-right: 4px;
                    min-width: 90px;
                    max-width: 280px;
                    font-size: 12px;
                    font-weight: 500;
                }}
                QTabBar::tab:selected {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {surface}, stop:0.92 rgba(26, 29, 36, 0.95), stop:1 rgba(79, 140, 255, 0.25));
                    color: #ffffff;
                    border: 1px solid rgba(79, 140, 255, 0.45);
                    border-bottom: 2.5px solid {accent};
                    font-weight: 600;
                }}
                QTabBar::tab:hover:!selected {{
                    background: {surface_hover};
                    color: {text};
                    border: 1px solid rgba(255, 255, 255, 0.15);
                }}
                QTabBar::close-button {{
                    {close_css}
                    subcontrol-position: right;
                    subcontrol-origin: padding;
                    width: 14px;
                    height: 14px;
                    margin-right: 4px;
                    padding: 2px;
                    border-radius: 4px;
                    background: transparent;
                }}
                QTabBar::close-button:hover {{
                    {close_hov_css}
                    background: rgba(239, 68, 68, 0.25);
                }}
            """)
        else:
            # Top
            self._h_tab_bar.setStyleSheet(f"""
                QTabBar {{ background: transparent; }}
                {scroller_css}
                QTabBar::tab {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 255, 255, 0.07), stop:0.08 rgba(255, 255, 255, 0.03), stop:1 rgba(20, 24, 34, 0.6));
                    color: {c['text_muted']};
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-top: 1px solid rgba(255, 255, 255, 0.15);
                    border-bottom: none;
                    border-radius: 8px 8px 0 0;
                    padding: 5px 14px 5px 12px;
                    margin-right: 4px;
                    min-width: 90px;
                    max-width: 280px;
                    font-size: 12px;
                    font-weight: 500;
                }}
                QTabBar::tab:selected {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 255, 255, 0.22), stop:0.08 rgba(105, 128, 183, 0.55), stop:0.92 rgba(52, 67, 102, 0.52), stop:1 rgba(38, 49, 76, 0.50));
                    color: #ffffff;
                    border: 1px solid rgba(156, 190, 255, 0.66);
                    border-top: 2.5px solid {accent};
                    font-weight: 600;
                }}
                QTabBar::tab:hover:!selected {{
                    background: {surface_hover};
                    color: {text};
                    border: 1px solid rgba(255, 255, 255, 0.16);
                }}
                QTabBar::close-button {{
                    {close_css}
                    subcontrol-position: right;
                    subcontrol-origin: padding;
                    width: 14px;
                    height: 14px;
                    margin-right: 4px;
                    padding: 2px;
                    border-radius: 4px;
                    background: transparent;
                }}
                QTabBar::close-button:hover {{
                    {close_hov_css}
                    background: rgba(239, 68, 68, 0.25);
                }}
            """)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)

        # Draw subtle liquid-glass resize handle indicator on boundary edge
        if self.is_vertical:
            accent_hex = self.colors.get("accent", "#4f8cff")
            is_active = getattr(self, "_is_resizing_sidebar", False)
            handle_x = (self.width() - 1) if self._position == "left" else 0
            if is_active:
                p.setPen(QColor(accent_hex))
                p.drawLine(handle_x, 0, handle_x, self.height())
            else:
                p.setPen(QColor(255, 255, 255, 20))
                p.drawLine(handle_x, 0, handle_x, self.height())
        p.end()
        super().paintEvent(event)

    @staticmethod
    def _parse_text(raw: str) -> tuple[str, str]:
        s = raw.strip()
        parts = s.split("  ", 1)
        if len(parts) == 2 and len(parts[0]) <= 3:
            return parts[0].strip(), parts[1].strip()
        if len(s) > 2 and s[1] == " ":
            return s[0], s[2:].strip()
        return "○", s

    # -------------------------------------------------------------------------
    # QTabBar Compatible API
    # -------------------------------------------------------------------------
    def count(self) -> int:
        return len(self._tabs)

    def currentIndex(self) -> int:
        return self._current_index

    def setCurrentIndex(self, idx: int):
        if not (0 <= idx < len(self._tabs)):
            idx = -1
        prev = self._current_index
        self._current_index = idx

        # Sync horizontal bar
        if self._h_tab_bar.currentIndex() != idx:
            self._h_tab_bar.blockSignals(True)
            self._h_tab_bar.setCurrentIndex(idx)
            self._h_tab_bar.blockSignals(False)

        # Update only the old/new active rows. Restyling every sidebar tab on
        # each switch makes large sessions increasingly sluggish.
        if 0 <= prev < len(self._v_rows) and prev != idx:
            self._v_rows[prev].set_active(False)
        if 0 <= idx < len(self._v_rows):
            self._v_rows[idx].set_active(True)

        if idx >= 0 and idx < len(self._v_rows) and self._position in ("left", "right"):
            self._v_scroll.ensureWidgetVisible(self._v_rows[idx])

        if not self._signals_blocked and prev != idx and idx >= 0:
            self.currentChanged.emit(idx)

    def addTab(self, text: str) -> int:
        idx = len(self._tabs)
        fav, title = self._parse_text(text)
        self._tabs.append({"text": text, "fav": fav, "title": title})

        # Add to horizontal tab bar
        self._h_tab_bar.blockSignals(True)
        self._h_tab_bar.addTab(text)
        self._h_tab_bar.blockSignals(False)

        # Add to vertical sidebar
        row = VerticalTabRow(idx, fav, title, self.colors, self._position, self._v_container)
        row.close_btn.clicked.connect(lambda chk=False, r=row: self._on_vertical_tab_close(r.index))
        # Insert before stretch spacer
        self._v_row_layout.insertWidget(idx, row)
        self._v_rows.append(row)
        if self.is_vertical:
            row.show()

        self._v_count_badge.setText(str(len(self._tabs)))

        if self._current_index < 0:
            self.setCurrentIndex(0)
        return idx

    def insertTab(self, idx: int, text: str) -> int:
        fav, title = self._parse_text(text)
        idx = max(0, min(idx, len(self._tabs)))
        self._tabs.insert(idx, {"text": text, "fav": fav, "title": title})

        self._h_tab_bar.blockSignals(True)
        self._h_tab_bar.insertTab(idx, text)
        self._h_tab_bar.blockSignals(False)

        row = VerticalTabRow(idx, fav, title, self.colors, self._position, self._v_container)
        row.close_btn.clicked.connect(lambda chk=False, r=row: self._on_vertical_tab_close(r.index))
        self._v_row_layout.insertWidget(idx, row)
        self._v_rows.insert(idx, row)
        self._rebind_vertical_indices()
        if self.is_vertical:
            row.show()

        self._v_count_badge.setText(str(len(self._tabs)))
        return idx

    def removeTab(self, idx: int):
        if not (0 <= idx < len(self._tabs)):
            return
        self._tabs.pop(idx)

        self._h_tab_bar.blockSignals(True)
        self._h_tab_bar.removeTab(idx)
        self._h_tab_bar.blockSignals(False)

        row = self._v_rows.pop(idx)
        self._v_row_layout.removeWidget(row)
        row.deleteLater()
        self._rebind_vertical_indices()

        self._v_count_badge.setText(str(len(self._tabs)))

        # Update current index
        if len(self._tabs) == 0:
            self.setCurrentIndex(-1)
        elif self._current_index >= len(self._tabs):
            self.setCurrentIndex(len(self._tabs) - 1)
        elif self._current_index == idx:
            self.setCurrentIndex(min(idx, len(self._tabs) - 1))

    def setTabText(self, idx: int, text: str):
        if not (0 <= idx < len(self._tabs)):
            return
        fav, title = self._parse_text(text)
        self._tabs[idx] = {"text": text, "fav": fav, "title": title}

        self._h_tab_bar.blockSignals(True)
        self._h_tab_bar.setTabText(idx, text)
        self._h_tab_bar.blockSignals(False)

        if idx < len(self._v_rows):
            self._v_rows[idx].update_data(fav, title)

    def tabText(self, idx: int) -> str:
        if 0 <= idx < len(self._tabs):
            return self._tabs[idx]["text"]
        return ""

    def pos_name(self) -> str:
        return self._position

    def _rebind_vertical_indices(self):
        for i, row in enumerate(self._v_rows):
            row.index = i
            try:
                row.close_btn.clicked.disconnect()
            except Exception:
                pass
            row.close_btn.clicked.connect(lambda chk=False, r=row: self._on_vertical_tab_close(r.index))

    def blockSignals(self, b: bool) -> bool:
        prev = self._signals_blocked
        self._signals_blocked = b
        self._h_tab_bar.blockSignals(b)
        return prev

    # -------------------------------------------------------------------------
    # Internal Event Routing
    # -------------------------------------------------------------------------
    def _on_h_tab_clicked(self, idx: int):
        self.setCurrentIndex(idx)
        if not self._signals_blocked:
            self.tabBarClicked.emit(idx)

    def _on_h_tab_close_requested(self, idx: int):
        if not self._signals_blocked:
            self.tabCloseRequested.emit(idx)

    def _on_h_current_changed(self, idx: int):
        if not self._signals_blocked and idx != self._current_index:
            self.setCurrentIndex(idx)

    def _on_vertical_tab_clicked(self, idx: int):
        self.setCurrentIndex(idx)
        if not self._signals_blocked:
            self.tabBarClicked.emit(idx)

    def _on_vertical_tab_close(self, idx: int):
        if not self._signals_blocked:
            self.tabCloseRequested.emit(idx)
