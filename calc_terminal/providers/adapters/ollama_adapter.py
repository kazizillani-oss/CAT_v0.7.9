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

        # Support localhost vs 127.0.0.1 fallback on Windows (IPv6 ::1 resolution bug fix)
        endpoints_to_try = [base]
        if "localhost" in base:
            endpoints_to_try.append(base.replace("localhost", "127.0.0.1"))
        elif "127.0.0.1" in base:
            endpoints_to_try.append(base.replace("127.0.0.1", "localhost"))

        discovered_dict = {}
        for ep in endpoints_to_try:
            try:
                # 1. Query /api/tags for installed models
                resp = requests.get(f"{ep}/api/tags", timeout=timeout)
                if resp.status_code == 200:
                    raw_models = resp.json().get("models", [])
                    for m in raw_models:
                        name = str(m.get("name", "")).strip()
                        if name and name not in discovered_dict:
                            discovered_dict[name] = m
                # 2. Query /api/ps for currently running / loaded models
                try:
                    ps_resp = requests.get(f"{ep}/api/ps", timeout=timeout)
                    if ps_resp.status_code == 200:
                        ps_models = ps_resp.json().get("models", [])
                        for m in ps_models:
                            name = str(m.get("name", "")).strip()
                            if name and name not in discovered_dict:
                                discovered_dict[name] = m
                except Exception:
                    pass
                if discovered_dict:
                    base = ep
                    break
            except Exception:
                continue

        for name, m in discovered_dict.items():
            details = m.get("details", {}) if isinstance(m, dict) else {}
            param_size = details.get("parameter_size", "")
            family = details.get("family") or name.split(":")[0].capitalize()
            disp = f"{name} ({param_size})" if param_size else f"{name} (Local)"
            meta = {
                "model_id": name,
                "display_name": disp if not is_cloud else f"{name} (Cloud)",
                "family": family,
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

        # Merge with curated authentic catalog so users see all popular models
        try:
            from ...ollama_catalog import all_models as _all_curated
            existing_ids = {m.model_id for m in models}
            for cat in _all_curated():
                cname = cat.get("name")
                if cname and cname not in existing_ids:
                    meta = {
                        "model_id": cname,
                        "display_name": f"{cname} ({cat.get('params', 'Local')})",
                        "family": cat.get("family", "Ollama").capitalize(),
                        "availability": AVAILABILITY_LOCAL,
                        "capabilities": cat.get("caps", ["chat", "streaming", "local"]),
                        "tags": cat.get("categories", ["popular", "local"]),
                        "context_window": cat.get("context", 8192),
                        "endpoint": base,
                        "source": "curated_catalog",
                    }
                    val = ModelValidator.validate_raw(meta, self.provider_id, self.config)
                    if val.is_valid and val.model_info:
                        val.model_info.local = True
                        val.model_info.cloud = False
                        models.append(val.model_info)
                        existing_ids.add(cname)
        except Exception:
            existing_ids = {m.model_id for m in models}
            for name in self.DEFAULT_FALLBACKS:
                if name not in existing_ids:
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
