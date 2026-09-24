"""
CAT UI — design_system.py: ONE unified visual system for CAT CLI.

Design language: subtle skeuomorphism — soft 3D depth, layered
surfaces, slight bevels, raised buttons with pressed states, slightly
elevated cards/panels, clear hierarchy, smooth state transitions.
Still a serious developer/scientist terminal tool: no glass
everywhere, no heavy gradients, no readability cost.

What lives here (single source of truth — do not re-style widgets
ad hoc elsewhere, extend these tokens/classes instead):

* Breakpoints ......... breakpoint_for() — large/medium/small/tiny
* Wordmark ............ pick_wordmark() + CATWordmark — full/compact/
                        minimal CAT art selected by live width, NEVER
                        overflowing (single art source, no duplicates)
* Buttons ............. CATButton (+ .cat-btn CSS: normal/hover/
                        pressed/focus/disabled)
* Surfaces ............ CATPanel / CATCard (+ .cat-panel/.cat-card)
* Bubbles ............. .cat-bubble-user/.cat-bubble-assistant depth
                        refinements (additive over .cct-bubble-*)
* Error cards ......... error_card() — human-readable, non-blocking,
                        in-component error panel
* Responsiveness ...... RelayoutDebouncer (leading-edge + trailing
                        coalesce for resize storms)
* Lifecycle ........... TimerRegistry mixin + stop_timer() (every
                        background timer dies with its widget)

Colour/border/padding tokens are Textual `$variables` produced by
theme_css.css_variables() — this module only consumes them, so all
22 themes + light mode + AI-mode accents keep working unchanged.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

# --------------------------------------------------------------------------
# Responsive breakpoints (columns x rows of the live terminal).
#
# large  ......... w >= 120 — full three-pane + dashboard controls
# medium ......... 80 <= w < 120 — three-pane when practical, tighter
# small .......... 56 <= w < 80 — secondary panels collapse, chat first
# tiny ........... w < 56 or h < 18 — clean fallback, no overflow ever
# --------------------------------------------------------------------------
LARGE_MIN_WIDTH = 120
MEDIUM_MIN_WIDTH = 80
SMALL_MIN_WIDTH = 56
TINY_MAX_HEIGHT = 18

BP_LARGE = "large"
BP_MEDIUM = "medium"
BP_SMALL = "small"
BP_TINY = "tiny"


def breakpoint_for(width, height=None):
    """Classify the live terminal size. Pure function (unit-testable,
    no Textual needed). Never raises — garbage in maps to 'tiny',
    the safe fallback tier."""
    try:
        w = int(width or 0)
    except Exception:
        return BP_TINY
    try:
        h = int(height) if height is not None else 24
    except Exception:
        h = 24
    if w < SMALL_MIN_WIDTH or h < TINY_MAX_HEIGHT:
        return BP_TINY
    if w < MEDIUM_MIN_WIDTH:
        return BP_SMALL
    if w < LARGE_MIN_WIDTH:
        return BP_MEDIUM
    return BP_LARGE


# --------------------------------------------------------------------------
# CAT wordmark — responsive, single art source, never overflows.
#
# full ............ the classic 6-line block letters (calc_terminal.app.LOGO)
# compact ......... 3-line half-block variant for narrow panes
# minimal ......... plain "CAT" — always fits, zero layout risk
#
# Width budgets mirror the historical thresholds (full needs >= 34
# cols, compact >= 22) so existing screens keep their exact behavior
# when they delegate here.
# --------------------------------------------------------------------------
FULL_ART_MIN_WIDTH = 34
COMPACT_ART_MIN_WIDTH = 22

_FALLBACK_FULL_ART = [
    " ██████╗ █████╗ ████████╗",
    "██╔════╝██╔══██╗╚══██╔══╝",
    "██║     ███████║   ██║",
    "██║     ██╔══██║   ██║",
    "╚██████╗██║  ██║   ██║",
    " ╚═════╝╚═╝  ╚═╝   ╚═╝",
]

COMPACT_WORDMARK = [
    "▄▄▄▄ ▄▄▄▄▄ █████",
    "█    █▄▄█   █  ",
    "▀▀▀▀ █   █   █  ",
]

MINIMAL_WORDMARK = ["CAT"]


def full_wordmark():
    """The full 6-line CAT block letters. Single source of truth is
    calc_terminal.app.LOGO (what the classic terminal boots with);
    imported lazily — the backend app module is heavy and must not
    load at ui import time. Returns rstripped copies, never the live
    list, so callers cannot mutate the source."""
    try:
        from ..app import LOGO
        if LOGO:
            return [line.rstrip() for line in LOGO]
    except Exception:
        pass
    return list(_FALLBACK_FULL_ART)


def pick_wordmark(width):
    """Pick the largest wordmark variant that fits `width` columns.

    Returns (variant, lines) where variant is 'full' | 'compact' |
    'minimal'. Pure function, never raises, never overflows: unknown
    or tiny widths fall back to the 3-column minimal mark."""
    try:
        w = int(width or 0)
    except Exception:
        w = 0
    if w >= FULL_ART_MIN_WIDTH:
        return ("full", full_wordmark())
    if w >= COMPACT_ART_MIN_WIDTH:
        return ("compact", list(COMPACT_WORDMARK))
    return ("minimal", list(MINIMAL_WORDMARK))


def wordmark_markup(width):
    """Gradient-tinted Rich markup for the picked variant (same
    top-to-bottom mode-gradient family the composer badge uses;
    blended toward black in LIGHT mode to stay legible on white).
    The block NEVER exceeds `width`: callers render it inside a
    centered Static, so clipped/overflowing art is impossible."""
    try:
        from . import theme_css
        g_start, g_end = theme_css.gradient_hex()
        try:
            from .. import theme as _theme
            if _theme.is_light():
                from .empty_state import _darken
                g_start = _darken(g_start, 0.25)
                g_end = _darken(g_end, 0.25)
        except Exception:
            pass
        try:
            from .empty_state import _lerp_hex
        except Exception:
            _lerp_hex = None
        variant, lines = pick_wordmark(width)
        if variant == "minimal":
            return "[b]%sCAT[/]" % g_start
        n = max(1, len(lines) - 1)
        out = []
        for i, line in enumerate(lines):
            color = _lerp_hex(g_start, g_end, i / n) if _lerp_hex else g_start
            out.append("[%s b]%s[/]" % (color, line))
        return "\n".join(out)
    except Exception:
        return "[b]CAT[/]"


def error_card(title, lines, width=None):
    """Human-readable, non-blocking, in-component error panel:

        ┌─ CAT ──────────────────────────────┐
        │ ⚠ Provider unavailable             │
        │                                    │
        │ Backup provider is being used.     │
        └────────────────────────────────────┘

    `lines` is a string or list of strings (Rich markup allowed).
    Text is never clipped destructively: over-long lines are wrapped
    to `width` (default 46) instead of breaking the layout. Never
    raises — worst case returns a plain-text fallback."""
    try:
        from . import theme_css
        warning = theme_css.current_hex("warning")
        faint = theme_css.current_hex("text-faint")
        text = theme_css.current_hex("text")
    except Exception:
        warning, faint, text = "yellow", "grey", "white"
    try:
        w = max(20, int(width or 46))
    except Exception:
        w = 46
    try:
        if isinstance(lines, str):
            raw = lines.split("\n")
        else:
            raw = [str(x) for x in (lines or [])]
        body = []
        for ln in raw:
            while len(ln) > w:
                body.append(ln[:w])
                ln = ln[w:]
            body.append(ln)
        top = "┌─ CAT " + "─" * max(0, w - 7) + "┐"
        out = ["[%s]%s[/]" % (faint, top)]
        out.append("│ [%s]⚠ %s[/]%s│" % (
            warning, title, " " * max(0, w - len(title) - 4)))
        out.append("│" + " " * w + "│")
        for ln in body:
            out.append("│ [%s]%s[/]%s│" % (
                text, ln, " " * max(0, w - len(ln))))
        out.append("└" + "─" * w + "┘")
        return "\n".join(out)
    except Exception:
        try:
            return "CAT: %s — %s" % (title, lines)
        except Exception:
            return "CAT: error"


TEXTUAL_AVAILABLE = True
try:
    from textual.widgets import Button, Static
    from textual.containers import Vertical
except Exception:
    TEXTUAL_AVAILABLE = False


def stop_timer(handle):
    """Stop a set_interval/set_timer handle. Never raises; returns
    True when something was actually stopped."""
    try:
        if handle is not None:
            handle.stop()
            return True
    except Exception:
        pass
    return False


if TEXTUAL_AVAILABLE:

    DESIGN_SYSTEM_CSS = """
    /* ---- CAT design system: canonical 3D/skeuomorphic layer ---- */
    /* Consumes theme_css $variables only — all 22 themes, light   */
    /* mode and AI-mode accents keep working unchanged.            */
    .cat-btn {
        height: 3; min-height: 3; max-height: 3; padding: 0 2;
        min-width: 10;
        border: heavy;
        border-top: heavy $surface-highlight;
        border-left: heavy $surface-highlight;
        border-bottom: heavy $surface-dark;
        border-right: heavy $surface-dark;
        background: $surface-alt;
        color: $text;
        text-style: bold;
        content-align: center middle;
        transition: background 80ms, color 80ms, border 80ms, offset 80ms;
    }
    .cat-btn:hover {
        background: $accent 24%;
        border-top: heavy #ffffff;
        border-left: heavy $accent-highlight;
        border-bottom: heavy $accent;
        border-right: heavy $accent;
        color: $text;
        text-style: bold;
    }
    .cat-btn:focus {
        border-top: heavy #ffffff;
        border-left: heavy $accent-highlight;
        border-bottom: heavy $accent;
        border-right: heavy $accent;
        text-style: bold underline;
        background-tint: transparent;
    }
    .cat-btn:disabled { opacity: 0.45; text-style: not bold; }
    .cat-btn.cat-pressed {
        offset-y: 1;
        border-top: heavy $surface-dark;
        border-left: heavy $surface-dark;
        border-bottom: heavy $surface-highlight;
        border-right: heavy $surface-highlight;
        tint: $app-background 20%;
    }
    .cat-btn.-primary { background: $accent 55%; color: #ffffff; }
    .cat-btn.-danger { background: $error 45%; color: #ffffff; }
    .cat-btn-sm { height: 1; min-height: 1; max-height: 1; padding: 0 1; min-width: 6; }
    /* ---- elevated surfaces: panels read raised, cards float one  */
    /* level higher; hierarchy comes from edges, not decoration.    */
    .cat-panel {
        background: $surface;
        border: solid $border;
        border-top: solid $surface-highlight;
        border-left: solid $surface-highlight;
        padding: 1 2;
    }
    .cat-card {
        background: $surface-alt;
        border: solid $border;
        border-top: solid $surface-highlight;
        border-left: solid $surface-highlight;
        border-bottom: solid $surface-shadow;
        border-right: solid $surface-shadow;
        padding: 1 2;
    }
    .cat-elevated { border-top: solid $surface-highlight; border-left: solid $surface-highlight; }
    /* ---- chat bubbles: additive depth over .cct-bubble-* (the    */
    /* bubble's own mode-frozen inline style keeps winning where    */
    /* it matters; these rules only separate card from background). */
    .cat-bubble-user {
        border-right: heavy $accent 60%;
    }
    .cat-bubble-assistant {
        border-left: solid $surface-highlight;
        border-top: solid $surface-highlight;
    }
    .cat-codeblock {
        background: $surface-dark;
        border: solid $border;
        padding: 0 1;
    }
    .cat-input {
        background: $surface;
        border: solid $border;
        border-top: solid $surface-shadow;
        border-left: solid $surface-shadow;
        padding: 0 1;
    }
    .cat-input:focus {
        border: solid $accent;
    }
    .cat-wordmark { width: auto; text-align: center; }
    .cat-fallback {
        width: 1fr; height: auto; text-align: center;
        color: $text-muted; padding: 1 2;
    }
    .cat-error-card { width: auto; height: auto; color: $text; }
    /* ---- responsive tiers (set by WorkspaceShell._relayout): the */
    /* tiny tier strips secondary chrome so narrow terminals show  */
    /* a clean chat-first fallback instead of broken layout.       */
    .cat-bp-tiny #cct-chat-nav { display: none; }
    .cat-bp-tiny #cct-chips { display: none; }
    .cat-bp-tiny #cct-kbhints { display: none; }
    .cat-bp-tiny #cct-sidebar-expand-btn { display: none; }
    .cat-bp-tiny #cct-switch-files { display: none; }
    .cat-bp-small #cct-kbhints { display: none; }
    .cat-short #cct-kbhints { display: none; }
    """

    class TimerRegistry:
        """Mixin: every background timer a widget arms is tracked and
        dies with the widget. Usage: self.track_timer(self.set_interval(...))
        in on_mount/workers; on_unmount calls self.cancel_timers().
        Eliminates orphaned ticks after a screen/panel is destroyed."""

        def track_timer(self, handle):
            try:
                timers = getattr(self, "_tracked_timers", None)
                if timers is None:
                    self._tracked_timers = timers = []
                if handle is not None:
                    timers.append(handle)
            except Exception:
                pass
            return handle

        def cancel_timers(self):
            try:
                timers = getattr(self, "_tracked_timers", None) or []
                for handle in timers:
                    stop_timer(handle)
                self._tracked_timers = []
            except Exception:
                pass

    class RelayoutDebouncer:
        """Resize-storm guard: leading-edge immediate (first resize
        applies instantly, preserving interactive feel and any test
        that asserts synchronous layout), trailing-edge coalesced
        (a burst of N resizes costs 2 layouts, not N). Owns no
        widget state — the widget passes itself for set_timer."""

        def __init__(self, delay=0.06):
            self._delay = delay
            self._cooling = False
            self._pending = False
            self._latest = None
            self._timer = None

        def request(self, widget, callback):
            """Ask for `callback()` now-or-shortly. Never raises. The
            trailing catch-up always runs the LATEST requested
            callback, never a stale one."""
            try:
                self._latest = callback
                if not self._cooling:
                    self._cooling = True
                    try:
                        callback()
                    except Exception:
                        pass
                    stop_timer(self._timer)
                    try:
                        self._timer = widget.set_timer(
                            self._delay, lambda: self._settle(widget))
                    except Exception:
                        self._cooling = False
                else:
                    self._pending = True
            except Exception:
                try:
                    callback()
                except Exception:
                    pass

        def _settle(self, widget):
            self._timer = None
            try:
                if self._pending:
                    self._pending = False
                    latest = self._latest
                    try:
                        if latest is not None:
                            latest()
                    except Exception:
                        pass
                    try:
                        self._timer = widget.set_timer(
                            self._delay, lambda: self._settle(widget))
                    except Exception:
                        self._cooling = False
                else:
                    self._cooling = False
            except Exception:
                self._cooling = False

        def cancel(self):
            self._cooling = False
            self._pending = False
            self._latest = None
            stop_timer(self._timer)
            self._timer = None

    class CATButton(Button, TimerRegistry):
        """Canonical CAT button: raised 3D surface, hover lift, focus
        ring, dimmed disabled, and a brief depressed flash on press
        (Textual exposes :hover/:focus/:disabled natively; the
        pressed instant is rendered via .cat-pressed because terminal
        presses are too fast for a pseudo-class to read clearly).

        Drop-in for textual Button — same constructor/contract, only
        adds the CAT visual system. Never blocks input: the flash is
        a 120ms class toggle, never an animation loop."""

        def __init__(self, *args, **kwargs):
            classes = kwargs.get("classes", "")
            if "cat-btn" not in str(classes).split():
                kwargs["classes"] = (str(classes) + " cat-btn").strip()
            super().__init__(*args, **kwargs)
            self._press_flash = None

        def press(self):
            """Flash the depressed state, then behave exactly like a
            normal Button press (message order unchanged)."""
            try:
                self.add_class("cat-pressed")
                stop_timer(self._press_flash)
                self._press_flash = self.set_timer(0.12, self._clear_press_flash)
            except Exception:
                pass
            return super().press()

        def _clear_press_flash(self):
            try:
                self.remove_class("cat-pressed")
            except Exception:
                pass
            self._press_flash = None

        def on_unmount(self):
            stop_timer(self._press_flash)
            self._press_flash = None
            self.cancel_timers()

    class CATPanel(Vertical):
        """Slightly elevated panel surface (.cat-panel). Layout-only:
        no timers, no behavior, nothing to leak."""

        def __init__(self, *args, **kwargs):
            classes = kwargs.get("classes", "")
            if "cat-panel" not in str(classes).split():
                kwargs["classes"] = (str(classes) + " cat-panel").strip()
            super().__init__(*args, **kwargs)

    class CATCard(Vertical):
        """One level above CATPanel (.cat-card) — quick actions,
        status blocks, dashboard tiles. Layout-only."""

        def __init__(self, *args, **kwargs):
            classes = kwargs.get("classes", "")
            if "cat-card" not in str(classes).split():
                kwargs["classes"] = (str(classes) + " cat-card").strip()
            super().__init__(*args, **kwargs)

    class CATWordmark(Static):
        """Responsive CAT wordmark: full block letters on wide panes,
        compact half-block on narrow ones, plain 'CAT' where nothing
        else fits. refresh_for_width() is idempotent — only repaints
        when the variant actually changes, so resize storms cost one
        update, not one per event. Can never overflow: the minimal
        variant is 3 columns wide."""

        def __init__(self, width=0, id=None):
            super().__init__("", id=id, classes="cat-wordmark")
            self._variant = None
            if width:
                self.refresh_for_width(width)

        def refresh_for_width(self, width):
            """Returns the active variant ('full'|'compact'|'minimal').
            Never raises."""
            try:
                variant, _lines = pick_wordmark(width)
            except Exception:
                variant = "minimal"
            try:
                if variant != self._variant:
                    self._variant = variant
                    self.update(wordmark_markup(width))
            except Exception:
                pass
            return self._variant

        @property
        def variant(self):
            return self._variant or "minimal"

else:
    # Textual unavailable (backend-only contexts): keep the pure
    # helpers importable; widget names exist as None like elsewhere.
    DESIGN_SYSTEM_CSS = ""
    TimerRegistry = object
    RelayoutDebouncer = object
    CATButton = None
    CATPanel = None
    CATCard = None
    CATWordmark = None
