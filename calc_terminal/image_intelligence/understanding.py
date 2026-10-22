"""
CAT Image Intelligence — Vision AI Image Understanding (v0.8.0).

Features:
- Integration with existing CAT provider architecture (OpenAI, Gemini, Anthropic, Ollama)
- Verifies model vision capabilities before request (NEVER sends images to text-only models)
- Enforces user privacy and permissions (checks 'internet' permission for cloud vision)
- Explicit cloud transmission indicators [CLOUD AI TRANSMISSION] vs [LOCAL VISION]
- Multi-image comparison, UI screenshot analysis, code transcription, and scientific diagram interpretation
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

from .models import UnderstandingResult


class VisionUnderstandingService:
    """Production image understanding service using the configured AI provider."""

    def __init__(self):
        pass

    def is_cloud_provider(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Determines whether the active or given provider transmits data externally."""
        try:
            if not config:
                from .. import aicore
                config = aicore.load_config()
            prov = str(config.get("provider", "")).lower()
            # Local providers: ollama, localai, llama.cpp, vllm (local host), mock
            if prov in ("ollama", "local", "localai", "mock", "offline"):
                return False
            base_url = str(config.get("base_url", "")).lower()
            if "localhost" in base_url or "127.0.0.1" in base_url:
                return False
            return True
        except Exception:
            return True

    def check_vision_capable(self, config: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """Check whether the active or target model accepts native image payloads."""
        try:
            from .. import attachments as _att
            caps = _att.provider_capabilities(config)
            is_vision = bool(caps.get("vision"))
            if not config:
                from .. import aicore
                config = aicore.load_config()
            model_name = f"{config.get('provider', '?')}/{config.get('model', '?')}"
            return is_vision, model_name
        except Exception as e:
            return False, str(e)

    def check_permissions(self, is_cloud: bool) -> Tuple[bool, Optional[str]]:
        """Verify user permissions before sending data off-machine."""
        if not is_cloud:
            return True, None
        try:
            from .. import permissions as _perm
            pm = _perm.get_manager()
            if not pm.allowed("internet"):
                return False, (
                    "Cloud vision transmission blocked: 'Internet' permission is currently disabled. "
                    "Enable Internet in the Permissions panel or switch to a local Ollama vision model."
                )
        except Exception:
            pass
        return True, None

    def analyze(
        self,
        image_path: str,
        user_prompt: str = "",
        category: str = "general",
        config: Optional[Dict[str, Any]] = None,
        location_preference: str = "auto"
    ) -> UnderstandingResult:
        """Analyze an image using a vision-capable AI model."""
        t0 = time.perf_counter()

        if not os.path.isfile(image_path):
            return UnderstandingResult(
                summary="",
                detailed_analysis="",
                model_id="",
                provider="",
                is_cloud=False,
                category=category,
                latency_ms=0.0,
                error=f"Image file not found: {image_path}"
            )

        if not config:
            from .. import aicore
            config = aicore.load_config()

        is_cloud = self.is_cloud_provider(config)

        # Enforce location preference: if user explicitly asked for LOCAL, refuse cloud transmission
        if location_preference == "local" and is_cloud:
            return UnderstandingResult(
                summary="",
                detailed_analysis="",
                model_id=f"{config.get('provider')}/{config.get('model')}",
                provider=str(config.get("provider", "")),
                is_cloud=True,
                category=category,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                error=(
                    "Local processing was selected, but the active model is a cloud provider "
                    f"({config.get('provider')}). Local mode will not silently transmit data externally. "
                    "Configure a local Ollama vision model (e.g. 'ollama run llava') or allow cloud processing."
                )
            )

        # Verify vision capability: NEVER send image to text-only model
        capable, model_desc = self.check_vision_capable(config)
        if not capable:
            return UnderstandingResult(
                summary="",
                detailed_analysis="",
                model_id=model_desc,
                provider=str(config.get("provider", "")),
                is_cloud=is_cloud,
                category=category,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                error=(
                    f"Active model '{model_desc}' is not vision-capable and does not support image inputs. "
                    "Please switch to a vision model (e.g. gpt-4o, claude-3-5-sonnet, gemini-2.0-flash, or ollama/llava) "
                    "via /model or the Models panel."
                )
            )

        # Check permissions for cloud transmission
        allowed, perm_err = self.check_permissions(is_cloud)
        if not allowed:
            return UnderstandingResult(
                summary="",
                detailed_analysis="",
                model_id=f"{config.get('provider')}/{config.get('model')}",
                provider=str(config.get("provider", "")),
                is_cloud=is_cloud,
                category=category,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                error=perm_err
            )

        # Construct task-focused prompt
        constructed_prompt = self._build_prompt(category, user_prompt)

        try:
            from .. import vision as _vis
            # Normalize and encode image
            mime, b64, meta = _vis.encode_for_model(image_path)

            from .. import aicore
            # Transmit to vision model through existing provider bridge
            resp = _vis._query_vision_model(config, constructed_prompt, mime, b64)

            duration_ms = (time.perf_counter() - t0) * 1000.0

            # Generate concise summary from response
            summary_line = resp.strip().split("\n")[0][:140] if resp else "Visual analysis completed."

            return UnderstandingResult(
                summary=summary_line,
                detailed_analysis=resp,
                model_id=str(config.get("model", "")),
                provider=str(config.get("provider", "")),
                is_cloud=is_cloud,
                category=category,
                latency_ms=duration_ms,
                error=None
            )

        except Exception as exc:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            return UnderstandingResult(
                summary="",
                detailed_analysis="",
                model_id=str(config.get("model", "")),
                provider=str(config.get("provider", "")),
                is_cloud=is_cloud,
                category=category,
                latency_ms=duration_ms,
                error=f"Vision model query failed: {exc}"
            )

    def compare_images(
        self,
        image_paths: List[str],
        comparison_prompt: str = "Compare these images side by side and highlight differences.",
        config: Optional[Dict[str, Any]] = None
    ) -> UnderstandingResult:
        """Compare multiple attached images."""
        t0 = time.perf_counter()
        if not image_paths:
            return UnderstandingResult(
                summary="", detailed_analysis="", model_id="", provider="", is_cloud=False,
                latency_ms=0.0, error="No images provided for comparison."
            )

        if not config:
            from .. import aicore
            config = aicore.load_config()

        is_cloud = self.is_cloud_provider(config)
        allowed, perm_err = self.check_permissions(is_cloud)
        if not allowed:
            return UnderstandingResult(
                summary="", detailed_analysis="", model_id="", provider="", is_cloud=is_cloud,
                latency_ms=0.0, error=perm_err
            )

        capable, model_desc = self.check_vision_capable(config)
        if not capable:
            return UnderstandingResult(
                summary="", detailed_analysis="", model_id=model_desc, provider="", is_cloud=is_cloud,
                latency_ms=0.0, error=f"Active model '{model_desc}' does not support multimodal image comparison."
            )

        try:
            from .. import aicore
            from .. import attachments as _att

            att_objects = []
            for p in image_paths:
                if os.path.isfile(p):
                    att_objects.append(_att.AttachmentManager.create(p))

            prompt = (
                f"You are comparing {len(att_objects)} attached images.\n"
                f"User Request: {comparison_prompt}\n\n"
                "Please analyze similarities, visual differences, layout changes, color palette shifts, "
                "and any textual discrepancies between the attached images."
            )

            resp = aicore.query_ai(
                prompt,
                config=config,
                attachments=att_objects,
                size_class="large"
            )

            duration_ms = (time.perf_counter() - t0) * 1000.0
            return UnderstandingResult(
                summary=f"Comparison of {len(att_objects)} images complete.",
                detailed_analysis=resp,
                model_id=str(config.get("model", "")),
                provider=str(config.get("provider", "")),
                is_cloud=is_cloud,
                category="comparison",
                latency_ms=duration_ms,
                error=None
            )
        except Exception as e:
            return UnderstandingResult(
                summary="", detailed_analysis="", model_id="", provider="", is_cloud=is_cloud,
                latency_ms=(time.perf_counter() - t0) * 1000.0, error=f"Image comparison failed: {e}"
            )

    def _build_prompt(self, category: str, user_prompt: str) -> str:
        """Construct specialized analysis prompt based on image category."""
        base = user_prompt.strip() if user_prompt else "Analyze this image thoroughly."
        strategies = {
            "ui_screenshot": (
                "Examine this user interface screenshot. Transcribe visible window titles, tabs, menus, "
                "active buttons, inputs, error messages, and layout hierarchy. Identify any visual glitches or anomalies."
            ),
            "code_screenshot": (
                "Transcribe all visible code VERBATIM in a fenced block with the appropriate language identifier. "
                "Note any visible bugs, typos, line numbers, or context."
            ),
            "diagram": (
                "Analyze this diagram or chart. Identify all components, relationships, arrows, legend items, and values. "
                "Provide an ASCII/Mermaid structural representation."
            ),
            "scientific_figure": (
                "Examine this scientific figure or graph. State axes, units, data points, error bars, trends, and significance."
            ),
            "general": (
                "Provide a comprehensive, accurate description of the subjects, layout, text, and details in this image."
            )
        }
        strat = strategies.get(category, strategies["general"])
        return f"{base}\n\n[Analysis Strategy: {category}]\n{strat}"


_UNDERSTANDING_SERVICE: Optional[VisionUnderstandingService] = None


def get_understanding_service() -> VisionUnderstandingService:
    global _UNDERSTANDING_SERVICE
    if _UNDERSTANDING_SERVICE is None:
        _UNDERSTANDING_SERVICE = VisionUnderstandingService()
    return _UNDERSTANDING_SERVICE
