"""
CCT AI Personalization (v0.7.8 BONUS 2).

A professional, honest personalization layer on top of the existing
prompt pipeline. The user keeps a set of named "profiles"; the active
profile adjusts every AI answer's style WITHOUT replacing any of CCT's
norman system prompts, tools, or memory:

  - tone        -> a short directive appended to the system prompt
                   (balanced / concise / detailed / playful / formal)
  - additions   -> free-form rules the user writes ("always use SI
                   units", "never mention the JSON protocol", ...)
  - temperature -> a sampling override (0.0 - 2.0), applied where the
                   request config supports it — see request_config()
  - model       -> a preferred model label; advisory today (kept as
                   metadata the panel shows, because forcing a model
                   string across every provider/api_style the way a
                   real pin would is exactly the kind of deep rewrite
                   this passes on). It IS surfaced in the dashboard.
  - description, top_p, creativity, reasoning, response_length,
    memory_pref -> advisory metadata (v0.7.8.1 Personalize redesign):
    stored on the profile and surfaced in the dashboard; top_p IS
    forwarded to the request config (and payloads) where supported,
    the rest describe the profile for future wiring and are honest
    metadata, never fake settings.

Persistence: ~/.cct_profiles.json
    {"active": "<name>", "profiles": [ {name, description, tone,
     temperature, top_p, additions, model, creativity, reasoning,
     response_length, memory_pref, created_at, updated_at}, ... ]}

Integration points (both single-line, no behavior rewrite):
  - ai_modes.system_prompt_for   — every non-agent UI mode prompt
  - agent.run_agent              — agent + ai personas (tools loop)

A profile never affects anything when none is active; callers that
want the raw prompt keep pinning their own system_prompt and nothing
changes.
"""

from __future__ import annotations

import json
import os
import time

PROFILE_FILE = os.path.join(os.path.expanduser("~"), ".cct_profiles.json")

TONES = {
    "balanced": "Keep a measured, even tone: clear and direct, neither terse nor padded.",
    "concise": "Be concise. Answer in the fewest words that stay complete; prefer short sentences and no filler.",
    "detailed": "Be thorough. Give full context, step-by-step reasoning, and complete derivations where relevant.",
    "playful": "Keep a friendly, light tone. Stay accurate, but feel free to be a little playful and warm.",
    "formal": "Be formal and precise. Use professional, carefully-phrased language without casualisms.",
}

DEFAULT_PROFILE = {
    "name": "Balanced",
    "description": "",
    "tone": "balanced",
    "temperature": None,
    "top_p": None,
    "additions": "",
    "model": "",
    "creativity": None,
    "reasoning": "",
    "response_length": "",
    "memory_pref": "",
    "created_at": 0,
    "updated_at": 0,
}


def load_profiles() -> dict:
    """Return {'active': name, 'profiles': [...]}. Never raises."""
    try:
        if os.path.exists(PROFILE_FILE):
            with open(PROFILE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                profiles = data.get("profiles")
                if isinstance(profiles, list):
                    cleaned = []
                    for p in profiles:
                        if not isinstance(p, dict):
                            continue
                        base = dict(DEFAULT_PROFILE)
                        base.update({k: p.get(k, v) for k, v in DEFAULT_PROFILE.items()})
                        cleaned.append(base)
                    return {"active": str(data.get("active") or ""), "profiles": cleaned}
    except Exception:
        pass
    return {"active": "", "profiles": []}


def save_profiles(data: dict) -> bool:
    try:
        with open(PROFILE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "active": str(data.get("active") or ""),
                "profiles": [dict(DEFAULT_PROFILE, **p) for p in (data.get("profiles") or [])],
            }, f, indent=2)
        return True
    except Exception:
        return False


def profiles() -> list[dict]:
    return load_profiles().get("profiles", [])


def profile_names() -> list[str]:
    return [p.get("name", "?") for p in profiles()]


def active_profile() -> dict | None:
    """The active profile as a dict, or None when none is active or
    the active name no longer exists."""
    data = load_profiles()
    name = data.get("active") or ""
    if not name:
        return None
    for p in data.get("profiles", []):
        if p.get("name") == name:
            return p
    return None


def set_active(name: str):
    data = load_profiles()
    data["active"] = name
    save_profiles(data)


