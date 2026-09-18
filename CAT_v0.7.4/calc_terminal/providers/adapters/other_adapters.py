"""
calc_terminal/providers/adapters/other_adapters.py
==================================================
Adapters for xAI (Grok), Mistral, Cohere, Meta, and Generic OpenAI-compatible endpoints.
"""

import requests
from typing import List, Dict, Any

from .base import BaseProviderAdapter
from ...models.schema import ModelInfo, AVAILABILITY_PAID_API, AVAILABILITY_OPEN_WEIGHT
from ...models.validator import ModelValidator


class XAIAdapter(BaseProviderAdapter):
    provider_id = "xai"
    display_name = "xAI (Grok)"
    company = "xAI"
    region = "US"
    api_base = "https://api.x.ai/v1"
    authentication_type = "bearer_token"
    documentation_url = "https://docs.x.ai"

    catalog = {
        "grok-3": {
            "display_name": "Grok 3",
            "family": "Grok",
            "version": "3",
            "context_window": 131072,
            "max_output_tokens": 16384,
            "capabilities": ["reasoning", "coding", "vision", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 3.0, "output_price_per_1m": 15.0},
            "recommendation_badges": ["Best for Reasoning"],
        },
        "grok-3-mini": {
            "display_name": "Grok 3 Mini",
            "family": "Grok",
            "version": "3",
            "context_window": 131072,
            "max_output_tokens": 16384,
            "capabilities": ["coding", "tools", "streaming", "fast"],
            "pricing": {"input_price_per_1m": 0.3, "output_price_per_1m": 1.5},
            "recommendation_badges": ["Best Fast Model"],
        },
        "grok-2": {
            "display_name": "Grok 2",
            "family": "Grok",
            "version": "2",
            "context_window": 131072,
            "max_output_tokens": 8192,
            "capabilities": ["vision", "coding", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 2.0, "output_price_per_1m": 10.0},
        },
    }

    def discover_models(self, timeout: float = 8.0) -> List[ModelInfo]:
        base = self.get_api_base()
        key = self.get_api_key()
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"

        discovered_ids = []
        try:
            resp = requests.get(f"{base}/models", headers=headers, timeout=timeout)
            if resp.status_code == 200:
                for item in resp.json().get("data", []):
                    mid = str(item.get("id", "")).strip()
                    if mid:
                        discovered_ids.append(mid)
        except Exception:
            pass

        for cat_id in self.catalog:
            if cat_id not in discovered_ids:
                discovered_ids.append(cat_id)

        results = []
        for mid in discovered_ids:
            meta = dict(self.catalog.get(mid, {}))
            meta["model_id"] = mid
            meta["endpoint"] = base
            val = ModelValidator.validate_raw(meta, self.provider_id, self.config)
            if val.is_valid and val.model_info:
                results.append(val.model_info)
        return results


class MistralAdapter(BaseProviderAdapter):
    provider_id = "mistral"
    display_name = "Mistral AI"
    company = "Mistral AI"
    region = "EU"
    api_base = "https://api.mistral.ai/v1"
    authentication_type = "bearer_token"
    documentation_url = "https://docs.mistral.ai/getting-started/models/models_overview/"

    catalog = {
        "mistral-large-latest": {
            "display_name": "Mistral Large (Latest)",
            "family": "Mistral",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "capabilities": ["reasoning", "coding", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 2.0, "output_price_per_1m": 6.0},
            "recommendation_badges": ["Best for Coding"],
        },
        "codestral-latest": {
            "display_name": "Codestral (Latest)",
            "family": "Mistral",
            "context_window": 256000,
            "max_output_tokens": 16384,
            "capabilities": ["coding", "tools", "streaming", "fast"],
            "pricing": {"input_price_per_1m": 0.3, "output_price_per_1m": 0.9},
            "recommendation_badges": ["Best for Coding"],
        },
        "mistral-small-latest": {
            "display_name": "Mistral Small (Latest)",
            "family": "Mistral",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "capabilities": ["chat", "fast", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 0.1, "output_price_per_1m": 0.3},
            "recommendation_badges": ["Best Fast Model"],
        },
    }

    def discover_models(self, timeout: float = 8.0) -> List[ModelInfo]:
        base = self.get_api_base()
        key = self.get_api_key()
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"

        discovered_ids = []
        try:
            resp = requests.get(f"{base}/models", headers=headers, timeout=timeout)
            if resp.status_code == 200:
                for item in resp.json().get("data", []):
                    mid = str(item.get("id", "")).strip()
                    if mid:
                        discovered_ids.append(mid)
        except Exception:
            pass

        for cat_id in self.catalog:
            if cat_id not in discovered_ids:
                discovered_ids.append(cat_id)

        results = []
        for mid in discovered_ids:
            meta = dict(self.catalog.get(mid, {}))
            meta["model_id"] = mid
            meta["endpoint"] = base
            val = ModelValidator.validate_raw(meta, self.provider_id, self.config)
            if val.is_valid and val.model_info:
                results.append(val.model_info)
        return results


class CohereAdapter(BaseProviderAdapter):
    provider_id = "cohere"
    display_name = "Cohere"
    company = "Cohere"
    region = "CA"
    api_base = "https://api.cohere.com/v2"
    authentication_type = "bearer_token"
    documentation_url = "https://docs.cohere.com/v2/docs/models"

    catalog = {
        "command-r-plus": {
            "display_name": "Command R+",
            "family": "Command",
            "context_window": 128000,
            "max_output_tokens": 4096,
            "capabilities": ["reasoning", "coding", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 2.5, "output_price_per_1m": 10.0},
        },
        "command-r": {
            "display_name": "Command R",
            "family": "Command",
            "context_window": 128000,
            "max_output_tokens": 4096,
            "capabilities": ["coding", "tools", "streaming", "fast"],
            "pricing": {"input_price_per_1m": 0.5, "output_price_per_1m": 1.5},
            "recommendation_badges": ["Best Fast Model"],
        },
    }

    def discover_models(self, timeout: float = 8.0) -> List[ModelInfo]:
        base = self.get_api_base()
        key = self.get_api_key()
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"

        discovered_ids = []
        try:
            resp = requests.get(f"{base}/models", headers=headers, timeout=timeout)
            if resp.status_code == 200:
                for item in resp.json().get("models", []):
                    mid = str(item.get("name", "")).strip()
                    if mid:
                        discovered_ids.append(mid)
        except Exception:
            pass

        for cat_id in self.catalog:
            if cat_id not in discovered_ids:
                discovered_ids.append(cat_id)

        results = []
        for mid in discovered_ids:
            meta = dict(self.catalog.get(mid, {}))
            meta["model_id"] = mid
            meta["endpoint"] = base
            val = ModelValidator.validate_raw(meta, self.provider_id, self.config)
            if val.is_valid and val.model_info:
                results.append(val.model_info)
        return results


class GenericOpenAIAdapter(BaseProviderAdapter):
    """Fallback adapter for any OpenAI-compatible provider."""

    def discover_models(self, timeout: float = 8.0) -> List[ModelInfo]:
        base = self.get_api_base()
        key = self.get_api_key()
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"

        discovered = []
        try:
            resp = requests.get(f"{base}/models", headers=headers, timeout=timeout)
            if resp.status_code == 200:
                for item in resp.json().get("data", []):
                    mid = str(item.get("id", "")).strip()
                    if mid:
                        meta = {"model_id": mid, "endpoint": base}
                        val = ModelValidator.validate_raw(meta, self.provider_id, self.config)
                        if val.is_valid and val.model_info:
                            discovered.append(val.model_info)
        except Exception:
            pass
        return discovered
