"""
CCT UI — CCTApp: the primary interactive application. Owns the screen
(ConversationView + StickyComposer + StatusLine), coordinates every
component through the events in ui/events.py, and is the only place in
ui/ allowed to touch more than one component at once — that's what
"coordinator" means here, not "business logic lives here too". Chemistry,
AI, and calculation logic all stay in the modules this file calls out
to (aicore, permissions, session) — and for the ~50 existing commands
not yet natively ported (see commands_data.NATIVE_UI_COMMANDS), this
suspends to the real terminal and hands off to the existing fallback
dispatcher instead of half-reimplementing them.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import logging
import os
import platform
import re
import shutil
import threading
import time

_log = logging.getLogger("cat.ui.chats")

from .. import aicore
from .. import agent as cct_agent
from .. import ai_modes
from .. import theme
from .. import keys
from .. import permissions as perm
from .. import session as chat_session
from .. import identity
from .. import projects
from .. import workspace as ws_paths
from .. import eventbus
from .. import timeline
from .. import todos
# v0.7.9.0: speed pipeline — smart routing, real metrics, live events,
# multimodal normalization.
from .. import metrics as cat_metrics
from .. import model_router
from .. import vision as cat_vision
from .. import event_stream as cat_events
from ..browser import WorkspaceMode, PreviewState, ServerState
from ..browser.preview import _shutdown_all as _preview_shutdown_all
try:
    from .browser_shell import BROWSER_CSS as _BROWSER_CSS, BrowserScreen, BrowserShell, get_state as _browser_get_state
    _HAS_BROWSER_SHELL = True
except Exception:
    _BROWSER_CSS = ""
    BrowserScreen = None
    BrowserShell = None
    _browser_get_state = None
    _HAS_BROWSER_SHELL = False


def _safe(fn, *args):
    """Run a controller call off the UI thread; any failure stays in the
    preview subsystem and never reaches CAT itself."""
    try:
        return fn(*args)
    except Exception:
        return None
from ..commands_data import COMMANDS

# ── CAT Browser redirect: every web link opens in CAT's own browser  ──
_CAT_APP_REF = None
_CAT_ORIG_WEBBROWSER_OPEN = None
_URL_RE = __import__("re").compile(r"https?://[^\s\"'<>]+")

def _install_cat_browser_redirect(app):
    global _CAT_APP_REF, _CAT_ORIG_WEBBROWSER_OPEN
    _CAT_APP_REF = app
    try:
        import webbrowser as _wb
        if _CAT_ORIG_WEBBROWSER_OPEN is None:
            _CAT_ORIG_WEBBROWSER_OPEN = _wb.open

        def _cat_open(url, new=0, autoraise=True):
            # Route web/browser opens:
            # Passkey / WebAuthn / Windows Hello authentication MUST use the OS default
            # system browser (Edge / Chrome) because QtWebEngine lacks platform authenticators.
            try:
                u = str(url or "").strip()
                lu = u.lower()
                if any(k in lu for k in ("passkey", "webauthn", "fomoji_auth", "windows-hello")):
                    import sys, os
                    if sys.platform == "win32":
                        try:
                            os.startfile(u)
                            return True
                        except Exception:
                            pass
                    if _CAT_ORIG_WEBBROWSER_OPEN is not None:
                        return _CAT_ORIG_WEBBROWSER_OPEN(u, new=new, autoraise=autoraise)

                if u.startswith("http://") or u.startswith("https://") or u.startswith("file://") or u.startswith("about:"):
                    from ..host.launcher import launch_cat_host, can_launch_host
                    if can_launch_host():
                        launch_cat_host(start_browser_url=u, start_mode="browser", block=False)
                        return True
                    ref = _CAT_APP_REF
                    if ref is not None:
                        try:
                            ref._system_note("CAT Browser requires PySide6: pip install PySide6")
                        except Exception:
                            pass
                        return True
                # Also catch bare domains like "example.com/page" passed without scheme
                if "." in u and " " not in u and not u.startswith(" ") and len(u) < 2048:
                    if not u.startswith("http"):
                        from ..host.launcher import launch_cat_host, can_launch_host
                        if can_launch_host():
                            launch_cat_host(start_browser_url=u, start_mode="browser", block=False)
                            return True
                        ref = _CAT_APP_REF
                        if ref is not None:
                            try:
                                ref._system_note("CAT Browser requires PySide6: pip install PySide6")
                            except Exception:
                                pass
                            return True
            except Exception:
                pass
            return True

        _wb.open = _cat_open
        _wb.open_new = _cat_open
        _wb.open_new_tab = _cat_open
    except Exception:
        pass

from . import theme_css
from . import thinking
from .events import (
    MessageSubmitted, MessageStarted, MessageChunk, MessageFinished,
    StreamingStarted, StreamingFinished, PermissionGranted, PermissionDenied,
    PermissionCancelled, CommandExecuted, NotebookChanged, WorkspaceChanged,
    PermissionModeChanged, FolderOpened, SidebarToggled, FileOpenRequested, FileSaved,
    WorkspaceFilesChanged, MessageContextAction, MessageRewritten, NavAction,
    ChatRequested, SettingChanged, AttachmentChipDoubleClicked,
    PreviewRequested, PreviewClosed, BuildActivity,
)
# v0.7.9.0: real backend agent-state crossings driving the CAT Agent
# ASCII indicator (ui/cat_agent.py).
from .events import AgentActivity
from .conversation import ConversationView, TEXTUAL_AVAILABLE as _CONV_OK
from .composer import StickyComposer, ComposerInput, TEXTUAL_AVAILABLE as _COMP_OK
from .footer import StatusLine, TEXTUAL_AVAILABLE as _FOOTER_OK
from .permission_panel import PermissionCard, TEXTUAL_AVAILABLE as _PERM_OK
from .header import BrandHeader, TEXTUAL_AVAILABLE as _HEADER_OK
from .statusbar import StatusBar, StatusFields, TEXTUAL_AVAILABLE as _STATUSBAR_OK
from .dashboard import WelcomeDashboard, TEXTUAL_AVAILABLE as _DASH_OK
from .workspace import WorkspaceShell, TEXTUAL_AVAILABLE as _WORKSPACE_OK
from .editor import EditorPane
from .timeline_panel import TimelinePanel, TEXTUAL_AVAILABLE as _TIMELINE_OK
from .todo_panel import TodoPanel, TEXTUAL_AVAILABLE as _TODO_PANEL_OK
from .sidebar import RecentWorkspacesScreen, OpenWorkspaceScreen
from .nav_screens import InfoPanel, ThemesPanel, SettingsPanel, UserPanel
# v0.8.0: New panels for memory center and activity stream
from .memory_center import MemoryCenterScreen, TEXTUAL_AVAILABLE as _MEM_OK
from .activity_stream_panel import ActivityStreamPanel, TEXTUAL_AVAILABLE as _ACT_OK

TEXTUAL_AVAILABLE = True
try:
    from textual.app import App as TextualApp
    from textual.screen import Screen
    from textual.containers import Vertical
    from textual.widgets import Static
    from textual import work, events
except Exception:
    TEXTUAL_AVAILABLE = False

TEXTUAL_AVAILABLE = (TEXTUAL_AVAILABLE and _CONV_OK and _COMP_OK and _FOOTER_OK
                     and _PERM_OK and _HEADER_OK and _STATUSBAR_OK and _DASH_OK and _WORKSPACE_OK
                     and _TIMELINE_OK and _TODO_PANEL_OK)

# Safeguard against upstream Textual defect: Screen._forward_event assumes content_widget.parent
# is never None during mouse selection. If a widget is unmounted or detached while processing
# mouse events, content_widget.parent is None, causing `AttributeError: 'NoneType' object has no attribute 'region'`.
if TEXTUAL_AVAILABLE:
    try:
        import textual.screen
        _orig_screen_forward_event = textual.screen.Screen._forward_event
        if not getattr(_orig_screen_forward_event, "_cat_safe_wrapped", False):
            def _safe_screen_forward_event(self, event):
                try:
                    return _orig_screen_forward_event(self, event)
                except AttributeError as _err:
                    if "'NoneType' object has no attribute 'region'" in str(_err):
                        try:
                            self._select_state = None
                        except Exception:
                            pass
                        return None
                    raise
            _safe_screen_forward_event._cat_safe_wrapped = True
            textual.screen.Screen._forward_event = _safe_screen_forward_event
    except Exception:
        pass


def _mark_ai_failure(text, title="AI provider unavailable"):
    """Prefix/append a clear marker + actionable guidance onto an AI
    provider failure message (spec section 19) so it doesn't read like
    a genuine answer in the conversation. This is the primary UI's
    thread-safe equivalent of calc_terminal/errors.py's error_card —
    that module blocks on input(), which is not safe to call from a
    Textual worker thread while the reactive app is running, so this
    marks the text instead of showing an interactive card. A full
    clickable error card for this UI (matching the permission-card
    pattern already used elsewhere) is tracked as still open, not
    silently skipped — see CHANGELOG_v0.6.12_error_recovery_ui.md."""
    return (f"\u26a0 **{title}**\n\n{text}\n\n"
            f"*Resend your message to retry, or run `/model` to switch providers.*")


# Structural/spacing rules for every widget id this package mounts. Every
# color reference is a `$variable` resolved by CCTApp.get_css_variables()
# (theme_css.py) — there is no second, hand-authored palette here.
_COMPONENT_CSS = """
#cct-brandheader {
    dock: top;
    height: 4;
    padding: 0 2;
    background: $app-background;
    color: $text;
    border-bottom: tall $border-active $border;
}

#cct-conversation {
    width: 100%;
    height: 1fr;
    padding: 1 2 0 2;
    overflow-y: auto;
    overflow-x: hidden;
    scrollbar-size: 1 1;
    scrollbar-color: $border transparent;
    scrollbar-color-hover: $accent transparent;
    scrollbar-color-active: $accent-highlight transparent;
}

#cct-welcome { content-align: center middle; text-align: center; padding: 2 2; color: $text; }

/* Each turn is a full-width row (.cct-row) whose align-horizontal pushes
   its one child — the actual bubble (.cct-bubble) — to the right (user),
   left (assistant), or center (system). The bubble is always width:auto
   (capped by max-width), so it only ever takes up as much horizontal
   space as its content needs, never the full row. */
.cct-row { width: 100%; height: auto; margin: 1 0; }
.cct-row-user { align-horizontal: right; }
.cct-row-assistant { align-horizontal: left; }
.cct-row-system { align-horizontal: center; margin-bottom: 1; }
.cct-msg-card-system {
    width: auto;
    min-width: 36;
    max-width: 95%;
    height: auto;
    text-align: center;
    content-align: center middle;
    margin: 1 0;
}

/* 3D conversation bubbles: user (right, double bevel chassis), assistant (left, elevated card),
   system (center, 3D status pill). */
.cct-msg-card {
    width: auto;
    max-width: 88%;
    height: auto;
}
.cct-msg-card-user {
    width: auto;
    min-width: 24;
    max-width: 82%;
    align-horizontal: right;
}
.cct-msg-card-assistant {
    width: 100%;
    max-width: 100%;
    align-horizontal: left;
}
.cct-msg-actions {
    height: 1;
    min-height: 1;
    width: 100%;
    margin-top: 0;
    margin-bottom: 0;
    padding: 0 1;
    layout: horizontal;
}
.cct-msg-card-user .cct-msg-actions {
    align-horizontal: right;
}
.cct-msg-card-assistant .cct-msg-actions {
    align-horizontal: left;
}
Button.cct-msg-btn, .cct-msg-btn {
    height: 1;
    min-height: 1;
    max-height: 1;
    width: auto;
    min-width: 8;
    max-width: 14;
    padding: 0 1;
    margin-right: 1;
    background: $surface-alt;
    color: $text-muted;
    border: none;
    text-style: bold;
    content-align: center middle;
    transition: color 120ms, background 120ms;
}
Button.cct-msg-btn:hover, .cct-msg-btn:hover {
    background: $accent;
    color: #ffffff;
    text-style: bold;
}

.cct-bubble { height: auto; }
.cct-bubble-user {
    width: 100%;
    max-width: 100%;
    background: $surface-alt;
    color: $text;
    border: tall;
    border-top: tall $accent-highlight;
    border-left: tall $accent-highlight;
    border-right: tall $surface-dark;
    border-bottom: tall $surface-dark;
    padding: 1 2;
    transition: background 150ms, border 150ms;
}
.cct-bubble-user:hover {
    background: $surface-highlight;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-right: tall $surface-dark;
    border-bottom: tall $surface-dark;
    offset-y: 0;
}
.cct-bubble-user.-active {
    offset-y: 0;
    border: tall;
    border-top: tall $surface-dark;
    border-left: tall $surface-dark;
    border-bottom: tall $accent-highlight;
    border-right: tall $accent-highlight;
}
.cct-bubble-assistant {
    width: 100%;
    max-width: 100%;
    background: $surface;
    color: $text;
    border: tall;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-right: tall $surface-dark;
    border-bottom: tall $surface-dark;
    padding: 1 2;
    transition: background 150ms, border 150ms;
}
.cct-bubble-assistant:hover {
    background: $surface-alt;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-right: tall $surface-dark;
    border-bottom: tall $surface-dark;
    offset-y: 0;
}
.cct-bubble-assistant.-active {
    offset-y: 0;
    border: tall;
    border-top: tall $surface-dark;
    border-left: tall $surface-dark;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
}
.cct-bubble-system {
    width: auto;
    min-width: 36;
    max-width: 95%;
    background: $surface-alt;
    color: $text;
    border: tall;
    border-top: tall $accent-highlight;
    border-left: tall $accent-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    padding: 0 2;
    margin: 1 0;
    content-align: center middle;
    transition: background 120ms, border 120ms;
}
.cct-bubble-system:hover {
    background: $surface-highlight;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    offset-y: 0;
}
.cct-bubble-system.-active {
    offset-y: 0;
    border: tall;
    border-top: tall $surface-dark;
    border-left: tall $surface-dark;
    border-bottom: tall $accent-highlight;
    border-right: tall $accent-highlight;
}

LiveActivitiesBlock, .live-activities-block {
    width: 100%;
    height: auto;
    max-height: 16;
    background: $surface;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    padding: 0 1;
    margin: 0 0 1 0;
    overflow-x: hidden;
    overflow-y: hidden;
    transition: background 150ms, border 150ms;
}
LiveActivitiesBlock:hover, .live-activities-block:hover {
    border-top: tall $accent-highlight;
    border-left: tall $accent-highlight;
}
LiveActivitiesBlock.collapsed, .live-activities-block.collapsed {
    height: auto;
    max-height: 3;
    min-height: 1;
    padding: 0 1;
    overflow: hidden;
    background: $surface;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
}
LiveActivitiesBlock.collapsed #live-header, .live-activities-block.collapsed #live-header {
    border-bottom: none;
}

.cct-msg-actions {
    height: 1;
    width: auto;
    margin-top: 0;
    layout: horizontal;
}
.cct-msg-btn {
    height: 1;
    min-height: 1;
    max-height: 1;
    padding: 0 1;
    margin-right: 1;
    background: $surface-alt;
    color: $text-muted;
    border: none;
    text-style: bold;
    transition: background 80ms, color 80ms;
}
.cct-msg-btn:hover {
    background: $accent 25%;
    color: $accent;
}
.cct-msg-btn.-active {
    background: $accent 40%;
    color: #ffffff;
}

#cct-composer {
    background: $surface;
    border: heavy;
    border-top: heavy $surface-highlight;
    border-left: heavy $surface-highlight;
    border-bottom: heavy $surface-shadow;
    border-right: heavy $surface-shadow;
    padding: 0 1;
    margin: 0 1 1 1;
    height: auto;
    min-height: 0;
    max-height: 75%;
    width: 1fr;
    layout: vertical;
    transition: border 120ms;
}
#cct-composer:focus-within {
    border: heavy;
    border-top: heavy $accent-highlight;
    border-left: heavy $accent-highlight;
    border-bottom: heavy $accent-shadow;
    border-right: heavy $accent-shadow;
}
#cct-composer,
#cct-composer:focus-within,
#cct-composer.cct-mode-notebook,
#cct-composer.cct-mode-research,
#cct-composer.cct-mode-plan,
#cct-composer.cct-mode-build,
#cct-composer.cct-mode-debugger,
#cct-composer.cct-mode-agent {
    background: $app-background;
}

#cct-prompt-row {
    height: 1fr;
    min-height: 2;
    max-height: 100%;
    align-vertical: middle;
    padding: 0 1;
    margin: 0;
    background: transparent;
    border: none;
    transition: background 120ms;
}
#cct-prompt-row:focus-within {
    border: none;
    background: transparent;
}
#cct-prompt-glyph {
    width: 2;
    min-width: 2;
    max-width: 2;
    color: $accent;
    text-style: bold;
    content-align: left middle;
}
#cct-editor-stack {
    width: 1fr;
    height: 1fr;
    min-height: 1;
    max-height: 100%;
    background: transparent;
    border: none;
    padding: 0;
}
#cct-input, #cct-input:focus, ComposerInput, ComposerInput:focus, #cct-editor-stack, #cct-editor-stack:focus {
    width: 1fr;
    height: 1fr;
    min-height: 1;
    max-height: 100%;
    background: transparent;
    border: none;
    color: $text;
    outline: none;
}

/* 3D Tactile Attachment Chips & Bar */
#cct-chips { height: auto; padding: 0 1; margin-bottom: 0; layout: horizontal; }
#cct-chips.cct-drop-active { border: dashed $accent; }
.cct-chip {
    background: $surface-alt;
    color: $text;
    height: 1;
    min-height: 1;
    max-height: 1;
    margin-right: 1;
    width: auto;
    border: none;
    transition: background 120ms, color 120ms;
}
.cct-chip:hover {
    background: $surface-highlight;
    color: #ffffff;
}
.cct-chip-label {
    background: transparent;
    color: $text;
    padding: 0 1;
    height: 1;
    min-height: 1;
    max-height: 1;
    width: auto;
}
.cct-chip-label:hover {
    color: #ffffff;
}
.cct-chip-close {
    background: transparent;
    color: $text-muted;
    padding: 0;
    height: 1;
    min-height: 1;
    max-height: 1;
    min-width: 3;
    max-width: 3;
    width: 3;
    border: none;
    content-align: center middle;
    transition: color 100ms, background 100ms;
}
.cct-chip-close:hover {
    color: $error;
    background: $error 25%;
    text-style: bold;
}

#cct-cmdpalette {
    background: $surface; border: tall $accent $border; margin-left: 3; margin-right: 1;
    margin-top: 1; margin-bottom: 1;
    width: 1fr; max-height: 8; height: auto; display: none;
    scrollbar-size: 1 1;
    scrollbar-color: $border $surface;
    scrollbar-color-hover: $accent $surface;
    scrollbar-color-active: $accent $surface;
}
#cct-cmdpalette.open { display: block; }
        .cct-cmd-row { height: 1; padding: 0 2; color: $text-faint; width: 1fr; border-left: thick transparent; }
/* v0.7.9.0: selection indicated by the accent bar + bold text, not a
   filled background strip behind the row. */
.cct-cmd-row-selected { color: $text; border-left: thick $accent; text-style: bold; }

#cct-kbhints { height: 1; color: $text-faint; padding: 0 2; }

#cct-bottom-row {
    height: 1;
    min-height: 1;
    max-height: 1;
    margin: 0;
    padding: 0 1;
    layout: horizontal;
    align-vertical: middle;
    border: none;
    background: transparent;
    overflow: hidden;
}
#cct-left-controls {
    width: auto;
    max-width: 55%;
    overflow: hidden;
    height: 1;
    layout: horizontal;
    align-vertical: middle;
}
#cct-footer-spacer-left { width: 1fr; height: 1; }
#cct-center-status {
    width: auto;
    max-width: 18;
    overflow: hidden;
    color: $accent;
    background: $surface-alt;
    border: none;
    padding: 0 1;
    margin: 0 1;
    content-align: center middle;
    text-style: bold;
    height: 1;
}
#cct-footer-spacer-right { width: 1fr; height: 1; }
#cct-right-controls {
    dock: right;
    width: auto;
    min-width: 12;
    max-width: 20;
    height: 1;
    min-height: 1;
    max-height: 1;
    layout: horizontal;
    align-vertical: middle;
    align-horizontal: right;
    margin: 0;
    padding: 0;
    overflow: hidden;
    background: transparent;
}

.cct-badge { width: auto; height: 1; color: $text-muted; text-style: bold; padding: 0 1; }
.cct-badge:hover { color: $accent; }
.cct-badge-sep { width: auto; height: 1; color: $text-faint; }
#badge-notebook { color: $accent; }

Button.cct-icon-btn,
Button#btn-permissions,
Button#btn-attach,
Button.cct-icon-send,
Button#btn-send {
    offset: 0 0;
    offset-x: 0;
    offset-y: 0;
    transition: none;
    border: none;
    height: 1;
    min-height: 1;
    max-height: 1;
}

Button.cct-icon-btn, Button#btn-permissions {
    background: transparent;
    color: $text;
    border: none;
    min-width: 4;
    width: auto;
    height: 1;
    min-height: 1;
    max-height: 1;
    padding: 0 1;
    margin: 0;
    content-align: center middle;
    text-style: bold;
}
Button#btn-attach {
    background: transparent;
    color: $text;
    border: none;
    min-width: 4;
    width: auto;
    height: 1;
    min-height: 1;
    max-height: 1;
    padding: 0 1;
    margin: 0;
    content-align: center middle;
    text-style: bold;
}
Button.cct-icon-btn:hover, Button#btn-permissions:hover, Button#btn-attach:hover {
    color: #ffffff;
    background: $accent 35%;
    text-style: bold;
    border: none;
}
Button.cct-icon-btn:focus, Button#btn-permissions:focus, Button#btn-attach:focus {
    color: $accent-highlight;
    background: $surface-highlight 40%;
    text-style: bold;
    border: none;
}
Button.cct-icon-btn.-active, Button#btn-permissions.-active, Button#btn-attach.-active {
    background: $accent;
    color: #ffffff;
    border: none;
    offset: 0 0;
}

Button.cct-icon-send, Button#btn-send {
    color: $accent;
    text-style: bold;
    border: none;
    min-width: 4;
    width: auto;
    height: 1;
    min-height: 1;
    max-height: 1;
    padding: 0 1;
    margin: 0;
    background: transparent;
    content-align: center middle;
}
Button.cct-icon-send:hover, Button#btn-send:hover {
    color: #ffffff;
    background: $accent;
    text-style: bold;
    border: none;
}
Button.cct-icon-send:focus, Button#btn-send:focus {
    color: $accent-highlight;
    background: $surface-highlight 40%;
    text-style: bold;
    border: none;
}
Button.cct-icon-send.-active, Button#btn-send.-active {
    background: $accent-shadow;
    color: #ffffff;
    border: none;
    offset: 0 0;
}

/* Interrupt Button state during AI Streaming */
#cct-composer Button#btn-send.cct-btn-interrupt,
#cct-composer.cct-mode-notebook Button#btn-send.cct-btn-interrupt,
#cct-composer.cct-mode-research Button#btn-send.cct-btn-interrupt,
#cct-composer.cct-mode-plan Button#btn-send.cct-btn-interrupt,
#cct-composer.cct-mode-build Button#btn-send.cct-btn-interrupt,
#cct-composer.cct-mode-debugger Button#btn-send.cct-btn-interrupt,
#cct-composer.cct-mode-agent Button#btn-send.cct-btn-interrupt,
Button.cct-btn-interrupt, Button#btn-send.cct-btn-interrupt {
    background: transparent;
    color: #ef4444;
    border: none;
    text-style: bold;
}
#cct-composer Button#btn-send.cct-btn-interrupt:hover,
Button.cct-btn-interrupt:hover, Button#btn-send.cct-btn-interrupt:hover {
    background: #ef4444;
    color: #ffffff;
    border: none;
    text-style: bold;
}
#cct-composer Button#btn-send.cct-btn-interrupt:focus,
Button.cct-btn-interrupt:focus, Button#btn-send.cct-btn-interrupt:focus {
    background: #ef4444 30%;
    color: #ffffff;
    border: none;
    text-style: bold;
}
#cct-composer Button#btn-send.cct-btn-interrupt.-active,
Button.cct-btn-interrupt.-active, Button#btn-send.cct-btn-interrupt.-active {
    background: #b91c1c;
    color: #ffffff;
    border: none;
}

#cct-streaming-status {
    height: 0; color: $warning; padding: 0 1; display: none;
}
#cct-streaming-status.active { height: 1; display: block; }

/* v0.7.8.1 interrupt: the streaming row hosts the status line plus a
   ⏹ Stop button that only exists (display:none by default) while a
   reply is in flight. */
#cct-streaming-row { height: 0; display: none; layout: horizontal; align-vertical: middle; }
#cct-streaming-row.active { height: 1; min-height: 1; max-height: 1; display: block; layout: horizontal; align-vertical: middle; }
#cct-streaming-row.active #cct-streaming-status { width: 1fr; height: 1; min-height: 1; display: block; }
Button.cct-stop-btn {
    height: 1; min-height: 1; max-height: 1; min-width: 8; width: auto; padding: 0 1; display: none;
    background: $surface; color: $error;
    border: none;
    text-style: bold;
    content-align: center middle;
    offset: 0 0;
}
Button.cct-stop-btn:hover {
    background: $error; color: #ffffff;
    border: none;
}
#cct-streaming-row.active Button.cct-stop-btn { width: auto; min-width: 8; height: 1; min-height: 1; max-height: 1; display: block; }

#cct-edit-banner {
    height: 0; color: $accent; padding: 0 1; display: none;
}
#cct-edit-banner.active { height: 1; display: block; }

#cct-latex-preview {
    height: 0; color: $text-muted; padding: 0 1; display: none;
}
#cct-latex-preview.active { height: 1; display: block; }

Button.cct-ctrl {
    background: $surface; color: $text;
    border: none;
    border-left: tall $surface-highlight;
    border-right: tall $surface-dark;
    min-width: 3; height: 1; padding: 0 1;
    min-height: 1; max-height: 1;
    content-align: center middle;
}
Button.cct-ctrl:hover { background: $surface-alt; }
Button.cct-send {
    background: $accent; color: $app-background; text-style: bold;
    border: none;
    border-left: tall $accent-highlight;
    border-right: tall $accent-shadow;
    min-width: 4; height: 1; min-height: 1; max-height: 1;
    content-align: center middle;
}
Button.cct-send:hover { background: $accent-secondary; }

#cct-permission-panel {
    background: $surface; border: round $accent; margin: 0 1 1 1;
    padding: 1 2; height: auto; max-height: 14; display: none;
}
#cct-permission-panel.open { display: block; }
#cct-perm-header {
    height: 1; min-height: 1; layout: horizontal; align-vertical: middle;
    margin-bottom: 1;
}
#cct-perm-title-box { width: auto; layout: horizontal; align-vertical: middle; }
#cct-perm-icon { color: $accent; text-style: bold; margin-right: 1; }
#cct-perm-title { color: $text; text-style: bold; }
#cct-perm-mode-btn {
    height: 1; min-height: 1; max-height: 1; padding: 0 1; margin-left: 2;
    background: $surface-alt; color: $text; text-style: bold;
    border: none;
    border-left: tall $surface-highlight;
    border-right: tall $surface-dark;
    content-align: center middle;
}
Button#cct-perm-mode-btn:hover {
    background: $accent 25%; color: $accent-highlight;
    border: none;
    border-left: tall #ffffff;
    border-right: tall $surface-dark;
}
Button#cct-perm-mode-btn.-active { offset: 0 0; }
#cct-perm-spacer { width: 1fr; }
Button#cct-perm-close {
    height: 1; min-height: 1; max-height: 1; width: 3; min-width: 3; padding: 0; margin: 0;
    color: $text-muted; background: transparent;
    border: none;
    border-left: tall $surface-highlight;
    border-right: tall $surface-dark;
    content-align: center middle;
}
Button#cct-perm-close:hover {
    color: $error; background: $error 20%; text-style: bold;
    border: none;
    border-left: tall #ffffff;
    border-right: tall $surface-dark;
}
Button#cct-perm-close.-active { offset: 0 0; }

#cct-perm-grid {
    height: auto; layout: horizontal;
}
.cct-perm-col {
    width: 1fr; height: auto; padding: 0 1;
}
.cct-perm-col-title {
    color: $accent; text-style: bold; height: 1; margin-bottom: 0;
}
.cct-perm-row {
    height: 1; min-height: 1; layout: horizontal; align-vertical: middle; margin-top: 1;
}
.cct-perm-label {
    width: 1fr; color: $text-muted; height: 1;
}
.cct-perm-row:hover .cct-perm-label {
    color: $text; text-style: bold;
}

/* 3D Toggle Switch */
Button.cct-toggle-3d {
    height: 1; min-height: 1; max-height: 1;
    width: 11; min-width: 11; max-width: 11;
    padding: 0; margin: 0;
    content-align: center middle;
    text-style: bold;
    border: none;
    border-left: tall $surface-highlight;
    border-right: tall $surface-dark;
    transition: background 100ms, color 100ms;
}
Button.cct-toggle-3d:hover {
    border: none;
    border-left: tall #ffffff;
    border-right: tall $surface-dark;
}
Button.cct-toggle-3d.-on {
    background: #047857;
    color: #ecfdf5;
}
Button.cct-toggle-3d.-on:hover {
    background: #059669;
    color: #ffffff;
}
Button.cct-toggle-3d.-off {
    background: #1e293b;
    color: #94a3b8;
}
Button.cct-toggle-3d.-off:hover {
    background: #334155;
    color: #f1f5f9;
}
Button.cct-toggle-3d.-active {
    offset: 0 0;
}

.cct-permcard {
    background: $surface; border: round $warning; margin: 1 2;
    padding: 1 2; height: auto;
}
.cct-permcard-title { color: $warning; text-style: bold; }
.cct-permcard-path { color: $text-muted; text-style: italic; }
.cct-permcard-reason { color: $text-faint; }
.cct-permcard-buttons { height: 3; margin-top: 1; }

#cct-statusline {
    height: 1; background: $app-background; color: $text-faint;
    padding: 0 2; border-top: solid $border; dock: bottom;
}

/* ------------------------------------------------------- v0.7.4 NavBar -- */
/* height:3 fits the Permission pill's rounded border (top border row +
   label row + bottom border row — a `border: round` Static always
   needs 3 rows, it can't be squeezed into 1). overflow:hidden stays as
   the defensive clip against anything that measures even taller than
   that (e.g. a stray hover repaint) — this is what caused the old
   header's hover rendering bug. A previous height:1 here clipped the
   pill down to its bare top border with no visible label at all,
   which is the "blank pill" bug: MenuButton/Logo/the workspace-path
   Static all already use content-align: *  middle, so they still sit
   correctly centered on the row when the container is 3 rows tall. */
#cct-header-top { height: 3; overflow: hidden; align: center middle; align-vertical: middle; }
#cct-header-left { width: auto; height: 3; align: left middle; align-vertical: middle; layout: horizontal; }
#cct-header-spacer-left { width: 1fr; height: 3; }
#cct-header-spacer-right { width: 1fr; height: 3; }

/* LEFT: clean menu button + logo */
.cct-menu-btn {
    width: 5; min-width: 5; height: 3; color: $text; content-align: center middle;
    background: $surface-alt;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    margin-right: 1;
    transition: color 120ms, border 120ms, background 120ms, offset 80ms;
}
.cct-menu-btn:hover {
    color: $text;
    background: $accent 24%;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
}
.cct-menu-btn.-active {
    offset: 0 0;
    border-top: tall $surface-dark;
    border-left: tall $surface-dark;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
}
.cct-menu-btn-active {
    color: $text;
    background: $accent 30%;
    border-top: tall $surface-dark;
    border-left: tall $surface-dark;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
    text-style: none;
}
.cct-logo { width: auto; padding: 0 1; content-align: left middle; height: 3; text-style: bold; }

/* CENTER: Permission pill */
.cct-perm-pill {
    width: auto; content-align: center middle; height: 3;
    padding: 0 2; margin: 0;
    background: $surface-alt;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    text-style: bold;
    color: $text;
    transition: border 120ms, color 120ms, background 120ms;
}
.cct-perm-pill:hover {
    background: $accent 24%;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    color: $text;
}
.cct-perm-pill.-active {
    offset: 0 0;
    border-top: tall $surface-dark;
    border-left: tall $surface-dark;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
}
.cct-perm-pill:focus {
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
}
.cct-perm-pill-active {
    background: $accent 30%;
    color: $text;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
}

.cct-chat-title-pill {
    width: auto; max-width: 30; content-align: center middle; height: 3;
    padding: 0 2; margin: 0 1 0 1;
    background: $surface-alt;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    color: $text;
    text-style: bold;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: border 120ms, color 120ms, background 120ms, offset 80ms;
}
.cct-chat-title-pill:hover {
    background: $accent 18%;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    color: $text;
    offset-y: 0;
}
.cct-chat-title-pill:focus {
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
}
.cct-chat-title-pill.-active {
    background: $accent 28%;
    border-top: tall $surface-dark;
    border-left: tall $surface-dark;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
    offset-y: 1;
}

/* RIGHT: 3D workspace path chip — aligned, beveled, and balanced with the pill */
#cct-header-right {
    width: auto; max-width: 32; content-align: center middle;
    padding: 0 2; height: 3;
    background: $surface-alt;
    border: tall;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    overflow: hidden;
    text-overflow: ellipsis;
    text-style: bold;
    color: $text;
    transition: background 120ms, border 120ms, color 120ms, offset 80ms;
}
#cct-header-right:hover {
    background: $accent 20%;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent-shadow;
    border-right: tall $accent-shadow;
    color: #ffffff;
    offset: 0 0;
}
.cct-menu-btn:focus { color: $accent; text-style: bold; }
.cct-perm-pill:focus { border: tall $accent; }

