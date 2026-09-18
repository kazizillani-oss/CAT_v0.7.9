"""Headless verification for CAT v0.7.9.0 (layout / live explorer /
agent animation). Run: python _probe_cat_v079.py"""
import asyncio
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.workspace import WorkspaceShell
from calc_terminal.ui.composer import StickyComposer
from calc_terminal.ui.sidebar import Explorer
from calc_terminal.ui.events import (
    MessageStarted, MessageFinished, AgentActivity, WorkspaceFilesChanged)

WS = r"C:\Users\ADMIN\Downloads\compressed"


class _FakeRepl:
    VERSION = "0.7.9.0"


def tree_paths(explorer):
    """Collect loaded paths from the mounted DirectoryTree."""
    from textual.widgets import DirectoryTree
    body = explorer.query_one("#cct-sidebar-body")
    trees = body.query(DirectoryTree)
    if not trees:
        return set()
    tree = trees.first()
    found = set()

    def walk(node):
        data = getattr(node, "data", None)
        if data is not None and getattr(data, "path", None) is not None:
            found.add(str(data.path))
        for c in node.children:
            walk(c)

    try:
        walk(tree.root)
    except Exception:
        pass
    return found




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
    os.makedirs(WS, exist_ok=True)
    results = []

    def check(name, ok, extra=""):
        results.append((name, ok, extra))
        print(f"[{'PASS' if ok else 'FAIL'}] {name} {extra}")

    app = CCTApp(_FakeRepl(), [], {})
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await dismiss_welcome(app, pilot)
        # ---------------- 1. branding ----------------
        check("app title is CAT v0.7.9.0", app.title == "CAT v0.7.9.0",
              repr(app.title))
        from calc_terminal.ui.header import Logo
        logo = app.query_one(Logo)
        # force a render readback via its static content
        logo.redraw()
        await pilot.pause()
        logo_text = str(logo.render())
        check("header wordmark says CAT", "CAT" in logo_text, repr(logo_text))

        # ---------------- 2. layout structure ----------------
        shell = app.query_one(WorkspaceShell)
        composer = app.query_one(StickyComposer)
        main_col = shell.query_one("#cct-workspace-main")
        # v0.7.10: the composer lives in the CHAT COLUMN (#cct-chat-col),
        # itself a flow child of the main column — still never
        # screen-docked, and now geometrically unable to overlap the
        # editor/preview either (spec section 26).
        try:
            chat_col = shell.query_one("#cct-chat-col")
        except Exception:
            chat_col = None
        check("composer lives inside workspace main column",
              composer.parent is main_col or
              (chat_col is not None and composer.parent is chat_col))
        check("composer not screen-docked",
              composer.styles.dock != "bottom", f"dock={composer.styles.dock!r}")
        statusbar = app.query_one("StatusBar")
        check("status bar still screen-docked bottom",
              statusbar.styles.dock == "bottom")

        # open the test workspace
        await app._open_folder(WS)
        await pilot.pause()
        await asyncio.sleep(0.4)
        await pilot.pause()
        explorer = shell.explorer
        check("explorer visible after open_folder", explorer.display)

        # no-overlap invariant across explorer widths + window sizes
        def regions_ok():
            e = explorer.region
            h = shell.query_one("#cct-explorer-resizer").region
            c = composer.region
            m = main_col.region
            return (c.x >= h.x + h.width - 1
                    and h.x >= e.x + e.width - 1
                    and c.x >= m.x - 1
                    and c.width <= m.width + 2), \
                   f"explorer={e} divider={h} main={m} composer={c}"

        for w, size in [(14, (120, 40)), (32, (120, 40)), (60, (120, 40)),
                        (32, (80, 30)), (50, (200, 50))]:
            explorer.set_width(w)
            shell.sync_resizer()
            await pilot.resize_terminal(*size) if hasattr(
                pilot, "resize_terminal") else None
            await pilot.pause()
            await asyncio.sleep(0.05)
            await pilot.pause()
            ok, info = regions_ok()
            check(f"no overlap @ explorer_w={w} window={size}", ok, info)

        # divider visibility follows the explorer
        explorer.set_width(0)
        await pilot.pause()
        res = shell.query_one("#cct-explorer-resizer")
        check("divider hidden when explorer collapsed", not res.display)
        explorer.set_width(32)
        await pilot.pause()
        check("divider visible again", res.display)

        # composer explicit height clamp
        composer.set_explicit_height(500)
        await pilot.pause()
        check("composer height clamped to sane max",
              composer._explicit_height <= int(app.screen.size.height * 0.7),
              f"h={composer._explicit_height}")
        prev_h = composer._explicit_height
        composer.set_explicit_height(3)
        await pilot.pause()
        check("composer min height respected",
              composer._explicit_height >= 6,
              f"h={composer._explicit_height}")
        composer.set_explicit_height(None)
        composer.set_explicit_height(prev_h)
        # explorer width must be unaffected by composer resizing
        check("explorer width unaffected by composer resize",
              explorer.width == 32, f"w={explorer.width}")

        # persistence roundtrip
        from calc_terminal.ui import resizers
        resizers.save_layout(explorer_width=44, composer_height=18)
        got = resizers.load_layout()
        check("layout persistence roundtrip",
              got.get("explorer_width") == 44 and got.get("composer_height") == 18,
              str(got))
        resizers.save_layout(explorer_width=32)
        os.remove(resizers.LAYOUT_PATH) if os.path.exists(
            resizers.LAYOUT_PATH) else None

        # ---------------- 3. live explorer: external changes ----------------
        marker = os.path.join(WS, "realtime_test.txt")
        with open(marker, "w") as f:
            f.write("hello")
        t0 = time.time()
        appeared = False
        while time.time() - t0 < 8:
            await asyncio.sleep(0.25)
            await pilot.pause()
            if any(p.endswith("realtime_test.txt") for p in tree_paths(explorer)):
                appeared = True
                break
        check("external create appears automatically", appeared,
              f"({time.time()-t0:.1f}s)")

        os.remove(marker)
        t0 = time.time()
        gone = False
        while time.time() - t0 < 8:
            await asyncio.sleep(0.25)
            await pilot.pause()
            if not any(p.endswith("realtime_test.txt")
                       for p in tree_paths(explorer)):
                gone = True
                break
        check("external delete disappears automatically", gone,
              f"({time.time()-t0:.1f}s)")

        folder = os.path.join(WS, "test_folder")
        os.makedirs(folder, exist_ok=True)
        t0 = time.time()
        appeared = False
        while time.time() - t0 < 8:
            await asyncio.sleep(0.25)
            await pilot.pause()
            if any(p.endswith("test_folder") for p in tree_paths(explorer)):
                appeared = True
                break
        check("external folder appears automatically", appeared,
              f"({time.time()-t0:.1f}s)")

        shutil.rmtree(folder, ignore_errors=True)
        t0 = time.time()
        gone = False
        while time.time() - t0 < 8:
            await asyncio.sleep(0.25)
            await pilot.pause()
            if not any(p.endswith("test_folder") for p in tree_paths(explorer)):
                gone = True
                break
        check("external folder disappears automatically", gone,
              f"({time.time()-t0:.1f}s)")

        # ---------------- 4. agent-tool-driven update ----------------
        # (agent.py's write_file tool writes the REAL file first, then
        # the UI announces the change — mirror that order here.)
        agent_file = os.path.join(WS, "realtime_agent_test.txt")
        with open(agent_file, "w") as f:
            f.write("agent")
        app._notify_tool_fs_change("write_file", {"path": agent_file})
        t0 = time.time()
        appeared = False
        while time.time() - t0 < 5:
            await asyncio.sleep(0.15)
            await pilot.pause()
            if any(p.endswith("realtime_agent_test.txt")
                   for p in tree_paths(explorer)):
                appeared = True
                break
        check("CAT tool create appears immediately", appeared,
              f"({time.time()-t0:.1f}s)")

        app._notify_tool_fs_change("delete_file", {"path": agent_file})
        os.remove(agent_file)
        t0 = time.time()
        gone = False
        while time.time() - t0 < 5:
            await asyncio.sleep(0.15)
            await pilot.pause()
            if not any(p.endswith("realtime_agent_test.txt")
                       for p in tree_paths(explorer)):
                gone = True
                break
        check("CAT tool delete disappears immediately", gone,
              f"({time.time()-t0:.1f}s)")

        # ---------------- 5. CAT Agent animation lifecycle ----------------
        conv = app.conversation
        check("no indicator while idle", conv._agent_indicator is None)

        app.post_message(MessageStarted("t1"))
        await pilot.pause()
        ind = conv._agent_indicator
        check("indicator appears on MessageStarted", ind is not None)
        from calc_terminal.ui.cat_agent import CATAgentIndicator

        def _plain(w):
            r = w.render()
            return str(getattr(r, "plain", r))

        frame1 = _plain(ind) if ind else ""
        # v0.7.9.0: sample across several timer periods — both the eye
        # cycle AND the new Thinking.<dots> caption animate per tick.
        seen_frames = {frame1}
        for _ in range(10):
            await asyncio.sleep(0.12)
            await pilot.pause()
            if ind:
                seen_frames.add(_plain(ind))
        check("eyes/caption animate between frames", len(seen_frames) >= 3,
              f"{len(seen_frames)} distinct frame(s)")
        body_ok = all(
            f.split("\n")[0] == "CAT Agent"
            and f.split("\n")[2] == "   /[_]\\"
            and f.split("\n")[3] == "    ] ["
            for f in seen_frames if f)
        check("bot body byte-identical in every frame", body_ok)

        app.post_message(AgentActivity("t1", "tool_execution"))
        await pilot.pause()
        label = _plain(conv._agent_indicator).split("\n")[-1]
        check("state -> Working...", label == "Working...", label[-40:])
        app.post_message(AgentActivity("t1", "waiting_permission"))
        await pilot.pause()
        label = _plain(conv._agent_indicator).split("\n")[-1]
        check("state -> Waiting for permission...",
              label == "Waiting for permission...", label[-60:])
        app.post_message(AgentActivity("t1", "thinking"))
        await pilot.pause()
        label = _plain(conv._agent_indicator).split("\n")[-1]
        # v0.7.9.0: thinking caption animates through dot counts
        # ("Thinking." .. "Thinking....") inside this single component.
        from calc_terminal.ui.cat_agent import THINKING_DOTS
        check("state -> Thinking<dots> animation frame",
              label in THINKING_DOTS, label[-40:])

        app.post_message(MessageFinished("t1", "done text"))
        await pilot.pause()
        await pilot.pause()
        check("indicator removed on finish",
              conv._agent_indicator is None
              and not any(isinstance(c, CATAgentIndicator)
                          for c in conv.children))
        check("no fake assistant content from animation",
              all("o.o" not in str(c.render()) or "CAT Agent"
                  not in str(c.render()) for c in conv.children))

    fails = [r for r in results if not r[1]]
    print(f"\n{len(results)-len(fails)}/{len(results)} checks passed")
    return 1 if fails else 0


if __name__ == "__main__":
    import time
    sys.exit(asyncio.run(main()))
