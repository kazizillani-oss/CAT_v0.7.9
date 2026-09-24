"""
CCT UI theme bridge — theme.py is the single palette source; this module
is the ONLY place that turns it into Textual CSS variables. There is no
second, hand-authored palette here (that was the old composer.py's
COMPOSER_CSS bug — a flat black-and-blue palette that drifted from the
rest of the app's Tokyo Night colors). Every color a Textual widget
uses comes from theme.py's module-level RGB tuples via `css_variables()`
below, so `/theme light` restyles the primary UI exactly the same way
it already restyles every print()-based panel.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

from .. import theme
from .. import ai_modes


def _patch_rich_divide_line():
    """Defend against Rich/Textual ValueError: range() arg 3 must not be zero
    when widgets are rendered with width <= line_pad * 2."""
    try:
        import rich._wrap
        import rich.cells

        orig_divide_line = getattr(rich._wrap, "_cat_orig_divide_line", None)
        if orig_divide_line is None:
            orig_divide_line = rich._wrap.divide_line
            rich._wrap._cat_orig_divide_line = orig_divide_line

            def safe_divide_line(text, width, fold=True):
                if width <= 0:
                    return []
                return orig_divide_line(text, width, fold=fold)

            rich._wrap.divide_line = safe_divide_line

        orig_chop_cells = getattr(rich.cells, "_cat_orig_chop_cells", None)
        if orig_chop_cells is None:
            orig_chop_cells = rich.cells.chop_cells
            rich.cells._cat_orig_chop_cells = orig_chop_cells

            def safe_chop_cells(text, width, unicode_version="auto"):
                if width <= 0:
                    return [text] if text else []
                return orig_chop_cells(text, width, unicode_version=unicode_version)

            rich.cells.chop_cells = safe_chop_cells

        try:
            import textual.content
            if hasattr(textual.content, "divide_line"):
                textual.content.divide_line = rich._wrap.divide_line
        except Exception:
            pass
    except Exception:
        pass


_patch_rich_divide_line()


def _hex(rgb):
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"


# Textual CSS variable name -> theme.py attribute name. One row per
# variable; add a color here, not a second copy of its value anywhere
# else. `panel`/`element`/`border*` reuse the OC_* set theme.py already
# maintains for exactly this "OpenCode-style" surface (dark AND light
# variants already defined there — see theme.py's _THEMES dict).
_VARIABLE_SOURCE = {
    "surface": "OC_BG_PANEL",
    "surface-alt": "OC_BG_ELEMENT",
    "panel": "OC_BG_PANEL",
    "panel-alt": "OC_BG_ELEMENT",
    "border": "OC_BORDER",
    "border-active": "OC_BORDER_ACTIVE",
    "accent": "OC_PRIMARY",
    "accent-secondary": "OC_SECONDARY",
    "accent-highlight": "OC_ACCENT",
    "text": "TEXT",
    "text-muted": "DIM",
    "text-faint": "FAINT",
    "success": "GREEN",
    "warning": "ORANGE",
    "error": "RED",
}


_CSS_VAR_CACHE = {}
_LAST_THEME_MODE = None


def invalidate_css_cache():
    global _LAST_THEME_MODE, _CSS_VAR_CACHE
    _LAST_THEME_MODE = None
    _CSS_VAR_CACHE.clear()


def bevel_colors(hex_color):
    """Computes a lighter top-left highlight and a darker bottom-right shadow from a hex color."""
    try:
        c = str(hex_color).lstrip("#")
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        r = int(c[0:2], 16)
        g = int(c[2:4], 16)
        b = int(c[4:6], 16)
        # Highlight: blend +35% towards white
        hr = min(255, int(r + (255 - r) * 0.35))
        hg = min(255, int(g + (255 - g) * 0.35))
        hb = min(255, int(b + (255 - b) * 0.35))
        # Shadow: blend -45% towards dark black/navy
        sr = max(0, int(r * 0.45))
        sg = max(0, int(g * 0.45))
        sb = max(0, int(b * 0.45))
        return f"#{hr:02x}{hg:02x}{hb:02x}", f"#{sr:02x}{sg:02x}{sb:02x}"
    except Exception:
        return hex_color or "#38bdf8", hex_color or "#0f172a"


def css_variables():
    """Returns {css_variable_name: '#rrggbb'} built from theme.py's
    CURRENT palette (dark or light — whichever `theme.set_theme()` last
    selected). Pass this from `CCTApp.get_css_variables()`.

    On top of the dark/light base palette, the active AI mode
    (ai_modes.current_mode() — spec section 3) repaints `accent` and
    `accent-highlight` with that mode's color. This is the one thing
    that makes "Agent mode changes... accent color / borders / status
    indicators" (and the same for Build/Plan) true everywhere those two
    variables are already used (BrandHeader's mark, focused-panel
    borders, footer badges) — without a second, mode-specific palette
    to hand-maintain alongside theme.py's dark/light one.

    v0.7.9.0 LIGHT-MODE AUDIT: Textual's built-in defaults for a whole
    family of component variables are DARK-MODE values (#E0E0E0 text on
    buttons, reverse-video button focus, pale selection washes). In
    dark they're invisible because our own rules override most of them;
    in light they leak through as washed-out / glowing / unreadable
    highlights. When the active theme is light we now emit explicit,
    contrast-correct values for that family — dark emits nothing, so
    dark mode stays byte-for-byte what it was."""
    global _LAST_THEME_MODE, _CSS_VAR_CACHE
    cur_theme = getattr(theme, "CURRENT_THEME_NAME", "tokyo-night")
    cur_mode = ai_modes.current_mode() if hasattr(ai_modes, "current_mode") else "notebook"
    current_key = (cur_theme, cur_mode)
    if _LAST_THEME_MODE == current_key and _CSS_VAR_CACHE:
        return _CSS_VAR_CACHE

    out = {}
    for var_name, attr_name in _VARIABLE_SOURCE.items():
        rgb = getattr(theme, attr_name, None)
        if rgb is not None:
            out[var_name] = _hex(rgb)
    bg = theme._TERMINAL_BG.get(theme.CURRENT_THEME_NAME, (0, 0, 0))
    out["app-background"] = _hex(bg)
    out["background"] = out["app-background"]
    mode_accent = ai_modes.accent_hex()
    out["accent"] = mode_accent
    hi, sh = bevel_colors(mode_accent)
    out["accent-highlight"] = hi
    out["accent-shadow"] = sh
    out["border-active"] = mode_accent
    s_alt_rgb = getattr(theme, "OC_BG_ELEMENT", (30, 30, 46))
    s_rgb = getattr(theme, "OC_BG_PANEL", (24, 24, 37))
    out["surface-highlight"] = blend_hex(s_alt_rgb, (255, 255, 255), 0.18)
    out["surface-shadow"] = blend_hex(s_rgb, (0, 0, 0), 0.45)
    out["surface-dark"] = blend_hex(s_rgb, (0, 0, 0), 0.35)
    out["surface-active"] = blend_hex(s_alt_rgb, (255, 255, 255), 0.08)
    out["surface-light"] = out["surface-highlight"]
    out["accent-light"] = out["accent-highlight"]
    out["accent-muted"] = out["accent-shadow"]
    out["accent-dark"] = out["accent-shadow"]
    # Standard Textual core variable fallbacks (for Switch, DataTable, etc.)
    out["foreground"] = out.get("text", "#e0e0e0")
    out["primary"] = out.get("accent", "#38bdf8")
    out["secondary"] = out.get("accent-secondary", "#818cf8")
    out["border-blurred"] = out.get("border", "#30363d")
    out["screen-selection-background"] = out.get("accent", "#38bdf8") + "33"
    out["screen-selection-foreground"] = "#ffffff"

    # v0.7.8 FEATURE 3 (Mode Gradients): the active mode's two-stop
    # gradient, exposed for glass/shimmer accents (composer badge,
    # welcome hero, header mark). `accent` stays the flat solid color
    # for borders/bubbles; the gradient is used where a subtle wash is
    # wanted — never heavy.
    g_start, g_end = ai_modes.gradient()
    out["accent-gradient-start"] = g_start
    out["accent-gradient-end"] = g_end

    # v0.7.9.5 THEME CATALOG: every component-level variable below is now
    # derived from the ACTIVE THEME OBJECT (theme.get_theme_obj()) instead
    # of hardcoded GitHub-Light hexes, and emitted whenever the theme is
    # light. Dark themes keep Textual's own dark-mode defaults (unchanged
    # behavior from the v0.7.9.0 audit). Because each theme's schema
    # carries tuned selection/cursor/heading colors, ANY of the 22 themes
    # gets correct, contrast-checked chrome — no theme can inherit another
    # theme's colors anymore.
    if theme.is_light():
        t = theme.get_theme_obj()
        text_hex = t.hex("text")
        muted_hex = t.hex("text_muted")
        blue_hex = t.hex("accent_alt")
        cursor_bg = blend_hex(t.text, t.background, 0.12)
        out.update({
            # Buttons: Textual's default label color is #E0E0E0 (near-
            # white), which vanishes on light surfaces.
            "button-foreground": text_hex,
            # Focus: replace the default `b reverse` full-block invert
            # with plain bold — the active border already marks focus.
            "button-focus-text-style": "bold",
            # Text/inputs: subtle, readable selection — a soft solid
            # wash with dark text, never a bright glowing block, and it
            # cannot bleed into unselected neighbors.
            "input-selection-background": t.hex("selection_background"),
            "input-selection-foreground": t.hex("selection_text"),
            "screen-selection-background": t.hex("selection_background"),
            "screen-selection-foreground": t.hex("selection_text"),
            # Cursors: clearly visible without being loud.
            "input-cursor-background": cursor_bg,
            "input-cursor-foreground": t.hex("background"),
            "block-cursor-background": blue_hex,
            "block-cursor-foreground": "auto 87%",
            "block-cursor-blurred-background": blue_hex + "44",
            "block-cursor-blurred-foreground": text_hex,
            # Footer key caps: amber readable on light surfaces.
            "footer-key-foreground": t.hex("warning"),
            # Blurred borders stop assuming a near-black chrome color.
            "border-blurred": t.hex("border"),
            # Markdown headings in assistant bubbles: darker, WCAG-safe.
            "markdown-h1-color": blue_hex,
            "markdown-h2-color": blue_hex,
            "markdown-h3-color": blue_hex,
            "markdown-h4-color": text_hex,
            "markdown-h5-color": text_hex,
            # In light mode, surface tones must be soft and adaptive, never dark/black
            "surface-highlight": blend_hex(t.background, (255, 255, 255), 0.60),
            "accent-highlight": blue_hex,
            "accent-light": blue_hex,
            "surface-shadow": t.hex("border"),
            "surface-dark": t.hex("border"),
            "surface-active": blend_hex(t.background, t.text, 0.08),
            "surface-alt": blend_hex(t.background, t.text, 0.04),
        })
    _LAST_THEME_MODE = current_key
    _CSS_VAR_CACHE = out
    return out


def blend_hex(a, b, t):
    """Blend two RGB tuples (t=0 → a, t=1 → b) into a '#rrggbb' string."""
    r1, g1, b1 = a
    r2, g2, b2 = b
    return "#{:02x}{:02x}{:02x}".format(
        int(round(r1 + (r2 - r1) * t)),
        int(round(g1 + (g2 - g1) * t)),
        int(round(b1 + (b2 - b1) * t)))


def gradient_hex(key=None):
    """Direct (start_hex, end_hex) lookup for the active (or named) AI
    mode's gradient, for Rich-markup callers outside CSS."""
    return ai_modes.gradient(key)


