import sys
import os
import asyncio
import tempfile

ROOT = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.stdout.reconfigure(encoding="utf-8")

from calc_terminal.app import App
from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.workspace import WorkspaceShell
from calc_terminal.ui.sidebar import Explorer
from calc_terminal.ui.editor import EditorPane
from calc_terminal.ui.composer import StickyComposer
from calc_terminal.ui.footer import ComposerFooter
from calc_terminal.ui.header import BrandHeader, NavPanel
from calc_terminal.ui.palette import CommandPalette
from textual.widgets import Button, Static

async def run_all_tests():
    print("=" * 70)
    print("RUNNING ADVANCED RESPONSIVE & EDITOR SUITE V2")
    print("=" * 70)

    # --------------------------------------------------------------------------
    # Test 1: Aria mode badge rendering & composer footer in portrait
    # --------------------------------------------------------------------------
    print("\n--- Test 1: Aria Mode Chat Composer in Portrait (70x40) ---")
    repl = App()
    stats = {"solved": 0, "provider": "none", "model": "none"}
    app = CCTApp(repl, repl.history, stats)
    async with app.run_test(size=(70, 40)) as pilot:
        await pilot.pause()
        comp = app.query_one(StickyComposer)
        comp.set_ai_mode("build")
        await pilot.pause()

        footer = comp.query_one(ComposerFooter)
        badge = footer.query_one("#badge-notebook", Static)
        badge_text = badge.render().plain if hasattr(badge.render(), "plain") else str(badge.render())
        print("  Aria Badge Plain Text:", repr(badge_text))
        assert "Aria" in badge_text
        assert "🔨" in badge_text or "🛠" in badge_text

        # Verify buttons exist and are visible
        send_btn = comp.query_one("#btn-send", Button)
        perm_btn = comp.query_one("#btn-permissions", Button)
        attach_btn = comp.query_one("#btn-attach", Button)
        assert send_btn.display is True
        assert perm_btn.display is True
        assert attach_btn.display is True
        print("  [PASS] Aria mode active, badges and controls intact")

    # --------------------------------------------------------------------------
    # Test 2: Command Palette in portrait mode
    # --------------------------------------------------------------------------
    print("\n--- Test 2: Command Palette in Portrait (70x40) ---")
    repl = App()
    app = CCTApp(repl, repl.history, stats)
    async with app.run_test(size=(70, 40)) as pilot:
        await pilot.pause()
        comp = app.query_one(StickyComposer)
        palette = comp.query_one(CommandPalette)
        palette.open_for_query("/")
        await pilot.pause()

        assert palette.is_open() is True
        assert palette.styles.height.value <= 7
        rows = list(palette.query(".cct-cmd-row"))
        assert len(rows) > 0
        print(f"  [PASS] Palette opened in portrait with {len(rows)} commands, bounded height {palette.styles.height.value}")

        # Navigate with down arrow
        palette.move(1)
        await pilot.pause()
        assert palette._selected == 1
        print("  [PASS] Palette keyboard navigation functional")

    # --------------------------------------------------------------------------
    # Test 3: Portrait Header Explorer Button on Right
    # --------------------------------------------------------------------------
    print("\n--- Test 3: Portrait Header Explorer Button Placement ---")
    repl = App()
    app = CCTApp(repl, repl.history, stats)
    async with app.run_test(size=(70, 40)) as pilot:
        await pilot.pause()
        header = app.query_one(BrandHeader)
        assert header.has_class("is-portrait") is True
        exp_btn = header.query_one("#cct-header-explorer-btn", Button)
        assert exp_btn.display is True

        shell = app.query_one(WorkspaceShell)
        explorer = shell.query_one(Explorer)
        assert explorer.display is False

        # Click upper-right Explorer button
        await pilot.click("#cct-header-explorer-btn")
        await pilot.pause()
        assert explorer.display is True
        print("  [PASS] Upper-right explorer button toggled explorer full-screen in portrait")

    # --------------------------------------------------------------------------
    # Test 4: User Menu (NavPanel) Logical Grouping in Portrait
    # --------------------------------------------------------------------------
    print("\n--- Test 4: User Menu (NavPanel) Responsiveness in Portrait ---")
    repl = App()
    app = CCTApp(repl, repl.history, stats)
    async with app.run_test(size=(70, 40)) as pilot:
        await pilot.pause()
        panel = NavPanel()
        app.push_screen(panel)
        await pilot.pause()

        assert panel.is_portrait() is True
        items = [action_id for action_id, _, _ in panel._nav_cache]
        print("  NavPanel Portrait Items:", items)
        assert "__header" in items
        assert "open_folder" in items
        assert "recent_workspaces" in items
        assert "themes" in items
        assert "user" in items
        assert "signout" in items
        assert "quit" in items
        print("  [PASS] NavPanel logical grouping validated for portrait")

        # Dismiss via Escape
        await pilot.press("escape")
        await pilot.pause()
        assert not any(isinstance(s, NavPanel) for s in app.screen_stack)
        print("  [PASS] NavPanel dismissed with Escape")

    # --------------------------------------------------------------------------
    # Test 5: Landscape Mode Code Editor Controls (⿻ and Close)
    # --------------------------------------------------------------------------
    print("\n--- Test 5: Landscape Mode Code Editor Controls (⿻ & Close) ---")
    repl = App()
    app = CCTApp(repl, repl.history, stats)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        shell = app.query_one(WorkspaceShell)
        assert shell.is_portrait() is False

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tf:
            tf.write(b"# test landscape\nprint('cat landscape')\n")
            temp_path = tf.name

        shell.open_file(temp_path)
        await pilot.pause()

        editor = shell.query_one(EditorPane)
        split_btn = editor.query_one("#cct-tb-split", Static)
        close_btn = editor.query_one("#cct-tb-close", Static)
        back_btn = editor.query_one("#cct-tb-back", Static)

        # In landscape: split is visible, close is visible with text 'Close', back is hidden
        assert split_btn.display is True
        assert close_btn.display is True
        assert back_btn.display is False
        assert "Close" in str(close_btn.render())
        print("  [PASS] Landscape toolbar: split (⿻) visible, Close visible, Back hidden")

        # Test ⿻ toggle fullscreen
        assert shell.fullscreen is False
        await pilot.click("#cct-tb-split")
        await pilot.pause()
        assert shell.fullscreen is True
        print("  [PASS] Clicking ⿻ maximized editor to 100% viewport")

        # Test ⿻ restore split view
        await pilot.click("#cct-tb-split")
        await pilot.pause()
        assert shell.fullscreen is False
        print("  [PASS] Clicking ⿻ restored normal split view")

        # Test Close button
        await pilot.click("#cct-tb-close")
        await pilot.pause()
        assert len(editor._open_paths) == 0
        assert shell.chat_column.display is True
        print("  [PASS] Clicking Close closed tabs and restored CAT dashboard")

    # --------------------------------------------------------------------------
    # Test 6: Portrait File Selection direct transition from Explorer to Editor
    # --------------------------------------------------------------------------
    print("\n--- Test 6: Portrait File Selection Direct Transition ---")
    repl = App()
    app = CCTApp(repl, repl.history, stats)
    async with app.run_test(size=(75, 40)) as pilot:
        await pilot.pause()
        shell = app.query_one(WorkspaceShell)
        explorer = shell.query_one(Explorer)

        # Open explorer
        shell.toggle_sidebar()
        await pilot.pause()
        assert explorer.display is True
        assert shell.query_one("#cct-workspace-main").display is False

        # Open file
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tf:
            tf.write(b"print('file opened')\n")
            temp_file = tf.name

        shell.open_file(temp_file)
        await pilot.pause()

        # Explorer collapsed, main visible, editor full-screen
        assert explorer.display is False
        assert shell.query_one("#cct-workspace-main").display is True
        assert shell.right_pane.display is True
        assert shell.chat_column.display is False
        print("  [PASS] File opened: directly transitioned from Explorer to full-screen Editor")

        # Click Back to CAT
        await pilot.click("#cct-tb-back")
        await pilot.pause()
        assert shell.chat_column.display is True
        assert shell.right_pane.display is False
        print("  [PASS] ← Back to CAT returned to CAT Dashboard")

    print("\n" + "=" * 70)
    print("ALL 6/6 SUITE TESTS PASSED (100%)")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_all_tests())

