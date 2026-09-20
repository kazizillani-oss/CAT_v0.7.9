"""
v0.7.9.6 probe — 3D / skeuomorphism + responsive-art verification.

Read-only QA harness (never mutates app state). Three independent checks:

  1. CSS PARSE  — feeds the exact concatenated stylesheet CCTApp installs
                  (theme_css.BASE_CSS + app._COMPONENT_CSS + app._BROWSER_CSS)
                  through Textual's real stylesheet reader. A missing
                  `$variable` or a typo'd property shows up here instead of
                  crashing the TUI at runtime.
  2. ART CHAIN  — walks the chat-empty-state width ladder and asserts every
                  rung renders without raising and never exceeds its column
                  budget (the "super responsive mini cat" contract).
  3. SKEU AUDIT — audits the merged stylesheet for the 3D bevel contract:
                  every interactive surface must declare a raised bevel plus
                  hover-lift / press-in offsets.

Run:  python _probe_3d_responsive.py
Exit code 0 = all green.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FAILURES = []


def _fail(msg):
    FAILURES.append(msg)
    print("  [FAIL] " + msg)


def _ok(msg):
    print("  [ ok ] " + msg)


# ---------------------------------------------------------------- check 1 --
def check_css_parse():
    print("\n[1/3] CSS parse (Textual stylesheet reader)")
    try:
        from calc_terminal.ui import app as ui_app
        from calc_terminal.ui import theme_css
    except Exception as exc:
        _fail(f"importing ui modules raised {exc!r}")
        return None

    css = theme_css.BASE_CSS + ui_app._COMPONENT_CSS + ui_app._BROWSER_CSS
    print(f"  merged stylesheet: {len(css)} chars")
    try:
        from textual.css.stylesheet import Stylesheet
    except Exception as exc:
        _fail(f"textual.css.stylesheet unavailable: {exc!r}")
        return css

    try:
        sheet = Stylesheet()
        variables = theme_css.css_variables()
        # Every `$name` in the stylesheet must resolve against the same map
        # CCTApp.get_css_variables() returns at runtime. Strip /* comments */
        # first so prose like "$variable-driven" in a docstring isn't a hit.
        merged = theme_css.BASE_CSS + ui_app._COMPONENT_CSS
        stripped = re.sub(r"/\*.*?\*/", "", merged, flags=re.S)
        used = sorted(set(re.findall(r"\$([A-Za-z][A-Za-z0-9_-]*)", stripped)))
        missing = [v for v in used if v not in variables]
        if missing:
            _fail(f"undefined CSS variables referenced: {missing}")
        else:
            _ok(f"all {len(used)} referenced $variables are defined")
        sheet.set_variables(variables)
        sheet.add_source(css, None)
        sheet.parse()
        _ok("Stylesheet parsed the merged CSS without raising")
    except Exception as exc:
        _fail(f"Stylesheet rejected the app CSS: {exc!r}")
    return css


# ---------------------------------------------------------------- check 2 --
def _cell_len(text):
    try:
        import rich.cells
        return rich.cells.cell_len(text)
    except Exception:
        return len(text)


def check_art_chain():
    print("\n[2/4] Responsive CAT art chain (empty-state width ladder)")
    try:
        from calc_terminal.ui import empty_state as es
    except Exception as exc:
        _fail(f"importing empty_state raised {exc!r}")
        return

    if not getattr(es, "TEXTUAL_AVAILABLE", False) or es.CATChatEmptyState is None:
        _fail("empty_state has no CATChatEmptyState (Textual unavailable)")
        return

    # (pane width, expected variant key, column budget for the widest line)
    ladder = [
        (2, "text", 0),
        (4, "nanoface", 4),
        (6, "microface", 5),
        (10, "tinyface", 8),
        (14, "miniface", 11),
        (22, "compact", 16),
        (28, "semi", 27),
        (40, "full", 30),
    ]
    print("  --- width ladder (height=None, i.e. tall pane) ---")
    for width, expect_key, max_cols in ladder:
        got = es._pick_art_variant(width, None)
        if got != expect_key:
            _fail(f"width={width}: expected {expect_key!r}, got {got!r}")
            continue
        _ok(f"width={width:>3} -> {got}")
        _check_render(es, width, max_cols)

    print("  --- short-pane gate (height=6, no room for 3 rows) ---")
    for width, expect_key in ((14, "miniface2"), (22, "miniface2"),
                              (10, "miniface2"), (4, "nanoface"),
                              (40, "miniface2")):
        got = es._pick_art_variant(width, 6)
        if got != expect_key:
            _fail(f"w={width},h=6: expected {expect_key!r}, got {got!r}")
        else:
            _ok(f"w={width:>3},h=6 -> {got}")
    _check_render(es, 20, 24, variant="miniface2")

    print("  --- tall-pane gate (height=30 must NOT downgrade) ---")
    for width, expect_key in ((40, "full"), (28, "semi"), (22, "compact"),
                              (14, "miniface")):
        got = es._pick_art_variant(width, 30)
        if got != expect_key:
            _fail(f"w={width},h=30: expected {expect_key!r}, got {got!r}")
        else:
            _ok(f"w={width:>3},h=30 -> {got}")

    print("  --- ultra-narrow text fallback (must not overflow either) ---")
    for width, budget in ((2, 3), (3, 3), (8, 7), (14, 11), (22, 22)):
        widget = es.CATChatEmptyState()
        widget._compact = "text"
        widget._last_width = width
        markup = widget._art_markup()
        plain = re.sub(r"\[/?[^\]]*\]", "", markup)
        got = _cell_len(plain)
        if got > budget:
            _fail(f"text @ width={width}: {got} cols exceeds {budget}")
        else:
            _ok(f"text @ width={width:>3}: {got:>2} cols (budget {budget})")

    for name in ("_SEMI_ART", "_COMPACT_ART", "_MINI_CAT_ART", "_TINY_CAT_ART",
                 "_MICRO_CAT_ART", "_NANO_CAT_ART", "_MINI_CAT_ART_2ROW"):
        art = getattr(es, name, None)
        if not art:
            _fail(f"{name} missing or empty")
        else:
            widest = max(_cell_len(l) for l in art)
            _ok(f"{name} present ({len(art)} rows, widest {widest} cols)")


def _check_render(es, width, max_cols, variant=None):
    """Render one variant through the real widget and assert the widest
    plain-text line stays inside the column budget."""
    widget = es.CATChatEmptyState()
    if variant is not None:
        widget._compact = variant
    else:
        widget._compact = es._pick_art_variant(width, None)
    try:
        markup = widget._art_markup()
    except Exception as exc:
        _fail(f"width={width}: _art_markup raised {exc!r}")
        return
    widest = 0
    for line in markup.splitlines():
        plain = re.sub(r"\[/?[^\]]*\]", "", line)
        widest = max(widest, _cell_len(plain))
    if max_cols and widest > max_cols:
        _fail(f"width={width} -> {widget._compact!r}: art is {widest} cols, "
              f"budget {max_cols} — would overflow")
    else:
        _ok(f"  rendered {str(widget._compact):>9}: widest {widest:>2} cols")


# ---------------------------------------------------------------- check 3 --
def check_skeu_blocks(css):
    print("\n[3/4] 3D skeuomorphism contract")
    if not css:
        _fail("no stylesheet text available to audit")
        return

    must_have = {
        "global Button bevel": "Button, Button:ansi.-style-default",
        "button hover lift": "Button:hover, .cct-btn:hover",
        "button press-in": "Button.-active, .cct-btn.-active",
        "button sunken-disabled": "Button:disabled, .cct-btn:disabled",
        "dashboard quick-action keycap": "Button.cct-dash-action",
        "dash card 3D": ".cct-dash-card-3d",
        "chat bubble user": ".cct-bubble-user",
        "chat bubble assistant": ".cct-bubble-assistant",
        "chat bubble system": ".cct-bubble-system",
        "message action keycap": ".cct-msg-btn",
        "sunken input": ".cct-input-3d-skeu",
        "bubble press-in": ".cct-bubble-user.-active",
        "dash action press-in": "Button.cct-dash-action.-active",
    }
    for label, needle in must_have.items():
        if needle in css:
            _ok(f"{label} present")
        else:
            _fail(f"{label} missing ({needle!r})")

    tall = css.count("tall ")
    if tall < 40:
        _fail(f"only {tall} `tall` border declarations — bevel coverage too thin")
    else:
        _ok(f"{tall} `tall` border declarations (deep bevel coverage)")


def check_wiring(css):
    print("\n[4/4] Wiring & CSS ownership (v0.7.9.6 fixes)")
    # --- the dead dashboard branch in CCTApp._cascade_resize ----------
    try:
        from calc_terminal.ui.conversation import ConversationView
        src_ok = hasattr(ConversationView, "show_dashboard")
        if src_ok:
            _ok("ConversationView.show_dashboard present")
        else:
            _fail("ConversationView.show_dashboard missing")
    except Exception as exc:
        _fail(f"importing ConversationView raised {exc!r}")

    # --- `.cct-dash-col` must be layout-only --------------------------
    blocks = _rule_blocks(css)
    col = blocks.get(".cct-dash-col")
    card = blocks.get(".cct-dash-card-3d")
    if col is None:
        _fail(".cct-dash-col rule not found")
    else:
        leaked = [p for p in ("border", "background", "border-top",
                              "padding", "margin", "tint")
                  if re.search(rf"^\s*{p}\s*:", col, re.M)]
        if leaked:
            _fail(f".cct-dash-col redeclares card skin {leaked} — "
                  f"conflicts with .cct-dash-card-3d at equal specificity")
        else:
            _ok(".cct-dash-col is layout-only (no skin duplication)")
    if card is None:
        _fail(".cct-dash-card-3d rule not found (cards would be skinless)")
    else:
        for prop in ("border-top", "border-left", "border-bottom",
                     "border-right", "padding", "margin", "tint"):
            if not re.search(rf"^\s*{prop}\s*:", card, re.M):
                _fail(f".cct-dash-card-3d missing `{prop}` (3D skin incomplete)")
        _ok(".cct-dash-card-3d owns the full 3D card skin")

    # --- dashboard must DELEGATE its art ladder, not fork it -----------
    # Before v0.7.9.6 dashboard.py had its own 3-rung ladder, so every
    # face variant added to empty_state had to be hand-copied. If that
    # second ladder ever comes back, the two screens silently disagree.
    try:
        import inspect

        from calc_terminal.ui import dashboard as dash_mod
        from calc_terminal.ui import empty_state as es_mod
        src = inspect.getsource(dash_mod.WelcomeDashboard._art_lines)
        if "_pick_art_variant" in src:
            _ok("WelcomeDashboard._art_lines delegates to _pick_art_variant")
        else:
            _fail("WelcomeDashboard._art_lines has its own art ladder "
                  "(forks the shared responsive policy)")
        # height-gate must be honoured by the dashboard too
        if "_MIN_3ROW_HEIGHT" in src or ", h" in src or "h)" in src:
            _ok("WelcomeDashboard passes height into the ladder")
        variants = [es_mod._pick_art_variant(w, 40)
                    for w in (40, 28, 22, 14, 10, 6, 4, 2)]
        if len(set(variants)) < 5:
            _fail(f"ladder collapsed: {variants}")
        else:
            _ok(f"ladder produces {len(set(variants))} distinct variants")
    except Exception as exc:
        _fail(f"dashboard delegation check raised {exc!r}")


def _rule_blocks(css):
    """{selector: body} for every rule, splitting comma-separated
    selector lists so a shared rule (`.a, .b { ... }`) is queryable
    under each of its selectors individually."""
    out = {}
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        sel = selector.strip()
        # strip comments from the selector list
        sel = re.sub(r"/\*.*?\*/", "", sel, flags=re.S).strip()
        if not sel:
            continue
        for one in sel.split(","):
            one = " ".join(one.split())
            if one:
                out.setdefault(one, body)
    return out



def main():
    css = check_css_parse()
    check_art_chain()
    check_skeu_blocks(css)
    check_wiring(css)
    print("\n" + "=" * 62)
    if FAILURES:
        print(f"RESULT: {len(FAILURES)} failure(s)")
        for f in FAILURES:
            print("  - " + f)
        return 1
    print("RESULT: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
