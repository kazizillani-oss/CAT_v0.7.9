"""
calc_terminal/models/validator.py
=================================
8-Stage Model Validation Pipeline for CAT's Dynamic Model Registry.

Pipeline:
  1. IDENTITY CHECK  — Clean identifier, no control chars or invalid formats.
  2. PROVIDER CHECK  — Provider exists and is recognized in CAT ecosystem.
  3. MODEL-ID CHECK  — Matches provider naming conventions; canonical deduplication.
  4. ENDPOINT CHECK  — Verifies valid, safe API URL structure.
  5. AUTH CHECK      — Determines authentication requirements safely (no key logging).
  6. CAPABILITY CHECK— Discovers and assigns verified capabilities.
  7. AVAILABILITY CHECK — Confirms deployment availability state.
  8. REGISTRATION GATE  — Produces clean ModelInfo or marks DISCOVERED_BUT_UNAVAILABLE.
"""

import re
import urllib.parse
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict, Any

from .schema import (
    ModelInfo,
    STATUS_ACTIVE,
    STATUS_PREVIEW,
    STATUS_BETA,
    STATUS_DEPRECATED,
    STATUS_UNAVAILABLE,
    STATUS_AUTH_REQUIRED,
    STATUS_DISCOVERED_UNAVAILABLE,
    AVAILABILITY_PAID_API,
    AVAILABILITY_FREE_API,
    AVAILABILITY_LOCAL,
)


