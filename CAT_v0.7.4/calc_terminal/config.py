"""
CCT centralized configuration (spec section 13).

Before this module, settings were scattered: aicore.py wrote its own
~/.cct_ai_config.json for provider/model, theme.py wrote its own
~/.cct_theme.json for the color theme, memory.py had its own store for
facts/activity, and things like animation speed, history limits, or a
feedback-recipient address weren't stored anywhere — they were literal
constants inline in whichever file used them.

This module is the single source of truth going forward: one
dataclass (`CCTConfig`), one file (`~/.cct_config.json`), one
get/set/save API. It does NOT yet rip out aicore.py's or theme.py's
own persistence — that's real surgery on files that currently work,
and doing it carelessly under time pressure is how you break a
working AI connection. What it DOES do, today:

  - defines the full settings schema from the spec (provider, mode,
    theme, accent colors, animation speed, terminal appearance,
    startup page, model, ollama/openrouter endpoints, workspace dir,
    history limits, memory limits, simulation settings, feedback email)
  - persists it centrally and exposes get_config()/save_config()
  - is the fallback default source: theme.py's loader now asks this
    module for the configured default *before* falling back to its
    own hardcoded "dark" (see theme.load_saved_theme) — a real,
    working integration point, not parallel dead code
  - is ready for the Settings UI (cmd_settings) to read/write against
    instead of ad hoc prompts

Migrating aicore.py's provider/model storage and theme.py's per-theme
file fully onto this module is the next increment, tracked in
CHANGELOG_v0.6.3_architecture.md — not done silently, not skipped
silently.
"""

import json
import os
from dataclasses import dataclass, field, asdict, fields
from typing import Optional

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".cct_config.json")


@dataclass
class SimulationSettings:
    frame_delay: float = 0.06
    default_max_frames: int = 600
    default_orbital_points: int = 2200
    monte_carlo_batch: int = 6


