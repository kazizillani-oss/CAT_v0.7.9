"""
AI Integration Core for CCT [BETA].
Supports local Ollama or API-based models (OpenAI/Claude style) for chemistry.
"""

if __name__ == '__main__':
    print("This is a library file and is not meant to be run directly.")
    print("Please run 'python main.py' or 'python model.py' from the project root directory.")
    import sys
    sys.exit(1)

import os
import re
import json
import time
import sys
import base64
import zlib
import logging
import threading
import uuid
from urllib.parse import unquote, parse_qs, urlparse
from html import unescape as _html_unescape
try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    requests = None
    _HAS_REQUESTS = False

from . import theme
from . import identity
from .providers.provider_manager import (get_provider, get_provider_class,
    list_builtin_providers, resolve_config,
    fetch_models_for, connect_provider, mask_key)
from .providers.provider_manager import load_config as _pm_load_config
from .providers.provider_manager import save_config as _pm_save_config

_LOG = logging.getLogger("cct.aicore")

# Config is now managed by providers/provider_manager.py.
# kept here only for backward-compatible imports
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".cct_ai_config.json")

# Default chat system prompt, shared by query_ai()/stream_ai() when no
# caller-specific prompt is passed in (agent.py passes its own, richer
# prompts, which also fold in identity.IDENTITY_BLOCK -- see agent.py).
# Folding the identity block in here too means even code paths that call
# aicore directly with the bare default still answer "who made you"
# style questions correctly and consistently.
DEFAULT_SYSTEM_PROMPT = (
    "You are CAT AI, a coding and science assistant inside the Coding Agent "
    "calculations.\n\n" + identity.IDENTITY_BLOCK
)

# ---------------------------------------------------------------- provider registry
# Built dynamically from the provider SDK so every registered provider shows up
# automatically.  query_ai()/stream_ai() dispatch on `api_style` through the
# provider instance.  To add a new provider, create a subclass of BaseProvider
# and call provider_manager.register_provider() — no other code needs to change.
PROVIDERS = {}
_BUILTIN_PROVIDER_DICT = None

def _build_provider_dict(force_reload=False):
    global _BUILTIN_PROVIDER_DICT
    if _BUILTIN_PROVIDER_DICT is not None and not force_reload:
        return _BUILTIN_PROVIDER_DICT
    d = {}
    for info in list_builtin_providers():
        pid = info["id"]
        d[pid] = {
            "base_url": info.get("url", ""),
            "default_model": info.get("default_model", ""),
            "api_style": info.get("api_style", "openai"),
            "needs_key": info.get("needs_key", True),
            "extra_headers": {},
        }
    # Add providers that aren't built-in but essential
    extras = {
        "openrouter": {"base_url": "https://openrouter.ai/api/v1",
                       "default_model": "openai/gpt-4o-mini", "api_style": "openai",
                       "needs_key": True,
                       "extra_headers": {"HTTP-Referer": "https://github.com/cct",
                                         "X-Title": "Chemistry Calc Terminal"}},
        "groq":       {"base_url": "https://api.groq.com/openai/v1",
                       "default_model": "llama3.1-70b-versatile", "api_style": "openai",
                       "needs_key": True, "extra_headers": {}},
        "ollama":     {"base_url": "http://localhost:11434", "default_model": "llama3.3",
                       "api_style": "ollama", "needs_key": False, "extra_headers": {},
                       "auto_discover": True},
        "moonshot":   {"base_url": "https://api.moonshot.cn/v1", "default_model": "kimi-k3",
                       "api_style": "openai", "needs_key": True, "extra_headers": {}},
        "xai":        {"base_url": "https://api.x.ai/v1", "default_model": "grok-3",
                       "api_style": "openai", "needs_key": True, "extra_headers": {}},
    }
    d.update(extras)
    # Load ALL providers from providers.json so any provider selected via
    # /model or /provider has a valid base_url (nvidia, deepseek, etc.)
    try:
        from .models.manager import load_providers
        for p in load_providers():
            pid = p.get("id", "")
            if pid and pid not in d:
                ep = p.get("api_endpoint", "")
                d[pid] = {
                    "base_url": ep,
                    "default_model": p.get("default_model", ""),
                    "api_style": p.get("api_style", "openai"),
                    "needs_key": bool(p.get("needs_key", True)),
                    "extra_headers": {},
                }
            elif pid and pid in d and not d[pid].get("base_url"):
                d[pid]["base_url"] = p.get("api_endpoint", "")
    except Exception:
        pass
    _BUILTIN_PROVIDER_DICT = d
    return d


def _get_provider_info(provider_id):
    """Get provider info, with cache refresh if base_url is missing."""
    providers = _build_provider_dict()
    info = providers.get(provider_id)
    # v0.7.10: If provider exists but has no base_url, refresh cache
    if info and not info.get("base_url") and provider_id:
        providers = _build_provider_dict(force_reload=True)
        info = providers.get(provider_id)
    return info

# ---------------------------------------------------------------- token usage
# Best-effort session token accounting. Real usage is pulled straight out of
# the provider's own response body when it reports one (OpenAI/Anthropic/
# Gemini/native-Ollama all do); anything that doesn't is estimated at ~4
# chars/token, the same rule-of-thumb every provider's own docs use.
SESSION_USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "requests": 0}

# Known context-window sizes are data-driven now: curated model metadata
# lives in models/model_metadata.json (context_length), with the provider's
# fallback list in providers/providers.json. context_window_for() consults
# those stores first and only falls back to this default estimate.
DEFAULT_CONTEXT_WINDOW = 32000


