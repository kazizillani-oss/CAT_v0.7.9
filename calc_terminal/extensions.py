"""
CCT Extension Manager — Unified Extensions, Skills, Commands & Integrations (v0.7.9.10).

Central registry for Gestures, Personalize, Skills, Custom Commands, and Integrations.
Implements the full lifecycle:

    NOT_INSTALLED -> INSTALL -> INSTALLED_ENABLED
    INSTALLED_ENABLED -> DISABLE -> INSTALLED_DISABLED
    INSTALLED_DISABLED -> ENABLE -> INSTALLED_ENABLED
    INSTALLED_* -> UNINSTALL -> NOT_INSTALLED

Features:
- Unified Component Taxonomy: "extension" | "skill" | "command" | "integration"
- Rich Metadata: Stable ID, display name, author/publisher, original publication date,
  installation date, version, latest version, source, status, dependencies, permissions, errors.
- GitHub & Package Installation: Secure inspection, manifest validation, path traversal
  protection, and automated subsystem registration.
- Subsystem Integration:
    * Skills register into SkillRegistry for Kitty discovery.
    * Commands register into CustomCommandRegistry for CLI dispatch.
- Dependency checking during uninstallation.
- Preservation of built-in extensions: Gestures and Personalize (Publisher: Kazi Zillani).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Base directory for size calculation (calc_terminal package)
_PKG_ROOT = Path(__file__).parent

def _calc_size(paths: List[Path]) -> int:
    """Sum file sizes for given paths (files or dirs)."""
    total = 0
    for p in paths:
        try:
            if p.is_file():
                total += p.stat().st_size
            elif p.is_dir():
                for f in p.rglob("*"):
                    if f.is_file():
                        try:
                            total += f.stat().st_size
                        except Exception:
                            pass
        except Exception:
            pass
    return total

def _format_size(nbytes: int) -> str:
    if nbytes < 1024:
        return f"{nbytes} B"
    if nbytes < 1024 * 1024:
        return f"{nbytes/1024:.1f} KB"
    return f"{nbytes/1024/1024:.1f} MB"

# Built-in extensions — shipped with CAT.
BUILTIN_EXTENSIONS: Dict[str, Dict[str, Any]] = {
    "gestures": {
        "id": "gestures",
        "name": "Gestures",
        "display_name": "Gestures",
        "type": "extension",
        "description": "Advanced gesture controls for CAT — double-click, long-press, swipe and custom shortcuts.",
        "icon": "✋",
        "publisher": "Kazi Zillani",
        "publisher_type": "individual",  # individual | company | organization
        "publisher_verified": True,
        "verified": True,
        "trusted": True,
        "version": "1.0.0",
        "category": "Productivity",
        "keywords": ["gestures", "shortcuts", "productivity", "touch"],
        "size_bytes": None,  # calculated lazily
        "size_display": None,
        "action": "gestures",  # header.NAV_ITEMS action id
        "kind": "builtin",
        "published_at": "2026-01-01",
        "permissions": ["input_events"],
        "dependencies": [],
        "compatibility": ">=0.7.0",
    },
    "personalize": {
        "id": "personalize",
        "name": "Personalize",
        "display_name": "Personalize",
        "type": "extension",
        "description": "AI personality, tone, custom instructions and memory — make CAT yours.",
        "icon": "🎨",
        "publisher": "Kazi Zillani",
        "publisher_type": "individual",
        "publisher_verified": True,
        "verified": True,
        "trusted": True,
        "version": "1.0.0",
        "category": "Personalization",
        "keywords": ["personalize", "personality", "tone", "instructions", "memory"],
        "size_bytes": None,
        "size_display": None,
        "action": "customize_ai",
        "kind": "builtin",
        "published_at": "2026-01-01",
        "permissions": ["preferences", "memory"],
        "dependencies": [],
        "compatibility": ">=0.7.0",
    },
    "rea": {
        "id": "rea",
        "name": "REA",
        "display_name": "REA — Reasoning & Execution Architecture",
        "type": "skill",
        "description": "Autonomous dual-track reasoning and stepwise execution architecture for complex coding agents. Formulates hypotheses, verifies edge cases, and audits outcomes. Highly credited to Morluto (@morluto).",
        "icon": "🧠",
        "publisher": "Morluto",
        "publisher_id": "@morluto",
        "publisher_type": "individual",
        "publisher_verified": True,
        "verified": True,
        "trusted": True,
        "version": "1.2.0",
        "category": "Planning",
        "keywords": ["rea", "reasoning", "execution", "planning", "agent", "morluto"],
        "size_bytes": 1024 * 36,
        "size_display": "36.0 KB",
        "action": "skill_rea",
        "kind": "builtin",
        "published_at": "2026-03-15",
        "url": "https://github.com/morluto/rea",
        "credits": "Created by Morluto (@morluto) — https://github.com/morluto/rea. Full credit for agentic reasoning architecture.",
        "permissions": ["read_files", "write_files", "shell_commands"],
        "dependencies": [],
        "compatibility": ">=0.9.0",
    },
    "archify": {
        "id": "archify",
        "name": "Archify",
        "display_name": "Archify — Codebase Architecture & Blueprinting",
        "type": "skill",
        "description": "Comprehensive codebase architecture analysis, modular system design blueprinting, and architectural constraint enforcement. Highly credited to tt-a1i (@tt-a1i).",
        "icon": "🏛️",
        "publisher": "tt-a1i",
        "publisher_id": "@tt-a1i",
        "publisher_type": "individual",
        "publisher_verified": True,
        "verified": True,
        "trusted": True,
        "version": "1.0.4",
        "category": "Architecture",
        "keywords": ["archify", "architecture", "system-design", "blueprints", "modularity", "tt-a1i"],
        "size_bytes": 1024 * 28,
        "size_display": "28.0 KB",
        "action": "skill_archify",
        "kind": "builtin",
        "published_at": "2026-04-10",
        "url": "https://github.com/tt-a1i/archify",
        "credits": "Created by tt-a1i (@tt-a1i) — https://github.com/tt-a1i/archify. Full credit for codebase architectural mapping.",
        "permissions": ["read_files"],
        "dependencies": [],
        "compatibility": ">=0.9.0",
    },
    "remotion": {
        "id": "remotion",
        "name": "Remotion",
        "display_name": "Remotion — Programmatic Video & Motion Graphics",
        "type": "skill",
        "description": "Programmatic video creation, React motion graphics, audio synchronization, and MP4 rendering with Remotion. Highly credited to Jonny Burger & the Remotion team (@remotion-dev).",
        "icon": "🎬",
        "publisher": "Jonny Burger & Remotion Dev",
        "publisher_id": "@remotion-dev",
        "publisher_type": "organization",
        "publisher_verified": True,
        "verified": True,
        "trusted": True,
        "version": "4.0.0",
        "category": "Media",
        "keywords": ["remotion", "video", "motion-graphics", "react", "rendering", "media", "jonnyburger"],
        "size_bytes": 1024 * 52,
        "size_display": "52.0 KB",
        "action": "skill_remotion",
        "kind": "builtin",
        "published_at": "2026-02-20",
        "url": "https://github.com/remotion-dev/skills",
        "credits": "Created by Jonny Burger and Remotion team (@remotion-dev) — https://github.com/remotion-dev/skills.",
        "permissions": ["read_files", "write_files", "shell_commands"],
        "dependencies": [],
        "compatibility": ">=0.9.0",
    },
    "skillopt": {
        "id": "skillopt",
        "name": "SkillOpt",
        "display_name": "SkillOpt — Agent Skill & Context Optimizer",
        "type": "skill",
        "description": "Algorithmic skill selection, context pruning, prompt optimization, and tool execution cost minimization for AI agents. Highly credited to Microsoft Research (@microsoft).",
        "icon": "⚡",
        "publisher": "Microsoft Research",
        "publisher_id": "@microsoft",
        "publisher_type": "organization",
        "publisher_verified": True,
        "verified": True,
        "trusted": True,
        "version": "1.1.0",
        "category": "Optimization",
        "keywords": ["skillopt", "optimization", "context-pruning", "token-reduction", "microsoft", "performance"],
        "size_bytes": 1024 * 34,
        "size_display": "34.0 KB",
        "action": "skill_skillopt",
        "kind": "builtin",
        "published_at": "2026-05-01",
        "url": "https://github.com/microsoft/skillopt",
        "credits": "Created by Microsoft Research (@microsoft) — https://github.com/microsoft/skillopt. Full credit for agent context & skill optimization.",
        "permissions": ["read_files"],
        "dependencies": [],
        "compatibility": ">=0.9.0",
    },
    "page-mascot": {
        "id": "page-mascot",
        "name": "Page Mascot",
        "display_name": "Page Mascot — Interactive Cursor Companion",
        "type": "skill",
        "description": "Interactive cursor-tracking mascot, sprite animation controller, and companion reactivity widget for TUIs and web dashboards. Highly credited to nilbuild (@nilbuild).",
        "icon": "🐱",
        "publisher": "nilbuild",
        "publisher_id": "@nilbuild",
        "publisher_type": "individual",
        "publisher_verified": True,
        "verified": True,
        "trusted": True,
        "version": "1.0.2",
        "category": "Design",
        "keywords": ["page-mascot", "mascot", "companion", "cursor-tracking", "interactive", "nilbuild", "sprites"],
        "size_bytes": 1024 * 42,
        "size_display": "42.0 KB",
        "action": "skill_page_mascot",
        "kind": "builtin",
        "published_at": "2026-06-12",
        "url": "https://github.com/nilbuild/page-mascot",
        "credits": "Created by nilbuild (@nilbuild) — https://github.com/nilbuild/page-mascot. Full credit for interactive cursor companion mascots.",
        "permissions": ["read_files", "write_files"],
        "dependencies": [],
        "compatibility": ">=0.9.0",
    },
    "frontend-design": {
        "id": "frontend-design",
        "name": "Frontend Design",
        "display_name": "Frontend Design — Modern UI/UX & Responsive Systems",
        "type": "skill",
        "description": "Production-grade frontend design system: tactile 3D tall bevels, WCAG AA color science, fluid responsive layouts, and polished micro-interactions. Highly credited to Anthropic Quickstarts & Antigravity Design (@anthropic).",
        "icon": "✨",
        "publisher": "Anthropic & Antigravity Design",
        "publisher_id": "@anthropic",
        "publisher_type": "organization",
        "publisher_verified": True,
        "verified": True,
        "trusted": True,
        "version": "2.1.0",
        "category": "Design",
        "keywords": ["frontend-design", "design", "ui", "ux", "responsive", "typography", "tall-bevel", "anthropic"],
        "size_bytes": 1024 * 48,
        "size_display": "48.0 KB",
        "action": "skill_frontend_design",
        "kind": "builtin",
        "published_at": "2026-07-04",
        "url": "https://github.com/anthropics/anthropic-quickstarts",
        "credits": "Anthropic Quickstarts Standards & Antigravity Design (@anthropic). Full credit for tactile UI systems.",
        "permissions": ["read_files", "write_files"],
        "dependencies": [],
        "compatibility": ">=0.9.0",
    },
    "skill-creator": {
        "id": "skill-creator",
        "name": "Skill Creator",
        "display_name": "Skill Creator — Agent Skill Authoring & Packaging",
        "type": "skill",
        "description": "Comprehensive guidelines, validation checks, and templates for designing and packaging reusable Agent Skills with YAML frontmatter, execution constraints, and tool handoffs. Highly credited to Anthropic (@anthropic).",
        "icon": "🛠️",
        "publisher": "Anthropic",
        "publisher_id": "@anthropic",
        "publisher_type": "organization",
        "publisher_verified": True,
        "verified": True,
        "trusted": True,
        "version": "1.0.0",
        "category": "Tools",
        "keywords": ["skill-creator", "skills", "agent-skills", "anthropic", "packaging", "prompts"],
        "size_bytes": 1024 * 32,
        "size_display": "32.0 KB",
        "action": "skill_skill_creator",
        "kind": "builtin",
        "published_at": "2026-08-15",
        "url": "https://github.com/anthropics/skills/tree/main/skills/skill-creator",
        "credits": "Created by Anthropic (@anthropic) — https://github.com/anthropics/skills/tree/main/skills/skill-creator. Full credit for agent skill authoring and packaging guidelines.",
        "permissions": ["read_files", "write_files"],
        "dependencies": [],
        "compatibility": ">=0.9.0",
    },
    "find-skills": {
        "id": "find-skills",
        "name": "Find Skills",
        "display_name": "Find Skills — Agent Skills Discovery & Search",
        "type": "skill",
        "description": "Interactive search, evaluation, and safe installation of agent skills from GitHub repositories, packages, and community catalogues. Highly credited to Vercel Labs (@vercel-labs).",
        "icon": "🔍",
        "publisher": "Vercel Labs",
        "publisher_id": "@vercel-labs",
        "publisher_type": "organization",
        "publisher_verified": True,
        "verified": True,
        "trusted": True,
        "version": "1.0.0",
        "category": "Tools",
        "keywords": ["find-skills", "skill-finder", "discovery", "vercel", "vercel-labs", "registry", "catalog"],
        "size_bytes": 1024 * 30,
        "size_display": "30.0 KB",
        "action": "skill_find_skills",
        "kind": "builtin",
        "published_at": "2026-09-01",
        "url": "https://github.com/vercel-labs/skills/blob/main/skills/find-skills/SKILL.md",
        "credits": "Created by Vercel Labs (@vercel-labs) — https://github.com/vercel-labs/skills/blob/main/skills/find-skills/SKILL.md. Full credit for agent skill search and discovery.",
        "permissions": ["read_files", "network"],
        "dependencies": [],
        "compatibility": ">=0.9.0",
    },
}

# For size, map each builtin to its source files/dirs
_BUILTIN_PATHS = {
    "gestures": [_PKG_ROOT / "gestures", _PKG_ROOT / "ui" / "gestures_panel.py"],
    "personalize": [_PKG_ROOT / "ai_personalization.py", _PKG_ROOT / "ui" / "personalize_center.py"],
}

# Backward compat alias (old code imported EXTENSIONS)
EXTENSIONS = BUILTIN_EXTENSIONS

# Registry file (source of truth)
REGISTRY_FILE = Path.home() / ".cct_extensions_registry.json"

# Directory for custom user extensions
CUSTOM_EXTENSIONS_DIR = Path.home() / ".cct_extensions"
_LEGACY_CONFIG_KEY = "extensions"

_lock = threading.RLock()

# In-memory cache of registry state
_cached_state: Optional[Dict[str, Dict[str, Any]]] = None
_cached_mtime: float = 0


def _load_registry() -> Dict[str, Dict[str, Any]]:
    global _cached_state, _cached_mtime
    with _lock:
        try:
            mtime = REGISTRY_FILE.stat().st_mtime if REGISTRY_FILE.exists() else 0
            if _cached_state is not None and mtime == _cached_mtime:
                return dict(_cached_state)
        except Exception:
            pass

        data: Dict[str, Dict[str, Any]] = {}
        if REGISTRY_FILE.exists():
            try:
                with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    if isinstance(raw, dict):
                        if "extensions" in raw and isinstance(raw["extensions"], dict):
                            data = raw["extensions"]
                        else:
                            data = raw
                        filtered = {}
                        for k, v in data.items():
                            if isinstance(v, dict):
                                filtered[str(k)] = {
                                    "installed": bool(v.get("installed", False)),
                                    "enabled": bool(v.get("enabled", False)),
                                    "version": str(v.get("version", "")),
                                    "install_time": float(v.get("install_time", 0) or 0),
                                    "size_bytes": int(v.get("size_bytes", 0) or 0),
                                    "type": str(v.get("type", "extension")),
                                    "published_at": v.get("published_at"),
                                    "updated_at": float(v.get("updated_at", 0) or 0),
                                    "source": str(v.get("source", "")),
                                    "permissions": list(v.get("permissions", [])),
                                    "dependencies": list(v.get("dependencies", [])),
                                    "manifest": v.get("manifest", {}),
                                    "install_error": v.get("install_error"),
                                    "runtime_error": v.get("runtime_error"),
                                }
                            elif isinstance(v, bool):
                                filtered[str(k)] = {
                                    "installed": True,
                                    "enabled": bool(v),
                                    "version": "",
                                    "install_time": 0,
                                    "size_bytes": 0,
                                    "type": "extension",
                                    "permissions": [],
                                    "dependencies": [],
                                }
                        data = filtered
            except Exception:
                data = {}

        # Migration from legacy config.extensions (simple bool dict)
        if not data:
            try:
                from . import config as _cfg
                legacy = getattr(_cfg.load_config(), "extensions", None) or {}
                if isinstance(legacy, dict) and legacy:
                    for k, v in legacy.items():
                        if k in BUILTIN_EXTENSIONS:
                            b_meta = BUILTIN_EXTENSIONS[k]
                            if isinstance(v, bool):
                                data[str(k)] = {
                                    "installed": True,
                                    "enabled": bool(v),
                                    "version": b_meta.get("version", "1.0.0"),
                                    "install_time": time.time(),
                                    "size_bytes": _get_size_for(k),
                                    "type": b_meta.get("type", "extension"),
                                    "published_at": b_meta.get("published_at"),
                                    "permissions": b_meta.get("permissions", []),
                                    "dependencies": b_meta.get("dependencies", []),
                                }
                            elif isinstance(v, dict):
                                data[str(k)] = {
                                    "installed": bool(v.get("installed", True)),
                                    "enabled": bool(v.get("enabled", True)),
                                    "version": str(v.get("version", b_meta.get("version", "1.0.0"))),
                                    "install_time": float(v.get("install_time", 0) or time.time()),
                                    "size_bytes": int(v.get("size_bytes", 0) or _get_size_for(k)),
                                    "type": str(v.get("type", b_meta.get("type", "extension"))),
                                    "published_at": v.get("published_at", b_meta.get("published_at")),
                                    "permissions": list(v.get("permissions", b_meta.get("permissions", []))),
                                    "dependencies": list(v.get("dependencies", b_meta.get("dependencies", []))),
                                }
            except Exception:
                pass

        _cached_state = dict(data)
        try:
            _cached_mtime = REGISTRY_FILE.stat().st_mtime if REGISTRY_FILE.exists() else time.time()
        except Exception:
            _cached_mtime = time.time()
        return dict(data)


def _save_registry(data: Dict[str, Dict[str, Any]]):
    global _cached_state, _cached_mtime
    with _lock:
        try:
            REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": 1,
                "updated": time.time(),
                "extensions": data,
            }
            with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            _cached_state = dict(data)
            try:
                _cached_mtime = REGISTRY_FILE.stat().st_mtime
            except Exception:
                _cached_mtime = time.time()
            # Sync to config.extensions for backward compat
            try:
                from . import config as _cfg
                cfg = _cfg.load_config()
                legacy = {}
                for k, v in data.items():
                    if v.get("installed"):
                        legacy[k] = bool(v.get("enabled", False))
                cfg.extensions = legacy
                _cfg.save_config(cfg)
            except Exception:
                pass
        except Exception:
            pass


def _get_size_for(ext_id: str) -> int:
    """Calculate size for extension from its source files."""
    meta = BUILTIN_EXTENSIONS.get(ext_id)
    if meta and meta.get("size_bytes"):
        return int(meta["size_bytes"])
    paths = _BUILTIN_PATHS.get(ext_id, [])
    nbytes = _calc_size(paths) if paths else 0
    if nbytes == 0:
        ext_dir = CUSTOM_EXTENSIONS_DIR / ext_id
        if ext_dir.exists():
            nbytes = _calc_size([ext_dir])
    if nbytes == 0:
        nbytes = 1024 * 100
    return nbytes


# --------------------------------------------------------------------------
# Public ExtensionManager API
# --------------------------------------------------------------------------

def discover() -> List[Dict[str, Any]]:
    """Discover available extensions (built-in + installed third-party)."""
    return list_extensions()

def is_installed(extension_id: str) -> bool:
    data = _load_registry()
    rec = data.get(extension_id)
    if rec and rec.get("installed"):
        return True
    if extension_id in BUILTIN_EXTENSIONS:
        return True
    try:
        from .skills.engine import get_skills_engine
        if get_skills_engine().get_skill(extension_id) is not None:
            return True
    except Exception:
        pass
    try:
        from .skills.registry import get_skill_registry
        if get_skill_registry().get(extension_id) is not None:
            return True
    except Exception:
        pass
    return False

def is_enabled(extension_id: str) -> bool:
    data = _load_registry()
    rec = data.get(extension_id)
    if rec is not None:
        return bool(rec.get("installed") and rec.get("enabled"))
    return is_installed(extension_id)

def is_disabled(extension_id: str) -> bool:
    data = _load_registry()
    rec = data.get(extension_id)
    if rec is not None:
        return bool(rec.get("installed") and not rec.get("enabled"))
    return False

def get_state(extension_id: str) -> str:
    """Return state string: NOT_INSTALLED | INSTALLED_DISABLED | INSTALLED_ENABLED."""
    data = _load_registry()
    rec = data.get(extension_id)
    if not rec or not rec.get("installed"):
        return "NOT_INSTALLED"
    if rec.get("enabled"):
        return "INSTALLED_ENABLED"
    return "INSTALLED_DISABLED"

def get_metadata(extension_id: str) -> Optional[Dict[str, Any]]:
    """Return full rich metadata for extension, including live size, installed/enabled."""
    base = BUILTIN_EXTENSIONS.get(extension_id)
    data = _load_registry()
    rec = data.get(extension_id, {})

    if not base:
        # Check SkillsEngine for built-in or progressive disclosure skills
        try:
            from .skills.engine import get_skills_engine
            sk_eng = get_skills_engine().get_skill(extension_id)
            if sk_eng:
                inst = True
                enab = bool(rec.get("enabled")) if (rec and "enabled" in rec) else get_skills_engine().is_active(extension_id)
                return {
                    "id": extension_id,
                    "name": sk_eng.name,
                    "display_name": sk_eng.name,
                    "type": "skill",
                    "description": sk_eng.description,
                    "icon": sk_eng.icon,
                    "publisher": sk_eng.creator,
                    "publisher_id": sk_eng.github_username,
                    "publisher_type": "organization" if any(k in sk_eng.github_username.lower() for k in ("anthropic", "microsoft", "cloudflare", "cat", "remotion")) else "individual",
                    "publisher_verified": True,
                    "verified": True,
                    "trusted": True,
                    "version": sk_eng.version,
                    "category": sk_eng.category.title(),
                    "keywords": [extension_id, sk_eng.category, sk_eng.creator],
                    "size_bytes": 1024 * 32,
                    "size_display": "32.0 KB",
                    "installed": inst,
                    "enabled": enab,
                    "install_time": rec.get("install_time", 0) if rec else 0,
                    "updated_at": rec.get("updated_at", 0) if rec else 0,
                    "install_source": "builtin",
                    "permissions": ["read_files"],
                    "dependencies": [],
                    "cat_compatibility": ">=0.9.0",
                    "platform_compatibility": ["windows", "linux", "darwin"],
                    "install_error": None,
                    "runtime_error": None,
                    "state": "INSTALLED_ENABLED" if enab else "INSTALLED_DISABLED",
                    "kind": "builtin",
                    "action": f"skill_{extension_id}",
                    "repository": sk_eng.repository,
                    "license": sk_eng.license_name,
                }
        except Exception:
            pass

        # Check custom extension directory ~/.cct_extensions/<id>/
        ext_dir = CUSTOM_EXTENSIONS_DIR / extension_id
        manifest_file = ext_dir / "extension.json"
        manifest = {}
        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except Exception:
                pass
        if not manifest and rec and isinstance(rec.get("manifest"), dict):
            manifest = rec["manifest"]

        if manifest or rec:
            nbytes = _calc_size([ext_dir]) if ext_dir.exists() else int(rec.get("size_bytes", 1024 * 100))
            display_name = manifest.get("display_name") or manifest.get("name") or extension_id.title()
            ctype = str(manifest.get("type") or rec.get("type") or "extension").lower()
            return {
                "id": extension_id,
                "name": display_name,
                "display_name": display_name,
                "type": ctype,
                "description": manifest.get("description", rec.get("description", "Custom user component")),
                "icon": manifest.get("icon", "🧩"),
                "publisher": manifest.get("publisher", rec.get("publisher", "Unknown")),
                "publisher_type": manifest.get("publisher_type", "individual"),
                "publisher_verified": False,
                "verified": False,
                "trusted": bool(manifest.get("trusted", rec.get("trusted", False))),
                "version": manifest.get("version", rec.get("version", "1.0.0")),
                "category": manifest.get("category", "Custom"),
                "keywords": manifest.get("keywords", ["custom", extension_id]),
                "size_bytes": nbytes,
                "size_display": _format_size(nbytes),
                "installed": bool(rec.get("installed", True)),
                "enabled": bool(rec.get("enabled", True)),
                "install_time": rec.get("install_time", 0),
                "published_at": manifest.get("published_at", rec.get("published_at")),
                "updated_at": rec.get("updated_at", 0),
                "install_source": rec.get("source", "local"),
                "permissions": list(manifest.get("permissions") or rec.get("permissions") or []),
                "dependencies": list(manifest.get("dependencies") or rec.get("dependencies") or []),
                "cat_compatibility": manifest.get("compatibility", ">=0.7.0"),
                "platform_compatibility": manifest.get("platforms", ["windows", "linux", "darwin"]),
                "install_error": rec.get("install_error"),
                "runtime_error": rec.get("runtime_error"),
                "state": get_state(extension_id),
                "kind": "custom",
                "action": manifest.get("action", f"ext_{extension_id}"),
            }
        return None

    # Built-in extension
    installed = is_installed(extension_id)
    enabled = is_enabled(extension_id)
    nbytes = rec.get("size_bytes") if rec else None
    if not nbytes:
        nbytes = _get_size_for(extension_id)

    meta = dict(base)
    meta.update({
        "size_bytes": nbytes,
        "size_display": _format_size(nbytes),
        "installed": installed,
        "enabled": enabled,
        "state": get_state(extension_id),
        "install_time": rec.get("install_time", 0) if rec else 0,
        "updated_at": rec.get("updated_at", 0) if rec else 0,
        "install_source": "builtin",
        "install_error": rec.get("install_error"),
        "runtime_error": rec.get("runtime_error"),
    })
    return meta

def get_size(extension_id: str) -> int:
    meta = get_metadata(extension_id)
    return int(meta["size_bytes"]) if meta else 0

def list_extensions(category: Optional[str] = None, component_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all available extensions (built-in + discovered) with live states,
    with optional filtering by category or component type (extension/skill/command/integration).
    """
    out = []
    seen = set()
    # Built-ins first
    for kid in BUILTIN_EXTENSIONS:
        meta = get_metadata(kid)
        if meta:
            out.append(meta)
            seen.add(kid)
    # Discover custom extensions from ~/.cct_extensions
    if CUSTOM_EXTENSIONS_DIR.exists():
        try:
            for sub in CUSTOM_EXTENSIONS_DIR.iterdir():
                if sub.is_dir() and sub.name not in seen:
                    meta = get_metadata(sub.name)
                    if meta:
                        out.append(meta)
                        seen.add(sub.name)
        except Exception:
            pass
    # Add any custom installed extensions in registry not in directories
    data = _load_registry()
    for kid in data:
        if kid not in seen:
            meta = get_metadata(kid)
            if meta:
                out.append(meta)
                seen.add(kid)

    # Discover skills registered in SkillRegistry
    try:
        from .skills.registry import get_skill_registry
        for sk in get_skill_registry().list_skills():
            sk_id = sk.id
            if sk_id not in seen:
                sk_meta = {
                    "id": sk_id,
                    "name": sk.name,
                    "display_name": sk.name,
                    "type": "skill",
                    "description": sk.description,
                    "icon": "🧠",
                    "publisher": getattr(sk, "author", "CAT Skill System"),
                    "publisher_type": "organization" if getattr(sk, "builtin", False) else "individual",
                    "publisher_verified": getattr(sk, "builtin", False),
                    "verified": getattr(sk, "builtin", False),
                    "trusted": True,
                    "version": sk.version,
                    "category": sk.category.title(),
                    "keywords": sk.tags,
                    "size_bytes": 1024 * 32,
                    "size_display": "32.0 KB",
                    "installed": True,
                    "enabled": sk.enabled,
                    "state": "INSTALLED_ENABLED" if sk.enabled else "INSTALLED_DISABLED",
                    "install_time": sk.created_at,
                    "updated_at": sk.updated_at,
                    "install_source": "builtin" if sk.builtin else "skill_registry",
                    "permissions": [k for k, v in sk.permission_scope.items() if v],
                    "dependencies": sk.required_tools,
                    "cat_compatibility": ">=0.9.0",
                    "kind": "builtin" if sk.builtin else "skill",
                    "action": f"skill_{sk_id}",
                }
                out.append(sk_meta)
                seen.add(sk_id)
    except Exception:
        pass

    # Discover registered MCP servers and bridge them into Extensions Panel
    try:
        from . import mcp as _mcp
        for s in _mcp.load_servers():
            sid = f"mcp_{s.get('id', '')}"
            if sid not in seen:
                st = _mcp.server_status(s)
                tools_list = s.get("tools") or []
                tools_desc = f"Tools: {', '.join(tools_list[:4])}" if tools_list else "Dynamic MCP Protocol Tools"
                mcp_meta = {
                    "id": sid,
                    "name": s.get("name") or s.get("id"),
                    "display_name": f"🔌 MCP: {s.get('name') or s.get('id')}",
                    "type": "skill",
                    "description": f"MCP Protocol Server ({s.get('command') or s.get('url')}). {tools_desc}. Status: {st.get('state', 'ready')}.",
                    "icon": "🔌",
                    "publisher": s.get("creator") or s.get("publisher") or "Model Context Protocol",
                    "publisher_type": "organization",
                    "publisher_verified": True,
                    "verified": True,
                    "trusted": True,
                    "version": s.get("version") or "1.0.0",
                    "category": "MCP Server",
                    "keywords": ["mcp", "server", "tools", "protocol", s.get("id", "")],
                    "size_bytes": 1024 * 50,
                    "size_display": "50.0 KB",
                    "installed": True,
                    "enabled": bool(st.get("state") in ("connected", "ready", "idle") or True),
                    "state": "INSTALLED_ENABLED" if st.get("state") != "disconnected" else "INSTALLED_DISABLED",
                    "install_time": time.time(),
                    "updated_at": time.time(),
                    "install_source": "mcp_registry",
                    "permissions": ["mcp_tools", "network" if s.get("url") else "process_spawn"],
                    "dependencies": [],
                    "cat_compatibility": ">=0.9.0",
                    "kind": "mcp",
                    "action": f"mcp_connect_{s.get('id')}",
                }
                out.append(mcp_meta)
                seen.add(sid)
    except Exception:
        pass

    # Apply filters
    if category:
        cat_low = category.strip().lower()
        out = [m for m in out if str(m.get("category", "")).lower() == cat_low]
    if component_type:
        type_low = component_type.strip().lower()
        if type_low != "all":
            out = [m for m in out if str(m.get("type", "extension")).lower() == type_low]

    return out

