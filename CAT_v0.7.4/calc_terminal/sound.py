"""
Terminal sound effects for CCT — dependency-free, cross-platform.

No audio libraries are required. On Windows, the built-in `winsound`
module plays real short tones. Everywhere else (macOS/Linux terminals,
and Windows too if winsound is unavailable for some reason) it falls
back to the ASCII BEL character (`\\a`), which every terminal emulator
interprets as "ring the system bell" — the same mechanism your shell
uses for tab-complete errors. Some terminals mute this by default; if
nothing is audible, check your terminal's preferences for "audible
bell" / "terminal bell" and make sure it's turned on.

This module never raises and never blocks noticeably — a sound cue is
a nice-to-have, not something that should ever break the app or stall
an animation.
"""

import json
import os
import sys
import threading
import time

try:
    import winsound
    _HAS_WINSOUND = True
except ImportError:
    winsound = None
    _HAS_WINSOUND = False

_SETTINGS_FILE = os.path.expanduser("~/.cat_audio_settings.json")
_DEFAULT_SETTINGS = {
    "enabled": True,
    "volume": 80,
    "wake_sound": True,
    "listen_sound": True,
    "completion_sound": True,
    "close_sound": True,
    "notify_sound": True,
}

_SETTINGS = dict(_DEFAULT_SETTINGS)


def _load_settings():
    global _SETTINGS
    try:
        if os.path.exists(_SETTINGS_FILE):
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    _SETTINGS.update(saved)
    except Exception:
        pass


def _save_settings():
    try:
        os.makedirs(os.path.dirname(os.path.abspath(_SETTINGS_FILE)), exist_ok=True)
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(_SETTINGS, f, indent=2)
    except Exception:
        pass


_load_settings()


def get_audio_settings():
    """Return a copy of the current audio settings dictionary."""
    return dict(_SETTINGS)


def update_audio_settings(key, value):
    """Update a specific audio setting and persist to disk."""
    _SETTINGS[key] = value
    _save_settings()


def is_sound_enabled(event="all"):
    """Check whether master sound or a specific sound event is enabled."""
    if not _SETTINGS.get("enabled", True):
        return False
    key_map = {
        "wake_kitty": "wake_sound",
        "wake": "wake_sound",
        "listen_start": "listen_sound",
        "completion": "completion_sound",
        "success": "completion_sound",
        "voice_close": "close_sound",
        "notify": "notify_sound",
    }
    setting_key = key_map.get(event)
    if setting_key:
        return bool(_SETTINGS.get(setting_key, True))
    return True


def set_enabled(value):
    _SETTINGS["enabled"] = bool(value)
    _save_settings()


def is_enabled():
    return _SETTINGS.get("enabled", True)


def _bell(times=1, gap=0.08):
    for i in range(times):
        sys.stdout.write("\a")
        sys.stdout.flush()
        if i < times - 1:
            time.sleep(gap)


def _tone(freq, duration_ms):
    """Try a real tone via winsound. Returns True if it actually played
    a tone (so callers know NOT to also fall back to a bell)."""
    if not _HAS_WINSOUND:
        return False
    try:
        winsound.Beep(int(freq), int(duration_ms))
        return True
    except Exception:
        return False


def play_async(event="notify"):
    """Fire sound asynchronously on a daemon thread so the calling thread never waits."""
    play(event)


# ---------------------------------------------------------------- events --
def _play_blocking(event="notify"):
    """The actual tone/bell sequence. Runs on a worker thread via play()
    so no request/tool path ever waits on audio hardware."""
    try:
        if event in ("wake_kitty", "wake"):
            # Futuristic soft electronic cat-inspired ascending chime
            if not _tone(587, 50):  # D5
                _bell(1)
            else:
                time.sleep(0.02)
                _tone(880, 60)      # A5
                time.sleep(0.02)
                _tone(1318, 90)     # E6
        elif event == "listen_start":
            # Crisp activation chirp
            if not _tone(880, 60):
                _bell(1)
        elif event in ("completion", "success"):
            # Gentle soft completion chime
            if not _tone(784, 70):  # G5
                _bell(1)
            else:
                time.sleep(0.03)
                _tone(1046, 110)    # C6
        elif event == "voice_close":
            # Descending calm tone
            if not _tone(880, 60):
                _bell(1)
            else:
                time.sleep(0.02)
                _tone(440, 90)
        elif event == "startup":
            if not _tone(660, 90):
                _bell(1)
            else:
                _tone(880, 110)
        elif event == "error":
            if not _tone(220, 160):
                _bell(2, gap=0.12)
        elif event == "sim_start":
            if not _tone(600, 60):
                _bell(1)
        elif event == "tool":
            _tone(520, 45)
        elif event == "notify":
            if not _tone(659, 80):
                _bell(1)
        else:
            _bell(1)
    except Exception:
        pass


def play(event="notify"):
    """Plays an audio cue on a short-lived daemon thread."""
    if not is_sound_enabled(event):
        return
    if _HAS_WINSOUND:
        threading.Thread(target=_play_blocking, args=(event,),
                         daemon=True).start()
    else:
        _play_blocking(event)


def preview_sound(event="wake_kitty"):
    """Preview a sound event regardless of toggle (for Settings UI)."""
    if _HAS_WINSOUND:
        threading.Thread(target=_play_blocking, args=(event,),
                         daemon=True).start()
    else:
        _play_blocking(event)


# Back-compat explicit-async alias (same behavior as play() now).
play_async = play