def estimate_tokens(text):
    """Rough ~4-chars-per-token estimate, used whenever a provider doesn't
    report real usage numbers back."""
    if not text:
        return 0
    return max(1, len(str(text)) // 4)


def context_window_for(model):
    if not model:
        return DEFAULT_CONTEXT_WINDOW
    model = str(model).lower()
    # Data-driven: curated metadata first (exact id, any provider)...
    try:
        from .models import manager as _mgr
        meta = _mgr.get_model_meta(model)
        ctx = meta.get("context_length")
        if ctx:
            return int(ctx)
    except Exception:
        pass
    # ...then heuristic family match across all curated metadata.
    try:
        from .models.registry import get_model_info
        for _, m in _load_metadata_items():
            if m.get("family") and m["family"].lower() in model:
                ctx = m.get("context_length")
                if ctx:
                    return int(ctx)
    except Exception:
        pass
    return DEFAULT_CONTEXT_WINDOW


def _load_metadata_items():
    """Yield (model_id, metadata_dict) for every curated model."""
    from .models import manager as _mgr
    try:
        with open(_mgr.MODEL_METADATA_FILE, "r", encoding="utf-8") as f:
            import json as _json
            for m in _json.load(f).get("models", []):
                yield m.get("id", ""), m
    except Exception:
        return iter(())


def record_usage(prompt_tokens, completion_tokens):
    SESSION_USAGE["prompt_tokens"] += int(prompt_tokens or 0)
    SESSION_USAGE["completion_tokens"] += int(completion_tokens or 0)
    SESSION_USAGE["total_tokens"] += int(prompt_tokens or 0) + int(completion_tokens or 0)
    SESSION_USAGE["requests"] += 1


def get_session_usage():
    """Snapshot of this session's token use plus a best-effort estimate of
    how much of the current model's context window is left."""
    config = load_config()
    model = config.get("model", "")
    window = context_window_for(model)
    used = SESSION_USAGE["total_tokens"]
    return {
        "prompt_tokens": SESSION_USAGE["prompt_tokens"],
        "completion_tokens": SESSION_USAGE["completion_tokens"],
        "total_tokens": used,
        "requests": SESSION_USAGE["requests"],
        "model": model or "(not configured)",
        "context_window": window,
        "remaining_estimate": max(0, window - used),
    }


def reset_session_usage():
    SESSION_USAGE.update({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "requests": 0})


def _track_usage_from_data(api_style, data, prompt_text, completion_text):
    """Pull real usage numbers out of the provider's response body when
    present; fall back to the character-based estimate otherwise. Never
    raises — token accounting is a nice-to-have, not a dependency."""
    try:
        if api_style == "openai" and isinstance(data, dict) and isinstance(data.get("usage"), dict):
            u = data["usage"]
            record_usage(u.get("prompt_tokens", estimate_tokens(prompt_text)),
                         u.get("completion_tokens", estimate_tokens(completion_text)))
            return
        if api_style == "anthropic" and isinstance(data, dict) and isinstance(data.get("usage"), dict):
            u = data["usage"]
            record_usage(u.get("input_tokens", estimate_tokens(prompt_text)),
                         u.get("output_tokens", estimate_tokens(completion_text)))
            return
        if api_style == "gemini" and isinstance(data, dict) and isinstance(data.get("usageMetadata"), dict):
            u = data["usageMetadata"]
            record_usage(u.get("promptTokenCount", estimate_tokens(prompt_text)),
                         u.get("candidatesTokenCount", estimate_tokens(completion_text)))
            return
        if api_style == "ollama" and isinstance(data, dict) and "eval_count" in data:
            record_usage(data.get("prompt_eval_count", estimate_tokens(prompt_text)),
                         data.get("eval_count", estimate_tokens(completion_text)))
            return
    except Exception:
        pass
    record_usage(estimate_tokens(prompt_text), estimate_tokens(completion_text))


# ---------------------------------------------------------------- model switch
# Model suggestions are data-driven: the provider's fallback list in
# providers.json (seeded from the provider's own model catalog). Live
# fetching happens when /model opens — see models/manager.py.
def common_models(provider_id):
    """Recommended/known model ids for a provider (providers.json
    fallback list, plus any cached live list). Never raises."""
    out = []
    try:
        from .models import manager as _mgr
        provider = _mgr.get_provider(provider_id)
        if provider:
            out = [str(m) for m in provider.get("fallback_models", [])]
        cached = _mgr.get_cached(provider_id)
        if cached:
            live = [str(m) for m in cached[0]]
            for m in live:
                if m not in out:
                    out.append(m)
    except Exception:
        pass
    return out[:40]


def switch_model(model_name):
    """Change just the model for the currently configured provider —
    lighter-weight than the full /ai setup_ai() wizard. Returns (ok, msg)."""
    model_name = (model_name or "").strip()
    if not model_name:
        return False, "No model name given."
    config = load_config()
    if not config.get("provider"):
        return False, "No AI provider configured yet. Run /ai or /model to set one up first."
    old = config.get("model")
    config["model"] = model_name
    save_config(config)
    return True, f"Model switched from '{old}' to '{model_name}' ({config['provider']})."


# load_config/save_config delegate to provider_manager (so callers that
# do `from calc_terminal.aicore import load_config` still work).
def load_config():
    return _pm_load_config()

def save_config(config):
    return _pm_save_config(config)

def list_models(config):
    """Fetch the live list of model IDs actually available to this
    provider/key. Returns a (possibly empty) list of strings, never
    raises — callers should treat an empty list as 'listing unsupported
    or unreachable right now', not as an error.

    Priority chain (models/manager.py): provider API -> disk cache
    (cache/models/) -> built-in fallback list (providers.json).
    Successful fetches are cached on disk with a timestamp.
    """
    if not _HAS_REQUESTS:
        return []
    provider = config.get("provider")
    if not provider:
        return []
    # Data-driven resolution with disk caching
    try:
        from .models import manager as _mgr
        models, source = _mgr.get_models(provider, config)
        # "default" is the last-resort placeholder — treat as unsupported
        if models and models != ["default"]:
            return list(models)
    except Exception:
        pass
    # Legacy fallback for providers not covered by the manager
    info = _get_provider_info(provider)
    api_style = info["api_style"] if info else "openai"
    if provider == "ollama":
        base_url = config.get("ollama_url") or (info["base_url"] if info else "http://localhost:11434")
    else:
        base_url = config.get("base_url") or config.get("api_url") or (info["base_url"] if info else "")
    base_url = base_url.rstrip("/")
    api_key = config.get("api_key", "")
    extra_headers = info["extra_headers"] if info else {}
    try:
        if api_style == "ollama" and not base_url.endswith("/v1"):
            resp = requests.get(f"{base_url}/api/tags", timeout=8)
            if resp.status_code >= 400:
                return []
            return sorted(m.get("name", "") for m in resp.json().get("models", []) if m.get("name"))
        elif api_style == "openai":
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            headers.update(extra_headers)
            resp = requests.get(f"{base_url}/models", headers=headers, timeout=10)
            if resp.status_code >= 400:
                return []
            data = resp.json().get("data", [])
            return sorted(m.get("id", "") for m in data if isinstance(m, dict) and m.get("id"))
        elif api_style == "gemini":
            resp = requests.get(f"{base_url}/models?key={api_key}", timeout=10)
            if resp.status_code >= 400:
                return []
            out = []
            for m in resp.json().get("models", []):
                methods = m.get("supportedGenerationMethods", [])
                if not methods or "generateContent" in methods:
                    out.append(m.get("name", "").split("/")[-1])
            return sorted(set(n for n in out if n))
        else:
            return []
    except Exception:
        return []


def _prompt_model(provider, default_model, available):
    """Prompt for a model name, offering a live-fetched picker when one is
    available, but ALWAYS accepting free-form text too — so any model,
    including brand-new ones not in the list yet, still works. Also
    catches the classic mistake of typing the provider's name itself
    (e.g. typing 'gemini' as the model) instead of a real model id.
    """
    shown = available[:20]
    if shown:
        print(theme.dim(f"  Found {len(available)} model(s) available to this key/server."
                         + (f" Showing first {len(shown)}:" if len(available) > len(shown) else "")))
        for i, m in enumerate(shown, 1):
            print(theme.cyan(f"    {i}.") + " " + theme.text(m))
        print(theme.faint(f"  Type a number to pick one, or type ANY model name directly."))

    while True:
        model_in = input(theme.dim(f"  Model (default: {default_model}) \u25b8 ")).strip()
        if shown and model_in.isdigit() and 1 <= int(model_in) <= len(shown):
            return shown[int(model_in) - 1]
        candidate = _clean_model_name(model_in, default_model)
        if candidate.strip().lower() == str(provider).strip().lower():
            print(theme.orange(f"  '{candidate}' is the provider name, not a model id — "
                                f"e.g. try '{default_model}', or pick a number above."))
            continue
        return candidate


def setup_ai():
    if not _HAS_REQUESTS:
        print(theme.red("\n  Error: The 'requests' library is not installed."))
        print(theme.dim("  AI features require the 'requests' package to communicate with APIs."))
        print(theme.dim("  Please run: ") + theme.text("pip install requests", bold=True))
        time.sleep(3)
        return

    while True:
        theme.clear_screen()
        # Build the menu dynamically from PROVIDERS so every registered
        # provider shows up without hand-editing this list.
        menu_lines = [
            theme.badge("BETA", theme.BG_WARN) + " " + theme.purple("AI CONFIGURATION", bold=True),
            theme.dim("CAT AI is specialized for complex problem solving & scientific computing."),
            theme.dim("Any provider works with ANY model it supports — pick from the live list"),
            theme.dim("shown after your key, or type a model name yourself at any time."),
            "",
            theme.text("Choose your AI Provider:"),
        ]
        provider_dict = _build_provider_dict()
        keys = list(provider_dict.keys())
        for i, name in enumerate(keys, 1):
            info = provider_dict[name]
            tag = "Local, no key" if not info["needs_key"] else "API Key"
            menu_lines.append(theme.cyan(f"{i}. {name.capitalize()} ({tag})"))
        menu_lines.append(theme.cyan(f"{len(keys) + 1}. Custom API Endpoint"))
        menu_lines.append(theme.cyan(f"{len(keys) + 2}. Back to Menu"))
        menu_lines += ["", theme.faint("Press Enter to skip / use default settings.")]
        print(theme.panel(menu_lines, title="AI SETUP", color=theme.PURPLE, width=70))

        choice = input(theme.dim("  choice \u25b8 ")).strip()
        back_index = len(keys) + 2
        if choice == str(back_index) or choice == "":
            return

        config = load_config()

        # ---- pick a provider from the registry ----
        if choice.isdigit() and 1 <= int(choice) <= len(keys):
            name = keys[int(choice) - 1]
            info = provider_dict[name]
            config["provider"] = name
            # v0.7.10: Always save base_url when selecting a provider
            if info.get("base_url"):
                config["base_url"] = info["base_url"]
            if info["needs_key"]:
                config["api_key"] = input(theme.dim(f"  Enter {name.capitalize()} API Key \u25b8 ")).strip()
            available = []
            if info["needs_key"] or name == "ollama":
                print(theme.dim("  Checking which models are available..."))
                available = list_models(config)
            config["model"] = _prompt_model(name, info["default_model"], available)
            break

        # ---- custom endpoint (user supplies everything) ----
        elif choice == str(len(keys) + 1):
            config["provider"] = "custom"
            config["api_url"] = input(theme.dim("  API Endpoint URL \u25b8 ")).strip()
            config["base_url"] = config["api_url"]
            config["api_key"] = input(theme.dim("  API Key \u25b8 ")).strip()
            print(theme.dim("  Checking which models are available (best-effort, OpenAI-style /models)..."))
            available = list_models(config)
            config["model"] = _prompt_model("custom", "", available) if available else \
                input(theme.dim("  Model Name \u25b8 ")).strip()
            break

    save_config(config)
    print(theme.green("\n  AI Configuration saved successfully!"))
    print(theme.dim("  Verifying connection..."))
    ok, msg, models = verify_connection(config)
    print((theme.green if ok else theme.red)(("  \u2713 " if ok else "  \u2717 ") + msg))
    if models:
        preview = ", ".join(models[:8])
        print(theme.faint(f"  Models seen: {preview}{', ...' if len(models) > 8 else ''}"))
    time.sleep(1.5)


def _clean_model_name(user_input, default):
    """Normalise the model name typed at the prompt. Empty input, or words like
    'yes'/'no'/'ok' (commonly typed meaning 'use the default'), fall back to the
    real default — never saved literally as a model name."""
    if not user_input:
        return default
    if user_input.lower() in ("yes", "y", "no", "n", "ok", "true", "false", "default"):
        return default
    return user_input

def verify_connection(config=None):
    """Actively test the configured AI provider/model — a real network
    round trip, not just 'is a config file present'. Returns
    (ok: bool, message: str, models: list[str]).

    Uses the provider SDK for all built-in providers; falls back to
    the legacy per-api_style logic for non-SDK providers (ollama, groq).
    """
    if not _HAS_REQUESTS:
        return False, "The 'requests' library is not installed. Run: pip install requests", []

    config = config or load_config()
    provider = config.get("provider")
    if not provider:
        return False, "No AI provider configured yet. Run /ai (or /ai-verify after setup) to configure one.", []

    # Try provider SDK first
    try:
        inst = get_provider(config)
        if inst:
            ok, msg, models = inst.connect()
            return ok, msg, models
    except Exception:
        pass

    # Fallback for non-SDK providers
    info = _get_provider_info(provider)
    api_style = info["api_style"] if info else "openai"

    if provider == "ollama":
        base_url = config.get("ollama_url") or (info["base_url"] if info else "http://localhost:11434")
    else:
        base_url = config.get("base_url") or config.get("api_url") or (info["base_url"] if info else "")
    base_url = base_url.rstrip("/")

    api_key = config.get("api_key", "")
    model = config.get("model") or (info["default_model"] if info else "")
    extra_headers = info["extra_headers"] if info else {}

    try:
        if api_style == "ollama" and not base_url.endswith("/v1"):
            resp = requests.get(f"{base_url}/api/tags", timeout=8)
            _raise_for_status(resp)
            models = [m.get("name", "") for m in resp.json().get("models", [])]
            if models and model and not any(model in m for m in models):
                return (True,
                        f"Connected to Ollama at {base_url}, but model '{model}' isn't pulled locally yet. "
                        f"Run: ollama pull {model}",
                        models)
            return True, f"Connected to Ollama at {base_url} \u2014 {len(models)} local model(s) available.", models

        elif api_style == "openai":
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            headers.update(extra_headers)
            resp = requests.get(f"{base_url}/models", headers=headers, timeout=10)
            _raise_for_status(resp)
            data = resp.json().get("data", [])
            models = [m.get("id", "") for m in data if isinstance(m, dict)]
            note = ""
            if models and model and not any(model == m or model in m for m in models):
                note = f" Note: '{model}' wasn't in the list returned for this key — double-check the model name."
            return True, f"Connected to {provider} at {base_url} \u2014 {len(models)} model(s) visible to this key.{note}", models

        elif api_style == "gemini":
            resp = requests.get(f"{base_url}/models?key={api_key}", timeout=10)
            _raise_for_status(resp)
            models = []
            for m in resp.json().get("models", []):
                methods = m.get("supportedGenerationMethods", [])
                if not methods or "generateContent" in methods:
                    models.append(m.get("name", "").split("/")[-1])
            note = ""
            if models and model and model not in models:
                note = f" Note: '{model}' wasn't in the list returned for this key — pick one of the models shown, or double-check the name."
            return True, f"Connected to Gemini \u2014 {len(models)} model(s) visible to this key.{note}", models

        else:
            reply = query_ai("Reply with only the single word: OK",
                              system_prompt="You are a connectivity test. Reply with only: OK")
            failure_markers = ("could not reach", "the ai request timed out",
                                "error connecting", "http 4", "http 5", "not configured")
            if reply and not any(reply.lower().startswith(m) for m in failure_markers):
                return True, f"Connected to {provider}, model '{model}' responded successfully.", []
            return False, f"Connection test failed: {reply}", []

    except requests.exceptions.ConnectionError:
        return False, f"Could not reach {base_url}. Check the URL / your internet, or that Ollama is running (ollama serve).", []
    except requests.exceptions.Timeout:
        return False, "Connection timed out.", []
    except RuntimeError as e:
        return False, f"Verification failed: {e}", []
    except Exception as e:
        return False, f"Verification failed: {e}", []


def _sanitize_history(history):
    """Normalizes whatever a caller hands us into a clean list of
    (role, text) pairs with only 'user'/'assistant' roles, no empty
    turns, and no in-flight streaming placeholder (empty text). This
    is the ONE place that decides what "conversation history" means
    for every provider below — every api_style builds its request
    from this, so none of them can silently drop it again."""
    if not history:
        return []
    out = []
    for item in history:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            role, text = item
        elif isinstance(item, dict):
            role, text = item.get("role"), item.get("text", item.get("content", ""))
        else:
            continue
        role = "assistant" if role in ("assistant", "ai", "model") else "user"
        text = (text or "").strip()
        if text:
            out.append((role, text))
    return out


def _history_char_count(history):
    return sum(len(t) for _, t in history)


def _openai_messages(system_prompt, history, prompt, attachments=None, vision=False, model=""):
    """Shared by every OpenAI-compatible api_style (openai, groq,
    openrouter, vLLM, Ollama's /v1 endpoint) — system prompt, then
    every prior turn in order, then the new user prompt.

    v0.7.8.1: when `vision` is True and attachments carry images, the
    final user message becomes a content array (text + image_url data
    URLs) so vision-capable models actually see the attached images
    instead of only reading their metadata. v0.7.8.2: image parts use
    the OpenAI shape only here; Anthropic/Gemini get their own shapes
    (see _user_content)."""
    messages = []
    mod_lower = (model or "").lower()
    is_o1_mini = "o1-mini" in mod_lower or "o1-preview" in mod_lower
    sys_role = "developer" if ("o1" in mod_lower or "o3" in mod_lower) and not is_o1_mini else "system"
    if system_prompt:
        if is_o1_mini:
            prompt = f"{system_prompt}\n\n{prompt}"
        else:
            messages.append({"role": sys_role, "content": system_prompt})
    for role, text in history:
        messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": _user_content(
        prompt, attachments, vision, api_style="openai")})
    return messages