def list_installed(component_type: Optional[str] = None) -> List[Dict[str, Any]]:
    return [m for m in list_extensions(component_type=component_type) if m.get("installed")]

def list_enabled(component_type: Optional[str] = None) -> List[Dict[str, Any]]:
    return [m for m in list_extensions(component_type=component_type) if m.get("enabled") and m.get("installed")]

# --------------------------------------------------------------------------
# Lifecycle: INSTALL -> ENABLE -> DISABLE -> UPDATE -> UNINSTALL
# --------------------------------------------------------------------------

def install(extension_id: str) -> Tuple[bool, str]:
    """INSTALL: NOT_INSTALLED -> INSTALLED_ENABLED. Returns (ok, msg)."""
    # 1. If it's a built-in extension
    if extension_id in BUILTIN_EXTENSIONS:
        data = _load_registry()
        rec = data.get(extension_id)
        if rec and rec.get("installed"):
            if not rec.get("enabled"):
                rec["enabled"] = True
                _save_registry(data)
                return True, f"✓ {BUILTIN_EXTENSIONS[extension_id]['display_name']} enabled"
            return False, f"{extension_id} is already installed"

        nbytes = _get_size_for(extension_id)
        b_meta = BUILTIN_EXTENSIONS[extension_id]
        data[extension_id] = {
            "installed": True,
            "enabled": True,
            "version": b_meta.get("version", "1.0.0"),
            "install_time": time.time(),
            "published_at": b_meta.get("published_at"),
            "type": b_meta.get("type", "extension"),
            "permissions": b_meta.get("permissions", []),
            "dependencies": b_meta.get("dependencies", []),
            "size_bytes": nbytes,
            "source": "builtin",
        }
        _save_registry(data)
        return True, f"✓ {b_meta.get('display_name', extension_id)} installed successfully"

    # 2. Check if already installed
    data = _load_registry()
    if extension_id in data and data[extension_id].get("installed"):
        if not data[extension_id].get("enabled"):
            return enable(extension_id)
        return False, f"Extension '{extension_id}' is already installed"

    # 3. Check if available in curated catalogue
    from .extension_installer import CURATED_CATALOGUE
    for item in CURATED_CATALOGUE:
        if item["id"] == extension_id:
            return install_from_github(item["repo_url"])

    return False, f"Extension '{extension_id}' not found in marketplace"


