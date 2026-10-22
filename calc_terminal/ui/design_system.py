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
# large  ......... w >= 120 — full three-pane + full dashboard controls
# normal ......... 90 <= w < 120 — standard desktop, full cards
# medium ......... 70 <= w < 90 — 2-pane / 2+1 cards, compact controls
# small .......... 50 <= w < 70 — secondary panels collapse, chat first
# very_small ..... w < 50 or h < 20 — minimal fallback, zero overflow ever
# --------------------------------------------------------------------------
LARGE_MIN_WIDTH = 120
NORMAL_MIN_WIDTH = 90
MEDIUM_MIN_WIDTH = 70
SMALL_MIN_WIDTH = 50
VERY_SMALL_MAX_HEIGHT = 15

# Legacy 4-tier thresholds
LEGACY_MEDIUM_MIN_WIDTH = 80
LEGACY_SMALL_MIN_WIDTH = 56
LEGACY_TINY_MAX_HEIGHT = 18

BP_LARGE = "large"
BP_NORMAL = "normal"
BP_MEDIUM = "medium"
BP_SMALL = "small"
BP_VERY_SMALL = "very_small"
BP_TINY = "tiny"


class CATResponsiveBreakpoints:
    """Centralized 5-tier responsive layout breakpoint engine."""
    LARGE = BP_LARGE
    NORMAL = BP_NORMAL
    MEDIUM = BP_MEDIUM
    SMALL = BP_SMALL
    VERY_SMALL = BP_VERY_SMALL
    TINY = BP_TINY

    TIERS = (
        (LARGE, 120, 28),
        (NORMAL, 90, 24),
        (MEDIUM, 70, 20),
        (SMALL, 50, 16),
        (VERY_SMALL, 0, 0),
    )

    @classmethod
    def classify(cls, width, height=None):
        return breakpoint_for(width, height, five_tier=True)


class CATBorders:
    """Centralized border system tokens — clean, restrained, single-line terminal borders."""
    NONE = "none"
    SOLID = "solid $border"
    FOCUS = "solid $accent"
    CARD = "solid $border"
    CARD_FOCUS = "solid $accent"
    BUTTON = "solid $border"
    BUTTON_FOCUS = "solid $accent"
    COMPOSER = "solid $border"
    COMPOSER_FOCUS = "solid $accent"


class CATSpacing:
    """Centralized character-cell spacing tokens."""
    CARD_PADDING = "1 2"
    CARD_PADDING_COMPACT = "0 1"
    BUTTON_PADDING = "0 1"
    ROW_SPACING = "1 0"
    MARGIN_CARD = "0 1"
    MARGIN_CARD_STACKED = "1 0"


def breakpoint_for(width, height=None, five_tier=False):
    """Classify the live terminal size into responsive tiers.
    By default (five_tier=False), returns legacy 4-tier ('large', 'medium', 'small', 'tiny').
    When five_tier=True, returns 5-tier ('large', 'normal', 'medium', 'small', 'very_small').
    Pure function (unit-testable, no Textual needed). Never raises."""
    try:
        w = int(width or 0)
    except Exception:
        return BP_VERY_SMALL if five_tier else BP_TINY
    try:
        h = int(height) if height is not None else 24
    except Exception:
        h = 24

    if five_tier:
        if w < SMALL_MIN_WIDTH or h < VERY_SMALL_MAX_HEIGHT:
            return BP_VERY_SMALL
        if w < MEDIUM_MIN_WIDTH:
            return BP_SMALL
        if w < NORMAL_MIN_WIDTH:
            return BP_MEDIUM
        if w < LARGE_MIN_WIDTH:
            return BP_NORMAL
        return BP_LARGE

    if w < LEGACY_SMALL_MIN_WIDTH or h < LEGACY_TINY_MAX_HEIGHT:
        return BP_TINY
    if w < LEGACY_MEDIUM_MIN_WIDTH:
        return BP_SMALL
    if w < LARGE_MIN_WIDTH:
        return BP_MEDIUM
    return BP_LARGE


# --------------------------------------------------------------------------
# 45 RESPONSIVE CAT ASCII LOGO VARIANTS (Deterministic, never overflowing)
# --------------------------------------------------------------------------

# 01. MEGA_BLOCK (8 rows, w: 29) - Monumental 8-row block font
_ART_MEGA_BLOCK = [
    " ██████╗   █████╗  ████████╗ ",
    "██╔════╝  ██╔══██╗ ╚══██╔══╝ ",
    "██║       ███████║    ██║    ",
    "██║       ██╔══██║    ██║    ",
    "██║       ██║  ██║    ██║    ",
    "██║       ██║  ██║    ██║    ",
    "╚██████╗  ██║  ██║    ██║    ",
    " ╚═════╝  ╚═╝  ╚═╝    ╚═╝    ",
]