def add_profile(name: str, tone: str = "balanced", additions: str = "",
                temperature=None, model: str = "", **extras) -> dict:
    """Create or replace a profile by name (name is the key). Returns it.

    `extras` are stored as-is (used by the Personalize panel for the
    advisory fields: description, top_p, creativity, reasoning,
    response_length, memory_pref)."""
    now = int(time.time())
    prof = {
        "name": name,
        "tone": tone if tone in TONES else "balanced",
        "temperature": temperature,
        "additions": additions,
        "model": model,
        "created_at": now,
        "updated_at": now,
    }
    for key in ("description", "top_p", "creativity", "reasoning",
                "response_length", "memory_pref"):
        if extras.get(key) is not None:
            prof[key] = extras[key]
    data = load_profiles()
    data["profiles"] = [p for p in data["profiles"] if p.get("name") != name]
    data["profiles"].append(prof)
    save_profiles(data)
    return prof


def update_profile(name: str, **fields) -> dict | None:
    prof = add_profile(name,
                       tone=fields.get("tone", "balanced"),
                       additions=fields.get("additions", ""),
                       temperature=fields.get("temperature"),
                       model=fields.get("model", ""),
                       description=fields.get("description"),
                       top_p=fields.get("top_p"),
                       creativity=fields.get("creativity"),
                       reasoning=fields.get("reasoning"),
                       response_length=fields.get("response_length"),
                       memory_pref=fields.get("memory_pref"))
    return prof


def delete_profile(name: str):
    data = load_profiles()
    data["profiles"] = [p for p in data["profiles"] if p.get("name") != name]
    if data.get("active") == name:
        data["active"] = ""
    save_profiles(data)


# ---------------------------------------------------------------------------
# Integration helpers

ABOUT_ME_FILE = os.path.join(os.path.expanduser("~"), ".cct_about_me.json")

def load_about_me() -> dict:
    try:
        if os.path.exists(ABOUT_ME_FILE):
            with open(ABOUT_ME_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    return {}


def about_me_block() -> str:
    data = load_about_me()
    if not data or not any(v.strip() for v in data.values() if isinstance(v, str)):
        return ""
    lines = []
    for k, v in data.items():
        if isinstance(v, str) and v.strip():
            label = k.replace("_", " ").title()
            lines.append(f"- {label}: {v.strip()}")
    if not lines:
        return ""
    return "About the user:\n" + "\n".join(lines)


def is_memory_enabled() -> bool:
    prof = active_profile()
    if not prof:
        return True
    pref = (prof.get("memory_pref") or "auto").strip().lower()
    if pref == "off":
        return False
    return True


def tone_directive(profile: dict | None) -> str:
    if not profile:
        return ""
    tone = profile.get("tone") or "balanced"
    base = TONES.get(tone, TONES["balanced"])
    additions = (profile.get("additions") or "").strip()
    if not additions:
        return base
    return base + "\nUser style rules (always follow these, they override defaults):\n" + additions


def personalize_system_prompt(base_prompt: str) -> str:
    """Append the active profile's style directive + About Me to a system prompt."""
    if os.environ.get("CCT_DISABLE_PERSONALIZATION"):
        return base_prompt
    prof = active_profile()
    directive = tone_directive(prof)
    about = about_me_block()
    extra = ""
    if directive:
        extra += "\n\n<Personal style>\n" + directive + "\n</Personal style>"
    if about:
        extra += "\n\n<About Me>\n" + about + "\n</About Me>"
    if not extra:
        return base_prompt
    if base_prompt.endswith(extra.strip()):
        return base_prompt
    return base_prompt.rstrip() + extra


def request_config() -> dict | None:
    """Request-config overrides for the active profile: a dict with
    'temperature' and/or 'top_p' keys when the profile pins them, else
    None. Pass as `config` to aicore.query_ai/stream_ai to merge over
    the primary provider config (aicore merges {'temperature': ...} /
    {'top_p': ...} into the OpenAI/Anthropic/Gemini payloads)."""
    prof = active_profile()
    if not prof:
        return None
    out = {}
    temp = prof.get("temperature")
    if temp is not None:
        try:
            out["temperature"] = float(temp)
        except (TypeError, ValueError):
            pass
    top_p = prof.get("top_p")
    if top_p is not None:
        try:
            out["top_p"] = float(top_p)
        except (TypeError, ValueError):
            pass
    return out if out else None


def active_model_label() -> str:
    prof = active_profile()
    if not prof:
        return ""
    return prof.get("model") or ""