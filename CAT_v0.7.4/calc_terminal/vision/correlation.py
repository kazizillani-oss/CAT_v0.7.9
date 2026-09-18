"""
CAT v0.8.a — Screen → Code Correlation (spec 20).

Maps a visual annotation/cursor region to likely project files by:
  - DOM/preview context (if live preview is running)
  - filename / component heuristics
  - workspace search for component names near the annotation label

Never hallucinates an exact source location from pixels alone.
Returns a ranked list with confidence + evidence.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _norm_annotation_label(ann: Dict[str, Any]) -> str:
    return (ann.get("text") or ann.get("label") or ann.get("description") or "").strip()


def _guess_component_from_label(label: str) -> List[str]:
    """Extract likely component/file hints from a short label like 'Submit button glitches'."""
    if not label:
        return []
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]*", label)
    # keep capitalized or component-like words, also "button", "form", "submit"
    hints = []
    for w in words:
        lw = w.lower()
        if len(w) >= 3 and lw not in {"this", "that", "when", "with", "glitches", "broken", "jumps"}:
            hints.append(w)
    return hints[:8]


def _search_workspace(hints: List[str], root: str, max_hits: int = 12) -> List[Dict[str, Any]]:
    """Cheap filename + grep search. Returns [{path, reason, score}]."""
    if not root or not os.path.isdir(root):
        return []
    root_p = Path(root)
    results: List[Dict[str, Any]] = []
    # filename scan
    all_files = []
    for p in root_p.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".tsx",".ts",".jsx",".js",".py",".html",".css",".vue",".svelte"}:
            if any(part.startswith(".") or part == "node_modules" or part == "__pycache__" for part in p.parts):
                continue
            all_files.append(p)
            if len(all_files) > 8000:
                break
    for hint in hints:
        hl = hint.lower()
        for f in all_files:
            name_l = f.name.lower()
            if hl in name_l or hl.replace("-","") in name_l.replace("-",""):
                results.append({"path": str(f.relative_to(root_p)), "reason": f"filename contains '{hint}'", "score": 0.7})
                if len(results) >= max_hits:
                    return results
    # content grep for component names (cheap, capped)
    for hint in hints[:3]:
        hl = hint.lower()
        if len(hl) < 3:
            continue
        for f in all_files[:1200]:
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")[:20000]
            except Exception:
                continue
            if hl in text.lower():
                # boost if it's a component definition
                score = 0.6
                if re.search(rf"(class|function|const)\s+{re.escape(hint)}\b", text):
                    score = 0.85
                elif re.search(rf"<{re.escape(hint)}\b", text):
                    score = 0.75
                results.append({"path": str(f.relative_to(root_p)), "reason": f"mentions '{hint}'", "score": score})
                if len(results) >= max_hits:
                    return results
    # dedupe, keep highest score per path
    best: Dict[str, Dict] = {}
    for r in results:
        prev = best.get(r["path"])
        if prev is None or r["score"] > prev["score"]:
            best[r["path"]] = r
    ranked = sorted(best.values(), key=lambda r: r["score"], reverse=True)
    return ranked[:max_hits]


def correlate(
    annotations: List[Dict[str, Any]],
    cursor: Optional[Dict[str, Any]] = None,
    preview_context: Optional[Dict[str, Any]] = None,
    workspace_root: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns {
      "has_mapping": bool,
      "candidates": [{path, reason, score}],
      "preview_hint": str | None,
      "notes": str  # honest about uncertainty
    }
    """
    # preview / DOM hint is strongest — when live preview controller knows the entry URL + component
    preview_hint = None
    candidates: List[Dict[str, Any]] = []
    notes_parts: List[str] = []

    if preview_context:
        # preview_context may contain entry file / component map produced by browser/preview.py
        entry = preview_context.get("entry") or preview_context.get("url") or ""
        if entry:
            preview_hint = entry
            candidates.append({"path": entry, "reason": "live preview entry", "score": 0.65})
        dom = preview_context.get("dom_match") or preview_context.get("selector") or ""
        if dom:
            notes_parts.append(f"DOM context: {dom}")

    # annotation labels → hints → workspace search
    all_hints: List[str] = []
    for ann in (annotations or []):
        label = _norm_annotation_label(ann)
        hints = _guess_component_from_label(label)
        tool = ann.get("tool", "")
        if tool:
            hints.append(tool)
        all_hints.extend(hints)

    # also from cursor active_element
    if cursor and cursor.get("active_element"):
        all_hints.append(str(cursor["active_element"])[:40])

    # dedupe hints
    seen = set()
    uniq_hints: List[str] = []
    for h in all_hints:
        hl = h.lower()
        if hl not in seen:
            seen.add(hl)
            uniq_hints.append(h)

    if uniq_hints and workspace_root:
        hits = _search_workspace(uniq_hints, workspace_root, max_hits=10)
        candidates.extend(hits)

    # sort + dedupe candidates
    best: Dict[str, Dict] = {}
    for c in candidates:
        prev = best.get(c["path"])
        if prev is None or c["score"] > prev["score"]:
            best[c["path"]] = c
    ranked = sorted(best.values(), key=lambda c: c["score"], reverse=True)

    has_mapping = bool(ranked and ranked[0]["score"] >= 0.6)
    if not ranked:
        notes_parts.append("No code mapping could be inferred from the current visual context.")
        notes_parts.append("Try adding a short annotation label (e.g. 'Submit button') or opening the preview so CAT can see the component tree.")
    elif not has_mapping:
        notes_parts.append("Weak mapping only — candidates are guesses, not exact source locations.")

    return {
        "has_mapping": has_mapping,
        "candidates": ranked[:8],
        "preview_hint": preview_hint,
        "hints_used": uniq_hints[:10],
        "notes": " ".join(notes_parts),
    }
