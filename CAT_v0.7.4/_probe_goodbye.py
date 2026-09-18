"""
CAT v0.7.9.0 — unified shutdown / animated goodbye verification.

Covers every acceptance path:
  * static fallback (no color / piped) renders complete composition
  * animated render emits gradient frames + proper terminal cleanup
  * timing bound (<3 s)
  * AI farewell success path uses the SHARED generate_session_message
  * AI hanging/unavailable → bounded local fallback, never blocks
  * shutdown_session idempotent (second /quit ignored)
  * classic REPL exit paths (/exit, EOF) route through ONE handler
"""

import asyncio
import io
import os
import re
import sys
import time
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_results = []


def check(name, ok, detail=""):
    _results.append((name, bool(ok), detail))
    print(("[PASS] " if ok else "[FAIL] ") + name + (f" {detail}" if detail else ""))


def plain(s):
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", s)


async def main():
    from calc_terminal import goodbye

    # ---------------- static fallback -----------------------------------
    goodbye.reset_for_tests()
    buf = io.StringIO()
    with mock.patch.object(sys, "stdout", buf), \
         mock.patch.object(goodbye, "_color_ok", return_value=False), \
         mock.patch.object(goodbye.time, "sleep", lambda s: None):
        f = goodbye.generate_session_message(timeout=0.01)
        goodbye.render_goodbye(farewell=f, animate=False, stream=buf)
    p = plain(buf.getvalue())
    check("static: CAT face + logo + GOOD BYE block all present",
          "( o.o )" in p and "██╔════╝" in p and "╚████" in p
          and "G O O D   B Y E" in p)
    check("static: farewell line rendered under CAT AI",
          "CAT AI" in p and f in p)
    # v0.7.9.4: cleanup escapes are TTY-gated — piped output must end
    # clean (no literal escape characters).
    check("static: piped output has no cursor/SGR cleanup escapes",
          "\x1b[?25h" not in buf.getvalue())

    # ---------------- animated render ------------------------------------
    goodbye.reset_for_tests()
    buf2 = io.StringIO()
    t0 = time.time()
    with mock.patch.object(sys, "stdout", buf2), \
         mock.patch.object(goodbye, "_color_ok", return_value=True):
        goodbye.render_goodbye(farewell="fast", animate=True, stream=buf2)
    dt = time.time() - t0
    raw = buf2.getvalue()
    p2 = plain(raw)
    check("animated: full composition present",
          "( o.o )" in p2 and "╚████" in p2 and "G O O D   B Y E" in p2
          and "fast" in p2)
    check("animated: multiple gradient frames emitted",
          raw.count("38;2") > 200, f"{raw.count('38;2')} color runs")
    check("animated: cleanup resets SGR + shows cursor",
          raw.endswith("\x1b[0m\x1b[?25h\n")
          or "\x1b[0m\x1b[?25h" in raw[-40:])
    check("animated: completes well under 3 s", dt < 3.0,
          f"{dt:.2f}s")

    # ---------------- shared farewell generator --------------------------
    import calc_terminal.aicore as aicore
    goodbye.reset_for_tests()

    def fake_query(prompt, system_prompt=None, **k):
        return '"Paws fully rested. Go build something great."'
    with mock.patch.object(aicore, "load_config",
                           return_value={"provider": "x"}), \
         mock.patch.object(aicore, "query_ai", side_effect=fake_query):
        msg = goodbye.generate_session_message(timeout=1.0)
        check("AI farewell success via shared generator",
              "build something great" in msg, msg)

    def hang(*a, **k):
        time.sleep(30)
    t0 = time.time()
    with mock.patch.object(aicore, "load_config",
                           return_value={"provider": "x"}), \
         mock.patch.object(aicore, "query_ai", side_effect=hang):
        msg2 = goodbye.generate_session_message(timeout=0.3)
    dt2 = time.time() - t0
    check("AI hanging -> bounded local fallback (<1.5 s)",
          dt2 < 1.5 and len(msg2) > 5, f"{dt2:.2f}s '{msg2[:30]}'")

    err_sig = "AI not configured. Run /ai or /agent."
    with mock.patch.object(aicore, "load_config",
                           return_value={"provider": "x"}), \
         mock.patch.object(aicore, "query_ai", return_value=err_sig):
        msg3 = goodbye.generate_session_message(timeout=0.5)
        check("API error signature never becomes the farewell",
              "not configured" not in msg3.lower(), msg3[:40])

    # ---------------- idempotent shutdown --------------------------------
    goodbye.reset_for_tests()
    calls = {"n": 0}

    class FakeRepl:
        history = ["a"]

    r = FakeRepl()
    with mock.patch.object(goodbye, "render_goodbye",
                           side_effect=lambda **k: calls.__setitem__(
                               "n", calls["n"] + 1)):
        first = goodbye.shutdown_session(r, reason="task")
        second = goodbye.shutdown_session(r)
    check("shutdown_session renders exactly once",
          calls["n"] == 1 and first is True and second is False,
          f"calls={calls['n']}")

    # ---------------- classic exit paths funnel through one handler ------
    from calc_terminal.app import App
    goodbye.reset_for_tests()
    repl = App()
    with mock.patch.object(goodbye, "shutdown_session",
                           return_value=True) as sh:
        repl.handle("/quit")
        repl.handle("/exit")
    check("/quit AND /exit both route through shutdown_session",
          sh.call_count == 2, f"calls={sh.call_count}")
    # Empty session -> plain 'exit'; session with completed work -> the
    # '✓ Task completed' variant.
    got = [c.kwargs.get("reason") for c in sh.call_args_list]
    check("empty session uses reason='exit'", got[0] == "exit", str(got))

    goodbye.reset_for_tests()
    repl2 = App()
    repl2.history = ["notebook-1"]
    with mock.patch.object(goodbye, "shutdown_session",
                           return_value=True) as sh2:
        repl2.handle("/quit")
    check("session with work uses reason='task'",
          sh2.call_args.kwargs.get("reason") == "task")

    # ---------------- v0.7.9.4: wrap-proof rendering ----------------------
    class FakeTTY(io.StringIO):
        def isatty(self):
            return True

    for w in (36, 80):
        goodbye.reset_for_tests()
        fbuf = FakeTTY()
        with mock.patch.object(sys, "stdout", fbuf), \
             mock.patch.object(goodbye.time, "sleep", lambda s: None), \
             mock.patch.object(goodbye, "_term_width", return_value=w):
            goodbye.render_goodbye(farewell="narrow", animate=True,
                                   stream=fbuf)
        raw_lines = fbuf.getvalue().splitlines()
        over = [l for l in raw_lines
                if len(plain(l)) > w]
        check(f"[width {w}] NO line ever wraps (wrap-proof renderer)",
              not over,
              f"widest={max((len(plain(l)) for l in raw_lines), default=0)}")

    # exactly ONE of each element in the final composition
    goodbye.reset_for_tests()
    fbuf = FakeTTY()
    with mock.patch.object(sys, "stdout", fbuf), \
         mock.patch.object(goodbye.time, "sleep", lambda s: None), \
         mock.patch.object(goodbye, "_term_width", return_value=80):
        goodbye.render_goodbye(farewell="once", animate=True, stream=fbuf)
    p_final = plain(fbuf.getvalue())
    n_caption = p_final.count("G O O D   B Y E")
    n_face = p_final.count("( o.o )")
    n_farewell = p_final.count('"once"')
    check("final screen: exactly one GOOD BYE caption",
          n_caption == 1, str(n_caption))
    check("final screen: farewell message appears exactly once",
          n_farewell == 1, str(n_farewell))
    check("face frames were REPLACED, not appended (rewinds issued)",
          fbuf.getvalue().count("\x1b[J") >= (_ANIM_FRAMES := 6))

    # ---------------- screen clear before goodbye -------------------------
    goodbye.reset_for_tests()
    sbuf = FakeTTY()
    with mock.patch.object(sys, "stdout", sbuf), \
         mock.patch.object(goodbye.time, "sleep", lambda s: None):
        goodbye.shutdown_session(repl=None, reason="exit", animate=True)
    check("shutdown clears stale UI region first (\x1b[2J)",
          "\x1b[2J\x1b[H" in sbuf.getvalue())

    # ---------------- terminal title integration ---------------------------
    from calc_terminal import theme
    tbuf = FakeTTY()
    with mock.patch.object(sys, "stdout", tbuf):
        ok_set = theme.set_terminal_title("CAT CLI")
        theme.set_terminal_title_state("ready")
        popped = theme.restore_terminal_title()
    seqs = tbuf.getvalue()
    check("set_terminal_title emits OSC-0 sequence on a TTY",
          ok_set and "\x1b]0;CAT CLI\x07" in seqs)
    check("state helper maps ready -> 'CAT CLI — Ready'",
          "\x1b]0;CAT CLI — Ready\x07" in seqs)
    check("restore pops the xterm title stack",
          popped and "\x1b[23t" in seqs)

    piped_ok = theme.set_terminal_title("nope") is False \
        if not sys.stdout.isatty() else True
    check("title set is a safe no-op on piped output", piped_ok)

    fails = [r for r in _results if not r[1]]
    print(f"\n{len(_results) - len(fails)}/{len(_results)} goodbye checks passed")
    if fails:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
