"""
CAT Input Architecture — capabilities.py
Runtime input device detection and capabilities abstraction.

Detects:
- Touchscreen presence and maximum concurrent touch points (Win32 SM_MAXIMUMTOUCHES, SM_DIGITIZER)
- Mouse availability (SM_MOUSEPRESENT)
- Convertible / 2-in-1 slate mode (SM_CONVERTIBLESLATEMODE)
- Tablet PC capabilities (SM_TABLETPC)
- Display scaling / DPI awareness

Classifies runtime environment into:
- Normal Desktop
- Touchscreen Laptop
- 2-in-1 / Convertible
- Tablet-style Windows Device
"""

from __future__ import annotations

import os
import sys
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, List

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".cct_config.json")


class DeviceType(str, Enum):
    DESKTOP = "desktop"
    TOUCHSCREEN_LAPTOP = "touchscreen_laptop"
    CONVERTIBLE_2IN1 = "convertible_2in1"
    TABLET_WINDOWS = "tablet_windows"

    @property
    def display_name(self) -> str:
        if self == DeviceType.TOUCHSCREEN_LAPTOP:
            return "Touchscreen Laptop"
        if self == DeviceType.CONVERTIBLE_2IN1:
            return "2-in-1 / Convertible"
        if self == DeviceType.TABLET_WINDOWS:
            return "Tablet-style Windows Device"
        return "Normal Desktop"


@dataclass
class InputCapabilities:
    """Centralized input capability descriptor reusable across CAT UI."""
    touchscreen_available: bool = False
    mouse_available: bool = True
    keyboard_available: bool = True
    touch_primary: bool = False
    touch_mode_enabled: bool = False
    max_touch_points: int = 0
    device_type: DeviceType = DeviceType.DESKTOP
    slate_mode: bool = False
    scaling_factor: float = 1.0

    def to_dict(self) -> dict:
        return {
            "touchscreen_available": self.touchscreen_available,
            "mouse_available": self.mouse_available,
            "keyboard_available": self.keyboard_available,
            "touch_primary": self.touch_primary,
            "touch_mode_enabled": self.touch_mode_enabled,
            "max_touch_points": self.max_touch_points,
            "device_type": self.device_type.value,
            "device_name": self.device_type.display_name,
            "slate_mode": self.slate_mode,
            "scaling_factor": self.scaling_factor,
        }


# Listeners for capability changes (e.g. tablet flip, touch mode toggle)
_LISTENERS: List[Callable[[InputCapabilities], None]] = []
_CURRENT_CAPABILITIES: Optional[InputCapabilities] = None


def _read_config_touch_mode() -> Optional[bool]:
    """Read user-configured touch mode preference from ~/.cct_config.json if set."""
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "touch_mode" in data:
                    val = data["touch_mode"]
                    if isinstance(val, bool):
                        return val
    except Exception:
        pass
    return None


