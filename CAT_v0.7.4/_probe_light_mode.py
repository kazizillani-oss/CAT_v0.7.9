"""
CAT v0.7.9.0 — LIGHT-MODE UI audit verification.

Checks (headless, real rendering where possible):

  A. Theme token system
     1. light mode emits contrast-correct Textual component overrides
        (selection, cursors, button label/focus, markdown headings)
     2. dark mode emits NONE of them (dark unchanged)
  B. Accent-colored text readability
     3. every thinking-stage color passes WCAG >= 3:1 on its surface
     4. every command-palette color passes WCAG >= 3:1 on its surface
     5. completion summary ✓ color passes in both themes
  C. Code editor
     6. light -> GitHub-Light palette (white bg, subtle selection)
        dark -> Tokyo Night (unchanged)
     7. live /theme switch re-themes open editor tabs + chat bubbles
  D. Chat surfaces
     8. user-bubble label gets a contrast-correct color on light accents
     9. empty-state word-art colors darken in light mode
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_results = []


def check(name, ok, detail=""):
    _results.append((name, bool(ok), detail))
    print(("[PASS] " if ok else "[FAIL] ") + name + (f" {detail}" if detail else ""))


def _lum(hex_color):
    r = int(hex_color[1:3], 16) / 255.0
    g = int(hex_color[3:5], 16) / 255.0
    b = int(hex_color[5:7], 16) / 255.0
    lin = [(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
           for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(fg_hex, bg_hex):
    l1, l2 = _lum(fg_hex), _lum(bg_hex)
    lo, hi = min(l1, l2), max(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


async def dismiss_welcome(app, pilot, timeout=6.0):
    """Skip the animated Welcome Screen deterministically (it plays on
    every launch now and auto-continues into the Dashboard)."""
    from calc_terminal.ui.welcome_modal import WelcomeModal
    t0 = __import__("time").time()
    while __import__("time").time() - t0 < timeout:
        if not any(isinstance(s, WelcomeModal) for s in app.screen_stack):
            return
        await pilot.press("escape")
        await pilot.pause()
        await asyncio.sleep(0.05)


async def main():
    from calc_terminal import theme
    from calc_terminal.ui import theme_css
    from calc_terminal.ui import thinking, command_palette, editor as ed

    # ---------------- B/C/D pure-logic checks, both themes -------------
    for theme_name in ("light", "dark"):
        theme.set_theme(theme_name, persist=False, paint_bg=False)
        surface = "#ffffff" if theme_name == "light" else "#1a1b26"

        stage_colors = {k: thinking.stage_info(k)[1] for k in thinking.STAGES}
        bad = {k: f"{v} ({contrast(v, surface):.2f}:1)"
               for k, v in stage_colors.items() if contrast(v, surface) < 3.0}
        check(f"[{theme_name}] all thinking-stage colors readable "
              f"(WCAG>=3 on surface)", not bad,
              "; ".join(f"{k}:{d}" for k, d in list(bad.items())[:4]))

        pal_cmds = ["/solve", "/simulate", "/gpu3d", "/build", "/plan",
                    "/websearch", "/deepresearch", "/research", "/debug",
                    "/install", "/pipeline", "/devices", "/history",
                    "/help"]
        pal_bad = []
        for c in pal_cmds:
            col = command_palette.category_color(c)
            # 'history' uses the intentionally-muted gray role; give it a
            # relaxed floor. Everything else must hit WCAG>=3.
            floor = 2.4 if c == "/history" else 3.0
            if contrast(col, surface) < floor:
                pal_bad.append(f"{c}:{col}")
        check(f"[{theme_name}] command-palette colors readable",
              not pal_bad, ", ".join(pal_bad[:4]))

        lines = thinking.completion_summary_lines(provider="x")
        ok_line = lines[0]
        hex_in = "#" + ok_line.split("#", 1)[1].split("[")[0][:6] \
            if "#" in ok_line else ""
        check(f"[{theme_name}] completion summary uses themed green",
              bool(hex_in) and contrast(hex_in, surface) >= 3.0, hex_in)

    # ---------------- A: variable emission ------------------------------
    # v0.7.9.5: component variables are now DERIVED from the active
    # theme object (works for all 22 themes), so the assertions check
    # the derivation contract + contrast instead of one theme's hexes.
    theme.set_theme("light", persist=False, paint_bg=False)
    lv = theme_css.css_variables()
    t_light = theme.get_theme_obj()
    check("[light] selection override emitted (subtle solid wash)",
          lv.get("input-selection-background") == t_light.hex("selection_background")
          and lv.get("input-selection-foreground") == t_light.hex("selection_text"),
          str(lv.get("input-selection-background")))
    check("[light] screen selection emitted",
          "screen-selection-background" in lv)
    check("[light] button label forced to dark text",
          lv.get("button-foreground") == t_light.hex("text"),
          str(lv.get("button-foreground")))
    check("[light] button focus drops reverse-video block",
          lv.get("button-focus-text-style") == "bold")
    check("[light] cursors visible on white",
          contrast(lv.get("input-cursor-background", "#000"),
                   t_light.hex("background")) >= 3.0
          and str(lv.get("block-cursor-background")).startswith("#"),
          str(lv.get("input-cursor-background")))
    check("[light] markdown heading colors overridden",
          lv.get("markdown-h4-color") == t_light.hex("text"))

    theme.set_theme("dark", persist=False, paint_bg=False)
    dv = theme_css.css_variables()
    leaked = [k for k in ("button-foreground", "button-focus-text-style",
                          "input-selection-background",
                          "screen-selection-background",
                          "markdown-h4-color") if k in dv]
    check("[dark] NO component-variable overrides (dark untouched)",
          not leaked, ",".join(leaked))

    # ---------------- C: editor palettes --------------------------------
    theme.set_theme("light", persist=False, paint_bg=False)
    (name_l, bg_l, _g1, _g2, cur_l, _cl, _br, sel_l, _cols) = \
        ed._editor_palette()

    def _rgb(color):
        t = color.get_truecolor()
        return (t.red, t.green, t.blue)

    check("[light] editor palette = GitHub-Light",
          name_l == "cct-github-light" and _rgb(bg_l.bgcolor) == (255, 255, 255),
          name_l)
    check("[light] editor cursor visible (dark glyph on blue block)",
          _rgb(cur_l.bgcolor) == (9, 105, 218))

    theme.set_theme("dark", persist=False, paint_bg=False)
    name_d, bg_d = ed._editor_palette()[:2]
    check("[dark] editor palette = Tokyo Night (unchanged)",
          name_d == "cct-tokyonight"
          and _rgb(bg_d.bgcolor) == (22, 22, 30), name_d)

    theme.set_theme("light", persist=False, paint_bg=False)
    (_n, _bg, _gut, _ga, _cur, _cl, _br, sel_light, _cols) = ed._editor_palette()
    check("[light] editor selection is a soft blue wash (no glow)",
          sel_light.bgcolor is not None
          and _rgb(sel_light.bgcolor) == (182, 215, 255))

    # ---------------- D: live UI switch test -----------------------------
    from calc_terminal import aicore
    from calc_terminal import projects as _projects
    _projects.recent = lambda: []

    class FakeTransport:
        def __call__(self, prompt, system_prompt=None, history=None,
                     config=None, attachments=None, **kw):
            yield "Answer with ```py\nprint(1)\n``` fenced code."

    orig = aicore._stream_ai_once
    aicore._stream_ai_once = FakeTransport()

    from calc_terminal.ui.app import CCTApp
    theme.set_theme("light", persist=False, paint_bg=False)
    ai_modes_mod = __import__("calc_terminal.ai_modes", fromlist=["x"])
    saved_mode = ai_modes_mod.current_mode()

    app = CCTApp(repl=None, history=[], stats={})
    async with app.run_test(size=(110, 40), headless=True) as pilot:
        conv = app.query_one("#cct-conversation")
        for _ in range(6):
            await pilot.pause(); await asyncio.sleep(0.1)
        await dismiss_welcome(app, pilot)

        editor = app.query_one("ComposerInput")
        editor.focus()
        await pilot.press(*"hi"); await pilot.press("enter")
        t0 = __import__("time").time()
        while __import__("time").time() - t0 < 15:
            await pilot.pause(); await asyncio.sleep(0.1)
            if not getattr(app, "_is_streaming", False):
                break

        # user bubble inline label color chosen by luminance (light mode)
        items = list(conv._items.values())
        user_item = next((i for i in items if i.role == "user"), None)
        ok_user, detail_user = False, ""
        if user_item is not None:
            try:
                col = user_item.styles.color
                # textual.color.Color — .hex is like '#1b1f27'
                hexcol = getattr(col, "hex", None)
                detail_user = str(hexcol)
                ok_user = str(hexcol).lower() in ("#1b1f27", "#ffffff")
            except Exception as e:
                detail_user = repr(e)[:60]
        check("[light][live] user bubble label contrast-correct on accent",
              ok_user, detail_user)

        # live switch dark -> light already active; go light -> dark ->
        # light via the ONE centralized path and confirm nothing errors
        # and variables follow.
        app._apply_theme_switch("dark")
        await pilot.pause()
        v_dark = app.get_css_variables()
        check("[live] switch to dark updates CSS variables immediately",
              v_dark.get("app-background") == "#1a1b26"
              and "button-foreground" not in
              {k for k in v_dark if k.startswith("button-foreground")}
              or v_dark.get("button-focus-text-style", None) != "bold")
        app._apply_theme_switch("light")
        await pilot.pause()
        v_light = app.get_css_variables()
        check("[live] switch back to light restores overrides",
              v_light.get("button-foreground") == "#181c22")

        # bubbles survived the double switch and got re-rendered
        check("[live] chat bubbles intact after theme round-trip",
              len(conv._items) >= 2)

    aicore._stream_ai_once = orig
    ai_modes_mod.set_mode(saved_mode)

    fails = [r for r in _results if not r[1]]
    print(f"\n{len(_results) - len(fails)}/{len(_results)} light-mode checks passed")
    if fails:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
