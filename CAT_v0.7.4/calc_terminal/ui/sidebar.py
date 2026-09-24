"""
CAT UI — sidebar.py (spec v0.7 project structure + Sidebar section).

Explorer: Open Folder, the opened folder's file tree, Pinned/Recent
Projects, and a drag & drop hint area.

v0.7.9.0: the Explorer is a LIVE VIEW of the real filesystem — the
fs watcher (calc_terminal/fs_watcher.py) plus explicit agent tool
events push refresh_tree(changed_paths) the moment anything on disk
changes (create/delete/rename/move/modify), and the divider next to
this panel is a real drag handle (ui/resizers.py).
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os

from .. import projects
from .events import FolderOpened, FileOpenRequested, SidebarToggled

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Vertical, Horizontal, ScrollableContainer
    from textual.widgets import Static, DirectoryTree, Button, Input
    from textual.reactive import reactive
    from textual.screen import Screen
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False

def _safe_glyph(emoji: str, fallback: str) -> str:
    try:
        import sys
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        emoji.encode(enc)
        return emoji
    except Exception:
        return fallback

DEFAULT_WIDTH = 32
COLLAPSED_WIDTH = 0

# File extensions the spec's Drag & Drop section lists — used only to
# pick an icon glyph in the tree; DirectoryTree still shows every file,
# this doesn't filter anything out.
_ICONS = {
    ".py": "\U0001f40d", ".cpp": "\u2699", ".c": "\u2699", ".java": "\u2615",
    ".html": "\U0001f310", ".css": "\U0001f3a8", ".js": "\U0001f4dc",
    ".json": "{}", ".yaml": "\U0001f4c4", ".yml": "\U0001f4c4", ".toml": "\U0001f4c4",
    ".txt": "\U0001f4c4", ".md": "\U0001f4dd", ".pdf": "\U0001f4d5",
    ".docx": "\U0001f4d8", ".pptx": "\U0001f4d1", ".xlsx": "\U0001f4ca", ".csv": "\U0001f4ca",
    ".png": "\U0001f5bc", ".jpg": "\U0001f5bc", ".jpeg": "\U0001f5bc",
    ".gif": "\U0001f5bc", ".svg": "\U0001f5bc",
    ".zip": "\U0001f5c3", ".7z": "\U0001f5c3",
    ".xyz": "\u269b", ".pdb": "\u269b", ".mol": "\u269b", ".cif": "\u269b",
}


def icon_for(path):
    return _ICONS.get(os.path.splitext(path)[1].lower(), "\U0001f4c4")


if TEXTUAL_AVAILABLE:

    class _ProjectRow(Horizontal):
        """One clickable line in Pinned/Recent Projects — opens that
        folder on click. When `on_delete` is given (Recent Projects
        only), a small ✕ is appended to the right of the row; clicking
        it removes just that entry from the history and re-renders the
        block. Without a delete handler this renders exactly as the
        old single-Static row did (same text, same classes, same
        hover/click behaviour) — the standalone Recent Workspaces
        picker screens keep using that form."""

        def __init__(self, path, widget_id=None, on_delete=None, prefix="\U0001f4c1"):
            label = os.path.basename(path.rstrip(os.sep)) or path
            self.path = path
            self._on_delete = on_delete
            self._label = Static(f"  {prefix} {label}", id=widget_id,
                                 classes="cct-sidebar-project")
            super().__init__(classes="cct-sidebar-project-row")
            self.tooltip = path

        def compose(self):
            yield self._label
            if self._on_delete is not None:
                yield Static("\u2715", classes="cct-sidebar-project-del")

        def on_mount(self):
            if self._on_delete is not None:
                self._label.styles.width = "auto"

        def on_click(self, event):
            if event.widget and "del" in getattr(event.widget, "classes", set()):
                return
            self.post_message(FolderOpened(self.path))

    class _ConfirmClearRecent(Screen):
        """Confirmation dialog for the 'Clear Recent Projects' minor
        feature. Same real-Screen-push pattern as _AttachPrompt/
        _PathPrompt (ui/app.py) and PermissionModeMenu (ui/header.py) —
        this package never uses floating popup windows, only a
        centered/anchored Screen push, which behaves like a modal
        (blocks input to everything beneath it) without being one."""

        CSS = """
        _ConfirmClearRecent { align: center middle; background: $app-background 60%; }
        #cct-clearrecent-box {
            width: 56; height: auto; background: $surface;
            border: tall $border-active $border; padding: 1 2;
        }
        #cct-clearrecent-title { text-style: bold; padding-bottom: 1; }
        #cct-clearrecent-msg { color: $text-muted; padding-bottom: 1; }
        #cct-clearrecent-btns { height: 3; align-horizontal: right; }
        #cct-clearrecent-btns Button { margin-left: 1; border: tall $border-active $border; }
        """

        def compose(self):
            with Vertical(id="cct-clearrecent-box"):
                yield Static("Clear Recent Workspaces?", id="cct-clearrecent-title")
                yield Static(
                    "This will remove all recent project entries from the history.\n"
                    "Your project folders and files will NOT be deleted.",
                    id="cct-clearrecent-msg")
                with Horizontal(id="cct-clearrecent-btns"):
                    yield Button("Cancel", id="cct-clearrecent-cancel")
                    yield Button("Clear", id="cct-clearrecent-clear", variant="error")

        def on_button_pressed(self, event):
            self.dismiss(event.button.id == "cct-clearrecent-clear")

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(False)

    class _ClearRecentRow(Static):
        """'Clear Recent Projects' link, shown at the bottom of the
        Recent Projects section only when that list isn't already
        empty. Opens _ConfirmClearRecent; on confirm, clears only the
        recent-projects JSON store (projects.clear_recent()) and asks
        the owning Explorer to redraw the Pinned/Recent block — it
        never touches 'pinned', the currently open folder, or any file
        on disk."""

        def __init__(self, on_cleared):
            super().__init__("  \U0001f5d1 Clear Recent Workspaces",
                              classes="cct-sidebar-clear-recent")
            self._on_cleared = on_cleared

        def on_click(self, event):
            self.app.push_screen(_ConfirmClearRecent(), self._handle_result)

        def _handle_result(self, confirmed):
            if not confirmed:
                return
            projects.clear_recent()
            self._on_cleared()

    class _RecentWsRow(Horizontal):
        """One workspace row in the Recent Workspaces picker
        (v0.7.8.1 redesign): a clickable name label, a 📌 pin toggle and
        a ✕ remove button. Pinned workspaces sort first and show a
        filled pin; clicking the label picks the folder."""

        def __init__(self, path, pinned=False, selected=False, on_click=None,
                     on_toggle_pin=None, on_remove=None, search_hit=False):
            super().__init__(classes="cct-rws-row" + (" cct-rws-row-sel" if selected else ""))
            self.path = path
            self._pinned = pinned
            self._on_click = on_click
            self._on_toggle_pin = on_toggle_pin
            self._on_remove = on_remove
            label = os.path.basename(path.rstrip(os.sep)) or path
            pin_mark = "\U0001f4cc " if pinned else "  "
            self._label = Static(f"{pin_mark}[b]{label}[/]", classes="cct-rws-label")
            self._label.tooltip = path
            self._search_hit = search_hit

        def compose(self):
            yield self._label
            yield Static(self.path, classes="cct-rws-path")
            pin_classes = "cct-rws-pin" + (" cct-rws-pinned" if self._pinned else "")
            yield Static("\U0001f4cc", classes=pin_classes)
            yield Static("\u2715", classes="cct-rws-del")

        def set_selected(self, selected):
            self.set_class(selected, "cct-rws-row-sel")

        def on_click(self, event):
            w_classes = getattr(event.widget, "classes", set())
            if "cct-rws-pin" in w_classes:
                event.stop()
                if self._on_toggle_pin:
                    self._on_toggle_pin(self.path)
                return
            if "cct-rws-del" in w_classes:
                event.stop()
                if self._on_remove:
                    self._on_remove(self.path)
                return
            if self._on_click:
                self._on_click(self.path)

    class RecentWorkspacesScreen(Screen):
        """Standalone "Recent Workspaces" picker (v0.7.8.1 redesign —
        the primary workspace-management surface). Reachable from the
        header's menu even before any folder is open. Supports:

          - live search (filters by name or path)
          - pin / unpin (pinned sort first and stick)
          - remove a single entry
          - clear the whole history (confirm dialog)
          - up/down + Enter keyboard navigation
          - Esc closes, opening a row dismisses with that path

        Selecting a row dismisses with that path; CCTApp opens it the
        same way FolderOpened already does."""

        CSS = """
        RecentWorkspacesScreen { align: center middle; background: $app-background 60%; }
        #cct-recentws-box {
            width: 84; height: auto; max-height: 88%;
            background: $surface; border: tall $border-active $border;
            padding: 0 0 1 0;
            opacity: 0; offset-y: 1;
            transition: opacity 120ms, offset 150ms;
        }
        #cct-recentws-box.open { opacity: 1; offset-y: 0; }
        #cct-recentws-titlebar {
            height: 3; padding: 1 2 0 2;
            border-bottom: solid $border;
        }
        #cct-recentws-title { text-style: bold; width: 1fr; }
        #cct-recentws-close {
            width: 3; min-width: 3; height: 1;
            color: $text-faint; content-align: center middle;
        }
        #cct-recentws-close:hover { color: $error; }
        #cct-recentws-search { margin: 1 2 0 2; }
        #cct-recentws-count { color: $text-faint; height: 1; padding: 0 2; margin-top: 1; }
        #cct-recentws-list {
            height: auto; max-height: 12; min-height: 2; overflow-y: auto;
            margin: 0 1; padding: 0 1; scrollbar-gutter: stable;
            scrollbar-size: 1 1; scrollbar-color: $border $surface;
        }
        #cct-recentws-empty { color: $text-faint; padding: 2 1; }
        .cct-rws-row {
            height: 1; min-height: 1; max-height: 1;
            border-left: thick transparent;
            padding: 0 1; align-vertical: middle;
            transition: background 80ms, color 80ms;
        }
        .cct-rws-row:hover { background: $surface-alt; color: $text; }
        .cct-rws-row:hover .cct-rws-label { color: $accent; }
        .cct-rws-row:hover .cct-rws-path { color: $text; }
        .cct-rws-row-sel {
            background: $accent 18%;
            border-left: thick $accent;
            text-style: bold;
        }
        .cct-rws-row-sel .cct-rws-label { color: $accent; text-style: bold; }
        .cct-rws-row-sel .cct-rws-path { color: $text; }
        .cct-rws-label {
            width: 24; min-width: 20; max-width: 26;
            text-wrap: nowrap; text-overflow: ellipsis; overflow-x: hidden;
            height: 1; padding: 0 1 0 0; color: $text;
        }
        .cct-rws-path {
            width: 1fr; color: $text-faint;
            text-wrap: nowrap; text-overflow: ellipsis; overflow-x: hidden;
            height: 1; padding: 0 1;
        }
        .cct-rws-pin {
            width: 3; min-width: 3; height: 1;
            color: $text-faint; content-align: center middle;
        }
        .cct-rws-pin:hover { color: $accent; }
        .cct-rws-pinned { color: $warning; }
        .cct-rws-del {
            width: 3; min-width: 3; height: 1;
            color: $text-faint; content-align: center middle;
        }
        .cct-rws-del:hover { color: $error; }
        #cct-recentws-btns {
            height: 4; padding: 0 2;
            margin-top: 1;
            border-top: solid $border;
            align-horizontal: right;
            align-vertical: middle;
        }
        #cct-recentws-btns Button {
            margin-left: 1;
            min-width: 14;
            height: 3;
            border: tall $border-active $border;
        }
        .cct-btn-spacer { width: 1fr; }
        #cct-recentws-hint { color: $text-faint; height: 1; margin-top: 1; padding: 0 2; text-align: center; }
        """

        BINDINGS = [
            Binding("escape", "cancel", "Cancel"),
            Binding("down", "move_down_sel", "Next"),
            Binding("up", "move_up_sel", "Previous"),
        ]

        def __init__(self):
            super().__init__()
            self._entries = []   # list of workspace dicts from projects.workspaces()
            self._selected = 0

        def compose(self):
            with Vertical(id="cct-recentws-box"):
                with Horizontal(id="cct-recentws-titlebar"):
                    yield Static("\U0001f553  Recent Workspaces", id="cct-recentws-title")
                    yield Static("\u2715", id="cct-recentws-close")
                yield Input(placeholder="Search workspaces\u2026", id="cct-recentws-search")
                yield Static("", id="cct-recentws-count")
                with ScrollableContainer(id="cct-recentws-list"):
                    self._render_rows()
                with Horizontal(id="cct-recentws-btns"):
                    yield Button("\U0001f5d1  Clear Recent", id="cct-recentws-clear")
                    yield Static("", classes="cct-btn-spacer")
                    yield Button("Cancel", id="cct-recentws-cancel")
                    yield Button("  Open  ", id="cct-recentws-open", variant="primary")
                yield Static("Enter to open  \u00b7  Up/Down to select  \u00b7  Esc to close",
                             id="cct-recentws-hint")

        # --------------------------------------------------------- state --
        def _refresh(self):
            self._render_rows()
            self._update_count()

        def _render_rows(self):
            try:
                scroll = self.query_one("#cct-recentws-list", ScrollableContainer)
            except Exception:
                return
            query = ""
            try:
                query = self.query_one("#cct-recentws-search", Input).value.strip().lower()
            except Exception:
                pass
            scroll.remove_children()
            all_ws = projects.search(query)
            # v0.7.8.1: pinned workspaces always sort first.
            self._entries = sorted(all_ws, key=lambda w: (not w["pinned"], -w.get("opened_at", 0)))
            if not self._entries:
                scroll.mount(Static(
                    "No recent workspaces yet \u2014 open a folder to start.",
                    id="cct-recentws-empty"))
                self._selected = 0
                return
            self._selected = min(self._selected, len(self._entries) - 1)
            for i, w in enumerate(self._entries):
                row = _RecentWsRow(
                    w["path"], pinned=bool(w.get("pinned")), selected=(i == self._selected),
                    on_click=self._pick, on_toggle_pin=self._toggle_pin, on_remove=self._remove)
                scroll.mount(row)

        def _update_count(self):
            try:
                n = len(self._entries)
                pinned_n = sum(1 for w in self._entries if w.get("pinned"))
                parts = [f"{n} workspace{'s' if n != 1 else ''}"]
                if pinned_n:
                    parts.append(f"{pinned_n} pinned")
                self.query_one("#cct-recentws-count", Static).update(
                    "  \u00b7  ".join(parts))
            except Exception:
                pass

        # ------------------------------------------------------ actions --
        def _pick(self, path):
            self.dismiss(path)

        def _toggle_pin(self, path):
            projects.toggle_pin(path)
            self._refresh()

        def _remove(self, path):
            projects.remove_recent(path)
            self._refresh()

        def _clear(self):
            def _on_confirmed(confirmed):
                if confirmed:
                    projects.clear_recent()
                    self._refresh()
            self.app.push_screen(_ConfirmClearRecent(), _on_confirmed)

        # --------------------------------------------------------- events --
        def on_mount(self):
            self.call_after_refresh(lambda: self.query_one("#cct-recentws-box").add_class("open"))
            self.call_after_refresh(self._refresh)
            try:
                self.query_one("#cct-recentws-search", Input).focus()
            except Exception:
                pass

        def on_input_changed(self, event):
            if event.input.id == "cct-recentws-search":
                self._selected = 0
                self._refresh()

        def on_button_pressed(self, event):
            eid = event.button.id
            if eid in ("cct-recentws-cancel", "cct-recentws-close"):
                self.dismiss(None)
            elif eid == "cct-recentws-clear":
                self._clear()
            elif eid == "cct-recentws-open":
                if self._entries:
                    self._pick(self._entries[self._selected]["path"])

        def action_cancel(self):
            self.dismiss(None)

        def action_move_down_sel(self):
            if self._entries:
                self._selected = min(self._selected + 1, len(self._entries) - 1)
                self._refresh()

        def action_move_up_sel(self):
            if self._entries:
                self._selected = max(self._selected - 1, 0)
                self._refresh()

        def on_key(self, event):
            if event.key == "enter" and self._entries and self.app.screen is self:
                self._pick(self._entries[self._selected]["path"])

        def on_click(self, event):
            if getattr(event.widget, "id", None) == "cct-recentws-close":
                self.dismiss(None)
                return
            if getattr(event, "widget", None) in (self, None):
                self.dismiss(None)

    class OpenWorkspaceScreen(Screen):
        """Modern compact workspace picker dialog.

        Replaces the old _PathPrompt with a VS Code/Cursor-inspired
        dialog. Supports manual path entry, native folder browsing
        (tkinter), recent workspaces, path validation, and keyboard
        shortcuts. Compact ~68-col layout with smooth animations."""

        CSS = """
        OpenWorkspaceScreen { align: center middle; background: $app-background 70%; }
        #ows-box {
            width: 70; height: auto; max-height: 36;
            background: $surface; border: tall $border-active $border; padding: 0;
            opacity: 0; offset-y: 1;
            transition: opacity 150ms, offset 180ms;
        }
        #ows-box.open { opacity: 1; offset-y: 0; }
        #ows-titlebar {
            height: 3; padding: 1 2 0 2;
            border-bottom: solid $border; margin-bottom: 0;
        }
        #ows-title { text-style: bold; width: 1fr; }
        #ows-close-btn {
            width: 3; min-width: 3;
            content-align: center middle;
            color: $text-faint;
            transition: color 80ms;
        }
        #ows-close-btn:hover { color: $error; }
        #ows-body { padding: 1 2 1 2; }
        #ows-path-label { color: $text-faint; padding-bottom: 0; height: 1; }
        #ows-path-input { margin: 0 0 0 0; }
        #ows-hint { height: 1; padding: 0 0 1 0; }
        #ows-hint.ows-error { color: $error; }
        #ows-hint.ows-success { color: $success; }
        #ows-button-row { height: 3; align: center middle; margin-top: 0; }
        #ows-button-row Button { margin: 0 1; }
        #ows-recent-header {
            color: $text-faint; padding-top: 1; padding-bottom: 0;
            border-top: solid $border; margin-top: 1;
        }
        #ows-recent-body { height: auto; max-height: 10; overflow-y: auto; }
        .ows-recent-row {
            height: 1; color: $text-muted; padding: 0 1;
            border-left: solid transparent;
            transition: background 80ms, color 80ms;
        }
        .ows-recent-row:hover { color: $text; border-left: solid $border-active; }
        #ows-dropzone {
            height: 3; margin-top: 1;
            border: dashed $border; color: $text-faint;
            content-align: center middle;
        }
        """

        BINDINGS = [
            Binding("escape", "cancel", "Cancel"),
            Binding("ctrl+v", "paste_path", "Paste"),
            Binding("ctrl+l", "focus_path", "Focus path"),
            Binding("ctrl+o", "browse", "Browse"),
        ]

        def __init__(self):
            super().__init__()
            self._valid_path = None

        def compose(self):
            with Vertical(id="ows-box"):
                with Horizontal(id="ows-titlebar"):
                    yield Static("\U0001f4c2  Open Workspace", id="ows-title")
                    yield Button("\u2715", id="ows-close-btn", classes="cct-ctrl")
                with Vertical(id="ows-body"):
                    yield Static("Workspace Folder", id="ows-path-label")
                    yield Input(placeholder="C:\\Users\\...  or  /home/user/project", id="ows-path-input")
                    yield Static("", id="ows-hint")
                    with Horizontal(id="ows-button-row"):
                        yield Button("Browse...", id="ows-browse-btn")
                        yield Button("  Open  ", id="ows-open-btn", variant="primary")
                        yield Button("Cancel", id="ows-cancel-btn")
                    yield Static("Recent Workspaces", id="ows-recent-header")
                    with Vertical(id="ows-recent-body"):
                        rows = projects.recent()
                        if not rows:
                            yield Static("  No recent workspaces yet.", classes="ows-hint", id="ows-recent-empty")
                        else:
                            for p in rows[:10]:
                                yield _ProjectRow(p)
                    yield Static("\U0001f4c1  Drop folder here", id="ows-dropzone")

        def on_mount(self):
            self.call_after_refresh(
                lambda: self.query_one("#ows-box").add_class("open"))
            self.query_one("#ows-path-input", Input).focus()

        def on_input_submitted(self, event):
            if event.input.id == "ows-path-input":
                self._do_open()

        def on_button_pressed(self, event):
            eid = event.button.id
            if eid == "ows-browse-btn":
                self._do_browse()
            elif eid == "ows-open-btn":
                self._do_open()
            elif eid in ("ows-cancel-btn", "ows-close-btn"):
                self.dismiss(None)

        def on_input_changed(self, event):
            if event.input.id == "ows-path-input":
                self._validate()

        def on_folder_opened(self, event):
            """Intercept _ProjectRow's FolderOpened events and dismiss."""
            event.stop()
            path = os.path.abspath(os.path.expanduser(event.path))
            if os.path.isdir(path):
                self.dismiss(path)

        def on_click(self, event):
            # ✕ in titlebar may emit click on inner label, not the Button itself — walk parents
            w = getattr(event, "widget", None)
            cur = w
            while cur is not None:
                if getattr(cur, "id", None) == "ows-close-btn":
                    self.dismiss(None)
                    return
                cur = getattr(cur, "parent", None)
            if w in (self, None):
                self.dismiss(None)

        def action_cancel(self):
            self.dismiss(None)

        def action_paste_path(self):
            clipped = self._get_clipboard()
            if clipped:
                inp = self.query_one("#ows-path-input", Input)
                inp.value = clipped
                self._validate()

        def action_focus_path(self):
            self.query_one("#ows-path-input", Input).focus()

        def action_browse(self):
            self._do_browse()

        def _get_clipboard(self):
            try:
                import tkinter as tk
                root = tk.Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                try:
                    return root.clipboard_get()
                except tk.TclError:
                    return ""
                finally:
                    root.destroy()
            except Exception:
                return ""

        def _do_browse(self):
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            try:
                folder = filedialog.askdirectory(title="Select Workspace Folder")
            finally:
                root.destroy()
            if folder:
                inp = self.query_one("#ows-path-input", Input)
                inp.value = folder
                self._validate()

        def _validate(self):
            hint = self.query_one("#ows-hint", Static)
            raw = self.query_one("#ows-path-input", Input).value.strip()
            if not raw:
                hint.update("")
                self._valid_path = None
                return
            expanded = os.path.abspath(os.path.expanduser(raw))
            if not os.path.exists(expanded):
                hint.update("\u26a0 Path does not exist")
                self._valid_path = None
                return
            if not os.path.isdir(expanded):
                hint.update("\u26a0 Not a directory")
                self._valid_path = None
                return
            if not os.access(expanded, os.R_OK):
                hint.update("\u26a0 No read permission")
                self._valid_path = None
                return
            name = os.path.basename(expanded) or expanded
            hint.update(f"\u2713  {name}  \u2014  folder is valid")
            self._valid_path = expanded

        def _do_open(self):
            self._validate()
            if self._valid_path:
                self.dismiss(self._valid_path)
            else:
                hint = self.query_one("#ows-hint", Static)
                hint.update("\u26a0 Please enter a valid folder path")

    class WorkspaceHeader(Vertical):
        """v0.7.7 Project Header (spec section 9): the top strip of the
        Folder Panel, above the file tree, showing the workspace name,
        git branch, indexed languages/files, and session memory/context
        — the facts the footer and permission pill don't already show
        (model/mode/permission stay in their existing single widgets;
        nothing here duplicates them).

        Rendered by CCTApp: `set_workspace(path)` for the identity row,
        `set_context(ctx)` with the workspace_index result for the
        detail row. Textual markup only — no nested widgets beyond the
        two Static lines.

        Deliberately class-only (no fixed widget ids) — the Explorer
        re-creates this widget whenever a folder opens, and Textual's
        remove() lands through the message pump (not instantly), so a
        fixed id would collide with the previous instance's pending
        removal (the exact DuplicateIds race documented in
        Explorer._render_projects). Classes tolerate the brief overlap.
        """

        def __init__(self):
            super().__init__(classes="cct-workspace-header")
            self._path = None
            self._ctx = None

        def compose(self):
            yield Static("\U0001f4c2 No workspace open", classes="cct-wshead-name")
            yield Static("", classes="cct-wshead-detail")

        def set_workspace(self, path):
            self._path = path
            self._rerender()

        def set_context(self, ctx):
            self._ctx = ctx
            self._rerender()

        def _rerender(self):
            try:
                if self._path:
                    name = os.path.basename(self._path.rstrip(os.sep)) or self._path
                    branch = None
                    if self._ctx:
                        branch = (self._ctx.get("git") or {}).get("branch")
                    suffix = f" \u00b7 \U0001f33f {branch}" if branch else ""
                    self.query_one(".cct-wshead-name", Static).update(
                        f"[bold]\U0001f4c1 {name}[/bold]{suffix}")
                else:
                    self.query_one(".cct-wshead-name", Static).update(
                        "\U0001f4c2 No workspace open")
                detail = self._detail_line()
                self.query_one(".cct-wshead-detail", Static).update(detail)
            except Exception:
                pass

        def _detail_line(self):
            if not self._path:
                return "[dim]Open a folder to index it for the AI.[/dim]"
            from .. import workspace_index
            ctx = self._ctx
            if not ctx or not ctx.get("ok"):
                return "[dim]\U0001f504 indexing workspace\u2026[/dim]"
            bits = []
            if ctx["languages"]:
                bits.append(", ".join(ctx["languages"][:3]))
            bits.append(f"{ctx['file_count']} files")
            if ctx["dependencies"]:
                bits.append(f"{len(ctx['dependencies'])} deps")
            if ctx["package_managers"]:
                bits.append("/".join(ctx["package_managers"][:3]))
            line = " \u00b7 ".join(bits)
            try:
                from .. import memory as _mem
                mem = _mem.stats()
                if isinstance(mem, dict) and mem.get("turns") is not None:
                    line += f"  \u00b7  \U0001f4be {mem['turns']} mem"
            except Exception:
                pass
            try:
                from .. import aicore as _ai
                usage = _ai.get_session_usage()
                if isinstance(usage, dict) and usage.get("total_tokens"):
                    window = usage.get("context_window") or 128000
                    pct = int(100 * min(1.0, usage["total_tokens"] / max(1, window)))
                    line += f"  \u00b7  \u2699 ctx {pct}%"
            except Exception:
                pass
            return f"[dim]{line}[/dim]"

    class _CollapsedTreeRow(Static):
        """The multi-workspace 'collapsed' state (spec section 4): when
        a workspace's tree was collapsed, opening it shows this row
        instead of mounting the DirectoryTree. Clicking expands the
        tree in place and clears the collapsed flag."""

        def __init__(self, path, on_expand):
            self._path = path
            self._on_expand = on_expand
            super().__init__("  \u25b8  (tree collapsed \u2014 click to expand)",
                             classes="cct-sidebar-collapsed-row")

        def on_click(self, event):
            if self._on_expand:
                self._on_expand(self._path)

    class Explorer(Vertical):
        """The Explorer sidebar (spec v0.7 Sidebar section). Sections,
        top to bottom: Open Folder button, the open folder's file tree
        (once one is open), Pinned Projects, Recent Projects, and a
        Drag & Drop hint area.

        `width` is a reactive so `set_width()`/collapse can animate via
        CSS transition (see _COMPONENT_CSS's `transition: width`) rather
        than snapping instantly.
        """

        width = reactive(DEFAULT_WIDTH)

        def __init__(self, id="cct-sidebar"):
            super().__init__(id=id)
            self._workspace_root = None
            self._projects_container = None
            self._header = None
            self._tree_mounted = False
            # Gesture tracking for file triple-click / long-press
            self._last_file_click_time = 0
            self._last_file_click_path = None
            self._file_click_count = 0

        def compose(self):
            # Title row carries a dedicated collapse/expand toggle
            # (spec v0.7.4: the File Explorer behaves like a real IDE
            # sidebar — visible chevron, open/close at any time). The
            # chevron flips ▼/▶ with the panel's width state.
            with Horizontal(id="cct-sidebar-titlebar"):
                yield Static("[b]Explorer[/b]", id="cct-sidebar-title")
                yield Button(_safe_glyph("◀", "<"), id="cct-sidebar-collapse-btn",
                             classes="cct-sidebar-collapse-btn", tooltip="Collapse Sidebar (Ctrl+B)")
            yield Button("📁 Open Folder", id="cct-open-folder-btn", classes="cct-sidebar-open-btn")
            with ScrollableContainer(id="cct-sidebar-body"):
                yield Static("No folder open.", id="cct-sidebar-empty")

        def on_mount(self):
            self._render_projects()

        def _show_explorer_menu(self):
            items = [
                ("open_folder", "📁  Open Folder..."),
                ("refresh", "🔄  Refresh Explorer"),
                ("collapse_all", "📂  Collapse Folders"),
            ]
            if self._workspace_root:
                items.append(("close_workspace", "✕  Close Workspace"))
            try:
                from .context_menu import MessageContextMenu
                def on_dismiss(action):
                    if action == "open_folder":
                        self.post_message(FileOpenRequested("__open_folder_prompt__"))
                    elif action == "refresh":
                        self.refresh_tree()
                        self._render_projects()
                    elif action == "collapse_all":
                        if self._tree_mounted and hasattr(self, "_tree") and self._tree:
                            try:
                                self._tree.root.collapse_all()
                            except Exception:
                                pass
                    elif action == "close_workspace":
                        try:
                            self.close_workspace()
                        except Exception:
                            pass

                menu = MessageContextMenu(items, origin=(2, 4))
                self.app.push_screen(menu, callback=on_dismiss)
            except Exception:
                self.refresh_tree()
                self._render_projects()

        def close_workspace(self):
            """Closes the current open workspace folder and restores
            the sidebar to its default empty state with recent projects."""
            self._workspace_root = None
            self._tree_mounted = False
            old = self._header
            self._header = None
            if old is not None:
                try:
                    old.remove()
                except Exception:
                    pass
            try:
                body = self.query_one("#cct-sidebar-body", ScrollableContainer)
                for child in list(body.children):
                    child.remove()
                body.mount(Static("No folder open.", id="cct-sidebar-empty"))
                self._render_projects(body)
            except Exception:
                pass
            try:
                shell = self.app.query_one("#cct-workspace")
                if shell:
                    shell.workspace_root = None
                    shell.sync_resizer()
                    shell._relayout()
            except Exception:
                pass
            try:
                from .. import workspace as ws_paths
                old_ws = getattr(self.app, "_workspace_root", None)
                ws_paths.set_active_project(None)
                if hasattr(self.app, "_handle_workspace_chat_switch"):
                    self.app._handle_workspace_chat_switch(old_ws, None)
                if hasattr(self.app, "_workspace_root"):
                    self.app._workspace_root = None
                if hasattr(self.app, "_current_workspace"):
                    self.app._current_workspace = None
                if hasattr(self.app, "_refresh_header_breadcrumb"):
                    self.app._refresh_header_breadcrumb()
                if hasattr(self.app, "_refresh_header_right"):
                    self.app._refresh_header_right()
            except Exception:
                pass
            try:
                self.post_message(WorkspaceChanged(None))
            except Exception:
                pass

        def on_button_pressed(self, event):
            if event.button.id == "cct-open-folder-btn":
                self.post_message(FileOpenRequested("__open_folder_prompt__"))
            elif event.button.id == "cct-sidebar-collapse-btn":
                event.stop()
                self.toggle()
                self.post_message(SidebarToggled(self.width > 0 and self.display))
            elif event.button.id == "cct-sidebar-menu-btn":
                self._show_explorer_menu()

        # ---------------------------------------------------- workspace --
        def open_folder(self, path):
            """Mounts a real DirectoryTree rooted at `path`, replacing
            whatever the sidebar body currently shows. Also mounts the
            v0.7.7 Project Header (spec section 9) above the tree, and
            honors the workspace's remembered collapse state (spec
            section 4) — a collapsed workspace shows a single expand
            row instead of the tree."""
            path = os.path.abspath(os.path.expanduser(path))
            if not os.path.isdir(path):
                return False
            if path == self._workspace_root and self._tree_mounted:
                return True
            self._workspace_root = path
            projects.record_opened(path)
            try:
                body = self.query_one("#cct-sidebar-body", ScrollableContainer)
            except Exception:
                return True
            for child in list(body.children):
                child.remove()
            self._mount_header(path, body)
            if projects.is_collapsed(path):
                body.mount(_CollapsedTreeRow(path, self._expand_collapsed))
                self._tree_mounted = False
            else:
                body.mount(DirectoryTree(path, classes="cct-filetree"))
                self._tree_mounted = True
            self._render_projects(body)
            return True

        def _mount_header(self, path, body):
            """(Re)creates the Project Header. Same object-reference
            pattern as _render_projects: the old instance's remove()
            is scheduled through the message pump, so the new header is
            class-only (no fixed id) to survive the brief overlap."""
            old = self._header
            self._header = None
            if old is not None:
                try:
                    old.remove()
                except Exception:
                    pass
            header = WorkspaceHeader()
            header.set_workspace(path)
            self._header = header
            body.mount(header)

        def _expand_collapsed(self, path):
            """Clicking the collapsed-tree row: clear the flag, remount
            the real tree in place."""
            projects.set_collapsed(path, False)
            self._tree_mounted = False
            self.open_folder(path)

        def toggle_collapsed(self, path=None):
            """Collapses/expands the current workspace's tree (spec
            section 4's per-workspace collapse). The state is persisted
            in the workspace history store, so re-opening this folder
            later respects it."""
            path = path or self._workspace_root
            if not path:
                return
            body = self.query_one("#cct-sidebar-body", ScrollableContainer)
            if self._tree_mounted:
                projects.set_collapsed(path, True)
                for child in list(body.children):
                    child.remove()
                self._mount_header(path, body)
                body.mount(_CollapsedTreeRow(path, self._expand_collapsed))
                self._tree_mounted = False
                self._render_projects(body)
            else:
                projects.set_collapsed(path, False)
                self._tree_mounted = False
                self.open_folder(path)

        def set_workspace_header(self, ctx):
            """v0.7.7: CCTApp hands the workspace_index result here
            once indexing finishes; the Project Header's detail line
            re-renders with real languages/files/deps/git data."""
            if self._header is not None:
                self._header.set_context(ctx)

        def refresh_tree(self, changed_paths=None):
            """Live-view refresh (v0.7.9.0): keeps the mounted
            DirectoryTree in sync with the real filesystem. Called by
            the fs-watcher bridge, explicit agent-tool notifications,
            and post-turn diffs.

            Uses DirectoryTree.reload(), whose own subtree-reload
            machinery preserves every expanded folder and the
            highlighted node, and — importantly — safely discards any
            in-flight internal directory-load workers before rescanning
            (a bare node-level reload can race them and repaint stale
            contents). `changed_paths` is accepted for API symmetry;
            the Editor pane's open-file reload is handled by
            WorkspaceShell.refresh_explorer. No-op if no folder open."""
            del changed_paths  # editor refresh handled by the shell
            if self._workspace_root is None:
                return
            try:
                body = self.query_one("#cct-sidebar-body", ScrollableContainer)
                trees = body.query(DirectoryTree)
                if trees:
                    trees.first().reload()
            except Exception:
                pass

        @staticmethod
        def _affected_dirs(changed_paths):
            dirs = set()
            for p in changed_paths or []:
                p = os.path.abspath(str(p))
                dirs.add(p)
                parent = os.path.dirname(p)
                if parent:
                    dirs.add(parent)
            return dirs

        @staticmethod
        def _walk_loaded_nodes(tree):
            """Yields every already-loaded TreeNode (depth-first). Only
            loaded children are walked — collapsed branches don't need
            refreshing since their contents are re-read on expand."""
            stack = [tree.root]
            seen = 0
            while stack and seen < 4096:
                node = stack.pop()
                seen += 1
                yield node
                try:
                    stack.extend(node.children)
                except Exception:
                    pass

        def close_folder(self):
            self._workspace_root = None
            self._header = None
            self._tree_mounted = False
            body = self.query_one("#cct-sidebar-body", ScrollableContainer)
            for child in list(body.children):
                child.remove()
            body.mount(Static("No folder open.", id="cct-sidebar-empty"))
            self._render_projects(body)

        def _render_projects(self, body=None):
            """(Re)draws Pinned Projects, Recent Projects, the Clear
            Recent Projects link, and the drag & drop hint, inside a
            dedicated container (class 'cct-sidebar-projects'). Kept
            separate from the folder-name header / DirectoryTree that
            open_folder() mounts directly into `body` (both used to
            share the plain 'cct-sidebar-section' class, which meant
            there was no way to redraw just this block without also
            tearing down whichever folder is currently open) — this is
            what lets Clear Recent Projects call this again in place
            without touching the open project.

            The container is tracked by direct object reference
            (self._projects_container), NOT a fixed widget `id` re-used
            on every redraw. Widget.remove() in Textual is scheduled
            through the message pump, not instant — mounting a new
            widget with the same fixed id immediately after calling
            .remove() on the old one (as this used to do) can race
            that scheduled removal and raise DuplicateIds, which is
            exactly the crash this fixes: open_folder() clears `body`
            (scheduling removal of the previous container along with
            everything else) and then calls this method again in the
            same synchronous call stack, before that removal has
            actually landed."""
            body = body or self.query_one("#cct-sidebar-body", ScrollableContainer)
            old = self._projects_container
            self._projects_container = None
            if old is not None:
                try:
                    old.remove()
                except Exception:
                    # Already gone (e.g. open_folder()/close_folder()
                    # already wiped `body`, including this widget, right
                    # before calling us) — nothing left to clean up.
                    pass
            container = Vertical(classes="cct-sidebar-projects")
            self._projects_container = container
            body.mount(container)
            # v0.7.7 multi-workspace (spec section 4): one strip of every
            # known workspace (pinned + favorite + recent, newest first).
            # Clicking a row switches the Explorer to that folder in
            # place — the Folder Panel never closes when you browse
            # multiple workspaces (spec section 3).
            seen_paths = set()
            workspaces = projects.workspaces()[:6]
            if workspaces:
                container.mount(Static("[b]Workspaces[/b]",
                                       classes="cct-sidebar-project-header"))
                for w in workspaces:
                    p = w["path"]
                    seen_paths.add(os.path.abspath(p))
                    marks = ("\U0001f4cc" if w.get("pinned") else "") \
                            + ("\u2b50" if w.get("favorite") else "")
                    prefix = (marks + " ") if marks else "\U0001f4c2"
                    container.mount(_ProjectRow(
                        p, prefix=prefix,
                        on_delete=lambda path=p: self._remove_workspace(path)))
            pinned = [p for p in projects.pinned() if os.path.abspath(p) not in seen_paths]
            for p in pinned:
                seen_paths.add(os.path.abspath(p))
            recent = [p for p in projects.recent() if os.path.abspath(p) not in seen_paths][:6]
            if pinned:
                container.mount(Static("[b]Pinned Workspaces[/b]", classes="cct-sidebar-project-header"))
                for p in pinned:
                    container.mount(_ProjectRow(p))
            if recent:
                container.mount(Static("[b]Recent Workspaces[/b]", classes="cct-sidebar-project-header"))
                for p in recent:
                    # Per-project delete (v0.7.6 Patch 1): the ✕ on a
                    # recent row removes ONLY that entry from the store,
                    # then this block re-renders itself in place — same
                    # in-place pattern _ClearRecentRow already uses, so
                    # it never touches the open folder or 'pinned'.
                    container.mount(_ProjectRow(
                        p, on_delete=lambda path=p: self._delete_recent(path)))
                container.mount(_ClearRecentRow(self._render_projects))
            if not self._workspace_root:
                container.mount(Static(
                    "[dim]Drag & drop files here, or into Chat/Editor,\n"
                    "to attach them for the AI.[/dim]", classes="cct-sidebar-dropzone"))

        def _remove_workspace(self, path):
            """Removes a workspace from the history strip (✕ on a
            Workspaces row) — history only, never files on disk, and
            never closes the panel."""
            projects.remove(path)
            self._render_projects()

        def _delete_recent(self, path):
            projects.remove_recent(path)
            self._render_projects()

        # ------------------------------------------------------ open tree --
        def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected):
            # Gesture detection: triple-click file → quick actions
            import time as _t
            path = str(event.path)
            now = _t.time()
            if path == self._last_file_click_path and now - self._last_file_click_time < 0.4:
                self._file_click_count += 1
            else:
                self._file_click_count = 1
            self._last_file_click_time = now
            self._last_file_click_path = path
            if self._file_click_count == 3:
                self._file_click_count = 0
                try:
                    from ..gestures.manager import handle_gesture
                    ctx = {"path": path}
                    if handle_gesture("triple_click", "file", app=getattr(self, "app", None), context=ctx):
                        return
                except Exception:
                    pass
                # Fallback quick actions note
                try:
                    self.app._system_note(f"Quick actions for: {path}")
                except Exception:
                    pass
                return
            if self._file_click_count == 2:
                # Double-click file: check for reveal gesture (long_press fallback)
                try:
                    from ..gestures.manager import handle_gesture
                    ctx = {"path": path}
                    # Try long_press as reveal
                    if handle_gesture("long_press", "file", app=getattr(self, "app", None), context=ctx):
                        self._file_click_count = 0
                        return
                except Exception:
                    pass
            self.post_message(FileOpenRequested(path))

        def on_click(self, event):
            """Gesture on file → reveal actions (spec 23): long-press fallback via right-click."""
            try:
                # Right-click (button 3) on a file row triggers reveal gesture
                if getattr(event, "button", 1) == 3:
                    widget = getattr(event, "widget", None)
                    path = getattr(widget, "path", None) or getattr(self, "_last_file_click_path", "")
                    if path:
                        try:
                            from ..gestures.manager import handle_gesture
                            if handle_gesture("long_press", "file", app=getattr(self, "app", None), context={"path": path}):
                                event.stop()
                                return
                        except Exception:
                            pass
                        # Fallback to file context menu
                        origin = getattr(event, "screen_offset", None)
                        origin_xy = (origin.x, origin.y) if origin else (event.x, event.y)
                        self._show_touch_context_menu(path, origin_xy)
            except Exception:
                pass

        def on_touch_long_press(self, widget, screen_pos):
            """Touch long-press on file sidebar opens context actions."""
            path = getattr(widget, "path", None) or getattr(self, "_last_file_click_path", "")
            if not path:
                try:
                    tree = self.query_one(DirectoryTree)
                    if tree.cursor_node and getattr(tree.cursor_node, "data", None):
                        path = str(tree.cursor_node.data.path)
                except Exception:
                    pass
            path = path or self._workspace_root or ""
            if path:
                self._show_touch_context_menu(path, screen_pos)

        def _show_touch_context_menu(self, path, origin):
            try:
                from .context_menu import MessageContextMenu, FILE_MENU_ITEMS
                def _on_result(action):
                    if not action:
                        return
                    self._handle_file_action(action, path)
                self.app.push_screen(MessageContextMenu(FILE_MENU_ITEMS, origin=origin), _on_result)
            except Exception:
                pass

        def _handle_file_action(self, action, path):
            if action == "open":
                if os.path.isfile(path):
                    self.post_message(FileOpenRequested(path))
                elif os.path.isdir(path):
                    self.open_folder(path)
            elif action == "copy_path":
                try:
                    from .. import code_editor
                    code_editor.copy_to_clipboard(path)
                    self.app._system_note(f"Copied: {path}")
                except Exception:
                    pass
            elif action == "delete":
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                        self.refresh_tree()
                        self.app._system_note(f"Deleted: {os.path.basename(path)}")
                except Exception as e:
                    self.app._system_note(f"Delete failed: {e}")
            elif action == "rename":
                self.app._system_note(f"Selected for rename: {os.path.basename(path)}")
            elif action in ("new_file", "new_folder"):
                target_dir = path if os.path.isdir(path) else os.path.dirname(path)
                self.app._system_note(f"Create in: {target_dir}")


        # -------------------------------------------------- collapse/resize --
        def set_width(self, value):
            previous = self.width
            new_width = max(COLLAPSED_WIDTH, value)
            self.width = new_width
            self.styles.width = new_width
            # At 0 width the panel fully disappears without leaving any border or residue
            if new_width == 0:
                self.display = False
                self.set_class(True, "cct-sidebar-collapsed")
            else:
                self.display = True
                self.set_class(False, "cct-sidebar-collapsed")
            # Keep the title-bar chevron honest: ◀ when open (click
            # collapses), ▶ when collapsed (click expands again).
            if self.is_mounted:
                try:
                    btn = self.query_one("#cct-sidebar-collapse-btn", Button)
                    is_open = (self.width > 0 and self.display)
                    btn.label = _safe_glyph("◀", "<") if is_open else _safe_glyph("▶", ">")
                    btn.tooltip = "Collapse Sidebar (Ctrl+B)" if is_open else "Expand Sidebar (Ctrl+B)"
                except Exception:
                    pass
                # Announce visibility flips once, so the shell can keep
                # its resize divider in lockstep (and CCTApp persists
                # the state).
                if (previous > 0) != (self.width > 0 and self.display):
                    self.post_message(SidebarToggled(self.width > 0 and self.display))

        def _tree_mounted_or_root(self):
            return self._workspace_root is not None or self._tree_mounted

        def toggle(self):
            if self.width > 0 and self.display:
                self._restore_width = self.width
                self.set_width(COLLAPSED_WIDTH)
            else:
                self.display = True
                restore_w = getattr(self, "_restore_width", None) or DEFAULT_WIDTH
                self.set_width(max(restore_w, DEFAULT_WIDTH))

        def focus_tree(self):
            """Give the open folder's DirectoryTree keyboard focus after
            the sidebar is reopened (spec v0.7.4: "focus or reopen the
            existing explorer"), so it feels like a focused panel, not a
            static pane. No-op when no folder is open."""
            if self._workspace_root is None:
                return
            try:
                body = self.query_one("#cct-sidebar-body", ScrollableContainer)
                trees = body.query(DirectoryTree)
                if trees:
                    trees.first().focus()
            except Exception:
                pass

else:
    Explorer = None
    RecentWorkspacesScreen = None
    OpenWorkspaceScreen = None