# 02. HERO_ULTRA (7 rows, w: 28) - Majestic high-resolution block
_ART_HERO_ULTRA = [
    " ██████╗   █████╗  ████████╗",
    "██╔════╝  ██╔══██╗ ╚══██╔══╝",
    "██║       ███████║    ██║   ",
    "██║       ██╔══██║    ██║   ",
    "██║       ██║  ██║    ██║   ",
    "╚██████╗  ██║  ██║    ██║   ",
    " ╚═════╝  ╚═╝  ╚═╝    ╚═╝   ",
]

# 03. HERO_3D_ISOMETRIC (7 rows, w: 30) - 3D isometric extruded depth
_ART_HERO_3D_ISOMETRIC = [
    "   ___       ___     _______  ",
    "  / _ \\     / _ \\   /__  __/  ",
    " / / \\_\\   / /_\\ \\    / /     ",
    "| |  _    / ___   |  / /      ",
    "| |_/ /  / /   |  | / /       ",
    " \\___/  /_/    |_| /_/        ",
    "  \\_\\    \\_\\   \\_\\ \\_\\        ",
]

# 04. HERO_LARGE (6 rows, w: 26) - Classic 6-row block letters
_ART_HERO_LARGE = [
    " ██████╗  █████╗ ████████╗",
    "██╔════╝ ██╔══██╗╚══██╔══╝",
    "██║      ███████║   ██║   ",
    "██║      ██╔══██║   ██║   ",
    "╚██████╗ ██║  ██║   ██║   ",
    " ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ",
]

# 05. HERO_SHADOW (6 rows, w: 28) - 6-row drop shadow
_ART_HERO_SHADOW = [
    " ██████╗  ██████╗ ████████╗ ",
    "██╔════╝ ██╔═══██╗╚══██╔══╝ ",
    "██║      ████████║   ██║░░  ",
    "██║      ██╔═══██║   ██║░░  ",
    "╚██████╗ ██║   ██║   ██║░░  ",
    " ╚═════╝ ╚═╝   ╚═╝   ╚═╝░░  ",
]

# 06. HERO_SLANTED (6 rows, w: 25) - 6-row dynamic italic slant
_ART_HERO_SLANTED = [
    "   ______   ___   ______ ",
    "  / ____/  /   | /_  __/ ",
    " / /      / /| |  / /    ",
    "/ /___   / ___ | / /     ",
    "\\____/  /_/  |_|/_/      ",
    " \\___/  /_/  |_|/_/      ",
]

# 07. HERO_OUTLINE (6 rows, w: 28) - 6-row clean wireframe outline
_ART_HERO_OUTLINE = [
    " ┌──────┐ ┌──────┐ ┌───────┐",
    " │ ┌────┘ │ ┌──┐ │ └──┐ ┌──┘",
    " │ │      │ └──┘ │    │ │   ",
    " │ │      │ ┌──┐ │    │ │   ",
    " │ └────┐ │ │  │ │    │ │   ",
    " └──────┘ └─┘  └─┘    └─┘   ",
]

# 08. HERO_CYBER (6 rows, w: 27) - 6-row cyberpunk tech cutouts
_ART_HERO_CYBER = [
    "▄████▄   ▄████▄  ██████████",
    "██▀  ▀▀ ▄██  ██▄    ██     ",
    "██      ████████    ██     ",
    "██▄  ▄▄ ██    ██    ██     ",
    "▀████▀  ██    ██    ██     ",
    "  ▀▀    ▀▀    ▀▀    ▀▀     ",
]

# 09. HERO_DOUBLE_PIPE (6 rows, w: 27) - 6-row double-line pipe block
_ART_HERO_DOUBLE_PIPE = [
    "╔══════╗ ╔══════╗ ╔═══════╗",
    "║ ╔════╝ ║ ╔══╗ ║ ╚═╗ ╔═══╝",
    "║ ║      ║ ╚══╝ ║   ║ ║    ",
    "║ ║      ║ ╔══╗ ║   ║ ║    ",
    "║ ╚════╗ ║ ║  ║ ║   ║ ║    ",
    "╚══════╝ ╚═╝  ╚═╝   ╚═╝    ",
]

# 10. HERO_STANDARD (5 rows, w: 24) - 5-row bold outline
_ART_HERO_STANDARD = [
    "  ____   _____  _______ ",
    " / ___| / _ \\ \\|__   __|",
    "| |    | | | | |  | |   ",
    "| |___ | |_| | |  | |   ",
    " \\____| \\___/|_|  |_|   ",
]

# 11. HERO_DOUBLE (5 rows, w: 23) - 5-row double block font
_ART_HERO_DOUBLE = [
    " ████   ████  ████████ ",
    "██     ██  ██    ██    ",
    "██     ██████    ██    ",
    "██     ██  ██    ██    ",
    " ████  ██  ██    ██    ",
]

