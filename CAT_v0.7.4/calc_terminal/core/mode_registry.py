"""
CAT Custom Mode Engine & Registry per §2, §3, §55:
- Preserves the default AI modes (Notebook, Research, Plan, Build, Debugger, Agent)
- Supports user-created custom modes (e.g. BioLab, QuantumResearch, MLTrainer)
- Modes request capabilities from Capability Bus, never duplicating tool logic.
- Modes are installable, removable, editable, exportable, importable, validated, and permission-controlled.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple, Union


CUSTOM_MODES_PATH = os.path.join(os.path.expanduser("~"), ".cct_custom_modes.json")

# Default immutable modes per §2
DEFAULT_MODE_KEYS = ("notebook", "research", "plan", "build", "debugger", "agent")


@dataclass
class ModeBehavior:
    planning: str = "standard"  # standard, high, adaptive
    verification: str = "standard"  # standard, strict, relaxed
    citations: str = "optional"  # required, optional, none
    experiment_tracking: bool = False
    coding: str = "standard"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ModeSpec:
    name: str
    description: str = ""
    inherits: List[str] = field(default_factory=lambda: ["notebook"])
    capabilities: List[str] = field(default_factory=list)
    behavior: ModeBehavior = field(default_factory=ModeBehavior)
    permissions: List[str] = field(default_factory=list)
    preferred_models: List[str] = field(default_factory=list)
    backup_models: List[str] = field(default_factory=list)
    accent_hex: str = "#38bdf8"
    icon: str = "●"
    system_prompt: str = ""
    enabled: bool = True
    custom: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inherits": self.inherits,
            "capabilities": self.capabilities,
            "behavior": self.behavior.to_dict() if isinstance(self.behavior, ModeBehavior) else self.behavior,
            "permissions": self.permissions,
            "preferred_models": self.preferred_models,
            "backup_models": self.backup_models,
            "accent_hex": self.accent_hex,
            "icon": self.icon,
            "system_prompt": self.system_prompt,
            "enabled": self.enabled,
            "custom": self.custom,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModeSpec:
        beh_data = data.get("behavior", {})
        if isinstance(beh_data, dict):
            behavior = ModeBehavior(
                planning=beh_data.get("planning", "standard"),
                verification=beh_data.get("verification", "standard"),
                citations=beh_data.get("citations", "optional"),
                experiment_tracking=bool(beh_data.get("experiment_tracking", False)),
                coding=beh_data.get("coding", "standard"),
            )
        else:
            behavior = ModeBehavior()

        return cls(
            name=data["name"],
            description=data.get("description", ""),
            inherits=data.get("inherits", ["notebook"]),
            capabilities=data.get("capabilities", []),
            behavior=behavior,
            permissions=data.get("permissions", []),
            preferred_models=data.get("preferred_models", []),
            backup_models=data.get("backup_models", []),
            accent_hex=data.get("accent_hex", "#38bdf8"),
            icon=data.get("icon", "●"),
            system_prompt=data.get("system_prompt", ""),
            enabled=bool(data.get("enabled", True)),
            custom=bool(data.get("custom", True)),
        )


class ModeRegistry:
    """Registry managing custom user modes alongside project default modes."""

    def __init__(self, storage_path: str = CUSTOM_MODES_PATH):
        self.storage_path = storage_path
        self._custom_modes: Dict[str, ModeSpec] = {}
        self.load()

    def is_default_mode(self, name: str) -> bool:
        return name.strip().lower() in DEFAULT_MODE_KEYS

    def validate_mode(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        name = data.get("name", "").strip()
        if not name:
            errors.append("Mode name cannot be empty")
        elif not re.match(r"^[A-Za-z0-9_\-]+$", name):
            errors.append("Mode name must be alphanumeric with dashes or underscores only")
        elif self.is_default_mode(name):
            errors.append(f"Cannot overwrite default mode '{name}'")
        return (len(errors) == 0), errors

    def register_mode(
        self,
        spec: Optional[ModeSpec] = None,
        persist: bool = True,
        name: str = "",
        description: str = "",
        system_prompt: str = "",
        icon: str = "●",
        capabilities: Optional[List[str]] = None,
        inherits: Optional[str] = "agent",
    ) -> Tuple[bool, str]:
        if spec is None:
            spec = ModeSpec(
                name=name,
                description=description,
                system_prompt=system_prompt,
                icon=icon,
                capabilities=capabilities or [],
                inherits=inherits,
            )

        canonical = spec.name.strip().lower()
        if self.is_default_mode(canonical):
            return False, f"Cannot overwrite default mode '{spec.name}'"

        ok, errs = self.validate_mode(spec.to_dict())
        if not ok:
            return False, "; ".join(errs)

        self._custom_modes[canonical] = spec
        if persist:
            self.save()
        self._sync_with_ai_modes()
        return True, f"Mode '{spec.name}' registered successfully"

    def unregister_mode(self, name: str) -> Tuple[bool, str]:
        canonical = name.strip().lower()
        if self.is_default_mode(canonical):
            return False, f"Cannot delete default mode '{name}'"
        if canonical not in self._custom_modes:
            return False, f"Custom mode '{name}' not found"

        del self._custom_modes[canonical]
        self.save()
        self._sync_with_ai_modes()
        return True, f"Mode '{name}' removed successfully"

    def get_mode(self, name: str) -> Optional[ModeSpec]:
        """Lookup mode by exact or case-insensitive name."""
        canonical = (name or "").strip().lower()
        return self._custom_modes.get(canonical)

    def resolve_mode_name(self, query: str) -> Optional[str]:
        """Resolve a mode name from typed command or natural language (e.g., 'Use BioLab mode')."""
        if not query:
            return None
        clean = query.strip()
        # Direct check
        low = clean.lower().lstrip("/")
        if low in DEFAULT_MODE_KEYS:
            return low
        if low in self._custom_modes:
            return self._custom_modes[low].name

        # Natural language pattern check: e.g. "Use BioLab mode", "switch to Quantum mode"
        m = re.search(r"(?:use|switch to|enter|mode)\s+([A-Za-z0-9_\-]+)", clean, re.IGNORECASE)
        if m:
            cand = m.group(1).lower()
            if cand in DEFAULT_MODE_KEYS:
                return cand
            if cand in self._custom_modes:
                return self._custom_modes[cand].name

        return None

    def list_modes(self, include_defaults: bool = True) -> List[Dict[str, Any]]:
        modes = []
        if include_defaults:
            try:
                from .. import ai_modes
                for k in ai_modes.MODE_ORDER:
                    m = ai_modes.meta(k)
                    modes.append({
                        "name": m.get("label", k.title()),
                        "key": k,
                        "description": m.get("purpose", ""),
                        "icon": m.get("icon", "●"),
                        "default": True,
                        "enabled": True,
                    })
            except Exception:
                for k in DEFAULT_MODE_KEYS:
                    modes.append({"name": k.title(), "key": k, "default": True, "enabled": True})

        for spec in self._custom_modes.values():
            modes.append({
                "name": spec.name,
                "key": spec.name.lower(),
                "description": spec.description,
                "icon": spec.icon,
                "default": False,
                "enabled": spec.enabled,
                "capabilities": spec.capabilities,
                "inherits": spec.inherits,
            })
        return modes

    def export_mode(self, name: str, output_path: str) -> Tuple[bool, str]:
        spec = self.get_mode(name)
        if not spec:
            return False, f"Mode '{name}' not found"
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(spec.to_dict(), f, indent=2)
            return True, f"Exported mode '{name}' to {output_path}"
        except Exception as e:
            return False, f"Export failed: {e}"

    def import_mode(self, source: Union[str, Dict[str, Any]]) -> Tuple[bool, str]:
        try:
            if isinstance(source, str):
                if os.path.exists(source):
                    with open(source, "r", encoding="utf-8") as f:
                        data = json.load(f)
                else:
                    data = json.loads(source)
            else:
                data = source
            spec = ModeSpec.from_dict(data)
            return self.register_mode(spec)
        except Exception as e:
            return False, f"Import failed: {e}"

    def save(self) -> None:
        try:
            data = {k: spec.to_dict() for k, spec in self._custom_modes.items()}
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def load(self) -> None:
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k, v in data.items():
                    if not self.is_default_mode(k):
                        self._custom_modes[k.lower()] = ModeSpec.from_dict(v)
            self._sync_with_ai_modes()
        except Exception:
            pass

    def _sync_with_ai_modes(self) -> None:
        """Dynamically synchronize registered custom modes into ai_modes.MODE_META."""
        try:
            from .. import ai_modes
            for spec in self._custom_modes.values():
                if not spec.enabled:
                    continue
                k = spec.name.lower()
                rgb = ai_modes._hex_to_rgb(spec.accent_hex) or (140, 140, 240)
                ai_modes.MODE_META[k] = {
                    "label": spec.name,
                    "icon": spec.icon,
                    "accent": rgb,
                    "purpose": spec.description or f"Custom mode {spec.name}",
                    "gradient": ai_modes._auto_gradient(rgb),
                    "custom_spec": spec,
                }
                if k not in ai_modes.MODE_ORDER:
                    ai_modes.MODE_ORDER.append(k)
        except Exception:
            pass


mode_registry = ModeRegistry()
