"""
CCT UI — help_panel.py: Help Center panel with categorized topics,
quick reference, and keyboard shortcuts.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Vertical, Horizontal, ScrollableContainer
    from textual.screen import Screen
    from textual.widgets import Static, Button
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False


_HELP_TOPICS = [
    ("Getting Started", [
        ("Open a Folder", "Menu \u2192 Open Folder or Ctrl+O"),
        ("Start a Chat", "Type a message and press Enter"),
        ("Switch Models", "Menu \u2192 User \u2192 Model"),
        ("Change Permissions", "Click the permission pill in the header"),
    ]),
    ("Navigation", [
        ("Main Menu", "Click the \u2261 button or press Ctrl+M"),
        ("Dashboard", "Menu \u2192 Dashboard"),
        ("Recent Workspaces", "Menu \u2192 Recent Workspaces"),
        ("Chat History", "Menu \u2192 Chats"),
        ("Explorer Sidebar", "Ctrl+B to toggle"),
    ]),
    ("AI Features", [
        ("Agent Mode", "Type /agent followed by your task"),
        ("Chat Mode", "Just type your message directly"),
        ("Personalize AI", "Menu \u2192 Personalize"),
        ("MCP Servers", "Menu \u2192 MCP Servers"),
    ]),
    ("File Operations", [
        ("Open File", "Click file in Explorer or Ctrl+O"),
        ("Save File", "Ctrl+S"),
        ("New File", "Ctrl+N in Explorer"),
        ("Search Files", "Ctrl+Shift+F"),
    ]),
    ("View Controls", [
        ("Toggle Sidebar", "Ctrl+B"),
        ("Toggle Fullscreen", "F11"),
        ("Zoom In/Out", "Ctrl+= / Ctrl+-"),
        ("Reset Zoom", "Ctrl+0"),
    ]),
    ("Account", [
        ("Sign In", "Run: cat --auth login"),
        ("Sign Out", "Menu \u2192 User \u2192 Sign Out"),
        ("View Profile", "Menu \u2192 User"),
        ("Chat History", "Menu \u2192 Chats"),
    ]),
]

_KEYBOARD_SHORTCUTS = [
    ("Ctrl+M", "Open/close main menu"),
    ("Ctrl+B", "Toggle Explorer sidebar"),
    ("Ctrl+O", "Open folder"),
    ("Ctrl+S", "Save current file"),
    ("Ctrl+N", "New file"),
    ("Ctrl+Shift+F", "Search in files"),
    ("Ctrl+/", "Toggle comment"),
    ("Ctrl+Z", "Undo"),
    ("Ctrl+Shift+Z", "Redo"),
    ("F11", "Toggle fullscreen"),
    ("Ctrl+=", "Zoom in"),
    ("Ctrl+-", "Zoom out"),
    ("Ctrl+0", "Reset zoom"),
    ("Escape", "Close panel / cancel"),
    ("Tab", "Next field / autocomplete"),
    ("Shift+Tab", "Previous field"),
    ("Enter", "Submit / confirm"),
    ("Up/Down", "Navigate history / options"),
]


if TEXTUAL_AVAILABLE:

    class HelpCenterPanel(Screen):
        """Help Center with categorized topics and quick reference."""

        CSS = """
        HelpCenterPanel { align: center middle; background: $app-background 60%; }
        #hc-box {
            width: 82; max-width: 95%; height: 34; max-height: 88%;
            background: $surface; border: tall $border-active $border;
            padding: 0 0 1 0;
            opacity: 0; offset-y: 1;
            transition: opacity 120ms, offset 150ms;
            layout: vertical;
        }
        #hc-box.open { opacity: 1; offset-y: 0; }
        #hc-titlebar {
            height: 3; min-height: 3; padding: 0 2;
            border-bottom: solid $border;
            align-vertical: middle;
        }
        #hc-title { text-style: bold; width: 1fr; }
        #hc-close, Button#hc-close, Button.cct-popup-close {
            width: 3; min-width: 3; max-width: 3;
            height: 1; min-height: 1; max-height: 1;
            padding: 0; margin: 0;
            background: transparent; color: $text-faint; border: none;
            content-align: center middle;
        }
        #hc-close:hover, Button#hc-close:hover, Button.cct-popup-close:hover {
            color: $error; background: transparent; border: none;
        }
        #hc-body { height: 1fr; min-height: 0; }
        #hc-topics { width: 30; min-width: 30; height: 100%; padding: 1 1;
                     border-right: solid $border; background: transparent; }
        #hc-topic-list { width: 100%; height: 100%; overflow-y: auto;
                         scrollbar-size: 1 1;
                         scrollbar-color: $border $surface;
                         scrollbar-gutter: stable; background: transparent; }
        .hc-topic { height: 2; color: $text-muted; padding: 0 1;
                    background: transparent;
                    border-left: thick transparent; }
        .hc-topic:hover { color: $accent; text-style: bold; }
        .hc-topic-sel { color: $accent; border-left: thick $accent; text-style: bold; background: transparent; }
        #hc-detail { width: 1fr; height: 100%; padding: 0 2; overflow-y: auto;
                     scrollbar-size: 1 1;
                     scrollbar-color: $border $surface;
                     scrollbar-gutter: stable; }
        .hc-section { color: $text-faint; height: auto; padding-top: 1;
                      border-top: solid $border; margin-top: 1; }
        .hc-row { height: 1; color: $text-muted; padding: 0 0; }
        #hc-close-bar {
            height: 4; min-height: 4; padding: 0 2;
            border-top: solid $border;
            align-horizontal: right; align-vertical: middle;
        }
        #hc-close-bar Button {
            margin-left: 1;
            border: tall $border-active $border;
        }
        #hc-close-bar Button:hover {
            border: tall $accent-highlight $accent;
            color: $text;
        }
        #hc-close-bar Button.-primary {
            border: tall #c4b5fd #4c1d95;
            background: #7c3aed;
            color: #ffffff;
            text-style: bold;
        }
        #hc-close-bar Button.-primary:hover {
            border: tall #ddd6fe #5b21b6;
            background: #8b5cf6;
            color: #ffffff;
        }
        #hc-close-bar Button.-active {
            offset-y: 1;
        }
        """

        BINDINGS = [
            Binding("escape", "cancel", "Close"),
        ]

        def __init__(self):
            super().__init__()
            self._selected = 0

        def compose(self):
            from textual.containers import Horizontal as H
            with Vertical(id="hc-box"):
                with H(id="hc-titlebar"):
                    yield Static("?  Help Center", id="hc-title")
                    yield Button("\u2715", id="hc-close", classes="cct-popup-close cct-ctrl")
                with H(id="hc-body"):
                    with Vertical(id="hc-topics"):
                        with ScrollableContainer(id="hc-topic-list"):
                            for i, (cat, _) in enumerate(_HELP_TOPICS):
                                yield Static(f"  {cat}", classes="hc-topic",
                                             id=f"hc-topic-{i}")
                    with ScrollableContainer(id="hc-detail"):
                        yield from self._detail_lines(0)
                with H(id="hc-close-bar"):
                    yield Button("  \u2328 Shortcuts  ", id="hc-shortcuts", classes="cct-btn cct-btn-sm")
                    yield Button("  Done  ", id="hc-done", variant="primary", classes="cct-btn")

        def _detail_lines(self, index):
            """Yield widgets for the detail pane of topic `index`."""
            if index < 0 or index >= len(_HELP_TOPICS):
                return
            cat, items = _HELP_TOPICS[index]
            yield Static(cat, classes="hc-section")
            for label, desc in items:
                yield Static(f"  [b]{label}[/b]  \u2014  {desc}", classes="hc-row")

        def _rebuild_detail(self, index):
            try:
                detail = self.query_one("#hc-detail", ScrollableContainer)
            except Exception:
                return
            detail.remove_children()
            for widget in self._detail_lines(index):
                detail.mount(widget)

        def on_mount(self):
            self.call_after_refresh(
                lambda: self.query_one("#hc-box").add_class("open"))
            self._sync_selection()

        def _sync_selection(self):
            for i, _ in enumerate(_HELP_TOPICS):
                try:
                    row = self.query_one(f"#hc-topic-{i}", Static)
                    row.set_class(i == self._selected, "hc-topic-sel")
                except Exception:
                    pass

        def on_click(self, event):
            if getattr(event, "widget", None) in (self, None):
                self.dismiss(None)
                return
            # Check if a topic was clicked
            target = getattr(event, "widget", None)
            if target and hasattr(target, "id") and target.id and target.id.startswith("hc-topic-"):
                try:
                    idx = int(target.id.split("-")[-1])
                    self._selected = idx
                    self._sync_selection()
                    self._rebuild_detail(idx)
                except (ValueError, IndexError):
                    pass

        def on_button_pressed(self, event):
            if event.button.id == "hc-close" or event.button.id == "hc-done":
                self.dismiss(None)
            elif event.button.id == "hc-shortcuts":
                self.dismiss("shortcuts")

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)
            elif event.key in ("down", "tab"):
                self._selected = (self._selected + 1) % len(_HELP_TOPICS)
                self._sync_selection()
                self._rebuild_detail(self._selected)
            elif event.key in ("up", "shift+tab"):
                self._selected = (self._selected - 1) % len(_HELP_TOPICS)
                self._sync_selection()
                self._rebuild_detail(self._selected)

else:
    HelpCenterPanel = None
