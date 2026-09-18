"""
CCT UI — context_menu.py: the right-click context menu for chat
messages (v0.7.2 "Chat Context Menu & Conversation Actions" spec).

One reusable Screen (MessageContextMenu), built from a plain ordered
list of (action, label) tuples — conversation.py picks AI_MENU_ITEMS
or USER_MENU_ITEMS depending on which bubble was right-clicked, and
pushes this Screen positioned beside the click. This file only knows
"the user picked this row" (it returns the chosen action string via
Screen.dismiss()); what each action actually *does* is business logic
that lives in ui/app.py's on_message_context_action, same separation
every other component in this package already follows (see
ui/events.py's module docstring).

Same real-Screen-push pattern as PermissionModeMenu (ui/header.py) and
_AttachPrompt/_PathPrompt (ui/app.py) — this package has a standing
rule against floating popup windows; a Screen push positioned near the
click instead of centered is how "context menu" is done here without
breaking that rule. Textual doesn't have a real CSS "scale" transform
(only opacity/offset/size can `transition`), so the "fade + scale"
requirement in the spec is implemented the same honest way
PermissionModeMenu's dropdown already is: opacity + a small upward
offset, not a literal scale animation — see CHANGELOG_v0.7.2 for the
prior instance of this same tradeoff being called out explicitly
rather than silently faked.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Vertical
    from textual.screen import Screen
    from textual.widgets import Static
except Exception:
    TEXTUAL_AVAILABLE = False

# spec: "AI Response Context Menu"
AI_MENU_ITEMS = [
    ("copy", "\U0001f4cb  Copy Text"),
    ("summarize", "\U0001f4dc  Summarize Full Chat"),
    ("new_session", "\u2795  New Chat Session"),
    ("retry:build", "\U0001f501  Try Again in Build Mode"),
    ("retry:plan", "\U0001f501  Try Again in Plan Mode"),
    ("retry:notebook", "\U0001f501  Try Again in Notebook Mode"),
    ("retry:agent", "\U0001f501  Try Again in Agent Mode"),
    ("retry:research", "\U0001f501  Try Again in Research Mode"),
    ("retry:debugger", "\U0001f501  Try Again in Debugger Mode"),
]

# spec: "User Message Context Menu"
USER_MENU_ITEMS = [
    ("rewrite", "\u270f\ufe0f  Rewrite (Edit Prompt)"),
    ("copy", "\U0001f4cb  Copy Text"),
    ("summarize", "\U0001f4dc  Summarize Full Chat"),
    ("revert", "\u23ea  Revert"),
    ("fork", "\U0001f500  Fork Conversation"),
]

# File Context Menu (touch & right-click)
FILE_MENU_ITEMS = [
    ("open", "\U0001f4c4  Open"),
    ("rename", "\u270f\ufe0f  Rename"),
    ("delete", "\U0001f5d1\ufe0f  Delete"),
    ("copy_path", "\U0001f4cb  Copy Path"),
    ("new_file", "\u2795  New File"),
    ("new_folder", "\U0001f4c1  New Folder"),
]

MENU_WIDTH = 36


if TEXTUAL_AVAILABLE:

    class _MenuRow(Static):
        """One clickable row. Hover highlight is free via CSS `:hover`
        (same trick every other list row in this package uses);
        keyboard-driven highlight is applied explicitly by the parent
        Screen via the 'cct-ctxmenu-row-selected' class, since arrow-key
        navigation isn't a real mouse hover — same split
        PermissionModeMenu (ui/header.py) already uses."""

        def __init__(self, action, label, index):
            super().__init__(f"  {label}", classes="cct-ctxmenu-row")
            self.action = action
            self.index = index

        def on_click(self, event):
            event.stop()
            self.screen.dismiss(self.action)

    class MessageContextMenu(Screen):
        """The menu itself.

        `items` — ordered list of (action, label) tuples (AI_MENU_ITEMS
        or USER_MENU_ITEMS).
        `origin` — the (x, y) screen-cell coordinate the right-click
        landed on; the menu's top-left corner opens there (clamped so
        it never renders off the right/bottom edge of the terminal),
        which is what makes it "appear beside the mouse cursor" per the
        spec instead of centered like this package's other dialogs.

        dismiss() resolves to the chosen action string, or None if the
        menu was closed without choosing (Esc, or a click outside the
        box) — mirrors PermissionModeMenu's contract exactly.
        """

        CSS = """
        MessageContextMenu { align: left top; background: $app-background 0%; }
        #cct-ctxmenu-box {
            width: 36; height: auto;
            background: $surface;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $surface-dark;
            border-right: tall $surface-dark;
            padding: 1 0;
            opacity: 1; offset-y: 0;
        }
        #cct-ctxmenu-box.open { opacity: 1; offset-y: 0; }
        .cct-ctxmenu-row {
            height: 1; padding: 0 2; color: $text;
            background: $surface;
            border-left: thick $surface;
            border-right: thick $surface;
        }
        .cct-ctxmenu-row:hover {
            background: $surface-alt;
            color: $accent;
            border-left: thick $accent;
            border-right: thick $surface-alt;
            text-style: bold;
        }
        .cct-ctxmenu-row-selected {
            background: $surface-highlight;
            color: $accent;
            border-left: thick $accent;
            border-right: thick $surface-highlight;
            text-style: bold;
        }
        """

        def __init__(self, items, origin=(0, 0)):
            super().__init__()
            self._items = list(items)
            self._origin = origin
            self._selected = 0

        def compose(self):
            with Vertical(id="cct-ctxmenu-box"):
                for i, (action, label) in enumerate(self._items):
                    yield _MenuRow(action, label, i)

        def on_mount(self):
            box = self.query_one("#cct-ctxmenu-box")
            x, y = self._origin
            # The box's rendered size is fully known up front (fixed
            # width, one row per item + 2 rows of vertical padding, no
            # wrapping) so it can be clamped against the terminal size
            # without waiting for a layout pass.
            box_h = len(self._items) + 2
            max_x = max(0, self.size.width - MENU_WIDTH)
            max_y = max(0, self.size.height - box_h)
            box.styles.offset = (min(max(x, 0), max_x), min(max(y, 0), max_y))
            self._sync_selected_class()
            self.call_after_refresh(lambda: box.add_class("open"))

        def _sync_selected_class(self):
            for row in self.query(_MenuRow):
                row.set_class(row.index == self._selected, "cct-ctxmenu-row-selected")

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)
            elif event.key in ("down", "tab"):
                self._selected = (self._selected + 1) % len(self._items)
                self._sync_selected_class()
            elif event.key in ("up", "shift+tab"):
                self._selected = (self._selected - 1) % len(self._items)
                self._sync_selected_class()
            elif event.key == "enter":
                self.dismiss(self._items[self._selected][0])

        def on_click(self, event):
            # Clicking the dimmed backdrop outside the box closes the
            # menu without choosing anything — standard "click
            # elsewhere to dismiss" behavior. Rows handle their own
            # clicks directly (see _MenuRow.on_click, which calls
            # event.stop() so this handler never also fires for them).
            if getattr(event, "widget", None) in (self, None):
                self.dismiss(None)

else:
    MessageContextMenu = None
