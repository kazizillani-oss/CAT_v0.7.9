"""Dynamic model manager — the future-proof model management core.

Priority order for any provider:

    1. Fetch models from the provider's official API (live).
    2. If fetching fails, use the on-disk cache (cache/models/).
    3. If no cache exists, use the provider's built-in fallback list
       (providers.json -> fallback_models).

Every successful live fetch is written to the disk cache with a
timestamp. Opening /model triggers an automatic background refresh when
the cache is older than the configured interval, so newly released
models show up without an application update.

Everything is data-driven: provider metadata lives in
providers/providers.json and curated model metadata lives in
models/model_metadata.json — no model names are hardcoded in Python
source code.
"""

import json
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

# ── Paths ──────────────────────────────────────────────────────────────────
# project root = <project>/calc_terminal/models/../../
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # calc_terminal/
PROVIDERS_FILE = os.path.join(_PKG_DIR, "providers", "providers.json")
MODEL_METADATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "model_metadata.json")
CACHE_DIR = os.path.join(_ROOT, "cache", "models")

# ── Sources ────────────────────────────────────────────────────────────────
SOURCE_LIVE = "live"       # freshly fetched from the provider's API
SOURCE_CACHED = "cached"   # read from the local disk cache
SOURCE_DEFAULT = "default" # built-in fallback list (providers.json)

# ── Category filters (UI + /model search) ──────────────────────────────────
CATEGORIES = [
    "all", "free", "paid", "latest", "reasoning", "coding", "vision",
    "fast", "long_context", "image", "speech", "embedding", "experimental",
]

_lock = threading.Lock()
_providers: Optional[list[dict]] = None
_metadata: Optional[dict] = None
_metadata_index: Optional[dict] = None
_sources: dict[str, str] = {}      # provider_id -> last source used
_last_refresh: dict[str, str] = {} # provider_id -> ISO timestamp

# ── Loading (JSON = single source of truth) ────────────────────────────────

def _default_cache_ttl_hours() -> float:
    """Configured cache interval in hours (default 24)."""
    try:
        from .. import config as _cfg
        return float(_cfg.load_config().get("model_cache_ttl_hours", 24.0) or 24.0)
    except Exception:
        return 24.0


