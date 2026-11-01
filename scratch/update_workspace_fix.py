import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("calc_terminal/ui/workspace.py", "r", encoding="utf-8") as f:
    ws_content = f.read()

# 1. Update open_file
old_open_file = """        def open_file(self, path):
            \"\"\"Open a file in the editor WITHOUT disturbing a running
            Web Preview (spec section 11: tabs and preview are
            independent). Only when the right pane is already in CODE
            mode do we bring it forward in stacked layouts.\"\"\"
            try:
                editor = self.editor
                if editor is None:
                    return False
                if self._mode is WorkspaceMode.CODE and not self._fullscreen:
                    self._showing = "files"
                    self._relayout()
                return editor.open_file(path)
            except Exception:
                return False"""

new_open_file = """        def open_file(self, path):
            \"\"\"Open a file in the editor WITHOUT disturbing a running
            Web Preview (spec section 11: tabs and preview are
            independent). Only when the right pane is already in CODE
            mode do we bring it forward in stacked layouts.\"\"\"
            try:
                editor = self.editor
                if editor is None:
                    return False
                if self.is_portrait():
                    self.explorer.display = False
                    self.explorer.width = 0
                    self.explorer.remove_class("is-portrait")
                    main = self.query_one("#cct-workspace-main")
                    main.display = True
                    self._showing = "files"
                    self._relayout()
                elif self._mode is WorkspaceMode.CODE and not self._fullscreen:
                    self._showing = "files"
                    self._relayout()
                return editor.open_file(path)
            except Exception:
                return False"""

assert old_open_file in ws_content, "old_open_file not found"
ws_content = ws_content.replace(old_open_file, new_open_file)

# 2. Update _sync_sidebar_toggle
old_sync_sidebar = """        def _sync_sidebar_toggle(self):
            try:
                collapsed = (not self.explorer.display or self.explorer.width == 0)
                nav = self.query_one("#cct-chat-nav", Horizontal)
                btn = self.query_one("#cct-chat-sidebar-toggle", Button)
                nav.display = collapsed
                if collapsed:
                    btn.label = _safe_glyph("▶ Explorer", "> Explorer")
                    btn.tooltip = "Open Sidebar (Ctrl+B)"
            except Exception:
                pass"""

new_sync_sidebar = """        def _sync_sidebar_toggle(self):
            try:
                collapsed = (not self.explorer.display or self.explorer.width == 0)
                nav = self.query_one("#cct-chat-nav", Horizontal)
                btn = self.query_one("#cct-chat-sidebar-toggle", Button)
                if self.is_portrait():
                    nav.display = False
                else:
                    nav.display = collapsed
                    if collapsed:
                        btn.label = _safe_glyph("▶ Explorer", "> Explorer")
                        btn.tooltip = "Open Sidebar (Ctrl+B)"
            except Exception:
                pass"""

assert old_sync_sidebar in ws_content, "old_sync_sidebar not found"
ws_content = ws_content.replace(old_sync_sidebar, new_sync_sidebar)

with open("calc_terminal/ui/workspace.py", "w", encoding="utf-8", newline="\r\n") as f:
    f.write(ws_content)

print("Updated workspace.py successfully")

