"""
CAT v0.7.9.5 — THEME PICKER interaction probe (headless, real Textual).

Verifies the full requirement chain:

  1. ThemesPanel lists the FULL registry (all 21+ themes), not 2 rows.
  2. Hovering a row live-previews that theme immediately.
  3. Moving away (hover another row / leave) restores the saved theme.
  4. Previewing NEVER persists — saved stores keep the selected theme.
  5. Clicking a row applies + persists it to BOTH stores.
  6. Exactly one row carries the permanent ✓ at all times.
  7. Restart: load_saved_theme() restores the clicked theme.

Run: python _probe_theme_preview.py
"""

import asyncio
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest import mock  # noqa: E402

_results = []


def check(name, ok, detail=""):
    _results.append((name, bool(ok), detail))
    print(("[PASS] " if ok else "[FAIL] ") + name + (f" {detail}" if detail else ""))


async def dismiss_welcome(app, pilot, timeout=6.0):
    from calc_terminal.ui.welcome_modal import WelcomeModal
    t0 = __import__("time").time()
    while __import__("time").time() - t0 < timeout:
        if not any(isinstance(s, WelcomeModal) for s in app.screen_stack):
            return
        await pilot.press("escape")
        await asyncio.sleep(0.05)


async def main():
    from calc_terminal import theme
    from calc_terminal import config as cct_config
    from calc_terminal.app import App
    from calc_terminal.ui.app import CCTApp
    from calc_terminal.ui.nav_screens import ThemesPanel, _ThemeRow

    # Isolated persistence so the user's real theme choice is untouched.
    fd, tmp_theme = tempfile.mkstemp(prefix="cct_tp_", suffix=".json")
    os.close(fd)
    tmp_cfg_fd, tmp_cfg = tempfile.mkstemp(prefix="cct_cfg_", suffix=".json")
    os.close(tmp_cfg_fd)

    orig_theme_file = theme._THEME_FILE
    orig_cfg_cached = cct_config._cached
    theme._THEME_FILE = tmp_theme
    cct_config._cached = None
    cct_config.CONFIG_PATH = tmp_cfg

    try:
        with open(tmp_theme, "w", encoding="utf-8") as f:
            json.dump({"theme": "tokyo-night"}, f)
        theme.load_saved_theme()

        repl = App()
        app = CCTApp(repl, repl.history, {"solved": 0})
        async with app.run_test(size=(110, 38), headless=True) as pilot:
            await dismiss_welcome(app, pilot)
            await asyncio.sleep(0.1)

            panel = ThemesPanel(theme.get_theme())
            await app.push_screen(panel)
            await pilot.pause()
            await asyncio.sleep(0.15)

            rows = list(panel.query(_ThemeRow))
            check("catalog rendered", len(rows) >= len(theme.available_themes()),
                  f"rows={len(rows)}")

            def row_for(name):
                for r in rows:
                    if r.theme_name == name:
                        return r
                return None

            nord = row_for("nord")
            gruv = row_for("gruvbox")
            check("nord + gruvbox rows exist", nord is not None and gruv is not None)
            if not (nord and gruv):
                return

            # ---- hover preview applies live --------------------------------
            await pilot.hover(nord)
            await pilot.pause()
            await asyncio.sleep(0.15)
            live = theme.get_theme()
            check("hover applies preview live", live == "nord", f"live={live}")

            with open(tmp_theme, encoding="utf-8") as f:
                persisted = json.load(f)["theme"]
            check("preview NOT persisted", persisted == "tokyo-night",
                  f"file={persisted}")
            check("preview NOT in central config",
                  cct_config.get_config().default_theme != "nord",
                  str(cct_config.get_config().default_theme))

            # ---- moving away restores the saved theme ----------------------
            await pilot.hover(gruv)
            await pilot.pause()
            await asyncio.sleep(0.15)
            check("hover second theme previews it",
                  theme.get_theme() == "gruvbox", str(theme.get_theme()))

            # leave both rows entirely (hover a non-theme widget)
            await pilot.hover(app.brand_header)
            await pilot.pause()
            await asyncio.sleep(0.15)
            check("leaving rows restores saved theme",
                  theme.get_theme() == "tokyo-night", str(theme.get_theme()))

            # exactly one ✓ while hovering
            marks = [r.theme_name for r in rows
                     if "\u2713" in r.render().plain]
            check("exactly one permanent checkmark", marks == ["tokyo-night"],
                  str(marks))

            # ---- click = permanent apply + persist --------------------------
            app._on_theme_chosen("dracula")
            await pilot.pause()
            await asyncio.sleep(0.1)
            check("click applies permanently",
                  theme.get_theme() == "dracula", str(theme.get_theme()))
            with open(tmp_theme, encoding="utf-8") as f:
                persisted = json.load(f)["theme"]
            cfg_theme = cct_config.get_config().default_theme
            check("click persists to BOTH stores",
                  persisted == "dracula" and cfg_theme == "dracula",
                  f"file={persisted} cfg={cfg_theme}")

        # ---- restart: saved theme auto-applies ------------------------------
        repl2 = App()
        app2 = CCTApp(repl2, repl2.history, {"solved": 0})
        theme.set_theme("tokyo-night", persist=False, paint_bg=False)  # simulate fresh boot default
        async with app2.run_test(size=(110, 38), headless=True) as pilot:
            await dismiss_welcome(app2, pilot)
            theme.load_saved_theme()
            await pilot.pause()
            check("restart restores saved theme",
                  theme.get_theme() == "dracula", str(theme.get_theme()))
            check("app CSS follows restored theme",
                  app2.get_css_variables().get("app-background") ==
                  "#{:02x}{:02x}{:02x}".format(*theme.get_theme_obj().background))
    finally:
        theme._THEME_FILE = orig_theme_file
        cct_config._cached = orig_cfg_cached
        for pth in (tmp_theme, tmp_cfg):
            try:
                os.remove(pth)
            except OSError:
                pass

    passed = sum(1 for _, ok, _ in _results if ok)
    print(f"\n{passed}/{len(_results)} theme-preview checks passed")
    return passed == len(_results)


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
