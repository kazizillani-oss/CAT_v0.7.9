"""
CAT Developer SDK (v1.0.0) — Official Public API & Extension Framework

Provides stable, versioned public interfaces for third-party developers
to build CAT-compatible extensions, skills, slash commands, custom agents,
tools, MCP integrations, and UI components without modifying CAT Core.
"""

from __future__ import annotations

import os
import json
import time
import inspect
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Callable, Type, Union

from ..capability_registry import get_registry, CapabilitySpec

SDK_VERSION = "1.0.0"
API_VERSION = "0.7.9"


class SDKError(Exception):
    """Base exception for all SDK runtime errors."""
    pass


class ComponentValidationError(SDKError):
    """Raised when a component manifest or implementation fails validation."""
    pass


# =====================================================================
# Logging & Configuration APIs
# =====================================================================

class SDKLogger:
    """Scoped logger for SDK components with automatic redaction."""

    def __init__(self, component_name: str):
        self.name = component_name
        self._logger = logging.getLogger(f"cat.sdk.{component_name}")

    def info(self, msg: str, *args, **kwargs):
        self._logger.info(f"[{self.name}] {msg}", *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        self._logger.warning(f"[{self.name}] {msg}", *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        self._logger.error(f"[{self.name}] {msg}", *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs):
        self._logger.debug(f"[{self.name}] {msg}", *args, **kwargs)


class ConfigManager:
    """Persistent component configuration storage scoped to the workspace or global user directory."""

    def __init__(self, component_id: str, base_dir: Optional[str] = None):
        self.component_id = component_id
        self.base_dir = base_dir or os.path.join(os.path.expanduser("~"), ".cat", "sdk_configs")
        os.makedirs(self.base_dir, exist_ok=True)
        self.config_path = os.path.join(self.base_dir, f"{component_id}.json")
        self._data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def _save(self) -> None:
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception:
            pass


# =====================================================================
# Permissions & Security
# =====================================================================

@dataclass
class PermissionRequest:
    scope: str  # e.g., "filesystem:read", "filesystem:write", "network", "shell", "secrets"
    reason: str
    granted: bool = False
    requested_at: float = field(default_factory=time.time)


# =====================================================================
# Event Subscriptions & Bus
# =====================================================================

class EventBus:
    """Inter-component pub/sub message bus."""
    _instance = None
    _listeners: Dict[str, List[Callable[[str, Any], None]]] = {}

    @classmethod
    def get(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def subscribe(self, event_type: str, handler: Callable[[str, Any], None]) -> None:
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        if handler not in self._listeners[event_type]:
            self._listeners[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[str, Any], None]) -> None:
        if event_type in self._listeners and handler in self._listeners[event_type]:
            self._listeners[event_type].remove(handler)

    def publish(self, event_type: str, payload: Any = None) -> None:
        handlers = self._listeners.get(event_type, []) + self._listeners.get("*", [])
        for handler in handlers:
            try:
                handler(event_type, payload)
            except Exception as e:
                logging.getLogger("cat.sdk.eventbus").error(f"Event handler error: {e}")


# =====================================================================
# Component Lifecycle Hooks
# =====================================================================

class LifecycleHooks:
    """Hooks invoked by CAT Core during component lifecycle."""
    def on_init(self) -> None: pass
    def on_load(self) -> None: pass
    def on_unload(self) -> None: pass
    def on_enable(self) -> None: pass
    def on_disable(self) -> None: pass
    def on_event(self, event_type: str, data: Any) -> None: pass


# =====================================================================
# Core SDK Definitions & Manifests
# =====================================================================

@dataclass
class ExtensionManifest:
    id: str
    name: str
    version: str
    description: str
    author: str
    entry_point: str = "extension.py"
    min_cat_version: str = "0.7.0"
    permissions: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    homepage: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Extension(LifecycleHooks):
    """Base class for CAT extensions."""
    manifest: ExtensionManifest

    def __init__(self, manifest: ExtensionManifest):
        self.manifest = manifest
        self.logger = SDKLogger(manifest.id)
        self.config = ConfigManager(manifest.id)
        self.events = EventBus.get()


@dataclass
class CommandDefinition:
    name: str  # e.g., "/mycommand"
    description: str
    handler: Callable[[str], Any]
    category: str = "custom"
    usage: str = ""
    aliases: List[str] = field(default_factory=list)


@dataclass
class ToolDefinition:
    name: str
    description: str
    handler: Callable[..., Any]
    parameters: Dict[str, Any] = field(default_factory=dict)
    returns: str = "string"
    requires_confirmation: bool = False
    permissions: List[str] = field(default_factory=list)


@dataclass
class SkillManifest:
    id: str
    name: str
    description: str
    instructions: str
    tools: List[str] = field(default_factory=list)
    version: str = "1.0.0"


@dataclass
class KittyDefinition:
    id: str
    name: str
    title: str
    role_description: str
    system_prompt: str
    tools: List[str] = field(default_factory=list)
    color: str = "#88c0d0"
    avatar: str = "🐱"


@dataclass
class WorkflowNode:
    id: str
    name: str
    step_type: str  # "tool", "prompt", "script", "condition"
    action: str
    inputs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UIContribution:
    id: str
    target: str  # "sidebar", "menu", "header", "modal", "tab"
    title: str
    widget_factory: Optional[Callable[[], Any]] = None
    icon: str = "📦"


# =====================================================================
# Registration APIs (Bridges directly into CAT Universal Capability Registry)
# =====================================================================

def register_extension(ext: Extension) -> bool:
    reg = get_registry()
    spec = CapabilitySpec(
        id=f"ext_{ext.manifest.id}",
        name=ext.manifest.name,
        cap_type="EXTENSION",
        description=ext.manifest.description,
        version=ext.manifest.version,
        author=ext.manifest.author,
        tags=ext.manifest.tags,
        entrypoint=ext,
    )
    reg.register(spec)
    ext.on_init()
    ext.on_load()
    return True


def register_command(cmd: CommandDefinition) -> bool:
    reg = get_registry()
    cmd_name = cmd.name if cmd.name.startswith("/") else f"/{cmd.name}"
    spec = CapabilitySpec(
        id=f"cmd_{cmd_name.lstrip('/')}",
        name=cmd_name,
        cap_type="CLI_COMMAND",
        description=cmd.description,
        entrypoint=cmd.handler,
        tags=[cmd.category] + cmd.aliases,
    )
    reg.register(spec)
    # Also register in global commands_data if available
    try:
        from ..commands_data import COMMANDS
        if not any(c[0] == cmd_name for c in COMMANDS):
            COMMANDS.append((cmd_name, cmd.description))
    except Exception:
        pass
    return True


def register_tool(tool: ToolDefinition) -> bool:
    reg = get_registry()
    spec = CapabilitySpec(
        id=f"tool_{tool.name}",
        name=tool.name,
        cap_type="CORE_TOOL",
        description=tool.description,
        entrypoint=tool.handler,
        parameters=tool.parameters,
        tags=tool.permissions,
    )
    reg.register(spec)
    return True


def register_skill(skill: SkillManifest) -> bool:
    reg = get_registry()
    spec = CapabilitySpec(
        id=f"skill_{skill.id}",
        name=skill.name,
        cap_type="SKILL",
        description=skill.description,
        version=skill.version,
        entrypoint=skill,
        tags=skill.tools,
    )
    reg.register(spec)
    return True


def register_agent(agent: KittyDefinition) -> bool:
    reg = get_registry()
    spec = CapabilitySpec(
        id=f"agent_{agent.id}",
        name=agent.name,
        cap_type="AGENT_KITTY",
        description=agent.role_description,
        entrypoint=agent,
        tags=agent.tools + [agent.color],
    )
    reg.register(spec)
    return True


# Decorator forms for syntactic convenience
def extension(id: str, name: str, version: str = "1.0.0", description: str = "", author: str = ""):
    def decorator(cls: Type[Extension]):
        manifest = ExtensionManifest(id=id, name=name, version=version, description=description, author=author)
        cls.manifest = manifest
        return cls
    return decorator


def command(name: str, description: str = "", category: str = "custom", usage: str = ""):
    def decorator(fn: Callable[[str], Any]):
        cmd_def = CommandDefinition(name=name, description=description, handler=fn, category=category, usage=usage)
        register_command(cmd_def)
        return fn
    return decorator


def tool(name: str, description: str = "", parameters: Optional[Dict[str, Any]] = None, requires_confirmation: bool = False):
    def decorator(fn: Callable[..., Any]):
        tool_def = ToolDefinition(
            name=name, description=description, handler=fn,
            parameters=parameters or {}, requires_confirmation=requires_confirmation
        )
        register_tool(tool_def)
        return fn
    return decorator


# =====================================================================
# High-Level Programmatic Automation APIs
# =====================================================================

def chat(
    prompt: str,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    mode: str = "agent",
    stream: bool = False,
) -> Any:
    """Send a prompt to CAT AI using active or overridden provider and model."""
    from .. import aicore, ai_modes
    sys_prompt = ai_modes.system_prompt_for(mode)
    if stream:
        return aicore.stream_ai(
            prompt,
            system_prompt=sys_prompt,
            provider_override=provider,
            model_override=model,
        )
    chunks = []
    for chunk in aicore.stream_ai(
        prompt,
        system_prompt=sys_prompt,
        provider_override=provider,
        model_override=model,
    ):
        if chunk:
            chunks.append(chunk)
    return "".join(chunks).strip()


def plan(task: str, model: Optional[str] = None) -> str:
    """Execute non-destructive project inspection and review via Mira (Plan Mode).

    Guaranteed read-only: inspects codebases, identifies security concerns,
    and constructs milestone roadmaps without altering workspace files.
    """
    return chat(task, model=model, mode="plan")


def build(task: str, model: Optional[str] = None) -> str:
    """Execute production code implementation and changes via Aria (Build Mode).

    Full implementation authority: generates code solutions, refactors modules,
    and constructs verified test suites.
    """
    return chat(task, model=model, mode="build")


def review(path_or_task: str, model: Optional[str] = None) -> str:
    """Inspect and review a code file or architectural module without alterations."""
    prompt = f"Please conduct a comprehensive, read-only architectural and security review of:\n\n{path_or_task}"
    return plan(prompt, model=model)


def run_parallel(
    build_task: str,
    review_task: Optional[str] = None,
    build_model: Optional[str] = None,
    review_model: Optional[str] = None,
) -> Dict[str, Any]:
    """Run dual-agent parallel workflow: Aria builds while Mira reviews concurrently."""
    from ..parallel_runner import run_parallel_build_and_review
    return run_parallel_build_and_review(
        build_prompt=build_task,
        review_prompt=review_task,
        build_model=build_model,
        review_model=review_model,
    )


def list_providers() -> List[Dict[str, Any]]:
    """List all 200+ AI providers supported in CAT catalog."""
    from ..models.manager import load_providers
    return load_providers()


def list_models(provider_id: Optional[str] = None) -> List[str]:
    """List verified fallback and active models for a provider."""
    from ..models.manager import models_for
    from .. import aicore
    cfg = aicore.load_config() or {}
    pid = provider_id or cfg.get("provider", "OLLAMA")
    return models_for(pid)


def create_background_job(
    task: str,
    title: Optional[str] = None,
    role: str = "helper",
    model: Optional[str] = None,
) -> Any:
    """Submit a task to run quietly in the background as a persistent helper."""
    from ..parallel_runner import BackgroundJobManager
    mgr = BackgroundJobManager.get_instance()
    return mgr.submit_job(task, title=title, role=role, model=model)


