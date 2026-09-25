"""
CCT UI — ComposerFooter (the single badge row docked inside StickyComposer:
`NOTEBOOK · provider/model · Workspace` on the left, live context readout
center, minimal Permissions/Attach/Send glyphs right — flat dot-separated
text badges, not a button toolbar, matching the reference terminal-chat
aesthetic) and StatusLine (the compact bar CCTApp docks at the very
bottom of the screen). Both render state and dispatch events/bubble
presses to their parent — neither decides what a click means.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Horizontal
    from textual.widgets import Static, Button
    from textual.reactive import reactive
except Exception:
    TEXTUAL_AVAILABLE = False

from .events import NotebookChanged, WorkspaceChanged, CommandExecuted
from .. import ai_modes

WORKSPACE_CYCLE = ["Workspace", "Kinetics", "Quantum", "Notebook A"]


if TEXTUAL_AVAILABLE:

    def _hex_blend(h1, h2, t):
        """Linear interpolate two '#rrggbb' hex colors at t in [0, 1].
        Returns a '#rrggbb' hex string — local helper so the mode badge
        can render its 4-segment gradient bar without reaching into
        theme internals (theme.blend takes RGB tuples, not hex)."""
        a = [int(h1[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(h2[i:i + 2], 16) for i in (1, 3, 5)]
        return "#" + "".join(f"{int(round(x + (y - x) * t)):02x}"
                             for x, y in zip(a, b))

    def _safe_glyph(emoji, fallback):
        import sys
        try:
            enc = getattr(sys.stdout, "encoding", None) or "utf-8"
            emoji.encode(enc)
            return emoji
        except Exception:
            return fallback

    class _Badge(Static):
        """One flat, clickable text badge (no border/background chrome) —
        the `Notebook` / `provider model` / `Workspace` pieces of
        `NOTEBOOK \u00b7 openai/gpt-4o-mini \u00b7 Workspace`."""

        def __init__(self, text, badge_id, on_click=None, classes="cct-badge"):
            super().__init__(text, id=badge_id, classes=classes)
            self._on_click = on_click

        def on_click(self, event):
            if self._on_click:
                self._on_click()

    class ComposerFooter(Horizontal):
        """The single badge row along the bottom of the composer card:
        `Notebook \u00b7 model \u00b7 Workspace` (left), live context (center),
        three minimal glyph controls (right). One row, one component.
        """

        # Holds the AI-mode KEY ("notebook"/"agent"/"build"/"plan" — see
        # ai_modes.py), not a display string. Reactive name kept as
        # `notebook_mode` (rather than renamed to `ai_mode`) so the
        # NotebookChanged event this posts, and ui/app.py's existing
        # on_notebook_changed handler, didn't need touching to grow
        # from a 2-way NOTEBOOK/AGENT toggle to the spec's 4 modes.
        notebook_mode = reactive("notebook")
        context_tokens = reactive(0)

        def __init__(self, model_label="no model"):
            super().__init__(id="cct-bottom-row")
            self._model_label = model_label
            self._workspace_i = 0

        def _mode_badge_markup(self, mode_key):
            accent = ai_modes.accent_hex(mode_key)
            m = ai_modes.meta(mode_key)
            # v0.7.8: per-mode gradient applied to the badge — a 4-segment
            # ▮ bar blending the mode's two-stop gradient, then the icon in
            # the start color and the label in the end color.
            try:
                gs, ge = ai_modes.gradient(mode_key)
                bar = "".join(f"[{_hex_blend(gs, ge, t)}]\u25ae[/]"
                              for t in (0.0, 0.33, 0.66, 1.0))
                return f"{bar} [{gs} b]{m['icon']}[/] [{ge} b]{m['label']}[/]"
            except Exception:
                return f"[{accent} b]{m['icon']} {m['label']}[/]"

        def compose(self):
            with Horizontal(id="cct-left-controls"):
                yield _Badge(self._mode_badge_markup(self.notebook_mode),
                             "badge-notebook", self._toggle_notebook)
                yield Static("\u00b7", classes="cct-badge-sep")
                yield _Badge(self._model_label, "badge-model", self._open_model)
                yield Static("\u00b7", classes="cct-badge-sep")
                yield _Badge(WORKSPACE_CYCLE[0], "badge-workspace", self._cycle_workspace)
            yield Static(id="cct-footer-spacer-left")
            yield Static(self._status_text(), id="cct-center-status")
            yield Static(id="cct-footer-spacer-right")
            with Horizontal(id="cct-right-controls"):
                yield Button(_safe_glyph("🛡", "(P)"), id="btn-permissions", classes="cct-icon-btn", tooltip="Permissions & Security (Click / Alt+P)")
                yield Button(_safe_glyph("📎", "(+)"), id="btn-attach", classes="cct-icon-btn", tooltip="Attach file (Click / Alt+A)")
                yield Button(_safe_glyph("➤", ">"), id="btn-send", classes="cct-icon-btn cct-icon-send", tooltip="Send message (Enter)")

        def _status_text(self):
            return f"Context {self.context_tokens}K"

        def watch_context_tokens(self, value):
            try:
                self.query_one("#cct-center-status", Static).update(self._status_text())
            except Exception:
                pass

        def set_model_label(self, label):
            self._model_label = label
            try:
                self.query_one("#badge-model", _Badge).update(label)
            except Exception:
                pass

        def _toggle_notebook(self):
            """Clicking the badge cycles Notebook -> Agent -> Build ->
            Plan -> Notebook (spec section 3's four AI modes, up from
            the old two-stop NOTEBOOK/AGENT toggle)."""
            self.notebook_mode = ai_modes.next_mode(self.notebook_mode)
            self.query_one("#badge-notebook", _Badge).update(
                self._mode_badge_markup(self.notebook_mode))
            self.post_message(NotebookChanged(self.notebook_mode))

        def _open_model(self):
            self.post_message(CommandExecuted("/model"))

        def _cycle_workspace(self):
            self._workspace_i = (self._workspace_i + 1) % len(WORKSPACE_CYCLE)
            name = WORKSPACE_CYCLE[self._workspace_i]
            self.query_one("#badge-workspace", _Badge).update(name)
            self.post_message(WorkspaceChanged(name))

        def on_resize(self, event=None):
            """Responsive footer collapse at narrow viewports: ensures send button never gets pushed off."""
            w = (event.size.width if event else None) or (self.size.width if self.size else 80)
            try:
                center = self.query_one("#cct-center-status", Static)
                center.display = (w >= 70)
            except Exception:
                pass
            try:
                ws_badge = self.query_one("#badge-workspace", _Badge)
                ws_badge.display = (w >= 56)
            except Exception:
                pass

    class StatusLine(Static):
        """One compact bottom status line for the whole app — no boxes,
        no oversized labels. `get_fields` is a zero-arg callable
        returning [(label, value, tone), ...]; CCTApp supplies it and
        calls `refresh_status()` when something worth showing changes,
        instead of this widget reaching into backend state itself."""

        def __init__(self, get_fields, id="cct-statusline"):
            super().__init__(id=id)
            self._get_fields = get_fields

        def on_mount(self):
            self.refresh_status()

        def refresh_status(self):
            from . import theme_css
            tone_role = {"ready": "success", "warn": "warning", "err": "error", "": "text-muted"}
            parts = []
            for label, value, tone in self._get_fields():
                color = theme_css.current_hex(tone_role.get(tone, "text-muted"))
                text = f"[{color}]{value}[/]" if not label else f"{label} [{color}]{value}[/]"
                parts.append(text)
            self.update("   \u00b7   ".join(parts))

else:
    ComposerFooter = None
    StatusLine = None

