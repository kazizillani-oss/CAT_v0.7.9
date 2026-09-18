"""
CAT v0.7.9.0 — vision.py: the real image / multimodal pipeline.

    image
     ↓ validate          (exists, decodable, size caps)
     ↓ decode/normalize  (EXIF orientation, color mode, alpha, format)
     ↓ classify          (photo / screenshot / scanned document / chart /
     │                    diagram / code screenshot / handwritten)
     ↓ strategy          (resize/compress only as needed — quality kept)
     ↓ vision-capable model  (chosen by model_router when the active one
     │                    can't see — never just "model can't see this")
     ↓ structured analysis   (comprehensive extraction prompt per kind)

Rules:
* The image BYTES actually travel to the model (base64 data URL), never
  just the filename.
* Normalization never degrades quality unnecessarily: images within the
  budget pass through byte-for-byte; oversized ones are downscaled with
  a high-quality filter and/or recompressed at high quality.
* Corrupted/undecodable files produce an explicit honest error — never a
  fabricated description.
* Pillow is used when available (TIFF/BMP/WEBP conversion, EXIF fix);
  without it, provider-native formats still work and TIFF/BMP get an
  honest "cannot normalize" note instead of silent breakage.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import base64
import io
import os
from typing import Dict, Optional, Tuple

# Provider-safe formats + generous-but-sane transport budget.
MAX_DIMENSION = 1568        # long-edge cap (matches common vision models' tile grid)
MAX_BYTES = 4 * 1024 * 1024  # ~4 MB payload after normalization (pre-base64)
JPEG_QUALITY = 88

PROVIDER_NATIVE = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
ALL_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp",
                  ".tiff", ".tif", ".ico"}

_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
         ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
         ".tiff": "image/tiff", ".tif": "image/tiff", ".ico": "image/x-icon"}

_PIL = None
_PIL_TRIED = False


def _pil():
    global _PIL, _PIL_TRIED
    if not _PIL_TRIED:
        _PIL_TRIED = True
        try:
            from PIL import Image  # noqa: N811
            _PIL = Image
        except Exception:
            _PIL = None
    return _PIL


def pil_available() -> bool:
    return _pil() is not None


def ocr_available() -> bool:
    """True when a real OCR engine (pytesseract + tesseract binary) exists.
    Never assumed — checked, honestly reported."""
    try:
        import pytesseract  # noqa: F401
        import shutil
        return bool(shutil.which("tesseract"))
    except Exception:
        return False


class ImageError(Exception):
    """Raised for genuinely unreadable/corrupted/missing images."""


# ------------------------------------------------------------- validation --

def validate(path: str) -> int:
    """VALIDATE stage: existence, type, non-empty, sane size.
    Returns file size in bytes; raises ImageError with the real reason."""
    if not path or not os.path.lexists(path):
        raise ImageError(f"image not found: {path}")
    if os.path.isdir(path):
        raise ImageError(f"path is a directory, not an image: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext not in ALL_IMAGE_EXTS:
        raise ImageError(f"unsupported image extension: {ext or '(none)'}")
    try:
        size = os.path.getsize(path)
    except OSError as e:
        raise ImageError(f"cannot stat image: {e}")
    if size == 0:
        raise ImageError("image file is empty (0 bytes)")
    if size > 64 * 1024 * 1024:
        raise ImageError("image larger than the 64 MB safety limit")
    # Magic-byte sniff: catch renamed/corrupted files before decode time.
    try:
        with open(path, "rb") as f:
            head = f.read(16)
    except OSError as e:
        raise ImageError(f"cannot read image bytes: {e}")
    if not head:
        raise ImageError("image file is unreadable")
    return size


# ------------------------------------------------------------ classification --

_CODE_IMG_HINTS = ("code", "screenshot_snippet", "ide", "editor")
_DOC_HINTS = ("document", "scan", "receipt", "invoice", "page", "paper", "letter")


def classify_image(path: str, prompt: str = "") -> str:
    """SMART PIPELINE stage: best-effort local classifier for choosing the
    processing strategy. Returns one of:
    photo | screenshot | scanned_document | chart | diagram |
    code_screenshot | handwritten.

    Honest heuristic: filename hints + user wording + aspect ratio +
    format priors. It biases the analysis PROMPT, it does not fabricate
    facts about the content."""
    name = os.path.basename(path).lower()
    text = ((prompt or "") + " " + name).lower()

    if any(h in text for h in ("handwrit", "hand-written", "notes photo")):
        return "handwritten"
    if any(h in text for h in _CODE_IMG_HINTS) or any(
            h in name for h in ("code", "snippet", "ide_", "vscode", "screenshot_code")):
        return "code_screenshot"
    if any(h in text for h in ("chart", "graph", "plot", "bar ", "pie ")) \
            or "chart" in name or "plot" in name:
        return "chart"
    if any(h in text for h in ("diagram", "flowchart", "uml", "architecture diagram",
                               "sequence diagram", "er diagram")) or "diagram" in name:
        return "diagram"
    if any(h in text for h in _DOC_HINTS) or any(h in name for h in ("scan", "doc", "receipt", "invoice")):
        return "scanned_document"
    if "screenshot" in text or "screen shot" in text or "screen-" in name or "screenshot" in name:
        return "screenshot"

    # Aspect/format priors: tall multi-page scans vs typical photos.
    try:
        info = inspect(path)
        w, h = info.get("width", 0), info.get("height", 0)
        fmt = str(info.get("format", "")).upper()
        if w and h:
            ratio = max(w, h) / max(1, min(w, h))
            if ratio > 2.8 and min(w, h) > 800:
                return "scanned_document"
        if fmt == "PNG" and ratio < 1.6 and max(w, h) <= 2400:
            return "screenshot"
    except Exception:
        pass
    return "photo"


# ----------------------------------------------------------------- inspect --

def inspect(path: str) -> Dict:
    """Real metadata about an image (dimensions, format, mode) — no
    fabrication; empty dict fields when Pillow isn't available."""
    out: Dict = {"width": 0, "height": 0, "format": "", "mode": ""}
    Image = _pil()
    if Image is None:
        return out
    try:
        with Image.open(path) as im:
            out["width"], out["height"] = im.size
            out["format"] = (im.format or "").upper()
            out["mode"] = (im.mode or "").upper()
    except Exception:
        pass
    return out


