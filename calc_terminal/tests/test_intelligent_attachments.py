"""
Comprehensive Test Suite for Intelligent Attachments & Computer Vision (v0.8.0).

Tests:
- Image upload and validation
- Multiple attachments (images + code + documents)
- Corrupt and unsupported files
- Local OCR success and graceful fallback
- Object detection results, empty results, and bounding box overlays
- Missing model weights handling
- AI image authenticity classifier outputs and provenance
- Unsupported provider capabilities (prevent text-only model vision calls)
- Local-only operation without internet
- Cloud permission enforcement
- Provider error and rate limit handling
- Cancellation and cleanup
- UI responsiveness and async thread pool execution
- Agent integration (analyze_image tool with prompt-injection guard)
- Preservation of existing attachments (code, markdown, PDF, archives)
"""

import io
import os
import tempfile
import time
import pytest
from unittest.mock import MagicMock, patch

from PIL import Image, ImageDraw

from calc_terminal.attachments import (
    Attachment,
    AttachmentManager,
    detect_kind,
    extract_attachment,
    provider_capabilities,
)
from calc_terminal.image_intelligence import (
    AnalysisMode,
    AuthenticityDetector,
    AuthenticityResult,
    BoundingBox,
    CancelToken,
    CloudAuthenticityAdapter,
    DetectionResult,
    ImageAnalysisResult,
    UnderstandingResult,
    LocalObjectDetector,
    LocalOCREngine,
    OCRBlock,
    OCRResult,
    ProcessingLocation,
    Visualizer,
    get_authenticity_detector,
    get_object_detector,
    get_ocr_engine,
    get_orchestrator,
    get_understanding_service,
)
from calc_terminal import agent


@pytest.fixture
def sample_image():
    """Generates a temporary clean test image."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        im = Image.new("RGB", (200, 100), color=(240, 240, 240))
        d = ImageDraw.Draw(im)
        d.rectangle([20, 20, 80, 80], fill=(20, 100, 200))
        d.text((90, 40), "TEST", fill=(0, 0, 0))
        im.save(f.name)
        path = f.name
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def blank_image():
    """Generates a plain solid color image."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        im = Image.new("RGB", (100, 100), color=(128, 128, 128))
        im.save(f.name)
        path = f.name
    yield path
    if os.path.exists(path):
        os.remove(path)


# ---------------------------------------------------------------------------
# 1. Image upload and validation
# ---------------------------------------------------------------------------

def test_image_upload_and_validation(sample_image):
    kind = detect_kind(sample_image)
    assert kind == "image"

    att = AttachmentManager.create(sample_image)
    assert att.is_ready()
    assert att.kind == "image"
    assert att.size > 0
    assert "IMAGE" in att.content or "ATTACHED IMAGE" in att.content or "Dimensions" in att.content


# ---------------------------------------------------------------------------
# 2. Multiple attachments (images + code + documents)
# ---------------------------------------------------------------------------

def test_multiple_attachments(sample_image):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f_py:
        f_py.write("def calculate_total(): return 42\n")
        py_path = f_py.name

    try:
        att_img = AttachmentManager.create(sample_image)
        att_code = AttachmentManager.create(py_path)

        assert att_img.is_ready()
        assert att_code.is_ready()
        assert att_code.kind == "code"

        verified = AttachmentManager.verify([att_img, att_code])
        assert verified is True

        ctx = AttachmentManager.build_context([att_img, att_code])
        assert sample_image in ctx or os.path.basename(sample_image) in ctx
        assert "calculate_total" in ctx
    finally:
        if os.path.exists(py_path):
            os.remove(py_path)


# ---------------------------------------------------------------------------
# 3. Corrupt and unsupported files
# ---------------------------------------------------------------------------

def test_corrupt_and_unsupported_files():
    # Zero-byte image
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_zero:
        zero_path = f_zero.name

    try:
        att = AttachmentManager.create(zero_path)
        assert att.is_failed() or "failed" in att.extraction_status or "basic metadata" in (att.content or "")
    finally:
        if os.path.exists(zero_path):
            os.remove(zero_path)

    # Corrupt fake image
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f_corrupt:
        f_corrupt.write(b"NOT_A_REAL_JPEG_IMAGE_CONTENT_HERE")
        corrupt_path = f_corrupt.name

    try:
        orch = get_orchestrator()
        res = orch.analyze_sync(corrupt_path, modes=["hybrid"])
        assert res.status == "failed" or res.error is not None
    finally:
        if os.path.exists(corrupt_path):
            os.remove(corrupt_path)