def _anthropic_messages(history, prompt, attachments=None, vision=False):
    """Anthropic keeps `system` as its own top-level field, so this
    only builds the `messages` array (user/assistant turns)."""
    messages = [{"role": role, "content": text} for role, text in history]
    messages.append({"role": "user", "content": _user_content(
        prompt, attachments, vision, api_style="anthropic")})
    return messages


def _gemini_contents(history, prompt, attachments=None, vision=False):
    """Gemini calls the assistant role 'model', not 'assistant'."""
    contents = []
    for role, text in history:
        contents.append({"role": ("model" if role == "assistant" else "user"),
                          "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": _user_content(
        prompt, attachments, vision, api_style="gemini")})
    return contents


def _user_content(prompt, attachments=None, vision=False, api_style="openai"):
    """The final user message content. Plain string when there is
    nothing to attach natively; a provider-correct content array with
    text + image parts when vision is available AND readable images are
    attached. Images that failed to read are skipped here — their
    textual fallback block (built by the attachment manager) still
    carries the metadata.

    v0.7.8.2 (attachment pipeline fix): the image parts are shaped per
    provider — Anthropic and Gemini reject OpenAI's `image_url` block
    (they each have their own schema), so a vision-capable Anthropic or
    Gemini model previously received a malformed content array and the
    attached image never reached it. Each api_style now emits its own
    native shape:
      - openai:    {"type": "image_url", "image_url": {url: data-url}}
      - anthropic: {"type": "image", "source": {base64, media_type}}
      - gemini:    {"inline_data": {mime_type, data}}
    """
    if not vision or not attachments:
        return prompt
    images = []
    try:
        from . import attachments as _att
        for att in attachments:
            if _att.attachment_has_image_payload(att):
                # v0.7.9.0: the vision pipeline may hand us an ALREADY-
                # normalized base64 payload (metadata["inline_b64"]) — use
                # it directly instead of re-reading/re-encoding the file.
                inline = None
                try:
                    inline = (att.metadata or {}).get("inline_b64")
                except Exception:
                    inline = None
                if inline:
                    images.append((getattr(att, "mime_type", "image/png") or "image/png",
                                   inline))
                    continue
                try:
                    mime, b64 = _att.encode_image_data_url(att.path)
                except Exception:
                    continue
                images.append((mime, b64))
    except Exception:
        return prompt
    if not images:
        return prompt
    parts = []
    if api_style == "anthropic":
        parts.append({"type": "text", "text": prompt})
        for mime, b64 in images:
            parts.append({"type": "image",
                          "source": {"type": "base64", "media_type": mime,
                                     "data": b64}})
        return parts
    if api_style == "gemini":
        parts.append({"text": prompt})
        for mime, b64 in images:
            parts.append({"inline_data": {"mime_type": mime, "data": b64}})
        return parts
    parts.append({"type": "text", "text": prompt})
    for mime, b64 in images:
        parts.append({"type": "image_url",
                      "image_url": {"url": f"data:{mime};base64,{b64}"}})
    return parts


def _ollama_native_prompt(system_prompt, history, prompt):
    """The native /api/generate endpoint (no v1 alias) only accepts one
    flat `prompt` string — no messages array. To keep it from forgetting
    the conversation the same way the message-based providers would, we
    fold prior turns into the prompt as a plain transcript. `system` is
    still passed separately via the `system` field."""
    if not history:
        return prompt
    lines = [f"{'Assistant' if role == 'assistant' else 'User'}: {text}" for role, text in history]
    transcript = "\n".join(lines)
    return f"Conversation so far:\n{transcript}\n\nUser: {prompt}\nAssistant:"


def _resolve_provider(config):
    """Shared provider/URL/model resolution — used by both query_ai
    (blocking) and stream_ai (generator) so there's one place that
    decides which base_url/model/headers a request uses, not two that
    can drift apart. Returns (api_style, base_url, api_key, model,
    temperature, extra_headers)."""
    provider = config.get("provider")
    # Try provider SDK first
    _inst = get_provider(config)
    if _inst:
        base_url = _inst.get_base_url()
        # v0.7.10: Ensure base_url is never empty for non-SDK providers
        if not base_url and provider:
            info = _get_provider_info(provider)
            if info and info.get("base_url"):
                base_url = info["base_url"]
        return (_inst.API_STYLE, base_url, _inst.get_api_key(),
                _inst.get_model(), config.get("temperature"), _inst.get_extra_headers())
    info = _get_provider_info(provider)
    api_style = info["api_style"] if info else "openai"
    if provider == "ollama":
        base_url = config.get("ollama_url") or config.get("base_url") or (info["base_url"] if info else "http://localhost:11434")
        if "https://localhost" in base_url or base_url.rstrip("/") in ("http://localhost", "https://localhost"):
            base_url = "http://localhost:11434"
        if not api_style or (api_style == "openai" and "11434" not in base_url):
            api_style = "ollama"
    else:
        base_url = config.get("base_url") or config.get("api_url") or (info["base_url"] if info else "")
        # v0.7.10: If still no base_url, try to get it from providers.json
        if not base_url and provider:
            try:
                from .models.manager import load_providers
                for p in load_providers():
                    if p.get("id") == provider:
                        base_url = p.get("api_endpoint", "")
                        if base_url:
                            break
            except Exception:
                pass
    base_url = base_url.rstrip("/") if base_url else ""
    api_key = config.get("api_key", "")
    if not (api_key or "").strip() and provider:
        try:
            from .providers.provider_manager import get_env_api_key
            api_key = get_env_api_key(provider)
        except Exception:
            pass
    model = config.get("model") or (info["default_model"] if info else "gpt-4o-mini")
    temperature = config.get("temperature")
    extra_headers = info["extra_headers"] if info else {}
    return api_style, base_url, api_key, model, temperature, extra_headers


# The exact prefixes query_ai() (and query_ai_with_image()) return
# instead of raising, on every known failure path — copied verbatim
# from those functions' own `return` statements below so this can
# never drift out of sync silently. Used by callers (app.py's cmd_ai/
# cmd_agent, ui/app.py's _stream_worker) that want to show a real
# error-recovery card (spec section 19) instead of rendering the
# failure as if it were a normal chat answer.
_ERROR_SIGNATURES = (
    "The 'requests' library is required for AI features.",
    "AI not configured.",
    "Could not reach the AI server.",
    "The AI request timed out.",
    "Error connecting to AI:",
    "No model response received.",
    "Invalid API key.",
    "Rate limited.",
    "Quota exceeded.",
    "Model '",
    "Error: ",
    "*(Generation timed out)*",
    "(Generation timed out)",
    "Generation timed out",
    "*(interrupted",
    "Ollama Error:",
    "Error: Ollama",
    "Could not reach Ollama",
    "The Ollama request timed out",
    "Ollama streaming failure:",
)
# not a fixed prefix (provider name is interpolated) — matched separately
_ERROR_SUFFIX = "is not supported yet. Run /ai to reconfigure."


def is_error_response(text):
    """True if `text` is one of query_ai's own failure messages rather
    than an actual model answer."""
    if not text or not isinstance(text, str):
        return False
    t = text.strip()
    if t.startswith(_ERROR_SIGNATURES) or t.endswith(_ERROR_SUFFIX):
        return True
    low = t.lower()
    return any(h in low for h in _FALLOVER_HINTS)


# ---------------------------------------------------------------------------
# Backup-provider failover (v0.7.8 BONUS 1). query_ai()/stream_ai() first
# try the saved primary provider; when it reports quota exhaustion, a
# timeout, rate limiting, or is simply offline, they walk the enabled
# backup chain (providers/provider_manager.backup_configs(), priority
# order) and seamlessly finish the request against the next healthy one.
# The conversation never notices: history/summaries live in the UI and
# are re-sent verbatim to whichever provider answers.
#
# v0.7.9.5 REQUEST LIFECYCLE OVERHAUL (the '...' bug): the walk now has
# real engineering around it instead of one blind attempt per provider:
#
#   * TOTAL + IDLE timeouts, configurable per prompt class (config.py:
#     timeout_simple / timeout_normal / timeout_large /
#     model_idle_timeout). A provider trickling bytes forever can no
#     longer hold a turn open indefinitely, while an actively streaming
#     model is never misclassified as frozen just because it's slow.
#   * BOUNDED retries with EXPONENTIAL BACKOFF per provider
#     (model_max_retries_per_provider, model_retry_backoff_base) — only
#     for transient failures (timeouts / connection errors); quota and
#     config errors skip straight to the next provider.
#   * PROVIDER COOLDOWN (model_provider_cooldown): a provider that just
#     failed sits out future requests briefly, so a dead primary stops
#     taxing every turn; backups are tried first until it recovers.
#   * CANCELLATION: every in-flight HTTP response is registered;
#     cancel_active_requests() closes the sockets so Ctrl+C can stop a
#     request that's blocked inside a socket read.
#   * STRUCTURED REQUEST LOGGING (~/.cct_requests.log): one JSON line
#     per lifecycle event (start/first_token/finish/error/retry/
#     fallback) with timings and exception class — never API keys —
#     so a stuck response can always be diagnosed after the fact.

_FALLOVER_HINTS = ("quota", "rate limit", "rate_limit", "insufficient_quota",
                   "limit exceeded", "exhausted", "429 ", "could not reach",
                   "connection", "api key", "unauthorized", "401", "403",
                   "model not found", "not found", "no model", "not running",
                   "timed out", "timeout", "timedout", "time out",
                   "generation timed out", "cannot connect", "failed to connect",
                   "could not reach ollama", "ensure ollama is running")

# A hook the UI can install (set_failover_hook) to surface failover
# moments as chat notes instead of silence.
_FAILOVER_HOOK = None


def _should_failover(text):
    """True when a returned text looks like a provider-level failure worth
    switching providers for — CCT's own error strings, or the typical
    HTTP-level rate-limit / quota wording providers embed in bodies."""
    if not text or not isinstance(text, str):
        return True
    if not text.strip():
        return True
    if is_error_response(text):
        return True
    low = text.lower()
    return any(h in low for h in _FALLOVER_HINTS)


def _retryable_failure(text):
    """True for TRANSIENT failures worth an immediate retry against the
    SAME provider (network blip, momentary read timeout). Quota /
    rate-limit / configuration failures are not retryable — retrying
    them just burns seconds before the inevitable fallback."""
    if not text:
        return False
    t = text.strip()
    if t.startswith(("Could not reach the AI server.", "The AI request timed out.")):
        return True
    low = t.lower()
    # Transient network/timeout issues are worth retrying
    transient_hints = ("timed out", "timeout", "connection reset", "connection refused",
                       "connection error", "connection aborted", "broken pipe",
                       "eof occurred", "incomplete read", "remote end closed",
                       "server disconnected", "503", "502", "500")
    # Non-retryable: quota, auth, config issues
    non_retryable_hints = ("quota", "rate limit", "rate_limit", "401", "403",
                           "api key", "unauthorized", "not found", "404",
                           "not supported", "end of life", "deprecated")
    if any(h in low for h in non_retryable_hints):
        return False
    return any(h in low for h in transient_hints)


def _notify_failover(message):
    try:
        if _FAILOVER_HOOK is not None:
            _FAILOVER_HOOK(message)
    except Exception:
        pass


def set_failover_hook(callback):
    """Install a callable(message) hook invoked on every failover step
    (exhausted primary, switching to backup N, connected). The Textual UI
    uses this to post chat system notes; the classic REPL may leave it
    None to stay silent. Pass None to clear."""
    global _FAILOVER_HOOK
    _FAILOVER_HOOK = callback


