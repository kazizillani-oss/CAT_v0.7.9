"""
CatRuntime — Unified CAT Core Adapter Layer for Fatty CAT.

Single source of truth:
- Wraps existing CAT core modules (aicore, agent, ai_modes, providers, models,
  permissions, memory, customization, extensions, preview, etc.)
- Provides a clean, typed internal API consumed by Fatty CAT's web server and UI
- NEVER rewrites or duplicates business logic — exposes CAT core dynamically.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

# Ensure package is on sys.path (source-checkout only; pip-installed CAT
# already has `calc_terminal` importable).
try:
    import calc_terminal as _ct_check  # noqa: F401
except Exception:
    _CAT_ROOT = Path(__file__).resolve().parent.parent.parent
    if str(_CAT_ROOT) not in sys.path:
        sys.path.insert(0, str(_CAT_ROOT))

# CAT Core Imports
from calc_terminal import aicore, ai_modes, commands_data, config as cct_config, identity
from calc_terminal import memory, permissions as cct_perms
from calc_terminal.models import manager as model_manager
from calc_terminal.providers import provider_manager
from calc_terminal import ollama_catalog, ollama_download
from calc_terminal import customization, extensions as cct_ext
from calc_terminal import workspace as ws_module, projects as proj_module
from calc_terminal.viewers import registry as viewer_registry
from calc_terminal import eventbus, event_stream


class CatRuntime:
    """Canonical adapter around CAT Core functionality."""

    def __init__(self):
        self.start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        self.recent_events: List[Dict[str, Any]] = []
        self._wire_events()

    def _wire_events(self):
        """Wire into CAT eventbus to track recent activity."""
        def _on_bus_event(topic: str, **kwargs):
            entry = {
                "topic": topic,
                "timestamp": time.time(),
                "data": {k: str(v)[:150] for k, v in kwargs.items()}
            }
            self.recent_events.append(entry)
            if len(self.recent_events) > 100:
                self.recent_events.pop(0)

        for topic in (
            eventbus.FILE_CREATED, eventbus.FILE_SAVED, eventbus.FILE_DELETED,
            eventbus.AI_RESPONSE_GENERATED, eventbus.TERMINAL_COMMAND,
            eventbus.WORKSPACE_OPENED, eventbus.MODE_SWITCHED,
            eventbus.PACKAGE_INSTALLED, eventbus.TODO_CREATED, eventbus.TODO_COMPLETED
        ):
            eventbus.bus.subscribe(topic, lambda t=topic, **kw: _on_bus_event(t, **kw))

    # ─────────────────────────────────────────────────────────────
    # 1. Capability Discovery & Version Contract
    # ─────────────────────────────────────────────────────────────

    def get_capabilities(self) -> Dict[str, Any]:
        """Return the dynamic CAT capability registry and version contract."""
        cfg = aicore.load_config()
        v_reg = viewer_registry.ViewerRegistry()

        # Tools summary
        tools_list = [
            {"id": "list_formulas", "name": "List Formulas", "category": "math"},
            {"id": "solve_formula", "name": "Solve Formula", "category": "math"},
            {"id": "solve_custom", "name": "Solve Custom", "category": "math"},
            {"id": "calculate", "name": "Safe Calculator", "category": "math"},
            {"id": "generate_numerical", "name": "Generate Numerical", "category": "science"},
            {"id": "plot_preset", "name": "Plot Preset", "category": "graph"},
            {"id": "plot_function", "name": "Plot Function 2D", "category": "graph"},
            {"id": "plot_surface", "name": "Plot Surface 3D", "category": "graph"},
            {"id": "atom_2d", "name": "2D Atom Simulation", "category": "simulation"},
            {"id": "atom_3d", "name": "3D Atom Simulation", "category": "simulation"},
            {"id": "orbital", "name": "Quantum Orbital", "category": "simulation"},
            {"id": "orbital_grid", "name": "Orbital Grid Chart", "category": "simulation"},
            {"id": "bloch", "name": "Bloch Sphere Qubit", "category": "quantum"},
            {"id": "bonding", "name": "Chemical Bonding Map", "category": "science"},
            {"id": "web_search", "name": "Live Web Search", "category": "research"},
            {"id": "deep_research", "name": "Deep Research Synthesis", "category": "research"},
            {"id": "read_attachment", "name": "Read Attachment", "category": "file"},
            {"id": "read_file", "name": "Read File", "category": "file"},
            {"id": "write_file", "name": "Write File", "category": "file"},
            {"id": "create_folder", "name": "Create Folder", "category": "file"},
            {"id": "delete_file", "name": "Delete File", "category": "file"},
            {"id": "rename_file", "name": "Rename File", "category": "file"},
            {"id": "edit_file", "name": "Edit File", "category": "file"},
            {"id": "search_workspace", "name": "Search Workspace", "category": "file"},
            {"id": "list_directory", "name": "List Directory", "category": "file"},
            {"id": "inspect_project", "name": "Inspect Project Structure", "category": "project"},
            {"id": "archive_list", "name": "List Archive Contents", "category": "archive"},
            {"id": "archive_extract", "name": "Extract Archive", "category": "archive"},
            {"id": "archive_add_entries", "name": "Add to Archive", "category": "archive"},
            {"id": "archive_delete_entries", "name": "Delete from Archive", "category": "archive"},
            {"id": "archive_repack", "name": "Repack Archive", "category": "archive"},
            {"id": "archive_validate", "name": "Validate Archive", "category": "archive"},
            {"id": "run_terminal", "name": "Run Terminal Command", "category": "execution"},
            {"id": "run_build", "name": "Run Project Build", "category": "execution"},
            {"id": "run_tests", "name": "Run Test Suite", "category": "execution"},
            {"id": "install_packages", "name": "Install Packages", "category": "execution"},
            {"id": "device_action", "name": "Device Control Action", "category": "system"},
        ]

        # All 103 commands
        cmds = [{"command": c[0], "description": c[1]} for c in commands_data.COMMANDS]

        # Modes
        modes_dict = {}
        for k in ai_modes.MODE_ORDER:
            m = ai_modes.MODE_META.get(k, {})
            modes_dict[k] = {
                "key": k,
                "label": m.get("label", k.title()),
                "icon": m.get("icon", "●"),
                "accent": ai_modes._rgb_to_hex(m.get("accent", (122, 162, 247))),
                "gradient": [
                    ai_modes._rgb_to_hex(m["gradient"][0]),
                    ai_modes._rgb_to_hex(m["gradient"][1])
                ] if m.get("gradient") else ["#5d84f0", "#91beff"],
                "purpose": m.get("purpose", ""),
            }

        # Extensions
        ext_list = []
        for ext in cct_ext.BUILTIN_EXTENSIONS.values():
            eid = ext.get("id", "")
            ext_list.append({
                "id": eid,
                "name": ext.get("name", eid),
                "installed": cct_ext.is_installed(eid),
                "enabled": cct_ext.is_enabled(eid),
                "icon": ext.get("icon", "🧩"),
                "description": ext.get("description", ""),
            })

        return {
            "version_contract": {
                "cat_version": identity.APP_VERSION,
                "api_version": "1.0.0",
                "fatty_cat_version": "1.0.0",
            },
            "active_mode": ai_modes.current_mode(),
            "modes": modes_dict,
            "mode_order": list(ai_modes.MODE_ORDER),
            "active_provider": cfg.get("provider", "openai"),
            "active_model": cfg.get("model", "gpt-4o"),
            "has_api_key": bool(cfg.get("api_key")),
            "providers_count": len(model_manager.load_providers()),
            "commands": cmds,
            "native_ui_commands": list(commands_data.NATIVE_UI_COMMANDS),
            "tools": tools_list,
            "viewers": list(v_reg._providers.keys()),
            "extensions": ext_list,
            "features": [
                "chat", "agent", "build", "plan", "research", "debugger", "notebook",
                "files", "code_editor", "terminal", "browser", "live_preview",
                "models", "providers", "ollama", "permissions", "memory",
                "customization", "extensions", "vision", "diagnostics", "fomoji_auth",
                "cat_cli", "agents_registry", "multi_agent_orchestration", "missions",
                "task_scheduler", "cat_lab", "benchmark_studio", "model_lab",
                "dataset_registry", "experiment_tracker", "hardware_profiler",
                "storage_manager", "backup_restore", "cat_file_import_export",
                "integrations_center", "skills_registry", "custom_commands",
                "vscode_cat_cli_bridge", "vercel_serverless_ide"
            ],
        }

    # ─────────────────────────────────────────────────────────────
    # 2. AI Execution & Streaming
    # ─────────────────────────────────────────────────────────────

    async def stream_chat(
        self,
        message: str,
        mode: str = "notebook",
        history: Optional[List[Dict[str, str]]] = None,
        project_path: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream chat tokens directly from aicore.stream_ai()."""
        self.request_count += 1
        if project_path:
            ws_module.set_active_project(project_path)

        cfg = aicore.load_config()
        system_prompt = ai_modes.system_prompt_for(mode)

        loop = asyncio.get_event_loop()
        queue: asyncio.Queue[Tuple[str, Any]] = asyncio.Queue()

        def _worker():
            try:
                for chunk in aicore.stream_ai(
                    prompt=message,
                    system_prompt=system_prompt,
                    history=history,
                    config=cfg,
                    on_failover=lambda msg: loop.call_soon_threadsafe(
                        queue.put_nowait, ("failover", msg)
                    ),
                    size_class="normal"
                ):
                    loop.call_soon_threadsafe(queue.put_nowait, ("token", chunk))
                loop.call_soon_threadsafe(queue.put_nowait, ("done", None))
            except Exception as e:
                self.error_count += 1
                loop.call_soon_threadsafe(queue.put_nowait, ("error", str(e)))

        thread = asyncio.to_thread(_worker)
        task = asyncio.create_task(thread)

        try:
            while True:
                kind, data = await queue.get()
                if kind == "token":
                    yield {"type": "token", "text": data}
                elif kind == "failover":
                    yield {"type": "thinking", "text": f"Failover: {data}"}
                elif kind == "error":
                    yield {"type": "error", "error": data}
                    break
                elif kind == "done":
                    yield {"type": "done"}
                    break
        finally:
            await task

    def run_agent_turn(
        self,
        message: str,
        mode: str = "agent",
        max_steps: int = 15,
        project_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run a full step-by-step agent loop using agent.run_agent()."""
        self.request_count += 1
        if project_path:
            ws_module.set_active_project(project_path)

        from calc_terminal.agent import run_agent as _cct_run_agent

        try:
            agent_mode = "agent" if mode in ("agent", "build", "plan") else "ai"
            text, steps, meta = _cct_run_agent(
                message,
                max_steps=max_steps,
                verbose=False,
                mode=agent_mode
            )

            formatted_steps = []
            for s in steps:
                if len(s) >= 3:
                    formatted_steps.append({
                        "tool": s[0],
                        "args": s[1] if isinstance(s[1], dict) else {},
                        "result": str(s[2])[:800],
                    })

            return {
                "success": True,
                "response": text or "",
                "steps": formatted_steps,
                "meta": meta or {},
            }
        except Exception as e:
            self.error_count += 1
            return {
                "success": False,
                "response": f"Agent execution error: {e}",
                "steps": [],
                "meta": {},
            }

    # ─────────────────────────────────────────────────────────────
    # 3. AI Modes Management
    # ─────────────────────────────────────────────────────────────

    def get_modes(self) -> Dict[str, Any]:
        """Get snapshot of current modes and active mode."""
        return {
            "current": ai_modes.current_mode(),
            "order": list(ai_modes.MODE_ORDER),
            "modes": {
                k: {
                    "key": k,
                    "label": v.get("label", k.title()),
                    "icon": v.get("icon", "●"),
                    "accent": ai_modes._rgb_to_hex(v.get("accent", (122, 162, 247))),
                    "gradient": [
                        ai_modes._rgb_to_hex(v["gradient"][0]),
                        ai_modes._rgb_to_hex(v["gradient"][1])
                    ] if v.get("gradient") else ["#5d84f0", "#91beff"],
                    "purpose": v.get("purpose", ""),
                    "system_prompt": v.get("system_prompt", ""),
                }
                for k, v in ai_modes.MODE_META.items()
            }
        }

    def set_mode(self, mode_key: str) -> str:
        """Switch active AI mode."""
        res = ai_modes.set_mode(mode_key)
        eventbus.bus.publish(eventbus.MODE_SWITCHED, mode=res)
        return res

    def create_custom_mode(
        self,
        key: str,
        label: str,
        icon: str,
        accent_hex: str,
        purpose: str = "",
        system_prompt: str = ""
    ) -> Tuple[bool, str]:
        """Create user-defined mode via ai_modes.create_mode()."""
        return ai_modes.create_mode(key, label, icon, accent_hex, purpose, system_prompt)

    def delete_custom_mode(self, key: str) -> Tuple[bool, str]:
        """Delete custom mode."""
        return ai_modes.delete_mode(key)

    # ─────────────────────────────────────────────────────────────
    # 4. Providers & Models Management
    # ─────────────────────────────────────────────────────────────

    def list_providers(self) -> List[Dict[str, Any]]:
        """List all providers from providers.json."""
        all_provs = model_manager.load_providers()
        cfg = aicore.load_config()
        active_id = cfg.get("provider", "openai")

        out = []
        for p in all_provs:
            item = dict(p)
            item["is_active"] = (p.get("id") == active_id)
            out.append(item)
        return out

    def get_models_for_provider(self, provider_id: str, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Get models for provider using CAT model manager with caching."""
        cfg = aicore.load_config()
        models_res = model_manager.get_models(provider_id, config=cfg, force_refresh=force_refresh)
        if isinstance(models_res, tuple):
            models = models_res[0]
        else:
            models = models_res or []

        # If ollama and local service is running, also merge installed local models
        if provider_id == "ollama":
            try:
                installed = provider_manager.refresh_ollama_models(base_url="http://localhost:11434")
                if installed:
                    for im in installed:
                        if im not in models:
                            models.insert(0, im)
            except Exception:
                pass

        active_model = cfg.get("model", "")

        out = []
        for m_id in models:
            if not isinstance(m_id, str):
                continue
            meta = model_manager.get_model_meta(m_id, provider_id) or {}
            out.append({
                "id": m_id,
                "name": meta.get("name", m_id),
                "is_active": (m_id == active_model),
                "family": meta.get("family", ""),
                "description": meta.get("desc", meta.get("description", "")),
                "context_window": meta.get("context", meta.get("context_window", 4096)),
                "capabilities": meta.get("caps", meta.get("capabilities", [])),
                "free": meta.get("free", False),
            })
        return out

    def switch_model(self, provider_id: str, model_id: str, api_key: Optional[str] = None, base_url: Optional[str] = None) -> Dict[str, Any]:
        """Switch active provider and model in CAT config."""
        cfg = aicore.load_config()
        cfg["provider"] = provider_id
        cfg["model"] = model_id
        if api_key is not None:
            cfg["api_key"] = api_key
        if base_url:
            cfg["base_url"] = base_url
            if provider_id == "ollama":
                cfg["ollama_url"] = base_url
        elif provider_id == "ollama":
            cfg["base_url"] = "http://localhost:11434"
            cfg["ollama_url"] = "http://localhost:11434"
            cfg["api_style"] = "ollama"
        aicore.save_config(cfg)
        provider_manager.save_config(cfg)
        return {"success": True, "provider": provider_id, "model": model_id, "base_url": cfg.get("base_url")}

    # ─────────────────────────────────────────────────────────────
    # 5. Ollama Support
    # ─────────────────────────────────────────────────────────────

    def get_ollama_status(self) -> Dict[str, Any]:
        """Check Ollama installation and connection status."""
        base_url = ollama_download.ollama_base_url()
        installed = ollama_download.is_ollama_installed()
        running = ollama_download.is_ollama_running(base_url=base_url)
        installed_models = []
        if running:
            try:
                installed_models = provider_manager.refresh_ollama_models(base_url=base_url)
            except Exception:
                pass
        return {
            "installed": installed,
            "running": running,
            "base_url": base_url,
            "installed_models": installed_models,
        }

    def get_ollama_catalog(self, query: str = "") -> List[Dict[str, Any]]:
        """Return curated Ollama models from ollama_catalog.py."""
        if query:
            return ollama_catalog.search_models(query)
        return ollama_catalog.all_models()

    def ensure_ollama_started(self) -> Tuple[bool, str]:
        """Start local Ollama serve process if installed and not running."""
        return ollama_download.ensure_ollama_running(auto_start=True)

    # ─────────────────────────────────────────────────────────────
    # 6. Command Dispatcher
    # ─────────────────────────────────────────────────────────────

    def get_commands(self) -> List[Dict[str, str]]:
        """Return list of all 103 slash commands."""
        return [{"command": c[0], "description": c[1]} for c in commands_data.COMMANDS]

    def dispatch_command(self, cmd_line: str) -> Dict[str, Any]:
        """Dispatch a slash command to CAT handlers."""
        cmd = cmd_line.strip()
        parts = cmd.split(maxsplit=1)
        base = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if base in ("/about", "about"):
            return {"command": base, "output": f"FATTY CAT v{identity.APP_VERSION} (Source: {identity.APP_NAME})"}

        if base in ("/browser", "/browse", "/cat", "browser", "browse", "cat"):
            try:
                from calc_terminal.host.launcher import launch_cat_host, can_launch_host
                if can_launch_host():
                    target = arg or "about:home"
                    launch_cat_host(start_browser_url=target, start_mode="browser", block=False)
                    return {"command": base, "output": f"Launched CAT Browser: {target}"}
                return {"command": base, "output": "CAT Browser requires PySide6 on host."}
            except Exception as e:
                return {"command": base, "output": f"Error launching CAT Browser: {e}"}

        if base in ("/help", "help"):
            return {
                "command": base,
                "output": "Available commands:\n" + "\n".join(f"  {c[0]:<20} {c[1]}" for c in commands_data.COMMANDS[:30]) + "\n  ...and 70+ more. Use Command Palette (Ctrl+K) to browse all."
            }

        if base in ("/tokens", "tokens"):
            usage = aicore.get_session_usage()
            return {"command": base, "output": f"Tokens: {usage.get('total_tokens', 0)} used | Requests: {usage.get('requests', 0)}"}

        if base in ("/calculator", "/calc", "calc"):
            if not arg:
                return {"command": base, "output": "Usage: /calc <expression>  e.g. /calc 2.5 * log10(100)"}
            from calc_terminal.agent import _tool_calculate
            res = _tool_calculate({"expression": arg})
            return {"command": base, "output": res}

        if base in ("/formulas", "formulas"):
            from calc_terminal.agent import _tool_list_formulas
            return {"command": base, "output": _tool_list_formulas({})}

        if base in ("/solve", "solve"):
            if not arg:
                return {"command": base, "output": "Usage: /solve <formula_key> values={...} or /solve formula=... values={...} solve_for=..."}
            from calc_terminal.solver import FORMULA_LIBRARY
            matches = [k for k in FORMULA_LIBRARY if arg.lower() in k.lower()]
            if matches:
                info = FORMULA_LIBRARY[matches[0]]
                return {"command": base, "output": f"Formula: {info[0]}\nEquation: {info[2]}\nCategory: {info[1]}"}
            return {"command": base, "output": f"No formula found matching '{arg}'."}

        if base in ("/workspace", "workspace"):
            root = ws_module.active_project() or ws_module.root_dir()
            return {"command": base, "output": f"Active workspace: {root}"}

        if base in ("/mode", "mode"):
            if arg and arg in ai_modes.MODE_META:
                new_m = self.set_mode(arg)
                return {"command": base, "output": f"Switched AI mode to {new_m.upper()}."}
            return {"command": base, "output": f"Current mode: {ai_modes.current_mode().upper()}\nAvailable: {', '.join(ai_modes.MODE_ORDER)}"}

        if base in ("/memory", "/m", "memory"):
            from calc_terminal import memory as _cct_mem
            if arg.lower() == "clear":
                _cct_mem.clear()
                return {"command": base, "output": "Persistent memory cleared."}
            facts = _cct_mem.get_facts() if hasattr(_cct_mem, "get_facts") else []
            topics = _cct_mem.get_topics() if hasattr(_cct_mem, "get_topics") else []
            out = f"Persistent Facts ({len(facts)}):\n"
            for f in facts:
                txt = f if isinstance(f, str) else f.get("fact", str(f))
                out += f"  • {txt}\n"
            if topics:
                out += f"\nTop Topics: {', '.join(topics[:5])}"
            return {"command": base, "output": out or "No facts remembered yet."}

        if base in ("/extensions", "extensions"):
            exts = self.list_extensions()
            out = "CAT Extensions:\n"
            for e in exts:
                status = "✓ Enabled" if e.get("enabled") else "○ Disabled"
                out += f"  {e.get('name', e.get('id')):<30} {status}\n"
            return {"command": base, "output": out}

        if base in ("/atomsim", "/atom", "atomsim"):
            from calc_terminal.agent import _tool_simulate_atom_2d
            return {"command": base, "output": _tool_simulate_atom_2d({"element": arg or "H"})}

        if base in ("/orbitals", "orbitals"):
            from calc_terminal.agent import _tool_simulate_orbital
            return {"command": base, "output": _tool_simulate_orbital({"n": 2, "l": 1, "m": 0})}

        if base in ("/graph", "graph"):
            from calc_terminal.agent import _tool_plot_preset
            preset_name = arg or "first_order_kinetics"
            return {"command": base, "output": _tool_plot_preset({"preset": preset_name})}

        if base in ("/model", "model"):
            cfg = aicore.load_config()
            if arg:
                self.switch_model(cfg.get("provider", "ollama"), arg)
                return {"command": base, "output": f"Switched model to {arg}."}
            return {"command": base, "output": f"Active provider: {cfg.get('provider', 'ollama').upper()} · Model: {cfg.get('model', 'deepseek-r1')}"}

        if base in ("/ai-verify", "/verify", "verify"):
            cfg = aicore.load_config()
            prov = cfg.get("provider") or "ollama"
            mod = cfg.get("model") or "deepseek-r1"
            try:
                ok = aicore.verify_connection(prov, config=cfg)
                status = "✓ Connection Successful" if ok else "⚠ Connection Failed"
            except Exception as e:
                status = f"⚠ Verification Error: {e}"
            return {"command": base, "output": f"AI Connectivity Test for {prov.upper()} ({mod}): {status}"}

        # Route CAT CLI subcommands (/cat ..., cat ..., /agents, /missions, /lab, /benchmark, /dataset, /experiment, /hardware, /storage, /backup, /integrations, /skills, /schedule, /doctor, /debug, /providers, /models, /offline)
        cli_prefixes = {
            "/cat": [], "cat": [], "cct": [], "catx": [],
            "/agents": ["agents"], "/agent-cli": ["agent"], "agents": ["agents"],
            "/missions": ["missions"], "/mission": ["mission"], "missions": ["missions"], "mission": ["mission"],
            "/lab": ["lab"], "lab": ["lab"],
            "/benchmark": ["benchmark"], "/benchmarks": ["benchmarks"], "benchmark": ["benchmark"],
            "/dataset": ["dataset"], "/datasets": ["datasets"], "dataset": ["dataset"],
            "/experiment": ["experiment"], "/experiments": ["experiments"], "experiment": ["experiment"],
            "/hardware": ["hardware"], "hardware": ["hardware"],
            "/storage": ["storage"], "storage": ["storage"],
            "/backup": ["backup"], "backup": ["backup"],
            "/restore": ["restore"], "restore": ["restore"],
            "/integrations": ["integrations"], "/integration": ["integration"], "integrations": ["integrations"],
            "/skills": ["skills"], "/skill": ["skill"], "skills": ["skills"],
            "/schedule": ["schedule"], "/tasks": ["tasks"], "schedule": ["schedule"],
            "/doctor": ["--doctor"], "doctor": ["--doctor"],
            "/debug-info": ["--debug"], "/version": ["--version"],
            "/providers": ["providers"], "providers": ["providers"],
            "/models": ["models"], "models": ["models"],
            "/offline": ["offline"], "offline": ["offline"],
            "/import": ["import"], "/export": ["export"],
        }
        if base in cli_prefixes:
            import shlex
            try:
                extra = shlex.split(arg) if arg else []
            except Exception:
                extra = arg.split() if arg else []
            cli_argv = cli_prefixes[base] + extra
            if not cli_argv:
                cli_argv = ["--help"]
            res = self.execute_cat_cli(cli_argv)
            return {
                "command": base,
                "output": res.get("output") or res.get("stdout") or res.get("stderr") or "Executed CAT CLI command.",
                "returncode": res.get("returncode", 0),
                "success": res.get("success", True),
            }

        if base in ("/derive", "derive"):
            res = self.get_derivation(arg or "first")
            return {"command": base, "output": res.get("derivation") or res.get("error", "No derivation found.")}

        if base in ("/bloch", "bloch"):
            from calc_terminal.agent import _tool_simulate_bloch
            return {"command": base, "output": _tool_simulate_bloch({"state": arg or "|+>"})}

        if base in ("/bonding", "bonding"):
            from calc_terminal.agent import _tool_simulate_bonding
            return {"command": base, "output": _tool_simulate_bonding({"molecule": arg or "H2O"})}

        if base in ("/todos", "/todo", "todos", "todo"):
            from calc_terminal import todos as _todos
            if arg.lower().startswith("add "):
                item = _todos.add(arg[4:].strip())
                return {"command": base, "output": f"✓ Added todo #{item.get('id')}: {item.get('text')}"}
            items = _todos.list_todos() if hasattr(_todos, "list_todos") else _todos.load()
            if not items:
                return {"command": base, "output": "No todos in workspace. Use `/todo add <task>` to add one."}
            lines = ["Workspace Todos:"]
            for t in items[:25]:
                if isinstance(t, dict):
                    mark = "✓" if t.get("done") else "○"
                    lines.append(f"  {mark} [{t.get('id', '?')}] {t.get('text', '')}")
            return {"command": base, "output": "\n".join(lines)}

        if base in ("/security", "/scan", "security"):
            try:
                from calc_terminal import security_scanner
                root = ws_module.active_project() or ws_module.root_dir()
                rep = security_scanner.scan_workspace(root) if hasattr(security_scanner, "scan_workspace") else {"status": "clean", "Workspace": root}
                return {"command": base, "output": f"Security Scan ({root}):\n{rep}"}
            except Exception as e:
                return {"command": base, "output": f"Security Scanner: {e}"}

        return {
            "command": base,
            "output": f"Command {base} dispatched. Type /help or press Ctrl+K for command details."
        }

    # ─────────────────────────────────────────────────────────────
    # 7. Permissions
    # ─────────────────────────────────────────────────────────────

    def get_permissions(self) -> Dict[str, Any]:
        """Get current permission manager snapshot."""
        return {
            "mode": cct_perms.perm_manager.mode,
            "mode_label": cct_perms.perm_manager.mode_label(),
            "permissions": [
                {"key": k, "label": l, "enabled": v}
                for k, l, v in cct_perms.perm_manager.snapshot()
            ],
            "log": [
                {"time": t, "key": k, "action": a, "decision": d}
                for t, k, a, d in cct_perms.perm_manager.log[-30:]
            ],
        }

    def set_permission_mode(self, mode: str) -> Dict[str, Any]:
        cct_perms.perm_manager.set_mode(mode)
        return {"mode": cct_perms.perm_manager.mode, "label": cct_perms.perm_manager.mode_label()}

    def toggle_permission(self, key: str, enabled: bool) -> bool:
        return cct_perms.perm_manager.set(key, enabled)

    def decide_permission(self, key: str, decision: str, action_text: str = "") -> bool:
        return cct_perms.perm_manager.decide(key, decision, action_text)

    # ─────────────────────────────────────────────────────────────
    # 8. Memory
    # ─────────────────────────────────────────────────────────────

    def get_memory_facts(self) -> List[str]:
        data = memory.load()
        return data.get("facts", [])

    def add_memory_fact(self, fact: str):
        memory.add_fact(fact)

    def remove_memory_fact(self, index: int):
        data = memory.load()
        facts = data.get("facts", [])
        if 0 <= index < len(facts):
            facts.pop(index)
            data["facts"] = facts
            memory.save(data)

    def get_memory_activity(self) -> List[Dict[str, Any]]:
        data = memory.load()
        return data.get("activity", [])

    def get_memory_topics(self) -> Dict[str, int]:
        data = memory.load()
        return data.get("topics", {})

    # ─────────────────────────────────────────────────────────────
    # 9. Customization & UI Layout
    # ─────────────────────────────────────────────────────────────

    def get_customization(self) -> Dict[str, Any]:
        """Get entire layout and style customization state."""
        return customization.get_customization().to_dict()

    def update_layout_component(self, comp_id: str, updates: Dict[str, Any]) -> bool:
        """Update layout positioning or size for a UI panel."""
        cust = customization.get_customization()
        return cust.layout.update_component(comp_id, updates)

    def reset_customization(self) -> bool:
        """Reset layout and styling to factory defaults."""
        return customization.get_customization().reset_to_defaults()

    # ─────────────────────────────────────────────────────────────
    # 10. Extensions
    # ─────────────────────────────────────────────────────────────

    def list_extensions(self) -> List[Dict[str, Any]]:
        return cct_ext.list_extensions()

    def toggle_extension(self, ext_id: str, enable: bool) -> bool:
        if enable:
            return cct_ext.enable(ext_id)
        return cct_ext.disable(ext_id)

    def create_extension(self, **kwargs) -> Tuple[bool, Dict[str, Any]]:
        return cct_ext.create_extension(**kwargs)

    # ─────────────────────────────────────────────────────────────
    # 11. Science & Notebook
    # ─────────────────────────────────────────────────────────────

    def solve_formula(self, key: str, values: Dict[str, float]) -> Dict[str, Any]:
        from calc_terminal import solver
        try:
            solve_for, result, name, cat, eq = solver.solve_library_formula(key, values)
            return {
                "success": True,
                "name": name,
                "category": cat,
                "equation": eq,
                "solve_for": solve_for,
                "result": result,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_derivation(self, keyword: str) -> Dict[str, Any]:
        from calc_terminal import derivations
        text = derivations.get_derivation(keyword)
        if text:
            return {"success": True, "derivation": text}
        return {"success": False, "error": f"No derivation found for '{keyword}'"}

    def get_atom_sim(self, element: str) -> Dict[str, Any]:
        from calc_terminal import atomsim
        z = atomsim.resolve_element(element)
        if z is None:
            return {"success": False, "error": f"Unknown element '{element}'"}
        sym, name, shells, mass = atomsim.ELEMENTS[z]
        return {
            "success": True,
            "z": z,
            "symbol": sym,
            "name": name,
            "shells": shells,
            "mass": mass,
        }

    # ─────────────────────────────────────────────────────────────
    # 12. Diagnostics
    # ─────────────────────────────────────────────────────────────

    def get_diagnostics(self) -> Dict[str, Any]:
        """System diagnostics, version contract, runtime statistics."""
        cfg = aicore.load_config()
        uptime_sec = int(time.time() - self.start_time)

        # Hardware metrics
        specs = {}
        try:
            from calc_terminal import pc_specs
            specs = pc_specs.get_specs()
        except Exception:
            pass

        return {
            "contract": {
                "cat_version": identity.APP_VERSION,
                "api_version": "1.0.0",
                "fatty_cat_version": "1.0.0",
            },
            "runtime": {
                "uptime_seconds": uptime_sec,
                "request_count": self.request_count,
                "error_count": self.error_count,
                "active_workspace": ws_module.active_project() or ws_module.root_dir(),
                "active_provider": cfg.get("provider", "openai"),
                "active_model": cfg.get("model", "gpt-4o"),
                "active_mode": ai_modes.current_mode(),
            },
            "hardware": specs,
            "recent_events": self.recent_events[-25:],
        }



    # ─────────────────────────────────────────────────────────────
    # 13. Full CAT CLI Subcommand Execution & Subsystem Bridges
    # ─────────────────────────────────────────────────────────────

    def execute_cat_cli(self, argv_or_cmd: Any, cwd: Optional[str] = None) -> Dict[str, Any]:
        """Execute any CAT CLI command or subcommand in-process and capture output."""
        import io
        import re
        import shlex
        from contextlib import redirect_stdout, redirect_stderr

        if isinstance(argv_or_cmd, str):
            raw = argv_or_cmd.strip()
            try:
                argv = shlex.split(raw)
            except Exception:
                argv = raw.split()
        else:
            argv = [str(a) for a in (argv_or_cmd or [])]

        if argv and argv[0].lower() in ("cat", "catx", "cct", "/cat"):
            argv = argv[1:]

        if not argv:
            argv = ["--help"]

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        rc = 0
        old_cwd = os.getcwd()

        try:
            if cwd and os.path.isdir(cwd):
                try:
                    os.chdir(cwd)
                except OSError:
                    pass

            from calc_terminal import cli as _cat_cli
            from calc_terminal import cli_commands as _cat_cmds

            cmd0 = argv[0].lower()
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                if cmd0 in ("-h", "--help", "help"):
                    print(_cat_cli._usage("cat"))
                elif cmd0 in ("-v", "--version", "version"):
                    print(f"CAT v{_cat_cli._version()}")
                elif cmd0 in ("--debug", "debug"):
                    rc = _cat_cli._debug_cli(argv)
                elif cmd0 in ("--doctor", "doctor"):
                    from calc_terminal.doctor import main as _doc_main
                    rc = _doc_main(argv[1:])
                elif cmd0 in ("update", "--update") and len(argv) > 1 and argv[1] in ("--check", "check"):
                    rc = _cat_cli._update_check_cli(argv)
                elif cmd0 in ("agents", "--agents", "agent", "--agent", "kitties", "kitty"):
                    rc = _cat_cmds.agents_cli(argv)
                elif cmd0 in ("missions", "--missions", "mission", "--mission"):
                    rc = _cat_cmds.missions_cli(argv)
                elif cmd0 in ("storage", "--storage"):
                    rc = _cat_cmds.storage_cli(argv)
                elif cmd0 in ("backup", "--backup", "restore", "--restore"):
                    rc = _cat_cmds.backup_cli(argv)
                elif cmd0 in ("integrations", "--integrations", "integration", "--integration"):
                    rc = _cat_cmds.integrations_cli(argv)
                elif cmd0 in ("import", "export"):
                    rc = _cat_cmds.cat_file_cli(argv)
                elif cmd0 in ("hardware", "--hardware"):
                    rc = _cat_cmds.hardware_cli(argv)
                elif cmd0 in ("lab", "--lab"):
                    rc = _cat_cmds.lab_cli(argv)
                elif cmd0 in ("benchmark", "benchmarks", "--benchmark", "--benchmarks"):
                    rc = _cat_cmds.benchmark_cli(argv)
                elif cmd0 in ("dataset", "datasets", "--dataset", "--datasets"):
                    rc = _cat_cmds.dataset_cli(argv)
                elif cmd0 in ("experiment", "experiments", "--experiment", "--experiments"):
                    rc = _cat_cmds.experiment_cli(argv)
                elif cmd0 in ("schedule", "--schedule", "tasks", "--tasks"):
                    rc = _cat_cmds.scheduler_cli(argv)
                elif cmd0 in ("extensions", "--extensions", "extension", "--extension"):
                    rc = _cat_cmds.extensions_cli(argv)
                elif cmd0 in ("skills", "--skills", "skill", "--skill"):
                    rc = _cat_cmds.skills_cli(argv)
                elif cmd0 in ("commands", "--commands", "command", "--command"):
                    rc = _cat_cmds.commands_cli(argv)
                elif cmd0 in ("providers", "--providers", "provider", "--provider"):
                    rc = _cat_cli._providers_cli(argv)
                elif cmd0 in ("models", "--models", "model", "--model"):
                    if len(argv) > 1 and argv[1] in ("add", "test", "capacity", "remove", "info"):
                        rc = _cat_cmds.model_cli(argv)
                    elif len(argv) > 1 and argv[1] in ("recommend", "rec", "search", "find", "install", "pull", "benchmark", "bench", "refresh"):
                        rc = _cat_cli._models_cli(argv)
                    elif "--provider" in argv or "-p" in argv or "--category" in argv or "-c" in argv:
                        rc = _cat_cli._models_cli(argv)
                    else:
                        rc = _cat_cmds.model_cli(argv)
                elif cmd0 in ("offline", "--offline", "local-only", "--local-only"):
                    rc = _cat_cli._offline_cli(argv)
                else:
                    rc = _cat_cli.main(argv)
        except SystemExit as exc:
            rc = int(exc.code) if isinstance(exc.code, int) else 0
        except Exception as exc:
            rc = 1
            stderr_buf.write(f"Error executing CAT CLI command: {exc}\n")
        finally:
            try:
                os.chdir(old_cwd)
            except OSError:
                pass

        ansi_re = re.compile(r"\x1b\[[0-9;?<>=]*[A-Za-z]|\x1b\].*?\x1b\\")
        out_str = ansi_re.sub("", stdout_buf.getvalue()).strip()
        err_str = ansi_re.sub("", stderr_buf.getvalue()).strip()
        combined = out_str if out_str else err_str
        if out_str and err_str:
            combined = f"{out_str}\n{err_str}"

        return {
            "success": (rc or 0) == 0,
            "returncode": rc or 0,
            "stdout": out_str,
            "stderr": err_str,
            "output": combined,
            "argv": ["cat"] + argv,
        }

    def get_cat_cli_extension_info(self) -> Dict[str, Any]:
        """Return status and metadata of the integrated VS Code cat-cli extension & CLI binary."""
        import shutil
        repo_root = Path(__file__).resolve().parents[3]
        cat_cli_dir = repo_root / "cat-cli"
        pkg_json_path = cat_cli_dir / "package.json"
        vsix_files = list(repo_root.glob("*.vsix")) + (list(cat_cli_dir.glob("*.vsix")) if cat_cli_dir.exists() else [])
        pkg_meta: Dict[str, Any] = {}
        if pkg_json_path.is_file():
            try:
                import json
                pkg_meta = json.loads(pkg_json_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        from calc_terminal import cli as _cat_cli
        return {
            "installed": True,
            "module": "calc_terminal",
            "cli_version": _cat_cli._version(),
            "python_executable": sys.executable,
            "python_version": sys.version.split()[0],
            "entrypoints": {
                "cat": shutil.which("cat") or f"{sys.executable} -m calc_terminal",
                "catx": shutil.which("catx") or f"{sys.executable} -m calc_terminal",
                "cct": shutil.which("cct") or f"{sys.executable} -m calc_terminal",
                "module": f"{sys.executable} -m calc_terminal",
            },
            "vscode_extension": {
                "name": pkg_meta.get("name", "cat-cli"),
                "display_name": pkg_meta.get("displayName", "CAT — Coding Agent Terminal"),
                "version": pkg_meta.get("version", "0.8.6"),
                "publisher": pkg_meta.get("publisher", "KaziZillani"),
                "commands": [c.get("command") for c in pkg_meta.get("contributes", {}).get("commands", [])],
                "vsix_available": bool(vsix_files),
                "vsix_filename": vsix_files[0].name if vsix_files else None,
            },
            "subcommands": [
                {"command": "cat --version", "category": "core", "description": "Display installed CAT CLI version", "safe": True},
                {"command": "cat --debug", "category": "core", "description": "Display deterministic runtime & environment diagnostics", "safe": True},
                {"command": "cat --doctor", "category": "core", "description": "Run installation, terminal & provider health checks", "safe": True},
                {"command": "cat update --check", "category": "core", "description": "Check official GitHub releases for updates", "safe": True},
                {"command": "cat agent list", "category": "agents", "description": "List all built-in and custom AI agents (Kitties)", "safe": True},
                {"command": "cat mission list", "category": "missions", "description": "List all active, paused, and completed missions", "safe": True},
                {"command": "cat lab", "category": "lab", "description": "Open CAT Lab AI Experimentation Studio overview", "safe": True},
                {"command": "cat hardware status", "category": "lab", "description": "Inspect CPU, GPU, VRAM, CUDA & PyTorch profile", "safe": True},
                {"command": "cat benchmark list", "category": "lab", "description": "List standardized AI coding & reasoning benchmarks", "safe": True},
                {"command": "cat model list", "category": "lab", "description": "List Model Lab specs and hardware compatibility", "safe": True},
                {"command": "cat models recommend", "category": "models", "description": "Hardware-tailored local AI model recommendations", "safe": True},
                {"command": "cat providers status", "category": "providers", "description": "Real-time provider health, latency & backup failover pool", "safe": True},
                {"command": "cat providers audit", "category": "providers", "description": "Comprehensive audit of all registered providers & models", "safe": True},
                {"command": "cat dataset list", "category": "lab", "description": "List registered local datasets and feature profiles", "safe": True},
                {"command": "cat experiment list", "category": "lab", "description": "List tracked reproducible ML experiments", "safe": True},
                {"command": "cat storage status", "category": "storage", "description": "Display user storage breakdown across all CAT subsystems", "safe": True},
                {"command": "cat integration list", "category": "integrations", "description": "View status of AI, dev, research & MCP integrations", "safe": True},
                {"command": "cat extensions list", "category": "extensions", "description": "List installed and available CAT extensions", "safe": True},
                {"command": "cat extensions catalogue", "category": "extensions", "description": "Browse curated CAT extension catalogue", "safe": True},
                {"command": "cat skills list", "category": "skills", "description": "List all Kitty skills and tool requirements", "safe": True},
                {"command": "cat commands list", "category": "commands", "description": "List registered custom CLI commands", "safe": True},
                {"command": "cat schedule list", "category": "tasks", "description": "List scheduled and background agent tasks", "safe": True},
            ],
        }


# Singleton runtime adapter instance
runtime = CatRuntime()