# ---------------------------------------------------------------------------
# 4. OCR success and graceful fallback
# ---------------------------------------------------------------------------

def test_ocr_success_and_failure(sample_image):
    ocr = get_ocr_engine()
    res = ocr.extract_text(sample_image)
    assert isinstance(res, OCRResult)
    assert res.inference_time_ms >= 0.0

    # Non-existent file
    res_err = ocr.extract_text("non_existent_file_abc_123.png")
    assert res_err.error is not None
    assert "not found" in res_err.error.lower()


# ---------------------------------------------------------------------------
# 5. Object detection results and bounding box overlays
# ---------------------------------------------------------------------------

def test_object_detection_results_and_overlays(sample_image):
    det = get_object_detector()
    res = det.detect(sample_image)
    assert isinstance(res, DetectionResult)
    assert res.error is None
    assert res.inference_time_ms >= 0.0

    # Test Visualizer ASCII overlay rendering
    boxes = [
        BoundingBox(ymin=0.1, xmin=0.1, ymax=0.5, xmax=0.8, label="test-window", confidence=0.85),
        BoundingBox(ymin=0.6, xmin=0.2, ymax=0.9, xmax=0.7, label="button", confidence=0.92),
    ]
    overlay_text = Visualizer.render_ascii_overlay(boxes, width=40, height=10)
    assert "test-window" in overlay_text or "85%" in overlay_text
    assert "┌" in overlay_text and "┘" in overlay_text


# ---------------------------------------------------------------------------
# 6. Empty detection results
# ---------------------------------------------------------------------------

def test_empty_detection_results(blank_image):
    det = get_object_detector()
    res = det.detect(blank_image)
    assert isinstance(res, DetectionResult)
    assert res.error is None


# ---------------------------------------------------------------------------
# 7. Missing model weights handling
# ---------------------------------------------------------------------------

def test_missing_model_weights_handling(sample_image):
    # When deep classifier weights are absent, detector still runs spectral analysis
    det = AuthenticityDetector(weights_dir="/invalid/directory/nonexistent")
    res = det.detect(sample_image)
    assert isinstance(res, AuthenticityResult)
    assert res.ai_probability >= 0.0 and res.ai_probability <= 1.0
    assert len(res.limitations) > 0


# ---------------------------------------------------------------------------
# 8. AI image classifier outputs and provenance
# ---------------------------------------------------------------------------

def test_ai_image_classifier_outputs_and_provenance(sample_image):
    det = get_authenticity_detector()
    res = det.detect(sample_image)
    assert res.prediction in ("Likely AI-Generated", "Likely Authentic / Human-Captured", "Uncertain / Inconclusive")
    assert 0.0 <= res.confidence_score <= 1.0
    assert "limitations" in res.to_dict()
    assert any("JPEG" in lim or "compression" in lim for lim in res.limitations)

    # Test provenance detection with simulated generative metadata
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_prov:
        from PIL import PngImagePlugin
        meta = PngImagePlugin.PngInfo()
        meta.add_text("parameters", "Steps: 20, Sampler: Euler a, CFG scale: 7, Prompt: A futuristic cat")
        im = Image.new("RGB", (100, 100), color=(100, 150, 200))
        im.save(f_prov.name, pnginfo=meta)
        prov_path = f_prov.name

    try:
        res_prov = det.detect(prov_path)
        assert res_prov.provenance_info.get("verified_generator") is True
        assert res_prov.prediction == "Likely AI-Generated"
    finally:
        if os.path.exists(prov_path):
            os.remove(prov_path)


# ---------------------------------------------------------------------------
# 9. Unsupported provider capabilities
# ---------------------------------------------------------------------------

def test_unsupported_provider_capabilities(sample_image):
    text_only_config = {"provider": "openai", "model": "gpt-3.5-turbo"}
    caps = provider_capabilities(text_only_config)
    assert caps.get("vision") is False

    srv = get_understanding_service()
    capable, _ = srv.check_vision_capable(text_only_config)
    assert capable is False

    # Attempting to send image to text-only model returns honest refusal
    res = srv.analyze(sample_image, config=text_only_config)
    assert res.error is not None
    assert "not vision-capable" in res.error


# ---------------------------------------------------------------------------
# 10. Local-only operation without internet
# ---------------------------------------------------------------------------