def _backup_chain():
    """Get the backup provider chain for failover.
    
    v0.7.9.5: Improved Ollama handling for backup failover. Ollama
    providers are prioritized for local inference when available,
    providing a reliable fallback that works offline and has no
    rate limits or quota issues.
    
    v0.7.10: Enhanced model selection — always prefers instruct/chat
    models over base models; broader keyword matching for quality
    models; GPU/VRAM-aware model selection.
    """
    try:
        from .providers.provider_manager import backup_configs
        chain = backup_configs()
        
        # Base model identifiers (these models can't follow instructions)
        _BASE_MODEL_HINTS = ("-base", "_base", "base-q", "base_q",
                             ":base", "-base-", "base_model")
        # Good instruct/chat model identifiers
        _INSTRUCT_HINTS = ("instruct", "chat", "r1", "gemma", "qwen",
                           "llama-3", "phi-3", "phi-4", "mistral",
                           "codellama", "coder", "deepseek", "yi-",
                           "command", "mixtral", "wizard", "nous",
                           "solar", "neural", "orca", "zephyr",
                           "hermes", "dolphin", "tinyllama",
                           "starcoder", "codestral", "granite")
        
        def _is_base_model(name):
            low = name.lower()
            return any(b in low for b in _BASE_MODEL_HINTS)
        
        def _is_good_instruct(name):
            low = name.lower()
            if _is_base_model(name):
                return False
            return any(k in low for k in _INSTRUCT_HINTS)
        
        enhanced_chain = []
        for cfg, entry in chain:
            if cfg.get("provider") == "ollama":
                # Ensure Ollama has correct api_style and no key requirement
                cfg["api_style"] = "ollama"
                cfg["needs_key"] = False
                base_url = cfg.get("base_url") or "http://localhost:11434"
                cfg["base_url"] = base_url
                # Auto-verify that the configured model is installed locally;
                # If not or if it's a raw base model, fallback to a healthy instruct model!
                try:
                    import requests
                    tag_r = requests.get(f"{base_url}/api/tags", timeout=2.0)
                    if tag_r.status_code == 200:
                        raw_models = [m.get("name") for m in tag_r.json().get("models", []) if m.get("name")]
                        # Split into instruct vs base
                        instruct_models = [m for m in raw_models if not _is_base_model(m)]
                        good_models = [m for m in instruct_models if _is_good_instruct(m)]
                        # Prefer good instruct > any non-base > all
                        candidates = good_models if good_models else (instruct_models if instruct_models else raw_models)
                        
                        cur_m = cfg.get("model", "")
                        is_cur_base = _is_base_model(cur_m)
                        has_m = any(
                            cur_m == im or (":" not in cur_m and im.startswith(f"{cur_m}:"))
                            for im in candidates
                        )
                        if (not has_m or is_cur_base) and candidates:
                            # Score candidates: prefer r1 > instruct/chat > gemma > other
                            def _score(m):
                                ml = m.lower()
                                s = 0
                                if "r1" in ml: s += 100
                                if "instruct" in ml: s += 80
                                if "chat" in ml: s += 70
                                if "gemma" in ml: s += 60
                                if "qwen" in ml: s += 55
                                if "llama" in ml: s += 50
                                if "phi" in ml: s += 45
                                if "deepseek" in ml: s += 40
                                if "mistral" in ml: s += 35
                                return s
                            best = max(candidates, key=_score)
                            cfg["model"] = best
                            _LOG.info("Backup chain: replaced base/missing model '%s' → '%s'", cur_m, best)
                except Exception:
                    pass
            enhanced_chain.append((cfg, entry))
        
        return enhanced_chain
    except Exception:
        return []


# ------------------------------------------------------- request tuning --
def request_timeouts(config=None, size_class="normal"):
    """(connect_timeout, idle_read_timeout, total_timeout) in seconds for
    one model attempt. `size_class` is one of 'simple' | 'normal' |
    'large' and maps to the configurable total deadlines in config.py.
    The idle cap never exceeds the total deadline."""
    try:
        if config is None:
            from . import config as _cfgmod
            cfg = _cfgmod.get_config()
        else:
            cfg = config
        # Normalize dict vs object access
        if isinstance(cfg, dict):
            get = lambda k, d: cfg.get(k, d)
        else:
            get = lambda k, d: getattr(cfg, k, d)
        totals = {
            "simple": get("timeout_simple", 30),
            "normal": get("timeout_normal", 60),
            "large": get("timeout_large", 300),
        }
        total = float(totals.get(str(size_class), get("timeout_normal", 60)))
        idle = float(get("model_idle_timeout", 45))
        # Ollama local needs longer for model load on cold start (especially 7B+ on CPU)
        prov = ""
        try:
            if isinstance(cfg, dict):
                prov = cfg.get("provider","") or cfg.get("default_ai_provider","")
            else:
                prov = getattr(cfg, "default_ai_provider", "") or getattr(cfg, "provider","")
            if not prov and isinstance(config, dict):
                prov = config.get("provider","")
            if str(prov).lower() == "ollama":
                total = max(total, 180.0)
                idle = max(idle, 120.0)
        except Exception:
            pass
        # Cloud providers connect timeout should be resilient against latency/proxies
        connect = max(5.0, min(15.0, idle))
        # Ollama connect needs longer on cold start (model load from disk into RAM/VRAM)
        try:
            if str(prov).lower() == "ollama":
                connect = max(connect, 35.0)
        except Exception:
            pass
        # Reasoning models (o1, o3, deepseek-r1, Claude thinking) take 30-90s before first token
        try:
            mod = ""
            if isinstance(cfg, dict):
                mod = cfg.get("model", "") or cfg.get("default_model", "")
            else:
                mod = getattr(cfg, "model", "") or getattr(cfg, "default_model", "")
            if not mod and isinstance(config, dict):
                mod = config.get("model", "")
            if any(k in str(mod).lower() for k in ("o1", "o3", "r1", "reason", "thinking", "3-7", "3.7")):
                idle = max(idle, 120.0)
                total = max(total, 180.0)
        except Exception:
            pass
        idle = max(5.0, min(idle, total))
        return connect, idle, max(5.0, total)
    except Exception:
        return 15.0, 60.0, 180.0


_RETRY_STATE_LOCK = threading.Lock()
_PROVIDER_LAST_FAILURE = {}   # (provider, model) -> monotonic time


def _provider_key(cfg):
    return (str((cfg or {}).get("provider") or "?"),
            str((cfg or {}).get("model") or "?"))


def _mark_provider_failed(cfg):
    try:
        with _RETRY_STATE_LOCK:
            _PROVIDER_LAST_FAILURE[_provider_key(cfg)] = time.monotonic()
    except Exception:
        pass


def _mark_provider_ok(cfg):
    try:
        with _RETRY_STATE_LOCK:
            _PROVIDER_LAST_FAILURE.pop(_provider_key(cfg), None)
    except Exception:
        pass


def _provider_in_cooldown(cfg):
    try:
        from . import config as _cfgmod
        cooldown = float(getattr(_cfgmod.get_config(), "model_provider_cooldown", 20.0))
    except Exception:
        cooldown = 20.0
    with _RETRY_STATE_LOCK:
        last = _PROVIDER_LAST_FAILURE.get(_provider_key(cfg))
    if last is None:
        return False
    return (time.monotonic() - last) < cooldown


def _backoff_sleep(attempt_index):
    """Exponential backoff between same-provider retries: base *
    2**attempt, capped at 4 s. Short by design — instant hammering
    feels broken, multi-second stalls feel frozen."""
    try:
        from . import config as _cfgmod
        base = float(getattr(_cfgmod.get_config(), "model_retry_backoff_base", 0.6))
    except Exception:
        base = 0.6
    delay = min(4.0, base * (2 ** max(0, attempt_index)))
    try:
        time.sleep(delay)
    except Exception:
        pass


def _failover_targets(primary_cfg=None, requirements=None):
    """The ordered list of (config, entry_or_None, is_backup) attempts for
    one logical request: the resolved primary first, then the enabled
    backup chain.
    
    Integrated with CAT's Backup Provider & Resilience System:
    - Tier 1: Fallback models on the same provider.
    - Tier 2: Priority-ordered dynamic backup pool.
    - Intelligent capability matching (vision, tools, coding).
    - Health monitoring and circuit breaker cooldowns.
    """
    primary = dict(primary_cfg or load_config())
    prim_prov = str(primary.get("provider", "")).lower()
    if prim_prov and not (primary.get("api_key") or "").strip():
        try:
            from .providers.provider_manager import get_env_api_key
            env_k = get_env_api_key(prim_prov)
            if env_k:
                primary["api_key"] = env_k
        except Exception:
            pass

    try:
        from .resilience.failover_engine import get_failover_engine
        from .resilience.types import TaskRequirements
        from .model_router import get_privacy_policy

        engine = get_failover_engine()
        req = requirements if isinstance(requirements, TaskRequirements) else TaskRequirements()
        pol = get_privacy_policy()

        candidates = engine.build_failover_targets(
            primary_config=primary,
            requirements=req,
            privacy_policy=pol,
        )
        if candidates:
            return [(dict(c.config), c.entry, c.is_backup) for c in candidates]
    except Exception:
        pass

    # Fallback to direct walk if resilience engine unavailable
    chain = [(primary, None, False)]
    prim_url = str(primary.get("base_url", "")).rstrip("/")
    prim_model = str(primary.get("model", "")).lower()
    for bcfg, entry in _backup_chain():
        try:
            b_prov = str(bcfg.get("provider", "")).lower()
            b_url = str(bcfg.get("base_url", "")).rstrip("/")
            b_model = str(bcfg.get("model", "")).lower()
            if b_prov == prim_prov and b_url == prim_url and b_model == prim_model:
                continue
            needs_key = bcfg.get("needs_key", True)
            if b_prov == "ollama":
                needs_key = False
            if needs_key and not (bcfg.get("api_key") or "").strip():
                try:
                    from .providers.provider_manager import get_env_api_key
                    bk_key = get_env_api_key(b_prov)
                    if bk_key:
                        bcfg["api_key"] = bk_key
                except Exception:
                    pass
            if needs_key and not (bcfg.get("api_key") or "").strip():
                continue
        except Exception:
            pass
        chain.append((dict(bcfg), entry, True))

    fresh = [c for c in chain if not c[2] or not _provider_in_cooldown(c[0])]
    cooled = [c for c in chain if c not in fresh]
    return fresh + cooled


def _attempts_per_provider():
    try:
        from . import config as _cfgmod
        n = int(getattr(_cfgmod.get_config(), "model_max_retries_per_provider", 1))
    except Exception:
        n = 1
    return max(1, n) + 1  # configured retries PLUS the initial attempt


# ----------------------------------------------------- cancellation kit --
_ACTIVE_LOCK = threading.Lock()
_ACTIVE_RESPONSES = set()
_ACTIVE_PROVIDERS = set()
_CANCELLED_AT = 0.0  # wall-clock stamp of the last cancel_active_requests()


def _register_response(resp):
    try:
        with _ACTIVE_LOCK:
            _ACTIVE_RESPONSES.add(resp)
    except Exception:
        pass


def _unregister_response(resp):
    try:
        with _ACTIVE_LOCK:
            _ACTIVE_RESPONSES.discard(resp)
    except Exception:
        pass


def _register_provider(prov):
    try:
        with _ACTIVE_LOCK:
            _ACTIVE_PROVIDERS.add(prov)
    except Exception:
        pass


def _unregister_provider(prov):
    try:
        with _ACTIVE_LOCK:
            _ACTIVE_PROVIDERS.discard(prov)
    except Exception:
        pass


def cancel_active_requests():
    """Close every in-flight provider socket so a blocked iter_lines()
    read raises immediately instead of waiting out its idle timeout.
    Called by the UI when the user hits Ctrl+C / Stop. Safe to call
    when nothing is running."""
    global _CANCELLED_AT
    _CANCELLED_AT = time.time()
    with _ACTIVE_LOCK:
        current = list(_ACTIVE_RESPONSES)
        providers = list(_ACTIVE_PROVIDERS)
    for resp in current:
        try:
            resp.close()
        except Exception:
            pass
    for prov in providers:
        try:
            if hasattr(prov, "cancel_active"):
                prov.cancel_active()
        except Exception:
            pass
    return len(current) + len(providers)


