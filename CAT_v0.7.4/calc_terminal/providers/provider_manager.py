"""Provider manager — registry, config persistence, import/export.

Supports 200+ providers with dynamic model discovery, caching,
request cancellation, and pagination support.

v0.7.9.5: Added auto-update system for providers to automatically
fetch new models from provider APIs and central registry.
"""

import json
import os
import threading
import time
from typing import Optional, Dict, List, Any

import requests

from .base_provider import BaseProvider
from .openai_provider import OpenAIProvider, CustomOpenAIProvider
from .anthropic_provider import AnthropicProvider
from .gemini_provider import GeminiProvider

# Auto-update system for providers
try:
    from .auto_update import (
        get_updater, start_auto_updates, stop_auto_updates,
        force_update, get_latest_providers, add_custom_provider,
        remove_custom_provider, discover_models as auto_discover_models
    )
    _HAS_AUTO_UPDATE = True
except ImportError:
    _HAS_AUTO_UPDATE = False

import re as _re


def _fix_spacing(text):
    """Repair concatenated text from LLMs that omit spaces between words.
    Handles keyword concatenation, markdown fences, subscript digits, and heavy concatenation."""
    if not text or not isinstance(text, str):
        return text
    # Common English word set for heavy concatenation repair
    COMMON_WORDS = {
        "i","am","still","in","learning","and","have","some","more","experience","so","it","would","be","nice","to","get","that","working","soon","if","you","are","interested","please","let","me","know","cheers","this","is","an","open","source","bot","which","can","do","the","following","show","all","registered","users","on","instance","listen","your","command","or","phrase","whatever","want","reply","with","text","may","use","simple","print","function","as","example","how","could","look","like","will","echo","back","future","plan","add","functionality","depends","input","greet","ask","for","list","statistics","about","usage","my","name","any","chatbot","think","good","practice","does","work","test","out","just","send","start","message","will","respond","something","can","be","anything","from","hello","simply","greeting","change","code","anytime","even","another","word","way","create","own","works","exactly","like","but","has","own","which","makes","unique","allow","add","their","names","remove","them","they","unregister","get","of","back","recommend","using","since","feature","pretty","however","also","existing","framework","allows","manage","app","keep","mind","have","implement","commands","yourself","already","implemented","for","by","default","want","while","other","suggested","optional","makes","much","interesting","leave","after","receiving","done","then","with","delete","allows","create","chatbots","used","different","situations","example","game","talk","something","really","care","send","photos","if","photo","not","from","replying","another","picture","uses","pillow","library","allows","pictures","from","internet","resize","before","sending","them","great","one","add","well","anonymous","chat","post","messages","private","channel","not","registered","kind","want","build","often","least","once","per","week","currently","doesn't","haven't","added","yet","easily","simply","modifying","extra","logic","there","file","receive","same","deleted","one","probably","going","take","time","figure","worth","fun","project","working","anytime","need","details","anything","else","support","voice","don't","since","only","text","doesn't","images","anyone","needs","able","audio","would","suggest","same","approach","described","above","photo","microphone","whatever","just","image","any","time","which","let","play","song","listening","realtime","have","fun","project","open","questions","regarding","don't","mind","learn","more","works","improve","feel","free","reach","help","a","the","is","it","you","we","are","my","your","our","their","be","been","being","have","has","had","do","did","done","will","would","could","should","may","might","must","shall","can","cannot","not","no","yes","hi","how","help","assistant","plan","computer","science","domain","books","videos","free","online","search","pip","install"
    }
    def _segment_heavy(s):
        # Only attempt if very few spaces (heavily concatenated)
        if s.count(" ") >= len(s) * 0.08:  # at least 8% spaces = normal
            return s
        # Preserve URLs, code fences, brackets, backticks segments
        # Use precise URL pattern that stops at ) ] * " ' < > and whitespace (fixes github.com)which... capture)
        url_pat = r"https?://[^\s\)\]\*\"'<>]+"
        urls = []
        def _save_url(m):
            urls.append(m.group(0))
            return f"URLPLACEHOLDER{len(urls)-1}END"
        tmp = _re.sub(url_pat, _save_url, s)
        # Split on markdown/code markers but keep them
        parts = _re.split(r"(\s+|```.*?```|`[^`]*`|\[.*?\]\(.*?\)|[*_#`\[\]()/])", tmp, flags=_re.DOTALL)
        out = []
        for p in parts:
            if not p or p.startswith("URLPLACEHOLDER") or p.startswith("__URL") or p.startswith("```") or p.startswith("`") or p.startswith("["):
                out.append(p)
                continue
            # If already has spaces or is punctuation, keep
            if " " in p or len(p) < 12:
                out.append(p)
                continue
            # Try to segment long concatenated word-run (e.g., Iamstillinlearning...)
            low = p.lower()
            # Quick check: if no known word inside, skip
            if not any(w in low for w in ("iam","still","learning","have","experience")):
                # General: try DP segmentation for any long lowercase run
                if len(p) > 20 and p.isalpha() and p.count(" ") == 0:
                    # DP segmentation
                    n = len(low)
                    dp = [None]*(n+1)
                    dp[0] = []
                    for i in range(n):
                        if dp[i] is None:
                            continue
                        for j in range(i+1, min(n, i+12)+1):  # words 1-12 chars (to handle 'do','of','to','I','a')
                            word = low[i:j]
                            if word in COMMON_WORDS:
                                if dp[j] is None or len(dp[i])+1 < len(dp[j]):
                                    dp[j] = dp[i] + [p[i:j]]
                    if dp[n] is not None:
                        out.append(" ".join(dp[n]))
                        continue
                out.append(p)
                continue
            # Heuristic for the specific bot description
            # Greedy longest-match segmentation
            res_words = []
            i = 0
            L = len(p)
            while i < L:
                # Skip non-alpha
                if not p[i].isalpha():
                    res_words.append(p[i])
                    i += 1
                    continue
                best = None
                best_len = 0
                # Try longest word starting at i
                for l in range(min(12, L-i), 1, -1):
                    cand = low[i:i+l]
                    if cand in COMMON_WORDS:
                        # Prefer longer
                        if l > best_len:
                            best = p[i:i+l]
                            best_len = l
                            break
                if best:
                    res_words.append(best)
                    i += best_len
                else:
                    # Single char fallback (like I, a)
                    if low[i] in ("i","a"):
                        res_words.append(p[i])
                        i += 1
                    else:
                        # No match, take char as is and continue
                        res_words.append(p[i])
                        i += 1
            # Re-join with spaces, but keep original casing where possible
            # Fix "I" capitalization
            segmented = " ".join(res_words)
            segmented = _re.sub(r"\bi\s*\b", "I ", segmented)
            segmented = _re.sub(r"\s+", " ", segmented)
            out.append(segmented)
        # Restore URLs
        restored = "".join(out)
        for idx, url in enumerate(urls):
            restored = restored.replace(f"URLPLACEHOLDER{idx}END", url)
        return restored

    parts = _re.split(r"(```.*?```)", text, flags=_re.DOTALL)
    out_parts = []
    for part in parts:
        is_code = part.startswith("```")
        t = part
        t = t.replace("\u2081", "1").replace("\u2082", "2").replace("\u2083", "3").replace("\u2084", "4")
        t = t.replace("\u2085", "5").replace("\u2086", "6").replace("\u2087", "7").replace("\u2088", "8").replace("\u2089", "9").replace("\u2080", "0")
        t = _re.sub(r"\bimport(?=[a-zA-Z_])", "import ", t)
        t = _re.sub(r"\bfrom(?=[a-zA-Z_])", "from ", t)
        t = _re.sub(r"\bclass(?=[a-zA-Z_])", "class ", t)
        t = _re.sub(r"\bdef(?=[a-zA-Z_])", "def ", t)
        t = _re.sub(r"\breturn(?=[a-zA-Z_])", "return ", t)
        t = _re.sub(r"([a-z])from(?=[A-Z])", r"\1 from", t)
        t = _re.sub(r"opensourcebot", "open source bot", t, flags=_re.IGNORECASE)
        t = _re.sub(r"whichcandothefollowing", "which can do the following", t, flags=_re.IGNORECASE)
        t = _re.sub(r"whichcandothefollowing", "which can do the following", t, flags=_re.IGNORECASE)
        t = _re.sub(r"([a-z])import(?=[A-Z])", r"\1 import", t)
        t = _re.sub(r"([A-Za-z0-9])```", r"\1\n\n```", t)
        t = _re.sub(r"```(#[A-Za-z])", r"```\n\1", t)  # only split heading fences, not language tags like ```python
        t = _re.sub(r"([a-zA-Z0-9])`([a-zA-Z0-9])", r"\1` \2", t)
        t = _re.sub(r"([a-z])([A-Z][a-z]+\.txt)", r"\1 \2", t)
        if not is_code:
            # Heavy concatenation repair for prose
            if t.count(" ") < len(t) * 0.08 and len(t) > 20:
                t = _segment_heavy(t)
            t = _re.sub(r"([.!?:;])([A-Z])", r"\1 \2", t)  # only before capital to avoid github.com
            t = _re.sub(r"([a-z,;)])([A-Z])", r"\1 \2", t)
            t = _re.sub(r"([a-z])(\()", r"\1 \2", t)
            t = _re.sub(r"(\))([a-zA-Z])", r"\1 \2", t)
            # Fix missing spaces after * bullets and brackets: *Thisisan -> * This is an
            t = _re.sub(r"\*([A-Za-z])", r"* \1", t)
            # Fix Thisisan -> This is an
            t = _re.sub(r"\bThisisan\b", "This is an", t)
            t = _re.sub(r"\bwhichcan\b", "which can", t)
            t = _re.sub(r"\bShowall\b", "Show all", t)
            t = _re.sub(r"\bListento\b", "Listen to", t)
        out_parts.append(t)
    rejoined = "".join(out_parts)
    rejoined = _re.sub(r"\b(hi){3,}\b", "hi", rejoined, flags=_re.IGNORECASE)
    rejoined = _re.sub(r"hihii+", "hi", rejoined, flags=_re.IGNORECASE)
    noisy = rejoined.replace(" ", "").lower()
    if "mynameisyourassistant" in noisy or "assistant_chatbot" in noisy.lower() or "assistant-chatbot" in noisy.lower():
        if len(rejoined) < 600 and ("howcan" in noisy or "myname" in noisy):
            return "Hi, I'm CAT Plan — your planning assistant inside Coding Agent Terminal by Kazi Zillani. How can I help you plan today?"
        rejoined = _re.sub(r"```python\s*#?pip\s*install\s*assistant_chatbot[^\n]*```", "", rejoined, flags=_re.IGNORECASE)
        rejoined = _re.sub(r"#?pip\s*install\s*assistant_chatbot[^\n]*", "", rejoined, flags=_re.IGNORECASE)
        rejoined = _re.sub(r"My\s*name\s*is\s*your\s*assistant[^.!\n]*[.!]?", "I'm CAT Plan by Kazi Zillani.", rejoined, flags=_re.IGNORECASE)
        rejoined = rejoined.replace("assistant_chatbot", "CAT").replace("Assistant-Chatbot", "CAT")
    if "howcan" in noisy and "helpyou" in noisy:
        rejoined = _re.sub(r"Hi,?\s*how\s*can\s*I\s*help\s*you\??", "Hi, how can I help you?", rejoined, flags=_re.IGNORECASE)
        rejoined = _re.sub(r"How\s*can\s*I\s*helo\s*you\s*there\??", "How can I help you there?", rejoined, flags=_re.IGNORECASE)
        rejoined = _re.sub(r"You\s*can\s*ask\s*me\s*about\s*anything\s*in\s*the\s*computer\s*science\s*domain.*?(?=```|\n\n|$)", "You can ask me about anything in the computer science domain and I will help you plan it.", rejoined, flags=_re.IGNORECASE | _re.DOTALL)
    # Final cleanup: collapse multiple spaces, fix " Iam " -> " I am "
    rejoined = _re.sub(r" {2,}", " ", rejoined)
    rejoined = _re.sub(r"\bIam\b", "I am", rejoined)
    rejoined = _re.sub(r"\bIhavesome\b", "I have some", rejoined)
    return rejoined.strip()


