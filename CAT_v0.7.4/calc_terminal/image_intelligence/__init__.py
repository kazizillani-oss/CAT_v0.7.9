"""
CAT Image Intelligence — Intelligent Attachments with Computer Vision & AI Image Detection (v0.8.0).

Public API:
- Models: AnalysisMode, ProcessingLocation, BoundingBox, DetectionResult, OCRBlock, OCRResult, AuthenticityResult, UnderstandingResult, ImageAnalysisResult
- Authenticity: get_authenticity_detector, AuthenticityDetector, CloudAuthenticityAdapter
- Object Detection: get_object_detector, LocalObjectDetector
- OCR: get_ocr_engine, LocalOCREngine
- Understanding: get_understanding_service, VisionUnderstandingService
- Orchestrator: get_orchestrator, ImageIntelligenceOrchestrator, CancelToken
- Visualizer: Visualizer
"""

from .models import (
    AnalysisMode,
    ProcessingLocation,
    BoundingBox,
    DetectionResult,
    OCRBlock,
    OCRResult,
    AuthenticityResult,
    UnderstandingResult,
    ImageAnalysisResult,
)
from .authenticity import get_authenticity_detector, AuthenticityDetector, CloudAuthenticityAdapter
from .object_detector import get_object_detector, LocalObjectDetector
from .ocr_engine import get_ocr_engine, LocalOCREngine
from .understanding import get_understanding_service, VisionUnderstandingService
from .orchestrator import get_orchestrator, ImageIntelligenceOrchestrator, CancelToken
from .visualizer import Visualizer

__all__ = [
    "AnalysisMode",
    "ProcessingLocation",
    "BoundingBox",
    "DetectionResult",
    "OCRBlock",
    "OCRResult",
    "AuthenticityResult",
    "UnderstandingResult",
    "ImageAnalysisResult",
    "get_authenticity_detector",
    "AuthenticityDetector",
    "CloudAuthenticityAdapter",
    "get_object_detector",
    "LocalObjectDetector",
    "get_ocr_engine",
    "LocalOCREngine",
    "get_understanding_service",
    "VisionUnderstandingService",
    "get_orchestrator",
    "ImageIntelligenceOrchestrator",
    "CancelToken",
    "Visualizer",
]