def _just_cancelled():
    """True within a short window after cancel_active_requests() — used
    to convert the close-induced socket exception into a clean stop
    rather than a scary error message."""
    return (time.time() - _CANCELLED_AT) < 3.0


# ------------------------------------------------- structured req log --
_REQUEST_LOG = os.path.join(os.path.expanduser("~"), ".cct_requests.log")
_REQUEST_LOG_MAX = 512 * 1024
_REQLOG_LOCK = threading.Lock()


def log_request_event(request_id, event, provider=None, model=None,
                      size_class=None, elapsed_ms=None, detail=None,
                      chars=None, retry_count=None, fallback=None):
    """One JSON line per lifecycle event into ~/.cct_requests.log
    (rotated at ~512 KB). Records WHERE a request stopped and why —
    the diagnosis tool the permanent-'...' bug always needed. Never
    logs API keys, headers or prompt contents."""
    record = {"ts": round(time.time(), 3), "request_id": request_id,
              "event": event}
    if provider:
        record["provider"] = provider
    if model:
        record["model"] = model
    if size_class:
        record["size_class"] = size_class
    if elapsed_ms is not None:
        record["elapsed_ms"] = int(elapsed_ms)
    if chars is not None:
        record["chars"] = chars
    if retry_count is not None:
        record["retry_count"] = retry_count
    if fallback is not None:
        record["fallback"] = bool(fallback)
    if detail:
        record["detail"] = str(detail)[:200]
    line = json.dumps(record, ensure_ascii=True, default=str)
    try:
        with _REQLOG_LOCK:
            try:
                if os.path.exists(_REQUEST_LOG) and \
                        os.path.getsize(_REQUEST_LOG) > _REQUEST_LOG_MAX:
                    os.replace(_REQUEST_LOG, _REQUEST_LOG + ".old")
            except Exception:
                pass
            with open(_REQUEST_LOG, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        pass
    try:
        _LOG.debug("aicore.request %s", line)
    except Exception:
        pass


def _query_ai_once(prompt, system_prompt=DEFAULT_SYSTEM_PROMPT,
                   history=None, config=None, attachments=None,
                   size_class="normal"):
    """Single-attempt blocking chat completion against ONE provider
    config. Implemented as a consumer of _stream_ai_once so every
    api_style branch lives in exactly one place — the concatenation of
    a streamed reply is byte-identical to the blocking reply, and both
    surface provider failures as the same error strings, which keeps
    the failover detection in query_ai consistent."""
    pieces = []
    _metrics_note_model_start(config)
    for piece in _stream_ai_once(prompt, system_prompt=system_prompt,
                                 history=history, config=config,
                                 attachments=attachments,
                                 size_class=size_class):
        pieces.append(piece)
    return "".join(pieces)


def query_ai(prompt, system_prompt=DEFAULT_SYSTEM_PROMPT,
             history=None, config=None, on_failover=None, attachments=None,
             size_class="normal", requirements=None):
    """`history` is an optional list of (role, text) pairs — or {"role","text"}
    dicts — for every prior turn that should stay in context, oldest first.
    Every branch below sends it to the provider in whatever shape that
    provider's API expects; omit it (or pass None/[]) for a genuinely
    one-shot call. See ChatSession.as_prompt_history() for the usual source.

    v0.7.8: on primary-provider failure (quota/timeout/rate-limit/offline)
    transparently falls back to the enabled backup chain, notifying the
    installed failover hook at each step. `on_failover` overrides the
    global hook for this one call when given.

    v0.7.8.1: `attachments` is an optional list of Attachment objects
    (calc_terminal/attachments.py). They are verified before the request
    and sent natively (images) or as a text context block, per provider
    capability.

    v0.7.9.5 request lifecycle: `size_class` ('simple' | 'normal' |
    'large') picks the configurable total deadline; each provider gets
    bounded retries with exponential backoff for TRANSIENT failures;
    quota/config failures move on immediately; recently-failed providers
    sit out via cooldown until the chain exhausts.

    Returns the assistant text, or (on total failure) ONE of the
    _ERROR_SIGNATURES strings — loading states can always key off those,
    and callers can always tell a real answer from a failure."""
    hook_override = on_failover or _FAILOVER_HOOK

    def notify(message):
        try:
            if hook_override is not None:
                hook_override(message)
        except Exception:
            pass

    targets = _failover_targets(config, requirements=requirements)
    max_attempts = _attempts_per_provider()
    result = ""
    fallback_used = False

    for t_idx, (cfg, entry, is_backup) in enumerate(targets):
        provider = cfg.get("provider", "?")
        model = cfg.get("model", "")
        try:
            from .resilience.health_monitor import get_health_monitor
            get_health_monitor().record_turn_start(provider, model)
        except Exception:
            pass
        t_turn_start = time.time()
        for attempt in range(max_attempts):
            if attempt:
                log_request_event(_short_id(), "retry_same_provider",
                                  provider=provider,
                                  model=cfg.get("model"),
                                  size_class=size_class,
                                  retry_count=attempt)
            result = _query_ai_once(prompt, system_prompt=system_prompt,
                                    history=history, config=cfg,
                                    attachments=attachments,
                                    size_class=size_class)
            if not _should_failover(result):
                if is_backup:
                    _mark_backup_success(entry)
                    notify("\u2713 Connected successfully.")
                _mark_provider_ok(cfg)
                try:
                    from .resilience.health_monitor import get_health_monitor
                    lat = (time.time() - t_turn_start) * 1000.0
                    get_health_monitor().record_success(provider, model, latency_ms=lat)
                except Exception:
                    pass
                log_request_event(_short_id(), "finish",
                                  provider=provider, model=cfg.get("model"),
                                  size_class=size_class, chars=len(result),
                                  fallback=fallback_used)
                return result
            # Failure. Transient? → brief backoff, retry same provider.
            if attempt + 1 < max_attempts and _retryable_failure(result):
                log_request_event(_short_id(), "attempt_failed_retryable",
                                  provider=provider, detail=result[:120],
                                  size_class=size_class)
                _backoff_sleep(attempt)
                continue
            break  # non-retryable → next provider
        _mark_provider_failed(cfg)
        try:
            from .resilience.health_monitor import get_health_monitor
            from .resilience.failover_engine import get_failover_engine
            from .resilience.types import FailureType
            ft = get_failover_engine().classify_failure(result)
            get_health_monitor().record_failure(
                provider, model, error_message=result,
                is_rate_limit=(ft == FailureType.RATE_LIMIT)
            )
        except Exception:
            pass
        log_request_event(_short_id(), "provider_exhausted",
                          provider=provider, detail=result[:160],
                          size_class=size_class, fallback=True)
        if t_idx + 1 < len(targets):
            fallback_used = True
            nxt_cfg = targets[t_idx + 1][0]
            nxt = nxt_cfg.get("provider", "?")
            nxt_m = nxt_cfg.get("model", "")
            cur_m = cfg.get("model", "")
            cur_desc = f"{provider} ({cur_m})" if cur_m else provider
            nxt_desc = f"{nxt} ({nxt_m})" if nxt_m else nxt
            notify(f"\u26a0 Provider issue with {cur_desc}. Switching to Backup "
                   f"Provider ({nxt_desc})...")

    # Every provider failed — surface the last failure message so the UI
    # shows a real error card instead of waiting forever.
    log_request_event(_short_id(), "all_providers_failed",
                      detail=result[:200], size_class=size_class)
    return result


def _short_id():
    """Short unique id for log correlation."""
    return uuid.uuid4().hex[:12]


def _mark_backup_success(entry):
    try:
        from .providers.provider_manager import mark_backup_used
        mark_backup_used(entry)
    except Exception:
        pass


def _peek_first(generator):
    """Pull the first item from a generator, returning (item, generator)
    so callers can inspect it (failover decision) and still stream the
    rest exactly as the underlying generator produced it.

    The returned generator is the ORIGINAL generator, already advanced
    past the first item — it must NOT include `first` again, because
    every caller here does `yield first; yield from rest` and re-including
    it would emit the first chunk twice ("hellohello"). The previous
    `chain([first], generator)` implementation caused exactly that: every
    streamed reply started with its first fragment duplicated."""
    try:
        first = next(generator)
    except StopIteration:
        return None, iter(())
    return first, generator


def stream_ai(prompt, system_prompt=DEFAULT_SYSTEM_PROMPT,
              history=None, config=None, on_failover=None, attachments=None,
              size_class="normal", requirements=None):
    """Generator version of query_ai — yields text fragments as they
    arrive instead of returning one finished string, so the primary UI
    (calc_terminal/ui/) can grow a ConversationItem token-by-token
    instead of freezing until the whole reply lands.

    v0.7.8 failover: if the first fragment from the primary provider is a
    provider-failure signature, the whole stream is transparently retried
    against the next healthy backup instead of showing the error.

    v0.7.9.5 request lifecycle hardening:
      * NOTHING is yielded until real content arrives, so a failing
        provider can never leave a permanent '...' on screen — the walk
        moves to backups first.
      * A failure BEFORE any token → bounded same-provider retries with
        exponential backoff, then the next provider (cooldown-aware).
      * A failure MID-STREAM (tokens already delivered) does NOT
        silently switch providers and re-run the whole answer — the
        partial reply is kept and the loss is disclosed in one honest
        line.
      * Every lifecycle step is written to ~/.cct_requests.log.

    v0.7.8.1: `attachments` — see query_ai; verified before each attempt,
    attached natively (vision providers) or as text context."""
    hook_override = on_failover or _FAILOVER_HOOK

    def notify(message):
        try:
            if hook_override is not None:
                hook_override(message)
        except Exception:
            pass

    targets = _failover_targets(config, requirements=requirements)
    max_attempts = _attempts_per_provider()
    fallback_used = False
    last_error_piece = None

    for t_idx, (cfg, entry, is_backup) in enumerate(targets):
        provider = cfg.get("provider", "?")
        for attempt in range(max_attempts):
            _metrics_note_model_start(cfg)
            got_content = False
            error_piece = None
            for piece in _stream_ai_once(prompt, system_prompt=system_prompt,
                                         history=history, config=cfg,
                                         attachments=attachments,
                                         size_class=size_class):
                if not got_content:
                    if is_error_response(piece):
                        error_piece = piece
                        break
                else:
                    # Once streaming has begun, individual fragments (including whitespace/newlines)
                    # are NOT provider failures. Only known error signatures break the stream.
                    t = piece.strip() if isinstance(piece, str) else ""
                    if t and (t.startswith(_ERROR_SIGNATURES) or t.endswith(_ERROR_SUFFIX)):
                        error_piece = piece
                        break
                # Real content: stream it out immediately (requirement:
                # first token replaces '...' right away).
                got_content = True
                yield piece
            if error_piece is None:
                if got_content:
                    if is_backup:
                        _mark_backup_success(entry)
                        notify("\u2713 Connected successfully.")
                    _mark_provider_ok(cfg)
                    log_request_event(_short_id(), "finish",
                                      provider=provider, model=cfg.get("model"),
                                      size_class=size_class, fallback=fallback_used)
                    return
                # Generator ended with zero tokens and no signature —
                # treat as a provider-level empty response.
                error_piece = "No model response received."
            if got_content:
                # Mid-stream loss: keep the partial answer, disclose the
                # drop, do NOT duplicate the reply from another provider.
                _mark_provider_failed(cfg)
                log_request_event(_short_id(), "midstream_drop",
                                  provider=provider, detail=error_piece[:120],
                                  size_class=size_class)
                yield ("\n\n\u26a0 Connection lost mid-response \u2014 partial "
                       "answer kept. Send again to continue.")
                return
            last_error_piece = error_piece
            if attempt + 1 < max_attempts and _retryable_failure(error_piece):
                log_request_event(_short_id(), "attempt_failed_retryable",
                                  provider=provider, detail=error_piece[:120],
                                  size_class=size_class)
                _backoff_sleep(attempt)
                continue
            break  # non-retryable → next provider
        _mark_provider_failed(cfg)
        log_request_event(_short_id(), "provider_exhausted",
                          provider=provider, detail=(error_piece or "")[:160],
                          size_class=size_class, fallback=True)
        if t_idx + 1 < len(targets):
            fallback_used = True
            nxt_cfg = targets[t_idx + 1][0]
            nxt = nxt_cfg.get("provider", "?")
            nxt_m = nxt_cfg.get("model", "")
            cur_m = cfg.get("model", "")
            cur_desc = f"{provider} ({cur_m})" if cur_m else provider
            nxt_desc = f"{nxt} ({nxt_m})" if nxt_m else nxt
            notify(f"\u26a0 Provider issue with {cur_desc}. Switching to Backup "
                   f"Provider ({nxt_desc})...")

    # Nothing received anywhere — surface the final failure message so
    # the UI renders an error card instead of an eternal spinner.
    yield last_error_piece or "No model response received."


def _prepare_attachments(attachments, config):
    """v0.7.8.1: verify attachment objects (spec section 7) and decide
    whether this provider receives them natively (vision-capable) or as
    text context. Returns the `vision` flag consumed by the request
    builders. Emits ProviderAdapter verification lines to the debug log
    — never file contents."""
    if not attachments:
        return False
    try:
        from . import attachments as _att
    except Exception:
        return False
    _att.AttachmentManager.verify(
        attachments, log=lambda m: _LOG.debug("ProviderAdapter: %s", m))
    vision = False
    try:
        vision = bool(_att.provider_capabilities(config).get("vision"))
    except Exception:
        vision = False
    has_image = any(
        _att.attachment_has_image_payload(a) for a in attachments if a is not None)
    if vision and has_image:
        _LOG.debug("ProviderAdapter: native image payload attached")
    else:
        _LOG.debug("ProviderAdapter: attachment_context = present (textual block)")
    return vision


def _metrics_note_model_start(config=None):
    """Best-effort metrics/event hooks for one model request (never raises,
    never slows the path down meaningfully)."""
    try:
        from . import metrics as _m
        m = _m.current()
        if m is not None:
            m.count_model_call()
            m.stage_start("model_first_token")
            if config and not m.model_used:
                m.model_used = f"{config.get('provider', '?')}/{config.get('model', '?')}"
    except Exception:
        pass
    try:
        from .event_stream import stream, MODEL_REQUEST_STARTED
        stream.emit(MODEL_REQUEST_STARTED, source="aicore",
                    provider=(config or {}).get("provider"),
                    model=(config or {}).get("model"))
    except Exception:
        pass


def _metrics_note_first_token():
    """Called on the first REAL streamed token of a completion."""
    try:
        from . import metrics as _m
        m = _m.current()
        if m is not None:
            m.note_first_token()
            m.stage_end("model_first_token")
    except Exception:
        pass
    try:
        from .event_stream import stream, MODEL_FIRST_TOKEN
        stream.emit(MODEL_FIRST_TOKEN, source="aicore")
    except Exception:
        pass


class _TotalTimeout(Exception):
    """Raised between stream chunks when the TOTAL request deadline
    expires (distinct from requests' idle read timeout)."""


def _stream_ai_once(prompt, system_prompt=DEFAULT_SYSTEM_PROMPT,
                    history=None, config=None, attachments=None,
                    size_class="normal", request_id=None):
    """Single-attempt streaming generator against ONE provider config —
    the core of the public stream_ai; see its docstring for streaming
    behavior semantics. `config` defaults to the saved primary config;
    the v0.7.8 failover wrapper retries this against each backup.

    v0.7.8.1: `attachments` (Attachment objects) are verified here
    (spec section 7), then folded in by the request builder — natively
    as image parts when the provider is vision-capable, otherwise as
    text via the attachment manager's context block.

    v0.7.9.5 lifecycle:
      * `size_class` selects the configurable total timeout.
      * Every HTTP call uses a (connect, idle) timeout tuple; the total
        deadline is enforced BETWEEN chunks via _TotalTimeout, so an
        actively streaming model is never cut off mid-tokens but a
        silent one can't hold the UI forever either.
      * The response socket is registered for cancel_active_requests().
      * start / first_token / finish / error are logged structurally."""
    request_id = request_id or _short_id()
    t_start = time.monotonic()

    def elapsed_ms():
        return int((time.monotonic() - t_start) * 1000)

    if not _HAS_REQUESTS:
        yield "The 'requests' library is required for AI features. Please run: pip install requests"
        return

    config = config or load_config()
    provider = config.get("provider")
    if not provider:
        yield "AI not configured. Run /ai or /agent to configure your provider."
        return

    api_style, base_url, api_key, model, temperature, extra_headers = _resolve_provider(config)
    history = _sanitize_history(history)
    usage_prompt_text = prompt if not history else "\n".join(t for _, t in history) + "\n" + prompt

    vision = _prepare_attachments(attachments, config)

    # ---- lifecycle instrumentation (v0.7.9.5) --------------------------
    t_connect_idle = request_timeouts(config, size_class)[:2]
    deadline = time.monotonic() + request_timeouts(config, size_class)[2]
    log_request_event(request_id, "start", provider=provider, model=model,
                      size_class=size_class)

    def _check_deadline():
        if time.monotonic() > deadline:
            raise _TotalTimeout()

    def _lines_with_deadline(iterator):
        """Wraps resp.iter_lines() so the TOTAL deadline is enforced
        between chunks. Bytes keep flowing → no timeout (an actively
        streaming model is never misclassified as frozen); true silence
        is already bounded by the socket idle timeout."""
        for line in iterator:
            _check_deadline()
            yield line

    _tracked = []  # registered responses, unregistered in finally

    def _track(resp):
        _register_response(resp)
        _tracked.append(resp)
        return resp

    class _FirstToken:
        fired = False

        @classmethod
        def hit(cls):
            if not cls.fired:
                cls.fired = True
                _metrics_note_first_token()
                log_request_event(request_id, "first_token",
                                  provider=provider, model=model,
                                  size_class=size_class,
                                  elapsed_ms=elapsed_ms())

    try:
        # v0.7.10: Validate base_url before making request
        if not base_url:
            yield "AI not configured — no base URL set for this provider. Run /ai to reconfigure."
            return
        if not model:
            yield "AI not configured — no model selected. Run /model to choose one."
            return
        # Upfront API key check so unconfigured providers fail over immediately
        _prov_info = _get_provider_info(provider)
        if _prov_info and _prov_info.get("needs_key") and not (api_key or "").strip():
            yield f"API key missing for provider '{provider}'. Run /key or /provider to configure."
            return

        if api_style == "openai":
            url = f"{base_url}/chat/completions"
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            headers.update(extra_headers)
            payload = {
                "model": model,
                "messages": _openai_messages(system_prompt, history, prompt,
                                             attachments=attachments, vision=vision, model=model),
                "stream": True,
            }
            mod_lower = (model or "").lower()
            is_o_reasoning = ("o1" in mod_lower or "o3" in mod_lower) and "openrouter" not in str(base_url).lower()
            if is_o_reasoning:
                payload["max_completion_tokens"] = 4096
            elif temperature is not None:
                payload["temperature"] = temperature
            resp = _track(requests.post(url, headers=headers, json=payload,
                                         timeout=t_connect_idle, stream=True))
            _raise_for_status(resp)
            full = []
            usage = None
            for line in _lines_with_deadline(resp.iter_lines(decode_unicode=True)):
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if data_str == "[DONE]":
                    break
                try:
                    obj = json.loads(data_str)
                except ValueError:
                    continue
                choices = obj.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or {}
                    piece = delta.get("content")
                    if piece:
                        full.append(piece)
                        _FirstToken.hit()
                        yield piece
                if isinstance(obj.get("usage"), dict):
                    usage = obj["usage"]
            completion_text = "".join(full)
            if usage:
                record_usage(usage.get("prompt_tokens", estimate_tokens(usage_prompt_text)),
                             usage.get("completion_tokens", estimate_tokens(completion_text)))
            else:
                record_usage(estimate_tokens(usage_prompt_text), estimate_tokens(completion_text))
            return

        elif api_style == "anthropic":
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            headers.update(extra_headers)
            payload = {
                "model": model,
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": _anthropic_messages(history, prompt,
                                                attachments=attachments, vision=vision),
                "stream": True,
            }
            if temperature is not None:
                payload["temperature"] = temperature
            resp = _track(requests.post(f"{base_url}/messages", headers=headers,
                                         json=payload, timeout=t_connect_idle,
                                         stream=True))
            _raise_for_status(resp)
            full = []
            in_tokens = out_tokens = None
            for line in _lines_with_deadline(resp.iter_lines(decode_unicode=True)):
                if not line or not line.startswith("data:"):
                    continue
                try:
                    obj = json.loads(line[len("data:"):].strip())
                except ValueError:
                    continue
                etype = obj.get("type")
                if etype == "content_block_delta":
                    piece = (obj.get("delta") or {}).get("text")
                    if piece:
                        full.append(piece)
                        _FirstToken.hit()
                        yield piece
                elif etype == "message_start":
                    u = (obj.get("message") or {}).get("usage") or {}
                    in_tokens = u.get("input_tokens", in_tokens)
                elif etype == "message_delta":
                    u = obj.get("usage") or {}
                    out_tokens = u.get("output_tokens", out_tokens)
            completion_text = "".join(full)
            record_usage(in_tokens if in_tokens is not None else estimate_tokens(usage_prompt_text),
                         out_tokens if out_tokens is not None else estimate_tokens(completion_text))
            return

        elif api_style == "gemini":
            clean_model = model.removeprefix("models/")
            url = f"{base_url}/models/{clean_model}:streamGenerateContent?alt=sse&key={api_key}"
            payload = {
                "contents": _gemini_contents(history, prompt,
                                             attachments=attachments, vision=vision),
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "generationConfig": {
                    "temperature": temperature if temperature is not None else 0.7,
                    "maxOutputTokens": 4096,
                },
            }
            resp = _track(requests.post(url, json=payload, timeout=t_connect_idle,
                                        stream=True))
            _raise_for_status(resp)
            full = []
            usage_meta = None
            for line in _lines_with_deadline(resp.iter_lines(decode_unicode=True)):
                if not line or not line.startswith("data:"):
                    continue
                try:
                    obj = json.loads(line[len("data:"):].strip())
                except ValueError:
                    continue
                candidates = obj.get("candidates") or []
                if candidates:
                    parts = (candidates[0].get("content") or {}).get("parts") or []
                    for part in parts:
                        piece = part.get("text")
                        if piece:
                            full.append(piece)
                            _FirstToken.hit()
                            yield piece
                if isinstance(obj.get("usageMetadata"), dict):
                    usage_meta = obj["usageMetadata"]
            completion_text = "".join(full)
            if usage_meta:
                record_usage(usage_meta.get("promptTokenCount", estimate_tokens(usage_prompt_text)),
                             usage_meta.get("candidatesTokenCount", estimate_tokens(completion_text)))
            else:
                record_usage(estimate_tokens(usage_prompt_text), estimate_tokens(completion_text))
            return

        elif api_style == "ollama":
            # Ensure Ollama is running — auto-start `ollama serve` if needed (fixes "Could not reach" when not running)
            try:
                from .ollama_download import ensure_ollama_running, is_ollama_installed
                ok, msg = ensure_ollama_running(base_url, timeout=3, auto_start=True)
                if not ok:
                    hint = "Ollama not installed — install from https://ollama.com/download and run `ollama serve`" if not is_ollama_installed() else msg
                    raise RuntimeError(f"Could not reach the AI server. Could not reach Ollama at {base_url}. {hint}. Or install a model via ☰ → Ollama Models.")
            except RuntimeError:
                raise
            except Exception:
                pass

            from .models.profiles import get_model_profile
            from .providers.ollama_adapter import OllamaProvider
            from .ai_context import get_context_manager, AIRequest, AIMessage
            import uuid

            profile = get_model_profile("ollama", model, config)
            options = profile.get_effective_options({"temperature": temperature})

            # Detect current AI mode
            active_mode = "chat"
            if config and isinstance(config, dict) and config.get("mode"):
                active_mode = config.get("mode")
            else:
                try:
                    from . import ai_modes as _am
                    active_mode = _am.current_mode()
                except Exception:
                    active_mode = "chat"

            # Filter and budget history using AIContextManager to prevent cross-mode context pollution
            ctx_mgr = get_context_manager()
            ai_history = []
            for r, t in (history or []):
                ai_history.append(AIMessage(id=uuid.uuid4().hex, role=r, content=t, mode=active_mode))

            req = AIRequest(
                session_id=str(getattr(config, "get", lambda k, d="": d)("session_id", "cct")),
                request_id=request_id or uuid.uuid4().hex,
                mode=active_mode,
                user_message=prompt,
                history=ai_history,
                model=model,
                provider="ollama",
            )
            built_ctx = ctx_mgr.build_context(req, profile=profile)
            messages = built_ctx.messages

            # If caller supplied a custom system prompt (and not default), apply it to system role
            if system_prompt and system_prompt != DEFAULT_SYSTEM_PROMPT and messages and messages[0]["role"] == "system":
                if profile.is_small_or_base() and len(system_prompt) > 800:
                    messages[0]["content"] = system_prompt[:800] + "\nAnswer concisely."
                else:
                    messages[0]["content"] = system_prompt

            ollama_prov = OllamaProvider(base_url)
            _register_provider(ollama_prov)
            full = []
            try:
                for piece in ollama_prov.stream_chat(
                    model=model,
                    messages=messages,
                    options=options,
                    timeout=t_connect_idle,
                    request_id=request_id,
                    deadline=deadline,
                ):
                    _FirstToken.hit()
                    full.append(piece)
                    yield piece
            finally:
                _unregister_provider(ollama_prov)

            completion_text = "".join(full)
            record_usage(estimate_tokens(usage_prompt_text), estimate_tokens(completion_text))
            return

        else:
            yield f"Provider '{provider}' is not supported yet. Run /ai to reconfigure."
            return

    except GeneratorExit:
        # Consumer stopped iterating (cancel / screen teardown). Run the
        # cleanup in finally and close the socket promptly.
        raise
    except _TotalTimeout:
        log_request_event(request_id, "error", provider=provider, model=model,
                          size_class=size_class, elapsed_ms=elapsed_ms(),
                          detail="total request deadline exceeded")
        yield ("The AI request timed out before the provider finished "
               "responding. Try again, or run `/model` to switch to a faster model.")
    except requests.exceptions.ConnectionError as ce:
        if _just_cancelled():
            return  # user cancelled — stop cleanly, no scary message
        ce_str = str(ce).lower()
        log_request_event(request_id, "error", provider=provider, model=model,
                          size_class=size_class, elapsed_ms=elapsed_ms(),
                          detail=f"connection error: {ce_str[:120]}")
        if "ollama" in (provider or "").lower() or "localhost" in (base_url or ""):
            yield ("Could not reach your local Ollama server. "
                   "Make sure Ollama is running (`ollama serve`), or run `/ai` to switch to a cloud provider.")
        else:
            yield (f"Could not reach {provider or 'the AI server'}. "
                   "Check your internet connection and API URL, or run `/model` to switch providers.")
    except requests.exceptions.Timeout:
        if _just_cancelled():
            return
        log_request_event(request_id, "error", provider=provider, model=model,
                          size_class=size_class, elapsed_ms=elapsed_ms(),
                          detail="idle read timeout")
        if "ollama" in (provider or "").lower():
            yield ("Ollama took too long to respond — the model may be loading. "
                   "Try sending your message again, or run `/model` to pick a smaller model.")
        else:
            yield (f"Request to {provider or 'AI'} timed out. "
                   "Try again, use a faster model (`/model`), or check your network.")
    except RuntimeError as e:
        # v0.7.10: Better error messages for common HTTP errors
        if _just_cancelled():
            return
        err_msg = str(e)
        log_request_event(request_id, "error", provider=provider, model=model,
                          size_class=size_class, elapsed_ms=elapsed_ms(),
                          detail=err_msg[:200])
        if "410" in err_msg or "end of life" in err_msg.lower():
            yield (f"Model '{model}' has been retired by {provider}. "
                   "Run `/model` to choose a current model.")
        elif "401" in err_msg or "unauthorized" in err_msg.lower():
            yield (f"Invalid API key for {provider}. "
                   "Run `/ai` to reconfigure with a valid key.")
        elif "429" in err_msg or "rate limit" in err_msg.lower():
            yield (f"{provider} rate limit hit. Wait a moment and retry, "
                   "or run `/model` to switch providers.")
        elif "402" in err_msg or "quota" in err_msg.lower() or "insufficient" in err_msg.lower():
            yield (f"{provider} quota exceeded. Run `/model` to switch to a free provider "
                   "or add credits to your account.")
        elif "404" in err_msg or "not found" in err_msg.lower():
            yield (f"Model '{model}' not found on {provider}. "
                   "Run `/model` to pick an available model.")
        elif "500" in err_msg or "internal server error" in err_msg.lower():
            yield (f"{provider} server error. This is usually temporary — "
                   "try again in a moment, or run `/model` to switch.")
        else:
            yield f"Error from {provider}: {err_msg}"
    except Exception as e:
        if _just_cancelled():
            return
        log_request_event(request_id, "error", provider=provider, model=model,
                          size_class=size_class, elapsed_ms=elapsed_ms(),
                          detail=f"{type(e).__name__}: {e}")
        yield f"Error connecting to {provider or 'AI'}: {type(e).__name__}: {e}"
    finally:
        # ALWAYS drop the socket registrations — a finished or failed
        # request must never keep cancel_active_requests() holding stale
        # response objects (requirement: loading state always clears).
        for r in _tracked:
            _unregister_response(r)
        _tracked.clear()


