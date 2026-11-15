import os
import sys

# Ensure calc_terminal is importable
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from calc_terminal import extensions as ext_mgr
from calc_terminal.ui.extensions_panel import ExtensionsPanel
from calc_terminal.ui.chats_panel import ChatsPanel
from calc_terminal.ui.statusbar import ToolsModal, StatusBar
from calc_terminal.ui.dashboard import WelcomeDashboard
from calc_terminal.ui import theme_css

print("1. Testing ExtensionsPanel Built-in skills...")
p = ExtensionsPanel()
exts = p._filtered()
ext_ids = [e.get("id") for e in exts]
print(f"Total built-in extensions found: {len(exts)}")
print(f"IDs: {ext_ids}")

assert "skill-creator" in ext_ids, "skill-creator must be in built-in extensions"
assert "find-skills" in ext_ids, "find-skills must be in built-in extensions"
assert "gestures" in ext_ids, "gestures must be in built-in extensions"
assert "personalize" in ext_ids, "personalize must be in built-in extensions"
print("✓ Built-in skills verified: skill-creator and find-skills present!")

# Check creator attribution
sc = next(e for e in exts if e.get("id") == "skill-creator")
assert "Anthropic" in sc.get("publisher", ""), "Anthropic publisher credit required"
print(f"✓ skill-creator credit: {sc.get('publisher')}")

fs = next(e for e in exts if e.get("id") == "find-skills")
assert "Vercel" in fs.get("publisher", ""), "Vercel Labs publisher credit required"
print(f"✓ find-skills credit: {fs.get('publisher')}")

print("\n2. Testing ToolsModal...")
tm = ToolsModal()
assert str(getattr(tm._fmt_label(True, "Test"), "plain", tm._fmt_label(True, "Test"))) == "[x] Test"
assert str(getattr(tm._fmt_label(False, "Test"), "plain", tm._fmt_label(False, "Test"))) == "[ ] Test"
print("✓ ToolsModal checkbox formatting verified!")

print("\n3. Testing Dashboard responsive cards...")
d = WelcomeDashboard(["CAT"], "0.9.000", "test-model", 0, workspace_root=repo_root)
print("✓ WelcomeDashboard instantiated successfully!")

print("\n4. Testing ChatsPanel instantiation...")
cp = ChatsPanel()
print("✓ ChatsPanel instantiated successfully!")

print("\nALL BACKEND CHECKS PASSED PERFECTLY!")
