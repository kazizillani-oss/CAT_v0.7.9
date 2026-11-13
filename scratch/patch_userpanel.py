import os

# 1. Patch UserPanel in calc_terminal/ui/nav_screens.py
path_nav = "calc_terminal/ui/nav_screens.py"
with open(path_nav, "r", encoding="utf-8") as f:
    txt_nav = f.read()

target_compose = """                    yield Static("AI Configuration", classes="user-section")
                    yield Static("", id="user-model", classes="user-detail")
                    yield Static("", id="user-provider", classes="user-detail")
                    with Horizontal(classes="user-prefs"):
                        yield Button("  Model / Provider  ", id="user-modelcfg", classes="cct-btn cct-btn-sm")
                        yield Button("  Permissions  ", id="user-perms", classes="cct-btn cct-btn-sm")"""

replacement_compose = """                    yield Static("AI Configuration", classes="user-section")
                    yield Static("", id="user-model", classes="user-detail")
                    yield Static("", id="user-provider", classes="user-detail")
                    with Horizontal(classes="user-prefs"):
                        yield Button("  Model / Provider  ", id="user-modelcfg", classes="cct-btn cct-btn-sm")
                        yield Button("  Permissions  ", id="user-perms", classes="cct-btn cct-btn-sm")
                    with Horizontal(classes="user-prefs"):
                        yield Button("  🔌 MCP Servers  ", id="user-mcp", classes="cct-btn cct-btn-sm")
                        yield Button("  📡 Backup Providers  ", id="user-backup", classes="cct-btn cct-btn-sm")"""

if target_compose in txt_nav:
    txt_nav = txt_nav.replace(target_compose, replacement_compose, 1)
    print("SUCCESS: Added MCP and Backup buttons to UserPanel compose")
else:
    print("WARNING: target_compose not found in nav_screens.py")

target_btn = """            elif event.button.id == "user-perms":
                self.dismiss("permissions")"""

replacement_btn = """            elif event.button.id == "user-perms":
                self.dismiss("permissions")
            elif event.button.id == "user-mcp":
                self.dismiss("mcp_servers")
            elif event.button.id == "user-backup":
                self.dismiss("backup_providers")"""

if target_btn in txt_nav:
    txt_nav = txt_nav.replace(target_btn, replacement_btn, 1)
    print("SUCCESS: Added button handlers in UserPanel")
else:
    print("WARNING: target_btn not found in nav_screens.py")

with open(path_nav, "w", encoding="utf-8") as f:
    f.write(txt_nav)

# 2. Patch _on_user_panel_action in calc_terminal/ui/app.py
path_app = "calc_terminal/ui/app.py"
with open(path_app, "r", encoding="utf-8") as f:
    txt_app = f.read()

target_app_action = """            elif result == "workspace":
                self.push_screen(OpenWorkspaceScreen(), self._on_open_folder_path)"""

replacement_app_action = """            elif result == "mcp_servers":
                from .mcp_panel import McpServersPanel
                self.push_screen(McpServersPanel())
            elif result == "backup_providers":
                from .backup_panel import BackupProvidersPanel
                self.push_screen(BackupProvidersPanel())
            elif result == "workspace":
                self.push_screen(OpenWorkspaceScreen(), self._on_open_folder_path)"""

if target_app_action in txt_app:
    txt_app = txt_app.replace(target_app_action, replacement_app_action, 1)
    print("SUCCESS: Added mcp and backup handlers in _on_user_panel_action")
else:
    print("WARNING: target_app_action not found in app.py")

with open(path_app, "w", encoding="utf-8") as f:
    f.write(txt_app)

print("Finished UserPanel patch")

