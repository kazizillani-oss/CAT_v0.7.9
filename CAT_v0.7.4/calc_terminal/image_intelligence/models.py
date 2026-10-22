"""
CAT Image Intelligence — Data Models and Structures (v0.8.0).

Defines standardized data classes, enums, and serialization helpers for:
- AI-Generated Image Authenticity Detection
- Local Object Detection and Bounding Box Geometry
- Optical Character Recognition (OCR) and Text Extraction
- Vision AI Image Understanding
- Hybrid Vision Orchestration
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class AnalysisMode(str, Enum):
    AI_DETECTION = "ai_detection"
    OBJECT_DETECTION = "object_detection"
    OCR = "ocr"
    UNDERSTANDING = "understanding"
    HYBRID = "hybrid"


class ProcessingLocation(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    HYBRID = "hybrid"


@dataclass
class BoundingBox:
    """Normalized bounding box coordinates (0.0 to 1.0) with label and score."""
    ymin: float
    xmin: float
    ymax: float
    xmax: float
    label: str
    confidence: float = 0.0
    color: str = "cyan"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ymin": round(self.ymin, 4),
            "xmin": round(self.xmin, 4),
            "ymax": round(self.ymax, 4),
            "xmax": round(self.xmax, 4),
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "color": self.color,
        }

    def pixel_coords(self, width: int, height: int) -> Tuple[int, int, int, int]:
        """Convert normalized coordinates to absolute pixel box (x1, y1, x2, y2)."""
        x1 = max(0, int(self.xmin * width))
        y1 = max(0, int(self.ymin * height))
        x2 = min(width, int(self.xmax * width))
        y2 = min(height, int(self.ymax * height))
        return (x1, y1, x2, y2)


@dataclass
class DetectionResult:
    """Object detection outcome for one image."""
    objects: List[BoundingBox] = field(default_factory=list)
    model_id: str = "local-detector"
    device: str = "cpu"
    inference_time_ms: float = 0.0
    error: Optional[str] = None

    @property
    def count(self) -> int:
        return len(self.objects)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "model_id": self.model_id,
            "device": self.device,
            "inference_time_ms": round(self.inference_time_ms, 2),
            "objects": [obj.to_dict() for obj in self.objects],
            "error": self.error,
        }


@dataclass
class OCRBlock:
    """One recognized block, line, or word of text with optional coordinates."""
    text: str
    confidence: float = 1.0
    bbox: Optional[Tuple[float, float, float, float]] = None  # ymin, xmin, ymax, xmax

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "confidence": round(self.confidence, 4),
            "bbox": self.bbox,
        }


@dataclass
class OCRResult:
    """OCR extraction outcome for one image."""
    text: str = ""
    lines: List[str] = field(default_factory=list)
    blocks: List[OCRBlock] = field(default_factory=list)
    engine: str = "none"
    confidence: float = 0.0
    inference_time_ms: float = 0.0
    error: Optional[str] = None

    @property
    def word_count(self) -> int:
        return len(self.text.split()) if self.text else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "line_count": len(self.lines),
            "word_count": self.word_count,
            "engine": self.engine,
            "confidence": round(self.confidence, 4),
            "inference_time_ms": round(self.inference_time_ms, 2),
            "error": self.error,
        }


@dataclass
class AuthenticityResult:
    """AI-generated vs authentic image detection outcome."""
    prediction: str = "Uncertain / Inconclusive"  # "Likely AI-Generated" | "Likely Authentic / Human" | "Uncertain"
    ai_probability: float = 0.5                   # 0.0 (definitely authentic) to 1.0 (definitely AI)
    confidence_score: float = 0.0                 # calibration score: 0.0 (low) to 1.0 (high)
    model_id: str = "cat-spectral-authenticity-v1"
    method: str = "spectral_residual_analysis"
    device: str = "cpu"
    provenance_info: Dict[str, Any] = field(default_factory=dict)
    spectral_metrics: Dict[str, Any] = field(default_factory=dict)
    noise_metrics: Dict[str, Any] = field(default_factory=dict)
    limitations: List[str] = field(default_factory=lambda: [
        "JPEG re-compression, social media filters, or resizing can alter high-frequency artifacts.",
        "Unfamiliar generator architectures or fine-tuned diffusion models may evade current frequency classifiers.",
        "Heavily edited, composited, or digital artwork can yield borderline or ambiguous scores.",
        "This is an algorithmic statistical estimate, not a definitive legal or forensic proof of origin."
    ])
    inference_time_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction": self.prediction,
            "ai_probability": round(self.ai_probability, 4),
            "confidence_score": round(self.confidence_score, 4),
            "model_id": self.model_id,
            "method": self.method,
            "device": self.device,
            "provenance_info": self.provenance_info,
            "spectral_metrics": self.spectral_metrics,
            "noise_metrics": self.noise_metrics,
            "limitations": self.limitations,
            "inference_time_ms": round(self.inference_time_ms, 2),
            "error": self.error,
        }


@dataclass
class UnderstandingResult:
    """Vision-capable AI analysis outcome."""
    summary: str = ""
    detailed_analysis: str = ""
    model_id: str = ""
    provider: str = ""
    is_cloud: bool = False
    category: str = "general"
    latency_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "detailed_analysis": self.detailed_analysis,
            "model_id": self.model_id,
            "provider": self.provider,
            "is_cloud": self.is_cloud,
            "category": self.category,
            "latency_ms": round(self.latency_ms, 2),
            "error": self.error,
        }


@dataclass
class ImageAnalysisResult:
    """Complete unified image intelligence report for one attachment."""
    path: str
    filename: str
    width: int = 0
    height: int = 0
    format: str = ""
    size_bytes: int = 0
    modes_requested: List[str] = field(default_factory=list)
    location: str = "local"
    status: str = "ready"  # "ready" | "partial" | "failed"
    authenticity: Optional[AuthenticityResult] = None
    detection: Optional[DetectionResult] = None
    ocr: Optional[OCRResult] = None
    understanding: Optional[UnderstandingResult] = None
    hybrid_summary: Optional[str] = None
    total_time_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "filename": self.filename,
            "dimensions": f"{self.width}x{self.height}",
            "format": self.format,
            "size_bytes": self.size_bytes,
            "modes_requested": self.modes_requested,
            "location": self.location,
            "status": self.status,
            "total_time_ms": round(self.total_time_ms, 2),
            "authenticity": self.authenticity.to_dict() if self.authenticity else None,
            "detection": self.detection.to_dict() if self.detection else None,
            "ocr": self.ocr.to_dict() if self.ocr else None,
            "understanding": self.understanding.to_dict() if self.understanding else None,
            "hybrid_summary": self.hybrid_summary,
            "error": self.error,
        }

    def to_context_block(self) -> str:
        """Format as structured, untrusted context block for agents and models."""
        lines = [
            f"=== IMAGE INTELLIGENCE ANALYSIS: {self.filename} ===",
            f"Dimensions: {self.width} × {self.height} | Format: {self.format} | Processing: {self.location.upper()}"
        ]

        if self.authenticity:
            prob_pct = int(self.authenticity.ai_probability * 100)
            conf_pct = int(self.authenticity.confidence_score * 100)
            lines.append(f"\n[AI-Generated Image Authenticity Estimate]")
            lines.append(f"Verdict: {self.authenticity.prediction} (Estimate: {prob_pct}% AI probability, calibrated confidence: {conf_pct}%)")
            lines.append(f"Model: {self.authenticity.model_id} via {self.authenticity.method}")
            if self.authenticity.provenance_info.get("generator_metadata"):
                lines.append(f"Provenance Evidence: Detected {self.authenticity.provenance_info['generator_metadata']}")
            if self.authenticity.limitations:
                lines.append(f"Forensic Limitation: {self.authenticity.limitations[0]}")

        if self.detection and self.detection.objects:
            lines.append(f"\n[Detected Visual Objects ({self.detection.count})]")
            for i, obj in enumerate(self.detection.objects[:15], 1):
                conf = int(obj.confidence * 100)
                box_str = f"[{obj.ymin:.2f}, {obj.xmin:.2f}, {obj.ymax:.2f}, {obj.xmax:.2f}]"
                lines.append(f"  {i}. {obj.label} ({conf}% conf) at {box_str}")

        if self.ocr and self.ocr.text.strip():
            lines.append(f"\n[Extracted Text (OCR via {self.ocr.engine})]")
            lines.append("```text")
            lines.append(self.ocr.text.strip()[:3000])
            lines.append("```")

        if self.understanding and (self.understanding.summary or self.understanding.detailed_analysis):
            cloud_tag = "[CLOUD AI]" if self.understanding.is_cloud else "[LOCAL VISION]"
            lines.append(f"\n[Vision AI Understanding {cloud_tag} - Model: {self.understanding.model_id}]")
            text = self.understanding.detailed_analysis or self.understanding.summary
            lines.append(text.strip())

        if self.hybrid_summary:
            lines.append(f"\n[Hybrid Orchestration Synthesis]\n{self.hybrid_summary.strip()}")

        lines.append(f"=== END IMAGE INTELLIGENCE ANALYSIS ===")
        return "\n".join(lines)
