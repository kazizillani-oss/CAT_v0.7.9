"""
CAT Image Intelligence — Hybrid Vision Orchestration Layer (v0.8.0).

Features:
- Orchestrates multi-step computer vision and multimodal workflows:
  * Workflow 1: Image → Local OCR → Vision AI → Explanation
  * Workflow 2: Image → Local Object Detector → Bounding Boxes
  * Workflow 3: Image → Authenticity Classifier → Calibrated Prediction & Limitations
  * Workflow 4: UI Screenshot → Vision Model → Project Files → Debugger Agent
  * Workflow 5: Scientific Figure → Visual Analysis → Numerical Extraction
- Lazy loading and on-demand model execution (never runs expensive models unless requested)
- Thread pool execution keeping inference completely off the UI thread
- Progress callbacks, cancellation tokens, and performance benchmarking
"""

from __future__ import annotations

import concurrent.futures
import os
import time
from typing import Any, Callable, Dict, List, Optional, Set

from .authenticity import get_authenticity_detector
from .models import (
    AnalysisMode,
    AuthenticityResult,
    DetectionResult,
    ImageAnalysisResult,
    OCRResult,
    ProcessingLocation,
    UnderstandingResult,
)
from .object_detector import get_object_detector
from .ocr_engine import get_ocr_engine
from .understanding import get_understanding_service


class CancelToken:
    """Thread-safe cancellation token for async vision tasks."""

    def __init__(self):
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled


class ImageIntelligenceOrchestrator:
    """Central orchestration service for all CAT vision capabilities."""

    _instance: Optional[ImageIntelligenceOrchestrator] = None

    def __init__(self, max_workers: int = 3):
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="cat_vision_worker"
        )

    @classmethod
    def get_instance(cls) -> ImageIntelligenceOrchestrator:
        if cls._instance is None:
            cls._instance = ImageIntelligenceOrchestrator()
        return cls._instance

    def analyze_sync(
        self,
        image_path: str,
        modes: Optional[List[str]] = None,
        location: str = "local",
        user_prompt: str = "",
        on_progress: Optional[Callable[[str, float], None]] = None,
        cancel_token: Optional[CancelToken] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> ImageAnalysisResult:
        """Synchronously execute requested vision capabilities on an image."""
        t0 = time.perf_counter()
        if on_progress is None:
            on_progress = lambda _stage, _pct: None

        image_path = os.path.abspath(os.path.expanduser(image_path))
        filename = os.path.basename(image_path)

        # 1. Inspect image dimensions and validity
        w, h, fmt, sz = 0, 0, "", 0
        try:
            from PIL import Image
            with Image.open(image_path) as im:
                w, h = im.size
                fmt = (im.format or "IMAGE").upper()
            sz = os.path.getsize(image_path)
        except Exception as e:
            return ImageAnalysisResult(
                path=image_path,
                filename=filename,
                status="failed",
                error=f"Unreadable or corrupted image: {e}",
                total_time_ms=(time.perf_counter() - t0) * 1000.0
            )

        if not modes:
            modes = [AnalysisMode.HYBRID.value]

        active_modes: Set[str] = set(m.lower() for m in modes)
        is_hybrid = AnalysisMode.HYBRID.value in active_modes or "all" in active_modes

        res = ImageAnalysisResult(
            path=image_path,
            filename=filename,
            width=w,
            height=h,
            format=fmt,
            size_bytes=sz,
            modes_requested=list(modes),
            location=location,
            status="ready"
        )

        # Stage 1: Authenticity Detection
        if (is_hybrid or AnalysisMode.AI_DETECTION.value in active_modes) and not (cancel_token and cancel_token.is_cancelled):
            on_progress("Authenticity Detection", 0.20)
            try:
                auth_det = get_authenticity_detector()
                res.authenticity = auth_det.detect(image_path, prefer_location=location)
            except Exception as e:
                res.authenticity = AuthenticityResult(error=str(e))

        # Stage 2: Object Detection
        if (is_hybrid or AnalysisMode.OBJECT_DETECTION.value in active_modes) and not (cancel_token and cancel_token.is_cancelled):
            on_progress("Object Detection", 0.45)
            try:
                obj_det = get_object_detector()
                res.detection = obj_det.detect(image_path)
            except Exception as e:
                res.detection = DetectionResult(error=str(e))

        # Stage 3: OCR Text Extraction
        if (is_hybrid or AnalysisMode.OCR.value in active_modes) and not (cancel_token and cancel_token.is_cancelled):
            on_progress("OCR Text Extraction", 0.70)
            try:
                ocr_eng = get_ocr_engine()
                res.ocr = ocr_eng.extract_text(image_path)
            except Exception as e:
                res.ocr = OCRResult(error=str(e))

        # Stage 4: Vision AI Understanding
        if (is_hybrid or AnalysisMode.UNDERSTANDING.value in active_modes or user_prompt) and not (cancel_token and cancel_token.is_cancelled):
            on_progress("Vision AI Understanding", 0.90)
            try:
                # Classify category
                from .. import vision as _vis
                cat = _vis.classify_image(image_path, user_prompt)
                und_srv = get_understanding_service()
                res.understanding = und_srv.analyze(
                    image_path,
                    user_prompt=user_prompt,
                    category=cat,
                    config=config,
                    location_preference=location
                )
            except Exception as e:
                res.understanding = UnderstandingResult(error=str(e))

        # Stage 5: Hybrid Synthesis
        if is_hybrid:
            res.hybrid_summary = self._synthesize_hybrid(res, user_prompt)

        on_progress("Completed", 1.0)
        res.total_time_ms = (time.perf_counter() - t0) * 1000.0
        return res

    def analyze_async(
        self,
        image_path: str,
        modes: Optional[List[str]] = None,
        location: str = "local",
        user_prompt: str = "",
        on_progress: Optional[Callable[[str, float], None]] = None,
        cancel_token: Optional[CancelToken] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> concurrent.futures.Future:
        """Run analysis asynchronously off the UI thread."""
        return self._executor.submit(
            self.analyze_sync,
            image_path,
            modes=modes,
            location=location,
            user_prompt=user_prompt,
            on_progress=on_progress,
            cancel_token=cancel_token,
            config=config
        )

    def _synthesize_hybrid(self, res: ImageAnalysisResult, user_prompt: str) -> str:
        """Synthesizes multiple vision signals into an actionable hybrid report."""
        parts = []

        # 1. Authenticity verdict
        if res.authenticity and not res.authenticity.error:
            pct = int(res.authenticity.ai_probability * 100)
            parts.append(f"Authenticity: {res.authenticity.prediction} (~{pct}% estimated AI probability).")

        # 2. Objects summary
        if res.detection and res.detection.objects:
            labels = [obj.label for obj in res.detection.objects[:4]]
            parts.append(f"Objects Identified: {', '.join(labels)}.")

        # 3. OCR summary
        if res.ocr and res.ocr.text.strip():
            w_count = res.ocr.word_count
            parts.append(f"Text Content: Extracted {w_count} word(s) across {len(res.ocr.lines)} line(s).")

        # 4. Understanding summary
        if res.understanding and res.understanding.summary:
            parts.append(f"Visual Analysis: {res.understanding.summary}")

        if not parts:
            return "Visual inspection completed; no significant entities or text recognized."
        return " | ".join(parts)


def get_orchestrator() -> ImageIntelligenceOrchestrator:
    return ImageIntelligenceOrchestrator.get_instance()
