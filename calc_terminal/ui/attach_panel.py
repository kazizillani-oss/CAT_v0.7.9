"""
CCT UI — AttachPanel (v0.7.8.3 minimal redesign, v0.7.8.45 native Browse).

A small centered picker for the next message. Two views in one screen:

  chooser   📄 Browse · 📁 Folder · 🕘 Recent  (+ Cancel)
  browser   the existing Open Folder-style navigation:
            ← Back · → Forward · ↑ Up · ⌂ Home · 💽 Drives · path,
            folders-first list, type-to-filter, multi-select (Space)

v0.7.8.45: on Windows, "Browse" (label unchanged) opens the operating
system's own file dialog (native_picker.pick_files) — any drive/device,
"All Files (*.*)" plus categories — instead of the in-app browser. The
dialog blocks, so it runs in a worker thread; the result takes the same
dismiss path (a path string or a list of paths) and nothing else in
CCT changes. Folder / Recent keep the in-app browser everywhere; on
non-Windows platforms Browse does too.

No favorites, no search chrome, no metadata panel, no extra toolbars.
When the selected file would be unusable by the active model (e.g. an
image with a text-only model) a one-line honest note appears under the
list — never a fake "Context OK".

Emits results via dismiss() exactly like before:
  - a single path string for Folder mode (the browsed folder)
  - a list of paths for Files / Recent (multi-select)
CCTApp._on_attach_path handles both shapes. Drag & drop is already
covered by the paste-path detection in attachments.paths_from_paste.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os
from types import SimpleNamespace

TEXTUAL_AVAILABLE = True
try:
    from textual.screen import Screen
    from textual.containers import Vertical, Horizontal, ScrollableContainer
    from textual.widgets import Static, Button
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False

if TEXTUAL_AVAILABLE:
    from .attachments import attachment_kind, list_drives, format_size
    from .attachments import _vision_warning
    from .. import attachments as _core
    from . import theme_css

    _OPTIONS = (
        ("files", "\U0001f4c4  Browse"),
        ("folder", "\U0001f4c1  Folder"),
        ("recent", "\U0001f558  Recent"),
    )


    class _FsRow(Static):
        """One row of the browser: icon · name · kind · size, with
        selected and picked states."""

        def __init__(self, index, entry, selected=False, picked=False):
            self.index = index
            self.entry = entry
            super().__init__("", classes="ap-row"
                             + (" ap-row-sel" if selected else "")
                             + (" ap-row-picked" if picked else ""))
            self._redraw()

        def _redraw(self):
            icon, kind = attachment_kind(self.entry["path"])
            if self.entry.get("is_dir"):
                icon = "\U0001f4c1"
                kind = "folder"
            size = format_size(self.entry["path"]) if not self.entry.get("is_dir") else ""
            size_txt = f" \u00b7 {size}" if size else ""
            sel = " \u25b8" if "ap-row-sel" in self.classes else ""
            picked = " \u2713" if "ap-row-picked" in self.classes else ""
            self.update(
                f"  {icon} [{theme_css.current_hex('text')}]{self.entry['name']}[/]"
                f"[{theme_css.current_hex('text-faint')}]\u00b7{kind}{size_txt}[/]"
                f"{picked}{sel}")

        def set_selected(self, selected):
            self.set_class(selected, "ap-row-sel")
            self._redraw()

        def set_picked(self, picked):
            self.set_class(picked, "ap-row-picked")
            self._redraw()


    class AttachPanel(Screen):
        """Attach files or folders to the next message: a compact
        chooser (File / Folder / Recent) that expands into the
        Open Folder-style browser."""

        CSS = """
        AttachPanel { align: center middle; background: $app-background 70%; }
        #ap-box {
            width: 74; height: auto; max-height: 92%;
            background: $surface;
            border-top: tall $surface-highlight;
            border-bottom: tall $surface-dark;
            border-left: tall $surface-highlight;
            border-right: tall $surface-dark;
            padding: 0;
            opacity: 0; offset-y: 1;
            transition: opacity 150ms, offset 180ms;
        }
        #ap-box.ap-chooser { width: 44; }
        #ap-box.open { opacity: 1; offset-y: 0; }
        #ap-titlebar { height: 3; padding: 1 2 0 2; border-bottom: solid $border; }
        #ap-title { text-style: bold; width: 1fr; }
        #ap-options { height: 1; min-height: 1; width: auto; padding: 0;
            background: transparent; border: none; color: $accent;
            margin-right: 1; text-style: bold; }
        #ap-options:hover { background: transparent; color: $accent-secondary; }
        #ap-chooser { height: auto; padding: 1 2 0 2; align-horizontal: center; }
        #ap-chooser Button {
            margin-bottom: 1;
            border-top: tall $surface-highlight;
            border-bottom: tall $surface-dark;
            border-left: tall $surface-highlight;
            border-right: tall $surface-dark;
            background: $surface-alt;
            color: $text;
            text-style: bold;
            transition: background 100ms, offset 80ms;
        }
        #ap-chooser Button:hover {
            border-top: tall #ffffff;
            background: $surface-highlight;
            color: #ffffff;
        }
        #ap-nav { height: 3; padding: 0 2; }
        #ap-nav Button { margin-right: 0; }
        #ap-path { color: $text-muted; padding-left: 1; width: 1fr; overflow: hidden; text-overflow: ellipsis; }
        #ap-drives { height: 3; padding: 0 2; display: none; }
        #ap-drives.on { display: block; }
        #ap-drives Button { margin-right: 1; }
        #ap-browser { height: auto; min-height: 4; padding: 0 1; overflow-y: auto; scrollbar-gutter: stable; }
        .ap-row { height: 1; color: $text-muted; padding: 0 1; border-left: thick transparent; }
        .ap-row-sel { background: transparent; color: $text; border-left: thick $accent; text-style: bold; }
        .ap-row-picked { text-style: bold; }
        .ap-empty { color: $text-faint; padding: 1 1; }
        #ap-cap { color: $text-faint; height: 1; padding: 0 2; overflow: hidden; text-overflow: ellipsis; }
        #ap-actions { height: 5; padding: 0 2 1 2; border-top: solid $border; }
        #ap-actions Button {
            margin-right: 1;
            border-top: tall $surface-highlight;
            border-bottom: tall $surface-dark;
            border-left: tall $surface-highlight;
            border-right: tall $surface-dark;
            background: $surface-alt;
            color: $text;
            text-style: bold;
            transition: background 100ms, offset 80ms;
        }
        #ap-actions Button.cct-btn-primary {
            background: $accent 30%;
            color: #ffffff;
            border-top: tall $accent-highlight;
            border-bottom: tall $surface-dark;
            border-left: tall $accent;
            border-right: tall $accent-shadow;
            text-style: bold;
        }
        #ap-actions Button:hover {
            border-top: tall #ffffff;
            background: $surface-highlight;
            color: #ffffff;
        }
        #ap-actions Button.cct-btn-primary:hover {
            border-top: tall #ffffff;
            background: $accent 50%;
            color: #ffffff;
        }
        #ap-actions Button.-active { offset-y: 1; }
        #ap-box.cct-compact #ap-browser { min-height: 1; }
        #ap-box.cct-compact.ap-chooser #ap-chooser { padding-top: 0; }
        #ap-box.cct-compact.ap-chooser #ap-chooser Button { margin-bottom: 0; }
        #ap-box.cct-compact.ap-chooser #ap-titlebar { border-bottom: none; }
        """

        BINDINGS = [
            Binding("escape", "cancel", "Cancel"),
            Binding("down", "move_down_sel", "Next row"),
            Binding("up", "move_up_sel", "Previous row"),
            Binding("enter", "attach", "Attach"),
            Binding("space", "toggle_pick", "Pick/unpick"),
            Binding("backspace", "backspace_key", "Back"),
            Binding("left", "nav_back", "Back"),
            Binding("right", "nav_forward", "Forward"),
        ]

        def __init__(self, recents=None):
            super().__init__()
            self._view = "pick"
            self._mode = "files"
            self._recents = [p for p in (recents or []) if os.path.lexists(p)][:20]
            self._selected = 0
            self._picked = []
            self._query = ""
            self._cwd = os.path.expanduser("~")
            self._history = []
            self._fwd = []
            self._drives_on = False
            self._entries = []

        # ------------------------------------------------------------ UI
        def compose(self):
            with Vertical(id="ap-box"):
                with Horizontal(id="ap-titlebar"):
                    yield Static("\U0001f4ce  Attach to Message", id="ap-title")
                    yield Button("\u2190 Options", id="ap-options", classes="cct-btn cct-btn-sm")
                    yield Button("\u2715", id="ap-close", classes="cct-popup-close")
                with Vertical(id="ap-chooser"):
                    for key, label in _OPTIONS:
                        yield Button(label, id=f"ap-opt-{key}", classes="cct-btn")
                with Horizontal(id="ap-nav"):
                    yield Button("\u2190", id="ap-back", classes="cct-btn cct-btn-sm")
                    yield Button("\u2192", id="ap-fwd", classes="cct-btn cct-btn-sm")
                    yield Button("\u2191 Up", id="ap-up", classes="cct-btn cct-btn-sm")
                    yield Button("\u2302 Home", id="ap-home", classes="cct-btn cct-btn-sm")
                    yield Button("\U0001f4bd Drives", id="ap-drives-btn", classes="cct-btn cct-btn-sm")
                    yield Static("", id="ap-path")
                yield Horizontal(id="ap-drives")
                yield ScrollableContainer(id="ap-browser")
                yield Static("", id="ap-cap")
                with Horizontal(id="ap-actions"):
                    yield Button("Attach", id="ap-attach", classes="cct-btn cct-btn-primary")
                    yield Button("Cancel", id="ap-cancel", classes="cct-btn")

        # ----------------------------------------------------------- state
        def _show_chooser(self):
            self._view = "pick"
            self._query = ""
            self._picked = []
            self._selected = 0
            self._drives_on = False
            self._refresh_chrome()
            self._refresh_list()

        def _enter_mode(self, mode):
            self._mode = mode
            self._view = "browse"
            self._query = ""
            self._picked = []
            self._selected = 0
            if mode == "recent":
                self._refresh_list()
            else:
                self._load_dir(self._cwd)

        def _load_dir(self, path):
            path = os.path.normpath(path)
            if self._mode == "folder" and not os.path.isdir(path):
                path = os.path.dirname(path)
            if not self._history or self._history[-1] != self._cwd:
                self._history.append(self._cwd)
            self._cwd = path
            self._fwd = []
            self._selected = 0
            self._entries = self._list_entries(path)
            self._refresh_list()

        def _list_entries(self, path):
            out = []
            try:
                with os.scandir(path) as it:
                    for e in it:
                        try:
                            is_dir = e.is_dir()
                        except OSError:
                            is_dir = False
                        out.append({"name": e.name, "path": e.path,
                                    "is_dir": is_dir})
            except Exception:
                pass
            out.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
            return out

        def _visible_entries(self):
            q = self._query.strip().lower()
            if self._mode == "recent":
                return [{"name": os.path.basename(p.rstrip("/\\")) or p,
                         "path": p, "is_dir": os.path.isdir(p)} for p in self._recents
                        if not q or q in os.path.basename(p.rstrip("/\\")).lower()]
            entries = self._entries
            if self._mode == "folder":
                entries = [e for e in entries if e["is_dir"]]
            if q:
                entries = [e for e in entries if q in e["name"].lower()]
            return entries

        def _refresh_list(self):
            try:
                scroll = self.query_one("#ap-browser", ScrollableContainer)
                scroll.remove_children()
                rows = self._visible_entries()
                if not rows:
                    scroll.mount(Static("Nothing here.", classes="ap-empty"))
                else:
                    self._selected = min(self._selected, len(rows) - 1)
                    for i, entry in enumerate(rows):
                        picked = entry["path"] in self._picked
                        scroll.mount(_FsRow(i, entry, selected=(i == self._selected),
                                            picked=picked))
                self._refresh_chrome()
                self._refresh_cap()
                self._fit()
            except Exception:
                pass

        def _fit(self):
            """Re-fit after content changes: content_size is only valid
            after the next layout pass, so always defer one frame."""
            try:
                self.call_after_refresh(
                    lambda: theme_css.fit_dialog(self, "ap-box", "ap-browser"))
            except Exception:
                pass

        def _refresh_chrome(self):
            """Chooser vs browser chrome: which rows are visible, the
            title, the path, and the drive buttons."""
            try:
                browsing = self._view == "browse"
                self.query_one("#ap-chooser", Vertical).display = not browsing
                self.query_one("#ap-options", Button).display = browsing
                self.query_one("#ap-attach", Button).display = browsing
                browsing_dirs = browsing and self._mode in ("files", "folder")
                self.query_one("#ap-nav", Horizontal).display = browsing_dirs
                drives_row = self.query_one("#ap-drives", Horizontal)
                drives_row.set_class(browsing_dirs and self._drives_on, "on")
                drives_row.remove_children()
                if browsing_dirs and self._drives_on:
                    for d in list_drives():
                        drives_row.mount(Button(f" {d[0]}: ", id=f"ap-drive-{d[0]}",
                                                classes="cct-btn cct-btn-sm"))
                box = self.query_one("#ap-box", Vertical)
                box.set_class(not browsing, "ap-chooser")
                title = self.query_one("#ap-title", Static)
                if browsing:
                    name = {"files": "File", "folder": "Folder", "recent": "Recent"}[self._mode]
                    title.update(f"\U0001f4ce  Attach \u2014 {name}")
                else:
                    title.update("\U0001f4ce  Attach to Message")
                path = self.query_one("#ap-path", Static)
                if browsing_dirs:
                    path.update(f"  {self._cwd}")
                else:
                    path.update("")
            except Exception:
                pass

        def _refresh_cap(self):
            """One honest status line under the list: what's picked, and
            a weak-model warning when the selected file would be
            unusable by the active model. Never a fake readiness note."""
            try:
                cap = self.query_one("#ap-cap", Static)
                parts = []
                if self._picked:
                    names = ", ".join(
                        os.path.basename(p.rstrip("/\\")) for p in self._picked[:3])
                    more = f" +{len(self._picked) - 3}" if len(self._picked) > 3 else ""
                    parts.append(
                        f"[{theme_css.current_hex('text-muted')}]Picked: "
                        f"{len(self._picked)} \u00b7 {names}{more}[/]")
                elif self._mode in ("files", "recent"):
                    entry = self._current_entry()
                    if entry and not entry["is_dir"]:
                        kind, _k = attachment_kind(entry["path"])
                        warn = _vision_warning(SimpleNamespace(
                            kind=kind, path=entry["path"],
                            extraction_status=_core.STATUS_READY))
                        if warn:
                            parts.append(
                                f"[{theme_css.current_hex('error')}]\u26a0 {warn}[/]")
                cap.update("  " + "   ".join(parts))
            except Exception:
                pass

        # ----------------------------------------------------------- input
        def _rows(self):
            return self._visible_entries()

        def _current_entry(self):
            rows = self._rows()
            if not rows:
                return None
            return rows[min(self._selected, len(rows) - 1)]

        def _append_query(self, ch):
            if self._view != "browse":
                return
            self._query += ch
            self._selected = 0
            self._refresh_list()

        def on_key(self, event):
            key = event.key
            if key == "escape":
                if self._query:
                    self._query = ""
                    self._selected = 0
                    self._refresh_list()
                    event.stop()
                else:
                    self.dismiss(None)
            elif key == "backspace":
                if self._query:
                    self._query = self._query[:-1]
                    self._selected = 0
                    self._refresh_list()
                    event.stop()
            elif len(key) == 1 and key.isprintable():
                self._append_query(key)
                event.stop()

        def on_click(self, event):
            widget = getattr(event, "widget", None)
            if widget in (self, None):
                self.dismiss(None)
                return
            if isinstance(widget, _FsRow):
                entry = widget.entry
                if entry["is_dir"] and self._mode in ("files", "folder"):
                    self._query = ""
                    self._load_dir(entry["path"])
                else:
                    self._selected = widget.index
                    self._refresh_list()
                event.stop()
            elif widget is not None and widget.id and widget.id.startswith("ap-drive-"):
                letter = widget.id.split("-", 2)[2]
                self._query = ""
                self._load_dir(f"{letter}:\\")
                event.stop()

        # ----------------------------------------------------------- keys
        def action_move_down_sel(self):
            rows = self._rows()
            if rows and self._selected < len(rows) - 1:
                self._selected += 1
                self._refresh_list()

        def action_move_up_sel(self):
            if self._selected > 0:
                self._selected -= 1
                self._refresh_list()

        def action_toggle_pick(self):
            entry = self._current_entry()
            if not entry or self._mode == "folder":
                return
            if entry["path"] in self._picked:
                self._picked.remove(entry["path"])
            else:
                self._picked.append(entry["path"])
            self._refresh_list()

        def action_attach(self):
            entry = self._current_entry()
            if self._mode == "folder":
                self.dismiss(self._cwd)
            elif self._mode == "recent":
                if self._picked:
                    self.dismiss(list(self._picked))
                elif entry:
                    self.dismiss(entry["path"])
            else:
                if self._picked:
                    self.dismiss(list(self._picked))
                elif entry and entry["is_dir"]:
                    self._query = ""
                    self._load_dir(entry["path"])
                elif entry:
                    self.dismiss(entry["path"])

        def action_nav_back(self):
            if self._history:
                self._fwd.append(self._cwd)
                self._cwd = self._history.pop()
                self._query = ""
                self._selected = 0
                self._entries = self._list_entries(self._cwd)
                self._refresh_list()

        def action_nav_forward(self):
            if self._fwd:
                self._history.append(self._cwd)
                self._cwd = self._fwd.pop()
                self._query = ""
                self._selected = 0
                self._entries = self._list_entries(self._cwd)
                self._refresh_list()

        def action_cancel(self):
            self.dismiss(None)

        # --------------------------------------------------------- buttons
        def _browse_native(self):
            """'Browse' opens the OS's own file picker (any drive/device;
            All Files + categories; files only, never folders). The
            dialog blocks, so it runs in a worker thread; the result
            dismisses through the same path as the in-app browser.
            If the worker can't even start, the in-app browser opens —
            Browse must never dead-end."""
            from .. import native_picker
            if not native_picker.is_native_supported():
                self._enter_mode("files")
                return
            try:
                self.run_worker(self._native_browse_worker, thread=True)
            except Exception as e:
                import sys
                print(f"[AttachPanel] browse worker failed to start: {e}", file=sys.stderr)
                self._enter_mode("files")

        def _native_browse_worker(self):
            from .. import native_picker
            try:
                paths = native_picker.pick_files(initial_dir=self._cwd)
            except Exception as e:
                import sys
                print(f"[AttachPanel] native_browse_worker exception: {e}", file=sys.stderr)
                paths = None
            try:
                self.app.call_from_thread(self._on_native_browse, paths)
            except Exception as e:
                import sys
                print(f"[AttachPanel] call_from_thread failed: {e}", file=sys.stderr)

        def _on_native_browse(self, paths):
            # v0.8.1: None = every picker method failed — never a silent
            # no-op: show the notice AND fall back into the in-app
            # browser automatically, so Browse always lands somewhere
            # usable. [] = user cancelled (stay in chooser).
            if paths is None:
                try:
                    self.query_one("#ap-cap", Static).update(
                        "  [red]Native file dialog unavailable — in-app browser opened below.[/]")
                except Exception:
                    pass
                self._enter_mode("files")
                return
            if not paths:
                return  # cancelled — stay in chooser
            try:
                self.dismiss(paths if len(paths) > 1 else paths[0])
            except Exception:
                pass

        def on_button_pressed(self, event):
            eid = event.button.id
            if eid in ("ap-cancel", "ap-close"):
                self.dismiss(None)
            elif eid == "ap-attach":
                self.action_attach()
            elif eid == "ap-opt-files":
                self._browse_native()
            elif eid in ("ap-opt-folder", "ap-opt-recent"):
                self._enter_mode(eid.split("-")[2])
            elif eid == "ap-options":
                self._show_chooser()
            elif eid == "ap-back":
                self.action_nav_back()
            elif eid == "ap-fwd":
                self.action_nav_forward()
            elif eid == "ap-up":
                parent = os.path.dirname(self._cwd)
                if parent and os.path.isdir(parent):
                    self._query = ""
                    self._load_dir(parent)
            elif eid == "ap-home":
                self._query = ""
                self._load_dir(os.path.expanduser("~"))
            elif eid == "ap-drives-btn":
                self._drives_on = not self._drives_on
                self._refresh_chrome()

        def on_mount(self):
            self.call_after_refresh(lambda: self.query_one("#ap-box").add_class("open"))
            self.call_after_refresh(self._show_chooser)
            self.call_after_refresh(self._fit)

        def on_resize(self, event):
            self._fit()

else:
    AttachPanel = None