def _raise_for_status(resp):
    """Raise a clear error with the API's own message instead of a vague one.

    Most providers return a helpful JSON body explaining *why* a call failed
    (bad model name, invalid key, quota), but requests only surfaces the HTTP
    code. This pulls that detail out so the user can actually fix the issue.
    """
    if resp.status_code >= 400:
        try:
            body = resp.json()
            err = (body.get("error", {}).get("message")
                   or body.get("error", {}).get("status")
                   or str(body)[:300])
        except Exception:
            err = resp.text[:300] if resp.text else resp.reason
        raise RuntimeError(f"HTTP {resp.status_code}: {err}")


# ---------------------------------------------------------------- web search
# Key-free web search using DuckDuckGo's HTML endpoint (no API key needed,
# unlike Google/Bing search APIs). Used directly by /websearch and /research,
# and wired into the agent as a tool so it can look things up mid-answer.
def _unwrap_ddg_url(href):
    """DuckDuckGo's HTML results wrap outbound links in a redirect
    (/l/?uddg=<encoded-url>); unwrap that back to the real destination."""
    if href.startswith("//"):
        href = "https:" + href
    try:
        parsed = urlparse(href)
        if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
            qs = parse_qs(parsed.query)
            if "uddg" in qs:
                return unquote(qs["uddg"][0])
        return href
    except Exception:
        return href