# 12. HERO_BLOCK_SHADOW (5 rows, w: 25) - 5-row block with right shadow
_ART_HERO_BLOCK_SHADOW = [
    "█████╗  █████╗ ████████╗ ",
    "██╔══╝  ██╔═██╗╚══██╔══╝ ",
    "██║     ██████║   ██║    ",
    "╚█████╗ ██║ ██║   ██║    ",
    " ╚════╝ ╚═╝ ╚═╝   ╚═╝    ",
]

# 13. HERO_ROUNDED (5 rows, w: 24) - 5-row smooth curved font
_ART_HERO_ROUNDED = [
    " ╭────╮ ╭────╮ ╭───────╮",
    " │ ╭──╯ │ ╭╮ │ ╰──╮ ╭──╯",
    " │ │    │ ╰╯ │    │ │   ",
    " │ ╰──╮ │ ╭╮ │    │ │   ",
    " ╰────╯ ╰─╯╰─╯    ╰─╯   ",
]

# 14. HERO_STENCIL (5 rows, w: 18) - 5-row military stencil cuts
_ART_HERO_STENCIL = [
    "  ___   _   _____ ",
    " / __| /_\\ |_   _|",
    "| (__ / _ \\  | |  ",
    " \\___/_/ \\_\\ |_|  ",
    "  === =   =  ===  ",
]

# 15. HERO_RETRO (5 rows, w: 23) - 5-row retro arcade block
_ART_HERO_RETRO = [
    " ▄████▄   ▄▄▄   ▄▄▄▄▄▄▄",
    "██▀ ▀▀▀  ██ ██    ██   ",
    "██      ███████   ██   ",
    "██▄ ▄▄▄ ██   ██   ██   ",
    " ▀████▀ ▀▀   ▀▀   ▀▀   ",
]

# 16. HERO_COMPACT (4 rows, w: 24) - 4-row BBS slant
_ART_HERO_COMPACT = [
    "   ____    ___   ______ ",
    "  / __/   / _ | /_  __/ ",
    " / /__   / __ |  / /    ",
    " \\___/  /_/ |_| /_/     ",
]

# 17. COMPACT_BLOCK (4 rows, w: 18) - 4-row heavy solid block
_ART_COMPACT_BLOCK = [
    "█████ █████ ██████",
    "██    ██▄▄█   ██  ",
    "██    ██  █   ██  ",
    "█████ ██  █   ██  ",
]

# 18. COMPACT_PIPES (4 rows, w: 21) - 4-row box-drawing pipe art
_ART_COMPACT_PIPES = [
    "┌───┐ ┌───┐ ┌───────┐",
    "│ ┌─┘ │ ┌─┤ └──┐ ┌──┘",
    "│ └─┐ │ └─┤    │ │   ",
    "└───┘ └───┘    └─┘   ",
]

# 19. COMPACT_SHADOW (4 rows, w: 20) - 4-row compact drop shadow
_ART_COMPACT_SHADOW = [
    "▄▄▄▄  ▄▄▄▄  ▄▄▄▄▄▄▄ ",
    "█    █    █    █  ▒ ",
    "█▄▄▄ █▄▄▄▄█    █  ▒ ",
    " ▀▀▀  ▀  ▀     ▀    ",
]

# 20. COMPACT_SEGMENT (4 rows, w: 13) - 4-row 7-segment digital display
_ART_COMPACT_SEGMENT = [
    " _   _   ___ ",
    "/   /_\\   |  ",
    "\\_  | |   |  ",
    " -   -    -  ",
]

# 21. COMPACT_NEON (4 rows, w: 18) - 4-row glowing wire aesthetic
_ART_COMPACT_NEON = [
    "╭──╮  ╭──╮  ──┬── ",
    "│     ├──┤    │   ",
    "╰──╯  ┴  ┴    ┴   ",
    " ''   '  '    '   ",
]

# 22. COMPACT_OUTLINE (4 rows, w: 17) - 4-row wireframe outline
_ART_COMPACT_OUTLINE = [
    " /ˉˉ\\ /ˉˉ\\ ˉˉ|ˉˉ ",
    "|     |---|  |   ",
    " \\__  |   |  |   ",
    "    ˉ        ˉ   ",
]

# 23. MEDIUM_BLOCK (3 rows, w: 20) - 3-row full heavy block
_ART_MEDIUM_BLOCK = [
    "█████  █████  ██████",
    "██     ██▄▄█    ██  ",
    "█████  ██  █    ██  ",
]

# 24. MEDIUM_COMPACT (3 rows, w: 25) - Mascot + medium combo
_ART_MEDIUM_COMPACT = [
    " /\\_/\\   ████  ████ █████",
    "( o.o )  █     █▄▄█   █  ",
    " > ^ <   ████  █  █   █  ",
]

