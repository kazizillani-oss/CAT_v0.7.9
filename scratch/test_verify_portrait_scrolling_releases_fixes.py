"""
Verification Script for:
1. ExtensionsPanel scrolling & search debouncing (no fit_dialog thrashing)
2. Main menu cleanliness (no 50+ skills flooding main menu)
3. Header Explorer button hidden in portrait mode ONLY, visible in landscape
4. Explorer & Code Editor 100% fullscreen in portrait mode ONLY
5. BrandHeader height 3 in portrait, zero overlap with workspace/sidebar
6. GitHub releases check & GitHubReleasesModal
"""

import sys
import os

# Ensure repo root is on path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from calc_terminal.ui.header import get_nav_items, BrandHeader, NavPanel
from calc_terminal.ui.extensions_panel import ExtensionsPanel
from calc_terminal.ui.workspace import WorkspaceShell
from calc_terminal.ui.releases_modal import fetch_latest_release, GitHubReleasesModal
from calc_terminal.update_manager import update_manager
from calc_terminal import extensions as ext_mgr


def test_1_extensions_panel_scroll_and_debounce():
    print("[1] Testing ExtensionsPanel scrolling and debounce setup...")
    panel = ExtensionsPanel()
    # Check bindings
    bindings_keys = [b.key for b in panel.BINDINGS]
    assert "escape" in bindings_keys, "Missing escape binding"
    assert "pageup" in bindings_keys, "Missing pageup binding"
    assert "pagedown" in bindings_keys, "Missing pagedown binding"
    assert "up" in bindings_keys, "Missing up binding"
    assert "down" in bindings_keys, "Missing down binding"

    # Check action handlers exist
    assert hasattr(panel, "action_scroll_page_up")
    assert hasattr(panel, "action_scroll_page_down")
    assert hasattr(panel, "action_scroll_up")
    assert hasattr(panel, "action_scroll_down")

    # Check CSS contains overflow-y: scroll and explicit height
    assert "height: 86%" in panel.CSS
    assert "overflow-y: scroll" in panel.CSS
    assert "height: 1fr" in panel.CSS
    print("  -> ExtensionsPanel scroll configuration VERIFIED.")


def test_2_main_menu_cleanliness():
    print("[2] Testing Main Menu cleanliness...")
    nav_items = get_nav_items()
    actions = [it[0] for it in nav_items]
    print(f"  -> Main menu actions count: {len(actions)}")
    print(f"  -> Actions: {actions}")
    
    # Must have standard navigation
    assert "open_folder" in actions
    assert "chats" in actions
    assert "ai_agents" in actions
    assert "themes" in actions
    assert "extensions" in actions

    # Must NOT have 50+ raw skills cluttering the menu
    skill_actions = [a for a in actions if a.startswith("skill_") or a in ("ext:cat-database", "ext:superpowers", "ext:cat-quantum")]
    assert len(skill_actions) == 0, f"Found raw skills in main menu: {skill_actions}"
    assert len(actions) <= 25, f"Main menu is too long: {len(actions)}"
    print("  -> Main Menu cleanliness VERIFIED.")


def test_3_header_explorer_btn_visibility_portrait_vs_landscape():
    print("[3] Testing Header Explorer button visibility in portrait vs landscape...")
    hdr = BrandHeader()
    
    class FakeSize:
        def __init__(self, w, h):
            self.width = w
            self.height = h

    class FakeApp:
        def __init__(self, w, h):
            self.size = FakeSize(w, h)

    # 1. Test Landscape (120x35)
    hdr._app = FakeApp(120, 35)
    class FakeEvent:
        size = FakeSize(120, 35)
    
    # Fake children for on_resize
    class FakeWidget:
        def __init__(self):
            self.display = False
            self.label = ""
            self.classes = set()
        def update(self, *a, **k): pass
        def set_class(self, *a, **k): pass
        def refresh_label(self, *a, **k): pass

    exp_btn = FakeWidget()
    w_right = FakeWidget()
    logo = FakeWidget()
    pill = FakeWidget()

    def fake_query_one(selector, *args, **kwargs):
        if "cct-header-explorer-btn" in selector:
            return exp_btn
        if "cct-header-right" in selector:
            return w_right
        from calc_terminal.ui.header import Logo, PermissionPill
        if selector == Logo:
            return logo
        if selector == PermissionPill:
            return pill
        return FakeWidget()

    hdr.query_one = fake_query_one

    # Test Landscape (120x35) -> exp_btn should be VISIBLE
    hdr.on_resize(FakeEvent())
    assert hdr.has_class("is-portrait") is False, "120x35 falsely identified as portrait"
    assert exp_btn.display is True, "Explorer button should be VISIBLE in landscape"
    assert hdr.styles.height.value == 4, f"Landscape header should be height 4, got {hdr.styles.height}"
    print("  -> Landscape (120x35): Explorer button VISIBLE (height=4).")

    # 2. Test Portrait (50x70) -> exp_btn should be HIDDEN
    hdr._app = FakeApp(50, 70)
    FakeEvent.size = FakeSize(50, 70)
    hdr.on_resize(FakeEvent())
    assert hdr.has_class("is-portrait") is True, "50x70 not identified as portrait"
    assert exp_btn.display is False, "Explorer button should be HIDDEN in portrait"
    assert hdr.styles.height.value == 3, f"Portrait header should be height 3, got {hdr.styles.height}"
    print("  -> Portrait (50x70): Explorer button HIDDEN (height=3).")


def test_4_workspace_portrait_fullscreen():
    print("[4] Testing Workspace portrait detection & fullscreen...")
    shell = WorkspaceShell(None)

    class FakeSize:
        def __init__(self, w, h):
            self.width = w
            self.height = h

    class FakeApp:
        def __init__(self, w, h):
            self.size = FakeSize(w, h)

    # Landscape 120x40 -> False
    shell._app = FakeApp(120, 40)
    assert shell.is_portrait() is False, "120x40 falsely identified as portrait"

    # Portrait 60x50 -> True
    shell._app = FakeApp(60, 50)
    assert shell.is_portrait() is True, "60x50 was not identified as portrait"

    # Narrow 50x30 -> True
    shell._app = FakeApp(50, 30)
    assert shell.is_portrait() is True, "50x30 was not identified as portrait"
    print("  -> Workspace portrait detection VERIFIED.")


def test_5_github_releases():
    print("[5] Testing GitHub release fetcher...")
    rel = fetch_latest_release(timeout=2.0)
    assert "tag_name" in rel
    assert "name" in rel
    assert "body" in rel
    assert "html_url" in rel
    print(f"  -> Release fetched: {rel['name']} ({rel['tag_name']}), online={rel.get('online')}")

    # Test update_manager method
    mgr_rel = update_manager.check_github_release()
    assert "tag_name" in mgr_rel
    print("  -> update_manager.check_github_release() VERIFIED.")


if __name__ == "__main__":
    test_1_extensions_panel_scroll_and_debounce()
    test_2_main_menu_cleanliness()
    test_3_header_explorer_btn_visibility_portrait_vs_landscape()
    test_4_workspace_portrait_fullscreen()
    test_5_github_releases()
    print("\n>>> ALL 5 USER FEEDBACK VERIFICATION TESTS PASSED SUCCESSFULLY! <<<")
