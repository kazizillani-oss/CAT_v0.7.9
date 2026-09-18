"""
calc_terminal/compatibility_engine.py
=====================================
CAT Model Compatibility Engine — Intelligent hardware-to-model matching.

Part of CAT (Created by Kazi Zillani).
Calculates realistic operational memory footprints considering:
  - Parameter count (e.g. 1.5B, 3B, 4B, 7B, 14B, 32B, 70B)
  - Quantization format (e.g. Q4_K_M, Q5_K_M, Q8_0, FP16, FP8)
  - Model disk size
  - Target context window (e.g. 4K, 8K, 32K, 128K)
  - KV-cache memory requirements
  - GPU VRAM vs. System RAM hybrid offloading
  - Available memory headroom

Classifies models into the 5 standard CAT tiers:
  🟢 Excellent       — 100% in VRAM, full GPU acceleration, peak tokens/sec.
  🟢 Recommended     — Fully comfortable on device, fast interactive speeds.
  🟡 Usable          — Supported via RAM/CPU offloading; acceptable speed.
  🟠 Heavy           — High RAM consumption; reduced generation speed.
  🔴 Not Recommended — Exceeds total system resources, high risk of OOM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from .hardware_analyzer import HardwareAnalyzer, HardwareProfile


@dataclass
class CompatibilityReport:
    model_name: str
    tier: str              # EXCELLENT, RECOMMENDED, USABLE, HEAVY, NOT_RECOMMENDED
    tier_label: str        # e.g. "🟢 Excellent", "🟢 Recommended", etc.
    tier_label_ascii: str  # e.g. "[EXCELLENT]", "[RECOMMENDED]", etc.
    weights_gb: float
    kv_cache_gb: float
    total_memory_gb: float
    vram_used_gb: float
    ram_offload_gb: float
    estimated_tps: float   # Estimated tokens per second
    summary: str
    details: list[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "tier": self.tier,
            "tier_label": self.tier_label,
            "tier_label_ascii": self.tier_label_ascii,
            "weights_gb": self.weights_gb,
            "kv_cache_gb": self.kv_cache_gb,
            "total_memory_gb": self.total_memory_gb,
            "vram_used_gb": self.vram_used_gb,
            "ram_offload_gb": self.ram_offload_gb,
            "estimated_tps": self.estimated_tps,
            "summary": self.summary,
            "details": self.details,
        }


class ModelCompatibilityEngine:
    """Evaluates how a model will perform on the user's specific hardware."""

    TIER_EXCELLENT = "EXCELLENT"
    TIER_RECOMMENDED = "RECOMMENDED"
    TIER_USABLE = "USABLE"
    TIER_HEAVY = "HEAVY"
    TIER_NOT_RECOMMENDED = "NOT_RECOMMENDED"

    TIER_BADGES = {
        "EXCELLENT": "🟢 Excellent",
        "RECOMMENDED": "🟢 Recommended",
        "USABLE": "🟡 Usable",
        "HEAVY": "🟠 Heavy",
        "NOT_RECOMMENDED": "🔴 Not Recommended",
    }

    TIER_ASCII_BADGES = {
        "EXCELLENT": "[EXCELLENT]",
        "RECOMMENDED": "[RECOMMENDED]",
        "USABLE": "[USABLE]",
        "HEAVY": "[HEAVY]",
        "NOT_RECOMMENDED": "[NOT RECOMMENDED]",
    }

    @classmethod
    def evaluate_model(
        cls,
        model_name: str,
        params_str: str = "",
        size_gb: float = 0.0,
        quant: str = "Q4_K_M",
        context_len: int = 4096,
        hardware: Optional[HardwareProfile] = None,
    ) -> CompatibilityReport:
        """Calculate complete compatibility profile for a model."""
        hw = hardware or HardwareAnalyzer.analyze()

        # 1. Parse parameter count in billions
        billions = cls._parse_params(params_str or model_name)

        # 2. Calculate base weights memory
        if size_gb > 0.1:
            weights_gb = round(size_gb, 2)
        else:
            weights_gb = round(cls._estimate_weights_gb(billions, quant), 2)

        # 3. Calculate KV-cache memory requirement
        kv_cache_gb = round(cls._estimate_kv_cache_gb(billions, context_len), 2)

        # Runtime overhead (CUDA buffers, context allocation) ~0.5 GB
        runtime_overhead = 0.5
        total_memory_gb = round(weights_gb + kv_cache_gb + runtime_overhead, 2)

        # 4. Compare with GPU VRAM and System RAM
        vram_total = hw.gpu.vram_total_gb if hw.gpu.detected else 0.0
        vram_available = hw.gpu.vram_free_gb if hw.gpu.detected else 0.0
        if vram_available <= 0:
            vram_available = vram_total * 0.85

        ram_total = hw.ram.total_gb
        ram_available = hw.ram.available_gb

        # Compute offload split
        if hw.gpu.detected and vram_total > 0.5:
            if total_memory_gb <= vram_available:
                vram_used = total_memory_gb
                ram_offload = 0.0
            else:
                vram_used = max(0.0, vram_available - 0.5)
                ram_offload = max(0.0, total_memory_gb - vram_used)
        else:
            vram_used = 0.0
            ram_offload = total_memory_gb

        # 5. Classify into Tiers
        tier, summary, details, est_tps = cls._classify_tier(
            hw=hw,
            billions=billions,
            weights_gb=weights_gb,
            total_memory_gb=total_memory_gb,
            vram_used=vram_used,
            ram_offload=ram_offload,
            vram_total=vram_total,
            ram_total=ram_total,
            context_len=context_len,
        )

        badge = cls.TIER_BADGES.get(tier, "🟡 Usable")
        badge_ascii = cls.TIER_ASCII_BADGES.get(tier, "[USABLE]")

        return CompatibilityReport(
            model_name=model_name,
            tier=tier,
            tier_label=badge,
            tier_label_ascii=badge_ascii,
            weights_gb=weights_gb,
            kv_cache_gb=kv_cache_gb,
            total_memory_gb=total_memory_gb,
            vram_used_gb=round(vram_used, 2),
            ram_offload_gb=round(ram_offload, 2),
            estimated_tps=est_tps,
            summary=summary,
            details=details,
        )

    @classmethod
    def _parse_params(cls, text: str) -> float:
        """Extract billion parameters from string like '70b', '3.8B', 'qwen2.5-coder:3b'."""
        text = text.lower()
        match = re.search(r"[:\-_]?(\d+(?:\.\d+)?)\s*b\b", text)
        if match:
            try:
                return float(match.group(1))
            except Exception:
                pass
        match_m = re.search(r"[:\-_]?(\d+(?:\.\d+)?)\s*m\b", text)
        if match_m:
            try:
                return float(match_m.group(1)) / 1000.0
            except Exception:
                pass
        # Default fallback
        return 7.0

    @classmethod
    def _estimate_weights_gb(cls, billions: float, quant: str) -> float:
        """Estimate model weights size based on parameter count and quantization."""
        q = quant.upper()
        if "Q2" in q:
            bits = 2.6
        elif "Q3" in q:
            bits = 3.5
        elif "Q4" in q:
            bits = 4.5
        elif "Q5" in q:
            bits = 5.5
        elif "Q6" in q:
            bits = 6.6
        elif "Q8" in q or "FP8" in q:
            bits = 8.5
        elif "16" in q or "FP16" in q:
            bits = 16.0
        else:
            bits = 4.5  # Q4_K_M default

        return max(0.4, (billions * bits) / 8.0)

    @classmethod
    def _estimate_kv_cache_gb(cls, billions: float, context_len: int) -> float:
        """Estimate KV cache memory consumption for target context."""
        # Baseline: ~0.25MB per 1K context for ~7B models, scales with params and context
        heads_dim_factor = max(0.5, (billions / 7.0) ** 0.5)
        mb = (context_len / 1024.0) * 0.25 * heads_dim_factor * 1024.0
        return mb / 1024.0

    @classmethod
    def _classify_tier(
        cls,
        hw: HardwareProfile,
        billions: float,
        weights_gb: float,
        total_memory_gb: float,
        vram_used: float,
        ram_offload: float,
        vram_total: float,
        ram_total: float,
        context_len: int,
    ) -> Tuple[str, str, list[str], float]:
        details = []
        details.append(f"Model parameters: {billions:.1f}B | Operational Memory: {total_memory_gb:.1f} GB")

        total_system_memory = (vram_total if hw.gpu.detected else 0) + ram_total

        # Impossible / Out of Memory
        if total_memory_gb > (total_system_memory * 0.95):
            tier = cls.TIER_NOT_RECOMMENDED
            summary = f"Requires {total_memory_gb:.1f} GB memory; exceeds total system capacity ({total_system_memory:.1f} GB)."
            details.append("High probability of Out-Of-Memory (OOM) crash or extreme disk paging.")
            est_tps = 0.5
            return tier, summary, details, est_tps

        # 100% Fits in GPU VRAM (or Apple Unified Memory)
        if hw.gpu.detected and ram_offload <= 0.05 and vram_total >= total_memory_gb:
            if billions <= 4.0:
                tier = cls.TIER_EXCELLENT
                est_tps = 45.0 if hw.gpu.backend == "CUDA" else 35.0
                summary = f"Fits entirely inside {hw.gpu.name} ({vram_total:.1f} GB VRAM) with zero RAM offloading."
                details.append("Maximum GPU acceleration with low latency.")
            else:
                tier = cls.TIER_RECOMMENDED
                est_tps = 30.0 if hw.gpu.backend == "CUDA" else 25.0
                summary = f"Comfortably accommodated in GPU VRAM with full {hw.gpu.backend} acceleration."
                details.append("High interactive tokens/sec throughput.")
            return tier, summary, details, est_tps

        # Hybrid VRAM + RAM Offload
        if hw.gpu.detected and vram_total >= 3.0:
            offload_pct = (ram_offload / total_memory_gb) * 100.0
            if offload_pct <= 45.0 and total_memory_gb <= (hw.ram.total_gb * 0.7):
                tier = cls.TIER_RECOMMENDED
                est_tps = 18.0
                summary = f"Hybrid execution: {vram_used:.1f} GB in GPU VRAM + {ram_offload:.1f} GB offloaded to System RAM."
                details.append(f"Fast execution with ~{int(100 - offload_pct)}% GPU compute acceleration.")
            elif total_memory_gb <= (hw.ram.total_gb * 0.85):
                tier = cls.TIER_USABLE
                est_tps = 8.0
                summary = f"Partial offload: {vram_used:.1f} GB in VRAM, {ram_offload:.1f} GB in System RAM."
                details.append("Workable for background coding and general questions; generation speed is moderate.")
            else:
                tier = cls.TIER_HEAVY
                est_tps = 2.5
                summary = f"Heavy RAM offload ({ram_offload:.1f} GB); will utilize most available System RAM."
                details.append("Technically runnable, but response generation will be CPU-bound and slow.")
            return tier, summary, details, est_tps

        # CPU Only Inference (No GPU or very small VRAM)
        if total_memory_gb <= (hw.ram.total_gb * 0.45):
            if billions <= 2.0:
                tier = cls.TIER_RECOMMENDED
                est_tps = 14.0
                summary = "Compact architecture runs smoothly on modern CPU."
            else:
                tier = cls.TIER_USABLE
                est_tps = 7.0
                summary = f"Runs purely in System RAM ({total_memory_gb:.1f} GB) via CPU multi-threading."
        elif total_memory_gb <= (hw.ram.total_gb * 0.8):
            tier = cls.TIER_HEAVY
            est_tps = 2.5
            summary = f"Heavy CPU workload: requires {total_memory_gb:.1f} GB of {hw.ram.total_gb:.1f} GB System RAM."
            details.append("Noticeable system slowdown may occur during generation.")
        else:
            tier = cls.TIER_NOT_RECOMMENDED
            est_tps = 0.8
            summary = f"Consumes {total_memory_gb:.1f} GB RAM; risks system freeze or paging."

        return tier, summary, details, est_tps

    def __init__(self, hw: Optional[HardwareProfile] = None):
        self.hw = hw or HardwareAnalyzer.detect()
        self.profile = self.hw

    def evaluate(self, model_dict_or_name: Union[Dict[str, Any], str], context_len: int = 8192) -> CompatibilityReport:
        if isinstance(model_dict_or_name, str):
            name = model_dict_or_name
            params = name
            size_gb = 0.0
        else:
            name = model_dict_or_name.get("name", "model")
            params = model_dict_or_name.get("params", name)
            size_gb = float(model_dict_or_name.get("size_gb", 0.0))
            context_len = int(model_dict_or_name.get("context", context_len))

        return self.evaluate_model(
            model_name=name,
            params_str=params,
            size_gb=size_gb,
            context_len=context_len,
            hardware=self.hw,
        )

    def recommend_models(self, catalog_models: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize catalog models into optimal hardware-supported recommendations."""
        evaluated = []
        for m in catalog_models:
            rep = self.evaluate(m)
            evaluated.append({"model": m, "compat": rep})

        # Filter to viable tiers
        viable = [
            e for e in evaluated
            if e["compat"].tier in (self.TIER_EXCELLENT, self.TIER_RECOMMENDED, self.TIER_USABLE)
        ]

        def _sort_best(items):
            order = {self.TIER_EXCELLENT: 0, self.TIER_RECOMMENDED: 1, self.TIER_USABLE: 2}
            return sorted(items, key=lambda x: (order.get(x["compat"].tier, 9), -x["compat"].estimated_tps))

        coding = [e for e in viable if "coding" in e["model"].get("categories", []) or "code" in e["model"].get("caps", [])]
        reasoning = [e for e in viable if "reasoning" in e["model"].get("categories", []) or "reasoning" in e["model"].get("caps", [])]
        fast = [e for e in viable if "small" in e["model"].get("categories", []) or e["compat"].estimated_tps >= 25.0]

        return {
            "best_coding": _sort_best(coding),
            "best_reasoning": _sort_best(reasoning),
            "best_fast": _sort_best(fast),
            "all_viable": viable,
        }
