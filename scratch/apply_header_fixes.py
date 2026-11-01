import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9"

def update_file(rel_path, replacements):
    path = os.path.join(ROOT, rel_path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    modified = content
    for old, new in replacements:
        if old not in modified:
            print(f"FAILED to find target in {rel_path}:\n{old[:100]}...")
            return False
        modified = modified.replace(old, new, 1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(modified)
    print(f"Successfully updated {rel_path}")
    return True

# -------------------------------------------------------------
# 1. calc_terminal/ui/header.py
# -------------------------------------------------------------
header_replacements = [
    # NavPanel._get_filtered() portrait items - add mcp_servers and backup_providers
    (
        '''            if self.is_portrait():
                return (
                    ("__header", "⬡ CAT", "Coding Agent Terminal"),
                    ("__section_proj", "📁", "Project"),
                    ("open_folder", "📂", "Open Folder"),
                    ("recent_workspaces", "🕒", "Recent Workspaces"),
                    ("sep_proj", "", ""),
                    ("__section_app", "🎨", "Appearance"),
                    ("themes", "◑", "Themes"),
                    ("extensions", "▣", "Extensions"),
                    ("sep_app", "", ""),
                    ("__section_acc", "👤", "Account"),
                    ("user", "☺", "Users & Profile"),
                    ("signout", "⎋", "Sign Out"),
                    ("sep_acc", "", ""),
                    ("__section_sys", "⚙", "Application"),
                    ("quit", "✕", "Quit"),
                )''',
        '''            if self.is_portrait():
                return (
                    ("__header", "⬡ CAT", "Coding Agent Terminal"),
                    ("__section_proj", "📁", "Project"),
                    ("open_folder", "📂", "Open Folder"),
                    ("recent_workspaces", "🕒", "Recent Workspaces"),
                    ("sep_proj", "", ""),
                    ("__section_int", "🔌", "Integrations"),
                    ("mcp_servers", "🔌", "MCP Servers"),
                    ("backup_providers", "📡", "Backup Providers"),
                    ("sep_int", "", ""),
                    ("__section_app", "🎨", "Appearance"),
                    ("themes", "◑", "Themes"),
                    ("extensions", "▣", "Extensions"),
                    ("sep_app", "", ""),
                    ("__section_acc", "👤", "Account"),
                    ("user", "☺", "Users & Profile"),
                    ("signout", "⎋", "Sign Out"),
                    ("sep_acc", "", ""),
                    ("__section_sys", "⚙", "Application"),
                    ("quit", "✕", "Quit"),
                )'''
    ),
    # PermissionModeMenu box border - change tall to round $accent
    (
        '''        #cct-permmenu-box {
            width: auto;
            max-width: 48;
            height: auto;
            background: $surface;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $surface-dark;
            border-right: tall $surface-dark;
            padding: 1 1;
            opacity: 1; offset-y: 0;
        }''',
        '''        #cct-permmenu-box {
            width: auto;
            max-width: 48;
            height: auto;
            background: $surface;
            border: round $accent;
            padding: 1 1;
            opacity: 1; offset-y: 0;
        }'''
    ),
    # NavPanel on_row_picked - quit handler call _handle_quit
    (
        '''        def on_row_picked(self, action_id):
            if action_id == "quit":
                self.dismiss(None)
                try:
                    self.app.exit()
                except Exception:
                    pass
                return''',
        '''        def on_row_picked(self, action_id):
            if action_id == "quit":
                self.dismiss(None)
                if hasattr(self.app, "_handle_quit"):
                    self.app._handle_quit()
                else:
                    try:
                        self.app.exit()
                    except Exception:
                        pass
                return'''
    ),
    # BrandHeader._show_workspace_info - if no workspace open, open folder
    (
        '''        def _show_workspace_info(self):
            try:
                info_lines = [f"Path: {self._workspace_path or 'No workspace open'}"]''',
        '''        def _show_workspace_info(self):
            try:
                if not self._workspace_path or self._workspace_path == "No workspace open":
                    self.post_message(NavAction("open_folder"))
                    return
                info_lines = [f"Path: {self._workspace_path or 'No workspace open'}"]'''
    )
]

assert update_file("calc_terminal/ui/header.py", header_replacements)
print("Header.py update completed successfully.")