# 25. MEDIUM_DOUBLE (3 rows, w: 14) - 3-row double-line glyphs
_ART_MEDIUM_DOUBLE = [
    "╔═╗ ╔═╗ ╦═══╦ ",
    "║   ╠═╣   ║   ",
    "╚═╝ ╩ ╩   ╩   ",
]

# 26. MEDIUM_HALF_BLOCK (3 rows, w: 14) - 3-row upper/lower half block
_ART_MEDIUM_HALF_BLOCK = [
    "▄▀▀  ▄▀▀▄ ▀█▀ ",
    "█    █▄▄█  █  ",
    " ▀▀  ▀  ▀  ▀  ",
]

# 27. MEDIUM_HEX (3 rows, w: 14) - 3-row hexagonal terminal look
_ART_MEDIUM_HEX = [
    "⬡⬡⬡  ⬢⬢⬢  ⬡⬡⬡ ",
    "⬡    ⬢ ⬢   ⬡  ",
    "⬡⬡⬡  ⬢ ⬢   ⬡  ",
]

# 28. MEDIUM_SLANT (3 rows, w: 19) - 3-row mini italic slant
_ART_MEDIUM_SLANT = [
    "  //   ///|  ||||| ",
    " //   //_||    ||  ",
    "//__ //  ||    ||  ",
]

# 29. MEDIUM_PIPES (3 rows, w: 14) - 3-row box-drawing single pipe
_ART_MEDIUM_PIPES = [
    "┌─┐  ┌─┐  ─┬─ ",
    "│    ├─┤   │  ",
    "└─┘  ┴ ┴   ┴  ",
]

# 30. SMALL_BLOCK (3 rows, w: 15) - 3-row compact half-block
_ART_SMALL_BLOCK = [
    "▄▄▄▄ ▄▄▄▄ █████",
    "█    █▄▄█   █  ",
    "▀▀▀▀ █  █   █  ",
]

# 31. SMALL_COMPACT (3 rows, w: 13) - 3-row bevel
_ART_SMALL_COMPACT = [
    "█▀▀▀ █▀▀█ ▀█▀",
    "█    █▄▄█  █ ",
    "▀▀▀▀ ▀  ▀  ▀ ",
]

# 32. SMALL_PIPES (3 rows, w: 15) - 3-row compact box pipes
_ART_SMALL_PIPES = [
    "┌──┐ ┌──┐ ──┬──",
    "│    ├──┤   │  ",
    "└──┘ ┴  ┴   ┴  ",
]

# 33. SMALL_BRACKET (3 rows, w: 15) - 3-row bracketed retro style
_ART_SMALL_BRACKET = [
    "[==] [==] ==T==",
    "[    [==]   |  ",
    "[==] [  ]   |  ",
]

# 34. MINI_BLOCK (2 rows, w: 10) - 2-row mini block
_ART_MINI_BLOCK = [
    "█▀ █▀█ ▀█▀",
    "▀▀ ▀ ▀  ▀ ",
]

# 35. MINI_INLINE (2 rows, w: 15) - 2-row mascot banner
_ART_MINI_INLINE = [
    "/\\_/\\  [CAT]",
    "> ^ <  TERMINAL",
]

# 36. MINI_PIPES (2 rows, w: 10) - 2-row clean pipes
_ART_MINI_PIPES = [
    "┌─ ┌─┐ ─┬─",
    "└─ ┴ ┴  ┴ ",
]

# 37. MINI_DOTS (2 rows, w: 12) - 2-row dot-matrix font
_ART_MINI_DOTS = [
    "• •  ••• •••",
    "•••  • •  • ",
]

# 38. MINI_SLANT (2 rows, w: 11) - 2-row micro slant
_ART_MINI_SLANT = [
    "/¯ /ˉ\\ /|/",
    "\\_ | |  |  ",
]

# 39. TINY_BLOCK (1 row, w: 9) - 1-row framed block
_ART_TINY_BLOCK = [
    "[ C A T ]",
]

# 40. TINY_INLINE (1 row, w: 13) - 1-row mascot mark
_ART_TINY_INLINE = [
    "(=^･ω･^=) CAT",
]

# 41. TINY_BADGE (1 row, w: 9) - 1-row pill badge
_ART_TINY_BADGE = [
    "❮ C A T ❯",
]

# 42. TINY_CHEVRON (1 row, w: 9) - 1-row chevron
_ART_TINY_CHEVRON = [
    "»» CAT ««",
]

# 43. SINGLE_LINE (1 row, w: 5) - 1-row spaced letters
_ART_SINGLE_LINE = [
    "C A T",
]