def load_providers() -> list[dict]:
    """Load provider metadata from providers.json. Never raises — an
    unreadable file degrades to an empty list."""
    global _providers
    if _providers is not None:
        return _providers
    try:
        with open(PROVIDERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _providers = list(data.get("providers", []))
    except Exception:
        _providers = []
    return _providers


def reload_providers() -> list[dict]:
    """Force reload of providers.json (used by import/export flows)."""
    global _providers
    _providers = None
    return load_providers()


def get_provider(provider_id: str) -> Optional[dict]:
    """Return provider metadata dict or None."""
    for p in load_providers():
        if p.get("id") == provider_id:
            return p
    return None


def default_model_for(provider_id: str, fallback: str = "") -> str:
    """Data-driven default model for a provider: providers.json
    'default_model' field, else first fallback model, else `fallback`."""
    try:
        provider = get_provider(provider_id)
        if provider:
            dflt = str(provider.get("default_model") or "").strip()
            if dflt:
                return dflt
            fb = [str(m) for m in provider.get("fallback_models", []) if str(m).strip()]
            if fb:
                return fb[0]
    except Exception:
        pass
    return fallback


def list_providers() -> list[dict]:
    return sorted(load_providers(), key=lambda p: p.get("name", "").lower())


def _load_metadata() -> dict:
    """{model_id: metadata_dict} merged from model_metadata.json."""
    global _metadata
    if _metadata is not None:
        return _metadata
    out = {}
    try:
        with open(MODEL_METADATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for m in data.get("models", []):
            if m.get("id"):
                out[str(m["id"])] = m
    except Exception:
        pass
    _metadata = out
    return out


def get_model_meta(model_id: str, provider_id: str = "") -> Optional[dict]:
    """Curated metadata for a model. Falls back to matching any provider
    if provider_id is unknown."""
    try:
        from .dynamic_registry import get_registry
        reg = get_registry()
        m = reg.get_model(model_id, provider_id)
        if m:
            return {
                "id": m.model_id,
                "provider": m.provider,
                "display_name": m.display_name,
                "family": m.family,
                "context_length": m.context_window,
                "reasoning": m.has_capability("reasoning"),
                "coding": m.has_capability("coding"),
                "vision": m.has_capability("vision"),
                "embedding": m.has_capability("embedding"),
                "tools": m.has_capability("tools"),
                "streaming": m.has_capability("streaming"),
                "free": m.availability in ("free_api", "free_tier") or m.pricing.get("input_price_per_1m", 0.0) == 0.0,
                "paid": m.pricing.get("input_price_per_1m", 0.0) > 0.0,
                "deprecated": m.status == "deprecated",
                "preview": m.status in ("preview", "beta"),
                "input_price_per_1m": m.pricing.get("input_price_per_1m", 0.0),
                "output_price_per_1m": m.pricing.get("output_price_per_1m", 0.0),
                "reasoning_levels": m.reasoning_levels,
                "recommendation_badges": m.recommendation_badges,
            }
    except Exception:
        pass
    meta = _load_metadata()
    entry = meta.get(model_id)
    if entry and (not provider_id or entry.get("provider") == provider_id):
        return entry
    if provider_id and entry and entry.get("provider") != provider_id:
        return None
    return entry


# ── Disk cache (cache/models/{provider_id}.json) ───────────────────────────

def get_cache_path(provider_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(provider_id))
    return os.path.join(CACHE_DIR, f"{safe}.json")


def get_cached(provider_id: str) -> Optional[tuple[list[str], str]]:
    """(models, fetched_at_iso) from disk, or None."""
    path = get_cache_path(provider_id)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        models = data.get("models")
        if not isinstance(models, list) or not models:
            return None
        return [str(m) for m in models], str(data.get("fetched_at", ""))
    except Exception:
        return None


def write_cache(provider_id: str, models: list[str]):
    """Persist a fetched model list with a timestamp. Never raises."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    payload = {
        "provider": provider_id,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "models": sorted(set(models)),
    }
    try:
        tmp = get_cache_path(provider_id) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, get_cache_path(provider_id))
    except Exception:
        pass


def delete_cache(provider_id: str):
    try:
        path = get_cache_path(provider_id)
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def cache_age_hours(provider_id: str) -> Optional[float]:
    """How old the cached list is, in hours. None if no cache."""
    entry = get_cached(provider_id)
    if not entry:
        return None
    try:
        fetched = datetime.fromisoformat(entry[1])
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - fetched).total_seconds() / 3600.0)
    except Exception:
        return None


def cache_is_fresh(provider_id: str) -> bool:
    age = cache_age_hours(provider_id)
    if age is None:
        return False
    return age <= _default_cache_ttl_hours()


# ── Live fetching ──────────────────────────────────────────────────────────

def _fetch_openai_compatible(config: dict, timeout: int = 12) -> list[str]:
    """GET {base_url}/models → {"data": [{"id": ...}]}."""
    import requests
    base_url = (config.get("base_url") or config.get("api_url") or "").rstrip("/")
    if not base_url:
        return []
    headers = {"Content-Type": "application/json"}
    if config.get("api_key"):
        headers["Authorization"] = f"Bearer {config['api_key']}"
    resp = requests.get(f"{base_url}/models", headers=headers, timeout=timeout)
    if resp.status_code >= 400:
        return []
    data = resp.json()
    items = data.get("data", [])
    return sorted({str(m.get("id")) for m in items if isinstance(m, dict) and m.get("id")})


def _fetch_gemini(config: dict, timeout: int = 12) -> list[str]:
    """GET {base}/models?key=... → {"models": [{"name": "models/..."}]}."""
    import requests
    base_url = (config.get("base_url") or "").rstrip("/")
    if not base_url:
        return []
    api_key = config.get("api_key", "")
    resp = requests.get(f"{base_url}/models", params={"key": api_key}, timeout=timeout)
    if resp.status_code >= 400:
        return []
    out = []
    for m in resp.json().get("models", []):
        methods = m.get("supportedGenerationMethods") or []
        if not methods or "generateContent" in methods:
            name = str(m.get("name", ""))
            if "/" in name:
                name = name.split("/")[-1]
            if name:
                out.append(name)
    return sorted(set(out))


def _fetch_anthropic(config: dict, timeout: int = 12) -> list[str]:
    """GET {base}/models → {"data": [{"id": ...}]} (Anthropic models API)."""
    import requests
    base_url = (config.get("base_url") or "").rstrip("/")
    if not base_url:
        return []
    headers = {"Content-Type": "application/json"}
    if config.get("api_key"):
        headers["x-api-key"] = config["api_key"]
        headers["anthropic-version"] = "2023-06-01"
    resp = requests.get(f"{base_url}/models", headers=headers, timeout=timeout)
    if resp.status_code >= 400:
        return []
    data = resp.json()
    items = data.get("data", [])
    return sorted({str(m.get("id")) for m in items if isinstance(m, dict) and m.get("id")})


def _fetch_ollama(config: dict, timeout: int = 8) -> list[str]:
    """GET {base}/api/tags → {"models": [{"name": ...}]}."""
    import requests
    base_url = (config.get("base_url") or config.get("ollama_url") or
                "http://localhost:11434").rstrip("/")
    if base_url.endswith("/v1"):
        return _fetch_openai_compatible(config, timeout)
    resp = requests.get(f"{base_url}/api/tags", timeout=timeout)
    if resp.status_code >= 400:
        return []
    models = []
    for m in resp.json().get("models", []):
        name = m.get("name") if isinstance(m, dict) else None
        if name:
            models.append(str(name))
    return sorted(set(models))


def fetch_live(provider_id: str, config: dict = None) -> list[str]:
    """Try the official models API for a provider. Prefers registered
    provider SDK classes, falls back to a generic fetch by api_style.
    Returns [] on any failure (callers then fall back to cache/default).
    """
    cfg = dict(config or {})
    cfg.setdefault("provider", provider_id)
    provider = get_provider(provider_id) or {}
    cfg.setdefault("base_url", provider.get("api_endpoint", ""))
    cfg.setdefault("api_style", provider.get("api_style", "openai"))
    api_style = cfg.get("api_style", "openai")

    # Only gate on metadata when the provider is actually known — custom
    # providers (arbitrary base_url/api_style from user config) always try.
    if provider and not provider.get("supports_model_listing", False):
        return []

    try:
        from ..providers.provider_manager import get_provider_class
        cls = get_provider_class(provider_id)
        if cls is not None:
            inst = cls(cfg)
            if hasattr(inst, "fetch_models"):
                models = inst.fetch_models()
                if models:
                    return sorted(set(str(m) for m in models))
                return []
    except Exception:
        pass  # fall through to generic fetch

    try:
        if api_style == "openai":
            return _fetch_openai_compatible(cfg)
        if api_style == "gemini":
            return _fetch_gemini(cfg)
        if api_style == "anthropic":
            return _fetch_anthropic(cfg)
        if api_style == "ollama":
            return _fetch_ollama(cfg)
    except Exception:
        return []
    return []


# ── Core resolution (the priority chain) ───────────────────────────────────

def _fallback_models(provider_id: str) -> list[str]:
    provider = get_provider(provider_id) or {}
    fallback = [str(m) for m in provider.get("fallback_models", [])]
    if not fallback:
        fallback = ["default"]
    return fallback


def get_models(provider_id: str, config: dict = None,
               force_refresh: bool = False) -> tuple[list[str], str]:
    """Resolve the model list for a provider. Uses ProviderDiscoveryManager
    and DynamicModelRegistry with safe fallback to cache/default."""
    with _lock:
        if force_refresh:
            try:
                from ..providers.discovery_manager import get_discovery_manager
                dm = get_discovery_manager()
                discovered = dm.discover_provider(provider_id, config)
                if discovered:
                    models = [m.model_id for m in discovered]
                    write_cache(provider_id, models)
                    _sources[provider_id] = SOURCE_LIVE
                    _last_refresh[provider_id] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    return models, SOURCE_LIVE
            except Exception:
                pass
            models = fetch_live(provider_id, config)
            if models:
                write_cache(provider_id, models)
                _sources[provider_id] = SOURCE_LIVE
                _last_refresh[provider_id] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                return models, SOURCE_LIVE
            # live failed — fall through to cache then defaults

        cached = get_cached(provider_id)
        if cached:
            models, fetched_at = cached
            _sources[provider_id] = SOURCE_CACHED
            _last_refresh[provider_id] = fetched_at
            return list(models), SOURCE_CACHED

        try:
            from .dynamic_registry import get_registry
            reg = get_registry()
            reg_models = [m.model_id for m in reg.list_models(provider=provider_id)]
            if reg_models:
                return reg_models, SOURCE_CACHED
        except Exception:
            pass

        try:
            from ..providers.discovery_manager import get_discovery_manager
            dm = get_discovery_manager()
            discovered = dm.discover_provider(provider_id, config)
            if discovered:
                models = [m.model_id for m in discovered]
                write_cache(provider_id, models)
                _sources[provider_id] = SOURCE_LIVE
                _last_refresh[provider_id] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                return models, SOURCE_LIVE
        except Exception:
            pass

        models = fetch_live(provider_id, config)
        if models:
            write_cache(provider_id, models)
            _sources[provider_id] = SOURCE_LIVE
            _last_refresh[provider_id] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            return models, SOURCE_LIVE

        fallback = _fallback_models(provider_id)
        _sources[provider_id] = SOURCE_DEFAULT
        _last_refresh[provider_id] = ""
        return fallback, SOURCE_DEFAULT


def refresh_models(provider_id: str, config: dict = None) -> tuple[list[str], str]:
    """Force a fresh fetch from the provider's API. Returns
    (models, source) — falls back to cache/default on failure."""
    return get_models(provider_id, config, force_refresh=True)


def ensure_fresh(provider_id: str, config: dict = None) -> tuple[list[str], str]:
    """Refresh when the cache is stale, otherwise keep the cache.
    Called automatically whenever the model picker opens."""
    if cache_is_fresh(provider_id) and get_cached(provider_id):
        cached = get_cached(provider_id)
        _sources[provider_id] = SOURCE_CACHED
        _last_refresh[provider_id] = cached[1]
        return list(cached[0]), SOURCE_CACHED
    return refresh_models(provider_id, config)


def get_model_source(provider_id: str) -> str:
    """'live' | 'cached' | 'default' for the last resolution."""
    return _sources.get(provider_id, SOURCE_DEFAULT)


def get_last_refresh(provider_id: str) -> str:
    return _last_refresh.get(provider_id, "")


# ── New-model detection ────────────────────────────────────────────────────
# A model is "new" when it appeared in a live fetch but is not part of the
# built-in fallback list — so brand-new releases get a NEW badge without any
# application update.

def new_models(provider_id: str) -> set[str]:
    provider = get_provider(provider_id) or {}
    fallback = {str(m) for m in provider.get("fallback_models", [])}
    cached = get_cached(provider_id)
    if not cached:
        return set()
    live_set = set(cached[0])
    new = live_set - fallback
    for m in live_set:
        lower = m.lower()
        if any(k in lower for k in ("latest", "-exp", "exp-", "-preview", "preview-")):
            new.add(m)
    return new


# ── Enrichment / badges / filtering ────────────────────────────────────────

_FAST_HINTS = ("flash", "mini", "nano", "turbo", "lite", "small", "instant",
               "haiku", "-8b", "-7b", "8b-", "7b-", "speed", "fast", "fx")
_LONG_CTX_HINTS = ("128k", "200k", "1m", "1000000", "1048576", "2097152", "long", "extended")


def _pricing_tier(meta: Optional[dict], model_id: str) -> str:
    if meta:
        if meta.get("free"):
            return "free"
        if meta.get("paid"):
            return "paid"
    lower = model_id.lower()
    if any(k in lower for k in ("free", "open-", "gemma", "llama-4-scout")):
        return "free"
    return "unknown"


def _status(meta: Optional[dict]) -> str:
    if not meta:
        return "stable"
    if meta.get("deprecated"):
        return "deprecated"
    if meta.get("preview"):
        return "preview"
    return "stable"


def _capabilities(meta: Optional[dict], model_id: str) -> list[str]:
    if meta:
        caps = []
        for key, label in (("reasoning", "reasoning"), ("vision", "vision"),
                           ("coding", "coding"), ("embedding", "embeddings"),
                           ("image_generation", "image_gen"), ("speech", "audio"),
                           ("tools", "tool_use"), ("streaming", "streaming"),
                           ("chat", "chat")):
            if meta.get(key):
                caps.append(label)
        if caps:
            return caps
    caps = []
    lower = model_id.lower()
    if "vision" in lower or "4o" in lower or "flash" in lower:
        caps.append("vision")
    if "reason" in lower or "thinking" in lower or "o1" in lower or "o3" in lower or "r1" in lower:
        caps.append("reasoning")
    if "embed" in lower:
        caps.append("embeddings")
    if "whisper" in lower or "tts" in lower:
        caps.append("audio")
    return caps


def build_badges(provider_id: str, model_id: str, meta: Optional[dict] = None,
                 new_set: Optional[set[str]] = None) -> list[str]:
    """FREE/PAID + NEW/LATEST/RECOMMENDED/BETA/PREVIEW/DEPRECATED badges."""
    badges = []
    tier = _pricing_tier(meta, model_id)
    badges.append("[FREE]" if tier == "free" else "[PAID]" if tier == "paid" else "[?]")

    new_set = new_set if new_set is not None else set()
    if model_id in new_set:
        badges.append("[NEW]")
    if meta and meta.get("recommended"):
        badges.append("[LATEST]")
    if meta and meta.get("preview"):
        badges.append("[BETA]")
    status = _status(meta)
    if status == "preview" and not (meta and meta.get("preview") and model_id in new_set):
        pass
    if status == "deprecated":
        badges.append("[DEPRECATED]")
    if status == "preview":
        badges.append("[PREVIEW]")
    return badges


def enrich(provider_id: str, model_ids: list[str],
           with_new: bool = True) -> list[dict]:
    """Merge dynamic model IDs with curated metadata. Returns sorted list:
    {"id", "display_name", "family", "category", "capabilities",
     "context_length", "free", "paid", "pricing_tier", "status",
     "recommended", "preview", "deprecated", "badges", "is_new"}
    """
    new_set = new_models(provider_id) if with_new else set()
    result = []
    for mid in model_ids:
        meta = get_model_meta(mid, provider_id)
        entry = {
            "id": mid,
            "display_name": (meta or {}).get("display_name") or mid,
            "provider": provider_id,
            "family": (meta or {}).get("family", ""),
            "category": (meta or {}).get("category", "general"),
            "capabilities": _capabilities(meta, mid),
            "context_length": int((meta or {}).get("context_length", 0) or 0),
            "free": _pricing_tier(meta, mid) == "free",
            "paid": _pricing_tier(meta, mid) == "paid",
            "pricing_tier": _pricing_tier(meta, mid),
            "status": _status(meta),
            "recommended": bool((meta or {}).get("recommended", False)),
            "preview": bool((meta or {}).get("preview", False)),
            "deprecated": bool((meta or {}).get("deprecated", False)),
            "release_date": (meta or {}).get("release_date"),
            "input_price_per_1m": float((meta or {}).get("input_price_per_1m", 0.0) or 0.0),
            "output_price_per_1m": float((meta or {}).get("output_price_per_1m", 0.0) or 0.0),
            "is_new": mid in new_set,
            "badges": [],
        }
        entry["badges"] = build_badges(provider_id, mid, meta, new_set)
        result.append(entry)
    result.sort(key=lambda e: e["id"].lower())
    return result


def _is_latest(entry: dict, new_set: set[str]) -> bool:
    if entry["id"] in new_set:
        return True
    if entry.get("recommended"):
        return True
    if entry.get("status") in ("preview", "experimental"):
        return True
    return False


def _is_fast(entry: dict) -> bool:
    lower = entry["id"].lower()
    return any(h in lower for h in _FAST_HINTS)


def _is_long_context(entry: dict) -> bool:
    if entry.get("context_length", 0) >= 100000:
        return True
    lower = entry["id"].lower()
    return any(h in lower for h in _LONG_CTX_HINTS)


def apply_filter(entries: list[dict], filter_id: str,
                 new_set: Optional[set[str]] = None) -> list[dict]:
    """Filter enriched entries by category id (see CATEGORIES)."""
    if not filter_id or filter_id == "all":
        return list(entries)
    new_set = new_set if new_set is not None else set()
    out = []
    for e in entries:
        if filter_id == "free" and e["free"]:
            out.append(e)
        elif filter_id == "paid" and e["paid"]:
            out.append(e)
        elif filter_id == "latest" and _is_latest(e, new_set):
            out.append(e)
        elif filter_id == "reasoning" and "reasoning" in e["capabilities"]:
            out.append(e)
        elif filter_id == "coding" and "coding" in e["capabilities"]:
            out.append(e)
        elif filter_id == "vision" and "vision" in e["capabilities"]:
            out.append(e)
        elif filter_id == "fast" and _is_fast(e):
            out.append(e)
        elif filter_id == "long_context" and _is_long_context(e):
            out.append(e)
        elif filter_id == "image" and "image_gen" in e["capabilities"]:
            out.append(e)
        elif filter_id == "speech" and "audio" in e["capabilities"]:
            out.append(e)
        elif filter_id == "embedding" and "embeddings" in e["capabilities"]:
            out.append(e)
        elif filter_id == "experimental" and e.get("status") in ("preview", "experimental"):
            out.append(e)
    return out


def search(provider_id: str, query: str, filter_id: str = "all",
           model_ids: Optional[list[str]] = None) -> list[dict]:
    """Search models by name, family, capability, or provider name.
    Optionally apply a category filter. Returns enriched entries."""
    q = (query or "").strip().lower()
    if model_ids is None:
        models, _ = get_models(provider_id)
    else:
        models = model_ids
    entries = enrich(provider_id, models)
    if q:
        provider = get_provider(provider_id) or {}
        provider_name = (provider.get("name") or "").lower()
        out = []
        for e in entries:
            hay = " ".join([
                e["id"].lower(),
                e.get("family", "").lower(),
                e.get("category", "").lower(),
                " ".join(e["capabilities"]),
                provider_name,
                e.get("display_name", "").lower(),
            ])
            if q in hay:
                out.append(e)
        entries = out
    return apply_filter(entries, filter_id)


# ── Status ─────────────────────────────────────────────────────────────────

def get_status(provider_id: str, model_id: str = "") -> dict:
    """Everything /status needs:
    provider, country, current model, model source, last refresh,
    cache age, model count, provider capability flags."""
    provider = get_provider(provider_id) or {"id": provider_id}
    source = get_model_source(provider_id)
    last_refresh = get_last_refresh(provider_id)
    if not last_refresh:
        cached = get_cached(provider_id)
        if cached:
            last_refresh = cached[1]
            source = SOURCE_CACHED
    models, _ = get_models(provider_id)
    age = cache_age_hours(provider_id)
    return {
        "provider_id": provider_id,
        "provider_name": provider.get("name", provider_id),
        "country": provider.get("country", ""),
        "current_model": model_id or "",
        "model_source": source,
        "last_refresh": last_refresh,
        "cache_age_hours": age,
        "model_count": len(models),
        "supports_model_listing": bool(provider.get("supports_model_listing", False)),
        "supports_streaming": bool(provider.get("supports_streaming", False)),
        "supports_vision": bool(provider.get("supports_vision", False)),
        "supports_embeddings": bool(provider.get("supports_embeddings", False)),
        "supports_audio": bool(provider.get("supports_audio", False)),
        "supports_reasoning": bool(provider.get("supports_reasoning", False)),
        "openai_compatible": bool(provider.get("openai_compatible", False)),
        "free_models_available": bool(provider.get("free_models_available", False)),
        "paid_models_available": bool(provider.get("paid_models_available", False)),
    }


def provider_badges(provider_id: str) -> list[str]:
    """Capability badges for a provider row in the picker UI."""
    provider = get_provider(provider_id) or {}
    badges = []
    if provider.get("supports_vision"):
        badges.append("[VISION]")
    if provider.get("supports_embeddings"):
        badges.append("[EMBED]")
    if provider.get("supports_audio"):
        badges.append("[AUDIO]")
    if provider.get("supports_reasoning"):
        badges.append("[REASONING]")
    if provider.get("free_models_available"):
        badges.append("[FREE]")
    if provider.get("paid_models_available"):
        badges.append("[PAID]")
    if not provider.get("needs_key", True):
        badges.append("[NO KEY]")
    return badges