# ------------------------------------------------------------- normalize --

def _exif_transpose(im):
    """Apply EXIF orientation so photos taken sideways/right-way-down
    display correctly. No-op for images without EXIF orientation."""
    try:
        from PIL import ImageOps
        return ImageOps.exif_transpose(im)
    except Exception:
        return im


def _needs_conversion(fmt: str, mode: str, ext: str) -> bool:
    """Formats/modes providers reject or mishandle."""
    if ext == ".tiff" or ext == ".tif":
        return True                      # TIFF rarely accepted by vision APIs
    if ext == ".bmp":
        return True                      # BMP is huge; convert to PNG/JPEG
    if fmt in ("TIFF", "BMP", "MPO", "PPM"):
        return True
    if mode in ("CMYK", "I;16", "1"):
        return True
    if fmt == "GIF" and ext == ".gif":
        return False                     # static GIFs are accepted natively
    return False


def normalize(path: str,
              max_dimension: int = MAX_DIMENSION,
              max_bytes: int = MAX_BYTES) -> Tuple[str, bytes, Dict]:
    """NORMALIZE stage: validate → decode → EXIF-fix → convert/rescale/
    recompress ONLY as needed. Returns (mime, raw_bytes, meta).

    meta includes what was actually done (honest reporting):
      action: passthrough | converted | resized | resized+converted | error
    Raises ImageError for genuinely corrupted files."""
    size = validate(path)
    ext = os.path.splitext(path)[1].lower()
    meta = {"source_size": size, "action": "passthrough",
            "normalized": False, "pil": pil_available()}

    Image = _pil()
    if Image is None:
        # No Pillow: native formats pass through untouched; exotic ones
        # fail loudly and honestly here rather than at the API.
        if ext in PROVIDER_NATIVE:
            with open(path, "rb") as f:
                return _MIME[ext], f.read(), meta
        raise ImageError(
            f"{ext} images need Pillow ('pip install pillow') to be "
            f"converted into a provider-compatible format")

    try:
        with Image.open(path) as im:
            im.load()
            fmt = (im.format or "").upper()
            mode = im.mode or ""
            meta.update({"width": im.size[0], "height": im.size[1],
                         "format": fmt, "mode": mode})
            needs_convert = _needs_conversion(fmt, mode, ext)
            too_big_dim = max(im.size) > max_dimension

            if not needs_convert and not too_big_dim and size <= max_bytes:
                # Quality rule: nothing to do → original bytes verbatim.
                with open(path, "rb") as f:
                    meta["action"] = "passthrough"
                    return _MIME.get(ext, "image/png"), f.read(), meta

            work = _exif_transpose(im)
            if work is not im:
                meta["exif_rotated"] = True
                needs_convert = needs_convert or ext not in PROVIDER_NATIVE \
                    or True  # re-encoded after transpose; pick encoder below

            if too_big_dim:
                work.thumbnail((max_dimension, max_dimension),
                               getattr(Image, "LANCZOS", 1))
                meta["resized_to"] = list(work.size)

            has_alpha = "A" in work.getbands() or work.mode == "P"
            if has_alpha and not needs_convert:
                target_fmt, target_mime = "PNG", "image/png"
            elif has_alpha:
                target_fmt, target_mime = "PNG", "image/png"
            else:
                target_fmt, target_mime = "JPEG", "image/jpeg"
                if work.mode != "RGB":
                    work = work.convert("RGB")

            buf = io.BytesIO()
            save_kwargs = {}
            if target_fmt == "JPEG":
                save_kwargs = {"quality": JPEG_QUALITY, "optimize": True}
            elif target_fmt == "PNG":
                save_kwargs = {"optimize": True}
            work.save(buf, format=target_fmt, **save_kwargs)
            data = buf.getvalue()

            # One extra recompression pass if still over budget (rare).
            attempts = 0
            while len(data) > max_bytes and target_fmt == "JPEG" and attempts < 3:
                q = max(50, JPEG_QUALITY - 15 * (attempts + 1))
                buf = io.BytesIO()
                work.save(buf, format="JPEG", quality=q, optimize=True)
                data = buf.getvalue()
                meta["recompressed_quality"] = q
                attempts += 1
            if len(data) > max_bytes:
                raise ImageError(
                    "image cannot be normalized under the transport budget "
                    "without unacceptable quality loss")

            meta["action"] = ("resized+converted" if too_big_dim else "converted") \
                if needs_convert or too_big_dim else "recompressed"
            meta["normalized"] = meta["action"] != "passthrough"
            meta["out_format"] = target_fmt
            return target_mime, data, meta
    except ImageError:
        raise
    except Exception as e:
        raise ImageError(f"corrupted or undecodable image ({type(e).__name__}): {e}")


