"""
CAT — Backup Provider & Resilience System: Health Monitor
Author: Kazi Zillani

Lightweight, real-time provider and model health tracking based on actual
CAT observations. Strictly guarantees ZERO credential exposure.
"""

import re
import threading
import time
from typing import Dict, List, Optional, Tuple

from .circuit_breaker import CircuitBreakerState, get_circuit_breaker
from .types import ProviderHealthState

_KEY_CLEAN_RE = re.compile(r"(sk-[a-zA-Z0-9_\-]{8,}|gsk_[a-zA-Z0-9_\-]{8,}|AIzaSy[a-zA-Z0-9_\-]{8,}|[a-f0-9]{32,})", re.I)


def sanitize_error(text: str) -> str:
    """Mask any API keys, credentials, or auth tokens from error strings."""
    if not text or not isinstance(text, str):
        return ""
    cleaned = _KEY_CLEAN_RE.sub("[CREDENTIAL_REDACTED]", text)
    # Remove authorization headers or token params if present
    cleaned = re.sub(
        r"((?:authorization[:=]\s*)?bearer\s+|api[_\-\s]?key[:=\s]+|authorization[:=]\s*)['\"]?[a-zA-Z0-9_\.\-]+['\"]?",
        r"\1[REDACTED]",
        cleaned,
        flags=re.I,
    )
    return cleaned[:200]


class HealthMonitor:
    """Central registry of observable AI health state across CAT."""

    def __init__(self):
        self._lock = threading.Lock()
        # (provider, model) -> ProviderHealthState
        self._states: Dict[Tuple[str, str], ProviderHealthState] = {}
        self._breaker = get_circuit_breaker()

    def _key(self, provider: str, model: str) -> Tuple[str, str]:
        return (str(provider or "").strip().lower(), str(model or "").strip().lower())

    def record_turn_start(self, provider: str, model: str) -> None:
        """Mark turn attempt initiation."""
        with self._lock:
            k = self._key(provider, model)
            if k not in self._states:
                self._states[k] = ProviderHealthState(provider=provider, model=model)
            self._states[k].last_checked = time.time()

    def record_success(self, provider: str, model: str, latency_ms: Optional[float] = None) -> None:
        """Record successful inference turn."""
        p_low = str(provider or "").strip().lower()
        is_local = p_low in ("ollama", "local", "vllm")
        now = time.time()

        with self._lock:
            k = self._key(provider, model)
            state = self._states.get(k)
            if not state:
                state = ProviderHealthState(provider=provider, model=model)
                self._states[k] = state

            state.last_success = now
            state.last_checked = now
            state.consecutive_failures = 0
            state.success_count += 1
            state.circuit_open = False
            state.cooldown_until = 0.0

            if latency_ms is not None:
                if state.latency_ms is None:
                    state.latency_ms = latency_ms
                else:
                    # Exponential smoothing
                    state.latency_ms = round(0.7 * latency_ms + 0.3 * state.latency_ms, 1)

            if is_local:
                state.status = "local"
            elif state.latency_ms and state.latency_ms > 3500.0:
                state.status = "slow"
            else:
                state.status = "healthy"

        self._breaker.record_success(provider, model, latency_ms)

    def record_failure(
        self,
        provider: str,
        model: str,
        error_message: str = "",
        is_rate_limit: bool = False,
        cooldown_seconds: Optional[float] = None,
    ) -> None:
        """Record a failure without leaking any credential details."""
        now = time.time()
        safe_msg = sanitize_error(error_message)

        with self._lock:
            k = self._key(provider, model)
            state = self._states.get(k)
            if not state:
                state = ProviderHealthState(provider=provider, model=model)
                self._states[k] = state

            state.last_checked = now
            state.consecutive_failures += 1
            state.failure_count += 1
            state.last_error = safe_msg

            if is_rate_limit:
                state.status = "rate_limited"
                cd = cooldown_seconds or 60.0
                state.cooldown_until = now + cd
                state.circuit_open = True
            else:
                if state.consecutive_failures >= self._breaker.failure_threshold:
                    state.status = "offline"
                    cd = cooldown_seconds or self._breaker.default_cooldown
                    state.cooldown_until = now + cd
                    state.circuit_open = True
                else:
                    state.status = "slow"

        self._breaker.record_failure(
            provider,
            model,
            error=safe_msg,
            is_rate_limit=is_rate_limit,
            cooldown_seconds=cooldown_seconds,
        )

    def get_health(self, provider: str, model: str) -> ProviderHealthState:
        """Retrieve the health record for a provider/model."""
        with self._lock:
            k = self._key(provider, model)
            state = self._states.get(k)
            if not state:
                p_low = str(provider or "").strip().lower()
                is_local = p_low in ("ollama", "local", "vllm")
                state = ProviderHealthState(
                    provider=provider,
                    model=model,
                    status="local" if is_local else "disconnected",
                )
                self._states[k] = state
            # Synchronize breaker status
            breaker_state = self._breaker.get_state(provider, model)
            state.circuit_open = breaker_state in (CircuitBreakerState.OPEN,)
            return state

    def is_healthy(self, provider: str, model: str) -> bool:
        """Check if an endpoint is usable."""
        if not self._breaker.can_attempt(provider, model):
            return False
        st = self.get_health(provider, model)
        return st.status not in ("offline", "rate_limited") or not st.circuit_open

    def all_states(self) -> List[ProviderHealthState]:
        """Return a snapshot list of all tracked health records."""
        with self._lock:
            return list(self._states.values())

    def get_status_badge(self, provider: str, model: str) -> Tuple[str, str]:
        """Return (glyph, label) representation (e.g. ('🟢', 'Healthy'))."""
        st = self.get_health(provider, model)
        status = st.status
        if status == "local":
            return ("🟢", "Local")
        elif status == "healthy":
            return ("🟢", "Healthy")
        elif status == "slow":
            return ("🟡", "Slow")
        elif status == "rate_limited":
            return ("🟠", "Rate Limited")
        elif status == "offline":
            return ("🔴", "In Cooldown")
        return ("⚫", "Disconnected")


_GLOBAL_MONITOR: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    global _GLOBAL_MONITOR
    if _GLOBAL_MONITOR is None:
        _GLOBAL_MONITOR = HealthMonitor()
    return _GLOBAL_MONITOR
