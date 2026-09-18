"""
CCT UI — diff_panel.py: Live Diff Viewer (v0.7.10 spec section 14).

Shows before/after changes for files modified by the AI or user.
Displays inline diff with color-coded additions/deletions.

Lives in the right pane as a modal screen or inline panel.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Vertical, Horizontal, VerticalScroll
    from textual.screen import Screen
    from textual.widgets import Static, Button
except Exception:
    TEXTUAL_AVAILABLE = False


def _format_diff_lines(diff_lines):
    """Format diff lines with color coding."""
    formatted = []
    for line in diff_lines:
        if line.startswith('+++') or line.startswith('---'):
            # File headers
            formatted.append(f"[b]{line}[/b]")
        elif line.startswith('@@'):
            # Hunk headers
            formatted.append(f"[b cyan]{line}[/cyan]")
        elif line.startswith('+'):
            # Additions
            formatted.append(f"[green]{line}[/green]")
        elif line.startswith('-'):
            # Deletions
            formatted.append(f"[red]{line}[/red]")
        else:
            # Context lines
            formatted.append(line)
    return "\n".join(formatted)


if TEXTUAL_AVAILABLE:

    class DiffViewerPanel(Screen):
        """Live Diff Viewer panel showing before/after changes."""

        CSS = """
        DiffViewerPanel { align: center middle; background: $app-background 60%; }
        #cct-diff-box {
            width: 90%; height: 85%; background: $surface;
            border: round $border; padding: 1 2;
        }
        #cct-diff-header { height: 1; padding: 0 0 1 0; }
        #cct-diff-file { width: 1fr; }
        #cct-diff-stats { height: 1; padding: 0 0 1 0; }
        #cct-diff-content { height: 1fr; }
        #cct-diff-content Static { width: 100%; }
        #cct-diff-actions { height: 3; padding-top: 1; }
        #cct-diff-actions Button { margin-right: 1; }
        """

        def __init__(self, path="", diff_lines=None, original="", current=""):
            super().__init__()
            self._path = path
            self._diff_lines = diff_lines or []
            self._original = original
            self._current = current

        def compose(self):
            with Vertical(id="cct-diff-box"):
                with Horizontal(id="cct-diff-header"):
                    yield Static("[b]Live Diff Viewer[/b]", id="cct-diff-title")
                    yield Button("Close", id="cct-diff-close")
                yield Static(f"File: {self._path}", id="cct-diff-file")
                with Horizontal(id="cct-diff-stats"):
                    yield Static(self._compute_stats(), id="cct-diff-stats-text")
                yield VerticalScroll(
                    Static(self._format_content(), id="cct-diff-text"),
                    id="cct-diff-content"
                )
                with Horizontal(id="cct-diff-actions"):
                    yield Button("Copy Diff", id="cct-diff-copy")
                    yield Button("Revert Changes", id="cct-diff-revert")

        def _compute_stats(self):
            """Compute diff statistics."""
            additions = sum(1 for line in self._diff_lines if line.startswith('+'))
            deletions = sum(1 for line in self._diff_lines if line.startswith('-'))
            return f"[green]+{additions}[/green] [red]-{deletions}[/red] lines changed"

        def _format_content(self):
            """Format diff content with syntax highlighting."""
            if not self._diff_lines:
                return "[italic]No changes detected[/italic]"
            return _format_diff_lines(self._diff_lines)

        def on_button_pressed(self, event):
            if event.button.id == "cct-diff-close":
                self.dismiss(None)
            elif event.button.id == "cct-diff-copy":
                self._copy_diff()
            elif event.button.id == "cct-diff-revert":
                self._revert_changes()

        def _copy_diff(self):
            """Copy diff to clipboard."""
            try:
                import pyperclip
                diff_text = "\n".join(self._diff_lines)
                pyperclip.copy(diff_text)
            except Exception:
                pass

        def _revert_changes(self):
            """Revert file to original content."""
            if self._path and self._original:
                try:
                    with open(self._path, "w", encoding="utf-8") as f:
                        f.write(self._original)
                    self.dismiss("reverted")
                except Exception:
                    pass

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)

        def on_click(self, event):
            """Gesture on diff → before/after (spec 23). Double-click diff toggles view."""
            import time as _t
            try:
                now = _t.time()
                last = getattr(self, "_last_diff_click", 0)
                if now - last < 0.35:
                    self._last_diff_click = 0
                    try:
                        from ..gestures.manager import handle_gesture
                        if handle_gesture("double_click", "diff", app=getattr(self, "app", None), context={"path": self._path}):
                            event.stop()
                            return
                    except Exception:
                        pass
                    # Fallback: toggle before/after view if available
                    try:
                        self._show_before_after()
                        event.stop()
                    except Exception:
                        pass
                else:
                    self._last_diff_click = now
            except Exception:
                pass

        def _show_before_after(self):
            """Toggle before/after view."""
            try:
                from textual.containers import Vertical
                from textual.widgets import Static
                # Simple before/after toggle: show original vs current
                content = self.query_one("#cct-diff-text", Static)
                if hasattr(self, "_showing_before") and self._showing_before:
                    content.update(_format_diff_lines(self._diff_lines))
                    self._showing_before = False
                else:
                    # Show before and after stacked
                    before = self._original or "[no original]"
                    after = self._current or "[no current]"
                    content.update(f"[b]BEFORE[/b]\n{before}\n\n[b]AFTER[/b]\n{after}")
                    self._showing_before = True
            except Exception:
                pass

    class InlineDiffViewer(Vertical):
        """Inline diff viewer widget for showing changes in the editor."""

        CSS = """
        InlineDiffViewer { height: auto; max-height: 50%; }
        .cct-inline-diff-line { height: 1; width: 100%; }
        .cct-inline-diff-add { background: $success 20%; }
        .cct-inline-diff-del { background: $error 20%; }
        .cct-inline-diff-hunk { background: $accent 20%; }
        """

        def __init__(self, diff_lines=None, **kwargs):
            super().__init__(**kwargs)
            self._diff_lines = diff_lines or []

        def show_diff(self, diff_lines):
            """Display diff lines."""
            self._diff_lines = diff_lines
            self._render()

        def _render(self):
            """Render diff lines."""
            for child in list(self.children):
                child.remove()
            for line in self._diff_lines[:50]:  # Limit to 50 lines
                css_class = ""
                if line.startswith('+'):
                    css_class = "cct-inline-diff-add"
                elif line.startswith('-'):
                    css_class = "cct-inline-diff-del"
                elif line.startswith('@@'):
                    css_class = "cct-inline-diff-hunk"
                self.mount(Static(line, classes=f"cct-inline-diff-line {css_class}"))

else:
    DiffViewerPanel = None
    InlineDiffViewer = None