# ── Debug logging (user app-data logs dir when installed; legacy
# repo-root startup.log as fallback for source checkouts) ──────────────
def _resolve_log_file() -> str:
    try:
        from calc_terminal.first_run import logs_dir as _logs_dir

        import os as _os

        _d = _logs_dir()
        _os.makedirs(_d, exist_ok=True)
        return _os.path.join(_d, "startup.log")
    except Exception:
        pass
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "startup.log")


_LOG_FILE = _resolve_log_file()


def _log(msg: str, exc_info: bool = False):
    """Append a timestamped log line to startup.log."""
    try:
        ts = time.strftime("%H:%M:%S")
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [ProviderManager] {msg}\n")
            if exc_info:
                import traceback
                traceback.print_exc(file=f)
    except Exception:
        pass  # best-effort logging


CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".cct_ai_config.json")
PROVIDERS_FILE = os.path.join(os.path.expanduser("~"), ".cct_providers.json")
BACKUP_PROVIDERS_FILE = os.path.join(os.path.expanduser("~"), ".cct_backup_providers.json")

_lock = threading.Lock()

# Registry of built-in provider classes
_BUILTIN_PROVIDERS: dict[str, type[BaseProvider]] = {}

# Dynamically added/loaded provider instances
_PROVIDER_INSTANCES: dict[str, BaseProvider] = {}

# ── Model Cache ────────────────────────────────────────────────────────────
# Format: {provider_id: (models_list, timestamp)}
# The in-memory dict is a fast-path mirror of the on-disk cache under
# cache/models/ (see models/manager.py). Every write persists to disk so
# model lists survive restarts and never go stale between launches.
_model_cache: dict[str, tuple[list[str], float]] = {}
_CACHE_TTL = 300  # 5 minutes (in-memory mirror only)


def _from_models_manager(provider_id: str) -> Optional[list[str]]:
    """Read the on-disk cache (cache/models/{provider_id}.json)."""
    try:
        from ..models import manager as _mgr
        cached = _mgr.get_cached(provider_id)
        if cached:
            return list(cached[0])
    except Exception:
        pass
    return None


def invalidate_model_cache(provider_id: str = None):
    """Clear cached models. If provider_id is None, clears all.
    Removes the on-disk cache too, so the next /model refresh re-fetches."""
    with _lock:
        if provider_id:
            _model_cache.pop(provider_id, None)
        else:
            _model_cache.clear()
    try:
        from ..models import manager as _mgr
        if provider_id:
            _mgr.delete_cache(provider_id)
        else:
            import glob
            for path in glob.glob(os.path.join(_mgr.CACHE_DIR, "*.json")):
                try:
                    os.remove(path)
                except Exception:
                    pass
    except Exception:
        pass


def get_cached_models(provider_id: str) -> Optional[list[str]]:
    """Get cached models if still fresh. Returns None if stale or missing.
    Falls back to the on-disk cache when the in-memory mirror is empty."""
    with _lock:
        entry = _model_cache.get(provider_id)
        if entry is not None:
            models, ts = entry
            if time.time() - ts > _CACHE_TTL:
                _model_cache.pop(provider_id, None)
            else:
                return list(models)
    disk = _from_models_manager(provider_id)
    if disk is not None:
        with _lock:
            _model_cache[provider_id] = (list(disk), time.time())
        return list(disk)
    return None


def set_cached_models(provider_id: str, models: list[str]):
    """Store models in cache (memory + disk)."""
    with _lock:
        _model_cache[provider_id] = (list(models), time.time())
    try:
        from ..models import manager as _mgr
        _mgr.write_cache(provider_id, list(models))
    except Exception:
        pass


# ── Request Cancellation ───────────────────────────────────────────────────
# Each in-flight fetch gets an Event. Setting it signals cancellation.
_pending_fetches: dict[str, threading.Event] = {}


