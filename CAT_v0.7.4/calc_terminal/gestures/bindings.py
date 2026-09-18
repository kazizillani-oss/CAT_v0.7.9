"""
CAT Gestures — bindings.py: action registry and default mappings.

Conceptually:
    Gesture (trigger + target) -> Action -> Handler
    e.g. double_click on editor -> open_vscode -> handler opens VS Code
"""

# Valid gesture triggers
GESTURE_TRIGGERS = (
    "double_click",
    "triple_click",
    "long_press",
    "swipe_left",
    "swipe_right",
    "shortcut",  # custom keyboard shortcut (user-defined key combo)
)

# Valid gesture targets (UI surfaces)
GESTURE_TARGETS = (
    "editor",
    "preview",
    "file",
    "diff",
    "chat",
    "explorer",
    "global",  # shortcut can be global
)

# Valid shortcut key combos (user-typed, validated against this allow-list pattern)
# We allow any combo matching: [ctrl+][shift+][alt+]<key> where key is a-z,0-9,f1-f12,enter,space,tab, etc.
# The manager validates via regex, not this tuple — this is just for the picker hint.
SHORTCUT_HINTS = (
    "ctrl+s",
    "ctrl+o",
    "ctrl+enter",
    "shift+enter",
    "ctrl+shift+p",
    "ctrl+shift+f",
    "f5",
    "alt+enter",
)

# Valid actions
GESTURE_ACTIONS = (
    "open_vscode",
    "fullscreen_preview",
    "fullscreen_editor",
    "quick_actions",
    "reveal_actions",
    "open_diff",
    "before_after",
    "edit_message",
    "copy_path",
    "toggle_gesture",
    "show_preview",      # web preview (▷ / Shift+Enter)
    "toggle_preview",    # Ctrl+Shift+P
    "save_file",         # Ctrl+S
    "toggle_sidebar",    # Ctrl+B
    "open_palette",      # Ctrl+P
    "open_gestures",     # open this panel
    "open_vision",       # open CAT Vision
)

# Default gestures as shipped — covers spec examples
DEFAULT_GESTURES = [
    {
        "id": "gesture_editor_vscode",
        "name": "Double-click editor → VS Code",
        "trigger": "double_click",
        "target": "editor",
        "action": "open_vscode",
        "enabled": True,
        "description": "Double-click Code Editor → Open project in VS Code",
    },
    {
        "id": "gesture_preview_fullscreen",
        "name": "Double-click preview → Fullscreen",
        "trigger": "double_click",
        "target": "preview",
        "action": "fullscreen_preview",
        "enabled": True,
        "description": "Double-click Preview → Fullscreen Preview",
    },
    {
        "id": "gesture_file_quick",
        "name": "Triple-click file → Quick actions",
        "trigger": "triple_click",
        "target": "file",
        "action": "quick_actions",
        "enabled": True,
        "description": "Triple-click file → Open quick actions",
    },
    {
        "id": "gesture_file_reveal",
        "name": "Gesture on file → Reveal actions",
        "trigger": "long_press",
        "target": "file",
        "action": "reveal_actions",
        "enabled": True,
        "description": "Gesture on file → Reveal actions",
    },
    {
        "id": "gesture_diff_beforeafter",
        "name": "Gesture on diff → Before/After",
        "trigger": "double_click",
        "target": "diff",
        "action": "before_after",
        "enabled": True,
        "description": "Gesture on diff → Open before/after view",
    },
    {
        "id": "gesture_chat_edit",
        "name": "Gesture on chat → Edit message",
        "trigger": "double_click",
        "target": "chat",
        "action": "edit_message",
        "enabled": True,
        "description": "Gesture on chat message → Edit message",
    },
    # --- Shortcut defaults (user can edit/disable/create new) ---
    {
        "id": "gesture_shortcut_preview",
        "name": "Shift+Enter → Preview",
        "trigger": "shortcut",
        "target": "editor",
        "action": "show_preview",
        "enabled": True,
        "description": "Shift+Enter (editor) → Show Web Preview",
        "keys": "shift+enter",
    },
    {
        "id": "gesture_shortcut_save",
        "name": "Ctrl+S → Save",
        "trigger": "shortcut",
        "target": "editor",
        "action": "save_file",
        "enabled": True,
        "description": "Ctrl+S (editor) → Save File",
        "keys": "ctrl+s",
    },
    {
        "id": "gesture_shortcut_toggle_preview",
        "name": "Ctrl+Shift+P → Toggle Preview",
        "trigger": "shortcut",
        "target": "global",
        "action": "toggle_preview",
        "enabled": True,
        "description": "Ctrl+Shift+P (global) → Toggle Web Preview",
        "keys": "ctrl+shift+p",
    },
    {
        "id": "gesture_shortcut_fullscreen",
        "name": "F11 → Fullscreen Code Editor",
        "trigger": "shortcut",
        "target": "editor",
        "action": "fullscreen_editor",
        "enabled": True,
        "description": "F11 (editor) → Fullscreen Code Editor",
        "keys": "f11",
    },
]

# Action -> handler mapping (filled at runtime by manager)
# Handlers are callables: handler(app, context_dict) -> bool
ACTION_HANDLERS = {}


def register_handler(action, func):
    """Register a handler for an action."""
    ACTION_HANDLERS[action] = func


def get_handler(action):
    return ACTION_HANDLERS.get(action)
