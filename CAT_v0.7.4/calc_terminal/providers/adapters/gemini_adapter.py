"""
calc_terminal/providers/adapters/gemini_adapter.py
==================================================
Google Gemini Provider Adapter with live discovery and Gemini 2.5 support.
"""

import requests
from typing import List

from .base import BaseProviderAdapter
from ...models.schema import ModelInfo
from ...models.validator import ModelValidator


class GeminiAdapter(BaseProviderAdapter):
    provider_id = "gemini"
    display_name = "Google Gemini"
    company = "Google"
    region = "US"
    api_base = "https://generativelanguage.googleapis.com/v1beta"
    authentication_type = "query_param"
    documentation_url = "https://ai.google.dev/gemini-api/docs/models/gemini"

    CATALOG_MODELS = {
        "gemini-2.5-pro": {
            "display_name": "Gemini 2.5 Pro",
            "family": "Gemini",
            "version": "2.5",
            "context_window": 2000000,
            "max_output_tokens": 65536,
            "capabilities": ["reasoning", "coding", "vision", "audio", "tools", "streaming", "long_context"],
            "pricing": {"input_price_per_1m": 1.25, "output_price_per_1m": 5.0},
            "recommendation_badges": ["Best for Coding", "Best for Research"],
        },
        "gemini-2.5-flash": {
            "display_name": "Gemini 2.5 Flash",
            "family": "Gemini",
            "version": "2.5",
            "context_window": 1000000,
            "max_output_tokens": 32768,
            "capabilities": ["reasoning", "coding", "vision", "tools", "streaming", "fast", "long_context"],
            "pricing": {"input_price_per_1m": 0.1, "output_price_per_1m": 0.4},
            "recommendation_badges": ["Best Fast Model", "Best Budget Model"],
        },
        "gemini-2.0-flash": {
            "display_name": "Gemini 2.0 Flash",
            "family": "Gemini",
            "version": "2.0",
            "context_window": 1000000,
            "max_output_tokens": 8192,
            "capabilities": ["vision", "coding", "tools", "streaming", "fast"],
            "pricing": {"input_price_per_1m": 0.1, "output_price_per_1m": 0.4},
            "recommendation_badges": ["Best Fast Model"],
        },
        "gemini-2.0-flash-thinking": {
            "display_name": "Gemini 2.0 Flash Thinking",
            "family": "Gemini",
            "version": "2.0",
            "context_window": 1000000,
            "max_output_tokens": 65536,
            "reasoning_levels": ["high"],
            "capabilities": ["reasoning", "coding", "vision", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 0.15, "output_price_per_1m": 0.6},
            "recommendation_badges": ["Best for Reasoning"],
        },
    }

    def discover_models(self, timeout: float = 8.0) -> List[ModelInfo]:
        base = self.get_api_base()
        key = self.get_api_key()
        params = {}
        if key:
            params["key"] = key

        discovered_ids = []
        try:
            resp = requests.get(f"{base}/models", params=params, timeout=timeout)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                for m in models:
                    name = str(m.get("name", "")).strip()
                    if "/" in name:
                        name = name.split("/")[-1]
                    if name and not any(name.startswith(x) for x in ("embedding", "aqa", "imagen")):
                        discovered_ids.append(name)
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
