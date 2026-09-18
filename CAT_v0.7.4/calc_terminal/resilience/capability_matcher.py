"""
CAT — Backup Provider & Resilience System: Capability Matcher
Author: Kazi Zillani

Ensures backup selection is intelligent rather than sequential:
Compares Task Requirements + Provider Capabilities + Privacy Policy + Cost Policy
to select only backups that can actually perform the user's task.
"""

from typing import Any, Dict, List, Optional, Tuple

from ..model_router import (
    POLICY_BEST_AVAILABLE,
    POLICY_CLOUD_FIRST,
    POLICY_LOCAL_FIRST,
    POLICY_NEVER_CLOUD,
    ModelCapabilities,
    _capabilities_for,
)
from .health_monitor import get_health_monitor
from .types import CandidateTarget, CostPolicy, SecurityLevel, TaskRequirements


class CapabilityMatcher:
    """Matches task requirements against candidate provider/model endpoints."""

    def __init__(self):
        self.health_monitor = get_health_monitor()

    def is_local_provider(self, provider: str) -> bool:
        return str(provider or "").strip().lower() in ("ollama", "local", "vllm", "llamacpp")

    def is_free_provider(self, provider: str, model: str = "") -> bool:
        p_low = str(provider or "").strip().lower()
        if self.is_local_provider(p_low):
            return True
        # Free cloud providers/tiers
        if p_low in ("groq", "cerebras", "gemini"):
            return True
        return False

    def evaluate_target(
        self,
        config: dict,
        requirements: TaskRequirements,
        privacy_policy: str = POLICY_LOCAL_FIRST,
        cost_policy: CostPolicy = CostPolicy.ANY,
        security_level: SecurityLevel = SecurityLevel.BALANCED,
        entry: Optional[dict] = None,
        is_backup: bool = True,
        tier: int = 1,
    ) -> Optional[CandidateTarget]:
        """Verify eligibility and score a candidate target. Returns CandidateTarget or None."""
        provider = str(config.get("provider") or "").strip().lower()
        model = str(config.get("model") or "").strip()
        if not provider or not model:
            return None

        is_local = self.is_local_provider(provider)

        # 1. Privacy Policy Enforcement (ABSOLUTE RULE: User privacy overrides failover)
        if privacy_policy == POLICY_NEVER_CLOUD and not is_local:
            return None

        # 2. Cost Policy Enforcement
        if cost_policy == CostPolicy.LOCAL_ONLY and not is_local:
            return None
        if cost_policy == CostPolicy.FREE_ONLY and not self.is_free_provider(provider, model):
            return None

        # 3. Credential Check (Ollama needs no key; cloud needs API key)
        needs_key = config.get("needs_key", not is_local)
        if is_local:
            needs_key = False
        api_key = str(config.get("api_key") or "").strip()
        if needs_key and not api_key:
            return None

        # 4. Capability Check
        caps = _capabilities_for(config, is_backup=is_backup)

        # Vision requirement
        if requirements.vision and not caps.vision:
            return None

        # Tools requirement (e.g. coding agent requires tool loop compatibility)
        if requirements.tools:
            # Base models that cannot follow instructions should be skipped
            m_low = model.lower()
            if any(b in m_low for b in ("-base", "_base", "base-q", ":base")):
                return None
            if not caps.tools:
                return None

        # Context Window requirement
        if requirements.min_context > 0 and caps.context_window < requirements.min_context:
            return None
        if requirements.long_context and caps.context_window < 60000:
            return None

        # 5. Circuit Breaker & Health Check
        health = self.health_monitor.get_health(provider, model)
        if health.circuit_open and not self.health_monitor.is_healthy(provider, model):
            # Barred by active cooldown
            return None

        # 6. Scoring
        score = self.calculate_score(caps, health, requirements, privacy_policy, is_local)

        return CandidateTarget(
            provider=provider,
            model=model,
            config=dict(config),
            entry=entry,
            is_backup=is_backup,
            is_local=is_local,
            score=score,
            tier=tier,
        )

    def calculate_score(
        self,
        caps: ModelCapabilities,
        health: Any,
        requirements: TaskRequirements,
        privacy_policy: str,
        is_local: bool,
    ) -> float:
        """Dynamic routing score (0 to 100) based on observable CAT state."""
        score = 50.0

        # Capability fitness (up to +25)
        if requirements.coding:
            m_low = caps.model.lower()
            if any(k in m_low for k in ("coder", "code", "qwen", "deepseek", "sonnet")):
                score += 15.0
        if requirements.reasoning and caps.reasoning:
            score += 10.0
        if requirements.vision and caps.vision:
            score += 10.0

        # Privacy fitness (up to +20)
        if privacy_policy == POLICY_LOCAL_FIRST:
            score += 20.0 if is_local else 0.0
        elif privacy_policy == POLICY_CLOUD_FIRST:
            score += 20.0 if not is_local else 5.0
        elif privacy_policy == POLICY_BEST_AVAILABLE:
            score += 10.0

        # Health & Latency fitness (up to +20)
        if health.status in ("healthy", "local"):
            score += 15.0
        elif health.status == "slow":
            score += 5.0
        if health.latency_ms:
            if health.latency_ms < 1000:
                score += 5.0
            elif health.latency_ms > 4000:
                score -= 10.0

        # Consecutive failures penalty
        score -= min(30.0, health.consecutive_failures * 10.0)

        return max(0.0, min(100.0, score))


_GLOBAL_MATCHER: Optional[CapabilityMatcher] = None


def get_capability_matcher() -> CapabilityMatcher:
    global _GLOBAL_MATCHER
    if _GLOBAL_MATCHER is None:
        _GLOBAL_MATCHER = CapabilityMatcher()
    return _GLOBAL_MATCHER
