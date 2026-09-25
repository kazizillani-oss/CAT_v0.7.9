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
    _CAT_ROOT = Path(__file__).parent.parent
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
                "customization", "extensions", "vision", "diagnostics", "fomoji_auth"
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
            prov = cfg.get("provider", "ollama")
            mod = cfg.get("model", "deepseek-r1")
            try:
                ok = aicore.verify_connection(prov, config=cfg)
                status = "✓ Connection Successful" if ok else "⚠ Connection Failed"
            except Exception as e:
                status = f"⚠ Verification Error: {e}"
            return {"command": base, "output": f"AI Connectivity Test for {prov.upper()} ({mod}): {status}"}

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


# Singleton runtime adapter instance
runtime = CatRuntime()
