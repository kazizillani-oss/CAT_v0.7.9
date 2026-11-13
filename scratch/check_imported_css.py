import sys
from textual.css.stylesheet import Stylesheet
import calc_terminal.ui.theme_css as tc

vars = tc.css_variables()

modules = [
    "calc_terminal.ui.app",
    "calc_terminal.ui.header",
    "calc_terminal.ui.composer",
    "calc_terminal.ui.dashboard",
    "calc_terminal.ui.cat_greeting",
    "calc_terminal.ui.palette",
    "calc_terminal.ui.command_palette",
    "calc_terminal.ui.extensions_panel",
    "calc_terminal.ui.resizers",
    "calc_terminal.ui.welcome_modal",
    "calc_terminal.ui.startup_loader",
]

for mod_name in modules:
    mod = __import__(mod_name, fromlist=["*"])
    for attr in dir(mod):
        obj = getattr(mod, attr)
        css = getattr(obj, "CSS", None)
        if isinstance(css, str) and css.strip():
            sheet = Stylesheet(variables=vars)
            sheet.add_source(css, f"{mod_name}::{attr}")
            try:
                sheet.parse()
            except Exception as e:
                print("="*60)
                print(f"FAILED: {mod_name}::{attr}")
                if hasattr(e, "errors"):
                    for err in e.errors:
                        print("  Sub-error:", err)
                else:
                    print(f"  Error: {e}")
