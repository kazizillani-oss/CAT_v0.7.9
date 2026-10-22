"""
Reusable animation primitives for Chemistry Calc Terminal — the "creativity
on interface with animation" layer.

Each function is self-contained, TTY-aware (no-op + clean fallback when output
isn't a real terminal, e.g. piped or under tests), and built entirely on
`theme`'s 24-bit ANSI helpers. Used by boot, the `/art` browser, easter eggs,
and the new chat surface.

Animation policy: every function here checks `engine.ANIMATE` (the existing
global flag) and, if off, degrades to an instant static render. So `engine
--no-animation` users get the same final visual, just without motion.
"""

if __name__ == '__main__':
    print("This is a library file and is not meant to be run directly.")
    print("Please run 'python main.py' or 'python model.py' from the project root directory.")
    import sys
    sys.exit(1)

import random
import shutil
import sys
import time

from . import theme

try:
    from . import engine as _engine
except Exception:
    _engine = None


def _animate_enabled():
    """Honour the global ANIMATE flag when present; default to True."""
    if _engine is not None:
        return getattr(_engine, "ANIMATE", True)
    return True


def _is_tty():
    return sys.stdout.isatty()


# OpenCode's exact braille spinner frames, in order, at 80ms — the same set
# OpenCode's generic Spinner uses (`spinner.tsx`).
BRAILLE_FRAMES = ["\u280b", "\u2819", "\u2839", "\u2838", "\u283c",
                  "\u2834", "\u2826", "\u2827", "\u2807", "\u280f"]


def dots_spinner(label="thinking", cycles=10, color=None, interval=0.08):
    """OpenCode-style inline braille spinner with a label, self-erasing.

    Renders `{frame} {label}` on one line, cycling the braille frames, then
    erases the whole line when done (cursor stays on a clean line for whatever
    prints next). No-op when not a TTY or animations are off.
    """
    if not _is_tty() or not _animate_enabled():
        return
    color = color or theme.OC_PRIMARY
    last_w = 0
    for i in range(max(1, cycles)):
        frame = BRAILLE_FRAMES[i % len(BRAILLE_FRAMES)]
        cell = theme.fg(frame, color, bold=True) + " " + theme.fg(label, theme.OC_MUTED)
        w = theme.vlen(cell) + 2
        pad = " " * max(0, last_w - w)
        sys.stdout.write("\r" + cell + pad)
        sys.stdout.flush()
        last_w = w
        time.sleep(interval)
    # erase the line we drew
    sys.stdout.write("\r" + " " * (last_w + 1) + "\r")
    sys.stdout.flush()


