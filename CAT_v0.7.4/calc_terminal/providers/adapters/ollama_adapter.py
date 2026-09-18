"""
calc_terminal/providers/adapters/ollama_adapter.py
==================================================
Ollama Provider Adapter for Local and Cloud models.
"""

import requests
from typing import List

from .base import BaseProviderAdapter
from ...models.schema import ModelInfo, AVAILABILITY_LOCAL, AVAILABILITY_CLOUD, AVAILABILITY_OPEN_WEIGHT
from ...models.validator import ModelValidator


class OllamaAdapter(BaseProviderAdapter):
    provider_id = "ollama"
    display_name = "Ollama (Local / Cloud)"
    company = "Ollama"
    region = "Local"
    api_base = "http://localhost:11434"
    authentication_type = "none"
    documentation_url = "https://ollama.com"

    DEFAULT_FALLBACKS = [
        "llama3.3", "deepseek-r1", "qwen2.5-coder", "mistral", "phi4", "codellama"
    ]

    @property
    def is_local(self) -> bool:
        base = self.get_api_base()
        return not ("ollama.ai" in base or "cloud" in base)

    def discover_models(self, timeout: float = 6.0) -> List[ModelInfo]:
        base = self.get_api_base()
        models = []

        is_cloud = "ollama.ai" in base or "cloud" in base

        try:
            resp = requests.get(f"{base}/api/tags", timeout=timeout)
            if resp.status_code == 200:
                raw_models = resp.json().get("models", [])
                for m in raw_models:
                    name = str(m.get("name", "")).strip()
                    if name:
                        meta = {
                            "model_id": name,
                            "display_name": f"{name} (Local)" if not is_cloud else f"{name} (Cloud)",
                            "family": name.split(":")[0].capitalize(),
                            "availability": AVAILABILITY_CLOUD if is_cloud else AVAILABILITY_LOCAL,
                            "capabilities": ["chat", "streaming", "local" if not is_cloud else "cloud"],
                            "tags": ["local" if not is_cloud else "cloud", "open_weight"],
                            "endpoint": base,
                            "verified": True,
                        }
                        val = ModelValidator.validate_raw(meta, self.provider_id, self.config)
                        if val.is_valid and val.model_info:
                            val.model_info.local = not is_cloud
                            val.model_info.cloud = is_cloud
                            val.model_info.recommendation_badges = ["Best Local Model"] if not is_cloud else []
                            models.append(val.model_info)
        except Exception:
            pass

        # If local Ollama isn't currently running, return standard installable catalog as preview
        if not models:
            for name in self.DEFAULT_FALLBACKS:
                meta = {
                    "model_id": name,
                    "display_name": f"{name} (Ollama)",
                    "availability": AVAILABILITY_LOCAL,
                    "capabilities": ["chat", "streaming", "local"],
                    "tags": ["local", "open_weight"],
                    "endpoint": base,
                    "source": "fallback",
                }
                val = ModelValidator.validate_raw(meta, self.provider_id, self.config)
                if val.is_valid and val.model_info:
                    val.model_info.local = True
                    val.model_info.cloud = False
                    models.append(val.model_info)

        return models
