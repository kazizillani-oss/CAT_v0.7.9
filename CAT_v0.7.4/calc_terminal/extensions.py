"""
CCT Extension Manager — VS Code-style (v0.7.9.10).

Central registry for Gestures / CAT Vision / Personalize and future
third-party extensions. Implements the full lifecycle:

    NOT_INSTALLED -> INSTALL -> INSTALLED_ENABLED
    INSTALLED_ENABLED -> DISABLE -> INSTALLED_DISABLED
    INSTALLED_DISABLED -> ENABLE -> INSTALLED_ENABLED
    INSTALLED_* -> UNINSTALL -> NOT_INSTALLED

Main menu queries is_installed() && is_enabled() — never hard-coded.

Persistence: ~/.cct_extensions_registry.json (source of truth) +
~/.cct_config.json .extensions for backward compat migration.
Startup: discover() -> validate -> load enabled -> register features.

Features: metadata (name, icon, creator, verified, trusted, size,
version, category), size from filesystem, publisher identity (individual
vs company), trusted, VS Code-style UX, error isolation.
"""

from __future__ import annotations

import json
import os
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any

# --------------------------------------------------------------------------
# Built-in extension definitions (available to install). These use the same
# infrastructure as future third-party extensions — no special hard-coded
# path for these three.
# --------------------------------------------------------------------------

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

