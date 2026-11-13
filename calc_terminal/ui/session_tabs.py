"""
CAT UI — session_tabs.py: Chat Session Tab Bar.

Displays open chat sessions at the top of the chat area, with support for:
  - Tab switching and active session indicator (e.g. 'Greeting ✕')
  - '+ New session' quick action button
  - Unread session dot indicator (●)
  - Close tab (✕), 'Close tabs to the right'
  - Keyboard shortcuts:
      * Ctrl+Alt+W: always closes current session tab
      * Ctrl+Shift+T: reopens last closed session tab
      * Ctrl+W: closes active tab wherever focus is
"""

import time
from typing import List, Dict, Optional

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Horizontal
    from textual.widgets import Static, Button
    from textual.message import Message
except Exception:
    TEXTUAL_AVAILABLE = False


class ChatSessionTabBar(Horizontal if TEXTUAL_AVAILABLE else object):
    """Horizontal tab bar for chat sessions placed directly above the conversation."""

    DEFAULT_CSS = """
    ChatSessionTabBar {
        height: 1;
        min-height: 1;
        max-height: 1;
        width: 100%;
        background: transparent;
        layout: horizontal;
        padding: 0;
        margin: 0;
        overflow: hidden;
    }
    .cct-session-tab {
        width: auto;
        min-width: 10;
        max-width: 28;
        height: 1;
        min-height: 1;
        max-height: 1;
        background: #1c1e2e;
        color: #9399b2;
        border: none;
        padding: 0 1;
        margin: 0 1 0 0;
        text-style: none;
    }
    .cct-session-tab:hover {
        background: #25283c;
        color: #cdd6f4;
    }
    .cct-session-tab-active {
        background: #252839;
        color: #cdd6f4;
        text-style: bold;
    }
    .cct-session-tab-active:hover {
        background: #2b2e42;
        color: #ffffff;
    }
    .cct-session-close-btn {
        width: 2;
        min-width: 2;
        max-width: 2;
        height: 1;
        min-height: 1;
        max-height: 1;
        background: transparent;
        color: #6c7086;
        border: none;
        padding: 0;
        margin: 0;
        content-align: center middle;
    }
    .cct-session-close-btn:hover {
        background: #f38ba8;
        color: #11111b;
        text-style: bold;
    }
    .cct-session-new-btn {
        width: auto;
        min-width: 3;
        max-width: 16;
        height: 1;
        min-height: 1;
        max-height: 1;
        background: transparent;
        color: #89b4fa;
        border: none;
        padding: 0 1;
        margin: 0;
        text-style: bold;
    }
    .cct-session-new-btn:hover {
        background: #89b4fa;
        color: #11111b;
    }
    """

    class SessionSwitched(Message):
        def __init__(self, session_id: str) -> None:
            super().__init__()
            self.session_id = session_id

    class SessionClosed(Message):
        def __init__(self, session_id: str) -> None:
            super().__init__()
            self.session_id = session_id

    class NewSessionRequested(Message):
        pass

    def __init__(self, *args, **kwargs):
        if not TEXTUAL_AVAILABLE:
            return
        super().__init__(*args, **kwargs)
        self.sessions: List[Dict] = [
            {"id": "greeting", "title": "Greeting", "unread": False}
        ]
        self.active_id: str = "greeting"
        self._closed_stack: List[Dict] = []

    def compose(self):
        if not TEXTUAL_AVAILABLE:
            return
        yield from self._render_tabs()

    def _render_tabs(self):
        for s in self.sessions:
            sid = s["id"]
            title = s["title"]
            is_active = (sid == self.active_id)
            dot = "● " if s.get("unread") else ""
            tab_label = f"{dot}{title}"
            cls = "cct-session-tab cct-session-tab-active" if is_active else "cct-session-tab"
            yield Button(tab_label, id=f"cct-stab-{sid}", classes=cls)
            if is_active:
                yield Button("✕", id=f"cct-sclose-{sid}", classes="cct-session-close-btn", tooltip="Close Session (Ctrl+Alt+W)")
        yield Button("+ New session", id="cct-snew-btn", classes="cct-session-new-btn", tooltip="New Session (+)")

    def set_active_title(self, title: str):
        for s in self.sessions:
            if s["id"] == self.active_id:
                s["title"] = title
                break
        self.refresh_tabs()

    def mark_unread(self, session_id: Optional[str] = None):
        target = session_id or self.active_id
        for s in self.sessions:
            if s["id"] == target:
                s["unread"] = True
                break
        self.refresh_tabs()

    def mark_read(self, session_id: Optional[str] = None):
        target = session_id or self.active_id
        for s in self.sessions:
            if s["id"] == target:
                s["unread"] = False
                break
        self.refresh_tabs()

    def refresh_tabs(self):
        try:
            self.remove_children()
            for widget in self._render_tabs():
                self.mount(widget)
        except Exception:
            pass

    def add_session(self, session_id: str, title: str = "New Session"):
        self.sessions.append({"id": session_id, "title": title, "unread": False})
        self.active_id = session_id
        self.refresh_tabs()

    def close_active_session(self):
        self.close_session(self.active_id)

    def close_session(self, session_id: str):
        target = next((s for s in self.sessions if s["id"] == session_id), None)
        if target:
            self._closed_stack.append(target)
            self.sessions = [s for s in self.sessions if s["id"] != session_id]
            if not self.sessions:
                # Always keep at least 1 session tab
                self.sessions.append({"id": "session-1", "title": "Greeting", "unread": False})
                self.active_id = "session-1"
            elif self.active_id == session_id:
                self.active_id = self.sessions[-1]["id"]
            self.refresh_tabs()
            self.post_message(self.SessionClosed(session_id))
            self.post_message(self.SessionSwitched(self.active_id))

    def reopen_last_closed(self):
        if self._closed_stack:
            last = self._closed_stack.pop()
            self.sessions.append(last)
            self.active_id = last["id"]
            self.refresh_tabs()
            self.post_message(self.SessionSwitched(self.active_id))

    def close_tabs_to_right(self, session_id: Optional[str] = None):
        target_id = session_id or self.active_id
        idx = next((i for i, s in enumerate(self.sessions) if s["id"] == target_id), None)
        if idx is not None and idx < len(self.sessions) - 1:
            closed = self.sessions[idx + 1:]
            self._closed_stack.extend(closed)
            self.sessions = self.sessions[:idx + 1]
            if self.active_id not in [s["id"] for s in self.sessions]:
                self.active_id = target_id
            self.refresh_tabs()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "cct-snew-btn":
            self.post_message(self.NewSessionRequested())
        elif btn_id.startswith("cct-sclose-"):
            sid = btn_id[len("cct-sclose-"):]
            self.close_session(sid)
        elif btn_id.startswith("cct-stab-"):
            sid = btn_id[len("cct-stab-"):]
            self.active_id = sid
            self.mark_read(sid)
            self.refresh_tabs()
            self.post_message(self.SessionSwitched(sid))

