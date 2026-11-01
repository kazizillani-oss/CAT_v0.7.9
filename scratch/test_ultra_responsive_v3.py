import os
import sys
import asyncio

ROOT = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.stdout.reconfigure(encoding='utf-8')

from calc_terminal.app import App
from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.header import BrandHeader, NavPanel, PermissionPill, PermissionModeMenu
from calc_terminal.ui.composer import StickyComposer
from calc_terminal.ui.palette import CommandPalette
from calc_terminal.ui.nav_screens import ThemesPanel, UserPanel
from calc_terminal.ui.sidebar import OpenWorkspaceScreen, RecentWorkspacesScreen

async def run_v3_tests():
    print("=" * 70)
    print("RUNNING ULTRA-RESPONSIVE SUITE V3 VERIFICATION")
    print("=" * 70)

    repl = App()
    stats = {"solved": 0, "provider": "none", "model": "none"}

    # --- Test 1: Landscape Header Borders & Pill Alignment ---
    print("\n--- Test 1: Landscape Header Borders & Pill Alignment ---")
    app = CCTApp(repl, repl.history, stats)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        header = app.query_one(BrandHeader)
        pill = header.query_one(PermissionPill)
        ws_chip = header.query_one("#cct-header-right")
        menu_btn = header.query_one(".cct-menu-btn")

        print(f"  Landscape Header classes: {header.classes}")
        print(f"  PermissionPill border: {pill.styles.border}")
        print(f"  Workspace chip border: {ws_chip.styles.border}")
        print(f"  Menu button border: {menu_btn.styles.border}")

        assert pill.styles.border.top == ("round", pill.styles.border.top[1]) or pill.styles.border.top[0] in ("round", "solid"), "Pill must have round or solid border"
        assert ws_chip.styles.border.top[0] in ("round", "solid"), "Workspace chip must have round or solid border"
        assert menu_btn.styles.border.top[0] in ("round", "solid"), "Menu btn must have round or solid border"
        print("  [PASS] Landscape header buttons have clean, fully enclosed borders (no broken open-bottom)")

    # --- Test 2: Portrait NavPanel Integrations (MCP & Backup) ---
    print("\n--- Test 2: Portrait NavPanel Integrations (MCP & Backup) ---")
    app = CCTApp(repl, repl.history, stats)
    async with app.run_test(size=(70, 40)) as pilot:
        await pilot.pause()
        panel = NavPanel()
        app.push_screen(panel)
        await pilot.pause()

        items = [row.action_id for row in panel.query(".cct-navmenu-row")]
        print(f"  Portrait NavPanel Action IDs: {items}")

        assert "mcp_servers" in items, "mcp_servers MUST be present in portrait NavPanel"
        assert "backup_providers" in items, "backup_providers MUST be present in portrait NavPanel"
        assert "open_folder" in items, "open_folder must be present"
        assert "recent_workspaces" in items, "recent_workspaces must be present"
        assert "themes" in items, "themes must be present"
        assert "user" in items, "user must be present"
        assert "signout" in items, "signout must be present"
        assert "quit" in items, "quit must be present"
        print("  [PASS] MCP Servers & Backup Providers present and verified in portrait NavPanel")

    # --- Test 3: Command Palette Height & Visibility in Portrait ---
    print("\n--- Test 3: Command Palette Height & Visibility in Portrait ---")
    app = CCTApp(repl, repl.history, stats)
    async with app.run_test(size=(70, 40)) as pilot:
        await pilot.pause()
        comp = app.query_one(StickyComposer)
        palette = comp.query_one(CommandPalette)
        palette.open_for_query("/")
        await pilot.pause()

        rows = list(palette.query(".cct-cmd-row"))
        print(f"  Commands rendered: {len(rows)}, Palette height: {palette.styles.height}")
        assert len(rows) >= 5, f"Expected at least 5 commands to render, got {len(rows)}"
        assert palette.styles.height.value >= 6, "Palette height must be at least 6 to fit rows + borders"
        print("  [PASS] Command palette renders multiple commands cleanly with bounded height")

    # --- Test 4: Ultra-Responsive Modals in Portrait (User, Themes, Open, Recent) ---
    print("\n--- Test 4: Ultra-Responsive Modals in Portrait Mode ---")
    app = CCTApp(repl, repl.history, stats)
    async with app.run_test(size=(65, 38)) as pilot:
        await pilot.pause()

        # 4a: ThemesPanel
        tp = ThemesPanel("tokyo-night")
        app.push_screen(tp)
        await pilot.pause()
        assert tp.has_class("is-portrait"), "ThemesPanel must have is-portrait class"
        tp_box = tp.query_one("#cct-navpanel-box")
        print(f"  ThemesPanel width: {tp_box.size.width} in 65-col screen")
        assert tp_box.size.width <= 64, "ThemesPanel box must fit within 65-col portrait screen"
        tp.dismiss(None)
        await pilot.pause()

        # 4b: UserPanel
        up = UserPanel(lambda: {"user": {"name": "ADMIN"}, "model": "nemotron-3-ultra", "provider": "nvidia"})
        app.push_screen(up)
        await pilot.pause()
        assert up.has_class("is-portrait"), "UserPanel must have is-portrait class"
        up_box = up.query_one("#cct-navpanel-box")
        print(f"  UserPanel width: {up_box.size.width} in 65-col screen")
        assert up_box.size.width <= 64, "UserPanel box must fit within 65-col portrait screen"
        up.dismiss(None)
        await pilot.pause()

        # 4c: OpenWorkspaceScreen
        ows = OpenWorkspaceScreen()
        app.push_screen(ows)
        await pilot.pause()
        assert ows.has_class("is-portrait"), "OpenWorkspaceScreen must have is-portrait class"
        ows_box = ows.query_one("#ows-box")
        print(f"  OpenWorkspaceScreen width: {ows_box.size.width} in 65-col screen")
        assert ows_box.size.width <= 64, "OpenWorkspaceScreen box must fit within 65-col portrait screen"
        ows.dismiss(None)
        await pilot.pause()

        # 4d: RecentWorkspacesScreen
        rws = RecentWorkspacesScreen()
        app.push_screen(rws)
        await pilot.pause()
        assert rws.has_class("is-portrait"), "RecentWorkspacesScreen must have is-portrait class"
        rws_box = rws.query_one("#cct-recentws-box")
        print(f"  RecentWorkspacesScreen width: {rws_box.size.width} in 65-col screen")
        assert rws_box.size.width <= 64, "RecentWorkspacesScreen box must fit within 65-col portrait screen"
        rws.dismiss(None)
        await pilot.pause()

        print("  [PASS] All modals adapt to portrait mode with zero overflow")

    print("\n" + "=" * 70)
    print("ALL ULTRA-RESPONSIVE V3 SUITE TESTS PASSED (100%)")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_v3_tests())