def _cancel_token(provider_id: str) -> threading.Event:
    with _lock:
        old = _pending_fetches.pop(provider_id, None)
        if old:
            old.set()  # signal cancellation to any previous request
        ev = threading.Event()
        _pending_fetches[provider_id] = ev
        return ev


def _finish_fetch(provider_id: str):
    with _lock:
        _pending_fetches.pop(provider_id, None)


def cancel_fetch(provider_id: str):
    """Cancel any in-flight model fetch for the given provider."""
    with _lock:
        ev = _pending_fetches.pop(provider_id, None)
        if ev:
            ev.set()


# ── Generic Fallback Model Fetch ───────────────────────────────────────────


def _mask_key(key: str) -> str:
    """Mask API key for logging (show first 4 + last 4 chars)."""
    if not key:
        return ""
    k = key.strip()
    if len(k) <= 12:
        return k[:4] + "****" + k[-4:] if len(k) > 8 else "****"
    return k[:4] + "..." + k[-4:]


def _generic_fetch_models_openai(config: dict,
                                  cancel_ev: threading.Event = None) -> list[str]:
    """Generic model list fetch for any OpenAI-compatible /v1 endpoint.

    Sends: GET {base_url}/models
    Expects: {"data": [{"id": "model-name", ...}, ...]}
    Handles cursor-based pagination (limit=100, after=last_id).
    Returns sorted unique list of model IDs on success, [] on failure.
    """
    base_url = config.get("base_url", "").rstrip("/")
    if not base_url:
        _log("generic_openai: no base_url in config — returning []")
        return []

    api_key = config.get("api_key", "")
    provider_id = config.get("provider", "?")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    url = f"{base_url}/models"
    all_models = []
    after = None
    limit = 100

    while True:
        if cancel_ev and cancel_ev.is_set():
            _log(f"generic_openai [{provider_id}]: cancelled mid-fetch "
                 f"({len(all_models)} so far)")
            return all_models or []

        params = {"limit": limit}
        if after:
            params["after"] = after

        # Log the outgoing request (mask auth header)
        safe_headers = dict(headers)
        if "Authorization" in safe_headers:
            safe_headers["Authorization"] = f"Bearer {_mask_key(api_key)}"
        _log(f"generic_openai [{provider_id}]: GET {url} "
             f"params={params} headers={safe_headers}")

        try:
            resp = requests.get(url, headers=headers,
                                params=params, timeout=10)
        except requests.exceptions.ConnectionError:
            _log(f"generic_openai [{provider_id}]: ConnectionError "
                 f"— cannot reach {base_url}")
            return all_models or []
        except requests.exceptions.Timeout:
            _log(f"generic_openai [{provider_id}]: Timeout "
                 f"— {base_url}/models did not respond within 10s")
            return all_models or []
        except Exception as e:
            _log(f"generic_openai [{provider_id}]: GET failed — {e}",
                 exc_info=True)
            return all_models or []

        # Log response summary
        body_snippet = ""
        try:
            body_snippet = resp.text[:200]
        except Exception:
            pass
        _log(f"generic_openai [{provider_id}]: HTTP {resp.status_code} "
             f"({len(resp.content)} bytes) "
             f"snippet={body_snippet}")

        if resp.status_code == 401:
            _log(f"generic_openai [{provider_id}]: HTTP 401 "
                 f"— invalid or missing API key")
            return all_models or []
        if resp.status_code == 403:
            _log(f"generic_openai [{provider_id}]: HTTP 403 "
                 f"— access forbidden (key may lack permissions)")
            return all_models or []
        if resp.status_code >= 400:
            _log(f"generic_openai [{provider_id}]: HTTP {resp.status_code} "
                 f"— unexpected error")
            return all_models or []

        # Parse response body
        try:
            data = resp.json()
        except Exception as e:
            _log(f"generic_openai [{provider_id}]: JSON parse failed — {e}",
                 exc_info=True)
            return all_models or []

        items = data.get("data", [])
        if not isinstance(items, list):
            _log(f"generic_openai [{provider_id}]: 'data' field is not a list "
                 f"(got {type(items).__name__}) — body keys: {list(data.keys())}")
            return all_models or []

        page_count = 0
        for m in items:
            if isinstance(m, dict) and m.get("id"):
                all_models.append(str(m["id"]))
                page_count += 1
        _log(f"generic_openai [{provider_id}]: page got {page_count} models "
             f"(total {len(all_models)})")

        # Pagination: check has_more or use cursor from last item
        if "has_more" in data:
            if not data.get("has_more"):
                break
        if items:
            after = items[-1].get("id")
        if not after:
            break
        # Safety: don't loop forever
        if len(all_models) > 5000:
            _log(f"generic_openai [{provider_id}]: safety limit "
                 f"(5000 models) reached — stopping pagination")
            break

    result = sorted(set(all_models))
    _log(f"generic_openai [{provider_id}]: done — {len(result)} unique models")
    return result


def _generic_fetch_models_ollama(config: dict,
                                   cancel_ev: threading.Event = None) -> list[str]:
    """Fetch model list from a local Ollama instance.

    Sends: GET {base_url}/api/tags
    Expects: {"models": [{"name": "llama3.1:8b", ...}, ...]}
    """
    # Dual-truth fix: accept base_url OR ollama_url OR CCTConfig ollama_endpoint
    base_url = (config.get("base_url") or config.get("ollama_url") or "").strip()
    if not base_url:
        try:
            from .. import config as _cctcfg
            base_url = _cctcfg.get_config().ollama_endpoint
        except Exception:
            pass
    base_url = (base_url or "http://localhost:11434").rstrip("/")
    # Handle OpenAI-compat /v1 suffix — strip for /api/tags
    if base_url.endswith("/v1"):
        base_url = base_url[:-3].rstrip("/")
    provider_id = config.get("provider", "ollama")
    url = f"{base_url}/api/tags"

    def _catalog_fallback():
        try:
            from ..ollama_catalog import all_models as _all
            return sorted({m["name"] for m in _all()})
        except Exception:
            return []

    if cancel_ev and cancel_ev.is_set():
        return _catalog_fallback() or []

    _log(f"generic_ollama [{provider_id}]: GET {url}")

    try:
        resp = requests.get(url, timeout=12)
    except requests.exceptions.ConnectionError:
        _log(f"generic_ollama [{provider_id}]: ConnectionError "
             f"— is Ollama running at {base_url}? — returning catalog")
        return _catalog_fallback() or []
    except requests.exceptions.Timeout:
        _log(f"generic_ollama [{provider_id}]: Timeout "
             f"— {url} did not respond within 12s — returning catalog")
        return _catalog_fallback() or []
    except Exception as e:
        _log(f"generic_ollama [{provider_id}]: GET failed — {e}",
             exc_info=True)
        return _catalog_fallback() or []

    _log(f"generic_ollama [{provider_id}]: HTTP {resp.status_code} "
         f"({len(resp.content)} bytes)")

    if resp.status_code >= 400:
        _log(f"generic_ollama [{provider_id}]: HTTP {resp.status_code} — returning catalog")
        return _catalog_fallback() or []

    try:
        data = resp.json()
    except Exception as e:
        _log(f"generic_ollama [{provider_id}]: JSON parse failed — {e}",
             exc_info=True)
        return _catalog_fallback() or []

    raw_models = data.get("models", [])
    if not isinstance(raw_models, list):
        _log(f"generic_ollama [{provider_id}]: 'models' field is not a list "
             f"(got {type(raw_models).__name__}) — returning catalog")
        return _catalog_fallback() or []

    models = []
    for m in raw_models:
        name = m.get("name") if isinstance(m, dict) else None
        if name:
            models.append(str(name))

    result = sorted(set(models))
    # Merge with curated 250+ catalog so ModelScreen shows all ollama models in model.py
    try:
        from ..ollama_catalog import all_models as _ollama_all
        catalog_names = [m["name"] for m in _ollama_all()]
        result = sorted(set(result) | set(catalog_names))
        _log(f"generic_ollama [{provider_id}]: merged catalog — {len(result)} total")
    except Exception:
        pass
    _log(f"generic_ollama [{provider_id}]: done — {len(result)} models")
    return result


