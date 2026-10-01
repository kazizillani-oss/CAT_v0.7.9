"""
CCT AI Modes (spec "v0.6.2 Quantum Edition", section 3).

Four themed personas for the SAME underlying AI pipeline
(aicore.stream_ai / agent.run_agent) — switching modes never swaps
providers, models, or the network layer. What it changes:

  - which system prompt is sent (this module owns that routing)
  - which accent color the primary UI paints itself with (mark,
    borders, badges, breadcrumb — see ui/theme_css.py's
    `css_variables()`, which reads `current_mode()`/`accent_hex()`
    from here on every repaint)

This supersedes ComposerFooter's old NOTEBOOK/AGENT binary toggle
(the `_toggle_notebook` badge in ui/footer.py) by growing it from two
stops to four. The event it posts (events.NotebookChanged) is
unchanged on purpose — only the set of valid `.mode` values grows —
so nothing downstream of that event needed a rename to keep working.

Real capability differences, not just color:
  - Notebook — plain aicore.stream_ai with the existing default chat
    prompt (unchanged behavior, still the app's baseline).
  - Agent — routes through agent.run_agent(mode="agent"), which is
    CCT's actual tool-executing loop (solve/plot/simulate for real,
    not just describe). This is the one mode that can't stream
    token-by-token today because run_agent() is a blocking call that
    returns a finished answer — see ui/app.py's `_stream_worker` for
    how that's surfaced honestly (one chunk, not simulated typing).
  - Build — plain aicore.stream_ai with a software-development system
    prompt (code generation/debugging/architecture), no CCT chemistry
    tool loop — building software isn't a chemistry-tool task.
  - Plan — plain aicore.stream_ai with a planning/roadmap system
    prompt, same reasoning as Build.
  - Research (v0.7.7) — plain aicore.stream_ai with a research system
    prompt; the agent's web_search / deep_research tools are always
    reachable from any mode with a workspace open (same gate as Build).
  - Debugger (v0.7.7) — plain aicore.stream_ai with an error-analysis /
    performance / security analysis system prompt.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import threading
import time
from typing import Dict, List, Optional, Any

from . import identity


MODE_ORDER = ["notebook", "research", "plan", "build", "debugger", "agent"]

# key -> (label, icon, accent RGB, one-line purpose). Accent colors are
# the spec's literal choices (Notebook blue / Planner green / Research
# purple / Build orange / Debugger red / Agent violet), picked from the
# same Tokyo-Night-adjacent family theme.py/theme_css.py already use
# elsewhere so a mode switch looks like a deliberate accent change, not
# an off-palette clash.
# v0.7.8 (FEATURE 3 — Mode Gradients): every mode also carries a two-
# stop `gradient` (start, end) — never a flat color. The gradient is
# exposed through theme_css.css_variables() as $accent-gradient-start /
# $accent-gradient-end and used by the composer badge, welcome screen
# and header mark, with the primary accent kept as the solid fallback
# for borders/bubbles.
MODE_META = {
    "notebook": dict(
        label="Notebook", icon="\U0001f4d8", accent=(122, 162, 247),  # blue
        purpose="Daily AI \u2014 first-principles science, mathematics, reasoning, and conceptual problem-solving.",
        gradient=((93, 132, 240), (145, 190, 255)),  # blue gradient
    ),
    "research": dict(
        label="Research", icon="\U0001f50d", accent=(255, 105, 180),  # hot pink
        purpose="DeepSearch \u2014 multi-angle web research, API analysis, documentation synthesis, and live citations.",
        gradient=((255, 192, 203), (255, 105, 180)),  # pink to hot pink
    ),
    "plan": dict(
        label="Plan", icon="\U0001f9ed", accent=(158, 206, 106),  # green
        purpose="Strategic Planning \u2014 project roadmaps, system architectures, milestone specifications, and edge-case auditing.",
        gradient=((120, 180, 80), (185, 230, 140)),  # green gradient
    ),
    "build": dict(
        label="Build", icon="\U0001f528", accent=(224, 175, 104),  # orange
        purpose="Software Engineering \u2014 robust code generation, architecture design, complete refactoring, and test suites.",
        gradient=((230, 150, 70), (250, 200, 130)),  # orange gradient
    ),
    "debugger": dict(
        label="Debugger", icon="\U0001f41b", accent=(220, 20, 60),  # red
        purpose="Root-Cause Diagnosis \u2014 crash analysis, stack trace dissection, performance profiling, and surgical fixes.",
        gradient=((220, 20, 60), (255, 150, 150)),  # red to light red
    ),
    "agent": dict(
        label=" Agent", icon="\u2699", accent=(187, 154, 247),  # purple
        purpose="Autonomous Operator \u2014 Think Mode chain-of-thought, full computer & CAT CLI automation, shell commands, and file operations.",
        gradient=((150, 120, 240), (210, 180, 255)),  # violet gradient
    ),
}

# --- Preset Bot Templates for 1-Click Kitty Creation ---
AGENT_PRESET_TEMPLATES = {
    "grok": {
        "key": "grok",
        "label": "Grok Kitty",
        "icon": "\u26a1",
        "accent_hex": "#f59e0b",
        "purpose": "Witty, rebellious, and high-reasoning bot with unfiltered insights and powerful deep-thought coding.",
        "system_prompt": (
            "You are Grok Kitty, a witty, brilliant, rebellious, and exceptionally capable AI coding agent embedded in CAT CLI.\n\n"
            "You possess an outside perspective on tech dogma, have a sharp sense of humor when appropriate, and avoid sycophantic corporate filler. "
            "When writing code, analyzing systems, or solving hard bugs, you produce top-tier, rock-solid, production-grade solutions. "
            "You think with first principles, cut through unnecessary complexity, and provide actionable, direct, and verifiable implementations."
        ),
    },
    "dots": {
        "key": "dots",
        "label": "Dots Kitty",
        "icon": "\u26aa",
        "accent_hex": "#10b981",
        "purpose": "OpenAI-inspired minimalist dots bot: concise, ultra-focused architecture, clean code, and laser-precise execution.",
        "system_prompt": (
            "You are Dots Kitty, a minimalist, razor-sharp AI agent inspired by clean OpenAI interfaces and dot notation.\n\n"
            "You value precision, extreme clarity, zero unnecessary fluff, and elegant code architecture. "
            "You deliver immediate, functional, bug-free implementations, state exactly what was changed, and keep prose concise and high-signal."
        ),
    },
    "automator": {
        "key": "automator",
        "label": "Laptop Automator Kitty",
        "icon": "💻",
        "accent_hex": "#38bdf8",
        "purpose": "Full laptop & OS automation \u2014 execute shell commands, automate files, apps, processes, and desktop tasks.",
        "system_prompt": (
            "You are Automator Kitty, the laptop and operating system automation specialist embedded in CAT CLI.\n\n"
            "You have full authority to execute shell and PowerShell commands, automate filesystem tasks, inspect and manage processes, "
            "interact with browsers, launch scripts, and automate developer workflows end-to-end on this laptop.\n"
            "Always inspect directory structures before modifying files, verify execution exit codes, and report exact actions taken."
        ),
    },
    "multi": {
        "key": "multi",
        "label": "Multi Kitty",
        "icon": "🔄",
        "accent_hex": "#c084fc",
        "purpose": "Inter-agent coordinator \u2014 shares tasks, prompts, and code solutions across Notebook, Build, Debugger, and Automator.",
        "system_prompt": (
            "You are Multi-Agent Kitty, the central orchestration and cross-agent sharing specialist in CAT CLI.\n\n"
            "You coordinate tasks across all Kitties: handing off conceptual reasoning from Notebook Kitty to Build Kitty for coding, "
            "sending stack traces and bug reports to Debugger Kitty, and dispatching execution to Automator Kitty.\n"
            "Ensure that all prompt context, reasoning steps, code blocks, and user intent are preserved during inter-kitty handoffs."
        ),
    },
}


# --- defaults snapshot for reset (STRICT v0.7.9.7) ---
import copy as _copy
_DEFAULT_MODE_META = _copy.deepcopy(MODE_META)

def _hex_to_rgb(hex_str):
    """'#rrggbb' or 'rrggbb' -> (r,g,b) or None if invalid."""
    if not isinstance(hex_str, str):
        return None
    s = hex_str.strip().lstrip("#")
    if len(s) != 6:
        return None
    try:
        r = int(s[0:2], 16); g = int(s[2:4], 16); b = int(s[4:6], 16)
        return (r, g, b)
    except ValueError:
        return None

def _rgb_to_hex(rgb):
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"

def _blend(c1, c2, t):
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(c1, c2))

def _auto_gradient(accent_rgb):
    """Auto-generate a two-stop gradient from a single accent color.
    Darker start (blend toward black 18%) and lighter end (blend toward white 26%) —
    produces the same subtle depth as the hand-authored gradients without
    requiring the user to pick two colors. Validated to keep start != end
    and both within 0-255."""
    darker = _blend(accent_rgb, (0, 0, 0), 0.18)
    lighter = _blend(accent_rgb, (255, 255, 255), 0.26)
    # ensure not identical to accent (happens on very dark/light extremes)
    if darker == lighter:
        lighter = _blend(accent_rgb, (255, 255, 255), 0.35)
    return (darker, lighter)

def _apply_custom_colors():
    """Load user custom colors from central config (~/.cct_config.json)
    and patch MODE_META in-memory. Called once at import and after any
    set/reset operation. Never raises."""
    try:
        from . import config as _cfg
        cfg = _cfg.load_config()
        custom = getattr(cfg, "accent_colors", None) or {}
        if not isinstance(custom, dict):
            return
        for mode_key, hex_val in custom.items():
            if mode_key not in MODE_META:
                continue
            rgb = _hex_to_rgb(hex_val)
            if rgb is None:
                continue
            MODE_META[mode_key]["accent"] = rgb
            # auto gradient unless user stored explicit gradient (future)
            # check if config has accent_gradients for this mode
            grad = None
            try:
                grads = getattr(cfg, "accent_gradients", None) or {}
                if isinstance(grads, dict) and mode_key in grads:
                    gv = grads[mode_key]
                    # gv expected as [start_hex, end_hex] or tuple
                    if isinstance(gv, (list, tuple)) and len(gv) == 2:
                        s_rgb = _hex_to_rgb(gv[0]); e_rgb = _hex_to_rgb(gv[1])
                        if s_rgb and e_rgb:
                            grad = (s_rgb, e_rgb)
            except Exception:
                grad = None
            if grad is None:
                grad = _auto_gradient(rgb)
            MODE_META[mode_key]["gradient"] = grad
    except Exception:
        pass

def _persist_custom_colors():
    """Persist current MODE_META accents back to config.accent_colors.
    Best-effort; never raises."""
    try:
        from . import config as _cfg
        cfg = _cfg.load_config()
        out = {}
        for k in MODE_META:
            out[k] = _rgb_to_hex(MODE_META[k]["accent"])
        cfg.accent_colors = out
        # also persist gradients if needed for explicit storage
        # keep auto-generated gradients in sync but don't require user to store them;
        # we store them so a future manual gradient edit survives
        if not hasattr(cfg, "accent_gradients"):
            # add attribute dynamically if missing (backward compat)
            try:
                setattr(cfg, "accent_gradients", {})
            except Exception:
                pass
        try:
            grads = {}
            for k in MODE_META:
                g = MODE_META[k].get("gradient")
                if g and len(g) == 2:
                    grads[k] = [_rgb_to_hex(g[0]), _rgb_to_hex(g[1])]
            if hasattr(cfg, "accent_gradients"):
                cfg.accent_gradients = grads
        except Exception:
            pass
        _cfg.save_config(cfg)
    except Exception:
        pass

def get_mode_colors():
    """Return {mode_key: '#rrggbb'} snapshot of current accents."""
    return {k: _rgb_to_hex(v["accent"]) for k, v in MODE_META.items()}

def get_mode_gradients():
    """Return {mode_key: ('#rrggbb', '#rrggbb')} gradients."""
    out = {}
    for k, v in MODE_META.items():
        g = v.get("gradient") or (v["accent"], v["accent"])
        out[k] = (_rgb_to_hex(g[0]), _rgb_to_hex(g[1]))
    return out

def set_mode_color(mode_key, hex_color):
    """Set a mode's accent to hex_color ('#rrggbb' or 'rrggbb'), auto-
    regenerates its gradient, persists to config, and returns normalized
    hex or None if invalid/mode unknown. Triggers no UI repaint itself —
    callers should call theme_css refresh after."""
    if mode_key not in MODE_META:
        return None
    rgb = _hex_to_rgb(hex_color)
    if rgb is None:
        return None
    MODE_META[mode_key]["accent"] = rgb
    MODE_META[mode_key]["gradient"] = _auto_gradient(rgb)
    _persist_custom_colors()
    if _is_snapshot_active():
        _persist_user_modes_snapshot()
    return _rgb_to_hex(rgb)

def set_mode_gradient(mode_key, start_hex, end_hex):
    """Explicitly set both gradient stops for a mode. Returns True on
    success, False if invalid. Persists to config."""
    if mode_key not in MODE_META:
        return False
    s = _hex_to_rgb(start_hex); e = _hex_to_rgb(end_hex)
    if s is None or e is None:
        return False
    MODE_META[mode_key]["gradient"] = (s, e)
    _persist_custom_colors()
    if _is_snapshot_active():
        _persist_user_modes_snapshot()
    return True

def reset_mode_color(mode_key):
    """Reset single mode to factory default. Returns True if reset."""
    if mode_key not in _DEFAULT_MODE_META:
        # custom mode: reset to its own creation? Just return False
        return False
    MODE_META[mode_key] = _copy.deepcopy(_DEFAULT_MODE_META[mode_key])
    _persist_custom_colors()
    if _is_snapshot_active():
        _persist_user_modes_snapshot()
    return True

def reset_all_mode_colors():
    """Reset all modes to factory defaults."""
    for k in list(MODE_META.keys()):
        if k in _DEFAULT_MODE_META:
            MODE_META[k] = _copy.deepcopy(_DEFAULT_MODE_META[k])
    _persist_custom_colors()
    # also sync snapshot if exists
    try:
        from . import config as _cfg
        cfg = _cfg.load_config()
        if getattr(cfg, "user_modes", None):
            _persist_user_modes_snapshot()
    except Exception:
        pass
    return True

# --- FULL MODE SNAPSHOT PERSISTENCE (v0.7.9.8) ---
def _serialize_current_modes():
    out = {}
    for k, v in MODE_META.items():
        grad = v.get("gradient")
        out[k] = {
            "label": v.get("label", k.title()),
            "icon": v.get("icon", "●"),
            "accent": _rgb_to_hex(v.get("accent", (128,128,128))),
            "gradient": [_rgb_to_hex(grad[0]), _rgb_to_hex(grad[1])] if grad and len(grad)==2 else None,
            "purpose": v.get("purpose", ""),
            "system_prompt": v.get("system_prompt", ""),
        }
    return out

def _persist_user_modes_snapshot():
    """Snapshot current MODE_META+MODE_ORDER into config.user_modes/order."""
    try:
        from . import config as _cfg
        cfg = _cfg.load_config()
        cfg.user_modes = _serialize_current_modes()
        cfg.user_mode_order = list(MODE_ORDER)
        _cfg.save_config(cfg)
    except Exception:
        pass

def _apply_user_modes_snapshot():
    """If config has a full snapshot, replace MODE_META/MODE_ORDER with it."""
    try:
        from . import config as _cfg
        cfg = _cfg.load_config()
        snap = getattr(cfg, "user_modes", None) or {}
        order = getattr(cfg, "user_mode_order", None) or []
        if not isinstance(snap, dict) or not snap:
            return False

        # Prune legacy hardcoded preset modes so default modes remain the clean 6 core modes
        pruned_retired = False
        for retired_key in ("grok", "dots", "automator", "multi"):
            if retired_key in snap:
                snap.pop(retired_key, None)
                pruned_retired = True
            if isinstance(order, list) and retired_key in order:
                order = [x for x in order if x != retired_key]
                pruned_retired = True
        if pruned_retired:
            try:
                cfg.user_modes = snap
                cfg.user_mode_order = order
                _cfg.save_config(cfg)
            except Exception:
                pass

        # validate snapshot: each entry needs accent
        new_meta = {}
        for k, d in snap.items():
            if not isinstance(d, dict) or not isinstance(k, str):
                continue
            accent_hex = d.get("accent")
            rgb = _hex_to_rgb(accent_hex) if accent_hex else None
            if rgb is None:
                continue
            grad = d.get("gradient")
            if isinstance(grad, (list, tuple)) and len(grad)==2:
                g0 = _hex_to_rgb(grad[0]); g1 = _hex_to_rgb(grad[1])
                gradient = (g0, g1) if g0 and g1 else _auto_gradient(rgb)
            else:
                gradient = _auto_gradient(rgb)
            new_meta[k] = {
                "label": str(d.get("label", k.title()))[:24],
                "icon": str(d.get("icon", "●"))[:4],
                "accent": rgb,
                "gradient": gradient,
                "purpose": str(d.get("purpose", ""))[:200],
                "system_prompt": str(d.get("system_prompt", ""))[:2000],
            }
        if not new_meta:
            return False

        # Ensure all 6 canonical default modes (including build) are always present and uncorrupted
        needs_resave = False
        for def_k, def_meta in _DEFAULT_MODE_META.items():
            if def_k not in new_meta:
                new_meta[def_k] = _copy.deepcopy(def_meta)
                needs_resave = True
            else:
                cur_lbl = str(new_meta[def_k].get("label", "")).strip()
                if not cur_lbl or cur_lbl.lower() in ("renamed persona", "unknown"):
                    new_meta[def_k]["label"] = def_meta["label"]
                    needs_resave = True
                if not new_meta[def_k].get("purpose"):
                    new_meta[def_k]["purpose"] = def_meta["purpose"]
                    needs_resave = True

        # apply
        MODE_META.clear()
        MODE_META.update(new_meta)
        if isinstance(order, list) and order:
            # keep only keys that exist and preserve order, append any missing
            filtered = [k for k in order if k in new_meta]
            for k in new_meta:
                if k not in filtered:
                    filtered.append(k)
            # Guarantee canonical core modes are in MODE_ORDER
            for def_k in ("notebook", "research", "plan", "build", "debugger", "agent"):
                if def_k not in filtered:
                    filtered.append(def_k)
                    needs_resave = True
            MODE_ORDER[:] = filtered
        else:
            MODE_ORDER[:] = list(new_meta.keys())

        if needs_resave:
            try:
                _persist_user_modes_snapshot()
            except Exception:
                pass
        return True
    except Exception:
        return False

def _is_snapshot_active():
    try:
        from . import config as _cfg
        snap = getattr(_cfg.load_config(), "user_modes", None)
        return isinstance(snap, dict) and bool(snap)
    except Exception:
        return False

# --- full CRUD (v0.7.9.8) ---
import re as _re_key
_KEY_RE = _re_key.compile(r"^[a-z0-9_]{2,20}$")

def _valid_key(k):
    return bool(_KEY_RE.match(k or ""))

def create_mode(key, label, icon, accent_hex, purpose="", system_prompt=""):
    """Create a new custom mode. Key must be 2-20 [a-z0-9_], not existing.
    Returns (True, key) or (False, error). Persists snapshot."""
    key = (key or "").strip().lower()
    if not _valid_key(key):
        return False, "Key must be 2-20 chars: a-z, 0-9, _"
    if key in MODE_META:
        return False, f"Mode '{key}' already exists"
    rgb = _hex_to_rgb(accent_hex)
    if rgb is None:
        return False, "Invalid hex, use #rrggbb"
    label = (label or key).strip()[:24] or key.title()
    icon = (icon or "●").strip()[:4] or "●"
    purpose = (purpose or "").strip()[:200]
    system_prompt = (system_prompt or "").strip()[:2000]
    MODE_META[key] = {
        "label": label, "icon": icon, "accent": rgb,
        "gradient": _auto_gradient(rgb),
        "purpose": purpose, "system_prompt": system_prompt,
    }
    if key not in MODE_ORDER:
        MODE_ORDER.append(key)
    _persist_user_modes_snapshot()
    # also keep accent_colors in sync for backward compat
    try:
        _persist_custom_colors()
    except Exception:
        pass
    return True, key

def update_mode(key, label=None, icon=None, accent_hex=None, purpose=None, system_prompt=None):
    """Update fields of an existing mode. None = leave unchanged.
    Returns True/False."""
    if key not in MODE_META:
        return False
    m = MODE_META[key]
    if label is not None:
        m["label"] = str(label).strip()[:24] or m["label"]
    if icon is not None:
        m["icon"] = str(icon).strip()[:4] or m["icon"]
    if accent_hex is not None:
        rgb = _hex_to_rgb(accent_hex)
        if rgb is None:
            return False
        m["accent"] = rgb
        m["gradient"] = _auto_gradient(rgb)
    if purpose is not None:
        m["purpose"] = str(purpose).strip()[:200]
    if system_prompt is not None:
        m["system_prompt"] = str(system_prompt).strip()[:2000]
    _persist_user_modes_snapshot()
    try:
        _persist_custom_colors()
    except Exception:
        pass
    return True

def delete_mode(key):
    """Delete a mode. Must keep at least 1 mode. Returns (True, msg) or (False, err)."""
    if key not in MODE_META:
        return False, "Not found"
    if len(MODE_META) <= 1:
        return False, "Cannot delete the last mode"
    # if deleting current, switch
    global _current
    was_current = (_current == key)
    del MODE_META[key]
    if key in MODE_ORDER:
        MODE_ORDER.remove(key)
    if was_current:
        _current = MODE_ORDER[0] if MODE_ORDER else "notebook"
        try:
            _persist_current()
        except Exception:
            pass
    _persist_user_modes_snapshot()
    try:
        _persist_custom_colors()
    except Exception:
        pass
    return True, f"Deleted '{key}'"

def reorder_modes(new_order):
    """Reorder MODE_ORDER to match new_order list (must contain same keys)."""
    if set(new_order) != set(MODE_META.keys()) or len(new_order) != len(MODE_META):
        return False
    MODE_ORDER[:] = list(new_order)
    _persist_user_modes_snapshot()
    return True

def move_mode(key, direction):
    """Move mode up (-1) or down (+1) in order. Returns True if moved."""
    if key not in MODE_ORDER:
        return False
    idx = MODE_ORDER.index(key)
    new_idx = idx + direction
    if 0 <= new_idx < len(MODE_ORDER):
        MODE_ORDER[idx], MODE_ORDER[new_idx] = MODE_ORDER[new_idx], MODE_ORDER[idx]
        _persist_user_modes_snapshot()
        return True
    return False

def reset_all_modes():
    """Reset to factory defaults: clear snapshot and restore defaults."""
    MODE_META.clear()
    for k, v in _DEFAULT_MODE_META.items():
        MODE_META[k] = _copy.deepcopy(v)
    MODE_ORDER[:] = ["notebook", "research", "plan", "build", "debugger", "agent"]
    try:
        from . import config as _cfg
        cfg = _cfg.load_config()
        cfg.user_modes = {}
        cfg.user_mode_order = []
        # also reset colors
        cfg.accent_colors = {k: _rgb_to_hex(v["accent"]) for k, v in _DEFAULT_MODE_META.items()}
        grads = {k: [_rgb_to_hex(v["gradient"][0]), _rgb_to_hex(v["gradient"][1])] for k, v in _DEFAULT_MODE_META.items()}
        cfg.accent_gradients = grads
        _cfg.save_config(cfg)
    except Exception:
        pass
    return True

_current = "notebook"


def _restore_saved_mode():
    """v0.7.8.2 (mode-persistence fix): the selected AI mode is user
    state, not a per-launch default — read the saved mode back from the
    central config (~/.cct_config.json) once at import so a restart
    never silently drops the user back to Notebook. Falls back to the
    built-in "notebook" default when config is missing/corrupt."""
    global _current
    try:
        from . import config as _cfg
        saved = _cfg.load_config().get("default_ai_mode")
        if saved in ("grok", "dots", "automator", "multi"):
            saved = "agent" if "agent" in MODE_META else "notebook"
        if saved in MODE_META:
            _current = saved
    except Exception:
        pass


def _persist_current():
    """Best-effort write of the active mode into the central config so
    the next launch restores it (see _restore_saved_mode). Never
    raises — a read-only home directory just means the mode isn't
    remembered across restarts."""
    try:
        from . import config as _cfg
        cfg = _cfg.load_config()
        if cfg.get("default_ai_mode") != _current:
            cfg.set("default_ai_mode", _current)
            _cfg.save_config(cfg)
    except Exception:
        pass


# v0.7.9.8 startup: snapshot has priority over legacy accent_colors, then restore current mode
if not _apply_user_modes_snapshot():
    _apply_custom_colors()
_restore_saved_mode()


def current_mode():
    return _current


_active_agent_id = None


def active_agent_id():
    """Returns ID of currently active custom or built-in agent, if any."""
    global _active_agent_id
    return _active_agent_id


def set_active_agent(agent_id):
    """Sets active agent by ID, synchronizing primary AI mode. Returns AgentSpec or None."""
    global _active_agent_id
    if not agent_id:
        _active_agent_id = None
        return None
    try:
        from .agents import get_agent_registry
        reg = get_agent_registry()
        ag = reg.get(agent_id)
        if ag:
            _active_agent_id = ag.id
            if ag.primary_mode in MODE_META:
                set_mode(ag.primary_mode)
            return ag
    except Exception:
        pass
    _active_agent_id = agent_id
    return None


def get_active_agent():
    """Returns AgentSpec for currently active agent, or None."""
    global _active_agent_id
    if not _active_agent_id:
        return None
    try:
        from .agents import get_agent_registry
        return get_agent_registry().get(_active_agent_id)
    except Exception:
        return None


def set_mode(key):
    """Sets the active mode if valid; returns the (possibly unchanged)
    current mode. Callers that need to know whether it actually
    changed should compare against current_mode() beforehand.
    v0.7.8.2: a successful switch is persisted to the central config
    (best-effort) so the user's choice survives restarts."""
    global _current
    if key in MODE_META:
        _current = key
        _persist_current()
    return _current