def text_shimmer(s, colors=None, passes=1, step=0.02, bold=True):
    """Animate a moving gradient 'shimmer' across `s`, then leave the final
    gradient render printed in place.

    Each pass slides the color phase across the characters, so a CYAN→PURPLE
    gradient appears to flow left→right. Finishes with the static gradient so
    the text stays readable. No-op (prints the static gradient only) when not a
    TTY or animations are off.
    """
    if colors is None:
        colors = (theme.CYAN, theme.PURPLE, theme.CYAN)
    live = _is_tty() and _animate_enabled()
    n = max(1, len(s) - 1)
    b = theme.BOLD if bold else ""
    phases = range(0, n, max(1, n // 10)) if live else [0]

    for p in range(max(1, passes)):
        for off in phases:
            out = []
            for i, ch in enumerate(s):
                if ch == " ":
                    out.append(" ")
                    continue
                t = ((i / n) + (off / max(1, n))) % 1.0
                c = theme._stops(t, list(colors))
                out.append(f"{b}{theme.rgb(*c)}{ch}")
            out.append(theme.RESET)
            if live:
                sys.stdout.write("\r" + "".join(out))
                sys.stdout.flush()
                time.sleep(step)
    if live:
        sys.stdout.write("\r")
    # final static render
    print(theme.gradient(s, *colors, bold=bold))


def bars_load(label="warming up", duration=0.7, width=34, color=None):
    """An OpenCode-style filling blocks bar: `▀▄` pairs sweep in left→right
    with a label and a percentage, ending at 100%. A richer sibling of
    `theme.progress_bar`. Falls back to a single static line when not animated.
    """
    color = color or theme.OC_PRIMARY
    steps = 22
    label_cell = theme.fg(label, theme.OC_MUTED)
    live = _is_tty() and _animate_enabled()
    for i in range(steps + 1):
        filled = int(width * i / steps)
        # alternate half-blocks for a woven look
        bar_chars = []
        for j in range(width):
            if j < filled:
                bar_chars.append(theme.HALF_UP if j % 2 == 0 else theme.HALF_DN)
            else:
                bar_chars.append(theme.fg("\u2591", theme.OC_BG_ELEMENT))
        bar = theme.fg("".join(bar_chars[:filled]), color) + "".join(bar_chars[filled:])
        pct = int(100 * i / steps)
        sys.stdout.write(f"\r  {label_cell} {bar} {theme.fg(str(pct) + '%', theme.TEXT, bold=True)}")
        sys.stdout.flush()
        if live:
            time.sleep(duration / steps)
    sys.stdout.write("\n")


def scanline_clear(width=None, duration=0.25, color=None):
    """A single `▞` sweep line that travels top→bottom across `height` rows
    then clears, used as a premium transition between major screens. Leaves the
    screen empty afterward (caller draws the next view fresh). No-op when not a
    TTY or animations are off.

    Implemented as a vertical sweep of a full-width dim line so it reads as a
    scan-wipe without needing to know the full screen content.
    """
    if not _is_tty() or not _animate_enabled():
        return
    color = color or theme.OC_BORDER
    try:
        cols, rows = shutil.get_terminal_size(fallback=(78, 24))
    except Exception:
        cols, rows = 78, 24
    if width is None:
        width = cols
    line = theme.fg(theme.SWEEP * width, color)
    theme.hide_cursor()
    try:
        steps = max(3, min(rows - 2, 10))
        for i in range(steps):
            # move down `i+1` rows from the current line, draw, then it'll be
            # overwritten by the next step — simplest robust sweep that doesn't
            # depend on absolute cursor coordinates.
            if i > 0:
                sys.stdout.write(f"\033[1A\r")  # step back up one row
            sys.stdout.write("\r" + line)
            sys.stdout.flush()
            time.sleep(duration / steps)
            sys.stdout.write("\r" + " " * width + "\r")
            sys.stdout.flush()
            sys.stdout.write("\n")
    finally:
        theme.show_cursor()


def bouncy_reveal(lines, delay=0.04, color=None, colors=None, bold=True,
                  align="center", width=None):
    """Reveal a block of lines (typically ASCII art) one at a time with a
    gentle vertical 'bounce': each line is printed, briefly re-drawn one row up,
    then settled — giving art a playful entrance. Lines may be plain or already
    ANSI-colored; plain lines get a gradient via `theme.gradient`.

    `colors` (a tuple) drives the gradient. `color` (single) is a fallback if
    `colors` is None. Falls back to a flat one-line-at-a-time reveal (same as
    `theme.reveal_lines`) when not animated.
    """
    if colors is None:
        colors = (theme.CYAN, theme.PURPLE) if color is None else (color, color)
    live = _is_tty() and _animate_enabled()
    for idx, line in enumerate(lines):
        if line.strip() == "":
            print()
            continue
        # If the line already contains ANSI color codes, render as-is;
        # otherwise apply the gradient.
        already_colored = "\033[" in line
        rendered = line if already_colored else theme.gradient(line, *colors, bold=bold)
        if align == "center" and width:
            rendered = theme.vpad(rendered, width, "center")
        if live:
            # print, nudge up, reprint — the 'bounce'
            print(rendered)
            sys.stdout.write("\033[1A\r")  # up one row, col 0
            time.sleep(delay * 0.4)
            sys.stdout.write(rendered + "\n")
            sys.stdout.flush()
            time.sleep(delay * 0.6)
        else:
            print(rendered)
            time.sleep(delay)


def confetti_burst(width=None, count=20, colors=None, duration=0.5):
    """A quick celebratory scatter of `* ✦ · +` glyphs in assorted colors
    across the top of the current area, used by easter eggs and `/art` reveals.
    Self-erasing. No-op when not a TTY or animations are off.
    """
    if not _is_tty() or not _animate_enabled():
        return
    if colors is None:
        colors = [theme.CYAN, theme.PURPLE, theme.ORANGE, theme.GREEN, theme.OC_ACCENT]
    if width is None:
        try:
            width = shutil.get_terminal_size(fallback=(78, 24)).columns
        except Exception:
            width = 78
    glyphs = ["*", "\u2726", "\u00b7", "+", "\u2727"]  # * ✦ · + ✧
    rng = random.Random()
    rows = 3
    theme.hide_cursor()
    try:
        frames = 8
        for f in range(frames):
            grid = [[" "] * width for _ in range(rows)]
            for _ in range(count):
                x = rng.randrange(width)
                y = rng.randrange(rows)
                grid[y][x] = theme.fg(rng.choice(glyphs), rng.choice(colors), bold=True)
            buf = "\n".join("".join(r) for r in grid)
            if f > 0:
                sys.stdout.write(f"\033[{rows}A")
            sys.stdout.write("\r" + buf + "\n")
            sys.stdout.flush()
            time.sleep(duration / frames)
        # erase
        sys.stdout.write(f"\033[{rows}A")
        for _ in range(rows):
            sys.stdout.write("\r" + " " * width + "\n")
        sys.stdout.write(f"\033[{rows}A\r")
        sys.stdout.flush()
    finally:
        theme.show_cursor()


# =================================================================== v0.5.6 ==
# Additional "creativity on interface with animation" primitives — the extra
# motion layer for the polished OpenCode-style chat surface. Each is TTY-aware
# and honours the global ANIMATE flag, degrading to a static render otherwise.

def rail_grow(width, color=None, char=None, delay=0.006):
    """Animate a horizontal bar (default the OpenCode `▀` half-block cap)
    growing left→right in place, then leave the full bar printed.

    Used as the closing cap of the OpenCode input box so the box doesn't just
    *appear* — it *draws shut*, the way a real TUI slides its elements in.
    Returns nothing; prints one line. No-op animation when not a TTY/anim off
    (still prints the finished bar so the box stays visually closed)."""
    color = color or theme.OC_PRIMARY
    ch = char or theme.HALF_UP
    live = _is_tty() and _animate_enabled()
    width = max(1, width)
    if live:
        for n in range(1, width + 1):
            # ease-out-ish: step a little faster as it nears completion
            sys.stdout.write("\r" + theme.fg(ch * n, color))
            sys.stdout.flush()
            time.sleep(delay)
        sys.stdout.write("\n")
    else:
        print(theme.fg(ch * width, color))


def wave_pulse(width, color_a=None, color_b=None, cycles=2, delay=0.05):
    """An animated sine-wave divider using block-height glyphs
    (`▁▂▃▄▅▆▇█▇▆▅▄▃▂▁`) that scrolls left→right, then settles on a static
    gradient rule. A premium section break between the chat history and the
    next input box. Degrades to a static gradient rule when not animated."""
    color_a = color_a or theme.OC_PRIMARY
    color_b = color_b or theme.OC_SECONDARY
    blocks = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588\u2587\u2586\u2585\u2584\u2583\u2582"
    live = _is_tty() and _animate_enabled()
    width = max(8, width)
    if not live:
        print(theme.gradient(blocks[:width] if width < len(blocks) else blocks * (width // len(blocks) + 1),
                             color_a, color_b))
        return
    n = len(blocks)
    phase = 0
    total = cycles * n
    last_w = width
    theme.hide_cursor()
    try:
        for _ in range(total):
            row = "".join(blocks[(phase + j) % n] for j in range(width))
            # two-tone by position so it reads as a flowing wave
            out = "".join(
                theme.fg(row[j], color_a if (j % n) < n // 2 else color_b)
                for j in range(width))
            sys.stdout.write("\r" + out + " " * max(0, last_w - width))
            sys.stdout.flush()
            last_w = width
            phase += 1
            time.sleep(delay)
        # settle to a clean static gradient rule
        sys.stdout.write("\r" + theme.gradient("\u2500" * width, color_a, color_b) + "\n")
        sys.stdout.flush()
    finally:
        theme.show_cursor()


def bouncing_dots(label="thinking", count=3, color=None, cycles=12, delay=0.12):
    """Three dots that bounce up and down in sequence beside a label — a
    playful alternate to the braille spinner. Self-erasing. No-op when not a
    TTY or animations are off."""
    if not _is_tty() or not _animate_enabled():
        return
    color = color or theme.OC_PRIMARY
    heights = [" ", "\u2584", "\u2580"]  # below / dot / above baseline
    for _ in range(max(1, cycles)):
        for offset in range(len(heights)):
            cells = []
            for d in range(count):
                # each dot is phase-shifted so they ripple
                h = (offset + d) % len(heights)
                cells.append(theme.fg(heights[h], color, bold=True) if heights[h] != " " else " ")
            row = theme.fg(label, theme.OC_MUTED) + "  " + " ".join(cells)
            sys.stdout.write("\r" + row + "   ")
            sys.stdout.flush()
            time.sleep(delay)
    # erase
    sys.stdout.write("\r" + " " * (theme.vlen(theme.fg(label, theme.OC_MUTED)) + 2 + count * 2 + 3) + "\r")
    sys.stdout.flush()


def glow_pulse(text, color=None, cycles=4, delay=0.12, bold=True):
    """Pulse `text` between dim and vivid brightness a few times, then leave
    it printed vivid — a soft "alive" highlight for role labels / status
    words. No-op animation (static vivid print) when not a TTY/anim off."""
    color = color or theme.OC_PRIMARY
    vivid = color
    dim = tuple(int(c * 0.45) for c in color)   # darken ~55% for the dim beat
    live = _is_tty() and _animate_enabled()
    if not live:
        print(theme.fg(text, vivid, bold=bold))
        return
    n = max(2, len(text))
    for i in range(max(1, cycles) * 2):
        beat = vivid if i % 2 == 0 else dim
        # gradient across the text for a little shimmer while it pulses
        rendered = theme.gradient(text, beat, vivid, bold=bold)
        sys.stdout.write("\r" + rendered + " " * 2)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\r")
    print(theme.gradient(text, vivid, color_b=theme.OC_SECONDARY, bold=bold))
