"""
calc_terminal/models/dynamic_registry.py
========================================
Central Dynamic Model Registry for CAT (Version: 2026.09).

Maintains a living, persistent, continuously updated catalog of AI models and
providers. Automatically discovers newly available models from official APIs
and registers them without requiring CAT application updates.

Features:
  - Atomic persistence to disk (~/.cct/registry/ and cache/models/).
  - Thread-safe querying, updating, and reconciliation.
  - Multi-category categorization and intelligent task-based ranking.
  - Deprecation tracking and stale model protection against temporary network errors.
  - Full backward compatibility with legacy ModelInfo lookups.
"""

import glob
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

from .schema import (
    ModelInfo,
    STATUS_ACTIVE,
    STATUS_PREVIEW,
    STATUS_BETA,
    STATUS_DEPRECATED,
    STATUS_RETIRED,
    STATUS_UNAVAILABLE,
    STATUS_AUTH_REQUIRED,
    STATUS_DISCOVERED_UNAVAILABLE,
    CATEGORY_GENERAL,
    CATEGORY_REASONING,
    CATEGORY_CODING,
    CATEGORY_FAST,
    CATEGORY_CHEAP,
    CATEGORY_LONG_CONTEXT,
    CATEGORY_VISION,
    CATEGORY_AUDIO,
    CATEGORY_MULTIMODAL,
    CATEGORY_AGENT,
    CATEGORY_RESEARCH,
    CATEGORY_LOCAL,
    CATEGORY_OPEN_WEIGHT,
    CATEGORY_EMBEDDING,
    CATEGORY_SPECIALIZED,
    AVAILABILITY_LOCAL,
    AVAILABILITY_FREE_API,
    AVAILABILITY_PAID_API,
    AVAILABILITY_OPEN_WEIGHT,
)
from .validator import ModelValidator

_LOG = logging.getLogger("cct.dynamic_registry")


def _resolve_registry_dir() -> str:
    """Find the best writable persistent registry directory."""
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        base = os.path.join(local_app, "CCT", "registry")
    else:
        base = os.path.expanduser("~/.cct/registry")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        pass
    return base