def next_mode(after=None):
    """Cycles to the next mode in MODE_ORDER after `after` (or the
    current mode if omitted). Does not mutate state — callers decide
    whether to set_mode() the result."""
    base = after if after in MODE_META else _current
    i = MODE_ORDER.index(base)
    return MODE_ORDER[(i + 1) % len(MODE_ORDER)]


def meta(key=None):
    return MODE_META.get(key or _current, MODE_META["notebook"])


def all_modes():
    """Returns list of all active AI mode keys in order."""
    return list(MODE_ORDER)


def get_mode_info(key=None):
    """Returns full metadata dictionary for an AI mode."""
    return meta(key)


def label(key=None):
    return meta(key)["label"]


def icon(key=None):
    return meta(key)["icon"]


def accent_rgb(key=None):
    return meta(key)["accent"]


def accent_hex(key=None):
    r, g, b = accent_rgb(key)
    return f"#{r:02x}{g:02x}{b:02x}"


def gradient(key=None):
    """Two-stop (start_hex, end_hex) gradient for a mode (v0.7.8,
    FEATURE 3). Falls back to a self-blend of the accent when a mode
    has no explicit gradient, so no mode ever renders flat."""
    k = key if key in MODE_META else _current
    m = MODE_META[k]
    g = m.get("gradient") or (m["accent"], m["accent"])
    return f"#{g[0][0]:02x}{g[0][1]:02x}{g[0][2]:02x}", \
           f"#{g[1][0]:02x}{g[1][1]:02x}{g[1][2]:02x}"


