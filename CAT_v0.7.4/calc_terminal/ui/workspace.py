"""
CCT UI — ui/workspace.py (spec v0.7 Workspace section, distinct from
calc_terminal/workspace.py which stores *generated artifacts*, not the
IDE's open-folder state).

Adaptive workspace layout: Explorer sidebar on the left, a CHAT COLUMN
in the middle, and an independent RIGHT PANE that switches between the
Code Editor and the Live Web Preview:

    ┌──────────────┬─┬───────────────────┬─┬──────────────────┐
    │ FILE EXPLORER│║│ CHAT / AI         ║│ CODE ⇄ WEB       │
    │              │║│ (ConversationView)║│ (EditorPane /    │
    │  (draggable  │║│                   ║│  PreviewPanel)   │
    │   divider)   │║├───────────────────┤╵│ (drag divider)   │
    │              │║│ grip              ║│                  │
    │              │║├───────────────────┤╵│                  │
    │              │║│ CHAT COMPOSER     ║│                  │
    └──────────────┴─┴───────────────────┴─┴──────────────────┘

v0.7.10 layout contract:
* THREE independent multitasking sections (spec section 1): the File
  Pane, the Chat Area (with its own composer INSIDE its column), and
  the Code/Preview pane each own their geometry — the chat box is
  physically unable to overlap the editor or preview because they are
  siblings of separate columns, never overlays.
* The right pane preserves its width across Code⇄Preview switches and
  is horizontally resizable (RightPaneResizeHandle, persisted).
* Both halves of the right pane stay MOUNTED at all times — switching
  modes only flips `display`, so editor tabs/cursor/unsaved state and
  preview navigation/history all survive every switch.
* Closing the last editor tab never touches Web Preview (the server/
  browser belong to the workspace session, not a tab).

Narrow terminals fall back to the historical stacked behavior: a
Chat/Files switcher row shows exactly one section at a time.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os

from .sidebar import Explorer
from .editor import EditorPane
from .preview_panel import PreviewPanel
from .resizers import (ExplorerResizeHandle, ComposerResizeHandle,
                       RightPaneResizeHandle, SplitPreviewResizer,
                       load_layout, save_layout,
                       EXPLORER_DEFAULT_WIDTH, RIGHTPANE_DEFAULT_WIDTH)

TEXTUAL_AVAILABLE = True
try:
    from ..browser import WorkspaceMode
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Button, Static
except Exception:
    TEXTUAL_AVAILABLE = False


if TEXTUAL_AVAILABLE:

    def _safe_glyph(emoji: str, fallback: str) -> str:
        try:
            import sys
            enc = getattr(sys.stdout, "encoding", None) or "utf-8"
            emoji.encode(enc)
            return emoji
        except Exception:
            return fallback

    class WorkspaceShell(Horizontal):
        """Explorer (left) + adaptive main area (right) that keeps the
        chat, the editor AND the web preview mounted at all times."""

        # main-area width at which the chat and the right pane sit side
        # by side instead of stacking behind the switcher. Textual CSS
        # has no media queries, so this is decided in Python on Resize.
        SPLIT_MIN_WIDTH = 68

        def __init__(self, conversation_view, composer=None, id="cct-workspace"):
            super().__init__(id=id)
            self._conversation_view = conversation_view
            self._composer = composer
            self.workspace_root = None
            self._files_count = 0
            self._showing = "chat"      # "chat" | "files" (stack mode only)
            self._mode = WorkspaceMode.CODE
            self._fullscreen = False
            self._fullscreen_restore = None

        def compose(self):
            yield Explorer()
            yield ExplorerResizeHandle(self)
            with Vertical(id="cct-workspace-main"):
                with Horizontal(id="cct-workspace-switcher"):
                    yield Button(_safe_glyph("▶", ">"), id="cct-sidebar-expand-btn", classes="cct-chat-nav-btn cct-sidebar-expand-btn", tooltip="Open Sidebar (Ctrl+B)")
                    yield Button("Chat", id="cct-switch-chat", classes="cct-switch")
                    yield Button("Files", id="cct-switch-files", classes="cct-switch")
                with Horizontal(id="cct-workspace-body"):
                    with Vertical(id="cct-chat-col"):
                        with Horizontal(id="cct-chat-nav"):
                            yield Button(_safe_glyph("▶ Explorer", "> Explorer"), id="cct-chat-sidebar-toggle", classes="cct-chat-nav-btn", tooltip="Open Sidebar (Ctrl+B)")
                        yield self._conversation_view
                        if self._composer is not None:
                            yield ComposerResizeHandle(self)
                            yield self._composer
                    yield RightPaneResizeHandle(self)
                    with Vertical(id="cct-right-pane"):
                        # In split mode these become horizontal side-by-side with resizer between
                        yield EditorPane()
                        yield SplitPreviewResizer(self)
                        yield PreviewPanel()

        def on_mount(self):
            # No folder open yet: the Explorer stays hidden so the app
            # looks like a clean chat until the first Open Folder.
            self.explorer.display = False
            self.preview_panel.display = False
            try:
                saved = load_layout()
                w = saved.get("explorer_width")
                if w:
                    self.explorer.set_width(w)
                rw = saved.get("rightpane_width")
                if rw:
                    self.set_right_width(rw)
            except Exception:
                pass
            self.sync_resizer()
            self.sync_right_resizer()
            self._relayout()
            try:
                self.apply_custom_layout()
            except Exception:
                pass
            self._sync_sidebar_toggle()

        # ------------------------------------------------- properties --
        @property
        def fullscreen(self):
            return self._fullscreen

        @property
        def mode(self) -> "WorkspaceMode":
            return self._mode

        @property
        def explorer(self):
            try:
                return self.query_one(Explorer)
            except Exception:
                return None

        @property
        def editor(self):
            try:
                return self.query_one(EditorPane)
            except Exception:
                return None

        @property
        def preview_panel(self):
            try:
                return self.query_one(PreviewPanel)
            except Exception:
                return None

        @property
        def right_pane(self):
            """The #cct-right-pane container (width owner for resizing),
            or None before mount."""
            try:
                return self.query_one("#cct-right-pane", Vertical)
            except Exception:
                return None

        @property
        def chat_column(self):
            try:
                return self.query_one("#cct-chat-col", Vertical)
            except Exception:
                return None

        # ------------------------------------------------- resize handles --
        def sync_resizer(self):
            """The explorer-divider must exist exactly when the explorer
            does — hidden together, never left floating in between."""
            try:
                handle = self.query_one(ExplorerResizeHandle)
            except Exception:
                return
            visible = self.explorer.display and self.explorer.width > 0
            handle.display = visible

        def sync_right_resizer(self):
            """The right-divider exists only while the right pane is a
            real, visible column (split mode, not fullscreen)."""
            try:
                handle = self.query_one(RightPaneResizeHandle)
                pane = self.right_pane
            except Exception:
                return
            if pane is None:
                handle.display = False
                return
            handle.display = bool(
                pane.display and not self._fullscreen
                and self.chat_visible)

        @property
        def chat_visible(self):
            chat = self._conversation_view
            return bool(chat.display) if chat is not None else False

        def on_sidebar_toggled(self, event):
            """Explorer collapse/expand crossed through here on its way
            up to CCTApp — keep the divider in lockstep."""
            self.sync_resizer()
            self._relayout()
            self._sync_sidebar_toggle()

        def persist_explorer_width(self):
            save_layout(explorer_width=self.explorer.width or None)

        def on_resize(self):
            # Resize storms (rapid terminal drags) are coalesced by a
            # leading-edge + trailing debouncer: the first event lays
            # out immediately (interactive feel preserved), the burst
            # settles into one final layout instead of N.
            try:
                from . import design_system
                deb = getattr(self, "_relayout_debouncer", None)
                if deb is None or not isinstance(
                        deb, design_system.RelayoutDebouncer):
                    deb = design_system.RelayoutDebouncer(delay=0.06)
                    self._relayout_debouncer = deb
                deb.request(self, self._do_resize_layout)
            except Exception:
                self._do_resize_layout()

        def _do_resize_layout(self):
            # While the right pane is fullscreen the split/stack logic
            # must not fight the expanded layout.
            self._clamp_explorer_to_window()
            if not self._fullscreen:
                self._relayout()
            self._sync_sidebar_toggle()

        def _clamp_explorer_to_window(self):
            """Window got smaller? Shrink the explorer proportionally so
            the chat pane always keeps a usable width."""
            try:
                from .resizers import EXPLORER_MIN_WIDTH, EXPLORER_MAX_FRACTION
                explorer = self.explorer
                if not explorer.display or explorer.width <= 0:
                    return
                ceiling = max(EXPLORER_MIN_WIDTH + 4,
                              int(self.size.width * EXPLORER_MAX_FRACTION))
                if explorer.width > ceiling:
                    explorer.set_width(ceiling)
                    self.sync_resizer()
            except Exception:
                pass

        # ------------------------------------------- right pane mode --
        def set_right_mode(self, mode: "WorkspaceMode"):
            """CODE ⇄ PREVIEW ⇄ SPLIT switch. Pure display flips: the editor
            keeps its tabs/state, the preview keeps navigation/history,
            and the right pane's WIDTH never changes across switches.
            SPLIT shows both side-by-side, resizable."""
            if isinstance(mode, str):
                low = mode.lower()
                if low.startswith("split"):
                    mode = WorkspaceMode.SPLIT
                elif low.startswith("prev"):
                    mode = WorkspaceMode.PREVIEW
                else:
                    mode = WorkspaceMode.CODE
            self._mode = mode
            editor = self.editor
            panel = self.preview_panel
            right = self.right_pane
            if editor is not None:
                if mode is WorkspaceMode.SPLIT:
                    editor.display = True
                else:
                    editor.display = (mode is WorkspaceMode.CODE)
            if panel is not None:
                if mode is WorkspaceMode.SPLIT:
                    panel.display = True
                else:
                    panel.display = (mode is WorkspaceMode.PREVIEW)
            # Split layout: horizontal side-by-side inside right pane
            # Handle split resizer visibility
            try:
                from .resizers import SplitPreviewResizer
                resizer = self.query_one(SplitPreviewResizer)
                resizer.display = (mode is WorkspaceMode.SPLIT and not self._fullscreen)
            except Exception:
                pass
            if right is not None:
                try:
                    if mode is WorkspaceMode.SPLIT:
                        right.styles.layout = "horizontal"
                        # Editor and preview each take half
                        if editor is not None:
                            editor.styles.width = "1fr"
                            editor.styles.height = "100%"
                        if panel is not None:
                            panel.styles.width = "1fr"
                            panel.styles.height = "100%"
                            panel.styles.border_left = "none"
                    else:
                        right.styles.layout = "vertical"
                        if editor is not None:
                            editor.styles.width = "100%"
                            editor.styles.height = "1fr" if mode is WorkspaceMode.CODE else "100%"
                        if panel is not None:
                            panel.styles.width = "100%"
                            panel.styles.height = "1fr" if mode is WorkspaceMode.PREVIEW else "100%"
                            panel.styles.border_left = "none"
                except Exception:
                    pass
            # In stacked narrow mode the Files entry means the right
            # pane whichever half it currently shows.
            if not self._fullscreen:
                self._relayout()

        # -------------------------------------------- fullscreen pane --
        def set_fullscreen(self, active):
            """⿻ — expands whatever the right pane currently shows
            (Code OR Web Preview) to the whole viewport. Nothing is
            destroyed: Explorer/chat are display-hidden and the exact
            previous configuration is restored on exit."""
            try:
                main = self.query_one("#cct-workspace-main", Vertical)
                switcher = self.query_one("#cct-workspace-switcher")
            except Exception:
                return
            right = self.right_pane
            if right is None:
                return
            chat_col = self.chat_column
            explorer = self.explorer
            if active:
                if self._fullscreen:
                    return
                self._fullscreen = True
                self._fullscreen_restore = {
                    "explorer": explorer.display,
                    "showing": self._showing,
                    "chat_display": chat_col.display if chat_col else True,
                    "right_width": right.size.width or None,
                }
                explorer.display = False
                self.sync_resizer()
                switcher.display = False
                if chat_col is not None:
                    chat_col.display = False
                try:
                    self.query_one(RightPaneResizeHandle).display = False
                except Exception:
                    pass
                right.styles.width = "1fr"
                main.styles.width = "1fr"
            else:
                if not self._fullscreen:
                    return
                self._fullscreen = False
                restore = self._fullscreen_restore or {}
                explorer.display = bool(restore.get("explorer"))
                self._showing = restore.get("showing", "chat")
                main.styles.width = "1fr"
                if chat_col is not None:
                    chat_col.display = True
                saved_w = restore.get("right_width")
                right.styles.width = int(saved_w) if saved_w \
                    else RIGHTPANE_DEFAULT_WIDTH
                self.sync_resizer()
                self.sync_right_resizer()
                self._relayout()

        # --------------------------------------------- adaptive layout --
        def _relayout(self):
            """Split vs. stacked vs. chat-only, driven by the width of
            the main area and whether there is anything to show in the
            right pane (editor tabs or an active preview)."""
            try:
                main = self.query_one("#cct-workspace-main", Vertical)
                switcher = self.query_one("#cct-workspace-switcher")
            except Exception:
                return  # resize can fire before compose() lands
            right = self.right_pane
            chat_col = self.chat_column
            if right is None or chat_col is None:
                return
            n = self._files_count
            has_preview = self._mode in (WorkspaceMode.PREVIEW, WorkspaceMode.SPLIT)
            has_files = n > 0 or (self.editor is not None and bool(getattr(self.editor, "_open_paths", {})))
            explorer_w = self.explorer.width if self.explorer.display else 0
            usable = max(0, self.size.width - explorer_w)
            split_possible = usable >= self.SPLIT_MIN_WIDTH

            editor_disabled = False
            try:
                from .. import customization as _cust
                if _cust.is_active():
                    cust_mgr = _cust.get_manager()
                    ed_cfg = cust_mgr.get_component("code_editor") or cust_mgr.get_component("editor") or {}
                    if not ed_cfg.get("visible", True):
                        editor_disabled = True
            except Exception:
                pass

            # Responsive tier (design_system breakpoints): drives the
            # .cat-bp-* CSS classes that strip secondary chrome on
            # narrow/short terminals. Display flags below stay fully
            # owned by _relayout (recomputed every resize), so user
            # state (explorer visibility, _showing) is never mutated.
            tiny = False
            try:
                from . import design_system
                bp = design_system.breakpoint_for(
                    self.size.width, self.size.height)
                for _cls in ("cat-bp-large", "cat-bp-medium",
                             "cat-bp-small", "cat-bp-tiny"):
                    self.set_class(bp == _cls[7:], _cls)
                try:
                    short = (self.size.height or 24) <= 20
                except Exception:
                    short = False
                self.set_class(short, "cat-short")
                tiny = (bp == "tiny")
            except Exception:
                pass

            if (not has_files and not has_preview) or editor_disabled:
                # Nothing to show on the right or editor disabled: chat alone, full width.
                right.display = False
                self.sync_right_resizer()
                switcher.display = False
                chat_col.display = True
                chat_col.styles.width = "1fr"
                self._sync_switcher()
                self._sync_sidebar_toggle()
                return

            if tiny:
                # Extremely small terminal: clean chat-first fallback.
                # No switcher, no right pane, no overflow — the chat
                # column (min-width 24, overflow hidden) always fits.
                switcher.display = False
                chat_col.display = True
                right.display = False
                chat_col.styles.width = "1fr"
                self.sync_right_resizer()
                self._sync_switcher()
                self._sync_sidebar_toggle()
                return

            if split_possible:
                # Both columns visible, side by side.
                switcher.display = False
                chat_col.display = True
                right.display = True
                chat_col.styles.width = "1fr"
            else:
                # Stacked: switcher on top, exactly one section below.
                switcher.display = True
                chat_col.styles.width = "1fr"
                chat_col.display = self._showing == "chat"
                right.display = self._showing == "files"
            self.sync_right_resizer()
            self._sync_switcher()
            self._sync_sidebar_toggle()
            try:
                exp_btn = self.query_one("#cct-sidebar-expand-btn", Button)
                exp_btn.display = (not self.explorer.display or self.explorer.width == 0)
            except Exception:
                pass

        def _sync_switcher(self):
            """Highlights whichever of Chat/Files is currently shown in
            stacked mode (CSS decides the exact look)."""
            try:
                self.query_one("#cct-switch-chat", Button).set_class(
                    self._showing == "chat", "-active")
                self.query_one("#cct-switch-files", Button).set_class(
                    self._showing == "files", "-active")
            except Exception:
                pass

        def on_editor_tabs_changed(self, event):
            self._files_count = event.count
            self._relayout()

        def on_chat_requested(self, event):
            """Esc in the editor (or any other ChatRequested sender):
            bring the chat forward in stacked mode. The app handles
            focusing the composer after this bubbles up to it."""
            self._showing = "chat"
            self._relayout()

        def on_button_pressed(self, event):
            if event.button.id == "cct-switch-chat":
                self._showing = "chat"
                self._relayout()
            elif event.button.id == "cct-switch-files":
                self._showing = "files"
                self._relayout()
            elif event.button.id in ("cct-sidebar-expand-btn", "cct-chat-sidebar-toggle"):
                event.stop()
                self.toggle_sidebar()
            elif event.button.id == "cct-chat-clear-btn":
                event.stop()
                if hasattr(self.app, "_new_chat_session"):
                    self.app._new_chat_session()
                elif hasattr(self.app, "conversation"):
                    self.app.conversation.clear()
            elif event.button.id == "cct-chat-export-btn":
                event.stop()
                if hasattr(self.app, "_export_chat"):
                    self.app._export_chat()
            elif event.button.id == "cct-chat-reload-btn":
                event.stop()
                if hasattr(self.app, "_retry_last_turn"):
                    self.app._retry_last_turn()

        def toggle_sidebar(self):
            if self.explorer:
                if not self.explorer.display or self.explorer.width == 0:
                    self.explorer.display = True
                    restore_w = getattr(self.explorer, "_restore_width", None) or 32
                    self.explorer.set_width(max(restore_w, 32))
                else:
                    self.explorer.toggle()
                self.sync_resizer()
                self._relayout()
                self._sync_sidebar_toggle()

        def _sync_sidebar_toggle(self):
            try:
                collapsed = (not self.explorer.display or self.explorer.width == 0)
                nav = self.query_one("#cct-chat-nav", Horizontal)
                btn = self.query_one("#cct-chat-sidebar-toggle", Button)
                nav.display = collapsed
                if collapsed:
                    btn.label = _safe_glyph("▶ Explorer", "> Explorer")
                    btn.tooltip = "Open Sidebar (Ctrl+B)"
            except Exception:
                pass
            try:
                exp_btn = self.query_one("#cct-sidebar-expand-btn", Button)
                collapsed = (not self.explorer.display or self.explorer.width == 0)
                exp_btn.display = collapsed
            except Exception:
                pass

        def close_workspace(self):
            self.workspace_root = None
            if self.explorer:
                try:
                    self.explorer.close_workspace()
                except Exception:
                    pass
            self.sync_resizer()
            self._relayout()
            self._sync_sidebar_toggle()

        # --------------------------------------------------------- API --
        def set_right_width(self, width):
            """Width owner for the CODE/PREVIEW pane (both halves share
            one geometry, so switching modes can never resize it). The
            CLAMPED value is remembered so persistence never depends on
            a layout pass having landed."""
            pane = self.right_pane
            try:
                from .resizers import (RIGHTPANE_MIN_WIDTH,
                                       RIGHTPANE_MAX_FRACTION)
                total = max(30, self.size.width)
                ceiling = max(RIGHTPANE_MIN_WIDTH + 4,
                              int(total * RIGHTPANE_MAX_FRACTION))
                width = max(RIGHTPANE_MIN_WIDTH, min(ceiling, int(width)))
            except Exception:
                pass
            self._rightpane_width = width
            if pane is not None:
                pane.styles.width = width
            # Stretching the editor can make chat too narrow → re-evaluate
            # split vs stacked so dashboard never gets overlapped.
            if not self._fullscreen:
                try:
                    self._relayout()
                except Exception:
                    pass

        def persist_rightpane_width(self):
            save_layout(rightpane_width=getattr(self, "_rightpane_width",
                                                None))

        def open_folder(self, path):
            path = os.path.abspath(os.path.expanduser(path))
            if not os.path.isdir(path):
                return False
            self.workspace_root = path
            self.explorer.display = True
            self.explorer.open_folder(path)
            self.sync_resizer()
            self._relayout()
            self._sync_sidebar_toggle()
            return True

        def open_file(self, path):
            """Open a file in the editor WITHOUT disturbing a running
            Web Preview (spec section 11: tabs and preview are
            independent). Only when the right pane is already in CODE
            mode do we bring it forward in stacked layouts."""
            editor = self.editor
            if editor is None:
                return False
            if self._mode is WorkspaceMode.CODE and not self._fullscreen:
                self._showing = "files"
                self._relayout()
            return editor.open_file(path)

        def open_file_at(self, path, line=1, col=1):
            """Open a file in the editor and navigate cursor to (line, col)."""
            editor = self.editor
            if editor is None:
                return False
            if self._mode is WorkspaceMode.CODE and not self._fullscreen:
                self._showing = "files"
                self._relayout()
            if hasattr(editor, "open_file_at"):
                return editor.open_file_at(path, line, col)
            return editor.open_file(path)

        def show_chat(self):
            self._showing = "chat"
            self._relayout()

        def refresh_explorer(self, changed_paths=None):
            exp = self.explorer
            if exp:
                try:
                    exp.refresh_tree()
                except Exception:
                    pass
            ed = self.editor
            if ed:
                for p in (changed_paths or []):
                    try:
                        ed.reload_if_open(p)
                    except Exception:
                        pass

        def apply_custom_layout(self, layout_cfg=None):
            """CAT Customization: apply positional, sizing, ordering, and visibility layout."""
            try:
                from .. import customization as _cust
                active = _cust.is_active()
            except Exception:
                active = False

            try:
                main = self.query_one("#cct-workspace-main", Vertical)
                body = self.query_one("#cct-workspace-body", Horizontal)
                explorer = self.explorer
                resizer = self.query_one(ExplorerResizeHandle)
                chat_col = self.chat_column
                right_pane = self.right_pane
                right_resizer = self.query_one(RightPaneResizeHandle)
            except Exception:
                return

            if not active:
                # Customization is disabled or not installed: revert to default core layout
                self.styles.layout = "horizontal"
                body.styles.layout = "horizontal"
                try:
                    self.move_child(explorer, before=main)
                    self.move_child(resizer, before=main)
                except Exception:
                    pass
                try:
                    body.move_child(chat_col, before=right_pane)
                    body.move_child(right_resizer, before=right_pane)
                except Exception:
                    pass
                if self.workspace_root is None:
                    explorer.display = False
                chat_col.display = True
                chat_col.styles.width = "1fr"
                self.sync_resizer()
                self.sync_right_resizer()
                return

            # Active customization layout
            if layout_cfg is None:
                try:
                    layout_cfg = _cust.get_manager().get_layout()
                except Exception:
                    layout_cfg = {}

            sidebar_cfg = layout_cfg.get("sidebar") or layout_cfg.get("file_explorer") or {}
            chat_cfg = layout_cfg.get("chat", {})
            editor_cfg = layout_cfg.get("editor") or layout_cfg.get("code_editor") or {}

            # 1. SIDEBAR POSITION & SIZING & VISIBILITY (Sections 4, 8, 9)
            sb_pos = str(sidebar_cfg.get("position", "left")).lower()
            sb_vis = sidebar_cfg.get("visible", True)

            # Sizing (Section 8)
            sb_w = sidebar_cfg.get("width")
            if sb_w is not None:
                try:
                    if isinstance(sb_w, (int, float)):
                        explorer.set_width(int(sb_w))
                    elif isinstance(sb_w, str) and sb_w.endswith("%"):
                        pct = float(sb_w[:-1].strip())
                        total_w = max(40, self.size.width or 100)
                        explorer.set_width(max(14, int(total_w * pct / 100)))
                    elif isinstance(sb_w, str) and sb_w.isdigit():
                        explorer.set_width(int(sb_w))
                except Exception:
                    pass

            sb_order = sidebar_cfg.get("order", 0)
            chat_order = chat_cfg.get("order", 1)
            editor_order = editor_cfg.get("order", 2)

            # Position sidebar: left, right, top, bottom
            if sb_pos == "right" or (sb_order > chat_order and sb_order > editor_order and sb_pos != "left"):
                self.styles.layout = "horizontal"
                try:
                    self.move_child(main, before=resizer)
                    self.move_child(main, before=explorer)
                except Exception:
                    pass
            elif sb_pos == "top":
                self.styles.layout = "vertical"
                try:
                    self.move_child(explorer, before=main)
                    self.move_child(resizer, before=main)
                except Exception:
                    pass
            elif sb_pos == "bottom":
                self.styles.layout = "vertical"
                try:
                    self.move_child(main, before=resizer)
                    self.move_child(main, before=explorer)
                except Exception:
                    pass
            else:  # left (default)
                self.styles.layout = "horizontal"
                try:
                    self.move_child(explorer, before=main)
                    self.move_child(resizer, before=main)
                except Exception:
                    pass

            # Visibility: releases space if hidden
            if not sb_vis:
                explorer.display = False
                resizer.display = False
            else:
                explorer.display = True
                self.sync_resizer()

            # 2. CHAT & CODE EDITOR POSITIONS & SIZING & VISIBILITY (Sections 5, 6, 7, 8, 9, 10)
            chat_pos = str(chat_cfg.get("position", "center")).lower()
            editor_pos = str(editor_cfg.get("position", "right")).lower()
            chat_vis = chat_cfg.get("visible", True)
            editor_vis = editor_cfg.get("visible", True)

            # Sizes
            chat_w = chat_cfg.get("width")
            if chat_w is not None and str(chat_w).lower() not in ("auto", "1fr", "remaining"):
                try:
                    if isinstance(chat_w, str) and chat_w.endswith("%"):
                        chat_col.styles.width = chat_w
                    else:
                        chat_col.styles.width = int(chat_w)
                except Exception:
                    chat_col.styles.width = "1fr"
            else:
                chat_col.styles.width = "1fr"

            editor_w = editor_cfg.get("width")
            if editor_w is not None and str(editor_w).lower() not in ("auto", "1fr", "remaining"):
                try:
                    if isinstance(editor_w, str) and editor_w.endswith("%"):
                        right_pane.styles.width = editor_w
                    else:
                        right_pane.styles.width = int(editor_w)
                except Exception:
                    pass

            # Ordering / Position swap between Chat and Editor:
            if (chat_pos == "right" and editor_pos in ("left", "center")) or (editor_pos == "left" and chat_pos != "left") or (editor_order < chat_order and chat_pos != "left"):
                body.styles.layout = "horizontal"
                try:
                    body.move_child(right_pane, before=chat_col)
                    body.move_child(right_resizer, before=chat_col)
                except Exception:
                    pass
            elif chat_pos == "top" and editor_pos == "bottom":
                body.styles.layout = "vertical"
                try:
                    body.move_child(chat_col, before=right_pane)
                    body.move_child(right_resizer, before=right_pane)
                except Exception:
                    pass
            elif chat_pos == "bottom" and editor_pos == "top":
                body.styles.layout = "vertical"
                try:
                    body.move_child(right_pane, before=chat_col)
                    body.move_child(right_resizer, before=chat_col)
                except Exception:
                    pass
            else:  # Chat on left / center, editor on right
                body.styles.layout = "horizontal"
                try:
                    body.move_child(chat_col, before=right_pane)
                    body.move_child(right_resizer, before=right_pane)
                except Exception:
                    pass

            # Visibility: releases space if hidden
            chat_col.display = bool(chat_vis)
            has_preview = getattr(self, "_mode", None) in (WorkspaceMode.PREVIEW, WorkspaceMode.SPLIT)
            has_files = getattr(self, "_files_count", 0) > 0 or (self.editor is not None and bool(getattr(self.editor, "_open_paths", {})))
            if not editor_vis or (not has_files and not has_preview):
                right_pane.display = False
                right_resizer.display = False
            else:
                right_pane.display = True
                self.sync_right_resizer()

            self.sync_resizer()
            self.sync_right_resizer()
            self._sync_sidebar_toggle()

else:
    WorkspaceShell = None
