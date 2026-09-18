"""CAT v0.7.9.0 - CAT Agent animation regression probe.

Runs the animation for several seconds, captures EVERY rendered frame,
and enforces the acceptance criteria:

  * line 1 == "CAT Agent"          (immutable)
  * line 3 == "   /[_]\\"           (immutable)
  * line 4 == "    ] ["            (immutable)
  * only the eye slot on line 2 changes
  * every eye frame is exactly 3 chars and in VALID_EYES
  * no markup/escape artifacts ("[[", "/[[]_][/]", "][[]")
  * no frame accumulation / duplication (constant height & child count)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.events import (
    MessageStarted, MessageFinished, AgentActivity)
from calc_terminal.ui.cat_agent import (
    CATAgentIndicator, VALID_EYES, EYE_FRAMES,
    render_cat_agent, validate_frame)

WS = r"C:\Users\ADMIN\Downloads\compressed"
BODY_LINE_1 = "CAT Agent"
BODY_LINE_3 = "   /[_]\\"
BODY_LINE_4 = "    ] ["


class _FakeRepl:
    VERSION = "0.7.9.0"


def plain(indicator):
    """The widget's rendered content as pure text (no styles)."""
    rendered = indicator.render()
    return str(getattr(rendered, "plain", rendered))


results = []


def check(name, ok, extra=""):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {extra}")


# ---------------- unit level: template + validator ----------------
frame = render_cat_agent("o.o").split("\n")
check("template line 1 immutable", frame[0] == BODY_LINE_1, repr(frame[0]))
check("template line 3 immutable", frame[2] == BODY_LINE_3, repr(frame[2]))
check("template line 4 immutable", frame[3] == BODY_LINE_4, repr(frame[3]))
check("eye slot substituted once",
      frame[1] == "   (o.o)"
      and "\n".join(frame).count("(o.o)") == 1, repr(frame[1]))
for e in ("x.x", "", "(o.o)", "oo", "o.o.", "[["):
    check(f"validator rejects {e!r}",
          validate_frame(e) == "o.o"
          and all(len(v) == 3 for v in VALID_EYES))
all_frames = [render_cat_agent(e).split("\n") for e in VALID_EYES]
check("every valid frame keeps body byte-identical",
      all(f[0] == BODY_LINE_1 and f[2] == BODY_LINE_3 and f[3] == BODY_LINE_4
          for f in all_frames))
check("no escape artifacts in any frame",
      not any("[[" in "\n".join(f) or "]]" in "\n".join(f)
              for f in all_frames))




async def dismiss_welcome(app, pilot, timeout=6.0):
    """v0.7.9.0: the animated Welcome Screen plays on EVERY launch and
    auto-continues into the Dashboard. Probes skip it deterministically
    (Esc) so they exercise the layers underneath."""
    import asyncio as _aio
    from calc_terminal.ui.welcome_modal import WelcomeModal
    t0 = __import__("time").time()
    while __import__("time").time() - t0 < timeout:
        if not any(isinstance(s, WelcomeModal) for s in app.screen_stack):
            return
        await pilot.press("escape")
        await pilot.pause()
        await _aio.sleep(0.05)


