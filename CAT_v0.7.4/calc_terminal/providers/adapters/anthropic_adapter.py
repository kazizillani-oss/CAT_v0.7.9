"""
calc_terminal/providers/adapters/anthropic_adapter.py
====================================================
Anthropic Claude Provider Adapter with live discovery and Claude 4 support.
"""

import requests
from typing import List

from .base import BaseProviderAdapter
from ...models.schema import ModelInfo
from ...models.validator import ModelValidator


class AnthropicAdapter(BaseProviderAdapter):
    provider_id = "anthropic"
    display_name = "Anthropic (Claude)"
    company = "Anthropic"
    region = "US"
    api_base = "https://api.anthropic.com/v1"
    authentication_type = "header"
    documentation_url = "https://docs.anthropic.com/en/docs/about-claude/models"

    CATALOG_MODELS = {
        "claude-4-sonnet-20260515": {
            "display_name": "Claude 4 Sonnet",
            "family": "Claude",
            "version": "4",
            "context_window": 500000,
            "max_output_tokens": 32768,
            "capabilities": ["reasoning", "coding", "vision", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 3.0, "output_price_per_1m": 15.0},
            "recommendation_badges": ["Best for Coding"],
        },
        "claude-4-fable-5.1": {
            "display_name": "Claude 4 Fable 5.1",
            "family": "Claude",
            "version": "4",
            "context_window": 500000,
            "max_output_tokens": 64000,
            "capabilities": ["reasoning", "coding", "vision", "tools", "streaming", "long_context"],
            "pricing": {"input_price_per_1m": 4.0, "output_price_per_1m": 16.0},
            "recommendation_badges": ["Best for Research"],
        },
        "claude-sonnet-4": {
            "display_name": "Claude Sonnet 4",
            "family": "Claude",
            "version": "4",
            "context_window": 200000,
            "max_output_tokens": 16384,
            "capabilities": ["reasoning", "coding", "vision", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 3.0, "output_price_per_1m": 15.0},
            "recommendation_badges": ["Best for Coding"],
        },
        "claude-opus-4": {
            "display_name": "Claude Opus 4",
            "family": "Claude",
            "version": "4",
            "context_window": 200000,
            "max_output_tokens": 16384,
            "capabilities": ["reasoning", "coding", "vision", "research", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 15.0, "output_price_per_1m": 75.0},
            "recommendation_badges": ["Best for Reasoning"],
        },
        "claude-3-7-sonnet": {
            "display_name": "Claude 3.7 Sonnet",
            "family": "Claude",
            "version": "3.7",
            "context_window": 200000,
            "max_output_tokens": 8192,
            "capabilities": ["reasoning", "coding", "vision", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 3.0, "output_price_per_1m": 15.0},
            "recommendation_badges": ["Best for Coding"],
        },
        "claude-3-5-sonnet": {
            "display_name": "Claude 3.5 Sonnet",
            "family": "Claude",
            "version": "3.5",
            "context_window": 200000,
            "max_output_tokens": 8192,
            "capabilities": ["coding", "vision", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 3.0, "output_price_per_1m": 15.0},
        },
        "claude-3-5-haiku": {
            "display_name": "Claude 3.5 Haiku",
            "family": "Claude",
            "version": "3.5",
            "context_window": 200000,
            "max_output_tokens": 8192,
            "capabilities": ["coding", "tools", "streaming", "fast"],
            "pricing": {"input_price_per_1m": 0.8, "output_price_per_1m": 4.0},
            "recommendation_badges": ["Best Fast Model"],
        },
    }

    def discover_models(self, timeout: float = 8.0) -> List[ModelInfo]:
        base = self.get_api_base()
        key = self.get_api_key()
        headers = {"Content-Type": "application/json", "anthropic-version": "2023-06-01"}
        if key:
            headers["x-api-key"] = key

        discovered_ids = []
        try:
            resp = requests.get(f"{base}/models", headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                for item in data:
                    mid = str(item.get("id", "")).strip()
                    if mid:
                        discovered_ids.append(mid)
        except Exception:
            pass

        for cat_id in self.CATALOG_MODELS:
            if cat_id not in discovered_ids:
                discovered_ids.append(cat_id)

        results = []
        for mid in discovered_ids:
            meta = dict(self.CATALOG_MODELS.get(mid, {}))
            meta["model_id"] = mid
            meta["endpoint"] = base
            val = ModelValidator.validate_raw(meta, self.provider_id, self.config)
            if val.is_valid and val.model_info:
                results.append(val.model_info)
        return results