# 44. MICRO_MARK (1 row, w: 5) - 1-row diamond mark
_ART_MICRO_MARK = [
    "◆ CAT",
]

# 45. ICON_MARK (1 row, w: 3) - Minimal 3-character icon
_ART_ICON_MARK = [
    "CAT",
]

RESPONSIVE_LOGOS = {
    "MEGA_BLOCK": {"name": "Mega Block", "rows": 8, "min_w": 110, "min_h": 32, "lines": _ART_MEGA_BLOCK},
    "HERO_ULTRA": {"name": "Hero Ultra", "rows": 7, "min_w": 96, "min_h": 28, "lines": _ART_HERO_ULTRA},
    "HERO_3D_ISOMETRIC": {"name": "Hero 3D Isometric", "rows": 7, "min_w": 90, "min_h": 27, "lines": _ART_HERO_3D_ISOMETRIC},
    "HERO_LARGE": {"name": "Hero Large", "rows": 6, "min_w": 82, "min_h": 25, "lines": _ART_HERO_LARGE},
    "HERO_SHADOW": {"name": "Hero Shadow", "rows": 6, "min_w": 80, "min_h": 24, "lines": _ART_HERO_SHADOW},
    "HERO_SLANTED": {"name": "Hero Slanted", "rows": 6, "min_w": 78, "min_h": 23, "lines": _ART_HERO_SLANTED},
    "HERO_OUTLINE": {"name": "Hero Outline", "rows": 6, "min_w": 76, "min_h": 23, "lines": _ART_HERO_OUTLINE},
    "HERO_CYBER": {"name": "Hero Cyber", "rows": 6, "min_w": 74, "min_h": 23, "lines": _ART_HERO_CYBER},
    "HERO_DOUBLE_PIPE": {"name": "Hero Double Pipe", "rows": 6, "min_w": 74, "min_h": 23, "lines": _ART_HERO_DOUBLE_PIPE},
    "HERO_STANDARD": {"name": "Hero Standard", "rows": 5, "min_w": 72, "min_h": 22, "lines": _ART_HERO_STANDARD},
    "HERO_DOUBLE": {"name": "Hero Double", "rows": 5, "min_w": 70, "min_h": 21, "lines": _ART_HERO_DOUBLE},
    "HERO_BLOCK_SHADOW": {"name": "Hero Block Shadow", "rows": 5, "min_w": 68, "min_h": 21, "lines": _ART_HERO_BLOCK_SHADOW},
    "HERO_ROUNDED": {"name": "Hero Rounded", "rows": 5, "min_w": 66, "min_h": 21, "lines": _ART_HERO_ROUNDED},
    "HERO_STENCIL": {"name": "Hero Stencil", "rows": 5, "min_w": 65, "min_h": 20, "lines": _ART_HERO_STENCIL},
    "HERO_RETRO": {"name": "Hero Retro", "rows": 5, "min_w": 65, "min_h": 20, "lines": _ART_HERO_RETRO},
    "HERO_COMPACT": {"name": "Hero Compact", "rows": 4, "min_w": 64, "min_h": 20, "lines": _ART_HERO_COMPACT},
    "COMPACT_BLOCK": {"name": "Compact Block", "rows": 4, "min_w": 62, "min_h": 19, "lines": _ART_COMPACT_BLOCK},
    "COMPACT_PIPES": {"name": "Compact Pipes", "rows": 4, "min_w": 60, "min_h": 19, "lines": _ART_COMPACT_PIPES},
    "COMPACT_SHADOW": {"name": "Compact Shadow", "rows": 4, "min_w": 58, "min_h": 19, "lines": _ART_COMPACT_SHADOW},
    "COMPACT_SEGMENT": {"name": "Compact Segment", "rows": 4, "min_w": 58, "min_h": 18, "lines": _ART_COMPACT_SEGMENT},
    "COMPACT_NEON": {"name": "Compact Neon", "rows": 4, "min_w": 56, "min_h": 18, "lines": _ART_COMPACT_NEON},
    "COMPACT_OUTLINE": {"name": "Compact Outline", "rows": 4, "min_w": 56, "min_h": 18, "lines": _ART_COMPACT_OUTLINE},
    "MEDIUM_BLOCK": {"name": "Medium Block", "rows": 3, "min_w": 54, "min_h": 17, "lines": _ART_MEDIUM_BLOCK},
    "MEDIUM_COMPACT": {"name": "Medium Compact", "rows": 3, "min_w": 48, "min_h": 16, "lines": _ART_MEDIUM_COMPACT},
    "MEDIUM_DOUBLE": {"name": "Medium Double", "rows": 3, "min_w": 46, "min_h": 16, "lines": _ART_MEDIUM_DOUBLE},
    "MEDIUM_HALF_BLOCK": {"name": "Medium Half Block", "rows": 3, "min_w": 44, "min_h": 15, "lines": _ART_MEDIUM_HALF_BLOCK},
    "MEDIUM_HEX": {"name": "Medium Hex", "rows": 3, "min_w": 42, "min_h": 15, "lines": _ART_MEDIUM_HEX},
    "MEDIUM_SLANT": {"name": "Medium Slant", "rows": 3, "min_w": 42, "min_h": 15, "lines": _ART_MEDIUM_SLANT},
    "MEDIUM_PIPES": {"name": "Medium Pipes", "rows": 3, "min_w": 40, "min_h": 15, "lines": _ART_MEDIUM_PIPES},
    "SMALL_BLOCK": {"name": "Small Block", "rows": 3, "min_w": 38, "min_h": 14, "lines": _ART_SMALL_BLOCK},
    "SMALL_COMPACT": {"name": "Small Compact", "rows": 3, "min_w": 34, "min_h": 13, "lines": _ART_SMALL_COMPACT},
    "SMALL_PIPES": {"name": "Small Pipes", "rows": 3, "min_w": 32, "min_h": 13, "lines": _ART_SMALL_PIPES},
    "SMALL_BRACKET": {"name": "Small Bracket", "rows": 3, "min_w": 30, "min_h": 12, "lines": _ART_SMALL_BRACKET},
    "MINI_BLOCK": {"name": "Mini Block", "rows": 2, "min_w": 28, "min_h": 11, "lines": _ART_MINI_BLOCK},
    "MINI_INLINE": {"name": "Mini Inline", "rows": 2, "min_w": 24, "min_h": 10, "lines": _ART_MINI_INLINE},
    "MINI_PIPES": {"name": "Mini Pipes", "rows": 2, "min_w": 22, "min_h": 9, "lines": _ART_MINI_PIPES},
    "MINI_DOTS": {"name": "Mini Dots", "rows": 2, "min_w": 20, "min_h": 9, "lines": _ART_MINI_DOTS},
    "MINI_SLANT": {"name": "Mini Slant", "rows": 2, "min_w": 20, "min_h": 8, "lines": _ART_MINI_SLANT},
    "TINY_BLOCK": {"name": "Tiny Block", "rows": 1, "min_w": 18, "min_h": 7, "lines": _ART_TINY_BLOCK},
    "TINY_INLINE": {"name": "Tiny Inline", "rows": 1, "min_w": 16, "min_h": 6, "lines": _ART_TINY_INLINE},
    "TINY_BADGE": {"name": "Tiny Badge", "rows": 1, "min_w": 14, "min_h": 6, "lines": _ART_TINY_BADGE},
    "TINY_CHEVRON": {"name": "Tiny Chevron", "rows": 1, "min_w": 12, "min_h": 5, "lines": _ART_TINY_CHEVRON},
    "SINGLE_LINE": {"name": "Single Line", "rows": 1, "min_w": 10, "min_h": 5, "lines": _ART_SINGLE_LINE},
    "MICRO_MARK": {"name": "Micro Mark", "rows": 1, "min_w": 8, "min_h": 4, "lines": _ART_MICRO_MARK},
    "ICON_MARK": {"name": "Icon Mark", "rows": 1, "min_w": 0, "min_h": 0, "lines": _ART_ICON_MARK},
}