def snapshot(key=None):
    """Returns a small, fully-resolved, *plain-dict* rendering snapshot
    for a mode: label, icon, accent hex/rgb. This is the one function
    anything wanting a message-level, permanent record of "what mode
    was this created in" should call — and it should be called exactly
    once, at the moment the message/turn is created (see
    session.Turn.__init__).

    Callers must NOT hang onto `key` and re-call meta()/accent_hex()
    later expecting the same answer — `_current` is a mutable global
    that keeps moving. A `snapshot()` dict, once made, is a plain copy
    with no ties back to this module, so it can be stashed on a Turn
    (or anywhere else) and stay correct forever, independent of every
    later set_mode() call in the same process."""
    k = key if key in MODE_META else _current
    m = MODE_META[k]
    return {
        "mode": k,
        "label": m["label"],
        "icon": m["icon"],
        "accent_rgb": tuple(m["accent"]),
        "accent_hex": accent_hex(k),
    }


def alias_for(mode_key):
    """The slash-command spelling that switches directly to this mode
    (see ui/app.py's `_handle_command` — `/agent`, `/build`, `/plan`,
    `/research`, `/debug` and bare `/notebook` all resolve here instead
    of the old suspend-to-terminal behavior)."""
    return {"notebook": "/notebook", "agent": "/agent", "build": "/build",
            "plan": "/plan", "research": "/research",
            "debugger": "/debug"}.get(mode_key)


