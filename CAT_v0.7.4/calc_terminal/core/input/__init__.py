"""
CAT Core Input Package — proxy re-export of calc_terminal.input.
"""

from ...input import (
    DeviceType,
    InputCapabilities,
    detect_capabilities,
    get_input_capabilities,
    set_touch_mode,
    toggle_touch_mode,
    register_listener,
    unregister_listener,
    TouchTapRecognizer,
    TouchScrollHandler,
    TAP_MAX_DISTANCE,
    TAP_MAX_DURATION,
    DOUBLE_TAP_MAX_DELAY,
    LONG_PRESS_DURATION,
    TouchHitZone,
    RESIZER_TOUCH_PADDING,
    TouchFocusManager,
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