_LOGO_TIERS_LADDER = [
    ("MEGA_BLOCK", 110, 32),
    ("HERO_ULTRA", 96, 28),
    ("HERO_3D_ISOMETRIC", 90, 27),
    ("HERO_LARGE", 82, 25),
    ("HERO_SHADOW", 80, 24),
    ("HERO_SLANTED", 78, 23),
    ("HERO_OUTLINE", 76, 23),
    ("HERO_CYBER", 74, 23),
    ("HERO_DOUBLE_PIPE", 74, 23),
    ("HERO_STANDARD", 72, 22),
    ("HERO_DOUBLE", 70, 21),
    ("HERO_BLOCK_SHADOW", 68, 21),
    ("HERO_ROUNDED", 66, 21),
    ("HERO_STENCIL", 65, 20),
    ("HERO_RETRO", 65, 20),
    ("HERO_COMPACT", 64, 20),
    ("COMPACT_BLOCK", 62, 19),
    ("COMPACT_PIPES", 60, 19),
    ("COMPACT_SHADOW", 58, 19),
    ("COMPACT_SEGMENT", 58, 18),
    ("COMPACT_NEON", 56, 18),
    ("COMPACT_OUTLINE", 56, 18),
    ("MEDIUM_BLOCK", 54, 17),
    ("MEDIUM_COMPACT", 48, 16),
    ("MEDIUM_DOUBLE", 46, 16),
    ("MEDIUM_HALF_BLOCK", 44, 15),
    ("MEDIUM_HEX", 42, 15),
    ("MEDIUM_SLANT", 42, 15),
    ("MEDIUM_PIPES", 40, 15),
    ("SMALL_BLOCK", 38, 14),
    ("SMALL_COMPACT", 34, 13),
    ("SMALL_PIPES", 32, 13),
    ("SMALL_BRACKET", 30, 12),
    ("MINI_BLOCK", 28, 11),
    ("MINI_INLINE", 24, 10),
    ("MINI_PIPES", 22, 9),
    ("MINI_DOTS", 20, 9),
    ("MINI_SLANT", 20, 8),
    ("TINY_BLOCK", 18, 7),
    ("TINY_INLINE", 16, 6),
    ("TINY_BADGE", 14, 6),
    ("TINY_CHEVRON", 12, 5),
    ("SINGLE_LINE", 10, 5),
    ("MICRO_MARK", 8, 4),
    ("ICON_MARK", 0, 0),
]