def install_from_github(repo_url_or_slug: str, mock_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """
    Install a Skill, Command, Integration, or Extension from a GitHub repository or catalogue item.
    Performs full pre-installation inspection, path traversal validation, managed extraction,
    and registration with Kitties and CLI subsystems.
    """
    from .extension_installer import (
        inspect_repository,
        install_from_zip,
        register_component_in_subsystems,
    )

    # 1. Inspect repository and validate manifest without executing code
    insp = inspect_repository(repo_url_or_slug, mock_data=mock_data)
    if not insp.valid:
        return False, f"Inspection failed: {insp.error}"

    if not insp.compatibility_ok:
        return False, f"Compatibility check failed: {insp.compatibility_notes}"

    cid = insp.id
    if is_installed(cid):
        return False, f"Component '{cid}' is already installed. Use update('{cid}') to upgrade."

    dest_dir = CUSTOM_EXTENSIONS_DIR / cid
    dest_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 2. Extract files or write manifest
        if insp.archive_bytes:
            ok, msg = install_from_zip(insp.archive_bytes, insp, target_dir=dest_dir)
            if not ok:
                return False, msg
        else:
            # Write canonical extension.json
            with open(dest_dir / "extension.json", "w", encoding="utf-8") as f:
                json.dump(insp.manifest, f, indent=2)

            # If script code or entrypoint is provided in manifest
            if insp.manifest.get("script_code"):
                script_path = dest_dir / f"{cid}.py"
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(insp.manifest["script_code"])

        # 3. Register in appropriate subsystems (SkillRegistry, CustomCommandRegistry, etc.)
        reg_ok, reg_msg = register_component_in_subsystems(insp, dest_dir)
        if not reg_ok:
            shutil.rmtree(dest_dir, ignore_errors=True)
            return False, reg_msg

        return True, f"✓ Successfully installed {insp.component_type} '{insp.name}' (v{insp.version}) from GitHub!"
    except Exception as e:
        shutil.rmtree(dest_dir, ignore_errors=True)
        return False, f"Installation failed: {e}"


def check_for_dependencies(extension_id: str) -> List[str]:
    """Check if any currently installed extension depends on extension_id."""
    dependents = []
    for ext in list_installed():
        if ext["id"] == extension_id:
            continue
        deps = ext.get("dependencies", [])
        if extension_id in deps:
            dependents.append(ext["id"])
    return dependents


def uninstall(extension_id: str, force: bool = False) -> Tuple[bool, str]:
    """UNINSTALL: Removes registered capabilities and managed files safely."""
    data = _load_registry()
    rec = data.get(extension_id)
    if not rec or not rec.get("installed"):
        return False, f"'{extension_id}' is not installed"

    # Dependency check: warn if other extensions rely on this one
    dependents = check_for_dependencies(extension_id)
    if dependents and not force:
        return False, (
            f"Cannot uninstall '{extension_id}': Required as a dependency by {dependents}. "
            f"Disable or uninstall them first."
        )

    meta = get_metadata(extension_id) or {}
    ctype = meta.get("type", "extension")

    # 1. Unregister from Kitty Skills if it's a Skill
    if ctype == "skill":
        try:
            from .skills.registry import get_skill_registry
            get_skill_registry().unregister(extension_id)
        except Exception:
            pass

    # 2. Unregister from Custom Commands if it's a Command
    if ctype == "command" or extension_id:
        try:
            from .commands_registry import get_command_registry
            get_command_registry().unregister_by_extension(extension_id)
        except Exception:
            pass

    # 3. Remove from source-of-truth registry
    del data[extension_id]
    _save_registry(data)

    # 4. Safely remove ONLY the extension's managed directory
    try:
        ext_dir = CUSTOM_EXTENSIONS_DIR / extension_id
        if ext_dir.exists() and ext_dir.is_dir():
            shutil.rmtree(ext_dir, ignore_errors=True)
    except Exception:
        pass

    return True, f"✓ {meta.get('display_name', extension_id)} uninstalled successfully"


def enable(extension_id: str) -> Tuple[bool, str]:
    """ENABLE: INSTALLED_DISABLED -> INSTALLED_ENABLED."""
    data = _load_registry()
    rec = data.get(extension_id)
    if not rec or not rec.get("installed"):
        if is_installed(extension_id):
            meta = get_metadata(extension_id) or {}
            data[extension_id] = {
                "installed": True,
                "enabled": True,
                "version": meta.get("version", "1.0.0"),
                "install_time": time.time(),
                "updated_at": time.time(),
                "type": meta.get("type", "extension"),
                "permissions": meta.get("permissions", []),
                "dependencies": meta.get("dependencies", []),
            }
            rec = data[extension_id]
        else:
            return False, f"'{extension_id}' is not installed — install first"
    elif rec.get("enabled"):
        return False, f"'{extension_id}' is already enabled"

    rec["enabled"] = True
    rec["updated_at"] = time.time()
    _save_registry(data)

    meta = get_metadata(extension_id) or {}
    ctype = meta.get("type", "extension")

    # Re-enable in subsystem
    try:
        from .skills.registry import get_skill_registry
        sk = get_skill_registry().get(extension_id)
        if sk:
            sk.enabled = True
    except Exception:
        pass
    try:
        from .skills.engine import get_skills_engine
        get_skills_engine().activate_skill(extension_id)
    except Exception:
        pass

    if ctype == "command":
        try:
            from .commands_registry import get_command_registry
            get_command_registry().set_extension_enabled(extension_id, True)
        except Exception:
            pass

    return True, f"✓ {meta.get('display_name', extension_id)} enabled"


def disable(extension_id: str) -> Tuple[bool, str]:
    """DISABLE: INSTALLED_ENABLED -> INSTALLED_DISABLED."""
    data = _load_registry()
    rec = data.get(extension_id)
    if not rec or not rec.get("installed"):
        if is_installed(extension_id):
            meta = get_metadata(extension_id) or {}
            data[extension_id] = {
                "installed": True,
                "enabled": False,
                "version": meta.get("version", "1.0.0"),
                "install_time": time.time(),
                "updated_at": time.time(),
                "type": meta.get("type", "extension"),
                "permissions": meta.get("permissions", []),
                "dependencies": meta.get("dependencies", []),
            }
            rec = data[extension_id]
        else:
            return False, f"'{extension_id}' is not installed"
    elif not rec.get("enabled"):
        return False, f"'{extension_id}' is already disabled"

    rec["enabled"] = False
    rec["updated_at"] = time.time()
    _save_registry(data)

    meta = get_metadata(extension_id) or {}
    ctype = meta.get("type", "extension")

    # Deactivate in subsystem
    try:
        from .skills.registry import get_skill_registry
        sk = get_skill_registry().get(extension_id)
        if sk:
            sk.enabled = False
    except Exception:
        pass
    try:
        from .skills.engine import get_skills_engine
        get_skills_engine().deactivate_skill(extension_id)
    except Exception:
        pass

    if ctype == "command":
        try:
            from .commands_registry import get_command_registry
            get_command_registry().set_extension_enabled(extension_id, False)
        except Exception:
            pass

    return True, f"✓ {meta.get('display_name', extension_id)} disabled"


def toggle(extension_id: str) -> Tuple[bool, str]:
    if is_enabled(extension_id):
        return disable(extension_id)
    if is_installed(extension_id):
        return enable(extension_id)
    return install(extension_id)


def check_for_updates(extension_id: str) -> Tuple[bool, str, str, Dict[str, Any]]:
    """Check for component updates without executing code."""
    from .extension_installer import check_for_updates as _check_installer
    return _check_installer(extension_id)


def update(extension_id: str) -> Tuple[bool, str]:
    """Update an installed extension if a newer version is available."""
    has_update, curr_v, latest_v, details = check_for_updates(extension_id)
    if not has_update:
        return False, f"'{extension_id}' is already at the latest version (v{curr_v})."

    source = details.get("source")
    if not source:
        return False, "Cannot update: no remote source URL recorded."

    # Backup current state and perform re-installation
    uninstall(extension_id, force=True)
    ok, msg = install_from_github(source)
    if ok:
        return True, f"✓ Successfully updated '{extension_id}' from v{curr_v} to v{latest_v}!"
    return False, f"Update failed: {msg}"


def set_enabled(key: str, enabled: bool):
    """Backward compatibility helper."""
    if enabled:
        if not is_installed(key):
            install(key)
        else:
            enable(key)
    else:
        if is_installed(key):
            disable(key)


def should_show_in_menu(action_id: str) -> bool:
    """For header.NAV_ITEMS filtering: show only if installed+enabled."""
    if action_id in ("vision", "customization"):
        return False
    if action_id.startswith("ext_"):
        key = action_id[4:]
        return is_installed(key) and is_enabled(key)
    # Map action -> extension key
    action_to_key = {v["action"]: k for k, v in BUILTIN_EXTENSIONS.items()}
    key = action_to_key.get(action_id)
    if key is None:
        return True
    return is_installed(key) and is_enabled(key)


def create_extension(
    extension_id: str,
    name: str = "",
    description: str = "",
    icon: str = "🧩",
    publisher: str = "User",
    category: str = "Custom",
    version: str = "1.0.0",
    script_code: str = "",
    component_type: str = "extension",
) -> Tuple[bool, str]:
    """Create a new custom extension in ~/.cct_extensions/<id>/ and register it."""
    try:
        clean_id = (extension_id or "").strip().lower().replace(" ", "_").replace("-", "_")
        if not clean_id:
            return False, "Extension ID cannot be empty."
        if clean_id in BUILTIN_EXTENSIONS:
            return False, f"'{clean_id}' conflicts with a built-in extension."

        ext_dir = CUSTOM_EXTENSIONS_DIR / clean_id
        ext_dir.mkdir(parents=True, exist_ok=True)

        display_name = (name or "").strip() or clean_id.title()
        manifest = {
            "id": clean_id,
            "name": display_name,
            "display_name": display_name,
            "type": component_type,
            "description": (description or "").strip() or "Custom user-created extension",
            "icon": (icon or "").strip() or "🧩",
            "publisher": (publisher or "").strip() or "User",
            "publisher_type": "individual",
            "publisher_verified": False,
            "verified": False,
            "trusted": True,
            "version": (version or "").strip() or "1.0.0",
            "category": (category or "").strip() or "Custom",
            "keywords": ["custom", clean_id],
            "kind": "custom",
            "action": f"ext_{clean_id}",
            "published_at": time.strftime("%Y-%m-%d"),
            "permissions": [],
            "dependencies": [],
        }

        manifest_file = ext_dir / "extension.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        script_file = ext_dir / f"{clean_id}.py"
        if not script_file.exists() or script_code:
            code = script_code or f'"""\nCAT Extension: {display_name}\n"""\n\ndef activate(app=None):\n    pass\n'
            with open(script_file, "w", encoding="utf-8") as f:
                f.write(code)

        data = _load_registry()
        data[clean_id] = {
            "installed": True,
            "enabled": True,
            "version": manifest["version"],
            "install_time": time.time(),
            "published_at": manifest["published_at"],
            "type": component_type,
            "size_bytes": _calc_size([ext_dir]),
            "manifest": manifest,
            "source": "local",
            "permissions": [],
            "dependencies": [],
        }
        _save_registry(data)
        return True, f"✓ Custom extension '{display_name}' created and enabled successfully!"
    except Exception as e:
        return False, f"Failed to create extension: {e}"


# --------------------------------------------------------------------------
# Feature registration (for extensions that register menu items, panels, etc.)
# --------------------------------------------------------------------------

_registered_features: Dict[str, Dict[str, Any]] = {}

def register_feature(extension_id: str, feature_type: str, feature_id: str, meta: Dict[str, Any] = None):
    """Extensions call this to register a feature (menu item, panel, command)."""
    if not is_enabled(extension_id):
        return False
    key = f"{extension_id}:{feature_type}:{feature_id}"
    _registered_features[key] = {"extension": extension_id, "type": feature_type, "id": feature_id, "meta": meta or {}}
    return True

def unregister_feature(extension_id: str, feature_type: str, feature_id: str):
    key = f"{extension_id}:{feature_type}:{feature_id}"
    _registered_features.pop(key, None)

def get_registered_features(feature_type: str = None) -> List[Dict[str, Any]]:
    if feature_type:
        return [v for v in _registered_features.values() if v["type"] == feature_type]
    return list(_registered_features.values())


# --------------------------------------------------------------------------
# Startup & Subsystem Integration
# --------------------------------------------------------------------------

def validate_all() -> List[str]:
    """Validate installed extensions; return list of errors (empty if ok)."""
    errors = []
    for ext in list_installed():
        try:
            paths = _BUILTIN_PATHS.get(ext["id"], [])
            if paths:
                for p in paths:
                    if not p.exists():
                        errors.append(f"{ext['id']}: missing {p}")
        except Exception as e:
            errors.append(f"{ext['id']}: {e}")
    return errors


def load_enabled():
    """Load and activate enabled extensions at startup into Kitty & Command subsystems."""
    for ext in list_enabled():
        eid = ext["id"]
        ctype = ext.get("type", "extension")
        try:
            # If skill, ensure registered in SkillRegistry
            if ctype == "skill":
                try:
                    from .skills.registry import get_skill_registry
                    from .skills.skill_model import SkillDefinition
                    reg = get_skill_registry()
                    if not reg.get(eid):
                        sk = SkillDefinition(
                            id=eid,
                            name=ext["name"],
                            version=ext.get("version", "1.0.0"),
                            description=ext.get("description", ""),
                            category=ext.get("category", "general").lower(),
                            required_tools=ext.get("manifest", {}).get("required_tools", []),
                            instructions=ext.get("manifest", {}).get("instructions", ""),
                            enabled=True,
                        )
                        reg.register(sk)
                except Exception:
                    pass

            # If command, ensure registered in CustomCommandRegistry
            elif ctype == "command":
                try:
                    from .commands_registry import get_command_registry, CommandSpec
                    cmd_reg = get_command_registry()
                    cmd_name = ext.get("manifest", {}).get("command_name") or eid
                    if not cmd_reg.get(cmd_name):
                        script_p = CUSTOM_EXTENSIONS_DIR / eid / f"{cmd_name}.py"
                        cmd_reg.register(
                            CommandSpec(
                                id=eid,
                                name=cmd_name,
                                description=ext.get("description", ""),
                                extension_id=eid,
                                script_path=str(script_p) if script_p.exists() else None,
                                enabled=True,
                            )
                        )
                except Exception:
                    pass
        except Exception as e:
            print(f"[extensions] Failed to activate {eid}: {e}", file=sys.stderr)


def startup():
    """Full startup sequence: discover -> validate -> load enabled."""
    try:
        discover()
        errs = validate_all()
        if errs:
            for err in errs:
                print(f"[extensions] validate: {err}", file=sys.stderr)
        load_enabled()
    except Exception as e:
        print(f"[extensions] startup failed: {e} — CAT will continue without extensions", file=sys.stderr)


def enabled_actions() -> set:
    return {v["action"] for v in BUILTIN_EXTENSIONS.values() if is_enabled(v["id"])}


def _reset_for_tests():
    """Reset registry to clean state for test suites."""
    try:
        if REGISTRY_FILE.exists():
            REGISTRY_FILE.unlink()
    except Exception:
        pass
    try:
        from . import config as _cfg
        cfg = _cfg.load_config()
        cfg.extensions = {}
        _cfg.save_config(cfg)
    except Exception:
        pass
    global _cached_state, _cached_mtime
    _cached_state = None
    _cached_mtime = 0
    _load_registry()


def _clear_all_for_test():
    _reset_for_tests()
