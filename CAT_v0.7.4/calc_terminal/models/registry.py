"""Model registry — curated metadata + dynamic discovery merging.

Data-driven redesign (v0.7.4+): curated model metadata lives in
`models/model_metadata.json`, provider metadata + fallback model lists
live in `providers/providers.json`. No model names are hardcoded in
Python source — this module only loads and queries the JSON stores.

Dynamic model discovery, disk caching, refresh and category filtering
live in `models/manager.py`; this module keeps the classic lookup API
used by the picker UIs (get_model_info / get_badges / enrich_models /
group_by_tier / ...).
"""

import json
import os
from typing import Optional

from . import manager


# ── Schema ─────────────────────────────────────────────────────────────────

class ModelInfo:
    __slots__ = (
        "id", "provider", "family",
        "context_window", "capabilities",
        "pricing_tier", "status",
        "input_price_per_1m", "output_price_per_1m",
    )

    def __init__(self, id="", provider="", family="",
                 context_window=0, capabilities=None,
                 pricing_tier="unknown", status="stable",
                 input_price_per_1m=0.0, output_price_per_1m=0.0):
        self.id = id
        self.provider = provider
        self.family = family
        self.context_window = context_window
        self.capabilities = capabilities or []
        self.pricing_tier = pricing_tier
        self.status = status
        self.input_price_per_1m = input_price_per_1m
        self.output_price_per_1m = output_price_per_1m

    def to_dict(self):
        return {
            "id": self.id,
            "provider": self.provider,
            "family": self.family,
            "context_window": self.context_window,
            "capabilities": list(self.capabilities),
            "pricing_tier": self.pricing_tier,
            "status": self.status,
            "input_price_per_1m": self.input_price_per_1m,
            "output_price_per_1m": self.output_price_per_1m,
        }


# ── Metadata helpers (JSON-backed) ─────────────────────────────────────────

def _meta_to_legacy(entry: dict) -> dict:
    """Convert a model_metadata.json entry to the legacy ModelInfo dict."""
    caps = []
    for key, label in (("reasoning", "reasoning"), ("vision", "vision"),
                       ("coding", "coding"), ("embedding", "embeddings"),
                       ("image_generation", "image_gen"), ("speech", "audio"),
                       ("tools", "tool_use"), ("streaming", "streaming")):
        if entry.get(key):
            caps.append(label)
    if not caps:
        caps = ["chat", "streaming"]
    tier = "free" if entry.get("free") else "paid" if entry.get("paid") else "unknown"
    status = ("deprecated" if entry.get("deprecated")
              else "preview" if entry.get("preview") else "stable")
    return {
        "id": entry.get("id", ""),
        "provider": entry.get("provider", ""),
        "family": entry.get("family", ""),
        "context_window": int(entry.get("context_length", 0) or 0),
        "capabilities": caps,
        "pricing_tier": tier,
        "status": status,
        "input_price_per_1m": float(entry.get("input_price_per_1m", 0.0) or 0.0),
        "output_price_per_1m": float(entry.get("output_price_per_1m", 0.0) or 0.0),
        "recommendation_badges": entry.get("recommendation_badges", []),
    }


def _resolve_meta(model_id: str, provider_id: str) -> Optional[dict]:
    entry = manager.get_model_meta(model_id, provider_id)
    if entry:
        return _meta_to_legacy(entry)
    return None


# ── Lookup Helpers ─────────────────────────────────────────────────────────

def get_model_info(model_id: str, provider_id: str) -> Optional[dict]:
    """Look up curated metadata for a specific model+provider combination."""
    return _resolve_meta(model_id, provider_id)


def get_price_tier(model_id: str, provider_id: str) -> str:
    """Return 'free', 'paid', or 'unknown'."""
    info = get_model_info(model_id, provider_id)
    if info:
        return info.get("pricing_tier", "unknown")
    lower = model_id.lower()
    if any(kw in lower for kw in ("free", "open-")):
        return "free"
    return "unknown"


def get_capabilities(model_id: str, provider_id: str) -> list[str]:
    """Return list of known capabilities for this model."""
    info = get_model_info(model_id, provider_id)
    if info:
        return list(info.get("capabilities", []))
    return []