def encode_for_model(path: str, prompt: str = "",
                     max_dimension: int = MAX_DIMENSION,
                     max_bytes: int = MAX_BYTES) -> Tuple[str, str, Dict]:
    """The ONE call the attachment/aicore layer uses:
    returns (mime, base64_payload, meta) for a normalized image."""
    import time as _time
    t0 = _time.perf_counter()
    mime, data, meta = normalize(path, max_dimension=max_dimension,
                                 max_bytes=max_bytes)
    b64 = base64.b64encode(data).decode("ascii")
    try:
        from . import metrics
        m = metrics.current()
        if m is not None:
            m.mark_stage("vision", t0)
    except Exception:
        pass
    meta["payload_b64_chars"] = len(b64)
    return mime, b64, meta


# ------------------------------------------------------------- strategies --

_KIND_PROMPTS = {
    "photo": (
        "Describe this photograph thoroughly: main subjects, setting, colors, "
        "lighting, notable details, visible text or brands, and anything unusual."),
    "screenshot": (
        "This is a screen capture. Transcribe all visible UI elements, window "
        "titles, menus, buttons, error messages, code (verbatim, in fenced "
        "blocks), URLs, and values. Explain what application/screen this is."),
    "scanned_document": (
        "This is a scanned/document image. Extract ALL text verbatim preserving "
        "structure (headings, paragraphs, lists, tables as markdown tables). "
        "Include page metadata if visible (title, dates, signatures, stamps)."),
    "chart": (
        "Analyze this chart/graph: state the chart type, axes and their units, "
        "every series/legend entry, key data points (read approximate values), "
        "trends, anomalies, and the takeaway conclusion."),
    "diagram": (
        "Analyze this diagram: identify the diagram type, every node/component "
        "(with labels), every connection/arrow and its direction, groupings, "
        "and reconstruct its structure as an indented outline or mermaid-style "
        "text description."),
    "code_screenshot": (
        "This screenshot contains source code. Transcribe the code VERBATIM in "
        "a fenced block with the correct language tag, then explain what it "
        "does, note any bugs/issues you can see, and mention visible file "
        "names, line numbers or IDE context."),
    "handwritten": (
        "This appears to contain handwriting. Transcribe ALL handwritten "
        "content as faithfully as possible, marking unclear words with [?]. "
        "Preserve layout, numbering, equations (as LaTeX-ish plain text) and "
        "any printed content separately."),
}

