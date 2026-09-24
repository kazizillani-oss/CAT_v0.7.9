"""
CAT v0.7.9.0 — ui/empty_state.py: the chat-pane startup centerpiece.

Shown by ConversationView's existing welcome slot whenever the main
chat has no conversation in it, and removed the moment real turns
arrive (the same hide_welcome() chokepoint that always governed this
slot — so the art can never leak into history, prompts or copies).

    ┌─────────────── chat pane only ───────────────┐
    │                                              │
    │              ██████╗ █████╗ ████████╗        │
    │             ██╔════╝██╔══██╗╚══██╔══╝        │
    │             ██║     ███████║   ██║           │
    │             ██║     ██╔══██║   ██║           │
    │             ╚██████╗██║  ██║   ██║           │
    │              ╚═════╝╚═╝  ╚═╝   ╚═╝           │
    │                                              │
    │                 CAT v0.7.9.0                 │
    │       Chemistry • Coding • Intelligence      │
    │              ● CAT Notebook ready            │
    │ Create · Analyze · Build  · Debug · Research │
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
* Responsive: picks full / semi / compact / mini / text-only word art
  from the live widget width (on_resize), so a narrow chat pane never
  overflows.
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

# Width budgets (columns) of the word-art variants, including their
# side padding — used to pick the variant that fits without overflow.
# v0.7.9.6: extended the chain further down so ultra-narrow panes
# (4 cols — the floor of any usable chat region) still render a
# recognizable CAT motif instead of degrading to a single "CAT" label.
_FULL_ART_MIN_WIDTH = 34
_SEMI_ART_MIN_WIDTH = 28
_COMPACT_ART_MIN_WIDTH = 22
_MINI_ART_MIN_WIDTH = 14
_TINY_ART_MIN_WIDTH = 10
_MICRO_ART_MIN_WIDTH = 6
_NANO_ART_MIN_WIDTH = 4  # 2-row cat face floor — below this, text-only

# v0.7.9.6: the 3-row faces need ~5 rows of vertical breathing room to sit
# comfortably in the pane. Below that, the 2-row mini cat is swapped in so
# the centerpiece stays a cat face without pushing the version/tagline
# lines out of the viewport (the old behaviour let the art claim the whole
# pane and clip the identity block on a short terminal).
_MIN_3ROW_HEIGHT = 8


def _pick_art_variant(width, height=None, prefer_combo=False):
    """Pure, side-effect-free variant chooser — the single source of truth
    for the responsive art ladder.

    Returns one of: 'nanoface', 'microface', 'tinyface', 'miniface',
    'miniface2', 'compact', 'semi', 'combo', 'full'.
    """
    try:
        w = int(width or 0)
    except Exception:
        w = 0
    try:
        h = int(height) if height is not None else None
    except Exception:
        h = None

    if w >= _FULL_ART_MIN_WIDTH:
        # In split-pane views or when prefer_combo is requested, use the 3-row
        # side-by-side combo (cat face + CAT block wordmark) as in Screenshots 1, 3, 4, 5
        if prefer_combo:
            variant = "combo"
        else:
            variant = "full"
    elif w >= _SEMI_ART_MIN_WIDTH:
        variant = "semi"
    elif w >= _COMPACT_ART_MIN_WIDTH:
        variant = "compact"
    elif w >= _MINI_ART_MIN_WIDTH:
        variant = "miniface"
    elif w >= _TINY_ART_MIN_WIDTH:
        variant = "tinyface"
    elif w >= _MICRO_ART_MIN_WIDTH:
        variant = "microface"
    elif w >= _NANO_ART_MIN_WIDTH:
        variant = "nanoface"
    else:
        variant = "text"

    # Short-pane downgrade: on a pane with no room for three rows, EVERY
    # multi-row variant collapses to the 2-row cat — including the 6-row
    # `full` block letters, which would overflow even harder than the
    # 3-row faces. The nano face is already 2 rows, so it passes through.
    if h is not None and h < _MIN_3ROW_HEIGHT:
        if variant in ("full", "combo", "semi", "compact", "miniface", "tinyface",
                       "microface"):
            variant = "miniface2"
    return variant

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

    # Semi-compact variant (~26 cols) — proportional block letters
    # that fit between full and compact widths.
    _SEMI_ART = [
        "█▀▀▀▀▀  ▄▀▀▀▄  ▀▀█▀▀",
        "█       █▀▀▀█    █  ",
        "█▄▄▄▄▄  █   █    █  ",
    ]

    # Compact variant for narrow chat panes (~19 cols) — same three
    # letters, clean bevel block construction, still unmistakably "CAT".
    _COMPACT_ART = [
        "█▀▀▀ █▀▀█ ▀█▀",
        "█    █▄▄█  █ ",
        "▀▀▀▀ ▀  ▀  ▀ ",
    ]

    # Mini ASCII cat face for very narrow viewports (~10 cols, 3 rows)
    _MINI_CAT_ART = [
        "  /\\_/\\  ",
        " ( o.o ) ",
        "  > ^ <  ",
    ]

    # v0.7.9.6: extra-responsive chain of progressively-smaller cat
    # faces. Each variant is one row shorter / two cols narrower than
    # the previous so the chat pane centerpiece stays a recognizable
    # CAT motif all the way down to ~4 cols, instead of collapsing to
    # a text-only wordmark at the first hint of a narrow viewport.
    #
    # Tiny:  ~8 cols, 3 rows — keeps the eyes & smile
    _TINY_CAT_ART = [
        " /\\_/\\ ",
        "(o.o) ",
        " >^< ",
    ]
    # Micro: ~6 cols, 3 rows — stripped to eyes + a nose, still reads as a face
    _MICRO_CAT_ART = [
        "/\\_/\\",
        "o.o ",
        " > <",
    ]
    # Nano:  ~4 cols, 2 rows — minimal cat silhouette, last line of defense
    #        before the text-only fallback
    _NANO_CAT_ART = [
        "/\\_/",
        "o.o",
    ]
    # 2-row mini cat — used in tight horizontal banners where 3 rows
    # would otherwise overflow the available height.
    _MINI_CAT_ART_2ROW = [
        "/\\_/\\ (o.o)",
        " > ^ <  ",
    ]

    # Side-by-side combo variant (~30 cols, 3 rows) — the iconic cat face
    # + CAT block wordmark as featured in the flagship workspace views
    _COMBO_CAT_ART = [
        "  /\\_/\\   █████  █████  ██████",
        " ( o.o )  ██     ██▄▄█    ██  ",
        "  > ^ <   █████  ██  █    ██  ",
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
            offset-y: 2;
        }
        CATChatEmptyState.open {
            opacity: 1;
            offset-y: 0;
        }
        CATChatEmptyState {
            transition: opacity 600ms, offset 500ms;
        }
        CATChatEmptyState #cct-empty-art {
            width: auto;
            text-align: center;
            min-height: 1;
        }
        CATChatEmptyState .cct-empty-line {
            width: 1fr;
            text-align: center;
            min-height: 1;
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
            self._repaint_pending = False  # dirty flag for dedup
            self._resize_timer = None  # debounce timer handle
            self._pending_width = None  # last width seen in on_resize
            self._pending_height = None  # last height seen in on_resize
            self._last_width = 0  # last laid-out width (drives text fallback)

        # ------------------------------------------------------ content --
        def _art_markup(self):
            """Word-art block with a restrained top-to-bottom accent
            gradient (mode gradient stops — same family the composer
            badge uses). Falls back through semi → compact → mini → tiny
            → micro → nano → text-only as the pane narrows AND the short-
            pane 2-row cat when there isn't room for three rows, so it
            can never overflow horizontally or vertically.

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
            variant = self._compact or "full"
            if variant == "text":
                # v0.7.9.6: the wordmark fallback is now width-aware. At the
                # 2-3 col widths that reach here, the full 22-col banner
                # would overflow the pane, so it collapses in three steps
                # down to a bare `CAT` that fits any usable width.
                w = getattr(self, "_last_width", 0) or 0
                if w >= 22:
                    label = "━━━━━ 🐱 CAT CLI ━━━━━"
                elif w >= 14:
                    label = "━ 🐱 CAT ━"
                elif w >= 8:
                    label = "🐱 CAT"
                else:
                    label = "CAT"
                return f"[{g_start} b]{label}[/]"
            art = {
                "nanoface": _NANO_CAT_ART,
                "microface": _MICRO_CAT_ART,
                "tinyface": _TINY_CAT_ART,
                "miniface": _MINI_CAT_ART,
                "miniface2": _MINI_CAT_ART_2ROW,
                "compact": _COMPACT_ART,
                "semi": _SEMI_ART,
                "combo": _COMBO_CAT_ART,
            }.get(variant) or _full_art()
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
            # Responsive suggestions: shorter text for narrow panes.
            # v0.7.9.6: keyed off the renamed variant ladder (…face) so the
            # suggestion string shrinks in lockstep with the art instead of
            # falling through to the longest option on a narrow pane.
            if self._compact in ("text", "nanoface", "microface"):
                suggestions = "Create \u00b7 Build"
            elif self._compact in ("tinyface", "miniface", "miniface2"):
                suggestions = "Create \u00b7 Build \u00b7 Debug"
            elif self._compact in ("compact", "semi"):
                suggestions = ("Create \u00b7 Analyze \u00b7 Build "
                               "\u00b7 Debug")
            else:
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
            """Update all child Static widgets with current markup.
            Uses a dirty flag to deduplicate rapid successive calls."""
            if self._repaint_pending:
                return
            self._repaint_pending = True
            try:
                self._do_repaint()
            finally:
                self._repaint_pending = False

        def _do_repaint(self):
            """Actual repaint logic — guarded by _repaint_children()."""
            if not self.is_attached:
                return
            body = self._body_markup()
            try:
                self.query_one("#cct-empty-art", Static).update(body["art"])
            except Exception:
                pass
            try:
                self.query_one("#cct-empty-version", Static).update(
                    body["version"])
            except Exception:
                pass
            try:
                self.query_one("#cct-empty-tagline", Static).update(
                    body["tagline"])
            except Exception:
                pass
            try:
                self.query_one("#cct-empty-ready", Static).update(
                    body["ready"])
            except Exception:
                pass
            try:
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
            if not self.is_attached:
                return
            try:
                dot = self.query_one("#cct-empty-ready", Static)
                dot.styles.opacity = 1.0 if not self._pulse_up else 0.45
                self._pulse_up = not self._pulse_up
            except Exception:
                pass

        def on_resize(self, event):
            """Debounced resize: wait 50ms after the last resize event
            before recalculating layout, preventing thrashing during
            rapid terminal resizing. v0.7.9.6: also captures the latest
            width AND height here so the eventual _fit_width call doesn't
            need to touch the size object a second time (and can't observe
            a stale size if the user is mid-drag). The height is what
            drives the short-pane → 2-row cat downgrade."""
            if event and getattr(event, "size", None):
                self._pending_width = event.size.width
                self._pending_height = event.size.height
            elif hasattr(self, "app") and self.app and self.app.size:
                self._pending_width = self.app.size.width
                self._pending_height = max(1, self.app.size.height - 7)
            if self._resize_timer is not None:
                self._resize_timer.stop()
            self._resize_timer = self.set_timer(0.05, self._fit_width)

        def _fit_width(self):
            """Responsive rule: pick the largest art variant that fits the
            LIVE chat-pane width (never overflow horizontally) and, since
            v0.7.9.6, also respects the available HEIGHT so a short
            terminal degrades to the 2-row cat instead of clipping the
            identity block below the art.

            The decision itself lives in the module-level
            `_pick_art_variant()` helper — pure and unit-testable; this
            method only reads the live size and triggers a repaint.
            Short-circuits when the variant is unchanged, so a continuous
            stream of redraws with no real layout change costs
            effectively zero."""
            if not self.is_attached:
                return
            w = getattr(self, "_pending_width", None)
            h = getattr(self, "_pending_height", None)
            if hasattr(self, "app") and self.app and self.app.size:
                app_w = self.app.size.width
                app_h = self.app.size.height
                w = w or app_w
                if not h or h > app_h or (getattr(getattr(self, "parent", None), "size", None) and self.parent.size.height <= 3):
                    h = max(1, app_h - 7)
            if not w or not h:
                try:
                    size = self.size
                    w = w or (size.width or 0)
                    h = h or (size.height or 0)
                except Exception:
                    pass
            if not w:
                return  # widget not yet laid out — skip
            self._last_width = w
            is_split = False
            if hasattr(self, "app") and self.app and self.app.size:
                app_w = self.app.size.width
                if app_w and w < (app_w - 5):
                    is_split = True
            variant = _pick_art_variant(w, h, prefer_combo=is_split)
            if variant != self._compact:
                self._compact = variant
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
