"""
Cross-platform single-keypress reader, used to drive shortcut keys
inside the live simulations (atom viewer, orbital viewer, graphs)
without needing to press Enter.

Falls back gracefully to blocking input() on platforms/terminals where
raw mode isn't available (e.g. some CI pipes) so the app never crashes.
"""

import sys
import select


def stdin_is_interactive():
    """True if stdin is a real attached terminal that can deliver raw
    keypresses. False for pipes, redirected files, and other
    non-interactive contexts (CI runners, containers without -it,
    scripted input, etc).

    This matters because select.select() reports a pipe at EOF as
    'readable' forever, and termios/msvcrt both fail silently on a
    non-tty fd. Without this check, a live view driven by
    key_available()/read_key() spins in a tight busy loop forever,
    burning CPU and never exiting, since it can never actually detect a
    'q' keypress that will never arrive."""
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def key_available():
    """Non-blocking check: is a key waiting in stdin? Unix only; on
    platforms without select-on-stdin support this always returns False
    (the caller should just keep animating on a timer). Always False
    when stdin isn't a real interactive terminal — see
    stdin_is_interactive() for why."""
    if not stdin_is_interactive():
        return False
    try:
        r, _, _ = select.select([sys.stdin], [], [], 0)
        return bool(r)
    except Exception:
        return False


def read_key():
    """Read exactly one keypress, no Enter required. Returns '' if no
    raw-mode backend is available."""
    try:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':  # potential escape sequence
                # peek if more chars are coming (non-blocking)
                r, _, _ = select.select([sys.stdin], [], [], 0.01)
                if r:
                    ch += sys.stdin.read(2)  # read [A, [B, etc.
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return ch
    except Exception:
        pass
    try:
        import msvcrt
        if msvcrt.kbhit():
            return msvcrt.getch().decode(errors="ignore")
        return ""
    except Exception:
        return ""


SHORTCUTS_HELP = [
    ("q", "quit the live view / return to menu"),
    ("space", "pause / resume animation"),
    ("+ / -", "speed up / slow down"),
    ("n / p", "next / previous element or state"),
    ("r", "reset / randomize"),
    ("s", "save a snapshot (2D/3D image export)"),
]
