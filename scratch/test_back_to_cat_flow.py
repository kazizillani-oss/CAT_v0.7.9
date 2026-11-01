import sys
import os
ROOT = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import asyncio
import tempfile
from calc_terminal.app import App
from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.workspace import WorkspaceShell
from calc_terminal.ui.sidebar import Explorer
from calc_terminal.ui.editor import EditorPane

async def test_full_back_to_cat_flow():
    repl = App()
    stats = {"solved": 0, "provider": "none", "model": "none"}
    app = CCTApp(repl, repl.history, stats)
    async with app.run_test(size=(75, 40)) as pilot:
        await pilot.pause()
        shell = app.query_one(WorkspaceShell)
        main_box = shell.query_one("#cct-workspace-main")
        explorer = shell.query_one(Explorer)
        
        # 1. Initial state
        assert shell.is_portrait() is True
        assert explorer.display is False
        assert main_box.display is True
        print("[1] Initial launch: main displayed, explorer collapsed")
        
        # 2. Toggle explorer
        shell.toggle_sidebar()
        await pilot.pause()
        assert explorer.display is True
        assert explorer.has_class("is-portrait")
        assert main_box.display is False
        print("[2] Explorer opened full-screen")
        
        # 3. Click Back to CAT in explorer
        await pilot.click("#cct-sidebar-back-btn")
        await pilot.pause()
        assert explorer.display is False
        assert main_box.display is True
        print("[3] Explorer Back to CAT clicked: returned to CAT dashboard")
        
        # 4. Open file in portrait mode
        editor = shell.query_one(EditorPane)
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tf:
            tf.write(b"print('hello cat')\n")
            temp_path = tf.name
            
        shell.open_file(temp_path)
        await pilot.pause()
        right_pane = shell.query_one("#cct-right-pane")
        chat_col = shell.query_one("#cct-chat-col")
        assert right_pane.display is True
        assert chat_col.display is False
        print("[4] File opened: full screen editor active")
        
        # 5. Click Back to CAT in editor
        tb_back = editor.query_one("#cct-tb-back")
        assert tb_back.display is True
        await pilot.click("#cct-tb-back")
        await pilot.pause()
        assert right_pane.display is False
        assert chat_col.display is True
        assert main_box.display is True
        print("[5] Editor Back to CAT clicked: returned to CAT dashboard and composer")

if __name__ == "__main__":
    asyncio.run(test_full_back_to_cat_flow())
