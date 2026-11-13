"""
Tokyo Night color theme + low-level terminal rendering helpers for
Chemistry Calc Terminal (CCT).

No third-party dependencies required. Uses 24-bit ANSI escape codes,
which are supported by modern Windows Terminal, macOS Terminal, and
virtually all Linux terminal emulators.
"""

import os
import re
import sys
import json
import time
import unicodedata

# ---------------------------------------------------------------- colors --
CYAN    = (125, 207, 255)   # accent
PURPLE  = (195, 160, 255)   # secondary accent
GREEN   = (139, 224, 139)   # success
ORANGE  = (240, 180, 95)    # warning
RED     = (255, 127, 154)   # error
TEXT    = (232, 235, 250)   # primary text (near white)
DIM     = (135, 140, 175)   # secondary text
FAINT   = (90, 94, 128)     # faint / border text

RESET = "\033[0m"
BOLD = "\033[1m"

ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def enable_windows_ansi():
    """Best-effort: enable ANSI escapes on legacy Windows terminals."""
    try:
        import colorama
        colorama.init()
    except ImportError:
        pass


def rgb(r, g, b):
    return f"\033[38;2;{r};{g};{b}m"


def bgrgb(r, g, b):
    return f"\033[48;2;{r};{g};{b}m"


def fg(text, color, bold=False):
    code = rgb(*color)
    b = BOLD if bold else ""
    return f"{b}{code}{text}{RESET}"


def cyan(t, bold=False):   return fg(t, CYAN, bold)
def purple(t, bold=False): return fg(t, PURPLE, bold)
def green(t, bold=False):  return fg(t, GREEN, bold)
def orange(t, bold=False): return fg(t, ORANGE, bold)
def red(t, bold=False):    return fg(t, RED, bold)
def text(t, bold=False):   return fg(t, TEXT, bold)
def dim(t, bold=False):    return fg(t, DIM, bold)
def faint(t, bold=False):  return fg(t, FAINT, bold)


# ------------------------------------------------------- premium bg / highlight --
# Background-highlighted "badges" for a premium terminal look. colorama is
# used (when present) so legacy Windows cmd.exe also renders background
# colors correctly; on modern terminals we emit real 24-bit ANSI directly.
try:
    import colorama  # noqa: F401
    _HAS_COLORAMA = True
except ImportError:
    _HAS_COLORAMA = False


def bg(text_str, bgcolor, fgcolor=TEXT, bold=True):
    """Render text with a solid background highlight, e.g. a chat bubble
    fill or a status badge."""
    b = BOLD if bold else ""
    return f"{b}{bgrgb(*bgcolor)}{rgb(*fgcolor)}{text_str}{RESET}"


def badge(label, bgcolor, fgcolor=(20, 20, 30)):
    """A small pill-style highlighted badge, e.g. [ ONLINE ]."""
    return bg(f" {label} ", bgcolor, fgcolor, bold=True)


# Soft background tints used for chat bubbles / highlighted panels.
BG_USER = (40, 62, 92)     # muted blue   — user message bubble
BG_AI   = (48, 40, 74)     # muted violet — AI response bubble
BG_OK   = (33, 74, 55)     # muted green  — success highlight
BG_WARN = (79, 63, 30)     # muted amber  — warning highlight
BG_INFO = (33, 58, 79)     # muted cyan   — info highlight

# v0.5.1 "OpenCode-style" chatbox: a flat (non-gradient), single-hue
# border in a muted navy-blue, with a brighter vivid blue reserved for
# the one highlighted word in the meta row (mirrors "Build" in the
# reference screenshot) — a calmer, more premium look than the
# rainbow-gradient box used elsewhere in the app.
ACCENT_BLUE = (122, 162, 247)   # vivid — the one highlighted word
BORDER_BLUE = (61, 71, 112)     # muted — the box outline itself

# v0.5.2 refined chatbox palette — a touch brighter and more deliberately
# tuned than v0.5.1 so the box reads as a single calm object against the
# Tokyo Night background, exactly like the reference screenshot: a soft
# navy outline, a faint inner tint, and one reserved vivid accent for the
# mode word. Two border stops feed an almost-imperceptible horizontal
# gradient (premium tools do this — it adds depth without becoming a
# rainbow).
BORDER_SOFT_A = (74, 86, 130)   # left edge — slightly lifted navy
BORDER_SOFT_B = (60, 70, 110)   # right edge — settles back down
ACCENT_VIVID  = (130, 170, 255) # the one bold mode word (e.g. "NOTEBOOK")
STATUS_AMBER  = (230, 175, 110) # right-aligned status word
META_DIM      = (110, 120, 160) # dimmed model name next to the mode word
HINT_FAINT    = (96, 100, 134)  # keyboard-shortcut key caps
HINT_LABEL    = (130, 138, 175) # keyboard-shortcut label text


# Emoji/symbol code-point ranges that render as DOUBLE-WIDTH glyphs in
# virtually every terminal/monospace font in practice, even though
# Unicode itself classifies many of them as "Ambiguous" or "Neutral"
# width (so a naive East-Asian-Width check alone misses them). The
# flask icon (\u2697) used in the input box is one of these — treating
# it as 1 column instead of 2 was the cause of the reported "chat box
# not aligned" bug: every border/hint-row padding calculation that
# followed the icon was off by one column.
_WIDE_RANGES = (
    (0x2600, 0x27BF),   # misc symbols + dingbats (includes \u2697 flask)
    (0x1F300, 0x1FAFF), # emoji blocks (symbols, pictographs, supplemental)
)


def _char_width(ch):
    o = ord(ch)
    for lo, hi in _WIDE_RANGES:
        if lo <= o <= hi:
            return 2
    eaw = unicodedata.east_asian_width(ch)
    return 2 if eaw in ("W", "F") else 1


def vlen(s):
    """Visible column-width of a string: strips ANSI escape codes and
    counts double-width glyphs (emoji, CJK, symbol icons) as 2 columns
    instead of 1, matching how terminals actually render them."""
    return sum(_char_width(ch) for ch in ANSI_RE.sub("", s))


def vtruncate(s, width):
    """Truncate a (possibly ANSI-colored) string to at most `width` visible
    columns, preserving any escape codes and appending an ellipsis if it
    had to cut. Used by panel() so a line that's a few characters too long
    for the box gets shortened instead of overflowing and pushing every
    border on that row (and everything printed after it) out of
    alignment — the root cause of the reported box-alignment bug."""
    if vlen(s) <= width:
        return s
    if width <= 0:
        return ""
    out = []
    used = 0
    i = 0
    n = len(s)
    budget = max(0, width - 1)  # reserve 1 column for the ellipsis
    while i < n:
        m = ANSI_RE.match(s, i)
        if m:
            out.append(m.group(0))
            i = m.end()
            continue
        ch = s[i]
        w = _char_width(ch)
        if used + w > budget:
            break
        out.append(ch)
        used += w
        i += 1
    out.append("\u2026")
    return "".join(out)


def vpad(s, width, align="left"):
    """Pad a (possibly colored) string to `width` visible columns."""
    pad = max(0, width - vlen(s))
    if align == "left":
        return s + " " * pad
    if align == "right":
        return " " * pad + s
    left = pad // 2
    right = pad - left
    return " " * left + s + " " * right


def clear_screen():
    print("\033[2J\033[H", end="")


def cursor_home():
    sys.stdout.write("\033[H")


def hide_cursor():
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()


def show_cursor():
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()


def typewriter(s, delay=0.006, color=None, bold=False):
    """Print text one character at a time."""
    for ch in s:
        out = fg(ch, color, bold) if color else ch
        sys.stdout.write(out)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def progress_bar(label, duration=0.6, width=32, color=CYAN):
    """An animated fill-in progress bar, e.g. for boot/loading sequences."""
    steps = 24
    for i in range(steps + 1):
        filled = int(width * i / steps)
        bar = "\u2588" * filled + "\u2591" * (width - filled)
        pct = int(100 * i / steps)
        sys.stdout.write(f"\r  {dim(label)} {fg(bar, color)} {text(str(pct) + '%')}")
        sys.stdout.flush()
        time.sleep(duration / steps)
    sys.stdout.write("\n")


def reveal_lines(lines, delay=0.05, color=None, bold=False):
    """Print a block of lines one at a time (used for the ASCII logo)."""
    for line in lines:
        out = fg(line, color, bold) if color else line
        print(out)
        time.sleep(delay)


# ------------------------------------------------------------- box panel --
TL, TR, BL, BR, H, V = "╭", "╮", "╰", "╯", "─", "│"