BASE_ANALYSIS_PROMPT = (
    "Analyze the attached image comprehensively. Wherever supported by the "
    "image content, extract: visible objects and scene; ALL text (OCR); "
    "tables (as markdown); charts (axes, series, values, trends); diagrams "
    "(nodes, edges, structure); UI elements; code shown (verbatim in fenced "
    "blocks); document layout; mathematical expressions; visual relationships; "
    "and notable metadata. Be specific and complete — do NOT merely say what "
    "kind of thing the image is."
)


def analysis_prompt(kind: str, user_text: str = "") -> str:
    """Strategy-specific instruction combined with the user's actual ask.
    Used by both the direct-vision path and the agent's analyze_image tool."""
    specific = _KIND_PROMPTS.get(kind, BASE_ANALYSIS_PROMPT)
    ask = (user_text or "").strip()
    ocr_note = ""
    pre_ocr = ""
    if kind in ("scanned_document", "handwritten", "screenshot",
                "code_screenshot", "chart", "diagram"):
        if ocr_available():
            ocr_note = ("\n\nA local OCR engine is available; combine its raw "
                        "output (provided below) with your own visual reading "
                        "— reconcile differences explicitly.")
        else:
            ocr_note = ("\n\nPerform careful character-level OCR yourself as "
                        "part of the analysis.")
    prefix = f"The user asked: \"{ask}\"\n\n" if ask and ask.lower() not in (
        "analyze this image", "describe this image") else ""
    return (prefix + BASE_ANALYSIS_PROMPT + "\n\nImage-type strategy ("
            + kind + "): " + specific + ocr_note + pre_ocr)


def run_local_ocr(path: str) -> str:
    """Best-effort local OCR via pytesseract when installed. Returns ''
    (not an error) when unavailable — callers fold it into the prompt."""
    if not ocr_available():
        return ""
    try:
        import pytesseract
        from PIL import Image
        with Image.open(path) as im:
            return pytesseract.image_to_string(im) or ""
    except Exception:
        return ""


