"""
calc_terminal/providers/adapters/openai_adapter.py
=================================================
OpenAI Provider Adapter with live discovery and 2026 model coverage.

Includes native metadata for:
  - GPT-6 Astra (gpt-6-astra):
      * Reasoning levels: low, medium, high, xhigh, max
      * Context window: 1,050,000 tokens
      * Max output tokens: 128,000 tokens
      * Capabilities: reasoning, coding, vision, computer_use, research,
        document_workflows, tools, streaming, long_context
  - GPT-5.6 series (Sol, Terra, Luna)
  - o3 and o1 series (o3, o3-mini, o1, o1-mini)
  - GPT-4o and GPT-4o-mini
"""

import requests
from typing import List, Optional

from .base import BaseProviderAdapter
from ...models.schema import ModelInfo, STATUS_ACTIVE, AVAILABILITY_PAID_API
from ...models.validator import ModelValidator


class OpenAIAdapter(BaseProviderAdapter):
    provider_id = "openai"
    display_name = "OpenAI"
    company = "OpenAI"
    region = "US"
    api_base = "https://api.openai.com/v1"
    authentication_type = "bearer_token"
    documentation_url = "https://platform.openai.com/docs/models"

    # Known flagship catalog specifications
    CATALOG_MODELS = {
        "gpt-6-astra": {
            "display_name": "GPT-6 Astra",
            "family": "GPT",
            "version": "6",
            "release_date": "2026-03",
            "context_window": 1050000,
            "max_output_tokens": 128000,
            "reasoning_levels": ["low", "medium", "high", "xhigh", "max"],
            "modalities": ["text", "image"],
            "capabilities": [
                "reasoning", "coding", "vision", "computer_use", "research",
                "document_workflows", "tools", "streaming", "long_context"
            ],
            "pricing": {"input_price_per_1m": 5.0, "output_price_per_1m": 20.0},
            "recommendation_badges": ["Best for Coding", "Best for Reasoning", "Best Agent Model"],
        },
        "gpt-5.6-sol": {
            "display_name": "GPT-5.6 Sol",
            "family": "GPT",
            "version": "5.6",
            "context_window": 512000,
            "max_output_tokens": 64000,
            "capabilities": ["reasoning", "coding", "vision", "tools", "streaming", "long_context"],
            "pricing": {"input_price_per_1m": 2.5, "output_price_per_1m": 10.0},
            "recommendation_badges": ["Best for Reasoning"],
        },
        "gpt-5.6-terra": {
            "display_name": "GPT-5.6 Terra",
            "family": "GPT",
            "version": "5.6",
            "context_window": 256000,
            "max_output_tokens": 32000,
            "capabilities": ["coding", "vision", "tools", "streaming", "fast"],
            "pricing": {"input_price_per_1m": 1.0, "output_price_per_1m": 4.0},
            "recommendation_badges": ["Best Fast Model"],
        },
        "gpt-5.6-luna": {
            "display_name": "GPT-5.6 Luna",
            "family": "GPT",
            "version": "5.6",
            "context_window": 128000,
            "max_output_tokens": 16000,
            "capabilities": ["chat", "coding", "tools", "fast"],
            "pricing": {"input_price_per_1m": 0.3, "output_price_per_1m": 1.2},
            "recommendation_badges": ["Best Budget Model"],
        },
        "o3": {
            "display_name": "o3",
            "family": "o-series",
            "context_window": 200000,
            "max_output_tokens": 100000,
            "reasoning_levels": ["low", "medium", "high"],
            "capabilities": ["reasoning", "coding", "vision", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 10.0, "output_price_per_1m": 40.0},
            "recommendation_badges": ["Best for Reasoning"],
        },
        "o3-mini": {
            "display_name": "o3-mini",
            "family": "o-series",
            "context_window": 200000,
            "max_output_tokens": 65536,
            "reasoning_levels": ["low", "medium", "high"],
            "capabilities": ["reasoning", "coding", "tools", "streaming", "fast"],
            "pricing": {"input_price_per_1m": 1.1, "output_price_per_1m": 4.4},
            "recommendation_badges": ["Best for Coding", "Best for Reasoning"],
        },
        "gpt-4o": {
            "display_name": "GPT-4o",
            "family": "GPT",
            "version": "4o",
            "context_window": 128000,
            "max_output_tokens": 16384,
            "capabilities": ["vision", "coding", "tools", "streaming", "audio"],
            "pricing": {"input_price_per_1m": 2.5, "output_price_per_1m": 10.0},
        },
        "gpt-4o-mini": {
            "display_name": "GPT-4o-mini",
            "family": "GPT",
            "version": "4o",
            "context_window": 128000,
            "max_output_tokens": 16384,
            "capabilities": ["vision", "coding", "tools", "streaming", "fast"],
            "pricing": {"input_price_per_1m": 0.15, "output_price_per_1m": 0.6},
            "recommendation_badges": ["Best Fast Model"],
        },
    }

    def discover_models(self, timeout: float = 8.0) -> List[ModelInfo]:
        """Query official OpenAI /models API with catalog enrichment."""
        base = self.get_api_base()
        key = self.get_api_key()
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"

        discovered_ids = []
        try:
            resp = requests.get(f"{base}/models", headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                for item in data:
                    mid = str(item.get("id", "")).strip()
                    # Filter out non-chat / internal embedding / TTS endpoints
                    if mid and not any(mid.startswith(x) for x in ("dall-e", "text-embedding", "tts", "whisper", "babbage", "davinci")):
                        discovered_ids.append(mid)
        except Exception:
            pass

        # Always include our verified catalog specs even if live endpoint temporarily drops or has rate-limits
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
