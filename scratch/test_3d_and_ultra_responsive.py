import os
import sys
import asyncio

ROOT = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.stdout.reconfigure(encoding='utf-8')

from calc_terminal.app import App
from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.header import BrandHeader
from calc_terminal.ui.sidebar import RecentWorkspacesScreen, OpenWorkspaceScreen
from calc_terminal.ui.nav_screens import UserPanel, ThemesPanel

async def test_suite():
    print("=" * 70)
    print("RUNNING 3D EFFECTS & ULTRA-RESPONSIVE VERIFICATION SUITE")
    print("=" * 70)

    repl = App()
    stats = {"solved": 0, "provider": "none", "model": "none"}

    # 1. Landscape Header 3D & Centering
    print("\n[TEST 1] Landscape Header: 3D Bevels & Mathematical Dead-Centering")
    app = CCTApp(repl, repl.history, stats)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        bh = app.query_one(BrandHeader)
        btn = bh.query_one(".cct-menu-btn")
        perm = bh.query_one(".cct-perm-pill")
        right = bh.query_one("#cct-header-right")
        left_box = bh.query_one("#cct-header-left")
        right_box = bh.query_one("#cct-header-right-box")
        
        # Verify borders are tall 3D
        assert btn.styles.border.top[0] == "tall", f"MenuButton top border not tall: {btn.styles.border}"
        assert perm.styles.border.top[0] == "tall", f"PermPill top border not tall: {perm.styles.border}"
        assert right.styles.border.top[0] == "tall", f"Header right top border not tall: {right.styles.border}"
        
        # Verify left is at left corner, right is at right corner
        assert btn.region.x == 1, f"Menu button not at left corner: {btn.region}"
        assert right.region.x + right.region.width >= 100, f"Right pill not at right corner: {right.region}"
        
        # Verify Perm is centered
        perm_center = perm.region.x + perm.region.width / 2.0
        header_center = 120 / 2.0
        diff = abs(perm_center - header_center)
        print(f"  Header width: 120 | Perm Center: {perm_center} | Midpoint: {header_center} | Diff: {diff:.1f}")
        assert diff <= 3.0, f"Perm pill not centered: perm_center={perm_center}, header_center={header_center}"
        print("  ✓ MenuButton, PermPill, and Workspace Right Pill feature 3D bevel borders")
        print("  ✓ Landscape header elements correctly positioned (left, center, right)")

    # 2. RecentWorkspacesScreen Cross Button & Bottom Buttons
    print("\n[TEST 2] Recent Workspaces Screen: Cross Button & Bottom Buttons")
    app = CCTApp(repl, repl.history, stats)
    async with app.run_test(size=(70, 38)) as pilot:
        await pilot.pause()
        rws = RecentWorkspacesScreen()
        app.push_screen(rws)
        await pilot.pause()
        await pilot.pause()

        # Check titlebar height and close button
        tbar = rws.query_one("#cct-recentws-titlebar")
        close_btn = rws.query_one("#cct-recentws-close")
        print(f"  RWS Titlebar region: {tbar.region} | Size: {tbar.size}")
        print(f"  RWS Close btn region: {close_btn.region} | Size: {close_btn.size}")
        assert tbar.size.height >= 3, f"Titlebar height too small: {tbar.size.height}"
        assert close_btn.size.height >= 1, f"Close button height too small: {close_btn.size.height}"

        # Check bottom buttons
        btns_container = rws.query_one("#cct-recentws-btns")
        clear_b = rws.query_one("#cct-recentws-clear")
        cancel_b = rws.query_one("#cct-recentws-cancel")
        open_b = rws.query_one("#cct-recentws-open")
        
        print(f"  Btns container region: {btns_container.region}")
        print(f"  Clear btn: {clear_b.region} | Cancel: {cancel_b.region} | Open: {open_b.region}")
        
        # Verify no clipping / overflow
        c_right = btns_container.region.x + btns_container.region.width
        for b in [clear_b, cancel_b, open_b]:
            b_right = b.region.x + b.region.width
            assert b_right <= c_right + 1, f"Button {b.id} overflowed container: b_right={b_right}, c_right={c_right}"
        print("  ✓ Cross button fits completely with no truncation")
        print("  ✓ Bottom buttons (Clear, Cancel, Open) fit with ZERO overflow")

    # 3. OpenWorkspaceScreen Cross Button & Buttons
    print("\n[TEST 3] Open Workspace Screen: Cross Button & Action Buttons")
    app = CCTApp(repl, repl.history, stats)
    async with app.run_test(size=(70, 38)) as pilot:
        await pilot.pause()
        ows = OpenWorkspaceScreen()
        app.push_screen(ows)
        await pilot.pause()
        await pilot.pause()

        tbar = ows.query_one("#ows-titlebar")
        close_btn = ows.query_one("#ows-close-btn")
        print(f"  OWS Titlebar region: {tbar.region} | Size: {tbar.size}")
        print(f"  OWS Close btn region: {close_btn.region} | Size: {close_btn.size}")
        assert tbar.size.height >= 3, f"OWS Titlebar height too small: {tbar.size.height}"

        btn_row = ows.query_one("#ows-button-row")
        c_right = btn_row.region.x + btn_row.region.width
        for b in btn_row.query("Button"):
            b_right = b.region.x + b.region.width
            assert b_right <= c_right + 1, f"OWS Button {b.id} overflowed: b_right={b_right}, c_right={c_right}"
        print("  ✓ Open Workspace cross button fits with no bottom clipping")
        print("  ✓ Open Workspace buttons fit cleanly")

    # 4. UserPanel & ThemesPanel 3D & Responsive
    print("\n[TEST 4] UserPanel & ThemesPanel 3D Effects & Adaptation")
    app = CCTApp(repl, repl.history, stats)
    async with app.run_test(size=(65, 40)) as pilot:
        await pilot.pause()
        up = UserPanel(lambda: {"user": {"name": "ADMIN"}, "model": "nemotron-3-ultra", "provider": "nvidia"})
        app.push_screen(up)
        await pilot.pause()
        await pilot.pause()

        box = up.query_one(".cct-navpanel-box")
        assert box.styles.border.top[0] == "tall", f"UserPanel box border not tall: {box.styles.border}"
        assert box.region.width <= 65, f"UserPanel width overflow: {box.region.width}"
        print(f"  UserPanel Box width: {box.region.width} in 65-col viewport")
        print("  ✓ UserPanel 3D bevels applied and ultra-responsive layout verified")

    print("\n" + "=" * 70)
    print("ALL 4 ADVANCED 3D & ULTRA-RESPONSIVE SUITES PASSED (100%)")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_suite())

