"""CAT Code Editor — Shortcut & Keybinding Manager (calc_terminal/editor/shortcuts.py).

Centralized keybinding registration, normalization, conflict detection, and resolution.
Enforces VS Code keyboard compatibility with customizable bindings.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional


@dataclass
class Keybinding:
    """Represents a key combination mapped to a command ID."""
    command_id: str
    key: str
    when: Optional[str] = None  # e.g., "editor", "preview", "global"
    priority: int = 0
    enabled: bool = True


_NORMALIZE_CACHE: Dict[str, str] = {}


def normalize_key(key: str) -> str:
    """Normalize key combinations into canonical lowercase format: [ctrl+][alt+][shift+]key."""
    if not key:
        return ""
    cached = _NORMALIZE_CACHE.get(key)
    if cached is not None:
        return cached
    parts = [p.strip().lower() for p in key.replace("-", "+").split("+")]
    modifiers = set()
    base_key = ""
    for p in parts:
        if p in ("ctrl", "control"):
            modifiers.add("ctrl")
        elif p in ("alt", "option"):
            modifiers.add("alt")
        elif p in ("shift",):
            modifiers.add("shift")
        elif p:
            base_key = p
    ordered = []
    if "ctrl" in modifiers:
        ordered.append("ctrl")
    if "alt" in modifiers:
        ordered.append("alt")
    if "shift" in modifiers:
        ordered.append("shift")
    if base_key:
        ordered.append(base_key)
    result = "+".join(ordered)
    if len(_NORMALIZE_CACHE) < 512:
        _NORMALIZE_CACHE[key] = result
    return result


class ShortcutManager:
    """Manages all keyboard shortcuts across CAT IDE."""

    CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".cat_keybindings.json")

    def __init__(self) -> None:
        self._bindings: List[Keybinding] = []
        self._by_key: Dict[str, List[Keybinding]] = {}
        self._register_default_bindings()
        self.load_user_bindings()

    def _register_default_bindings(self) -> None:
        """Register default VS Code-compatible keybindings."""
        defaults = [
            # File Operations
            Keybinding("editor.save", "ctrl+s", when="editor", priority=10),
            Keybinding("editor.save", "ctrl+s", when="global", priority=5),
            Keybinding("editor.saveAs", "ctrl+shift+s", when="editor", priority=10),
            Keybinding("editor.closeTab", "ctrl+w", when="editor", priority=10),
            Keybinding("editor.reopenClosedTab", "ctrl+shift+t", when="global", priority=5),
            Keybinding("editor.quickOpen", "ctrl+p", when="global", priority=10),
            Keybinding("editor.commandPalette", "ctrl+shift+p", when="global", priority=10),

            # Search & Navigation
            Keybinding("editor.find", "ctrl+f", when="editor", priority=10),
            Keybinding("editor.replace", "ctrl+h", when="editor", priority=10),
            Keybinding("workspace.search", "ctrl+shift+f", when="global", priority=5),
            Keybinding("editor.goToDefinition", "f12", when="editor", priority=10),
            Keybinding("editor.findReferences", "shift+f12", when="editor", priority=10),
            Keybinding("editor.rename", "f2", when="editor", priority=10),

            # Code Editing
            Keybinding("editor.toggleComment", "ctrl+/", when="editor", priority=10),
            Keybinding("editor.selectNextOccurrence", "ctrl+d", when="editor", priority=10),
            Keybinding("editor.deleteLine", "ctrl+shift+k", when="editor", priority=10),
            Keybinding("editor.moveLineUp", "alt+up", when="editor", priority=10),
            Keybinding("editor.moveLineDown", "alt+down", when="editor", priority=10),
            Keybinding("editor.copyLineUp", "shift+alt+up", when="editor", priority=10),
            Keybinding("editor.copyLineDown", "shift+alt+down", when="editor", priority=10),
            Keybinding("editor.insertLineBelow", "alt+enter", when="editor", priority=10),
            Keybinding("editor.insertLineAbove", "alt+shift+enter", when="editor", priority=10),
            Keybinding("editor.triggerCompletion", "ctrl+space", when="editor", priority=10),

            # Live Preview
            Keybinding("preview.open", "shift+enter", when="editor", priority=20),
            Keybinding("preview.open", "ctrl+shift+enter", when="editor", priority=20),
            Keybinding("preview.open", "cmd+shift+enter", when="editor", priority=20),
            Keybinding("preview.open", "super+shift+enter", when="editor", priority=20),
            Keybinding("preview.open", "ctrl+enter", when="editor", priority=20),
            Keybinding("preview.open", "shift+enter", when="global", priority=5),
            Keybinding("preview.open", "ctrl+shift+enter", when="global", priority=5),
            Keybinding("preview.reload", "ctrl+r", when="preview", priority=10),
            Keybinding("preview.toggleSplit", "ctrl+shift+s", when="preview", priority=10),

            # Workbench & Shell
            Keybinding("workbench.action.toggleSidebar", "ctrl+b", when="global", priority=10),
            Keybinding("workbench.action.terminal.toggle", "ctrl+`", when="global", priority=10),
            Keybinding("workbench.view.explorer", "ctrl+shift+e", when="global", priority=10),
            Keybinding("workbench.view.scm", "ctrl+shift+g", when="global", priority=10),
            Keybinding("workbench.action.closeOverlays", "escape", when="global", priority=10),

            # Viewer
            Keybinding("viewer.fullscreen", "f11", when="global", priority=10),
            Keybinding("viewer.zoomIn", "ctrl+=", when="viewer", priority=10),
            Keybinding("viewer.zoomOut", "ctrl+-", when="viewer", priority=10),
        ]
        for kb in defaults:
            self.register(kb)

    def _rebuild_index(self) -> None:
        idx: Dict[str, List[Keybinding]] = {}
        for b in self._bindings:
            if b.enabled:
                idx.setdefault(b.key, []).append(b)
        self._by_key = idx

    def register(self, binding: Keybinding) -> None:
        """Register a keybinding with normalized key representation."""
        binding.key = normalize_key(binding.key)
        self._bindings.append(binding)
        if binding.enabled:
            self._by_key.setdefault(binding.key, []).append(binding)

    def unregister(self, command_id: str, key: Optional[str] = None) -> None:
        """Remove a keybinding by command ID and optionally key string."""
        norm_key = normalize_key(key) if key else None
        self._bindings = [
            b for b in self._bindings
            if not (b.command_id == command_id and (norm_key is None or b.key == norm_key))
        ]
        self._rebuild_index()

    def detect_conflicts(self, key: str, when: Optional[str] = None) -> List[Keybinding]:
        """Detect any existing enabled keybindings that share the same key and compatible context."""
        norm_key = normalize_key(key)
        candidates = self._by_key.get(norm_key, [])
        conflicts = []
        for b in candidates:
            if not b.enabled:
                continue
            if when is None or b.when is None or b.when == "global" or when == "global" or b.when == when:
                conflicts.append(b)
        return conflicts

    def resolve(self, raw_key: str, context: Optional[str] = None) -> Optional[str]:
        return self._resolve_impl(raw_key, context)

    match = resolve

    def _resolve_impl(self, raw_key: str, context: Optional[str] = None) -> Optional[str]:
        """Resolve a raw keyboard input event into the winning command ID."""
        norm_key = normalize_key(raw_key)
        candidates = self._by_key.get(norm_key)
        if not candidates:
            return None
        matching = []
        for b in candidates:
            if not b.enabled:
                continue
            # Context match: exact context wins, or global matches if no specific binding
            if context and b.when == context:
                matching.append((b.priority + 20, b.command_id))
            elif b.when in (None, "global"):
                matching.append((b.priority, b.command_id))
            elif not context:
                matching.append((b.priority, b.command_id))
        if not matching:
            return None
        # Highest score wins
        matching.sort(key=lambda item: item[0], reverse=True)
        return matching[0][1]

    def get_keybindings_for_command(self, command_id: str) -> List[str]:
        """Return all active key combination strings for a command ID."""
        keys = []
        for b in self._bindings:
            if b.command_id == command_id and b.enabled and b.key not in keys:
                keys.append(b.key)
        return keys

    def list_bindings(self) -> List[Keybinding]:
        """Return all registered keybindings."""
        return list(self._bindings)

    def load_user_bindings(self) -> None:
        """Load user-configured keybinding overrides from ~/.cat_keybindings.json."""
        if not os.path.exists(self.CONFIG_PATH):
            return
        try:
            with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                items = json.load(f)
                if isinstance(items, list):
                    for item in items:
                        cmd = item.get("command_id")
                        key = item.get("key")
                        if cmd and key:
                            # Higher priority for user customizations
                            self.register(Keybinding(
                                command_id=cmd,
                                key=key,
                                when=item.get("when"),
                                priority=item.get("priority", 50),
                                enabled=item.get("enabled", True),
                            ))
        except Exception:
            pass

    def save_user_bindings(self) -> bool:
        """Persist user custom keybindings to disk."""
        try:
            user_bindings = [asdict(b) for b in self._bindings if b.priority >= 50]
            with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(user_bindings, f, indent=2)
            return True
        except Exception:
            return False


# Global singleton manager
_GLOBAL_SHORTCUT_MANAGER: Optional[ShortcutManager] = None


def get_shortcut_manager() -> ShortcutManager:
    """Return the global ShortcutManager singleton."""
    global _GLOBAL_SHORTCUT_MANAGER
    if _GLOBAL_SHORTCUT_MANAGER is None:
        _GLOBAL_SHORTCUT_MANAGER = ShortcutManager()
    return _GLOBAL_SHORTCUT_MANAGER
