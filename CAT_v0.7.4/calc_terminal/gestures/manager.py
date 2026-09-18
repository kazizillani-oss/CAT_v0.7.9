"""
CAT Gestures — manager.py: persistence + CRUD + event dispatch.

Storage: ~/.cct_gestures.json  (list of gesture dicts)
If missing, defaults are seeded from bindings.DEFAULT_GESTURES.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Dict, List, Optional

from .bindings import DEFAULT_GESTURES, GESTURE_ACTIONS, GESTURE_TARGETS, GESTURE_TRIGGERS

STORE_PATH = os.path.join(os.path.expanduser("~"), ".cct_gestures.json")

# In-memory cache
_cache: Optional[List[Dict]] = None
_cache_mtime: float = 0


class Gesture(dict):
    """Typed dict for a gesture — behaves like a plain dict for JSON compat."""


def _load() -> List[Dict]:
    global _cache, _cache_mtime
    try:
        mtime = os.path.getmtime(STORE_PATH) if os.path.exists(STORE_PATH) else 0
        if _cache is not None and mtime == _cache_mtime:
            return list(_cache)
    except Exception:
        pass
    if not os.path.exists(STORE_PATH):
        data = [dict(g) for g in DEFAULT_GESTURES]
        _save(data)
        _cache = list(data)
        try:
            _cache_mtime = os.path.getmtime(STORE_PATH)
        except Exception:
            _cache_mtime = time.time()
        return list(data)
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                _cache = list(data)
                try:
                    _cache_mtime = os.path.getmtime(STORE_PATH)
                except Exception:
                    _cache_mtime = time.time()
                return list(data)
    except Exception:
        pass
    return [dict(g) for g in DEFAULT_GESTURES]


def _save(data: List[Dict]) -> bool:
    global _cache, _cache_mtime
    try:
        with open(STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        _cache = list(data)
        try:
            _cache_mtime = os.path.getmtime(STORE_PATH)
        except Exception:
            _cache_mtime = time.time()
        return True
    except Exception:
        return False


def list_gestures() -> List[Dict]:
    return _load()


def get_gesture(gesture_id: str) -> Optional[Dict]:
    for g in _load():
        if g.get("id") == gesture_id:
            return g
    return None


def find_gesture(trigger: str, target: str) -> Optional[Dict]:
    """Find enabled gesture matching trigger + target."""
    try:
        from .. import extensions as _ext
        if not _ext.is_enabled("gestures"):
            return None
    except Exception:
        pass
    for g in _load():
        if g.get("trigger") == trigger and g.get("target") == target and g.get("enabled"):
            return g
    return None


def _is_valid_shortcut(keys: str) -> bool:
    """Validate shortcut like ctrl+s, shift+enter, ctrl+shift+p, f5, alt+enter."""
    import re
    if not keys or not isinstance(keys, str):
        return False
    k = keys.strip().lower()
    # normalize: allow combos with +, allow single keys f1-f12, letters, numbers, enter/space/tab/esc etc
    pattern = r"^(?:(?:ctrl|shift|alt|cmd|meta)\+)*(?:[a-z0-9]|f(?:[1-9]|1[0-2])|enter|space|tab|esc|escape|backspace|delete|up|down|left|right|home|end|pageup|pagedown|insert)$"
    return bool(re.match(pattern, k))

def add_gesture(
    name: str,
    trigger: str,
    target: str,
    action: str,
    description: str = "",
    enabled: bool = True,
    keys: str = "",
) -> Optional[Dict]:
    if trigger not in GESTURE_TRIGGERS:
        return None
    if target not in GESTURE_TARGETS:
        return None
    if action not in GESTURE_ACTIONS:
        return None
    # shortcut trigger requires a key combo
    if trigger == "shortcut":
        if not keys or not _is_valid_shortcut(keys):
            return None
        # ensure keys unique among enabled shortcuts
        for g in _load():
            if g.get("trigger") == "shortcut" and g.get("keys","").lower() == keys.lower() and g.get("enabled"):
                return None  # duplicate
    data = _load()
    gesture = {
        "id": f"gesture_{uuid.uuid4().hex[:8]}",
        "name": name,
        "trigger": trigger,
        "target": target,
        "action": action,
        "enabled": bool(enabled),
        "description": description or f"{trigger} on {target} → {action}",
        "created_at": time.time(),
    }
    if trigger == "shortcut" and keys:
        gesture["keys"] = keys.strip().lower()
        gesture["description"] = f"{keys} ({target}) → {action}"
    data.append(gesture)
    _save(data)
    _publish_gesture_event("gesture_created", gesture)
    return gesture


def find_shortcut(keys: str) -> Optional[Dict]:
    """Find enabled shortcut gesture matching keys (case-insensitive)."""
    # Extension guard: Gestures disabled → inactive (spec section 5)
    try:
        from .. import extensions as _ext
        if not _ext.is_enabled("gestures"):
            return None
    except Exception:
        pass
    k = (keys or "").strip().lower()
    if not k:
        return None
    for g in _load():
        if g.get("trigger") == "shortcut" and g.get("keys","").lower() == k and g.get("enabled"):
            return g
    return None


def handle_shortcut(keys: str, app=None, context: Optional[Dict] = None) -> bool:
    """Dispatch a keyboard shortcut."""
    # Extension guard: Gestures disabled → inactive
    try:
        from .. import extensions as _ext
        if not _ext.is_enabled("gestures"):
            return False
    except Exception:
        pass
    g = find_shortcut(keys)
    if not g:
        return False
    action = g.get("action")
    if not action:
        return False
    try:
        from .bindings import ACTION_HANDLERS
        handler = ACTION_HANDLERS.get(action)
        if handler is not None:
            return bool(handler(app, context or {}, g))
        return _builtin_handler(action, app, context or {}, g)
    except Exception:
        return False


def update_gesture(gesture_id: str, **fields) -> Optional[Dict]:
    data = _load()
    for g in data:
        if g.get("id") == gesture_id:
            for k in ("name", "trigger", "target", "action", "enabled", "description", "keys"):
                if k in fields:
                    if k == "trigger" and fields[k] not in GESTURE_TRIGGERS:
                        continue
                    if k == "target" and fields[k] not in GESTURE_TARGETS:
                        continue
                    if k == "action" and fields[k] not in GESTURE_ACTIONS:
                        continue
                    if k == "keys" and fields[k]:
                        if not _is_valid_shortcut(str(fields[k])):
                            continue
                        fields[k] = str(fields[k]).strip().lower()
                    g[k] = fields[k]
            _save(data)
            _publish_gesture_event("gesture_updated", g)
            return g
    return None


def delete_gesture(gesture_id: str) -> bool:
    data = _load()
    remaining = [g for g in data if g.get("id") != gesture_id]
    if len(remaining) == len(data):
        return False
    _save(remaining)
    _publish_gesture_event("gesture_deleted", {"id": gesture_id})
    return True


def toggle_gesture(gesture_id: str) -> Optional[Dict]:
    data = _load()
    for g in data:
        if g.get("id") == gesture_id:
            g["enabled"] = not bool(g.get("enabled", True))
            _save(data)
            _publish_gesture_event("gesture_toggled", g)
            return g
    return None


def reset_defaults() -> List[Dict]:
    data = [dict(g) for g in DEFAULT_GESTURES]
    _save(data)
    _publish_gesture_event("gestures_reset", {"count": len(data)})
    return list(data)


def _publish_gesture_event(topic: str, detail: Dict):
    try:
        from .. import eventbus

        eventbus.bus.publish(topic, **detail)
    except Exception:
        pass


# ---------------------------------------------------------------- handler dispatch

def handle_gesture(trigger: str, target: str, app=None, context: Optional[Dict] = None) -> bool:
    """
    Dispatch a gesture: look up enabled gesture for (trigger, target),
    then invoke its action handler.

    Returns True if a handler ran, False if no matching gesture/handler.
    """
    try:
        from .. import extensions as _ext
        if not _ext.is_enabled("gestures"):
            return False
    except Exception:
        pass
    gesture = find_gesture(trigger, target)
    if not gesture:
        return False
    action = gesture.get("action")
    if not action:
        return False
    # Try to get handler from bindings
    try:
        from .bindings import ACTION_HANDLERS

        handler = ACTION_HANDLERS.get(action)
        if handler is not None:
            try:
                return bool(handler(app, context or {}, gesture))
            except Exception:
                return False
        # Built-in fallback handlers (no app dependency)
        return _builtin_handler(action, app, context or {}, gesture)
    except Exception:
        return False


def _builtin_handler(action: str, app, context: Dict, gesture: Dict) -> bool:
    """Fallback handlers when no custom handler registered — covers spec examples."""
    try:
        # --- new shortcut actions ---
        if action == "show_preview":
            # Shift+Enter or toolbar ▷
            if app and hasattr(app, "_workspace_shell") and app._workspace_shell:
                try:
                    # find active file or any web file
                    editor = app._workspace_shell.editor
                    # delegate to EditorPane's preview if possible
                    if editor and hasattr(editor, "action_show_preview"):
                        editor.action_show_preview()
                        return True
                    # fallback: post PreviewRequested
                    from ..ui.events import PreviewRequested
                    # try to get path from context or active editor
                    path = (context.get("path") if context else None)
                    if not path and editor:
                        area = editor.active_text_area() if hasattr(editor, "active_text_area") else None
                        path = getattr(area, "path", None) if area else None
                    if path:
                        app.post_message(PreviewRequested(path))
                        return True
                    # try workspace root fallback
                    app.post_message(PreviewRequested(""))
                    return True
                except Exception:
                    pass
            return False
        if action == "toggle_preview":
            if app and hasattr(app, "action_toggle_preview"):
                app.action_toggle_preview()
                return True
            return False
        if action == "save_file":
            if app and hasattr(app, "action_save_file"):
                app.action_save_file()
                return True
            # fallback via editor
            if app and hasattr(app, "_workspace_shell") and app._workspace_shell:
                try:
                    app._workspace_shell.editor.save_active()
                    return True
                except Exception:
                    pass
            return False
        if action == "toggle_sidebar":
            if app and hasattr(app, "action_toggle_sidebar"):
                app.action_toggle_sidebar()
                return True
            return False
        if action == "open_palette":
            if app and hasattr(app, "action_open_palette"):
                app.action_open_palette()
                return True
            return False
        if action == "open_gestures":
            if app:
                try:
                    from ..ui.gestures_panel import GesturesPanel
                    app.push_screen(GesturesPanel())
                    return True
                except Exception:
                    pass
            return False
        if action == "open_vision":
            if app:
                try:
                    from ..ui.vision_panel import VisionPanel
                    app.push_screen(VisionPanel())
                    return True
                except Exception:
                    pass
            return False

        if action == "open_vscode":
            # Double-click editor → open in VS Code
            path = (context.get("path") or context.get("workspace") or "") if context else ""
            if app is not None and hasattr(app, "_workspace_root") and app._workspace_root:
                path = path or app._workspace_root
            if path:
                import subprocess
                import shutil
                code_bin = shutil.which("code") or shutil.which("code.cmd")
                if code_bin:
                    subprocess.Popen([code_bin, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if app:
                        try:
                            app._system_note(f"Opened {path} in VS Code")
                        except Exception:
                            pass
                    return True
                if app:
                    try:
                        app._system_note("VS Code not found (install 'code' on PATH)")
                    except Exception:
                        pass
            return False

        if action == "fullscreen_preview":
            if app and hasattr(app, "action_toggle_right_pane_fullscreen"):
                app.action_toggle_right_pane_fullscreen()
                return True
            return False

        if action == "fullscreen_editor":
            if app and hasattr(app, "action_toggle_right_pane_fullscreen"):
                app.action_toggle_right_pane_fullscreen()
                return True
            return False

        if action == "quick_actions":
            path = context.get("path", "") if context else ""
            if app:
                try:
                    from ..ui.context_menu import FileQuickActions

                    # Show quick actions via system note fallback if UI not available
                    app._system_note(f"Quick actions for: {path or 'file'}")
                except Exception:
                    pass
            return True

        if action == "reveal_actions":
            path = context.get("path", "") if context else ""
            if app:
                try:
                    app._system_note(f"Actions revealed for: {path}")
                except Exception:
                    pass
            return True

        if action == "before_after":
            if app and hasattr(app, "_workspace_shell"):
                try:
                    editor = app._workspace_shell.editor
                    if editor:
                        editor.show_diff()
                        return True
                except Exception:
                    pass
            return False

        if action == "edit_message":
            turn_id = context.get("turn_id") if context else None
            if turn_id and app:
                try:
                    # Trigger rewrite via MessageContextAction
                    from ..ui.events import MessageContextAction

                    app.post_message(MessageContextAction("rewrite", turn_id))
                    return True
                except Exception:
                    pass
            return False

        if action == "copy_path":
            path = context.get("path", "") if context else ""
            if path:
                try:
                    from .. import code_editor

                    code_editor.copy_to_clipboard(path)
                    if app:
                        app._system_note(f"Copied path: {path}")
                    return True
                except Exception:
                    pass
            return False
    except Exception:
        return False
    return False


# Convenience: register builtins on import
try:
    from .bindings import ACTION_HANDLERS as _AH

    for _act in ("open_vscode", "fullscreen_preview", "fullscreen_editor", "quick_actions", "reveal_actions", "before_after", "edit_message", "copy_path", "show_preview", "toggle_preview", "save_file", "toggle_sidebar", "open_palette", "open_gestures", "open_vision"):
        if _act not in _AH:
            _AH[_act] = lambda app, ctx, g, _a=_act: _builtin_handler(_a, app, ctx, g)
except Exception:
    pass