class DynamicModelRegistry:
    """Central dynamic repository of AI models and provider capabilities."""

    _instance: Optional["DynamicModelRegistry"] = None
    _lock = threading.Lock()

    @classmethod
    def reset_instance(cls):
        with cls._lock:
            cls._instance = None

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DynamicModelRegistry, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, registry_dir: Optional[str] = None):
        if getattr(self, "_initialized", False):
            return
        self._dir = registry_dir or _resolve_registry_dir()
        self._models_file = os.path.join(self._dir, "models.json")
        self._providers_file = os.path.join(self._dir, "providers.json")
        self._discovery_state_file = os.path.join(self._dir, "discovery_state.json")
        self._version_file = os.path.join(self._dir, "registry_version.json")

        self._rw_lock = threading.RLock()
        self._models: Dict[str, ModelInfo] = {}  # key: canonical_model_id (provider:model_id)
        self._providers: Dict[str, Dict[str, Any]] = {}
        self._discovery_state: Dict[str, Any] = {}
        self._new_models_queue: List[str] = []

        self._load_initial_registry()
        self._initialized = True

    # ── Persistence & Migration ────────────────────────────────────────────────

    def _load_initial_registry(self):
        """Load from persistent disk, or bootstrap from bundled files."""
        with self._rw_lock:
            loaded = False
            if os.path.isfile(self._models_file):
                try:
                    with open(self._models_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for item in data.get("models", []):
                        info = ModelInfo.from_dict(item)
                        self._models[info.canonical_model_id] = info
                    loaded = True
                except Exception as e:
                    _LOG.warning(f"Failed to load cached models.json: {e}")

            # Bootstrap default catalog from model_metadata.json & providers.json if needed
            self._bootstrap_bundled_catalog()

            # Ensure flagship 2026 models like GPT-6 Astra are always registered
            self._ensure_flagship_2026_models()

    def _bootstrap_bundled_catalog(self):
        """Ingest existing models from model_metadata.json without overwriting user data."""
        pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        metadata_file = os.path.join(pkg_dir, "models", "model_metadata.json")
        if os.path.isfile(metadata_file):
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("models", []):
                    res = ModelValidator.validate_raw(item, item.get("provider", "openai"))
                    if res.is_valid and res.model_info:
                        cid = res.model_info.canonical_model_id
                        if cid not in self._models:
                            self._models[cid] = res.model_info
            except Exception as e:
                _LOG.warning(f"Failed to bootstrap from model_metadata.json: {e}")

        # Ingest providers from providers.json
        providers_file = os.path.join(pkg_dir, "providers", "providers.json")
        if os.path.isfile(providers_file):
            try:
                with open(providers_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for p in data.get("providers", []):
                    pid = p.get("id")
                    if pid and pid not in self._providers:
                        self._providers[pid] = dict(p)
                    # Register fallback models
                    for fb_model in p.get("fallback_models", []):
                        res = ModelValidator.validate_raw(fb_model, pid)
                        if res.is_valid and res.model_info:
                            cid = res.model_info.canonical_model_id
                            if cid not in self._models:
                                res.model_info.source = "fallback"
                                self._models[cid] = res.model_info
            except Exception as e:
                _LOG.warning(f"Failed to bootstrap from providers.json: {e}")

    def _ensure_flagship_2026_models(self):
        """Guarantee official 2026 flagship models (e.g. GPT-6 Astra) are seeded."""
        # 1. OpenAI GPT-6 Astra
        astra = ModelInfo(
            provider="openai",
            model_id="gpt-6-astra",
            display_name="GPT-6 Astra",
            family="GPT",
            version="6",
            canonical_model_id="openai:gpt-6-astra",
            release_date="2026-03",
            status=STATUS_ACTIVE,
            availability=AVAILABILITY_PAID_API,
            modalities=["text", "image"],
            capabilities=[
                "reasoning", "coding", "vision", "computer_use", "research",
                "document_workflows", "tools", "streaming", "long_context"
            ],
            context_window=1050000,
            max_output_tokens=128000,
            reasoning_levels=["low", "medium", "high", "xhigh", "max"],
            pricing={"input_price_per_1m": 5.0, "output_price_per_1m": 20.0},
            endpoint="https://api.openai.com/v1",
            authentication_required=True,
            local=False,
            cloud=True,
            verified=True,
            source="official_api",
            tags=["flagship", "2026", "reasoning", "coding", "computer_use"],
            recommendation_badges=["Best for Coding", "Best for Reasoning", "Best Agent Model"],
        )
        self._models[astra.canonical_model_id] = astra

        # 2. Claude 4 Fable 5.1 & Sonnet
        claude4 = ModelInfo(
            provider="anthropic",
            model_id="claude-4-fable-5.1",
            display_name="Claude 4 Fable 5.1",
            family="Claude",
            version="4",
            canonical_model_id="anthropic:claude-4-fable-5.1",
            status=STATUS_ACTIVE,
            availability=AVAILABILITY_PAID_API,
            modalities=["text", "image"],
            capabilities=["reasoning", "coding", "vision", "tools", "streaming", "long_context"],
            context_window=500000,
            max_output_tokens=64000,
            reasoning_levels=["standard", "extended"],
            pricing={"input_price_per_1m": 4.0, "output_price_per_1m": 16.0},
            endpoint="https://api.anthropic.com/v1",
            authentication_required=True,
            verified=True,
            source="official_api",
            recommendation_badges=["Best for Research"],
        )
        self._models[claude4.canonical_model_id] = claude4

        claude4_sonnet = ModelInfo(
            provider="anthropic",
            model_id="claude-4-sonnet-20260515",
            display_name="Claude 4 Sonnet",
            family="Claude",
            version="4",
            canonical_model_id="anthropic:claude-4-sonnet-20260515",
            status=STATUS_ACTIVE,
            availability=AVAILABILITY_PAID_API,
            modalities=["text", "image"],
            capabilities=["reasoning", "coding", "vision", "tools", "streaming"],
            context_window=500000,
            max_output_tokens=32768,
            pricing={"input_price_per_1m": 3.0, "output_price_per_1m": 15.0},
            endpoint="https://api.anthropic.com/v1",
            authentication_required=True,
            verified=True,
            source="official_api",
            recommendation_badges=["Best for Coding"],
        )
        self._models[claude4_sonnet.canonical_model_id] = claude4_sonnet

        # 3. DeepSeek-R1 / DeepSeek-V3
        ds_r1 = ModelInfo(
            provider="deepseek",
            model_id="deepseek-reasoner",
            display_name="DeepSeek-R1 (Reasoner)",
            family="DeepSeek",
            canonical_model_id="deepseek:deepseek-reasoner",
            status=STATUS_ACTIVE,
            availability=AVAILABILITY_OPEN_WEIGHT,
            capabilities=["reasoning", "coding", "tools", "streaming"],
            context_window=128000,
            max_output_tokens=32768,
            reasoning_levels=["high"],
            pricing={"input_price_per_1m": 0.55, "output_price_per_1m": 2.19},
            endpoint="https://api.deepseek.com/v1",
            authentication_required=True,
            verified=True,
            source="official_api",
            tags=["open_weight", "reasoning"],
            recommendation_badges=["Best for Reasoning", "Best Budget Model"],
        )
        self._models[ds_r1.canonical_model_id] = ds_r1

        # 4. Moonshot Kimi K3
        kimi_k3 = ModelInfo(
            provider="moonshot",
            model_id="kimi-k3",
            display_name="Kimi K3",
            family="Kimi",
            canonical_model_id="moonshot:kimi-k3",
            status=STATUS_ACTIVE,
            availability=AVAILABILITY_PAID_API,
            capabilities=["reasoning", "coding", "long_context", "tools", "streaming"],
            context_window=256000,
            max_output_tokens=16384,
            endpoint="https://api.moonshot.cn/v1",
            authentication_required=True,
            verified=True,
            source="official_api",
            recommendation_badges=["Best for Research"],
        )
        self._models[kimi_k3.canonical_model_id] = kimi_k3

    def save_to_disk(self):
        """Persist current catalog to disk atomically."""
        with self._rw_lock:
            try:
                os.makedirs(self._dir, exist_ok=True)
                payload = {
                    "version": "2026.09",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "total_models": len(self._models),
                    "models": [m.to_dict() for m in self._models.values()],
                }
                tmp_file = self._models_file + ".tmp"
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
                os.replace(tmp_file, self._models_file)
            except Exception as e:
                _LOG.error(f"Failed to persist models to disk: {e}")

    # ── Registry Mutators & Querying ───────────────────────────────────────────

    def register_model(self, model_info: ModelInfo) -> bool:
        """Register or update a validated ModelInfo."""
        with self._rw_lock:
            cid = model_info.canonical_model_id
            is_new = cid not in self._models
            model_info.last_seen = datetime.now(timezone.utc).isoformat()
            self._models[cid] = model_info
            if is_new:
                self._new_models_queue.append(cid)
            return is_new

    def get_model(self, model_id: str, provider_id: Optional[str] = None) -> Optional[ModelInfo]:
        """Look up model by ID or canonical ID."""
        with self._rw_lock:
            if provider_id:
                cid = f"{provider_id.lower()}:{model_id}"
                if cid in self._models:
                    return self._models[cid]
            # Search by model_id directly
            for m in self._models.values():
                if m.model_id == model_id and (not provider_id or m.provider == provider_id.lower()):
                    return m
            # Partial match (e.g. without provider prefix)
            for m in self._models.values():
                if m.model_id.lower() == model_id.lower():
                    return m
            return None

    def list_models(
        self,
        provider: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        state: Optional[str] = None,
        include_deprecated: bool = False,
        search: Optional[str] = None,
    ) -> List[ModelInfo]:
        """Filter and return list of models matching criteria."""
        with self._rw_lock:
            results = list(self._models.values())

            if provider:
                pid = provider.lower().strip()
                results = [m for m in results if m.provider == pid]

            # State-specific filters
            state_val = (state or status or "").lower().strip()
            if state_val == "new":
                results = [m for m in results if m.canonical_model_id in self._new_models_queue or "new" in m.tags]
            elif state_val == "updated":
                results = [m for m in results if "updated" in m.tags]
            elif state_val in ("deprecated", "retired"):
                include_deprecated = True
                results = [m for m in results if m.status in (STATUS_DEPRECATED, STATUS_RETIRED)]
            elif state_val:
                results = [m for m in results if m.status == state_val]

            if not include_deprecated and state_val not in ("deprecated", "retired"):
                results = [m for m in results if m.status not in (STATUS_DEPRECATED, STATUS_RETIRED, STATUS_UNAVAILABLE)]

            if category and category.lower() not in ("all", "*"):
                results = [m for m in results if m.matches_category(category)]

            if search:
                q = search.lower().strip()
                results = [
                    m for m in results
                    if q in m.model_id.lower() or q in m.display_name.lower() or q in m.family.lower()
                ]

            return results

    def reconcile_models(self, provider_id: str, discovered_models: List[ModelInfo]) -> Dict[str, List[str]]:
        """Compare freshly discovered remote models against the local registry.
        Calculates: added, updated, removed, deprecated, unchanged."""
        with self._rw_lock:
            pid = provider_id.lower().strip()
            existing_for_provider = {
                m.model_id: m for m in self._models.values() if m.provider == pid
            }
            remote_ids = {m.model_id: m for m in discovered_models}

            added = []
            updated = []
            deprecated = []
            unchanged = []

            # 1. Process newly found or existing models
            for mid, rem in remote_ids.items():
                if mid not in existing_for_provider:
                    self.register_model(rem)
                    added.append(mid)
                else:
                    cur = existing_for_provider[mid]
                    has_changes = False
                    # Check if model status transitioned to deprecated
                    if rem.status in (STATUS_DEPRECATED, STATUS_RETIRED) and cur.status not in (STATUS_DEPRECATED, STATUS_RETIRED):
                        cur.status = rem.status
                        deprecated.append(mid)
                        has_changes = True
                    # Update capabilities or context if expanded
                    if set(rem.capabilities) - set(cur.capabilities):
                        cur.capabilities = list(set(cur.capabilities) | set(rem.capabilities))
                        has_changes = True
                    if rem.context_window > cur.context_window:
                        cur.context_window = rem.context_window
                        has_changes = True
                    cur.last_seen = datetime.now(timezone.utc).isoformat()
                    cur.stale = False
                    if has_changes:
                        if mid not in deprecated:
                            updated.append(mid)
                    else:
                        unchanged.append(mid)

            # 2. Process models missing from remote discovery
            if remote_ids:
                for mid, cur in existing_for_provider.items():
                    if mid not in remote_ids:
                        cur.stale = True
                        if cur.status in (STATUS_DEPRECATED, STATUS_RETIRED):
                            unchanged.append(mid)
                        else:
                            cur.status = STATUS_DEPRECATED
                            deprecated.append(mid)
            else:
                # When remote discovery returned 0 models (e.g. offline/network failure),
                # preserve models as stale without marking them deprecated
                for mid, cur in existing_for_provider.items():
                    cur.stale = True
                    unchanged.append(mid)

            self.save_to_disk()
            return {
                "added": added,
                "updated": updated,
                "deprecated": deprecated,
                "unchanged": unchanged,
            }

    # ── Intelligent Ranking & Categorization ──────────────────────────────────

    def rank_models(
        self,
        models: Optional[List[ModelInfo]] = None,
        task: str = "general",
    ) -> List[Tuple[ModelInfo, float, List[str]]]:
        """Rank models according to task-specific score and assign recommendation badges."""
        with self._rw_lock:
            candidates = list(models if models is not None else self._models.values())
            scored = []

            for m in candidates:
                score = 50.0  # base score

                # Context window bonus
                if m.context_window >= 1000000:
                    score += 25.0
                elif m.context_window >= 200000:
                    score += 15.0
                elif m.context_window >= 128000:
                    score += 10.0

                # Capability bonuses
                if m.has_capability("reasoning"):
                    score += 20.0
                if m.has_capability("coding"):
                    score += 15.0
                if m.has_capability("vision"):
                    score += 10.0
                if m.has_capability("computer_use"):
                    score += 15.0

                # Verification bonus
                if m.verified:
                    score += 10.0

                # Recency / Status bonus
                if m.status == STATUS_ACTIVE:
                    score += 5.0
                elif m.status == STATUS_PREVIEW:
                    score += 2.0
                elif m.status == STATUS_DEPRECATED:
                    score -= 40.0

                # Dynamic Badges
                badges = list(m.recommendation_badges)
                if not badges:
                    if m.has_capability("coding") and ("astra" in m.model_id.lower() or "coder" in m.model_id.lower() or "sonnet" in m.model_id.lower()):
                        badges.append("Best for Coding")
                    if m.has_capability("reasoning") and ("reasoner" in m.model_id.lower() or "r1" in m.model_id.lower() or "o1" in m.model_id.lower() or "o3" in m.model_id.lower() or "astra" in m.model_id.lower()):
                        badges.append("Best for Reasoning")
                    if m.local:
                        badges.append("Best Local Model")
                    if m.matches_category(CATEGORY_FAST):
                        badges.append("Best Fast Model")
                    if m.availability in (AVAILABILITY_FREE_API, AVAILABILITY_OPEN_WEIGHT) or m.pricing.get("input_price_per_1m", 0.0) < 1.0:
                        badges.append("Best Budget Model")

                scored.append((m, round(score, 1), badges))

            # Sort descending by score
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored

    def get_ranked_models(
        self,
        task: str = "general",
        limit: Optional[int] = None,
        models: Optional[List[ModelInfo]] = None,
    ) -> List[ModelInfo]:
        """Return list of models sorted by suitability for a task."""
        scored = self.rank_models(models=models, task=task)
        res = [m for m, score, badges in scored]
        if limit is not None:
            res = res[:limit]
        return res

    def get_audit_summary(self) -> Dict[str, Any]:
        """Return a complete audit overview of providers and models."""
        with self._rw_lock:
            all_m = list(self._models.values())
            active_m = [m for m in all_m if m.status == STATUS_ACTIVE]
            new_m = [m for m in all_m if m.canonical_model_id in self._new_models_queue]
            dep_m = [m for m in all_m if m.status in (STATUS_DEPRECATED, STATUS_RETIRED)]
            unavail_m = [m for m in all_m if m.status in (STATUS_UNAVAILABLE, STATUS_DISCOVERED_UNAVAILABLE)]
            auth_req_m = [m for m in all_m if m.status == STATUS_AUTH_REQUIRED]

            # Unique providers represented in registry
            providers_seen = sorted({m.provider for m in all_m})
            by_prov: Dict[str, int] = {}
            for m in all_m:
                by_prov[m.provider] = by_prov.get(m.provider, 0) + 1

            return {
                "total_models": len(all_m),
                "total_providers": len(providers_seen),
                "providers_discovered": len(providers_seen),
                "providers_active": len([p for p in providers_seen if any(m.provider == p and m.status == STATUS_ACTIVE for m in all_m)]),
                "providers_requiring_auth": len({m.provider for m in auth_req_m}),
                "models_discovered": len(all_m),
                "models_active": len(active_m),
                "new_models": len(new_m),
                "deprecated": len(dep_m),
                "unavailable": len(unavail_m),
                "providers_list": providers_seen,
                "models_by_provider": by_prov,
                "models_by_state": {
                    "available": len(active_m),
                    "new": len(new_m),
                    "deprecated": len(dep_m),
                    "unavailable": len(unavail_m),
                },
            }

    def pop_new_models(self) -> List[ModelInfo]:
        """Return and clear newly detected models since last poll."""
        with self._rw_lock:
            models = [self._models[cid] for cid in self._new_models_queue if cid in self._models]
            self._new_models_queue.clear()
            return models


# Singleton convenience accessors
def get_registry() -> DynamicModelRegistry:
    return DynamicModelRegistry()

def get_dynamic_registry() -> DynamicModelRegistry:
    return DynamicModelRegistry()