def get_badges(model_id: str, provider_id: str) -> list[str]:
    """Return list of badge strings for UI display.
    Each badge is a short color-tagged string like \"[FREE]\", \"[VISION]\", etc.
    """
    badges = []
    info = get_model_info(model_id, provider_id)

    # Pricing badge
    tier = (info.get("pricing_tier", "unknown") if info
            else get_price_tier(model_id, provider_id))
    if tier == "free":
        badges.append("[FREE]")
    elif tier == "paid":
        badges.append("[PAID]")
    else:
        badges.append("[?]")

    # Status badge
    if info:
        status = info.get("status", "")
        if status == "preview":
            badges.append("[PREVIEW]")
        elif status == "experimental":
            badges.append("[EXP]")
        elif status == "deprecated":
            badges.append("[DEPRECATED]")

    # Capability badges
    caps = info.get("capabilities", []) if info else []
    if "vision" in caps:
        badges.append("[VISION]")
    if "reasoning" in caps:
        badges.append("[REASONING]")
    if "coding" in caps:
        badges.append("[CODING]")
    if "image_gen" in caps:
        badges.append("[IMAGE]")
    if "audio" in caps:
        badges.append("[AUDIO]")
    if "embeddings" in caps:
        badges.append("[EMBED]")

    # Context window badge
    if info:
        ctx = info.get("context_window", 0)
        if ctx >= 1000000:
            badges.append("[1M]")
        elif ctx >= 100000:
            badges.append("[100K]")
        elif ctx >= 32000:
            badges.append("[32K]")
        elif ctx >= 8000:
            badges.append("[8K]")

    # Recommendation badges from dynamic registry (e.g. Best for Coding)
    if info:
        for b in info.get("recommendation_badges", []):
            b_clean = f"[{b.strip('[]').upper()}]"
            if b_clean not in badges:
                badges.append(b_clean)

    return badges


def get_family(model_id: str, provider_id: str) -> str:
    """Return the model family name, if known."""
    info = get_model_info(model_id, provider_id)
    if info:
        return info.get("family", "")
    return ""


def get_context_window(model_id: str, provider_id: str) -> int:
    """Return the context window size, if known."""
    info = get_model_info(model_id, provider_id)
    if info:
        return info.get("context_window", 0)
    return 0


# ── Dynamic Merge ──────────────────────────────────────────────────────────

def enrich_models(provider_id: str, model_ids: list[str]) -> list[dict]:
    """Merge dynamic model list with curated metadata.

    Returns a list of dicts, one per model, sorted alphabetically:
        {"id": str, "pricing_tier": str, "badges": list[str],
         "capabilities": list[str], "family": str, "context_window": int}
    """
    result = []
    for mid in model_ids:
        info = get_model_info(mid, provider_id)
        if info:
            result.append({
                "id": mid,
                "pricing_tier": info.get("pricing_tier", "unknown"),
                "badges": get_badges(mid, provider_id),
                "capabilities": list(info.get("capabilities", [])),
                "family": info.get("family", ""),
                "context_window": info.get("context_window", 0),
                "status": info.get("status", "stable"),
            })
        else:
            tier = get_price_tier(mid, provider_id)
            result.append({
                "id": mid,
                "pricing_tier": tier,
                "badges": ["[?]"],
                "capabilities": [],
                "family": "",
                "context_window": 0,
                "status": "unknown",
            })
    result.sort(key=lambda x: x["id"].lower())
    return result


def tier_sort_key(entry: dict) -> int:
    """Sort key: free (0) before paid (1) before unknown (2)."""
    t = entry.get("pricing_tier", "unknown")
    return {"free": 0, "paid": 1, "unknown": 2}.get(t, 2)


def group_by_tier(enriched: list[dict]) -> dict[str, list[dict]]:
    """Group enriched model list by pricing tier.

    Returns {"free": [...], "paid": [...], "unknown": [...]}
    """
    groups: dict[str, list[dict]] = {"free": [], "paid": [], "unknown": []}
    for entry in enriched:
        tier = entry.get("pricing_tier", "unknown")
        groups.setdefault(tier, []).append(entry)
    return groups


# ── Re-exports (new manager API convenience) ───────────────────────────────

def get_providers() -> list[dict]:
    """All provider metadata from providers.json."""
    return manager.list_providers()


def get_provider(provider_id: str) -> Optional[dict]:
    return manager.get_provider(provider_id)