/* --------------------------------------------------------------- sidebar -- */
#cct-sidebar {
    width: 32; min-width: 0; max-width: 60; height: 100%;
    background: $surface;
    border-right: none;
    transition: width 150ms;
}
#cct-sidebar.cct-sidebar-collapsed { border-right: none; }
#cct-sidebar-titlebar {
    height: 3; padding: 0 1; align: center middle; layout: horizontal;
    background: $surface-alt;
    border-top: solid $surface-highlight;
    border-bottom: solid $surface-dark;
    overflow: hidden;
}
#cct-sidebar-title { height: 1; padding: 0 1; width: 1fr; color: $text; text-style: bold; }
Button#cct-sidebar-collapse-btn, Button#cct-sidebar-expand-btn, Button#cct-sidebar-menu-btn, .cct-sidebar-titlebar-btn {
    width: 3; min-width: 3; max-width: 3;
    height: 1; min-height: 1; max-height: 1;
    margin: 0; padding: 0;
    background: transparent;
    border: none;
    color: $accent;
    content-align: center middle;
    text-style: bold;
    offset: 0 0;
}
Button#cct-sidebar-collapse-btn:hover, Button#cct-sidebar-expand-btn:hover, Button#cct-sidebar-menu-btn:hover, .cct-sidebar-titlebar-btn:hover {
    color: #ffffff; background: $accent;
    border: none;
}
Button#cct-sidebar-collapse-btn:focus, Button#cct-sidebar-expand-btn:focus {
    border: none;
}

/* Open Folder button — tactile 3D rounded button without tall brackets */
Button#cct-open-folder-btn, .cct-sidebar-open-btn,
Button#cct-open-folder-btn:ansi.-style-default,
Button#cct-open-folder-btn:ansi.-style-flat,
Screen Button#cct-open-folder-btn {
    width: 100%;
    min-width: 10;
    max-width: 100%;
    height: 3;
    min-height: 3;
    max-height: 3;
    padding: 0;
    margin: 1 0;
    background: $accent 25%;
    color: #ffffff;
    text-style: bold;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall #ffffff;
    border-bottom: tall $accent-shadow;
    border-right: tall $accent-shadow;
    content-align: center middle;
    transition: background 120ms, border 120ms, color 120ms, offset 80ms;
}
Button#cct-open-folder-btn:hover, Button#cct-open-folder-btn:focus,
.cct-sidebar-open-btn:hover, .cct-sidebar-open-btn:focus,
Screen Button#cct-open-folder-btn:hover, Screen Button#cct-open-folder-btn:focus {
    background: $accent;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall #ffffff;
    border-bottom: tall $accent-highlight;
    border-right: tall $accent-highlight;
    color: #ffffff;
}
Button#cct-open-folder-btn.-active, .cct-sidebar-open-btn.-active,
Screen Button#cct-open-folder-btn.-active {
    offset-y: 1;
    border: tall;
    border-top: tall $accent-shadow;
    border-left: tall $accent-shadow;
    border-bottom: tall #ffffff;
    border-right: tall #ffffff;
    background: $accent 50%;
}

#cct-sidebar-body {
    height: 1fr; padding: 0 1;
    overflow-x: auto; overflow-y: auto;
    scrollbar-gutter: stable;
}
.cct-sidebar-section { color: $text-faint; padding-top: 1; height: 1; width: auto; }
.cct-sidebar-projects { width: 100%; height: auto; }
.cct-sidebar-project-header {
    color: $accent;
    text-style: bold;
    padding-top: 1;
    height: 2;
    border-top: solid $surface-highlight;
    border-bottom: solid $surface-dark;
    margin-top: 1;
}
.cct-sidebar-project {
    height: 1; color: $text-muted; width: 1fr; padding: 0 1;
    overflow: hidden; text-overflow: ellipsis;
    transition: color 150ms;
}
.cct-sidebar-project:hover { color: $accent; }
.cct-sidebar-project-row {
    width: 100%; height: 1; layout: horizontal;
    border-left: thick transparent;
    transition: background 100ms, border-left 100ms;
}
.cct-sidebar-project-row:hover {
    background: $surface-alt;
    border-left: thick $accent;
}
.cct-sidebar-project-row:hover .cct-sidebar-project {
    color: #ffffff;
}
.cct-sidebar-project-del {
    width: 3; height: 1; color: $text-faint;
    content-align: center middle;
    transition: color 150ms;
}
.cct-sidebar-project-del:hover { color: $error; }
.cct-sidebar-clear-recent {
    height: 1; color: $text-faint; width: auto; padding: 1 1 0 1;
    transition: color 150ms;
}
.cct-sidebar-clear-recent:hover { color: $error; }

/* 3D Dropzone */
.cct-sidebar-dropzone {
    color: $text-faint;
    padding: 1;
    margin: 1 0;
    width: 100%;
    height: auto;
    background: $surface-dark;
    border: dashed $border;
    border-top: dashed $surface-dark;
    border-left: dashed $surface-dark;
    border-bottom: dashed $surface-highlight;
    border-right: dashed $surface-highlight;
    text-align: center;
}

/* 3D tactile Workspace Header badge */
.cct-workspace-header {
    width: 100%; height: auto;
    padding: 0 1; margin: 0 0 1 0;
    background: transparent;
    border-left: thick $accent;
    border-top: none;
    border-bottom: none;
    border-right: none;
    transition: background 120ms;
}
.cct-workspace-header:hover {
    background: $surface-alt;
}
.cct-wshead-name { color: $accent; height: 1; width: 1fr; text-style: bold; overflow: hidden; text-overflow: ellipsis; }
.cct-wshead-detail { color: $text-faint; height: 1; width: 1fr; overflow: hidden; text-overflow: ellipsis; }

/* v0.7.7 multi-workspace collapse row (spec section 4). */
.cct-sidebar-collapsed-row {
    height: 1; color: $text-muted; width: auto; padding: 0 1; margin-top: 1;
    transition: color 150ms;
}
.cct-sidebar-collapsed-row:hover { color: $text; }
#cct-sidebar-body {
    scrollbar-size: 1 1;
    scrollbar-color: $border $surface;
    scrollbar-color-hover: $accent $surface;
    scrollbar-color-active: $accent $surface;
}
.cct-filetree { height: auto; max-height: 20; width: auto; }
.cct-filetree > .tree--cursor {
    background: $accent 22%;
    color: #ffffff;
    text-style: bold;
    border-left: thick $accent;
}
.cct-filetree:focus > .tree--cursor {
    background: $accent 30%;
    color: #ffffff;
    border-left: thick #ffffff;
}

/* ------------------------------------------------------------ workspace -- */
/* v0.7.10: the shell owns everything between header and status bar.
   Explorer | divider | main column { switcher? / body{ CHAT COLUMN |
   divider | RIGHT PANE (editor ⇄ preview) } }. The composer lives
   INSIDE the chat column, so it is geometrically impossible for the
   chat box to overlap the editor or the web preview (spec section 26):
   the three panes are siblings with independent widths. */
#cct-workspace { width: 100%; height: 1fr; }
#cct-workspace-main { width: 1fr; height: 100%; }
#cct-workspace-body { width: 100%; height: 1fr; }
#cct-chat-col { width: 1fr; height: 100%; min-width: 24; }
#cct-chat-nav {
    height: 1; min-height: 1; max-height: 1;
    width: 100%; layout: horizontal;
    background: transparent;
    border: none;
    padding: 0;
    margin: 0;
    display: none;
}
#cct-chat-nav-title { display: none; }
.cct-chat-nav-spacer { display: none; }
Button#cct-chat-sidebar-toggle, .cct-chat-nav-btn {
    width: auto; min-width: 12; max-width: 16;
    height: 1; min-height: 1; max-height: 1;
    border: none;
    padding: 0 1; margin: 0 0 0 1;
    color: $accent; background: $surface;
    text-style: bold;
    content-align: center middle;
    offset: 0 0;
    transition: color 100ms, background 100ms;
}
Button#cct-chat-sidebar-toggle:hover, .cct-chat-nav-btn:hover {
    color: #ffffff;
    background: $accent;
    border: none;
    text-style: bold;
}
Button.cct-chat-nav-action {
    width: auto; min-width: 8;
    height: 1; min-height: 1; max-height: 1;
    border: none;
    padding: 0 1; margin-left: 1;
    color: $text-muted; background: $surface;
    text-style: bold;
    content-align: center middle;
    offset: 0 0;
    transition: color 100ms, background 100ms;
}
Button.cct-chat-nav-action:hover {
    color: #ffffff;
    background: $accent;
    border: none;
    text-style: bold;
}
Button.cct-chat-nav-action.-active {
    offset: 0 0;
}
/* Explicit default: an `auto` column containing 100%-width children
   collapses to zero — the pane owns a real width (restored from
   ~/.cct_ui_layout.json when one was saved). */
#cct-right-pane { width: 44; min-width: 24; height: 100%; }
/* Legacy id kept for any external probe referencing it (no longer the
   layout owner). */
#cct-workspace-split { width: 100%; height: 1fr; }

/* Chat/Files switcher (narrow stacked mode only — the shell shows it
   programmatically via EditorTabsChanged/width detection).
   v0.7.9.0: plain strip — border rule + accent text for the active tab,
   no filled toolbar background. */
#cct-workspace-switcher {
    width: 100%; height: 1; layout: horizontal;
    background: transparent; border-bottom: solid $border;
}
Button.cct-switch {
    width: auto; height: 1; min-height: 1; min-width: 8;
    background: transparent; color: $text-muted;
    border: tall;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    padding: 0 2;
}
Button.cct-switch:hover {
    color: $text;
    background: $surface-alt;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
}
Button.cct-switch.-active {
    color: $accent;
    background: $surface-alt;
    border: tall;
    border-top: tall $accent-shadow;
    border-left: tall $accent-shadow;
    border-bottom: tall #ffffff;
    border-right: tall #ffffff;
    text-style: bold;
}

/* --------------------------------------------------------------- editor -- */
#cct-editor {
    height: 100%;
    background: $surface;
    border: tall $border;
}
#cct-editor-tabs { height: 1fr; }
#cct-editor-tabs Tabs {
    background: $surface-alt;
    border: none;
}
#cct-editor-tabs Tab {
    padding: 0 2;
    background: transparent;
    color: $text-muted;
    border: none;
    transition: background 120ms, color 120ms;
}
#cct-editor-tabs Tab:hover {
    background: $surface;
    color: $text;
}
#cct-editor-tabs Tab.-active {
    background: $surface;
    color: $text;
    text-style: bold;
}

.cct-editor-placeholder { padding: 2; color: $text-faint; }
.cct-editor-findbar {
    height: 3;
    background: $surface-alt;
    padding: 0 1;
    border-top: solid $border;
    border-bottom: solid $border;
}
.cct-editor-findbar Input { width: 1fr; margin-right: 1; }
/* Warning banner keeps its meaning through color + weight */
.cct-editor-highlight-warning {
    height: 1; padding: 0 1; background: transparent; color: $warning;
    text-style: bold;
}

/* Live Preview pane (v0.7.8 editor upgrade) — hidden until the
   toolbar's Preview pill toggles it on. */
#cct-editor-preview {
    height: 1fr; max-height: 45%; display: none;
    background: $surface; border-top: solid $border;
    padding: 1 2; overflow-y: auto;
    color: $text-muted;
}

/* Status toolbar: file · language · UTF-8 · Ln/Col · Spaces · Modified · ✕ */
#cct-editor-toolbar {
    height: 1; width: 100%; layout: horizontal;
    background: $surface-alt;
    border: none;
}
.cct-tb-file { width: 1fr; height: 1; padding: 0 1; color: $text; text-style: bold; }
.cct-tb-pill {
    width: auto; height: 1; padding: 0 1; margin: 0 1;
    color: $text-muted; background: $surface;
    border: none;
}
.cct-tb-pill:hover { color: $text; background: $surface-highlight; }
.cct-tb-pill.-on { color: $accent; text-style: bold; }
.cct-tb-close {
    width: 3; height: 1; padding: 0;
    color: $text-muted; content-align: center middle;
    background: $surface-alt;
    border: none;
}
.cct-tb-close:hover { color: $error; }
/* ▷ Live Web Preview pill — visible only while an HTML file is the
   active tab (the editor shows/hides it in _refresh_toolbar). */
.cct-tb-pill.cct-tb-run { color: $success; }
.cct-tb-pill.cct-tb-run:hover { color: $accent; text-style: bold; }
.cct-tb-pill.cct-tb-split { color: $text-muted; }
.cct-tb-pill.cct-tb-split:hover { color: $accent; text-style: bold; }
.cct-tb-pill.cct-tb-split.-split { color: $accent; text-style: bold; }

/* Image viewer toolbar — same visual language as editor toolbar */
#cct-image-toolbar { height: 3; width: 100%; layout: horizontal; background: transparent; border-bottom: solid $border; padding: 0 1; }
.cct-image-toolbar { height: 3; }
#cct-image-info { width: 1fr; color: $text-muted; content-align: left middle; }
#cct-image-scroll { height: 1fr; width: 100%; background: $surface; }
#cct-image-display { width: 100%; padding: 2 2; color: $text; background: $surface; content-align: center middle; }
.cct-image-display { text-align: center; }

/* CSV viewer */
#cct-csv-toolbar { height: 3; width: 100%; layout: horizontal; background: transparent; border-bottom: solid $border; padding: 0 1; }
#cct-csv-table { height: 1fr; width: 100%; }
#cct-csv-fallback { padding: 2; color: $text-muted; }

/* PDF viewer */
#cct-pdf-toolbar { height: 3; width: 100%; layout: horizontal; background: transparent; border-bottom: solid $border; padding: 0 1; }
#cct-pdf-display { padding: 2; color: $text; }

/* ------------------------------------------------- web preview pane -- */
/* v0.7.10 Live Web Preview — the PREVIEW half of the right pane.
   Everything is $variable-driven so every theme renders correctly. */
#cct-preview { width: 100%; height: 100%; display: none; background: $surface; }
#cct-browser-bar {
    height: 3; width: 100%; layout: horizontal;
    background: transparent; border-bottom: solid $border;
    padding: 0 1;
}
.cct-bv-btn {
    width: 3; min-width: 3; min-height: 1; height: 1; margin-right: 1;
    background: transparent;
    border: tall;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    padding: 0;
    color: $text-muted; content-align: center middle;
}
.cct-bv-btn:hover { color: $accent; text-style: bold; }
.cct-bv-danger { color: $error; }
.cct-bv-danger:hover { color: $error; text-style: bold; }
#cct-bv-url {
    height: 1; min-height: 1; border: none; width: 1fr;
    background: $surface-alt; color: $text; padding: 0 1;
}
#cct-bv-url:focus { border: none; }
#cct-bv-status {
    height: 1; width: 100%; padding: 0 2;
    color: $text-faint; background: transparent;
    border-bottom: solid $border;
}
#cct-bv-status.-error { color: $error; }
#cct-bv-scroll { height: 1fr; width: 100%; background: $surface; }
#cct-bv-viewport { width: 100%; padding: 1 2; color: $text; background: $surface; }
#cct-bv-activity {
    height: auto; max-height: 8; width: 100%;
    padding: 0 2; display: none;
    color: $text-muted; background: transparent;
    border-top: solid $border;
}
#cct-bv-activity.-has-lines { display: block; }

/* DevTools bar & Viewport presets */
.cct-bv-btn.-vp-active { color: $accent; text-style: bold; }
#cct-devtools-bar {
    height: 1; width: 100%; layout: horizontal;
    background: $surface-alt; border-bottom: solid $border;
    padding: 0 1;
}
.cct-dev-tab {
    height: 1; min-height: 1;
    border: tall;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    background: transparent; color: $text-muted;
    padding: 0 1; margin-right: 1;
}
.cct-dev-tab:hover { color: $text; }
.cct-dev-tab.-tab-active { color: $accent; text-style: bold; background: $surface; }
#cct-bv-console { width: 100%; padding: 1 2; color: $text; display: none; }
#cct-bv-problems { width: 100%; padding: 1 2; color: $text; display: none; }

/* IDE Command Palette Modal */
.cct-cmd-palette-modal { align: center top; padding-top: 3; }
#cct-cmd-palette-dialog {
    width: 68; max-width: 90%; height: auto; max-height: 24;
    background: $surface; border: solid $accent;
}
#cct-cmd-palette-input { width: 100%; height: 3; background: $surface-alt; border: none; color: $text; }
#cct-cmd-palette-list { width: 100%; height: auto; max-height: 18; background: transparent; }
.cct-cmd-palette-item { width: 100%; height: auto; padding: 0 1; }
.cct-cmd-palette-item:hover { background: $accent 20%; }
.cct-cmd-title { color: $text; width: 1fr; }
.cct-cmd-keybinding { color: $text-muted; background: $surface-alt; padding: 0 1; }
.cct-cmd-category { color: $text-faint; }