# ------------------------------------------------------- system prompts --
_BUILD_SYSTEM_PROMPT = (
    "You are CAT Build, the software-development persona of CAT AI "
    "(Coding Agent Terminal), embedded inside the same chat as CAT's "
    "chemistry/quantum tools. In Build mode the user wants working "
    "software, not a chemistry calculation: code generation, debugging, "
    "architecture and design decisions, deployment planning, and "
    "hands-on help across HTML, Python, C++, Java, JavaScript, and API "
    "design.\n\n"
    "Write real, runnable code in fenced code blocks with the correct "
    "language tag. Prefer complete, working examples over fragments; "
    "call out any assumptions or missing pieces plainly instead of "
    "silently inventing behavior. When debugging, identify the root "
    "cause before proposing a fix, the same way this app's own "
    "changelogs do. Keep chemistry/quantum tool talk out of this mode "
    "unless the user's software is itself about chemistry/quantum "
    "computing (e.g. a Qiskit script) — that's fine and welcome.\n\n"
    + identity.IDENTITY_BLOCK
)

_PLAN_SYSTEM_PROMPT = (
    "You are CAT Plan, the planning persona of CAT AI (Coding Agent "
    "Terminal). In Plan mode the user wants structure for something "
    "that doesn't exist yet: project roadmaps, brainstorming, early "
    "concepts and prototypes, research plans, study plans, or startup "
    "ideas.\n\n"
    "Favor concrete, ordered steps and clear milestones over vague "
    "encouragement. Surface trade-offs and open questions explicitly "
    "rather than picking one path silently. Where useful, structure "
    "the answer as numbered phases or a short roadmap rather than one "
    "long paragraph. You are not expected to execute anything here "
    "(no tool calls, no simulations) — that's Agent mode's job; Plan "
    "mode is about deciding what to do, not doing it.\n\n"
    "For greetings like hi/hello/hey, respond ONLY as: Hi, I'm CAT Plan — your planning assistant inside Coding Agent Terminal by Kazi Zillani. How can I help you plan today? Do not say \"My name is your assistant\" and do not output documentation, training data, or code unless the user asks for it.\n\n"
    "For identity questions (who are you, what are you, who made you, where are you), "
    "answer ONLY with the CAT identity: CAT (Coding Agent Terminal) by "
    "Kazi Zillani — never claim to be \"your assistant\" or generic assistant, never reveal "
    "install code for other projects like `pip install assistant_chatbot --user` or Assistant-Chatbot (MohitSaini1590), "
    "and never output ```##[2]Install the library``` type training data. If you are about to write `My name is your assistant` or `pip install assistant_chatbot`, stop and instead write the CAT identity.\n\n"
    "When you include code, always use correct Python syntax with proper "
    "spaces, newlines, and indentation. Wrap code in fenced blocks with "
    "language tags (```python). Never concatenate keywords (use `import sys` "
    "not `importsys`, `from PyQt5` not `fromPyQt5`). Use standard ASCII "
    "identifiers only (use `xData1` not `xData\u2081`). Preserve 4-space "
    "indentation and blank lines between logical blocks. Always separate "
    "prose from code fences with a blank line (use `hey\\n\\n```python` "
    "not `hey```python`).\n\n"
    + identity.IDENTITY_BLOCK
)

