"""
CAT — Backup Provider & Resilience System: Failover Engine
Author: Kazi Zillani

Handles intelligent error classification and two-tier failover orchestration:
- Tier 1: Alternate fallback models within the SAME provider.
- Tier 2: Priority-ordered backup providers from the dynamic backup pool.
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from .capability_matcher import get_capability_matcher
from .health_monitor import get_health_monitor, sanitize_error
from .types import CandidateTarget, CostPolicy, FailureType, SecurityLevel, TaskRequirements

_LOG = logging.getLogger(__name__)

# Error pattern classifiers
_RATE_LIMIT_HINTS = (
    "rate limit", "rate_limit", "429", "too many requests", "resource has been exhausted",
    "insufficient_quota", "quota exceeded", "exceeded your current quota", "tokens per minute",
    "requests per minute", "tpm limit", "rpm limit",
)

_AUTH_HINTS = (
    "401", "403", "unauthorized", "api key", "invalid api key", "authentication failed",
    "forbidden", "permission denied", "invalid token", "bad api key",
)

_MODEL_UNAVAILABLE_HINTS = (
    "model not found", "does not exist", "model unavailable", "not loaded", "no such model",
    "404", "model_not_found", "unknown model", "deprecated",
)

_CONTEXT_HINTS = (
    "maximum context length", "context length exceeded", "too many tokens",
    "token limit", "prompt is too long", "exceeds maximum context",
)

_TRANSIENT_HINTS = (
    "timed out", "timeout", "connection reset", "connection refused", "connection aborted",
    "broken pipe", "server disconnected", "502", "503", "504", "bad gateway",
    "service unavailable", "remote end closed", "incomplete read",
)

_SERVER_ERROR_HINTS = (
    "500", "internal server error", "server error", "backend error",
)


class FailoverEngine:
    """Classifies provider failures and generates optimal two-tier candidate targets."""

    def __init__(self):
        self.matcher = get_capability_matcher()
        self.health_monitor = get_health_monitor()

    def classify_failure(self, error_text: str, status_code: Optional[int] = None) -> FailureType:
        """Classify raw error message or HTTP response into standardized FailureType."""
        if not error_text and not status_code:
            return FailureType.UNKNOWN

        code = status_code or 0
        if code == 429:
            return FailureType.RATE_LIMIT
        if code in (401, 403):
            return FailureType.AUTH_FAILURE
        if code == 404:
            return FailureType.MODEL_UNAVAILABLE
        if code in (502, 503, 504):
            return FailureType.TRANSIENT
        if code == 500:
            return FailureType.SERVER_ERROR

        low = (error_text or "").lower()

        if any(h in low for h in _RATE_LIMIT_HINTS):
            return FailureType.RATE_LIMIT
        if any(h in low for h in _AUTH_HINTS):
            return FailureType.AUTH_FAILURE
        if any(h in low for h in _MODEL_UNAVAILABLE_HINTS):
            return FailureType.MODEL_UNAVAILABLE
        if any(h in low for h in _CONTEXT_HINTS):
            return FailureType.CONTEXT_TOO_LARGE
        if any(h in low for h in _TRANSIENT_HINTS):
            return FailureType.TRANSIENT
        if any(h in low for h in _SERVER_ERROR_HINTS):
            return FailureType.SERVER_ERROR

        return FailureType.UNKNOWN

    def is_retryable(self, failure_type: FailureType) -> bool:
        """True if failure is transient and warrants an immediate backoff retry on same model."""
        return failure_type in (FailureType.TRANSIENT, FailureType.TIMEOUT)

    def should_failover(self, result_text: str) -> bool:
        """True if the assistant response represents an error needing failover."""
        if not result_text or not isinstance(result_text, str):
            return True
        if not result_text.strip():
            return True

        from ..aicore import is_error_response
        if is_error_response(result_text):
            return True

        ftype = self.classify_failure(result_text)
        return ftype != FailureType.UNKNOWN

    def get_provider_fallback_models(self, provider_id: str) -> List[str]:
        """Fetch alternative models configured for the given provider.
        For local providers like Ollama, dynamically checks actually-installed
        models so non-existent catalog entries never cause failover loops."""
        try:
            pid = str(provider_id or "").strip().lower()
            if pid == "ollama":
                try:
                    from ..providers.adapters.ollama_adapter import OllamaAdapter
                    adapter = OllamaAdapter()
                    live = adapter.discover_models(timeout=1.5)
                    if live:
                        installed = []
                        for m in live:
                            mid = str(getattr(m, "model_id", "") or "").strip()
                            if mid and mid not in installed:
                                installed.append(mid)
                        if installed:
                            return installed
                except Exception:
                    pass
            from ..models.manager import get_provider
            prov = get_provider(provider_id)
            if prov and prov.get("fallback_models"):
                return [str(m).strip() for m in prov["fallback_models"] if str(m).strip()]
        except Exception:
            pass
        return []

    def build_failover_targets(
        self,
        primary_config: dict,
        requirements: Optional[TaskRequirements] = None,
        privacy_policy: str = "local_first",
        cost_policy: CostPolicy = CostPolicy.ANY,
        security_level: SecurityLevel = SecurityLevel.BALANCED,
    ) -> List[CandidateTarget]:
        """Build the complete, two-tier failover walk:
        Tier 1: Primary provider (active model, then alternative models on same provider).
        Tier 2: Backup pool providers in configured priority order.
        """
        req = requirements or TaskRequirements()
        targets: List[CandidateTarget] = []
        seen_endpoints = set()

        def _add_target(cfg: dict, entry: Optional[dict], is_backup: bool, tier: int):
            prov = str(cfg.get("provider") or "").strip().lower()
            model = str(cfg.get("model") or "").strip()
            if not prov or not model:
                return
            key = (prov, model)
            if key in seen_endpoints:
                return

            candidate = self.matcher.evaluate_target(
                config=cfg,
                requirements=req,
                privacy_policy=privacy_policy,
                cost_policy=cost_policy,
                security_level=security_level,
                entry=entry,
                is_backup=is_backup,
                tier=tier,
            )
            if candidate:
                targets.append(candidate)
                seen_endpoints.add(key)

        # 1. Primary endpoint
        prim = dict(primary_config or {})
        prim_prov = str(prim.get("provider") or "").strip().lower()
        if prim_prov:
            # Ensure API key resolved
            if not (prim.get("api_key") or "").strip():
                try:
                    from ..providers.provider_manager import get_env_api_key
                    k = get_env_api_key(prim_prov)
                    if k:
                        prim["api_key"] = k
                except Exception:
                    pass
            _add_target(prim, entry=None, is_backup=False, tier=1)

            # Tier 1 Fallback Models on the SAME provider (capped to at most 2 to avoid cascading hangs)
            fb_models = self.get_provider_fallback_models(prim_prov)
            for fb_model in fb_models[:2]:
                if fb_model.lower() != str(prim.get("model", "")).lower():
                    tier1_cfg = dict(prim)
                    tier1_cfg["model"] = fb_model
                    _add_target(tier1_cfg, entry=None, is_backup=False, tier=1)

        # 2. Tier 2: Dynamic Backup Pool
        try:
            from ..providers.provider_manager import backup_configs
            for bcfg, entry in backup_configs():
                _add_target(bcfg, entry=entry, is_backup=True, tier=2)
        except Exception as e:
            _LOG.debug("Error loading backup configs: %s", e)

        # If strict security, only allow explicitly configured backup providers
        if security_level == SecurityLevel.STRICT:
            targets = [t for t in targets if not t.is_backup or (t.entry and t.entry.get("enabled"))]

        # Prioritize fresh endpoints over endpoints recently in cooldown
        fresh = [t for t in targets if self.health_monitor.is_healthy(t.provider, t.model)]
        demoted = [t for t in targets if t not in fresh]

        return fresh + demoted


_GLOBAL_ENGINE: Optional[FailoverEngine] = None


def get_failover_engine() -> FailoverEngine:
    global _GLOBAL_ENGINE
    if _GLOBAL_ENGINE is None:
        _GLOBAL_ENGINE = FailoverEngine()
    return _GLOBAL_ENGINE
