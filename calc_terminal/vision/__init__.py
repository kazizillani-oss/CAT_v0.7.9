"""
CAT v0.8.a Vision Agent — screen capture, frame pipeline, annotation,
visual context, and before/after verification.

Usage (server):
    from calc_terminal.vision.session import VisionSessionManager
    from calc_terminal.vision.context import VisionContextEngine
    from calc_terminal.vision.verify import BeforeAfterVerifier

Usage (frontend JS calls /api/vision/* endpoints on the server).
"""

__version__ = "0.8.a"

from .session import VisionSessionManager, VisionSession, SessionState
from .capture import CaptureEngine, CaptureMode, CaptureConfig
from .frame_pipeline import FramePipeline, FrameMeta, ChangeLevel
from .annotations import AnnotationEngine, Annotation, AnnotationTool
from .context import VisionContextEngine, VisualContext
from .verify import BeforeAfterVerifier, VerificationResult
from .safety import PrivacyController, SafetyConfig
from .provider import VisionProviderRouter
from .cursor import CursorTracker, PointerEvent, DwellRegion
from .priority import FramePriorityEngine, PriorityLevel
from . import events as vision_events

__all__ = [
    "VisionSessionManager", "VisionSession", "SessionState",
    "CaptureEngine", "CaptureMode", "CaptureConfig",
    "FramePipeline", "FrameMeta", "ChangeLevel",
    "AnnotationEngine", "Annotation", "AnnotationTool",
    "VisionContextEngine", "VisualContext",
    "BeforeAfterVerifier", "VerificationResult",
    "PrivacyController", "SafetyConfig",
    "VisionProviderRouter",
    "CursorTracker", "PointerEvent", "DwellRegion",
    "FramePriorityEngine", "PriorityLevel",
    "vision_events",
]

# ---------------------------------------------------------------------------
# Legacy image-pipeline compatibility (calc_terminal/vision.py)
# The file calc_terminal/vision.py (image validation/normalization +
# vision-capable model routing) and the package calc_terminal/vision/
# (screen-capture agent) share the import name.  Python prefers the
# package directory, so `import calc_terminal.vision` would hide the file.
# Re-expose the file's public symbols here so `from calc_terminal import
# vision` and `vision.pil_available()` keep working without a rename.
try:
    import importlib.util as _ilu
    import pathlib as _pl
    _vision_file = _pl.Path(__file__).with_name("vision.py")
    # When this package is loaded as `calc_terminal.vision`, the file is
    # `calc_terminal/vision.py`'s sibling (one directory up).
    if not _vision_file.exists():
        _vision_file = _pl.Path(__file__).parent.parent / "vision.py"
        # fallback: the classic location is calc_terminal/vision.py next
        # to the package directory.
        if not _vision_file.exists():
            _vision_file = _pl.Path(__file__).parent / "vision.py"
    if _vision_file.exists():
        _spec = _ilu.spec_from_file_location(
            "calc_terminal._vision_image", str(_vision_file))
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
        # Re-export the image pipeline API
        for _name in (
            "MAX_DIMENSION", "MAX_BYTES", "JPEG_QUALITY",
            "PROVIDER_NATIVE", "ALL_IMAGE_EXTS",
            "pil_available", "ocr_available", "ImageError",
            "validate", "classify_image", "inspect",
            "normalize", "encode_for_model",
            "analysis_prompt", "BASE_ANALYSIS_PROMPT",
            "run_local_ocr", "find_vision_config", "analyze",
        ):
            if hasattr(_mod, _name):
                globals()[_name] = getattr(_mod, _name)
        # Backward-compat: `vision.vision` self-reference (some probes do
        # `from calc_terminal import vision; vision.vision`?)
        __all__.extend([n for n in (
            "pil_available", "ocr_available", "ImageError",
            "validate", "classify_image", "inspect",
            "normalize", "encode_for_model",
            "analysis_prompt", "BASE_ANALYSIS_PROMPT",
            "run_local_ocr", "find_vision_config", "analyze",
            "MAX_DIMENSION", "MAX_BYTES",
        ) if n not in __all__])
except Exception:
    pass
