"""
CAT — Backup Provider & Resilience System: Native Ollama Local Adapter
Author: Kazi Zillani

First-class native integration for local Ollama fallback.
Requires:
- Zero API keys
- Zero cloud endpoints
- Automatic discovery of local models via /api/tags
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

_LOG = logging.getLogger(__name__)

DEFAULT_OLLAMA_URL = "http://localhost:11434"

# Quality instruct model heuristics
INSTRUCT_PREFERENCES = [
    "qwen2.5-coder", "qwen3", "qwen2.5", "llama3.3", "llama3.2",
    "llama3.1", "deepseek-r1", "deepseek-coder", "codellama",
    "mistral", "gemma2", "phi3", "phi4", "starcoder",
]


class OllamaAdapter:
    """Zero-config discovery and management for local Ollama backup."""

    def __init__(self, base_url: str = DEFAULT_OLLAMA_URL):
        self.base_url = (base_url or DEFAULT_OLLAMA_URL).rstrip("/")
        self._cached_models: Optional[List[dict]] = None
        self._last_checked = 0.0

    def is_available(self, timeout: float = 1.5) -> bool:
        """Check if local Ollama daemon is reachable."""
        try:
            import requests
            resp = requests.get(f"{self.base_url}/api/tags", timeout=timeout)
            return resp.status_code == 200
        except Exception:
            return False

    def list_installed_models(self, force_refresh: bool = False) -> List[dict]:
        """Fetch models currently pulled on the local machine."""
        now = time.time()
        if not force_refresh and self._cached_models is not None and (now - self._last_checked) < 30.0:
            return self._cached_models

        try:
            import requests
            resp = requests.get(f"{self.base_url}/api/tags", timeout=2.5)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                self._cached_models = models
                self._last_checked = now
                return models
        except Exception as e:
            _LOG.debug("Ollama discovery failed: %s", e)

        return []

    def get_model_names(self) -> List[str]:
        return [str(m.get("name", "")).strip() for m in self.list_installed_models() if m.get("name")]

    def select_best_model(self, coding: bool = False, reasoning: bool = False) -> Optional[str]:
        """Pick the best available instruct model installed locally."""
        names = self.get_model_names()
        if not names:
            return None

        # Filter out raw non-instruct base models
        non_base = [
            n for n in names
            if not any(b in n.lower() for b in ("-base", "_base", "base-q", ":base"))
        ]
        candidates = non_base if non_base else names

        if coding:
            for pref in ("coder", "code", "qwen", "deepseek"):
                for m in candidates:
                    if pref in m.lower():
                        return m

        if reasoning:
            for m in candidates:
                if "r1" in m.lower() or "reasoning" in m.lower():
                    return m

        for pref in INSTRUCT_PREFERENCES:
            for m in candidates:
                if pref in m.lower():
                    return m

        return candidates[0]

    def build_backup_entry(self, model: Optional[str] = None) -> dict:
        """Create a standard backup configuration entry for Ollama."""
        selected_model = model or self.select_best_model() or "llama3.3"
        return {
            "provider": "ollama",
            "model": selected_model,
            "api_key": "",
            "base_url": self.base_url,
            "api_style": "ollama",
            "name": "Ollama (Local Backup)",
            "enabled": True,
            "status": "connected" if self.is_available() else "disconnected",
            "last_used": 0,
            "priority": 999,  # Default to final local safety net
        }


_GLOBAL_OLLAMA: Optional[OllamaAdapter] = None


def get_ollama_adapter() -> OllamaAdapter:
    global _GLOBAL_OLLAMA
    if _GLOBAL_OLLAMA is None:
        _GLOBAL_OLLAMA = OllamaAdapter()
    return _GLOBAL_OLLAMA
