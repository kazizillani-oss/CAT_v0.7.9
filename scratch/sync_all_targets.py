import os
import shutil
from pathlib import Path

SOURCE_ROOT = Path(r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\calc_terminal")

TARGET_DIRS = [
    Path(r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\CAT_v0.7.4\calc_terminal"),
    Path(r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\build\lib\calc_terminal"),
    Path(r"C:\Users\ADMIN\AppData\Local\Programs\CAT\lib\calc_terminal"),
    Path(r"C:\Users\ADMIN\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\site-packages\calc_terminal"),
    Path(r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\.venv-cat-test\Lib\site-packages\calc_terminal"),
    Path(r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\.venv-package-test\Lib\site-packages\calc_terminal"),
    Path(r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\.venv-test\Lib\site-packages\calc_terminal"),
    Path(r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\.venv-test314\Lib\site-packages\calc_terminal"),
]

FILES_TO_SYNC = [
    # Universal Foundation Engines
    "capability_registry.py",
    "tool_engine.py",
    # Engineering Excellence & Maturity Subsystems (Parts 1-8)
    os.path.join("sdk", "__init__.py"),
    os.path.join("sdk", "developer_tools.py"),
    os.path.join("sdk", "examples", "sample_extension", "manifest.json"),
    os.path.join("sdk", "examples", "sample_extension", "extension.py"),
    os.path.join("sdk", "examples", "sample_skill", "skill.json"),
    os.path.join("sdk", "examples", "sample_command", "command.py"),
    os.path.join("core", "recovery_engine.py"),
    os.path.join("core", "recovery.py"),
    os.path.join("core", "checkpoint.py"),
    "context_engine.py",
    "observability.py",
    "offline.py",
    "update_manager.py",
    "multi_workspace.py",
    "doc_center.py",
    # Critical Systems
    "code_intel.py",
    "ai_eval.py",
    "automation_engine.py",
    "security_center.py",
    "deployment_center.py",
    # High-Priority Systems
    "db_studio.py",
    "ai_cost_manager.py",
    "workflow_builder.py",
    "github_studio.py",
    "cloud_workspace.py",
    "knowledge_center.py",
    "app_connectors.py",
    "agent_studio.py",
    # Core & Subsystem Extensions
    "dev_commands.py",
    "office_commands.py",
    "pkg_commands.py",
    "skill_commands.py",
    "mcp.py",
    "agent.py",
    "commands_data.py",
    "voice.py",
    "sound.py",
    "theme.py",
    "registry.py",
    "identity.py",
    "app.py",
    "fallback_cli.py",
    "fomoji_manager.py",
    "permissions.py",
    "aicore.py",
    "ai_modes.py",
    "parallel_runner.py",
    "platform_screens.py",
    "extensions.py",
    os.path.join("providers", "providers.json"),
    os.path.join("skills", "registry.py"),
    os.path.join("skills", "engine.py"),
    os.path.join("skills", "builtin", "manifest.json"),
    os.path.join("skills", "builtin", "rea-reverse-engineer", "SKILL.md"),
    os.path.join("skills", "builtin", "archify", "SKILL.md"),
    os.path.join("skills", "builtin", "remotion-best-practices", "SKILL.md"),
    os.path.join("skills", "builtin", "skillopt-sleep", "SKILL.md"),
    os.path.join("skills", "builtin", "page-mascot", "SKILL.md"),
    os.path.join("skills", "builtin", "frontend-design", "SKILL.md"),
    # UI Modules & Screens
    os.path.join("ui", "app.py"),
    os.path.join("ui", "header.py"),
    os.path.join("ui", "dashboard.py"),
    os.path.join("ui", "cat_greeting.py"),
    os.path.join("ui", "palette.py"),
    os.path.join("ui", "command_palette.py"),
    os.path.join("ui", "composer.py"),
    os.path.join("ui", "footer.py"),
    os.path.join("ui", "statusbar.py"),
    os.path.join("ui", "session_tabs.py"),
    os.path.join("ui", "whats_new_modal.py"),
    os.path.join("ui", "extensions_panel.py"),
    os.path.join("ui", "platform_screens.py"),
    os.path.join("ui", "resizers.py"),
    os.path.join("ui", "theme_css.py"),
    os.path.join("ui", "welcome_modal.py"),
    os.path.join("ui", "startup_loader.py"),
    os.path.join("ui", "sidebar.py"),
    os.path.join("ui", "workspace.py"),
    os.path.join("ui", "nav_screens.py"),
    os.path.join("ui", "memory_center.py"),
    os.path.join("ui", "thinking.py"),
    os.path.join("ui", "agent_menu.py"),
    os.path.join("ui", "chats_panel.py"),
    os.path.join("ui", "command_palette_modal.py"),
    os.path.join("ui", "context_menu.py"),
    os.path.join("ui", "conversation.py"),
    os.path.join("ui", "attachments.py"),
    os.path.join("ui", "permission_panel.py"),
    os.path.join("ui", "ollama_panel.py"),
    os.path.join("ui", "mode_colors_panel.py"),
    os.path.join("ui", "vision_panel.py"),
    os.path.join("ui", "live_activities.py"),
    os.path.join("ui", "widgets.py"),
    os.path.join("ui", "design_system.py"),
    os.path.join("ui", "events.py"),
    os.path.join("web", "cat_runtime.py"),
]

print("Starting synchronization across targets...")
total_copied = 0
for target in TARGET_DIRS:
    if not target.exists():
        print(f"Skipping non-existent target: {target}")
        continue
    count = 0
    for rel_path in FILES_TO_SYNC:
        src = SOURCE_ROOT / rel_path
        dst = target / rel_path
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            count += 1
            total_copied += 1
        else:
            print(f"  Source not found: {src}")
    print(f"Synchronized {count} files to: {target}")

print(f"\nTotal files synchronized successfully: {total_copied}")