def select_logo(width, height=None, available_width=None, available_height=None):
    """Deterministic selection of the best-fitting CAT logo variant based on
    terminal width, height, and available dimensions. Pure function, zero flickering."""
    w = available_width if available_width is not None else width
    h = available_height if available_height is not None else (height or 24)
    try:
        w = max(0, int(w or 0))
    except Exception:
        w = 80
    try:
        h = max(0, int(h or 24))
    except Exception:
        h = 24

    for key, min_w, min_h in _LOGO_TIERS_LADDER:
        if w >= min_w and h >= min_h:
            return key, list(RESPONSIVE_LOGOS[key]["lines"])

    return "ICON_MARK", list(RESPONSIVE_LOGOS["ICON_MARK"]["lines"])


_FALLBACK_FULL_ART = [
    "  ██████╗ █████╗ ████████╗",
    " ██╔════╝██╔══██╗╚══██╔══╝",
    " ██║     ███████║   ██║   ",
    " ██║     ██╔══██║   ██║   ",
    " ╚██████╗██║  ██║   ██║   ",
    "  ╚═════╝╚═╝  ╚═╝   ╚═╝   ",
]

COMPACT_WORDMARK = [
    "▄▄▄▄ ▄▄▄▄▄ █████",
    "█    █▄▄█   █  ",
    "▀▀▀▀ █   █   █  ",
]

MINIMAL_WORDMARK = ["CAT"]

FULL_ART_MIN_WIDTH = 34
COMPACT_ART_MIN_WIDTH = 22


def full_wordmark():
    """Returns the full 6-line CAT block letters matching calc_terminal.app.LOGO."""
    try:
        from ..app import LOGO
        if LOGO:
            return [line.rstrip() for line in LOGO]
    except Exception:
        pass
    return list(_FALLBACK_FULL_ART)


def pick_wordmark(width):
    """Pick the largest wordmark variant that fits `width` columns.
    Returns (variant, lines) where variant is 'full' | 'compact' | 'minimal'.
    Pure function, never raises, never overflows."""
    try:
        w = int(width or 0)
    except Exception:
        w = 0
    if w >= FULL_ART_MIN_WIDTH:
        return ("full", full_wordmark())
    if w >= COMPACT_ART_MIN_WIDTH:
        return ("compact", list(COMPACT_WORDMARK))
    return ("minimal", list(MINIMAL_WORDMARK))


