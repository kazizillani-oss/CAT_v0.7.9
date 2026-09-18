"""Model lifecycle management — validation, deprecation handling,
alias resolution, background refresh, and health monitoring.

Architecture:
  ┌─────────────────────────┐
  │   Application/Chat      │
  │   pre_request_check()   │
  │   validate_and_chat()   │
  └────────┬────────────────┘
           │ validate_model()
           ▼
  ┌─────────────────────────┐
  │  ModelLifecycleManager  │
  │  ─ cache check          │
  │  ─ deprecation check    │
  │  ─ alias resolution     │
  │  ─ refresh on stale     │
  └────────┬────────────────┘
           │ fetch_models()
           ▼
  ┌─────────────────────────┐
  │   Provider Adapter      │
  │   (generic fallback or  │
  │    registered class)    │
  └─────────────────────────┘
"""

import os
import re
import threading
import time
from typing import Optional
from dataclasses import dataclass, field


# ── Logging ────────────────────────────────────────────────────────────────

_LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "startup.log")


def _log(msg: str, exc_info: bool = False):
    try:
        ts = time.strftime("%H:%M:%S")
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [Lifecycle] {msg}\n")
            if exc_info:
                import traceback
                traceback.print_exc(file=f)
    except Exception:
        pass


# ── Result Types ───────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    """Result of a model validation check."""
    valid: bool
    model: str
    message: str = ""
    replacement: Optional[str] = None
    retry_after_refresh: bool = False


@dataclass
class RecoveryResult:
    """Result of a deprecation recovery attempt."""
    recovered: bool
    model: str
    message: str
    new_model: Optional[str] = None


@dataclass
class ProviderCapabilities:
    """Capability flags for a provider adapter."""
    supports_model_listing: bool = True
    supports_streaming: bool = True
    supports_tools: bool = False
    supports_reasoning: bool = False
    supports_vision: bool = False
    supports_audio: bool = False
    supports_images: bool = False
    supports_embeddings: bool = False
    supports_reranking: bool = False


@dataclass
class ProviderHealth:
    """Health snapshot for a provider."""
    provider_id: str = ""
    online: bool = False
    api_reachable: bool = False
    authenticated: bool = False
    model_list_available: bool = False
    chat_supported: bool = False
    latency_ms: float = 0.0
    last_checked: float = 0.0
    error: str = ""


# ── Model Alias / Replacement Map ──────────────────────────────────────────
# Known model renames/replacements published by providers.
# Format: (provider_id, old_model) -> new_model
# Data-driven (v0.7.4+): the authoritative alias list lives in
# models/model_metadata.json ("aliases"); the dict below is the fallback
# used only when the JSON store is unreadable.

_MODEL_ALIASES: dict[tuple[str, str], str] = {
    # OpenAI
    ("openai", "gpt-4"): "gpt-4o",
    ("openai", "gpt-4-turbo-preview"): "gpt-4-turbo",
    ("openai", "gpt-3.5-turbo-0125"): "gpt-4o-mini",

    # Anthropic
    ("anthropic", "claude-3-opus-20240229"): "claude-opus-4-20250514",
    ("anthropic", "claude-3-sonnet-20240229"): "claude-sonnet-4-20250514",
    ("anthropic", "claude-3-haiku-20240307"): "claude-3-5-haiku-20241022",
    ("anthropic", "claude-instant-1"): "claude-3-haiku-20240307",
    ("anthropic", "claude-2.1"): "claude-3-5-sonnet-20241022",
    ("anthropic", "claude-2.0"): "claude-3-5-sonnet-20241022",
    ("anthropic", "claude-1"): "claude-3-5-sonnet-20241022",
    ("anthropic", "claude-1.3"): "claude-3-5-sonnet-20241022",
    ("anthropic", "claude-1.2"): "claude-3-5-sonnet-20241022",
    ("anthropic", "claude-1.1"): "claude-3-5-sonnet-20241022",

    # DeepSeek
    ("deepseek", "deepseek-chat"): "deepseek-chat",
    ("deepseek", "deepseek-v2"): "deepseek-chat",

    # Mistral
    ("mistral", "mistral-tiny"): "open-mistral-nemo",
    ("mistral", "mistral-small-latest"): "mistral-small-2402",
    ("mistral", "mistral-medium-latest"): "mistral-large-2407",

    # Google
    ("gemini", "gemini-pro"): "gemini-1.5-pro",
    ("gemini", "gemini-pro-vision"): "gemini-1.5-pro",
    ("gemini", "gemini-ultra"): "gemini-2.0-flash",

    # xAI
    ("xai", "grok-1"): "grok-2-1212",

    # Perplexity
    ("perplexity", "pplx-70b-online"): "sonar-pro",
    ("perplexity", "pplx-7b-online"): "sonar",

    # Cohere
    ("cohere", "command-xlarge"): "command",
    ("cohere", "command-xlarge-beta"): "command",
    ("cohere", "command-medium"): "command-r",
    ("cohere", "command-medium-beta"): "command-r",
}


