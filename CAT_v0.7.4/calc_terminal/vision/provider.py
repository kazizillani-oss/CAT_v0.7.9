"""
CAT v0.8.a — Vision Provider Router.

Capability-aware routing for vision requests.  Routes vision analysis
to the best available provider based on capabilities, cost, and quality.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class VisionCapability:
    vision: bool = False
    max_image_tokens: int = 0
    supported_formats: tuple = ("png", "jpeg", "gif", "webp")
    supports_video: bool = False
    supports_audio: bool = False
    supports_streaming: bool = False
    cost_per_image_token: float = 0.0
    quality_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vision": self.vision,
            "max_image_tokens": self.max_image_tokens,
            "supported_formats": list(self.supported_formats),
            "supports_video": self.supports_video,
            "supports_audio": self.supports_audio,
            "supports_streaming": self.supports_streaming,
            "cost_per_image_token": self.cost_per_image_token,
            "quality_score": self.quality_score,
        }


PROVIDER_VISION_CAPS: Dict[str, VisionCapability] = {
    "openai": VisionCapability(
        vision=True, max_image_tokens=8192,
        supported_formats=("png", "jpeg", "gif", "webp"),
        cost_per_image_token=0.01, quality_score=0.95,
    ),
    "anthropic": VisionCapability(
        vision=True, max_image_tokens=8192,
        supported_formats=("png", "jpeg", "gif", "webp"),
        cost_per_image_token=0.015, quality_score=0.93,
    ),
    "google": VisionCapability(
        vision=True, max_image_tokens=16384,
        supported_formats=("png", "jpeg", "gif", "webp"),
        cost_per_image_token=0.008, quality_score=0.90,
    ),
    "ollama": VisionCapability(
        vision=True, max_image_tokens=4096,
        supported_formats=("png", "jpeg"),
        cost_per_image_token=0.0, quality_score=0.70,
    ),
    "groq": VisionCapability(
        vision=True, max_image_tokens=4096,
        supported_formats=("png", "jpeg", "webp"),
        cost_per_image_token=0.003, quality_score=0.80,
    ),
    "mistral": VisionCapability(
        vision=True, max_image_tokens=8192,
        supported_formats=("png", "jpeg", "gif", "webp"),
        cost_per_image_token=0.01, quality_score=0.85,
    ),
    "deepseek": VisionCapability(
        vision=True, max_image_tokens=8192,
        supported_formats=("png", "jpeg", "gif", "webp"),
        cost_per_image_token=0.005, quality_score=0.82,
    ),
    "together": VisionCapability(
        vision=True, max_image_tokens=8192,
        supported_formats=("png", "jpeg", "gif", "webp"),
        cost_per_image_token=0.008, quality_score=0.85,
    ),
    "openrouter": VisionCapability(
        vision=True, max_image_tokens=16384,
        supported_formats=("png", "jpeg", "gif", "webp"),
        cost_per_image_token=0.01, quality_score=0.88,
    ),
}


class VisionProviderRouter:
    """Routes vision requests to the best available provider."""

    def __init__(self, config: Optional[Dict] = None):
        self._config = config or {}
        self._fallback_order = [
            "openai", "anthropic", "google", "deepseek",
            "groq", "mistral", "together", "openrouter", "ollama",
        ]

    def get_capabilities(self, provider: str) -> VisionCapability:
        return PROVIDER_VISION_CAPS.get(provider, VisionCapability())

    def find_vision_capable(self, config: Optional[Dict] = None) -> Optional[Tuple[Dict, VisionCapability]]:
        cfg = config or self._config
        provider = cfg.get("provider", "")
        model = cfg.get("model", "")

        caps = self.get_capabilities(provider)
        if caps.vision:
            return cfg, caps

        for fallback_provider in self._fallback_order:
            if fallback_provider == provider:
                continue
            fallback_caps = self.get_capabilities(fallback_provider)
            if fallback_caps.vision:
                fallback_config = dict(cfg)
                fallback_config["provider"] = fallback_provider
                return fallback_config, fallback_caps

        return None

    def select_best_provider(self, image_size: int = 0,
                             need_video: bool = False,
                             prefer_free: bool = False) -> Optional[Tuple[str, VisionCapability]]:
        candidates = []
        for provider, caps in PROVIDER_VISION_CAPS.items():
            if not caps.vision:
                continue
            if need_video and not caps.supports_video:
                continue
            if prefer_free and caps.cost_per_image_token > 0:
                continue
            if image_size > 0 and image_size > caps.max_image_tokens * 100:
                continue
            candidates.append((provider, caps))

        if prefer_free:
            candidates = [(p, c) for p, c in candidates if c.cost_per_image_token == 0]

        if not candidates:
            return None

        candidates.sort(key=lambda x: (
            -x[1].quality_score,
            x[1].cost_per_image_token,
        ))
        return candidates[0]

    def route_vision_request(self, frame_b64: str,
                             frame_size_bytes: int = 0,
                             config: Optional[Dict] = None) -> Dict[str, Any]:
        cfg = config or self._config
        provider = cfg.get("provider", "")
        caps = self.get_capabilities(provider)

        result = {
            "provider": provider,
            "capabilities": caps.to_dict(),
            "routed": caps.vision,
            "fallback_used": False,
        }

        if not caps.vision:
            route = self.find_vision_capable(cfg)
            if route:
                fallback_cfg, fallback_caps = route
                result["provider"] = fallback_cfg.get("provider", "")
                result["capabilities"] = fallback_caps.to_dict()
                result["routed"] = True
                result["fallback_used"] = True
                result["original_provider"] = provider
            else:
                result["error"] = "No vision-capable provider available"

        return result

    def get_all_capabilities(self) -> Dict[str, Dict]:
        return {
            provider: caps.to_dict()
            for provider, caps in PROVIDER_VISION_CAPS.items()
        }
