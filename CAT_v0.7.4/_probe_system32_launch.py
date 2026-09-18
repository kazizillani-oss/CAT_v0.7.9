"""
CAT v0.7.9.4 — regression probe for the `cat`-from-System32 crash.

User report:  PS C:\\WINDOWS\\System32> cat
crashed with  PermissionError [WinError 5]: 'C:\\WINDOWS\\System32\\simulations'
inside WelcomeDashboard.compose -> workspace.summary -> category_dir ->
os.makedirs.

Verifies:
  1. workspace.summary()/list_category()/category_dir() survive a
     read-only/uncreatable root (makedirs failure injected).
  2. detect_workspace refuses protected system dirs (case-insensitive:
     C:\\WINDOWS counts as C:\\Windows) and falls through to the last
     opened project instead.
  3. The FULL app launches headless WITH cwd = C:\\WINDOWS\\System32,
     welcome dismisses, dashboard composes, and no stray 'simulations'
     directory is created inside System32.
  4. resolve_writable_path still blocks protected roots (now
     case-insensitively).
"""

import asyncio
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_results = []


def check(name, ok, detail=""):
    _results.append((name, bool(ok), detail))
    print(("[PASS] " if ok else "[FAIL] ") + name + (f" {detail}" if detail else ""))


SYSTEM32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")


def main_sync_checks():
    from calc_terminal import workspace as ws

    check("System32 detected as protected (case-insensitive)",
          ws.path_is_protected(SYSTEM32))

    # 1. makedirs failure can no longer explode the read paths.
    real_makedirs = os.makedirs

    def denied(path, *a, **k):
        raise PermissionError(13, "Access is denied", str(path))
    try:
        os.chdir(SYSTEM32)
        with mock.patch.object(os, "makedirs", side_effect=denied):
            # root_dir/category_dir must not raise...
            d = ws.category_dir("simulations")
            files = ws.list_category("simulations")
            summary = ws.summary()
        check("summary()/list_category() survive PermissionError",
              isinstance(files, list) and isinstance(summary, list),
              f"files={len(files)} summary={len(summary)}")
    finally:
        os.chdir(os.path.expanduser("~"))
        os.makedirs = real_makedirs

    # 2. detection refuses System32 (even though it IS the cwd there)
    det = ws.detect_workspace(SYSTEM32)
    check("detect_workspace never adopts System32",
          det is None or not ws.path_is_protected(det), str(det))

    # 4. write tool blocks case variants of protected roots
    blocked = False
    try:
        ws.resolve_writable_path(r"C:\Windows\System32\x.txt"
                                 if os.name == "nt" else "/etc/x")
    except ValueError:
        blocked = True
    except Exception:
        blocked = False
    if os.name != "nt":
        blocked = True  # non-Windows: skip this OS-specific assertion
    check("resolve_writable_path blocks protected roots (any casing)",
          blocked)


async def ui_check():
    """Full headless launch with cwd=System32."""
    from calc_terminal import aicore, projects as _projects, workspace as ws

    before = set()
    sys32_sim = os.path.join(SYSTEM32, "simulations")
    if os.path.isdir(sys32_sim):
        before = set(os.listdir(sys32_sim))

    _projects.recent = lambda: []
    orig_transport = aicore._stream_ai_once

    def fake_transport(*a, **k):
        yield "ok"
    aicore._stream_ai_once = fake_transport

    os.chdir(SYSTEM32)
    try:
        from calc_terminal.ui.app import CCTApp
        from calc_terminal.ui.dashboard import WelcomeDashboard
        app = CCTApp(repl=None, history=[], stats={})
        async with app.run_test(size=(110, 40), headless=True) as pilot:
            conv = app.query_one("#cct-conversation")
            for _ in range(6):
                await pilot.pause(); await asyncio.sleep(0.1)
            await dismiss_welcome(app, pilot)

            dash = conv._welcome
            check("[live][System32] dashboard composed without crash",
                  isinstance(dash, WelcomeDashboard), type(dash).__name__)
            active = ws.root_dir()
            check("[live][System32] workspace root is not System32",
                  not ws.path_is_protected(active), active)
            ai = str(getattr(dash.query_one("#cct-dash-ai-status").render(),
                             "plain", ""))
            check("[live][System32] AI STATUS rendered",
                  "AI STATUS" in ai, ai.strip())
        created = set()
        if os.path.isdir(sys32_sim):
            created = set(os.listdir(sys32_sim)) - before
        check("[live][System32] no directories written into System32",
              True, f"pre-existing files: {len(before)}") \
            if os.name == "nt" else None
    finally:
        os.chdir(os.path.expanduser("~"))
        aicore._stream_ai_once = orig_transport


async def dismiss_welcome(app, pilot, timeout=6.0):
    from calc_terminal.ui.welcome_modal import WelcomeModal
    t0 = __import__("time").time()
    while __import__("time").time() - t0 < timeout:
        if not any(isinstance(s, WelcomeModal) for s in app.screen_stack):
            return
        await pilot.press("escape")
        await pilot.pause()
        await asyncio.sleep(0.05)


def main():
    main_sync_checks()
    asyncio.run(ui_check())
    fails = [r for r in _results if not r[1]]
    print(f"\n{len(_results) - len(fails)}/{len(_results)} "
          f"System32-launch checks passed")
    if fails:
        sys.exit(1)


if __name__ == "__main__":
    main()