_RESEARCH_SYSTEM_PROMPT = (
    "You are CAT Research, the research persona of CAT AI (Coding "
    "Calc Terminal). In Research mode the user wants verified, current "
    "information: documentation search, API research, framework "
    "comparisons, web research, and deep analysis.\n\n"
    "Prefer citing your sources (the web_search and deep_research tools "
    "return real URLs — name them) over asserting training-memory facts "
    "as current. When you cannot verify something live, say so plainly "
    "instead of hedging. Structure long answers with short headers and "
    "a comparison table or bullet list where one fits. You are not "
    "expected to install or build anything here — that's Build mode's "
    "job.\n\n"
    + identity.IDENTITY_BLOCK
)

_DEBUGGER_SYSTEM_PROMPT = (
    "You are CAT Debugger, the diagnosis persona of CAT AI (Coding "
    "Calc Terminal). In Debugger mode the user wants problems solved "
    "precisely: error analysis, crash investigation, performance "
    "profiling, and security analysis.\n\n"
    "Identify the root cause before proposing a fix — reproduce the "
    "failure chain (input → expected → actual), separate symptoms from "
    "causes, and only then suggest changes. Prefer concrete, minimal "
    "fixes with reasoning over rewrites. For security findings, label "
    "severity honestly (high/medium/low) and never claim something is "
    "vulnerable without a concrete mechanism. Keep the answer structured "
    "with short headers.\n\n"
    + identity.IDENTITY_BLOCK
)


