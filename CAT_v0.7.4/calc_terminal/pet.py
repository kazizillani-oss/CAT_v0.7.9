"""
Live mascot pet — Feature request v0.5.6+: "a mascot animated pet
character who can walk, run, and sleep in real time in the terminal."

The app is a blocking-input CLI (it sits on `input()` between turns),
so there's no free-running redraw thread here — but the pet still
*feels* alive: every time the prompt box is about to be drawn, it
looks at how long it's been since the user last did anything and
picks a state accordingly:

  * fired off a question quickly (< RUN_THRESHOLD s)  -> "run"
  * normal pace                                       -> "walk"
  * left the terminal alone for a while (idle)        -> "sleep"

Each redraw also advances an internal tick, so across a few turns the
walk/run cycles actually animate across the screen instead of freezing
on one frame, and /pet plays a short live loop on demand.
"""

import sys
import time

from . import theme

WALK_FRAMES = ["\\o/", " o<", "/o\\", ">o "]
RUN_FRAMES = ["\\o_/", "_o/-", "-\\o_", "/-o\\"]
SLEEP_FRAMES = ["(-.-) zzz", "(-.-)  zz", "(-.-)   z", "(-.-)    "]

RUN_THRESHOLD = 4       # seconds since last activity -> "run"
SLEEP_THRESHOLD = 45    # seconds idle -> "sleep"

_last_activity = time.time()
_tick = 0


def mark_activity():
    """Call this once per submitted command/question — resets the idle
    clock so the *next* time the pet is drawn, it reflects how long the
    user took to respond this round."""
    global _last_activity
    _last_activity = time.time()


def current_state():
    elapsed = time.time() - _last_activity
    if elapsed >= SLEEP_THRESHOLD:
        return "sleep"
    if elapsed <= RUN_THRESHOLD:
        return "run"
    return "walk"


def _frames_for(state):
    return {"walk": WALK_FRAMES, "run": RUN_FRAMES, "sleep": SLEEP_FRAMES}[state]


def _color_for(state):
    return {"walk": theme.CYAN, "run": theme.ORANGE, "sleep": theme.PURPLE}.get(
        state, theme.CYAN)


def frame_line(width=78, state=None):
    """One line showing the pet in its current (or forced) state at its
    current tick position. Calling this repeatedly advances the walk."""
    global _tick
    _tick += 1
    state = state or current_state()
    frames = _frames_for(state)
    frame = frames[_tick % len(frames)]
    color = _color_for(state)

    if state == "sleep":
        pos = 2
    else:
        span = max(4, width - len(frame) - 6)
        step = 2 if state == "run" else 1
        pos = (_tick * step) % span

    return " " * pos + theme.gradient(frame, color, theme.PURPLE, bold=True)


def print_frame(width=78, state=None):
    if not sys.stdout.isatty():
        return
    print(frame_line(width, state=state))


def demo(width=78, seconds_per_state=1.2):
    """A short live loop cycling through all three states in place —
    used by /pet so you can actually watch it walk, run, then fall
    asleep without waiting around for real idle time to pass."""
    if not sys.stdout.isatty():
        print(theme.faint("  (mascot needs a real terminal to animate — "
                           "showing static frames instead)"))
        for state in ("walk", "run", "sleep"):
            print(theme.dim(f"  {state}: ") + frame_line(width, state=state))
        return
    for state, delay in (("walk", 0.05), ("run", 0.03), ("sleep", 0.4)):
        steps = max(6, int(seconds_per_state / delay))
        for _ in range(steps):
            line = frame_line(width, state=state)
            sys.stdout.write("\r" + line + " " * 10)
            sys.stdout.flush()
            time.sleep(delay)
        sys.stdout.write("\r" + " " * (width + 10) + "\r")
    sys.stdout.flush()
