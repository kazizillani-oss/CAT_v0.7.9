"""
CAT v0.7.9.0 — cat_agent.py: the animated CAT Agent activity indicator.

A small ASCII bot that lives in the chat area while the agent is
actually working. The BODY IS IMMUTABLE; only the two eye characters
inside the parentheses and the status caption ever change:

    CAT Notebook            <- mode-specific label (real mode state)
       (o.o)                <- only "(eyes)" animates
       /[_]\\
        ] [
    Thinking....            <- caption animates smoothly 1..4 dots

ROOT CAUSE of the glitched body this module replaces: earlier builds
embedded Rich-markup escape sequences ("[[") inside the animated art
STRING itself, so the bot's shape depended on markup-parsing behavior
and could surface mutated bodies like "/[[]_][/]" or "][[]". This
module owns fixed plain-text TEMPLATES, substitutes ONLY the eye slot
with validated 3-character frames, and renders through rich.text.Text
spans (no markup parser anywhere near the body). Every frame is
generated independently from the same immutable template — nothing is
ever appended to or mutated from the previous frame.

v0.7.9.0 additions:

* MODE-SPECIFIC IDENTITY — the label always reflects the ACTUAL active
  mode (ai_modes.current_mode()): CAT Notebook / CAT Research / CAT
  Planner / CAT Build / CAT Debug / CAT Agent (+ overrides for Multi-AI
  and Vision turns). Never a hard-coded global label.
* SMOOTH THINKING ANIMATION — the caption loops Thinking. .. Thinking....
  inside ONE live component (never separate chat messages).
* STATE-SPECIFIC EYES — thinking blinks gently; tool execution goes
  wide-eyed; waiting holds still (no fake activity).

Hard rules:

* Body layout is a frozen constant per frame; never modified between frames.
* Eyes come ONLY from VALID_EYES (exactly three characters each), so
  the rendered width is constant and malformed frames are impossible.
* Pure UI state: no model tokens, no request payload changes, no fake
  assistant messages, nothing added to chat history.
* Lifecycle driven by real backend state (MessageStarted /
  AgentActivity / MessageFinished); the timer is stopped and the
  component removed the moment work ends (finish/fail/cancel).
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os

TEXTUAL_AVAILABLE = True
try:
    from textual.widgets import Static
    from rich.text import Text
except Exception:
    TEXTUAL_AVAILABLE = False

# ------------------------------------------------- immutable templates --
# "{eyes}" is the ONLY body slot any frame may substitute. These lines
# must render byte-for-byte identically on every single frame.
_BODY_TEMPLATE = [
    "{label}",
    "   ({eyes})",
    "   /[_]\\",
    "    ] [",
]

# ---------------------------------------------------- valid eye frames --
# Controlled vocabulary: every frame is exactly three characters ->
# left_eye, center, right_eye. Nothing outside this set can ever render.
VALID_EYES = frozenset({
    "o.o",
    "0.0",
    "O.O",
    "-.-",
    "o~o",
    "0~0",
    "o-o",
    "O-o",
})

# Per-state eye cycles: thinking blinks gently, execution stares wide,
# multi-AI keeps maximum alert. Waiting/terminal states HOLD a frame.
STATE_EYE_FRAMES = {
    "thinking":           ("o.o", "O.O", "0.0", "o~o"),
    "tool_execution":     ("0.0", "O.O"),
    "tool_running":       ("0.0", "O.O"),
    "routing":            ("o.o", "o~o"),
    "vision":             ("O.O", "0.0", "O.O", "o.o"),
    "multi_agent":        ("O.O", "0.0", "O.O"),
    "waiting_permission": ("o.o",),
    "success":            ("o.o",),
    "error":              ("-.-",),
    "cancelled":          ("-.-",),
}
EYE_FRAMES = STATE_EYE_FRAMES["thinking"]      # backward-compatible default

DEFAULT_EYES = "o.o"

FRAME_INTERVAL = 0.2  # seconds per frame (smooth band: 150-300 ms)

ANIMATION_ENABLED = os.environ.get("CAT_AGENT_ANIMATION", "1") not in ("0", "false", "no")

# ------------------------------------------------------------- labels --
def mode_label_for(mode_key):
    """The REAL mode name -> the CAT identity label shown above the bot.
    Driven by actual mode state (ai_modes.MODE_META keys); unknown keys
    fall back to plain 'CAT Agent'."""
    return {
        "notebook": "CAT Notebook",
        "research": "CAT Research",
        "plan":     "CAT Planner",
        "build":    "CAT Build",
        "debugger": "CAT Debug",
        "agent":    "CAT Agent",
        "multi_ai": "CAT Multi-AI",
        "vision":   "CAT Vision",
    }.get(mode_key, "CAT Agent")


# ------------------------------------------------------- state labels --
# "Thinking..." now ANIMATES through dot counts (THINKING_DOTS below);
# other states are static captions because they describe instantaneous
# real facts rather than ongoing work.
THINKING_DOTS = ("Thinking.", "Thinking..", "Thinking...", "Thinking....")

STATE_LABELS = {
    "thinking":           THINKING_DOTS[0],
    "tool_execution":     "Working...",
    "tool_running":       "Working...",
    "routing":            "Routing...",
    "vision":             "Analyzing image...",
    "multi_agent":        "Coordinating agents...",
    "waiting_permission": "Waiting for permission...",
    "success":            "Done.",
    "error":              "Failed.",
    "cancelled":          "Cancelled.",
    "idle":               "",
}

STATE_COLORS = {  # role key resolved against theme variables
    "thinking":           "accent",
    "tool_execution":     "warning",
    "tool_running":       "warning",
    "routing":            "accent",
    "vision":             "accent",
    "multi_agent":        "accent",
    "waiting_permission": "warning",
    "success":            "success",
    "error":              "error",
    "cancelled":          "text-faint",
    "idle":               "text-faint",
}

DEFAULT_STATE = "thinking"

# States in which the bot holds a STABLE frame instead of blinking:
# waiting must not pretend to think; terminal states are static by definition.
HOLD_STATES = frozenset({
    "waiting_permission",
    "success",
    "error",
    "cancelled",
})


def validate_frame(eyes):
    """Never render a malformed eye string."""
    return eyes if eyes in VALID_EYES else DEFAULT_EYES


def render_cat_agent(eyes, label="CAT Agent"):
    """Generates one complete frame INDEPENDENTLY from the immutable
    template. Plain text only — no markup, no ANSI, nothing concatenated
    from previous frames."""
    safe = validate_frame(eyes)
    safe_label = str(label).replace("\n", " ")[:40] or "CAT Agent"
    lines = [line.replace("{eyes}", safe).replace("{label}", safe_label)
             for line in _BODY_TEMPLATE]
    return "\n".join(lines)


if TEXTUAL_AVAILABLE:

    class CATAgentIndicator(Static):
        """Dedicated UI component for the animation. Mounted ONCE by
        ConversationView while a turn is genuinely in flight; removed by
        finish/fail/cancel. Chat history never contains animation frames."""

        DEFAULT_CSS = """
        CATAgentIndicator {
            width: auto;
            min-width: 20;
            max-width: 100%;
            height: auto;
            padding: 0 1;
            color: $text-muted;
        }
        """

        def __init__(self, state=DEFAULT_STATE, mode_key=None, **kwargs):
            super().__init__(None, **kwargs)
            self._state = state
            self._mode_key = mode_key
            self._tick = 0
            self._timer = None

        # ------------------------------------------------------ lifecycle --
        def on_mount(self):
            self._render_frame()
            self._start_timer()

        def on_unmount(self):
            self.stop()

        def stop(self):
            """Halt the timer and release it. Called by ConversationView
            hide_agent_activity() on finish/fail/cancel, and defensively
            on unmount — the timer must never outlive the component."""
            if self._timer is not None:
                try:
                    self._timer.stop()
                except Exception:
                    pass
                self._timer = None

        def reset(self):
            """Clears animation state: stops ticking, resets counters,
            blanks the display."""
            self.stop()
            self._tick = 0
            self._state = DEFAULT_STATE
            try:
                self.update(None)
            except Exception:
                pass

        def _start_timer(self):
            if self._timer is not None or not ANIMATION_ENABLED:
                return
            interval = FRAME_INTERVAL
            try:
                # Respect the existing global animation-speed setting
                # (config.CCTConfig.animation_speed), clamped into the
                # 150-300 ms band's neighbourhood.
                from .. import config as cct_config
                speed = float(getattr(cct_config.load_config(),
                                      "animation_speed", 1.0) or 1.0)
                if speed > 0:
                    interval = max(0.15, min(0.30, FRAME_INTERVAL / speed))
            except Exception:
                pass
            self._timer = self.set_interval(interval, self._next_frame)

        def _next_frame(self):
            """One tick = ONE fresh frame from the template. Never
            appends to or mutates the previous frame — update() replaces
            the whole content each time."""
            self._tick += 1
            self._render_frame()

        # --------------------------------------------------------- state --
        @property
        def state(self):
            return self._state

        @property
        def eyes(self):
            frames = STATE_EYE_FRAMES.get(self._state, EYE_FRAMES)
            return frames[self._tick % len(frames)]

        @property
        def label(self):
            """The identity line above the bot — always the ACTUAL active
            mode, never a hard-coded global."""
            if self._mode_key:
                return mode_label_for(self._mode_key)
            try:
                from .. import ai_modes
                return mode_label_for(ai_modes.current_mode())
            except Exception:
                return "CAT Agent"

        def set_mode(self, mode_key):
            """Switch the identity label — called with the ACTUAL current
            mode so the bot always announces the right persona."""
            self._mode_key = mode_key
            self._render_frame()

        def set_state(self, state):
            """Switches the status caption + eye behavior only. The body
            never changes. Holding states pause the eye timer (no fake
            motion); active states resume it."""
            if state not in STATE_LABELS:
                state = DEFAULT_STATE
            if state != self._state:
                self._state = state
                self._tick = 0   # restart eye cycle per state transition
            self._render_frame()
            if state in HOLD_STATES:
                self.stop()          # freeze on the current stable frame
            else:
                self._start_timer()  # resumes ticking (no-op if running)

        def _caption(self):
            """The animated status line under the bot. 'thinking' loops
            Thinking. .. Thinking.... smoothly inside this single live
            component — never as separate chat messages."""
            if self._state == "thinking":
                return THINKING_DOTS[self._tick % len(THINKING_DOTS)]
            return STATE_LABELS.get(self._state, "")

        # ------------------------------------------------------- rendering --
        def _render_frame(self):
            """Builds the frame as rich.text.Text SPANS — the body lines
            are literal characters taken verbatim from the template, so
            no markup/ANSI parser can ever alter them."""
            eyes = validate_frame(self.eyes)
            label = self._caption()
            head_label = self.label
            color_role = STATE_COLORS.get(self._state, "text")
            try:
                hexes = self._theme_hexes()
                body = hexes.get("text", "#cccccc")
                dim = hexes.get("text-faint", "#777777")
                accent = hexes.get(color_role, body)
            except Exception:
                body = dim = accent = "#cccccc"

            frame = render_cat_agent(eyes, head_label)
            text = Text(no_wrap=True, end="")
            first, eye_line, rest = (frame.split("\n", 2) + ["", ""])[:3]
            text.append(first + "\n", style=dim)         # the CAT <Mode> title
            left, mid, right = eye_line[:4], eye_line[4:7], eye_line[7:]
            text.append(left, style=body)
            text.append(mid, style=accent)      # the eyes themselves
            text.append(right + "\n", style=body)
            text.append(rest, style=body)
            if label:
                text.append("\n" + label, style=accent)
            try:
                self.update(text)  # replace-all semantics: no accumulation
            except Exception:
                # Widget mid-teardown — the next tick simply won't paint.
                pass

        @staticmethod
        def _theme_hexes():
            from . import theme_css
            return theme_css.css_variables()

else:

    CATAgentIndicator = None