def panel(lines, title=None, color=CYAN, width=78, pad_x=2, title_gradient=None):
    """Render a rounded box panel around a list of (plain or ANSI) lines.
    If `title_gradient` is a tuple of 2+ colors, the title text itself is
    rendered as a smooth gradient instead of the flat `color`."""
    inner = width - 2
    out = []

    if title:
        label = f" {title.upper()} " if title_gradient else f" {title} "
        t = gradient(label, *title_gradient, bold=True) if title_gradient else label
        left = (inner - vlen(t)) // 2
        right = inner - vlen(t) - left
        top = fg(TL + H * left, color) + t + fg(H * right + TR, color)
        out.append(top)
    else:
        top = TL + H * inner + TR
        out.append(fg(top, color))

    for ln in lines:
        avail = inner - pad_x * 2
        content = vpad(vtruncate(ln, avail), avail)
        out.append(fg(V, color) + " " * pad_x + content + " " * pad_x + fg(V, color))

    bottom = BL + H * inner + BR
    out.append(fg(bottom, color))
    return "\n".join(out)


def window_titlebar(title, width=78):
    """A macOS-style window chrome strip: red/yellow/green dots on the
    left, the title centered, in its own closed rounded box — printed
    just above the main content panel, mimicking a native app window."""
    dots = fg("\u25cf", (237, 106, 94)) + " " + fg("\u25cf", (245, 191, 79)) + " " + fg("\u25cf", (97, 194, 91))
    inner = width - 2
    top = fg(TL + H * inner + TR, FAINT)
    bot = fg(BL + H * inner + BR, FAINT)
    dots_cell = " " + dots
    title_cell = fg(title, TEXT, bold=True)
    row_plain = vpad(dots_cell, (inner - vlen(title_cell)) // 2) if vlen(title_cell) < inner else dots_cell
    left_w = (inner - vlen(title_cell)) // 2
    row = vpad(dots_cell, left_w) + title_cell
    row = vpad(row, inner)
    mid = fg(V, FAINT) + row + fg(V, FAINT)
    return "\n".join([top, mid, bot])


def input_box(hint="Ask Chemistry\u2026", width=78, left_hint="enter send", right_hint=""):
    """A bordered chat input box like a modern TUI, e.g.:
    ╭──────────────────────────────╮
    │ ›   ▌                        │
    ╰──────────────────────────────╯
      enter send            engine
    """
    inner = width - 2
    top = fg(TL + H * inner + TR, CYAN)
    row = fg(V, CYAN) + " " + fg("\u203a", CYAN, bold=True) + "   " + fg("\u258c", CYAN) + \
        " " * (inner - 7) + fg(V, CYAN)
    bot = fg(BL + H * inner + BR, CYAN)
    hint_row = dim(left_hint) + " " * max(1, width - vlen(left_hint) - vlen(right_hint)) + dim(right_hint)
    return "\n".join([top, row, bot, hint_row])


def hr(width=78, color=FAINT, ch="─"):
    return fg(ch * width, color)


def center(s, width=78):
    return vpad(s, width, "center")


# ---------------------------------------------------------- gradients --
# Lightweight character-by-character 24-bit color interpolation — gives
# a "premium" shimmering look to borders, titles and rules without any
# external dependency (still just plain ANSI escape codes).

def lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _stops(t, stops):
    """t in [0,1] across N-1 segments defined by `stops` (list of colors)."""
    if len(stops) == 1:
        return stops[0]
    seg = 1.0 / (len(stops) - 1)
    i = min(int(t / seg), len(stops) - 2)
    local_t = (t - i * seg) / seg
    return lerp(stops[i], stops[i + 1], local_t)


def gradient(s, *colors, bold=False):
    """Render `s` with a smooth color gradient across its visible
    characters. Pass 2+ colors, e.g. gradient(txt, CYAN, PURPLE) or
    gradient(txt, CYAN, PURPLE, CYAN) for a shimmering round-trip."""
    if not colors:
        colors = (CYAN, PURPLE)
    n = max(1, len(s) - 1)
    b = BOLD if bold else ""
    out = []
    for i, ch in enumerate(s):
        if ch == " ":
            out.append(" ")
            continue
        c = _stops(i / n, colors)
        out.append(f"{b}{rgb(*c)}{ch}")
    return "".join(out) + RESET


def gradient_rule(width, *colors, ch="─"):
    return gradient(ch * width, *colors)


# A calm "alive" pulse color used for status dots / engine indicators —
# alternates gently so the same screen looks a little different each
# time it's redrawn, without any real animation loop needed.
def pulse_color(base_a=GREEN, base_b=CYAN):
    return base_a if int(time.time() * 2) % 2 == 0 else base_b


def pulse_dot(base_a=GREEN, base_b=CYAN):
    return fg("\u25cf", pulse_color(base_a, base_b), bold=True)


# ---------------------------------------------------- premium input box --
FLASK = "\u2697"   # ⚗

# v0.5.2 angular box-drawing characters — the reference screenshot uses
# sharp 90-degree corners (┌┐└┘), not rounded ones (╭╮╰╯). Keeping these
# as named constants means a single edit point if a future design wants
# rounded corners back.
ATL, ATR, ABL, ABR, AH, AV = "┌", "┐", "└", "┘", "─", "│"


def soft_border_line(width, left_ch, mid_ch, right_ch,
                     c1=BORDER_SOFT_A, c2=BORDER_SOFT_B):
    """A horizontal box edge drawn with a very gentle left→right color
    interpolation between two navy stops. It's intentionally subtle (the
    two stops are close in value) so the border reads as a single calm
    object rather than a rainbow — the same trick premium terminal tools
    use to add depth to a flat outline."""
    inner = width - 2
    out = []
    out.append(f"{rgb(*c1)}{left_ch}")
    for i in range(inner):
        t = i / max(1, inner - 1)
        r, g, b = lerp(c1, c2, t)
        out.append(f"{rgb(r, g, b)}{mid_ch}")
    out.append(f"{rgb(*c2)}{right_ch}{RESET}")
    return "".join(out)


def premium_input_frame(width=78, top_colors=(CYAN, PURPLE, CYAN)):
    """Top border + prompt-row prefix for the redesigned gradient chatbox.
    Returns (top_line, row_prefix) — caller prints top_line, then reads
    input() using row_prefix so the cursor lands inside the box."""
    inner = width - 2
    top = gradient(TL + H * inner + TR, *top_colors)
    icon = gradient(FLASK, *top_colors[:2], bold=True)
    row_prefix = fg(V, top_colors[0]) + "  " + icon + "   "
    return top, row_prefix


def premium_input_close(width=78, bottom_colors=(PURPLE, CYAN), left_hint="\u21b5 send",
                          mid_hint="/help commands", right_hint="engine ready"):
    inner = width - 2
    bot = gradient(BL + H * inner + BR, *bottom_colors)
    dot = pulse_dot()
    fixed = 12 + vlen(left_hint) + vlen(mid_hint) + vlen(right_hint)
    if width - fixed < 1:
        # Too narrow to fit left + mid + right hints with real padding —
        # drop the middle hint rather than let the padding collapse to a
        # hardcoded minimum of 1, which used to make the right_hint /
        # status dot crowd into (and visually misalign with) the rest of
        # the row on narrower terminals.
        fixed = 8 + vlen(left_hint) + vlen(right_hint)
        pad = max(1, width - fixed)
        hint = "   " + faint(left_hint) + " " * pad + dot + " " + dim(right_hint)
    else:
        pad = width - fixed
        hint = ("   " + faint(left_hint) + faint("   \u00b7   ") + faint(mid_hint) +
                " " * pad + dot + " " + dim(right_hint))
    return bot, hint


# ----------------------------------------------------- OpenCode-style kit --
# Characters + palette for the v0.5.6 OpenCode-inspired chat surface.
# These are ADDITIVE — nothing above changes. OpenCode's signature look is a
# single heavy left rail (no right border) terminating in a half-block, with a
# `▀` underline cap below; an avatar square `▣` marks the assistant; a `●` dot
# prefixes tips. The OC_* palette is OpenCode's own Tokyo-Night mapping, kept
# separate from CCT's existing CYAN/PURPLE constants so both identities coexist.

HV       = "\u2503"   # ┃ heavy vertical — the OpenCode input rail
HALF_UP  = "\u2580"   # ▀ upper half block — the underline cap
HALF_DN  = "\u2584"   # ▄ lower half block — fills for load bars
SQ_MARK  = "\u25a3"   # ▣ assistant avatar / role marker
DOT      = "\u25cf"   # ● tip / status dot
SWEEP    = "\u259e"   # ▞ the scanline-clear sweep glyph

# OpenCode's Tokyo-Night semantic roles (additive — CCT's own palette above is
# untouched). Used by the new rail input + hybrid message renderers.
OC_BG_PANEL    = (30, 32, 48)     # message panel fill
OC_BG_ELEMENT  = (34, 36, 54)     # input box fill / hover
OC_BORDER      = (115, 122, 162)  # default rail/border
OC_BORDER_ACTIVE = (144, 153, 178) # active (mode-coloured) rail
OC_PRIMARY     = (130, 170, 255)  # the vivid mode word (Build / NOTEBOOK)
OC_SECONDARY   = (192, 153, 255)  # secondary accent (purple)
OC_ACCENT      = (255, 150, 108)  # orange accent / tip
OC_MUTED       = (130, 139, 184)  # muted text / key caps


def heavy_rail(width, color=OC_PRIMARY, terminator="\u2579"):
    """OpenCode's signature LEFT rail: a vertical `┃` run followed by the
    terminator char. Returns ONE colored prefix string (the caller prints it
    once per row of the input box). `terminator` defaults to `╹` (U+2575) —
    the half-heavy up bar OpenCode uses so the rail curls off at the bottom."""
    return fg(HV, color) + (" " if width <= 0 else "")


def rail_terminator(color=OC_PRIMARY, terminator="\u2579"):
    """The single char that ends the rail at its bottom. Kept separate so the
    input renderer can swap it in for the last row without recomputing width."""
    return fg(terminator, color)


def underline_cap(width, color=OC_PRIMARY):
    """The `▀` bottom cap row that visually closes the input box under the
    meta row, exactly like OpenCode's cap. Full-width, no side borders."""
    return fg(HALF_UP * max(1, width), color)


# ------------------------------------------------------------- theme switch --
# v0.5.6: a real light/dark toggle. Every color name below is a plain module
# global that every other file reads at call time via theme.CYAN, theme.BG_AI,
# etc. — so set_theme() just reassigns those globals in place and every panel,
# badge, and chat bubble anywhere in the app picks up the new palette
# immediately, with zero changes needed anywhere else.
#
# v0.7.9.5 THEME SYSTEM OVERHAUL: the two-entry dict grew into a normalized
# registry of 22 full palettes built on ONE Theme schema (the semantic field
# set every UI surface consumes). Each Theme is compiled down to the same
# 30 legacy module globals the rest of this file has always exported, so
# classic-terminal panels, badges and bubbles keep working unchanged while
# the whole palette catalog becomes data-driven:
#
#   Theme(name, label, dark, background, surface, surface_hover, text,
#         text_muted, text_faint, border, border_active, accent,
#         accent_alt, accent_secondary, input_background,
#         selection_background, selection_text, success, warning, error)
#
# "dark" and "light" survive as compatibility aliases (they resolve to
# tokyo-night / github-light), so saved configs and /theme dark|light keep
# working byte-for-byte.

import threading
from dataclasses import dataclass as _dc_dataclass


def _hx(h):
    """'#rrggbb' -> (r, g, b)."""
    h = (h or "").lstrip("#")
    if len(h) != 6:
        return (128, 128, 128)
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (128, 128, 128)


@_dc_dataclass(frozen=True)
class Theme:
    """Normalized theme schema — every UI surface (Textual CSS bridge,
    classic-terminal panels, editor palettes) reads ONLY these fields."""
    name: str
    label: str
    dark: bool = True
    background: tuple = (26, 27, 38)
    surface: tuple = (30, 32, 48)
    surface_hover: tuple = (34, 36, 54)
    text: tuple = (232, 235, 250)
    text_muted: tuple = (135, 140, 175)
    text_faint: tuple = (90, 94, 128)
    border: tuple = (115, 122, 162)
    border_active: tuple = (144, 153, 178)
    accent: tuple = (130, 170, 255)
    accent_alt: tuple = (125, 207, 255)
    accent_secondary: tuple = (192, 153, 255)
    input_background: tuple = (34, 36, 54)
    selection_background: tuple = (49, 52, 75)
    selection_text: tuple = (232, 235, 250)
    success: tuple = (139, 224, 139)
    warning: tuple = (240, 180, 95)
    error: tuple = (255, 127, 154)

    def hex(self, attr):
        """'#rrggbb' for one of this theme's color fields."""
        v = getattr(self, attr)
        return "#{:02x}{:02x}{:02x}".format(*v)


# ------------------------------------------------------------ WCAG helpers --
def _lum(c):
    def chan(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = c
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def contrast_ratio(a, b):
    """WCAG contrast ratio between two RGB tuples (>=1.0)."""
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def fit_contrast(color, bg, minimum=3.0):
    """Nudge `color` toward black/white until it reaches `minimum`
    contrast against `bg`. Themes are authored correct already; this is
    the safety net that guarantees no shipped theme can ship an
    invisible accent (requirement #17)."""
    if contrast_ratio(color, bg) >= minimum:
        return color
    target_dark = _lum(bg) > 0.35  # light background → darken the color
    for step in range(1, 21):
        t = step * 0.06
        other = (0, 0, 0) if target_dark else (255, 255, 255)
        cand = blend(color, other, t)
        if contrast_ratio(cand, bg) >= minimum:
            return cand
    return (0, 0, 0) if target_dark else (255, 255, 255)


# ------------------------------------------------------------ the registry --
def T(name, label, dark, bg, surf, hover, text, muted, faint, border,
      border_active, accent, alt, secondary, input_bg, sel_bg, sel_text,
      success, warning, error):
    return Theme(
        name=name, label=label, dark=dark,
        background=_hx(bg), surface=_hx(surf), surface_hover=_hx(hover),
        text=_hx(text), text_muted=_hx(muted), text_faint=_hx(faint),
        border=_hx(border), border_active=_hx(border_active),
        accent=_hx(accent), accent_alt=_hx(alt), accent_secondary=_hx(secondary),
        input_background=_hx(input_bg),
        selection_background=_hx(sel_bg), selection_text=_hx(sel_text),
        success=_hx(success), warning=_hx(warning), error=_hx(error))


_THEME_LIST = [
    # ── 1. CAT Originals (Official Signature Family) ──
    T("cat-origin", "🐱 CAT Origin", True,
      "#1e1e24", "#16161a", "#282832", "#e2e8f0", "#9494a8", "#c4b5fd",
      "#363645", "#7c3aed", "#7c3aed", "#f59e0b", "#a78bfa",
      "#16161a", "#36364e", "#ffffff",
      "#10b981", "#f59e0b", "#ef4444"),
    T("cat-dark", "🌙 CAT Dark", True,
      "#121218", "#181820", "#222230", "#f0f2f8", "#8890a8", "#5c647c",
      "#2e3448", "#a78bfa", "#a78bfa", "#38bdf8", "#c4b5fd",
      "#181820", "#3c4460", "#ffffff",
      "#34d399", "#fbbf24", "#f87171"),
    T("cat-midnight", "🌌 CAT Midnight", True,
      "#0d0e15", "#13141f", "#1b1c2b", "#e4e6f2", "#7e829e", "#515570",
      "#26283d", "#818cf8", "#818cf8", "#6366f1", "#a5b4fc",
      "#13141f", "#2e314d", "#ffffff",
      "#22c55e", "#eab308", "#ef4444"),
    T("cat-cyber", "⚡ CAT Cyber", True,
      "#0a0b10", "#10121a", "#181b26", "#00ffcc", "#5eead4", "#14b8a6",
      "#1f2937", "#f43f5e", "#f43f5e", "#06b6d4", "#ec4899",
      "#10121a", "#374151", "#ffffff",
      "#10b981", "#f59e0b", "#f43f5e"),
    T("cat-amethyst", "🔮 CAT Amethyst", True,
      "#140e1d", "#1a1226", "#261b38", "#ede6f6", "#aa9cb8", "#6e6080",
      "#35274d", "#c084fc", "#c084fc", "#e879f9", "#d8b4fe",
      "#1a1226", "#3f2e5c", "#ffffff",
      "#4ade80", "#fbbf24", "#f87171"),
    T("cat-aurora", "🌌 CAT Aurora", True,
      "#0a1118", "#0f1a24", "#162736", "#e0f2fe", "#7dd3fc", "#38bdf8",
      "#1e3a50", "#2dd4bf", "#2dd4bf", "#a78bfa", "#38bdf8",
      "#0f1a24", "#204560", "#ffffff",
      "#34d399", "#fcd34d", "#f87171"),

    # ── 2. Premium & Modern Dark ──
    T("tokyo-night", "🌒 Tokyo Night", True,
      "#1a1b26", "#1e2030", "#222436", "#e8ebfa", "#878caf", "#5a5e80",
      "#737aa2", "#9099b2", "#82aaff", "#7dcfff", "#c09aff",
      "#222436", "#31344b", "#e8ebfa",
      "#8be08b", "#f0b45f", "#ff7f9a"),
    T("tokyo-night-storm", "⛈️ Tokyo Night Storm", True,
      "#24283b", "#1f2335", "#292e42", "#c0caf5", "#7aa2f7", "#565f89",
      "#3b4261", "#7aa2f7", "#7aa2f7", "#7dcfff", "#bb9af7",
      "#1f2335", "#414868", "#ffffff",
      "#9ece6a", "#e0af68", "#f7768e"),
    T("catppuccin-mocha", "😺 Catppuccin Mocha", True,
      "#1e1e2e", "#181825", "#313244", "#cdd6f4", "#a6adc8", "#6c7086",
      "#313244", "#89b4fa", "#89b4fa", "#89dceb", "#cba6f7",
      "#181825", "#45475a", "#dde3ff",
      "#a6e3a1", "#f9e2af", "#f38ba8"),
    T("catppuccin-macchiato", "😺 Catppuccin Macchiato", True,
      "#24273a", "#1e2030", "#363a4f", "#cad3f5", "#a5adcb", "#6e738d",
      "#363a4f", "#8aadf4", "#8aadf4", "#91d7e3", "#b7bdf8",
      "#1e2030", "#454a63", "#e8ecff",
      "#a6da95", "#eed49f", "#ed8796"),
    T("catppuccin-frappe", "😺 Catppuccin Frappé", True,
      "#303446", "#292c3c", "#414559", "#c6d0f5", "#a5adce", "#737994",
      "#414559", "#8caaee", "#8caaee", "#99d1db", "#babbf1",
      "#292c3c", "#4c517d", "#e6ebff",
      "#a6d189", "#e5c890", "#e78284"),
    T("dracula", "🧛 Dracula", True,
      "#282a36", "#21222c", "#343746", "#f8f8f2", "#8b93b8", "#6272a4",
      "#44475a", "#bd93f9", "#bd93f9", "#8be9fd", "#ff79c6",
      "#21222c", "#44475a", "#f8f8f2",
      "#50fa7b", "#ffb86c", "#ff5555"),
    T("nord", "❄️ Nord", True,
      "#2e3440", "#3b4252", "#434c5e", "#eceff4", "#c0c8d4", "#7b88a1",
      "#434c5e", "#88c0d0", "#88c0d0", "#81a1c1", "#b48ead",
      "#3b4252", "#434c5e", "#eceff4",
      "#a3be8c", "#ebcb8b", "#bf616a"),
    T("nord-frost", "🧊 Nord Frost", True,
      "#1e222a", "#252b36", "#2f3847", "#e5e9f0", "#88c0d0", "#63748e",
      "#3b4659", "#81a1c1", "#81a1c1", "#8fbcbb", "#b48ead",
      "#252b36", "#434f66", "#ffffff",
      "#a3be8c", "#ebcb8b", "#d08770"),
    T("rose-pine", "🌲 Rose Pine", True,
      "#191724", "#1f1d2e", "#26233a", "#e0def4", "#908caa", "#6e6a86",
      "#403d52", "#c4a7e7", "#c4a7e7", "#9ccfd8", "#ebbcba",
      "#1f1d2e", "#403d52", "#e0def4",
      "#9ccfd8", "#f6c177", "#eb6f92"),
    T("rose-pine-moon", "🌙 Rose Pine Moon", True,
      "#232136", "#2a273f", "#393552", "#e0def4", "#908caa", "#6e6a86",
      "#56526e", "#c4a7e7", "#c4a7e7", "#9ccfd8", "#ebbcba",
      "#2a273f", "#393552", "#e0def4",
      "#9ccfd8", "#f6c177", "#eb6f92"),
    T("monokai", "🍄 Monokai", True,
      "#272822", "#2d2e27", "#3e3d32", "#f8f8f2", "#a6a28d", "#75715e",
      "#49483e", "#a6e22e", "#a6e22e", "#66d9ef", "#ae81ff",
      "#1e1f1c", "#49483e", "#f8f8f2",
      "#a6e22e", "#e6db74", "#f92672"),
    T("monokai-pro", "💎 Monokai Pro", True,
      "#2d2a2e", "#221f22", "#403e41", "#fcfcfa", "#939293", "#727072",
      "#403e41", "#ffd866", "#ffd866", "#78dce8", "#ab9df2",
      "#221f22", "#49464b", "#fcfcfa",
      "#a9dc76", "#fc9867", "#ff6188"),
    T("monokai-dimmed", "🕯️ Monokai Dimmed", True,
      "#1e1e1e", "#242424", "#303030", "#d4d4d4", "#9e9e9e", "#686868",
      "#383838", "#c5a5ff", "#c5a5ff", "#9cdcfe", "#dcdcaa",
      "#242424", "#484848", "#ffffff",
      "#b5cea8", "#ce9178", "#f44747"),
    T("gruvbox-dark", "🍂 Gruvbox Dark", True,
      "#282828", "#32302f", "#3c3836", "#ebdbb2", "#bdae93", "#928374",
      "#504945", "#fe8013", "#fe8013", "#83a598", "#d3869b",
      "#32302f", "#504945", "#fbf1c7",
      "#b8bb26", "#fabd2f", "#fb4934"),
    T("gruvbox-material-dark", "🪵 Gruvbox Material", True,
      "#242728", "#2c3031", "#383c3e", "#d4be98", "#a99f92", "#7c6f64",
      "#454c4e", "#e78a4e", "#e78a4e", "#7daea3", "#d3869b",
      "#2c3031", "#50585a", "#fbf1c7",
      "#a9b665", "#d8a657", "#ea6962"),
    T("flexoki-dark", "🍵 Flexoki Dark", True,
      "#100f0f", "#1c1b1a", "#282726", "#cecdc3", "#a8a49c", "#878479",
      "#333130", "#da702c", "#da702c", "#3aa99f", "#8b7ec8",
      "#1c1b1a", "#3d3c38", "#fffcf0",
      "#879a39", "#d0a215", "#d14d41"),
    T("solarized-dark", "☀️ Solarized Dark", True,
      "#002b36", "#073642", "#0f4c59", "#93a1a1", "#839496", "#586e75",
      "#1a4b57", "#268bd2", "#268bd2", "#2aa198", "#6c71c4",
      "#073642", "#124b59", "#eee8d5",
      "#859900", "#b58900", "#dc322f"),
    T("solarized-osaka", "🏯 Solarized Osaka", True,
      "#00141a", "#002b36", "#073642", "#839496", "#2aa198", "#586e75",
      "#0f4c59", "#268bd2", "#268bd2", "#b58900", "#d33682",
      "#002b36", "#195666", "#ffffff",
      "#859900", "#cb4b16", "#dc322f"),

    # ── 3. Developer Classics & Modern Systems ──
    T("atom-one-dark", "⚛️ Atom One Dark", True,
      "#282c34", "#2f343d", "#3a404b", "#d7dae0", "#828997", "#5c6370",
      "#3e4451", "#61afef", "#61afef", "#56b6c2", "#c678dd",
      "#2c313a", "#3e4451", "#d7dae0",
      "#98c379", "#e5c07b", "#e06c75"),
    T("one-dark-pro", "🪐 One Dark Pro", True,
      "#1e2227", "#242831", "#2e3440", "#abb2bf", "#61afef", "#5c6370",
      "#3b4048", "#61afef", "#61afef", "#98c379", "#c678dd",
      "#242831", "#424854", "#ffffff",
      "#98c379", "#e5c07b", "#e06c75"),
    T("github-dark", "🐙 GitHub Dark", True,
      "#0d1117", "#161b22", "#21262d", "#e6edf3", "#8b949e", "#6e7681",
      "#30363d", "#58a6ff", "#58a6ff", "#bc8cff", "#79c0ff",
      "#161b22", "#388bfd33", "#ffffff",
      "#3fb950", "#d29922", "#f85149"),
    T("github-dark-dimmed", "🐙 GitHub Dark Dimmed", True,
      "#1c2128", "#22272e", "#2d333b", "#adbac7", "#768390", "#545d68",
      "#373e47", "#539bf5", "#539bf5", "#6cb6ff", "#b083f0",
      "#22272e", "#444c56", "#ffffff",
      "#57ab5a", "#c69026", "#e5534b"),
    T("vscode-dark", "💻 VS Code Dark", True,
      "#1e1e1e", "#252526", "#2d2d30", "#cccccc", "#858585", "#656565",
      "#3e3e42", "#007acc", "#007acc", "#4ec9b0", "#c586c0",
      "#252526", "#094771", "#ffffff",
      "#6a9955", "#dcdcaa", "#f44747"),
    T("ansi-dark", "⬛ ANSI Dark", True,
      "#000000", "#101418", "#1a2026", "#d4d4d4", "#9a9a9a", "#6e6e6e",
      "#3a3f44", "#5fafd7", "#5fafd7", "#5fafd7", "#ad7fa8",
      "#161b20", "#264f78", "#ffffff",
      "#8ae234", "#c4a000", "#ff5f5f"),
    T("textual-dark", "📟 Textual Dark", True,
      "#141414", "#1e1e1e", "#2b2b2b", "#e8e8e8", "#a5a5a5", "#6f6f6f",
      "#3b3b3b", "#4a9eff", "#4a9eff", "#63d0e8", "#b085eb",
      "#1e1e1e", "#2b4c6f", "#e8e8e8",
      "#4ebf22", "#ffcf24", "#e05656"),

    # ── 4. Cyberpunk, Neon & Futuristic ──
    T("cyberpunk-neon", "⚡ Cyberpunk Neon", True,
      "#08080d", "#12121c", "#1c1c2e", "#00ffea", "#ff007f", "#8080a0",
      "#26263d", "#00ffea", "#00ffea", "#ffe600", "#ff007f",
      "#12121c", "#3a3a5c", "#ffffff",
      "#00ff7f", "#ffe600", "#ff0055"),
    T("oled-black", "⚫ OLED Pure Black", True,
      "#000000", "#080808", "#121212", "#ffffff", "#888888", "#555555",
      "#1f1f1f", "#38bdf8", "#38bdf8", "#c084fc", "#4ade80",
      "#080808", "#2a2a2a", "#ffffff",
      "#22c55e", "#eab308", "#ef4444"),
    T("synthwave-84", "🌆 Synthwave '84", True,
      "#262335", "#241b2f", "#34294f", "#fffefe", "#b6a0ff", "#8468b8",
      "#493d6d", "#ff7edb", "#ff7edb", "#36f9f6", "#fe4450",
      "#241b2f", "#614d85", "#ffffff",
      "#72f1b8", "#fede5d", "#fe4450"),
    T("synthwave-neon", "🕹️ Synthwave Neon", True,
      "#1a102f", "#22153e", "#2e1c54", "#ff71ce", "#01cdfe", "#8d79b2",
      "#3d266e", "#01cdfe", "#01cdfe", "#05ffa1", "#ff71ce",
      "#22153e", "#56369c", "#ffffff",
      "#05ffa1", "#fffb96", "#ff71ce"),
    T("laserwave", "👾 Laserwave", True,
      "#1b1924", "#222030", "#2c293e", "#eb64b9", "#74dfc4", "#817b9c",
      "#393550", "#40b4c4", "#40b4c4", "#b381c5", "#eb64b9",
      "#222030", "#4b4568", "#ffffff",
      "#74dfc4", "#ffe261", "#eb64b9"),
    T("matrix", "🟢 Matrix", True,
      "#0d110d", "#121a12", "#1a261a", "#00ff41", "#00bb2d", "#008f11",
      "#1c381c", "#00ff41", "#00ff41", "#008f11", "#39ff14",
      "#121a12", "#1e461e", "#ffffff",
      "#00ff41", "#c4a000", "#ff3333"),
    T("radium", "☢️ Radium", True,
      "#0c130e", "#131d16", "#1c2b21", "#e3fcec", "#34d399", "#588065",
      "#263a2d", "#10b981", "#10b981", "#6ee7b7", "#a7f3d0",
      "#131d16", "#324d3c", "#ffffff",
      "#10b981", "#facc15", "#f87171"),

    # ── 5. Atmospheric, Oceanic & Celestial Dark ──
    T("moonlight", "🌕 Moonlight", True,
      "#1e2030", "#222436", "#2f334d", "#c8d3f5", "#82aaff", "#636d99",
      "#3b4261", "#82aaff", "#82aaff", "#c099ff", "#fca7ea",
      "#222436", "#444b73", "#ffffff",
      "#c3e88d", "#ffc777", "#ff757f"),
    T("horizon-dark", "🌅 Horizon Dark", True,
      "#1c1e26", "#232530", "#2e303e", "#e0e2ea", "#e95678", "#6c6f93",
      "#383a4c", "#fab795", "#fab795", "#26bbd9", "#ee64ac",
      "#232530", "#484a60", "#ffffff",
      "#29d398", "#fac29a", "#e95678"),
    T("oceanic-next", "🌊 Oceanic Next", True,
      "#1b2b34", "#22333b", "#2c404a", "#d8dee9", "#6699cc", "#65737e",
      "#343d46", "#6699cc", "#6699cc", "#5fb3b3", "#c594c5",
      "#22333b", "#4f5b66", "#ffffff",
      "#99c794", "#fac863", "#ec5f67"),
    T("andromeda", "🌌 Andromeda", True,
      "#1e2025", "#23262d", "#2d313a", "#e5e5e5", "#00e8c6", "#747c8c",
      "#383c47", "#c74ded", "#c74ded", "#ffe66d", "#ff00aa",
      "#23262d", "#484f5e", "#ffffff",
      "#96e072", "#ffe66d", "#ee5d43"),
    T("palenight", "🌌 Palenight", True,
      "#292d3e", "#252837", "#32374d", "#d0d0e0", "#8796b0", "#676e95",
      "#3c435e", "#ab47bc", "#ab47bc", "#80cbc4", "#ffcb6b",
      "#252837", "#444b6a", "#ffffff",
      "#c3e88d", "#ffcb6b", "#ff5370"),
    T("material-deep-ocean", "🌊 Deep Ocean", True,
      "#0f111a", "#141724", "#1b1f30", "#8f93a2", "#82aaff", "#464b5d",
      "#21263b", "#82aaff", "#82aaff", "#80cbc4", "#c792ea",
      "#141724", "#2e3450", "#ffffff",
      "#c3e88d", "#ffcb6b", "#ff5370"),
    T("abyss", "🕳️ Abyss", True,
      "#000c18", "#051525", "#0a2038", "#6688cc", "#225588", "#335577",
      "#103050", "#80a0ff", "#80a0ff", "#40c0ff", "#ddbb88",
      "#051525", "#184570", "#ffffff",
      "#22bb88", "#ddbb88", "#ff4444"),
    T("cobalt2", "🔷 Cobalt2", True,
      "#193549", "#15232d", "#1f4662", "#ffffff", "#0088ff", "#627e99",
      "#26567a", "#ffc600", "#ffc600", "#00ffff", "#ff9d00",
      "#15232d", "#2c6c9a", "#ffffff",
      "#3ad900", "#ffc600", "#ff0000"),
    T("shades-of-purple", "🟪 Shades of Purple", True,
      "#2d2b55", "#222044", "#37346b", "#e3dfff", "#fad000", "#7e78a6",
      "#433f82", "#fad000", "#fad000", "#a599e9", "#fb94ff",
      "#222044", "#524d9c", "#ffffff",
      "#b362ff", "#fad000", "#ec3a37"),
    T("night-owl", "🦉 Night Owl", True,
      "#011627", "#0b253a", "#12334f", "#d6deeb", "#82aaff", "#5f7e97",
      "#1d3b53", "#c792ea", "#c792ea", "#7fdbca", "#ecc48d",
      "#0b253a", "#234d6f", "#ffffff",
      "#22da6e", "#addb67", "#ef5350"),
    T("ayu-mirage", "🌫️ Ayu Mirage", True,
      "#1f2430", "#191e2a", "#232834", "#cbccc6", "#707a8c", "#5c6773",
      "#333b4d", "#ffcc66", "#ffcc66", "#5ccfe6", "#d4bfff",
      "#191e2a", "#3e485e", "#ffffff",
      "#bae67e", "#ffd580", "#f28779"),
    T("ayu-dark", "🖤 Ayu Dark", True,
      "#0f141c", "#141923", "#1d2330", "#e6e1cf", "#e6b450", "#5c6773",
      "#273042", "#ffb454", "#ffb454", "#39bae6", "#d4bfff",
      "#141923", "#323e54", "#ffffff",
      "#aad94c", "#ffb454", "#f07178"),
    T("kanagawa", "🌊 Kanagawa", True,
      "#1f1f28", "#16161e", "#2a2a37", "#dcd7ba", "#7e9cd8", "#727169",
      "#363646", "#7e9cd8", "#7e9cd8", "#7aa89f", "#957fb8",
      "#16161e", "#494759", "#ffffff",
      "#98bb6c", "#e6c384", "#e46876"),
    T("kanagawa-dragon", "🐉 Kanagawa Dragon", True,
      "#181616", "#121212", "#222020", "#c5c9c5", "#8a9aa0", "#625e5a",
      "#2d2a2a", "#c4746e", "#c4746e", "#8ba4b0", "#8992a7",
      "#121212", "#433e3e", "#ffffff",
      "#87a987", "#c4b28a", "#c4746e"),
    T("vesper", "🕯️ Vesper", True,
      "#101010", "#161616", "#222222", "#ffffff", "#999999", "#505050",
      "#2d2d2d", "#ff5c57", "#ff5c57", "#ffc799", "#a8a8a8",
      "#161616", "#3d3d3d", "#ffffff",
      "#5af78e", "#ffc799", "#ff5c57"),
    T("obsidian-dark", "💎 Obsidian Dark", True,
      "#161618", "#1c1c1f", "#26262b", "#e0e0e4", "#a388ee", "#686872",
      "#35353d", "#a388ee", "#a388ee", "#74c0fc", "#f08c00",
      "#1c1c1f", "#43434e", "#ffffff",
      "#69db7c", "#ffd43b", "#ff6b6b"),
    T("eclipse-dark", "🌘 Eclipse Dark", True,
      "#0a0a0f", "#101017", "#1a1a24", "#e8e8f0", "#f59e0b", "#606075",
      "#282838", "#fbbf24", "#fbbf24", "#38bdf8", "#ec4899",
      "#101017", "#38384f", "#ffffff",
      "#34d399", "#fbbf24", "#f43f5e"),
    T("everforest-dark", "🌲 Everforest Dark", True,
      "#2d353b", "#272e33", "#343f44", "#d3c6aa", "#a7c080", "#7fbbb3",
      "#3d484d", "#a7c080", "#a7c080", "#83c092", "#d699b6",
      "#272e33", "#4c595f", "#ffffff",
      "#a7c080", "#dbbc7f", "#e67e80"),
    T("poimandres", "🌌 Poimandres", True,
      "#1b1e28", "#171922", "#252b37", "#e4f0fb", "#add7ff", "#7390aa",
      "#303b4d", "#5de4c7", "#5de4c7", "#89ddff", "#f087bd",
      "#171922", "#3a475d", "#ffffff",
      "#5de4c7", "#fffac2", "#d0679d"),
    T("snazzy", "✨ Snazzy", True,
      "#282a36", "#1e2029", "#343644", "#eff0eb", "#57c7ff", "#686868",
      "#3d4052", "#ff5c57", "#ff5c57", "#9aedfe", "#ff6ac1",
      "#1e2029", "#4a4e63", "#ffffff",
      "#5af78e", "#f3f99d", "#ff5c57"),
    T("deep-space", "🚀 Deep Space", True,
      "#0b0d13", "#11141f", "#1b2030", "#d0d7de", "#7d8590", "#484f58",
      "#21262d", "#79c0ff", "#79c0ff", "#a5d6ff", "#d2a8ff",
      "#11141f", "#1f2a44", "#ffffff",
      "#56d364", "#e3b341", "#ff7b72"),
    T("emerald-zen", "🌿 Emerald Zen", True,
      "#0f1715", "#141f1c", "#1d2c28", "#e1ede9", "#7fa398", "#507066",
      "#2b423c", "#34d399", "#34d399", "#10b981", "#6ee7b7",
      "#141f1c", "#284a3f", "#ffffff",
      "#34d399", "#f59e0b", "#f87171"),
    T("solar-flare", "🔥 Solar Flare", True,
      "#18110b", "#20170f", "#2c2016", "#faecd8", "#a89078", "#705d4d",
      "#3d2f23", "#f97316", "#f97316", "#ea580c", "#fb923c",
      "#20170f", "#48301c", "#ffffff",
      "#84cc16", "#eab308", "#ef4444"),
]

_THEMES = {t.name: t for t in _THEME_LIST}

# Compatibility aliases: saved configs / /theme dark | light keep working.
_THEME_ALIASES = {
    "origin": "cat-origin",
    "cat": "cat-origin",
    "cat-origin": "cat-origin",
    "dark": "cat-origin",
    "light": "cat-origin",
    "cat-light": "cat-origin",
    "cat-dark": "cat-dark",
    "ivory": "cat-origin",
    "catppuccin-latte": "cat-origin",
    "rose-pine-dawn": "cat-origin",
    "gruvbox-light": "cat-origin",
    "flexoki-light": "cat-origin",
    "solarized-light": "cat-origin",
    "atom-one-light": "cat-origin",
    "github-light": "cat-origin",
    "vscode-light": "cat-origin",
    "ansi-light": "cat-origin",
    "textual-light": "cat-origin",
    "tokyo": "tokyo-night",
    "catppuccin": "catppuccin-mocha",
    "gruvbox": "gruvbox-dark",
    "flexoki": "flexoki-dark",
    "vscode": "vscode-dark",
    "github": "github-dark",
    "cyberpunk": "cyberpunk-neon",
    "oled": "oled-black",
    "synthwave": "synthwave-84",
}

DEFAULT_THEME_NAME = "cat-origin"

# Real terminal background paint map (best-effort — OSC 11), derived from
# every registered theme so any theme switch paints the right backdrop.
_TERMINAL_BG = {t.name: t.background for t in _THEME_LIST}

CURRENT_THEME_NAME = DEFAULT_THEME_NAME
_THEME_FILE = os.path.join(os.path.expanduser("~"), ".cct_theme.json")


def resolve_theme_name(name):
    """Map any accepted identifier (canonical name, alias, case/space
    variant) to a registered canonical name; unknown names fall back to
    the current theme rather than crashing."""
    key = str(name).strip().lower().replace(" ", "-").replace("_", "-")
    key = _THEME_ALIASES.get(key, key)
    if key in ("light", "cat-light", "light-theme") or key.endswith("-light") or key.startswith("light-"):
        return _THEME_ALIASES.get("light", DEFAULT_THEME_NAME)
    if key in _THEMES:
        return key
    if key.startswith("dark"):
        return _THEME_ALIASES.get("dark", "cat-dark")
    return CURRENT_THEME_NAME if CURRENT_THEME_NAME in _THEMES else DEFAULT_THEME_NAME


def get_theme_obj(name=None):
    """The normalized Theme object for `name` (or the active theme)."""
    resolved = resolve_theme_name(name if name is not None else CURRENT_THEME_NAME)
    return _THEMES.get(resolved) or _THEMES[DEFAULT_THEME_NAME]


def get_theme_families():
    """Group all registered themes into their official dark families."""
    return {
        "CAT Originals": [t for t in _THEME_LIST if t.name.startswith("cat-")],
        "Cyberpunk, Neon & OLED": [t for t in _THEME_LIST if t.name in (
            "cyberpunk-neon", "oled-black", "synthwave-84", "synthwave-neon",
            "laserwave", "matrix", "radium", "snazzy")],
        "Premium & Modern": [t for t in _THEME_LIST if t.name in (
            "tokyo-night", "tokyo-night-storm", "catppuccin-mocha", "catppuccin-macchiato",
            "catppuccin-frappe", "dracula", "nord", "nord-frost", "rose-pine",
            "rose-pine-moon", "monokai", "monokai-pro", "monokai-dimmed", "gruvbox-dark",
            "gruvbox-material-dark", "flexoki-dark", "solarized-dark", "solarized-osaka")],
        "Developer Classics": [t for t in _THEME_LIST if t.name in (
            "atom-one-dark", "one-dark-pro", "github-dark", "github-dark-dimmed",
            "vscode-dark", "ansi-dark", "textual-dark")],
        "Atmospheric & Oceanic": [t for t in _THEME_LIST if t.name in (
            "moonlight", "horizon-dark", "oceanic-next", "andromeda", "palenight",
            "material-deep-ocean", "abyss", "cobalt2", "shades-of-purple", "night-owl",
            "ayu-mirage", "ayu-dark", "kanagawa", "kanagawa-dragon", "vesper",
            "obsidian-dark", "eclipse-dark", "everforest-dark", "poimandres",
            "deep-space", "emerald-zen", "solar-flare")],
    }


def import_custom_theme(data: dict) -> bool:
    """Import a custom user theme from a JSON dictionary."""
    try:
        name = str(data.get("name", "custom")).strip().lower().replace(" ", "-")
        label = str(data.get("label", f"🎨 {name.title()}"))
        dark = bool(data.get("dark", True))
        t = T(
            name, label, dark,
            data.get("background", "#1e1e24"),
            data.get("surface", "#16161a"),
            data.get("surface_hover", "#282832"),
            data.get("text", "#e2e8f0"),
            data.get("text_muted", "#9494a8"),
            data.get("text_faint", "#c4b5fd"),
            data.get("border", "#363645"),
            data.get("border_active", "#7c3aed"),
            data.get("accent", "#7c3aed"),
            data.get("accent_alt", "#f59e0b"),
            data.get("accent_secondary", "#a78bfa"),
            data.get("input_background", "#16161a"),
            data.get("selection_background", "#36364e"),
            data.get("selection_text", "#ffffff"),
            data.get("success", "#10b981"),
            data.get("warning", "#f59e0b"),
            data.get("error", "#ef4444"),
        )
        _THEMES[name] = t
        if t not in _THEME_LIST:
            _THEME_LIST.append(t)
        _TERMINAL_BG[name] = t.background
        return True
    except Exception:
        return False


def export_theme_json(name: str = None) -> dict:
    """Export the active (or named) theme as a clean JSON dictionary."""
    t = get_theme_obj(name)
    return {
        "name": t.name,
        "label": t.label,
        "dark": t.dark,
        "background": t.hex("background"),
        "surface": t.hex("surface"),
        "surface_hover": t.hex("surface_hover"),
        "text": t.hex("text"),
        "text_muted": t.hex("text_muted"),
        "text_faint": t.hex("text_faint"),
        "border": t.hex("border"),
        "border_active": t.hex("border_active"),
        "accent": t.hex("accent"),
        "accent_alt": t.hex("accent_alt"),
        "accent_secondary": t.hex("accent_secondary"),
        "input_background": t.hex("input_background"),
        "selection_background": t.hex("selection_background"),
        "selection_text": t.hex("selection_text"),
        "success": t.hex("success"),
        "warning": t.hex("warning"),
        "error": t.hex("error"),
    }


# ------------------------------------------------- legacy var compilation --
_THEME_COLOR_VARS = [
    "CYAN", "PURPLE", "GREEN", "ORANGE", "RED", "TEXT", "DIM", "FAINT",
    "BG_USER", "BG_AI", "BG_OK", "BG_WARN", "BG_INFO",
    "ACCENT_BLUE", "BORDER_BLUE", "BORDER_SOFT_A", "BORDER_SOFT_B", "ACCENT_VIVID",
    "STATUS_AMBER", "META_DIM", "HINT_FAINT", "HINT_LABEL",
    "OC_BG_PANEL", "OC_BG_ELEMENT", "OC_BORDER", "OC_BORDER_ACTIVE",
    "OC_PRIMARY", "OC_SECONDARY", "OC_ACCENT", "OC_MUTED",
]


_COMPILED_CACHE = {}


def compile_theme_vars(t):
    """Compile a normalized Theme into the 30 legacy module-global colors
    every print()-based panel reads (theme.CYAN, theme.BG_AI, ...). The
    two pre-existing themes get hand-tuned overrides so their look stays
    byte-for-byte what it was before the overhaul."""
    if t.name in _COMPILED_CACHE:
        return dict(_COMPILED_CACHE[t.name])
    dark = t.dark
    bg = t.background

    bubble_user = blend(bg, t.accent_alt, 0.30 if dark else 0.14)
    bubble_ai = blend(bg, t.accent_secondary, 0.30 if dark else 0.10)
    bubble_ok = blend(bg, t.success, 0.32 if dark else 0.16)
    bubble_warn = blend(bg, t.warning, 0.32 if dark else 0.20)
    bubble_info = blend(bg, t.accent_alt, 0.22 if dark else 0.12)

    soft_a = blend(t.border, t.text, 0.22)
    soft_b = blend(t.border, bg, 0.30)
    vivid = blend(t.accent_alt, (255, 255, 255), 0.15) if dark else t.accent_alt
    status_amber = fit_contrast(t.warning, bg, 3.0)

    res = {
        "CYAN": fit_contrast(t.accent_alt, bg, 3.0),
        "PURPLE": fit_contrast(t.accent_secondary, bg, 3.0),
        "GREEN": fit_contrast(t.success, bg, 3.0),
        "ORANGE": status_amber,
        "RED": fit_contrast(t.error, bg, 3.0),
        "TEXT": t.text,
        "DIM": fit_contrast(t.text_muted, bg, 2.5),
        "FAINT": t.text_faint,
        "BG_USER": bubble_user, "BG_AI": bubble_ai, "BG_OK": bubble_ok,
        "BG_WARN": bubble_warn, "BG_INFO": bubble_info,
        "ACCENT_BLUE": t.accent_alt,
        "BORDER_BLUE": t.border,
        "BORDER_SOFT_A": soft_a, "BORDER_SOFT_B": soft_b,
        "ACCENT_VIVID": vivid,
        "STATUS_AMBER": status_amber,
        "META_DIM": t.text_muted,
        "HINT_FAINT": t.text_faint,
        "HINT_LABEL": t.text_muted,
        "OC_BG_PANEL": t.surface,
        "OC_BG_ELEMENT": t.input_background,
        "OC_BORDER": t.border,
        "OC_BORDER_ACTIVE": fit_contrast(t.border_active, t.surface, 2.0),
        "OC_PRIMARY": fit_contrast(t.accent, t.surface, 3.0),
        "OC_SECONDARY": fit_contrast(t.accent_secondary, t.surface, 3.0),
        "OC_ACCENT": status_amber,
        "OC_MUTED": t.text_muted,
    }
    _COMPILED_CACHE[t.name] = dict(res)
    return res


# Hand-tuned legacy tables for the two themes that existed before the
# overhaul — applied verbatim so existing users see zero visual drift.
_LEGACY_OVERRIDES = {
    "tokyo-night": {
        "CYAN": (125, 207, 255), "PURPLE": (195, 160, 255), "GREEN": (139, 224, 139),
        "ORANGE": (240, 180, 95), "RED": (255, 127, 154), "TEXT": (232, 235, 250),
        "DIM": (135, 140, 175), "FAINT": (90, 94, 128),
        "BG_USER": (40, 62, 92), "BG_AI": (48, 40, 74), "BG_OK": (33, 74, 55),
        "BG_WARN": (79, 63, 30), "BG_INFO": (33, 58, 79),
        "ACCENT_BLUE": (122, 162, 247), "BORDER_BLUE": (61, 71, 112),
        "BORDER_SOFT_A": (74, 86, 130), "BORDER_SOFT_B": (60, 70, 110),
        "ACCENT_VIVID": (130, 170, 255), "STATUS_AMBER": (230, 175, 110),
        "META_DIM": (110, 120, 160), "HINT_FAINT": (96, 100, 134),
        "HINT_LABEL": (130, 138, 175),
        "OC_BG_PANEL": (30, 32, 48), "OC_BG_ELEMENT": (34, 36, 54),
        "OC_BORDER": (115, 122, 162), "OC_BORDER_ACTIVE": (144, 153, 178),
        "OC_PRIMARY": (130, 170, 255), "OC_SECONDARY": (192, 153, 255),
        "OC_ACCENT": (255, 150, 108), "OC_MUTED": (130, 139, 184),
    },
    "github-light": {
        "CYAN": (9, 105, 218), "PURPLE": (130, 80, 223), "GREEN": (16, 124, 45),
        "ORANGE": (146, 88, 0), "RED": (207, 34, 46), "TEXT": (24, 28, 34),
        "DIM": (74, 82, 92), "FAINT": (110, 119, 129),
        "BG_USER": (215, 243, 255), "BG_AI": (247, 236, 255), "BG_OK": (212, 250, 221),
        "BG_WARN": (255, 246, 186), "BG_INFO": (204, 238, 255),
        "ACCENT_BLUE": (9, 105, 218), "BORDER_BLUE": (176, 192, 208),
        "BORDER_SOFT_A": (196, 204, 213), "BORDER_SOFT_B": (214, 221, 228),
        "ACCENT_VIVID": (9, 105, 218), "STATUS_AMBER": (133, 79, 0),
        "META_DIM": (74, 82, 92), "HINT_FAINT": (110, 119, 129), "HINT_LABEL": (74, 82, 92),
        "OC_BG_PANEL": (255, 255, 255), "OC_BG_ELEMENT": (240, 243, 247),
        "OC_BORDER": (186, 194, 204), "OC_BORDER_ACTIVE": (9, 105, 218),
        "OC_PRIMARY": (9, 105, 218), "OC_SECONDARY": (130, 80, 223),
        "OC_ACCENT": (176, 72, 0), "OC_MUTED": (74, 82, 92),
    },
}

# GitHub-Light syntax palette for the code pad (feature 1) — deliberately
# fixed regardless of the app's own dark/light theme, since that's what was
# asked for ("own syntax with light github theme").
SYNTAX_GITHUB_LIGHT = {
    "keyword": (207, 34, 46), "string": (10, 48, 105), "comment": (106, 115, 125),
    "number": (0, 92, 197), "function": (130, 80, 223), "builtin": (149, 56, 0),
    "operator": (36, 41, 47), "plain": (36, 41, 47),
}


def _paint_terminal_bg(name):
    try:
        r, g, b = _TERMINAL_BG[name]
        sys.stdout.write(f"\033]11;#{r:02x}{g:02x}{b:02x}\033\\")
        sys.stdout.flush()
    except Exception:
        pass


def set_theme(name, persist=True, paint_bg=True):
    """Apply a theme by name (canonical id or legacy alias). Compiles the
    normalized Theme into this module's color globals, repaints the
    terminal backdrop, and — unless `persist=False` (hover previews!) —
    saves the choice to BOTH stores (~/.cct_theme.json and the central
    config's default_theme) so it survives restarts.

    Returns the canonical theme name actually applied."""
    global CURRENT_THEME_NAME
    resolved = resolve_theme_name(name)
    t = _THEMES[resolved]
    compiled = compile_theme_vars(t)
    compiled.update(_LEGACY_OVERRIDES.get(resolved, {}))
    globals().update({k: v for k, v in compiled.items() if k in _THEME_COLOR_VARS})
    CURRENT_THEME_NAME = resolved
    try:
        from .ui import theme_css
        theme_css.invalidate_css_cache()
    except Exception:
        pass
    if paint_bg:
        _paint_terminal_bg(resolved)
    if persist:
        try:
            with open(_THEME_FILE, "w", encoding="utf-8") as f:
                json.dump({"theme": resolved}, f)
        except Exception:
            pass
        try:
            from . import config as _config
            cfg = _config.get_config()
            if cfg.default_theme != resolved:
                cfg.default_theme = resolved
                _config.save_config(cfg)
        except Exception:
            pass
    return resolved


def get_theme():
    return CURRENT_THEME_NAME


def is_light():
    """All light modes have been completely removed from CAT CLI.
    Always returns False to ensure dark contrast across all surfaces."""
    return False


def available_themes():
    """THE single authoritative list of canonical theme names. Every
    picker in the app — the main-menu Themes entry, Settings Center,
    and the /theme command — renders from this list, so no interface
    can ever drift from what set_theme() actually supports."""
    return [t.name for t in _THEME_LIST]


def theme_names():
    """Alias kept for symmetry with label lookups; returns the same
    authoritative list as available_themes()."""
    return available_themes()


def theme_label(name):
    """Human label for a theme name (every entry the pickers show comes
    from here so labels stay consistent too)."""
    t = _THEMES.get(resolve_theme_name(name))
    return t.label if t else str(name)


def blend(c1, c2, t):
    """Linear RGB blend between two color tuples — used to build the
    per-mode gradients (v0.7.8, FEATURE 3) without any extra deps."""
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(c1, c2))


# ------------------------------------------------------- color roles --
# v0.7.9.0 light-mode audit: one semantic role -> palette-attribute map
# shared by EVERY component that paints accent-colored text outside CSS
# (thinking-stage spinners, the command palette icons, completion
# summaries). Roles resolve against the CURRENT theme's globals at call
# time, so dark keeps its Tokyo Night values and light automatically
# gets its darker, WCAG-readable counterparts — no hardcoded hex can
# leak a dark-mode color onto a white surface anymore.
_COLOR_ROLES = {
    "blue":   ("ACCENT_BLUE", "CYAN"),
    "cyan":   ("CYAN",),
    "purple": ("PURPLE",),
    "amber":  ("STATUS_AMBER", "ORANGE"),
    "green":  ("GREEN",),
    "red":    ("RED",),
    "gray":   ("FAINT", "DIM"),
    "muted":  ("META_DIM", "DIM"),
}


def role_hex(role, fallback="#888888"):
    """Hex string for a semantic color role in the CURRENT theme.
    Unknown roles return `fallback`; never raises."""
    for attr in _COLOR_ROLES.get(str(role), ()):
        rgb = globals().get(attr)
        if isinstance(rgb, tuple) and len(rgb) == 3:
            try:
                return "#{:02x}{:02x}{:02x}".format(*rgb)
            except Exception:
                continue
    return fallback


def load_saved_theme():
    """Restore the user's last theme choice — call once at boot.

    Priority: an explicit per-session choice already saved to
    _THEME_FILE wins (unchanged behavior). If nothing's been saved
    yet, fall back to the centralized config's default_theme
    (calc_terminal/config.py). v0.7.9.5: ANY registered theme name is
    honored now — the old loader only acted on the literal value
    "light", which silently dropped every other palette."""
    try:
        if os.path.exists(_THEME_FILE):
            with open(_THEME_FILE, encoding="utf-8") as f:
                saved = json.load(f).get("theme", DEFAULT_THEME_NAME)
        else:
            from . import config as _config
            saved = _config.get_config().default_theme
        resolved = resolve_theme_name(saved)
        # Only re-apply when it differs from the import-time default so a
        # plain boot with no saved choice doesn't repaint anything.
        if os.path.exists(_THEME_FILE) or str(saved or "").strip().lower() not in (
                "", "dark", "tokyo-night", DEFAULT_THEME_NAME):
            set_theme(resolved, persist=False, paint_bg=True)
    except Exception:
        pass


# ------------------------------------------------------- terminal title --
# v0.7.9.4: ONE centralized terminal/tab-title owner (requirement: CAT
# must identify itself in the terminal instead of showing "PowerShell").
# Uses the OSC-0 title sequence every supported terminal understands —
# Windows Terminal, PowerShell 7 console, classic conhost, most *nix
# emulators — and degrades to a silent no-op on dumb/piped output so no
# raw escape characters ever print.
_APP_TITLE_BASE = "CAT CLI"

_title_saved = False


def _title_ok():
    try:
        if os.environ.get("TERM", "") == "dumb":
            return False
        return bool(getattr(sys.stdout, "isatty", lambda: False)())
    except Exception:
        return False


def set_terminal_title(title):
    """Set the terminal/window/tab title. Centralized — call this (or
    set_terminal_title_state) rather than emitting OSC sequences anywhere
    else. Never raises; no-op when output isn't a real terminal."""
    global _title_saved
    if not _title_ok():
        return False
    clean = "".join(ch for ch in str(title)
                    if ch.isprintable() and ch not in "\x07\x1b")[:80]
    try:
        # xterm title-stack push once, before the first custom title, so
        # restore_terminal_title() can bring the user's shell label back.
        # Terminals without stacking support ignore it silently.
        if not _title_saved:
            try:
                sys.stdout.write("\x1b[22t")
            except Exception:
                pass
            _title_saved = True
        osc_seq = f"\x1b]0;{clean}\x07"
        try:
            sys.stdout.write(osc_seq)
            sys.stdout.flush()
        except UnicodeEncodeError:
            buf = getattr(sys.stdout, "buffer", None)
            if buf is not None:
                buf.write(osc_seq.encode("utf-8"))
                buf.flush()

        # Also set Win32 console title and icon if on Windows
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.kernel32.SetConsoleTitleW(clean)
                from . import terminal_identity
                terminal_identity.apply_console_icon()
            except Exception:
                pass

        return True
    except Exception:
        return False


def set_terminal_title_state(state):
    """Standardized CAT CLI title states:
    starting | ready | running | exiting."""
    mapping = {
        "starting": "CAT CLI — Starting",
        "ready":    "CAT CLI — Ready",
        "running":  "CAT CLI — Running",
        "exiting":  "CAT CLI — Exiting",
    }
    suffix = mapping.get(str(state).lower())
    if suffix:
        return set_terminal_title(suffix)
    return set_terminal_title(str(state))


def restore_terminal_title():
    """Give the shell its identity back after CAT exits (xterm stack
    pop; terminals that never pushed just keep whatever they had — no
    garbage is printed either way)."""
    global _title_saved
    if not _title_saved or not _title_ok():
        _title_saved = False
        return False
    try:
        sys.stdout.write("\x1b[23t")
        sys.stdout.flush()
        _title_saved = False
        return True
    except Exception:
        _title_saved = False
        return False