def current_hex(role):
    """One-off lookup for widgets that need a raw hex string outside CSS
    var resolution (e.g. an f-string building Rich markup). `role` is
    one of the keys in `_VARIABLE_SOURCE` above, or 'app-background'."""
    return css_variables().get(role, "#888888")


# Shared layout/spacing rules every ui/ widget file composes with. Pure
# structure — no literal colors — every color reference below is a Textual
# `$variable` resolved at runtime from css_variables(), so switching
# `/theme light` <-> dark restyles this without touching a single rule here.
BASE_CSS = """
Screen { background: $app-background; }

.cct-panel {
    background: $surface;
    border: heavy;
    border-top: heavy $surface-highlight;
    border-left: heavy $surface-highlight;
    border-bottom: heavy $surface-dark;
    border-right: heavy $surface-dark;
    tint: $surface-dark 6%;
    transition: background 80ms;
}

.cct-panel:focus-within {
    border: heavy;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy $border-active;
    border-right: heavy $border-active;
    tint: $accent 4%;
}

.cct-card-3d, .cct-panel-3d {
    background: $surface;
    border: heavy;
    border-top: heavy $surface-highlight;
    border-left: heavy $surface-highlight;
    border-bottom: heavy $surface-dark;
    border-right: heavy $surface-dark;
    tint: $surface-dark 5%;
    padding: 1 2;
}

.cct-panel-3d-raised {
    background: $surface;
    border: heavy;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy $surface-dark;
    border-right: heavy $surface-dark;
    tint: $surface-highlight 6%;
    padding: 1 2;
}

.cct-card-3d-inset {
    background: $app-background;
    border: heavy;
    border-top: heavy $surface-shadow;
    border-left: heavy $surface-shadow;
    border-bottom: heavy $surface-highlight;
    border-right: heavy $surface-highlight;
    tint: $surface-dark 10%;
    padding: 1 2;
}

.cct-dashboard {
    background: $surface;
    border: heavy;
    border-top: heavy $surface-highlight;
    border-left: heavy $surface-highlight;
    border-bottom: heavy $surface-dark;
    border-right: heavy $surface-dark;
    tint: $surface-dark 4%;
    overflow-y: auto;
    height: auto;
    max-height: 100%;
}

.cct-dashboard-header {
    background: $surface-alt;
    border-bottom: heavy $surface-dark;
    tint: $surface-highlight 5%;
    padding: 1 2;
}

.cct-text { color: $text; }
.cct-text-muted { color: $text-muted; }
.cct-text-faint { color: $text-faint; }
.cct-success { color: $success; }
.cct-warning { color: $warning; }
.cct-error { color: $error; }

/* Tooltip: themed, 3D raised border with legible contrast (fixes black-box hover bug) */
Tooltip {
    background: $surface-alt;
    color: $text;
    border: heavy $border-active;
    padding: 0 1;
    text-style: none;
    max-width: 60;
    opacity: 0.98;
}

/* Toast: themed 3D raised notification card with beveled lighting */
Toast, Toast.-information, Toast.-warning, Toast.-error {
    background: $surface;
    color: $text;
    border: heavy;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy $surface-dark;
    border-right: heavy $surface-dark;
    tint: $surface-highlight 6%;
    padding: 1 2;
    transition: opacity 200ms;
}
Toast.-warning {
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy $warning;
    border-right: heavy $warning;
    tint: $warning 5%;
}
Toast.-error {
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy $error;
    border-right: heavy $error;
    tint: $error 5%;
}
Toast.-information {
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy $accent-shadow;
    border-right: heavy $accent-shadow;
    tint: $accent 4%;
}

/* ==================================================== v0.7.9.6 ======
   CAT 3D SKEUOMORPHIC DESIGN SYSTEM
   Strong, physical-looking 3D buttons + cards with a real bevel (bright
   top-left highlight + dark bottom-right shadow), a soft glow on hover,
   and a satisfying press-down on activation. Every `Button` in the
   app picks this up by default — no per-widget restyling needed —
   so the whole TUI looks and feels like one cohesive piece of
   hardware instead of a flat terminal skin.

   The trick is a *double* border: an outer `border-top/left` in the
   light highlight color and an outer `border-bottom/right` in the
   dark shadow color. Textual's per-side `border-top/left/right/bottom`
   shorthand draws four independent edges in four colors, so the
   button reads as physically raised. A 1-step `offset-y: -1` on hover
   "lifts" the button (already inside Textual's render model); the
   press state inverts the bevel and drops `offset-y: 1` for the
   physical press feel.

   This block is the *only* authority on Button visuals — every later
   Button rule (`.cct-btn`, `.cct-btn-primary`, `.cct-dash-action`,
   `.cct-btn-3d-skeu`, the modal buttons, the icon buttons) inherits
   from here so restyling the whole system is a one-line change.
   ------------------------------------------------------------------ */
.cct-btn-3d-skeu,
.cct-btn-3d-skeu:ansi.-style-default,
.cct-btn-3d-skeu:ansi.-style-flat,
Screen .cct-btn-3d-skeu,
Button.cct-btn-3d-skeu,
Button.cct-btn-3d-skeu.-style-default,
Button.cct-btn-3d-skeu:ansi.-style-default,
Button.cct-btn-3d-skeu:ansi.-style-flat,
Screen Button.cct-btn-3d-skeu {
    /* REAL 3D bevel: 4 different border edges drawn in 4 colors */
    height: 3; min-height: 3; max-height: 3;
    padding: 0 2;
    min-width: 10;
    background: $surface-alt;
    color: $text;
    text-style: bold;
    content-align: center middle;
    border: tall;
    /* top + left = light coming from above-left (highlight) */
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    /* bottom + right = shadow falling away */
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    /* subtle inner sheen — visible on the body */
    tint: $surface-highlight 8%;
    /* crisp motion */
    transition: background 90ms, offset 70ms, tint 120ms;
}

.cct-btn-3d-skeu:hover,
Button.cct-btn-3d-skeu:hover,
Screen Button.cct-btn-3d-skeu:hover {
    background: $accent 24%;
    color: #ffffff;
    text-style: bold;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent;
    border-right: tall $accent;
    tint: $accent 12%;
}

.cct-btn-3d-skeu:focus,
Button.cct-btn-3d-skeu:focus,
Screen Button.cct-btn-3d-skeu:focus {
    background-tint: transparent;
    background: $accent 14%;
    color: #ffffff;
    text-style: bold;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent;
    border-right: tall $accent;
    tint: $accent 8%;
}

.cct-btn-3d-skeu.-active,
Button.cct-btn-3d-skeu.-active,
Screen Button.cct-btn-3d-skeu.-active {
    background: $accent;
    color: #ffffff;
    text-style: bold;
    border: tall;
    border-top: tall $accent-shadow;
    border-left: tall $accent-shadow;
    border-bottom: tall #ffffff;
    border-right: tall #ffffff;
    tint: $app-background 22%;
}

.cct-btn-3d-skeu:disabled,
Button.cct-btn-3d-skeu:disabled,
Screen Button.cct-btn-3d-skeu:disabled {
    opacity: 0.50;
    text-style: not bold;
    background: $surface;
    color: $text-muted;
    border: tall;
    border-top: tall $surface-shadow;
    border-left: tall $surface-shadow;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
    tint: $surface-dark 18%;
}

/* ---- v0.7.9.6: dashboard quick actions — heavier bevel + glow on
   hover so they read as the primary call-to-action rather than just
   another row of buttons. Replaces the old .cct-dash-action block. */
Button.cct-dash-action,
.cct-dash-action,
Button.cct-dash-action.-style-default,
Button.cct-dash-action:ansi.-style-default,
Button.cct-dash-action:ansi.-style-flat,
Screen Button.cct-dash-action {
    height: 3; min-height: 3; max-height: 3;
    padding: 0;
    min-width: 14; max-width: 26; width: 1fr;
    margin: 0 1;
    color: #ffffff;
    text-style: bold;
    content-align: center middle;
    /* DOUBLE BEVEL: outer light, inner darker — physical "raised" keycap */
    background: $surface-alt;
    border: tall;
    border-top: tall #38bdf8;
    border-left: tall #38bdf8;
    border-bottom: tall $accent-shadow;
    border-right: tall $accent-shadow;
    tint: $accent 10%;
    transition: background 90ms, tint 140ms;
}

Button.cct-dash-action:hover,
Screen Button.cct-dash-action:hover {
    background: $accent;
    color: #ffffff;
    text-style: bold;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall #ffffff;
    border-bottom: tall $accent-highlight;
    border-right: tall $accent-highlight;
    tint: $accent 18%;
}

Button.cct-dash-action:focus,
Screen Button.cct-dash-action:focus {
    background: $accent 18%;
    color: #ffffff;
    text-style: bold;
    background-tint: transparent;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall #ffffff;
    border-bottom: tall $accent-highlight;
    border-right: tall $accent-highlight;
    tint: $accent 12%;
}

Button.cct-dash-action.-active,
Screen Button.cct-dash-action.-active {
    background: $accent-shadow;
    color: #ffffff;
    text-style: bold;
    border: tall;
    border-top: tall $accent-shadow;
    border-left: tall $accent-shadow;
    border-bottom: tall #ffffff;
    border-right: tall #ffffff;
    tint: $app-background 22%;
}

Button.cct-dash-action:disabled,
Screen Button.cct-dash-action:disabled {
    opacity: 0.45;
    text-style: not bold;
    background: $surface;
    color: $text-muted;
    border: tall;
    border-top: tall $surface-shadow;
    border-left: tall $surface-shadow;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
}

/* ---- v0.7.9.6: 3D SKEU DASHBOARD CARDS — the dashboard's three
   columns render through this rule. Two-tone border = physical card
   sitting on the dashboard surface. On hover a faint accent glow
   appears so the user can tell where focus lives. */
.cct-dash-card-3d,
.cct-panel-3d-card {
    background: $surface;
    color: $text;
    padding: 1 2;
    margin: 0 1 1 1;
    border: tall;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    tint: $surface-highlight 5%;
    transition: background 100ms, tint 120ms;
}

.cct-dash-card-3d:hover,
.cct-panel-3d-card:hover,
.cct-dash-card-3d:focus-within,
.cct-panel-3d-card:focus-within {
    background: $surface;
    tint: $accent 5%;
    border: tall;
    border-top: tall $accent-highlight;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent-shadow;
    border-right: tall $accent-shadow;
}

/* v0.7.9.6: dashboard header bar (the title row above the columns) —
   inset look with light coming from below. */
.cct-dash-header-3d {
    background: $surface-alt;
    border: tall;
    border-top: tall $surface-shadow;
    border-left: tall $surface-shadow;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
    tint: $accent 5%;
    padding: 1 2;
}

/* v0.7.9.6: 3D SKEU INPUTS — sunken text inputs. Top/left dark
   (inside the panel), bottom/right light (rim of the panel). */
.cct-input-3d-skeu {
    background: $app-background;
    color: $text;
    border: tall;
    border-top: tall $surface-shadow;
    border-left: tall $surface-shadow;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
    padding: 0 1;
    text-style: none;
    transition: background 90ms;
}

.cct-input-3d-skeu:focus {
    background: $app-background;
    border: tall;
    border-top: tall $surface-shadow;
    border-left: tall $surface-shadow;
    border-bottom: tall $accent-highlight;
    border-right: tall $accent-highlight;
    color: $text;
    text-style: none;
}

/* ==================================================== v0.7.8.1 ======
   Shared DESIGN SYSTEM — button + popup conventions every dialog in
   ui/ follows, so no panel ever ships its own ad-hoc sizes again.
   ------------------------------------------------------------------ */

/* ---- Button system (v0.7.8.61): ONE shared definition for every
   button in the app. Bare `Button` rules override Textual's own
   default "hkey/tall" half-block design (▔▁ rails / ▊▔▎ boxes) at
   equal specificity — app CSS is merged after widget CSS, so the tie
   resolves to this block. Variants drop in via Textual's emitted
   `.-primary` / `.-error` / `.-success` classes. The clickable region,
   border, background, and text all share the same 3-cell footprint:
   no button-specific positioning, spacing hacks, or fractional sizes.

   v0.7.8.61 changes (washed-out / "highlighted" button look):
   - `text-style: not bold` — Textual's default Button CSS force-bolds
     every label (`Button.-style-default { text-style: bold }`), which
     made ALL buttons read as selected/highlighted. The base resets it;
     focus and the primary variant re-bold explicitly.
   - `background: $surface-alt` — the old `$surface` background equals
     the panel color, so buttons melted into their cards. `$surface-alt`
     sits one step lighter and reads as a raised control everywhere.
   - hover: accent wash + active border; focus: active border + bold,
     with Textual's default `background-tint` cleared so focus never
     smears the button.
   - `.-active` (pressed): the button sinks one row (`offset-y: 1`) and
     darkens via `tint` — a real press, not a palette swap.
   - disabled buttons dim without losing their label.
   The `Button:ansi.-style-default/-style-flat` duplicates keep this
   block winning over Textual's widget defaults even in setups where
   the `:ansi` pseudo-class matches. ----

   v0.7.9.6: Every bare `Button` in the app now inherits the full
   3D skeuomorphic bevel — taller borders, real lift on hover, real
   press on activation, sunken disabled state. The earlier 'heavy'
   borders read more like outlines; `tall` borders give the buttons
   a 2-cell-thick bevel so they look physically raised off the
   panel surface, which is the whole point of skeuomorphism. */
Button, Button:ansi.-style-default, Button:ansi.-style-flat, .cct-btn {
    height: 3; min-height: 3; max-height: 3; padding: 0 2;
    min-width: 10;
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
    transition: background 90ms, offset 70ms, tint 120ms;
}
Button:hover, .cct-btn:hover {
    background: $accent 26%;
    color: #ffffff;
    text-style: bold;
    offset: 0 0;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent;
    border-right: tall $accent;
    tint: $accent 10%;
}
Button:focus, .cct-btn:focus {
    color: #ffffff;
    text-style: bold;
    background-tint: transparent;
    background: $accent 14%;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent;
    border-right: tall $accent;
    tint: $accent 7%;
}
Button:disabled, .cct-btn:disabled {
    opacity: 0.50; text-style: not bold;
    background: $surface;
    color: $text-muted;
    border: tall;
    border-top: tall $surface-shadow;
    border-left: tall $surface-shadow;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
    tint: $surface-dark 18%;
    offset: 0 0;
}
Button.-active, .cct-btn.-active {
    offset: 0 0;
    color: #ffffff;
    background: $accent;
    text-style: bold;
    border: tall;
    border-top: tall $accent-shadow;
    border-left: tall $accent-shadow;
    border-bottom: tall #ffffff;
    border-right: tall #ffffff;
    tint: $app-background 22%;
}
.chats-filter-btn.-active,
Screen .chats-filter-btn.-active {
    offset-y: 0;
    offset-x: 0;
    offset: 0 0;
}
/* v0.7.9.6: kept identical to the skeu block above so theme-shape
   variants (rounded/pill/square/ghost/outlined/filled/minimal) and
   older widget lookups still resolve to the same 3D skeu look. */
Button.cct-dash-action, .cct-dash-action,
Button.cct-dash-action.-style-default,
Button.cct-dash-action:ansi.-style-default,
Button.cct-dash-action:ansi.-style-flat,
Screen Button.cct-dash-action {
    height: 3; min-height: 3; max-height: 3;
    padding: 0;
    min-width: 14; max-width: 26; width: 1fr; margin: 0 1;
    background: $surface-alt;
    color: #ffffff;
    text-style: bold;
    content-align: center middle;
    border: tall;
    border-top: tall #38bdf8;
    border-left: tall #38bdf8;
    border-bottom: tall $accent-shadow;
    border-right: tall $accent-shadow;
    tint: $accent 10%;
    transition: background 90ms, offset 70ms, tint 140ms;
}
Button.cct-dash-action:hover, .cct-dash-action:hover,
Screen Button.cct-dash-action:hover {
    background: $accent;
    color: #ffffff;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall #ffffff;
    border-bottom: tall $accent-highlight;
    border-right: tall $accent-highlight;
    text-style: bold;
    offset: 0 0;
    tint: $accent 18%;
}
Button.cct-dash-action:focus, .cct-dash-action:focus,
Screen Button.cct-dash-action:focus {
    background-tint: transparent;
    background: $accent 18%;
    color: #ffffff;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall #ffffff;
    border-bottom: tall $accent-highlight;
    border-right: tall $accent-highlight;
    text-style: bold;
    tint: $accent 12%;
    offset: 0 0;
}
Button.cct-dash-action.-active, .cct-dash-action.-active,
Screen Button.cct-dash-action.-active {
    offset: 0 0;
    background: $accent-shadow;
    color: #ffffff;
    border: tall;
    border-top: tall $accent-shadow;
    border-left: tall $accent-shadow;
    border-bottom: tall #ffffff;
    border-right: tall #ffffff;
    text-style: bold;
    tint: $app-background 22%;
}

/* v0.7.9.6: also upgraded to the strong-tall 3D skeu metrics so any
   `Button.cct-btn-3d` (without the `-skeu` suffix) also picks up the
   new bevel + press-down affordance. Identical metrics to the primary
   Button rule — both classes are interchangeable from a visual
   standpoint. */
.cct-btn-3d,
Button.cct-btn-3d {
    height: 3; min-height: 3; max-height: 3;
    padding: 0 2;
    min-width: 10;
    background: $surface-alt;
    color: $text;
    text-style: bold;
    content-align: center middle;
    border: tall;
    border-top: tall $accent-highlight;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent-shadow;
    border-right: tall $accent-shadow;
    tint: $accent 6%;
    transition: background 90ms, offset 70ms, tint 120ms;
}
.cct-btn-3d:hover,
Button.cct-btn-3d:hover {
    background: $accent 28%;
    color: #ffffff;
    text-style: bold;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall #ffffff;
    border-bottom: tall $accent;
    border-right: tall $accent;
    offset: 0 0;
    tint: $accent 12%;
}
.cct-btn-3d:focus,
Button.cct-btn-3d:focus {
    color: #ffffff;
    text-style: bold;
    background-tint: transparent;
    background: $accent 16%;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall #ffffff;
    border-bottom: tall $accent-highlight;
    border-right: tall $accent-highlight;
    tint: $accent 8%;
}
.cct-btn-3d.-active,
Button.cct-btn-3d.-active {
    offset: 0 0;
    background: $accent;
    color: #ffffff;
    text-style: bold;
    border: tall;
    border-top: tall $accent-shadow;
    border-left: tall $accent-shadow;
    border-bottom: tall #ffffff;
    border-right: tall #ffffff;
    tint: $app-background 22%;
}

/* Universal 3D Skeuomorphic Button Keycaps */
Button.cct-btn, Button.cct-modal-btn, Button.cct-btn-sm, Button.cct-btn-primary {
    border: tall;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-shadow;
    border-right: tall $surface-shadow;
    background: $surface;
    color: $text;
    text-style: bold;
    tint: $surface-highlight 4%;
    transition: background 80ms, offset 60ms;
}
Button.cct-btn:hover, Button.cct-modal-btn:hover, Button.cct-btn-sm:hover {
    border: tall;
    border-top: tall $accent-highlight;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent-shadow;
    border-right: tall $accent-shadow;
    background: $surface-alt;
    color: #ffffff;
}
Button.cct-btn:focus, Button.cct-modal-btn:focus, Button.cct-btn-sm:focus {
    border: tall;
    border-top: tall $accent-highlight;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent-shadow;
    border-right: tall $accent-shadow;
    background: $surface-alt;
    color: #ffffff;
}
Button.cct-btn.-active, Button.cct-modal-btn.-active, Button.cct-btn-sm.-active {
    offset: 0 0;
    border: tall;
    border-top: tall $surface-shadow;
    border-left: tall $surface-shadow;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
    background: $surface-dark;
    tint: $app-background 18%;
}
Button.cct-btn-primary, Button.-primary {
    border: tall;
    border-top: tall $accent-highlight;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent-shadow;
    border-right: tall $accent-shadow;
    background: $accent;
    color: #ffffff;
}
Button.cct-btn-primary:hover, Button.-primary:hover {
    background: $accent-highlight;
    color: #ffffff;
}
Button.cct-btn-primary.-active, Button.-primary.-active {
    offset: 0 0;
    border-top: tall $accent-shadow;
    border-left: tall $accent-shadow;
    border-bottom: tall $accent-highlight;
    border-right: tall $accent-highlight;
    background: $accent-shadow;
}

/* Universal 3D Skeuomorphic Sunken Tray Inputs / Search Bars */
Input.cct-search-input, .cct-input-3d, #search-input, #model-search, #pc-search Input, #ext-search Input, #cust-search Input, #mcp-search Input {
    border: tall;
    border-top: tall $surface-shadow;
    border-left: tall $surface-shadow;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
    background: $app-background;
    color: $text;
    transition: background 80ms;
}
Input.cct-search-input:focus, .cct-input-3d:focus, #search-input:focus, #model-search:focus, #pc-search Input:focus, #ext-search Input:focus, #cust-search Input:focus, #mcp-search Input:focus {
    border: tall;
    border-top: tall $surface-shadow;
    border-left: tall $surface-shadow;
    border-bottom: tall $accent-highlight;
    border-right: tall $accent-highlight;
    background: $app-background;
}
Button.cct-ctrl, .cct-ctrl,
Button.cct-ctrl:ansi.-style-default,
Button.cct-ctrl:ansi.-style-flat {
    height: 1; min-height: 1; max-height: 1;
    min-width: 3; max-width: 3; width: 3; padding: 0; margin: 0;
    background: transparent; color: $text-faint;
    border: none;
    content-align: center middle;
    transition: background 80ms, offset 60ms;
}
Button.cct-ctrl:hover, .cct-ctrl:hover {
    color: $error; background: transparent; border: none;
}

#cct-right-controls {
    dock: right;
    width: auto;
    min-width: 12;
    max-width: 20;
    height: 1;
    min-height: 1;
    max-height: 1;
    layout: horizontal;
    align-vertical: middle;
    align-horizontal: right;
    margin: 0;
    padding: 0;
    overflow-x: hidden;
    overflow-y: hidden;
    background: transparent;
}

Button.cct-icon-btn,
Button.cct-icon-btn:hover,
Button.cct-icon-btn:focus,
Button.cct-icon-btn.-active,
Button#btn-permissions,
Button#btn-permissions:hover,
Button#btn-permissions:focus,
Button#btn-permissions.-active,
Button#btn-attach,
Button#btn-attach:hover,
Button#btn-attach:focus,
Button#btn-attach.-active,
Button.cct-icon-send,
Button.cct-icon-send:hover,
Button.cct-icon-send:focus,
Button.cct-icon-send.-active,
Button#btn-send,
Button#btn-send:hover,
Button#btn-send:focus,
Button#btn-send.-active,
Button.cct-stop-btn,
Button#btn-stop,
Button#cct-sidebar-collapse-btn,
Button#cct-chat-sidebar-toggle {
    offset: 0 0;
    offset-x: 0;
    offset-y: 0;
    transition: none;
    border: none;
    height: 1;
    min-height: 1;
    max-height: 1;
}

Button.cct-icon-btn, .cct-icon-btn,
Button.cct-icon-btn:ansi.-style-default,
Button.cct-icon-btn:ansi.-style-flat,
Button#btn-permissions,
Button#btn-permissions:ansi.-style-default {
    height: 1; min-height: 1; max-height: 1;
    min-width: 4; width: auto; padding: 0 1; margin: 0;
    background: transparent; color: $text;
    border: none;
    text-style: bold;
    content-align: center middle;
    offset: 0 0;
}
Button#btn-attach,
Button#btn-attach:ansi.-style-default {
    height: 1; min-height: 1; max-height: 1;
    min-width: 4; width: auto; padding: 0 1; margin: 0;
    background: transparent; color: $text;
    border: none;
    text-style: bold;
    content-align: center middle;
    offset: 0 0;
}
Button.cct-icon-btn:hover, Button#btn-permissions:hover, Button#btn-attach:hover {
    color: #ffffff; background: $accent 35%; text-style: bold;
    border: none;
}
Button.cct-icon-btn:focus, Button#btn-permissions:focus, Button#btn-attach:focus {
    color: $accent-highlight; background: $surface-highlight 40%; text-style: bold;
    border: none;
}
Button.cct-icon-btn.-active, Button#btn-permissions.-active, Button#btn-attach.-active {
    background: $accent; color: #ffffff;
    border: none;
    offset: 0 0;
}

Button.cct-icon-send, .cct-icon-send,
Button.cct-icon-send:ansi.-style-default,
Button.cct-icon-send:ansi.-style-flat,
Button#btn-send,
Button#btn-send:ansi.-style-default {
    height: 1; min-height: 1; max-height: 1;
    min-width: 4; width: auto; padding: 0 1; margin: 0;
    background: transparent; color: $accent;
    border: none;
    text-style: bold;
    content-align: center middle;
    offset: 0 0;
}
Button.cct-icon-send:hover, Button#btn-send:hover {
    color: #ffffff; background: $accent; text-style: bold;
    border: none;
}
Button.cct-icon-send:focus, Button#btn-send:focus {
    color: $accent-highlight; background: $surface-highlight 40%; text-style: bold;
    border: none;
}
Button.cct-icon-send.-active, Button#btn-send.-active {
    background: $accent-shadow; color: #ffffff;
    border: none;
    offset: 0 0;
}

/* Interrupt Button state during AI Streaming */
#cct-composer Button#btn-send.cct-btn-interrupt,
#cct-composer.cct-mode-notebook Button#btn-send.cct-btn-interrupt,
#cct-composer.cct-mode-research Button#btn-send.cct-btn-interrupt,
#cct-composer.cct-mode-plan Button#btn-send.cct-btn-interrupt,
#cct-composer.cct-mode-build Button#btn-send.cct-btn-interrupt,
#cct-composer.cct-mode-debugger Button#btn-send.cct-btn-interrupt,
#cct-composer.cct-mode-agent Button#btn-send.cct-btn-interrupt,
Button.cct-btn-interrupt, Button#btn-send.cct-btn-interrupt {
    background: transparent;
    color: #ef4444;
    border: none;
    text-style: bold;
}
#cct-composer Button#btn-send.cct-btn-interrupt:hover,
Button.cct-btn-interrupt:hover, Button#btn-send.cct-btn-interrupt:hover {
    background: #ef4444;
    color: #ffffff;
    border: none;
    text-style: bold;
}
#cct-composer Button#btn-send.cct-btn-interrupt:focus,
Button.cct-btn-interrupt:focus, Button#btn-send.cct-btn-interrupt:focus {
    background: #ef4444 30%;
    color: #ffffff;
    border: none;
    text-style: bold;
}
#cct-composer Button#btn-send.cct-btn-interrupt.-active,
Button.cct-btn-interrupt.-active, Button#btn-send.cct-btn-interrupt.-active {
    background: #b91c1c;
    color: #ffffff;
    border: none;
}

/* 1-Row Inline Controls: Stop button, Sidebar collapse, and Navigation toggles */
Button.cct-stop-btn, Button#btn-stop, Button.cct-stop-btn:ansi.-style-default {
    height: 1; min-height: 1; max-height: 1;
    min-width: 8; width: auto; padding: 0 1;
    background: $surface; color: $error;
    border: none;
    text-style: bold;
    content-align: center middle;
    offset: 0 0;
}
Button.cct-stop-btn:hover, Button#btn-stop:hover {
    background: $error; color: #ffffff;
    border: none;
}

Button#cct-sidebar-collapse-btn, Button#cct-sidebar-collapse-btn:ansi.-style-default,
Button#cct-sidebar-menu-btn, .cct-sidebar-titlebar-btn {
    width: auto; min-width: 3;
    height: 1; min-height: 1; max-height: 1;
    margin: 0; padding: 0 1;
    background: transparent;
    border: none;
    color: $accent;
    content-align: center middle;
    text-style: bold;
    offset: 0 0;
}
Button#cct-sidebar-collapse-btn:hover, Button#cct-sidebar-menu-btn:hover, .cct-sidebar-titlebar-btn:hover {
    color: #ffffff; background: $accent 40%;
    border: none;
}

Button#cct-chat-sidebar-toggle, Button#cct-chat-sidebar-toggle:ansi.-style-default,
.cct-chat-nav-btn {
    width: auto; min-width: 12; max-width: 16;
    height: 1; min-height: 1; max-height: 1;
    border: none;
    padding: 0 1; margin: 0 0 0 1;
    color: $accent; background: $surface;
    text-style: bold;
    content-align: center middle;
    offset: 0 0;
    transition: color 100ms, background 100ms;
}
Button#cct-chat-sidebar-toggle:hover, .cct-chat-nav-btn:hover {
    color: #ffffff;
    background: $accent;
    border: none;
    text-style: bold;
}

/* AI Mode Dynamic 3D Chassis & Skeuomorphic Accent Theming */
#cct-composer,
#cct-composer:focus-within,
#cct-composer.cct-mode-notebook,
#cct-composer.cct-mode-research,
#cct-composer.cct-mode-plan,
#cct-composer.cct-mode-build,
#cct-composer.cct-mode-debugger,
#cct-composer.cct-mode-agent {
    background: $app-background;
}

#cct-composer.cct-mode-notebook {
    border: heavy;
    border-top: heavy #89b4fa;
    border-left: heavy #89b4fa;
    border-bottom: heavy #3d59a1;
    border-right: heavy #3d59a1;
}
#cct-composer.cct-mode-notebook:focus-within {
    border: heavy;
    border-top: heavy #b4befe;
    border-left: heavy #b4befe;
    border-bottom: heavy #5875b7;
    border-right: heavy #5875b7;
}
#cct-composer.cct-mode-notebook #cct-prompt-glyph {
    color: #7aa2f7;
}
#cct-composer.cct-mode-notebook #cct-prompt-row,
#cct-composer.cct-mode-notebook #cct-prompt-row:focus-within {
    border: none;
}
#cct-composer.cct-mode-notebook Button#btn-send,
#cct-composer.cct-mode-notebook Button.cct-icon-send {
    background: transparent;
    color: #7aa2f7;
}
#cct-composer.cct-mode-notebook Button#btn-send:hover,
#cct-composer.cct-mode-notebook Button.cct-icon-send:hover {
    background: #7aa2f7 25%;
    color: #89b4fa;
}

#cct-composer.cct-mode-research {
    border: heavy;
    border-top: heavy #ff85c0;
    border-left: heavy #ff85c0;
    border-bottom: heavy #9e366a;
    border-right: heavy #9e366a;
}
#cct-composer.cct-mode-research:focus-within {
    border: heavy;
    border-top: heavy #ffb3d9;
    border-left: heavy #ffb3d9;
    border-bottom: heavy #b8437d;
    border-right: heavy #b8437d;
}
#cct-composer.cct-mode-research #cct-prompt-glyph {
    color: #ff69b4;
}
#cct-composer.cct-mode-research #cct-prompt-row,
#cct-composer.cct-mode-research #cct-prompt-row:focus-within {
    border: none;
}
#cct-composer.cct-mode-research Button#btn-send,
#cct-composer.cct-mode-research Button.cct-icon-send {
    background: transparent;
    color: #ff69b4;
}
#cct-composer.cct-mode-research Button#btn-send:hover,
#cct-composer.cct-mode-research Button.cct-icon-send:hover {
    background: #ff69b4 25%;
    color: #ff85c0;
}

#cct-composer.cct-mode-plan {
    border: heavy;
    border-top: heavy #a6e3a1;
    border-left: heavy #a6e3a1;
    border-bottom: heavy #567e30;
    border-right: heavy #567e30;
}
#cct-composer.cct-mode-plan:focus-within {
    border: heavy;
    border-top: heavy #c5f3be;
    border-left: heavy #c5f3be;
    border-bottom: heavy #6e9d40;
    border-right: heavy #6e9d40;
}
#cct-composer.cct-mode-plan #cct-prompt-glyph {
    color: #9ece6a;
}
#cct-composer.cct-mode-plan #cct-prompt-row,
#cct-composer.cct-mode-plan #cct-prompt-row:focus-within {
    border: none;
}
#cct-composer.cct-mode-plan Button#btn-send,
#cct-composer.cct-mode-plan Button.cct-icon-send {
    background: transparent;
    color: #9ece6a;
}
#cct-composer.cct-mode-plan Button#btn-send:hover,
#cct-composer.cct-mode-plan Button.cct-icon-send:hover {
    background: #9ece6a 25%;
    color: #a6e3a1;
}

#cct-composer.cct-mode-build {
    border: heavy;
    border-top: heavy #f0d3a7;
    border-left: heavy #f0d3a7;
    border-bottom: heavy #966b33;
    border-right: heavy #966b33;
}
#cct-composer.cct-mode-build:focus-within {
    border: heavy;
    border-top: heavy #fae3b0;
    border-left: heavy #fae3b0;
    border-bottom: heavy #b88642;
    border-right: heavy #b88642;
}
#cct-composer.cct-mode-build #cct-prompt-glyph {
    color: #e0af68;
}
#cct-composer.cct-mode-build #cct-prompt-row,
#cct-composer.cct-mode-build #cct-prompt-row:focus-within {
    border: none;
}
#cct-composer.cct-mode-build Button#btn-send,
#cct-composer.cct-mode-build Button.cct-icon-send {
    background: transparent;
    color: #e0af68;
}
#cct-composer.cct-mode-build Button#btn-send:hover,
#cct-composer.cct-mode-build Button.cct-icon-send:hover {
    background: #e0af68 25%;
    color: #fab387;
}

#cct-composer.cct-mode-debugger {
    border: heavy;
    border-top: heavy #f38ba8;
    border-left: heavy #f38ba8;
    border-bottom: heavy #991b1b;
    border-right: heavy #991b1b;
}
#cct-composer.cct-mode-debugger:focus-within {
    border: heavy;
    border-top: heavy #fca5a5;
    border-left: heavy #fca5a5;
    border-bottom: heavy #b91c1c;
    border-right: heavy #b91c1c;
}
#cct-composer.cct-mode-debugger #cct-prompt-glyph {
    color: #dc143c;
}
#cct-composer.cct-mode-debugger #cct-prompt-row,
#cct-composer.cct-mode-debugger #cct-prompt-row:focus-within {
    border: none;
}
#cct-composer.cct-mode-debugger Button#btn-send,
#cct-composer.cct-mode-debugger Button.cct-icon-send {
    background: transparent;
    color: #dc143c;
}
#cct-composer.cct-mode-debugger Button#btn-send:hover,
#cct-composer.cct-mode-debugger Button.cct-icon-send:hover {
    background: #dc143c 25%;
    color: #f38ba8;
}

#cct-composer.cct-mode-agent {
    border: heavy;
    border-top: heavy #cba6f7;
    border-left: heavy #cba6f7;
    border-bottom: heavy #7a58b8;
    border-right: heavy #7a58b8;
}
#cct-composer.cct-mode-agent:focus-within {
    border: heavy;
    border-top: heavy #e0caff;
    border-left: heavy #e0caff;
    border-bottom: heavy #946fd4;
    border-right: heavy #946fd4;
}
#cct-composer.cct-mode-agent #cct-prompt-glyph {
    color: #bb9af7;
}
#cct-composer.cct-mode-agent #cct-prompt-row,
#cct-composer.cct-mode-agent #cct-prompt-row:focus-within {
    border: none;
}
#cct-composer.cct-mode-agent Button#btn-send,
#cct-composer.cct-mode-agent Button.cct-icon-send {
    background: transparent;
    color: #bb9af7;
}
#cct-composer.cct-mode-agent Button#btn-send:hover,
#cct-composer.cct-mode-agent Button.cct-icon-send:hover {
    background: #bb9af7 25%;
    color: #cba6f7;
}

/* 3D Toggle Switch */
Button.cct-toggle-3d {
    height: 1; min-height: 1; max-height: 1;
    width: 9; min-width: 9; max-width: 9;
    padding: 0; margin: 0;
    content-align: center middle;
    text-style: bold;
    border: none;
    transition: background 100ms, offset 60ms;
}
Button.cct-toggle-3d.-on {
    background: #047857;
    color: #ecfdf5;
}
Button.cct-toggle-3d.-on:hover {
    background: #059669;
    color: #ffffff;
}
Button.cct-toggle-3d.-off {
    background: #1e293b;
    color: #94a3b8;
}
Button.cct-toggle-3d.-off:hover {
    background: #334155;
    color: #f1f5f9;
}
Button.cct-toggle-3d.-active {
    offset-y: 1;
}
Button.-primary, .cct-btn.-primary, Button.cct-btn-primary {
    background: $accent 30%;
    color: $text;
    border-top: tall $accent-highlight;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent;
    border-right: tall $accent;
    text-style: bold;
}
Button.-primary:hover, .cct-btn.-primary:hover, Button.cct-btn-primary:hover {
    background: $accent 50%;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent;
    border-right: tall $accent;
    color: #ffffff;
    offset: 0 0;
}
Button.-primary:focus, .cct-btn.-primary:focus, Button.cct-btn-primary:focus {
    background: $accent 45%;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent;
    border-right: tall $accent;
    color: #ffffff;
    text-style: bold;
}
Button.-primary.-active, .cct-btn.-primary.-active, Button.cct-btn-primary.-active {
    offset: 0 0;
    border-top: tall $accent;
    border-left: tall $accent;
    border-bottom: tall $accent-highlight;
    border-right: tall $accent-highlight;
}
Button.-error, .cct-btn.-error { background: $surface-alt; color: $error; border: tall $error #7f1d1d; text-style: bold; }
Button.-error:hover, .cct-btn.-error:hover { background: $error 25%; color: #ffffff; border: tall #fca5a5 $error; }
Button.-error:focus, .cct-btn.-error:focus { background: $error 15%; border: tall #fca5a5 $error; text-style: bold; }
Button.-error.-active, .cct-btn.-error.-active { background: $error; color: #ffffff; border: tall #7f1d1d #fca5a5; offset: 0 0; }
Button.-success, .cct-btn.-success { background: $surface-alt; color: $success; border: tall $success #14532d; text-style: bold; }
Button.-success:hover, .cct-btn.-success:hover { background: $success 25%; color: #ffffff; border: tall #86efac $success; }
Button.-success:focus, .cct-btn.-success:focus { background: $success 15%; border: tall #86efac $success; text-style: bold; }
Button.-success.-active, .cct-btn.-success.-active { background: $success; color: #ffffff; border: tall #14532d #86efac; offset: 0 0; }
Button.cct-btn-sm, .cct-btn-sm { min-width: 8; padding: 0 1; }
Button.cct-btn-cta, .cct-btn-cta { min-width: 20; padding: 0 3; }

/* Shared form field look: same tall-nothing-to-hide rule — every
   Input app-wide gets the real single-line rounded border instead of
   Textual's default 3-cell "tall" block box. */
Input {
    height: 3;
    border: tall;
    border-top: tall $surface-shadow;
    border-left: tall $surface-shadow;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
    background: $app-background;
    color: $text;
    padding: 0 1;
}
Input:focus {
    border: tall;
    border-top: tall $accent-shadow;
    border-left: tall $accent-shadow;
    border-bottom: tall $accent-highlight;
    border-right: tall $accent-highlight;
}

/* ---- Popup system: every centered modal uses .cct-popup (the dimmed
   full-screen overlay) + .cct-popup-box (the card). Fade + slide-up
   open animation, sharp 3D border, never wider than the terminal, and
   `Esc`/`Enter` handling lives in each Screen (shared convention). */
.cct-popup {
    align: center middle;
    background: $app-background 65%;
}
.cct-popup-box {
    width: auto; height: auto; max-width: 100%; max-height: 100%;
    background: $surface;
    border: heavy;
    border-top: heavy #ffffff;
    border-left: heavy $surface-highlight;
    border-bottom: heavy $surface-shadow;
    border-right: heavy $surface-shadow;
    tint: $surface-highlight 5%;
    padding: 0;
    opacity: 0; offset-y: 1;
    transition: opacity 180ms, offset 200ms;
}
.cct-popup-box.open { opacity: 1; offset-y: 0; }

/* Title bar shared by every popup card. */
.cct-popup-titlebar {
    height: 3; padding: 1 2 0 2;
    border-bottom: solid $border;
}
.cct-popup-title { text-style: bold; width: 1fr; }
.cct-popup-subtitle { color: $text-faint; padding: 1 2 0 2; }
.cct-popup-hint { color: $text-faint; padding: 0 2 1 2; }
.cct-popup-close, Button.cct-popup-close,
Button.cct-popup-close:ansi.-style-default,
Button.cct-popup-close:ansi.-style-flat,
Button.cct-popup-close:focus,
Button#hc-close,
Button#hc-close:ansi.-style-default,
Button#hc-close:ansi.-style-flat,
Button#ollama-close,
Button#ollama-close:ansi.-style-default,
Button#mcp-close,
Button#mcp-close:ansi.-style-default,
Button#bpp-close,
Button#bpp-close:ansi.-style-default,
Button#act-close,
Button#act-close:ansi.-style-default,
Button#pp-close,
Button#pp-close:ansi.-style-default,
Button#pc-close,
Button#pc-close:ansi.-style-default,
Button#ap-close,
Button#ap-close:ansi.-style-default,
Button#apf-close,
Button#apf-close:ansi.-style-default,
Button#amf-close,
Button#amf-close:ansi.-style-default {
    width: 3; min-width: 3; max-width: 3;
    height: 1; min-height: 1; max-height: 1;
    padding: 0; margin: 0;
    background: transparent; color: $text-faint; border: none;
    content-align: center middle;
}
.cct-popup-close:hover, Button.cct-popup-close:hover,
Button.cct-popup-close:hover:ansi.-style-default,
Button#hc-close:hover,
Button#ollama-close:hover,
Button#mcp-close:hover,
Button#bpp-close:hover,
Button#act-close:hover,
Button#pp-close:hover,
Button#pc-close:hover,
Button#ap-close:hover,
Button#apf-close:hover,
Button#amf-close:hover {
    color: $error;
    background: transparent;
    border: none;
}
.cct-popup-actions {
    height: 5; padding: 0 2 1 2; border-top: solid $border;
    align-horizontal: right;
}
.cct-popup-actions Button { margin-left: 1; }

/* Form fields inside popups — consistent height and spacing. */
.cct-popup-box Input {
    height: 3;
    border: tall;
    border-top: tall $surface-shadow;
    border-left: tall $surface-shadow;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
    background: $app-background;
    color: $text; margin: 0 0 0 0; padding: 0 1;
}
.cct-popup-box Input:focus {
    border: tall;
    border-top: tall $accent-shadow;
    border-left: tall $accent-shadow;
    border-bottom: tall $accent-highlight;
    border-right: tall $accent-highlight;
}
.cct-field-label { color: $text-faint; height: 2; padding-top: 1; }

/* ====================================================================
   CAT Customization — Dynamic UI & Button Styles (Section 11)
   Shapes: minimal, rounded, pill, square, ghost, outlined, filled, compact, large
   Sizes: small, medium, large, compact
   ==================================================================== */
.cust-btn-shape-minimal Button, .cust-btn-shape-minimal Button:ansi.-style-default { border: none; background: transparent; }
.cust-btn-shape-minimal Button:hover { background: $accent 15%; border: none; }
.cust-btn-shape-rounded Button, .cust-btn-shape-rounded Button:ansi.-style-default { border: round $border; padding: 0 1; min-width: 10; min-height: 3; height: 3; }
.cust-btn-shape-pill Button, .cust-btn-shape-pill Button:ansi.-style-default { border: round $border; padding: 0 1; min-width: 10; min-height: 3; height: 3; }
.cust-btn-shape-square Button, .cust-btn-shape-square Button:ansi.-style-default { border: solid $border; padding: 0 1; min-width: 10; min-height: 3; height: 3; }
.cust-btn-shape-ghost Button, .cust-btn-shape-ghost Button:ansi.-style-default { border: none; background: transparent; }
.cust-btn-shape-ghost Button:hover { background: $accent 12%; }
.cust-btn-shape-outlined Button, .cust-btn-shape-outlined Button:ansi.-style-default { border: solid $border; background: transparent; padding: 0 1; min-width: 10; min-height: 3; height: 3; }
.cust-btn-shape-outlined Button:hover { background: $accent 15%; }
.cust-btn-shape-filled Button, .cust-btn-shape-filled Button:ansi.-style-default { border: none; background: $surface-alt; }
.cust-btn-shape-compact Button, .cust-btn-shape-compact Button:ansi.-style-default { height: 1; min-height: 1; min-width: 8; padding: 0 1; border: none; }
.cust-btn-shape-large Button, .cust-btn-shape-large Button:ansi.-style-default { height: 4; min-height: 4; min-width: 16; padding: 1 3; }

.cust-btn-size-small Button, .cust-btn-size-small Button:ansi.-style-default { height: 1; min-height: 1; min-width: 8; padding: 0 1; border: none; }
.cust-btn-size-medium Button, .cust-btn-size-medium Button:ansi.-style-default { height: 3; min-height: 3; min-width: 12; padding: 0 1; }
.cust-btn-size-large Button, .cust-btn-size-large Button:ansi.-style-default { height: 4; min-height: 4; min-width: 16; padding: 1 3; }
.cust-btn-size-compact Button, .cust-btn-size-compact Button:ansi.-style-default { height: 1; min-height: 1; min-width: 8; padding: 0 1; border: none; }

/* Preserve 3D Action & Dashboard Buttons from flat customization overrides */
Button.cct-dash-action, Button.cct-dash-action.-style-default,
Screen Button.cct-dash-action, Screen.cust-btn-shape-rounded Button.cct-dash-action,
Screen.cust-btn-shape-pill Button.cct-dash-action, Screen.cust-btn-shape-square Button.cct-dash-action,
Screen.cust-btn-shape-ghost Button.cct-dash-action, Screen.cust-btn-shape-outlined Button.cct-dash-action,
Screen.cust-btn-shape-filled Button.cct-dash-action, Screen.cust-btn-shape-minimal Button.cct-dash-action,
Button#cct-open-folder-btn, Screen Button#cct-open-folder-btn {
    border: heavy;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy $accent-shadow;
    border-right: heavy $accent-shadow;
}

/* ====================================================================
   CAT Touchscreen & Touch-Friendly UI Mode Rules (.cct-touch-mode)
   ==================================================================== */
.cct-touch-mode Button, .cct-touch-mode .cct-btn, .cct-touch-mode .cct-ctrl {
    min-height: 3;
    min-width: 10;
    padding: 0 2;
}
.cct-touch-mode Button.cct-icon-btn {
    min-width: 4;
    min-height: 1;
    padding: 0 1;
}
.cct-touch-mode .cct-badge {
    padding: 0 1;
    min-width: 6;
}
.cct-touch-mode .cct-rws-row,
.cct-touch-mode .cct-setting-row,
.cct-touch-mode .cct-nav-item,
.cct-touch-mode .cct-sidebar-project-row {
    min-height: 2;
    padding: 0 1;
}
.cct-touch-mode .cct-filetree {
    padding: 0 1;
}
.cct-touch-mode Button:hover,
.cct-touch-mode Button:focus,
.cct-touch-mode .cct-btn:hover,
.cct-touch-mode .cct-btn:focus,
.cct-touch-mode .cct-ctrl:hover,
.cct-touch-mode .cct-ctrl:focus {
    background: $accent 30%;
    border: solid $accent;
}
.cct-touch-mode #cct-explorer-resizer,
.cct-touch-mode #cct-rightpane-resizer {
    background: $border;
}
.cct-touch-mode #cct-explorer-resizer:hover,
.cct-touch-mode #cct-explorer-resizer.dragging,
.cct-touch-mode #cct-rightpane-resizer:hover,
.cct-touch-mode #cct-rightpane-resizer.dragging {
    background: $accent;
}
.cct-touch-mode .cct-tb-pill {
    padding: 0 1;
    min-width: 3;
}
.cct-touch-mode .cct-tb-pill:hover,
.cct-touch-mode .cct-tb-pill:focus {
    color: $accent;
    text-style: bold;
}
.cct-touch-mode .cct-tb-close {
    min-width: 4;
    padding: 0 1;
}
.cct-touch-mode .cct-bv-btn {
    min-width: 4;
    padding: 0 1;
}
.cct-touch-mode .cct-bv-btn:hover,
.cct-touch-mode .cct-bv-btn:focus {
    color: $accent;
    background: $surface-alt;
}
"""


