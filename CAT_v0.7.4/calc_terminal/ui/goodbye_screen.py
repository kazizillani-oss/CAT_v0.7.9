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
        GoodbyeScreen {
            align: center middle;
            background: $app-background;
        }
        #goodbye-box {
            width: 76;
            max-width: 92%;
            height: auto;
            max-height: 28;
            background: $surface;
            border: tall;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $surface-dark;
            border-right: tall $surface-dark;
            tint: $surface-highlight 4%;
            padding: 1 3;
            align: center middle;
        }
        #goodbye-cat {
            color: $accent;
            height: auto;
            text-align: center;
        }
        #goodbye-block {
            color: $text;
            height: auto;
            text-align: center;
            text-style: bold;
        }
        #goodbye-title {
            color: $accent;
            height: auto;
            text-align: center;
            padding-top: 1;
            text-style: bold;
        }
        #goodbye-msg {
            color: $text;
            height: auto;
            text-align: center;
            padding: 1 2;
            margin: 1 1;
            background: $surface-alt;
            border: tall;
            border-top: tall $surface-shadow;
            border-left: tall $surface-shadow;
            border-bottom: tall $surface-highlight;
            border-right: tall $surface-highlight;
            tint: $accent 4%;
            text-style: bold;
        }
        #goodbye-exit-btn {
            width: 24;
            min-width: 18;
            height: 3;
            min-height: 3;
            max-height: 3;
            margin: 1 0 0 0;
            background: $surface-alt;
            color: $text;
            text-style: bold;
            content-align: center middle;
            border: tall;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $surface-dark;
            border-right: tall $surface-dark;
            tint: $surface-highlight 6%;
            transition: background 90ms, border 90ms, offset 70ms, tint 90ms;
        }
        #goodbye-exit-btn:hover {
            background: $accent 28%;
            color: #ffffff;
            text-style: bold;
            border: tall;
            border-top: tall #ffffff;
            border-left: tall $accent-highlight;
            border-bottom: tall $accent;
            border-right: tall $accent;
            tint: $accent 12%;
        }
        #goodbye-exit-btn:focus {
            background: $accent 20%;
            color: #ffffff;
            text-style: bold;
            background-tint: transparent;
            border: tall;
            border-top: tall #ffffff;
            border-left: tall $accent-highlight;
            border-bottom: tall $accent;
            border-right: tall $accent;
            tint: $accent 8%;
        }
        #goodbye-exit-btn.-active {
            background: $accent 40%;
            color: #ffffff;
            text-style: bold;
            border: tall;
            border-top: tall $surface-shadow;
            border-left: tall $surface-shadow;
            border-bottom: tall $surface-highlight;
            border-right: tall $surface-highlight;
            offset-y: 1;
            tint: $app-background 20%;
        }
        #goodbye-hint {
            color: $text-faint;
            height: 1;
            text-align: center;
            margin-top: 1;
        }
        """
        BINDINGS = [Binding("escape", "close", "Close"), Binding("enter", "close", "Close"), Binding("q", "close", "Close")]

        def __init__(self, farewell="Session saved. See you soon! \U0001F43E"):
            super().__init__()
            self._farewell = farewell

        def compose(self):
            with Vertical(id="goodbye-box"):
                cat_lines = _GOODBYE_CAT
                yield Static("\n".join(cat_lines), id="goodbye-cat")
                yield Static("\n".join(_GOODBYE_BLOCK), id="goodbye-block")
                yield Static("G O O D   B Y E", id="goodbye-title")
                yield Static(self._farewell, id="goodbye-msg")
                yield Button("\U0001f43e Exit CAT", id="goodbye-exit-btn", classes="cct-dash-action")
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
