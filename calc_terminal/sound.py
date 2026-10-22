"""
Terminal sound effects for CCT — dependency-free, cross-platform.

No audio libraries are required. On Windows, the built-in `winsound`
module plays real short tones. Everywhere else (macOS/Linux terminals,
and Windows too if winsound is unavailable for some reason) it falls
back to the ASCII BEL character (`\\a`), which every terminal emulator
interprets as "ring the system bell" — the same mechanism your shell
uses for tab-complete errors. Some terminals mute this by default; if
nothing is audible, check your terminal's preferences for "audible
bell" / "terminal bell" and make sure it's turned on.

This module never raises and never blocks noticeably — a sound cue is
a nice-to-have, not something that should ever break the app or stall
an animation.
"""

import sys
import threading
import time

try:
    import winsound
    _HAS_WINSOUND = True
except ImportError:
    winsound = None
    _HAS_WINSOUND = False

_ENABLED = True


def set_enabled(value):
    global _ENABLED
    _ENABLED = bool(value)


def is_enabled():
    return _ENABLED


def _bell(times=1, gap=0.08):
    for i in range(times):
        sys.stdout.write("\a")
        sys.stdout.flush()
        if i < times - 1:
            time.sleep(gap)


def _tone(freq, duration_ms):
    """Try a real tone via winsound. Returns True if it actually played
    a tone (so callers know NOT to also fall back to a bell)."""
    if not _HAS_WINSOUND:
        return False
    try:
        winsound.Beep(int(freq), int(duration_ms))
        return True
    except Exception:
        return False


def play_async(event="notify"):
    """v0.7.9.0 (requirement #1/#31 — SPEED): `winsound.Beep` BLOCKS its
    calling thread for the full tone duration (~45-160 ms per tone, and
    'success' plays TWO). Inside the agent loop that meant every single
    tool call paid 100-220 ms of pure sound latency — measured, not
    guessed (see scripts/benchmark_cat.py: tool 'calculate' took ~219 ms,
    all of it winsound.Beep). Sounds are now fired on a throwaway daemon
    thread so the request path never waits on audio."""
    if not _ENABLED:
        return
    threading.Thread(target=play, args=(event,), daemon=True).start()


# ---------------------------------------------------------------- events --
# Each named event below is used consistently across the app: booting up,
# a notebook/solve/plot finishing successfully, an error, a live
# simulation starting, and a quiet tick for each agent tool call so an
# agent run happening on-screen is also audible turn-by-turn.
def _play_blocking(event="notify"):
    """The actual tone/bell sequence. Runs on a worker thread via play()
    so no request/tool path ever waits on audio hardware."""
    try:
        if event == "startup":
            if not _tone(660, 90):
                _bell(1)
            else:
                _tone(880, 110)
        elif event == "success":
            if not _tone(880, 90):
                _bell(1)
            else:
                _tone(1175, 120)
        elif event == "error":
            if not _tone(220, 160):
                _bell(2, gap=0.12)
        elif event == "sim_start":
            if not _tone(600, 60):
                _bell(1)
        elif event == "tool":
            # Deliberately quiet: a short tick per agent tool call, and
            # NO bell fallback (repeated bells during a multi-step agent
            # run would get annoying fast on terminals without winsound).
            _tone(520, 45)
        else:
            _bell(1)
    except Exception:
        pass


def play(event="notify"):
    """v0.7.9.0 SPEED FIX (measured, see scripts/benchmark_cat.py):
    winsound.Beep BLOCKS its thread for the whole tone — 'success' costs
    ~220 ms, every agent 'tool' tick ~45 ms. Playing inline meant every
    single tool execution in a run paid that latency in wall-clock time.
    Tones now run on a short-lived daemon thread; the ASCII-bell fallback
    stays inline because writing '\\a' is instantaneous."""
    if not _ENABLED:
        return
    if _HAS_WINSOUND:
        threading.Thread(target=_play_blocking, args=(event,),
                         daemon=True).start()
    else:
        _play_blocking(event)


# Back-compat explicit-async alias (same behavior as play() now).
play_async = play
