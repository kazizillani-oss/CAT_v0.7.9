"""
CCT UI — animations.py (spec v0.7 project structure list).

The v0.7 spec asks for a `ui/animations.py` file with Thinking/
Searching/Responding indicators and live elapsed time. That engine
already existed and already matched the spec exactly — see
thinking.py's docstring ("Advanced AI Response Animation System",
spec item #25) — just under a different filename, wired into
composer.py's live status row and conversation.py's completion
summary.

Per the v0.7 brief ("Do NOT rewrite working modules"), this file does
not reimplement that logic a second time. It re-exports thinking.py's
public surface under the name the new architecture list expects, and
adds one small piece that genuinely didn't exist yet: an `AnimatedTick`
helper Textual widgets can use to self-drive a spinner + elapsed-timer
label without each caller hand-rolling its own `set_interval` bookkeeping.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import time

from .thinking import (  # noqa: F401  (re-exported, not unused)
    DOT_FRAMES, BRAILLE_FRAMES, BLOCK_FRAMES, STYLES,
    STAGES, DEFAULT_STAGE, IDLE_ICONS,
    spinner_frame, detect_stage, stage_info, format_timer,
    idle_icon, commands_used, completion_summary_lines,
)

TEXTUAL_AVAILABLE = True
try:
    from textual.widgets import Static
except Exception:
    TEXTUAL_AVAILABLE = False


if TEXTUAL_AVAILABLE:

    class AnimatedTick(Static):
        """A self-driving `<spinner frame> <Stage Label> <elapsed>s`
        line — Thinking / Searching / Responding, matching the spec's
        three named animation styles via thinking.stage_info()'s style
        field. Callers set the stage with `set_stage(key, prompt=...)`;
        this widget owns its own interval and elapsed-time math so nothing
        else has to poll it.
        """

        def __init__(self, stage=DEFAULT_STAGE, id=None):
            super().__init__("", id=id, classes="cct-animated-tick")
            self._stage = stage
            self._tick = 0
            self._started = time.time()
            self._chunk_count = 0
            self._running = False

        def on_mount(self):
            self._redraw()

        def start(self, stage=None):
            self._started = time.time()
            self._chunk_count = 0
            self._tick = 0
            if stage:
                self._stage = stage
            self._running = True
            self._redraw()
            self._interval = self.set_interval(1 / 8, self._on_tick)

        def stop(self):
            self._running = False
            try:
                self._interval.stop()
            except Exception:
                pass

        def note_chunk(self):
            """Call once per streamed chunk so elapsed-time-based stage
            progression (thinking.detect_stage) can tell 'still waiting
            for the first token' from 'tokens are already arriving'."""
            self._chunk_count += 1

        def set_stage(self, stage_key):
            self._stage = stage_key
            self._redraw()

        def elapsed(self):
            return time.time() - self._started

        def _on_tick(self):
            self._tick += 1
            self._redraw()

        def _redraw(self):
            label, color, style = stage_info(self._stage)
            frame = spinner_frame(style, self._tick)
            elapsed_txt = format_timer(self.elapsed()) if self._running else ""
            text = f"[{color}]{frame} {label}"
            if elapsed_txt:
                text += f"  {elapsed_txt}"
            text += "[/]"
            self.update(text)

else:
    AnimatedTick = None
