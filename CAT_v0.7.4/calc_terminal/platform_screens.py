"""
CAT Platform Screens — Cross-Platform Interfaces Showcase (v0.9.000).

Surfaces status, installation, and usage instructions for all 5 platforms:
  1. Terminal UI (TUI)
  2. Desktop App (macOS, Windows, Linux)
  3. Web App (catcli pair)
  4. Mobile Support (/touch)
  5. Python Developer SDK
"""

from __future__ import annotations

TEXTUAL_AVAILABLE = True
try:
    from textual.screen import ModalScreen
    from textual.containers import Vertical, Horizontal, VerticalScroll
    from textual.widgets import Static, Button
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False
    ModalScreen = object


class PlatformCenterModal(ModalScreen if TEXTUAL_AVAILABLE else object):
    """Modal displaying CAT's 5 native cross-platform interfaces."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("enter", "dismiss", "OK", show=False),
    ]

    DEFAULT_CSS = """
    PlatformCenterModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.75);
    }
    #cct-platform-box {
        width: 82;
        max-width: 95%;
        height: auto;
        max-height: 85%;
        background: #141624;
        border: tall;
        border-top: tall #89b4fa;
        border-left: tall #7aa2f7;
        border-bottom: tall #585b70;
        border-right: tall #45475a;
        padding: 0;
        layout: vertical;
    }
    #cct-platform-header {
        height: 3;
        min-height: 3;
        padding: 0 1;
        layout: horizontal;
        align-vertical: middle;
        background: #1c1e2d;
        color: #89b4fa;
        border-top: tall #89b4fa;
        border-left: tall #89b4fa;
        border-bottom: tall #585b70;
        border-right: tall #45475a;
        margin: 1 1 0 1;
    }
    #cct-platform-title {
        text-style: bold;
        width: 1fr;
        color: #89b4fa;
    }
    #cct-platform-close {
        width: 3;
        min-width: 3;
        height: 1;
        background: transparent;
        color: #ff99a8;
        border: none;
        content-align: center middle;
        text-style: bold;
    }
    #cct-platform-close:hover {
        background: #f38ba8;
        color: #11111b;
    }
    #cct-platform-scroll {
        height: auto;
        max-height: 18;
        padding: 1;
        overflow-y: auto;
    }
    .platform-card {
        height: auto;
        padding: 1;
        margin: 0 0 1 0;
        background: #1a1c2e;
        border-top: tall #89b4fa;
        border-left: tall #7aa2f7;
        border-bottom: tall #383a52;
        border-right: tall #2a2c42;
    }
    #cct-platform-footer {
        height: 3;
        min-height: 3;
        padding: 0 1;
        layout: horizontal;
        align: right middle;
        background: #181926;
        margin: 0 1 1 1;
    }
    .cct-btn-ok {
        height: 1;
        background: #89b4fa;
        color: #11111b;
        border: none;
        padding: 0 2;
        text-style: bold;
    }
    .cct-btn-ok:hover {
        background: #b4befe;
    }
    """

    def compose(self):
        with Vertical(id="cct-platform-box"):
            with Horizontal(id="cct-platform-header"):
                yield Static("🌐 CAT Cross-Platform Interfaces (5 Native Surfaces)", id="cct-platform-title")
                yield Button("✕", id="cct-platform-close")
            with VerticalScroll(id="cct-platform-scroll"):
                yield Static(
                    "[bold #89b4fa]1. Terminal UI (TUI)[/]\n"
                    "Keyboard-first, lightning-fast terminal environment with Tokyo Night 3D bevels.\n"
                    "[dim]Launch with:[/] [cyan]`python -m calc_terminal`[/] or [cyan]`cat`[/]",
                    classes="platform-card"
                )
                yield Static(
                    "[bold #a6e3a1]2. Desktop Application (macOS, Windows, Linux)[/]\n"
                    "Dedicated native windowed app with integrated editor, terminal, and browser preview.\n"
                    "[dim]Executables:[/] [cyan]`cat-desktop.exe`[/] (Win), [cyan]`CAT.app`[/] (macOS), [cyan]`cat-desktop.AppImage`[/] (Linux)",
                    classes="platform-card"
                )
                yield Static(
                    "[bold #fab387]3. Web App & Pairing (`catcli pair`)[/]\n"
                    "Real-time collaborative browser interface powered by local WebSocket server.\n"
                    "[dim]Run server:[/] [cyan]`catcli pair`[/] or [cyan]`python -m calc_terminal.web.server`[/]",
                    classes="platform-card"
                )
                yield Static(
                    "[bold #f38ba8]4. Mobile & Touchscreen Support (`/touch`)[/]\n"
                    "Adaptive layout optimized for touchscreen laptops and mobile viewing, with enlarged touch buttons.\n"
                    "[dim]Toggle with:[/] [cyan]`/touch`[/] or [cyan]`Ctrl+Shift+T`[/]",
                    classes="platform-card"
                )
                yield Static(
                    "[bold #cba6f7]5. Python Developer SDK (`calc_terminal.sdk`)[/]\n"
                    "Automate agent workflows, planning, building, and 200+ model routing programmatically.\n"
                    "[dim]Python usage:[/] [cyan]`import calc_terminal.sdk as cat; cat.chat(...); cat.plan(...)`[/]",
                    classes="platform-card"
                )
            with Horizontal(id="cct-platform-footer"):
                yield Button("Close (Esc)", id="btn-platform-done", classes="cct-btn-ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()

