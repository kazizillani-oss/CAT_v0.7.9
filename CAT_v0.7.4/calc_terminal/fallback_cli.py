"""
CCT fallback CLI — the plain print()/input() chat renderer, used ONLY
when the primary Textual UI (calc_terminal.ui.app.CCTApp) can't attach:
no real tty, redirected/piped stdout, an unsupported platform, or
Textual not installed. calc_terminal.app.App's main loop and its /ai
and /agent chat commands call into this module for that case.

Renders chat turns as highlighted background bubbles, a typing
indicator, and a streamed (word-by-word) response reveal — all built on
theme.py's colorama-backed background highlighting, no external chat
framework required. `fallback_input()` is the single input entry point
(see its docstring for the two call shapes it covers).
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
import textwrap

from . import theme
from . import anim as _anim
from . import pet as _pet

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.formatted_text import ANSI, HTML
    from prompt_toolkit.styles import Style as PTStyle
    from prompt_toolkit.key_binding import KeyBindings
    _HAS_PROMPT_TOOLKIT = True
except Exception:
    _HAS_PROMPT_TOOLKIT = False

BUBBLE_W = 70

# Sentinel placed in the `below` list to mark the row that should be drawn
# with the animated rail-grow cap instead of printed as a static string.
_oc_rail_cap_obj = object()

# v0.5.6 — the home dashboard's `smart_input` delegates to the new
# OpenCode-style `opencode_input` when this is True (the default). Set to False
# to fall back to the v0.5.2 bordered box. Kept as a module flag so the choice
# is a one-line toggle, not a call-site change.
USE_OPENCODE_INPUT = True


def _wrap_block(s, width):
    out = []
    for para in s.split("\n"):
        out.extend(textwrap.wrap(para, width=width) or [""])
    return out


def _rjust_ansi(s, width):
    pad = max(0, width - theme.vlen(s))
    return " " * pad + s


def _ljust_ansi(s, width):
    pad = max(0, width - theme.vlen(s))
    return s + " " * pad


def user_message(msg, tag="you", term_width=None):
    """A proper, right-aligned chat bubble for the user's message.

    v0.5.6: for LONG user messages (more than one wrapped line), `run()` now
    prefers `user_message_rail()` (the OpenCode left-rail panel) instead. This
    short-message bubble is unchanged for back-compat and short inputs.
    """
    if term_width is None:
        from . import engine
        term_width = engine.WIDTH

    print()
    lines = _wrap_block(msg, BUBBLE_W - 4)
    inner_w = max((len(l) for l in lines), default=0)

    top = "╭" + "─" * (inner_w + 2) + "╮"
    bot = "╰" + "─" * (inner_w + 2) + "╯"

    print(_rjust_ansi(theme.gradient(top, theme.CYAN, theme.GREEN), term_width))
    for l in lines:
        row = "│ " + l.ljust(inner_w) + " │"
        print(_rjust_ansi(theme.bg(row, theme.BG_USER, theme.TEXT), term_width))
    print(_rjust_ansi(theme.gradient(bot, theme.CYAN, theme.GREEN), term_width))
    print(_rjust_ansi(theme.dim(tag.upper()), term_width))
    print()


# ---------------------------------------------------- v0.5.6 OpenCode kit --
# The new hybrid chat surface. These ADD to the functions above — nothing
# above changes signature or behavior. The renderers pick a look by message
# length so the chat reads well for both a one-liner and a full notebook:
#   * short user msg  -> right-aligned gradient bubble (CCT identity, unchanged)
#   * long  user msg  -> OpenCode left-rail filled panel (`user_message_rail`)
#   * short AI reply  -> gradient bubble + `▣ tag · model · dur` footer
#   * long  AI reply  -> borderless indented markdown-ish text + same footer

def _fmt_duration(seconds):
    """Compact duration string for the avatar footer: '3s', '1m 4s', etc."""
    s = max(0, int(seconds))
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


def _ai_footer(tag, model_label, duration):
    """The OpenCode-style assistant footer line: `▣ Tag · model · dur`, with
    the avatar square in the primary accent, the tag in plain text, and the
    model + duration dimmed. Indented to sit under the reply body."""
    mark = theme.fg(theme.SQ_MARK, theme.OC_PRIMARY, bold=True)
    parts = [theme.fg(tag, theme.TEXT, bold=True)]
    if model_label:
        parts.append(theme.fg(model_label, theme.OC_MUTED))
    parts.append(theme.fg(_fmt_duration(duration), theme.OC_MUTED))
    return "  " + mark + " " + theme.fg(" \u00b7 ", theme.OC_MUTED).join(parts)


def thinking(label="CAT AI", model_label=None):
    """The cleaner default 'thinking' indicator: OpenCode's braille spinner
    (`⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` @80ms) inline with `{label} is thinking`, self-erasing.

    A lighter, more modern alternative to the multi-line mascot
    `typing_indicator`. Both exist; this is the v0.5.6 default.
    """
    print()
    suffix = (" " + model_label) if model_label else ""
    _anim.dots_spinner(f"{label}{suffix} is thinking", cycles=12)
    # leave a faint blank so the reply that follows has breathing room
    print()


def user_message_rail(msg, tag="you", term_width=None):
    """OpenCode-style user message: a colored LEFT-rail filled panel (rail in
    the primary accent, `OC_BG_PANEL` fill, NO right border). Used for longer
    user messages; short ones keep the right-aligned bubble (`user_message`).

        ┃ solve PV = nRT with n=2, T=300, P=1   (fill, no right edge)
        ┃
    """
    if term_width is None:
        from . import engine
        term_width = engine.WIDTH
    print()
    # wrap to leave room for the rail + padding on the left
    wrap_w = max(30, min(BUBBLE_W, term_width - 6))
    lines = _wrap_block(msg, wrap_w)
    inner_w = max((len(l) for l in lines), default=0)
    rail = theme.fg(theme.HV, theme.OC_PRIMARY)
    for l in lines:
        row = l + " " * (inner_w - len(l))
        print("  " + rail + " " + theme.bg(row, theme.OC_BG_PANEL, theme.TEXT))
    # terminator row (the half-heavy up bar) + tag
    print("  " + theme.rail_terminator(theme.OC_PRIMARY) + " " + theme.fg(tag.upper(), theme.OC_MUTED))
    print()


def ai_message(text, tag="CAT AI", model_label=None, long=False,
               speed=0.006, duration=0.0):
    """The v0.5.6 adaptive AI reply renderer (full-hybrid mode).

    * `long=False` (default, short replies): a PURPLE→CYAN gradient bubble with
      a streamed word-by-word reveal (same feel as `ai_bubble_stream`), then a
      `▣ {tag} · {model} · {dur}` avatar footer.
    * `long=True` (notebook / derivation-style replies): BORDERLESS indented
      text with simple markdown-ish coloring (ALL-CAPS lines → accent heading,
      `code`/backtick spans → green, `**bold**` → orange), then the same footer.

    `duration` is the measured reply time in seconds (callers pass it from the
    agent run). If 0/unset, no duration segment is appended.

    `ai_bubble_stream` is kept unchanged for back-compat; this is the preferred
    renderer.
    """
    if not text or not text.strip():
        print()
        return

    if long:
        _ai_message_borderless(text, tag, model_label, duration)
    else:
        _ai_message_bubble(text, tag, model_label, duration, speed)


def _ai_message_bubble(text, tag, model_label, duration, speed):
    """Short-reply path: gradient bubble + streamed reveal + avatar footer."""
    lines = _wrap_block(text, BUBBLE_W - 4)
    if not lines:
        return
    inner_w = max((len(l) for l in lines), default=0)
    top = theme.gradient("\u256d" + "\u2500" * (inner_w + 2) + "\u256e", theme.PURPLE, theme.CYAN)
    bot = theme.gradient("\u2570" + "\u2500" * (inner_w + 2) + "\u256f", theme.PURPLE, theme.CYAN)

    print("\n  " + theme.badge(tag, theme.BG_AI, fgcolor=(225, 210, 255)))
    print("  " + top)
    for l in lines:
        # streamed reveal on the first line only; subsequent lines appear
        # instantly (keeps short multi-line answers snappy without losing the
        # "typing" feel on the opening line)
        if l is lines[0] and sys.stdout.isatty() and speed > 0:
            shown = ""
            row_prefix = "  " + theme.gradient("\u2502 ", theme.PURPLE, theme.CYAN)
            row_suffix = theme.gradient(" \u2502", theme.PURPLE, theme.CYAN)
            for word in l.split(" "):
                shown = (shown + " " + word).strip()
                sys.stdout.write("\r" + row_prefix +
                                 theme.bg(_ljust_ansi(shown, inner_w), theme.BG_AI, theme.TEXT) +
                                 row_suffix)
                sys.stdout.flush()
                time.sleep(speed)
        row = "  " + theme.gradient("\u2502 ", theme.PURPLE, theme.CYAN) + \
              theme.bg(_ljust_ansi(l, inner_w), theme.BG_AI, theme.TEXT) + \
              theme.gradient(" \u2502", theme.PURPLE, theme.CYAN)
        sys.stdout.write("\r" + row + "\n")
    print("  " + bot)
    print(_ai_footer(tag, model_label, duration))
    print()


_FENCE_RE = None


def _split_fences(text):
    """Split AI reply text into a list of (\"prose\", text) / (\"code\", lang,
    code) segments on ``` fences. Feeds both the borderless renderer (so
    code blocks get their own bordered, highlighted box instead of being
    flattened into plain indented lines) and the /copycode command (via
    code_editor.remember_block)."""
    global _FENCE_RE
    if _FENCE_RE is None:
        import re
        _FENCE_RE = re.compile(r"```([a-zA-Z0-9_+-]*)\n(.*?)(?:```|\Z)", re.S)
    segments = []
    pos = 0
    for m in _FENCE_RE.finditer(text):
        if m.start() > pos:
            segments.append(("prose", text[pos:m.start()]))
        lang = m.group(1).strip().lower()
        code = m.group(2).rstrip("\n")
        segments.append(("code", lang, code))
        pos = m.end()
    if pos < len(text):
        segments.append(("prose", text[pos:]))
    if not segments:
        segments = [("prose", text)]
    return segments


def _render_code_block(lang, code, width=None):
    """A real bordered, syntax-highlighted code block for AI replies —
    replaces the old behavior of just flattening code into plain indented
    text. Registers the block with code_editor so /copycode can grab it."""
    from . import code_editor as _code_editor
    _code_editor.remember_block(code, lang)
    w = (width or BUBBLE_W) - 4
    lines = code.split("\n")
    highlighter = _code_editor.highlight_python if lang in ("", "py", "python") else theme.text
    inner_w = max([len(l) for l in lines] + [10])
    inner_w = min(inner_w, w)
    top_label = f" {lang or 'code'} "
    print("  " + theme.faint("┌─" + top_label + "─" * max(1, inner_w - len(top_label)) + "┐"))
    for l in lines:
        shown = l if len(l) <= inner_w else l[:inner_w - 1] + "\u2026"
        print("  " + theme.faint("│ ") + highlighter(shown))
    print("  " + theme.faint("└" + "─" * (inner_w + 1) + "┘"))
    print("  " + theme.faint(f"{len(lines)} line(s) \u2022 /copycode to copy this block"))


def _markdown_colorize(line):
    """Cheap inline markdown-ish coloring for the borderless (long) reply:
      * a fully-UPPERCASE (>=3 char) line -> accent heading
      * `spans in backticks` -> green
      * **spans in double-asterisks** -> orange bold
    Anything else is plain TEXT. Only handles simple, non-overlapping spans —
    good enough for notebook-style prose; falls back to plain on no match."""
    import re
    if line.strip() and len(line.strip()) >= 3 and line.strip() == line.strip().upper() and any(c.isalpha() for c in line):
        return theme.fg(line, theme.OC_ACCENT, bold=True)
    out = line
    out = re.sub(r"`([^`]+)`", lambda m: theme.fg(m.group(1), theme.GREEN, bold=True), out)
    out = re.sub(r"\*\*([^*]+)\*\*", lambda m: theme.fg(m.group(1), theme.ORANGE, bold=True), out)
    return out


def _ai_message_borderless(text, tag, model_label, duration):
    """Long-reply path: borderless indented markdown-ish text + footer, the
    OpenCode assistant-message look. No box, no fill — just clean flowing
    text with a `▣ tag · model · dur` footer at the end.

    v0.5.6: any ```fenced``` code block in the reply gets pulled out and
    rendered as its own bordered, syntax-highlighted box (see
    _render_code_block) instead of being flattened into plain indented
    lines — this is what was showing raw, unhighlighted HTML/code before.
    """
    print()
    gutter = "   "
    for seg in _split_fences(text):
        if seg[0] == "code":
            _, lang, code = seg
            print()
            _render_code_block(lang, code)
            print()
            continue
        para_text = seg[1]
        for para in para_text.split("\n"):
            if para.strip() == "":
                print()
                continue
            for wl in _wrap_block(para, BUBBLE_W - 4):
                print(gutter + _markdown_colorize(wl))
    print()
    print("  " + _ai_footer(tag, model_label, duration).lstrip())
    print()


def is_long_reply(text, term_width=None):
    """Heuristic the chat loops use to pick bubble vs borderless for the AI
    reply: more than 4 wrapped lines OR contains an ALL-CAPS section header
    (a hallmark of the agent's notebook output)."""
    if not text:
        return False
    lines = _wrap_block(text, BUBBLE_W - 4)
    if len(lines) > 4:
        return True
    import re
    for ln in text.split("\n"):
        s = ln.strip()
        if s and len(s) >= 3 and s == s.upper() and any(c.isalpha() for c in s):
            return True
    return False


def is_long_question(msg):
    """Heuristic for user messages: pick the rail panel vs the bubble based on
    wrapped-line count (>1 -> rail panel)."""
    if not msg:
        return False
    return len(_wrap_block(msg, BUBBLE_W - 4)) > 1


def render_user(msg, tag="you", term_width=None):
    """Adaptive user message: rail panel for long, bubble for short. This is
    what `run()` calls now instead of `user_message` directly."""
    if is_long_question(msg):
        user_message_rail(msg, tag=tag, term_width=term_width)
    else:
        user_message(msg, tag=tag, term_width=term_width)


def render_ai(text, tag="CAT AI", model_label=None, duration=0.0, term_width=None):
    """Adaptive AI message: borderless for long replies, bubble for short.
    `term_width` accepted for API symmetry; the renderers size off BUBBLE_W."""
    long = is_long_reply(text, term_width)
    ai_message(text, tag=tag, model_label=model_label, long=long, duration=duration)


def typing_indicator(label="Chemistry AI", cycles=3, term_width=None):
    """A multi-line, animated bot 'thinking' indicator.

    v0.5.6: kept as the mascot-style alternate; the cleaner default is now
    `thinking()` (OpenCode's braille spinner). Both are available.
    """
    bot_frames = [
        [" (o.o) ", "/[_]\\", " ] [ "],
        [" (o.O) ", "/[_]\\", " ] [ "],
        [" (O.o) ", "/[_]\\", " ] [ "],
        [" (-.-) ", "/[_]\\", " ] [ "],
    ]
    thinking_frames = [".  ", ".. ", "..."]

    print()  # Start on a new line
    total_frames = cycles * 4
    num_lines_to_clear = len(bot_frames[0]) + 1

    for i in range(total_frames):
        bot_art = bot_frames[i % len(bot_frames)]
        dots = thinking_frames[i % len(thinking_frames)]

        if i > 0:
            sys.stdout.write(f"\033[{num_lines_to_clear}A")

        max_art_width = max(theme.vlen(l) for l in bot_art)
        for line in bot_art:
            padded_line = theme.vpad(line, max_art_width, "center")
            print("  " + theme.gradient(padded_line, theme.CYAN, theme.PURPLE))

        pill = theme.badge(f"{label} is thinking{dots}", theme.BG_AI, fgcolor=(225, 210, 255))
        print("  " + pill + " " * 10)

        sys.stdout.flush()
        time.sleep(0.15)

    # Erase the animation
    sys.stdout.write(f"\033[{num_lines_to_clear}A")
    for _ in range(num_lines_to_clear):
        sys.stdout.write(" " * 60 + "\n")
    sys.stdout.write(f"\033[{num_lines_to_clear}A")
    sys.stdout.flush()


def ai_bubble_stream(text_block, width=BUBBLE_W, speed=0.008, tag="Chemistry AI"):
    """Stream an AI response inside a bubble, next to a bot icon."""
    raw_bot_art = [" (o.o) ", "/[_]\\" , " ] [ "]
    max_bot_width = max(theme.vlen(l) for l in raw_bot_art)
    bot_art = [
        theme.gradient(theme.vpad(l, max_bot_width, "center"), theme.CYAN, theme.PURPLE)
        for l in raw_bot_art
    ]
    bot_width = theme.vlen(bot_art[0])

    lines = _wrap_block(text_block, width - 4)
    if not lines: return

    inner_w = max((len(l) for l in lines), default=0)
    top = theme.gradient("╭" + "─" * (inner_w + 2) + "╮", theme.PURPLE, theme.CYAN)
    bot = theme.gradient("╰" + "─" * (inner_w + 2) + "╯", theme.PURPLE, theme.CYAN)

    print("\n  " + theme.badge(tag, theme.BG_AI, fgcolor=(225, 210, 255)))
    print("  " + bot_art[0] + " " + top)

    for i, l in enumerate(lines):
        bot_line = bot_art[i+1] if i+1 < len(bot_art) else " " * bot_width
        line_prefix = "  " + bot_line + " " + theme.gradient("│ ", theme.PURPLE, theme.CYAN)

        sys.stdout.write(line_prefix)
        shown = ""
        for word in l.split(" "):
            shown = (shown + " " + word).strip()
            sys.stdout.write("\r" + line_prefix +
                              theme.bg(_ljust_ansi(shown, inner_w), theme.BG_AI) +
                              theme.gradient(" │", theme.PURPLE, theme.CYAN))
            sys.stdout.flush()
            time.sleep(speed)

        sys.stdout.write("\r" + line_prefix +
                          theme.bg(_ljust_ansi(l, inner_w), theme.BG_AI) +
                          theme.gradient(" │", theme.PURPLE, theme.CYAN) + "\n")

    bot_line_for_bottom = bot_art[len(lines) + 1] if len(lines) + 1 < len(bot_art) else " " * bot_width
    print("  " + bot_line_for_bottom + " " + bot)

    for i in range(len(lines) + 2, len(bot_art)):
        print("  " + bot_art[i])
    print()


def highlight_line(label, value, bgcolor=theme.BG_INFO, fgcolor=(230, 240, 255)):
    """One highlighted key/value row — used for live readouts (quantum
    numbers, simulation stats, etc.)."""
    return theme.badge(label, bgcolor, fgcolor) + " " + theme.text(value)


TIPS = [
    "\"first order half life\"", "\"mole concept\"", "\"derive second order\"",
    "/solve  \u2014 39 formulas, solved for any variable", "/game  \u2014 learn chemistry by playing",
    "/atomsim Fe  \u2014 watch an iron atom spin up", "/orbitals 3d  \u2014 live electron cloud",
    "/agent  \u2014 an AI that solves, plots & simulates", "\"arrhenius equation\"",
    "/graph  \u2014 animated kinetics & titration curves",
]
_tip_cursor = [0]


def _next_tip():
    i = _tip_cursor[0] % len(TIPS)
    _tip_cursor[0] += 1
    return TIPS[i]


def _xml_escape(s):
    """prompt_toolkit's HTML() parses its input as real XML, so any
    raw '&' (or '<'/'>') in dynamic text — like a TIPS entry mentioning
    'plots & simulates' — breaks it with an ExpatError. Escape before
    ever putting user-facing text inside HTML(...)."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _live_width(fallback=78):
    """Re-measure the terminal width right before drawing the input box,
    instead of trusting the WIDTH constant computed once at startup.
    Startup-only sizing drifts out of alignment whenever the actual
    terminal/embedding pane is a different size than it was at launch
    (a resized window, or a web-embedded pty that reports its size a
    beat after the app starts) — this keeps the box's borders and the
    hint row underneath it consistent with whatever the box was
    actually drawn at."""
    try:
        from . import engine
        return engine.term_width(fallback=fallback)
    except Exception:
        return fallback


def _erase_echoed_input(prefix_w, raw, width):
    """Erase the terminal's own live-typed echo of `raw` so that whatever
    gets printed right after (the chat bubble, the box's closing rows)
    is the ONLY copy of the text left on screen.

    Fixes the reported 'double text' bug: the previous version of this
    function moved the cursor up `rows_used - 1` lines before clearing,
    which is an off-by-one — for the single most common case, a short
    one-line answer (`rows_used == 1`), that's `0` lines, i.e. no
    cursor movement at all. The clear-to-end-of-screen that followed
    then had nothing above it left to erase (the cursor was already on
    the fresh line below, since Enter had just printed a newline), so
    the raw echoed text stayed on screen — and then got printed a
    second time right after it. Moving up the full `rows_used` fixes
    it for every input length, not just the multi-line/pasted case this
    was originally written for.
    """
    if not sys.stdout.isatty():
        return
    try:
        term_cols = shutil.get_terminal_size(fallback=(width, 24)).columns
    except Exception:
        term_cols = width
    total = prefix_w + len(raw)
    rows_used = max(1, -(-total // max(1, term_cols)))
    sys.stdout.write(f"\x1b[{rows_used}A")
    sys.stdout.write("\r\x1b[0J")
    sys.stdout.flush()


def _reflow_submitted_line(raw, row_prefix, width):
    """Clear the terminal's own raw echo of the just-submitted line.

    This used to also re-print the question inline (icon + word-wrapped
    text) directly under the box — which, combined with the chat bubble
    printed a moment later by `user_message()`, was the second half of
    the 'double text' bug: the same line rendered twice, in two
    different styles. Now this only erases; the single canonical
    on-screen copy of what was typed is the chat bubble.
    """
    _erase_echoed_input(theme.vlen(row_prefix), raw, width)


def _clear_input_row_keep_below(prefix_w, raw, width, rows_below):
    """Erase just the plain, unstyled terminal echo of the submitted
    input line, leaving whatever is already drawn *beneath* it (the
    box's meta row, bottom border, hints, tip) untouched, then park
    the cursor on a clean line past all of it.

    Used by `premium_input`, which (as of v0.5.5) draws the rest of
    the box *before* reading input — saving the cursor position with
    `\\x1b[s` right where the input line goes, printing everything
    below it, then jumping back up to that saved spot with `\\x1b[u`
    so the box looks fully closed (border, meta row, hints, tip) from
    the moment it appears, instead of only after Enter is pressed.

    That pre-draw means the old `_erase_echoed_input`'s clear-to-end-
    of-screen (`\\x1b[0J`) can't be reused here — it would wipe out
    the pre-drawn rows along with the echoed text. This clears only
    the row(s) the echo itself occupies, and — rather than counting
    relative cursor moves (the source of the off-by-one bug the old
    function's docstring describes) — always moves via the saved
    anchor, so it can't drift.
    """
    if not sys.stdout.isatty():
        return
    try:
        term_cols = shutil.get_terminal_size(fallback=(width, 24)).columns
    except Exception:
        term_cols = width
    total = prefix_w + len(raw)
    rows_used = max(1, -(-total // max(1, term_cols)))

    sys.stdout.write("\x1b[u")
    for i in range(rows_used):
        sys.stdout.write("\x1b[2K")
        if i < rows_used - 1:
            sys.stdout.write("\x1b[1B")
    sys.stdout.write("\x1b[u")
    sys.stdout.write(f"\x1b[{1 + rows_below}B\r")
    sys.stdout.flush()


def ask(prompt_str, width=None):
    """A drop-in replacement for `input(prompt_str)` for any call site
    that shows the result again right after via `user_message()` (the
    /agent and /ai chat loops). Reads the line normally, then erases
    the terminal's own echo of it so the bubble printed next is the
    only copy on screen — same fix as the main input box, for the
    other two places the same 'double text' pattern showed up."""
    if width is None:
        width = _live_width()
    raw = input(prompt_str)
    _erase_echoed_input(theme.vlen(prompt_str), raw, width)
    return raw


WALK_FRAMES = ["\\o/", " o<", "/o\\", ">o "]


def animate_mascot_intro(width=78, duration=0.9):
    """A tiny ASCII mascot crosses the top of the chatbox before it
    appears — pure single-width ASCII (no emoji) so it can never throw
    off column alignment on any terminal/font.

    v0.5.6: the mascot is a real living pet (see pet.py) — its state
    depends on how long it's been since the user last did something:
    quick back-to-back turns make it *run*, a normal pace has it
    *walk*, and leaving the terminal idle for a while puts it to
    *sleep* (drawn in place with a little zzz instead of crossing the
    screen).
    """
    if not sys.stdout.isatty():
        return
    state = _pet.current_state()
    if state == "sleep":
        for _ in range(10):
            line = _pet.frame_line(width, state="sleep")
            sys.stdout.write("\r" + line + " " * 10)
            sys.stdout.flush()
            time.sleep(0.2)
        sys.stdout.write("\r" + " " * (width + 10) + "\r")
        sys.stdout.flush()
        return
    span = max(10, width - 12)
    delay = 0.018 if state == "run" else 0.03
    steps = max(8, min(span, int(duration / delay)))
    for _ in range(steps):
        line = _pet.frame_line(width, state=state)
        sys.stdout.write("\r" + line + " " * 6)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\r" + " " * (width + 6) + "\r")
    sys.stdout.flush()


def _oc_geometry(term_width):
    """Box width + centering offset for the v0.5.2 chatbox.

    The reference screenshot is a centered box that sits with clean,
    even side margins (not edge-to-edge, not cramped). v0.5.2 tunes the
    proportions so the box is the same calm width on every reasonable
    terminal:

      * ~72% of the terminal width — wide enough to read as a real,
        substantial input object (like the reference) while keeping
        generous breathing room on both sides.
      * clamped to 58-76 columns so it never collapses on a thin
        embedded pane or stretches too wide on a big monitor.
      * centered with equal left/right margins.
    """
    box_w = max(58, min(76, int(term_width * 0.72)))
    if box_w > term_width - 6:
        box_w = max(40, term_width - 6)
    left_pad = max(0, (term_width - box_w) // 2)
    return box_w, left_pad


def _oc_top(box_w, left_pad):
    """Top edge of the v0.5.2 box: a soft left→right navy gradient on
    angular ┌─…─┐ corners — premium depth without becoming a rainbow."""
    return " " * left_pad + theme.soft_border_line(
        box_w, theme.ATL, theme.AH, theme.ATR,
        theme.BORDER_SOFT_A, theme.BORDER_SOFT_B)


def _oc_bottom(box_w, left_pad):
    """Bottom edge — same gradient, mirrored with └─…─┘ corners."""
    return " " * left_pad + theme.soft_border_line(
        box_w, theme.ABL, theme.AH, theme.ABR,
        theme.BORDER_SOFT_B, theme.BORDER_SOFT_A)


def _oc_row_prefix(left_pad, icon):
    """Prompt for the live input row: left border + icon. There's no
    live right-hand border while typing — a single-line prompt can't
    track how much to pad on every keystroke the way a real redrawing
    TUI (which is what OpenCode itself is, under the hood) can. The
    box closes with all four sides once the line is submitted, below."""
    return " " * left_pad + theme.fg(theme.AV, theme.BORDER_SOFT_A) + "  " + icon + "   "


def _oc_meta_row(box_w, left_pad, mode_label, model_label, effort_label):
    """The row under the input line, closed on both sides: mode label
    in bold vivid blue (like 'Build' in the reference image), model
    name dimmed next to it, effort/status word right-aligned in
    amber. This is the second row of the two-row chatbox."""
    inner = box_w - 2
    budget = max(10, inner - 3)

    left_plain = mode_label + ("  " + model_label if model_label else "")
    right_plain = effort_label or ""

    if len(left_plain) + len(right_plain) + 1 > budget:
        avail_right = max(4, budget - len(left_plain) - 1)
        if len(right_plain) > avail_right:
            right_plain = right_plain[:max(1, avail_right - 1)].rstrip() + "\u2026"
        avail_left = max(4, budget - len(right_plain) - 1)
        if len(left_plain) > avail_left:
            left_plain = left_plain[:max(1, avail_left - 1)].rstrip() + "\u2026"
            model_label = None

    gap = max(1, budget - len(left_plain) - len(right_plain))
    left_colored = theme.fg(mode_label, theme.ACCENT_VIVID, bold=True)
    if model_label:
        left_colored += theme.fg("  " + model_label, theme.META_DIM)
    body = "  " + left_colored + " " * gap + theme.fg(right_plain, theme.STATUS_AMBER, bold=True) + " "
    border_l = theme.fg(theme.AV, theme.BORDER_SOFT_A)
    border_r = theme.fg(theme.AV, theme.BORDER_SOFT_B)
    return " " * left_pad + border_l + body + border_r


DEFAULT_HINTS = (("tab", "suggestions"), ("/help", "commands"))


def _oc_hint_row(box_w, left_pad, hints=DEFAULT_HINTS):
    """Keyboard-shortcut hints, right-aligned under the box's right
    edge, printed entirely outside the border — exactly where the
    reference screenshot puts 'tab agents   ctrl+p commands'.

    Each key cap is rendered faint+bold (like a physical key) and its
    label dimmed, with a wider 4-space gutter between pairs so the row
    breathes instead of crowding."""
    text_plain = "    ".join(f"{k} {l}" for k, l in hints)
    colored = "    ".join(
        theme.fg(k, theme.HINT_FAINT, bold=True) + " " + theme.fg(l, theme.HINT_LABEL)
        for k, l in hints)
    total_w = left_pad + box_w
    pad = max(1, total_w - len(text_plain))
    return " " * pad + colored


def _oc_tip_row(left_pad, tip_text):
    """The 'try: ...' callout under the box, left-aligned under its
    left edge with a colored dot — same spot and style as the
    reference screenshot's '\u25cf Tip Run /share...' line."""
    return " " * left_pad + theme.pulse_dot() + " " + theme.dim("try: ") + theme.faint(tip_text)


def premium_input(width=78, show_tip=True, mode_label="NOTEBOOK", model_label=None,
                   effort_label="engine ready", animate=True, hints=DEFAULT_HINTS,
                   right_hint=None):
    """The v0.5.2 chatbox: a narrow, centered, angular-cornered box
    with a soft navy gradient border — same shape, proportions and
    2-row layout as the reference design, but with a refined premium
    feel (calmer palette, sharper corners, better-proportioned width):

        ┌──────────────────────────────────────────────────┐
        │  ⚗   Ask Chemistry…                              │
        │  NOTEBOOK   GEMINI-FLASH-LITE              ready │
        └──────────────────────────────────────────────────┘
                                    tab suggestions  /help commands
        ● try: "arrhenius equation"

    This is the plain-input fallback (no live suggestion dropdown);
    `smart_input()` layers that on top when prompt_toolkit is
    installed. `right_hint` is accepted for backwards compatibility
    and used as `effort_label` if that isn't given explicitly.

    v0.5.5: the meta row, bottom border, hint row and tip line are
    now drawn *before* `input()` is even called — matching the
    reference design, where the whole box (closed on all sides, with
    hints and a tip underneath) is visible from the moment it
    appears, not just after Enter is pressed. The cursor position is
    saved right where the input line goes, everything below it is
    printed, then the cursor jumps back up to that saved spot so
    `input()` reads there with the rest of the box already on screen.
    """
    if right_hint and effort_label == "engine ready":
        effort_label = right_hint
    width = _live_width(fallback=width)
    if animate:
        animate_mascot_intro(width)

    box_w, left_pad = _oc_geometry(width)
    icon = theme.fg(theme.FLASK, theme.ACCENT_VIVID, bold=True)
    row_prefix = _oc_row_prefix(left_pad, icon)

    print(_oc_top(box_w, left_pad))

    tip_text = _next_tip() if show_tip else None
    below = [
        _oc_meta_row(box_w, left_pad, mode_label, model_label, effort_label),
        _oc_bottom(box_w, left_pad),
        _oc_hint_row(box_w, left_pad, hints),
    ]
    if tip_text:
        below.append(_oc_tip_row(left_pad, tip_text))

    interactive = sys.stdout.isatty()
    if interactive:
        sys.stdout.write("\x1b[s")   # anchor: exactly where the input line goes
        print()                      # placeholder row `input()` will read on
        for line in below:
            print(line)
        sys.stdout.write("\x1b[u")   # jump back up to the anchor
        sys.stdout.flush()

    try:
        raw = input(row_prefix)
    except (EOFError, KeyboardInterrupt):
        if interactive:
            sys.stdout.write(f"\x1b[{1 + len(below)}B\r")
            sys.stdout.flush()
        else:
            print(_oc_bottom(box_w, left_pad))
        raise

    if interactive:
        _clear_input_row_keep_below(theme.vlen(row_prefix), raw, width, len(below))
    else:
        # No TTY (piped/non-interactive output, e.g. tests): the
        # cursor tricks above are meaningless, so fall back to the
        # original linear print-after-input order.
        for line in below:
            print(line)
    return raw


if _HAS_PROMPT_TOOLKIT:
    class _SuggestCompleter(Completer):
        """Match-anywhere completer that powers the live suggestion
        dropdown: as soon as what's typed appears anywhere inside a
        known command or question, it shows up as a pickable row."""

        def __init__(self, items):
            self.items = items or []  # list of (trigger_text, description)

        def get_completions(self, document, complete_event):
            typed = document.text_before_cursor.strip().lower()
            if not typed:
                return
            seen = set()
            for trigger, desc in self.items:
                if trigger in seen:
                    continue
                if typed in trigger.lower():
                    seen.add(trigger)
                    yield Completion(
                        trigger,
                        start_position=-len(document.text_before_cursor),
                        display=trigger,
                        display_meta=desc,
                    )

    def _animated_fill(buf, text, speed=0.012):
        """Type a fully-picked suggestion into the buffer letter by
        letter — the closest a terminal can get to a smooth CSS-style
        fill-in animation when a suggestion is accepted with Tab."""
        buf.delete_before_cursor(len(buf.text))
        for ch in text:
            buf.insert_text(ch)
            sys.stdout.flush()
            time.sleep(speed)


_PT_STYLE = None
if _HAS_PROMPT_TOOLKIT:
    # v0.5.2 dropdown palette — tuned to sit inside the soft-navy box
    # instead of fighting it: the selected row lifts to the same vivid
    # blue as the mode word, unselected rows stay calm on the Tokyo
    # Night background.
    _PT_STYLE = PTStyle.from_dict({
        "":                                          "fg:#c0caf5",
        "completion-menu":                           "bg:#16161e fg:#c0caf5",
        "completion-menu.completion":                "bg:#16161e fg:#9aa5d8",
        "completion-menu.completion.current":        "bg:#2a3866 fg:#ffffff bold",
        "completion-menu.meta.completion":            "bg:#16161e fg:#6a78a0 italic",
        "completion-menu.meta.completion.current":    "bg:#2a3866 fg:#dfe5ff",
        "scrollbar.background":                      "bg:#16161e",
        "scrollbar.button":                          "bg:#3a466e",
        "bottom-toolbar":                            "bg:#12121a fg:#6e78a0",
        "placeholder":                               "fg:#565f89",
    })


# ----------------------------------------------------- opencode geometry --
# The v0.5.6 OpenCode-style input: a heavy left `┃` rail + `╹` terminator with
# a `▀` underline cap, a meta row (vivid mode word + dim model + right-aligned
# status), a hint row, and a `● Tip` line. Same proportions as `premium_input`
# (re-uses `_oc_geometry`) but with OpenCode's borderless-left-rail identity.

def _oc_rail_prefix(left_pad):
    """The live input row prefix: left margin + heavy rail `┃` + 2-col gutter
    + the flask icon. Mirrors `_oc_row_prefix` but with the heavy rail instead
    of the angular left border."""
    icon = theme.fg(theme.FLASK, theme.OC_PRIMARY, bold=True)
    return " " * left_pad + theme.fg(theme.HV, theme.OC_PRIMARY) + "  " + icon + "   "


def _oc_rail_meta_row(box_w, left_pad, mode_label, model_label, effort_label):
    """OpenCode meta row: rail + vivid mode word + dim model (left), status
    right-aligned, no right border. Same budget/truncation logic as
    `_oc_meta_row` so long model names still fit."""
    budget = max(10, box_w - 3)
    left_plain = mode_label + ("  " + model_label if model_label else "")
    right_plain = effort_label or ""
    if len(left_plain) + len(right_plain) + 1 > budget:
        avail_right = max(4, budget - len(left_plain) - 1)
        if len(right_plain) > avail_right:
            right_plain = right_plain[:max(1, avail_right - 1)].rstrip() + "\u2026"
        avail_left = max(4, budget - len(right_plain) - 1)
        if len(left_plain) > avail_left:
            left_plain = left_plain[:max(1, avail_left - 1)].rstrip() + "\u2026"
            model_label = None
    gap = max(1, budget - len(left_plain) - len(right_plain))
    left_colored = theme.fg(mode_label, theme.OC_PRIMARY, bold=True)
    if model_label:
        left_colored += theme.fg("  " + model_label, theme.OC_MUTED)
    rail = theme.fg(theme.HV, theme.OC_PRIMARY)
    body = "  " + left_colored + " " * gap + theme.fg(right_plain, theme.OC_ACCENT, bold=True)
    return " " * left_pad + rail + body


def _oc_rail_cap_row(box_w, left_pad):
    """The `▀` underline cap + `╹` terminator: closes the input box visually
    under the meta row, exactly like OpenCode's cap row."""
    inner = box_w - 2
    return " " * left_pad + theme.rail_terminator(theme.OC_PRIMARY) + \
        theme.fg(theme.HALF_UP * inner, theme.OC_PRIMARY)


def _oc_rail_cap_animated(box_w, left_pad, color=None, delay=0.006):
    """Animated version of the cap row: the `╹` terminator prints instantly,
    then the `▀` half-block cap GROWS left→right across the box width (via
    `anim.rail_grow`) so the input box visibly *draws shut* instead of just
    popping in. Falls back to the static `_oc_rail_cap_row` when animations
    are off or there's no TTY."""
    color = color or theme.OC_PRIMARY
    inner = box_w - 2
    # print the terminator + leave the cursor at the start of the cap run
    sys.stdout.write(" " * left_pad + theme.rail_terminator(color))
    sys.stdout.flush()
    _anim.rail_grow(inner, color=color, char=theme.HALF_UP, delay=delay)


def opencode_input(width=78, show_tip=True, mode_label="NOTEBOOK", model_label=None,
                   effort_label="engine ready", animate=True, suggestions=None,
                   hints=DEFAULT_HINTS, right_hint=None):
    """The v0.5.6 OpenCode-style chatbox — the new default look for the home
    dashboard (reached automatically via `smart_input` when
    `USE_OPENCODE_INPUT` is True):

        ┃  ⚗   Ask Chemistry…
        ┃  NOTEBOOK   gemini-flash-lite              ready
        ╹▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
                                    tab suggestions  /help commands
        ● try: "arrhenius equation"

    A single heavy left rail (no right/top/bottom border), a meta row, a `▀`
    cap, then hints + tip outside the rail — same proportions and 2-row layout
    as the reference, with OpenCode's exact row order.

    Keeps the live prompt_toolkit suggestion dropdown when available (same
    completer/Tab-fill/`_PT_STYLE` as `smart_input`); falls back to a plain
    `input()` + the v0.5.5 pre-draw/echo-erase machinery otherwise. Signature
    matches `smart_input` so it's a drop-in.
    """
    if right_hint and effort_label == "engine ready":
        effort_label = right_hint
    width = _live_width(fallback=width)
    if animate:
        animate_mascot_intro(width)

    box_w, left_pad = _oc_geometry(width)
    tip_text = _next_tip() if show_tip else None
    row_prefix = _oc_rail_prefix(left_pad)

    # The input-row rail (top of the box)
    print(" " * left_pad + theme.fg(theme.HV, theme.OC_PRIMARY))

    # Rows printed BELOW the input line — pre-drawn (v0.5.5 pattern) so the box
    # looks fully closed the instant it appears. The cap row is marked with a
    # sentinel so the plain-input path can grow it with an animation.
    below = [
        _oc_rail_meta_row(box_w, left_pad, mode_label, model_label, effort_label),
        _oc_rail_cap_obj,
        _oc_hint_row(box_w, left_pad, hints),
    ]
    if tip_text:
        below.append(_oc_tip_row(left_pad, tip_text))

    interactive = sys.stdout.isatty()

    # ---- prompt_toolkit path: live dropdown + live-rendered below-rows ----
    if _HAS_PROMPT_TOOLKIT and interactive:
        completer = _SuggestCompleter(suggestions)
        kb = KeyBindings()

        @kb.add("tab")
        def _accept(event):
            buf = event.current_buffer
            state = buf.complete_state
            if state and state.completions:
                completion = state.current_completion or state.completions[0]
                _animated_fill(buf, completion.text)
                buf.cancel_completion()
            else:
                buf.start_completion(select_first=False)

        def _toolbar():
            lines = [
                _oc_rail_cap_row(box_w, left_pad) if line is _oc_rail_cap_obj else line
                for line in below
            ]
            return ANSI("\n".join(lines))

        session = PromptSession(
            completer=completer,
            complete_while_typing=True,
            mouse_support=True,
            style=_PT_STYLE,
            key_bindings=kb,
            bottom_toolbar=_toolbar,
            reserve_space_for_menu=6,
            erase_when_done=True,
        )

        label = "Ask Chemistry\u2026"
        inline_tip = _next_tip()
        content_start = theme.vlen(row_prefix) - left_pad
        budget = max(0, box_w - content_start - 1)
        tip_budget = budget - len(label) - 2
        if tip_budget < 6:
            inline_tip = ""
        elif theme.vlen(inline_tip) > tip_budget:
            inline_tip = inline_tip[:max(1, tip_budget - 1)].rstrip() + "\u2026"
        tip_span = f'  <style fg="#565f89">{_xml_escape(inline_tip)}</style>' if inline_tip else ""
        placeholder = HTML(f'<style fg="#9aa5d8">{_xml_escape(label)}</style>{tip_span}')

        try:
            raw = session.prompt(ANSI(row_prefix), placeholder=placeholder)
        except (EOFError, KeyboardInterrupt):
            raise
        finally:
            try:
                from .terminal_host import sanitize_terminal
                sanitize_terminal()
            except Exception:
                pass
        # echo-erase the prompt_toolkit output, then print the canonical box
        _erase_echoed_input(theme.vlen(row_prefix), raw, width)
        return raw

    # ---- plain input() fallback (no prompt_toolkit) -----------------------
    if interactive:
        sys.stdout.write("\x1b[s")   # anchor where the input line goes
        print()                      # placeholder row input() reads on
        # print the below-rows, but render the cap row with a left→right
        # grow animation so the box visibly draws shut.
        for line in below:
            if line is _oc_rail_cap_obj:
                _oc_rail_cap_animated(box_w, left_pad)
            else:
                print(line)
        sys.stdout.write("\x1b[u")   # jump back to the anchor
        sys.stdout.flush()

    try:
        raw = input(row_prefix)
    except (EOFError, KeyboardInterrupt):
        if interactive:
            sys.stdout.write(f"\x1b[{1 + len(below)}B\r")
            sys.stdout.flush()
        raise

    if interactive:
        _clear_input_row_keep_below(theme.vlen(row_prefix), raw, width, len(below))
    else:
        for line in below:
            print(_oc_rail_cap_row(box_w, left_pad) if line is _oc_rail_cap_obj else line)
    return raw


def fallback_input(width=78, show_tip=True, mode_label="NOTEBOOK", model_label=None,
                    effort_label="engine ready", animate=True, suggestions=None,
                    hints=DEFAULT_HINTS, right_hint=None, label=None, bg_color=None,
                    placeholder="Ask a question\u2026", hint=None):
    """THE single fallback-CLI input entry point (used only when the
    primary Textual UI — calc_terminal.ui.app.CCTApp — can't attach: no
    tty, piped stdout, or textual not installed).

    Two call shapes, matching the two contexts the old chatui.py used to
    split across separate functions:

      * `fallback_input(...)` (no `label`) — the home-dashboard box, same
        narrow soft-bordered v0.5.2 chatbox as before, with a live
        suggestion dropdown when prompt_toolkit is installed.
      * `fallback_input(label="AI", bg_color=theme.BG_INFO, ...)` — the
        /ai and /agent chat-loop prompt: a colored badge + `\u276f` arrow
        matching the chat bubbles printed around it, instead of the home
        box (reusing the home box here previously caused a reported
        mismatched-geometry bug).

    This merges what used to be two public functions (`smart_input` /
    `chat_input`) into one entry point, so there's a single fallback
    input implementation instead of two call sites to keep in sync.
    """
    if label is not None:
        return _chat_style_input(label, bg_color or theme.BG_INFO, suggestions=suggestions,
                                  width=width, placeholder=placeholder, hint=hint)
    return _home_style_input(width=width, show_tip=show_tip, mode_label=mode_label,
                              model_label=model_label, effort_label=effort_label,
                              animate=animate, suggestions=suggestions, hints=hints,
                              right_hint=right_hint)


def _home_style_input(width=78, show_tip=True, mode_label="NOTEBOOK", model_label=None,
                       effort_label="engine ready", animate=True, suggestions=None,
                       hints=DEFAULT_HINTS, right_hint=None):
    """Everything `premium_input` does — the same narrow, centered,
    soft-bordered v0.5.2 chatbox — plus a real, live suggestion
    dropdown while typing (the meta row even stays visible live, as a
    prompt_toolkit bottom-toolbar, sitting right under the input
    exactly like the reference design shows it):

      * dropdown appears as soon as what's typed matches a known
        command/topic
      * navigate with \u2191/\u2193, or click a row with the mouse
        (mouse-aware terminals switch the pointer to a hand/click
        cursor over it automatically once mouse reporting is on —
        that part is the terminal emulator's job, not this app's)
      * Tab fills the highlighted row in with a short animated
        letter-by-letter type-in; clicking or pressing Enter on a
        highlighted row fills it in instantly, same as any standard
        autocomplete widget

    Needs `prompt_toolkit` (`pip install prompt_toolkit`); falls back
    to the plain `premium_input()` automatically if it isn't
    installed, so the app still runs with zero extra dependencies.

    v0.5.6: by default delegates to the new OpenCode-style `opencode_input`
    (the heavy left-rail box) via the `USE_OPENCODE_INPUT` flag. Set that flag
    to False to get this v0.5.2 bordered box back unchanged.
    """
    if right_hint and effort_label == "engine ready":
        effort_label = right_hint
    if USE_OPENCODE_INPUT:
        return opencode_input(width=width, show_tip=show_tip, mode_label=mode_label,
                              model_label=model_label, effort_label=effort_label,
                              animate=animate, suggestions=suggestions, hints=hints)
    if not _HAS_PROMPT_TOOLKIT:
        return premium_input(width=width, show_tip=show_tip, mode_label=mode_label,
                              model_label=model_label, effort_label=effort_label,
                              animate=animate, hints=hints)

    width = _live_width(fallback=width)
    if animate:
        animate_mascot_intro(width)

    box_w, left_pad = _oc_geometry(width)
    icon = theme.fg(theme.FLASK, theme.ACCENT_VIVID, bold=True)
    row_prefix = _oc_row_prefix(left_pad, icon)
    print(_oc_top(box_w, left_pad))

    completer = _SuggestCompleter(suggestions)
    kb = KeyBindings()

    @kb.add("tab")
    def _accept(event):
        buf = event.current_buffer
        state = buf.complete_state
        if state and state.completions:
            completion = state.current_completion or state.completions[0]
            _animated_fill(buf, completion.text)
            buf.cancel_completion()
        else:
            buf.start_completion(select_first=False)

    def _toolbar():
        # v0.5.5: the full rest of the box — bottom border, hints,
        # tip included, not just the meta row — rendered as one
        # multi-line toolbar so it's visible live, from the moment
        # the box appears, matching the reference design (previously
        # only the meta row showed here, and everything else waited
        # until Enter was pressed). prompt_toolkit owns this region
        # and redraws it itself on every keystroke, so — unlike the
        # plain-input fallback — there's no need for manual cursor
        # save/restore tricks here; it can't collide with the
        # completion dropdown's reserved space either, since that's
        # laid out above this toolbar, not over it.
        lines = [
            _oc_meta_row(box_w, left_pad, mode_label, model_label, effort_label),
            _oc_bottom(box_w, left_pad),
            _oc_hint_row(box_w, left_pad, hints),
        ]
        if show_tip:
            lines.append(_oc_tip_row(left_pad, below_tip))
        return ANSI("\n".join(lines))

    session = PromptSession(
        completer=completer,
        complete_while_typing=True,
        mouse_support=True,
        style=_PT_STYLE,
        key_bindings=kb,
        bottom_toolbar=_toolbar,
        reserve_space_for_menu=6,
        erase_when_done=True,
    )

    inline_tip = _next_tip()
    below_tip = _next_tip()
    # Clean two-tone placeholder: the prompt itself in a calm gray, the
    # rotating example suggestion in a fainter tone — the same quiet
    # hierarchy premium input fields use (label dim, sample fainter).
    #
    # v0.5.4 fix: trim/drop the tip so "icon + label + tip" never
    # renders wider than the box itself. Previously this text had no
    # width budget at all, so on a narrow terminal — where
    # `_oc_geometry` clamps box_w down via `term_width - 6` — a long
    # tip like '"first order half life"' printed straight past the
    # box's right edge. Because the border above/below is drawn at
    # the (narrower) box_w, that made the border look like it cut off
    # mid-word instead of framing the whole line (reported bug).
    label = "Ask Chemistry\u2026"
    content_start = theme.vlen(row_prefix) - left_pad
    budget = max(0, box_w - content_start - 1)
    tip_budget = budget - len(label) - 2
    if tip_budget < 6:
        inline_tip = ""
    elif theme.vlen(inline_tip) > tip_budget:
        inline_tip = inline_tip[:max(1, tip_budget - 1)].rstrip() + "\u2026"

    tip_span = f'  <style fg="#565f89">{_xml_escape(inline_tip)}</style>' if inline_tip else ""
    placeholder = HTML(f'<style fg="#9aa5d8">{_xml_escape(label)}</style>{tip_span}')

    try:
        raw = session.prompt(ANSI(row_prefix), placeholder=placeholder)
    except (EOFError, KeyboardInterrupt):
        print(_oc_bottom(box_w, left_pad))
        raise
    finally:
        try:
            from .terminal_host import sanitize_terminal
            sanitize_terminal()
        except Exception:
            pass

    print(_oc_meta_row(box_w, left_pad, mode_label, model_label, effort_label))
    print(_oc_bottom(box_w, left_pad))
    print(_oc_hint_row(box_w, left_pad, hints))
    if show_tip:
        print(_oc_tip_row(left_pad, below_tip))
    return raw


def _chat_style_input(label, bg_color, suggestions=None, width=None,
                       placeholder="Ask a question\u2026", hint=None):
    """Suggestion-aware input for the /ai and /agent chat loops.

    Deliberately keeps THEIR OWN look — a colored ' AI '/' AGENT ' badge
    plus a `\u276f` arrow, matching every chat bubble printed around it —
    instead of borrowing the home dashboard's bordered 'Ask Chemistry…'
    box (`smart_input`). Reusing that box here was the cause of a
    reported bug: its placeholder is hard-coded to 'Ask Chemistry…' and
    its box geometry is tuned for the home screen, so inside /ai or
    /agent it rendered a mismatched, sometimes misaligned, generic box
    instead of the distinct AI/Agent chat prompt. This gives the same
    live autocomplete dropdown (arrow keys, Tab to fill, mouse click)
    without changing that prompt's identity.

    Falls back to plain `ask()` (no dropdown) if prompt_toolkit isn't
    installed, so the app still runs with zero extra dependencies.
    """
    if width is None:
        width = _live_width()
    prompt_str = theme.bg(f" \u2588 {label} \u2588 ", bg_color) + " \u276f "

    if not _HAS_PROMPT_TOOLKIT:
        raw = ask(prompt_str, width=width)
        if hint:
            print(theme.faint("  " + hint))
        return raw

    completer = _SuggestCompleter(suggestions)
    kb = KeyBindings()

    @kb.add("tab")
    def _accept(event):
        buf = event.current_buffer
        state = buf.complete_state
        if state and state.completions:
            completion = state.current_completion or state.completions[0]
            _animated_fill(buf, completion.text)
            buf.cancel_completion()
        else:
            buf.start_completion(select_first=False)

    session = PromptSession(
        completer=completer,
        complete_while_typing=True,
        mouse_support=True,
        style=_PT_STYLE,
        key_bindings=kb,
        reserve_space_for_menu=6,
        erase_when_done=True,
    )
    placeholder_ft = HTML(f'<style fg="#565f89">{placeholder}</style>')

    try:
        raw = session.prompt(ANSI(prompt_str), placeholder=placeholder_ft)
    except (EOFError, KeyboardInterrupt):
        raise
    finally:
        try:
            from .terminal_host import sanitize_terminal
            sanitize_terminal()
        except Exception:
            pass
    _erase_echoed_input(theme.vlen(prompt_str), raw, width)
    if hint:
        print(theme.faint("  " + hint))
    return raw


def prompt_bar():
    """The premium highlighted 'Ask Chemistry…' input bar."""
    left = theme.bg(" \u276f ", theme.BG_INFO, (150, 220, 255))
    hint = theme.dim("Ask Chemistry\u2026 ")
    return left + " " + hint


def status_ribbon(items):
    """A row of status key/values, e.g. mode / engine / precision.

    v0.7.9.0 (requirement #34 — remove DECORATIVE text highlighting):
    this used to paint every chip with a filled color BACKGROUND
    (badge()), which made ordinary labels look selected/active. Now it's
    clean typography only — dim uppercase keys, normal values, separated
    by dots. Legitimate selection/focus states elsewhere are untouched."""
    chips = []
    for label, val in items:
        chips.append(theme.dim(f"{label} ".upper()) + theme.text(str(val)))
    return "  \u00b7  ".join(chips)