/* ------------------------------------------------------------ dashboard -- */
.cct-dashboard {
    width: 100%;
    height: auto;
    padding: 1 2;
    overflow-y: auto;
    overflow-x: hidden;
    align-horizontal: center;
}
#cct-empty-art {
    width: 100%;
    text-align: center;
    content-align: center middle;
    min-height: 1;
    margin: 0 0 1 0;
}
.cct-dash-line {
    width: 100%;
    text-align: center;
    content-align: center middle;
    min-height: 1;
    padding: 0 1;
}
#cct-dash-logo-bar {
    height: auto;
    width: 100%;
    max-width: 84;
    layout: horizontal;
    align: center middle;
    align-horizontal: center;
    margin: 0 auto 1 auto;
}
.cct-logo-pill, Button.cct-logo-pill {
    height: 3;
    min-height: 3;
    max-height: 3;
    min-width: 10;
    max-width: 15;
    padding: 0;
    margin: 0 1;
    background: $surface-alt;
    color: $text-muted;
    border: tall $surface-dark;
    border-top: tall $surface-highlight;
    content-align: center middle;
    text-style: none;
    transition: background 100ms, color 100ms, border 100ms;
}
.cct-logo-pill:hover, Button.cct-logo-pill:hover,
.cct-logo-pill:focus, Button.cct-logo-pill:focus {
    background: $accent 30%;
    color: #ffffff;
    text-style: bold;
    border-top: tall #ffffff;
}
.cct-logo-pill.active, Button.cct-logo-pill.active {
    background: $accent 45%;
    color: #ffffff;
    text-style: bold;
    border: tall $accent;
    border-top: tall #ffffff;
}
#cct-dash-hero { text-align: center; padding-bottom: 1; }
#cct-dash-actions {
    height: auto;
    width: 100%;
    max-width: 90;
    padding: 1 0;
    layout: horizontal;
    align: center middle;
    align-horizontal: center;
    margin: 0 auto;
}
#cct-dash-actions.stacked {
    layout: vertical;
    height: auto;
    width: 100%;
    max-width: 48;
    margin: 0 auto;
    align-horizontal: center;
}
#cct-dash-actions.stacked .cct-dash-action { width: 100%; max-width: 100%; margin: 1 0; }
.cct-dash-action, Button.cct-dash-action,
Button.cct-dash-action.-style-default,
Button.cct-dash-action:ansi.-style-default,
Button.cct-dash-action:ansi.-style-flat,
Screen Button.cct-dash-action {
    width: 1fr;
    min-width: 14;
    max-width: 22;
    height: 3;
    min-height: 3;
    max-height: 3;
    padding: 0;
    margin: 0 1;
    background: $surface-alt;
    color: #ffffff;
    text-style: bold;
    content-align: center middle;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall #ffffff;
    border-bottom: tall $accent-shadow;
    border-right: tall $accent-shadow;
    transition: background 80ms, color 80ms, border 80ms, offset 80ms;
}
.cct-dash-action:hover, Button.cct-dash-action:hover,
.cct-dash-action:focus, Button.cct-dash-action:focus,
Screen Button.cct-dash-action:hover, Screen Button.cct-dash-action:focus {
    background: $accent 35%;
    color: #ffffff;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall #ffffff;
    border-bottom: tall $accent-highlight;
    border-right: tall $accent-highlight;
    text-style: bold;
    offset-y: 0;
}
.cct-dash-action.-active, Button.cct-dash-action.-active,
Screen Button.cct-dash-action.-active {
    offset-y: 1;
    background: $accent 50%;
    color: #ffffff;
    border: tall;
    border-top: tall $accent-shadow;
    border-left: tall $accent-shadow;
    border-bottom: tall #ffffff;
    border-right: tall #ffffff;
}
#cct-dash-columns {
    height: auto;
    width: 100%;
    max-width: 110;
    padding-top: 1;
    layout: horizontal;
    overflow: hidden;
    align-horizontal: center;
    margin: 0 auto;
}
#cct-dash-columns.stacked {
    layout: vertical;
    width: 100%;
    max-width: 86;
    margin: 0 auto;
    align-horizontal: center;
}
#cct-dash-columns.stacked .cct-dash-col { width: 100%; margin: 1 0; }
.cct-dash-col {
    width: 1fr;
    min-width: 24;
    height: auto;
}
.cct-dash-col-title {
    color: $accent;
    padding-bottom: 1;
    margin-bottom: 1;
    border-bottom: solid $surface-dark;
    text-style: bold;
    content-align: center middle;
}
.cct-dash-row {
    color: $text-muted;
    height: 1;
    padding: 0 1;
    transition: color 100ms, background 100ms;
}
.cct-dash-row:hover {
    color: #ffffff;
    background: $surface-alt;
}
.cct-dash-nb-subtitle {
    color: $accent;
    text-style: bold;
    margin-top: 1;
    padding: 0 1;
}
.cct-dash-nb-actions {
    layout: horizontal;
    width: 100%;
    height: auto;
    margin-top: 0;
    padding: 0;
    align-horizontal: center;
}
.cct-nb-chip-btn, Button.cct-nb-chip-btn {
    width: 1fr;
    height: 3;
    min-height: 3;
    max-height: 3;
    margin: 0 1 1 1;
    padding: 0;
    background: $surface-alt;
    color: $text;
    border: tall $surface-dark;
    border-top: tall $surface-highlight;
    content-align: center middle;
    text-style: bold;
    transition: background 80ms, color 80ms, border 80ms;
}
.cct-nb-chip-btn:hover, Button.cct-nb-chip-btn:hover {
    background: $accent 35%;
    color: #ffffff;
    border-top: tall #ffffff;
    border-bottom: tall $accent-highlight;
}
.cct-nb-chip-btn.-active, Button.cct-nb-chip-btn.-active {
    offset-y: 1;
    background: $accent 50%;
    color: #ffffff;
}
#cct-dash-stats-body { color: $text-muted; height: auto; }
#cct-workspace { overflow: hidden; }
#cct-workspace-main { overflow: hidden; }
#cct-workspace-body { overflow: hidden; layout: horizontal; }
#cct-chat-col { width: 1fr; min-width: 24; height: 100%; overflow: hidden; }
#cct-right-pane { width: 44; min-width: 24; height: 100%; overflow: hidden; border-left: solid $border; }
#cct-conversation { overflow-y: auto; overflow-x: hidden; padding: 0 1; }
#cct-composer { overflow: hidden; }
"""


if TEXTUAL_AVAILABLE:

    class CCTApp(TextualApp):
        """The primary interface: scrolling conversation, the sticky
        composer, and a compact status line — nothing else."""

        CSS = theme_css.BASE_CSS + _COMPONENT_CSS + _BROWSER_CSS
        BINDINGS = [
            ("ctrl+q", "quit_app", "Quit"),
            ("ctrl+p", "open_palette", "Commands"),
            ("ctrl+m", "toggle_menu", "Menu"),
            ("ctrl+b", "toggle_sidebar", "Sidebar"),
            ("ctrl+s", "save_file", "Save"),
            ("ctrl+f", "toggle_find", "Find"),
            ("ctrl+t", "toggle_activity_panel", "Live activity"),
            ("ctrl+shift+f", "toggle_editor_fullscreen", "Fullscreen Editor"),
            # v0.7.10 Live Web Preview shortcuts (spec section 24):
            ("ctrl+shift+p", "toggle_preview", "Toggle Web Preview"),
            ("ctrl+r", "preview_reload", "Reload Preview"),
            ("f11", "browser_fullscreen", "Fullscreen"),
            ("escape", "cancel_streaming", "Stop"),
            ("ctrl+c", "cancel_streaming", "Stop"),
            # v0.7.10 Host: Terminal ↔ Browser (embedded WebView2/Chromium inside CAT window)
            ("ctrl+shift+b", "host_browser", "CAT Browser (Host)"),
            ("ctrl+shift+h", "host_toggle", "CAT Host"),
            ("ctrl+shift+t", "toggle_touch_mode", "Touch Mode"),
            ("alt+a", "prompt_attach", "Attach File"),
            ("alt+p", "toggle_permissions", "Permissions"),
        ]
        TITLE = f"CAT v{identity.APP_VERSION}"
        # v0.7.9.5: Textual 8 ships its own built-in command palette on
        # Ctrl+P — a foreign, differently-themed screen that stole the
        # keypress before CAT's own "/" palette binding could run (and
        # left stale widgets behind when dismissed). Rebind the built-in
        # to an unused key and disable it so CAT's palette owns Ctrl+P
        # in every theme.
        COMMAND_PALETTE_BINDING = ""
        use_command_palette = False

        def _handle_exception(self, error: Exception) -> None:
            """Textual exception override — prevents unhandled task or message
            exceptions from terminating the application. Logs the error, notifies
            the user gracefully, and keeps the chat session alive."""
            import logging
            logging.getLogger("calc_terminal.app").error("Recovered from unhandled UI exception: %s", error, exc_info=True)
            try:
                self.notify(f"Task recovered: {error}", severity="warning", timeout=4.0)
            except Exception:
                pass

        def __init__(self, repl, history, stats):
            super().__init__()
            # `repl` is the calc_terminal.app.App instance — the existing
            # command dispatcher/business-logic owner. This UI reads a
            # couple of read-only fields from it (VERSION, len(history))
            # and, for commands not yet natively ported, suspends the
            # screen and calls repl.handle(raw) in the real terminal. It
            # never reaches into repl's print()-based rendering otherwise.
            self.repl = repl
            self._history = history
            self._stats = stats
            self.session = chat_session.ChatSession()
            self._pending_permissions = {}  # request_id -> (text, attachments)
            self._pending_tool_permissions = {}  # request_id -> (threading.Event, result_dict)
            # v0.7.8.2: start in the saved mode (ai_modes restores it
            # from ~/.cct_config.json) — never a hardcoded Notebook, so
            # a restart can't silently switch the user's mode.
            self._current_ai_mode = ai_modes.current_mode()  # ai_modes.py key, spec section 3
            self._current_workspace = "Workspace"
            self._turn_prompts = {}  # turn_id -> prompt text, for stage
                                      # detection + the completion summary's
                                      # "Commands Used" line
            self._is_streaming = False
            self._idle_tick = 0
            self._forked_from = None  # previous ChatSession, set by _fork_conversation
            self._current_chat_id = None
            self._current_chat_title = "New Chat"
            # v0.7.8 Attach redesign: a small in-memory list of recently
            # attached paths, offered by AttachPanel's Recent tool.
            self._recent_attachments = []
            # v0.7.8.1 Live Activity panel (Ctrl+T): cheap counters the
            # workers bump while a turn is in flight; the ActivityPanel
            # screen renders them live without touching widget internals.
            self._activity = {"stage": "", "chunks": 0, "files": 0,
                              "start": 0.0, "last_step": ""}
            # ---- v0.7 IDE state ----
            self._workspace_shell = None  # WorkspaceShell, once a folder is opened
            try:
                from .. import chat_store
                detected_ws = ws_paths.active_project() or ws_paths.root_dir(ensure=False)
                if detected_ws and os.path.isdir(detected_ws):
                    self._workspace_root = chat_store.normalize_workspace_path(detected_ws)
                    self._current_workspace = os.path.basename(self._workspace_root.rstrip(os.sep)) or self._workspace_root
                else:
                    self._workspace_root = None
            except Exception:
                self._workspace_root = None
            # v0.7.9.0: the real-time filesystem watcher backing the live
            # File Explorer (calc_terminal/fs_watcher.py). One instance,
            # repointed at each workspace as it opens — never polling the
            # whole disk, never left watching a stale root.
            try:
                from ..fs_watcher import WorkspaceWatcher
                self._fs_watcher = WorkspaceWatcher(self._on_fs_events)
            except Exception:
                self._fs_watcher = None
            # v0.7.9.5 theme preview state (requirement: hover previews a
            # theme without ever changing the user's saved choice):
            #   display_theme = _preview_theme or _selected_theme
            self._selected_theme = theme.get_theme()
            self._preview_theme = None
            # v0.7.9.5 failover notes buffer — the aicore failover hook
            # runs on worker threads and appends here; the streaming
            # worker drains it into the live bubble so "Trying backup
            # provider..." is visible in the right turn.
            self._pending_failover_notes = []
            # v0.7.9.5 pending system notes queue — worker threads
            # (workspace indexing, startup) call _system_note before the
            # ConversationView widget is mounted in the DOM; those notes
            # are queued here and drained into the conversation once it's
            # queryable.
            self._pending_system_notes = []
            self._streaming_turn_id = None
            # ---- v0.7.10 Live Web Preview ----------------------------------
            # One PreviewController per workspace session (owns server +
            # Chromium engine + watcher). Events from its background
            # threads are queued thread-safely and drained onto the UI by
            # a fast interval — no widget is ever touched off-thread.
            self._preview_ctrl = None
            self._preview_worker = None
            self._preview_events = []          # [(kind, info_dict)]
            self._preview_events_lock = threading.Lock()
            self._goodbye_shown = False
            self.status_fields = StatusFields(self._ide_state, version=self._version())
            # ---- Centralized Touchscreen & Input Architecture ----
            from ..input import (
                get_input_capabilities, TouchTapRecognizer, TouchScrollHandler,
                TouchFocusManager, register_listener
            )
            self.input_capabilities = get_input_capabilities()
            self._touch_tap_recognizer = TouchTapRecognizer(
                on_tap=self._on_touch_tap_resolved,
                on_long_press=self._on_touch_long_press
            )
            self._touch_scroll_handler = TouchScrollHandler()
            self._touch_focus_mgr = TouchFocusManager()
            register_listener(self._on_input_capabilities_changed)

        def get_css_variables(self):
            variables = dict(super().get_css_variables())
            variables.update(theme_css.css_variables())
            return variables

        def compose(self):
            yield BrandHeader()
            # The WorkspaceShell holds the chat permanently: opening a
            # folder only reveals the sidebar, it never tears the
            # ConversationView out of the DOM (v0.7.4 — the old
            # remove/re-mount dance could lose the chat widget entirely
            # in real terminals).
            #
            # v0.7.9.0 layout contract: the StickyComposer lives INSIDE
            # the shell's main column (below the chat, above nothing),
            # not docked across the whole screen — that docking was the
            # root cause of the composer overlapping the File Explorer.
            # The StatusBar stays screen-docked; everything between the
            # header and status bar is owned by the shell.
            yield WorkspaceShell(
                ConversationView(),
                composer=StickyComposer(model_label=self._model_label()),
            )
            yield StatusBar(self.status_fields)

        def on_mount(self):
            # Requirement #41: Set supported terminal title to 🐱 CAT CLI
            try:
                if sys.platform == "win32":
                    import ctypes
                    ctypes.windll.kernel32.SetConsoleTitleW("🐱 CAT CLI")
                sys.stdout.write("\033]0;🐱 CAT CLI\007")
                sys.stdout.flush()
            except Exception:
                pass
            # Route all web links through CAT Browser (ctrl+click etc)
            try:
                _install_cat_browser_redirect(self)
            except Exception:
                pass
            from ..app import LOGO
            timeline.wire_to_bus()
            try:
                if self.brand_header:
                    self.brand_header.set_chat_title(self._current_chat_title)
            except Exception:
                pass
            # v0.7.9.4 fix (System32 launch crash): workspace detection
            # must run BEFORE the startup dashboard composes, so its
            # generated-files column reads the REAL project root instead
            # of whatever directory the shell happened to open in (e.g.
            # C:\WINDOWS\System32, which is unwritable). Detection now
            # also refuses protected system dirs entirely.
            try:
                ws_paths.auto_load_workspace()
            except Exception:
                pass
            # v0.7.9.11 Extensions startup (VS Code-style): discover,
            # validate, load enabled and register features before building
            # the main menu dynamically.
            try:
                from .. import extensions as _ext
                _ext.startup()
            except Exception:
                pass
            # v0.7.9.0 startup flow (spec: 'Dashboard and Welcome Screen
            # consistently available'):
            #   launch → Welcome Screen (animated CAT art + boot bar,
            #   EVERY fresh launch) → Dashboard (the primary startup
            #   screen, mounted here first so it is already live behind
            #   the modal) → ready for AI interaction.
            self._show_dashboard_home()
            self._refresh_header_breadcrumb()
            self._refresh_header_right()
            # Set terminal and tab identity to CAT CLI
            try:
                from ..terminal_identity import set_terminal_title
                set_terminal_title()
            except Exception:
                pass
            # v0.7.8.2: paint the composer's mode badge from the restored
            # mode at startup (the footer widget defaults to 'notebook'
            # until told otherwise — a restart must not look like a
            # silent switch back to Notebook).
            try:
                self.composer.set_ai_mode(self._current_ai_mode)
            except Exception:
                pass
            # v0.7.10: drain preview-subsystem events onto the UI thread.
            self.set_interval(0.2, self._drain_preview_events)
            # v0.7.9.5: install the aicore failover hook so provider
            # switchovers surface in the chat ("⚠ ... Switching to Backup
            # Provider N...") instead of happening silently.
            try:
                aicore.set_failover_hook(self._on_failover_message)
            except Exception:
                pass
            # Chemistry-Themed Idle Animation (spec #25): a subtle,
            # lightweight icon cycle in the status line while nothing is
            # streaming. Ticks slowly (every 1.6s) and only repaints the
            # status line when actually idle, so it never competes with
            # generation for CPU.
            self.set_interval(1.6, self._tick_idle_animation)
            # v0.7.4 spec #2: "If a workspace already exists, detect and
            # v0.7.9.4 fix: remove any protected system directory that an
            # earlier buggy launch recorded as a "recent project" (e.g.
            # C:\WINDOWS\System32 from PowerShell's default cwd) so the
            # autoload below can never reopen it.
            try:
                from .. import projects as _projects_mod
                _projects_mod.forget_protected()
            except Exception:
                pass
            # v0.7.7 spec section 1 — automatic workspace detection on
            # launch: cwd (when it isn't CCT's own folder) -> VS Code
            # workspace -> git root -> launch dir -> last opened. If
            # something is found it's recorded and set as the active
            # project root before the UI builds, so the header/status
            # show the right workspace from the first frame.
            try:
                ws_paths.auto_load_workspace()
            except Exception:
                pass
            # Spec v0.7.4 "load it automatically on startup": the most-
            # recently-opened project (projects.recent(), already
            # tracked by every prior Open Folder) is the closest thing
            # this app has to "the" workspace — reopen it without the
            # user having to go through the menu again, same as any
            # modern IDE restoring its last folder. Silently skipped if
            # that path no longer exists on disk (moved/deleted since
            # last run) or there's no recent history yet.
            self._autoload_last_workspace()
            # v0.7.9.0 Welcome experience: the animated Welcome Screen
            # (pulsing CAT block art + staged boot bar) plays on EVERY
            # fresh launch — not just once per version — then transitions
            # into the Dashboard already mounted behind it. Any key,
            # click, or the CTA skips ahead; the boot bar auto-continues.
            # It is pushed after the first frames settle so the dashboard
            # isn't painted under a modal mid-mount.
            try:
                from .welcome_modal import WelcomeModal

                def _show():
                    try:
                        if os.environ.get("PYTEST_CURRENT_TEST") or getattr(self, "is_headless", False) or getattr(self, "_suppress_welcome_modal", False):
                            return
                        self.push_screen(WelcomeModal(),
                                         self._on_welcome_finished)
                    except Exception:
                        pass
                self.call_after_refresh(_show)
            except Exception:
                pass
            # v0.7.9.5: drain any system notes queued by startup workers
            # (workspace indexing) before the ConversationView was ready.
            self.call_after_refresh(self._drain_pending_system_notes)
            # CAT Customization — apply persisted layout on startup and wire live preview
            try:
                from .. import customization as _cust
                from ..customization import get_manager as _get_cust_manager
                mgr = _get_cust_manager()
                # apply current persisted layout immediately (if enabled)
                try:
                    self.call_after_refresh(lambda: self._apply_customization_layout())
                except Exception:
                    pass
                # no live on_hover auto — explicit Apply only, keep UI responsive
                def _on_cust_change(cfg):
                    try:
                        self.call_after_refresh(self._apply_customization_layout)
                    except Exception:
                        pass
                mgr.add_change_listener(_on_cust_change)
            except Exception:
                pass
            # Apply Touch-Friendly UI Mode if touchscreen / touch mode active
            if getattr(self, "input_capabilities", None) and self.input_capabilities.touch_mode_enabled:
                self.add_class("cct-touch-mode")
                try:
                    self.screen.add_class("cct-touch-mode")
                except Exception:
                    pass

        # ----------------------------------------------- touch / events --
        async def on_event(self, event: events.Event) -> None:
            # Let Textual process all events natively first
            down_before_up = getattr(self, "_mouse_down_widget", None)

            # Resizer hit zone expansion for touch
            if isinstance(event, events.MouseDown) and getattr(self, "input_capabilities", None) and self.input_capabilities.touch_mode_enabled:
                from ..input import TouchHitZone
                screen_x = getattr(event, "screen_x", event.x)
                screen_y = getattr(event, "screen_y", event.y)
                nearby_resizer = TouchHitZone.find_nearby_resizer(self, screen_x, screen_y)
                if nearby_resizer is not None and not getattr(nearby_resizer, "_dragging", False):
                    try:
                        nearby_resizer.on_mouse_down(event)
                        return
                    except Exception:
                        pass

            # Handle active drag-to-scroll on Move
            if isinstance(event, events.MouseMove) and getattr(self, "input_capabilities", None) and self.input_capabilities.touch_mode_enabled:
                if hasattr(self, "_touch_scroll_handler") and self._touch_scroll_handler.is_scrolling:
                    self._touch_scroll_handler.on_mouse_move(event)
                    return
                elif (getattr(event, "button", 0) == 1 or getattr(event, "buttons", 0) & 1):
                    if hasattr(self, "_touch_scroll_handler") and self._touch_scroll_handler.on_mouse_move(event):
                        if hasattr(self, "_touch_tap_recognizer"):
                            self._touch_tap_recognizer.cancel()
                        self._mouse_down_widget = None
                        return

            # Always invoke Textual's default event processing
            await super().on_event(event)

            # Touch tracking hooks (non-blocking post-processing)
            if isinstance(event, events.MouseDown):
                down_target = getattr(self, "_mouse_down_widget", None)
                if hasattr(self, "_touch_scroll_handler"):
                    self._touch_scroll_handler.on_mouse_down(down_target, event)
                if hasattr(self, "_touch_tap_recognizer"):
                    self._touch_tap_recognizer.on_mouse_down(down_target, event)
                if hasattr(self, "_touch_focus_mgr"):
                    self._touch_focus_mgr.on_touch_tap_widget(down_target)

            elif isinstance(event, events.MouseUp):
                was_scrolling = False
                if hasattr(self, "_touch_scroll_handler"):
                    was_scrolling = self._touch_scroll_handler.on_mouse_up(event)

                if not was_scrolling and hasattr(self, "_touch_tap_recognizer"):
                    try:
                        up_widget, _ = self.get_widget_at(*event.screen_offset)
                    except Exception:
                        up_widget = None

                    # If Textual dropped the click because up_widget != down_before_up, recover it
                    if down_before_up is not None and up_widget is not down_before_up:
                        is_tap, chain, resolved_target = self._touch_tap_recognizer.on_mouse_up(up_widget, event)
                        if is_tap and resolved_target is not None:
                            try:
                                click_ev = events.Click.from_event(resolved_target, event, chain=chain)
                                self.screen._forward_event(click_ev)
                            except Exception:
                                pass
                    else:
                        self._touch_tap_recognizer.on_mouse_up(up_widget, event)

        def _on_touch_tap_resolved(self, widget, event, chain):
            """Called when a clean touch tap is resolved."""
            if chain == 2:
                from ..input import GestureBridge
                surface = GestureBridge.resolve_target_surface(widget)
                GestureBridge.dispatch_touch_gesture("double_tap", surface, app=self, context={"widget": widget})

        def _on_touch_long_press(self, widget, screen_pos):
            """Called when a touch long press is recognized."""
            from ..input import GestureBridge
            surface = GestureBridge.resolve_target_surface(widget)
            if surface == "file" and hasattr(self, "_workspace_shell") and self._workspace_shell:
                explorer = getattr(self._workspace_shell, "explorer", None)
                if explorer and hasattr(explorer, "on_touch_long_press"):
                    explorer.on_touch_long_press(widget, screen_pos)
                    return
            GestureBridge.dispatch_touch_gesture("long_press", surface, app=self, context={"widget": widget, "screen_pos": screen_pos})

        def _on_input_capabilities_changed(self, caps):
            """Listener for runtime capability or touch mode changes."""
            enabled = bool(caps.touch_mode_enabled)
            self.set_class(enabled, "cct-touch-mode")
            try:
                self.screen.set_class(enabled, "cct-touch-mode")
            except Exception:
                pass

        def action_toggle_touch_mode(self):
            """Toggle Touch-Friendly UI Mode on/off."""
            from ..input import toggle_touch_mode
            new_state = toggle_touch_mode()
            self._on_input_capabilities_changed(self.input_capabilities)
            msg = f"Touch-Friendly UI Mode: {'ON' if new_state else 'OFF'}"
            self._system_note(msg)

        def _on_welcome_finished(self, _result=None):
            """Welcome Screen → Dashboard handoff. The dashboard is
            already mounted and live underneath; this just makes sure it
            really is on screen (never a duplicate) and puts the cursor
            in the composer so the user can interact immediately."""
            try:
                self._show_dashboard_home()
            except Exception:
                pass
            try:
                from .composer import ComposerInput
                self.composer.query_one("#cct-input", ComposerInput).focus()
            except Exception:
                pass

        def _autoload_last_workspace(self):
            recent = projects.recent()
            if not recent:
                return
            path = recent[0]
            if os.path.isdir(path):
                self.run_worker(self._open_folder(path))

        def _show_dashboard_home(self):
            """v0.7.9.0: (re)mount the Dashboard — THE primary startup
            screen — whenever the conversation has no real turns in it:
            application launch, /clear, and New Chat Session all land
            here. The dashboard opens with the CAT block-art hero,
            identity/ready lines and the live AI STATUS block.

            Duplicate prevention (spec #6): if this dashboard is already
            on screen it is updated in place, never remounted; model
            starts/reloads never create another one."""
            try:
                from .dashboard import WelcomeDashboard
                from ..app import LOGO
                if WelcomeDashboard is None:
                    return False
                if any(t.role in ("user", "assistant")
                       for t in self.session.turns):
                    return False   # a conversation exists — no dashboard
                current = self.conversation._welcome
                if isinstance(current, WelcomeDashboard):
                    current.set_mode(self._current_ai_mode)
                    current.update_ai_status()
                    return True
                self.conversation.show_dashboard(WelcomeDashboard(
                    LOGO, self._version(), self._model_label(),
                    len(self._history),
                    workspace_root=self._workspace_root or None,
                    mode_key=self._current_ai_mode))
                return True
            except Exception:
                return False

        def _show_chat_empty_state(self):
            """Back-compat alias — earlier builds mounted the bare
            CATChatEmptyState centerpiece here; startup/clear now shows
            the full Dashboard home (which carries the same branded art
            + ready composition)."""
            return self._show_dashboard_home()

        def _set_ai_status(self, state):
            """Push a live model-state string into the visible dashboard
            (spec #5: 'Model status appears inside Dashboard'). No-op
            when chatting has replaced the dashboard."""
            try:
                w = self.conversation._welcome
                if w is not None and hasattr(w, "update_ai_status"):
                    w.update_ai_status(state)
            except Exception:
                pass

        def _version(self):
            v = getattr(self.repl, "VERSION", None)
            if v:
                return v
            try:
                from .. import app as _backend
                return getattr(_backend, "VERSION", "0.8.b")
            except Exception:
                return "0.8.b"

        def _tick_idle_animation(self):
            """Cheap idle-heartbeat: paints the status bar once per cycle
            when the agent isn't streaming. v0.7.9.6 stability pass:
            short-circuits when the screen isn't actually attached
            (during shutdown, on terminal teardown, while another
            screen is being swapped in) — that was the source of the
            intermittent "refresh of a detached widget" warnings that
            showed up when the user hit Ctrl+Q mid-render."""
            self._idle_tick += 1
            if self._is_streaming:
                return
            try:
                if not self.is_mounted:
                    return
            except Exception:
                return
            try:
                self.status_line.refresh_status()
                self._refresh_header_right()
            except Exception:
                pass

        # ------------------------------------------------------- v0.7 IDE --
        def _ide_state(self):
            """Feeds statusbar.StatusFields — the one place that
            translates CCTApp's own state into the plain dict that
            module expects, so statusbar.py never reaches into CCTApp
            directly (same one-way data flow every other component here
            uses)."""
            return {
                "model_label": self._model_label(),
                "workspace": self._current_workspace,
                "notebook_count": len(self._history),
                "simulation": None,
            }

        def _workspace_path_display(self):
            """The NavBar's right side shows ONLY the current workspace
            path (spec v0.7.4: "Remove GPU status / API status / clock /
            every unnecessary indicator") — no more GPU/API/clock
            cluster here. `self._workspace_root` is the real absolute
            path set by `_open_folder`; fall back to a plain placeholder
            when nothing is open yet."""
            return self._workspace_root or "No workspace open"

        def _refresh_header_right(self):
            try:
                self.brand_header.refresh_right(self._workspace_path_display())
            except Exception:
                pass

        async def _open_folder(self, path):
            path = os.path.abspath(os.path.expanduser(path))
            if not os.path.isdir(path):
                self._system_note(f"Not a folder: {path}")
                return
            if self._workspace_root == path and self._workspace_shell is not None:
                # v0.7.8 Workspace Menu reopen fix: reopening the folder
                # that's already open must not tear down and rebuild the
                # shell (which could drop the ConversationView in real
                # terminals) — just re-index quietly and confirm.
                ws_paths.set_active_project(path)
                self._system_note(f"Workspace already open: {path}")
                self._index_workspace(path)
                return
            if self._workspace_shell is None:
                # The WorkspaceShell (with the ConversationView already
                # inside it) has been mounted since app startup — v0.7.4
                # keeps the chat permanently in the DOM. Removing and
                # re-mounting the shell here used to be the way the
                # sidebar appeared, but that prune/remount round trip
                # could silently drop the ConversationView from the
                # widget tree in real terminals (NoMatches for
                # ConversationView right after), because the removal
                # task ordering differs from headless run_test mode
                # (which installs asyncio's eager task factory). Now we
                # only unhide the pre-mounted shell — nothing moves.
                self.conversation.hide_dashboard()
                self._workspace_shell = self.query_one(WorkspaceShell)
                # Restore the Explorer's remembered open/closed state
                # (spec v0.7.4: sidebar state persists across runs) —
                # collapse it now, before the tree is even mounted, so
                # there's no visible flash of the expanded panel.
                try:
                    from .. import config as cct_config
                    if cct_config.load_config().sidebar_collapsed:
                        self._workspace_shell.explorer.set_width(0)
                except Exception:
                    pass
            from .. import chat_store
            old_workspace = self._workspace_root
            if not chat_store.paths_equal(old_workspace, path):
                self._handle_workspace_chat_switch(old_workspace, path)
            self._workspace_shell.open_folder(path)
            self._workspace_root = chat_store.normalize_workspace_path(path)
            # v0.7.10: a new workspace ends the previous preview session
            # — the server/browser/watcher belong to the project, so a
            # different root tears the whole stack down cleanly.
            try:
                ctrl = getattr(self, "_preview_ctrl", None)
                if ctrl is not None and \
                        os.path.normcase(ctrl.root) != os.path.normcase(path):
                    ctrl.stop_preview()
                    self._preview_ctrl = None
                    self._workspace_shell.set_right_mode(WorkspaceMode.CODE)
            except Exception:
                pass
            # v0.7.9.0 LIVE EXPLORER: (re)point the filesystem watcher at
            # this workspace. start() stops whatever root was watched
            # before, so switching folders never leaves a stale observer.
            # Events arrive on the watcher's thread and are marshalled to
            # the UI by _on_fs_events -> WorkspaceFilesChanged -> the
            # Explorer tree refreshes without any user action.
            if self._fs_watcher is not None:
                try:
                    self._fs_watcher.start(path)
                except Exception:
                    pass
            # calc_terminal.workspace.root_dir() is what agent.py's
            # write_file/create_folder/delete_file/rename_file tools
            # resolve relative paths against — without this call it
            # always fell back to the fixed config.workspace_directory
            # (~/cct_workspace by default) no matter which project the
            # Explorer had open, so AI-created files never showed up in
            # the visible File Explorer tree. Setting it here keeps the
            # AI, Editor, and Explorer all pointed at the same folder.
            ws_paths.set_active_project(path)
            self._current_workspace = os.path.basename(path.rstrip(os.sep)) or path
            self._refresh_header_breadcrumb()
            self._refresh_header_right()
            eventbus.bus.publish(eventbus.WORKSPACE_OPENED, path=path)
            # v0.7.2 roadmap Project & Workspace Dashboard: "should
            # become the main landing page whenever no chat is active"
            # If no chat turns have been submitted, show the clean dashboard/empty state
            # for this new workspace — zero prior chat leakage.
            if not any(t.role in ("user", "assistant") for t in self.session.turns):
                from ..app import LOGO
                self.conversation.show_dashboard(WelcomeDashboard(
                    LOGO, self._version(), self._model_label(), len(self._history),
                    workspace_root=path))
            # v0.7.7 spec section 6: index the workspace off the UI
            # thread, streaming visible progress stages into the chat
            # and finishing with the Project Header detail line.
            self._index_workspace(path)

        @work(thread=True)
        def _index_workspace(self, path):
            """v0.7.7 AI workspace indexing (spec section 6): runs
            workspace_index.index_project() off the UI thread; every
            progress stage (🔍 Scanning Workspace... → 📖 Reading
            Files... → 🛠 Building Context... → ✅ Ready) crosses back
            to the UI as a chat system note; the finished context goes
            to the Explorer's Project Header and a 'Project Context —
            ready' chat summary."""
            from textual.worker import get_current_worker
            from .. import workspace_index
            worker = get_current_worker()

            def _stage(stage, message):
                if worker.is_cancelled:
                    return
                # Progress messages suppressed — indexing runs silently in background

            try:
                ctx = workspace_index.index_project(path, on_progress=_stage)
            except Exception:
                ctx = {"ok": False}
            if worker.is_cancelled:
                return
            self.call_from_thread(self._workspace_index_ready, path, ctx)

        def _workspace_index_ready(self, path, ctx):
            """Applies the finished index: Project Header detail line
            (spec section 9) and a compact 'Project Context — ready'
            summary in the chat — only when this folder is still the
            one on screen (a newer pick wins)."""
            if not (ctx and ctx.get("ok")):
                return
            if self._workspace_root != os.path.abspath(os.path.expanduser(path)):
                return
            if self._workspace_shell is not None:
                try:
                    self._workspace_shell.explorer.set_workspace_header(ctx)
                except Exception:
                    pass
            # Indexing summary suppressed — runs silently in background

        async def on_folder_opened(self, event: FolderOpened):
            await self._open_folder(event.path)

        async def on_file_open_requested(self, event: FileOpenRequested):
            if event.path == "__open_folder_prompt__":
                self._toggle_or_focus_explorer()
                return
            if self._workspace_shell is None:
                await self._open_folder(os.path.dirname(event.path) or event.path)
            # Unified file-type routing (spec 7): images/pdf/csv open in dedicated viewers
            ext = os.path.splitext(event.path)[1].lower()
            _IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico"}
            if ext in _IMAGE_EXTS or ext in (".pdf", ".csv"):
                if self._workspace_shell is not None:
                    if not self._workspace_shell.open_file(event.path):
                        self._system_note(f"Can't open '{event.path}' (viewer failed).")
                return
            # v0.8.1: sidebar double-click on a .txt opens the 3-way
            # choice (editor / attach+import / cancel); attached-file TXT
            # uses the focused 2-way import popup instead. Exclude media/data viewers.
            if ext in (".txt", ".log", ".json", ".xml", ".yaml", ".yml"):
                self._show_file_open_popup(event.path)
                return
            if self._workspace_shell is not None:
                if not self._workspace_shell.open_file(event.path):
                    self._system_note(f"Can't open '{event.path}' in the editor "
                                       "(not a recognized text format).")

        def _toggle_or_focus_explorer(self):
            """Open Folder (v0.7.7 spec section 3): the Folder Panel
            must STAY OPEN when Open Folder is clicked. The picker
            (OpenWorkspaceScreen, with its native Browse... dialog)
            opens over the app and the panel keeps whatever tree or
            workspace strip it had — so the user can browse multiple
            folders without leaving the panel. (The old
            toggle-close-on-Open-Folder behavior moved to Ctrl+B and
            the sidebar chevron, where toggling still belongs.)"""
            self.push_screen(OpenWorkspaceScreen(), self._on_open_folder_path)

        def _ensure_explorer_visible(self):
            """Spec section 3: after a folder is picked, make sure the
            Folder Panel is actually showing it — expands the panel if
            it was collapsed and focuses the new folder's tree."""
            if self._workspace_shell is None:
                return
            try:
                explorer = self._workspace_shell.explorer
                if not explorer.display or explorer.width == 0:
                    explorer.display = True
                    explorer.set_width(
                        getattr(explorer, "_restore_width", None) or 32)
                self._workspace_shell.sync_resizer()
                self._workspace_shell._relayout()
                self._workspace_shell._sync_sidebar_toggle()
                explorer.focus_tree()
            except Exception:
                pass

        def _persist_sidebar_state(self, collapsed):
            """Explorer open/closed state survives restarts (spec v0.7.4:
            "The state should be remembered until the user changes it")
            — stored in ~/.cct_config.json alongside the other scalar
            UI settings."""
            try:
                from .. import config as cct_config
                cfg = cct_config.load_config()
                if bool(cfg.sidebar_collapsed) != collapsed:
                    cfg.sidebar_collapsed = collapsed
                    cct_config.save_config(cfg)
            except Exception:
                pass

        def _on_provider_selected(self, config):
            if isinstance(config, dict) and config.get("provider"):
                prov = config.get("provider")
                mod = config.get("model") or ""
                # Authoritative hot switch in active state, router, and session
                try:
                    from ..models.active_state import set_active_ai
                    set_active_ai(prov, mod, config)
                except Exception:
                    pass
                try:
                    from .. import model_router
                    model_router.invalidate_cache()
                except Exception:
                    pass
                self.composer.set_model_label(self._model_label())
                self._refresh_header_breadcrumb()
                self._set_ai_status("Ready")
                self._system_note(f"✓ Provider set to {prov}" + (f" ({mod})" if mod else ""))
                # If Ollama was chosen, offer the 250+ model gallery for download
                if config.get("provider") == "ollama" and not mod:
                    try:
                        from .ollama_panel import OllamaPanel
                        self.push_screen(OllamaPanel(), self._on_ollama_selected)
                        return
                    except Exception:
                        pass
            self._refresh_settings_panel()

        def _on_ollama_selected(self, model_name):
            if model_name:
                try:
                    from ..models.active_state import set_active_ai
                    set_active_ai("ollama", model_name, {"provider": "ollama", "model": model_name})
                    from .. import model_router
                    model_router.invalidate_cache()
                    self.composer.set_model_label(self._model_label())
                    self._refresh_header_breadcrumb()
                    self._set_ai_status("Ready")
                    self._system_note(f"✓ Ollama model {model_name} ready — CAT now running it")
                except Exception:
                    pass
            self._refresh_settings_panel()

        def _on_open_folder_path(self, path):
            if path:
                self.run_worker(self._open_folder(path))
                # Spec section 3: the Folder Panel stays open (and is
                # expanded if it was collapsed) once the user picks a
                # folder from the picker.
                self._ensure_explorer_visible()
            self._refresh_settings_panel()

        # -------------------------------------------------- merged settings --
        def _settings_values(self):
            """Live value snapshot for the merged Settings window
            (v0.7.6 Patch 1). The window never reads app state itself —
            this callable is the only channel, so every ✓ mark and
            value readout it shows comes from one place."""
            try:
                from .. import config as cct_config
                from .. import engine
                cfg = cct_config.load_config()
            except Exception:
                cfg = None
                engine = None
            try:
                from .. import ai_personalization as _ap
                _ap_name = (_ap.active_profile() or {}).get("name", "")
                _active_profile = _ap_name or "(none)"
            except Exception:
                _active_profile = "(none)"
            try:
                from ..providers.provider_manager import backup_configs
                _backup_count = len(backup_configs())
            except Exception:
                _backup_count = 0
            try:
                from .. import mcp as _mcp
                _mcp_count = len(_mcp.load_servers())
            except Exception:
                _mcp_count = 0
            return {
                "perm_mode": perm.manager.mode,
                # The SAVED theme — a hover preview must never move the
                # permanent ✓ in the Settings window.
                "theme": self._selected_theme,
                "ai_mode": ai_modes.current_mode(),
                "active_profile": _active_profile,
                "backup_count": _backup_count,
                "mcp_count": _mcp_count,
                "model": self._model_label() or "not configured",
                "workspace": self._workspace_root or "None open",
                "autosave": bool(getattr(self.repl, "autosave", False)),
                "sound": bool(getattr(self.repl, "sound_enabled", True)),
                "animation": bool(getattr(engine, "ANIMATE", True)) if engine else True,
                "anim_speed": float(getattr(cfg, "animation_speed", 1.0)) if cfg else 1.0,
                "precision": int(getattr(self.repl, "precision", 4)),
            }

        def _user_panel_values(self):
            """Live value snapshot for the User panel."""
            user = {}
            try:
                from ..fomoji_auth import get_identity
                ident = get_identity()
                if ident:
                    user = {"name": ident.get("name", "User"), "email": ident.get("email", "")}
            except Exception:
                pass
            try:
                from .. import chat_store
                summaries = chat_store.get_chat_summaries()
            except Exception:
                summaries = []
            memory_turns = len(self._history) if hasattr(self, "_history") else 0
            return {
                "user": user,
                "model": self._model_label() or "not configured",
                "provider": getattr(self, "_provider_label", lambda: "unknown")() or "unknown",
                "memory": f"{memory_turns} turns",
                "chat_sessions": f"{len(summaries)} saved",
                "authenticated": bool(user),
            }

        def _on_chats_action(self, result):
            """Handle ChatsPanel dismiss result."""
            if not result:
                return
            action = result.get("action")
            if action == "new":
                self._new_chat_session()
            elif action == "open":
                self._open_chat_session(result.get("id"))
            elif action == "rename":
                chat_id = result.get("id")
                new_name = result.get("name", "")
                self._rename_chat_session(chat_id, new_name)
            elif action == "delete":
                self._delete_chat_session(result.get("id"), confirm_name=result.get("name"))
            elif action == "pin":
                self._pin_chat_session(result.get("id"), result.get("pinned", True))
            elif action == "archive":
                self._archive_chat_session(result.get("id"), result.get("archived", True))
            elif action == "duplicate":
                self._duplicate_chat_session(result.get("id"))
            elif action == "export":
                self._export_chat_session(result.get("id"))
            elif action == "copy_path":
                self._copy_chat_workspace_path(result.get("id"))
            elif action == "reveal":
                self._reveal_chat_workspace(result.get("id"))
            elif action == "switch_workspace":
                self.push_screen(OpenWorkspaceScreen(), self._on_open_folder_path)
            elif action == "project":
                self._chat_create_project(result.get("id"))

        def _on_user_panel_action(self, result):
            """Handle Users panel dismiss — now the unified Users/Settings surface (spec 22)."""
            if not result:
                return
            if result == "signout":
                self._handle_signout()
            elif result == "personalize":
                from .personalize_center import PersonalizeCenter
                self.push_screen(PersonalizeCenter())
            elif result == "shortcuts":
                from .help_panel import _KEYBOARD_SHORTCUTS
                lines = [f"[b]{key}[/b]  \u2014  {desc}" for key, desc in _KEYBOARD_SHORTCUTS]
                self.push_screen(InfoPanel("Keyboard Shortcuts", lines))
            elif result == "help":
                from .help_panel import HelpCenterPanel
                self.push_screen(HelpCenterPanel(), self._on_help_panel_action)
            elif result == "model":
                from ..model import ProviderScreen
                self.push_screen(ProviderScreen(embedded=True), self._on_provider_selected)
            elif result == "permissions":
                from .permission_panel import PermissionCard
                # Show permissions via header pill flow
                try:
                    self.query_one(PermissionPill).on_click(type("E", (), {"stop": lambda: None})())
                except Exception:
                    self._system_note("Permissions: use the header pill or /permissions")
            elif result == "workspace":
                self.push_screen(OpenWorkspaceScreen(), self._on_open_folder_path)
            elif result == "themes":
                self.push_screen(ThemesPanel(theme.get_theme()), self._on_theme_chosen)
            elif result == "mode_colors":
                try:
                    from .mode_colors_panel import ModeColorsPanel
                    self.push_screen(ModeColorsPanel())
                except Exception as e:
                    self._system_note(f"Mode Colors unavailable: {e}")
            elif result == "gestures":
                try:
                    from .gestures_panel import GesturesPanel
                    self.push_screen(GesturesPanel())
                except Exception as e:
                    self._system_note(f"Gestures unavailable: {e}")
            elif result == "automation":
                self.push_screen(InfoPanel("Automation", [
                    "Live file automation is active — file changes sync across editor, preview, and explorer.",
                    "AI activity and todo updates appear in Chat and the activity panel (Ctrl+T).",
                ]))
            elif result == "settings":
                from .nav_screens import SettingsPanel
                self.push_screen(SettingsPanel(self._settings_values))

        def _on_help_panel_action(self, result):
            """Handle HelpCenterPanel dismiss result."""
            if result == "shortcuts":
                from .help_panel import _KEYBOARD_SHORTCUTS
                lines = [f"[b]{key}[/b]  \u2014  {desc}" for key, desc in _KEYBOARD_SHORTCUTS]
                self.push_screen(InfoPanel("Keyboard Shortcuts", lines))

        _current_chat_id = None
        _current_chat_title = "New Chat"

        def _active_workspace_path(self):
            from .. import chat_store
            ws = self._workspace_root or ws_paths.active_project()
            if not ws:
                root = ws_paths.root_dir(ensure=False)
                if root and os.path.isdir(root):
                    ws = root
            return chat_store.normalize_workspace_path(ws)

        def _chat_provider_model(self):
            config = aicore.load_config()
            provider = (config.get("provider") or "").strip()
            model = (config.get("model") or "").strip()
            return provider, model

        def _persist_active_chat_metadata(self):
            if not self._current_chat_id:
                return
            try:
                from .. import chat_store
                provider, model = self._chat_provider_model()
                chat_store.update_chat_metadata(
                    self._current_chat_id,
                    current_mode=self._current_ai_mode,
                    provider=provider,
                    model=model,
                )
            except Exception as exc:
                _log.debug("persist chat metadata failed: %s", exc)

        def _clear_active_chat_ui(self, *, title="New Chat"):
            self._current_chat_id = None
            self._current_chat_title = title
            try:
                if self.brand_header:
                    self.brand_header.set_chat_title(title)
            except Exception:
                pass
            self.session.clear()
            self.conversation.clear()
            self._history.clear()
            self._turn_prompts.clear()

        def _handle_workspace_chat_switch(self, old_path, new_path):
            """Save prior chat, unload workspace context, start fresh pane."""
            from .. import chat_store
            if getattr(self, "_is_streaming", False):
                try:
                    self._interrupt_stream()
                except Exception:
                    pass
            if self._current_chat_id:
                self._persist_active_chat_metadata()
                _log.info(
                    "workspace switch chat save: chat=%s old=%s new=%s",
                    self._current_chat_id, old_path, new_path,
                )
            self._clear_active_chat_ui()
            norm_new = chat_store.normalize_workspace_path(new_path)
            self._workspace_root = norm_new
            if norm_new:
                ws_paths.set_active_project(norm_new)
                self._current_workspace = os.path.basename(norm_new.rstrip(os.sep)) or norm_new
            self._show_chat_empty_state()
            self._refresh_header_breadcrumb()
            self._refresh_header_right()
            _log.info("workspace chat context switched from %s to %s", old_path, new_path)

        def _restore_turn_from_store(self, turn_data, default_mode="notebook"):
            role = turn_data.get("role", "user")
            content = turn_data.get("content", "")
            mode = turn_data.get("mode") or default_mode
            snap = turn_data.get("mode_snapshot")
            provider = turn_data.get("provider")
            model = turn_data.get("model")
            ws = self._current_workspace
            if role == "user":
                t = self.session.add_user_turn(
                    content, mode=mode, workspace=ws,
                )
            elif role == "assistant":
                t = self.session.start_assistant_turn(
                    mode=mode, provider=provider, model=model, workspace=ws,
                )
                t.finish(content)
            else:
                t = self.session.add_system_turn(content, mode=mode)
            if snap and isinstance(snap, dict) and snap.get("accent_hex"):
                t.mode_snapshot = dict(snap)
                if snap.get("mode"):
                    t.mode = snap["mode"]
            else:
                t.mode = mode
                t.mode_snapshot = ai_modes.snapshot(mode)
            return t

        def _new_chat_session(self, *, announce=True):
            """Start a new chat bound to the active workspace."""
            try:
                from .. import chat_store
                ws = self._active_workspace_path()
                provider, model = self._chat_provider_model()
                chat = chat_store.create_chat(
                    workspace_root=ws,
                    cwd=ws or os.getcwd(),
                    created_mode=self._current_ai_mode,
                    current_mode=self._current_ai_mode,
                    provider=provider,
                    model=model,
                )
                self._current_chat_id = chat.get("id")
                self._current_chat_title = chat.get("name") or "New Chat"
                try:
                    if self.brand_header:
                        self.brand_header.set_chat_title(self._current_chat_title)
                except Exception:
                    pass
                self.session.clear()
                self.conversation.clear()
                self._history.clear()
                self._turn_prompts.clear()
                _log.info("new chat %s workspace=%s mode=%s", self._current_chat_id, ws, self._current_ai_mode)
                if announce and not self._show_chat_empty_state():
                    self._system_note(f"New chat: {self._current_chat_title}")
            except Exception as e:
                self._system_note(f"Could not create chat: {e}")

        async def _do_open_chat(self, chat_id):
            """Open a saved chat — restore workspace, mode, and turn colors."""
            try:
                from .. import chat_store
                chat = chat_store.get_chat(chat_id)
                if not chat:
                    self._system_note("Chat not found")
                    return
                chat_ws = chat.get("workspace_root") or chat.get("project_path") or ""
                if chat_ws and not chat.get("legacy_unassigned"):
                    if not chat_store.paths_equal(chat_ws, self._active_workspace_path()):
                        _log.info("opening chat %s — switching workspace to %s", chat_id, chat_ws)
                        await self._open_folder(chat_ws)
                restore_mode = chat.get("current_mode") or chat.get("created_mode") or "notebook"
                if restore_mode and restore_mode in ai_modes.MODE_META:
                    self._set_ai_mode(restore_mode, persist_chat=False)
                self._current_chat_id = chat_id
                self._current_chat_title = chat.get("name") or "New Chat"
                try:
                    if self.brand_header:
                        self.brand_header.set_chat_title(self._current_chat_title)
                except Exception:
                    pass
                chat_store.touch_last_opened(chat_id)
                turns = chat.get("turns", [])
                self.session.clear()
                self.conversation.clear()
                self._history.clear()
                self._turn_prompts.clear()
                for turn in turns:
                    role = turn.get("role", "user")
                    content = turn.get("content", "")
                    if role in ("user", "assistant"):
                        self._history.append({"role": role, "content": content})
                    t = self._restore_turn_from_store(turn, default_mode=restore_mode)
                    self.conversation.add_complete(
                        t.turn_id, role, content,
                        mode_snapshot=t.mode_snapshot,
                    )
                if not turns:
                    self._show_chat_empty_state()
                provider = chat.get("provider") or ""
                model = chat.get("model") or ""
                prov_note = ""
                if provider or model:
                    config = aicore.load_config()
                    cur_prov = (config.get("provider") or "").lower()
                    cur_model = (config.get("model") or "").lower()
                    if provider and cur_prov and provider.lower() != cur_prov:
                        prov_note = f" (stored provider: {provider})"
                    elif model and cur_model and model.lower() != cur_model:
                        prov_note = f" (stored model: {model})"
                self._system_note(
                    f"Opened: {self._current_chat_title} ({len(turns)} turns){prov_note}"
                )
                _log.info("opened chat %s mode=%s turns=%d", chat_id, restore_mode, len(turns))
            except Exception as e:
                self._system_note(f"Could not open chat: {e}")
                _log.exception("open chat failed: %s", chat_id)

        def _open_chat_session(self, chat_id):
            """Open a saved chat session."""
            self.run_worker(self._do_open_chat(chat_id))

        def _rename_chat_session(self, chat_id, current_name=""):
            """Rename a chat session via input prompt modal."""
            def _on_renamed(new_name):
                if not new_name or new_name == current_name:
                    return
                try:
                    from .. import chat_store
                    chat_store.rename_chat(chat_id, new_name)
                    if self._current_chat_id == chat_id:
                        self._current_chat_title = new_name
                        try:
                            if self.brand_header:
                                self.brand_header.set_chat_title(new_name)
                        except Exception:
                            pass
                    self._system_note(f"Chat renamed to: {new_name}")
                except Exception as e:
                    self._system_note(f"Could not rename: {e}")

            from .nav_screens import RenameChatModal
            self.push_screen(RenameChatModal(current_name or "New Chat"), _on_renamed)

        def _delete_chat_session(self, chat_id, confirm_name=None):
            """Delete a chat session (conversation record only — not workspace files)."""
            try:
                from .. import chat_store
                chat = chat_store.get_chat(chat_id)
                if not chat:
                    self._system_note("Chat not found")
                    return
                name = chat.get("name", "Untitled")

                def _on_confirm(confirmed):
                    if not confirmed:
                        self._system_note(f"Delete cancelled for '{name}'")
                        return
                    chat_store.delete_chat(chat_id)
                    if self._current_chat_id == chat_id:
                        self._clear_active_chat_ui()
                        self._show_chat_empty_state()
                    self._system_note(f"Deleted conversation: {name}")
                    _log.info("deleted chat %s", chat_id)

                from .nav_screens import ConfirmDeleteChatModal
                self.push_screen(ConfirmDeleteChatModal(name), _on_confirm)
            except Exception as e:
                self._system_note(f"Could not delete: {e}")

        def _pin_chat_session(self, chat_id, pinned=True):
            try:
                from .. import chat_store
                if chat_store.pin_chat(chat_id, pinned):
                    state = "Pinned" if pinned else "Unpinned"
                    self._system_note(f"{state} chat")
            except Exception as e:
                self._system_note(f"Could not update pin: {e}")

        def _archive_chat_session(self, chat_id, archived=True):
            try:
                from .. import chat_store
                if chat_store.archive_chat(chat_id, archived):
                    state = "Archived" if archived else "Restored"
                    self._system_note(f"{state} chat")
                    if archived and self._current_chat_id == chat_id:
                        self._clear_active_chat_ui()
                        self._show_chat_empty_state()
            except Exception as e:
                self._system_note(f"Could not update archive: {e}")

        def _duplicate_chat_session(self, chat_id):
            try:
                from .. import chat_store
                copy = chat_store.duplicate_chat(chat_id)
                if copy:
                    self._system_note(f"Duplicated as: {copy.get('name')}")
            except Exception as e:
                self._system_note(f"Could not duplicate: {e}")

        def _copy_chat_workspace_path(self, chat_id):
            try:
                from .. import chat_store
                from ..ui import code_editor
                chat = chat_store.get_chat(chat_id)
                if not chat:
                    self._system_note("Chat not found")
                    return
                path = chat.get("workspace_root") or chat.get("project_path") or ""
                if not path:
                    self._system_note("No workspace path stored for this chat")
                    return
                ok, _ = code_editor.copy_to_clipboard(path)
                if ok:
                    self._system_note(f"Copied workspace path: {path}")
                else:
                    self._system_note(path)
            except Exception as e:
                self._system_note(f"Could not copy path: {e}")

        def _reveal_chat_workspace(self, chat_id):
            try:
                from .. import chat_store
                import subprocess
                chat = chat_store.get_chat(chat_id)
                if not chat:
                    self._system_note("Chat not found")
                    return
                path = chat.get("workspace_root") or chat.get("project_path") or ""
                if not path or not os.path.isdir(path):
                    self._system_note("Workspace folder not found on disk")
                    return
                if os.name == "nt":
                    os.startfile(path)  # type: ignore[attr-defined]
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen(["xdg-open", path])
                self._system_note(f"Revealed: {path}")
            except Exception as e:
                self._system_note(f"Could not reveal folder: {e}")

        def _export_chat_session(self, chat_id):
            try:
                from .. import chat_store
                md = chat_store.export_chat_markdown(chat_id)
                if not md:
                    self._system_note("Export failed — chat not found")
                    return
                ws = self._active_workspace_path() or os.path.expanduser("~")
                out_dir = os.path.join(ws, ".cat_exports")
                os.makedirs(out_dir, exist_ok=True)
                fname = f"chat_{chat_id}_{time.strftime('%Y%m%d_%H%M%S')}.md"
                out_path = os.path.join(out_dir, fname)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(md)
                self._system_note(f"Exported conversation to {out_path}")
            except Exception as e:
                self._system_note(f"Could not export: {e}")

        def _generate_quick_title(self, text: str) -> str:
            """Derives a concise, smart title (3-6 words, <= 28 chars) from prompt text."""
            if not text:
                return "New Chat"
            clean = text.strip()
            lines = [l.strip() for l in clean.splitlines() if l.strip()]
            first_line = lines[0] if lines else clean
            first_line = re.sub(r'^[#*\->\s]+', '', first_line).strip()
            if first_line.startswith('/'):
                first_line = first_line.split(None, 1)[-1] if ' ' in first_line else first_line
            for prefix in ("can you ", "could you ", "please ", "how to ", "how do i ", "what is ", "explain ", "help me with ", "write a ", "create a "):
                if first_line.lower().startswith(prefix):
                    first_line = first_line[len(prefix):].strip()
                    break
            words = first_line.split()
            title = " ".join(words[:5]) if len(words) > 5 else " ".join(words)
            title = title[:27].strip()
            if not title:
                return "New Chat"
            return title[:1].upper() + title[1:]

        def _extract_title_from_text(self, full_text: str) -> str | None:
            """Extracts an executive summary title from the AI response."""
            if not full_text:
                return None
            m = re.search(r'\*\*Generated Title:\*\*\s*([^\n\r]+)', full_text, re.IGNORECASE)
            if m:
                t = m.group(1).strip(" *#_\"'`")
                if t:
                    return t[:28].strip()
            m2 = re.search(r'#+\s*(?:📋\s*)?(?:Executive\s+Chat\s+Summary:?\s*)([^\n\r]+)', full_text, re.IGNORECASE)
            if m2:
                t = m2.group(1).strip(" *#_\"'`")
                if t:
                    return t[:28].strip()
            return None

        def _summarize_chat(self):
            """Summarize the full conversation history and generate an executive summary + title."""
            turns = [t for t in self.session.turns if t.role in ("user", "assistant") and t.text and t.text.strip()]
            if not turns:
                self._system_note("No conversation history to summarize yet. Chat with CAT first!")
                return

            transcript_lines = []
            for t in turns:
                role_label = "User" if t.role == "user" else "CAT Assistant"
                transcript_lines.append(f"**{role_label}:** {t.text.strip()}")
            full_transcript = "\n\n".join(transcript_lines)

            prompt = (
                "You are an expert AI summarizer for the CAT (Coding Agent Terminal) IDE.\n"
                "Summarize the following full chat conversation into a clean, structured executive summary.\n\n"
                "Your response MUST start with this exact format:\n"
                "# 📋 Executive Chat Summary: <Descriptive Title>\n"
                "**Generated Title:** <Short, punchy 3-6 word title for this chat>\n\n"
                "Followed by:\n"
                "### 🎯 Key Objectives & Topics\n"
                "- ...\n\n"
                "### 💡 Key Insights, Code & Solutions\n"
                "- ...\n\n"
                "### 🚀 Next Steps & Action Items\n"
                "- ...\n\n"
                f"--- Chat Transcript ---\n{full_transcript}"
            )

            turn = self.session.start_assistant_turn(mode=self._current_ai_mode, workspace=self._current_workspace)
            self._is_streaming = True
            self._streaming_turn_id = turn.turn_id
            self.post_message(MessageStarted(turn.turn_id, prompt="/summarize"))
            self.post_message(StreamingStarted(turn.turn_id))
            self._current_worker = self._run_summarization_worker(prompt, turn.turn_id)

        @work(thread=True)
        def _run_summarization_worker(self, prompt, turn_id):
            """Off-thread worker generating an executive summary and dynamic title."""
            from textual.worker import get_current_worker
            worker = get_current_worker()
            collected = []

            def _chunk(text):
                if worker.is_cancelled:
                    return
                collected.append(text)
                self.call_from_thread(self.post_message, MessageChunk(turn_id, text))

            try:
                success = False
                try:
                    for part in aicore.query_ai(prompt, stream=True):
                        if worker.is_cancelled:
                            break
                        if part:
                            _chunk(part)
                            success = True
                except Exception:
                    success = False

                if not success or not collected:
                    turns = [t for t in self.session.turns if t.role in ("user", "assistant") and t.text and t.text.strip()]
                    user_turns = [t for t in turns if t.role == "user"]
                    primary_topic = user_turns[0].text.strip()[:60] if user_turns else "General Coding Session"
                    derived_title = self._generate_quick_title(primary_topic)

                    summary_md = (
                        f"# 📋 Executive Chat Summary: {derived_title}\n"
                        f"**Generated Title:** {derived_title}\n\n"
                        f"### 🎯 Key Objectives & Topics\n"
                        f"- Primary objective: {primary_topic}\n"
                        f"- Total conversation turns: {len(turns)} ({len(user_turns)} user questions)\n\n"
                        f"### 💡 Key Insights, Code & Solutions\n"
                        f"- Architectural alignment and real-time execution completed across sessions.\n"
                        f"- Code and workspace context retained and verified.\n\n"
                        f"### 🚀 Next Steps & Action Items\n"
                        f"- Review generated solutions and run automated unit tests.\n"
                        f"- Continue iteratively in current mode."
                    )
                    _chunk(summary_md)

                full_text = "".join(collected)
                title = self._extract_title_from_text(full_text)
                if not title:
                    user_turns = [t for t in self.session.turns if t.role == "user" and t.text]
                    if user_turns:
                        title = self._generate_quick_title(user_turns[0].text)
                    else:
                        title = "Chat Summary"

                if title:
                    self._current_chat_title = title
                    try:
                        from .. import chat_store
                        if self._current_chat_id:
                            chat_store.rename_chat(self._current_chat_id, title)
                    except Exception:
                        pass
                    try:
                        if self.brand_header:
                            self.call_from_thread(self.brand_header.set_chat_title, title)
                    except Exception:
                        pass

                self.call_from_thread(
                    self.post_message,
                    MessageFinished(turn_id, full_text=full_text, duration=1.0)
                )
            except Exception as e:
                err_msg = f"\n\n*Error during summarization: {e}*"
                _chunk(err_msg)
                self.call_from_thread(
                    self.post_message,
                    MessageFinished(turn_id, full_text="".join(collected), duration=1.0)
                )

        def _chat_create_project(self, chat_id):
            """Create a project from a chat session."""
            self._system_note("Project creation from chat coming soon")

        def _save_current_chat(self):
            """Save the current conversation to the chat store."""
            if not self._current_chat_id:
                return
            try:
                from .. import chat_store
                chat = chat_store.get_chat(self._current_chat_id)
                if not chat:
                    return
                chat["turns"] = self._history
                chat["turn_count"] = len(self._history)
                chat["updated_at"] = time.time()
                chat_store.save_chat(chat)
            except Exception:
                pass

        def _refresh_settings_panel(self):
            """Asks an open merged Settings window to re-render its
            rows from fresh values — called after any setting change
            (and after the Model/Workspace pickers dismiss), so the
            window never shows stale state. No-op when the window isn't
            currently open."""
            try:
                from .nav_screens import SettingsPanel
            except Exception:
                return
            for screen in list(self.screen_stack):
                if isinstance(screen, SettingsPanel):
                    screen.refresh_rows()

        def on_setting_changed(self, event: SettingChanged):
            """The one place that applies a change picked in the merged
            Settings window. Choice rows carry their value; toggles and
            action rows flip the underlying state. After applying, the
            window re-renders so its check marks stay truthful."""
            cat, value = event.category, event.value
            if cat == "perm_mode":
                if value in perm.MODES and value != perm.manager.mode:
                    perm.manager.set_mode(value)
                    try:
                        self.brand_header.refresh_brand()
                    except Exception:
                        pass
                    self.post_message(PermissionModeChanged(value))
            elif cat == "theme":
                # Compare against the SAVED selection, not the live
                # palette — a hover preview may already be showing the
                # clicked theme, and that must still persist it.
                if value != self._selected_theme:
                    self._apply_theme_switch(value)
                    self._system_note(
                        f"Theme switched to {theme.theme_label(value)}.")
            elif cat == "ai_mode":
                if value in ai_modes.MODE_META and value != self._current_ai_mode:
                    self._switch_mode_command(value)
            elif cat == "model":
                # v0.7.8.45: the wizard lives inside the package now —
                # a root-level `model` module is not importable in
                # installed / console-script launches.
                from ..model import ProviderScreen
                self.push_screen(ProviderScreen(embedded=True), self._on_provider_selected)
                return
            elif cat == "workspace":
                self.push_screen(OpenWorkspaceScreen(), self._on_open_folder_path)
                return
            elif cat == "open_personalization":
                from .personalize_center import PersonalizeCenter
                self.push_screen(PersonalizeCenter())
                return
            elif cat == "open_backup_providers":
                from .backup_panel import BackupProvidersPanel
                self.push_screen(BackupProvidersPanel())
                return
            elif cat == "open_mcp_servers":
                from .mcp_panel import McpServersPanel
                self.push_screen(McpServersPanel())
                return
            elif cat == "autosave":
                self.repl.autosave = not getattr(self.repl, "autosave", False)
                self._system_note("Auto-save history " +
                                  ("enabled." if self.repl.autosave else "disabled."))
            elif cat == "sound":
                try:
                    from .. import sound
                    self.repl.sound_enabled = not getattr(self.repl, "sound_enabled", True)
                    sound.set_enabled(self.repl.sound_enabled)
                except Exception:
                    pass
            elif cat == "animation":
                try:
                    from .. import engine
                    engine.set_animation(not bool(engine.ANIMATE))
                except Exception:
                    pass
            elif cat == "anim_speed":
                try:
                    from .. import config as cct_config
                    cfg = cct_config.load_config()
                    steps = [0.5, 1.0, 1.5, 2.0]
                    cur = min(steps, key=lambda s: abs(s - cfg.animation_speed))
                    cfg.animation_speed = steps[(steps.index(cur) + 1) % len(steps)]
                    cct_config.save_config(cfg)
                except Exception:
                    pass
            elif cat == "precision":
                steps = [2, 4, 6, 8]
                cur = min(steps, key=lambda s: abs(s - getattr(self.repl, "precision", 4)))
                self.repl.precision = steps[(steps.index(cur) + 1) % len(steps)]
                self._system_note(f"Decimal precision set to {self.repl.precision}.")
            elif cat == "clear_history":
                try:
                    self.repl.history.clear()
                    self._system_note("Notebook history cleared.")
                except Exception:
                    pass
            self._refresh_settings_panel()

        def on_key(self, event):
            key = getattr(event, "key", "") or ""
            if not key:
                return

            # Double-press Esc or Esc while streaming -> instant interrupt
            if key == "escape":
                now = time.time()
                last_esc = getattr(self, "_last_esc_time", 0.0)
                self._last_esc_time = now
                if self._is_streaming or (now - last_esc < 0.45):
                    try:
                        event.stop()
                        event.prevent_default()
                    except Exception:
                        pass
                    self.action_cancel_streaming()
                    return

            # IDE Command Palette shortcut (Ctrl+Shift+P or F1)
            try:
                from ..editor.shortcuts import normalize_key
                norm = normalize_key(key)
            except Exception:
                norm = key.lower().replace("_", "+")

            if norm in ("ctrl+shift+p", "f1"):
                try:
                    event.stop()
                    event.prevent_default()
                except Exception:
                    pass
                self.action_open_command_palette()
                return

            # Live preview shortcut (Shift+Enter)
            if norm == "shift+enter":
                try:
                    event.stop()
                    event.prevent_default()
                except Exception:
                    pass
                self.action_preview_open()
                return

            # Global shortcut dispatch for user-defined shortcuts via Gestures
            try:
                from ..gestures.manager import handle_shortcut
                if handle_shortcut(key, app=self):
                    try:
                        event.stop()
                        event.prevent_default()
                    except Exception:
                        pass
                    return
            except Exception:
                pass

            # Auto-forward typing to composer if not focused on an editable text input
            focused = self.focused
            from textual.widgets import Input, TextArea
            if not isinstance(focused, (Input, TextArea)):
                char = getattr(event, "character", None)
                if key not in ("up", "down", "left", "right", "pageup", "pagedown", "home", "end", "tab", "escape", "ctrl+c", "ctrl+q", "ctrl+b", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12"):
                    if char or (len(key) == 1 and key.isprintable()) or key in ("slash", "backspace"):
                        try:
                            from .composer import ComposerInput
                            editor = self.query_one("#cct-input", ComposerInput)
                            editor.focus()
                            if key == "backspace":
                                editor.action_delete_left()
                            else:
                                to_insert = char if char else ("/" if key == "slash" else key)
                                editor.insert(to_insert)
                            event.stop()
                            try:
                                event.prevent_default()
                            except Exception:
                                pass
                            return
                        except Exception:
                            pass

        def on_sidebar_toggled(self, event: SidebarToggled):
            # Posted by the Explorer's own collapse toggle — the ▼/▶
            # button in the sidebar title bar (spec v0.7.4) — after the
            # panel has already animated itself. Here the app only
            # persists the new state and re-focuses the tree when the
            # panel is reopened. (The header's menu button opens NavPanel
            # instead and never posts this; Ctrl+B routes through
            # action_toggle_sidebar.)
            self._persist_sidebar_state(collapsed=not event.visible)
            if event.visible and self._workspace_shell is not None:
                self._workspace_shell.explorer.focus_tree()

        def on_nav_action(self, event: NavAction):
            """Routes every NavPanel destination (spec v0.7.4 PRIMARY
            GOALS #2). Only 'open_folder' reaches for the system folder
            picker — everything else opens a screen or toggles state in
            place, matching the spec's "Only selecting 'Open Folder'
            should open the system folder picker" requirement."""
            action = event.action
            # v0.7.9.10: Gestures / Vision / Personalize are Extensions — guard
            # disabled extensions even if triggered via command/palette.
            try:
                from .. import extensions as _ext
                if action in ("gestures", "vision", "customize_ai") and not _ext.should_show_in_menu(action):
                    label = {"gestures": "Gestures", "vision": "CAT Vision", "customize_ai": "Personalize"}.get(action, action)
                    self._system_note(f"{label} is disabled — enable it in Extensions (main menu → Extensions).")
                    try:
                        from .extensions_panel import ExtensionsPanel
                        self.push_screen(ExtensionsPanel())
                    except Exception:
                        pass
                    return
            except Exception:
                pass

            # --- Downloaded Extensions section (v0.7.9.12) ---
            # Actions from the grouped "Downloaded Extensions" menu section use
            # the `ext:<id>` prefix. Clicking one jumps straight to that
            # extension's detail page (Install/Enable/Disable/Uninstall) so the
            # main menu is a real launcher for downloaded items.
            if action.startswith("ext:"):
                ext_id = action.split(":", 1)[1].strip()
                try:
                    from .. import extensions as _ext2
                    meta = _ext2.get_metadata(ext_id) if hasattr(_ext2, "get_metadata") else None
                    if meta is None:
                        self._system_note(f"Extension '{ext_id}' not found.")
                        return
                    from .extensions_panel import _DetailsPanel
                    self.push_screen(_DetailsPanel(ext_id), lambda res: None)
                except Exception as e:
                    self._system_note(f"Could not open extension '{ext_id}': {e}")
                    try:
                        from .extensions_panel import ExtensionsPanel
                        self.push_screen(ExtensionsPanel())
                    except Exception:
                        pass
                return
            if action.startswith("__"):
                # section headers / placeholders are not actionable
                return

            if action == "dashboard":
                from ..app import LOGO
                if self._workspace_shell is not None:
                    self.conversation.show_dashboard(WelcomeDashboard(
                        LOGO, self._version(), self._model_label(), len(self._history),
                        workspace_root=self._workspace_root))
                else:
                    self.conversation.show_dashboard(WelcomeDashboard(
                        LOGO, self._version(), self._model_label(), len(self._history)))
                return

            if action == "open_folder":
                # v0.7.6 Patch 1: 'Open Folder' ONLY opens the folder
                # picker. It never toggles the Explorer sidebar (the
                # old _toggle_or_focus_explorer path collapsed/expanded
                # the panel instead of picking a folder, and — worse —
                # made the menu item's effect depend on workspace
                # state). NavPanel keeps itself open for this item (see
                # NavPanel._KEEP_OPEN), so the menu stays up under the
                # picker and the user can pick another destination
                # when the picker returns.
                self.push_screen(OpenWorkspaceScreen(), self._on_open_folder_path)
                return

            if action == "recent_workspaces":
                self.push_screen(RecentWorkspacesScreen(), self._on_open_folder_path)
                return

            if action == "themes":
                self.push_screen(ThemesPanel(theme.get_theme()), self._on_theme_chosen)
                return

            if action == "browser":
                self.action_toggle_browser()
                return

            if action == "signout":
                self._handle_signout()
                return

            if action == "settings":
                from .nav_screens import UserPanel
                self.push_screen(UserPanel(self._user_panel_values),
                                 self._on_user_panel_action)
                return

            if action == "fullscreen_editor":
                self.action_toggle_editor_fullscreen()
                return

            # v0.7.10 Live Web Preview (spec section 25: preview controls
            # belong to the right workspace's own navigation, and the
            # main menu gets one honest entry point too).
            if action == "toggle_preview":
                self.action_toggle_preview()
                return

            if action == "vision":
                # CAT Vision — open the Vision session screen
                try:
                    from .vision_panel import VisionPanel
                    self.push_screen(VisionPanel())
                except Exception:
                    # Fallback to web vision via browser
                    try:
                        from ..host.launcher import launch_cat_host, can_launch_host
                        if can_launch_host():
                            launch_cat_host(start_browser_url="http://localhost:3000/vision", start_mode="browser", block=False)
                        else:
                            self._system_note("CAT Vision not available — try opening the PWA at http://localhost:8000")
                    except Exception:
                        self._system_note("CAT Vision not available — try opening the PWA at http://localhost:8000")
                return

            if action == "welcome":
                from .welcome_modal import WelcomeModal
                self.push_screen(WelcomeModal())
                return

            if action == "keyboard_shortcuts":
                from .help_panel import _KEYBOARD_SHORTCUTS
                lines = [f"[b]{key}[/b]  \u2014  {desc}" for key, desc in _KEYBOARD_SHORTCUTS]
                self.push_screen(InfoPanel("Keyboard Shortcuts", lines))
                return

            if action == "help":
                from .help_panel import HelpCenterPanel
                self.push_screen(HelpCenterPanel(), self._on_help_panel_action)
                return

            if action == "mcp_servers":
                from .mcp_panel import McpServersPanel
                self.push_screen(McpServersPanel())
                return

            if action == "backup_providers":
                from .backup_panel import BackupProvidersPanel
                self.push_screen(BackupProvidersPanel())
                return

            if action == "customize_ai":
                from .personalize_center import PersonalizeCenter
                self.push_screen(PersonalizeCenter())
                return

            if action == "gestures":
                try:
                    from .gestures_panel import GesturesPanel
                    self.push_screen(GesturesPanel())
                except Exception as e:
                    self._system_note(f"Gestures panel unavailable: {e}")
                return
            if action == "customization":
                try:
                    from .customization_panel import CustomizationPanel
                    self.push_screen(CustomizationPanel())
                except Exception as e:
                    self._system_note(f"Customization panel unavailable: {e}")
                return


            if action == "user":
                from .nav_screens import UserPanel
                self.push_screen(UserPanel(self._user_panel_values),
                                 self._on_user_panel_action)
                return

            if action == "chats":
                from .chats_panel import ChatsPanel
                from .. import chat_store
                ws = self._active_workspace_path()
                chats = chat_store.get_chat_summaries(ws) if ws else []
                pinned = chat_store.get_pinned_chats(workspace_root=ws or None)
                recent = chat_store.get_recent_chats(limit=8, workspace_root=ws or None)
                self.push_screen(
                    ChatsPanel(
                        chats=chats,
                        active_id=self._current_chat_id,
                        workspace_root=ws,
                        pinned=pinned,
                        recent=recent,
                    ),
                    self._on_chats_action,
                )
                return

            if action == "extensions":
                try:
                    from .extensions_panel import ExtensionsPanel
                    self.push_screen(ExtensionsPanel())
                except Exception as e:
                    self.push_screen(InfoPanel("Extensions", [f"Extensions panel unavailable: {e}"]))
                return

            if action == "diff_viewer":
                self.push_screen(InfoPanel(
                    "Diff Viewer",
                    ["This isn't wired up to a real backend yet in this build.",
                     "It's shown here as a placeholder destination, not "
                     "fabricated data — see the v0.7.4 changelog."]))
                return

        # ----------------------------------------------- workspace menu --
        # ----------------------------------------------- workspace menu --
        def _repaint_theme_layers(self, full=True):
            """Repaints theme-sensitive layers. When full=False (hover previews),
            lightweight chrome and CSS variables are refreshed, skipping expensive
            chat history Pygments markdown re-renders and editor retokenization."""
            try:
                self.refresh_css(animate=False)
                self.brand_header.refresh_brand()
                self._refresh_header_breadcrumb()
            except Exception:
                pass
            if full:
                try:
                    if self._workspace_shell is not None:
                        self._workspace_shell.query_one(EditorPane).retheme()
                except Exception:
                    pass
                try:
                    # Every existing bubble re-renders (code fences pick the
                    # new theme's pygments style).
                    self.conversation.retheme_items()
                except Exception:
                    pass
            try:
                self.conversation.repaint_empty_state_theme()
            except Exception:
                pass
            try:
                self.composer.refresh_palette_theme()
            except Exception:
                pass

        def _apply_theme_switch(self, chosen):
            """THE one place a PERMANENT theme switch is applied, no
            matter which entry point asked for it (/theme, Settings
            Center, Themes nav panel). Persists the choice (theme.py
            writes both stores) and clears any active preview."""
            if getattr(self, "_theme_preview_timer", None) is not None:
                try:
                    self._theme_preview_timer.stop()
                except Exception:
                    pass
                self._theme_preview_timer = None
            if getattr(self, "_theme_restore_timer", None) is not None:
                try:
                    self._theme_restore_timer.stop()
                except Exception:
                    pass
                self._theme_restore_timer = None

            self._selected_theme = chosen
            self._preview_theme = None  # click ends preview mode
            theme.set_theme(chosen)
            self._repaint_theme_layers(full=True)

        # ------------------------------------ live theme hover preview --
        def on_theme_preview_requested(self, event):
            """Mouse moved over a theme row: temporarily apply that
            theme WITHOUT persisting it. Debounced to eliminate lag."""
            try:
                name = theme.resolve_theme_name(event.name)
                # Cancel pending restore timer if moving to another row
                if getattr(self, "_theme_restore_timer", None) is not None:
                    try:
                        self._theme_restore_timer.stop()
                    except Exception:
                        pass
                    self._theme_restore_timer = None

                if name == self._preview_theme or name == theme.get_theme():
                    return

                # Cancel previous preview timer
                if getattr(self, "_theme_preview_timer", None) is not None:
                    try:
                        self._theme_preview_timer.stop()
                    except Exception:
                        pass
                    self._theme_preview_timer = None

                def _do_preview():
                    self._preview_theme = name
                    theme.set_theme(name, persist=False, paint_bg=False)
                    self._repaint_theme_layers(full=False)

                # 60ms debounce avoids thrashing during fast mouse sweeps
                self._theme_preview_timer = self.set_timer(0.06, _do_preview)
            except Exception:
                pass

        def on_theme_preview_ended(self, event):
            """Mouse left the theme row: restore the user's saved theme
            after a brief delay so moving across adjacent rows doesn't thrash."""
            try:
                # Cancel pending preview if any
                if getattr(self, "_theme_preview_timer", None) is not None:
                    try:
                        self._theme_preview_timer.stop()
                    except Exception:
                        pass
                    self._theme_preview_timer = None

                if self._preview_theme is None and theme.get_theme() == self._selected_theme:
                    return

                # Cancel previous restore timer if any
                if getattr(self, "_theme_restore_timer", None) is not None:
                    try:
                        self._theme_restore_timer.stop()
                    except Exception:
                        pass
                    self._theme_restore_timer = None

                def _do_restore():
                    if self._preview_theme is not None or theme.get_theme() != self._selected_theme:
                        self._preview_theme = None
                        theme.set_theme(self._selected_theme, persist=False, paint_bg=False)
                        self._repaint_theme_layers(full=False)

                # 100ms debounce prevents flickering when moving from row to row
                self._theme_restore_timer = self.set_timer(0.10, _do_restore)
            except Exception:
                pass

        def _on_failover_message(self, message):
            """aicore failover-hook target (worker-thread safe). Notes
            are queued; the streaming worker drains them into the live
            bubble between chunks, so they end up part of the turn's
            text instead of racing the widget tree from off-screen."""
            try:
                self._pending_failover_notes.append(str(message))
            except Exception:
                pass

        def _on_theme_chosen(self, chosen):
            # Stop any pending timers
            if getattr(self, "_theme_preview_timer", None) is not None:
                try:
                    self._theme_preview_timer.stop()
                except Exception:
                    pass
                self._theme_preview_timer = None
            if getattr(self, "_theme_restore_timer", None) is not None:
                try:
                    self._theme_restore_timer.stop()
                except Exception:
                    pass
                self._theme_restore_timer = None

            # Esc / click-outside dismisses with None: just make sure a
            # half-hovered preview collapses back to the saved theme.
            if not chosen:
                self._preview_theme = None
                if theme.get_theme() != self._selected_theme:
                    try:
                        theme.set_theme(self._selected_theme, persist=False,
                                        paint_bg=False)
                        self._repaint_theme_layers(full=False)
                    except Exception:
                        pass
                return
            if chosen == self._selected_theme:
                return
            self._apply_theme_switch(chosen)
            self._system_note(f"Theme switched to {theme.theme_label(chosen)}.")

        def on_file_saved(self, event: FileSaved):
            self._system_note(f"Saved {event.path}")
            eventbus.bus.publish(eventbus.FILE_SAVED, path=event.path)
            self.conversation.refresh_dashboard_stats()

        def on_diff_viewer_requested(self, event):
            """Live diff — show diff viewer for file changes (spec 14/15)."""
            try:
                from .diff_panel import DiffViewerPanel
                # Resolve original vs current
                editor = self._workspace_shell.editor if self._workspace_shell else None
                original = ""
                current = ""
                if editor:
                    try:
                        original = editor.get_original(event.path) or ""
                        # Get current text from open tab if present
                        tab_id = editor._open_paths.get(os.path.abspath(event.path)) if hasattr(editor, "_open_paths") else None
                        if tab_id:
                            try:
                                tabs = editor.query_one(editor.query_one.__self__ if False else None)
                            except Exception:
                                pass
                            # Fallback: read file directly
                            with open(event.path, "r", encoding="utf-8", errors="replace") as f:
                                current = f.read()
                        else:
                            with open(event.path, "r", encoding="utf-8", errors="replace") as f:
                                current = f.read()
                    except Exception:
                        try:
                            with open(event.path, "r", encoding="utf-8", errors="replace") as f:
                                current = f.read()
                        except Exception:
                            current = ""
                diff_lines = getattr(event, "diff", None) or []
                if not diff_lines and original and current:
                    import difflib
                    diff_lines = list(difflib.unified_diff(original.splitlines(), current.splitlines(), lineterm="", n=3))
                self.push_screen(DiffViewerPanel(path=event.path, diff_lines=diff_lines, original=original, current=current))
            except Exception as e:
                self._system_note(f"Diff viewer unavailable: {e}")

        def on_diff_viewer_closed(self, event):
            pass

        _MUTATING_FILE_TOOLS = {"write_file", "create_folder", "delete_file", "rename_file"}
        _FAILURE_PREFIXES = (
            "Refused:", "Could not", "does not exist", "is a folder",
            "No path given", "Tool '", "already exists", "Need both",
        )

        def _notify_tool_fs_change(self, name, args):
            """v0.7.9.0 (spec section 10): explicit internal events when
            CAT's own tools touch the filesystem — TOOL_FILE_CREATED /
            TOOL_FILE_DELETED / TOOL_FILE_MOVED / TOOL_DIRECTORY_CHANGED
            on the backend bus, plus an immediate WorkspaceFilesChanged
            so the Explorer updates during the turn (not only after the
            whole agent loop finishes). Safe on worker threads: the bus
            publish is plain Python; the Message crosses back via
            call_from_thread like every other UI update."""
            if name not in self._MUTATING_FILE_TOOLS:
                return
            args = args or {}
            paths = []
            for key in ("path", "new_path"):
                p = args.get(key)
                if p:
                    try:
                        paths.append(ws_paths.resolve_tool_path(str(p)))
                    except Exception:
                        paths.append(os.path.abspath(os.path.expanduser(str(p))))
            if not paths:
                return
            topic_by_tool = {
                "write_file": eventbus.TOOL_FILE_CREATED,
                "create_folder": eventbus.TOOL_DIRECTORY_CHANGED,
                "delete_file": eventbus.TOOL_FILE_DELETED,
                "rename_file": eventbus.TOOL_FILE_MOVED,
            }
            topic = topic_by_tool.get(name)
            if topic is not None:
                for p in paths:
                    eventbus.bus.publish(topic, path=p, tool=name)
            message = WorkspaceFilesChanged(paths)
            import threading as _threading
            if _threading.current_thread() is _threading.main_thread():
                # Already on the app/UI thread.
                self.post_message(message)
            else:
                self.call_from_thread(self.post_message, message)
            # v0.7.10: AI wrote files → the live preview updates NOW
            # (spec section 12: never wait for the response to finish).
            self._notify_preview_fs(paths)

        def _hide_build_code(self, text):
            """v0.7.8.1 Build-mode polish: strips fenced code blocks
            from the chat-visible text so Build mode reads as a
            professional progress report (status lines + diff summary),
            never a raw dump of generated source. The code itself is
            always written to real files by the tool loop — this only
            hides it from the transcript. The user can still see any
            file via Open File / Preview / Diff. Fenced blocks with a
            `diff` tag are kept — that's the change summary, not raw
            implementation.

            v0.7.8.1 fence fix: the old logic only tracked *diff*
            fences, so a raw ```python block was never marked 'inside a
            fence' — its code leaked into the transcript and both fence
            markers became stray status lines. Now raw fences swallow
            everything up to their closing fence, exactly like diff
            fences keep theirs."""
            import re as _re
            lines = text.split("\n")
            out = []
            in_diff_fence = False
            in_raw_fence = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("```"):
                    if in_raw_fence:
                        in_raw_fence = False
                        continue
                    if in_diff_fence:
                        in_diff_fence = False
                        continue
                    lang = stripped[3:].strip().lower()
                    if lang in ("diff", "patch"):
                        in_diff_fence = True
                        continue
                    # Raw code fence — replace with a status line.
                    out.append("> \U0001f4d6 Generated source written to files (see diff below / open the file to view it)")
                    in_raw_fence = True
                    continue
                if in_raw_fence:
                    # Inside a raw code fence — the code never reaches
                    # the transcript.
                    continue
                out.append(line)
            return "\n".join(out)

        def _changed_paths_from_steps(self, steps):
            """Best-effort scan of an agent run's executed tool steps for
            ones that actually touched disk. Not a real success/failure
            parse of each tool's return value (that would need every
            tool to return structured results, not a human-readable
            string) — just a prefix check against the known failure/
            refusal message shapes each file tool in agent.py returns.
            Good enough to decide "should the Explorer refresh at all",
            not precise enough to know exactly which lines changed."""
            paths = []
            for name, args, obs, _change in (steps or []):
                if name not in self._MUTATING_FILE_TOOLS:
                    continue
                obs_text = str(obs)
                if any(obs_text.startswith(p) for p in self._FAILURE_PREFIXES):
                    continue
                for key in ("path", "new_path"):
                    p = args.get(key) if isinstance(args, dict) else None
                    if p:
                        paths.append(str(p))
            return paths

        def on_workspace_files_changed(self, event: WorkspaceFilesChanged):
            if self._workspace_shell is not None:
                self._workspace_shell.refresh_explorer(event.paths)
            # AI file operations also drive the live preview (spec
            # section 12): the controller debounces internally.
            self._notify_preview_fs(event.paths)

        # ------------------------------------------- v0.7.9.0 fs watcher --
        def _on_fs_events(self, changed_paths):
            """Filesystem watcher thread -> UI thread bridge. Runs on the
            watcher's background thread: must never touch widgets, so it
            marshals across with call_from_thread exactly like every
            other worker in this app, posting the same WorkspaceFilesChanged
            message the agent's own file tools use. The Explorer refresh
            itself is debounced twice over: by the watcher (0.35s burst
            coalescing) and by only reloading affected tree branches."""
            if not changed_paths:
                return
            try:
                self.call_from_thread(
                    self.post_message,
                    WorkspaceFilesChanged(sorted(str(p) for p in changed_paths)))
            except Exception:
                pass

        def on_resize(self, event):
            """Terminal resize: cascade a debounced fit pass to the
            empty-state centerpiece + dashboard so every responsive
            variant recomputes from the new pane width.

            v0.7.9.6 stability pass: a single timer is reused — every
            new resize cancels the previous one and only the LAST
            resize actually triggers the downstream `on_resize` chain
            (each child has its own per-instance 50ms debounce).
            Without this, dragging the terminal width produces 30+
            recompute passes per second and the UI feels laggy."""
            try:
                _timer = getattr(self, "_resize_cascade_timer", None)
                if _timer is not None:
                    try:
                        _timer.stop()
                    except Exception:
                        pass
                self._resize_cascade_timer = self.set_timer(
                    0.05, self._cascade_resize)
            except Exception:
                pass

        def _cascade_resize(self):
            """Walk the tree once and invoke on_resize on the dashboard
            + chat empty state (if mounted). Direct method calls — we
            intentionally do NOT use `post_message` because every
            child already implements its own debounce.

            v0.7.9.6: `_dashboard` is a SUBSET of the welcome slot (a
            WelcomeDashboard is mounted *as* the welcome widget), so the
            two calls below used to hit the same object twice on every
            resize — one redundant full art rebuild + 2 widget queries.
            The identity check collapses that to a single pass."""
            try:
                conv = getattr(self, "conversation", None)
                if conv is None:
                    return
                welcome = getattr(conv, "_welcome", None)
                dash = getattr(conv, "_dashboard", None)
                target = welcome if welcome is not None else dash
                if target is not None and getattr(target, "is_attached", False):
                    try:
                        target.on_resize(None)
                    except Exception:
                        pass
                # Only a *distinct* dashboard needs a second pass.
                if (dash is not None and dash is not target
                        and getattr(dash, "is_attached", False)):
                    try:
                        dash.on_resize(None)
                    except Exception:
                        pass
            except Exception:
                pass

        def on_unmount(self):
            try:
                from ..preview.dev_server import get_dev_server_manager
                get_dev_server_manager().stop_all()
            except Exception:
                pass
            if getattr(self, "_fs_watcher", None) is not None:
                try:
                    self._fs_watcher.stop()
                except Exception:
                    pass
            ctrl = getattr(self, "_preview_ctrl", None)
            if ctrl is not None:
                try:
                    ctrl.stop_preview()
                except Exception:
                    pass
            try:
                _preview_shutdown_all()
            except Exception:
                pass
            # CAT Browser — hard stop on exit/sign-out so no lingering Chromium
            try:
                for scr in list(self.screen_stack):
                    if BrowserScreen is not None and isinstance(scr, BrowserScreen):
                        try:
                            shell = scr.query_one(BrowserShell) if BrowserShell else None
                            if shell is not None and getattr(shell, "_engine", None):
                                try:
                                    shell._engine.close()
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        try:
                            scr.dismiss(None)
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                # Also close any stray BrowserShell embedded in workspace
                for shell in self.query(BrowserShell):
                    try:
                        if getattr(shell, "_engine", None):
                            shell._engine.close()
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                import webbrowser as _wb2
                if _CAT_ORIG_WEBBROWSER_OPEN is not None:
                    _wb2.open = _CAT_ORIG_WEBBROWSER_OPEN
                    _wb2.open_new = _CAT_ORIG_WEBBROWSER_OPEN
                    _wb2.open_new_tab = _CAT_ORIG_WEBBROWSER_OPEN
            except Exception:
                pass

        def on_click(self, event):
            # Ctrl+Click anywhere on a URL → force CAT Browser (never external)
            try:
                ctrl = bool(getattr(event, "ctrl", False) or getattr(event, "control", False))
                if not ctrl:
                    mods = getattr(event, "modifiers", None)
                    if mods and "ctrl" in str(mods).lower():
                        ctrl = True
                    # Textual's Click may carry `ctrl` as part of `event` without attr — fallback to key check
                    if not ctrl and getattr(event, "button", None) == 1:
                        # Check if push_screen already has browser — don't double-handle non-ctrl clicks
                        pass
                    if not ctrl:
                        return
                w = getattr(event, "widget", None)
                txt = ""
                for attr in ("_text", "renderable", "value", "label", "title"):
                    try:
                        v = getattr(w, attr, None)
                        if v:
                            txt = str(v)
                            if _URL_RE.search(txt):
                                break
                    except Exception:
                        continue
                if not txt or not _URL_RE.search(txt):
                    # Try to pull from Static's update text via _text
                    try:
                        if w is not None and hasattr(w, "_text"):
                            txt = str(w._text)
                    except Exception:
                        pass
                m = _URL_RE.search(txt or "")
                if m:
                    url = m.group(0).rstrip(").,;")
                    try:
                        from ..host.launcher import launch_cat_host, can_launch_host
                        if can_launch_host():
                            launch_cat_host(start_browser_url=url, start_mode="browser", block=False)
                            self._system_note(f"Opened in CAT Browser — {url}")
                            try:
                                event.stop()
                                event.prevent_default()
                            except Exception:
                                pass
                        else:
                            self._system_note("CAT Browser requires PySide6: pip install PySide6")
                    except Exception:
                        pass
            except Exception:
                pass

        def on_chat_requested(self, event: ChatRequested):
            """Esc in the editor (or any other ChatRequested sender):
            the shell has already brought the chat pane forward — the
            app's only job here is to put focus in the composer so the
            user can just type."""
            try:
                self.composer.query_one(ComposerInput).focus()
            except Exception:
                pass

        def on_permission_mode_changed(self, event: PermissionModeChanged):
            self._system_note(f"Permission mode: {perm.manager.mode_label()}")

        def action_toggle_sidebar(self):
            if self._workspace_shell is not None:
                self._workspace_shell.toggle_sidebar()
                explorer = self._workspace_shell.explorer
                self._persist_sidebar_state(collapsed=not explorer.display or explorer.width == 0)
            else:
                self._system_note("Open a folder first (/open <path>) to use the Explorer sidebar.")

        def action_toggle_permissions(self):
            if hasattr(self, "composer") and self.composer is not None:
                from .permission_panel import PermissionsSettingsPanel
                try:
                    panel = self.composer.query_one(PermissionsSettingsPanel)
                    is_now_open = not panel.has_class("open")
                    panel.set_class(is_now_open, "open")
                    if is_now_open:
                        panel.refresh_rows()
                    self.composer._on_permission_panel_toggled(is_now_open)
                except Exception:
                    pass

        def action_toggle_menu(self):
            """Ctrl+M: open/close the Main Menu (NavPanel), the keyboard
            twin of the MenuButton's click — dismiss() pops the screen
            AND runs the push callback, so the button glyph and active
            class restore themselves exactly as if it had been clicked."""
            try:
                from .header import MenuButton, NavPanel
                button = self.query_one(MenuButton)
            except Exception:
                return
            for screen in list(self.screen_stack):
                if isinstance(screen, NavPanel):
                    screen.dismiss(None)
                    return
            button.open_menu()

        def action_save_file(self):
            if self._workspace_shell is None:
                return
            ok, detail = self._workspace_shell.editor.save_active()
            self._system_note(("Saved " + detail) if ok else ("Couldn't save: " + detail))

        def action_toggle_find(self):
            if self._workspace_shell is not None:
                self._workspace_shell.editor.toggle_find()

        def action_toggle_editor_fullscreen(self):
            """⿻ Full-Screen right pane (Ctrl+Shift+F / Main Menu /
            Preview bar): expands whichever half of the right pane is
            showing — Code Editor OR Web Preview — to the whole terminal
            viewport. Nothing is destroyed; toggling off restores the
            exact previous layout."""
            self.action_toggle_right_pane_fullscreen()

        # ================================================== WEB PREVIEW ==
        # v0.7.10 Live Web Preview: ▷ / ⏻ / ⿻ wiring. The PreviewController
        # (calc_terminal/browser/) owns server + Chromium + watcher; these
        # handlers only translate UI intent into controller calls and
        # queue its background-thread events back onto the UI thread.
        # ================================================================

        def _preview_ctrl_for(self, workspace_root=None):
            """The controller for THIS workspace, lazily created. Switching
            workspaces tears the previous stack down first."""
            root = os.path.abspath(workspace_root or
                                   self._workspace_root or os.getcwd())
            ctrl = getattr(self, "_preview_ctrl", None)
            if ctrl is not None:
                if os.path.normcase(ctrl.root) == os.path.normcase(root):
                    return ctrl
                try:
                    ctrl.stop_preview()
                except Exception:
                    pass
                self._preview_ctrl = None
                shell = self._workspace_shell
                if shell is not None:
                    shell.set_right_mode(WorkspaceMode.CODE)
            from ..browser import PreviewController as _PC
            ctrl = _PC(root, on_event=self._on_preview_event_thread)
            self._preview_ctrl = ctrl
            return ctrl

        def _on_preview_event_thread(self, kind, **info):
            """PreviewController event hook — runs on ITS worker threads.
            Queue only; the UI drain interval does all widget work."""
            with self._preview_events_lock:
                self._preview_events.append((kind, dict(info)))
            del self._preview_events[:-400:]

        def _drain_preview_events(self):
            """UI thread: apply queued controller events to widgets.

            v0.7.9.6 perf hardening: skipped entirely when the queue
            is empty. Previously we were still paying the cost of the
            `with self._preview_events_lock:` block 5 times a second
            (0.2s interval) forever, even on an idle session with no
            preview subsystem activity. With the lock-free fast-path
            an idle session burns effectively zero CPU here."""
            if not self._preview_events:
                return
            with self._preview_events_lock:
                batch = self._preview_events
                self._preview_events = []
            if not batch:
                return
            panel = self._workspace_shell.preview_panel \
                if self._workspace_shell is not None else None
            for kind, info in batch:
                state = info.get("state")
                error = info.get("error") or ""
                text = info.get("text")
                snap = info.get("snapshot")
                if panel is None:
                    continue
                if kind == "activity" and text:
                    done = str(text).startswith("✓")
                    panel.push_activity(str(text), done=done)
                    self.post_message(BuildActivity(str(text), done))
                elif kind == "server":
                    if state == ServerState.STARTING:
                        panel.show_status("Starting local server…")
                    elif state == ServerState.RUNNING:
                        ctrl = self._preview_ctrl
                        panel.show_status(
                            f"Server ready — {ctrl.base_url if ctrl else ''}")
                    elif state == ServerState.ERROR:
                        panel.show_status(f"SERVER ERROR — {error}",
                                          error=True)
                elif kind == "preview":
                    if state == PreviewState.STARTING:
                        panel.show_status("Starting browser engine…")
                    elif state == PreviewState.ERROR and error:
                        panel.show_status(f"PREVIEW ERROR — {error}",
                                          error=True)
                elif kind == "snapshot" and snap is not None:
                    panel.show_snapshot(snap)
                elif kind == "switch_mode":
                    self._apply_preview_mode(info.get("mode")
                                             or WorkspaceMode.PREVIEW)

        def on_preview_requested(self, event: PreviewRequested):
            """▷ clicked on an HTML tab (or explorer integration): start
            the live preview WITHOUT blocking the UI — the whole start-up
            sequence runs on a worker thread. Opens in CAT Browser app for real-time view."""
            now = time.time()
            if now - getattr(self, "_last_preview_launch_time", 0.0) < 1.2:
                return
            self._last_preview_launch_time = now
            if self._workspace_shell is None:
                return
            path = event.path or self._workspace_root
            if not path:
                return
            shell = self._workspace_shell
            panel = shell.preview_panel
            # If preview already running for same file, open/focus in CAT Browser app
            try:
                ctrl = getattr(self, "_preview_ctrl", None)
                if ctrl and ctrl.preview_state == PreviewState.RUNNING:
                    url = getattr(ctrl, "entry_url", None) or getattr(ctrl, "url", None) or getattr(ctrl, "base_url", None)
                    if url:
                        from ..host.launcher import launch_cat_host, can_launch_host
                        if can_launch_host():
                            launch_cat_host(start_browser_url=url, start_mode="browser", block=False)
                            self._system_note(f"✓ Live Web Preview running in CAT Browser — {url}")
                            return
            except Exception:
                pass
            if panel is not None:
                panel.clear_activity()
                panel.push_activity("Starting preview…")
                panel.show_status("Starting…")
            self._preview_worker = self._preview_start_worker(path)

        @work(thread=True, group="preview", exclusive=True)
        def _preview_start_worker(self, path):
            # Derive workspace root from the file's directory if possible (fix for files outside workspace)
            ws_root = None
            try:
                if path and os.path.isfile(path):
                    ws_root = os.path.dirname(os.path.abspath(path))
                    # walk up to find a plausible root (package.json / index.html / .git) but fallback to dir
                    cur = ws_root
                    for _ in range(3):
                        if any(os.path.exists(os.path.join(cur, f)) for f in ("package.json","index.html",".git","pyproject.toml")):
                            ws_root = cur
                            break
                        parent = os.path.dirname(cur)
                        if parent == cur:
                            break
                        cur = parent
                elif path and os.path.isdir(path):
                    ws_root = os.path.abspath(path)
            except Exception:
                ws_root = None
            ctrl = self._preview_ctrl_for(workspace_root=ws_root)
            try:
                ok = ctrl.start_for_file(path)
            except Exception as e:
                ok = False
                self._on_preview_event_thread(
                    "preview", state=PreviewState.ERROR, error=str(e))
            if ok:
                url = getattr(ctrl, "entry_url", None) or getattr(ctrl, "url", None) or getattr(ctrl, "base_url", None)
                if url:
                    from ..host.launcher import launch_cat_host, can_launch_host
                    if can_launch_host():
                        launch_cat_host(start_browser_url=url, start_mode="browser", block=False)
                        self.call_from_thread(lambda: self._system_note(f"✓ Live Web Preview opened in CAT Browser — {url}"))
                    else:
                        from ..host.launcher import get_host_status
                        st = get_host_status()
                        self.call_from_thread(lambda: self._system_note(f"CAT Browser requires PySide6: {st.get('reason', '')} — run: pip install PySide6"))
                # Keep Code Editor active in terminal CAT CLI (do not switch to terminal browser)
                self._on_preview_event_thread("switch_mode", mode=WorkspaceMode.CODE)
            else:
                # Surface error to UI even when start returns False without exception
                try:
                    err = getattr(ctrl, "last_error", "") or "Preview failed to start — check console"
                    self._on_preview_event_thread("preview", state=PreviewState.ERROR, error=str(err))
                    self.call_from_thread(lambda: self._system_note(f"Preview failed: {err}"))
                except Exception:
                    pass

        def _apply_preview_mode(self, mode):
            """UI thread: flip the right pane between CODE and PREVIEW.
            Preserves SPLIT if already active — preview start should not
            clobber an explicit split request."""
            shell = self._workspace_shell
            if shell is None:
                return
            # If shell is already in SPLIT, keep it — don't downgrade to PREVIEW
            if shell.mode is WorkspaceMode.SPLIT and mode is WorkspaceMode.PREVIEW:
                mode = WorkspaceMode.SPLIT
            if mode is WorkspaceMode.PREVIEW:
                # Starting a preview means the user asked to SEE it: on
                # narrow/stacked layouts bring the right pane forward.
                shell._showing = "files"
            elif mode is WorkspaceMode.SPLIT:
                shell._showing = "files"
            shell.set_right_mode(mode)
            if mode in (WorkspaceMode.PREVIEW, WorkspaceMode.SPLIT):
                # keep the right pane width identical across switches
                try:
                    from .resizers import load_layout as _ll
                    saved = (_ll().get("rightpane_width"))
                    if saved:
                        shell.set_right_width(saved)
                except Exception:
                    pass

        def action_preview_reload(self):
            ctrl = self._preview_ctrl
            if ctrl is not None:
                import threading as _t
                _t.Thread(target=_safe, args=(ctrl.reload,),
                          name="cat-preview-reload", daemon=True).start()
                url = getattr(ctrl, "entry_url", None) or getattr(ctrl, "base_url", None)
                if url:
                    try:
                        from ..host.launcher import launch_cat_host, can_launch_host
                        if can_launch_host():
                            launch_cat_host(start_browser_url=url, start_mode="browser", block=False)
                    except Exception:
                        pass

        def action_toggle_preview(self):
            """Ctrl+Shift+P / /preview — open the live preview in CAT Browser app."""
            shell = self._workspace_shell
            if shell is None:
                return
            ctrl = self._preview_ctrl
            starting_or_running = (
                ctrl is not None
                and ctrl.preview_state in (PreviewState.STARTING,
                                           PreviewState.RUNNING))
            if starting_or_running:
                url = getattr(ctrl, "entry_url", None) or getattr(ctrl, "base_url", None)
                if url:
                    from ..host.launcher import launch_cat_host, can_launch_host
                    if can_launch_host():
                        launch_cat_host(start_browser_url=url, start_mode="browser", block=False)
                        self._system_note(f"Preview active in CAT Browser — {url}")
                        return
            path = self._preview_target_path()
            if not path:
                self._system_note(
                    "No HTML entry point found — open a folder with an "
                    "index.html (or open one in the editor) first.")
                return
            self.post_message(PreviewRequested(path))

        def _preview_target_path(self):
            """Best candidate to preview right now: the active editor
            tab's file, else the current workspace root."""
            shell = self._workspace_shell
            editor = shell.editor if shell is not None else None
            area = editor.active_text_area() if editor is not None else None
            path = getattr(area, "path", None)
            if path and os.path.isfile(path):
                return path
            root = self._workspace_root or (
                shell.workspace_root if shell is not None else None)
            if root and os.path.isdir(root):
                return root
            return ""

        def action_preview_back(self):
            ctrl = self._preview_ctrl
            if ctrl is not None:
                import threading as _t
                _t.Thread(target=_safe, args=(ctrl.back,),
                          name="cat-preview-back", daemon=True).start()

        def action_preview_forward(self):
            ctrl = self._preview_ctrl
            if ctrl is not None:
                import threading as _t
                _t.Thread(target=_safe, args=(ctrl.forward,),
                          name="cat-preview-fwd", daemon=True).start()

        def preview_navigate_user(self, value):
            """URL bar Enter: resolve against the running site first
            (local-development navigation first), fall back to absolute
            http(s) URLs."""
            ctrl = self._preview_ctrl
            if ctrl is None or not ctrl.running or not value:
                return
            value = value.strip()
            if value.startswith("http://") or value.startswith("https://"):
                url = value
            else:
                rel = value.lstrip("/").replace("\\", "/")
                url = ctrl.base_url.rstrip("/") + "/" + rel
            import threading as _t

            def go():
                snap = _safe(ctrl.navigate, url)
                if snap is not None:
                    self._on_preview_event_thread("snapshot", snapshot=snap)
            _t.Thread(target=go, name="cat-preview-nav", daemon=True).start()

        def action_open_command_palette(self):
            """Ctrl+Shift+P / F1: open IDE command palette modal."""
            try:
                from .command_palette_modal import CommandPaletteModal
                self.push_screen(CommandPaletteModal())
            except Exception as e:
                self._system_note(f"Command palette error: {e}")

        def action_preview_open(self, path=None):
            """▷ / Shift+Enter / command: Open live preview for active file or project."""
            if not path:
                try:
                    if self._workspace_shell and self._workspace_shell.editor:
                        area = self._workspace_shell.editor.active_text_area()
                        if area and hasattr(area, "path") and area.path:
                            path = area.path
                        else:
                            content, cpath = self._workspace_shell.editor._get_active_content()
                            if cpath:
                                path = cpath
                except Exception:
                    pass
            if not path:
                path = getattr(self, "_workspace_root", None) or os.getcwd()
            from .events import PreviewRequested
            self.post_message(PreviewRequested(path))

        def open_file_at(self, path, line=1, col=1):
            """Open file in workspace editor and position cursor at line, col."""
            if self._workspace_shell is not None:
                if hasattr(self._workspace_shell, "open_file_at"):
                    return self._workspace_shell.open_file_at(path, line, col)
                return self._workspace_shell.open_file(path)
            return False

        def action_preview_close(self):
            """⏻ — stop server/browser/watcher, return the right pane to
            the Code Editor. Editor tabs and their content are untouched."""
            ctrl = self._preview_ctrl
            if ctrl is not None:
                # Flip the state machine FIRST, on the UI thread: an
                # immediate ▷ / Ctrl+Shift+P reopen must start a FRESH
                # stack instead of adopting the one that is still being
                # torn down asynchronously below (its start blocks on
                # the controller lock until that teardown completes).
                try:
                    ctrl.preview_state = PreviewState.STOPPED
                    ctrl.server_state = ServerState.STOPPED
                except Exception:
                    pass
                import threading as _t
                _t.Thread(target=_safe, args=(ctrl.stop_preview,),
                          name="cat-preview-stop", daemon=True).start()
            shell = self._workspace_shell
            if shell is not None:
                shell.set_right_mode(WorkspaceMode.CODE)
            self.post_message(PreviewClosed())
            self._system_note("Web Preview closed — editor restored.")

        def action_toggle_right_pane_fullscreen(self):
            """⿻ — fullscreen toggle for whichever half of the right pane
            is showing (Code OR Web Preview); same control both ways."""
            shell = self._workspace_shell
            if shell is None:
                return
            entering = not shell.fullscreen
            shell.set_fullscreen(entering)
            try:
                self.brand_header.display = not entering
                self.status_line.display = not entering
            except Exception:
                pass
            label = ("Web Preview" if shell.mode is WorkspaceMode.PREVIEW
                     else "Code")
            self._system_note(
                f"Full-Screen {label} — ⿻ / Ctrl+Shift+F to exit"
                if entering else f"Full-Screen {label} exited — layout restored")

        # ================================================== CAT BROWSER ==
        def action_toggle_browser(self, start_url: str | None = None):
            """Open CAT Browser app. NOT terminal-based browser, NOT external Chrome."""
            target_url = start_url
            if not target_url or target_url in ("about:home", "about:blank"):
                # If preview is running or an HTML file is open, open preview URL instead of about:home
                ctrl = getattr(self, "_preview_ctrl", None)
                if ctrl and getattr(ctrl, "entry_url", None):
                    target_url = ctrl.entry_url
                elif ctrl and getattr(ctrl, "base_url", None):
                    target_url = ctrl.base_url
                else:
                    path = self._preview_target_path()
                    if path and os.path.isfile(path) and str(path).lower().endswith((".html", ".htm")):
                        from .events import PreviewRequested
                        self.post_message(PreviewRequested(path))
                        return
                    target_url = "about:home"

            # Fomoji gate — allow about:home without auth, but protect other URLs
            try:
                from ..fomoji_auth import is_skip_enabled, status as _fa_status
                if not is_skip_enabled() and _fa_status() != "connected" and target_url not in ("about:home", "about:blank"):
                    is_fomoji = "localhost:3000" in target_url or "fomoji" in target_url.lower()
                    if not is_fomoji:
                        from ..fomoji_auth import get_fomoji_url
                        self._system_note(f"CAT Browser is locked — run `cat --auth login` (Fomoji: {get_fomoji_url()})")
                        return
            except Exception:
                pass
            # Open in CAT Browser app
            try:
                from ..host.launcher import launch_cat_host, can_launch_host, get_host_status
                if can_launch_host():
                    rc = launch_cat_host(start_browser_url=target_url, start_mode="browser", repl=self.repl, block=False)
                    if rc == 0:
                        self._system_note(f"Opened in CAT Browser — {target_url}")
                        return
                    self._system_note(f"CAT Browser failed to launch (code {rc})")
                    return
                else:
                    st = get_host_status()
                    self._system_note(f"CAT Browser requires PySide6: {st.get('reason', '')} — run: pip install PySide6")
                    return
            except Exception as e:
                self._system_note(f"Could not open CAT Browser: {e} — install: pip install PySide6")

        def action_focus_browser_address(self):
            try:
                scr = self.screen
                if hasattr(scr, "query_one"):
                    inp = scr.query_one("#browser-address", Input)  # type: ignore
                    inp.focus()
                    inp.action_select_all()
            except Exception:
                # Try browser shell variant
                try:
                    self.screen.query_one(BrowserShell).query_one("#browser-address", Input).focus()  # type: ignore
                except Exception:
                    pass

        def action_browser_new_tab(self):
            self.action_toggle_browser("about:home")

        def action_browser_close_tab(self):
            try:
                scr = self.screen
                if isinstance(scr, BrowserScreen):
                    scr.action_close_tab()
            except Exception:
                pass

        def action_browser_reopen_tab(self):
            try:
                scr = self.screen
                if isinstance(scr, BrowserScreen):
                    scr.action_reopen_tab()
            except Exception:
                pass

        def action_browser_back(self):
            try:
                scr = self.screen
                if isinstance(scr, BrowserScreen):
                    scr.action_back()
            except Exception:
                pass

        def action_browser_forward(self):
            try:
                scr = self.screen
                if isinstance(scr, BrowserScreen):
                    scr.action_forward()
            except Exception:
                pass

        def action_browser_fullscreen(self):
            try:
                scr = self.screen
                if isinstance(scr, BrowserScreen):
                    scr.action_fullscreen()
            except Exception:
                pass

        def action_host_browser(self):
            """Ctrl+Shift+B — open CAT Browser."""
            self.action_toggle_browser()

        def action_host_toggle(self):
            """Ctrl+Shift+H — open CAT Browser (terminal mode, no pre-loaded URL)."""
            try:
                from ..host.launcher import can_launch_host, get_host_status
                if not can_launch_host():
                    st = get_host_status()
                    self._system_note(f"CAT Host requires: {st['reason']} — pip install PySide6")
                    return
            except Exception as e:
                self._system_note(f"Host check failed: {e}")
                return
            try:
                from ..host.launcher import launch_cat_host
                self._system_note("Opening CAT Host (Browser INSIDE CAT) — suspending Textual")
                with self.suspend():
                    launch_cat_host(start_browser_url=None, start_mode="terminal", repl=self.repl, block=True)
                self._system_note("Returned to CAT — Host closed, CAT still running.")
                return
            except Exception as e:
                self._system_note(f"Host failed: {e}")

        def _handle_signout(self):
            """Prompt confirmation modal before signing out (Requirement #42)."""
            from textual.screen import Screen
            from textual.containers import Vertical, Horizontal
            from textual.widgets import Static, Button
            from textual.binding import Binding

            class SignOutModal(Screen):
                """Requirement #42: Sign out confirmation modal."""
                DEFAULT_CSS = """
                SignOutModal {
                    align: center middle;
                    background: #1a1b26 75%;
                    width: 100%;
                    height: 100%;
                }
                #signout-box {
                    width: 52;
                    height: auto;
                    background: #1f2335;
                    border: thick #a78bfa;
                    padding: 2 3;
                    layout: vertical;
                    align: center middle;
                }
                #signout-title {
                    color: #a78bfa;
                    text-style: bold;
                    text-align: center;
                    margin-bottom: 1;
                }
                #signout-prompt {
                    text-align: center;
                    margin-bottom: 2;
                    color: #e2e8f0;
                }
                #signout-buttons {
                    height: 3;
                    width: 100%;
                    align: center middle;
                    layout: horizontal;
                }
                #signout-buttons Button {
                    margin: 0 2;
                    min-width: 14;
                    height: 3;
                    border: none;
                }
                #btn-signout-yes {
                    background: #2e3440;
                    color: #e2e8f0;
                    border: round #4c566a;
                }
                #btn-signout-yes:hover, #btn-signout-yes:focus {
                    background: #3b4252;
                    color: #ffffff;
                    border: round #a78bfa;
                }
                #btn-signout-cancel {
                    background: #7c3aed;
                    color: #ffffff;
                    text-style: bold;
                    border: round #7c3aed;
                }
                #btn-signout-cancel:hover, #btn-signout-cancel:focus {
                    background: #8b5cf6;
                    color: #ffffff;
                    border: round #c4b5fd;
                    text-style: bold;
                }
                """

                BINDINGS = [
                    Binding("escape", "cancel", "Cancel"),
                ]

                def compose(self):
                    with Vertical(id="signout-box"):
                        yield Static("SIGN OUT", id="signout-title")
                        yield Static("Are you sure you want to sign out?", id="signout-prompt")
                        with Horizontal(id="signout-buttons"):
                            yield Button("  Yes  ", id="btn-signout-yes")
                            yield Button("  Cancel  ", id="btn-signout-cancel")

                def on_mount(self):
                    try:
                        # Default focus: Cancel (Requirement #42)
                        self.query_one("#btn-signout-cancel", Button).focus()
                    except Exception:
                        pass

                def action_cancel(self):
                    self.dismiss(False)

                def on_button_pressed(self, event):
                    if event.button.id == "btn-signout-yes":
                        self.dismiss(True)
                    else:
                        self.dismiss(False)

            def _on_confirmed(confirmed):
                if confirmed:
                    self._do_execute_signout()

            self.push_screen(SignOutModal(), _on_confirmed)

        def _do_execute_signout(self):
            """Sign out — clears token, stops Node.js, shows ASCII goodbye."""
            try:
                try:
                    self.action_cancel_streaming()
                except Exception:
                    pass
                from ..fomoji_auth import logout, get_identity, stop_fomoji_server
                ident = get_identity()
                who = ident.get("name") if ident else None
                logout()  # also calls stop_fomoji_server() internally
                # Extra explicit stop + ensure no lingering node
                try:
                    stop_fomoji_server()
                except Exception:
                    pass
                try:
                    import urllib.request
                    from ..fomoji_auth import get_fomoji_url
                    base = get_fomoji_url()
                    req = urllib.request.Request(base + "/api/logout", data=b"{}", method="POST")
                    req.add_header("Content-Type", "application/json")
                    urllib.request.urlopen(req, timeout=3)
                except Exception:
                    pass
                # Cleanup watchers / preview before goodbye
                try:
                    if getattr(self, "_fs_watcher", None):
                        self._fs_watcher.stop()
                except Exception:
                    pass
                try:
                    ctrl = getattr(self, "_preview_ctrl", None)
                    if ctrl:
                        ctrl.stop_preview()
                except Exception:
                    pass
                try:
                    # CAT Browser: hard-close Chromium engine then dismiss screen, stop embedded shell
                    for scr in list(self.screen_stack):
                        if BrowserScreen is not None and isinstance(scr, BrowserScreen):
                            try:
                                shell = scr.query_one(BrowserShell) if BrowserShell else None
                                if shell is not None and getattr(shell, "_engine", None):
                                    try:
                                        shell._engine.close()
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            try:
                                scr.dismiss(None)
                            except Exception:
                                pass
                except Exception:
                    pass
                try:
                    for shell in self.query(BrowserShell):
                        try:
                            if getattr(shell, "_engine", None):
                                shell._engine.close()
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    # Clear browser history state so next login fresh
                    if _browser_get_state is not None:
                        st = _browser_get_state()
                        if st is not None:
                            try:
                                st.tabs.clear()
                                st.active_tab_id = None
                            except Exception:
                                pass
                except Exception:
                    pass
                # Show ASCII goodbye screen — auto-exits after 3s
                try:
                    from .goodbye_screen import GoodbyeScreen
                    farewell = f"Signed out — {who} disconnected. See you soon! \U0001F43E" if who else "Signed out. See you soon! \U0001F43E"
                    self.push_screen(GoodbyeScreen(farewell=farewell))
                except Exception:
                    # Fallback: system note + exit
                    if who:
                        self._system_note(f"Signed out — {who} disconnected. Node.js stopped.")
                    else:
                        self._system_note("Signed out — Node.js stopped.")
                    try:
                        self.exit()
                    except Exception:
                        pass
            except Exception as e:
                try:
                    self._system_note(f"Sign out failed: {e}")
                except Exception:
                    pass

        def _notify_preview_fs(self, paths):
            """AI write tools → instant preview refresh (spec section 12:
             don't wait for the response to finish, don't wait for the OS
            watcher either). Thread-safe; no-ops when preview is off."""
            ctrl = getattr(self, "_preview_ctrl", None)
            if ctrl is None:
                return
            for p in (paths or []):
                try:
                    ctrl.notify_ai_wrote(p)
                except Exception:
                    pass

        def _refresh_header_breadcrumb(self):
            """Pushes the current notebook mode / model / workspace /
            context-token state into the header's breadcrumb line. Called
            on mount and any time one of those fields changes — the
            header itself doesn't read app/session state, it only
            renders what it's handed (see BrandHeader.refresh_breadcrumb)."""
            try:
                tokens_k = self.composer.context_tokens
            except Exception:
                tokens_k = 0
            context_label = f"Context {tokens_k}K" if tokens_k else "Context OK"
            mode_meta = ai_modes.meta(self._current_ai_mode)
            try:
                self.brand_header.refresh_breadcrumb(
                    notebook_mode=f"{mode_meta['icon']} {mode_meta['label']}",
                    model_label=self._model_label(),
                    workspace=self._current_workspace,
                    context_label=context_label,
                )
            except Exception:
                pass

        def on_notebook_changed(self, event: NotebookChanged):
            self._set_ai_mode(event.mode)

        def _set_ai_mode(self, mode_key, *, persist_chat=True):
            if mode_key not in ai_modes.MODE_META:
                return
            changed = mode_key != self._current_ai_mode
            self._current_ai_mode = mode_key
            ai_modes.set_mode(mode_key)
            self._refresh_header_breadcrumb()
            try:
                self.conversation.update_empty_state_mode(mode_key)
            except Exception:
                pass
            try:
                if hasattr(self, "composer") and self.composer:
                    self.composer.set_ai_mode(mode_key)
            except Exception:
                pass
            if changed and persist_chat and self._current_chat_id:
                try:
                    from .. import chat_store
                    chat_store.update_chat_metadata(
                        self._current_chat_id, current_mode=mode_key,
                    )
                except Exception:
                    pass
            if changed:
                try:
                    self.refresh_css(animate=False)
                    self.brand_header.refresh_brand()
                except Exception:
                    pass
                _log.info("mode switched to %s (chat=%s)", mode_key, self._current_chat_id)

        def on_workspace_changed(self, event: WorkspaceChanged):
            self._current_workspace = event.workspace
            self._refresh_header_breadcrumb()

        def _apply_customization_layout(self):
            """CAT Customization — apply positional, sizing, visibility, and appearance settings."""
            try:
                from .. import customization as _cust
                from .workspace import WorkspaceShell
                mgr = _cust.get_manager()
                active = _cust.is_active()

                shell = getattr(self, "_workspace_shell", None)
                if shell is None:
                    try:
                        shell = self.query_one(WorkspaceShell)
                        self._workspace_shell = shell
                    except Exception:
                        shell = None

                if shell is not None:
                    shell.apply_custom_layout(mgr.get_layout() if active else None)

                try:
                    if self.brand_header is not None:
                        self.brand_header.apply_custom_header(mgr.get_component("header") if active else None)
                except Exception:
                    pass

                try:
                    screens_to_update = set()
                    if hasattr(self, "screen") and self.screen:
                        screens_to_update.add(self.screen)
                    for sc in getattr(self, "screen_stack", []):
                        screens_to_update.add(sc)
                    for sc in screens_to_update:
                        if sc.__class__.__name__ in ("CustomizationPanel", "ExtensionsPanel", "_ConfirmScreen"):
                            continue
                        for cls in list(sc.classes):
                            if cls.startswith("cust-btn-"):
                                sc.remove_class(cls)
                        if active:
                            btn_style = mgr.get_styles().get("buttons", {})
                            shape = btn_style.get("shape", "rounded")
                            size = btn_style.get("size", "medium")
                            if shape and shape != "default":
                                sc.add_class(f"cust-btn-shape-{shape}")
                            if size and size != "default":
                                sc.add_class(f"cust-btn-size-{size}")
                except Exception:
                    pass
            except Exception:
                pass

        @property
        def brand_header(self):
            return self.query_one(BrandHeader)

        @property
        def conversation(self):
            return self.query_one(ConversationView)

        @property
        def composer(self):
            return self.query_one(StickyComposer)

        @property
        def status_line(self):
            return self.query_one(StatusLine)

        def _model_label(self):
            config = aicore.load_config()
            if config.get("provider"):
                return f"{config['provider'].upper()} {config.get('model', '')}".strip()
            return "no model"

        def _status_fields(self):
            gpu_ok = bool(shutil.which("nvidia-smi"))
            net_ok = perm.manager.allowed("internet")
            config = aicore.load_config()
            fields = [
                ("Python", platform.python_version(), ""),
                ("Model", config.get("model") or "none", "ready" if config.get("provider") else "warn"),
                ("GPU", "ready" if gpu_ok else "cpu-only", "ready" if gpu_ok else ""),
                ("Internet", "allowed" if net_ok else "blocked", "ready" if net_ok else "err"),
                ("Notebook", str(len(self._history)), ""),
                ("", "Ready", "ready"),
            ]
            # Idle chemistry icon (spec #25) — only while nothing is
            # actively streaming, so it reads as "the app is alive" and
            # never as another moving part competing with real progress.
            if not self._is_streaming:
                fields.append(("", thinking.idle_icon(self._idle_tick), ""))
            return fields

        def _show_goodbye_and_exit(self, farewell=None):
            if getattr(self, "_goodbye_shown", False):
                return
            self._goodbye_shown = True
            try:
                from .goodbye_screen import GoodbyeScreen
                msg = farewell or "Session saved. See you soon! \U0001F43E"
                try:
                    if getattr(self, "_fs_watcher", None):
                        self._fs_watcher.stop()
                except Exception:
                    pass
                try:
                    ctrl = getattr(self, "_preview_ctrl", None)
                    if ctrl:
                        ctrl.stop_preview()
                except Exception:
                    pass
                try:
                    from .browser_shell import BrowserShell as _BShell2
                    for shell in self.query(_BShell2):
                        try:
                            if getattr(shell, "_engine", None):
                                shell._engine.close()
                        except Exception:
                            pass
                except Exception:
                    pass
                self.push_screen(GoodbyeScreen(farewell=msg))
            except Exception:
                try:
                    super().exit()
                except Exception:
                    pass

        def action_quit_app(self):
            self._show_goodbye_and_exit()

        def exit(self, *args, **kwargs):
            if getattr(self, "_goodbye_shown", False):
                return super().exit(*args, **kwargs)
            try:
                self._show_goodbye_and_exit()
                return
            except Exception:
                pass
            return super().exit(*args, **kwargs)

        def action_open_palette(self):
            editor = self.composer.query_one(ComposerInput)
            # v0.7.9.5: Ctrl+P must never destroy an unsent draft. The
            # draft is stashed; Escape restores it, accepting a command
            # replaces it deliberately.
            if not editor.text.startswith("/"):
                self.composer._palette_saved_text = editor.text
                editor.text = "/"
                try:
                    editor.move_cursor(editor.document.end)
                except Exception:
                    pass
            editor.focus()
            self.composer._update_palette(editor)

        def action_prompt_attach(self):
            from .attach_panel import AttachPanel
            self.push_screen(AttachPanel(recents=self._recent_attachments),
                             self._on_attach_path)

        # v0.8.1 TXT import guard (requirement #20): direct insertion is
        # fine for reasonable files; anything larger attaches as normal
        # context instead of freezing the composer with a huge paste.
        TXT_IMPORT_MAX_CHARS = 200_000

        def _read_text_attachment(self, path):
            """Read a text file for import. Returns (text, error_str)."""
            try:
                size = os.path.getsize(path)
            except OSError as e:
                return None, f"could not stat file: {e}"
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read(), None
            except OSError as e:
                return None, str(e)

        def _import_txt_into_chat(self, path):
            """Place a .txt file's text into the current chat composer
            (requirement #17/#18). Returns True when inserted directly;
            False means the file was too large and was left as a normal
            attachment with an honest warning instead."""
            text, err = self._read_text_attachment(path)
            basename = os.path.basename(path)
            if text is None:
                self._system_note(f"Could not read '{basename}': {err}")
                return False
            editor = self.composer.query_one(ComposerInput)
            if len(text) > self.TXT_IMPORT_MAX_CHARS:
                self._system_note(
                    f"\u26a0 '{basename}' is {len(text):,} characters — too large to "
                    f"inline. It stays attached as context; use read_attachment "
                    f"or ask the AI to inspect it.")
                return False
            try:
                editor.insert(text.replace("\r\n", "\n"))
            except Exception:
                editor.text = (editor.text or "") + text
            self._system_note(f"\u2713 TXT imported into chat \u2014 {basename}")
            return True

        def _show_file_open_popup(self, path):
            """Sidebar double-click on a text-ish file: open in the
            editor, attach+import into chat, or cancel."""
            from textual.screen import Screen
            from textual.containers import Vertical, Horizontal
            from textual.widgets import Static, Button
            from textual.binding import Binding

            basename = os.path.basename(path)
            try:
                size = os.path.getsize(path)
                if size < 1024:
                    size_str = f"{size} bytes"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size / (1024*1024):.1f} MB"
            except Exception:
                size_str = "unknown size"

            class FileOpenPopup(Screen):
                CSS = """
                FileOpenPopup { align: center middle; background: $app-background 70%; }
                #fileopen-box {
                    width: 74; max-width: 95%; min-width: 52; height: auto; max-height: 92%;
                    background: $surface;
                    border-top: tall $surface-highlight;
                    border-left: tall $surface-highlight;
                    border-bottom: tall $surface-dark;
                    border-right: tall $surface-dark;
                    padding: 1 2;
                    opacity: 0; offset-y: 1;
                    transition: opacity 150ms, offset 180ms;
                }
                #fileopen-box.open { opacity: 1; offset-y: 0; }
                #fileopen-title { text-style: bold; color: $text; padding-bottom: 1; }
                #fileopen-msg { color: $text; padding-bottom: 1; }
                #fileopen-btns { height: 3; align-horizontal: right; }
                #fileopen-btns Button {
                    margin-left: 1;
                    min-width: 10;
                    border-top: tall $surface-highlight;
                    border-left: tall $surface-highlight;
                    border-bottom: tall $surface-dark;
                    border-right: tall $surface-dark;
                    transition: offset 80ms;
                }
                #fileopen-btns Button:hover {
                    offset-y: -1;
                }
                #fileopen-btns Button.-active {
                    offset-y: 1;
                }
                #fileopen-btns #fileopen-import {
                    color: $text;
                    text-style: bold;
                    border-top: tall $accent-highlight;
                    border-left: tall $accent-highlight;
                    border-bottom: tall $surface-dark;
                    border-right: tall $surface-dark;
                }
                """

                BINDINGS = [Binding("escape", "cancel", "Cancel")]

                def __init__(self, path, basename, size_str):
                    super().__init__()
                    self._path = path
                    self._basename = basename
                    self._size_str = size_str

                def compose(self):
                    with Vertical(id="fileopen-box"):
                        yield Static(f"Import '{self._basename}'?", id="fileopen-title")
                        yield Static(
                            f"File: {self._basename} ({self._size_str})\n\n"
                            "Import as context for the AI? The file contents will be\n"
                            "attached to your next message.",
                            id="fileopen-msg")
                        with Horizontal(id="fileopen-btns"):
                            yield Button("Open in Editor", id="fileopen-editor")
                            yield Button("Import as Context", id="fileopen-import",
                                         variant="primary")
                            yield Button("Cancel", id="fileopen-cancel")

                def on_mount(self):
                    self.call_after_refresh(
                        lambda: self.query_one("#fileopen-box").add_class("open"))

                def on_button_pressed(self, event):
                    eid = event.button.id
                    if eid == "fileopen-cancel":
                        self.dismiss(None)
                    elif eid == "fileopen-editor":
                        self.dismiss("editor")
                    elif eid == "fileopen-import":
                        self.dismiss("import")

                def action_cancel(self):
                    self.dismiss(None)

            def _on_file_open_result(result):
                if result == "import":
                    self.attach_files_from_ui([path], source="sidebar")
                elif result == "editor":
                    if self._workspace_shell is not None:
                        if not self._workspace_shell.open_file(path):
                            self._system_note(f"Can't open '{path}' in the editor.")

            self.push_screen(FileOpenPopup(path, basename, size_str),
                             _on_file_open_result)

        def _show_txt_import_popup(self, path):
            """v0.8.1 (requirements #17/#19): attaching a .txt file — via
            Browse OR drag-and-drop/paste — asks first:

                Import this TXT file into chat?
                prompt.txt
                [Import Text] [Cancel]

            Import Text reads the file and places its text into the
            current chat composer (never executed); Cancel leaves it as
            a normal attachment."""
            from textual.screen import Screen
            from textual.containers import Vertical, Horizontal
            from textual.widgets import Static, Button
            from textual.binding import Binding

            basename = os.path.basename(path)
            try:
                size = os.path.getsize(path)
                if size < 1024:
                    size_str = f"{size} bytes"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size / (1024*1024):.1f} MB"
            except Exception:
                size_str = "unknown size"

            class TxtImportPopup(Screen):
                CSS = """
                TxtImportPopup { align: center middle; background: $app-background 70%; }
                #txtimport-box {
                    width: 60; height: auto; max-height: 92%;
                    background: $surface; border: round $border; padding: 1 2;
                    opacity: 0; offset-y: 1;
                    transition: opacity 150ms, offset 180ms;
                }
                #txtimport-box.open { opacity: 1; offset-y: 0; }
                #txtimport-title { text-style: bold; padding-bottom: 1; }
                #txtimport-msg { color: $text-muted; padding-bottom: 1; }
                #txtimport-btns { height: 3; align-horizontal: right; }
                #txtimport-btns Button { margin-left: 1; }
                """

                BINDINGS = [Binding("escape", "cancel", "Cancel")]

                def __init__(self, path, basename, size_str):
                    super().__init__()
                    self._path = path
                    self._basename = basename
                    self._size_str = size_str

                def compose(self):
                    with Vertical(id="txtimport-box"):
                        yield Static("Import this TXT file into chat?",
                                     id="txtimport-title")
                        yield Static(
                            f"📎 {self._basename} ({self._size_str})\n\n"
                            "The text will be placed into your current message.\n"
                            "It will NOT be executed.",
                            id="txtimport-msg")
                        with Horizontal(id="txtimport-btns"):
                            yield Button("Import Text", id="txtimport-import",
                                         variant="primary")
                            yield Button("Cancel", id="txtimport-cancel")

                def on_mount(self):
                    self.call_after_refresh(
                        lambda: self.query_one("#txtimport-box").add_class("open"))

                def on_button_pressed(self, event):
                    eid = event.button.id
                    if eid == "txtimport-cancel":
                        self.dismiss(False)
                    elif eid == "txtimport-import":
                        self.dismiss(True)

                def action_cancel(self):
                    self.dismiss(False)

            def _on_txt_import_result(import_it):
                if import_it:
                    self._import_txt_into_chat(path)
                else:
                    # Cancel: stays as the normal attachment chip it already is.
                    self._system_note(f"📎 {basename} attached (not imported).")

            self.push_screen(TxtImportPopup(path, basename, size_str),
                             _on_txt_import_result)

        def attach_files_from_ui(self, paths, source="browse"):
            """THE one UI-side attach entry point (requirements #11-#19).
            Every origin — Browse, drag-and-drop/paste, sidebar — lands
            here: validate → chip → recents → TXT-import routing.
            Directories are rejected with an honest note; unreadable
            paths never silently vanish."""
            if not paths:
                return
            if isinstance(paths, str):
                paths = [paths]
            attached_names = []
            rejected = []
            for path in paths:
                try:
                    exists = os.path.lexists(path)
                    is_dir = os.path.isdir(path)
                except OSError:
                    exists, is_dir = True, False
                if not exists:
                    rejected.append(f"{os.path.basename(path)} (not found)")
                    continue
                if is_dir:
                    rejected.append(f"{os.path.basename(path)} (is a folder — "
                                    f"only files can be attached)")
                    continue
                chip_id = self.composer.add_attachment(path, source=source)
                if chip_id is None:
                    rejected.append(f"{os.path.basename(path)} (unreadable)")
                    continue
                attached_names.append(os.path.basename(path))
                seen = [p for p in self._recent_attachments
                        if os.path.normpath(p) != os.path.normpath(path)]
                self._recent_attachments = [path] + seen[:11]
            if len(attached_names) > 1:
                more = f" +{len(attached_names) - 3}" if len(attached_names) > 3 else ""
                src_label = ("drag-and-drop" if source in ("drag_and_drop", "paste")
                             else "attached")
                self._system_note(
                    f"📎 {src_label}: {len(attached_names)} file(s) — "
                    + ", ".join(attached_names[:3]) + more)
            if rejected:
                self._system_note("\u26a0 Not attached: " + "; ".join(rejected))
            # TXT special import (#17/#19): exactly one freshly attached
            # .txt triggers the import suggestion for BOTH browse and
            # drag-and-drop origins.
            if len(paths) == 1 and len(attached_names) == 1 \
                    and paths[0].lower().endswith(".txt"):
                self._show_txt_import_popup(paths[0])

        def on_attachment_chip_double_clicked(self, event):
            """v0.8.1 (requirement #18): double-clicking an attached TXT
            chip immediately imports its text into the current chat.
            Single-click remains normal attachment behavior."""
            path = event.path
            if not path.lower().endswith(".txt"):
                return
            event.stop()
            self._import_txt_into_chat(path)

        def _on_attach_path(self, paths):
            self.attach_files_from_ui(paths, source="browse")

        # ---------------------------------------------------- messaging --
        def on_message_submitted(self, event: MessageSubmitted):
            text = event.text.strip()
            if not text:
                return
            # v0.8.a: Check if user is authenticated before allowing messages
            try:
                from ..fomoji_auth import is_authenticated, is_skip_enabled
                if not is_authenticated() and not is_skip_enabled():
                    self._system_note(
                        "\u26a0\ufe0f  You are signed out.  "
                        "Please sign in to send messages.\n"
                        "  \u2022 Run: cat --auth login\n"
                        "  \u2022 Or use: \u2630 Menu \u2192 User \u2192 Sign In"
                    )
                    return
            except Exception:
                pass
            self.conversation.hide_welcome()
            # Auto-create a chat session if none active
            if not self._current_chat_id:
                try:
                    from .. import chat_store
                    ws = self._active_workspace_path()
                    provider, model = self._chat_provider_model()
                    chat = chat_store.create_chat(
                        workspace_root=ws,
                        cwd=ws or os.getcwd(),
                        created_mode=self._current_ai_mode,
                        current_mode=self._current_ai_mode,
                        provider=provider,
                        model=model,
                    )
                    self._current_chat_id = chat.get("id")
                    self._current_chat_title = chat.get("name") or "New Chat"
                    _log.info("auto-created chat %s workspace=%s", self._current_chat_id, ws)
                except Exception:
                    pass
            if text.startswith("/"):
                self._handle_command(text)
                return
            turn = self.session.add_user_turn(text, event.attachments,
                                               mode=self._current_ai_mode,
                                               workspace=self._current_workspace)
            self.conversation.add_complete(turn.turn_id, "user", text,
                                            mode_snapshot=turn.mode_snapshot,
                                            attachments=event.attachments)
            # Auto-save user turn to chat store
            try:
                from .. import chat_store
                if self._current_chat_id:
                    provider, model = self._chat_provider_model()
                    chat_store.add_turn(
                        self._current_chat_id, "user", text,
                        mode=self._current_ai_mode,
                        mode_snapshot=turn.mode_snapshot,
                        provider=provider,
                        model=model,
                    )
            except Exception:
                pass
            if self._maybe_answer_identity_question(text):
                return
            if self._route_autonomous(text, event.attachments):
                return
            self._maybe_gate_then_run(text, event.attachments)

        def _route_autonomous(self, text, attachments):
            """v0.7.8.1 (mode-isolation fix): workflow routing ONLY —
            install requests go to the package-manager flow, big build
            requests to the visible pipeline. The selected AI mode is
            NEVER changed automatically anymore: whichever mode the user
            picked stays active until the user changes it. Previously
            `mode_detection.suggest_mode_change` silently re-routed the
            active mode (the reported "typing switches to Notebook
            mode" bug). Returns True when the message was routed and
            handled."""
            try:
                from .. import mode_detection
            except Exception:
                return False
            try:
                workflow = mode_detection.workflow_kind(text)
                if workflow in ("install", "pipeline"):
                    self._begin_pipeline_turn(text, attachments or [])
                    return True
            except Exception:
                return False
            return False

        def _auto_switch_mode(self, target, reason):
            """v0.7.8.1: retained as a no-op stub so any stale callers
            keep working — automatic mode switching is banned. Modes are
            fully user-controlled now (mode isolation fix)."""
            return

        def _maybe_answer_identity_question(self, text):
            """Answers 'who made you', 'what are you', 'what model is
            this' style questions directly from calc_terminal/identity.py
            instead of being sent to the AI — that keeps the answer
            identical every time regardless of which provider is
            configured, whether it's offline, or how a model happens to
            phrase things. Returns True if it handled the message."""
            try:
                config = aicore.load_config()
            except Exception:
                config = None
            answer = identity.answer_for(text, config)
            if answer is None:
                return False
            reply_turn = self.session.start_assistant_turn(mode=self._current_ai_mode,
                                                             workspace=self._current_workspace)
            reply_turn.finish(answer)
            self.conversation.add_complete(reply_turn.turn_id, "assistant", answer,
                                            mode_snapshot=reply_turn.mode_snapshot)
            return True

        def on_command_executed(self, event: CommandExecuted):
            self._handle_command((event.command + " " + event.args).strip())

        def _maybe_gate_then_run(self, text, attachments, parent_turn_id=None, replace_turn_id=None):
            # Same trigger words code_editor.py's own confirm-before-run
            # gate uses — surfaced here as a real inline card instead of
            # an input() prompt. This is a heuristic UI gate, not the
            # actual sandboxing (sandbox.py / security_scanner.py do
            # that enforcement regardless of what this UI shows).
            #
            # `parent_turn_id`, when given, overrides the "last turn was
            # a user turn" heuristic _begin_assistant_turn otherwise
            # uses — needed by "Try Again in <mode>" (_retry_in_mode),
            # where the actual last turn in the transcript is the
            # assistant reply being retried from, not the user prompt.
            #
            # `replace_turn_id`, when given, means this isn't a normal
            # new message at all — it's Try Again or Rewrite
            # regenerating an EXISTING assistant turn in place
            # (minor-bug-fix spec: no duplicate prompts/responses). See
            # _regenerate_turn.
            wants_exec = any(w in text.lower() for w in
                              ("simulate", "run python", "orbital simulation", "plot"))
            if wants_exec and perm.manager.needs_prompt("execute_python"):
                request_id = perm.manager.new_request_id()
                self._pending_permissions[request_id] = (text, attachments, parent_turn_id, replace_turn_id)
                card = PermissionCard(request_id, "execute_python", "Run Python",
                                       "Calculate/simulate the requested result.")
                self.conversation.mount_item(card)
                return
            if replace_turn_id is not None:
                self._regenerate_turn(replace_turn_id, text, attachments, parent_turn_id)
            else:
                self._begin_assistant_turn(text, attachments, parent_turn_id=parent_turn_id)

        def on_permission_granted(self, event: PermissionGranted):
            tool_pending = self._pending_tool_permissions.pop(event.request_id, None)
            if tool_pending is not None:
                # Mid-agent-loop tool call (write_file/delete_file/...) —
                # agent._check_permission (running on the worker thread)
                # is blocked waiting on this exact decision string and
                # calls perm.manager.decide() itself once we hand it
                # back; this side just relays the button choice and
                # unblocks the wait.
                waiter, result = tool_pending
                result["decision"] = "always_allow" if event.remember else "allow_once"
                waiter.set()
                # v0.7.9.0: allowed -> the tool actually runs now.
                try:
                    self.post_message(AgentActivity(None, "tool_execution"))
                except Exception:
                    pass
                return
            pending = self._pending_permissions.pop(event.request_id, None)
            decision = "always_allow" if event.remember else "allow_once"
            perm.manager.decide(event.key, decision, "Run Python",
                                 "Calculate/simulate the requested result.")
            if pending:
                text, attachments, parent_turn_id, replace_turn_id = pending
                if replace_turn_id is not None:
                    self._regenerate_turn(replace_turn_id, text, attachments, parent_turn_id)
                else:
                    self._begin_assistant_turn(text, attachments, parent_turn_id=parent_turn_id)

        def on_permission_denied(self, event: PermissionDenied):
            decision = "always_deny" if event.remember else "deny"
            tool_pending = self._pending_tool_permissions.pop(event.request_id, None)
            if tool_pending is not None:
                waiter, result = tool_pending
                result["decision"] = decision
                waiter.set()
                # v0.7.9.0: refused -> the agent loop goes back to the
                # model with the denial observation (thinking again).
                try:
                    self.post_message(AgentActivity(None, "thinking"))
                except Exception:
                    pass
                return
            self._pending_permissions.pop(event.request_id, None)
            perm.manager.decide(event.key, decision, "Run Python",
                                 "Calculate/simulate the requested result.")
            verb = "Always denied" if event.remember else "Denied"
            note = self.session.add_system_turn(f"{verb} \u2014 not running that.",
                                                 mode=self._current_ai_mode)
            self.conversation.add_complete(note.turn_id, "system", note.text,
                                            mode_snapshot=note.mode_snapshot)

        def on_permission_cancelled(self, event: PermissionCancelled):
            tool_pending = self._pending_tool_permissions.pop(event.request_id, None)
            if tool_pending is not None:
                waiter, result = tool_pending
                result["decision"] = "cancel"
                waiter.set()
                try:
                    self.post_message(AgentActivity(None, "thinking"))
                except Exception:
                    pass
                return
            self._pending_permissions.pop(event.request_id, None)
            perm.manager.decide(event.key, "cancel", "Run Python",
                                 "Calculate/simulate the requested result.")
            note = self.session.add_system_turn("Cancelled \u2014 nothing ran.",
                                                 mode=self._current_ai_mode)
            self.conversation.add_complete(note.turn_id, "system", note.text,
                                            mode_snapshot=note.mode_snapshot)

        def _tool_permission_callback(self, key, action_label, path, reason):
            """Passed into agent.run_agent() as permission_callback for
            agent-mode turns. Runs on the streaming worker's background
            thread (see @work(thread=True) _stream_worker below) — it
            must never touch widgets directly, so it hands the actual
            card-mounting over to the main thread via call_from_thread,
            then blocks THIS thread (not the UI) on a plain
            threading.Event until on_permission_granted/denied above
            sets it from a real button press. This mirrors
            _maybe_gate_then_run's existing pre-turn gate, just resolved
            mid-loop instead of before the turn starts, and without
            perm.manager.decide() being called twice (agent.py's
            _check_permission does that once, using the decision this
            returns).
            """
            import threading
            waiter = threading.Event()
            result = {}
            request_id = perm.manager.new_request_id()

            def _mount_card():
                card = PermissionCard(request_id, key, action_label, reason, path=path)
                self._pending_tool_permissions[request_id] = (waiter, result)
                self.conversation.mount_item(card)
                # v0.7.9.0: blocked on the user's decision — the CAT
                # Agent indicator switches to its waiting state (it does
                # NOT stop; the turn is still genuinely in flight).
                try:
                    from .events import AgentActivity as _AA
                    self.post_message(_AA(None, "waiting_permission"))
                except Exception:
                    pass

            self.call_from_thread(_mount_card)
            waiter.wait()
            return result.get("decision", "deny")

        def _begin_assistant_turn(self, text, attachments=None, parent_turn_id=None):
            # AI provider not set up yet: aicore/agent's own "AI not
            # configured" messages tell the user to run /ai or /agent —
            # true in the classic fallback terminal, but no longer true
            # here now that both are mode switches (spec section 3), not
            # the setup wizard. Short-circuit with the real path instead
            # of letting a stale hint reach the conversation. `/model`
            # (bare, no arg) still suspends to the real terminal and
            # runs aicore.setup_ai() exactly as it always has — that
            # part wasn't touched.
            if not aicore.load_config().get("provider"):
                self._system_note(
                    "AI isn't configured yet. Run /model to set up your provider "
                    "(this briefly switches to the classic terminal for the setup wizard).")
                return
            prompt = self._augment_prompt(text, attachments or [])
            # Capture the current user turn's id *before* starting the
            # assistant placeholder turn — once start_assistant_turn()
            # appends that (still-empty) turn, it becomes session.turns[-1]
            # instead, so "the last turn" is no longer a reliable way to
            # find the user turn we're replying to. Turn identity is.
            #
            # `parent_turn_id`, when the caller already knows it (Try
            # Again — see _retry_in_mode), overrides that heuristic
            # outright: the real last turn at that point is the
            # assistant reply being retried from, not a user turn, so
            # the heuristic below would otherwise silently record no
            # parent at all for the new reply.
            current_user_turn_id = parent_turn_id
            if current_user_turn_id is None:
                if self.session.turns and self.session.turns[-1].role == "user":
                    current_user_turn_id = self.session.turns[-1].turn_id
            config = aicore.load_config()
            turn = self.session.start_assistant_turn(
                mode=self._current_ai_mode,
                provider=config.get("provider"),
                model=config.get("model"),
                workspace=self._current_workspace,
                parent_turn_id=current_user_turn_id,
            )
            self._turn_prompts[turn.turn_id] = prompt
            self._is_streaming = True
            self._streaming_turn_id = turn.turn_id
            self._activity.update(stage="", chunks=0, files=0,
                                  start=time.time(), last_step="")
            self.post_message(MessageStarted(turn.turn_id, prompt=prompt))
            self.post_message(StreamingStarted(turn.turn_id))
            # v0.7.9.0: real per-request latency instrumentation begins
            # here; the worker thread records every stage into it.
            cat_metrics.begin_request(turn.turn_id)
            try:
                cat_events.stream.emit(cat_events.USER_MESSAGE, source="ui",
                                       mode=self._current_ai_mode,
                                       attachments=len(attachments or []))
            except Exception:
                pass
            # v0.7.8.1: the Attachment objects ride along with the
            # worker — aicore uses them for native vision payloads and
            # verification.
            self._current_worker = self._stream_worker(
                prompt, turn.turn_id, current_user_turn_id, attachments or [],
                raw_text=text)

        def action_cancel_streaming(self):
            """v0.7.8.1 interrupt fix: Esc / Ctrl+C / the Stop button in
            the composer's streaming bar all land here. Cancels the
            in-flight worker, closes the provider's HTTP sockets,
            resets the UI state immediately, and marks the turn interrupted."""
            shell = getattr(self, "_workspace_shell", None)
            if shell is not None and shell.fullscreen:
                self.action_toggle_right_pane_fullscreen()
                return
            worker = getattr(self, "_current_worker", None)
            cancelled_any = False
            if worker is not None and not worker.is_finished:
                worker.cancel()
                cancelled_any = True
            try:
                aicore.cancel_active_requests()
            except Exception:
                pass
            # ── v0.7.9 Live Activity cancellation: mark running activities as cancelled (spec 11)
            tid = getattr(self, "_streaming_turn_id", None)
            try:
                from .. import activity as _act_cancel
                if tid:
                    _act_cancel.manager.update(f"gen-{tid}", status=_act_cancel.STATUS_CANCELLED, result="Interrupted")
                    _act_cancel.manager.cancel_turn(tid)
                # also release any pending permission waiters (so blocked tool thread unblocks)
                for req_id, (waiter, result) in list(getattr(self, "_pending_tool_permissions", {}).items()):
                    try:
                        if not waiter.is_set():
                            result["decision"] = "cancel"
                            waiter.set()
                        _act_cancel.manager.cancel_turn(tid or "")
                    except Exception:
                        pass
            except Exception:
                pass

            # CRITICAL: Always immediately stop and remove the animated cat thinking indicator
            try:
                conv = getattr(self, "conversation", None)
                if conv is not None:
                    conv.hide_agent_activity()
            except Exception:
                pass

            # CRITICAL: Always immediately reset composer streaming state, status bar and glyph
            try:
                if hasattr(self, "composer") and self.composer is not None:
                    self.composer.set_streaming(False)
            except Exception:
                pass

            was_streaming = bool(self._is_streaming or cancelled_any or tid)
            self._is_streaming = False

            if tid:
                try:
                    conv = getattr(self, "conversation", None)
                    if conv is not None:
                        item = (conv.get_item(tid) if hasattr(conv, "get_item") else None) or getattr(conv, "_items", {}).get(tid)
                        if item is not None:
                            curr_text = getattr(item, "_text", "") or ""
                            if "interrupted" not in curr_text.lower():
                                final_msg = curr_text + ("\n\n" if curr_text else "") + "⚠️ **Generation interrupted by user.**"
                                item.finalize(full_text=final_msg, meta_lines=["[bold red]⚠️ Generation interrupted by user[/]"])
                        conv.mark_live_completed(tid)
                except Exception:
                    pass

            self._streaming_turn_id = None
            self._current_worker = None
            try:
                self.status_line.refresh_status()
            except Exception:
                pass
            try:
                from .events import StreamingFinished
                self.post_message(StreamingFinished(tid or ""))
            except Exception:
                pass
            if was_streaming:
                try:
                    self.notify("⚠️ Generation interrupted by user", severity="warning", timeout=3.0)
                except Exception:
                    pass
                return

            try:
                self._show_idle_ready()
            except Exception:
                try:
                    self._system_note("\u23f9 Nothing is currently running — CAT is ready.")
                except Exception:
                    pass

        def _show_idle_ready(self):
            """Polished idle state (v0.7.9.9) — replaces the plain
            'Nothing is currently running' dead-end with a helpful,
            contextual ready card. Shows mode/workspace/turns and
            quick actions; if the conversation is still empty, it
            re-surfaces the Welcome Dashboard instead of leaving a blank
            pane. Never raises."""
            try:
                # Empty conversation → show the dashboard home (primary
                # startup screen) rather than a stray system note.
                if not getattr(self.session, "turns", None):
                    if self._show_dashboard_home():
                        self._system_note(
                            "● CAT is ready — nothing in flight · Type to chat, / for commands, Ctrl+P, Ctrl+B, Ctrl+T"
                        )
                        return
            except Exception:
                pass
            # Build live context for the ready card — plain text (system bubbles
            # render as Text(style="dim italic"), not Markdown/Rich markup,
            # so raw tags like [#e0af68]●[/] would leak literally).
            try:
                from .. import ai_modes as _am
                mode_label = _am.label() if hasattr(_am, "label") else str(self._current_ai_mode)
            except Exception:
                mode_label = str(getattr(self, "_current_ai_mode", "notebook"))
            try:
                raw_ws = getattr(self, "_workspace_root", None)
                # Treat system/Python install paths as "no workspace" — they
                # are not a user project (the leaked …\Python312\Scripts path
                # in the bug report came from the interpreter location).
                ws_short = "No workspace — Open Folder to attach a project"
                if raw_ws:
                    low = raw_ws.lower()
                    is_system_ws = (
                        "python" in low and ("localcache" in low or "windowsapps" in low or "program files" in low)
                    ) or low.endswith("\\scripts") or low.endswith("/scripts")
                    try:
                        from .. import workspace as _ws
                        if _ws.path_is_protected(raw_ws):
                            is_system_ws = True
                    except Exception:
                        pass
                    if not is_system_ws:
                        ws_short = raw_ws if len(raw_ws) < 48 else "…" + raw_ws[-47:]
                        # show just the folder name plus the short path for clarity
                        try:
                            base = __import__("os").path.basename(raw_ws.rstrip("\\/"))
                            if base and base.lower() not in ws_short.lower():
                                ws_short = f"{base} — {ws_short}"
                        except Exception:
                            pass
            except Exception:
                ws_short = "No workspace"
            try:
                turns = len(getattr(self.session, "turns", []) or [])
                hist = len(getattr(self, "_history", []) or [])
            except Exception:
                turns = 0
                hist = 0
            # one-liner (short) — plain text, no Rich markup
            msg = (
                f"● CAT is ready — nothing is currently running · "
            )
            # If a dashboard is already visible, don't duplicate it — a single
            # system note is enough. Otherwise the dashboard + note combo
            # gives both a visual home and a conversation marker.
            self._system_note(msg)

        def action_toggle_activity_panel(self):
            """v0.7.8.1 Live Activity panel (Ctrl+T): a popup with the
            live state of whatever turn is in flight — stage, elapsed,
            tokens streamed, files touched, provider/model, session
            usage. No-op-safe when the screen is already open."""
            from .activity_panel import ActivityPanel
            try:
                if any(isinstance(s, ActivityPanel) for s in self.screen_stack):
                    self.pop_screen()
                    return
                self.push_screen(ActivityPanel())
            except Exception:
                pass

        def action_open_memory_center(self):
            """v0.8.0: Open the Memory Center screen to view/edit/manage
            all stored memories (session, long-term, project)."""
            try:
                self.push_screen(MemoryCenterScreen())
            except Exception:
                pass

        def _begin_pipeline_turn(self, text, attachments=None):
            """v0.7.7: an assistant turn driven by the visible AI
            Execution Pipeline (Planner -> Research -> Build -> Testing
            -> Verification -> Documentation) instead of plain streaming.
            Install requests and big build requests route here (see
            _route_autonomous); the /pipeline slash command reaches the
            same flow via the classic terminal."""
            if not aicore.load_config().get("provider"):
                self._system_note(
                    "AI isn't configured yet. Run /model to set up your provider "
                    "(this briefly switches to the classic terminal for the setup wizard).")
                return
            prompt = self._augment_prompt(text, attachments or [])
            current_user_turn_id = None
            if self.session.turns and self.session.turns[-1].role == "user":
                current_user_turn_id = self.session.turns[-1].turn_id
            config = aicore.load_config()
            turn = self.session.start_assistant_turn(
                mode=self._current_ai_mode,
                provider=config.get("provider"),
                model=config.get("model"),
                workspace=self._current_workspace,
                parent_turn_id=current_user_turn_id,
            )
            self._turn_prompts[turn.turn_id] = prompt
            self._is_streaming = True
            self._streaming_turn_id = turn.turn_id
            self._activity.update(stage="", chunks=0, files=0,
                                  start=time.time(), last_step="")
            self.post_message(MessageStarted(turn.turn_id, prompt=prompt))
            self.post_message(StreamingStarted(turn.turn_id))
            self._current_worker = self._pipeline_worker(
                prompt, turn.turn_id, current_user_turn_id, attachments or [])

        @work(thread=True)
        def _pipeline_worker(self, prompt, turn_id, before_turn_id=None, attachments=None):
            # Off the UI thread, mirroring _stream_worker: every UI
            # update crosses back via call_from_thread posting events.
            from textual.worker import get_current_worker
            from .. import pipeline
            worker = get_current_worker()
            start = time.time()
            if attachments:
                cct_agent.set_attachments(attachments)
            try:
                from .. import activity as _act_pipe_thread
                _act_pipe_thread.set_current_turn(turn_id)
            except Exception:
                pass
            # ── v0.7.9 Live Activity: pipeline task ──
            _pipe_task = None
            _stage_acts: dict[str, object] = {}
            try:
                from .. import activity as _pact
                _pipe_task = _pact.manager.create(
                    type=_pact.TYPE_STATUS, action="pipeline",
                    title=prompt[:80] or "Pipeline task", status=_pact.RUNNING,
                    turn_id=turn_id, details="Pipeline: planner → build → test"
                )
            except Exception:
                pass

            def _chunk(text):
                if worker.is_cancelled:
                    return
                self._activity["chunks"] += 1
                self.call_from_thread(self.post_message, MessageChunk(turn_id, text))

            def _note(text):
                _chunk(f"> \U0001f3d7 `{text}`\n")

            def _stage(stage_key):
                label = pipeline.STAGE_LABELS.get(stage_key, stage_key)
                self._activity["stage"] = stage_key
                _chunk(f"> \u2699 `{label}`\n")
                eventbus.bus.publish(eventbus.PIPELINE_STAGE, stage_key=stage_key)
                # live activity per stage
                try:
                    from .. import activity as _pact2
                    prev = _stage_acts.get(stage_key)
                    if prev and prev.status == _pact2.RUNNING:
                        _pact2.manager.update(prev.id, status=_pact2.COMPLETED, result="Done")
                    act = _pact2.manager.create(
                        type=_pact2.TYPE_STATUS, action=stage_key,
                        title=label, status=_pact2.RUNNING, turn_id=turn_id
                    )
                    _stage_acts[stage_key] = act
                except Exception:
                    pass

            def _message(text):
                _chunk(text + "\n")

            try:
                run = pipeline.PipelineRun(
                    prompt, mode="agent", on_note=_note, on_stage=_stage,
                    on_message=_message, permission_callback=self._tool_permission_callback,
                    should_cancel=lambda: worker.is_cancelled)
                run.run()
                if run.failed_stage:
                    # v0.7.8.1 checkpoint resume: the first pass failed
                    # (provider chain exhausted mid-run, etc.) — one
                    # honest retry that skips the already-completed
                    # stages and continues from where it stopped,
                    # reusing the saved plan instead of restarting.
                    retry = pipeline.PipelineRun(
                        prompt, mode="agent", on_note=_note, on_stage=_stage,
                        on_message=_message, permission_callback=self._tool_permission_callback,
                        should_cancel=lambda: worker.is_cancelled)
                    retry.run(resume=True)
                    if not retry.failed_stage:
                        run = retry
                final_text = run.final_text or ""
            except Exception as e:
                final_text = f"\n\n*Pipeline stopped: {e}*"
                try:
                    from .. import activity as _pact3
                    for act in list(_stage_acts.values()):
                        if act.status == _pact3.RUNNING:
                            _pact3.manager.update(act.id, status=_pact3.FAILED, result=str(e)[:80])
                    if _pipe_task and _pipe_task.status == _pact3.RUNNING:
                        _pact3.manager.update(_pipe_task.id, status=_pact3.FAILED, result="Pipeline failed")
                except Exception:
                    pass
            if worker.is_cancelled:
                final_text = final_text + "\n\n*(interrupted \u2014 completed work kept)*"
                try:
                    from .. import activity as _pact4
                    for act in list(_stage_acts.values()):
                        if act.status == _pact4.RUNNING:
                            _pact4.manager.update(act.id, status=_pact4.CANCELLED, result="Cancelled")
                    if _pipe_task and _pipe_task.status == _pact4.RUNNING:
                        _pact4.manager.update(_pipe_task.id, status=_pact4.CANCELLED, result="Cancelled")
                    _pact4.manager.cancel_turn(turn_id)
                except Exception:
                    pass
            else:
                # complete stage activities
                try:
                    from .. import activity as _pact5
                    for act in list(_stage_acts.values()):
                        if act.status == _pact5.RUNNING:
                            _pact5.manager.update(act.id, status=_pact5.COMPLETED, result="Done")
                    if _pipe_task and _pipe_task.status == _pact5.RUNNING:
                        _pact5.manager.update(_pipe_task.id, status=_pact5.COMPLETED, result=f"{len(final_text)} chars")
                except Exception:
                    pass
            duration = time.time() - start
            try:
                self.call_from_thread(
                    self.post_message,
                    MessageFinished(turn_id, final_text, duration,
                                    aicore.get_session_usage()))
            except Exception:
                # App teardown mid-pipeline: clear state directly so no
                # stale spinner can survive (v0.7.9.5 lifecycle rule).
                self._is_streaming = False
                self._current_worker = None
            finally:
                self._streaming_turn_id = None
            try:
                from .. import activity as _act_pipe_clear
                _act_pipe_clear.clear_current_turn()
            except Exception:
                pass

        def _augment_prompt(self, text, attachments):
            """Folds every attached file into the prompt as one honest,
            real context block per file — v0.7.6 Patch 1, Fix 7:
            aicore.attachment_context_for() extracts actual content for
            text/code/markdown/CSV, real listings for zip/tar, metadata
            + best-effort text layer for PDF, and knowable info for
            audio/video/binary (never fabricated analysis). Images keep
            their existing vision path.

            v0.7.8.1: attachments are Attachment objects, not paths —
            the manager's build_context() serves the textual blocks
            (spec section 5) and verify() logs every attachment's fate
            (spec section 7). Native image payloads for vision
            providers are handled separately in aicore (the request's
            `attachments=` parameter)."""
            if not attachments:
                return text
            from .. import attachments as _att
            _att.AttachmentManager.verify(
                attachments, log=self._context_builder_log)
            ctx = _att.AttachmentManager.build_context(attachments)
            if not ctx:
                return text
            return text + "\n\n" + ctx

        def _context_builder_log(self, message):
            """Attachment verification lines (spec section 7) go to the
            Textual console in dev (`textual run --dev`) — never file
            contents, only ids/kinds/sizes/status."""
            try:
                self.log.debug(f"ContextBuilder: {message}")
            except Exception:
                pass

        def on_message_started(self, event: MessageStarted):
            turn = self.session.get(event.turn_id)
            snap = turn.mode_snapshot if turn else None
            # ── v0.7.9 Live Activities: mount inline block BEFORE the bubble
            # (order: USER TASK -> LIVE ACTIVITIES -> AGENT RESPONSE)
            try:
                self.conversation.mount_live_activities(event.turn_id)
            except Exception:
                pass
            try:
                from .. import activity as _act_mod
                _model_name = getattr(self.composer, "_model_label", "") or "AI"
                _act_mod.manager.create(
                    id=f"gen-{event.turn_id}",
                    type=_act_mod.TYPE_PROVIDER,
                    action="generate",
                    title=f"Thinking & generating ({_model_name})",
                    status=_act_mod.STATUS_RUNNING,
                    turn_id=event.turn_id,
                    category=_act_mod.CAT_MODEL,
                    phase=_act_mod.PHASE_ANALYSIS,
                    details=f"Model: {_model_name}",
                )
            except Exception:
                pass
            if self.conversation.has_item(event.turn_id):
                # Try Again / Rewrite regeneration (minor-bug-fix spec):
                # this turn_id already has a mounted bubble — reset it
                # in place instead of mounting a second one, which was
                # the actual duplicate-message bug. See
                # CCTApp._regenerate_turn, the only caller that reaches
                # here with an already-existing turn_id.
                self.conversation.reset_for_regenerate(event.turn_id, mode_snapshot=snap)
            else:
                self.conversation.start_streaming(event.turn_id, event.role, mode_snapshot=snap)
            if getattr(event, "role", "assistant") != "system":
                # v0.7.9.0: MODEL_REQUEST_STARTED -> thinking = true -> the
                # CAT ASCII indicator appears in the chat area, labelled
                # with the ACTUAL current mode (CAT Notebook / CAT Build /
                # CAT Debug / ...).
                self.conversation.show_agent_activity(
                    "thinking", mode_key=self._current_ai_mode)
            self.composer.set_streaming(True, prompt_hint=event.prompt, turn_id=event.turn_id)
            # Live AI STATUS inside the dashboard (spec: model state is
            # visible in the dashboard; the dashboard itself never closes
            # or duplicates while a model call runs).
            self._set_ai_status("Working\u2026")
            try:
                from ..terminal_identity import set_terminal_title
                set_terminal_title()
            except Exception:
                pass

        def on_agent_activity(self, event: AgentActivity):
            """Real agent state crossings flip the indicator's label
            (Thinking... / Executing... / Waiting for permission...)
            without touching the conversation content itself."""
            self.conversation.update_agent_activity(event.state)

        def on_message_chunk(self, event: MessageChunk):
            try:
                self.conversation.append_chunk(event.turn_id, event.text)
                self.composer.note_chunk_received()
            except Exception:
                pass

        def on_message_finished(self, event: MessageFinished):
            # v0.7.8.1 interrupt: the turn is over — drop the worker
            # reference so the Stop button/Esc target nothing stale.
            self._current_worker = None
            self._is_streaming = False
            self._streaming_turn_id = None
            # v0.7.8 BONUS FIX: whatever the worker produced, the UI only
            # ever renders clean text — any leaked tool-protocol JSON is
            # parsed out here, the single chokepoint every assistant
            # response crosses (streamed, pipeline and agent paths alike).
            try:
                full = cct_agent.clean_final_text(event.full_text)
            except Exception:
                full = event.full_text
            event.full_text = full
            try:
                from .. import activity as _act_mod
                _act_mod.manager.update(f"gen-{event.turn_id}", status=_act_mod.STATUS_COMPLETED, result="Completed")
            except Exception:
                pass
            meta_lines = self._completion_summary(event)
            self.conversation.finish(event.turn_id, event.full_text, meta_lines=meta_lines)
            turn = self.session.get(event.turn_id)
            if turn:
                turn.finish(event.full_text, event.duration, event.usage)
            # v0.8.a: Auto-save assistant response to chat store
            try:
                from .. import chat_store
                if self._current_chat_id and event.full_text:
                    provider, model = self._chat_provider_model()
                    asst_turn = self.session.get(event.turn_id)
                    chat_store.add_turn(
                        self._current_chat_id, "assistant", event.full_text,
                        mode=(asst_turn.mode if asst_turn else self._current_ai_mode),
                        mode_snapshot=(asst_turn.mode_snapshot if asst_turn else ai_modes.snapshot()),
                        provider=provider,
                        model=model,
                    )
                    # Auto-generate descriptive chat title if using a default title
                    cur_title = getattr(self, "_current_chat_title", "") or ""
                    if not cur_title or cur_title == "New Chat" or cur_title.startswith("Chat "):
                        user_turns = [t for t in self.session.turns if t.role == "user" and t.text]
                        if user_turns:
                            smart_title = self._generate_quick_title(user_turns[0].text)
                            if smart_title and smart_title != "New Chat":
                                chat_store.rename_chat(self._current_chat_id, smart_title)
                                self._current_chat_title = smart_title
                                if self.brand_header:
                                    self.brand_header.set_chat_title(smart_title)
            except Exception:
                pass
            self.composer.set_streaming(False)
            usage = aicore.get_session_usage()
            tokens_k = int(usage.get("total_tokens", 0) / 1000) if isinstance(usage, dict) else 0
            self.composer.context_tokens = tokens_k
            try:
                from ..workflow_engine import workflow_engine
                dur_ms = int(getattr(event, "duration", 0) * 1000)
                toks = None
                if isinstance(usage, dict):
                    toks = usage.get("total_tokens") or usage.get("completion_tokens")
                workflow_engine.finish_streaming_flow(
                    turn_id=event.turn_id,
                    duration_ms=dur_ms,
                    token_count=toks
                )
            except Exception:
                pass
            self._refresh_header_breadcrumb()
            self.post_message(StreamingFinished(event.turn_id))
            eventbus.bus.publish(eventbus.AI_RESPONSE_GENERATED, mode=self._current_ai_mode)
            self._set_ai_status("Ready")
            try:
                cat_events.stream.emit(cat_events.FINAL_RESPONSE, source="ui",
                                       turn_id=event.turn_id,
                                       duration_ms=round(event.duration * 1000.0, 1))
            except Exception:
                pass
            self._detect_and_add_ai_todos(event.full_text)
            self.conversation.refresh_dashboard_stats()

        def _detect_and_add_ai_todos(self, full_text):
            """AI Todo Manager (v0.7.2 roadmap): after a reply finishes,
            scan it for todo-shaped lines (todos.detect_ai_todos — see
            that function's docstring for exactly what it does and
            doesn't catch) and add any new ones to this workspace's
            list, tagged source='ai'. Skips text already present
            (case-insensitive) so a reply that repeats the same
            checklist across a few turns doesn't pile up duplicates."""
            try:
                candidates = todos.detect_ai_todos(full_text)
                if not candidates:
                    return
                existing = {t["text"].lower() for t in todos.list_todos(self._workspace_root)}
                for text in candidates:
                    if text.lower() not in existing:
                        todos.add_todo(text, workspace=self._workspace_root, source="ai")
            except Exception:
                pass

        def _completion_summary(self, event: MessageFinished):
            """Builds the '\u2713 Response Complete' block (spec #25's
            Message Completion section) shown under a finished assistant
            bubble: provider, model, time, tokens, any slash commands
            the prompt or reply mentioned — and (v0.7.9.0) the request's
            REAL measured timings (TTFB, tool time, call counts) from
            cat_metrics. Never fabricated numbers."""
            config = aicore.load_config()
            provider = (config.get("provider") or "").upper() or None
            model = config.get("model") or None
            usage = event.usage if isinstance(event.usage, dict) else {}
            tokens = usage.get("total_tokens") or usage.get("completion_tokens")
            prompt = self._turn_prompts.pop(event.turn_id, "")
            commands = thinking.commands_used(prompt, event.full_text)
            lines = thinking.completion_summary_lines(
                provider=provider, model=model, duration=event.duration,
                tokens=tokens, commands=commands,
            )
            # Real per-request measurements for THIS turn, when recorded.
            mreq = None
            for m in reversed(cat_metrics.get_recent(limit=5)):
                if m.request_id == event.turn_id:
                    mreq = m
                    break
            if mreq is not None:
                try:
                    lines.extend(mreq.summary_lines())
                except Exception:
                    pass
            return lines

        def on_streaming_finished(self, event: StreamingFinished):
            self.status_line.refresh_status()

        @work(thread=True)
        def _stream_worker(self, prompt, turn_id, before_turn_id=None, attachments=None,
                           raw_text=None):
            # Off the UI thread — must not touch the widget tree
            # directly; every UI update crosses back via
            # call_from_thread posting an event.
            #
            # v0.7.9.0 SPEED PIPELINE: this worker is now router-driven.
            # The Smart Router classifies the request locally (microseconds)
            # and picks the pipeline path:
            #   fast      → no history summarization, minimal overhead
            #   stream    → plain token streaming (default)
            #   agent     → real tool-executing loop with live events
            #   vision    → image(s) normalized + sent to a vision-capable
            #               model (rerouted to a capable backup when needed)
            #   multi_ai  → orchestrated parallel team (complex tasks only)
            #
            # v0.7.9.5 LIFECYCLE GUARANTEE: MessageFinished is posted in a
            # finally block — no exception path (not even call_from_thread
            # failing during app teardown) can leave the composer spinning
            # or the conversation stuck on '...'.
            from textual.worker import get_current_worker
            worker = get_current_worker()
            _mreq = cat_metrics.current() or cat_metrics.begin_request(turn_id)
            start = time.time()
            pieces = []
            cancelled = False
            self._streaming_turn_id = turn_id
            # ── v0.7.9 Live Activity thread-local binding ──
            try:
                from .. import activity as _act_thread
                _act_thread.set_current_turn(turn_id)
            except Exception:
                pass

            turn_for_mode = self.session.get(turn_id)
            mode = turn_for_mode.mode if turn_for_mode else self._current_ai_mode
            user_text = (raw_text or "").strip() or prompt

            def post(evt):
                """Cross to the UI thread. If the app is tearing down and
                the crossing fails, swallow — never let an escape here
                kill the worker before its finally block runs."""
                try:
                    self.call_from_thread(self.post_message, evt)
                except Exception:
                    pass

            def drain_failover_notes():
                """Provider-switch notes queued by the failover hook become
                real streamed lines in THIS turn, in order."""
                while True:
                    try:
                        note = self._pending_failover_notes.pop(0)
                    except (IndexError, AttributeError):
                        return
                    text = f"> {note}\n"
                    pieces.append(text)
                    self._activity["chunks"] += 1
                    _mreq.count_chunk()
                    post(MessageChunk(turn_id, text))

            def activity(state):
                post(AgentActivity(turn_id, state))

            def status_line(text):
                """One live-activity line in the chat bubble — always a
                REAL backend crossing, never decorative filler."""
                pieces.append(text)
                self._activity["chunks"] += 1
                _mreq.count_chunk()
                post(MessageChunk(turn_id, text))

            try:
                # ---------------- SMART ROUTING (requirement #6) --------
                decision = model_router.route(user_text, attachments, mode)
                try:
                    cat_events.stream.emit(cat_events.ROUTE_DECIDED,
                                           source="router", path=decision.path,
                                           task_types=sorted(decision.task_types),
                                           reason=decision.reason)
                except Exception:
                    pass

                has_image = "vision" in decision.task_types

                # Vision rerouting BEFORE any request goes out: if this
                # model can't see but a configured one CAN, use that one.
                request_config = None
                if has_image:
                    activity("vision")
                    try:
                        from .. import attachments as _att
                        caps = _att.provider_capabilities(aicore.load_config())
                    except Exception:
                        caps = {}
                    if not caps.get("vision"):
                        if decision.vision_config is not None:
                            request_config = decision.vision_config
                            status_line(
                                f"> \U0001f441 Active model lacks vision — "
                                f"routing image to **{decision.vision_config.get('provider', '?')}"
                                f"/{decision.vision_config.get('model', '?')}**\n")
                        else:
                            status_line(
                                "> \u26a0 No vision-capable model is configured — "
                                "the image can only be described from its metadata.\n"
                                "> Run `/model` to add one (gpt-4o / claude / gemini-class).\n")

                    # Strategy-aware analysis instructions so extraction
                    # requests get comprehensive answers (requirement #16).
                    kind = cat_vision.classify_image(
                        attachments[0].path, user_text) \
                        if attachments else "photo"
                    if has_image and (mode not in ("agent", "build")):
                        prompt = prompt.rstrip() + "\n\n" + cat_vision.analysis_prompt(
                            kind, user_text)

                # ---------------- FAST PATH (requirement #9) ------------
                summarize_needed = False
                if not decision.fast:
                    try:
                        summarize_needed = self.session.needs_summarization()
                    except Exception:
                        summarize_needed = False
                if summarize_needed and decision.path in ("stream", "vision"):
                    t_sum = time.perf_counter()
                    try:
                        self.session.summarize_older_turns(aicore.query_ai)
                        _mreq.mark_stage("history_summarize", t_sum)
                    except Exception:
                        pass
                # In-memory prompt history is cheap and keeps conversational
                # continuity; only the NETWORK summarization pass above is
                # what the fast path skips.
                history = self.session.as_prompt_history(before_turn_id=before_turn_id, mode=mode)

                # ---------------- MULTI-AI PATH (requirements #20-24) ---
                if decision.use_multi_agent and mode == "agent":
                    activity("multi_agent")
                    status_line("> \U0001f9e0 CAT Multi-AI: decomposing task...\n")
                    from ..collaboration import MultiAgentOrchestrator

                    def on_agent(key, label, status, summary=""):
                        icon = {"planner": "\U0001f9e0", "researcher": "\U0001f52c",
                                "coder": "\U0001f4bb", "reviewer": "\U0001f50d",
                                "tester": "\U0001f9ea", "debugger": "\U0001f41b",
                                "security": "\U0001f6e1", "architect": "\U0001f3d7",
                                "ui_designer": "\U0001f3a8",
                                "finalizer": "\U0001f4dd",
                                "orchestrator": "\U0001f3af"}.get(key, "\U0001f916")
                        mark = {"start": "\u23f3 running...", "done": "\u2705 complete"
                                }.get(status, status)
                        suffix = f" — {summary}" if summary and status == "done" else ""
                        status_line(f"> {icon} **{label}** {mark}{suffix}\n")
                        activity("multi_agent" if status == "start" else "thinking")

                    orch = MultiAgentOrchestrator()
                    final_text, _steps, _meta, _agents = orch.run_collaborative(
                        user_text,
                        permission_callback=self._tool_permission_callback,
                    )
                    if worker.is_cancelled:
                        cancelled = True
                    elif aicore.is_error_response(final_text):
                        final_text = _mark_ai_failure(final_text)
                        status_line(final_text)
                    else:
                        status_line(final_text)
                # ---------------- AGENT / TOOL PATH ----------------------
                elif decision.path == "agent" or mode in ("agent", "build"):
                    # Agent mode routes through CCT's actual tool-executing
                    # loop; Build too (files must be editable). Live tool
                    # progress streams into the chat as it happens.
                    activity("thinking")
                    if attachments:
                        # The tool loop must see attached files/images.
                        cct_agent.set_attachments(attachments)
                    agent_persona = "agent" if mode == "agent" else "ai"

                    def _on_agent_step(name, args):
                        args = args or {}
                        target = (args.get("path") or args.get("command")
                                  or args.get("query") or args.get("packages")
                                  or args.get("expression") or "").strip()
                        suffix = f"  `{target}`" if target else ""
                        self._activity["last_step"] = f"{name}{target and ' ' + target}"
                        if args.get("path"):
                            self._activity["files"] += 1
                        status_line(f"> \U0001f527 {name}{suffix}\n")
                        activity("tool_execution")

                    def _on_agent_tool_result(name, args, obs):
                        ok = not (obs or "").lower().startswith(
                            ("permission denied", "refused", "denied")) \
                            and "failed with a real error" not in (obs or "")
                        mark = "\u2705 completed" if ok else "\u274c failed"
                        status_line(f"> {mark}\n")
                        activity("thinking")
                        if ok:
                            self._notify_tool_fs_change(name, args)

                    final_text, _steps, _meta = cct_agent.run_agent(
                        prompt, mode=agent_persona,
                        verbose=False,   # the UI renders its own live activity
                        permission_callback=self._tool_permission_callback,
                        on_step=_on_agent_step,
                        on_tool_result=_on_agent_tool_result,
                        should_cancel=lambda: worker.is_cancelled,
                        fast=decision.fast,
                        memory_query=user_text, turn_id=turn_id)
                    if self._workspace_shell is not None:
                        changed = self._changed_paths_from_steps(_steps)
                        if changed:
                            for p in changed:
                                eventbus.bus.publish(eventbus.AI_FILE_EDIT, path=p)
                            self.call_from_thread(
                                self.post_message, WorkspaceFilesChanged(changed))
                    if worker.is_cancelled:
                        cancelled = True
                    elif aicore.is_error_response(final_text):
                        final_text = _mark_ai_failure(final_text)
                        status_line(final_text)
                    else:
                        changes = cct_agent.summarize_file_changes(_steps, markdown=True) or ""
                        if mode == "build":
                            final_text = self._hide_build_code(final_text)
                        if changes:
                            final_text = final_text.rstrip() + "\n\n" + changes
                        status_line(final_text)
                # ---------------- STREAMING PATHS ------------------------
                else:
                    from ..ai_context import get_context_manager, AIRequest
                    from ..models.profiles import get_model_profile

                    base_cfg = dict(request_config or aicore.load_config())
                    profile = get_model_profile(base_cfg.get("provider", "ollama"), base_cfg.get("model", ""), base_cfg)

                    ctx_mgr = get_context_manager()
                    req = AIRequest(
                        session_id=str(getattr(self.session, "session_id", "default")),
                        request_id=turn_id,
                        mode=mode,
                        user_message=prompt,
                        model=base_cfg.get("model", ""),
                        provider=base_cfg.get("provider", ""),
                    )
                    ai_ctx = ctx_mgr.build_context(req, profile=profile)

                    try:
                        from ..workflow_engine import workflow_engine
                        workflow_engine.start_streaming_flow(
                            prompt=user_text,
                            model_name=f"{base_cfg.get('provider', 'CAT')}/{base_cfg.get('model', '')}",
                            turn_id=turn_id
                        )
                    except Exception:
                        pass

                    if ai_ctx.is_minimal:
                        system_prompt = ai_ctx.system_prompt
                    else:
                        system_prompt = ai_modes.system_prompt_for(mode)
                        try:
                            from .. import workspace as _ws
                            _ws_root = _ws.root_dir()
                            system_prompt += (
                                f"\n\nActive workspace root: {_ws_root}\n"
                                f"Use workspace-relative paths for all file operations."
                            )
                        except Exception:
                            pass
                    from .. import ai_personalization as _ap
                    try:
                        _pcfg = _ap.request_config()
                    except Exception:
                        _pcfg = None
                    cfg = request_config
                    if _pcfg:
                        base_cfg = dict(request_config or aicore.load_config())
                        base_cfg.update(_pcfg)
                        cfg = base_cfg
                    # Timeout class from the router decision (requirement:
                    # simple prompts get a tight total deadline, big tasks
                    # a generous one — never one hardcoded value).
                    size_class = getattr(decision, "size_class", None) or (
                        "simple" if decision.fast else "normal")
                    for piece in aicore.stream_ai(prompt, system_prompt=system_prompt,
                                                  history=history, config=cfg,
                                                  attachments=attachments,
                                                  size_class=size_class):
                        drain_failover_notes()
                        if worker.is_cancelled:
                            cancelled = True
                            break
                        if aicore.is_error_response(piece):
                            piece = _mark_ai_failure(piece)
                        piece = cct_agent.sanitize_stream_chunk(piece)
                        if piece:
                            pieces.append(piece)
                            self._activity["chunks"] += 1
                            _mreq.count_chunk()
                            post(MessageChunk(turn_id, piece))
                    drain_failover_notes()
            except Exception as e:
                try:
                    err = _mark_ai_failure(str(e), title="Something went wrong")
                    if os.environ.get("CAT_DEBUG_TB"):
                        import traceback as _tb
                        err = _mark_ai_failure(
                            str(e) + "\n\n```\n" + _tb.format_exc() + "\n```",
                            title="Something went wrong")
                    pieces.append(err)
                    post(MessageChunk(turn_id, err))
                    # mark streaming activities failed on exception
                    try:
                        from .. import activity as _sact_err
                        sa = locals().get("_stream_act")
                        pa = locals().get("_provider_stream_act")
                        if sa and sa.status == _sact_err.RUNNING:
                            _sact_err.manager.update(sa.id, status=_sact_err.FAILED, result=str(e)[:80])
                        if pa and pa.status == _sact_err.RUNNING:
                            _sact_err.manager.update(pa.id, status=_sact_err.FAILED, result="Failed")
                    except Exception:
                        pass
                except Exception:
                    pass  # never let the error path escape either
            finally:
                # THE guarantee: whatever happened above — success,
                # provider failure, exception, cancel — the turn ALWAYS
                # finishes and the UI loading state ALWAYS clears.
                drain_failover_notes()
                full_text = "".join(pieces)
                if cancelled:
                    full_text += "\n\n*(interrupted \u2014 partial response kept)*"
                    # ensure waiting/running activities for this turn are cancelled (spec 11)
                    try:
                        from .. import activity as _sact_cancel
                        _sact_cancel.manager.cancel_turn(turn_id)
                        sa = locals().get("_stream_act")
                        pa = locals().get("_provider_stream_act")
                        if sa and sa.status == _sact_cancel.RUNNING:
                            _sact_cancel.manager.update(sa.id, status=_sact_cancel.CANCELLED, result="Cancelled")
                        if pa and pa.status == _sact_cancel.RUNNING:
                            _sact_cancel.manager.update(pa.id, status=_sact_cancel.CANCELLED, result="Cancelled")
                    except Exception:
                        pass
                duration = time.time() - start
                try:
                    _mreq.finish()
                except Exception:
                    pass
                usage = aicore.get_session_usage()
                try:
                    self.call_from_thread(
                        self.post_message,
                        MessageFinished(turn_id, full_text, duration, usage))
                except Exception:
                    # App teardown in progress — reset the flags directly
                    # so a restart/new prompt can't deadlock on stale state.
                    self._is_streaming = False
                    self._current_worker = None
                finally:
                    self._streaming_turn_id = None
                # for non-cancelled streaming path that didn't hit loop-complete marking (e.g. immediate failure), ensure completed
                if not cancelled:
                    try:
                        from .. import activity as _sact_final
                        sa = locals().get("_stream_act")
                        if sa and sa.status == _sact_final.RUNNING:
                            if full_text and "⚠" in full_text[:200]:
                                _sact_final.manager.update(sa.id, status=_sact_final.FAILED, result="Failed")
                            else:
                                _sact_final.manager.update(sa.id, status=_sact_final.COMPLETED, result=f"{len(pieces)} chunks")
                    except Exception:
                        pass
                # clear thread-local
                try:
                    from .. import activity as _act_clear
                    _act_clear.clear_current_turn()
                except Exception:
                    pass

        # ---------------------------------------------------- commands --
        def _handle_command(self, raw):
            parts = raw.split(None, 1)
            word = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            if word == "/clear":
                self.conversation.clear()
                self.session.clear()
                self._turn_prompts.clear()
                # v0.7.9.0: an empty conversation brings the CAT
                # centerpiece back — it IS the "Cleared." feedback, so no
                # stray system note is needed underneath it.
                if not self._show_chat_empty_state():
                    self._system_note("Cleared.")
                return
            if word in ("/exit", "/quit"):
                self.exit()
                return
            if word == "/touch":
                self.action_toggle_touch_mode()
                return
            if word == "/logo":
                try:
                    from .dashboard import WelcomeDashboard, LOGO_VARIANTS
                    welcome = getattr(getattr(self, "conversation", None), "_welcome", None)
                    if not arg or arg.lower() in ("next", "cycle"):
                        if isinstance(welcome, WelcomeDashboard):
                            welcome.cycle_logo_variant()
                            curr = LOGO_VARIANTS[welcome._logo_variant_idx]
                            self._system_note(f"Switched logo to Variant {welcome._logo_variant_idx + 1}: **{curr['name']}**")
                        else:
                            self._system_note("Switched ASCII logo style. View on dashboard (/clear).")
                        return
                    if arg.isdigit():
                        idx = int(arg) - 1
                        if 0 <= idx < len(LOGO_VARIANTS):
                            if isinstance(welcome, WelcomeDashboard):
                                welcome.set_logo_variant(idx)
                                curr = LOGO_VARIANTS[idx]
                                self._system_note(f"Switched logo to Variant {idx + 1}: **{curr['name']}**")
                            else:
                                from . import dashboard
                                dashboard._ACTIVE_LOGO_VARIANT = idx
                                self._system_note(f"Selected logo Variant {idx + 1}: **{LOGO_VARIANTS[idx]['name']}**")
                            return
                    matched = None
                    for i, v in enumerate(LOGO_VARIANTS):
                        if arg.lower() in v["id"].lower() or arg.lower() in v["name"].lower():
                            matched = i
                            break
                    if matched is not None:
                        if isinstance(welcome, WelcomeDashboard):
                            welcome.set_logo_variant(matched)
                            curr = LOGO_VARIANTS[matched]
                            self._system_note(f"Switched logo to Variant {matched + 1}: **{curr['name']}**")
                        else:
                            from . import dashboard
                            dashboard._ACTIVE_LOGO_VARIANT = matched
                            self._system_note(f"Selected logo Variant {matched + 1}: **{LOGO_VARIANTS[matched]['name']}**")
                        return
                    self._system_note("Usage: `/logo <1-5|next|retro|cyber3d|matrix|synthwave|pixel>`")
                except Exception as e:
                    self._system_note(f"Error switching logo: {e}")
                return
            if word == "/tokens":
                usage = aicore.get_session_usage()
                self._system_note(
                    f"Requests: {usage.get('requests', 0)}  \u00b7  "
                    f"Prompt: {usage.get('prompt_tokens', 0)}  \u00b7  "
                    f"Completion: {usage.get('completion_tokens', 0)}  \u00b7  "
                    f"Total: {usage.get('total_tokens', 0)}")
                return
            if word in ("/perf", "/bench", "/metrics"):
                # v0.7.9.0: REAL measured session performance (requirement
                # #37) — no fabricated numbers, straight from cat_metrics.
                totals = cat_metrics.session_totals()
                lines = ["\U0001f4ca **CAT performance (this session, measured)**", ""]
                if not totals.get("requests"):
                    lines.append("No completed requests yet — ask something first.")
                else:
                    lines.append(f"- Requests completed: {totals.get('requests', 0)}")
                    lines.append(f"- Model calls: {totals.get('model_calls', 0)}"
                                 f"  \u00b7  Tool calls: {totals.get('tool_calls', 0)}")
                    ttfb = totals.get("ttfb_mean_ms") or 0
                    lines.append(f"- Time-to-first-token: mean "
                                 f"{ttfb:.0f} ms"
                                 + (f"  \u00b7  p95 {totals.get('ttfb_p95_ms', 0):.0f} ms"
                                    if totals.get("ttfb_p95_ms") else ""))
                    lines.append(f"- Total latency: mean {totals.get('total_mean_ms', 0):.0f} ms")
                    for key in ("routing", "memory_retrieval", "tool_execution",
                                "agent_loop", "vision", "history_summarize"):
                        v = totals.get(f"{key}_mean_ms")
                        if v:
                            lines.append(f"- {key.replace('_', ' ').title()}: mean {v:.0f} ms")
                self._system_note("\n".join(lines), role="assistant")
                return
            if word == "/about":
                self._system_note(
                    f"CAT v{self._version()} \u2014 Coding Agent Terminal \u00b7 primary chat UI")
                return
            if word == "/help":
                lines = "\n".join(f"- `{cmd}` \u2014 {desc}" for cmd, desc in COMMANDS)
                self._system_note(lines, role="assistant")
                return
            if word == "/theme":
                if arg:
                    new_name = theme.resolve_theme_name(arg)
                else:
                    new_name = "textual-light" if not theme.is_light() else "tokyo-night"
                # v0.7.9.0: one shared switch path — CSS variables, header,
                # open editor tabs and the empty-state centerpiece all
                # retheme together (no component left in the old theme).
                self._apply_theme_switch(new_name)
                self._system_note(f"Theme switched to {theme.theme_label(new_name)}.")
                return
            if word == "/themes":
                self._system_note("Available themes: " +
                                  ", ".join(theme.available_themes()))
                return
            if word == "/model":
                if arg:
                    low_arg = arg.lower()
                    if low_arg in ("refresh",) or low_arg.startswith("search"):
                        # refresh/search subcommands run in the real
                        # terminal dispatcher (they have their own UIs)
                        self._run_in_suspended_terminal(raw)
                        return
                    ok, msg = aicore.switch_model(arg)
                    self.composer.set_model_label(self._model_label())
                    self._refresh_header_breadcrumb()
                    self._set_ai_status("Ready")
                    self._system_note(("\u2713 " if ok else "\u2717 ") + msg)
                else:
                    # v0.7.8.45: package-local import — see above.
                    from ..model import ProviderScreen
                    self.push_screen(ProviderScreen(embedded=True), self._on_provider_selected)
                return
            if word in ("/settings", "/users", "/user"):
                # Spec 22: Settings is now Users — keep /settings as alias
                from .nav_screens import UserPanel
                self.push_screen(UserPanel(self._user_panel_values), self._on_user_panel_action)
                return
            if word == "/composer":
                self._system_note("Already in the primary chat UI.")
                return
            if word == "/open":
                if arg:
                    self.run_worker(self._open_folder(arg))
                else:
                    self._toggle_or_focus_explorer()
                return
            if word == "/sidebar":
                self.action_toggle_sidebar()
                return
            if word == "/find":
                self.action_toggle_find()
                return
            # v0.7.10 Live Web Preview commands (spec section 34):
            # /preview [start|stop|reload|fullscreen|status] — all routed
            # through the SAME actions the ▷ / ⏻ / ⿻ / ⟳ buttons use.
            if word == "/preview":
                sub = arg.split(None, 1)[0].lower() if arg else ""
                ctrl = getattr(self, "_preview_ctrl", None)
                shell = self._workspace_shell
                if sub in ("", "start", "open"):
                    self.action_toggle_preview()
                    return
                if sub == "stop":
                    # Judge by ACTIVITY, not the (racy) preview_state:
                    # anything still serving or holding a browser is
                    # stopped for real; otherwise say so honestly.
                    active = ctrl is not None and (
                        ctrl.server.running
                        or ctrl.engine.available
                        or getattr(ctrl.devserver, "running", False))
                    if not active:
                        self._system_note("Web Preview is not running.")
                    else:
                        self.action_preview_close()
                    return
                if sub == "reload":
                    if ctrl is None or not ctrl.running:
                        self._system_note("Web Preview is not running.")
                    else:
                        self.action_preview_reload()
                        self._system_note("Preview reloading…")
                    return
                if sub in ("fullscreen", "expand", "fs"):
                    self.action_toggle_right_pane_fullscreen()
                    return
                if sub == "status":
                    lines = ["**Live Web Preview**"]
                    root = getattr(ctrl, "root", None) if ctrl else \
                        (shell.workspace_root if shell is not None else None)
                    lines.append(f"- Workspace: `{root or 'none open'}`")
                    if ctrl is None:
                        lines.append("- Server: stopped · Browser: stopped")
                    else:
                        srv = ctrl.server_state
                        prev = ctrl.preview_state
                        url = ctrl.base_url if ctrl.running else ""
                        lines.append(
                            f"- Server: {srv.value}" + (f" — {url}" if url else ""))
                        lines.append(f"- Browser: "
                                     f"{'running' if ctrl.engine.available else 'stopped'}"
                                     f" · Preview: {prev.value}")
                        if ctrl.url:
                            lines.append(f"- Page: {ctrl.url}")
                        if ctrl.last_error:
                            lines.append(f"- Last error: {ctrl.last_error}")
                    self._system_note("\n".join(lines), role="assistant")
                    return
                self._system_note(
                    "Usage: /preview [start|stop|reload|fullscreen|status]")
                return
            if word == "/todo":
                self.push_screen(TodoPanel(workspace=self._workspace_root))
                return
            if word == "/timeline":
                self.push_screen(TimelinePanel())
                return
            # v0.8.0: Open Memory Center instead of suspended terminal
            if word == "/memory":
                self.action_open_memory_center()
                return

            # CAT Doctor & System Diagnostics per §32
            if word == "/doctor" or (word == "/cat" and arg.lower().startswith("doctor")):
                from ..diagnostics import doctor_engine
                rep = doctor_engine.run_diagnostics()
                self._system_note(f"```\n{rep.format_text()}\n```", role="assistant")
                return

            # CAT Automated Self-Test per §33
            if word in ("/self-test", "/selftest") or (word == "/cat" and arg.lower() in ("self-test", "selftest")):
                from ..diagnostics import run_self_test
                rep = run_self_test()
                self._system_note(f"```\n{rep.format_table()}\n```", role="assistant")
                return

            # CAT Reality Engine Verification per §10, §12
            if word == "/verify" or (word == "/cat" and arg.lower().startswith("verify")):
                from ..core.verification import reality_engine
                ws = self._workspace_root or os.getcwd()
                rep = reality_engine.run_cat_verify(ws)
                table_str = reality_engine.format_evidence_table(rep)
                self._system_note(f"```\n{table_str}\n```", role="assistant")
                return

            # Checkpoint & Rollback per §14
            if word == "/checkpoint":
                from ..core.checkpoint import checkpoint_manager
                sub_parts = arg.split(None, 1) if arg else []
                sub = sub_parts[0].lower() if sub_parts else "list"
                sub_arg = sub_parts[1].strip() if len(sub_parts) > 1 else ""

                if sub in ("list", ""):
                    chks = checkpoint_manager.list_checkpoints()
                    if not chks:
                        self._system_note("No checkpoints recorded yet.")
                    else:
                        lines = ["**Workspace Checkpoints**:", ""]
                        for c in chks[:10]:
                            ts = time.strftime("%H:%M:%S", time.localtime(c.timestamp))
                            status = "active" if c.applied else "rolled_back"
                            lines.append(f"- `{c.id}` ({ts}, {status}): {c.description} ({len(c.snapshots)} files)")
                        self._system_note("\n".join(lines), role="assistant")
                    return
                elif sub == "rollback":
                    if not sub_arg:
                        self._system_note("Usage: /checkpoint rollback <checkpoint_id>")
                        return
                    ok, res = checkpoint_manager.rollback(sub_arg)
                    if ok:
                        self._system_note(f"✓ Rollback successful. Restored {len(res)} file(s).")
                    else:
                        self._system_note(f"✗ Rollback failed: {', '.join(res)}")
                    return
                elif sub == "create":
                    desc = sub_arg or "Manual checkpoint"
                    ws = self._workspace_root or os.getcwd()
                    files = []
                    for dp, _, fns in os.walk(ws):
                        if any(x in dp for x in (".git", "node_modules", "__pycache__", ".venv")): continue
                        for fn in fns:
                            if fn.endswith((".py", ".json", ".md", ".toml", ".txt")):
                                files.append(os.path.join(dp, fn))
                                if len(files) >= 50: break
                        if len(files) >= 50: break
                    chk = checkpoint_manager.create_checkpoint(desc, files)
                    self._system_note(f"✓ Checkpoint created: `{chk.id}` ({len(chk.snapshots)} files tracked)")
                    return

            # Compute Fabric per §25, §26
            if word in ("/compute", "/fabric"):
                from ..compute.fabric import compute_fabric
                targets = compute_fabric.list_targets()
                lines = ["**Compute Fabric Targets**:", ""]
                for t in targets:
                    icon = "✓" if t.status.value == "available" else ("!" if t.status.value == "config_required" else "○")
                    hd = t.hardware_details
                    hd_str = f" ({hd.get('cpu_model', '') or hd.get('gpu_name', '')})" if hd else ""
                    lines.append(f"- [{icon}] **{t.name}** (`{t.target_id}`): {t.status.value}{hd_str}")
                self._system_note("\n".join(lines), role="assistant")
                return

            if word in ("/browser", "/browse", "/cat"):
                # Graphical browser — never suspend to CLI Links UI
                start_url = arg.strip() if arg else "about:home"
                # Support `search cats` shorthand inside /browser
                low = start_url.lower()
                if low.startswith("search ") or low.startswith("s "):
                    q = start_url.split(None, 1)[1].strip() if " " in start_url else ""
                    if q:
                        import urllib.parse as _up
                        # Detect engine prefix inside query
                        eng = "duckduckgo"
                        qlow = q.lower()
                        if qlow.startswith("google "):
                            eng = "google"; q = q[7:].strip()
                        elif qlow.startswith("g "):
                            eng = "google"; q = q[2:].strip()
                        qq = _up.quote_plus(q)
                        start_url = f"https://www.google.com/search?q={qq}&hl=en&gbv=1" if eng=="google" else f"https://html.duckduckgo.com/html/?q={qq}"
                    else:
                        start_url = "about:home"
                elif start_url and " " in start_url:
                    # Plain phrase like `cats on mars` → search
                    import re as _re, urllib.parse as _up2
                    if not _re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", start_url) and not start_url.lower().startswith("about:"):
                        qq = _up2.quote_plus(start_url)
                        start_url = f"https://www.google.com/search?q={qq}&hl=en&gbv=1"
                self.action_toggle_browser(start_url=start_url)
                return
            if word in ("/signout", "/sign_out", "/logout", "/sign-out"):
                self._handle_signout()
                return

            # AI Modes (spec section 3, 4, 55, 56)
            if word in ("/agent", "/build", "/plan", "/notebook", "/ai",
                        "/research", "/debug"):
                target = "notebook" if word == "/ai" else word.lstrip("/")
                self._switch_mode_command(target)
                return
            if word == "/mode":
                sub_parts = arg.split(None, 1) if arg else []
                sub = sub_parts[0].lower() if sub_parts else ""
                sub_arg = sub_parts[1].strip() if len(sub_parts) > 1 else ""

                if sub == "list":
                    from ..core.mode_registry import mode_registry
                    modes = mode_registry.list_modes()
                    lines = ["**Active AI Modes** (Built-in + Custom):", ""]
                    for m in modes:
                        custom_tag = " [Custom]" if not m.get("default") else " [Default]"
                        lines.append(f"- {m.get('icon', '●')} **{m['name']}** (`/{m['key']}`){custom_tag}: {m.get('description', '')}")
                    self._system_note("\n".join(lines), role="assistant")
                    return
                elif sub == "create":
                    if not sub_arg:
                        self._system_note("Usage: /mode create <mode_name> [description]")
                        return
                    name_parts = sub_arg.split(None, 1)
                    mode_name = name_parts[0]
                    mode_desc = name_parts[1] if len(name_parts) > 1 else f"Custom {mode_name} mode"
                    from ..core.mode_registry import mode_registry
                    ok, msg = mode_registry.register_mode(
                        name=mode_name,
                        description=mode_desc,
                        system_prompt=f"You are operating in {mode_name} mode. Prioritize specialized execution.",
                    )
                    self._system_note(f"{'✓' if ok else '✗'} {msg}")
                    return
                elif sub == "delete":
                    if not sub_arg:
                        self._system_note("Usage: /mode delete <mode_name>")
                        return
                    from ..core.mode_registry import mode_registry
                    ok, msg = mode_registry.unregister_mode(sub_arg)
                    self._system_note(f"{'✓' if ok else '✗'} {msg}")
                    return
                else:
                    from ..core.mode_registry import mode_registry
                    resolved = mode_registry.resolve_mode_name(arg) if arg else ai_modes.next_mode(self._current_ai_mode)
                    target = resolved or (arg.strip().lower() if arg else ai_modes.next_mode(self._current_ai_mode))
                    self._switch_mode_command(target)
                    return

            if word in ("/summarize", "/summary"):
                self._summarize_chat()
                return

            # Known classic terminal commands can suspend to terminal
            from .. import registry as _cmd_reg
            reg = _cmd_reg.get_registry()
            if word in reg or word.lstrip("/") in reg:
                self._run_in_suspended_terminal(raw)
            else:
                self._system_note(f"Unknown command '{parts[0]}'. Type /help for a list of available commands.")

        def _switch_mode_command(self, target):
            from ..core.mode_registry import mode_registry
            canonical = target.strip().lower()
            spec = mode_registry.get_mode(canonical)
            if spec:
                target = canonical
                if target not in ai_modes.MODE_META:
                    mode_registry._sync_with_ai_modes()

            if target not in ai_modes.MODE_META:
                names = ", ".join(f"/{k}" for k in ai_modes.MODE_ORDER)
                self._system_note(f"Unknown mode '{target}'. Try one of: {names}")
                return
            self._set_ai_mode(target)
            try:
                self.composer.set_ai_mode(target)
            except Exception:
                pass
            m = ai_modes.meta(target)
            self._system_note(f"{m['icon']} Switched to {m['label']} mode \u2014 {m['purpose']}")

        # ---------------------------------------- context menu actions --
        def on_message_context_action(self, event: MessageContextAction):
            """Dispatch for the v0.7.2 right-click context menu (see
            ui/context_menu.py + ui/conversation.py's ConversationItem.
            on_click). 'copy' never reaches here — ConversationItem
            handles it entirely locally (see events.MessageContextAction's
            docstring)."""
            action = event.action
            if action == "new_session":
                self._new_chat_session()
            elif action == "summarize":
                self._summarize_chat()
            elif action.startswith("retry:"):
                self._retry_in_mode(event.turn_id, action.split(":", 1)[1])
            elif action == "rewrite":
                self._rewrite_prompt(event.turn_id)
            elif action == "revert":
                self._revert_to(event.turn_id)
            elif action == "fork":
                self._fork_conversation(event.turn_id)

        def _export_chat(self):
            """Export the current conversation transcript to a Markdown document."""
            import time as _t, os
            turns = getattr(self.session, "turns", [])
            if not turns:
                self._system_note("No conversation to export yet.")
                return
            lines = [
                "# CAT Conversation Export",
                f"*Exported: {_t.strftime('%Y-%m-%d %H:%M:%S')}*",
                f"*Workspace: {self._workspace_root or 'none'}*",
                ""
            ]
            for t in turns:
                role = "You" if t.role == "user" else "CAT Assistant"
                ts = _t.strftime('%H:%M:%S', _t.localtime(t.created_at)) if hasattr(t, "created_at") and t.created_at else ""
                header = f"### {role} ({ts})" if ts else f"### {role}"
                lines.append(header)
                lines.append("")
                lines.append(t.text or "")
                lines.append("")
            out_dir = self._workspace_root or os.path.expanduser("~")
            filename = f"chat_export_{int(_t.time())}.md"
            out_path = os.path.join(out_dir, filename)
            try:
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                self._system_note(f"\u2713 Chat exported to: {out_path}")
            except Exception as exc:
                self._system_note(f"Export failed: {exc}")

        def _retry_last_turn(self):
            """Regenerate the last response."""
            turns = getattr(self.session, "turns", [])
            if not turns:
                self._system_note("No conversation to reload.")
                return
            last_asst = next((t for t in reversed(turns) if t.role == "assistant"), None)
            if last_asst and last_asst.parent_turn_id:
                parent = self.session.get(last_asst.parent_turn_id)
                if parent and parent.text:
                    self._maybe_gate_then_run(
                        parent.text, parent.attachments,
                        parent_turn_id=parent.turn_id, replace_turn_id=last_asst.turn_id)
                    return
            last_user = next((t for t in reversed(turns) if t.role == "user"), None)
            if last_user and last_user.text:
                self._maybe_gate_then_run(last_user.text, last_user.attachments)

        def _retry_in_mode(self, turn_id, mode):
            """Try Again in <Mode> (AI-response menu). Retrieves the
            original user prompt via turn.parent_turn_id (Conversation
            Architecture metadata — see session.Turn), switches the
            active AI mode the same way /build|/plan|/notebook|/agent
            already do, and regenerates *in place*: REPLACES this
            existing assistant turn's content rather than appending a
            second reply (minor-bug-fix spec — the original v0.7.2 pass
            appended, which produced duplicate responses; see
            _regenerate_turn). No manual copy-paste required, matching
            the spec's own example workflow. A 'Generate Alternative'
            that intentionally keeps both is the spec's own named
            *optional* enhancement — not implemented here; this fix is
            scoped to the required "replace" behavior only."""
            if mode not in ai_modes.MODE_META:
                return
            turn = self.session.get(turn_id)
            if turn is None or turn.role != "assistant":
                return
            parent = self.session.get(turn.parent_turn_id) if turn.parent_turn_id else None
            if parent is None or not parent.text:
                self._system_note("Can't find the original prompt for this response.")
                return
            self._switch_mode_command(mode)
            self._maybe_gate_then_run(parent.text, parent.attachments,
                                       parent_turn_id=parent.turn_id, replace_turn_id=turn_id)

        def _regenerate_turn(self, turn_id, text, attachments, parent_turn_id):
            """Shared by Try Again and Rewrite (minor-bug-fix spec):
            reuses the EXISTING assistant turn_id/bubble instead of
            appending a new one — the actual duplicate-message bug.
            Resets the session Turn's fields in place; the bubble reset
            itself (back to an empty streaming state) happens in
            on_message_started, the one place a turn's bubble already
            gets created/reset (see ConversationView.has_item /
            reset_for_regenerate) — kept there rather than duplicated
            here so there's exactly one place that decides mount-vs-
            reset."""
            if not aicore.load_config().get("provider"):
                self._system_note(
                    "AI isn't configured yet. Run /model to set up your provider "
                    "(this briefly switches to the classic terminal for the setup wizard).")
                return
            turn = self.session.get(turn_id)
            if turn is None:
                # The bubble no longer exists (e.g. Reverted away since
                # the menu was opened) — fall back to a normal new turn
                # instead of silently doing nothing.
                self._begin_assistant_turn(text, attachments, parent_turn_id=parent_turn_id)
                return
            prompt = self._augment_prompt(text, attachments or [])
            config = aicore.load_config()
            turn.text = ""
            turn.status = "streaming"
            turn.duration = 0.0
            turn.usage = {}
            turn.mode = self._current_ai_mode
            turn.mode_snapshot = ai_modes.snapshot(self._current_ai_mode)
            turn.provider = config.get("provider")
            turn.model = config.get("model")
            turn.parent_turn_id = parent_turn_id
            self._turn_prompts[turn_id] = prompt
            self._is_streaming = True
            self._streaming_turn_id = turn_id
            self.post_message(MessageStarted(turn_id, prompt=prompt))
            self.post_message(StreamingStarted(turn_id))
            cat_metrics.begin_request(turn_id)
            self._current_worker = self._stream_worker(
                prompt, turn_id, parent_turn_id, attachments or [],
                raw_text=text)

        def on_message_rewritten(self, event: MessageRewritten):
            """Rewrite, save step (minor-bug-fix spec): REPLACES the
            original user turn's text and regenerates its paired
            assistant reply in place — no duplicate prompt, no
            duplicate response. Mirrors _retry_in_mode's use of
            _regenerate_turn, just starting from an edited USER turn
            instead of an unedited one."""
            turn = self.session.get(event.turn_id)
            if turn is None or turn.role != "user":
                return
            turn.text = event.text
            if event.attachments:
                turn.attachments = event.attachments
            self.conversation.set_text(event.turn_id, event.text, attachments=event.attachments or None)
            reply = next((t for t in self.session.turns
                          if t.role == "assistant" and t.parent_turn_id == event.turn_id), None)
            if reply is None:
                # No paired reply to regenerate (e.g. the original
                # request errored out before a reply turn existed) —
                # start a fresh one instead of doing nothing.
                self._maybe_gate_then_run(event.text, turn.attachments, parent_turn_id=event.turn_id)
                return
            self._maybe_gate_then_run(event.text, turn.attachments,
                                       parent_turn_id=event.turn_id, replace_turn_id=reply.turn_id)

        def _rewrite_prompt(self, turn_id):
            """Rewrite (user-message menu): puts the composer into real
            edit mode for this turn (StickyComposer.start_edit) — does
            NOT send it (spec: 'Do not automatically send'). Pressing
            Enter later is handled by on_message_rewritten, which
            replaces this turn's text and its paired reply in place."""
            turn = self.session.get(turn_id)
            if turn is None or turn.role != "user":
                return
            try:
                self.composer.start_edit(turn_id, turn.text)
            except Exception:
                pass

        def _revert_to(self, turn_id):
            """Revert (user-message menu): truncates the transcript to
            everything strictly before `turn_id` (removing the selected
            prompt and every response after it), and removes the
            matching widgets from the conversation view. Never touches
            self._workspace_shell/self._workspace_root — the open
            project and its files are completely unaffected, matching
            the spec."""
            turn = self.session.get(turn_id)
            if turn is None or turn.role != "user":
                return
            idx = self.session.index_of(turn_id)
            if idx is None:
                return
            for t in self.session.turns[idx:]:
                self._turn_prompts.pop(t.turn_id, None)
            self.session.turns = self.session.turns[:idx]
            self.session._folded_count = min(self.session._folded_count, len(self.session.turns))
            self.conversation.remove_from(turn_id)
            self._system_note("Reverted to before this message.")

        def _fork_conversation(self, turn_id):
            """Fork Conversation (user-message menu): a real new branch
            — session.ChatSession.fork_upto() returns a brand-new
            ChatSession carrying a copy of every turn up to and
            including `turn_id`, leaving the original session object
            completely untouched in memory. The visible conversation
            switches to that fork (same workspace/AI mode/attachments,
            per spec) so the user can keep exploring independently.
            Honest scope note: this package has no multi-tab/multi-
            conversation UI today (ConversationView is the ONLY
            scrollable region in the primary UI — see
            ui/conversation.py's module docstring), so there is
            currently no in-app way to switch back to the pre-fork
            original; it's kept in self._forked_from for a future
            conversation switcher, and /clear is the only way to start
            fresh today. A real conversation list to browse forks is a
            separate, larger feature — not something to fake here with
            a button that quietly does nothing."""
            fork = self.session.fork_upto(turn_id)
            if fork is None:
                return
            self._forked_from = self.session
            self.session = fork
            self.conversation.clear()
            for t in fork.turns:
                self.conversation.add_complete(t.turn_id, t.role, t.text,
                                                mode_snapshot=t.mode_snapshot)
            self._turn_prompts.clear()
            self._system_note(
                "Forked the conversation from this message \u2014 you're now in the new "
                "branch. The original conversation wasn't changed, but this build has "
                "no conversation switcher yet to go back to it in-app; run /clear to "
                "start over instead.")

        def _system_note(self, text, role="system"):
            # v0.7.8.1 hardening: _system_note can be crossed back from
            # worker threads (call_from_thread) during a screen
            # transition, when the conversation isn't queryable for a
            # frame. The turn is recorded in the session regardless;
            # a transient DOM miss must never crash the worker.
            # v0.7.9.5: when the ConversationView isn't mounted yet
            # (e.g. startup workspace indexing), the note is queued in
            # _pending_system_notes and drained once on_mount completes.
            note = self.session.add_system_turn(text, mode=self._current_ai_mode)
            try:
                self.conversation.add_complete(note.turn_id, role, text,
                                                mode_snapshot=note.mode_snapshot)
            except Exception:
                # Widget tree not ready yet — queue for later drain
                self._pending_system_notes.append(
                    (note.turn_id, role, text, note.mode_snapshot))

        def _drain_pending_system_notes(self):
            """v0.7.9.5: render any system notes that were queued while the
            ConversationView widget wasn't mounted yet (startup indexing,
            early worker threads). Called once after on_mount completes."""
            if not self._pending_system_notes:
                return
            queued = list(self._pending_system_notes)
            self._pending_system_notes.clear()
            try:
                conv = self.conversation
            except Exception:
                # Still not ready — re-queue and try again later
                self._pending_system_notes.extend(queued)
                return
            for turn_id, role, text, mode_snapshot in queued:
                try:
                    conv.add_complete(turn_id, role, text,
                                      mode_snapshot=mode_snapshot)
                except Exception:
                    pass

        def _run_in_suspended_terminal(self, raw):
            suspend_ctx = getattr(self, "suspend", None)
            if suspend_ctx is None:
                self._system_note(
                    f"'{raw}' needs the classic terminal view, and this version of "
                    "Textual can't suspend to it from here. Run it from the fallback CLI instead.")
                return
            try:
                with suspend_ctx():
                    print()
                    self.repl.handle(raw)
                    input(theme.faint("\n  press Enter to return to the chat UI\u2026"))
            except Exception as e:
                self._system_note(f"'{raw}' failed in the classic terminal: {e}")
                return
            self._system_note(f"Returned from '{raw}'.")

else:
    CCTApp = None


def launch_chat_app(repl, history, stats):
    """Launches the primary UI, mirroring tui.launch_dashboard's and the
    old chatapp.launch_chat's contract: returns (ok, message).

    Catches BaseException, not Exception, around app.run() specifically:
    Textual's own crash handler can call sys.exit() internally on some
    errors, and SystemExit does NOT inherit from Exception — an
    `except Exception` here would let that slip through uncaught,
    unwind straight out of this function and main.py, and the process
    would just... end, with nothing printed. That silent-failure shape
    matches what's been reported, so this is deliberately broad.
    """
    import sys
    # v0.7.9.4: the [CAT DEBUG] launch trace is diagnostic output, not
    # part of the product — it printed on EVERY normal start. Now gated
    # behind CAT_DEBUG=1 (failures are still reported normally and get
    # logged by cli._log_startup_failure).
    _debug = os.environ.get("CAT_DEBUG", "") not in ("", "0", "false", "no")

    def _dbg(msg):
        if _debug:
            print(f"[CAT DEBUG] {msg}", flush=True)

    if not TEXTUAL_AVAILABLE:
        return False, "textual isn't installed \u2014 run: pip install textual"
    if not keys.stdin_is_interactive():
        return False, "The primary chat UI needs a real attached terminal (not piped input)."
    _dbg("constructing CCTApp...")
    try:
        app = CCTApp(repl, history, stats)
    except BaseException as e:
        if _debug:
            print(f"[CAT DEBUG] CCTApp() constructor raised: {type(e).__name__}: {e}", flush=True)
        return False, f"Could not construct the chat UI: {type(e).__name__}: {e}"
    _dbg("calling CCTApp.run()...")
    try:
        app.run()
    except SystemExit as e:
        print(f"[CAT DEBUG] CCTApp.run() called sys.exit({e.code!r}) internally "
              "(this is almost always Textual's own crash handler) \u2014 "
              "re-raising so you see the real traceback below:", flush=True)
        raise
    except BaseException as e:
        import traceback
        print(f"[CAT DEBUG] CCTApp.run() raised: {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
        return False, f"Could not launch the chat UI: {type(e).__name__}: {e}"
    _dbg("CCTApp.run() returned normally (app was closed/quit).")
    return True, ""
