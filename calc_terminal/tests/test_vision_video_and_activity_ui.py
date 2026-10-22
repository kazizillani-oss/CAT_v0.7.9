import os
import tempfile
import pytest
from calc_terminal.vision import video_analyzer
from calc_terminal import attachments
from calc_terminal import model_router
from calc_terminal.ui import conversation


def test_video_analyzer_mp4_generation_and_parse():
    """Verify that video_analyzer parses ISO-BMFF mp4 atoms correctly."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        # Construct minimal ftyp atom
        ftyp = b"ftypisom\x00\x00\x02\x00isomiso2mp41"
        f.write(len(ftyp + b"1234").to_bytes(4, "big") + ftyp)
        # Construct mvhd atom inside moov
        mvhd_payload = b"\x00" * 4 + b"\x00" * 4 + b"\x00" * 4 + (1000).to_bytes(4, "big") + (5000).to_bytes(4, "big") + b"\x00" * 80
        mvhd_atom = (len(mvhd_payload) + 8).to_bytes(4, "big") + b"mvhd" + mvhd_payload
        moov_atom = (len(mvhd_atom) + 8).to_bytes(4, "big") + b"moov" + mvhd_atom
        f.write(moov_atom)
        temp_path = f.name

    try:
        info = video_analyzer.inspect_video(temp_path)
        assert "MP4" in info.get("container", "")
        assert info.get("duration", 0) == 5.0
        
        ctx = video_analyzer.build_video_analysis_context(temp_path)
        assert "ATTACHED VIDEO MEDIA SPECIFICATION & ANALYSIS" in ctx
        assert "MP4" in ctx
        assert "00:05" in ctx
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_attachments_video_and_image_context():
    """Verify attachments module extracts rich context for video and image."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2mp41")
        temp_path = f.name

    try:
        content, meta, kind, err = attachments.extract_attachment(temp_path)
        assert kind == "video"
        assert err is None
        assert "ATTACHED VIDEO MEDIA SPECIFICATION & ANALYSIS" in content
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_model_router_vision_hints():
    """Verify vision detection supports comprehensive models without blocking."""
    caps_llama = model_router.capabilities_for("ollama", "llama-3.2-11b-vision")
    assert caps_llama.vision is True

    caps_qwen = model_router.capabilities_for("openai", "qwen2.5-vl-72b-instruct")
    assert caps_qwen.vision is True

    caps_gpt4o = model_router.capabilities_for("openai", "gpt-4o")
    assert caps_gpt4o.vision is True

    caps_gemini = model_router.capabilities_for("gemini", "gemini-2.0-flash")
    assert caps_gemini.vision is True


def test_parse_activity_and_body_splits_and_cleans():
    """Verify activity lines and response text are cleanly separated."""
    raw = (
        "> ⚠ No vision-capable model is configured. Run /model to add one. "
        "🔧 readfile portfolio/src/main.tsx — ✔ completed\n\n"
        "Here is what I found in main.tsx:\n"
        "> Real blockquote from assistant\n"
        "All good."
    )
    acts, body = conversation._parse_activity_and_body(raw)
    assert len(acts) == 2
    assert "No vision-capable model" in acts[0]
    assert "readfile" in acts[1]
    assert "✔ completed" in acts[1]
    assert "Here is what I found in main.tsx:" in body
    assert "> Real blockquote from assistant" in body


def test_format_activity_item():
    """Verify tool lines format with proper typography and status badges."""
    t1 = conversation._format_activity_item(
        "🔧 **readfile**  `portfolio/src/main.tsx` — ✔ completed",
        is_light=False, accent="#f59e0b"
    )
    assert "readfile" in t1
    assert "portfolio/src/main.tsx" in t1
    assert "✔ completed" in t1
    assert "#10b981" in t1

    t2 = conversation._format_activity_item(
        "🔧 writefile  `src/App.tsx`",
        is_light=False, accent="#f59e0b"
    )
    assert "writefile" in t2
    assert "src/App.tsx" in t2
    assert "⏳ in progress..." in t2


def test_activity_widget_is_closed_panel():
    """Verify that _build_activity_widget creates a complete, closed Panel."""
    from rich.panel import Panel
    from rich import box

    panel = conversation._build_activity_widget(
        [
            "🔧 list_directory portfolio/src/components — ✔ completed",
            "🔧 list_directory portfolio/src/components/workspace — ✔ completed",
        ],
        is_light=False,
        accent="#f59e0b",
    )
    assert isinstance(panel, Panel)
    assert panel.box == box.SQUARE
    assert "Activity & Tools" in str(panel.title)

