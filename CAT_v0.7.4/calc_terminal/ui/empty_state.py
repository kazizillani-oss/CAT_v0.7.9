"""
CAT v0.7.9.0 — ui/empty_state.py: the chat-pane startup centerpiece.

Shown by ConversationView's existing welcome slot whenever the main
chat has no conversation in it, and removed the moment real turns
arrive (the same hide_welcome() chokepoint that always governed this
slot — so the art can never leak into history, prompts or copies).

    ┌─────────────── chat pane only ───────────────┐
    │                                              │
    │              ██████╗ █████╗ ████████╗        │
    │             ██╔════╝██╔══██╗╚══██╔══╝         │
    │             ██║     ███████║   ██║           │
    │             ██║     ██╔══██║   ██║           │
    │             ╚██████╗██║  ██║   ██║           │
    │              ╚═════╝╚═╝  ╚═╝   ╚═╝           │
    │                                              │
    │                 CAT v0.7.9.0                 │
    │          Chemistry • Coding • Intelligence   │
    │                  ● CAT Notebook ready        │
    │   Create · Analyze · Build · Debug · Research│
    │                                              │
    └──────────────────────────────────────────────┘

Hard rules:

* This is an EMPTY-STATE COMPONENT, never a message: it is not added to
  session turns, never sent to the model, and is removed before the
  first real bubble mounts.
* Centered inside the CHAT PANE ONLY — it lives inside
  ConversationView, which is already inside WorkspaceShell's main
  column, so explorer width / composer height / window resizes can
  never make it overlap anything (the v0.7.9.0 layout contract holds).
* Mode-aware: the ready line reflects the ACTUAL active mode
  (ai_modes.current_mode()) via set_mode().
* Responsive: picks full / compact / text-only word art from the live
  widget width (on_resize), so a narrow chat pane never overflows.
* Subtle one-shot entrance animation (fade + slight rise) and an
  optional slow pulse on the ready dot only — the word art itself never
  moves continuously.

The animated CAT bot (ui/cat_agent.py) is a DIFFERENT component for a
DIFFERENT moment: that one appears while the agent is actively working;
this one exists only while there is nothing in the chat at all.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Vertical
    from textual.widgets import Static
except Exception:
    TEXTUAL_AVAILABLE = False

# Width budgets (columns) of the two word-art variants, including their
# side padding — used to pick the variant that fits without overflow.
_FULL_ART_MIN_WIDTH = 34
_COMPACT_ART_MIN_WIDTH = 22

if TEXTUAL_AVAILABLE:

    def _full_art():
        """The app's own CAT block letters (single source of truth: the
        classic terminal boots with exactly these glyphs). Imported
        lazily — the backend app module is heavy and must not load at
        ui import time."""
        try:
            from ..app import LOGO
            if LOGO:
                return [line.rstrip() for line in LOGO]
        except Exception:
            pass
        return [
            " ██████╗ █████╗ ████████╗",
            "██╔════╝██╔══██╗╚══██╔══╝",
            "██║     ███████║   ██║",
            "██║     ██╔══██║   ██║",
            "╚██████╗██║  ██║   ██║",
            " ╚═════╝╚═╝  ╚═╝   ╚═╝",
        ]

    # Compact variant for narrow chat panes (~16 cols) — same three
    # letters, half-block construction, still unmistakably "CAT".
    _COMPACT_ART = [
        "▄▄▄▄ ▄▄▄▄▄ █████",
        "█    █▄▄█   █  ",
        "▀▀▀▀ █   █   █  ",
    ]

    def _lerp_hex(a: str, b: str, t: float) -> str:
        """Linear blend of two '#rrggbb' colors — powers the subtle
        top-to-bottom gradient across the word art lines."""
        try:
            ar, ag, ab = int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16)
            br, bg, bb = int(b[1:3], 16), int(b[3:5], 16), int(b[5:7], 16)
            return "#{:02x}{:02x}{:02x}".format(
                round(ar + (br - ar) * t),
                round(ag + (bg - ag) * t),
                round(ab + (bb - ab) * t))
        except Exception:
            return b

    def _darken(hex_color: str, amount: float) -> str:
        """Blend a hex color toward black by `amount` (0..1). Used only
        by the light theme so gradient stops stay readable on white."""
        try:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            f = max(0.0, min(1.0, 1.0 - amount))
            return "#{:02x}{:02x}{:02x}".format(
                round(r * f), round(g * f), round(b * f))
        except Exception:
            return hex_color

    def _mode_label(mode_key=None):
        """'CAT <Mode>' identity from the ACTUAL mode state (never a
        hard-coded global label)."""
        try:
            from .cat_agent import mode_label_for
            from .. import ai_modes
            return mode_label_for(mode_key or ai_modes.current_mode())
        except Exception:
            return "CAT"

    class CATChatEmptyState(Vertical):
        """The startup / empty-chat centerpiece. State inputs: version,
        mode, ready, theme — all rendered as plain Rich markup; nothing
        here ever touches session state."""

        DEFAULT_CSS = """
        CATChatEmptyState {
            width: 1fr;
            height: 1fr;
            align: center middle;
            opacity: 0;
            offset-y: 3;
        }
        CATChatEmptyState.open {
            opacity: 1;
            offset-y: 0;
        }
        CATChatEmptyState {
            transition: opacity 500ms, offset-y 500ms;
        }
        CATChatEmptyState #cct-empty-art {
            width: auto;
            text-align: center;
        }
        CATChatEmptyState .cct-empty-line {
            width: 1fr;
            text-align: center;
        }
        CATChatEmptyState #cct-empty-ready {
            transition: opacity 1300ms;
        }
        """

        def __init__(self, version="0.7.9.0", mode_key=None, ready=True,
                     tagline="Chemistry \u2022 Coding \u2022 Intelligence"):
            super().__init__(id="cct-empty-state")
            self._version = version
            self._mode_key = mode_key
            self._ready = bool(ready)
            self._tagline = tagline
            self._compact = False   # re-evaluated on resize

        # ------------------------------------------------------ content --
        def _art_markup(self):
            """Word-art block with a restrained top-to-bottom accent
            gradient (mode gradient stops — same family the composer
            badge uses). Falls back through compact → text-only as the
            pane narrows, so it can never overflow horizontally.

            v0.7.9.0 light-mode audit: mode-gradient end stops are tuned
            for dark surfaces; on white the pale ends dropped below 2:1
            contrast and looked washed out. In LIGHT mode each line
            color is blended ~25% toward black first, keeping the
            gradient subtle but clearly legible."""
            from . import theme_css
            g_start, g_end = theme_css.gradient_hex()
            try:
                from .. import theme as _theme
                if _theme.is_light():
                    g_start = _darken(g_start, 0.25)
                    g_end = _darken(g_end, 0.25)
            except Exception:
                pass
            if self._compact == "text":
                return f"[b]{g_start}CAT[/]"
            art = _COMPACT_ART if self._compact else _full_art()
            n = max(1, len(art) - 1)
            lines = []
            for i, line in enumerate(art):
                color = _lerp_hex(g_start, g_end, i / n)
                lines.append(f"[{color} b]{line}[/]")
            return "\n".join(lines)

        def _body_markup(self):
            from . import theme_css
            faint = theme_css.current_hex("text-faint")
            muted = theme_css.current_hex("text-muted")
            success = theme_css.current_hex("success")
            label = _mode_label(self._mode_key)
            status = (f"[{success}]\u25cf[/] [{muted} b]{label}[/] "
                      f"[{faint}]ready[/]") if self._ready else \
                     (f"[{faint}]\u25cb starting\u2026[/]")
            suggestions = ("Create \u00b7 Analyze \u00b7 Build \u00b7 Debug "
                           "\u00b7 Research")
            return {
                "art": self._art_markup(),
                "version": f"[{muted} b]CAT v{self._version}[/]",
                "tagline": f"[{faint}]{self._tagline}[/]",
                "ready": status,
                "suggestions": f"[{faint}]{suggestions}[/]",
            }

        def _repaint_children(self):
            body = self._body_markup()
            try:
                self.query_one("#cct-empty-art", Static).update(body["art"])
                self.query_one("#cct-empty-version", Static).update(
                    body["version"])
                self.query_one("#cct-empty-tagline", Static).update(
                    body["tagline"])
                self.query_one("#cct-empty-ready", Static).update(
                    body["ready"])
                self.query_one("#cct-empty-suggest", Static).update(
                    body["suggestions"])
            except Exception:
                pass

        # ------------------------------------------------------- events --
        def compose(self):
            body = self._body_markup()
            yield Static(body["art"], id="cct-empty-art")
            yield Static(body["version"], id="cct-empty-version",
                         classes="cct-empty-line")
            yield Static("", id="cct-empty-gap1", classes="cct-empty-line")
            yield Static(body["tagline"], id="cct-empty-tagline",
                         classes="cct-empty-line")
            yield Static("", id="cct-empty-gap2", classes="cct-empty-line")
            yield Static(body["ready"], id="cct-empty-ready",
                         classes="cct-empty-line")
            yield Static(body["suggestions"], id="cct-empty-suggest",
                         classes="cct-empty-line")

        def on_mount(self):
            self.call_after_refresh(self._fit_width)
            # Subtle entrance: fade in + slight upward settle (one-shot).
            # Implemented with a class-toggle transition instead of a
            # CSS @keyframes animation — an infinite/long animation can
            # hold Textual's "wait for screen" busy state, while this
            # settles once and is done.
            self.call_later(self.add_class, "open")
            # Optional light status effect: slow pulse on the ready dot
            # ONLY (never the word art). A gentle timer-driven opacity
            # oscillation, smoothed by the CSS transition above.
            if self._ready:
                self._pulse_up = False
                self.set_interval(1.3, self._pulse_ready_dot)

        def _pulse_ready_dot(self):
            try:
                dot = self.query_one("#cct-empty-ready", Static)
                dot.styles.opacity = 1.0 if not self._pulse_up else 0.45
                self._pulse_up = not self._pulse_up
            except Exception:
                pass

        def on_resize(self, event):
            self._fit_width()

        def _fit_width(self):
            """Responsive rule: pick the largest art variant that fits
            the LIVE chat-pane width (never overflow horizontally)."""
            try:
                w = self.size.width or self.outer_size.width or 0
            except Exception:
                w = 0
            if w >= _FULL_ART_MIN_WIDTH:
                compact = False
            elif w >= _COMPACT_ART_MIN_WIDTH:
                compact = True
            else:
                compact = "text"
            if compact != self._compact:
                self._compact = compact
                self._repaint_children()

        # ------------------------------------------------- public state --
        def set_mode(self, mode_key):
            """Called with the ACTUAL current mode whenever it changes —
            the ready line always names the real persona."""
            self._mode_key = mode_key
            self._repaint_children()

        def repaint_theme(self):
            """Re-read theme colors (called after /theme switches)."""
            self._repaint_children()

else:
    CATChatEmptyState = None
