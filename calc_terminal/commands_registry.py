"""
CAT Custom Commands Registry — Manages Extension & User CLI Commands.

Provides registration, collision prevention against core CAT CLI commands,
argument validation, permission scoping, and execution dispatching.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import storage

logger = logging.getLogger("cat.commands.registry")

_LOCK = threading.RLock()
_REGISTRY_INSTANCE: Optional[CustomCommandRegistry] = None

# Core CAT CLI commands reserved to prevent collisions
BUILTIN_COMMANDS: set[str] = {
    "agent", "agents",
    "mission", "missions",
    "storage", "backup", "restore",
    "integrations", "integration",
    "experiment", "experiments",
    "models", "model",
    "providers", "provider",
    "offline",
    "terminal", "cli", "console",
    "hardware", "lab", "benchmark", "benchmarks", "dataset", "datasets",
    "doctor",
    "browse", "open", "view", "preview", "viewer", "cat-browser",
    "fatty", "web", "pwa", "server", "mascot", "mascots",
    "fomoji", "auth", "signout", "logout",
    "vision",
    "update", "rollback", "repair",
    "import", "export",
    "help", "version",
    "extensions", "extension",
    "skills", "skill",
    "commands", "command",
    "curl", "brew", "sudo",
}


@dataclass
class CommandSpec:
    id: str                                  # Unique identifier: e.g. "github-flow.review"
    name: str                                # CLI command trigger: e.g. "review-pr"
    description: str = ""
    extension_id: str = ""                   # Sponsoring extension ID
    usage: str = ""                          # e.g. "cat review-pr <pr-number>"
    args_spec: List[Dict[str, Any]] = field(default_factory=list)  # [{"name": "pr", "required": True}]
    script_path: Optional[str] = None        # Script to execute
    handler: Optional[Callable] = None       # Python callable if in-process
    permissions: List[str] = field(default_factory=list)  # ["read_files", "network"]
    enabled: bool = True
    builtin: bool = False
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "extension_id": self.extension_id,
            "usage": self.usage or f"cat {self.name}",
            "args_spec": self.args_spec,
            "script_path": self.script_path,
            "permissions": self.permissions,
            "enabled": self.enabled,
            "builtin": self.builtin,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CommandSpec:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            extension_id=data.get("extension_id", ""),
            usage=data.get("usage", ""),
            args_spec=data.get("args_spec", []),
            script_path=data.get("script_path"),
            permissions=data.get("permissions", []),
            enabled=data.get("enabled", True),
            builtin=data.get("builtin", False),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


class CustomCommandRegistry:
    """Thread-safe registry for extension-provided and user CLI commands."""

    def __init__(self, registry_file: Optional[Path] = None):
        self.registry_file = registry_file or (Path(storage.get_subpath("commands")) / "registry.json")
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        self._commands: Dict[str, CommandSpec] = {}
        self._load()

    def _load(self) -> None:
        with _LOCK:
            if self.registry_file.exists():
                try:
                    with open(self.registry_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        for k, v in data.items():
                            if isinstance(v, dict):
                                spec = CommandSpec.from_dict(v)
                                self._commands[spec.name.lower()] = spec
                except Exception as e:
                    logger.warning(f"Failed to load commands registry from {self.registry_file}: {e}")

    def _save(self) -> None:
        with _LOCK:
            try:
                payload = {k: v.to_dict() for k, v in self._commands.items() if not v.builtin}
                with open(self.registry_file, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save commands registry: {e}")

    def validate_command(self, spec: CommandSpec) -> Tuple[bool, Optional[str]]:
        """Validate command specification and detect collisions with built-ins."""
        if not spec.id or not spec.id.strip():
            return False, "Command ID cannot be empty."
        clean_name = (spec.name or "").strip().lower()
        if not clean_name:
            return False, "Command name cannot be empty."
        if not re.match(r"^[a-z0-9_\-]+$", clean_name):
            return False, f"Command name '{clean_name}' must be alphanumeric with dashes or underscores."
        
        # Check collision against built-in CAT CLI commands
        if clean_name in BUILTIN_COMMANDS:
            return False, (
                f"COMMAND_COLLISION_ERROR: Command '{clean_name}' conflicts with a core CAT built-in command. "
                f"Please choose a distinct command name or prefix (e.g. 'ext-{clean_name}')."
            )
        return True, None

    def register(self, spec: CommandSpec, persist: bool = True) -> Tuple[bool, Optional[str]]:
        """Register a command with collision validation."""
        valid, err = self.validate_command(spec)
        if not valid:
            return False, err

        clean_name = spec.name.strip().lower()
        with _LOCK:
            # Check if already registered by another extension
            existing = self._commands.get(clean_name)
            if existing and existing.id != spec.id and existing.extension_id != spec.extension_id:
                return False, (
                    f"Command '{clean_name}' is already registered by extension '{existing.extension_id}'. "
                    f"Use a distinct command name."
                )

            spec.updated_at = time.time()
            self._commands[clean_name] = spec
            if persist:
                self._save()
        return True, None

    def unregister(self, command_name: str) -> bool:
        """Unregister a command by name."""
        clean = (command_name or "").strip().lower()
        with _LOCK:
            if clean in self._commands:
                del self._commands[clean]
                self._save()
                return True
            return False

    def unregister_by_extension(self, extension_id: str) -> int:
        """Remove all commands provided by an extension."""
        removed = 0
        with _LOCK:
            to_del = [k for k, v in self._commands.items() if v.extension_id == extension_id]
            for k in to_del:
                del self._commands[k]
                removed += 1
            if removed:
                self._save()
        return removed

    def get(self, command_name: str) -> Optional[CommandSpec]:
        """Lookup command by name (case-insensitive)."""
        clean = (command_name or "").strip().lower()
        with _LOCK:
            return self._commands.get(clean)

    def list_commands(self, include_disabled: bool = False, extension_id: Optional[str] = None) -> List[CommandSpec]:
        """List registered commands, optionally filtering by extension or disabled status."""
        with _LOCK:
            res = list(self._commands.values())
            if not include_disabled:
                res = [c for c in res if c.enabled]
            if extension_id:
                res = [c for c in res if c.extension_id == extension_id]
            return sorted(res, key=lambda c: c.name)

    def set_enabled(self, command_name: str, enabled: bool) -> bool:
        """Enable or disable a command."""
        clean = (command_name or "").strip().lower()
        with _LOCK:
            cmd = self._commands.get(clean)
            if cmd:
                cmd.enabled = bool(enabled)
                cmd.updated_at = time.time()
                self._save()
                return True
            return False

    def set_extension_enabled(self, extension_id: str, enabled: bool) -> int:
        """Enable or disable all commands owned by an extension."""
        count = 0
        with _LOCK:
            for cmd in self._commands.values():
                if cmd.extension_id == extension_id:
                    cmd.enabled = bool(enabled)
                    cmd.updated_at = time.time()
                    count += 1
            if count:
                self._save()
        return count

    def dispatch(self, argv: List[str]) -> int:
        """Execute a custom command."""
        if not argv:
            print("Error: No command specified.", file=sys.stderr)
            return 1

        cmd_name = argv[0].strip().lower()
        cmd = self.get(cmd_name)
        if not cmd:
            print(f"Error: Command '{cmd_name}' not found.", file=sys.stderr)
            return 1

        if not cmd.enabled:
            print(
                f"Error: Command '{cmd_name}' is currently disabled (provided by '{cmd.extension_id}').\n"
                f"Enable it with: cat extensions enable {cmd.extension_id}",
                file=sys.stderr
            )
            return 1

        # Check for help flag
        if len(argv) > 1 and argv[1] in ("--help", "-h", "help"):
            print(f"Usage: {cmd.usage or f'cat {cmd.name}'}")
            if cmd.description:
                print(f"\n{cmd.description}")
            if cmd.args_spec:
                print("\nArguments:")
                for arg in cmd.args_spec:
                    req = " (required)" if arg.get("required") else " (optional)"
                    print(f"  {arg.get('name', 'arg')}{req}: {arg.get('description', '')}")
            if cmd.permissions:
                print(f"\nRequired Permissions: {', '.join(cmd.permissions)}")
            print(f"\nProvided by Extension: {cmd.extension_id}")
            return 0

        # Execute in-process callable if available
        if cmd.handler and callable(cmd.handler):
            try:
                res = cmd.handler(argv[1:])
                return int(res) if isinstance(res, int) else 0
            except Exception as e:
                print(f"Error executing command '{cmd_name}': {e}", file=sys.stderr)
                return 1

        # Execute external script if specified
        if cmd.script_path and os.path.exists(cmd.script_path):
            try:
                ext = Path(cmd.script_path).suffix.lower()
                if ext == ".py":
                    cmd_line = [sys.executable, cmd.script_path] + argv[1:]
                else:
                    cmd_line = [cmd.script_path] + argv[1:]
                proc = subprocess.run(cmd_line)
                return proc.returncode
            except Exception as e:
                print(f"Error running command script '{cmd.script_path}': {e}", file=sys.stderr)
                return 1

        print(f"Command '{cmd_name}' has no executable target.", file=sys.stderr)
        return 1


def get_command_registry() -> CustomCommandRegistry:
    """Singleton getter for the command registry."""
    global _REGISTRY_INSTANCE
    with _LOCK:
        if _REGISTRY_INSTANCE is None:
            _REGISTRY_INSTANCE = CustomCommandRegistry()
        return _REGISTRY_INSTANCE