def fit_dialog(screen, box_id, scroll_id, fill_ids=()):
    """Size a centered dialog card to its content, capped to the terminal.

    Textual CSS alone cannot express "card is content-sized, but when the
    terminal is too short the middle scrolls and the footer stays
    visible": an `1fr` middle always inflates an auto-height card to its
    max-height, and an auto middle overflows the capped card. So each
    dialog releases its card to natural auto sizing, waits for that
    layout to actually land, and then imposes ONE of two consistent
    states:

      Release — every id this helper may have forced before (the card,
      its scroll area, and the fill ids) is reset back to its natural
      CSS height. The next layout passes therefore measure real natural
      sizes, never heights distorted by a previous fit.

      Apply   — v0.7.8.5: the card's natural total height is its own
      *measured region* in the released layout — Textual already stacks
      every child (header, scroll area, footer) at natural heights, so
      re-deriving the total from chrome/fixed/content sums is both
      unnecessary and wrong (that old math double-counted the scroll
      area's padding, so every dialog landed 1-2 rows short and the
      footer buttons were pushed past the box border and clipped).
      The card height is set to that measured natural total, capped at
      `vh - 4` and floored at 6. When capped, the scroll area switches
      to `1fr` (so the footer stays visible in the card) and every id
      in `fill_ids` switches from `auto` to `100%` (used by two-column
      dialogs whose columns must fill the card and scroll internally
      instead of overflowing it).

    Textual never applies a changed CSS height instantly: the released
    box keeps its previous region for one layout pass, and content that
    mounts *after* a fit call (row lists rebuilt in on_mount/on_resize
    handlers) only lands a frame later. A single measure-then-set cycle
    can therefore snapshot a stale region and freeze the dialog at a
    too-small height with its footer pushed past the box border. So
    apply() loops: it waits until the released region no longer matches
    a height this helper previously imposed, measures, writes the new
    heights, and then runs one more release+measure pass — repeating
    only while consecutive measures disagree. Every cycle starts from
    the same released baseline, so fits converge to the stable natural
    size and cannot shrink or inflate the card frame by frame.
    """
    import os

    # Per-screen memory of the height the last fit imposed on each box,
    # used to tell "the released layout hasn't landed yet" (region still
    # equals what we forced) apart from "the layout is stable at natural".
    memory = getattr(screen, "_cct_fit_memory", None)
    if memory is None:
        memory = {}
        try:
            screen._cct_fit_memory = memory
        except Exception:
            pass

    def _q(ident):
        return screen.query_one(f"#{ident}")

    def remember(value):
        memory[box_id] = value

    def release():
        wanted = [box_id, scroll_id, *fill_ids]
        for ident in wanted:
            try:
                _q(ident).styles.height = "auto"
            except Exception:
                pass

    def apply(attempts=0):
        if attempts > 14:
            return  # cannot settle; leave whatever is on screen
        try:
            box = _q(box_id)
            scroll = _q(scroll_id)
        except Exception:
            return
        if not (box.is_attached and scroll.is_attached):
            return
        vh = screen.size.height
        # Short terminals: panels may hide chrome (subtitles/hints) via
        # the shared .cct-compact class; re-measure once it takes effect.
        want_compact = vh < 28
        if want_compact != box.has_class("cct-compact"):
            box.set_class(want_compact, "cct-compact")
            screen.call_after_refresh(lambda: apply(attempts))
            return

        last_imposed = memory.get(box_id)
        if last_imposed is not None and box.region.height == last_imposed:
            # Still showing the previous fit — the released layout
            # hasn't landed yet. Wait one more frame (bounded; equal
            # values are also the stable end-state, so giving up here is
            # harmless).
            screen.call_after_refresh(lambda: apply(attempts + 1))
            return

        natural_total = box.region.height
        if natural_total < 2:
            # Layout not ready (first frame); try again after the next one.
            screen.call_after_refresh(lambda: apply(attempts + 1))
            return
        capped = natural_total > vh - 4
        target = max(6, min(natural_total, vh - 4))
        if os.environ.get("CCT_FIT_DEBUG"):
            children = ", ".join(
                f"{c.id or type(c).__name__}={c.region.height}" for c in box.children)
            print(f"[fit] {box_id}@{vh}: box={box.region} natural={natural_total} "
                  f"target={target} capped={capped} children=[{children}]")
        if target == last_imposed:
            # The released layout agrees with the previous fit: stable.
            # The styles below may still hold the release() reset from
            # the confirmation cycle above — re-assert the settled state
            # and stop.
            scroll.styles.height = "1fr" if capped else "auto"
            for child_id in fill_ids:
                try:
                    _q(child_id).styles.height = "100%" if capped else "auto"
                except Exception:
                    pass
            return
        box.styles.height = target
        scroll.styles.height = "1fr" if capped else "auto"
        for child_id in fill_ids:
            try:
                _q(child_id).styles.height = "100%" if capped else "auto"
            except Exception:
                pass
        remember(target)
        # Content may still be landing; confirm with one more
        # release + measure cycle before calling it settled.
        release()
        screen.call_after_refresh(lambda: apply(attempts + 1))

    release()
    screen.call_after_refresh(apply)