# Built-in extensions — these are the only ones shipped with CAT.
# Future third-party extensions will be discovered from ~/.cct_extensions/
# or registry and use the same schema.
BUILTIN_EXTENSIONS: Dict[str, Dict[str, Any]] = {
    "gestures": {
        "id": "gestures",
        "name": "Gestures",
        "display_name": "Gestures",
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
    },
    "personalize": {
        "id": "personalize",
        "name": "Personalize",
        "display_name": "Personalize",
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
# Legacy config key for migration
_LEGACY_CONFIG_KEY = "extensions"

_lock = threading.RLock()

# In-memory cache of registry state
# state: {ext_id: {"installed": bool, "enabled": bool, "version": str, "install_time": float, "size_bytes": int}}
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

        # Try registry file
        data: Dict[str, Dict[str, Any]] = {}
        if REGISTRY_FILE.exists():
            try:
                with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    if isinstance(raw, dict):
                        # support both {id: {installed, enabled}} and legacy list
                        if "extensions" in raw and isinstance(raw["extensions"], dict):
                            data = raw["extensions"]
                        else:
                            # flat dict
                            data = raw
                        # filter to known structure
                        filtered = {}
                        for k, v in data.items():
                            if isinstance(v, dict):
                                filtered[str(k)] = {
                                    "installed": bool(v.get("installed", False)),
                                    "enabled": bool(v.get("enabled", False)),
                                    "version": str(v.get("version", "")),
                                    "install_time": float(v.get("install_time", 0) or 0),
                                    "size_bytes": int(v.get("size_bytes", 0) or 0),
                                }
                            elif isinstance(v, bool):
                                # legacy: True => installed+enabled, False => installed disabled? But old code used False = disabled (installed but disabled)
                                # For migration, treat True as installed+enabled, False as installed+disabled
                                filtered[str(k)] = {
                                    "installed": True,
                                    "enabled": bool(v),
                                    "version": "",
                                    "install_time": 0,
                                    "size_bytes": 0,
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
                            if isinstance(v, bool):
                                data[str(k)] = {
                                    "installed": True,
                                    "enabled": bool(v),
                                    "version": BUILTIN_EXTENSIONS[k].get("version", "1.0.0"),
                                    "install_time": time.time(),
                                    "size_bytes": _get_size_for(k),
                                }
                            elif isinstance(v, dict):
                                data[str(k)] = {
                                    "installed": bool(v.get("installed", True)),
                                    "enabled": bool(v.get("enabled", True)),
                                    "version": str(v.get("version", "")),
                                    "install_time": float(v.get("install_time", 0) or time.time()),
                                    "size_bytes": int(v.get("size_bytes", 0) or _get_size_for(k)),
                                }
            except Exception:
                pass

        # First run: extensions are NOT installed until user installs them
        # (VS Code-style: Install → Enable → appears in menu).
        # Keep data empty so get_state() returns NOT_INSTALLED for builtins.
        if not data:
            # don't auto-install — user must click Install in Extensions panel
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
            # also sync to config.extensions for backward compat (simple bool)
            try:
                from . import config as _cfg
                cfg = _cfg.load_config()
                # keep legacy simple dict for old code that reads config.extensions
                legacy = {}
                for k, v in data.items():
                    # only store enabled if installed, else not present? For legacy, store enabled bool if installed, else missing
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
    # Check cache from builtin
    meta = BUILTIN_EXTENSIONS.get(ext_id)
    if meta and meta.get("size_bytes"):
        return int(meta["size_bytes"])
    paths = _BUILTIN_PATHS.get(ext_id, [])
    nbytes = _calc_size(paths) if paths else 0
    # if no paths, try to find extension dir ~/.cct_extensions/<id>/
    if nbytes == 0:
        ext_dir = Path.home() / ".cct_extensions" / ext_id
        if ext_dir.exists():
            nbytes = _calc_size([ext_dir])
    if nbytes == 0:
        # fallback: estimate 100KB per extension
        nbytes = 1024 * 100
    return nbytes


def _ensure_size(ext_id: str, state: Dict[str, Any]) -> int:
    if state.get("size_bytes"):
        return int(state["size_bytes"])
    nbytes = _get_size_for(ext_id)
    state["size_bytes"] = nbytes
    return nbytes

# --------------------------------------------------------------------------
# Public ExtensionManager API (spec section 15)
# --------------------------------------------------------------------------

def discover() -> List[Dict[str, Any]]:
    """Discover available extensions (built-in + installed third-party)."""
    return list_extensions()

def is_installed(extension_id: str) -> bool:
    data = _load_registry()
    rec = data.get(extension_id)
    return bool(rec and rec.get("installed"))

def is_enabled(extension_id: str) -> bool:
    data = _load_registry()
    rec = data.get(extension_id)
    return bool(rec and rec.get("installed") and rec.get("enabled"))

def is_disabled(extension_id: str) -> bool:
    data = _load_registry()
    rec = data.get(extension_id)
    return bool(rec and rec.get("installed") and not rec.get("enabled"))

def get_state(extension_id: str) -> str:
    """Return state string: NOT_INSTALLED | INSTALLED_DISABLED | INSTALLED_ENABLED | INSTALLING etc."""
    data = _load_registry()
    rec = data.get(extension_id)
    if not rec or not rec.get("installed"):
        return "NOT_INSTALLED"
    if rec.get("enabled"):
        return "INSTALLED_ENABLED"
    return "INSTALLED_DISABLED"

def get_metadata(extension_id: str) -> Optional[Dict[str, Any]]:
    """Return full metadata for extension, including live size, installed/enabled."""
    base = BUILTIN_EXTENSIONS.get(extension_id)
    if not base:
        # Check custom extension directory ~/.cct_extensions/<id>/
        ext_dir = CUSTOM_EXTENSIONS_DIR / extension_id
        manifest_file = ext_dir / "extension.json"
        data = _load_registry()
        rec = data.get(extension_id, {})
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
            display_name = manifest.get("name") or manifest.get("display_name") or extension_id.title()
            return {
                "id": extension_id,
                "name": display_name,
                "display_name": display_name,
                "description": manifest.get("description", "Custom user extension"),
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
                "state": get_state(extension_id),
                "kind": "custom",
                "action": manifest.get("action", f"ext_{extension_id}"),
            }
        return None
    # built-in
    data = _load_registry()
    rec = data.get(extension_id, {})
    is_inst = bool(rec.get("installed")) if rec else True  # default installed for backward compat handled in _load_registry
    # Actually _load_registry ensures installed for builtins if empty, so if rec is None after load, it means not installed? But _load_registry would have created it if empty.
    # For explicit check, if rec is None, treat as not installed only if registry has been initialized with data
    # To know if not installed, check if extension_id in data
    installed = is_installed(extension_id)
    enabled = is_enabled(extension_id)
    # calculate size
    nbytes = 0
    if rec:
        nbytes = rec.get("size_bytes") or _get_size_for(extension_id)
    else:
        nbytes = _get_size_for(extension_id)
    meta = dict(base)
    meta.update({
        "size_bytes": nbytes,
        "size_display": _format_size(nbytes),
        "installed": installed,
        "enabled": enabled,
        "state": get_state(extension_id),
        "install_time": rec.get("install_time", 0) if rec else 0,
    })
    return meta

def get_size(extension_id: str) -> int:
    meta = get_metadata(extension_id)
    return int(meta["size_bytes"]) if meta else 0

def list_extensions() -> List[Dict[str, Any]]:
    """List all available extensions (built-in + discovered) with live states."""
    out = []
    seen = set()
    # built-ins first
    for kid in BUILTIN_EXTENSIONS:
        meta = get_metadata(kid)
        if meta:
            out.append(meta)
            seen.add(kid)
    # discover custom extensions from ~/.cct_extensions
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
    # add any custom installed extensions in registry not in builtins
    data = _load_registry()
    for kid in data:
        if kid not in seen:
            meta = get_metadata(kid)
            if meta:
                out.append(meta)
                seen.add(kid)
    return out

def list_installed() -> List[Dict[str, Any]]:
    return [m for m in list_extensions() if m.get("installed")]

def list_enabled() -> List[Dict[str, Any]]:
    return [m for m in list_extensions() if m.get("enabled") and m.get("installed")]

# Lifecycle: INSTALL -> INSTALLED_ENABLED
def install(extension_id: str) -> tuple[bool, str]:
    """INSTALL: NOT_INSTALLED -> INSTALLED_ENABLED. Returns (ok, msg)."""
    # validate exists as available
    if extension_id not in BUILTIN_EXTENSIONS:
        # check if it's already installed custom
        data = _load_registry()
        if extension_id in data and data[extension_id].get("installed"):
            return False, f"{extension_id} is already installed"
        # unknown extension — cannot install from marketplace yet (would need download)
        # For built-in, we allow install; for unknown, treat as install of custom placeholder
        if extension_id not in data:
            return False, f"Extension '{extension_id}' not found in marketplace"
    data = _load_registry()
    rec = data.get(extension_id)
    if rec and rec.get("installed"):
        # if already installed but disabled, enable it (spec: INSTALL on installed should probably enable)
        if not rec.get("enabled"):
            rec["enabled"] = True
            _save_registry(data)
            return True, f"{extension_id} enabled"
        return False, f"{extension_id} is already installed"
    # perform install
    nbytes = _get_size_for(extension_id)
    # simulate installing state (could be async, but spec says update immediately)
    data[extension_id] = {
        "installed": True,
        "enabled": True,
        "version": BUILTIN_EXTENSIONS.get(extension_id, {}).get("version", "1.0.0"),
        "install_time": time.time(),
        "size_bytes": nbytes,
    }
    _save_registry(data)
    # CAT Customization lifecycle hook
    if extension_id == "customization":
        try:
            from . import customization as _cust
            _cust.on_install()
            _cust.on_enable()
        except Exception:
            pass
    # feature registration will happen via should_show_in_menu / startup
    return True, f"✓ {BUILTIN_EXTENSIONS.get(extension_id, {}).get('display_name', extension_id)} installed successfully"

def uninstall(extension_id: str) -> tuple[bool, str]:
    """UNINSTALL: INSTALLED_* -> NOT_INSTALLED. Returns (ok, msg)."""
    data = _load_registry()
    rec = data.get(extension_id)
    if not rec or not rec.get("installed"):
        return False, f"{extension_id} is not installed"
    # remove
    del data[extension_id]
    _save_registry(data)
    # also clean up extension directory if exists
    try:
        ext_dir = Path.home() / ".cct_extensions" / extension_id
        if ext_dir.exists():
            import shutil
            shutil.rmtree(ext_dir, ignore_errors=True)
    except Exception:
        pass
    if extension_id == "customization":
        try:
            from . import customization as _cust2
            _cust2.on_uninstall()
        except Exception:
            pass
    return True, f"✓ {extension_id} uninstalled"

def enable(extension_id: str) -> tuple[bool, str]:
    """ENABLE: INSTALLED_DISABLED -> INSTALLED_ENABLED."""
    data = _load_registry()
    rec = data.get(extension_id)
    if not rec or not rec.get("installed"):
        return False, f"{extension_id} is not installed — install first"
    if rec.get("enabled"):
        return False, f"{extension_id} is already enabled"
    rec["enabled"] = True
    _save_registry(data)
    if extension_id == "customization":
        try:
            from . import customization as _cust3
            _cust3.on_enable()
        except Exception:
            pass
    return True, f"✓ {get_metadata(extension_id)['display_name']} enabled"

def disable(extension_id: str) -> tuple[bool, str]:
    """DISABLE: INSTALLED_ENABLED -> INSTALLED_DISABLED."""
    data = _load_registry()
    rec = data.get(extension_id)
    if not rec or not rec.get("installed"):
        return False, f"{extension_id} is not installed"
    if not rec.get("enabled"):
        return False, f"{extension_id} is already disabled"
    rec["enabled"] = False
    _save_registry(data)
    if extension_id == "customization":
        try:
            from . import customization as _cust4
            _cust4.on_disable()
        except Exception:
            pass
    return True, f"✓ {get_metadata(extension_id)['display_name']} disabled"

def toggle(extension_id: str) -> tuple[bool, str]:
    if is_enabled(extension_id):
        return disable(extension_id)
    if is_installed(extension_id):
        return enable(extension_id)
    return install(extension_id)

# Backward compat for old simple API (bool)
def set_enabled(key: str, enabled: bool):
    if enabled:
        # if not installed, install
        if not is_installed(key):
            install(key)
        else:
            enable(key)
    else:
        # disable but keep installed
        if is_installed(key):
            disable(key)
        else:
            # if not installed, nothing to disable
            pass

def should_show_in_menu(action_id: str) -> bool:
    """For header.NAV_ITEMS filtering: show only if installed+enabled."""
    if action_id in ("vision", "customization"):
        return False
    if action_id.startswith("ext_"):
        key = action_id[4:]
        return is_installed(key) and is_enabled(key)
    # map action -> extension key
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
) -> tuple[bool, str]:
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
            "size_bytes": _calc_size([ext_dir]),
            "manifest": manifest,
        }
        _save_registry(data)
        return True, f"✓ Custom extension '{display_name}' created and enabled successfully!"
    except Exception as e:
        return False, f"Failed to create extension: {e}"

# --------------------------------------------------------------------------
# Feature registration (for future extensions that add menu items, panels, etc.)
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
# Startup
# --------------------------------------------------------------------------

def validate_all() -> List[str]:
    """Validate installed extensions; return list of errors (empty if ok)."""
    errors = []
    for ext in list_installed():
        try:
            # check that its module files still exist (for built-ins)
            paths = _BUILTIN_PATHS.get(ext["id"], [])
            if paths:
                for p in paths:
                    if not p.exists():
                        errors.append(f"{ext['id']}: missing {p}")
        except Exception as e:
            errors.append(f"{ext['id']}: {e}")
    return errors

def load_enabled():
    """Load enabled extensions at startup — register their features."""
    for ext in list_enabled():
        try:
            # For built-ins, registration is implicit via should_show_in_menu;
            # for future third-party, we would import and call their activate().
            pass
        except Exception as e:
            # error isolation: don't crash CAT
            print(f"[extensions] failed to load {ext['id']}: {e}")

def startup():
    """Full startup sequence: discover -> validate -> load enabled -> build menu."""
    try:
        discover()
        errs = validate_all()
        if errs:
            for err in errs:
                print(f"[extensions] validate: {err}")
        load_enabled()
    except Exception as e:
        print(f"[extensions] startup failed: {e} — CAT will continue without extensions")

# Backwards compat aliases for old code that used simple enabled check
def enabled_actions() -> set:
    return {v["action"] for v in BUILTIN_EXTENSIONS.values() if is_enabled(v["id"])}

# For tests: reset to defaults (used in testing)
def _reset_for_tests():
    try:
        if REGISTRY_FILE.exists():
            REGISTRY_FILE.unlink()
    except Exception:
        pass
    # clear legacy config state too
    try:
        from . import config as _cfg
        cfg = _cfg.load_config()
        cfg.extensions = {}
        # also clear registry snapshot in config if any
        if hasattr(cfg, "user_modes"):
            # don't clear user modes here - that's for ai_modes, not extensions
            pass
        _cfg.save_config(cfg)
    except Exception:
        pass
    global _cached_state, _cached_mtime
    _cached_state = None
    _cached_mtime = 0
    # re-create with all installed+enabled
    _load_registry()

def _clear_all_for_test():
    _reset_for_tests()