def wordmark_markup(width, height=None, available_width=None, available_height=None, variant_override=None):
    """Gradient-tinted Rich markup for the picked CAT logo variant."""
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

        if variant_override and variant_override in RESPONSIVE_LOGOS:
            lines = list(RESPONSIVE_LOGOS[variant_override]["lines"])
        elif height is not None or available_width is not None or available_height is not None:
            _key, lines = select_logo(width, height, available_width, available_height)
        else:
            _variant, lines = pick_wordmark(width)

        if not lines or lines == ["CAT"]:
            return f"[b]{g_start}CAT[/]"

        n = max(1, len(lines) - 1)
        out = []
        for i, line in enumerate(lines):
            color = _lerp_hex(g_start, g_end, i / n) if _lerp_hex else g_start
            out.append(f"[{color} b]{line}[/]")
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
    from textual.containers import Vertical, Horizontal
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
    /* ---- CAT design system: canonical restrained terminal layer ---- */
    /* Consumes theme_css $variables only — all 22 themes, light   */
    /* mode and AI-mode accents keep working unchanged.            */
    .cat-btn {
        height: 3; min-height: 3; max-height: 3; padding: 0 1;
        min-width: 10;
        border: solid $border;
        background: $surface-alt;
        color: $text;
        text-style: bold;
        content-align: center middle;
        transition: background 80ms, color 80ms, border 80ms;
    }
    .cat-btn:hover {
        background: $accent 24%;
        border: solid $accent;
        color: #ffffff;
        text-style: bold;
    }
    .cat-btn:focus {
        border: solid $accent;
        text-style: bold;
        background-tint: transparent;
    }
    .cat-btn:disabled { opacity: 0.45; text-style: not bold; }
    .cat-btn.cat-pressed {
        border: solid $accent;
        tint: $app-background 20%;
    }
    .cat-btn.-primary { background: $accent 55%; color: #ffffff; border: solid $accent; }
    .cat-btn.-danger { background: $error 45%; color: #ffffff; border: solid $error; }
    .cat-btn-sm { height: 1; min-height: 1; max-height: 1; padding: 0 1; min-width: 6; }

    /* ---- elevated surfaces: clean single-line border and stable surface ---- */
    .cat-panel {
        background: $surface;
        border: solid $border;
        padding: 1 2;
    }
    .cat-card {
        background: $surface;
        border: solid $border;
        padding: 1 2;
        transition: border 100ms;
    }
    .cat-card:hover, .cat-card:focus-within {
        border: solid $accent;
    }
    .cat-elevated { border: solid $border; }

    /* ---- chat bubbles: restrained borders ---- */
    .cat-bubble-user {
        border-right: solid $accent;
    }
    .cat-bubble-assistant {
        border-left: solid $border;
    }
    .cat-codeblock {
        background: $surface-dark;
        border: solid $border;
        padding: 0 1;
    }
    .cat-input {
        background: $surface;
        border: solid $border;
        padding: 0 1;
    }
    .cat-input:focus {
        border: solid $accent;
    }
    .cat-wordmark, .cat-logo { width: auto; text-align: center; }
    .cat-fallback {
        width: 1fr; height: auto; text-align: center;
        color: $text-muted; padding: 1 2;
    }
    .cat-error-card { width: auto; height: auto; color: $text; }

    /* ---- responsive tiers: 5 distinct breakpoints ---- */
    .cat-bp-very-small #cct-chat-nav { display: none; }
    .cat-bp-very-small #cct-chips { display: none; }
    .cat-bp-very-small #cct-kbhints { display: none; }
    .cat-bp-very-small #cct-sidebar-expand-btn { display: none; }
    .cat-bp-very-small #cct-switch-files { display: none; }
    .cat-bp-very-small #cct-center-status { display: none; }
    .cat-bp-small #cct-kbhints { display: none; }
    .cat-bp-small #cct-center-status { display: none; }
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

    class CATLogo(Static):
        """Unified 15-variant responsive CAT ASCII Logo component.
        Deterministic selection, zero flickering, mode-gradient tinting."""

        def __init__(self, width=0, height=None, id="cct-empty-art", classes="cat-logo"):
            super().__init__("", id=id, classes=classes)
            self._variant = None
            self._last_dims = None
            if width:
                self.refresh_logo(width, height)

        def refresh_logo(self, width, height=None, available_width=None, available_height=None, override=None):
            """Deterministically refreshes the logo. Idempotent: repaints only
            when the variant changes or override is toggled."""
            dims = (width, height, available_width, available_height, override)
            if dims == self._last_dims and self._variant is not None:
                return self._variant
            self._last_dims = dims

            if override and override in RESPONSIVE_LOGOS:
                chosen_key = override
            else:
                chosen_key, _ = select_logo(width, height, available_width, available_height)

            if chosen_key != self._variant or override is not None:
                self._variant = chosen_key
                try:
                    self.update(wordmark_markup(width, height, available_width, available_height, variant_override=override))
                except Exception:
                    self.update("[b]CAT[/]")
            return self._variant

        @property
        def variant(self):
            return self._variant or "ICON_MARK"

    class CATStatusBar(Horizontal):
        """Responsive bottom status bar container with automatic breakpoint collapse."""

        def __init__(self, *args, **kwargs):
            classes = kwargs.get("classes", "")
            if "cat-status-bar" not in str(classes).split():
                kwargs["classes"] = (str(classes) + " cat-status-bar").strip()
            super().__init__(*args, **kwargs)

    class CATResponsiveLayout:
        """Utility methods to manage responsive classes on containers."""

        @staticmethod
        def apply_breakpoint(widget, width, height=None):
            """Applies responsive breakpoint class (.cat-bp-*) to widget."""
            if not widget:
                return
            bp = breakpoint_for(width, height)
            for tier in (BP_LARGE, BP_NORMAL, BP_MEDIUM, BP_SMALL, BP_VERY_SMALL):
                cls_name = f"cat-bp-{tier}"
                if tier == bp:
                    if not widget.has_class(cls_name):
                        widget.add_class(cls_name)
                else:
                    if widget.has_class(cls_name):
                        widget.remove_class(cls_name)
            return bp

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
    CATLogo = None
    CATStatusBar = None
    CATResponsiveLayout = None

