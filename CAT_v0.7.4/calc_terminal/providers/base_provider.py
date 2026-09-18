"""Abstract base class for all AI providers in CCT."""

from abc import ABC, abstractmethod
from typing import Optional


class BaseProvider(ABC):
    """Every provider implements this interface. Add a new one by
    subclassing and registering it in ProviderManager."""

    ID: str = ""
    NAME: str = ""
    NEEDS_KEY: bool = True
    DEFAULT_MODEL: str = ""
    API_STYLE: str = "openai"

    # ── Capability flags (override in subclasses) ─────────────────────
    supports_model_listing: bool = True
    supports_streaming: bool = True
    supports_tools: bool = False
    supports_reasoning: bool = False
    supports_vision: bool = False
    supports_audio: bool = False
    supports_images: bool = False
    supports_embeddings: bool = False
    supports_reranking: bool = False

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def connect(self) -> tuple[bool, str, list[str]]:
        """Test connectivity. Returns (ok, message, available_models)."""

    @abstractmethod
    def fetch_models(self) -> list[str]:
        """GET /models or equivalent. Returns list of model IDs or []."""

    def fetch_models_paginated(self, cancel_event=None) -> list[str]:
        """Fetch models with pagination support. Override for providers
        with paginated APIs. Default implementation delegates to fetch_models().
        `cancel_event` is a threading.Event; check periodically and return
        early if set."""
        if cancel_event and cancel_event.is_set():
            return []
        return self.fetch_models()

    @abstractmethod
    def chat(self, prompt: str, system_prompt: str = "",
             history: Optional[list] = None) -> str:
        """Non-streaming chat completion."""

    @abstractmethod
    def stream(self, prompt: str, system_prompt: str = "",
               history: Optional[list] = None):
        """Streaming generator yielding text fragments."""

    def embeddings(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError(f"{self.ID} does not support embeddings")

    def vision(self, prompt: str, image_b64: str, mime: str) -> str:
        raise NotImplementedError(f"{self.ID} does not support vision")

    def health_check(self) -> dict:
        """Return status info: latency, version, etc."""
        return {"provider": self.ID, "status": "unknown"}

    def get_base_url(self) -> str:
        return (self.config.get("base_url") or
                self.config.get("api_url") or "").rstrip("/")

    def get_api_key(self) -> str:
        return self.config.get("api_key", "")

    def get_model(self) -> str:
        return self.config.get("model") or self.default_model()

    @classmethod
    def default_model(cls) -> str:
        """Data-driven default; overridden by provider classes that resolve
        from providers.json. Falls back to the hardcoded DEFAULT_MODEL."""
        return cls.DEFAULT_MODEL

    def get_extra_headers(self) -> dict:
        return dict(self.config.get("extra_headers", {}))

    @classmethod
    def to_provider_dict(cls) -> dict:
        """Return the standard provider info dict for this class."""
        return {
            "id": cls.ID,
            "name": cls.NAME,
            "url": cls._default_url() if hasattr(cls, "_default_url") else "",
            "api_style": cls.API_STYLE,
            "needs_key": cls.NEEDS_KEY,
            "default_model": cls.default_model(),
            "models": [],
            "models_cache": [],
            "features": [],
            "openai_compat": cls.API_STYLE == "openai",
            "desc": "",
        }

    def dispose(self):
        """Cleanup hook when provider is removed."""
