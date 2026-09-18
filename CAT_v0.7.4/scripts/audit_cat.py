import os
import sys
import json
import inspect
import importlib

def inspect_mod(mod_name):
    try:
        mod = importlib.import_module(mod_name)
        funcs = [n for n, o in inspect.getmembers(mod, inspect.isfunction) if o.__module__ == mod_name]
        classes = [n for n, o in inspect.getmembers(mod, inspect.isclass) if o.__module__ == mod_name]
        attrs = [n for n in dir(mod) if not n.startswith('__')]
        return {"funcs": funcs, "classes": classes, "attrs": attrs}
    except Exception as e:
        return {"error": str(e)}

print("=== INSPECTING ACTUAL MODULE STRUCTURES ===")
for m in [
    "calc_terminal.agent",
    "calc_terminal.ai_modes",
    "calc_terminal.permissions",
    "calc_terminal.memory",
    "calc_terminal.cct_perms",
    "calc_terminal.commands_data",
    "calc_terminal.web.cat_runtime",
    "calc_terminal.aicore",
    "calc_terminal.projects",
    "calc_terminal.workspace",
    "calc_terminal.fomoji_auth",
    "calc_terminal.extensions"
]:
    res = inspect_mod(m)
    print(f"\n--- {m} ---")
    if "error" in res:
        print("  Error:", res["error"])
    else:
        print(f"  Classes ({len(res['classes'])}): {res['classes']}")
        print(f"  Functions ({len(res['funcs'])}): {res['funcs'][:10]}")
        print(f"  Notable Attrs: {[a for a in res['attrs'] if a not in res['classes'] and a not in res['funcs']][:10]}")
