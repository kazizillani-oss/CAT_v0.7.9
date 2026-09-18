"""
CAT Input Architecture Module
Centralized input abstraction for touchscreens, 2-in-1s, mice, and keyboards.
"""

from .capabilities import (
    DeviceType,
    InputCapabilities,
    detect_capabilities,
    get_input_capabilities,
    set_touch_mode,
    toggle_touch_mode,
    register_listener,
    unregister_listener,
)
from .touch import (
    TouchTapRecognizer,
    TouchScrollHandler,
    TAP_MAX_DISTANCE,
    TAP_MAX_DURATION,
    DOUBLE_TAP_MAX_DELAY,
    LONG_PRESS_DURATION,
)
from .pointer import (
    TouchHitZone,
    RESIZER_TOUCH_PADDING,
)
from .focus import (
    TouchFocusManager,
)
from .gestures import (
    GestureBridge,
)

__all__ = [
    "DeviceType",
    "InputCapabilities",
    "detect_capabilities",
    "get_input_capabilities",
    "set_touch_mode",
    "toggle_touch_mode",
    "register_listener",
    "unregister_listener",
    "TouchTapRecognizer",
    "TouchScrollHandler",
    "TAP_MAX_DISTANCE",
    "TAP_MAX_DURATION",
    "DOUBLE_TAP_MAX_DELAY",
    "LONG_PRESS_DURATION",
    "TouchHitZone",
    "RESIZER_TOUCH_PADDING",
    "TouchFocusManager",
    "GestureBridge",
]