_TAG_RE = re.compile(r"<.*?>", re.S)


def web_search(query, max_results=5):
    """Best-effort web search, no API key required. Returns a list of
    {\"title\", \"url\", \"snippet\"} dicts, or [] if unreachable/blocked —
    callers should treat an empty list as 'couldn't search right now', not
    an error."""
    query = (query or "").strip()
    if not query or not _HAS_REQUESTS:
        return []
    try:
        resp = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query}, timeout=12,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CAT/0.7.9.0)"},
        )
        if resp.status_code >= 400:
            return []
        html = resp.text
        results = []
        pattern = re.compile(
            r'result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'result__snippet[^>]*>(.*?)</a>', re.S)
        for m in pattern.finditer(html):
            href, title_html, snippet_html = m.groups()
            title = _html_unescape(_TAG_RE.sub("", title_html)).strip()
            snippet = _html_unescape(_TAG_RE.sub("", snippet_html)).strip()
            url = _unwrap_ddg_url(href)
            if title and url:
                results.append({"title": title, "url": url, "snippet": snippet})
            if len(results) >= max_results:
                break
        return results
    except Exception:
        return []


def deep_research(topic, num_queries=3, results_per_query=4):
    """Runs several web searches around different angles of `topic`, then
    asks the configured AI to synthesize a structured, source-numbered
    research summary from the actual retrieved snippets (not from the
    model's own unchecked memory). Returns (summary_text, sources) where
    sources is a de-duplicated list of {\"title\", \"url\", \"snippet\"} dicts,
    numbered in the same order referenced as [1], [2]... in the summary."""
    topic = (topic or "").strip()
    if not topic:
        return "No research topic given.", []

    sub_queries = [topic]
    config = load_config()
    if config.get("provider"):
        angles_raw = query_ai(
            f"Give exactly {num_queries} short, distinct web-search queries (one per "
            f"line, no numbering, no extra commentary) that together would build a "
            f"thorough, well-rounded understanding of: {topic}",
            system_prompt="You output ONLY the search queries, one per line, nothing else.")
        angles = [a.strip("-•*0123456789. ").strip() for a in (angles_raw or "").splitlines() if a.strip()]
        if angles:
            sub_queries = angles[:num_queries]

    all_results = []
    seen_urls = set()
    for q in sub_queries:
        for r in web_search(q, max_results=results_per_query):
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                all_results.append(r)

    if not all_results:
        return (f"No web results could be retrieved for '{topic}' — check the "
                f"internet connection this terminal has, DuckDuckGo may also be "
                f"rate-limiting/blocking this network."), []

    evidence = "\n\n".join(
        f"[{i + 1}] {r['title']}\n{r['url']}\n{r['snippet']}"
        for i, r in enumerate(all_results[:12]))

    if not config.get("provider"):
        return ("AI not configured, so here are the raw sources found "
                "(run /model or /ai to also get a synthesized summary):\n\n" + evidence,
                all_results[:12])

    summary = query_ai(
        f"Research topic: {topic}\n\nSources:\n{evidence}\n\n"
        "Write a clear, well-organized research summary of the topic using ONLY "
        "these sources. Reference sources inline as [1], [2] etc. matching the "
        "numbers above. Point out any disagreement between sources. Do not invent "
        "facts the sources don't support.",
        system_prompt=("You are a careful research assistant. Be accurate, cite "
                        "sources by their bracket number, and never invent facts "
                        "not supported by the given sources."))
    return summary, all_results[:12]


# ------------------------------------------------------------ file / image import
# Backs /import (feature 6): local text files get their content read straight
# into the AI/agent's context; local images get sent to a vision-capable
# provider (OpenAI/Anthropic/Gemini) so the model can actually "see" them.
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
TEXT_FILE_MAX_CHARS = 20000


def is_image_file(path):
    return os.path.splitext(str(path))[1].lower() in IMAGE_EXTS


def read_text_file_for_context(path):
    """Returns (content, truncated) or (None, False) on failure."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(TEXT_FILE_MAX_CHARS + 1)
        truncated = len(content) > TEXT_FILE_MAX_CHARS
        if truncated:
            content = content[:TEXT_FILE_MAX_CHARS]
        return content, truncated
    except Exception:
        return None, False


# ------------------------------------------------------- attachment context
# v0.7.6 Patch 1, Fix 7: one attachment gets one honest, real context block
# fed to the AI. Plain text/code/markdown gets its actual content; CSV gets
# a genuine header/sample/count; zip/tar get a real listing; PDF gets real
# metadata + a best-effort text-layer extraction (stdlib-only — no pypdf in
# this environment); audio/video report what's known (size/ext) and say
# plainly when a metadata library isn't installed. Never fabricated data.
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".wma", ".opus"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".m4v", ".mpg", ".mpeg"}
_BINARY_EXTS = {".exe", ".dll", ".so", ".dylib", ".bin", ".dat", ".db", ".sqlite",
                ".sqlite3", ".pyc", ".pdb", ".iso", ".img", ".parquet", ".h5", ".hdf5"}


def _human_size(n):
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    return f"{n / 1024 ** 3:.1f} GB"


def _pdf_context(path, name, size_txt, max_chars):
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except Exception as e:
        return f"[attachment: {name} ({size_txt}) \u2014 unreadable PDF: {e}]"
    counts = [int(m) for m in re.findall(rb"/Count\s+(\d+)", raw)]
    page_txt = f"{max(counts)} pages" if counts else "page count unknown"
    meta_bits = []
    for key in (b"Title", b"Author", b"Subject", b"Creator", b"Producer"):
        m = re.search(key + rb"\s*\(([^()\\]*(?:\\.[^()\\]*)*)\)", raw[:200000])
        if m:
            val = m.group(1)[:120].decode("latin-1", "replace")
            meta_bits.append(f"{key.decode()}: {val}")
    meta_txt = ("; ".join(meta_bits) + ".") if meta_bits else "no document metadata."
    # Best-effort text-layer extraction: decompress every object stream
    # and pull out literal text shown via Tj/TJ operators. Stdlib-only,
    # so genuinely imperfect — but real text, never fabricated.
    texts = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.DOTALL):
        data = m.group(1).lstrip(b"\r\n")
        for payload in (data,):
            try:
                payload = zlib.decompress(data)
            except Exception:
                pass
            texts += re.findall(rb"\(((?:[^()\\]|\\.)*)\)\s*Tj", payload)
    plain = " ".join(
        t.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
        .decode("latin-1", "replace") for t in texts)
    plain = re.sub(r"\s+", " ", plain).strip()
    if plain:
        if len(plain) > max_chars:
            plain = plain[:max_chars] + " \u2026[truncated]"
        body = f"[attachment: {name} ({size_txt}) \u2014 PDF, {page_txt}; {meta_txt}]\n{plain}"
    else:
        body = (f"[attachment: {name} ({size_txt}) \u2014 PDF, {page_txt}; {meta_txt} "
                f"No extractable text layer (scanned image or glyph-encoded PDF).]")
    return body


def _zip_context(path, name, size_txt):
    import zipfile
    try:
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            files = [i for i in infos if not i.is_dir()]
            dirs = [i for i in infos if i.is_dir()]
            total = sum(i.file_size for i in files)
            listing = "\n".join(i.filename for i in files[:40])
            more = f"\n\u2026 and {len(files) - 40} more files" if len(files) > 40 else ""
            return (f"[attachment: {name} ({size_txt}) \u2014 zip archive: {len(files)} files, "
                    f"{len(dirs)} folders, {_human_size(total)} uncompressed]\n"
                    f"{listing}{more}" if files else
                    f"[attachment: {name} ({size_txt}) \u2014 zip archive, empty.]")
    except Exception as e:
        return f"[attachment: {name} ({size_txt}) \u2014 not a readable zip archive: {e}]"


def _tar_context(path, name, size_txt):
    import tarfile
    try:
        with tarfile.open(path) as tf:
            members = tf.getmembers()
            files = [m for m in members if m.isfile()]
            listing = "\n".join(m.name for m in files[:40])
            more = f"\n\u2026 and {len(files) - 40} more files" if len(files) > 40 else ""
            return (f"[attachment: {name} ({size_txt}) \u2014 tar archive: {len(files)} files]\n"
                    f"{listing}{more}" if files else
                    f"[attachment: {name} ({size_txt}) \u2014 tar archive, empty.]")
    except Exception as e:
        return f"[attachment: {name} ({size_txt}) \u2014 not a readable tar archive: {e}]"


def _csv_context(path, name, size_txt, max_chars):
    import csv
    header, sample, total = None, [], 0
    capped = False
    try:
        with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
            for i, row in enumerate(csv.reader(f)):
                if i == 0:
                    header = row
                elif len(sample) < 5:
                    sample.append(row)
                total += 1
                if total >= 5000:
                    capped = True
                    break
    except Exception as e:
        return f"[attachment: {name} ({size_txt}) \u2014 could not parse CSV: {e}]"
    cols = f"{len(header)} columns" if header else "0 columns"
    total_txt = f"{total} rows" + (" (capped at 5000)" if capped else "")
    lines = [f"[attachment: {name} ({size_txt}) \u2014 CSV, {cols}, {total_txt}]"]
    if header:
        lines.append("header: " + " | ".join(header))
    if sample:
        lines.append("first rows:")
        lines += ["  " + " | ".join(row) for row in sample]
    body = "\n".join(lines)
    return body[:max_chars] + (" \u2026[truncated]" if len(body) > max_chars else "")


def _image_context(path, name, size_txt):
    note = (f"[Attached image: {path} \u2014 not yet included in streamed "
            f"replies; vision-capable providers analyze it via the "
            f"query_ai_with_image path instead]")
    try:
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
            fmt = (im.format or "").upper()
        return (f"[Attached image: {name} ({size_txt}, {w}x{h} {fmt}) \u2014 "
                f"not yet included in streamed replies; vision-capable "
                f"providers analyze it via the query_ai_with_image path instead]")
    except Exception:
        return note


def attachment_context_for(path, max_chars=TEXT_FILE_MAX_CHARS):
    """v0.7.6 Patch 1, Fix 7: the complete AI-side context block for one
    attached file — real content or real metadata per file type, always
    honest about what couldn't be extracted (no fabricated analysis).
    Images keep the existing vision path; text-like files (md, code,
    data, config) get their actual content; CSV/zip/tar/PDF get genuine
    structure; audio/video report what's knowable in this environment.
    """
    if not os.path.isfile(path):
        return f"[attachment not found: {path}]"
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    try:
        size = os.path.getsize(path)
    except Exception:
        size = 0
    size_txt = _human_size(size)

    if is_image_file(path):
        return _image_context(path, name, size_txt)
    if ext == ".pdf":
        return _pdf_context(path, name, size_txt, max_chars)
    if ext == ".zip":
        return _zip_context(path, name, size_txt)
    if ext in {".tar", ".gz", ".bz2", ".tgz"}:
        return _tar_context(path, name, size_txt)
    if ext in {".rar", ".7z"}:
        return (f"[attachment: {name} ({size_txt}) \u2014 {ext} archive; "
                f"no stdlib reader exists here, extract it first and attach "
                f"the contents instead]")
    if ext == ".csv":
        return _csv_context(path, name, size_txt, max_chars)
    if ext in AUDIO_EXTS:
        return (f"[attachment: {name} ({size_txt}) \u2014 audio file; duration "
                f"and tags would need the 'mutagen' package, which isn't "
                f"installed in this environment]")
    if ext in VIDEO_EXTS:
        return (f"[attachment: {name} ({size_txt}) \u2014 video file; duration "
                f"and codec info would need the 'mutagen' package, which "
                f"isn't installed in this environment]")
    if ext in _BINARY_EXTS:
        return f"[attachment: {name} ({size_txt}) \u2014 binary {ext} file, content not readable as text]"

    content, truncated = read_text_file_for_context(path)
    if content is None:
        return f"[attachment: {name} ({size_txt}) \u2014 could not be read as text]"
    head = (f"[attachment: {name} ({size_txt})"
            + (" \u2014 truncated to first chars]" if truncated else "]"))
    return head + "\n" + content


def encode_image_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _guess_image_mime(path):
    ext = os.path.splitext(str(path))[1].lower().lstrip(".")
    return {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp"}.get(ext, "image/png")


def query_ai_with_image(prompt, image_path,
                         system_prompt=("You are CAT AI. Describe and analyze the attached image "
                                        "precisely.\n\n" + identity.IDENTITY_BLOCK)):
    """Same idea as query_ai but attaches one local image, for providers whose
    API actually supports vision here (OpenAI-style, Anthropic, Gemini).

    v0.7.9.0 (requirement #19 — multimodal fallback): the image is
    normalized through the vision pipeline first; if the ACTIVE model
    can't receive native images but another CONFIGURED model can, the
    request is rerouted there instead of replying 'model can't see this'.
    Only when no vision-capable model exists at all is that reported,
    clearly and honestly."""
    if not _HAS_REQUESTS:
        return "The 'requests' library is required for AI features. Please run: pip install requests"

    try:
        from . import vision as _vision
        mime, b64 = _vision.encode_for_model(image_path, prompt)[:2]
    except Exception as e:
        return f"Could not read image '{image_path}': {e}"

    config = load_config()
    provider = config.get("provider")
    if not provider:
        return "AI not configured. Run /ai, /agent, or /model to configure your provider first."

    info = PROVIDERS.get(provider)
    api_style = info["api_style"] if info else "openai"
    used_config = config
    if api_style not in ("openai", "anthropic", "gemini"):
        # Primary can't take native images — look for a configured one that can.
        try:
            from . import model_router as _mr
            vcfg, _caps = _mr.find_vision_capable(config)
        except Exception:
            vcfg = None
        if vcfg is None:
            return ("No vision-capable model is currently configured, so the "
                    f"image couldn't be analyzed visually ({provider} has no "
                    "native vision transport here). Configure one via /model.")
        used_config = vcfg
        info = PROVIDERS.get(used_config.get("provider"), {})
        api_style = info["api_style"] if info else "openai"

    if provider == "ollama":
        base_url = config.get("ollama_url") or (info["base_url"] if info else "http://localhost:11434")
    else:
        base_url = used_config.get("base_url") or used_config.get("api_url") or (info["base_url"] if info else "")
    base_url = base_url.rstrip("/")
    api_key = used_config.get("api_key", "")
    model = used_config.get("model") or (info["default_model"] if info else "gpt-4o-mini")
    extra_headers = info["extra_headers"] if info else {}

    try:
        if api_style == "openai":
            url = f"{base_url}/chat/completions"
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            headers.update(extra_headers)
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ]},
                ],
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            _raise_for_status(resp)
            data = resp.json()
            content = data['choices'][0]['message']['content']
            _track_usage_from_data("openai", data, prompt, content)
            return content

        elif api_style == "anthropic":
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01",
                       "content-type": "application/json"}
            headers.update(extra_headers)
            payload = {
                "model": model, "max_tokens": 1024, "system": system_prompt,
                "messages": [{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                    {"type": "text", "text": prompt},
                ]}],
            }
            resp = requests.post(f"{base_url}/messages", headers=headers, json=payload, timeout=60)
            _raise_for_status(resp)
            data = resp.json()
            content = data['content'][0]['text']
            _track_usage_from_data("anthropic", data, prompt, content)
            return content

        elif api_style == "gemini":
            url = f"{base_url}/models/{model}:generateContent?key={api_key}"
            payload = {
                "contents": [{"role": "user", "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime, "data": b64}},
                ]}],
                "systemInstruction": {"parts": [{"text": system_prompt}]},
            }
            resp = requests.post(url, json=payload, timeout=60)
            _raise_for_status(resp)
            data = resp.json()
            content = data['candidates'][0]['content']['parts'][0]['text']
            _track_usage_from_data("gemini", data, prompt, content)
            return content

    except requests.exceptions.ConnectionError:
        return "Could not reach the AI server for image analysis. Check your internet/API URL."
    except requests.exceptions.Timeout:
        return "The image analysis request timed out. Try again, or use a faster model."
    except Exception as e:
        return f"Error analyzing image: {e}"
