"""
CAT — Backup Provider & Resilience System: Circuit Breaker
Author: Kazi Zillani

Prevents CAT from wasting precious seconds or burning rate limits on broken,
unreachable, or rate-limited AI endpoints.
"""

import threading
import time
from typing import Dict, Optional, Tuple


class CircuitBreakerState:
    CLOSED = "closed"        # Normal operation: requests pass through
    OPEN = "open"            # Tripped: requests fail immediately to prevent stalls
    HALF_OPEN = "half_open"  # Cooldown expired: single probe attempt allowed


class CircuitBreaker:
    """Per-endpoint circuit breaker guarding providers and models."""

    def __init__(
        self,
        failure_threshold: int = 3,
        default_cooldown: float = 30.0,
        rate_limit_cooldown: float = 60.0,
    ):
        self.failure_threshold = max(1, failure_threshold)
        self.default_cooldown = max(0.01, default_cooldown)
        self.rate_limit_cooldown = max(0.01, rate_limit_cooldown)
        self._lock = threading.Lock()
        # (provider, model) -> dict
        self._endpoints: Dict[Tuple[str, str], dict] = {}

    def _key(self, provider: str, model: str) -> Tuple[str, str]:
        return (str(provider or "").strip().lower(), str(model or "").strip().lower())

    def _get_record(self, provider: str, model: str) -> dict:
        k = self._key(provider, model)
        if k not in self._endpoints:
            self._endpoints[k] = {
                "state": CircuitBreakerState.CLOSED,
                "consecutive_failures": 0,
                "cooldown_until": 0.0,
                "last_failure_ts": 0.0,
                "last_success_ts": 0.0,
                "last_error": "",
                "probe_in_flight": False,
            }
        return self._endpoints[k]

    def can_attempt(self, provider: str, model: str) -> bool:
        """True if the endpoint is allowed to receive a request."""
        with self._lock:
            rec = self._get_record(provider, model)
            now = time.time()
            state = rec["state"]

            if state == CircuitBreakerState.CLOSED:
                return True

            if state == CircuitBreakerState.OPEN:
                if now >= rec["cooldown_until"]:
                    # Cooldown elapsed -> transition to half_open for a probe
                    rec["state"] = CircuitBreakerState.HALF_OPEN
                    rec["probe_in_flight"] = True
                    return True
                return False

            if state == CircuitBreakerState.HALF_OPEN:
                # Only allow one probe at a time
                if not rec["probe_in_flight"]:
                    rec["probe_in_flight"] = True
                    return True
                return False

            return True

    def record_success(self, provider: str, model: str, latency_ms: Optional[float] = None) -> None:
        """Reset breaker to CLOSED upon a successful turn."""
        with self._lock:
            rec = self._get_record(provider, model)
            rec["state"] = CircuitBreakerState.CLOSED
            rec["consecutive_failures"] = 0
            rec["cooldown_until"] = 0.0
            rec["last_success_ts"] = time.time()
            rec["probe_in_flight"] = False

    def record_failure(
        self,
        provider: str,
        model: str,
        error: str = "",
        is_rate_limit: bool = False,
        cooldown_seconds: Optional[float] = None,
    ) -> None:
        """Increment failure counter and trip breaker if threshold exceeded."""
        with self._lock:
            rec = self._get_record(provider, model)
            rec["consecutive_failures"] += 1
            now = time.time()
            rec["last_failure_ts"] = now
            rec["last_error"] = str(error)[:160]
            rec["probe_in_flight"] = False

            cooldown = cooldown_seconds or (
                self.rate_limit_cooldown if is_rate_limit else self.default_cooldown
            )

            # In HALF_OPEN, any failure immediately trips back to OPEN with full cooldown
            if rec["state"] == CircuitBreakerState.HALF_OPEN:
                rec["state"] = CircuitBreakerState.OPEN
                rec["cooldown_until"] = now + cooldown
            elif is_rate_limit or rec["consecutive_failures"] >= self.failure_threshold:
                rec["state"] = CircuitBreakerState.OPEN
                rec["cooldown_until"] = now + cooldown

    def get_state(self, provider: str, model: str) -> str:
        """Return current breaker state string."""
        with self._lock:
            rec = self._get_record(provider, model)
            now = time.time()
            if rec["state"] == CircuitBreakerState.OPEN and now >= rec["cooldown_until"]:
                return CircuitBreakerState.HALF_OPEN
            return rec["state"]

    def is_in_cooldown(self, provider: str, model: str) -> bool:
        """True if the endpoint is strictly barred by an active cooldown."""
        with self._lock:
            rec = self._get_record(provider, model)
            return rec["state"] == CircuitBreakerState.OPEN and time.time() < rec["cooldown_until"]

    def reset(self, provider: str, model: str) -> None:
        with self._lock:
            rec = self._get_record(provider, model)
            rec["state"] = CircuitBreakerState.CLOSED
            rec["consecutive_failures"] = 0
            rec["cooldown_until"] = 0.0
            rec["probe_in_flight"] = False

    def reset_all(self) -> None:
        with self._lock:
            for rec in self._endpoints.values():
                rec["state"] = CircuitBreakerState.CLOSED
                rec["consecutive_failures"] = 0
                rec["cooldown_until"] = 0.0
                rec["probe_in_flight"] = False


_GLOBAL_BREAKER: Optional[CircuitBreaker] = None


def get_circuit_breaker() -> CircuitBreaker:
    global _GLOBAL_BREAKER
    if _GLOBAL_BREAKER is None:
        _GLOBAL_BREAKER = CircuitBreaker()
    return _GLOBAL_BREAKER
