"""
CCT TUI Dashboard — a real Textual application (actual widgets, actual
panes, actual layout engine — not raw print() dressed up to look like
one) offering a genuine split-pane view: a command sidebar, a scrolling
notebook-history feed, and a live status footer. This is optional and
additive: the primary interface stays the existing print()-based
terminal UI everywhere else, and /tui is one explicit command that
drops into this richer view and returns cleanly to the normal prompt
on quit.

Textual (like any full-screen TUI) needs a real attached terminal —
launching it against a pipe or non-tty stdin/stdout does not hang (it
fails fast), matching the same honesty precedent as keys.py's
stdin_is_interactive() guard for the raw-keypress live views.
"""

from . import keys

TEXTUAL_AVAILABLE = True
try:
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.widgets import Header, Footer, Static, Label
except Exception:
    TEXTUAL_AVAILABLE = False


if TEXTUAL_AVAILABLE:

    class NotebookCard(Static):
        def __init__(self, index, nb):
            body = (
                f"[b]{index}. {nb.get('topic', 'Notebook')}[/b]\n"
                f"[dim]{nb.get('question', '')[:90]}[/dim]\n"
                f"[green]{nb.get('final_answer', '')}[/green]"
            )
            super().__init__(body, classes="notebook-card")

    class CCTDashboard(App):
        """Sidebar of quick actions + scrolling notebook history +
        live status footer, all real Textual widgets/layout."""

        CSS = """
        Screen { background: $surface; }
        #sidebar { width: 26; border-right: solid $accent; padding: 1; }
        #main { padding: 1 2; }
        .notebook-card { border: round $accent; padding: 1; margin-bottom: 1; }
        #statusline { height: 1; color: $text-muted; }
        """
        BINDINGS = [("q", "quit_dashboard", "Back to terminal"), ("r", "refresh", "Refresh")]

        def __init__(self, history, stats):
            super().__init__()
            self._history = history
            self._stats = stats

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Horizontal():
                with Vertical(id="sidebar"):
                    yield Label("[b]CAT[/b]")
                    yield Label("Chemistry Calc Terminal")
                    yield Label("")
                    yield Label("[b]Session[/b]")
                    yield Label(f"Solved: {self._stats.get('solved', 0)}")
                    yield Label(f"Provider: {self._stats.get('provider', 'none')}")
                    yield Label(f"Model: {self._stats.get('model', 'none')}")
                    yield Label("")
                    yield Label("[dim]q  back to terminal[/dim]")
                    yield Label("[dim]r  refresh[/dim]")
                with VerticalScroll(id="main"):
                    if self._history:
                        for i, nb in enumerate(reversed(self._history), 1):
                            yield NotebookCard(len(self._history) - i + 1, nb)
                    else:
                        yield Static("No notebooks solved yet this session.")
            yield Static(id="statusline")
            yield Footer()

        def on_mount(self):
            self.query_one("#statusline", Static).update(
                f" {len(self._history)} notebook(s) in session history")

        def action_quit_dashboard(self):
            self.exit()

        def action_refresh(self):
            self.refresh()


def launch_dashboard(history, stats):
    """Runs the Textual dashboard synchronously (blocks until the user
    presses q or closes it), then returns control to the normal CLI
    loop. Returns (ok, message)."""
    if not TEXTUAL_AVAILABLE:
        return False, "textual isn't installed — run: pip install textual"
    if not keys.stdin_is_interactive():
        return False, "The TUI dashboard needs a real attached terminal (not piped input)."
    try:
        app = CCTDashboard(history, stats)
        app.run()
        return True, ""
    except Exception as e:
        return False, f"Could not launch TUI dashboard: {e}"
