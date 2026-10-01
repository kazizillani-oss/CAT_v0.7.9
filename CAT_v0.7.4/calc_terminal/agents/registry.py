"""
CAT Agents — Extensible Agent Registry.

Manages built-in, local, imported, and custom agents.
Provides search, creation, editing, duplication, enable/disable toggling,
safe `.cat` export/import, memory isolation, and provider health integration.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Sequence, Union

from .agent_model import (
    AgentSpec,
    AGENT_STATUS_IDLE,
    AGENT_STATUS_RUNNING,
    AGENT_STATUS_THINKING,
    AGENT_STATUS_USING_TOOL,
    AGENT_STATUS_WAITING_PERMISSION,
    AGENT_STATUS_COMPLETED,
    AGENT_STATUS_FAILED,
    AGENT_STATUS_RATE_LIMITED,
    AGENT_STATUS_PROVIDER_ERROR,
    AGENT_STATUS_OFFLINE,
)
from .builtin_agents import BUILTIN_AGENTS
from .. import storage

logger = logging.getLogger("cat.agents.registry")

_REGISTRY_LOCK = threading.RLock()
_INSTANCE: Optional[AgentRegistry] = None


class AgentRegistry:
    """Thread-safe registry for CAT AI agents."""

    def __init__(self, agents_dir: Optional[str] = None):
        self.agents_dir = agents_dir or storage.get_subpath("agents")
        self._builtin: Dict[str, AgentSpec] = copy.deepcopy(BUILTIN_AGENTS)
        self._custom: Dict[str, AgentSpec] = {}
        self._execution_status: Dict[str, str] = {}  # agent_id -> status string
        self._disabled_builtins: set[str] = set()
        self._loaded = False
        os.makedirs(self.agents_dir, exist_ok=True)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with _REGISTRY_LOCK:
            if self._loaded:
                return
            self._load_custom_agents()
            self._load_state_overrides()
            self._loaded = True

    def _load_custom_agents(self) -> None:
        """Discovers and parses custom agent definitions from user storage."""
        if not os.path.isdir(self.agents_dir):
            return

        for fname in os.listdir(self.agents_dir):
            fpath = os.path.join(self.agents_dir, fname)
            if not os.path.isfile(fpath):
                continue

            try:
                if fname.endswith(".cat") or fname.endswith(".catagent"):
                    valid, envelope, err, _ = storage.read_cat_file(fpath)
                    if valid and envelope and envelope.get("type") == "agent":
                        data = envelope.get("data", {})
                        if "id" not in data:
                            data["id"] = envelope.get("id")
                        agent = AgentSpec.from_dict(data)
                        agent.builtin = False
                        self._custom[agent.id] = agent
                elif fname.endswith(".json") and not fname.startswith("_"):
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        agent = AgentSpec.from_dict(data)
                        agent.builtin = False
                        self._custom[agent.id] = agent
            except Exception as e:
                logger.warning(f"Error loading agent file {fname}: {e}")

    def _load_state_overrides(self) -> None:
        """Loads enabled/disabled overrides for built-in agents."""
        state_file = os.path.join(self.agents_dir, "_state.json")
        if os.path.isfile(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                disabled = state.get("disabled_builtins") or []
                self._disabled_builtins = set(disabled)
                for aid in self._disabled_builtins:
                    if aid in self._builtin:
                        self._builtin[aid].enabled = False
            except Exception as e:
                logger.warning(f"Error loading agent states: {e}")

    def _persist_state_overrides(self) -> None:
        state_file = os.path.join(self.agents_dir, "_state.json")
        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({"disabled_builtins": list(self._disabled_builtins)}, f, indent=2)
        except Exception as e:
            logger.warning(f"Error persisting agent states: {e}")

    def register(self, agent: AgentSpec, persist: bool = True) -> AgentSpec:
        """Registers a custom agent. Persists to storage by default."""
        self._ensure_loaded()
        with _REGISTRY_LOCK:
            agent.builtin = False
            self._custom[agent.id] = agent

            if persist:
                self.save_agent(agent)
            return agent

    def save_agent(self, agent: AgentSpec) -> str:
        """Saves a custom agent as a `.cat` file in user storage."""
        safe_id = re.sub(r"[^\w\-.]", "_", agent.id)
        out_path = os.path.join(self.agents_dir, f"{safe_id}.cat")
        storage.export_cat_file(
            obj_type="agent",
            obj_id=agent.id,
            data=agent.to_dict(),
            metadata={"name": agent.name, "description": agent.description},
            out_path=out_path,
        )
        return out_path

    def unregister(self, agent_id: str) -> bool:
        """Deletes a custom agent. Built-in agents cannot be deleted (only disabled)."""
        self._ensure_loaded()
        with _REGISTRY_LOCK:
            if agent_id in self._builtin:
                # Built-ins can only be disabled, not deleted
                return self.disable(agent_id)

            if agent_id in self._custom:
                del self._custom[agent_id]
                # Remove file
                safe_id = re.sub(r"[^\w\-.]", "_", agent_id)
                for ext in (".cat", ".catagent", ".json"):
                    fpath = os.path.join(self.agents_dir, f"{safe_id}{ext}")
                    if os.path.isfile(fpath):
                        try:
                            os.remove(fpath)
                        except OSError:
                            pass
                return True
            return False

    def update(self, agent_id: str, updates: Dict[str, Any]) -> Optional[AgentSpec]:
        """Updates attributes of an existing agent."""
        self._ensure_loaded()
        with _REGISTRY_LOCK:
            agent = self.get(agent_id)
            if not agent:
                return None

            for k, v in updates.items():
                if hasattr(agent, k) and k not in ("id", "builtin"):
                    setattr(agent, k, v)

            if not agent.builtin:
                self.save_agent(agent)
            else:
                if "enabled" in updates:
                    if updates["enabled"]:
                        self._disabled_builtins.discard(agent_id)
                    else:
                        self._disabled_builtins.add(agent_id)
                    self._persist_state_overrides()
            return agent

    def get(self, agent_id: str) -> Optional[AgentSpec]:
        """Look up an agent by ID."""
        self._ensure_loaded()
        with _REGISTRY_LOCK:
            return self._custom.get(agent_id) or self._builtin.get(agent_id)

    def list(self, include_disabled: bool = True, category: Optional[str] = None) -> List[AgentSpec]:
        """Lists all registered agents."""
        self._ensure_loaded()
        with _REGISTRY_LOCK:
            all_agents = list(self._builtin.values()) + list(self._custom.values())
            if not include_disabled:
                all_agents = [a for a in all_agents if a.enabled]
            if category:
                all_agents = [a for a in all_agents if a.category == category]
            return all_agents

    def search(
        self,
        query: str = "",
        mode: Optional[str] = None,
        tool: Optional[str] = None,
        provider: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[AgentSpec]:
        """Searches agents by query string, mode, tool, provider, or tags."""
        self._ensure_loaded()
        q = (query or "").strip().lower()
        results = []

        with _REGISTRY_LOCK:
            for agent in self.list(include_disabled=True):
                # Mode filter
                if mode and mode.lower() != agent.primary_mode.lower() and mode.lower() not in [m.lower() for m in agent.allowed_modes]:
                    continue
                # Tool filter
                if tool and tool.lower() not in [t.lower() for t in agent.tools]:
                    continue
                # Provider filter
                if provider and provider.lower() not in (agent.provider.lower(), "default"):
                    continue
                # Tags filter
                if tags:
                    agent_tags = [t.lower() for t in agent.tags]
                    if not any(t.lower() in agent_tags for t in tags):
                        continue

                # Text query match across name, id, description, tags, tools
                if q:
                    haystack = f"{agent.name} {agent.id} {agent.description} {' '.join(agent.tags)} {' '.join(agent.tools)} {agent.primary_mode} {agent.provider}".lower()
                    if q not in haystack:
                        continue

                results.append(agent)

        return results

    def enable(self, agent_id: str) -> bool:
        """Enables an agent."""
        self._ensure_loaded()
        with _REGISTRY_LOCK:
            agent = self.get(agent_id)
            if not agent:
                return False
            agent.enabled = True
            if agent.builtin:
                self._disabled_builtins.discard(agent_id)
                self._persist_state_overrides()
            else:
                self.save_agent(agent)
            return True

    def disable(self, agent_id: str) -> bool:
        """Disables an agent."""
        self._ensure_loaded()
        with _REGISTRY_LOCK:
            agent = self.get(agent_id)
            if not agent:
                return False
            agent.enabled = False
            if agent.builtin:
                self._disabled_builtins.add(agent_id)
                self._persist_state_overrides()
            else:
                self.save_agent(agent)
            return True

    def duplicate(self, agent_id: str, new_id: str, new_name: str) -> AgentSpec:
        """Duplicates an existing agent with a new ID and name."""
        self._ensure_loaded()
        with _REGISTRY_LOCK:
            src = self.get(agent_id)
            if not src:
                raise ValueError(f"Agent '{agent_id}' does not exist.")

            new_spec = copy.deepcopy(src)
            new_spec.id = new_id
            new_spec.name = new_name
            new_spec.builtin = False
            new_spec.category = "custom"
            self.register(new_spec, persist=True)
            return new_spec

    def export_agent(self, agent_id: str, filepath: Optional[str] = None) -> str:
        """Exports an agent definition to a safe `.cat` file."""
        agent = self.get(agent_id)
        if not agent:
            raise ValueError(f"Agent '{agent_id}' not found.")

        if not filepath:
            safe_id = re.sub(r"[^\w\-.]", "_", agent.id)
            filepath = os.path.join(os.getcwd(), f"{safe_id}.catagent")

        return storage.export_cat_file(
            obj_type="agent",
            obj_id=agent.id,
            data=agent.to_dict(),
            metadata={"name": agent.name, "description": agent.description},
            out_path=filepath,
        )

    def import_agent(self, filepath_or_content: Union[str, dict], force: bool = False) -> AgentSpec:
        """Imports an agent from a `.cat` / `.catagent` / JSON file or dictionary safely.

        Never runs arbitrary code and validates all capabilities.
        """
        if isinstance(filepath_or_content, dict):
            envelope = filepath_or_content
        else:
            valid, envelope, err, warnings = storage.read_cat_file(filepath_or_content)
            if not valid or not envelope:
                # Try raw JSON fallback
                with open(filepath_or_content, "r", encoding="utf-8") as f:
                    envelope = json.load(f)

        if envelope.get("format") == "cat" and envelope.get("type") == "agent":
            data = envelope.get("data", {})
        else:
            data = envelope

        agent = AgentSpec.from_dict(data)
        agent.builtin = False

        existing = self.get(agent.id)
        if existing and not force:
            agent.id = f"{agent.id}-copy"
            agent.name = f"{agent.name} (Imported)"

        self.register(agent, persist=True)
        return agent

    # ── Execution Status & Provider Health Integration ─────────────────────────
    def set_execution_status(self, agent_id: str, status: str) -> None:
        with _REGISTRY_LOCK:
            self._execution_status[agent_id] = status

    def get_agent_status(self, agent_id: str) -> Dict[str, Any]:
        """Returns comprehensive real-time status for an agent."""
        agent = self.get(agent_id)
        if not agent:
            return {"status": AGENT_STATUS_OFFLINE, "error": f"Agent {agent_id} not found"}

        exec_status = self._execution_status.get(agent_id, AGENT_STATUS_IDLE)

        # Inspect provider health
        prov = agent.provider
        model = agent.model
        health_info = {"provider": prov, "model": model, "healthy": True, "details": "Ready"}

        try:
            from ..providers import provider_manager as pm
            from ..resilience.health_monitor import get_health_monitor
            from .. import aicore

            if prov in ("default", ""):
                cfg = aicore.load_config() or {}
                prov = cfg.get("provider", "openai")
                if not model:
                    model = cfg.get("model", "")

            mon = get_health_monitor()
            badge, lbl = mon.get_status_badge(prov, model)
            h = mon.get_health(prov, model)
            health_info["provider"] = prov
            health_info["model"] = model
            health_info["healthy"] = h.healthy
            health_info["latency_ms"] = h.latency_ms
            health_info["status_label"] = lbl

            # Inspect backup providers for this agent
            backups = pm.load_backup_providers()
            health_info["backup_pool_count"] = len(backups)
            health_info["backup_available"] = bool(backups)
        except Exception:
            pass

        return {
            "agent_id": agent.id,
            "name": agent.name,
            "status": exec_status,
            "enabled": agent.enabled,
            "primary_mode": agent.primary_mode,
            "provider_info": health_info,
        }

    # ── Memory Integration ───────────────────────────────────────────────────
    def get_agent_memory(self, agent_id: str, scope: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves memories isolated for this agent."""
        mem_dir = storage.get_subpath("memory", "agents", agent_id)
        if not os.path.isdir(mem_dir):
            return []

        memories = []
        for fname in os.listdir(mem_dir):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(mem_dir, fname), "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if not scope or data.get("scope") == scope:
                        memories.append(data)
                except Exception:
                    pass
        return memories

    def clear_agent_memory(self, agent_id: str) -> int:
        """Clears memory stored for this agent."""
        mem_dir = storage.get_subpath("memory", "agents", agent_id)
        count = 0
        if os.path.isdir(mem_dir):
            for fname in os.listdir(mem_dir):
                fpath = os.path.join(mem_dir, fname)
                try:
                    os.remove(fpath)
                    count += 1
                except OSError:
                    pass
        return count


def get_agent_registry() -> AgentRegistry:
    """Returns the singleton AgentRegistry."""
    global _INSTANCE
    if _INSTANCE is None:
        with _REGISTRY_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AgentRegistry()
    return _INSTANCE