@dataclass
class CCTConfig:
    # --- feedback ---
    feedback_email: Optional[str] = None          # recipient; None = unset
    feedback_backend: str = "none"                # "none" | "smtp" | "api"

    # --- AI ---
    default_ai_provider: str = "openai"            # openai|claude|gemini|groq|openrouter|ollama|custom
    default_ai_mode: str = "notebook"               # notebook|research|plan|build|debugger|agent
    default_model: str = ""                         # provider-specific model id; "" = provider default
    privacy_policy: str = "local_first"            # local_first | cloud_first | best_available | never_cloud
    enable_model_fallback: bool = True             # auto failover across local/cloud model chain
    ollama_endpoint: str = "http://localhost:11434"
    openrouter_endpoint: str = "https://openrouter.ai/api/v1"
    model_cache_ttl_hours: float = 24.0            # how long cache/models/ lists stay fresh before auto-refresh

    # --- AI request lifecycle (v0.7.9.5) --------------------------------
    # Total-request deadlines by prompt class, in seconds. A streaming
    # response is NEVER cut off mid-tokens just because it's long: the
    # total deadline only fires when nothing useful has been produced,
    # while model_idle_timeout bounds silence BETWEEN tokens.
    timeout_simple: int = 30                        # trivial/fast-path prompts
    timeout_normal: int = 60                        # regular chat turns
    timeout_large: int = 300                        # agent / build / pipeline work
    model_idle_timeout: int = 45                    # max silence between stream chunks
    model_max_retries_per_provider: int = 1         # extra attempts per provider
    model_provider_cooldown: float = 20.0           # seconds a failing provider sits out
    model_retry_backoff_base: float = 0.6           # exponential backoff base (0.6s, 1.2s, ...)

    # --- appearance ---
    default_theme: str = "dark"
    accent_colors: dict = field(default_factory=lambda: {
        "notebook": "#7aa2f7",   # blue (ai_modes MODE_META notebook)
        "agent":    "#bb9af7",   # purple (agent)
        "build":    "#e0af68",   # orange (build)
        "plan":     "#9ece6a",   # green (plan)
        "research": "#ff69b4",   # hot pink (research)
        "debugger": "#dc143c",   # crimson (debugger)
    })
    accent_gradients: dict = field(default_factory=dict)  # optional explicit gradients {mode: [start_hex, end_hex]}
    # --- full mode customization (v0.7.9.8) ---
    # When non-empty, these completely replace ai_modes.MODE_META / MODE_ORDER
    # (snapshot of current modes). Empty = use built-in defaults + accent_colors overrides.
    user_modes: dict = field(default_factory=dict)  # {key: {label, icon, accent, gradient:[s,e], purpose, system_prompt?}}
    user_mode_order: list = field(default_factory=list)  # ordered keys matching user_modes
    # --- extensions (v0.7.9.10) ---
    # Gestures / Vision / Personalize are installable extensions: enabled => show in main menu,
    # disabled/uninstalled => hidden until re-enabled via Extensions panel.
    # Empty dict = all enabled (backward compat). Explicit False = disabled/uninstalled.
    extensions: dict = field(default_factory=dict)  # e.g. {"gestures": true, "vision": false, "personalize": true}
    animation_speed: float = 1.0                    # multiplier; 0.5 = slower, 2.0 = faster
    terminal_appearance: str = "auto"                # "auto" | "ansi256" | "truecolor"
    startup_page: str = "welcome"                    # "welcome" | "last_session" | "notebook"
    sidebar_collapsed: bool = False                  # Explorer sidebar open/closed (persisted toggle state)

    # --- permissions ---
    default_permission_mode: str = "ask"              # ask|restricted|full

    # --- workspace / data ---
    workspace_directory: str = field(
        default_factory=lambda: os.path.join(os.path.expanduser("~"), "cct_workspace"))
    history_limit: int = 500
    memory_limit: int = 2000

    simulation: SimulationSettings = field(default_factory=SimulationSettings)

    # ---------------------------------------------------------- helpers --
    def to_dict(self):
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d):
        d = dict(d or {})
        sim = d.pop("simulation", None) or {}
        known = {f.name for f in fields(cls)}
        d = {k: v for k, v in d.items() if k in known}
        cfg = cls(**d)
        if sim:
            for k, v in sim.items():
                if hasattr(cfg.simulation, k):
                    setattr(cfg.simulation, k, v)
        return cfg

    def get(self, dotted_key, default=None):
        """e.g. get('accent_colors.build') or get('simulation.frame_delay')"""
        obj = self
        for part in dotted_key.split("."):
            if isinstance(obj, dict):
                if part not in obj:
                    return default
                obj = obj[part]
            elif hasattr(obj, part):
                obj = getattr(obj, part)
            else:
                return default
        return obj

    def set(self, dotted_key, value):
        parts = dotted_key.split(".")
        obj = self
        for part in parts[:-1]:
            obj = obj[part] if isinstance(obj, dict) else getattr(obj, part)
        last = parts[-1]
        if isinstance(obj, dict):
            obj[last] = value
        else:
            setattr(obj, last, value)


_cached = None


def _seed_from_aicore(cfg):
    """If the user already configured a provider via /ai (aicore.py's
    own ~/.cct_ai_config.json) before this central config existed, use
    its non-secret fields (provider/model/ollama_url) as the initial
    defaults here instead of showing the generic hardcoded ones. Reads
    the file directly rather than importing aicore, so config.py stays
    the lighter-weight module with no dependency on it."""
    aicore_file = os.path.join(os.path.expanduser("~"), ".cct_ai_config.json")
    if not os.path.exists(aicore_file):
        return cfg
    try:
        with open(aicore_file, "r", encoding="utf-8") as f:
            ai = json.load(f)
    except (json.JSONDecodeError, OSError):
        return cfg
    if ai.get("provider"):
        cfg.default_ai_provider = ai["provider"]
    if ai.get("model"):
        cfg.default_model = ai["model"]
    if ai.get("ollama_url"):
        cfg.ollama_endpoint = ai["ollama_url"]
    return cfg


def load_config():
    """Read ~/.cct_config.json, filling in defaults for anything missing
    or malformed. Never raises — a corrupt config file degrades to
    defaults rather than crashing the app."""
    global _cached
    if _cached is not None:
        return _cached
    cfg = CCTConfig()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            cfg = CCTConfig.from_dict(raw)
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass
    else:
        # first run ever — no point re-asking for a provider the user
        # already set up through /ai before this module existed
        cfg = _seed_from_aicore(cfg)
    _cached = cfg
    return cfg


def save_config(cfg=None):
    """Persist the given (or currently cached) config to disk. Returns
    True on success, False if the write failed (e.g. read-only home)."""
    global _cached
    cfg = cfg or _cached or CCTConfig()
    _cached = cfg
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg.to_dict(), f, indent=2)
        return True
    except OSError:
        return False


def get_config():
    return load_config()