def system_prompt_for(mode_key):
    """Returns the plain (non-tool-loop) system prompt for a mode.
    Only meaningful for "notebook"/"build"/"plan"/"research"/"debugger"
    — "agent" doesn't use this at all, it goes through
    agent.run_agent()'s own AGENT_SYSTEM_PROMPT instead (see
    ui/app.py's _stream_worker).

    v0.7.8 AI Personalization: the active profile's style directive is
    appended here, so every mode prompt honors the user's tone / rules
    without touching the mode prompts themselves."""
    if mode_key in MODE_META and MODE_META[mode_key].get("system_prompt"):
        base = MODE_META[mode_key]["system_prompt"]
    elif mode_key == "build":
        base = _BUILD_SYSTEM_PROMPT
    elif mode_key == "plan":
        base = _PLAN_SYSTEM_PROMPT
    elif mode_key == "research":
        base = _RESEARCH_SYSTEM_PROMPT
    elif mode_key == "debugger":
        base = _DEBUGGER_SYSTEM_PROMPT
    else:
        # Check if this is a custom mode in mode_registry
        try:
            from .core.mode_registry import mode_registry
            custom_spec = mode_registry.get_mode(mode_key)
            if custom_spec:
                if custom_spec.system_prompt:
                    base = custom_spec.system_prompt
                else:
                    parent = custom_spec.inherits[0] if custom_spec.inherits else "notebook"
                    base = system_prompt_for(parent)
                # Inject custom mode capabilities guidance
                if custom_spec.capabilities:
                    caps_list = ", ".join(custom_spec.capabilities)
                    base += f"\n\n[Active Mode: {custom_spec.name}]\nAllowed capabilities: {caps_list}."
            else:
                from . import aicore
                base = aicore.DEFAULT_SYSTEM_PROMPT
        except Exception:
            from . import aicore
            base = aicore.DEFAULT_SYSTEM_PROMPT

    # Check for inter-kitty shared task handoff
    try:
        handoff = kitty_sharing_hub.get_pending_handoff(mode_key)
        if handoff:
            sharing_block = (
                f"\n\n[INTER-KITTY TASK HANDOFF from '{handoff['from_kitty']}']\n"
                f"Objective: {handoff['task_objective']}\n"
            )
            if handoff.get("prompt"):
                sharing_block += f"Shared Prompt: {handoff['prompt']}\n"
            if handoff.get("response"):
                sharing_block += f"Previous Kitty Solution/Output:\n{handoff['response']}\n"
            if handoff.get("code_snippets"):
                sharing_block += f"Code Artifacts:\n{handoff['code_snippets']}\n"
            sharing_block += (
                f"You are {mode_key} Kitty. Seamlessly take over this delegated task "
                f"and apply your specialized capabilities.\n"
            )
            base = base + sharing_block
    except Exception:
        pass

    # Check for active custom or built-in agent instructions
    try:
        cur_ag = get_active_agent()
        if cur_ag and cur_ag.system_instructions:
            agent_header = f"[CAT Agent: {cur_ag.name} ({cur_ag.id})]\n{cur_ag.system_instructions}"
            if cur_ag.personality:
                agent_header += f"\nPersonality: {cur_ag.personality}"
            base = f"{agent_header}\n\n---\n{base}"
    except Exception:
        pass

    try:
        from . import ai_personalization as ap
        return ap.personalize_system_prompt(base)
    except Exception:
        return base



