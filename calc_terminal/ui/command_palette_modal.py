"""CAT Code Editor — IDE Command Palette Modal (calc_terminal/ui/command_palette_modal.py).

VS Code-style Command Palette modal triggered by Ctrl+Shift+P:
- Fuzzy searches all registered IDE commands from CommandRegistry.
- Displays category, title, description, and keybinding badges.
- Up/Down navigation, Enter to execute, Esc to dismiss.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

TEXTUAL_AVAILABLE = True
try:
    from rich.text import Text
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Vertical, VerticalScroll
    from textual.screen import ModalScreen
    from textual.widgets import Input, Static
except Exception:
    TEXTUAL_AVAILABLE = False
    ModalScreen = object  # type: ignore

from ..editor.commands import CATCommand, get_command_registry
from ..editor.shortcuts import get_shortcut_manager


class CommandPaletteModal(ModalScreen):
    """Full-featured IDE Command Palette modal dialog."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Dismiss", show=False),
        Binding("up", "move_up", "Move Up", show=False),
        Binding("down", "move_down", "Move Down", show=False),
    ]

    DEFAULT_CSS = """
    CommandPaletteModal {
        align: center top;
        background: rgba(0, 0, 0, 0.65);
        padding-top: 3;
    }
    #cct-cmd-modal-box {
        width: 76;
        height: auto;
        max-height: 24;
        background: $surface;
        border: round $accent;
        padding: 0;
    }
    #cct-cmd-modal-input {
        dock: top;
        border: none;
        border-bottom: solid $border;
        background: $surface-alt;
        padding: 0 1;
        margin: 0;
    }
    #cct-cmd-modal-scroll {
        height: auto;
        max-height: 18;
        padding: 0;
    }
    .cct-cmd-modal-row {
        height: 1;
        padding: 0 1;
        background: transparent;
        color: $text;
    }
    .cct-cmd-modal-row-selected {
        background: $accent;
        color: $app-background;
        text-style: bold;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._matches: List[Tuple[CATCommand, str]] = []
        self._selected_index: int = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="cct-cmd-modal-box"):
            yield Input(placeholder="Type a command or search actions...", id="cct-cmd-modal-input")
            with VerticalScroll(id="cct-cmd-modal-scroll"):
                yield Static("", id="cct-cmd-modal-list")

    def on_mount(self) -> None:
        self._filter_commands("")
        try:
            self.query_one("#cct-cmd-modal-input", Input).focus()
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "cct-cmd-modal-input":
            self._filter_commands(event.value.strip())

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._execute_selected()

    def _filter_commands(self, query: str) -> None:
        reg = get_command_registry()
        shortcut_mgr = get_shortcut_manager()
        all_cmds = reg.list_commands()
        q = query.lower()

        matches = []
        for cmd in all_cmds:
            keys = shortcut_mgr.get_keybindings_for_command(cmd.id)
            key_str = f" [{keys[0].upper()}]" if keys else ""
            if not q or q in cmd.title.lower() or q in cmd.id.lower() or q in cmd.category.lower():
                matches.append((cmd, key_str))

        self._matches = matches
        self._selected_index = 0
        self._render_rows()

    def _render_rows(self) -> None:
        try:
            list_widget = self.query_one("#cct-cmd-modal-list", Static)
            if not self._matches:
                list_widget.update("[dim italic]  No matching commands found.[/dim italic]")
                return

            lines = []
            for i, (cmd, key_str) in enumerate(self._matches[:40]):
                is_sel = (i == self._selected_index)
                prefix = "▶ " if is_sel else "  "
                cat_tag = f"[{cmd.category}] " if cmd.category else ""
                badge = f"  [dim]{key_str}[/dim]" if key_str else ""
                
                if is_sel:
                    lines.append(f"[reverse bold]{prefix}{cat_tag}{cmd.title}{badge}[/reverse bold]")
                else:
                    lines.append(f"{prefix}[cyan]{cat_tag}[/cyan]{cmd.title}{badge}")

            list_widget.update("\n".join(lines))
        except Exception:
            pass

    def action_move_up(self) -> None:
        if self._matches:
            self._selected_index = max(0, self._selected_index - 1)
            self._render_rows()

    def action_move_down(self) -> None:
        if self._matches:
            self._selected_index = min(len(self._matches) - 1, self._selected_index + 1)
            self._render_rows()

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def _execute_selected(self) -> None:
        if self._matches and 0 <= self._selected_index < len(self._matches):
            cmd, _ = self._matches[self._selected_index]
            self.dismiss(None)
            try:
                reg = get_command_registry()
                app = getattr(self, "app", None)
                ctx = {"app": app}
                reg.execute(cmd.id, context=ctx)
            except Exception:
                pass
