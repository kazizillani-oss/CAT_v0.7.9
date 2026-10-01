"""
CAT CLI — Subcommand Handlers for Agents, Missions, Storage, Backup, and Integrations.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from typing import List, Optional

from . import storage
from . import theme


# -----------------------------------------------------------------------------
# 1. Agents CLI
# -----------------------------------------------------------------------------

def agents_cli(argv: List[str]) -> int:
    """Handles `cat agents` and `cat agent ...` commands."""
    from .agents import get_agent_registry, AgentSpec

    reg = get_agent_registry()
    args = argv[1:] if argv and argv[0] in ("agents", "--agents", "agent", "--agent") else argv
    sub = args[0].lower() if args else "list"

    if sub in ("--help", "-h", "help"):
        print("Usage: cat agent [command] [options]")
        print("\nCommands:")
        print("  list (default)      List all built-in and custom AI agents")
        print("  search <query>      Search agents by name, tag, mode, or tool")
        print("  create              Create a new custom AI agent")
        print("  edit <id>           Edit an existing agent configuration")
        print("  delete <id>         Delete a custom agent")
        print("  enable <id>         Enable an agent")
        print("  disable <id>        Disable an agent")
        print("  status <id>         View real-time status and provider health for an agent")
        print("  run <id> [prompt]   Run a turn with the specified agent")
        print("  duplicate <id> <new_id> [new_name]  Duplicate an agent")
        print("  export <id> [file]  Export an agent definition to a .catagent file")
        print("  import <file>       Import an agent from a .cat/.catagent file")
        print("  memory <id> [--clear] View or clear an agent's memory")
        return 0

    if sub in ("list", "ls"):
        agents = reg.list(include_disabled=True)
        print("=" * 78)
        print("                          CAT AI AGENT REGISTRY")
        print("=" * 78)
        print(f"  {'#':<3} | {'ID':<16} | {'Name':<20} | {'Mode':<10} | {'Provider':<10} | {'Type':<8} | {'State'}")
        print("  " + "-" * 74)
        for i, a in enumerate(agents):
            state_str = "✓ Enabled" if a.enabled else "✗ Disabled"
            type_str = "Built-in" if a.builtin else "Custom"
            prov_str = a.provider or "default"
            print(f"  {i+1:<3} | {a.id:<16} | {a.icon} {a.name[:18]:<18} | {a.primary_mode:<10} | {prov_str:<10} | {type_str:<8} | {state_str}")
        print("=" * 78)
        print(f"Total Agents: {len(agents)} ({sum(1 for a in agents if a.enabled)} active)")
        print("Commands: cat agent search <q> | cat agent create | cat agent status <id> | cat agent run <id>")
        return 0

    if sub == "search":
        query = " ".join(args[1:]).strip() if len(args) > 1 else ""
        if not query:
            print("Usage: cat agent search <query>")
            return 1
        results = reg.search(query)
        print(f"\nSearch Results for '{query}' ({len(results)} matches):")
        print("-" * 65)
        for a in results:
            en = "Enabled" if a.enabled else "Disabled"
            print(f"  • {a.icon} {a.name} ({a.id}) [{a.primary_mode}] — {en}")
            if a.description:
                print(f"    {a.description[:90]}")
            if a.tools:
                print(f"    Tools: {', '.join(a.tools[:6])}")
        print("-" * 65)
        return 0

    if sub in ("status", "info"):
        if len(args) < 2:
            print("Usage: cat agent status <agent_id>")
            return 1
        aid = args[1]
        st = reg.get_agent_status(aid)
        if "error" in st:
            print(f"Error: {st['error']}", file=sys.stderr)
            return 1
        ag = reg.get(aid)
        print("=" * 60)
        print(f"  AGENT STATUS: {ag.icon} {ag.name} ({ag.id})")
        print("=" * 60)
        print(f"  State           : {st.get('status')}")
        print(f"  Primary Mode    : {st.get('primary_mode')}")
        print(f"  Enabled         : {'Yes' if st.get('enabled') else 'No'}")
        pinfo = st.get("provider_info", {})
        print(f"  Primary Provider: {pinfo.get('provider')} (model: {pinfo.get('model') or 'default'})")
        print(f"  Health Status   : {pinfo.get('status_label', 'Healthy')}")
        if pinfo.get("latency_ms"):
            print(f"  Provider Latency: {pinfo.get('latency_ms')}ms")
        print(f"  Backup Failover : {pinfo.get('backup_pool_count', 0)} candidate(s) ready")
        print(f"  Memory Scope    : {ag.memory_scope}")
        print(f"  Declared Tools  : {', '.join(ag.tools) if ag.tools else 'Inherited from mode'}")
        print("=" * 60)
        return 0

    if sub == "enable":
        if len(args) < 2:
            print("Usage: cat agent enable <agent_id>")
            return 1
        aid = args[1]
        if reg.enable(aid):
            print(f"✓ Agent '{aid}' enabled.")
            return 0
        print(f"Agent '{aid}' not found.", file=sys.stderr)
        return 1

    if sub == "disable":
        if len(args) < 2:
            print("Usage: cat agent disable <agent_id>")
            return 1
        aid = args[1]
        if reg.disable(aid):
            print(f"✓ Agent '{aid}' disabled.")
            return 0
        print(f"Agent '{aid}' not found.", file=sys.stderr)
        return 1

    if sub in ("delete", "rm"):
        if len(args) < 2:
            print("Usage: cat agent delete <agent_id>")
            return 1
        aid = args[1]
        ag = reg.get(aid)
        if not ag:
            print(f"Agent '{aid}' not found.", file=sys.stderr)
            return 1
        if ag.builtin:
            print(f"Built-in agent '{aid}' cannot be deleted. Disabling it instead.")
            reg.disable(aid)
            return 0
        if reg.unregister(aid):
            print(f"✓ Custom agent '{aid}' deleted.")
            return 0
        print(f"Failed to delete '{aid}'.", file=sys.stderr)
        return 1

    if sub == "create":
        # Supports flags or interactive prompt
        p = argparse.ArgumentParser(prog="cat agent create")
        p.add_argument("name", nargs="?", default="")
        p.add_argument("--id", default="")
        p.add_argument("--desc", default="")
        p.add_argument("--mode", default="build")
        p.add_argument("--provider", default="default")
        p.add_argument("--model", default="")
        p.add_argument("--instructions", default="")
        p.add_argument("--tools", default="")
        p.add_argument("--memory", default="project")
        parsed, _ = p.parse_known_args(args[1:])

        name = parsed.name
        if not name:
            if sys.stdin.isatty():
                try:
                    name = input("Agent Name: ").strip()
                except (EOFError, KeyboardInterrupt):
                    return 1
            else:
                print("Usage: cat agent create <name> [--id ID] [--mode MODE] [--provider PROV]")
                return 1

        if not name:
            print("Error: Agent name cannot be empty.", file=sys.stderr)
            return 1

        aid = parsed.id or re.sub(r"[^\w\-]", "-", name.lower()).strip("-")
        tools_list = [t.strip() for t in parsed.tools.split(",") if t.strip()] if parsed.tools else []

        spec = AgentSpec(
            id=aid,
            name=name,
            description=parsed.desc or f"Custom agent {name}",
            primary_mode=parsed.mode,
            provider=parsed.provider,
            model=parsed.model,
            system_instructions=parsed.instructions,
            tools=tools_list,
            memory_scope=parsed.memory,
            builtin=False,
            category="custom",
        )
        reg.register(spec, persist=True)
        print(f"✓ Created custom agent '{spec.name}' (ID: {spec.id})")
        print(f"  Configuration saved to: {storage.get_subpath('agents', f'{spec.id}.cat')}")
        return 0

    if sub == "duplicate":
        if len(args) < 3:
            print("Usage: cat agent duplicate <source_id> <new_id> [new_name]")
            return 1
        src_id, new_id = args[1], args[2]
        new_name = args[3] if len(args) > 3 else f"{new_id.replace('-', ' ').title()}"
        try:
            ag = reg.duplicate(src_id, new_id, new_name)
            print(f"✓ Duplicated agent '{src_id}' to '{ag.name}' ({ag.id})")
            return 0
        except Exception as e:
            print(f"Error duplicating agent: {e}", file=sys.stderr)
            return 1

    if sub == "export":
        if len(args) < 2:
            print("Usage: cat agent export <agent_id> [output_file]")
            return 1
        aid = args[1]
        out_f = args[2] if len(args) > 2 else None
        try:
            exported_p = reg.export_agent(aid, out_f)
            print(f"✓ Exported agent '{aid}' to: {exported_p}")
            return 0
        except Exception as e:
            print(f"Export error: {e}", file=sys.stderr)
            return 1

    if sub in ("import", "load"):
        if len(args) < 2:
            print("Usage: cat agent import <filepath>")
            return 1
        in_f = args[1]
        try:
            ag = reg.import_agent(in_f)
            print(f"✓ Imported agent '{ag.name}' ({ag.id})")
            return 0
        except Exception as e:
            print(f"Import error: {e}", file=sys.stderr)
            return 1

    if sub == "run":
        if len(args) < 2:
            print("Usage: cat agent run <agent_id> [prompt]")
            return 1
        aid = args[1]
        ag = reg.get(aid)
        if not ag:
            print(f"Error: Agent '{aid}' not found.", file=sys.stderr)
            return 1
        prompt = " ".join(args[2:]).strip() if len(args) > 2 else ""
        if not prompt:
            if sys.stdin.isatty():
                try:
                    prompt = input(f"Prompt for {ag.name}: ").strip()
                except (EOFError, KeyboardInterrupt):
                    return 1
            else:
                prompt = "Hello"

        from . import aicore
        from . import ai_modes
        ai_modes.set_active_agent(aid)
        print(f"Running turn with {ag.icon} {ag.name} [{ag.primary_mode}]...")
        sys_prompt = ag.system_instructions or f"You are {ag.name}."
        res = aicore.query_ai(prompt=prompt, system_prompt=sys_prompt, mode=ag.primary_mode)
        txt = res.get("text", "")
        if txt:
            print(f"\n{txt}\n")
            return 0
        elif res.get("error"):
            print(f"Agent turn error: {res['error']}", file=sys.stderr)
            return 1
        return 0

    if sub == "memory":
        if len(args) < 2:
            print("Usage: cat agent memory <agent_id> [--clear]")
            return 1
        aid = args[1]
        if "--clear" in args:
            cnt = reg.clear_agent_memory(aid)
            print(f"✓ Cleared {cnt} memory records for agent '{aid}'.")
            return 0
        mems = reg.get_agent_memory(aid)
        print(f"Memory for agent '{aid}' ({len(mems)} records):")
        for m in mems:
            print(f"  - [{m.get('scope', 'project')}] {m.get('content', '')}")
        return 0

    print(f"Unknown agent command: {sub}. Run `cat agent --help` for available commands.", file=sys.stderr)
    return 1


# -----------------------------------------------------------------------------
# 2. Missions CLI
# -----------------------------------------------------------------------------

def missions_cli(argv: List[str]) -> int:
    """Handles `cat missions` and `cat mission ...` commands."""
    from .missions import get_mission_manager

    mm = get_mission_manager()
    args = argv[1:] if argv and argv[0] in ("missions", "--missions", "mission", "--mission") else argv
    sub = args[0].lower() if args else "list"

    if sub in ("--help", "-h", "help"):
        print("Usage: cat mission [command] [options]")
        print("\nCommands:")
        print("  list (default)      List all active and completed missions")
        print("  create <title>      Create a new mission with an objective")
        print("  open <id>           View mission dashboard, tasks, checkpoints, and plan")
        print("  pause <id>          Pause a running mission and create a checkpoint")
        print("  resume <id>         Resume a paused mission from its last checkpoint")
        print("  complete <id>       Mark a mission completed with final result")
        print("  delete <id>         Delete a mission and its checkpoints")
        print("  export <id> [file]  Export mission to a portable .cat file")
        print("  import <file>       Import a mission from a .cat file")
        return 0

    if sub in ("list", "ls"):
        missions = mm.list()
        print("=" * 78)
        print("                          CAT MISSION SYSTEM")
        print("=" * 78)
        print(f"  {'#':<3} | {'ID':<26} | {'Title':<22} | {'Status':<10} | {'Tasks':<6} | {'Checkpoints'}")
        print("  " + "-" * 74)
        for i, m in enumerate(missions):
            glyph = "●" if m.status == "running" else "✓" if m.status == "completed" else "⏳" if m.status == "paused" else "○"
            status_str = f"{glyph} {m.status}"
            tasks_str = f"{sum(1 for t in m.tasks if t.status == 'completed')}/{len(m.tasks)}"
            cp_str = f"{len(m.checkpoints)} cp"
            print(f"  {i+1:<3} | {m.id:<26} | {m.title[:20]:<22} | {status_str:<10} | {tasks_str:<6} | {cp_str}")
        print("=" * 78)
        print(f"Total Missions: {len(missions)}")
        print("Commands: cat mission create <title> | cat mission open <id> | cat mission pause <id>")
        return 0

    if sub == "create":
        title = args[1] if len(args) > 1 else ""
        if not title:
            if sys.stdin.isatty():
                try:
                    title = input("Mission Title: ").strip()
                except (EOFError, KeyboardInterrupt):
                    return 1
            else:
                print("Usage: cat mission create <title> [--objective OBJ]")
                return 1

        obj = " ".join(args[2:]).strip() if len(args) > 2 else title
        m = mm.create(title=title, objective=obj)
        print(f"✓ Created mission '{m.title}' (ID: {m.id})")
        print(f"  Saved to: {storage.get_subpath('missions', f'{m.id}.cat')}")
        return 0

    if sub in ("open", "show", "view", "inspect"):
        if len(args) < 2:
            print("Usage: cat mission open <mission_id>")
            return 1
        mid = args[1]
        m = mm.get(mid)
        if not m:
            print(f"Mission '{mid}' not found.", file=sys.stderr)
            return 1
        print("=" * 74)
        print(f"  MISSION: {m.title}")
        print(f"  ID     : {m.id}")
        print(f"  Status : {m.status.upper()}")
        print(f"  Created: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(m.created_at))}")
        print("-" * 74)
        print(f"  Objective:\n    {m.objective}")
        if m.agents:
            print(f"\n  Assigned Agents: {', '.join(m.agents)}")
        if m.tasks:
            print("\n  Tasks:")
            for t in m.tasks:
                t_glyph = "✓" if t.status == "completed" else "●" if t.status == "running" else "○"
                print(f"    {t_glyph} [{t.id}] {t.title} ({t.status})")
        if m.checkpoints:
            print("\n  Checkpoints:")
            for cp in m.checkpoints:
                t_str = time.strftime('%H:%M:%S', time.localtime(cp.timestamp))
                print(f"    • [{t_str}] {cp.name} (completed: {cp.tasks_completed})")
        if m.final_result:
            print(f"\n  Final Result:\n    {m.final_result}")
        print("=" * 74)
        return 0

    if sub == "pause":
        if len(args) < 2:
            print("Usage: cat mission pause <mission_id>")
            return 1
        mid = args[1]
        if mm.pause(mid):
            print(f"✓ Mission '{mid}' paused (checkpoint created).")
            return 0
        print(f"Mission '{mid}' not found.", file=sys.stderr)
        return 1

    if sub == "resume":
        if len(args) < 2:
            print("Usage: cat mission resume <mission_id>")
            return 1
        mid = args[1]
        if mm.resume(mid):
            print(f"✓ Mission '{mid}' resumed from checkpoint.")
            return 0
        print(f"Mission '{mid}' not found.", file=sys.stderr)
        return 1

    if sub == "complete":
        if len(args) < 2:
            print("Usage: cat mission complete <mission_id> [result]")
            return 1
        mid = args[1]
        res = " ".join(args[2:]).strip() if len(args) > 2 else "Mission completed."
        if mm.complete(mid, res):
            print(f"✓ Mission '{mid}' marked completed.")
            return 0
        print(f"Mission '{mid}' not found.", file=sys.stderr)
        return 1

    if sub in ("delete", "rm"):
        if len(args) < 2:
            print("Usage: cat mission delete <mission_id>")
            return 1
        mid = args[1]
        if mm.delete(mid):
            print(f"✓ Mission '{mid}' deleted.")
            return 0
        print(f"Mission '{mid}' not found.", file=sys.stderr)
        return 1

    if sub == "export":
        if len(args) < 2:
            print("Usage: cat mission export <mission_id> [file]")
            return 1
        mid = args[1]
        out_f = args[2] if len(args) > 2 else None
        try:
            exported_p = mm.export_mission(mid, out_f)
            print(f"✓ Exported mission '{mid}' to: {exported_p}")
            return 0
        except Exception as e:
            print(f"Export error: {e}", file=sys.stderr)
            return 1

    if sub in ("import", "load"):
        if len(args) < 2:
            print("Usage: cat mission import <file>")
            return 1
        in_f = args[1]
        try:
            m = mm.import_mission(in_f)
            print(f"✓ Imported mission '{m.title}' ({m.id})")
            return 0
        except Exception as e:
            print(f"Import error: {e}", file=sys.stderr)
            return 1

    print(f"Unknown mission command: {sub}. Run `cat mission --help`.", file=sys.stderr)
    return 1


# -----------------------------------------------------------------------------
# 3. Storage CLI
# -----------------------------------------------------------------------------

def storage_cli(argv: List[str]) -> int:
    """Handles `cat storage` commands."""
    args = argv[1:] if argv and argv[0] in ("storage", "--storage") else argv
    sub = args[0].lower() if args else "status"

    if sub in ("--help", "-h", "help"):
        print("Usage: cat storage [command]")
        print("\nCommands:")
        print("  status (default)  Display storage usage breakdown and metrics")
        print("  path              Print canonical user data directory path")
        print("  open              Open storage folder in system file manager")
        print("  clean             Safely clean temporary cache files")
        return 0

    if sub in ("path", "dir", "location"):
        print(storage.get_storage_dir())
        return 0

    if sub in ("status", "info"):
        st = storage.get_storage_status()
        print("=" * 70)
        print("                       CAT USER STORAGE REPORT")
        print("=" * 70)
        print(f"  Location : {st['base_path']}")
        print(f"  Total    : {st['readable_total']} ({st['total_files']} files)")
        print("-" * 70)
        print(f"  {'Subsystem':<16} | {'Files':<8} | {'Size':<12} | {'Directory Path'}")
        print("  " + "-" * 66)
        for name, info in st["breakdown"].items():
            print(f"  {name.title():<16} | {info['count']:<8} | {info['readable_size']:<12} | {info['path']}")
        print("=" * 70)
        print("Commands: cat storage path | cat storage open | cat backup | cat storage clean")
        return 0

    if sub == "open":
        p = storage.get_storage_dir()
        print(f"Opening {p} ...")
        if sys.platform == "win32":
            os.startfile(p)
        elif sys.platform == "darwin":
            subprocess.run(["open", p])
        else:
            subprocess.run(["xdg-open", p])
        return 0

    if sub in ("clean", "clear-cache", "cleanup"):
        rem = storage.clear_cache()
        print(f"✓ Removed {rem} temporary cache file(s). User data, agents, and chats were preserved.")
        return 0

    print(f"Unknown storage command: {sub}. Run `cat storage --help`.", file=sys.stderr)
    return 1


# -----------------------------------------------------------------------------
# 4. Backup & Restore CLI
# -----------------------------------------------------------------------------

def backup_cli(argv: List[str]) -> int:
    """Handles `cat backup` and `cat restore`."""
    is_restore = argv and argv[0] in ("restore", "--restore")
    args = argv[1:]

    if is_restore:
        if not args or args[0] in ("--help", "-h"):
            print("Usage: cat restore <backup_file.zip> [--overwrite]")
            return 0
        bpath = args[0]
        overwrite = "--overwrite" in args or "-f" in args
        ok, msg = storage.restore_backup(bpath, overwrite=overwrite)
        if ok:
            print(f"✓ {msg}")
            return 0
        else:
            print(f"Restore failed: {msg}", file=sys.stderr)
            return 1

    # Backup command
    out_target = args[0] if args and not args[0].startswith("-") else None
    print("Creating safe CAT local backup archive...")
    try:
        archive_path = storage.create_backup(out_target)
        size_str = storage.format_bytes(os.path.getsize(archive_path))
        print(f"✓ Backup created: {archive_path} ({size_str})")
        print("  Secrets and cache files were automatically excluded.")
        return 0
    except Exception as e:
        print(f"Backup failed: {e}", file=sys.stderr)
        return 1


# -----------------------------------------------------------------------------
# 5. Integrations CLI
# -----------------------------------------------------------------------------

def integrations_cli(argv: List[str]) -> int:
    """Handles `cat integrations` and `cat integration ...`."""
    from .integrations import get_integration_registry

    reg = get_integration_registry()
    args = argv[1:] if argv and argv[0] in ("integrations", "--integrations", "integration", "--integration") else argv
    sub = args[0].lower() if args else "list"

    if sub in ("--help", "-h", "help"):
        print("Usage: cat integration [command]")
        print("\nCommands:")
        print("  list (default)      View status of all AI, development, research, and tool integrations")
        print("  status <id>         Inspect detailed status and capabilities for an integration")
        print("  connect <id>        Connect or test connectivity for an integration")
        print("  disconnect <id>     Disconnect an integration")
        print("  refresh             Re-probe live connection status for all integrations")
        return 0

    if sub in ("refresh",):
        print("Probing connection status across integrations...")
        reg.refresh_statuses()
        print("✓ Refreshed.")

    if sub in ("list", "ls", "refresh"):
        items = reg.list()
        categories = {
            "ai_providers": "AI Providers",
            "development": "Development Platforms",
            "research": "Research & Notebooks",
            "tools": "Developer Tools & MCP",
        }

        print("=" * 74)
        print("                      CAT INTEGRATION CENTER")
        print("=" * 74)
        for cat_key, cat_title in categories.items():
            cat_items = [i for i in items if i.category == cat_key]
            if not cat_items:
                continue
            print(f"\n  [{cat_title.upper()}]")
            for item in cat_items:
                badge = "✓ Connected" if item.status == "Connected" else "○ Disconnected" if item.status == "Disconnected" else "⚠ Needs Auth" if item.status == "Needs Authentication" else "✗ Unavailable"
                print(f"    {item.icon} {item.name:<18} | {badge:<20} | {item.details[:30]}")

        print("\n" + "=" * 74)
        print("Commands: cat integration connect <name> | cat integration status <name>")
        return 0

    if sub in ("status", "info"):
        if len(args) < 2:
            print("Usage: cat integration status <id>")
            return 1
        iid = args[1].lower()
        st = reg.status(iid)
        if "error" in st:
            print(f"Error: {st['error']}", file=sys.stderr)
            return 1
        print("=" * 60)
        print(f"  INTEGRATION: {st.get('name')} ({st.get('id')})")
        print("=" * 60)
        print(f"  Category    : {st.get('category')}")
        print(f"  Status      : {st.get('status')}")
        print(f"  Details     : {st.get('details')}")
        print(f"  Auth Type   : {st.get('auth_type')}")
        if st.get("capabilities"):
            print(f"  Capabilities: {', '.join(st['capabilities'])}")
        print("=" * 60)
        return 0

    if sub == "connect":
        if len(args) < 2:
            print("Usage: cat integration connect <id>")
            return 1
        iid = args[1].lower()
        ok, msg = reg.connect(iid)
        if ok:
            print(f"✓ {msg}")
            return 0
        else:
            print(f"✗ {msg}", file=sys.stderr)
            return 1

    if sub == "disconnect":
        if len(args) < 2:
            print("Usage: cat integration disconnect <id>")
            return 1
        iid = args[1].lower()
        if reg.disconnect(iid):
            print(f"✓ Disconnected '{iid}'.")
            return 0
        print(f"Integration '{iid}' not found.", file=sys.stderr)
        return 1

    print(f"Unknown integration command: {sub}. Run `cat integration --help`.", file=sys.stderr)
    return 1


# -----------------------------------------------------------------------------
# 6. Generic `.cat` Import / Export CLI
# -----------------------------------------------------------------------------

def cat_file_cli(argv: List[str]) -> int:
    """Handles top-level `cat import <file.cat>` and `cat export <type> <id>`."""
    cmd = argv[0].lower().lstrip("-")
    args = argv[1:]

    if cmd == "import":
        if not args or args[0] in ("--help", "-h"):
            print("Usage: cat import <file.cat>")
            return 0
        fpath = args[0]
        valid, env, err, warnings = storage.read_cat_file(fpath)
        if not valid or not env:
            print(f"✗ Invalid CAT file: {err}", file=sys.stderr)
            return 1

        print("=" * 60)
        print("  CAT FILE VALIDATOR & IMPORTER")
        print("=" * 60)
        print(f"  File     : {os.path.basename(fpath)}")
        print(f"  Type     : {env.get('type')}")
        print(f"  ID       : {env.get('id')}")
        print(f"  Version  : {env.get('version')}")
        if warnings:
            print("  Security Audits:")
            for w in warnings:
                print(f"    ⚠ {w}")
        print("=" * 60)

        obj_type = env.get("type")
        if obj_type == "agent":
            from .agents import get_agent_registry
            ag = get_agent_registry().import_agent(env)
            print(f"✓ Successfully imported Agent: {ag.name} ({ag.id})")
            return 0
        elif obj_type == "mission":
            from .missions import get_mission_manager
            m = get_mission_manager().import_mission(env)
            print(f"✓ Successfully imported Mission: {m.title} ({m.id})")
            return 0
        elif obj_type == "model":
            from .lab import get_model_registry, ModelSpec
            data = env.get("payload", {}).get("model", env.get("payload", {}))
            spec = ModelSpec.from_dict(data)
            get_model_registry().register(spec, persist=True)
            print(f"✓ Successfully imported Model: {spec.name} ({spec.id})")
            return 0
        elif obj_type == "benchmark":
            from .lab import get_benchmark_registry, BenchmarkSpec
            data = env.get("payload", {}).get("benchmark", env.get("payload", {}))
            spec = BenchmarkSpec.from_dict(data)
            get_benchmark_registry().register(spec, persist=True)
            print(f"✓ Successfully imported Benchmark: {spec.name} ({spec.id})")
            return 0
        elif obj_type == "dataset":
            from .lab import get_dataset_registry, DatasetSpec
            data = env.get("payload", {}).get("dataset", env.get("payload", {}))
            spec = DatasetSpec.from_dict(data)
            get_dataset_registry().add(spec, persist=True)
            print(f"✓ Successfully imported Dataset: {spec.name} ({spec.id})")
            return 0
        else:
            print(f"Import for type '{obj_type}' completed.")
            return 0

    if cmd == "export":
        if len(args) < 2 or args[0] in ("--help", "-h"):
            print("Usage: cat export <agent|mission|model|benchmark|dataset> <id> [output_file.cat]")
            return 0
        obj_type, obj_id = args[0].lower(), args[1]
        out_f = args[2] if len(args) > 2 else None

        if obj_type in ("agent", "bot"):
            from .agents import get_agent_registry
            p = get_agent_registry().export_agent(obj_id, out_f)
            print(f"✓ Exported agent to: {p}")
            return 0
        elif obj_type in ("mission", "task"):
            from .missions import get_mission_manager
            p = get_mission_manager().export_mission(obj_id, out_f)
            print(f"✓ Exported mission to: {p}")
            return 0
        elif obj_type in ("model",):
            from .lab import get_model_registry
            m = get_model_registry().get(obj_id)
            if not m:
                print(f"Model '{obj_id}' not found.", file=sys.stderr)
                return 1
            dest = out_f or f"{obj_id}.cat"
            storage.write_cat_file(dest, obj_type="model", payload={"model": m.to_dict()})
            print(f"✓ Exported model to: {dest}")
            return 0
        elif obj_type in ("benchmark",):
            from .lab import get_benchmark_registry
            b = get_benchmark_registry().get(obj_id)
            if not b:
                print(f"Benchmark '{obj_id}' not found.", file=sys.stderr)
                return 1
            dest = out_f or f"{obj_id}.cat"
            storage.write_cat_file(dest, obj_type="benchmark", payload={"benchmark": b.to_dict()})
            print(f"✓ Exported benchmark to: {dest}")
            return 0
        elif obj_type in ("dataset",):
            from .lab import get_dataset_registry
            d = get_dataset_registry().get(obj_id)
            if not d:
                print(f"Dataset '{obj_id}' not found.", file=sys.stderr)
                return 1
            dest = out_f or f"{obj_id}.cat"
            storage.write_cat_file(dest, obj_type="dataset", payload={"dataset": d.to_dict()})
            print(f"✓ Exported dataset to: {dest}")
            return 0
        else:
            print(f"Unsupported export type '{obj_type}'. Supported: agent, mission, model, benchmark, dataset", file=sys.stderr)
            return 1

    return 1


# -----------------------------------------------------------------------------
# 7. Hardware Profiler CLI
# -----------------------------------------------------------------------------

def hardware_cli(argv: List[str]) -> int:
    """Handles `cat hardware [status|gpu|cpu|memory]`."""
    from .lab import (
        get_hardware_status_text,
        get_gpu_status_text,
        get_cpu_status_text,
        get_memory_status_text,
    )
    args = argv[1:] if argv and argv[0] in ("hardware", "--hardware") else argv
    sub = args[0].lower() if args else "status"

    if sub in ("--help", "-h", "help"):
        print("Usage: cat hardware [status|gpu|cpu|memory]")
        print("\nCommands:")
        print("  status (default)  Complete system hardware & ML runtime profile")
        print("  gpu               Detailed GPU, VRAM, and accelerator backend status")
        print("  cpu               Processor architecture, physical & logical cores")
        print("  memory            RAM capacity, utilization, and GPU VRAM pressure")
        return 0

    if sub in ("gpu", "--gpu", "-g"):
        print(get_gpu_status_text())
        return 0
    elif sub in ("cpu", "--cpu", "-c"):
        print(get_cpu_status_text())
        return 0
    elif sub in ("memory", "ram", "--memory", "-m"):
        print(get_memory_status_text())
        return 0
    else:
        print(get_hardware_status_text())
        return 0


# -----------------------------------------------------------------------------
# 8. CAT Lab Hub CLI
# -----------------------------------------------------------------------------

def lab_cli(argv: List[str]) -> int:
    """Handles top-level `cat lab` dashboard view."""
    from .lab import (
        get_model_registry,
        get_benchmark_registry,
        get_dataset_registry,
        get_experiment_tracker,
        get_hardware_profile,
    )
    m_reg = get_model_registry()
    b_reg = get_benchmark_registry()
    d_reg = get_dataset_registry()
    e_tracker = get_experiment_tracker()
    hw = get_hardware_profile()

    print("=" * 74)
    print("                    CAT LAB — AI EXPERIMENTATION STUDIO")
    print("=" * 74)
    print(f"  Primary Device : {hw['primary_device']} | OS: {hw['os_name']}")
    print(f"  PyTorch        : {hw['pytorch']['version']} ({hw['pytorch']['details']})")
    print(f"  CUDA Runtime   : {hw['cuda']['version']}")
    print("-" * 74)
    print(f"  [BENCHMARK STUDIO]  {len(b_reg.list())} benchmarks configured")
    for b in b_reg.list()[:3]:
        print(f"    • {b.name:<32} ({len(b.tasks)} tasks, type: {b.benchmark_type})")
    print(f"  [MODEL LAB]         {len(m_reg.list())} models registered")
    for m in m_reg.list()[:3]:
        print(f"    • {m.name:<32} ({m.framework}, {m.precision}, status: {m.status})")
    print(f"  [DATASETS]          {len(d_reg.list())} datasets profiled")
    for d in d_reg.list()[:3]:
        print(f"    • {d.name:<32} ({d.num_samples} samples, {d.format})")
    print(f"  [EXPERIMENTS]       {len(e_tracker.list())} experiments tracked")
    print("=" * 74)
    print("Commands:")
    print("  cat benchmark list | cat benchmark run <id> | cat benchmark compare")
    print("  cat model list     | cat model add          | cat model test <id>")
    print("  cat experiment list| cat dataset list       | cat hardware")
    return 0


# -----------------------------------------------------------------------------
# 9. Benchmark Studio CLI
# -----------------------------------------------------------------------------

def benchmark_cli(argv: List[str]) -> int:
    """Handles `cat benchmark [list|create|run|stop|compare|export]`."""
    from .lab import (
        get_benchmark_registry,
        get_model_registry,
        BenchmarkRunner,
        BenchmarkSpec,
        BenchmarkTask,
        render_benchmark_report_card,
        render_multi_model_comparison,
    )
    b_reg = get_benchmark_registry()
    m_reg = get_model_registry()

    args = argv[1:] if argv and argv[0] in ("benchmark", "benchmarks", "--benchmark") else argv
    sub = args[0].lower() if args else "list"

    if sub in ("--help", "-h", "help"):
        print("Usage: cat benchmark [command]")
        print("\nCommands:")
        print("  list (default)              List available benchmarks")
        print("  create <id> <name>          Create a custom benchmark")
        print("  run <id> [--model <model>]  Run a benchmark against a model")
        print("  stop                        Stop the currently executing benchmark")
        print("  compare <run1.cat> <run2.cat> Compare multiple benchmark runs")
        print("  export <run_id> --format csv [out.csv]  Export run measurements to CSV")
        return 0

    if sub in ("list", "ls"):
        benchmarks = b_reg.list()
        print("=" * 76)
        print("                      CAT BENCHMARK STUDIO")
        print("=" * 76)
        print(f"  {'#':<3} | {'ID':<24} | {'Name':<28} | {'Type':<10} | {'Tasks'}")
        print("-" * 76)
        for idx, b in enumerate(benchmarks, 1):
            print(f"  {idx:<3} | {b.id:<24} | {b.name[:28]:<28} | {b.benchmark_type:<10} | {len(b.tasks)} tasks")
        print("=" * 76)
        print("Commands: cat benchmark run <id> | cat benchmark export <run_id> --format csv")
        return 0

    if sub in ("stop", "cancel"):
        BenchmarkRunner.request_stop()
        print("✓ Requested benchmark runner to stop.")
        return 0

    if sub in ("create", "add"):
        if len(args) < 3:
            print("Usage: cat benchmark create <id> <name> [type]")
            return 1
        b_id, b_name = args[1], args[2]
        b_type = args[3] if len(args) > 3 else "coding"
        spec = BenchmarkSpec(
            id=b_id,
            name=b_name,
            benchmark_type=b_type,
            tasks=[
                BenchmarkTask(id="task-01", prompt="Sample test prompt", expected_output="expected text")
            ],
        )
        b_reg.register(spec, persist=True)
        print(f"✓ Created benchmark: {spec.name} ({spec.id})")
        return 0

    if sub in ("run", "start"):
        if len(args) < 2:
            print("Usage: cat benchmark run <id> [--model <model_id>]")
            return 1
        b_id = args[1]
        b = b_reg.get(b_id)
        if not b:
            print(f"Benchmark '{b_id}' not found.", file=sys.stderr)
            return 1

        # Select model
        model_id = "deepseek-r1-local"
        if "--model" in args:
            idx = args.index("--model")
            if idx + 1 < len(args):
                model_id = args[idx + 1]

        model = m_reg.get(model_id) or m_reg.list()[0]
        print(f"Running benchmark '{b.name}' ({len(b.tasks)} tasks) against model '{model.name}'...")

        def _prog(cur, total, tr):
            mark = "✓" if tr.passed else "✗"
            print(f"  [{cur}/{total}] {mark} {tr.task_id} ({tr.latency_sec:.2f}s, {tr.tokens_per_sec:.1f} tok/s)")

        res = BenchmarkRunner.run(b, model, on_progress=_prog)
        print()
        print(render_benchmark_report_card(res))
        return 0

    if sub in ("compare",):
        if len(args) < 2:
            print("Usage: cat benchmark compare <run1.cat|run_id> [run2.cat|run_id...]")
            return 1
        # Read runs from storage reports
        from ..storage import get_subpath, read_cat_file
        from .models import BenchmarkRunResult
        results = []
        for target in args[1:]:
            target_path = target
            if not os.path.isfile(target_path):
                target_path = get_subpath("reports", f"{target}.cat")
            if os.path.isfile(target_path):
                try:
                    meta, payload = read_cat_file(target_path)
                    r_data = payload.get("benchmark_run", payload)
                    results.append(BenchmarkRunResult.from_dict(r_data))
                except Exception as e:
                    print(f"Warning: could not load run file {target}: {e}", file=sys.stderr)
            else:
                print(f"Run file not found: {target}", file=sys.stderr)

        if not results:
            print("No valid benchmark runs found to compare.", file=sys.stderr)
            return 1
        print(render_multi_model_comparison(results))
        return 0

    if sub in ("export",):
        if len(args) < 2:
            print("Usage: cat benchmark export <run_id> --format csv [out.csv]")
            return 1
        run_id = args[1]
        out_f = None
        for i, a in enumerate(args):
            if a.endswith(".csv"):
                out_f = a
        if not out_f:
            out_f = f"{run_id}.csv"

        # Load run
        from ..storage import get_subpath, read_cat_file
        from .models import BenchmarkRunResult
        target_path = get_subpath("reports", f"{run_id}.cat")
        if not os.path.isfile(target_path) and os.path.isfile(run_id):
            target_path = run_id

        if not os.path.isfile(target_path):
            print(f"Benchmark run '{run_id}' not found in reports.", file=sys.stderr)
            return 1

        meta, payload = read_cat_file(target_path)
        r_data = payload.get("benchmark_run", payload)
        res = BenchmarkRunResult.from_dict(r_data)
        out_path = BenchmarkRunner.export_to_csv(res, out_f)
        print(f"✓ Exported benchmark measurements to: {out_path}")
        return 0

    print(f"Unknown benchmark command: {sub}. Run `cat benchmark --help`.", file=sys.stderr)
    return 1


# -----------------------------------------------------------------------------
# 10. Model Lab CLI
# -----------------------------------------------------------------------------

def model_cli(argv: List[str]) -> int:
    """Handles `cat model [list|add|info|test|run|benchmark|stop|remove]`."""
    from .lab import (
        get_model_registry,
        check_compatibility,
        ModelRunner,
        ModelSpec,
    )
    reg = get_model_registry()

    args = argv[1:] if argv and argv[0] in ("model", "models", "--model") else argv
    sub = args[0].lower() if args else "list"

    if sub in ("--help", "-h", "help"):
        print("Usage: cat model [command]")
        print("\nCommands:")
        print("  list (default)      List registered local and custom models")
        print("  info <id>           Display model specifications and compatibility check")
        print("  test <id>           Run an authentic inference probe test")
        print("  add <id> <name>     Register a new model spec")
        print("  capacity <id>       Run a progressive input capacity test")
        print("  remove <id>         Unregister a model")
        return 0

    if sub in ("list", "ls"):
        models = reg.list()
        print("=" * 76)
        print("                         CAT MODEL LAB")
        print("=" * 76)
        print(f"  {'#':<3} | {'ID':<22} | {'Name':<24} | {'Framework':<10} | {'Status'}")
        print("-" * 76)
        for idx, m in enumerate(models, 1):
            print(f"  {idx:<3} | {m.id:<22} | {m.name[:24]:<24} | {m.framework:<10} | {m.status}")
        print("=" * 76)
        print("Commands: cat model info <id> | cat model test <id> | cat model add")
        return 0

    if sub in ("info", "status"):
        if len(args) < 2:
            print("Usage: cat model info <id>")
            return 1
        mid = args[1]
        m = reg.get(mid)
        if not m:
            print(f"Model '{mid}' not found.", file=sys.stderr)
            return 1

        compat = check_compatibility(m)
        print("=" * 66)
        print(f"  MODEL SPECIFICATION: {m.name.upper()}")
        print("=" * 66)
        print(f"  ID           : {m.id}")
        print(f"  Type         : {m.model_type}")
        print(f"  Framework    : {m.framework}")
        print(f"  Runtime      : {m.provider_runtime}")
        print(f"  Precision    : {m.precision} (Quant: {m.quantization})")
        print(f"  Context Size : {m.context_size} tokens")
        print(f"  Expected VRAM: {m.expected_vram_gb:.1f} GB")
        print(f"  Expected RAM : {m.expected_ram_gb:.1f} GB")
        print(f"  Capabilities : {', '.join(m.capabilities)}")
        print("-" * 66)
        print(f"  [COMPATIBILITY AUDIT]: {compat.status}")
        for d in compat.details:
            print(f"    • {d}")
        if not compat.details:
            print("    ✓ All hardware requirements fully met by host environment.")
        print("=" * 66)
        return 0

    if sub in ("test", "run"):
        if len(args) < 2:
            print("Usage: cat model test <id> [prompt]")
            return 1
        mid = args[1]
        m = reg.get(mid)
        if not m:
            print(f"Model '{mid}' not found.", file=sys.stderr)
            return 1
        prompt = args[2] if len(args) > 2 else "Explain what makes CAT CLI unique in one sentence."
        print(f"Sending test probe to '{m.name}'...")
        res = ModelRunner.run_inference(m, prompt=prompt)
        print("=" * 60)
        print(f"  Success   : {'✓ Yes' if res['success'] else '✗ No'}")
        print(f"  Latency   : {res['latency_sec']:.2f}s ({res['tokens_per_second']:.1f} tok/s)")
        print(f"  Tokens    : {res['input_tokens']} in / {res['output_tokens']} out")
        if res.get("error"):
            print(f"  Error     : {res['error']}")
        if res.get("output"):
            print(f"  Output    :\n{res['output']}")
        print("=" * 60)
        return 0 if res["success"] else 1

    if sub in ("capacity",):
        if len(args) < 2:
            print("Usage: cat model capacity <id>")
            return 1
        mid = args[1]
        m = reg.get(mid)
        if not m:
            print(f"Model '{mid}' not found.", file=sys.stderr)
            return 1
        print(f"Running progressive capacity test on '{m.name}' (context: {m.context_size})...")
        cap_res = ModelRunner.run_capacity_test(m)
        print("-" * 60)
        for t in cap_res["tier_results"]:
            st = "✓ PASS" if t["success"] else "✗ FAIL"
            print(f"  {t['tier']:<28} : {st} ({t['latency_sec']:.2f}s, {t['tokens_per_sec']:.1f} tok/s)")
        print("-" * 60)
        print(f"Failure Point: {cap_res['failure_point']}")
        return 0

    if sub in ("add", "create"):
        if len(args) < 3:
            print("Usage: cat model add <id> <name> [framework]")
            return 1
        mid, mname = args[1], args[2]
        mfw = args[3] if len(args) > 3 else "ollama"
        spec = ModelSpec(id=mid, name=mname, framework=mfw)
        reg.register(spec, persist=True)
        print(f"✓ Registered model: {spec.name} ({spec.id})")
        return 0

    if sub in ("remove", "delete"):
        if len(args) < 2:
            print("Usage: cat model remove <id>")
            return 1
        mid = args[1]
        if reg.unregister(mid):
            print(f"✓ Removed model '{mid}'.")
            return 0
        print(f"Model '{mid}' not found.", file=sys.stderr)
        return 1

    print(f"Unknown model command: {sub}. Run `cat model --help`.", file=sys.stderr)
    return 1


# -----------------------------------------------------------------------------
# 11. Dataset CLI
# -----------------------------------------------------------------------------

def dataset_cli(argv: List[str]) -> int:
    """Handles `cat dataset [list|add|info|remove]`."""
    from .lab import get_dataset_registry
    reg = get_dataset_registry()

    args = argv[1:] if argv and argv[0] in ("dataset", "datasets", "--dataset") else argv
    sub = args[0].lower() if args else "list"

    if sub in ("--help", "-h", "help"):
        print("Usage: cat dataset [command]")
        print("\nCommands:")
        print("  list (default)      List registered local datasets")
        print("  add <file_path>     Inspect and register a local dataset file")
        print("  info <id>           Display dataset sample statistics and features")
        print("  remove <id>         Remove dataset metadata")
        return 0

    if sub in ("list", "ls"):
        items = reg.list()
        print("=" * 72)
        print("                      CAT DATASET REGISTRY")
        print("=" * 72)
        print(f"  {'#':<3} | {'ID':<24} | {'Name':<24} | {'Samples':<8} | {'Format'}")
        print("-" * 72)
        for idx, d in enumerate(items, 1):
            print(f"  {idx:<3} | {d.id:<24} | {d.name[:24]:<24} | {d.num_samples:<8} | {d.format}")
        print("=" * 72)
        print("Commands: cat dataset add <path> | cat dataset info <id>")
        return 0

    if sub in ("add", "inspect"):
        if len(args) < 2:
            print("Usage: cat dataset add <file_path>")
            return 1
        fpath = args[1]
        try:
            spec = reg.inspect_file(fpath)
            reg.add(spec, persist=True)
            print(f"✓ Registered dataset: {spec.name} ({spec.id})")
            print(f"  Samples : {spec.num_samples} rows")
            print(f"  Features: {spec.num_features} columns ({', '.join(spec.labels[:5])})")
            return 0
        except Exception as e:
            print(f"Failed to profile dataset: {e}", file=sys.stderr)
            return 1

    if sub in ("info", "status"):
        if len(args) < 2:
            print("Usage: cat dataset info <id>")
            return 1
        did = args[1]
        d = reg.get(did)
        if not d:
            print(f"Dataset '{did}' not found.", file=sys.stderr)
            return 1
        print("=" * 64)
        print(f"  DATASET PROFILE: {d.name.upper()}")
        print("=" * 64)
        print(f"  ID        : {d.id}")
        print(f"  Format    : {d.format}")
        print(f"  File Path : {d.file_path or 'In-Memory Reference'}")
        print(f"  Samples   : {d.num_samples}")
        print(f"  Features  : {d.num_features} ({', '.join(d.labels)})")
        print(f"  File Size : {d.file_size_bytes} bytes")
        print(f"  Missing   : {d.missing_values} missing/null elements")
        print("=" * 64)
        return 0

    print(f"Unknown dataset command: {sub}. Run `cat dataset --help`.", file=sys.stderr)
    return 1


# -----------------------------------------------------------------------------
# 12. Experiment Tracker CLI
# -----------------------------------------------------------------------------

def experiment_cli(argv: List[str]) -> int:
    """Handles `cat experiment [list|create|run|resume]`."""
    from .lab import get_experiment_tracker, PyTorchTrainer
    tracker = get_experiment_tracker()

    args = argv[1:] if argv and argv[0] in ("experiment", "experiments", "--experiment") else argv
    sub = args[0].lower() if args else "list"

    if sub in ("--help", "-h", "help"):
        print("Usage: cat experiment [command]")
        print("\nCommands:")
        print("  list (default)      List tracked experiments")
        print("  create <name>       Initialize a new reproducible experiment")
        print("  run <id>            Execute an experiment training loop")
        return 0

    if sub in ("list", "ls"):
        items = tracker.list()
        print("=" * 72)
        print("                     CAT EXPERIMENT TRACKER")
        print("=" * 72)
        print(f"  {'#':<3} | {'ID':<24} | {'Name':<24} | {'Status':<10} | {'Checkpoints'}")
        print("-" * 72)
        for idx, e in enumerate(items, 1):
            print(f"  {idx:<3} | {e.id:<24} | {e.name[:24]:<24} | {e.status:<10} | {len(e.checkpoints)} cp")
        print("=" * 72)
        print("Commands: cat experiment create <name> | cat experiment run <id>")
        return 0

    if sub in ("create", "new"):
        if len(args) < 2:
            print("Usage: cat experiment create <name> [--model <model_id>]")
            return 1
        name = args[1]
        mid = "pytorch-mlp-classifier"
        if "--model" in args:
            idx = args.index("--model")
            if idx + 1 < len(args):
                mid = args[idx + 1]
        exp = tracker.create(name=name, model_id=mid)
        print(f"✓ Initialized experiment: {exp.name} ({exp.id})")
        print(f"  Captured environment snapshot on {exp.environment.get('primary_device', 'CPU')}.")
        return 0

    if sub in ("run", "train"):
        if len(args) < 2:
            print("Usage: cat experiment run <id>")
            return 1
        eid = args[1]
        exp = tracker.get(eid)
        if not exp:
            print(f"Experiment '{eid}' not found.", file=sys.stderr)
            return 1

        print(f"Starting training workflow for experiment '{exp.name}'...")
        trainer = PyTorchTrainer()

        def _epoch_cb(prog):
            print(f"  Epoch {prog.epoch}/{prog.total_epochs} | Loss: {prog.loss:.4f} | Acc: {prog.accuracy:.2f}")

        res = trainer.run_training_experiment(exp, epochs=5, on_epoch=_epoch_cb)
        if res["success"]:
            tracker.set_status(exp.id, "completed")
            tracker.add_checkpoint(exp.id, name="Final Model", metrics={"accuracy": res["final_accuracy"], "loss": res["final_loss"]})
            print(f"✓ Completed training in {res['runtime_sec']:.2f}s on {res['device']}.")
            return 0
        else:
            print(f"Training notice: {res.get('error')}")
            if res.get("guide"):
                print(res["guide"])
            return 1

    print(f"Unknown experiment command: {sub}. Run `cat experiment --help`.", file=sys.stderr)
    return 1