def _save_config_touch_mode(enabled: bool) -> None:
    """Save user touch mode toggle to ~/.cct_config.json."""
    try:
        data = {}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data["touch_mode"] = bool(enabled)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def detect_capabilities() -> InputCapabilities:
    """Perform real runtime capability detection on Windows and cross-platform."""
    touchscreen_available = False
    mouse_available = True
    keyboard_available = True
    max_touch_points = 0
    slate_mode = False
    is_tablet_pc = False
    slate_mode_val = None
    device_type = DeviceType.DESKTOP
    scaling_factor = 1.0

    # Win32 detection
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32

            # SM_DIGITIZER (94)
            # 0x01 = NID_INTEGRATED_TOUCH, 0x02 = NID_EXTERNAL_TOUCH, 0x40 = NID_MULTI_INPUT, 0x80 = NID_READY
            digitizer_val = user32.GetSystemMetrics(94)
            # SM_MAXIMUMTOUCHES (95) - returns number of touches or 0
            max_touches = user32.GetSystemMetrics(95)
            max_touch_points = max(0, int(max_touches))

            # SM_MOUSEPRESENT (19)
            mouse_present = user32.GetSystemMetrics(19)
            mouse_available = bool(mouse_present)

            # SM_TABLETPC (86)
            tablet_pc_val = user32.GetSystemMetrics(86)
            is_tablet_pc = bool(tablet_pc_val)

            # SM_CONVERTIBLESLATEMODE (0x2003 = 8195)
            # 0 = laptop/clamshell mode, 1 = slate/tablet mode
            slate_mode_val = user32.GetSystemMetrics(0x2003)
            slate_mode = bool(slate_mode_val == 1)

            # If max touches > 0 or digitizer has touch bits
            if max_touch_points > 0 or (digitizer_val & 0x03):
                touchscreen_available = True

            # DPI detection
            try:
                dpi = user32.GetDpiForSystem()
                if dpi > 0:
                    scaling_factor = round(dpi / 96.0, 2)
            except (AttributeError, Exception):
                scaling_factor = 1.0

        except Exception:
            # Fallback if ctypes or user32 fails
            touchscreen_available = False
            mouse_available = True

    # Device Classification
    if touchscreen_available:
        if slate_mode or (is_tablet_pc and not mouse_available):
            device_type = DeviceType.TABLET_WINDOWS
        elif is_tablet_pc or slate_mode_val == 0:
            # Device has 2-in-1 sensor or convertible capability
            device_type = DeviceType.CONVERTIBLE_2IN1
        else:
            device_type = DeviceType.TOUCHSCREEN_LAPTOP
    else:
        device_type = DeviceType.DESKTOP

    # Touch Primary determination
    touch_primary = False
    if device_type == DeviceType.TABLET_WINDOWS or slate_mode:
        touch_primary = True

    # Touch Mode Enabled determination:
    # 1. Environment variable override: CCT_TOUCH_MODE=1 / 0
    # 2. Config file preference: ~/.cct_config.json -> touch_mode
    # 3. Default: True if touchscreen is detected, False otherwise
    env_override = os.environ.get("CCT_TOUCH_MODE", "").strip().lower()
    config_pref = _read_config_touch_mode()

    if env_override in ("1", "true", "yes", "on"):
        touch_mode_enabled = True
    elif env_override in ("0", "false", "no", "off"):
        touch_mode_enabled = False
    elif config_pref is not None:
        touch_mode_enabled = config_pref
    else:
        touch_mode_enabled = bool(touchscreen_available)

    return InputCapabilities(
        touchscreen_available=touchscreen_available,
        mouse_available=mouse_available,
        keyboard_available=keyboard_available,
        touch_primary=touch_primary,
        touch_mode_enabled=touch_mode_enabled,
        max_touch_points=max_touch_points,
        device_type=device_type,
        slate_mode=slate_mode,
        scaling_factor=scaling_factor,
    )


def get_input_capabilities(force_refresh: bool = False) -> InputCapabilities:
    """Get or initialize the cached input capabilities."""
    global _CURRENT_CAPABILITIES
    if _CURRENT_CAPABILITIES is None or force_refresh:
        _CURRENT_CAPABILITIES = detect_capabilities()
    return _CURRENT_CAPABILITIES


def set_touch_mode(enabled: bool, persist: bool = True) -> InputCapabilities:
    """Explicitly enable or disable touch-friendly mode."""
    caps = get_input_capabilities()
    caps.touch_mode_enabled = bool(enabled)
    if persist:
        _save_config_touch_mode(caps.touch_mode_enabled)
    _notify_listeners(caps)
    return caps


def toggle_touch_mode(persist: bool = True) -> bool:
    """Toggle touch-friendly mode on or off."""
    caps = get_input_capabilities()
    new_state = not caps.touch_mode_enabled
    set_touch_mode(new_state, persist=persist)
    return new_state


def register_listener(callback: Callable[[InputCapabilities], None]) -> None:
    """Register a listener invoked when input capabilities or touch mode changes."""
    if callback not in _LISTENERS:
        _LISTENERS.append(callback)


def unregister_listener(callback: Callable[[InputCapabilities], None]) -> None:
    """Unregister a capability listener."""
    if callback in _LISTENERS:
        _LISTENERS.remove(callback)


def _notify_listeners(caps: InputCapabilities) -> None:
    for cb in list(_LISTENERS):
        try:
            cb(caps)
        except Exception:
            pass
