"""
CAT v0.8.a — AI Analysis Modes (spec 19).

Three internal levels:
  QUICK  — low latency, current frame + current annotation + recent interaction
  DEEP   — selected frame(s) + annotations + cursor + project + chat
  DEBUG  — full pipeline: vision → identify UI region → locate code → propose fix → apply → verify
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AnalysisLevel(str, Enum):
    QUICK = "quick"
    DEEP = "deep"
    DEBUG = "debug"


@dataclass
class AnalysisRequest:
    level: AnalysisLevel
    session_id: str
    prompt: str = ""
    include_code: bool = False
    include_before_after: bool = False
    error_message: str = ""
    user_intent: str = ""


@dataclass
class AnalysisResult:
    level: AnalysisLevel
    analysis: str
    frame_index: Optional[int] = None
    confidence: float = 0.0
    findings: List[str] = field(default_factory=list)
    suggested_fix: Optional[str] = None
    related_files: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    provider: str = ""
    model: str = ""


def build_system_prompt(level: AnalysisLevel) -> str:
    if level == AnalysisLevel.QUICK:
        return (
            "You are CAT Vision — QUICK mode. Low latency.\n"
            "Analyze the current frame + current annotation + recent cursor context.\n"
            "Be concise, point to the immediate issue, suggest one next step."
        )
    if level == AnalysisLevel.DEEP:
        return (
            "You are CAT Vision — DEEP analysis. Thorough reasoning.\n"
            "Analyze selected frame(s), annotations, cursor context, project/code context, and chat history.\n"
            "Explain what you see, root cause, and a specific fix with file/function references when possible."
        )
    # DEBUG
    return (
        "You are CAT Vision — DEBUG mode. Full engineering workflow.\n"
        "Pipeline: Vision → Identify UI region → Determine likely behavior → Inspect project\n"
        "→ Locate related code → Reproduce where possible → Propose fix → Wait for permission → Verify.\n"
        "Correlate the visual region with project code. If exact mapping is unavailable, say so — never hallucinate file locations.\n"
        "Propose a concrete code change and flag the permission gate."
    )


def build_user_prompt(req: AnalysisRequest, ctx: Dict[str, Any]) -> str:
    parts: List[str] = []
    if req.level == AnalysisLevel.QUICK:
        parts.append(req.prompt or "Quick analyze: what is visible and what should the user check?")
        if ctx.get("annotation_summary"):
            parts.append(f"Annotation: {ctx['annotation_summary']}")
        if ctx.get("cursor_summary"):
            parts.append(f"Cursor: {ctx['cursor_summary']}")
    elif req.level == AnalysisLevel.DEEP:
        parts.append(req.prompt or "Deep analyze this screen. What is wrong and how to fix it?")
        if req.error_message:
            parts.append(f"Error reported: {req.error_message}")
        if req.user_intent:
            parts.append(f"User intent: {req.user_intent}")
        if ctx.get("annotation_summary"):
            parts.append(f"Annotations: {ctx['annotation_summary']}")
        if ctx.get("cursor_summary"):
            parts.append(f"Cursor context: {ctx['cursor_summary']}")
        if ctx.get("project_hint"):
            parts.append(f"Project: {ctx['project_hint']}")
    else:  # DEBUG
        parts.append("VISUAL DEBUG SESSION — full pipeline.")
        if req.prompt:
            parts.append(f"User: {req.prompt}")
        if req.error_message:
            parts.append(f"Error: {req.error_message}")
        if req.user_intent:
            parts.append(f"Intent: {req.user_intent}")
        parts.append(
            "Provide:\n"
            "1. What you see (UI elements, text, state)\n"
            "2. Errors/warnings/anomalies\n"
            "3. Root cause hypothesis with code reference if locatable\n"
            "4. Specific fix suggestion with code\n"
            "5. Observation: say when exact source mapping is unavailable\n"
            "6. Do NOT apply fixes yourself — propose and wait for permission"
        )
    return "\n\n".join(parts)


def run_analysis(req: AnalysisRequest, visual_ctx, config: Optional[Dict] = None) -> AnalysisResult:
    """Run one analysis level against a VisualContext (vision/context.py)."""
    t0 = time.time()
    system_prompt = build_system_prompt(req.level)
    # build minimal ctx hints from visual_ctx
    ctx_hints: Dict[str, Any] = {}
    try:
        if visual_ctx.annotations:
            ctx_hints["annotation_summary"] = "; ".join(
                f"{a.get('tool','?')}" for a in visual_ctx.annotations[:5]
            )
        if visual_ctx.pointer_telemetry:
            pt = visual_ctx.pointer_telemetry
            ctx_hints["cursor_summary"] = f"active={pt.get('active_element','')} moving={pt.get('cursor_moving',False)}"
        if visual_ctx.project_context:
            ctx_hints["project_hint"] = visual_ctx.project_context.get("type", "")
    except Exception:
        pass
    user_prompt = build_user_prompt(req, ctx_hints)
    # enrich visual_ctx with our prompts before calling provider
    visual_ctx.analysis_prompt = user_prompt
    # route
    try:
        from .provider import VisionProviderRouter
        from .. import aicore
        from ..attachments import Attachment
        import base64
        router = VisionProviderRouter(config)
        cfg, caps = router.find_vision_capable(config) or (None, None)
        if cfg is None:
            return AnalysisResult(level=req.level, analysis="No vision-capable model configured. Run /model to choose one.", duration_ms=(time.time()-t0)*1000)
        # Build attachment from frame_b64
        att = Attachment.__new__(Attachment)
        att.id = f"att-vision-{req.level.value}-{int(time.time()*1000)%1000000}"
        att.name = "vision_frame"
        att.path = ""
        att.extension = ".png"
        att.mime_type = "image/png"
        att.size = len(visual_ctx.frame_b64 or "")
        att.kind = "image"
        att.content = "[vision frame]"
        att.metadata = {"inline_b64": visual_ctx.frame_b64 or ""}
        att.extraction_status = "ready"
        att.error = None
        att.created_at = time.time()
        att.source = "vision_analysis"
        # Attachments: frame + optional before frame
        attachments = [att]
        if req.include_before_after and visual_ctx.before_frame_b64:
            att2 = Attachment.__new__(Attachment)
            att2.id = "att-vision-before"
            att2.name = "before_frame"
            att2.path = ""
            att2.extension = ".png"
            att2.mime_type = "image/png"
            att2.size = len(visual_ctx.before_frame_b64)
            att2.kind = "image"
            att2.content = "[before frame]"
            att2.metadata = {"inline_b64": visual_ctx.before_frame_b64}
            att2.extraction_status = "ready"
            att2.error = None
            att2.created_at = time.time()
            att2.source = "vision_verify"
            attachments.append(att2)
        analysis_text = aicore.query_ai(
            user_prompt,
            system_prompt=system_prompt,
            history=None,
            config=cfg,
            attachments=attachments,
            size_class="large" if req.level != AnalysisLevel.QUICK else "normal",
        )
        return AnalysisResult(
            level=req.level,
            analysis=analysis_text or "",
            frame_index=None,
            confidence=0.7,
            duration_ms=(time.time()-t0)*1000,
            provider=cfg.get("provider",""),
            model=cfg.get("model",""),
        )
    except Exception as e:
        return AnalysisResult(level=req.level, analysis=f"Analysis failed: {e}", duration_ms=(time.time()-t0)*1000)