def _load_aliases() -> dict[tuple[str, str], str]:
    """Authoritative alias map from model_metadata.json; falls back to the
    embedded dict if the JSON store is missing or unreadable."""
    try:
        from ..models import manager as _mgr
        with open(_mgr.MODEL_METADATA_FILE, "r", encoding="utf-8") as f:
            import json as _json
            data = _json.load(f)
        out = {}
        for a in data.get("aliases", []):
            if a.get("provider") and a.get("from") and a.get("to"):
                out[(str(a["provider"]), str(a["from"]))] = str(a["to"])
        if out:
            return out
    except Exception:
        pass
    return dict(_MODEL_ALIASES)

# Patterns that indicate a model-not-found error in the response
_MODEL_NOT_FOUND_PATTERNS = [
    "model.*not found",
    "model.*unavailable",
    "model.*deprecated",
    "model.*decommissioned",
    "model.*removed",
    "model.*retired",
    "model.*no longer",
    "model.*unknown",
    "model.*invalid",
    "model.*unsupported",
    "unknown model",
    "not found",
    "not a valid model",
    "does not exist",
    "has been decommissioned",
    "has been deprecated",
    "has been removed",
    "is not supported",
    "is not available",
]

# ── Refresh Tracking ───────────────────────────────────────────────────────
# {provider_id: {"last_refresh": timestamp, "refresh_count": int, "daily": bool}}

_refresh_tracker: dict[str, dict] = {}
_refresh_lock = threading.Lock()
_REFRESH_COOLDOWN = 300  # 5 minutes minimum between refreshes
_DAILY_REFRESH_SECONDS = 86400  # 24 hours


def _get_refresh_state(provider_id: str) -> dict:
    with _refresh_lock:
        if provider_id not in _refresh_tracker:
            _refresh_tracker[provider_id] = {
                "last_refresh": 0.0,
                "refresh_count": 0,
                "daily_refreshed": False,
            }
        return _refresh_tracker[provider_id]


def _update_refresh_time(provider_id: str):
    with _refresh_lock:
        state = _refresh_tracker.get(provider_id, {})
        state["last_refresh"] = time.time()
        state["refresh_count"] = state.get("refresh_count", 0) + 1
        _refresh_tracker[provider_id] = state


def should_refresh(provider_id: str, force: bool = False) -> bool:
    """Check whether a model refresh is needed for this provider.

    Returns True when:
      - force=True
      - never refreshed before
      - last refresh older than cooldown (for on-error immediate refresh)
      - last refresh older than 24h (daily refresh)
    """
    if force:
        return True
    state = _get_refresh_state(provider_id)
    now = time.time()
    last = state.get("last_refresh", 0.0)
    if last == 0.0:
        return True  # never refreshed
    if now - last > _DAILY_REFRESH_SECONDS:
        return True  # stale daily refresh
    return False


# ── Model Lifecycle Manager ────────────────────────────────────────────────