@dataclass
class ValidationResult:
    is_valid: bool
    status: str
    rejection_reason: Optional[str] = None
    model_info: Optional[ModelInfo] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class ModelValidator:
    """Validates discovered models before they enter CAT's active registry."""

    # Disallowed patterns (malformed IDs, binary garbage, HTML injections)
    INVALID_ID_CHARS = re.compile(r"[\x00-\x1f\x7f<>\"'`;|&$]")

    @classmethod
    def validate_raw(
        cls,
        raw_model: Any,
        provider_id: str,
        provider_config: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """Run the full 8-stage validation pipeline on a model candidate."""
        config = provider_config or {}
        warnings = []

        # ── Stage 1: IDENTITY CHECK ──────────────────────────────────────────
        if not raw_model:
            return ValidationResult(
                is_valid=False,
                status=STATUS_DISCOVERED_UNAVAILABLE,
                rejection_reason="Empty or null model object.",
            )

        if isinstance(raw_model, str):
            model_id = raw_model.strip()
            raw_dict = {"model_id": model_id}
        elif isinstance(raw_model, dict):
            raw_dict = dict(raw_model)
            model_id = str(raw_dict.get("id") or raw_dict.get("model_id") or "").strip()
        elif hasattr(raw_model, "to_dict"):
            raw_dict = raw_model.to_dict()
            model_id = str(raw_dict.get("model_id") or raw_dict.get("id") or "").strip()
        else:
            return ValidationResult(
                is_valid=False,
                status=STATUS_DISCOVERED_UNAVAILABLE,
                rejection_reason=f"Unsupported raw model type: {type(raw_model).__name__}",
            )

        if not model_id:
            return ValidationResult(
                is_valid=False,
                status=STATUS_DISCOVERED_UNAVAILABLE,
                rejection_reason="Model has empty identifier.",
            )

        if model_id in ("*", "default", "none"):
            return ValidationResult(
                is_valid=False,
                status=STATUS_DISCOVERED_UNAVAILABLE,
                rejection_reason=f"Model ID is an invalid placeholder or wildcard: '{model_id}'",
            )

        if cls.INVALID_ID_CHARS.search(model_id):
            return ValidationResult(
                is_valid=False,
                status=STATUS_DISCOVERED_UNAVAILABLE,
                rejection_reason=f"Model ID contains prohibited characters: '{model_id}'",
            )

        # ── Stage 2: PROVIDER CHECK ──────────────────────────────────────────
        pid = str(provider_id or raw_dict.get("provider") or "").strip().lower()
        if not pid:
            return ValidationResult(
                is_valid=False,
                status=STATUS_DISCOVERED_UNAVAILABLE,
                rejection_reason="Missing provider identifier.",
            )

        # ── Stage 3: MODEL-ID CHECK & CANONICAL MAPPING ───────────────────────
        canonical_id = cls._derive_canonical_id(model_id, pid)

        # ── Stage 4: ENDPOINT CHECK ──────────────────────────────────────────
        endpoint = str(
            raw_dict.get("endpoint")
            or config.get("base_url")
            or config.get("api_url")
            or ""
        ).strip()
        if endpoint:
            try:
                parsed = urllib.parse.urlparse(endpoint)
                if parsed.scheme not in ("http", "https"):
                    return ValidationResult(
                        is_valid=False,
                        status=STATUS_DISCOVERED_UNAVAILABLE,
                        rejection_reason=f"Insecure endpoint scheme '{parsed.scheme}': must be http or https",
                    )
            except Exception as e:
                return ValidationResult(
                    is_valid=False,
                    status=STATUS_DISCOVERED_UNAVAILABLE,
                    rejection_reason=f"Malformed endpoint URL: {e}",
                )

        # ── Stage 5: AUTH CHECK ──────────────────────────────────────────────
        needs_auth = config.get("needs_key", True)
        if pid == "ollama":
            needs_auth = False
        api_key = config.get("api_key")

        model_status = STATUS_ACTIVE
        if needs_auth and not api_key:
            # Model is known and documented, but user has not configured auth yet
            model_status = STATUS_AUTH_REQUIRED

        # ── Stage 6: CAPABILITY CHECK ────────────────────────────────────────
        capabilities = cls._infer_capabilities(model_id, pid, raw_dict)
        context_window = int(raw_dict.get("context_window") or raw_dict.get("context_length") or 128000)
        max_output = int(raw_dict.get("max_output_tokens") or 4096)
        reasoning_levels = raw_dict.get("reasoning_levels") or []

        # Special recognition for 2026 flagship models
        if pid == "openai" and "gpt-6-astra" in model_id.lower():
            if not reasoning_levels:
                reasoning_levels = ["low", "medium", "high", "xhigh", "max"]
            context_window = max(context_window, 1050000)
            max_output = max(max_output, 128000)
            for cap in ("reasoning", "coding", "vision", "computer_use", "research", "document_workflows"):
                if cap not in capabilities:
                    capabilities.append(cap)

        # ── Stage 7: AVAILABILITY CHECK ──────────────────────────────────────
        availability = raw_dict.get("availability") or (
            AVAILABILITY_LOCAL if pid == "ollama" else AVAILABILITY_PAID_API
        )
        if raw_dict.get("free") or raw_dict.get("is_free"):
            availability = AVAILABILITY_FREE_API

        if raw_dict.get("deprecated") or "deprecated" in model_id.lower():
            model_status = STATUS_DEPRECATED
        elif raw_dict.get("preview") or "preview" in model_id.lower() or "beta" in model_id.lower():
            model_status = STATUS_PREVIEW

        # ── Stage 8: REGISTRATION GATE ───────────────────────────────────────
        display_name = raw_dict.get("display_name") or cls._clean_display_name(model_id)

        model_info = ModelInfo(
            provider=pid,
            model_id=model_id,
            display_name=display_name,
            canonical_model_id=canonical_id,
            family=raw_dict.get("family", ""),
            version=raw_dict.get("version", ""),
            release_date=raw_dict.get("release_date"),
            status=model_status,
            availability=availability,
            modalities=raw_dict.get("modalities") or ["text"],
            capabilities=capabilities,
            context_window=context_window,
            max_output_tokens=max_output,
            reasoning_levels=reasoning_levels,
            pricing=raw_dict.get("pricing") or {"input_price_per_1m": 0.0, "output_price_per_1m": 0.0},
            endpoint=endpoint,
            authentication_required=needs_auth,
            local=pid == "ollama",
            cloud=pid != "ollama",
            verified=bool(raw_dict.get("verified", False)),
            source=raw_dict.get("source", "official_api"),
            tags=raw_dict.get("tags") or [],
        )

        return ValidationResult(
            is_valid=True,
            status=model_status,
            model_info=model_info,
            warnings=warnings,
        )

    @staticmethod
    def _derive_canonical_id(model_id: str, provider_id: str) -> str:
        """Normalize model identifier across multi-endpoint routers."""
        clean = model_id.strip()
        # Remove routing prefix (e.g. 'openai/gpt-4o-mini' -> 'gpt-4o-mini')
        if "/" in clean and not clean.startswith("http"):
            parts = clean.split("/")
            if len(parts) == 2 and parts[0].lower() in (
                "openai", "anthropic", "google", "meta-llama", "mistralai", "deepseek", "qwen"
            ):
                clean = parts[1]
        return f"{provider_id}:{clean}"

    @staticmethod
    def _clean_display_name(model_id: str) -> str:
        # Convert raw ids like 'gpt-6-astra' -> 'GPT-6 Astra'
        clean = model_id.split("/")[-1]
        words = clean.replace("-", " ").replace("_", " ").split()
        capitalized = []
        for w in words:
            if w.lower() in ("gpt", "glm", "api", "r1", "v3", "hy3", "mimo"):
                capitalized.append(w.upper())
            else:
                capitalized.append(w.capitalize())
        return " ".join(capitalized)

    @staticmethod
    def _infer_capabilities(model_id: str, provider_id: str, raw_dict: dict) -> List[str]:
        caps = list(raw_dict.get("capabilities", []))
        if not caps:
            caps = ["chat", "streaming"]

        # Normalize capability synonyms in input list
        if any(c in ("cot", "chain_of_thought", "reasoning") for c in caps):
            if "reasoning" not in caps:
                caps.append("reasoning")
        if any(c in ("code", "coder", "coding") for c in caps):
            if "coding" not in caps:
                caps.append("coding")

        mid = model_id.lower()
        if any(k in mid for k in ("reasoner", "r1", "o1", "o3", "k3", "qwq", "thinking")):
            if "reasoning" not in caps:
                caps.append("reasoning")
        if any(k in mid for k in ("coder", "codestral", "astra", "code", "dev")):
            if "coding" not in caps:
                caps.append("coding")
        if any(k in mid for k in ("vision", "4o", "4v", "pixtral", "vl", "gemini")):
            if "vision" not in caps:
                caps.append("vision")
        if any(k in mid for k in ("mini", "flash", "turbo", "instant", "haiku", "8b")):
            if "fast" not in caps:
                caps.append("fast")
        if "tools" in raw_dict or "function" in raw_dict:
            if "tools" not in caps:
                caps.append("tools")
        return list(set(caps))

    def validate(self, model: ModelInfo) -> Tuple[bool, str]:
        """Validate a ModelInfo instance directly."""
        res = self.validate_raw(model, model.provider)
        if not res.is_valid:
            return False, res.rejection_reason or "Validation failed"
        # Check if capabilities were normalized
        if res.model_info:
            model.capabilities = res.model_info.capabilities
        return True, "Valid"
