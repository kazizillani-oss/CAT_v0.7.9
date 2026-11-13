"""
CAT UI — whats_new_modal.py: What's New in 0.9.000 Modal.

Features:
  - Header: "What's new in 0.9.000" with [esc] badge
  - GitHub Copilot Auto
  - Side Panel Tab Shortcuts (Ctrl+W, Ctrl+Alt+W, Ctrl+Shift+T, Close tabs to the right)
  - Mark Sessions Read or Unread (Tab dot indicator, read/unread states)
  - Footer with scroll hint and [ ok ] button
"""

TEXTUAL_AVAILABLE = True
try:
    from textual.screen import Screen
    from textual.containers import Vertical, Horizontal, VerticalScroll
    from textual.widgets import Static, Button
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False


class WhatsNewModal(Screen if TEXTUAL_AVAILABLE else object):
    """What's New in 0.9.000 release highlight modal."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close", show=False),
        Binding("enter", "dismiss_modal", "Close", show=False),
    ]

    DEFAULT_CSS = """
    WhatsNewModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.75);
    }
    #cct-wn-box {
        width: 72;
        max-width: 96%;
        height: auto;
        max-height: 24;
        background: #181926;
        border: tall;
        border-top: tall #89b4fa;
        border-left: tall #7aa2f7;
        border-bottom: tall #11111b;
        border-right: tall #181926;
        padding: 0;
        layout: vertical;
        overflow: hidden;
    }
    #cct-wn-header {
        height: 3;
        min-height: 3;
        padding: 0 1;
        layout: horizontal;
        align-vertical: middle;
        background: #1e1e2e;
        border-bottom: solid #313244;
    }
    #cct-wn-title {
        width: 1fr;
        color: #cdd6f4;
        text-style: bold;
        align-vertical: middle;
    }
    #cct-wn-esc {
        width: auto;
        color: #6c7086;
        text-style: italic;
        align-vertical: middle;
    }
    #cct-wn-scroll {
        height: 1fr;
        min-height: 12;
        max-height: 16;
        padding: 1 2;
        overflow-y: auto;
        scrollbar-gutter: stable;
        scrollbar-size: 1 1;
        scrollbar-color: #89b4fa #181926;
    }
    .cct-wn-card {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        background: #1e2030;
        border: tall;
        border-top: tall #45475a;
        border-left: tall #45475a;
        border-bottom: tall #11111b;
        border-right: tall #181926;
    }
    .cct-wn-card-title {
        color: #89b4fa;
        text-style: bold;
        margin-bottom: 0;
    }
    .cct-wn-card-desc {
        color: #a6adc8;
    }
    #cct-wn-footer {
        height: 3;
        min-height: 3;
        padding: 0 1;
        layout: horizontal;
        align-vertical: middle;
        background: #1e1e2e;
        border-top: solid #313244;
    }
    #cct-wn-scroll-hint {
        width: 1fr;
        color: #6c7086;
        text-style: italic;
        align-vertical: middle;
    }
    #cct-wn-ok-btn {
        width: 8;
        min-width: 8;
        height: 1;
        background: #89b4fa;
        color: #11111b;
        border: none;
        text-style: bold;
        content-align: center middle;
    }
    #cct-wn-ok-btn:hover {
        background: #b4befe;
        color: #11111b;
    }
    """

    def compose(self):
        if not TEXTUAL_AVAILABLE:
            return
        with Vertical(id="cct-wn-box"):
            with Horizontal(id="cct-wn-header"):
                yield Static("What's new in 0.9.000", id="cct-wn-title")
                yield Static("[#6c7086]esc[/]", id="cct-wn-esc")
            with VerticalScroll(id="cct-wn-scroll"):
                with Vertical(classes="cct-wn-card"):
                    yield Static("GitHub Copilot Auto", classes="cct-wn-card-title")
                    yield Static(
                        "Pick Auto in the model picker when your Copilot account has an Auto pool, and Copilot's "
                        "router chooses the model for each session at the Auto discount. If routing fails, "
                        "CAT falls back to the account's default chat model.",
                        classes="cct-wn-card-desc",
                    )
                with Vertical(classes="cct-wn-card"):
                    yield Static("Side Panel Tab Shortcuts", classes="cct-wn-card-title")
                    yield Static(
                        "Right-click a side panel tab and choose Close tabs to the right. Ctrl+W now closes "
                        "side panel tabs wherever focus is, Ctrl+Alt+W always closes the session tab, and "
                        "Ctrl+Shift+T reopens the last closed tab of either kind where it was.",
                        classes="cct-wn-card-desc",
                    )
                with Vertical(classes="cct-wn-card"):
                    yield Static("Mark Sessions Read or Unread", classes="cct-wn-card-title")
                    yield Static(
                        "Open the menu on a tab, Home row, project row or inbox card and choose Mark as unread "
                        "to keep its dot until you next visit.",
                        classes="cct-wn-card-desc",
                    )
            with Horizontal(id="cct-wn-footer"):
                yield Static("scroll ↑/↓", id="cct-wn-scroll-hint")
                yield Button("ok", id="cct-wn-ok-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("cct-wn-ok-btn",):
            self.dismiss(None)

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

