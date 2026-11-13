# Master script to apply all 3D Skeuomorphic UI, Header, Voice, and Command Cleanup fixes across the codebase.

import re

# ==============================================================================
# 1. Update calc_terminal/registry.py (Remove aliases for removed commands)
# ==============================================================================
with open("calc_terminal/registry.py", "r", encoding="utf-8") as f:
    reg_code = f.read()

old_alias_table = '''ALIAS_TABLE = {
    "/h": "/help", "/c": "/calculator", "/s": "/solve", "/f": "/formulas",
    "/k": "/kinetics", "/d": "/derive", "/g": "/graph", "/a": "/about",
    "/gm": "/game", "/pg": "/game",
    "/e": "/electrochemistry", "/r": "/random", "/x": "/exit",
    "/o": "/orbitals", "/u": "/upload", "/v": "/voice", "/3": "/sim3d",
    "/ag": "/agent", "/y": "/history", "/st": "/settings", "/sh": "/shortcuts",
    "/at": "/atomsim", "/vf": "/verify", "/?": "/help", "/m": "/memory",
    "/cp": "/codepad", "/tk": "/tokens", "/th": "/theme", "/ws": "/websearch",
    "/rs": "/research", "/im": "/import", "/pt": "/pet", "/cc": "/copycode",
    "/rx": "/react", "/ex": "/export", "/tu": "/tui", "/co": "/composer",
    "/br": "/browser", "/bw": "/browse", "/cat": "/browser",
}'''

new_alias_table = '''ALIAS_TABLE = {
    "/h": "/help", "/c": "/calculator", "/s": "/solve", "/f": "/formulas",
    "/d": "/derive", "/a": "/about", "/x": "/exit",
    "/u": "/upload", "/v": "/voice",
    "/ag": "/agent", "/y": "/history", "/st": "/settings", "/sh": "/shortcuts",
    "/vf": "/verify", "/?": "/help", "/m": "/memory",
    "/cp": "/codepad", "/tk": "/tokens", "/th": "/theme", "/ws": "/websearch",
    "/rs": "/research", "/im": "/import", "/pt": "/pet", "/cc": "/copycode",
    "/rx": "/react", "/ex": "/export", "/tu": "/tui", "/co": "/composer",
    "/br": "/browser", "/bw": "/browse", "/cat": "/browser",
}'''

if old_alias_table in reg_code:
    reg_code = reg_code.replace(old_alias_table, new_alias_table)
    with open("calc_terminal/registry.py", "w", encoding="utf-8") as f:
        f.write(reg_code)
    print("Updated calc_terminal/registry.py")

# ==============================================================================
# 2. Update calc_terminal/ui/command_palette.py
# ==============================================================================
with open("calc_terminal/ui/command_palette.py", "r", encoding="utf-8") as f:
    pal_code = f.read()

old_pal_cat = '''_CATEGORY_OF = {
    "solve": "solve", "calculator": "solve", "kinetics": "solve",
    "derive": "solve", "electrochemistry": "solve", "formulas": "solve",

    "sim3d": "simulate", "atomsim": "simulate", "orbitals": "simulate",
    "orbitalgrid": "simulate", "bonding": "simulate", "bloch": "simulate",
    "react": "simulate", "graph": "simulate",

    "gpu3d": "gpu3d",'''

new_pal_cat = '''_CATEGORY_OF = {
    "solve": "solve", "calculator": "solve",
    "derive": "solve", "formulas": "solve",

    "bloch": "simulate",
    "react": "simulate",'''

if old_pal_cat in pal_code:
    pal_code = pal_code.replace(old_pal_cat, new_pal_cat)
    with open("calc_terminal/ui/command_palette.py", "w", encoding="utf-8") as f:
        f.write(pal_code)
    print("Updated calc_terminal/ui/command_palette.py")

# ==============================================================================
# 3. Update calc_terminal/ui/header.py (Remove wide unstyled spacers)
# ==============================================================================
with open("calc_terminal/ui/header.py", "r", encoding="utf-8") as f:
    hdr_code = f.read()

old_hdr_compose = '''        def compose(self):
            with Horizontal(id="cct-header-top"):
                with Horizontal(id="cct-header-left"):
                    yield MenuButton()
                    yield Logo()
                yield Static("", id="cct-header-spacer-left")
                yield PermissionPill()
                yield Static("", id="cct-header-spacer-right")
                with Horizontal(id="cct-header-right-box"):
                    yield Button(_safe_glyph("📁", "Exp"), id="cct-header-explorer-btn", classes="cct-header-explorer-btn", tooltip="Toggle Explorer (Ctrl+B)")
                    yield _Clickable("", widget_id="cct-header-right", on_click=self._show_workspace_info)'''

new_hdr_compose = '''        def compose(self):
            with Horizontal(id="cct-header-top"):
                with Horizontal(id="cct-header-left"):
                    yield MenuButton()
                    yield Logo()
                yield PermissionPill()
                with Horizontal(id="cct-header-right-box"):
                    yield Button(_safe_glyph("📁", "Exp"), id="cct-header-explorer-btn", classes="cct-header-explorer-btn", tooltip="Toggle Explorer (Ctrl+B)")
                    yield _Clickable("", widget_id="cct-header-right", on_click=self._show_workspace_info)'''

if old_hdr_compose in hdr_code:
    hdr_code = hdr_code.replace(old_hdr_compose, new_hdr_compose)
    with open("calc_terminal/ui/header.py", "w", encoding="utf-8") as f:
        f.write(hdr_code)
    print("Updated calc_terminal/ui/header.py compose()")

print("Core files updated.")

