"""
CAT Gestures — configurable gesture -> action -> handler system.

Each gesture maps a user input (double-click, triple-click, etc.) on a
specific UI surface to an action handled by the app.

Storage: ~/.cct_gestures.json (JSON list of gesture dicts)
"""

from .manager import (
    Gesture,
    list_gestures,
    get_gesture,
    add_gesture,
    update_gesture,
    delete_gesture,
    toggle_gesture,
    reset_defaults,
    handle_gesture,
)
from .bindings import (
    ACTION_HANDLERS,
    GESTURE_TARGETS,
    GESTURE_TRIGGERS,
    DEFAULT_GESTURES,
)

__all__ = [
    "Gesture",
    "list_gestures",
    "get_gesture",
    "add_gesture",
    "update_gesture",
    "delete_gesture",
    "toggle_gesture",
    "reset_defaults",
    "handle_gesture",
    "ACTION_HANDLERS",
    "GESTURE_TARGETS",
    "GESTURE_TRIGGERS",
    "DEFAULT_GESTURES",
]