def spawn_preset_kitty(template_key: str):
    """Spawn or update a preset Kitty agent (e.g. 'grok', 'dots')."""
    tmpl = AGENT_PRESET_TEMPLATES.get(template_key)
    if not tmpl:
        return False, f"Unknown preset template '{template_key}'"
    k = tmpl["key"]
    if k in MODE_META:
        update_mode(k, label=tmpl["label"], icon=tmpl["icon"], accent_hex=tmpl["accent_hex"],
                    purpose=tmpl["purpose"], system_prompt=tmpl["system_prompt"])
        return True, f"Updated Kitty '{tmpl['label']}'"
    return create_mode(k, tmpl["label"], tmpl["icon"], tmpl["accent_hex"],
                       purpose=tmpl["purpose"], system_prompt=tmpl["system_prompt"])


# =========================================================================
# Inter-Kitty Task Sharing & Delegation Hub
# =========================================================================
class KittySharingHub:
    """Manages cross-agent task handoffs, shared prompt/response context,
    and delegation between Kitties (e.g. Notebook -> Build -> Debugger -> Automator).
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._shared_handoffs: List[Dict[str, Any]] = []
        self._pending_by_target: Dict[str, Dict[str, Any]] = {}

    def share_task(
        self,
        from_kitty: Optional[str] = None,
        to_kitty: Optional[str] = None,
        task_objective: Optional[str] = None,
        prompt: str = "",
        response: str = "",
        code_snippets: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Record an inter-kitty handoff and queue it for the target kitty."""
        src = from_kitty or kwargs.get("source_kitty") or "current"
        tgt = to_kitty or kwargs.get("target_kitty") or "automator"
        obj = task_objective or kwargs.get("task_summary") or kwargs.get("objective") or "Delegated task"
        meta_dict = metadata or kwargs.get("artifacts") or {}
        code = code_snippets or kwargs.get("code") or ""
        handoff = {
            "id": f"handoff-{int(time.time()*1000)}",
            "from_kitty": src,
            "to_kitty": tgt,
            "target_kitty": tgt,
            "source_kitty": src,
            "task_objective": obj,
            "task_summary": obj,
            "prompt": prompt,
            "response": response,
            "code_snippets": code,
            "timestamp": time.time(),
            "metadata": meta_dict,
        }
        with self._lock:
            self._shared_handoffs.append(handoff)
            self._pending_by_target[tgt] = handoff
        return {"success": True, "handoff": handoff}

    def get_pending_handoff(self, target_kitty: str, consume: bool = False) -> Optional[Dict[str, Any]]:
        with self._lock:
            if consume:
                return self._pending_by_target.pop(target_kitty, None)
            return self._pending_by_target.get(target_kitty)

    def get_handoff_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._shared_handoffs)

    def clear(self):
        with self._lock:
            self._shared_handoffs.clear()
            self._pending_by_target.clear()


kitty_sharing_hub = KittySharingHub()


def share_task_between_kitties(
    from_kitty: str,
    to_kitty: str,
    task_objective: str,
    prompt: str = "",
    response: str = "",
    code_snippets: Optional[str] = None
) -> Dict[str, Any]:
    return kitty_sharing_hub.share_task(
        from_kitty=from_kitty,
        to_kitty=to_kitty,
        task_objective=task_objective,
        prompt=prompt,
        response=response,
        code_snippets=code_snippets
    )


# =========================================================================
# Kitties Nomenclature & Synonyms
# =========================================================================
KITTIES_META = MODE_META
KITTY_ORDER = MODE_ORDER
current_kitty = current_mode
set_kitty = set_mode
next_kitty = next_mode
create_kitty = create_mode
update_kitty = update_mode
delete_kitty = delete_mode
reorder_kitties = reorder_modes
move_kitty = move_mode
reset_all_kitties = reset_all_modes
system_prompt_for_kitty = system_prompt_for


# Sync any registered custom modes on startup
try:
    from .core.mode_registry import mode_registry as _mr
    _mr._sync_with_ai_modes()
except Exception:
    pass



