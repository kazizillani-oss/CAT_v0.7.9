"""
calc_terminal/providers/adapters/base.py
========================================
Base Provider Adapter Interface for Dynamic Model Discovery.

Every provider adapter implements this contract to allow CAT to automatically
discover, validate, and query AI models directly from official provider APIs.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any

from ...models.schema import ModelInfo, STATUS_ACTIVE, STATUS_UNAVAILABLE, AVAILABILITY_PAID_API
from ...models.validator import ModelValidator


class BaseProviderAdapter(ABC):
    """Abstract interface for all CAT provider adapters."""

    provider_id: str = ""
    display_name: str = ""
    company: str = ""
    region: str = "US"
    api_base: str = ""
    authentication_type: str = "bearer_token"  # bearer_token | query_param | none | custom
    documentation_url: str = ""

    def __init__(self, provider_id_or_config: Any = None, config: Optional[Dict[str, Any]] = None):
        if isinstance(provider_id_or_config, str):
            self.provider_id = provider_id_or_config
            self.config = dict(config or {})
        elif isinstance(provider_id_or_config, dict):
            self.config = dict(provider_id_or_config)
        else:
            self.config = dict(config or {})

    def get_api_base(self) -> str:
        return (
            self.config.get("base_url")
            or self.config.get("api_url")
            or self.api_base
        ).rstrip("/")

    def get_api_key(self) -> Optional[str]:
        return self.config.get("api_key")

    @abstractmethod
    def discover_models(self, timeout: float = 8.0) -> List[ModelInfo]:
        """Fetch and normalize model listings from official provider endpoint."""
        pass

    def validate_model(self, model_id: str) -> Tuple[bool, str]:
        """Check if model ID is recognized and supported by this adapter."""
        if not model_id or not model_id.strip():
            return False, "Empty model identifier."
        return True, "Valid model ID."

    def get_model_metadata(self, model_id: str) -> Optional[ModelInfo]:
        """Return curated or default ModelInfo for a specific model ID."""
        res = ModelValidator.validate_raw(model_id, self.provider_id, self.config)
        return res.model_info if res.is_valid else None

    def get_capabilities(self, model_id: str) -> List[str]:
        meta = self.get_model_metadata(model_id)
        return meta.capabilities if meta else ["chat", "streaming"]

    def get_limits(self, model_id: str) -> Dict[str, int]:
        meta = self.get_model_metadata(model_id)
        if meta:
            return {"context_window": meta.context_window, "max_output_tokens": meta.max_output_tokens}
        return {"context_window": 128000, "max_output_tokens": 4096}

    def get_pricing(self, model_id: str) -> Dict[str, float]:
        meta = self.get_model_metadata(model_id)
        return meta.pricing if meta else {"input_price_per_1m": 0.0, "output_price_per_1m": 0.0}

    def get_availability(self, model_id: str) -> str:
        meta = self.get_model_metadata(model_id)
        return meta.availability if meta else AVAILABILITY_PAID_API

    def health_check(self, timeout: float = 5.0) -> Dict[str, Any]:
        """Ping provider endpoint to verify connectivity and status."""
        import requests
        base = self.get_api_base()
        if not base:
            return {"status": "unknown", "provider": self.provider_id, "message": "No endpoint configured"}
        try:
            # Most OpenAI-compatible endpoints respond to GET /models or /
            headers = {}
            key = self.get_api_key()
            if key and self.authentication_type == "bearer_token":
                headers["Authorization"] = f"Bearer {key}"
            resp = requests.get(f"{base}/models", headers=headers, timeout=timeout)
            if resp.status_code == 401:
                return {"status": "online", "provider": self.provider_id, "auth_required": True, "code": 401}
            if resp.status_code < 400:
                return {"status": "online", "provider": self.provider_id, "code": resp.status_code}
            if resp.status_code >= 500:
                return {"status": "degraded", "provider": self.provider_id, "code": resp.status_code}
            return {"status": "online", "provider": self.provider_id, "code": resp.status_code}
        except requests.exceptions.Timeout:
            return {"status": "degraded", "provider": self.provider_id, "error": "Timeout"}
        except requests.exceptions.ConnectionError:
            return {"status": "offline", "provider": self.provider_id, "error": "Connection error"}
        except Exception as e:
            return {"status": "unknown", "provider": self.provider_id, "error": str(e)}