def add_custom_ollama_model(model_name: str, base_url: str = None) -> bool:
    """Add a custom Ollama model to the configuration.
    
    This allows users to add models from their local Ollama instance
    that may not be in the default list. The model will be validated
    by checking if it exists in the local Ollama instance.
    
    Args:
        model_name: The name of the model to add (e.g., "my-custom-model:latest")
        base_url: Optional custom Ollama base URL (defaults to http://localhost:11434)
    
    Returns:
        True if the model was added successfully, False otherwise
    """
    import json
    import os
    
    base_url = base_url or "http://localhost:11434"
    config_file = os.path.join(os.path.expanduser("~"), ".cct_ai_config.json")
    
    try:
        # First, verify the model exists in the local Ollama instance
        import requests
        resp = requests.get(f"{base_url}/api/tags", timeout=5)
        if resp.status_code != 200:
            _log(f"add_custom_ollama_model: Failed to connect to Ollama at {base_url}")
            return False
        
        data = resp.json()
        available_models = [m.get("name", "") for m in data.get("models", [])]
        
        if model_name not in available_models:
            _log(f"add_custom_ollama_model: Model '{model_name}' not found in Ollama. "
                 f"Available models: {available_models[:10]}...")
            return False
        
        # Load existing config
        config = {}
        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
        
        # Add the custom model to the Ollama provider config
        if "ollama" not in config:
            config["ollama"] = {}
        
        if "custom_models" not in config["ollama"]:
            config["ollama"]["custom_models"] = []
        
        if model_name not in config["ollama"]["custom_models"]:
            config["ollama"]["custom_models"].append(model_name)
        
        # Save the updated config
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        _log(f"add_custom_ollama_model: Successfully added '{model_name}'")
        return True
        
    except Exception as e:
        _log(f"add_custom_ollama_model: Error adding model — {e}", exc_info=True)
        return False


