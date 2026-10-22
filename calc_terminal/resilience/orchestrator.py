"""
CAT — Backup Provider & Resilience System: Unified AI Orchestrator
Author: Kazi Zillani

The central orchestrator coordinating AI provider access across CAT's entire
architecture: Chat, Coding Agent, IDE Agent, Tools, Browser Agent, and Live Preview.
"""

import logging
import time
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

from .agent_state import AgentTaskState
from .circuit_breaker import get_circuit_breaker
from .failover_engine import get_failover_engine
from .health_monitor import get_health_monitor, sanitize_error
from .ollama_adapter import get_ollama_adapter
from .types import CandidateTarget, CostPolicy, FailureType, SecurityLevel, TaskRequirements

_LOG = logging.getLogger(__name__)


class AIOrchestrator:
    """Master AI Orchestration & Resilience Core for CAT."""

    def __init__(self):
        self.engine = get_failover_engine()
        self.health_monitor = get_health_monitor()
        self.circuit_breaker = get_circuit_breaker()
        self.ollama = get_ollama_adapter()
        self.security_level = SecurityLevel.BALANCED
        self.cost_policy = CostPolicy.ANY
        self._failover_callbacks: List[Callable[[str], None]] = []

    def add_failover_listener(self, callback: Callable[[str], None]) -> None:
        """Register a callback to receive user-facing failover announcements."""
        if callback not in self._failover_callbacks:
            self._failover_callbacks.append(callback)

    def remove_failover_listener(self, callback: Callable[[str], None]) -> None:
        if callback in self._failover_callbacks:
            self._failover_callbacks.remove(callback)

    def notify_failover(self, message: str) -> None:
        for cb in self._failover_callbacks:
            try:
                cb(message)
            except Exception:
                pass

    def get_privacy_policy(self) -> str:
        try:
            from ..model_router import get_privacy_policy
            return get_privacy_policy()
        except Exception:
            return "local_first"

    def set_privacy_policy(self, policy: str) -> None:
        try:
            from ..model_router import set_privacy_policy
            set_privacy_policy(policy)
        except Exception:
            pass

    def enable_emergency_offline_mode(self) -> Tuple[bool, str]:
        """Switch CAT to local-only emergency mode: zero cloud, Ollama primary."""
        self.set_privacy_policy("never_cloud")
        self.cost_policy = CostPolicy.LOCAL_ONLY
        is_ollama_ready = self.ollama.is_available()
        models = self.ollama.get_model_names() if is_ollama_ready else []

        if is_ollama_ready and models:
            msg = f"Offline Local Mode active. Local Ollama available ({len(models)} models: {', '.join(models[:3])})."
            return True, msg
        elif is_ollama_ready:
            msg = "Offline Local Mode active. Local Ollama daemon running, but no models found (run `cat models pull <name>`)."
            return True, msg
        else:
            msg = "Offline Local Mode active. Cloud disabled. Note: Local Ollama is not currently detected at localhost:11434."
            return False, msg

    def build_targets(
        self,
        primary_config: Optional[dict] = None,
        requirements: Optional[TaskRequirements] = None,
    ) -> List[CandidateTarget]:
        """Resolve ordered list of capable, allowed candidate targets."""
        try:
            from .. import aicore
            prim = dict(primary_config or aicore.load_config() or {})
        except Exception:
            prim = dict(primary_config or {})

        return self.engine.build_failover_targets(
            primary_config=prim,
            requirements=requirements or TaskRequirements(),
            privacy_policy=self.get_privacy_policy(),
            cost_policy=self.cost_policy,
            security_level=self.security_level,
        )

    def execute_query(
        self,
        prompt: str,
        system_prompt: str = "",
        history: Optional[List] = None,
        attachments: Optional[List] = None,
        requirements: Optional[TaskRequirements] = None,
        config: Optional[dict] = None,
        on_failover: Optional[Callable[[str], None]] = None,
        size_class: str = "normal",
    ) -> str:
        """Execute chat/generation turn with resilient automatic failover."""
        targets = self.build_targets(primary_config=config, requirements=requirements)
        if not targets:
            return "No eligible AI providers available for this task under current privacy and capability settings."

        from ..aicore import (
            _attempts_per_provider,
            _backoff_sleep,
            _mark_backup_success,
            _query_ai_once,
            _short_id,
            log_request_event,
        )

        last_result = ""
        max_attempts = _attempts_per_provider()
        fallback_used = False

        for t_idx, target in enumerate(targets):
            cfg = target.config
            provider = target.provider
            model = target.model

            self.health_monitor.record_turn_start(provider, model)
            t_start = time.time()

            for attempt in range(max_attempts):
                if attempt > 0:
                    log_request_event(
                        _short_id(), "retry_same_provider",
                        provider=provider, model=model,
                        size_class=size_class, retry_count=attempt
                    )

                last_result = _query_ai_once(
                    prompt,
                    system_prompt=system_prompt,
                    history=history,
                    config=cfg,
                    attachments=attachments,
                    size_class=size_class,
                )

                if not self.engine.should_failover(last_result):
                    elapsed_ms = (time.time() - t_start) * 1000.0
                    self.health_monitor.record_success(provider, model, latency_ms=elapsed_ms)
                    if target.is_backup and target.entry:
                        _mark_backup_success(target.entry)
                        self.notify_failover(f"✓ Connected to backup ({provider}/{model}).")
                        if on_failover:
                            on_failover(f"✓ Connected to backup ({provider}/{model}).")

                    log_request_event(
                        _short_id(), "finish",
                        provider=provider, model=model,
                        size_class=size_class, chars=len(last_result),
                        fallback=fallback_used
                    )
                    return last_result

                # Classify failure
                ftype = self.engine.classify_failure(last_result)
                is_rate_limit = ftype == FailureType.RATE_LIMIT

                if attempt + 1 < max_attempts and self.engine.is_retryable(ftype):
                    log_request_event(
                        _short_id(), "attempt_failed_retryable",
                        provider=provider, detail=last_result[:120],
                        size_class=size_class
                    )
                    _backoff_sleep(attempt)
                    continue

                # Non-retryable or retries exhausted
                self.health_monitor.record_failure(
                    provider, model, error_message=last_result, is_rate_limit=is_rate_limit
                )
                break

            # Failover to next target
            if t_idx + 1 < len(targets):
                fallback_used = True
                nxt = targets[t_idx + 1]
                cur_desc = f"{provider} ({model})"
                nxt_desc = f"{nxt.provider} ({nxt.model})"
                msg = f"⚠ Provider issue with {cur_desc}. Switching to {'Model Fallback' if nxt.tier == 1 else 'Backup Provider'} ({nxt_desc})..."
                self.notify_failover(msg)
                if on_failover:
                    on_failover(msg)

        return last_result or "All configured AI providers failed to respond."

    def execute_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        history: Optional[List] = None,
        attachments: Optional[List] = None,
        requirements: Optional[TaskRequirements] = None,
        config: Optional[dict] = None,
        on_failover: Optional[Callable[[str], None]] = None,
        size_class: str = "normal",
    ) -> Generator[str, None, None]:
        """Stream response fragments with automatic failover if first chunk fails."""
        targets = self.build_targets(primary_config=config, requirements=requirements)
        if not targets:
            yield "No eligible AI providers available for this task."
            return

        from ..aicore import (
            _attempts_per_provider,
            _backoff_sleep,
            _mark_backup_success,
            _peek_first,
            _stream_ai_once,
        )

        last_err = ""
        max_attempts = _attempts_per_provider()

        for t_idx, target in enumerate(targets):
            cfg = target.config
            provider = target.provider
            model = target.model

            self.health_monitor.record_turn_start(provider, model)
            t_start = time.time()

            for attempt in range(max_attempts):
                gen = _stream_ai_once(
                    prompt,
                    system_prompt=system_prompt,
                    history=history,
                    config=cfg,
                    attachments=attachments,
                    size_class=size_class,
                )
                first, rest = _peek_first(gen)

                if first is None:
                    last_err = "No output produced by AI provider."
                    continue

                if not self.engine.should_failover(first):
                    elapsed_ms = (time.time() - t_start) * 1000.0
                    self.health_monitor.record_success(provider, model, latency_ms=elapsed_ms)
                    if target.is_backup and target.entry:
                        _mark_backup_success(target.entry)
                    yield first
                    yield from rest
                    return

                # First chunk indicates failure
                last_err = first
                ftype = self.engine.classify_failure(first)
                is_rate_limit = ftype == FailureType.RATE_LIMIT

                if attempt + 1 < max_attempts and self.engine.is_retryable(ftype):
                    _backoff_sleep(attempt)
                    continue

                self.health_monitor.record_failure(
                    provider, model, error_message=first, is_rate_limit=is_rate_limit
                )
                break

            if t_idx + 1 < len(targets):
                nxt = targets[t_idx + 1]
                msg = f"⚠ Switching provider from {provider}/{model} to {nxt.provider}/{nxt.model}..."
                self.notify_failover(msg)
                if on_failover:
                    on_failover(msg)

        yield last_err or "All configured AI providers failed."

    def test_provider(self, config: dict) -> Tuple[bool, str, List[str]]:
        """Verify connectivity, model availability, and response latency."""
        from ..providers import provider_manager as pm
        start = time.time()
        ok, msg, models = pm.connect_provider(config)
        elapsed_ms = (time.time() - start) * 1000.0

        prov = config.get("provider", "?")
        model = config.get("model", "")
        if ok:
            self.health_monitor.record_success(prov, model, latency_ms=elapsed_ms)
        else:
            self.health_monitor.record_failure(prov, model, error_message=msg)

        return ok, sanitize_error(msg), models


_GLOBAL_ORCHESTRATOR: Optional[AIOrchestrator] = None


def get_orchestrator() -> AIOrchestrator:
    global _GLOBAL_ORCHESTRATOR
    if _GLOBAL_ORCHESTRATOR is None:
        _GLOBAL_ORCHESTRATOR = AIOrchestrator()
    return _GLOBAL_ORCHESTRATOR
