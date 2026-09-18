"""Goodbye screen with ASCII art — shown on sign-out."""

if __name__ == "__main__":
    import sys
    sys.exit(1)

TEXTUAL_AVAILABLE = True
try:
    from textual.screen import Screen
    from textual.containers import Vertical
    from textual.widgets import Static, Button
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False

_GOODBYE_CAT = [
    "  /\\_/\\  ",
    " ( o.o ) ",
    "  > ^ <  ",
]

_GOODBYE_BLOCK = [
    "░██████╗░░█████╗░░█████╗░██████╗░  ██████╗░██╗░░░██╗███████╗",
    "██╔════╝░██╔══██╗██╔══██╗██╔══██╗  ██╔══██╗╚██╗░██╔╝██╔════╝",
    "██║░░██╗░██║░░██║██║░░██║██║░░██║  ██████╦╝░╚████╔╝░█████╗░░",
    "██║░░╚██╗██║░░██║██║░░██║██║░░██║  ██╔══██╗░░╚██╔╝░░██╔══╝░░",
    "╚██████╔╝╚█████╔╝╚█████╔╝██████╔╝  ██████╦╝░░░██║░░░███████╗",
    "░╚═════╝░░╚════╝░░╚════╝░╚═════╝░  ╚═════╝░░░░╚═╝░░░╚══════╝",
]

if TEXTUAL_AVAILABLE:
    class GoodbyeScreen(Screen):
        CSS = """
        GoodbyeScreen { align: center middle; background: $app-background; }
        #goodbye-box {
            width: 72; height: auto; max-height: 24;
            background: $surface; border: round $border;
            padding: 1 2; align: center middle;
        }
        #goodbye-cat { color: $accent; height: auto; text-align: center; }
        #goodbye-block { color: $text; height: auto; text-align: center; }
        #goodbye-title { color: $accent; height: auto; text-align: center; padding-top: 1; text-style: bold; }
        #goodbye-msg { color: $text-muted; height: auto; text-align: center; padding-top: 1; }
        #goodbye-hint { color: $text-faint; height: 1; text-align: center; padding-top: 1; }
        """
        BINDINGS = [Binding("escape", "close", "Close"), Binding("enter", "close", "Close"), Binding("q", "close", "Close")]

        def __init__(self, farewell="Session saved. See you soon! \U0001F43E"):
            super().__init__()
            self._farewell = farewell

        def compose(self):
            with Vertical(id="goodbye-box"):
                # Try to use art.py if available for richer art
                try:
                    from .. import art as _art
                    from .. import theme as _theme
                    # Pick a nice cat variant
                    cat_lines = _GOODBYE_CAT
                except Exception:
                    cat_lines = _GOODBYE_CAT
                yield Static("\n".join(cat_lines), id="goodbye-cat")
                yield Static("\n".join(_GOODBYE_BLOCK), id="goodbye-block")
                yield Static("G O O D   B Y E", id="goodbye-title")
                yield Static(self._farewell, id="goodbye-msg")
                yield Static("Press Enter, Esc or Q to exit  \u00b7  Auto-close in 3s", id="goodbye-hint")

        def on_mount(self):
            self.set_timer(3.0, self._auto_close)

        def _auto_close(self):
            try:
                self.dismiss(None)
                self.app.exit()
            except Exception:
                pass

        def on_key(self, event):
            if event.key in ("escape", "enter", "q"):
                self.dismiss(None)
                try:
                    self.app.exit()
                except Exception:
                    pass

        def action_close(self):
            self.dismiss(None)
            try:
                self.app.exit()
            except Exception:
                pass

        def on_button_pressed(self, event):
            self.dismiss(None)
            try:
                self.app.exit()
            except Exception:
                pass
else:
    GoodbyeScreen = None