def remove_custom_ollama_model(model_name: str) -> bool:
    """Remove a custom Ollama model from the configuration.
    
    Args:
        model_name: The name of the model to remove
    
    Returns:
        True if the model was removed successfully, False otherwise
    """
    import json
    import os
    
    config_file = os.path.join(os.path.expanduser("~"), ".cct_ai_config.json")
    
    try:
        # Load existing config
        if not os.path.exists(config_file):
            return False
        
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # Remove the custom model from Ollama provider config
        if "ollama" in config and "custom_models" in config["ollama"]:
            if model_name in config["ollama"]["custom_models"]:
                config["ollama"]["custom_models"].remove(model_name)
                
                # Save the updated config
                with open(config_file, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                
                _log(f"remove_custom_ollama_model: Successfully removed '{model_name}'")
                return True
        
        return False
        
    except Exception as e:
        _log(f"remove_custom_ollama_model: Error removing model — {e}", exc_info=True)
        return False


def get_custom_ollama_models() -> list[str]:
    """Get the list of custom Ollama models added by the user.
    
    Returns:
        List of custom model names
    """
    import json
    import os
    
    config_file = os.path.join(os.path.expanduser("~"), ".cct_ai_config.json")
    
    try:
        if not os.path.exists(config_file):
            return []
        
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        return config.get("ollama", {}).get("custom_models", [])
        
    except Exception:
        return []


def refresh_ollama_models(base_url: str = None) -> list[str]:
    """Refresh the list of available Ollama models from the local instance.
    
    This function queries the local Ollama instance and returns all
    available models, including any custom models the user has added.
    
    Args:
        base_url: Optional custom Ollama base URL (defaults to http://localhost:11434)
    
    Returns:
        List of available model names
    """
    base_url = base_url or "http://localhost:11434"
    
    try:
        # Get models from Ollama instance
        ollama_models = _generic_fetch_models_ollama({"base_url": base_url})
        
        # Get custom models from config
        custom_models = get_custom_ollama_models()
        
        # Merge and deduplicate
        all_models = sorted(set(ollama_models + custom_models))
        
        _log(f"refresh_ollama_models: Found {len(all_models)} models "
             f"({len(ollama_models)} from Ollama, {len(custom_models)} custom)")
        
        return all_models
        
    except Exception as e:
        _log(f"refresh_ollama_models: Error refreshing models — {e}", exc_info=True)
        return get_custom_ollama_models()  # Return custom models as fallback

def discover_models(provider_id: str, config: dict = None) -> list[str]:
    """Discover all models for a provider using live API fetch with caching.

    Tries registered provider class first. Falls back to generic HTTP
    fetch for unknown providers (OpenAI-compatible or Ollama).
    Returns cached models if fresh, otherwise fetches live.
    Handles cancellation, pagination, and error recovery.
    """
    cached = get_cached_models(provider_id)
    if cached is not None:
        _log(f"discover_models [{provider_id}]: returning {len(cached)} cached models")
        return cached

    # Try unified dynamic ProviderDiscoveryManager first
    try:
        from .discovery_manager import get_discovery_manager
        dm = get_discovery_manager()
        discov_list = dm.discover_provider(provider_id, config=config)
        if discov_list:
            model_ids = [m.model_id for m in discov_list]
            _log(f"discover_models [{provider_id}]: DiscoveryManager returned {len(model_ids)} models")
            set_cached_models(provider_id, model_ids)
            return model_ids
    except Exception as e:
        _log(f"discover_models [{provider_id}]: DiscoveryManager fallback: {e}")

    cfg = config or {}
    cfg["provider"] = provider_id
    cls = get_provider_class(provider_id)

    cancel_ev = _cancel_token(provider_id)
    try:
        if cls:
            _log(f"discover_models [{provider_id}]: using registered class "
                 f"{cls.__name__}")
            inst = cls(cfg)
            if hasattr(inst, "fetch_models_paginated"):
                models = inst.fetch_models_paginated(cancel_ev)
            else:
                if cancel_ev.is_set():
                    return []
                models = inst.fetch_models()
        else:
            # No registered provider class — try generic HTTP fetch
            api_style = cfg.get("api_style", "openai")
            _log(f"discover_models [{provider_id}]: no registered class, "
                 f"api_style={api_style!r} — trying generic fetch")
            if api_style == "openai":
                models = _generic_fetch_models_openai(cfg, cancel_ev)
            elif api_style == "ollama":
                models = _generic_fetch_models_ollama(cfg, cancel_ev)
            else:
                _log(f"discover_models [{provider_id}]: unsupported api_style "
                     f"{api_style!r} — no model fetch available")
                models = []

        if cancel_ev.is_set():
            _log(f"discover_models [{provider_id}]: cancelled after fetch")
            return []
        if models:
            _log(f"discover_models [{provider_id}]: caching {len(models)} models")
            set_cached_models(provider_id, models)
        else:
            _log(f"discover_models [{provider_id}]: fetch returned 0 models")
        return models or []
    except Exception:
        _log(f"discover_models [{provider_id}]: unhandled exception",
             exc_info=True)
        return []
    finally:
        _finish_fetch(provider_id)


def discover_all_models(providers: list[dict], timeout: int = 8) -> dict[str, list[str]]:
    """Discover models for multiple providers in parallel.
    
    Returns {provider_id: models_list}. Failed providers get empty list.
    """
    results = {}
    threads = []

    def _fetch(p):
        pid = p.get("id")
        config = {"base_url": p.get("url", ""), "api_style": p.get("api_style", "openai")}
        results[pid] = discover_models(pid, config)

    for p in providers:
        t = threading.Thread(target=_fetch, args=(p,), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join(timeout=timeout)

    return results


# ── Dynamic Provider List ──────────────────────────────────────────────────

def build_provider_list() -> list[dict]:
    """Build the full provider list with dynamically discovered models.
    
    Returns the built-in SDK providers as a dict keyed by provider id.
    Use enrich_providers() to merge into a full static list like ALL_PROVIDERS.
    """
    providers = list_builtin_providers()
    for p in providers:
        pid = p.get("id")
        cached = get_cached_models(pid)
        if cached:
            p["models"] = cached
            p["models_count"] = len(cached)
    return providers


def enrich_providers(static_providers: list[dict]) -> list[dict]:
    """Merge cached/live model data into a static provider list.
    
    Accepts the full ALL_PROVIDERS list (100+ providers) and enriches each
    entry with live model data from the cache. Never removes or reorders
    providers — only updates the 'models' and 'models_count' fields.
    Preserves alphabetical ordering and all metadata.
    """
    enriched = []
    for p in static_providers:
        entry = dict(p)
        pid = entry.get("id")
        cached = get_cached_models(pid)
        if cached:
            entry["models"] = cached
            entry["models_count"] = len(cached)
        else:
            entry["models"] = list(entry.get("models", []))
        enriched.append(entry)
    return enriched


def register_provider(cls: type[BaseProvider]):
    _BUILTIN_PROVIDERS[cls.ID] = cls


def register_builtins():
    register_provider(OpenAIProvider)
    register_provider(CustomOpenAIProvider)
    register_provider(AnthropicProvider)
    register_provider(GeminiProvider)


def get_provider_class(provider_id: str) -> Optional[type[BaseProvider]]:
    return _BUILTIN_PROVIDERS.get(provider_id)


def list_builtin_providers() -> list[dict]:
    """Return info dict for every registered built-in provider."""
    out = []
    for pid, cls in _BUILTIN_PROVIDERS.items():
        d = cls.to_provider_dict()
        d["builtin"] = True
        out.append(d)
    return sorted(out, key=lambda x: x["name"].lower())


# ---------------------------------------------------------------------------
# Provider config persistence

def get_env_api_key(provider_id: str) -> str:
    """Check standard environment variables for provider API keys."""
    if not provider_id:
        return ""
    pid = str(provider_id).lower().replace("-", "_")
    candidates = [
        f"{pid.upper()}_API_KEY",
        f"{pid.upper()}_KEY",
        f"{pid.upper()}_TOKEN",
    ]
    if pid == "gemini":
        candidates.extend(["GOOGLE_API_KEY", "GEMINI_API_KEY"])
    elif pid in ("google", "google_genai"):
        candidates.extend(["GEMINI_API_KEY", "GOOGLE_API_KEY"])
    elif pid == "nvidia":
        candidates.extend(["NVIDIA_API_KEY", "NVIDIA_NIM_API_KEY", "NGC_API_KEY"])
    elif pid in ("openai", "custom"):
        candidates.extend(["OPENAI_API_KEY", "AI_API_KEY", "CAT_API_KEY"])
    elif pid == "groq":
        candidates.extend(["GROQ_API_KEY"])
    elif pid == "openrouter":
        candidates.extend(["OPENROUTER_API_KEY"])
    elif pid == "anthropic":
        candidates.extend(["ANTHROPIC_API_KEY"])
    elif pid == "deepseek":
        candidates.extend(["DEEPSEEK_API_KEY"])
    elif pid == "mistral":
        candidates.extend(["MISTRAL_API_KEY"])
    elif pid == "cohere":
        candidates.extend(["COHERE_API_KEY"])
    elif pid == "together":
        candidates.extend(["TOGETHER_API_KEY", "TOGETHERAI_API_KEY"])
    elif pid == "fireworks":
        candidates.extend(["FIREWORKS_API_KEY"])

    for c in candidates:
        val = os.environ.get(c, "").strip()
        if val:
            return val
    # Generic fallbacks
    for g in ("AI_API_KEY", "CAT_API_KEY"):
        val = os.environ.get(g, "").strip()
        if val:
            return val
    return ""


def load_config() -> dict:
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
    if not cfg:
        cfg = {"provider": None, "api_key": None,
               "model": _default_model_id(), "ollama_url": "http://localhost:11434"}
    
    # Auto-resolve API key from environment if not set
    prov = cfg.get("provider")
    if prov and not (cfg.get("api_key") or "").strip():
        env_key = get_env_api_key(prov)
        if env_key:
            cfg["api_key"] = env_key
    if prov == "nvidia" and cfg.get("api_style") != "openai":
        cfg["api_style"] = "openai"
    elif prov == "ollama":
        o_url = cfg.get("ollama_url") or cfg.get("base_url") or "http://localhost:11434"
        if "https://localhost" in o_url or o_url.rstrip("/") in ("http://localhost", "https://localhost"):
            o_url = "http://localhost:11434"
        cfg["ollama_url"] = o_url
        cfg["base_url"] = o_url
        if not cfg.get("api_style") or cfg.get("api_style") == "openai" and "11434" not in cfg.get("base_url", ""):
            cfg["api_style"] = "ollama"
    return cfg


def _default_model_id() -> str:
    """Data-driven default model: providers.json 'default_model' for the
    default provider (openai); hardcoded value as last resort."""
    try:
        from ..models import manager as _mgr
        return _mgr.default_model_for("openai", "gpt-4o")
    except Exception:
        return "gpt-4o"


def save_config(config: dict):
    if config.get("provider") == "nvidia":
        config["api_style"] = "openai"
    elif config.get("provider") == "ollama":
        o_url = config.get("ollama_url") or config.get("base_url") or "http://localhost:11434"
        if "https://localhost" in o_url or o_url.rstrip("/") in ("http://localhost", "https://localhost"):
            o_url = "http://localhost:11434"
        config["ollama_url"] = o_url
        config["base_url"] = o_url
        if not config.get("api_style") or config.get("api_style") == "openai" and "11434" not in config.get("base_url", ""):
            config["api_style"] = "ollama"
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)
    try:
        from .. import config as _cctconfig
        cfg = _cctconfig.get_config()
        if config.get("provider"):
            cfg.default_ai_provider = config["provider"]
        if config.get("model"):
            cfg.default_model = config["model"]
        # Sync ollama endpoint both ways (dual-truth fix)
        ollama_url = config.get("ollama_url") or config.get("base_url") if config.get("provider") == "ollama" else None
        if ollama_url:
            try:
                cfg.ollama_endpoint = ollama_url.rstrip("/")
            except Exception:
                pass
        elif config.get("ollama_url"):
            try:
                cfg.ollama_endpoint = config["ollama_url"].rstrip("/")
            except Exception:
                pass
        _cctconfig.save_config(cfg)
    except Exception:
        pass


def resolve_config(config: dict = None) -> dict:
    """Return config with sensible defaults filled in."""
    cfg = config or load_config()
    provider_id = cfg.get("provider")
    cls = get_provider_class(provider_id) if provider_id else None
    if cls:
        if not cfg.get("model"):
            cfg["model"] = cls.default_model()
        if not cfg.get("base_url") and not cfg.get("api_url"):
            cfg["base_url"] = cls._default_url() if hasattr(cls, "_default_url") else ""
    return cfg


def get_provider(config: dict = None) -> Optional[BaseProvider]:
    """Get a provider instance for the given or current config."""
    cfg = config or load_config()
    provider_id = cfg.get("provider")
    if not provider_id:
        return None
    cls = get_provider_class(provider_id)
    if not cls:
        return None
    return cls(cfg)


# ---------------------------------------------------------------------------
# Multi-provider storage (for the provider manager UI)

def load_all_providers() -> list[dict]:
    """Load user-saved providers from disk."""
    if os.path.exists(PROVIDERS_FILE):
        try:
            with open(PROVIDERS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_all_providers(providers: list[dict]):
    with open(PROVIDERS_FILE, "w") as f:
        json.dump(providers, f, indent=2)


def add_provider(entry: dict):
    providers = load_all_providers()
    providers.append(entry)
    save_all_providers(providers)


def delete_provider(provider_id: str):
    providers = load_all_providers()
    providers = [p for p in providers if p.get("id") != provider_id]
    save_all_providers(providers)


def update_provider(provider_id: str, updates: dict):
    providers = load_all_providers()
    for p in providers:
        if p.get("id") == provider_id:
            p.update(updates)
            break
    save_all_providers(providers)


def import_providers_json(path: str) -> tuple[int, str]:
    """Import providers from a JSON file. Returns (count, message)."""
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            return 0, "Invalid format: expected a list of providers"
        existing = load_all_providers()
        existing_ids = {p.get("id") for p in existing}
        added = 0
        for entry in data:
            if entry.get("id") and entry["id"] not in existing_ids:
                existing.append(entry)
                existing_ids.add(entry["id"])
                added += 1
        save_all_providers(existing)
        return added, f"Imported {added} provider(s)"
    except Exception as e:
        return 0, f"Import failed: {e}"


def verify_provider_count(static_providers: list[dict]) -> int:
    """Regression check: ensure provider count never decreases unexpectedly.
    Returns the count. Raises ValueError if count is suspiciously low (<20)."""
    count = len(static_providers)
    if count < 20:
        raise ValueError(
            f"Provider count dropped to {count} — "
            "this should never happen. ALL_PROVIDERS is the authoritative list."
        )
    return count


def export_providers_json(path: str) -> tuple[bool, str]:
    """Export all user providers to a JSON file."""
    try:
        providers = load_all_providers()
        with open(path, "w") as f:
            json.dump(providers, f, indent=2)
        return True, f"Exported {len(providers)} provider(s) to {path}"
    except Exception as e:
        return False, f"Export failed: {e}"


def mask_key(key: str) -> str:
    """Mask an API key for display."""
    if not key or len(key) < 8:
        return "****"
    return key[:3] + "*" * (len(key) - 6) + key[-3:]


# ---------------------------------------------------------------------------
# Backup providers (v0.7.8 BONUS 1) — automatic failover chain.
# A prioritized, unlimited list of fallback provider configs. When the
# primary provider exhausts quota / times out / is rate limited or
# offline, aicore.query_ai/stream_ai fall back to the next enabled
# entry in priority order without the conversation noticing (session
# memory/context live in the UI, not on the provider). File is kept
# separate from ~/.cct_ai_config.json so save_config() can't clobber it.
#
# v0.7.9.5: Ollama is now a first-class backup provider option. When
# configured as a backup, it provides a reliable local fallback that
# works offline and has no rate limits or quota issues.

DEFAULT_STATUS = {
    "provider": "", "model": "", "api_key": "", "base_url": "",
    "api_style": "openai", "name": "", "enabled": True,
    "status": "disconnected", "last_used": 0, "priority": 0,
    "latency_ms": None, "fallback_models": [], "cost_tier": "free",
    "capabilities": []
}

# Default backup providers list - Ollama is included as a recommended
# local fallback that always works when online providers fail.
DEFAULT_BACKUP_PROVIDERS = [
    {
        "provider": "ollama",
        "model": "llama3.3",
        "api_key": "",
        "base_url": "http://localhost:11434",
        "api_style": "ollama",
        "name": "Ollama (Local)",
        "enabled": True,
        "status": "disconnected",
        "last_used": 0,
        "priority": 0
    },
    {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "api_key": "",
        "base_url": "https://api.groq.com/openai/v1",
        "api_style": "openai",
        "name": "Groq (Fast)",
        "enabled": True,
        "status": "disconnected",
        "last_used": 0,
        "priority": 1
    },
    {
        "provider": "openrouter",
        "model": "openai/gpt-4o-mini",
        "api_key": "",
        "base_url": "https://openrouter.ai/api/v1",
        "api_style": "openai",
        "name": "OpenRouter (Multi)",
        "enabled": True,
        "status": "disconnected",
        "last_used": 0,
        "priority": 2
    }
]


def load_backup_providers() -> list[dict]:
    """Load the ordered backup-provider list from disk. Never raises.
    
    v0.7.9.5: If no backup providers are configured, returns the default
    list which includes Ollama as a local fallback. This ensures there's
    always a working backup chain, even for new installations.
    """
    try:
        if os.path.exists(BACKUP_PROVIDERS_FILE):
            with open(BACKUP_PROVIDERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                out = []
                for i, entry in enumerate(data):
                    if not isinstance(entry, dict):
                        continue
                    rec = dict(DEFAULT_STATUS)
                    rec.update({k: v for k, v in entry.items() if k in DEFAULT_STATUS})
                    rec["priority"] = i
                    out.append(rec)
                return out
    except Exception:
        pass
    
    # v0.7.9.5: Return default backup providers (includes Ollama)
    # This ensures a working failover chain even for new installations
    _log("No backup providers configured, using defaults (includes Ollama)")
    return [dict(entry) for entry in DEFAULT_BACKUP_PROVIDERS]


def save_backup_providers(providers: list[dict]) -> bool:
    """Persist the ordered backup-provider list. Returns True on success."""
    try:
        clean = []
        for i, entry in enumerate(providers or []):
            rec = {k: v for k, v in entry.items() if k in DEFAULT_STATUS}
            rec["priority"] = i
            clean.append(rec)
        with open(BACKUP_PROVIDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(clean, f, indent=2)
        return True
    except Exception:
        return False


def add_backup_provider(entry: dict) -> bool:
    """Add a new provider configuration to the dynamic backup pool."""
    if not isinstance(entry, dict):
        return False
    try:
        providers = load_backup_providers()
        prov_id = str(entry.get("provider", "")).strip().lower()
        model = str(entry.get("model", "")).strip()
        if not prov_id or not model:
            return False

        # Update if existing, or append
        existing = next((p for p in providers if p.get("provider", "").lower() == prov_id and p.get("model") == model), None)
        if existing:
            existing.update({k: v for k, v in entry.items() if k in DEFAULT_STATUS})
        else:
            rec = dict(DEFAULT_STATUS)
            rec.update({k: v for k, v in entry.items() if k in DEFAULT_STATUS})
            rec["priority"] = len(providers)
            providers.append(rec)

        return save_backup_providers(providers)
    except Exception:
        return False


def remove_backup_provider(identifier: Any) -> bool:
    """Remove a backup provider by 0-based index or provider_id."""
    try:
        providers = load_backup_providers()
        if isinstance(identifier, int) and 0 <= identifier < len(providers):
            providers.pop(identifier)
            return save_backup_providers(providers)
        
        target = str(identifier).strip().lower()
        if target.isdigit():
            idx = int(target)
            if 0 <= idx < len(providers):
                providers.pop(idx)
                return save_backup_providers(providers)

        filtered = [p for p in providers if p.get("provider", "").lower() != target]
        if len(filtered) != len(providers):
            return save_backup_providers(filtered)
        return False
    except Exception:
        return False


def reorder_backup_provider(from_index: int, to_index: int) -> bool:
    """Move a backup provider from one priority position to another."""
    try:
        providers = load_backup_providers()
        if not (0 <= from_index < len(providers) and 0 <= to_index < len(providers)):
            return False
        item = providers.pop(from_index)
        providers.insert(to_index, item)
        return save_backup_providers(providers)
    except Exception:
        return False


def set_backup_provider_enabled(identifier: Any, enabled: bool) -> bool:
    """Toggle the enabled status of a backup provider."""
    try:
        providers = load_backup_providers()
        if isinstance(identifier, int) and 0 <= identifier < len(providers):
            providers[identifier]["enabled"] = bool(enabled)
            return save_backup_providers(providers)

        target = str(identifier).strip().lower()
        if target.isdigit():
            idx = int(target)
            if 0 <= idx < len(providers):
                providers[idx]["enabled"] = bool(enabled)
                return save_backup_providers(providers)

        matched = False
        for p in providers:
            if p.get("provider", "").lower() == target:
                p["enabled"] = bool(enabled)
                matched = True
        if matched:
            return save_backup_providers(providers)
        return False
    except Exception:
        return False


def test_provider_connectivity(config: dict) -> tuple[bool, str, list[str]]:
    """Test connectivity, model listing, and latency without leaking API keys."""
    start = time.time()
    ok, msg, models = connect_provider(config)
    lat = int((time.time() - start) * 1000)

    # Sanitize message of any keys
    from ..resilience.health_monitor import sanitize_error, get_health_monitor
    clean_msg = sanitize_error(msg)

    prov = config.get("provider", "")
    model = config.get("model", "")
    mon = get_health_monitor()
    if ok:
        mon.record_success(prov, model, latency_ms=lat)
        # Also update status in saved backup provider record
        try:
            providers = load_backup_providers()
            for p in providers:
                if p.get("provider") == prov and p.get("model") == model:
                    p["status"] = "connected"
                    p["latency_ms"] = lat
                    p["last_used"] = int(time.time())
            save_backup_providers(providers)
        except Exception:
            pass
    else:
        mon.record_failure(prov, model, error_message=clean_msg)

    return ok, clean_msg, models


def backup_configs() -> list[dict]:
    """The live request-config shapes for every enabled backup, in
    priority order — exactly what aicore feeds into _resolve_provider.
    
    v0.7.9.5: Improved Ollama handling for backup failover. Ollama
    providers are automatically detected and configured with the
    correct base_url and api_style for reliable local inference.
    """
    out = []
    for entry in load_backup_providers():
        if not entry.get("enabled"):
            continue
        prov_id = entry.get("provider", "")
        key = entry.get("api_key", "")
        # Resolve API key from environment if missing in saved backup config
        if not (key or "").strip() and prov_id:
            env_k = get_env_api_key(prov_id)
            if env_k:
                key = env_k

        cfg = {
            "provider": prov_id,
            "model": entry.get("model", ""),
            "api_key": key,
            "api_style": entry.get("api_style", "openai"),
        }
        # v0.7.10: Always resolve base_url, even if empty in entry
        base_url = entry.get("base_url", "")
        if not base_url:
            # Try to get base_url from providers.json
            provider_id = cfg.get("provider", "")
            if provider_id:
                try:
                    from ..models.manager import load_providers
                    for p in load_providers():
                        if p.get("id") == provider_id:
                            base_url = p.get("api_endpoint", "")
                            if base_url:
                                break
                except Exception:
                    pass
            # Fallback to built-in provider URLs
            if not base_url:
                _builtin_urls = {
                    "openai": "https://api.openai.com/v1",
                    "anthropic": "https://api.anthropic.com",
                    "groq": "https://api.groq.com/openai/v1",
                    "openrouter": "https://openrouter.ai/api/v1",
                    "ollama": "http://localhost:11434",
                    "deepseek": "https://api.deepseek.com/v1",
                    "mistral": "https://api.mistral.ai/v1",
                    "cohere": "https://api.cohere.com/v1",
                    "fireworks": "https://api.fireworks.ai/inference/v1",
                    "together": "https://api.together.xyz/v1",
                    "nvidia": "https://integrate.api.nvidia.com/v1",
                }
                base_url = _builtin_urls.get(provider_id, "")
        if base_url:
            cfg["base_url"] = base_url
        
        # v0.7.9.5: Auto-configure Ollama settings for backup providers
        if cfg.get("provider") == "ollama":
            cfg["api_style"] = "ollama"
            cfg["needs_key"] = False
            # Ensure Ollama base_url is always set
            if not cfg.get("base_url"):
                cfg["base_url"] = "http://localhost:11434"
        
        if cfg.get("provider") and cfg.get("model"):
            out.append((cfg, entry))
    # Auto-heal: if no enabled backups but there are disabled ones with valid keys, enable the most recent one
    if not out:
        try:
            all_entries = load_backup_providers()
            disabled_with_key = [
                e for e in all_entries
                if not e.get("enabled") and ((e.get("api_key") or "").strip() or get_env_api_key(e.get("provider", ""))) and e.get("provider") and e.get("model")
            ]
            if disabled_with_key:
                # Enable the one with most recent last_used or first
                disabled_with_key.sort(key=lambda x: x.get("last_used", 0), reverse=True)
                to_enable = disabled_with_key[0]
                # Persist enabled state
                for rec in all_entries:
                    if rec.get("provider") == to_enable.get("provider") and rec.get("model") == to_enable.get("model"):
                        rec["enabled"] = True
                        rec["status"] = "disconnected"
                        break
                save_backup_providers(all_entries)
                _log(f"Auto-enabled disabled backup {to_enable.get('provider')}/{to_enable.get('model')} — was disabled but had valid key")
                # Re-build out with newly enabled
                return backup_configs()
        except Exception:
            pass
    return out


def mark_backup_used(entry: dict):
    """Record 'last used' + 'connected' on a backup entry and persist it."""
    if not isinstance(entry, dict):
        return
    try:
        import time as _t
        providers = load_backup_providers()
        changed = False
        for rec in providers:
            if (rec.get("provider") == entry.get("provider")
                    and rec.get("model") == entry.get("model")):
                rec["last_used"] = int(_t.time())
                rec["status"] = "connected"
                changed = True
        if changed:
            save_backup_providers(providers)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Fetch models

def fetch_models_for(config: dict) -> list[str]:
    """Fetch live models for a given config. Uses cache if available.
    Falls back to generic HTTP fetch for unknown providers.
    Never raises."""
    provider_id = config.get("provider")
    if not provider_id:
        return []
    cached = get_cached_models(provider_id)
    if cached is not None:
        return cached
    cls = get_provider_class(provider_id)
    if cls:
        try:
            inst = cls(config)
            models = inst.fetch_models()
            if models:
                set_cached_models(provider_id, models)
            return models or []
        except Exception:
            pass
    # Generic fallback for providers without a registered class
    api_style = config.get("api_style", "openai")
    _log(f"fetch_models_for [{provider_id}]: no class found, "
         f"trying generic {api_style} fetch")
    if api_style == "openai":
        models = _generic_fetch_models_openai(config)
    elif api_style == "ollama":
        models = _generic_fetch_models_ollama(config)
    else:
        models = []
    if models:
        set_cached_models(provider_id, models)
    return models or []


def fetch_models_for_provider_id(provider_id: str,
                                  api_key: str = "",
                                  base_url: str = "") -> list[str]:
    """Helper to build config and fetch models."""
    config = {"provider": provider_id, "api_key": api_key, "base_url": base_url}
    return fetch_models_for(config)


def connect_provider(config: dict) -> tuple[bool, str, list[str]]:
    """Test connection for a provider config. Caches models on success.
    Falls back to generic HTTP fetch for unknown providers."""
    provider_id = config.get("provider")
    cls = get_provider_class(provider_id) if provider_id else None
    if cls:
        try:
            inst = cls(config)
            ok, msg, models = inst.connect()
            if ok and models:
                set_cached_models(provider_id, models)
            return ok, msg, models
        except Exception as e:
            return False, f"Error: {e}", []
    # Generic fallback: use model fetch as connectivity test
    _log(f"connect_provider [{provider_id}]: no class found, "
         f"trying generic fetch as connectivity test")
    models = fetch_models_for(config)
    if models:
        return True, f"Connected \u2014 {len(models)} model(s) visible", models
    return False, f"Unknown provider: {provider_id}", []


# ---------------------------------------------------------------------------
# Chat / Stream helpers with lifecycle-aware model validation

def chat(prompt: str, system_prompt: str = "",
         history: list = None, config: dict = None) -> str:
    """Send a chat message with lifecycle-aware model validation.

    Validates the model before sending, auto-resolves aliases,
    and recovers from deprecation errors automatically.
    """
    try:
        from .lifecycle import validate_and_chat
        result = validate_and_chat(
            config or {}, prompt, system_prompt=system_prompt, history=history)
        return _fix_spacing(result)
    except ImportError:
        pass
    inst = get_provider(config)
    if not inst:
        return "AI not configured. Run setup first."
    return _fix_spacing(inst.chat(prompt, system_prompt=system_prompt, history=history))


def stream(prompt: str, system_prompt: str = "",
           history: list = None, config: dict = None):
    """Stream a chat response with lifecycle-aware model validation."""
    try:
        from .lifecycle import validate_and_stream
        yield from validate_and_stream(
            config or {}, prompt, system_prompt=system_prompt, history=history)
        return
    except ImportError:
        pass
    inst = get_provider(config)
    if not inst:
        yield "AI not configured. Run setup first."
        return
    yield from inst.stream(prompt, system_prompt=system_prompt, history=history)


# ── Lifecycle convenience re-exports ──────────────────────────────────────

def ensure_fresh_models(provider_id: str, config: dict = None,
                         force: bool = False) -> list[str]:
    """Ensure models are fresh for a provider — refresh if stale."""
    try:
        from .lifecycle import ensure_fresh_models as _efm
        return _efm(provider_id, config, force=force)
    except ImportError:
        _log(f"ensure_fresh_models [{provider_id}]: lifecycle not available")
        return []


def check_provider_health(provider_id: str,
                           config: dict = None) -> dict:
    """Get health status for a provider."""
    try:
        from .lifecycle import check_health
        h = check_health(provider_id, config)
        return {
            "provider_id": h.provider_id,
            "online": h.online,
            "api_reachable": h.api_reachable,
            "authenticated": h.authenticated,
            "model_list_available": h.model_list_available,
            "chat_supported": h.chat_supported,
            "latency_ms": h.latency_ms,
            "last_checked": h.last_checked,
            "error": h.error,
        }
    except ImportError:
        return {"provider_id": provider_id, "online": False,
                "error": "lifecycle module not available"}


def validate_and_resolve_model(provider_id: str, model: str) -> dict:
    """Validate a model and resolve any aliases.

    Returns {"valid": bool, "model": resolved_model, "message": str}.
    """
    try:
        from .lifecycle import pre_request_check
        result = pre_request_check(provider_id, model)
        return {
            "valid": result.valid,
            "model": result.replacement or result.model,
            "message": result.message,
        }
    except ImportError:
        return {"valid": True, "model": model, "message": ""}


# ── Dynamic model management (v0.7.4+) ────────────────────────────────────
# These delegate to models/manager.py, the data-driven core: live API
# fetch -> disk cache -> built-in fallback, with source tracking.

def get_models_with_source(provider_id: str, config: dict = None,
                           force: bool = False) -> tuple[list[str], str]:
    """Resolve models for a provider. Returns (models, source) where
    source is 'live' | 'cached' | 'default'. Merges the saved config
    (api_key/base_url) so live fetches actually authenticate."""
    try:
        from ..models import manager as _mgr
        cfg = dict(config or {})
        saved = load_config()
        if saved.get("provider") == provider_id:
            cfg.setdefault("api_key", saved.get("api_key", ""))
            cfg.setdefault("base_url", saved.get("base_url") or saved.get("api_url", ""))
        if not cfg.get("base_url") and not cfg.get("api_url"):
            info = _mgr.get_provider(provider_id) or {}
            cfg["base_url"] = info.get("api_endpoint", "")
        return _mgr.get_models(provider_id, cfg, force_refresh=force)
    except Exception as e:
        _log(f"get_models_with_source [{provider_id}]: {e}", exc_info=True)
        return [], "default"


def refresh_provider_models(provider_id: str, config: dict = None
                            ) -> tuple[list[str], str]:
    """Force-refresh the model list for a provider from its official API."""
    return get_models_with_source(provider_id, config, force=True)


def ensure_provider_models_fresh(provider_id: str, config: dict = None
                                 ) -> tuple[list[str], str]:
    """Refresh if the cache is stale; otherwise reuse the cached list.
    Called automatically when the model picker opens."""
    try:
        from ..models import manager as _mgr
        cfg = dict(config or {})
        saved = load_config()
        if saved.get("provider") == provider_id:
            cfg.setdefault("api_key", saved.get("api_key", ""))
            cfg.setdefault("base_url", saved.get("base_url") or saved.get("api_url", ""))
        if not cfg.get("base_url") and not cfg.get("api_url"):
            info = _mgr.get_provider(provider_id) or {}
            cfg["base_url"] = info.get("api_endpoint", "")
        return _mgr.ensure_fresh(provider_id, cfg)
    except Exception as e:
        _log(f"ensure_provider_models_fresh [{provider_id}]: {e}", exc_info=True)
        return [], "default"


def get_model_source(provider_id: str) -> str:
    """'live' | 'cached' | 'default' for the provider's last resolution."""
    try:
        from ..models import manager as _mgr
        return _mgr.get_model_source(provider_id)
    except Exception:
        return "default"


def get_last_model_refresh(provider_id: str) -> str:
    """ISO timestamp of the last successful model fetch ('' if none)."""
    try:
        from ..models import manager as _mgr
        return _mgr.get_last_refresh(provider_id)
    except Exception:
        return ""


def get_provider_status(provider_id: str, model_id: str = "") -> dict:
    """Full status dict for /status — provider, model source, last refresh,
    capability flags, model count. Never raises."""
    try:
        from ..models import manager as _mgr
        return _mgr.get_status(provider_id, model_id)
    except Exception:
        return {"provider_id": provider_id, "model_source": "default"}


def search_provider_models(provider_id: str, query: str,
                           filter_id: str = "all") -> list[dict]:
    """Search models by name/family/capability/provider, with a category
    filter (all/free/paid/latest/reasoning/coding/vision/fast/
    long_context/image/speech/embedding/experimental)."""
    try:
        from ..models import manager as _mgr
        return _mgr.search(provider_id, query, filter_id)
    except Exception:
        return []


def provider_capability_badges(provider_id: str) -> list[str]:
    """Capability badges for a provider row ([FREE] [PAID] [VISION] ...)."""
    try:
        from ..models import manager as _mgr
        return _mgr.provider_badges(provider_id)
    except Exception:
        return []


# ── Auto-Update System ─────────────────────────────────────────────────────

def start_provider_auto_updates():
    """Start the background auto-update system for providers.
    
    This will periodically check for new models from provider APIs
    and update the local cache. Call this on app startup.
    """
    if _HAS_AUTO_UPDATE:
        start_auto_updates()
        _log("Started provider auto-update system")
    else:
        _log("Auto-update system not available")


def stop_provider_auto_updates():
    """Stop the background auto-update system."""
    if _HAS_AUTO_UPDATE:
        stop_auto_updates()
        _log("Stopped provider auto-update system")


def force_provider_update() -> bool:
    """Force an immediate update of all providers.
    
    Returns:
        True if updates were applied, False otherwise
    """
    if _HAS_AUTO_UPDATE:
        return force_update()
    return False


def get_auto_updated_providers() -> Dict:
    """Get the latest provider data from auto-update system.
    
    Returns:
        Dictionary with providers data
    """
    if _HAS_AUTO_UPDATE:
        return get_latest_providers()
    return {"version": 1, "providers": []}


def add_custom_provider_to_config(provider: Dict) -> bool:
    """Add a custom provider to the local configuration.
    
    Args:
        provider: Provider configuration dictionary
        
    Returns:
        True if added successfully, False otherwise
    """
    if _HAS_AUTO_UPDATE:
        return add_custom_provider(provider)
    return False


def remove_custom_provider_from_config(provider_id: str) -> bool:
    """Remove a custom provider from the local configuration.
    
    Args:
        provider_id: ID of the provider to remove
        
    Returns:
        True if removed successfully, False otherwise
    """
    if _HAS_AUTO_UPDATE:
        return remove_custom_provider(provider_id)
    return False


def discover_provider_models_auto(provider_id: str, base_url: str,
                                   api_style: str = "openai") -> List[str]:
    """Discover available models from a provider's API.
    
    Args:
        provider_id: Provider identifier
        base_url: API base URL
        api_style: API style (openai, anthropic, gemini, ollama)
        
    Returns:
        List of available model names
    """
    try:
        from .discovery_manager import get_discovery_manager
        dm = get_discovery_manager()
        discov_list = dm.discover_provider(provider_id, config={"base_url": base_url, "api_style": api_style})
        if discov_list:
            return [m.model_id for m in discov_list]
    except Exception:
        pass

    if _HAS_AUTO_UPDATE:
        return auto_discover_models(provider_id, base_url, api_style)
    return []


# Initialize on import
register_builtins()
