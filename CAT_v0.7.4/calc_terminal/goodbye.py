"""
CAT v0.7.9.0 — goodbye.py: the unified animated shutdown experience.

ONE centralized shutdown flow for every normal exit path:

    Ctrl+Q (Textual) · /quit · /exit · EOF · task/session completion
        ↓
    shutdown_session(...)            ← idempotent entry point
        ↓
    generate_session_message(...)    ← shared AI farewell generator
        ↓                            (uses aicore.query_ai — the SAME
    render_goodbye(...)                provider/failover system the
        ↓                              Textual UI uses for every reply;
    cleanup + flush                    bounded ~2.5 s, falls back to a
                                       local line when AI is unavailable)

SINGLE-RENDER ARCHITECTURE (v0.7.9.4 fix):

There is exactly ONE renderer (render_goodbye) and exactly ONE owner
(shutdown_session). No other module prints goodbye art. The old build
replaced animation frames with RELATIVE cursor-up moves — which desync
the instant any rendered line wraps to a second row, leaving compounded
residual frames ("GOOD BYE / GOOD BYE", giant corrupted CAT stacks).
The renderer is now wrap-proof by construction:

* every drawn line is left-aligned at a fixed 2-column indent with NO
  width-based padding, so no line can ever exceed its natural block
  width (≤ 34 cells);
* art variants are picked from the LIVE terminal width (full /
  compact / wordmark) BEFORE drawing;
* all rules/bars are clipped to the terminal width;
* frames replace each other with cursor-up over a CONSTANT row height,
  which can now never be wrong;
* the screen is cleared once up-front (\x1b[2J) so no stale Textual
  output or earlier scrollback shares the region.

Hard rules:

* IDEMPOTENT — shutdown_session can never render twice.
* NEVER FAILS ON AI — farewell generated off-thread with a hard timeout;
  local fallback otherwise; the farewell string is generated exactly
  ONCE per shutdown and reused by the renderer.
* TERMINAL-ONLY — plain text + ANSI inside the current terminal.
* READABLE EVERYWHERE — gradients from the CURRENT theme; clean static
  fallback with zero escape litter when color isn't supported.
* FAST — ~1.3 s of animation.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os
import random
import sys
import threading
import time

_CAT_FACE = (
    r"  /\_/\ ",
    r" ( o.o )",
    r"  > ^ <",
)

# "GOOD BYE" in the same ANSI-shadow block style as the CAT logo.
_GOODBYE_BLOCK = (
    "░██████╗░░█████╗░░█████╗░██████╗░  ██████╗░██╗░░░██╗███████╗",
    "██╔════╝░██╔══██╗██╔══██╗██╔══██╗  ██╔══██╗╚██╗░██╔╝██╔════╝",
    "██║░░██╗░██║░░██║██║░░██║██║░░██║  ██████╦╝░╚████╔╝░█████╗░░",
    "██║░░╚██╗██║░░██║██║░░██║██║░░██║  ██╔══██╗░░╚██╔╝░░██╔══╝░░",
    "╚██████╔╝╚█████╔╝╚█████╔╝██████╔╝  ██████╦╝░░░██║░░░███████╗",
    "░╚═════╝░░╚════╝░░╚════╝░╚═════╝░  ╚═════╝░░░░╚═╝░░░╚══════╝",
)
_GOODBYE_BLOCK_W = max(len(l) for l in _GOODBYE_BLOCK)

# Compact CAT logo for narrow terminals (same glyphs as the chat
# empty-state/dashboard compact variant).
_COMPACT_LOGO = (
    " ██████╗  █████╗ ████████╗",
    "██╔════╝ ██╔══██╗╚══██╔══╝",
    "██║      ███████║   ██║   ",
    "██║      ██╔══██║   ██║   ",
    "╚██████╗ ██║  ██║   ██║   ",
    " ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ",
)

_FALLBACK_LINES = (
    "Session complete. Keep building amazing things with CAT. \U0001F43E",
    "Great work today! CAT will be here when you need us. \U0001F43E",
    "All wrapped up. Thanks for coding with CAT \u2014 see you soon! \U0001F43E",
    "Session saved successfully. Happy coding! \U0001F43E",
    "Done! CAT is signing off \u2014 catch you next time! \U0001F43E",
)

_ANIM_FRAME_S = 0.09
_ANIM_FRAMES = 6
_FACE_HOLD_S = 0.35
_FAREWELL_AI_TIMEOUT_S = 2.5

_shutdown_lock = threading.Lock()
_shutdown_state = {"done": False}


def reset_for_tests():
    with _shutdown_lock:
        _shutdown_state["done"] = False


def already_shown():
    return _shutdown_state["done"]


def _color_ok(stream=None):
    try:
        stream = stream or sys.stdout
        if os.environ.get("NO_COLOR"):
            return False
        if os.environ.get("TERM", "") == "dumb":
            return False
        return bool(getattr(stream, "isatty", lambda: False)())
    except Exception:
        return False


def _term_width(stream=None, default=80):
    try:
        return os.get_terminal_size(fileno=stream.fileno()).columns \
            if hasattr(stream, "fileno") else default
    except Exception:
        return default


def generate_session_message(context=None, timeout=_FAREWELL_AI_TIMEOUT_S,
                             stream=None):
    """THE shared session-message generator (spec #10): both the Textual
    UI and this CLI goodbye ask the same function for farewell text.

    Routes through aicore.query_ai — the exact provider + backup-failover
    machinery every Textual reply uses — on a daemon thread with a hard
    `timeout`, so shutdown can NEVER hang on the API and NEVER fails
    because of it."""
    result = {"text": ""}

    def _worker():
        try:
            from . import aicore
            cfg = aicore.load_config() or {}
            if not cfg.get("provider"):
                return
            ctx = (context or {}).get("summary", "")
            prompt = (
                "Write ONE short, warm farewell line (max 18 words) for a "
                "coding-agent CLI session that just ended cleanly."
                + (f" Context: {ctx}." if ctx else "")
                + " You may use one paw emoji. No quotes, no preamble.")
            raw = aicore.query_ai(
                prompt,
                system_prompt="You write tiny, polished CLI farewells. "
                              "Output only the line itself.",
                size_class="simple")
            raw = (raw or "").strip().strip('"').strip()
            if raw and len(raw) <= 200 and "\n\n" not in raw \
                    and not aicore.is_error_response(raw):
                result["text"] = raw.splitlines()[0].strip()
        except Exception:
            pass

    th = threading.Thread(target=_worker, daemon=True,
                          name="cat-goodbye-farewell")
    th.start()
    th.join(max(0.0, timeout))

    text = result["text"]
    if text:
        return text
    idx = random.Random(os.getpid()).randrange(len(_FALLBACK_LINES))
    return _FALLBACK_LINES[idx]


# --------------------------------------------------------------- render --

def _gradient_frame(lines, colors, phase, bold=True):
    from . import theme
    shifted = list(colors[phase % len(colors):]) + \
        list(colors[:phase % len(colors)])
    return [theme.gradient(line, *shifted, bold=bold) for line in lines]


def _emit(lines):
    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.flush()


def _rewind(n_rows):
    """Replace the previous frame EXACTLY: cursor up n rows, erase down.
    Safe because the renderer guarantees no line ever wraps."""
    sys.stdout.write(f"\x1b[{n_rows}A\x1b[J")
    sys.stdout.flush()


def _pick_logo(width):
    try:
        from .app import LOGO as CAT_LOGO
    except Exception:
        CAT_LOGO = None
    if width >= 30:
        lines = [l.rstrip() for l in (CAT_LOGO or [])] or ["CAT"]
        h = max(1, len(lines))
    elif width >= 20:
        lines, h = list(_COMPACT_LOGO), len(_COMPACT_LOGO)
    else:
        lines, h = ["C A T"], 1
    return [("  " + l) for l in lines], h   # fixed 2-col indent


def _pick_goodbyes(width):
    if width >= _GOODBYE_BLOCK_W + 4:
        return [("  " + l) for l in _GOODBYE_BLOCK]
    return None   # narrow terminal: caption-only


def render_goodbye(farewell=None, note_lines=None, task_complete=False,
                   animate=None, stream=None):
    """Draw the complete goodbye composition ONCE through this single
    pipeline. `farewell` should come from the caller's cached
    generate_session_message() result so the AI is asked at most one
    time per shutdown."""
    from . import theme

    stream = stream or sys.stdout
    if animate is None:
        animate = _color_ok(stream)
    width = max(20, min(_term_width(stream), 120))

    if farewell is None:
        farewell = generate_session_message(stream=stream)

    colors = (theme.CYAN, theme.PURPLE, theme.CYAN)
    if theme.is_light():
        colors = (theme.ACCENT_BLUE, theme.PURPLE, theme.ACCENT_BLUE)

    print()
    print(theme.dim("─" * min(width - 1, 60)))

    if task_complete:
        print(theme.green("\u2713 Task completed"))

    # ---- 1. small CAT face --------------------------------------------
    face = [("  " + l) for l in _CAT_FACE]
    if animate:
        _emit([theme.gradient(l, *colors) for l in face])
        time.sleep(_FACE_HOLD_S)
        _rewind(len(face))
    else:
        _emit([theme.dim(l) for l in face])

    # ---- 2. CAT logo — gradient sweep (wrap-proof) ---------------------
    logo_lines, logo_h = _pick_logo(width)
    if animate:
        for frame in range(_ANIM_FRAMES):
            _emit(_gradient_frame(logo_lines, colors, frame))
            time.sleep(_ANIM_FRAME_S)
            if frame < _ANIM_FRAMES - 1:
                _rewind(logo_h)
        _emit([theme.gradient(l, colors[0], colors[1], bold=True)
               for l in logo_lines])
    else:
        _emit([theme.text(l) for l in logo_lines])

    # ---- 3. GOOD BYE — reverse-direction gradient ----------------------
    goodbyes = _pick_goodbyes(width)
    caption = "G O O D   B Y E"
    pad = max(0, min(9, (width - len(caption)) // 2 - 2))
    cap_line = " " * (2 + pad) + caption

    if goodbyes:
        if animate:
            for frame in range(4):
                _emit(_gradient_frame(goodbyes, colors, -frame))
                time.sleep(_ANIM_FRAME_S)
                if frame < 3:
                    _rewind(len(goodbyes))
            _emit([theme.gradient(l, colors[1], colors[0], bold=True)
                   for l in goodbyes])
        else:
            _emit([theme.dim(l) for l in goodbyes])
    print()
    print(theme.gradient(cap_line, colors[1], colors[0], bold=True)
          if animate or True else cap_line)
    print()

    # ---- 4. farewell ----------------------------------------------------
    bar = "─" * min(width - 1, 46)
    print(theme.gradient(bar, colors[0], colors[1])
          if (_color_ok(stream)) else theme.dim(bar))
    print(f"{theme.purple('CAT AI')}  \"{farewell}\"")
    print(theme.gradient(bar, colors[1], colors[0])
          if (_color_ok(stream)) else theme.dim(bar))

    # ---- 5. session notes ------------------------------------------------
    for line in (note_lines or []):
        print(theme.dim(line))

    if _color_ok(stream):
        sys.stdout.write("\x1b[0m\x1b[?25h")
    sys.stdout.flush()


# ---------------------------------------------------- centralized exit --
def shutdown_session(repl=None, reason="exit", note_lines=None,
                     animate=None):
    """THE one shutdown entry point every normal exit path routes
    through. Idempotent: a second call renders nothing.

    Order guaranteed:
        stop flags → title 'Exiting' → farewell (ONE bounded AI attempt,
        cached) → clear screen → animated goodbye (single owner) →
        restore shell title → terminal cleanup/flush.
    """
    with _shutdown_lock:
        if _shutdown_state["done"]:
            return False
        _shutdown_state["done"] = True

    try:
        if repl is not None:
            repl.running = False
    except Exception:
        pass

    try:
        from . import theme
        theme.set_terminal_title_state("exiting")
    except Exception:
        pass

    try:
        history_count = len(getattr(repl, "history", []) or [])
    except Exception:
        history_count = 0
    notes = list(note_lines or [])
    notes.append(f"Session saved. {history_count} notebook(s) solved this session.")

    farewell = generate_session_message(
        context={"summary": f"{history_count} notebooks solved"}
        if history_count else None)

    if _color_ok():
        # Requirement #7: wipe stale UI remnants so exactly one goodbye
        # composition exists on screen.
        sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.flush()

    render_goodbye(farewell=farewell, note_lines=notes,
                   task_complete=(reason == "task"), animate=animate)

    try:
        from . import theme
        theme.restore_terminal_title()
    except Exception:
        pass
    return True