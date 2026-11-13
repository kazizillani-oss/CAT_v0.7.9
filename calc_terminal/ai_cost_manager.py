"""
CAT AI Cost & Usage Manager (v0.7.9 Complete Platform Expansion)

Token usage tracking, multi-provider pricing models, budget caps,
cost breakdown analytics, and session financial audit.
"""

import os
import time
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

# Pricing in USD per 1,000,000 tokens (input, output)
MODEL_PRICING = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "deepseek-chat": (0.14, 0.28),
    "deepseek-reasoner": (0.55, 2.19),
    "llama-3.3-70b": (0.50, 0.80),
    "ollama": (0.00, 0.00),  # local free
}

@dataclass
class UsageEntry:
    timestamp: float
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AICostManager:
    """Tracks token consumption and expenditures across all AI queries."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._entries: List[UsageEntry] = []
            cls._instance._budget_limit_usd: float = 10.00
            cls._instance._storage_path = os.path.expanduser("~/.cat/ai_usage.json")
            os.makedirs(os.path.dirname(cls._instance._storage_path), exist_ok=True)
            cls._instance._load_usage()
        return cls._instance

    def _load_usage(self):
        if os.path.exists(self._storage_path):
            try:
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._budget_limit_usd = data.get("budget_limit_usd", 10.00)
                raw_entries = data.get("entries", [])
                self._entries = [UsageEntry(**e) for e in raw_entries if isinstance(e, dict)]
            except Exception:
                self._entries = []

    def _save_usage(self):
        try:
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump({
                    "budget_limit_usd": self._budget_limit_usd,
                    "entries": [e.to_dict() for e in self._entries[-500:]]
                }, f, indent=2)
        except Exception:
            pass

    def record_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        provider: str = "auto"
    ) -> UsageEntry:
        """Calculate and log token consumption for an inference call."""
        total = prompt_tokens + completion_tokens
        # Find pricing
        m_lower = model.lower()
        price_tuple = (0.50, 1.50)  # default fallback
        for k, v in MODEL_PRICING.items():
            if k in m_lower:
                price_tuple = v
                break

        in_price, out_price = price_tuple
        cost = (prompt_tokens / 1_000_000 * in_price) + (completion_tokens / 1_000_000 * out_price)

        entry = UsageEntry(
            timestamp=time.time(),
            model=model,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            estimated_cost_usd=round(cost, 6)
        )
        self._entries.append(entry)
        self._save_usage()
        return entry

    def get_summary(self) -> Dict[str, Any]:
        """Aggregate total tokens and cost across models."""
        total_prompt = sum(e.prompt_tokens for e in self._entries)
        total_comp = sum(e.completion_tokens for e in self._entries)
        total_tokens = sum(e.total_tokens for e in self._entries)
        total_cost = sum(e.estimated_cost_usd for e in self._entries)

        by_model: Dict[str, Dict[str, Any]] = {}
        for e in self._entries:
            m = e.model
            if m not in by_model:
                by_model[m] = {"calls": 0, "tokens": 0, "cost_usd": 0.0}
            by_model[m]["calls"] += 1
            by_model[m]["tokens"] += e.total_tokens
            by_model[m]["cost_usd"] = round(by_model[m]["cost_usd"] + e.estimated_cost_usd, 5)

        budget_remaining = max(0.0, self._budget_limit_usd - total_cost)
        pct_used = (total_cost / self._budget_limit_usd * 100.0) if self._budget_limit_usd > 0 else 0.0

        return {
            "total_calls": len(self._entries),
            "total_tokens": total_tokens,
            "prompt_tokens": total_prompt,
            "completion_tokens": total_comp,
            "total_cost_usd": round(total_cost, 4),
            "budget_limit_usd": self._budget_limit_usd,
            "budget_remaining_usd": round(budget_remaining, 4),
            "budget_used_percent": round(pct_used, 1),
            "by_model": by_model
        }

    def set_budget(self, limit_usd: float) -> float:
        self._budget_limit_usd = max(0.1, limit_usd)
        self._save_usage()
        return self._budget_limit_usd

    def reset_usage(self):
        self._entries.clear()
        self._save_usage()


# Global singleton
ai_cost_manager = AICostManager()

def get_ai_cost_manager() -> AICostManager:
    return ai_cost_manager

