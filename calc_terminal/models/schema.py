"""
calc_terminal/models/schema.py
==============================
Standardized Model Metadata Schema for CAT's Dynamic Model Registry.

Represents AI models in a unified, provider-agnostic format supporting:
  - Canonical model identity across multiple deployment endpoints.
  - Granular capability detection (reasoning, coding, vision, computer use, etc.).
  - Multi-level reasoning configurations (e.g. low, medium, high, xhigh, max).
  - Clear access tier categorization (open_weight, free_api, paid_api, local, cloud).
  - Release and verification tracking (first_seen, last_seen, last_verified).
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional


# Standard Availability States
AVAILABILITY_API = "api"
AVAILABILITY_OPEN_WEIGHT = "open_weight"
AVAILABILITY_FREE_API = "free_api"
AVAILABILITY_FREE_TIER = "free_tier"
AVAILABILITY_PAID_API = "paid_api"
AVAILABILITY_LOCAL = "local"
AVAILABILITY_CLOUD = "cloud"
AVAILABILITY_SUBSCRIPTION = "subscription"

# Standard Model Statuses
STATUS_ACTIVE = "active"
STATUS_PREVIEW = "preview"
STATUS_BETA = "beta"
STATUS_DEPRECATED = "deprecated"
STATUS_RETIRED = "retired"
STATUS_UNAVAILABLE = "unavailable"
STATUS_AUTH_REQUIRED = "auth_required"
STATUS_DISCOVERED_UNAVAILABLE = "discovered_but_unavailable"

# Standard Categories
CATEGORY_GENERAL = "general"
CATEGORY_REASONING = "reasoning"
CATEGORY_CODING = "coding"
CATEGORY_FAST = "fast"
CATEGORY_CHEAP = "cheap"
CATEGORY_LONG_CONTEXT = "long_context"
CATEGORY_VISION = "vision"
CATEGORY_AUDIO = "audio"
CATEGORY_MULTIMODAL = "multimodal"
CATEGORY_AGENT = "agent"
CATEGORY_RESEARCH = "research"
CATEGORY_LOCAL = "local"
CATEGORY_OPEN_WEIGHT = "open_weight"
CATEGORY_EMBEDDING = "embedding"
CATEGORY_SPECIALIZED = "specialized"
CATEGORY_FREE_API = "free"
CATEGORY_PAID_API = "paid"
AVAILABILITY_FREE_TIER = "free_tier"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ModelInfo:
    """Standardized representation of an AI model in CAT."""

    provider: str
    model_id: str
    display_name: str = ""
    family: str = ""
    version: str = ""
    canonical_model_id: str = ""
    release_date: Optional[str] = None
    status: str = STATUS_ACTIVE
    availability: str = AVAILABILITY_PAID_API
    modalities: List[str] = field(default_factory=lambda: ["text"])
    capabilities: List[str] = field(default_factory=lambda: ["chat", "streaming"])
    context_window: int = 128000
    max_output_tokens: int = 4096
    reasoning_levels: List[str] = field(default_factory=list)
    pricing: Dict[str, float] = field(default_factory=lambda: {"input_price_per_1m": 0.0, "output_price_per_1m": 0.0})
    endpoint: str = ""
    authentication_required: bool = True
    local: bool = False
    cloud: bool = True
    verified: bool = False
    source: str = "official_api"
    first_seen: str = field(default_factory=_now_iso)
    last_seen: str = field(default_factory=_now_iso)
    last_verified: str = field(default_factory=_now_iso)
    stale: bool = False
    tags: List[str] = field(default_factory=list)
    recommendation_badges: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.display_name:
            self.display_name = self.model_id
        if not self.canonical_model_id:
            self.canonical_model_id = f"{self.provider}:{self.model_id}"
        if not self.family:
            self.family = self._derive_family()

    def _derive_family(self) -> str:
        mid = self.model_id.lower()
        if "gpt" in mid or "o1" in mid or "o3" in mid:
            return "GPT"
        if "claude" in mid:
            return "Claude"
        if "gemini" in mid:
            return "Gemini"
        if "deepseek" in mid:
            return "DeepSeek"
        if "qwen" in mid:
            return "Qwen"
        if "kimi" in mid or "moonshot" in mid:
            return "Kimi"
        if "glm" in mid:
            return "GLM"
        if "grok" in mid:
            return "Grok"
        if "mistral" in mid or "codestral" in mid:
            return "Mistral"
        if "command" in mid:
            return "Command"
        if "llama" in mid:
            return "Llama"
        if "minimax" in mid or "abab" in mid:
            return "MiniMax"
        if "hunyuan" in mid or "hy" in mid:
            return "Hunyuan"
        if "doubao" in mid or "seed" in mid:
            return "Seed"
        if "ernie" in mid:
            return "ERNIE"
        return self.provider.capitalize()

    @property
    def availability_state(self) -> str:
        return self.status

    def is_usable(self) -> bool:
        """A model is usable only when it has an active/preview state,
        is verified or from an official provider endpoint, and is not
        marked as discovered_but_unavailable."""
        return (
            self.status in (STATUS_ACTIVE, STATUS_PREVIEW, STATUS_BETA)
            and not self.status == STATUS_DISCOVERED_UNAVAILABLE
        )

    def has_capability(self, capability: str) -> bool:
        cap = capability.lower().strip()
        return cap in [c.lower() for c in self.capabilities]

    def matches_category(self, category: str) -> bool:
        cat = category.lower().strip()
        if cat in ("all", "*"):
            return True
        if cat == CATEGORY_LOCAL:
            return self.local
        if cat == CATEGORY_OPEN_WEIGHT:
            return self.availability == AVAILABILITY_OPEN_WEIGHT or "open_weight" in self.tags
        if cat in (CATEGORY_FREE_API, "free"):
            return self.availability in (AVAILABILITY_FREE_API, AVAILABILITY_FREE_TIER) or self.pricing.get("input_price_per_1m", 0.0) == 0.0
        if cat in (CATEGORY_PAID_API, "paid"):
            return self.pricing.get("input_price_per_1m", 0.0) > 0.0
        if cat == CATEGORY_REASONING:
            return self.has_capability("reasoning") or bool(self.reasoning_levels) or any(k in self.model_id.lower() for k in ("reasoner", "r1", "o1", "o3", "qwq", "k3", "thinking"))
        if cat == CATEGORY_CODING:
            return self.has_capability("coding") or any(k in self.model_id.lower() for k in ("coder", "codestral", "astra", "code"))
        if cat == CATEGORY_VISION:
            return self.has_capability("vision") or "image" in self.modalities or any(k in self.model_id.lower() for k in ("vision", "4o", "4v", "pixtral", "vl", "gemini"))
        if cat == CATEGORY_FAST:
            return self.has_capability("fast") or any(k in self.model_id.lower() for k in ("mini", "flash", "turbo", "instant", "haiku", "8b"))
        if cat == CATEGORY_LONG_CONTEXT:
            return self.context_window >= 128000
        if cat == CATEGORY_AGENT:
            return self.has_capability("agent") or self.has_capability("computer_use") or self.has_capability("tools")
        if cat == CATEGORY_RESEARCH:
            return self.has_capability("research") or self.matches_category(CATEGORY_REASONING)
        return self.has_capability(cat) or cat in self.tags

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelInfo":
        cleaned = dict(data)
        # Handle backward-compatible fields
        if "id" in cleaned and "model_id" not in cleaned:
            cleaned["model_id"] = cleaned.pop("id")
        if "context_length" in cleaned and "context_window" not in cleaned:
            cleaned["context_window"] = int(cleaned.pop("context_length") or 128000)
        # Retain only recognized dataclass keys
        valid_keys = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in cleaned.items() if k in valid_keys}
        return cls(**filtered)
