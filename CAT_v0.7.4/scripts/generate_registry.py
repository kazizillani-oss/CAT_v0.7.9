import os
import json
from calc_terminal.commands_data import COMMANDS, NATIVE_UI_COMMANDS
from calc_terminal.ai_modes import MODE_META, MODE_ORDER
from calc_terminal.permissions import MODES, MUTATING_KEYS, PERMISSION_DEFS
from calc_terminal.extensions import BUILTIN_EXTENSIONS
from calc_terminal.agent import TOOLS

# Tools
tools_list = []
for name, t_info in TOOLS.items():
    desc = t_info.get("desc", "")
    args = t_info.get("args", "")
    tools_list.append({
        "name": name,
        "category": "agent_tool",
        "source": "calc_terminal/agent.py",
        "description": desc,
        "args_signature": args,
        "permission_required": name in ["write_file", "delete_file", "edit_file", "rename_file", "run_terminal", "install_packages", "device_action"],
        "fatty_cat_status": "connected_via_runtime",
        "browser_compatible": True
    })

# Commands
commands_list = []
for cmd in COMMANDS:
    if isinstance(cmd, (list, tuple)):
        cmd_name = cmd[0]
        cmd_desc = cmd[1] if len(cmd) > 1 else ""
    elif isinstance(cmd, dict):
        cmd_name = cmd.get("name", "")
        cmd_desc = cmd.get("desc", "")
    else:
        cmd_name = str(cmd)
        cmd_desc = ""
    commands_list.append({
        "name": cmd_name,
        "category": "cli_command",
        "source": "calc_terminal/commands_data.py",
        "description": cmd_desc,
        "is_native_ui": cmd_name in NATIVE_UI_COMMANDS,
        "permission_required": False,
        "fatty_cat_status": "connected_via_dispatch",
        "browser_compatible": True
    })

# Modes
modes_list = []
for m_id in MODE_ORDER:
    m_info = MODE_META.get(m_id, {})
    modes_list.append({
        "id": m_id,
        "name": m_info.get("label", m_id.title()),
        "category": "ai_mode",
        "source": "calc_terminal/ai_modes.py",
        "color": m_info.get("color"),
        "accent": m_info.get("accent"),
        "icon": m_info.get("icon"),
        "fatty_cat_status": "connected",
        "browser_compatible": True
    })

# Permissions
perms_list = []
for item in PERMISSION_DEFS:
    if isinstance(item, (list, tuple)):
        k = item[0]
        label = item[1] if len(item) > 1 else k
        default_val = item[2] if len(item) > 2 else True
    elif isinstance(item, dict):
        k = item.get("key", "")
        label = item.get("label", k)
        default_val = item.get("default", True)
    else:
        k = str(item)
        label = k
        default_val = True

    perms_list.append({
        "key": k,
        "label": label,
        "category": "permissions",
        "source": "calc_terminal/permissions.py",
        "is_mutating": k in MUTATING_KEYS,
        "default": default_val,
        "fatty_cat_status": "connected",
        "browser_compatible": True
    })

# Extensions
exts_list = []
for ext_id, ext_info in BUILTIN_EXTENSIONS.items():
    exts_list.append({
        "id": ext_id,
        "name": ext_info.get("name", ext_id),
        "category": "extensions",
        "source": "calc_terminal/extensions.py",
        "description": ext_info.get("description", ""),
        "enabled_by_default": ext_info.get("enabled", False),
        "fatty_cat_status": "connected_via_api",
        "browser_compatible": True
    })

# Providers
with open("calc_terminal/providers/providers.json", "r", encoding="utf-8") as fp:
    prov_data = json.load(fp)

registry = {
    "version": "0.7.9.0",
    "total_capabilities": len(tools_list) + len(commands_list) + len(modes_list) + len(perms_list) + len(exts_list) + len(prov_data),
    "summary": {
        "tools_count": len(tools_list),
        "commands_count": len(commands_list),
        "modes_count": len(modes_list),
        "permissions_count": len(perms_list),
        "extensions_count": len(exts_list),
        "providers_count": len(prov_data)
    },
    "tools": tools_list,
    "commands": commands_list,
    "modes": modes_list,
    "permissions": perms_list,
    "extensions": exts_list,
    "providers_count": len(prov_data)
}

with open("cat_capability_registry.json", "w", encoding="utf-8") as fp:
    json.dump(registry, fp, indent=2)

print(f"SUCCESS: Generated cat_capability_registry.json with {registry['total_capabilities']} total capabilities.")
print(f"Tools: {len(tools_list)}, Commands: {len(commands_list)}, Modes: {len(modes_list)}, Perms: {len(perms_list)}, Exts: {len(exts_list)}, Providers: {len(prov_data)}")