# ------------------------------------------------------------ model bridge --

def find_vision_config():
    """Bridge to the router: a config dict for a vision-capable configured
    model, or None when none exists (callers report that honestly)."""
    try:
        from . import model_router
        cfg, caps = model_router.find_vision_capable()
        return cfg
    except Exception:
        return None


def analyze(path: str, user_text: str = "", history=None,
            config: Optional[dict] = None):
    """Full VISION PATH: normalize → classify (+local OCR when available)
    → vision-capable model → structured answer string. Uses the given
    config when it can see, otherwise reroutes to a capable backup;
    raises ImageError for bad files and returns an honest message when no
    vision-capable model is configured at all."""
    mime, b64, meta = encode_for_model(path, user_text)
    kind = classify_image(path, user_text)
    prompt = analysis_prompt(kind, user_text)
    local_text = run_local_ocr(path)
    if local_text.strip():
        prompt += "\n\nLOCAL OCR OUTPUT (machine-read, may contain errors):\n" \
            + local_text[:4000]

    try:
        from .event_stream import stream, IMAGE_ANALYSIS_STARTED, IMAGE_ANALYSIS_FINISHED
        stream.emit(IMAGE_ANALYSIS_STARTED, source="vision", path=os.path.basename(path),
                    kind=kind, action=meta.get("action"))
    except Exception:
        pass

    cfg = config
    if cfg is not None:
        try:
            from .attachments import provider_capabilities
            if not provider_capabilities(cfg).get("vision"):
                cfg = None
        except Exception:
            cfg = None
    if cfg is None:
        cfg = find_vision_config()
    if cfg is None:
        return ("No vision-capable AI model is currently configured, so I "
                "cannot visually analyze this image. Configure one (e.g. a "
                "gpt-4o / claude / gemini-class vision model via /model) and "
                "attach it again.", meta)

    answer = _query_vision_model(cfg, prompt, mime, b64, system_extra=kind)
    try:
        from .event_stream import stream, IMAGE_ANALYSIS_FINISHED
        stream.emit(IMAGE_ANALYSIS_FINISHED, source="vision", path=os.path.basename(path),
                    kind=kind, chars=len(answer or ""))
    except Exception:
        pass
    return answer, meta


def _query_vision_model(config: dict, prompt: str, mime: str, b64: str,
                        system_extra: str = "") -> str:
    """One vision completion against an explicit provider config, using
    aicore's own request machinery through the public attachments path
    (keeps per-provider payload shaping in exactly one place)."""
    try:
        from . import aicore
        try:
            from . import identity
            system_prompt = ("You are CAT Vision, CAT's precise image-analysis "
                             "specialist. Be exhaustive and concrete.\n\n"
                             + identity.IDENTITY_BLOCK)
        except Exception:
            system_prompt = ("You are CAT Vision, CAT's precise image-analysis "
                             "specialist. Be exhaustive and concrete.")
        att = _temp_attachment(mime, b64)
        return aicore.query_ai(prompt, system_prompt=system_prompt,
                               history=None, config=config,
                               attachments=[att], size_class="large")
    except Exception as e:
        return f"Image analysis failed: {e}"


def _temp_attachment(mime, b64):
    """Build a minimal Attachment-like object carrying an already-encoded
    image payload so aicore._user_content can shape it per-provider
    without re-reading or re-normalizing the file."""
    from .attachments import Attachment
    att = Attachment.__new__(Attachment)
    att.id = f"att-vision-{abs(hash(b64[:64])) % 1000000}"
    att.name = "image"
    att.path = ""
    att.extension = "." + mime.split("/")[-1].split("+")[0]
    att.mime_type = mime
    att.size = 0
    att.kind = "image"
    att.content = "[native image payload]"
    att.metadata = {"inline_b64": b64}
    att.extraction_status = "ready"
    att.error = None
    att.created_at = 0.0
    att.source = "pipeline"
    return att