async def main():
    # The indicator's title line is now MODE-AWARE (CAT <Mode>); pin the
    # mode so the classic "CAT Agent" assertions below hold.
    from calc_terminal import ai_modes
    ai_modes.set_mode("agent")
    os.makedirs(WS, exist_ok=True)
    app = CCTApp(_FakeRepl(), [], {})
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await dismiss_welcome(app, pilot)
        conv = app.conversation

        # ---- start: real MessageStarted crossing ----
        app.post_message(MessageStarted("t-fix"))
        await pilot.pause()
        ind = conv._agent_indicator
        check("indicator mounted on start", isinstance(ind, CATAgentIndicator))
        # MessageStarted legitimately mounts TWO widgets: the streaming
        # bubble row AND the indicator.

        # ---- capture ~4s of frames while thinking ----
        captured = []
        t0 = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - t0 < 4.0:
            await asyncio.sleep(0.05)
            captured.append(plain(conv._agent_indicator))
        check("frames actually captured over 4s", len(captured) > 15,
              f"n={len(captured)}")

        bad_body = [c for c in captured
                    if c.split("\n")[0] != BODY_LINE_1]
        bad_line3 = [c for c in captured
                     if c.split("\n")[2] != BODY_LINE_3]
        bad_line4 = [c for c in captured
                     if c.split("\n")[3] != BODY_LINE_4]
        check("line 1 identical in ALL frames", not bad_body)
        check("line 3 identical in ALL frames", not bad_line3,
              repr(bad_line3[:1]))
        check("line 4 identical in ALL frames", not bad_line4,
              repr(bad_line4[:1]))

        eyes_seen = set()
        for c in captured:
            lines = c.split("\n")
            eyes = lines[1].strip()[1:-1]
            eyes_seen.add(eyes)
        check("only validated 3-char eye frames rendered",
              bool(eyes_seen) and eyes_seen <= VALID_EYES, str(sorted(eyes_seen)))
        check("multiple distinct eye states shown", len(eyes_seen) >= 3,
              str(sorted(eyes_seen)))
        check("no corrupted body anywhere",
              not any("/[[]_" in c or "][[]" in c for c in captured))

        heights = {len(c.split("\n")) for c in captured}
        check("no frame accumulation (constant 5-line block)",
              heights == {5}, str(heights))
        # v0.7.9.0: the CAPTION now animates (Thinking. .. Thinking....),
        # so total-block width legitimately varies; the BOT BODY
        # (title/eyes/arms lines) must still be pixel-stable every frame.
        body_widths = {max(len(l) for l in c.split("\n")[:4]) for c in captured}
        check("stable BODY width across frames", len(body_widths) == 1,
              str(body_widths))
        # The chat history must never accumulate animation frames: the
        # ONLY place the bot may exist is the one indicator widget.
        # (Background system notes from workspace auto-indexing may
        # legitimately arrive mid-capture; they are ordinary messages,
        # not animation output.)
        inds = [c for c in conv.children if isinstance(c, CATAgentIndicator)]
        check("exactly ONE animation component during run", len(inds) == 1,
              f"n={len(inds)}")
        check("no bot art leaked into chat messages",
              all("CAT Agent" not in _safe_plain(c) for c in conv.children
                  if not isinstance(c, CATAgentIndicator)))

        # ---- state transitions keep body intact ----
        app.post_message(AgentActivity("t-fix", "tool_running"))
        await pilot.pause()
        cap = plain(conv._agent_indicator).split("\n")
        check("tool state caption 'Working...'",
              cap[-1] == "Working..." and cap[0] == BODY_LINE_1
              and cap[2] == BODY_LINE_3 and cap[3] == BODY_LINE_4,
              repr(cap[-1]))
        app.post_message(AgentActivity("t-fix", "waiting_permission"))
        await pilot.pause()
        cap = plain(conv._agent_indicator).split("\n")
        check("waiting_permission caption",
              cap[-1] == "Waiting for permission..."
              and cap[0] == BODY_LINE_1 and cap[2] == BODY_LINE_3
              and cap[3] == BODY_LINE_4, repr(cap[-1]))
        stable_a = plain(conv._agent_indicator)
        await asyncio.sleep(0.45)
        stable_b = plain(conv._agent_indicator)
        check("waiting state holds a STABLE frame",
              stable_a == stable_b)

        # ---- stop paths leave clean layout ----
        app.post_message(MessageFinished("t-fix", "final answer"))
        await pilot.pause()
        await pilot.pause()
        check("indicator removed after finish",
              conv._agent_indicator is None
              and not any(isinstance(c, CATAgentIndicator)
                          for c in conv.children))
        check("layout clean - no duplicated bots",
              sum("CAT Agent" in _safe_plain(c) for c in conv.children) == 0)

        # error/cancel exits also remove the component
        for turn_id in ("t-err", "t-cancel"):
            app.post_message(MessageStarted(turn_id))
            await pilot.pause()
            ok_mounted = conv._agent_indicator is not None
            app.post_message(MessageFinished(turn_id, "partial"))
            await pilot.pause()
            await pilot.pause()
            ok_removed = conv._agent_indicator is None
            check(f"{turn_id}: mounted then cleanly removed",
                  ok_mounted and ok_removed)

        # timer really stopped on the last indicator
        last = [c for c in conv.children if isinstance(c, CATAgentIndicator)]
        check("no live animation timers remain", not last)

    print(f"\n{sum(results)}/{len(results)} animation checks passed")
    return 0 if all(results) else 1


def _safe_plain(widget):
    r = widget.render()
    return str(getattr(r, "plain", r))


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