def test_local_only_operation_without_internet(sample_image):
    cloud_config = {"provider": "openai", "model": "gpt-4o"}
    srv = get_understanding_service()

    # When user requests local-only, cloud config must be rejected
    res = srv.analyze(sample_image, config=cloud_config, location_preference="local")
    assert res.error is not None
    assert "will not silently transmit" in res.error or "Local processing was selected" in res.error


# ---------------------------------------------------------------------------
# 11. Cloud permission enforcement
# ---------------------------------------------------------------------------

def test_cloud_permission_enforcement(sample_image):
    cloud_config = {"provider": "openai", "model": "gpt-4o"}
    srv = get_understanding_service()

    with patch("calc_terminal.permissions.PermissionManager.allowed", return_value=False):
        res = srv.analyze(sample_image, config=cloud_config)
        assert res.error is not None
        assert "Internet" in res.error or "blocked" in res.error


# ---------------------------------------------------------------------------
# 12. Provider error and rate limit handling
# ---------------------------------------------------------------------------

def test_provider_errors_and_rate_limits(sample_image):
    srv = get_understanding_service()
    with patch("calc_terminal.vision._query_vision_model", side_effect=RuntimeError("Rate limit exceeded (HTTP 429)")):
        vision_cfg = {"provider": "gemini", "model": "gemini-2.0-flash"}
        with patch.object(srv, "check_vision_capable", return_value=(True, "gemini/gemini-2.0-flash")):
            with patch.object(srv, "check_permissions", return_value=(True, None)):
                res = srv.analyze(sample_image, config=vision_cfg)
                assert res.error is not None
                assert "429" in res.error or "Rate limit" in res.error


# ---------------------------------------------------------------------------
# 13. Cancellation and cleanup
# ---------------------------------------------------------------------------

def test_cancellation_and_cleanup(sample_image):
    orch = get_orchestrator()
    token = CancelToken()
    token.cancel()

    res = orch.analyze_sync(sample_image, modes=["hybrid"], cancel_token=token)
    assert isinstance(res, ImageAnalysisResult)
    # Since cancelled immediately, stages are bypassed
    assert res.understanding is None or res.understanding.summary == ""


# ---------------------------------------------------------------------------
# 14. UI responsiveness and async thread pool execution
# ---------------------------------------------------------------------------

def test_ui_responsiveness_and_async_executor(sample_image):
    orch = get_orchestrator()
    future = orch.analyze_async(sample_image, modes=["ocr", "object_detection"])
    assert hasattr(future, "result")

    result = future.result(timeout=10.0)
    assert isinstance(result, ImageAnalysisResult)
    assert result.status == "ready"


# ---------------------------------------------------------------------------
# 15. Agent integration (analyze_image tool with prompt-injection guard)
# ---------------------------------------------------------------------------

def test_agent_integration_analyze_image_tool(sample_image):
    assert "analyze_image" in agent.TOOLS

    tool_def = agent.TOOLS["analyze_image"]
    output = tool_def["run"]({"path": sample_image, "mode": "hybrid"})

    assert isinstance(output, str)
    assert "SYSTEM NOTICE" in output
    assert "untrusted visual input" in output or "untrusted user-supplied image" in output
    assert "IMAGE INTELLIGENCE ANALYSIS" in output


# ---------------------------------------------------------------------------
# 16. Preservation of existing attachments (code, markdown, PDF, archives)
# ---------------------------------------------------------------------------

def test_preservation_of_existing_file_attachments():
    with tempfile.TemporaryDirectory() as td:
        # Code attachment
        py_file = os.path.join(td, "script.py")
        with open(py_file, "w", encoding="utf-8") as f:
            f.write("print('hello world')\n")
        att_code = AttachmentManager.create(py_file)
        assert att_code.is_ready()
        assert att_code.kind == "code"
        assert "print('hello world')" in att_code.content

        # Markdown attachment
        md_file = os.path.join(td, "notes.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write("# Architecture Notes\n- Point 1\n- Point 2\n")
        att_md = AttachmentManager.create(md_file)
        assert att_md.is_ready()
        assert att_md.kind == "markdown"
        assert "Architecture Notes" in att_md.content

        # Zip archive attachment
        import zipfile
        zip_path = os.path.join(td, "bundle.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("inner.txt", "archived text")
        att_zip = AttachmentManager.create(zip_path)
        assert att_zip.is_ready()
        assert att_zip.kind == "archive"
        assert "inner.txt" in att_zip.content