class ModelLifecycleManager:
    """Central manager for model lifecycle operations.

    Provides model validation, deprecation detection, alias resolution,
    background refresh coordination, and health monitoring.
    """

    def __init__(self):
        self._deprecated: dict[str, dict[str, str]] = {}
        # {provider_id: {bad_model: replacement_model_or_none}}

    # ── Validation ─────────────────────────────────────────────────────

    def validate_model(self, provider_id: str, model: str) -> ValidationResult:
        """Check whether a model is valid, current, and available.

        Returns ValidationResult with:
          - valid=True if model is good to use
          - replacement set if an alias or upgrade path exists
          - retry_after_refresh=True if models are stale
        """
        if not model:
            return ValidationResult(
                valid=False, model=model,
                message="No model selected")

        # 1. Check if model is actively tracked as deprecated
        dep_map = self._deprecated.get(provider_id, {})
        if model in dep_map:
            replacement = dep_map[model]
            msg = (f"Model \"{model}\" has been deprecated"
                   + (f" \u2014 use \"{replacement}\" instead" if replacement else ""))
            _log(f"validate_model [{provider_id}] DEPRECATED: {model}"
                 + (f" -> {replacement}" if replacement else ""))
            return ValidationResult(
                valid=False, model=model, message=msg,
                replacement=replacement, retry_after_refresh=False)

        # 2. Check alias map (data-driven: model_metadata.json)
        alias_key = (provider_id, model)
        alias_map = _load_aliases()
        if alias_key in alias_map:
            replacement = alias_map[alias_key]
            _log(f"validate_model [{provider_id}] ALIAS: {model} -> {replacement}")
            return ValidationResult(
                valid=True, model=replacement,
                message=f"Model \"{model}\" aliased to \"{replacement}\"",
                replacement=replacement, retry_after_refresh=False)

        # 3. Check cache freshness
        try:
            from .provider_manager import get_cached_models
            cached = get_cached_models(provider_id)
            if cached is not None:
                if model in cached:
                    return ValidationResult(valid=True, model=model)
                # Model not in cached list — might be new or removed
                # Try refreshing if cache is old
                state = _get_refresh_state(provider_id)
                if time.time() - state.get("last_refresh", 0) > _REFRESH_COOLDOWN:
                    return ValidationResult(
                        valid=False, model=model,
                        message="Model not found in current registry",
                        retry_after_refresh=True)
        except Exception:
            pass

        # 4. No cache — model is unknown but could still work
        return ValidationResult(valid=True, model=model)

    def resolve_alias(self, provider_id: str, model: str) -> str:
        """Resolve model alias to its current name. Returns current model."""
        alias_key = (provider_id, model)
        return _load_aliases().get(alias_key, model)

    # ── Deprecation Handling ───────────────────────────────────────────

    def is_model_not_found_error(self, status_code: int, response_text: str) -> bool:
        """Heuristic check if an error response indicates a model lifecycle issue."""
        if status_code in (400, 404, 410):
            lower = response_text.lower()
            for pattern in _MODEL_NOT_FOUND_PATTERNS:
                if re.search(pattern, lower):
                    return True
        return False

    def handle_deprecation_error(
        self, provider_id: str, model: str,
        status_code: int, response_text: str
    ) -> RecoveryResult:
        """Handle a model-not-found error with automatic recovery.

        Steps:
          1. Refresh model list from provider
          2. If model reappears, keep it
          3. If model is gone, check alias map
          4. If alias exists, switch to alias
          5. If same-family model exists, suggest it
          6. Mark model as deprecated for future checks
        """
        _log(f"handle_deprecation [{provider_id}] model={model} "
             f"HTTP {status_code}: {response_text[:200]}")

        # Step 1: Refresh models
        try:
            from .provider_manager import discover_models, get_cached_models
            config = {"provider": provider_id, "base_url": "", "api_style": "openai"}
            refreshed = discover_models(provider_id, config)
            _log(f"handle_deprecation [{provider_id}] refreshed: {len(refreshed)} models")
        except Exception as e:
            _log(f"handle_deprecation [{provider_id}] refresh failed: {e}")
            refreshed = []

        # Step 2: Check if model reappeared
        if model in refreshed:
            _log(f"handle_deprecation [{provider_id}] {model} still available after refresh")
            return RecoveryResult(
                recovered=True, model=model,
                message=f"Model \"{model}\" confirmed available")

        # Step 3: Check alias
        replacement = self.resolve_alias(provider_id, model)
        if replacement != model:
            _log(f"handle_deprecation [{provider_id}] alias: {model} -> {replacement}")
            self._mark_deprecated(provider_id, model, replacement)
            return RecoveryResult(
                recovered=True, model=replacement,
                message=f"Model \"{model}\" aliased to \"{replacement}\"",
                new_model=replacement)

        # Step 4: Find same-family replacement from refreshed list
        from calc_terminal.models.registry import get_family
        family = get_family(model, provider_id)
        if family and refreshed:
            same_family = sorted([m for m in refreshed
                                  if get_family(m, provider_id) == family])
            if same_family:
                replacement = same_family[-1]  # pick newest in family
                _log(f"handle_deprecation [{provider_id}] family match: "
                     f"{family} -> {replacement}")
                self._mark_deprecated(provider_id, model, replacement)
                return RecoveryResult(
                    recovered=True, model=replacement,
                    message=f"Switched to \"{replacement}\" (same family: {family})",
                    new_model=replacement)

        # Step 5: Try provider default
        try:
            from .provider_manager import get_provider_class
            cls = get_provider_class(provider_id)
            replacement = cls.default_model() if cls else ""
            if cls and replacement:
                _log(f"handle_deprecation [{provider_id}] using default: {replacement}")
                self._mark_deprecated(provider_id, model, replacement)
                return RecoveryResult(
                    recovered=True, model=replacement,
                    message=f"Fell back to default model \"{replacement}\"",
                    new_model=replacement)
        except Exception:
            pass

        # Step 6: Pick first available model
        if refreshed:
            replacement = sorted(refreshed)[0]
            _log(f"handle_deprecation [{provider_id}] first available: {replacement}")
            self._mark_deprecated(provider_id, model, replacement)
            return RecoveryResult(
                recovered=True, model=replacement,
                message=f"Using first available model \"{replacement}\"",
                new_model=replacement)

        # Step 7: No recovery possible
        _log(f"handle_deprecation [{provider_id}] no recovery possible")
        return RecoveryResult(
            recovered=False, model=model,
            message=f"Model \"{model}\" is no longer available and no replacement found")

    def _mark_deprecated(self, provider_id: str, model: str, replacement: Optional[str] = None):
        """Track a deprecated model so future validate_model calls catch it fast."""
        if provider_id not in self._deprecated:
            self._deprecated[provider_id] = {}
        self._deprecated[provider_id][model] = replacement
        _log(f"deprecated [{provider_id}] tracked: {model}"
             + (f" -> {replacement}" if replacement else ""))

    def get_deprecated(self, provider_id: str) -> dict[str, Optional[str]]:
        """Get known deprecated models for a provider."""
        return dict(self._deprecated.get(provider_id, {}))

    # ── Pre-Request Check ─────────────────────────────────────────────

    def pre_request_check(self, provider_id: str, model: str) -> ValidationResult:
        """Complete pre-request validation with auto-recovery.

        Called before every chat/stream request.
        Validates the model, resolves aliases, triggers refresh if stale.
        """
        result = self.validate_model(provider_id, model)
        if result.valid:
            return result

        # If stale cache, refresh and re-validate
        if result.retry_after_refresh:
            _log(f"pre_request_check [{provider_id}] refreshing stale models")
            try:
                from .provider_manager import discover_models, set_cached_models
                config = {"provider": provider_id, "base_url": "", "api_style": "openai"}
                fresh = discover_models(provider_id, config)
                if fresh and model in fresh:
                    _update_refresh_time(provider_id)
                    return ValidationResult(valid=True, model=model,
                                            message="Model confirmed after refresh")
                if fresh and len(fresh) > 0:
                    # Model still not found — try deprecation recovery
                    recovery = self.handle_deprecation_error(
                        provider_id, model, 400,
                        "Model not found in refreshed registry")
                    if recovery.recovered and recovery.new_model:
                        _update_refresh_time(provider_id)
                        return ValidationResult(
                            valid=True, model=recovery.new_model,
                            message=recovery.message,
                            replacement=recovery.new_model)
            except Exception as e:
                _log(f"pre_request_check [{provider_id}] error during refresh: {e}")

        return result

    # ── Chat/Stream Wrappers ───────────────────────────────────────────

    def validate_and_chat(
        self, config: dict,
        prompt: str, system_prompt: str = "",
        history: Optional[list] = None
    ) -> str:
        """Wrapper around provider chat() that validates model first.

        If the model is deprecated/aliased, resolves it automatically.
        If the request fails with model-not-found, attempts recovery.
        """
        provider_id = config.get("provider", "")
        model = config.get("model", "")

        # Phase 1: Pre-request validation
        validation = self.pre_request_check(provider_id, model)
        if not validation.valid:
            return (f"[Model Error] {validation.message}")

        # Use resolved model
        resolved = validation.replacement or validation.model
        if resolved != model:
            config["model"] = resolved
            _log(f"validate_and_chat [{provider_id}] model resolved: {model} -> {resolved}")

        # Phase 2: Send request
        try:
            from .provider_manager import get_provider
            inst = get_provider(config)
            if not inst:
                return "AI not configured."
            response = inst.chat(prompt, system_prompt, history)
            return response
        except Exception as e:
            error_text = str(e)
            _log(f"validate_and_chat [{provider_id}] chat failed: {error_text}",
                 exc_info=True)

            # Phase 3: Check for model-not-found in exception
            if self.is_model_not_found_error(0, error_text):
                recovery = self.handle_deprecation_error(
                    provider_id, resolved, 0, error_text)
                if recovery.recovered and recovery.new_model:
                    config["model"] = recovery.new_model
                    _log(f"validate_and_chat [{provider_id}] retry with {recovery.new_model}")
                    try:
                        inst = get_provider(config)
                        if inst:
                            return (f"[Auto-recovered] {recovery.message}\n\n"
                                    + inst.chat(prompt, system_prompt, history))
                    except Exception:
                        pass
                return (f"[Model Error] {recovery.message}")

            return f"Error: {error_text}"

    def validate_and_stream(
        self, config: dict,
        prompt: str, system_prompt: str = "",
        history: Optional[list] = None
    ):
        """Wrapper around provider stream() that validates model first.

        Same lifecycle logic as validate_and_chat but yields text fragments.
        """
        provider_id = config.get("provider", "")
        model = config.get("model", "")

        validation = self.pre_request_check(provider_id, model)
        if not validation.valid:
            yield f"[Model Error] {validation.message}"
            return

        resolved = validation.replacement or validation.model
        if resolved != model:
            config["model"] = resolved
            _log(f"validate_and_stream [{provider_id}] model resolved: {model} -> {resolved}")

        try:
            from .provider_manager import get_provider
            inst = get_provider(config)
            if not inst:
                yield "AI not configured."
                return
            yield from inst.stream(prompt, system_prompt, history)
        except Exception as e:
            error_text = str(e)
            _log(f"validate_and_stream [{provider_id}] stream failed: {error_text}",
                 exc_info=True)

            if self.is_model_not_found_error(0, error_text):
                recovery = self.handle_deprecation_error(
                    provider_id, resolved, 0, error_text)
                if recovery.recovered and recovery.new_model:
                    config["model"] = recovery.new_model
                    yield f"\n[Auto-recovered] {recovery.message}\n"
                    try:
                        inst = get_provider(config)
                        if inst:
                            yield from inst.stream(prompt, system_prompt, history)
                            return
                    except Exception:
                        pass
                yield f"\n[Model Error] {recovery.message}"
            else:
                yield f"Error: {error_text}"

    # ── Health Monitoring ─────────────────────────────────────────────

    def check_health(self, provider_id: str,
                     config: Optional[dict] = None) -> ProviderHealth:
        """Check provider health: reachability, auth, model listing, chat.

        Returns a ProviderHealth dataclass with detailed status.
        """
        health = ProviderHealth(provider_id=provider_id, last_checked=time.time())

        if not config:
            try:
                from .provider_manager import load_config
                cfg = load_config()
                config = cfg
            except Exception:
                health.error = "No config available"
                return health

        cfg = dict(config) if config else {}
        cfg["provider"] = provider_id
        start = time.time()

        try:
            from .provider_manager import get_provider, get_provider_class
            from .provider_manager import get_cached_models, discover_models

            cls = get_provider_class(provider_id)
            has_class = cls is not None

            # Try to instantiate provider
            inst = get_provider(cfg)
            if inst:
                health.api_reachable = True
                health.chat_supported = True

                # Auth check via model fetch
                try:
                    models = inst.fetch_models()
                    if models:
                        health.authenticated = True
                        health.model_list_available = True
                    else:
                        health.authenticated = False
                        health.error = "Model list empty (auth may be missing)"
                except Exception as auth_e:
                    health.error = str(auth_e)
                    health.authenticated = False

            elif has_class:
                health.error = "Provider class found but instantiation failed"
            else:
                # Generic provider — try HTTP reachability
                base_url = cfg.get("base_url", "")
                if base_url:
                    import requests
                    try:
                        resp = requests.get(f"{base_url.rstrip('/')}/models",
                                            timeout=5)
                        health.api_reachable = resp.status_code < 500
                        health.authenticated = resp.status_code not in (401, 403)
                        health.model_list_available = resp.status_code == 200
                    except Exception as e:
                        health.error = str(e)
                        health.api_reachable = False

            health.online = health.api_reachable
            health.latency_ms = round((time.time() - start) * 1000)

        except Exception as e:
            health.error = str(e)
            _log(f"check_health [{provider_id}] failed: {e}", exc_info=True)

        # Update refresh tracker
        _update_refresh_time(provider_id)
        return health

    # ── Background Refresh ────────────────────────────────────────────

    def ensure_fresh_models(self, provider_id: str,
                            config: Optional[dict] = None,
                            force: bool = False) -> list[str]:
        """Ensure models are fresh — refresh if needed.

        Called on provider creation, first use, or manually.
        """
        if not should_refresh(provider_id, force=force):
            try:
                from .provider_manager import get_cached_models
                cached = get_cached_models(provider_id)
                if cached is not None:
                    return cached
            except Exception:
                pass

        cfg = config or {"provider": provider_id, "base_url": "", "api_style": "openai"}
        cfg["provider"] = provider_id

        try:
            from .provider_manager import discover_models
            models = discover_models(provider_id, cfg)
            _update_refresh_time(provider_id)
            _log(f"ensure_fresh_models [{provider_id}]: {len(models)} models "
                 f"({'cached' if not force else 'forced'})")
            return models or []
        except Exception as e:
            _log(f"ensure_fresh_models [{provider_id}] failed: {e}")
            return []


