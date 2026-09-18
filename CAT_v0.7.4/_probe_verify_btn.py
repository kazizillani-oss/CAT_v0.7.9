"""Verify dialogs after the fit_dialog fix:
- every displayed Button fully inside its dialog box
- box fully inside the screen
- across terminal sizes (small/medium/large) and after a mid-open resize
Also re-exports SVGs for visual inspection.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import calc_terminal.mcp as mcp
mcp.load_servers = lambda: [
    {"id": "srv1", "name": "Math Tools", "kind": "remote",
     "url": "http://localhost:3000/mcp", "status": "connected",
     "version": "2024-11-05", "latency_ms": 42, "tools": ["add", "mul"],
     "last_connected": 1755300000},
    {"id": "srv2", "name": "Git Helper", "kind": "local",
     "command": "npx git-mcp", "status": "disconnected",
     "version": "", "latency_ms": None, "tools": []},
]
from calc_terminal.providers import provider_manager as pm
pm.load_backup_providers = lambda: [
    {"provider": "openai", "model": "gpt-4o-mini", "api_key": "k",
     "status": "connected", "latency_ms": 120, "enabled": True,
     "last_used": 1755300000, "base_url": "", "api_style": "openai"},
    {"provider": "anthropic", "model": "claude-3-5-haiku", "api_key": "k",
     "status": "disconnected", "latency_ms": None, "enabled": True,
     "last_used": 0, "base_url": "", "api_style": "anthropic"},
]
import calc_terminal.ai_personalization as pers
pers.load_profiles = lambda: {"profiles": [
    {"name": "Concise Coder", "tone": "concise", "temperature": 0.2,
     "model": "", "style_rules": "short answers", "active": True},
    {"name": "Lab Partner", "tone": "detailed", "temperature": 0.6,
     "model": "", "style_rules": "explain chemistry", "active": False},
]}

OUT = os.path.join(os.environ.get("TEMP", "/tmp"), "cct_btn_probe")
os.makedirs(OUT, exist_ok=True)

PANELS = {
    "mcp": ("calc_terminal.ui.mcp_panel", "McpServersPanel", "mcp-box", "mcp-list"),
    "mcp_add": ("calc_terminal.ui.mcp_panel", "_AddMcpForm", "amf-box", "amf-body"),
    "backup": ("calc_terminal.ui.backup_panel", "BackupProvidersPanel", "bpp-box", "bpp-list"),
    "backup_add": ("calc_terminal.ui.backup_panel", "_AddProviderForm", "apf-box", "apf-body"),
    "welcome": ("calc_terminal.ui.welcome_modal", "WelcomeModal", "wm-box", "wm-body"),
    "personalize": (
        "calc_terminal.ui.personalization_panel", "PersonalizationPanel",
        "pp-box", "pp-main"),
    "attach": ("calc_terminal.ui.attach_panel", "AttachPanel", "ap-box", "ap-browser"),
}

failures = []


def in_scrollable_area(button):
    """True when the button lives inside a scrollable container — its
    region is virtual (may extend past the visible box) and the box
    being capped is exactly why it scrolls. Such buttons are content,
    not the fixed footer controls."""
    w = button.parent
    while w is not None:
        try:
            if getattr(getattr(w, "styles", None), "overflow_y", "") == "auto":
                return True
        except Exception:
            pass
        w = w.parent
    return False


def assert_ok(name, vh, label, box_r, buttons, screen_size):
    problems = []
    for b in buttons:
        vr = b.region
        if vr.width == 0 or vr.height == 0:
            continue  # hidden control, not laid out
        if in_scrollable_area(b):
            continue  # scrollable content, not a footer control
        if not (box_r.intersection(vr) == vr and vr.intersection(box_r) == vr):
            problems.append(f"button #{b.id} {vr} NOT inside box {box_r}")
    if box_r.height < 6:
        problems.append(f"box too short: {box_r}")
    if not (box_r.x >= 0 and box_r.y >= 0
            and box_r.bottom <= screen_size.height and box_r.right <= screen_size.width):
        problems.append(f"box {box_r} outside screen {screen_size}")
    if problems:
        failures.append(f"[{name}@{vh} {label}] " + " | ".join(problems))
        for p in problems:
            print("   FAIL:", p)


async def main():
    from textual.app import App
    from calc_terminal.ui import theme_css

    class ProbeApp(App):
        CSS = theme_css.BASE_CSS

        def get_css_variables(self):
            variables = dict(super().get_css_variables())
            variables.update(theme_css.css_variables())
            return variables

    all_ok = True
    for name, (mod, cls_name, box_id, _scroll_id) in PANELS.items():
        module = __import__(mod, fromlist=[cls_name])
        cls = getattr(module, cls_name)
        for vh in (24, 30, 36, 50):
            app = ProbeApp()
            async with app.run_test(size=(96, vh), headless=True) as pilot:
                screen = cls()
                await app.push_screen(screen)
                for _ in range(15):
                    await pilot.pause()
                    await asyncio.sleep(0.12)

                box = screen.query_one(f"#{box_id}")
                buttons = [w for w in screen.query("Button") if w.display]
                assert_ok(name, vh, "initial", box.region, buttons, app.size)
                if name == "attach":
                    # expand attach panel into the browser view too
                    try:
                        screen._enter_mode("files")
                        for _ in range(12):
                            await pilot.pause()
                            await asyncio.sleep(0.12)
                        box = screen.query_one(f"#{box_id}")
                        buttons = [w for w in screen.query("Button") if w.display]
                        assert_ok(name, vh, "browser", box.region, buttons, app.size)
                    except Exception as e:
                        failures.append(f"[attach@{vh}] browser view error: {e}")
            await asyncio.sleep(0.05)

        # mid-open resize test at 36 -> 24 -> 40
        app = ProbeApp()
        async with app.run_test(size=(96, 36), headless=True) as pilot:
            module = __import__(PANELS[name][0], fromlist=[PANELS[name][1]])
            cls = getattr(module, PANELS[name][1])
            screen = cls()
            await app.push_screen(screen)
            for _ in range(15):
                await pilot.pause()
                await asyncio.sleep(0.12)
            for label, (w, h) in (("resize->24", (80, 24)), ("resize->40", (110, 40))):
                try:
                    app._set_size(w, h)
                except Exception:
                    try:
                        from textual.geometry import Size
                        app.size = Size(w, h)
                    except Exception:
                        pass
                for _ in range(20):
                    await pilot.pause()
                    await asyncio.sleep(0.12)
                box = screen.query_one(f"#{box_id_of(name)}")
                buttons = [b for b in screen.query("Button") if b.display]
                box_r = box.region
                screen_vh = box.screen.size.height
                assert_ok(name, 0, label, box_r, buttons, box.screen.size)
            # screenshot final state
            await pilot.pause()
            try:
                app.save_screenshot(os.path.join(OUT, f"{name}_resize40.svg"))
            except Exception:
                pass
        await asyncio.sleep(0.05)

    # fresh screenshots at 110x36 for visual review
    for name, (mod, cls_name, box_id, _s) in PANELS.items():
        app = ProbeApp()
        async with app.run_test(size=(110, 36), headless=True) as pilot:
            module = __import__(mod, fromlist=[cls_name])
            cls = getattr(module, cls_name)
            screen = cls()
            await app.push_screen(screen)
            for _ in range(15):
                await pilot.pause()
                await asyncio.sleep(0.12)
            if name == "attach":
                screen._enter_mode("files")
                for _ in range(12):
                    await pilot.pause()
                    await asyncio.sleep(0.12)
            try:
                app.save_screenshot(os.path.join(OUT, f"{name}_fixed.svg"))
                print("saved", f"{name}_fixed.svg")
            except Exception as e:
                print("shot fail", name, e)
        await asyncio.sleep(0.05)

    if failures:
        print("\n==== FAILURES ====")
        for f in failures:
            print(f)
        all_ok = False
    print("\nRESULT:", "ALL PASS" if all_ok else "HAS FAILURES")


def box_id_of(name):
    return PANELS[name][2]


asyncio.run(main())