"""
CAT CLI — Workspace-aware Chats browser (3D skeuomorphic control panel).

Hierarchical workspace grouping, scoped search, filters, pinned/recent
sections, and touch-friendly controls. Metadata-first — message bodies
load only when a chat is opened.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, ScrollableContainer, Vertical
    from textual.screen import Screen
    from textual.widgets import Button, Input, Static
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    Screen = object  # type: ignore


def _rel_time(ts: float) -> str:
    if not ts:
        return ""
    delta = max(0, time.time() - ts)
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)} min ago"
    if delta < 86400:
        return f"{int(delta // 3600)} hr ago"
    if delta < 172800:
        return "Yesterday"
    return datetime.fromtimestamp(ts).strftime("%b %d")


def _mode_badge(mode_key: str, mode_snapshot: Optional[Dict] = None) -> str:
    try:
        from .. import ai_modes
        from . import theme_css
        snap = mode_snapshot or ai_modes.snapshot(mode_key)
        hex_c = snap.get("accent_hex") or theme_css.current_hex("accent")
        icon = snap.get("icon", "●")
        label = (snap.get("label") or mode_key or "Mode").strip()
        return f"[{hex_c}]{icon} {label.upper()}[/{hex_c}]"
    except Exception:
        return f"● {(mode_key or 'mode').upper()}"


if TEXTUAL_AVAILABLE:

    class ChatsPanel(Screen):
        """Premium workspace-organized chat browser with solid 3D skeuomorphic controls."""

        CSS = """
        ChatsPanel {
            align: center middle;
            background: $app-background 65%;
        }
        #chats-shell {
            width: 100%;
            height: 100%;
            max-width: 100;
            max-height: 100%;
            padding: 0 1;
        }
        #chats-box {
            width: 100%;
            height: 100%;
            max-width: 94;
            max-height: 100%;
            min-width: 38;
            background: $surface;
            border-top: tall $surface-highlight;
            border-bottom: tall $surface-dark;
            border-left: tall $surface-highlight;
            border-right: tall $surface-dark;
            padding: 0;
            layout: vertical;
        }
        #chats-titlebar {
            height: 3;
            min-height: 3;
            max-height: 3;
            padding: 0 1 0 2;
            border-bottom: solid $border;
            layout: horizontal;
            align-vertical: middle;
        }
        #chats-title { text-style: bold; width: 1fr; align-vertical: middle; }
        #chats-close, .chats-close-btn {
            width: 5;
            min-width: 5;
            max-width: 5;
            height: 1;
            min-height: 1;
            max-height: 1;
            padding: 0;
            margin: 0;
            background: $surface-alt;
            color: $accent;
            border: none;
            content-align: center middle;
            text-style: bold;
            transition: background 100ms, color 100ms;
        }
        #chats-close:hover, .chats-close-btn:hover {
            background: $error;
            color: #ffffff;
            text-style: bold;
        }
        #chats-workspace-bar {
            height: auto;
            min-height: 3;
            padding: 0 2 1 2;
            border-bottom: solid $border 40%;
            background: $surface-alt 30%;
        }
        #chats-ws-label {
            color: $text-faint;
            width: auto;
            margin-right: 1;
        }
        #chats-ws-path {
            width: 1fr;
            text-style: bold;
            color: $accent;
            overflow: hidden;
        }
        #chats-ws-switch {
            min-width: 10;
            min-height: 3;
            height: 3;
            margin-left: 1;
            border: heavy;
            border-top: heavy $surface-highlight;
            border-left: heavy $surface-highlight;
            border-bottom: heavy $surface-dark;
            border-right: heavy $surface-dark;
            background: $surface-alt;
            color: $text;
            text-style: bold;
        }
        #chats-search-row {
            height: auto;
            min-height: 3;
            padding: 1 2 0 2;
        }
        #chats-search {
            width: 1fr;
            min-height: 3;
            background: $surface-dark;
            border: heavy $surface-dark;
            color: $text;
        }
        #chats-search:focus {
            border: heavy $accent;
            background: $surface-dark;
        }
        #chats-scope {
            min-width: 14;
            min-height: 3;
            height: 3;
            margin-left: 1;
            border: heavy;
            border-top: heavy $surface-highlight;
            border-left: heavy $surface-highlight;
            border-bottom: heavy $surface-dark;
            border-right: heavy $surface-dark;
            background: $surface-alt;
            text-style: bold;
            color: $text;
        }
        #chats-filters {
            height: auto;
            min-height: 3;
            padding: 0 2;
            overflow-x: hidden;
            layout: horizontal;
        }
        .chats-filter-btn {
            width: 1fr;
            min-width: 8;
            min-height: 3;
            height: 3;
            margin-right: 1;
            margin-top: 0;
            margin-bottom: 0;
            offset: 0 0;
            offset-x: 0;
            offset-y: 0;
            border: heavy;
            border-top: heavy $surface-highlight;
            border-left: heavy $surface-highlight;
            border-bottom: heavy $surface-dark;
            border-right: heavy $surface-dark;
            background: $surface-alt;
            color: $text;
            text-style: bold;
            padding: 0 1;
        }
        .chats-filter-btn:last-child {
            margin-right: 0;
        }
        .chats-filter-btn:hover {
            background: $surface-highlight;
            border-top: heavy #ffffff 60%;
            border-left: heavy #ffffff 60%;
            offset: 0 0;
            offset-y: 0;
        }
        .chats-filter-btn.-active,
        .chats-filter-btn.-active:focus,
        .chats-filter-btn.-active:hover {
            background: $accent 35%;
            color: #ffffff;
            border: heavy;
            border-top: heavy #ffffff 70%;
            border-left: heavy #ffffff 70%;
            border-bottom: heavy $surface-dark;
            border-right: heavy $surface-dark;
            text-style: bold;
            offset: 0 0;
            offset-x: 0;
            offset-y: 0;
            margin-top: 0;
            margin-bottom: 0;
        }
        #chats-list {
            height: 1fr;
            min-height: 8;
            overflow-y: auto;
            margin: 0;
            padding: 0 1;
            scrollbar-gutter: stable;
        }
        .chats-section-title {
            color: $text-faint;
            text-style: bold;
            height: 1;
            padding: 1 1 0 1;
        }
        .chats-ws-header {
            height: auto;
            min-height: 3;
            padding: 0 1;
            margin-top: 1;
            border-top: solid $border 40%;
            border-left: thick $accent 50%;
            background: $surface-alt 30%;
        }
        .chats-ws-header:hover { background: $surface-highlight 40%; }
        .chats-ws-header.-collapsed { opacity: 0.85; }
        .chats-date-label {
            color: $text-faint;
            height: 1;
            padding: 1 2 0 3;
            text-style: italic;
        }
        .chats-row {
            height: auto;
            min-height: 3;
            border-left: thick transparent;
            padding: 0 1 0 2;
            margin: 0 0 0 2;
            transition: background 100ms, color 100ms, border 100ms;
        }
        .chats-row:hover {
            background: $surface-highlight 40%;
        }
        .chats-row-sel {
            background: $surface-alt;
            border-left: thick $accent;
            text-style: bold;
        }
        .chats-row-pin { color: $warning; }
        #chats-empty {
            color: $text-faint;
            padding: 2 2;
            height: auto;
            min-height: 4;
        }
        #chats-btns {
            height: auto;
            min-height: 7;
            padding: 1 1 0 1;
            border-top: solid $border;
        }
        #chats-btns-row1, #chats-btns-row2 {
            height: 3;
            min-height: 3;
            width: 100%;
            margin-bottom: 1;
            layout: horizontal;
        }
        #chats-btns Button {
            margin-right: 1;
            width: 1fr;
            min-width: 8;
            height: 3;
            min-height: 3;
            border: heavy;
            border-top: heavy $surface-highlight;
            border-left: heavy $surface-highlight;
            border-bottom: heavy $surface-dark;
            border-right: heavy $surface-dark;
            background: $surface-alt;
            color: $text;
            text-style: bold;
            padding: 0 1;
        }
        #chats-btns-row1 Button:last-child, #chats-btns-row2 Button:last-child {
            margin-right: 0;
        }
        #chats-btns Button:hover {
            background: $surface-highlight;
            border-top: heavy #ffffff 60%;
            border-left: heavy #ffffff 60%;
        }
        #chats-btns Button.cct-btn-primary {
            background: $accent 35%;
            color: #ffffff;
            border: heavy;
            border-top: heavy #ffffff 70%;
            border-left: heavy #ffffff 70%;
            border-bottom: heavy $surface-dark;
            border-right: heavy $surface-dark;
        }
        #chats-btns Button.cct-btn-primary:hover {
            background: $accent 45%;
        }
        #chats-btns Button.cct-btn-danger {
            background: $error 25%;
            color: #ffffff;
            border: heavy;
            border-top: heavy #fca5a5 60%;
            border-left: heavy #fca5a5 60%;
            border-bottom: heavy $surface-dark;
            border-right: heavy $surface-dark;
        }
        #chats-btns Button.cct-btn-danger:hover {
            background: $error 35%;
        }
        #chats-hint {
            color: $text-faint;
            height: auto;
            min-height: 2;
            padding: 0 2 1 2;
        }
        """

        BINDINGS = [
            Binding("escape", "cancel", "Close"),
            Binding("down", "move_down_sel", "Next"),
            Binding("up", "move_up_sel", "Previous"),
            Binding("enter", "open_selected", "Open"),
            Binding("n", "new_chat", "New"),
            Binding("delete", "delete_chat", "Delete"),
            Binding("p", "toggle_pin", "Pin"),
            Binding("r", "rename_chat", "Rename"),
            Binding("a", "archive_chat", "Archive"),
            Binding("d", "duplicate_chat", "Duplicate"),
            Binding("s", "toggle_scope", "Scope"),
            Binding("slash", "focus_search", "Search"),
        ]

        FILTERS = [
            ("all", "All"),
            ("current_workspace", "Current"),
            ("pinned", "Pinned"),
            ("archived", "Archived"),
        ]

        def __init__(
            self,
            chats: Optional[List[Dict]] = None,
            active_id: Optional[str] = None,
            workspace_root: Optional[str] = None,
            pinned: Optional[List[Dict]] = None,
            recent: Optional[List[Dict]] = None,
        ):
            super().__init__()
            self._all_chats = list(chats or [])
            self._chats = list(self._all_chats)
            self._pinned = list(pinned or [])
            self._recent = list(recent or [])
            self._active_id = active_id
            self._workspace_root = workspace_root or ""
            self._selected: Optional[Tuple[str, str]] = None  # (kind, id)
            self._filter = "current_workspace"
            self._scope = "current"
            self._search = ""
            self._collapsed_ws: set = set()
            self._flat_rows: List[Tuple[str, str, Dict]] = []
            self._pick_initial_selection()

        def _pick_initial_selection(self):
            if self._active_id:
                for c in self._chats:
                    if c.get("id") == self._active_id:
                        self._selected = ("chat", self._active_id)
                        return
            if self._pinned:
                self._selected = ("chat", self._pinned[0].get("id", ""))
            elif self._chats:
                self._selected = ("chat", self._chats[0].get("id", ""))

        def compose(self) -> ComposeResult:
            with Vertical(id="chats-shell"):
                with Vertical(id="chats-box"):
                    with Horizontal(id="chats-titlebar"):
                        yield Static("▣  CAT CLI  ·  Chats", id="chats-title")
                        yield Button("✕", id="chats-close", classes="cct-ctrl chats-close-btn", tooltip="Close (Esc)")
                    with Horizontal(id="chats-workspace-bar"):
                        yield Static("Workspace: ", id="chats-ws-label")
                        yield Static("", id="chats-ws-path")
                        yield Button("Switch", id="chats-ws-switch", classes="cct-btn cct-btn-sm")
                    with Horizontal(id="chats-search-row"):
                        yield Input(placeholder="Search title, messages, path… (/ to focus)", id="chats-search")
                        yield Button("Current WS", id="chats-scope", classes="cct-btn cct-btn-sm")
                    with Horizontal(id="chats-filters"):
                        for key, label in self.FILTERS:
                            cls = "chats-filter-btn"
                            if key == self._filter:
                                cls += " -active"
                            yield Button(label, id=f"chats-filter-{key}", classes=cls)
                    with ScrollableContainer(id="chats-list"):
                        pass
                    with Vertical(id="chats-btns"):
                        with Horizontal(id="chats-btns-row1"):
                            yield Button("+ New", id="chats-new", classes="cct-btn cct-btn-sm")
                            yield Button("Open", id="chats-open", classes="cct-btn cct-btn-sm cct-btn-primary")
                            yield Button("Rename", id="chats-rename", classes="cct-btn cct-btn-sm")
                            yield Button("Pin", id="chats-pin", classes="cct-btn cct-btn-sm")
                            yield Button("Archive", id="chats-archive", classes="cct-btn cct-btn-sm")
                        with Horizontal(id="chats-btns-row2"):
                            yield Button("Duplicate", id="chats-dup", classes="cct-btn cct-btn-sm")
                            yield Button("Export", id="chats-export", classes="cct-btn cct-btn-sm")
                            yield Button("Copy Path", id="chats-copy-path", classes="cct-btn cct-btn-sm")
                            yield Button("Reveal Folder", id="chats-reveal", classes="cct-btn cct-btn-sm")
                            yield Button("Delete", id="chats-delete", classes="cct-btn cct-btn-sm cct-btn-danger")
                    yield Static(
                        "Enter open · ↑↓ select · P pin · R rename · Del delete · Esc close",
                        id="chats-hint",
                    )

        def on_mount(self):
            self._refresh_workspace_bar()
            self._apply_layout_width()
            self.call_after_refresh(self._refresh)
            try:
                self.query_one("#chats-search").focus()
            except Exception:
                pass

        def on_resize(self, _event=None):
            self._apply_layout_width()

        def _apply_layout_width(self):
            try:
                box = self.query_one("#chats-box")
                w = self.size.width if self.size.width else 80
                if w < 48:
                    box.styles.max_width = w - 2
                elif w < 72:
                    box.styles.max_width = w - 4
                else:
                    box.styles.max_width = min(94, w - 4)
            except Exception:
                pass

        def _refresh_workspace_bar(self):
            try:
                path = self._workspace_root or "No workspace open"
                short = path
                if len(short) > 48:
                    short = "…" + short[-45:]
                self.query_one("#chats-ws-path", Static).update(short)
                scope_btn = self.query_one("#chats-scope", Button)
                scope_btn.label = "All WS" if self._scope == "all" else "Current WS"
            except Exception:
                pass

        def _rebuild_flat_rows(self):
            from .. import chat_store

            self._flat_rows = []
            seen_cids = set()

            if self._search.strip():
                self._chats = chat_store.search_chats(
                    self._search,
                    workspace_root=self._workspace_root,
                    scope=self._scope,
                )
                self._chats = chat_store.filter_chats(
                    self._chats,
                    filter_name=self._filter,
                    workspace_root=self._workspace_root,
                )
            else:
                if self._scope == "current" and self._workspace_root:
                    base = chat_store.get_chat_summaries(self._workspace_root, include_archived=True)
                else:
                    base = chat_store.get_chat_summaries(include_archived=True)
                self._chats = chat_store.filter_chats(
                    base,
                    filter_name=self._filter,
                    workspace_root=self._workspace_root,
                )

            # 1. Pinned filter view
            if self._filter == "pinned":
                for c in self._chats:
                    cid = c.get("id")
                    if cid and cid not in seen_cids:
                        seen_cids.add(cid)
                        self._flat_rows.append(("chat", cid, c))

            # 2. Standard hierarchical view
            else:
                if self._filter != "archived" and not self._search and self._pinned:
                    pinned_matches = []
                    for c in self._pinned:
                        if self._scope == "current" and self._workspace_root:
                            if not chat_store.paths_equal(c.get("workspace_root"), self._workspace_root):
                                continue
                        pinned_matches.append(c)
                    if pinned_matches:
                        self._flat_rows.append(("section", "pinned", {}))
                        for c in pinned_matches:
                            cid = c.get("id")
                            if cid and cid not in seen_cids:
                                seen_cids.add(cid)
                                self._flat_rows.append(("chat", cid, c))

                # Group remaining chats hierarchically by workspace
                groups = chat_store.group_chats_by_workspace(self._chats)
                for g in groups:
                    wkey = g.get("workspace_key", "")
                    chats_in_g = [c for c in g.get("chats", []) if c.get("id") not in seen_cids]
                    if not chats_in_g and not self._search:
                        continue
                    if wkey in self._collapsed_ws:
                        self._flat_rows.append(("ws_collapsed", wkey, g))
                    else:
                        self._flat_rows.append(("ws", wkey, g))
                        for date_label, date_chats in chat_store.group_chats_by_date(chats_in_g):
                            valid_chats = [c for c in date_chats if c.get("id") not in seen_cids]
                            if not valid_chats:
                                continue
                            self._flat_rows.append(("date", f"{wkey}:{date_label}", {"label": date_label}))
                            for c in valid_chats:
                                cid = c.get("id")
                                seen_cids.add(cid)
                                self._flat_rows.append(("chat", cid, c))

            if not self._selected and self._flat_rows:
                for kind, rid, _ in self._flat_rows:
                    if kind == "chat":
                        self._selected = (kind, rid)
                        break

        def _refresh(self):
            from .. import chat_store
            from . import theme_css

            self._rebuild_flat_rows()
            try:
                scroll = self.query_one("#chats-list", ScrollableContainer)
            except Exception:
                return
            scroll.remove_children()

            hex_text = theme_css.current_hex("text")
            hex_faint = theme_css.current_hex("text-faint")
            hex_accent = theme_css.current_hex("accent")

            if not self._flat_rows:
                if self._workspace_root and self._filter == "current_workspace":
                    msg = (
                        "No conversations in this workspace\n\n"
                        "Start a new conversation to begin."
                    )
                else:
                    msg = "No conversations match your filters."
                scroll.mount(Static(msg, id="chats-empty"))
                return

            for kind, rid, data in self._flat_rows:
                if kind == "section":
                    title = "⭐ PINNED" if rid == "pinned" else "⏱ CONVERSATIONS"
                    scroll.mount(Static(title, classes="chats-section-title"))
                elif kind == "ws":
                    name = data.get("workspace_name", "Workspace")
                    path = data.get("workspace_root") or "Legacy / Unassigned"
                    count = data.get("chat_count", 0)
                    activity = _rel_time(data.get("last_activity", 0))
                    chat_word = "chat" if count == 1 else "chats"
                    row = Static(
                        f"[{hex_accent}]▾ 📁 WORKSPACE {name}[/{hex_accent}]  "
                        f"[{hex_faint}]({count} {chat_word}) · {activity}[/{hex_faint}]\n"
                        f"   [{hex_faint}]{path}[/{hex_faint}]",
                        classes="chats-ws-header",
                    )
                    row._row_kind = "ws"
                    row._row_id = rid
                    scroll.mount(row)
                elif kind == "ws_collapsed":
                    name = data.get("workspace_name", "Workspace")
                    path = data.get("workspace_root") or "Legacy / Unassigned"
                    count = data.get("chat_count", 0)
                    row = Static(
                        f"[{hex_faint}]▸ 📁 WORKSPACE {name} ({count}) · {path}[/{hex_faint}]",
                        classes="chats-ws-header -collapsed",
                    )
                    row._row_kind = "ws_collapsed"
                    row._row_id = rid
                    scroll.mount(row)
                elif kind == "date":
                    label = str(data.get("label", ""))
                    scroll.mount(Static(f"── {label} ──", classes="chats-date-label"))
                elif kind == "chat":
                    chat = data
                    cid = chat.get("id", "")
                    name = chat.get("name", "Untitled")
                    ws_short = chat_store.workspace_display_name(chat.get("workspace_root"))
                    ts = _rel_time(chat.get("updated_at", 0))
                    pin = "⭐ " if chat.get("pinned") else ""
                    is_sel = self._selected == ("chat", cid)
                    cls = "chats-row-sel" if is_sel else "chats-row"
                    if chat.get("pinned"):
                        cls += " chats-row-pin"
                    turn_cnt = chat.get("turn_count", 0)
                    if not turn_cnt and "turns" in chat:
                        turn_cnt = len(chat.get("turns", []))
                    t_str = f"{turn_cnt} turn" if turn_cnt == 1 else f"{turn_cnt} turns"
                    marker = "▶ " if is_sel else "  "
                    row = Static(
                        f"{marker}[{hex_text}]{pin}{name}[/{hex_text}]\n"
                        f"    [{hex_faint}]{ws_short} · {t_str} · {ts}[/{hex_faint}]",
                        classes=cls,
                    )
                    row._row_kind = "chat"
                    row._row_id = cid
                    row._chat_data = chat
                    scroll.mount(row)

        def _sel_chat(self) -> Optional[Dict]:
            if not self._selected or self._selected[0] != "chat":
                return None
            cid = self._selected[1]
            for _, _, data in self._flat_rows:
                if data.get("id") == cid:
                    return data
            return None

        def _delete_selected_chat(self):
            chat = self._sel_chat()
            if not chat:
                return
            cid = chat.get("id")
            name = chat.get("name", "Untitled")
            from .nav_screens import ConfirmDeleteChatModal

            def _on_confirm(confirmed):
                if not confirmed:
                    return
                try:
                    from .. import chat_store
                    chat_store.delete_chat(cid)
                    # If this chat was active in the app, reset active chat state
                    if hasattr(self.app, "_current_chat_id") and self.app._current_chat_id == cid:
                        try:
                            self.app._clear_active_chat_ui()
                            self.app._show_chat_empty_state()
                        except Exception:
                            pass
                    # Update in-memory collections
                    self._all_chats = [c for c in self._all_chats if c.get("id") != cid]
                    self._chats = [c for c in self._chats if c.get("id") != cid]
                    self._pinned = [c for c in self._pinned if c.get("id") != cid]
                    self._recent = [c for c in self._recent if c.get("id") != cid]
                    self._selected = None
                    self._pick_initial_selection()
                    self._refresh()
                    try:
                        self.notify(f"Deleted conversation: {name}", severity="information")
                    except Exception:
                        pass
                except Exception as e:
                    try:
                        self.notify(f"Could not delete: {e}", severity="error")
                    except Exception:
                        pass

            try:
                self.app.push_screen(ConfirmDeleteChatModal(name), _on_confirm)
            except Exception:
                self.dismiss({"action": "delete", "id": cid, "name": name})

        def _move_sel(self, delta: int):
            chat_indices = [i for i, (k, _, _) in enumerate(self._flat_rows) if k == "chat"]
            if not chat_indices:
                return
            cur = 0
            if self._selected and self._selected[0] == "chat":
                for j, idx in enumerate(chat_indices):
                    if self._flat_rows[idx][1] == self._selected[1]:
                        cur = j
                        break
            nxt = (cur + delta) % len(chat_indices)
            idx = chat_indices[nxt]
            self._selected = ("chat", self._flat_rows[idx][1])
            self._refresh()

        def on_input_changed(self, event):
            if event.input.id == "chats-search":
                self._search = event.value
                self._refresh()

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)
            elif event.key == "down":
                self._move_sel(1)
            elif event.key == "up":
                self._move_sel(-1)
            elif event.key == "enter":
                chat = self._sel_chat()
                if chat:
                    self.dismiss({"action": "open", "id": chat.get("id")})
            elif event.key in ("delete", "backspace"):
                self._delete_selected_chat()
            elif event.key == "n":
                self.dismiss({"action": "new"})
            elif event.key == "p":
                chat = self._sel_chat()
                if chat:
                    self.dismiss({"action": "pin", "id": chat.get("id"), "pinned": not chat.get("pinned")})
            elif event.key == "r":
                chat = self._sel_chat()
                if chat:
                    self.dismiss({"action": "rename", "id": chat.get("id"), "name": chat.get("name")})
            elif event.key == "a":
                chat = self._sel_chat()
                if chat:
                    self.dismiss({"action": "archive", "id": chat.get("id"), "archived": not chat.get("archived")})
            elif event.key == "d":
                chat = self._sel_chat()
                if chat:
                    self.dismiss({"action": "duplicate", "id": chat.get("id")})
            elif event.key == "s":
                self._toggle_scope()
            elif event.key == "slash":
                try:
                    self.query_one("#chats-search", Input).focus()
                except Exception:
                    pass

        def _toggle_scope(self):
            self._scope = "all" if self._scope == "current" else "current"
            self._refresh_workspace_bar()
            self._refresh()

        def on_click(self, event):
            target = getattr(event, "widget", None)
            kind = getattr(target, "_row_kind", None)
            rid = getattr(target, "_row_id", None)
            if kind == "chat" and rid:
                if self._selected == ("chat", rid):
                    self.dismiss({"action": "open", "id": rid})
                    return
                self._selected = ("chat", rid)
                self._refresh()
                return
            if kind == "ws" and rid:
                self._collapsed_ws.add(rid)
                self._refresh()
                return
            if kind == "ws_collapsed" and rid:
                self._collapsed_ws.discard(rid)
                self._refresh()
                return
            if getattr(event, "widget", None) in (self, None):
                try:
                    if len(self.app.screen_stack) > 1:
                        self.dismiss(None)
                except Exception:
                    pass

        def on_button_pressed(self, event):
            bid = event.button.id or ""
            if bid == "chats-close":
                self.dismiss(None)
            elif bid == "chats-new":
                self.dismiss({"action": "new"})
            elif bid == "chats-open":
                chat = self._sel_chat()
                if chat:
                    self.dismiss({"action": "open", "id": chat.get("id")})
            elif bid == "chats-rename":
                chat = self._sel_chat()
                if chat:
                    self.dismiss({"action": "rename", "id": chat.get("id"), "name": chat.get("name")})
            elif bid == "chats-pin":
                chat = self._sel_chat()
                if chat:
                    self.dismiss({"action": "pin", "id": chat.get("id"), "pinned": not chat.get("pinned")})
            elif bid == "chats-archive":
                chat = self._sel_chat()
                if chat:
                    self.dismiss({"action": "archive", "id": chat.get("id"), "archived": not chat.get("archived")})
            elif bid == "chats-dup":
                chat = self._sel_chat()
                if chat:
                    self.dismiss({"action": "duplicate", "id": chat.get("id")})
            elif bid == "chats-export":
                chat = self._sel_chat()
                if chat:
                    self.dismiss({"action": "export", "id": chat.get("id")})
            elif bid == "chats-copy-path":
                chat = self._sel_chat()
                if chat:
                    self.dismiss({"action": "copy_path", "id": chat.get("id")})
            elif bid == "chats-reveal":
                chat = self._sel_chat()
                if chat:
                    self.dismiss({"action": "reveal", "id": chat.get("id")})
            elif bid == "chats-delete":
                self._delete_selected_chat()
            elif bid == "chats-ws-switch":
                self.dismiss({"action": "switch_workspace"})
            elif bid == "chats-scope":
                self._toggle_scope()
            elif bid.startswith("chats-filter-"):
                self._filter = bid.replace("chats-filter-", "")
                for btn in self.query("#chats-filters Button"):
                    btn.remove_class("-active")
                event.button.add_class("-active")
                self._refresh()

        def action_new_chat(self):
            self.dismiss({"action": "new"})

        def action_cancel(self):
            self.dismiss(None)

        def action_open_selected(self):
            chat = self._sel_chat()
            if chat:
                self.dismiss({"action": "open", "id": chat.get("id")})

        def action_delete_chat(self):
            self._delete_selected_chat()

        def action_toggle_pin(self):
            chat = self._sel_chat()
            if chat:
                self.dismiss({"action": "pin", "id": chat.get("id"), "pinned": not chat.get("pinned")})

        def action_rename_chat(self):
            chat = self._sel_chat()
            if chat:
                self.dismiss({"action": "rename", "id": chat.get("id"), "name": chat.get("name")})

        def action_archive_chat(self):
            chat = self._sel_chat()
            if chat:
                self.dismiss({"action": "archive", "id": chat.get("id"), "archived": not chat.get("archived")})

        def action_duplicate_chat(self):
            chat = self._sel_chat()
            if chat:
                self.dismiss({"action": "duplicate", "id": chat.get("id")})

        def action_toggle_scope(self):
            self._toggle_scope()

        def action_focus_search(self):
            try:
                self.query_one("#chats-search", Input).focus()
            except Exception:
                pass

        def action_move_down_sel(self):
            self._move_sel(1)

        def action_move_up_sel(self):
            self._move_sel(-1)

else:
    ChatsPanel = None  # type: ignore