# ── Singleton ──────────────────────────────────────────────────────────────

_instance: Optional[ModelLifecycleManager] = None
_lock = threading.Lock()


def get_lifecycle() -> ModelLifecycleManager:
    """Get the shared ModelLifecycleManager singleton."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ModelLifecycleManager()
    return _instance


# ── Convenience Functions ──────────────────────────────────────────────────

def validate_model(provider_id: str, model: str) -> ValidationResult:
    return get_lifecycle().validate_model(provider_id, model)


def pre_request_check(provider_id: str, model: str) -> ValidationResult:
    return get_lifecycle().pre_request_check(provider_id, model)


def resolve_alias(provider_id: str, model: str) -> str:
    return get_lifecycle().resolve_alias(provider_id, model)


def handle_deprecation_error(provider_id: str, model: str,
                              status_code: int, response_text: str) -> RecoveryResult:
    return get_lifecycle().handle_deprecation_error(
        provider_id, model, status_code, response_text)


def validate_and_chat(config: dict, prompt: str, system_prompt: str = "",
                       history: Optional[list] = None) -> str:
    return get_lifecycle().validate_and_chat(config, prompt, system_prompt, history)


def validate_and_stream(config: dict, prompt: str, system_prompt: str = "",
                         history: Optional[list] = None):
    return get_lifecycle().validate_and_stream(config, prompt, system_prompt, history)


def check_health(provider_id: str, config: Optional[dict] = None) -> ProviderHealth:
    return get_lifecycle().check_health(provider_id, config)


def ensure_fresh_models(provider_id: str, config: Optional[dict] = None,
                         force: bool = False) -> list[str]:
    return get_lifecycle().ensure_fresh_models(provider_id, config, force=force)


def get_deprecated_models(provider_id: str) -> dict[str, Optional[str]]:
    return get_lifecycle().get_deprecated(provider_id)
