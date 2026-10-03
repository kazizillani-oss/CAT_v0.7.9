"""
CCT Agent — Chemistry Agentic AI [BETA].

Layers a real tool-using agent loop on top of aicore's provider access
(API or Ollama) so the model doesn't just *talk* about chemistry — it can
actually drive the app: solve exact formulas symbolically, run the safe
calculator, plot any 2D curve or 3D surface (a built-in chemistry preset,
OR a completely custom function/curve the model names itself), and start
live 2D/3D atom, electron/proton, and quantum-orbital simulations.

Protocol: the model is asked to reply with exactly one JSON object per
turn — either {"action": "tool", "tool": ..., "args": {...}} to use a
tool, or {"action": "final", "text": ...} to answer. Results of each
tool call are fed back in as the next turn so the model can chain
several tools (e.g. solve a value, then plot it) before finishing. This
works uniformly across every provider in aicore.PROVIDERS (OpenAI,
Anthropic, Gemini, Groq, OpenRouter, Ollama, or a custom endpoint)
because it only relies on plain text in/out, not provider-specific
function-calling schemas.
"""

import fnmatch
import json
import math
import os
import random
import re
import subprocess
import sys
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, Set

from . import theme
from . import aicore
from . import solver
from . import atomsim
from . import identity
from . import sim3d
from . import graphs
from . import sound
from . import memory
from . import security_scanner
from . import sandbox
from . import permissions as perm
from . import workspace
from .tool_call_normalizer import normalize_tool_calls, extract_final_answer, is_tool_call_response

# ------------------------------------------------------------- attachments --
# Feature 6: files/images imported via /import (or the code pad's :import)
# are tracked here so the agent can be told about them and fetch their
# content/analysis on demand via the read_attachment tool, without having
# to paste the whole file into every prompt up front.
#
# v0.7.8.1: entries are normalized Attachment objects
# (calc_terminal/attachments.py) — never bare path strings — so the
# read_attachment tool serves real extracted content, and the composer's
# attached files (set_attachments) are visible to the same tool.
_ATTACHMENTS = []


def add_attachment(path):
    """Register one attachment (path, or an Attachment object).
    Kept for the legacy /import and code-pad :import paths; the primary
    UI uses set_attachments() instead."""
    from . import attachments as _att
    if isinstance(path, _att.Attachment):
        _ATTACHMENTS.append(path)
        return
    _ATTACHMENTS.append(_att.AttachmentManager.create(path))


def set_attachments(attachments):
    """v0.7.8.1: replace the session attachment list wholesale — the UI
    worker calls this before an agent/build turn so the model can read
    the files attached via the composer through read_attachment."""
    _ATTACHMENTS.clear()
    for a in (attachments or []):
        if a is not None:
            _ATTACHMENTS.append(a)


def get_attachments():
    return list(_ATTACHMENTS)


def clear_attachments():
    _ATTACHMENTS.clear()


def _attachments_context():
    if not _ATTACHMENTS:
        return ""
    lines = ["Files/images attached this session (real, addressable context — "
             "use read_attachment to see content, archive_list for archives, "
             "or operate on their real paths directly with file tools):"]
    for a in _ATTACHMENTS:
        if isinstance(a, dict):  # legacy shape
            path, kind = a.get("path"), a.get("kind", "file")
            lines.append(f"- {path} ({kind})")
            continue
        status = getattr(a, "extraction_status", "ready")
        suffix = "" if status == "ready" else f", status: {status}"
        size = getattr(a, "size", 0) or 0
        lines.append(f"- id: {a.id} | name: {a.name} | type: {a.kind} | "
                     f"size: {size}B | path: {a.path}{suffix}")
    return "\n".join(lines)


MAX_STEPS = 18
_CALC_NS = {
    "sqrt": math.sqrt, "log10": math.log10, "log": math.log, "sin": math.sin,
    "cos": math.cos, "tan": math.tan, "pi": math.pi, "e": math.e,
    "abs": abs, "round": round, "exp": math.exp,
}
_CALC_ALLOWED = re.compile(r"^[0-9+\-*/().\s,a-zA-Z_]*$")


# ------------------------------------------------------------------ tools --
def _floats(d):
    out = {}
    for k, v in (d or {}).items():
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            pass
    return out


def _tool_list_formulas(args):
    lines = [f"{k} = {v[2]}  [{v[1]}] \u2014 {v[0]}" for k, v in solver.FORMULA_LIBRARY.items()]
    return "Formula library keys (use with solve_formula):\n" + "\n".join(lines)


def _tool_solve_formula(args):
    key = str(args.get("key", "")).strip()
    known = _floats(args.get("values"))
    if key not in solver.FORMULA_LIBRARY:
        matches = [k for k in solver.FORMULA_LIBRARY if key and key.lower() in k.lower()]
        if not matches:
            return (f"Unknown formula key '{key}'. Call list_formulas first to see valid "
                     f"keys such as kin_first, ideal_gas, nernst, arrhenius, half_life_1.")
        key = matches[0]
    try:
        solve_for, result, name, cat, eq = solver.solve_library_formula(key, known)
    except solver.SolveError as e:
        sound.play("error")
        return f"Could not solve '{key}': {e}"
    sound.play("success")
    return f"Solved '{name}' [{cat}]: {eq}  ->  {solve_for} = {result:.6g}"


def _tool_solve_custom(args):
    formula = str(args.get("formula", "")).strip()
    known = _floats(args.get("values"))
    solve_for = str(args.get("solve_for", "")).strip()
    if not formula or "=" not in formula or not solve_for:
        return "Need a formula containing '=', known values, and a solve_for variable name."
    try:
        result, eq = solver.solve_formula(formula, known, solve_for)
    except solver.SolveError as e:
        sound.play("error")
        return f"Could not solve: {e}"
    sound.play("success")
    return f"Solved {eq}  ->  {solve_for} = {result:.6g}"


def _tool_calculate(args):
    expr = str(args.get("expression", "")).strip().replace("^", "**")
    if not expr or not _CALC_ALLOWED.match(expr):
        return "Invalid or unsafe expression."
    try:
        result = eval(expr, {"__builtins__": {}}, _CALC_NS)
    except Exception as e:
        sound.play("error")
        return f"Calculation error: {e}"
    sound.play("success")
    return f"{args.get('expression')} = {result}"


def _tool_generate_numerical(args):
    from .generators import GENERATORS
    from .engine import render_notebook
    topic = str(args.get("topic", "first")).lower()
    keys = list(GENERATORS.keys())
    matches = [k for k in keys if topic in k or k in topic]
    key = matches[0] if matches else random.choice(keys)
    nb = GENERATORS[key]()
    print()
    render_notebook(nb)
    sound.play("success")
    return f"Generated and rendered a full {nb['topic']} notebook above. Final answer: {nb['final_answer']}"


def _tool_plot_preset(args):
    name = str(args.get("preset", "")).strip()
    valid = [k for k, _ in graphs.PRESETS]
    if name not in valid:
        matches = [k for k in valid if name and name in k]
        if not matches:
            return f"Unknown preset '{name}'. Valid presets: {', '.join(valid)}"
        name = matches[0]
    xs, ys, title, xl, yl = graphs.preset_curve(name)
    print()
    graphs.ascii_plot(xs, ys, title, xl, yl)
    sound.play("success")
    result = f"Plotted built-in preset '{name}' ({title}) as an animated terminal graph."
    if args.get("export"):
        try:
            path = graphs.export_2d(xs, ys, title, xl, yl)
            result += f" Exported PNG: {path}"
        except Exception as e:
            result += f" (PNG export failed: {e})"
    return result


def _tool_plot_function(args):
    """Plot / graph ANY named 2D function — this is the 'name anything to
    the model' hook: the AI can invent a title and formula on the spot."""
    expr = str(args.get("expression", "x")).strip()
    xmin = args.get("xmin", 0)
    xmax = args.get("xmax", 10)
    title = args.get("title") or f"y = {expr}"
    try:
        xs, ys, t, xl, yl = graphs.custom_curve(
            expr, xmin, xmax, 60, title,
            str(args.get("xlabel", "x")), str(args.get("ylabel", "y")))
    except graphs.ExpressionError as e:
        sound.play("error")
        return f"Could not plot '{expr}': {e}"
    print()
    graphs.ascii_plot(xs, ys, t, xl, yl)
    sound.play("success")
    result = f"Plotted custom function '{expr}' over x in [{xmin}, {xmax}] as \"{title}\"."
    if args.get("export"):
        try:
            path = graphs.export_custom_2d(expr, xmin, xmax, 300, title,
                                            str(args.get("xlabel", "x")), str(args.get("ylabel", "y")))
            result += f" Exported PNG: {path}"
        except Exception as e:
            result += f" (PNG export failed: {e})"
    return result


def _tool_plot_surface(args):
    """Export a 3D surface PNG — a built-in preset ('orbital_3d' or 'pvt')
    or any AI-named surface z = f(x, y)."""
    kind = str(args.get("kind", "")).strip().lower()
    try:
        if kind in ("orbital_3d", "pvt"):
            path = graphs.export_3d_surface(kind)
            sound.play("success")
            return f"Exported the built-in 3D surface '{kind}': {path}"
        expr = str(args.get("expression", "x**2 - y**2")).strip()
        title = args.get("title") or f"z = {expr}"
        path = graphs.export_custom_3d(
            expr,
            args.get("xmin", -5), args.get("xmax", 5),
            args.get("ymin", -5), args.get("ymax", 5),
            45, title)
        sound.play("success")
        return f"Exported custom 3D surface \"{title}\" (z = {expr}): {path}"
    except graphs.ExpressionError as e:
        sound.play("error")
        return f"Could not export surface: {e}"
    except Exception as e:
        sound.play("error")
        return f"3D export failed (is matplotlib/numpy installed?): {e}"


def _tool_atom_2d(args):
    z = atomsim.resolve_element(str(args.get("element", "C")))
    if z is None:
        sound.play("error")
        return f"Unknown element '{args.get('element')}'. Use a symbol (C, Fe, Na...) or Z=1-36."
    frames = int(args.get("frames", 220))
    print()
    sound.play("sim_start")
    atomsim.atom_simulation(z, max_frames=max(20, min(frames, 2000)))
    sym, name, shells, mass = atomsim.ELEMENTS[z]
    return f"Ran the live 2D Bohr atom/electron/proton simulation for {name} ({sym}, Z={z})."


def _tool_atom_3d(args):
    z = atomsim.resolve_element(str(args.get("element", "C")))
    if z is None:
        sound.play("error")
        return f"Unknown element '{args.get('element')}'. Use a symbol (C, Fe, Na...) or Z=1-36."
    frames = int(args.get("frames", 220))
    print()
    sound.play("sim_start")
    sim3d.atom_simulation_3d(z, max_frames=max(20, min(frames, 2000)))
    sym, name, shells, mass = atomsim.ELEMENTS[z]
    return f"Ran the live real-time 3D atom/electron/proton simulation for {name} ({sym}, Z={z})."


def _tool_orbital(args):
    key = str(args.get("orbital", "1s")).lower().strip()
    if key not in atomsim.ORBITALS:
        sound.play("error")
        return f"Unknown orbital '{key}'. Valid: {', '.join(atomsim.ORBITALS)}"
    points = int(args.get("points", 1200))
    print()
    sound.play("sim_start")
    atomsim.orbital_simulation(key, max_points=max(200, min(points, 5000)))
    return f"Rendered the live |\u03c8|\u00b2 Monte-Carlo probability cloud for the {key} orbital."


def _tool_orbital_grid(args):
    try:
        path = atomsim.snapshot_orbital_grid()
    except Exception as e:
        sound.play("error")
        return f"Orbital grid export failed (is matplotlib/numpy/scipy installed?): {e}"
    if not path:
        sound.play("error")
        return "matplotlib/numpy/scipy not installed \u2014 orbital grid export skipped."
    sound.play("success")
    return f"Exported the hydrogen orbital reference chart (multiple n,l,m panels): {path}"


def _tool_bloch(args):
    from . import scires
    import math as _math
    try:
        theta_deg = float(args.get("theta_deg", 90.0))
        phi_deg = float(args.get("phi_deg", 0.0))
    except (TypeError, ValueError):
        sound.play("error")
        return "theta_deg/phi_deg must be numbers (degrees)."
    try:
        path = scires.render_bloch_sphere(theta_deg, phi_deg)
    except Exception as e:
        sound.play("error")
        return f"Bloch sphere export failed (is matplotlib/numpy/scipy installed?): {e}"
    if not path:
        sound.play("error")
        return "matplotlib/numpy/scipy not installed \u2014 Bloch sphere export skipped."
    sound.play("success")
    probs = scires.bloch_state_probs(_math.radians(theta_deg), _math.radians(phi_deg))
    p_summary = ", ".join(f"{b}: {p[0]*100:.1f}%/{p[1]*100:.1f}%" for b, p in probs.items())
    return (f"Exported a Bloch sphere for theta={theta_deg}\u00b0, phi={phi_deg}\u00b0 to {path}. "
            f"Exact measurement probabilities ({p_summary}).")


def _tool_bonding(args):
    from . import scires
    key = str(args.get("molecule", "furan")).strip().lower()
    if key not in scires.MOLECULES:
        sound.play("error")
        return (f"Unknown molecule '{key}'. Available: "
                 f"{', '.join(sorted(scires.MOLECULES.keys()))}")
    try:
        path = scires.render_bonding(key)
    except Exception as e:
        sound.play("error")
        return f"Bonding map export failed (is matplotlib/numpy/scipy installed?): {e}"
    if not path:
        sound.play("error")
        return "matplotlib/numpy/scipy not installed \u2014 bonding map export skipped."
    sound.play("success")
    return f"Exported a stylized electron-localization / bonding density map for {key}: {path}"


def _tool_web_search(args):
    query = str(args.get("query", "")).strip()
    if not query:
        return "No query given."
    results = aicore.web_search(query, max_results=int(args.get("max_results", 5) or 5))
    if not results:
        return f"No web results found for '{query}' (search unreachable or blocked)."
    lines = [f"[{i+1}] {r['title']} — {r['url']}\n    {r['snippet']}" for i, r in enumerate(results)]
    return "Web search results:\n" + "\n".join(lines)


def _tool_deep_research(args):
    topic = str(args.get("topic", "")).strip()
    if not topic:
        return "No research topic given."
    summary, sources = aicore.deep_research(topic, num_queries=int(args.get("num_queries", 3) or 3))
    src_lines = "\n".join(f"[{i+1}] {s['title']} — {s['url']}" for i, s in enumerate(sources))
    return f"Research summary for '{topic}':\n{summary}\n\nSources:\n{src_lines}"


def _tool_fetch_web_page(args):
    url = str(args.get("url", "")).strip()
    if not url:
        return "No URL provided."
    max_chars = int(args.get("max_chars", 8000) or 8000)
    return aicore.fetch_web_page(url, max_chars=max_chars)


def _tool_read_attachment(args):
    if not _ATTACHMENTS:
        return "No files/images have been imported this session."
    # Accept path fragments, attachment ids, or bare filenames so the
    # model can address an attached file however it was described in
    # context (requirement #22: attachments are real, addressable
    # context: attached_file_id / filename / type / size / path).
    ident = str(args.get("path", args.get("file_id", args.get("filename", "")))).strip()
    match = None
    if ident:
        ident_low = ident.lower()
        for a in _ATTACHMENTS:
            path = a["path"] if isinstance(a, dict) else a.path
            aid = "" if isinstance(a, dict) else getattr(a, "id", "")
            aname = os.path.basename(path).lower()
            if (ident in path) or (aid and ident_low == aid.lower()) \
                    or aname == ident_low or aname.endswith(ident_low):
                match = a
                break
        if match is None:
            names = ", ".join(
                os.path.basename((x["path"] if isinstance(x, dict) else x.path))
                for x in _ATTACHMENTS)
            return (f"No attachment matches '{ident}'. Attached this session: {names}.")
    match = match or _ATTACHMENTS[-1]
    if isinstance(match, dict):  # legacy shape
        path, kind = match["path"], match["kind"]
    else:
        path, kind = match.path, match.kind
    if kind == "image" or aicore.is_image_file(path):
        result = aicore.query_ai_with_image(
            "Describe this image precisely; transcribe any code, chemistry, "
            "or math it contains.", path)
        return f"Image '{path}' analysis:\n{result}"
    if kind == "video" or any(path.lower().endswith(ext) for ext in (".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv", ".wmv", ".ts")):
        from .vision import video_analyzer
        v_ctx = video_analyzer.build_video_analysis_context(path)
        return f"Video '{path}' structural and visual analysis:\n{v_ctx}"
    # v0.7.6 Patch 1, Fix 7: non-image attachments go through the same
    # per-type context builder the streamed UI uses (real text for
    # text/code/md/CSV, real listings for zip/tar, PDF metadata + text
    # layer, honest notes for audio/video/binary) instead of a raw
    # text read that fails on every non-text file.
    # v0.7.8.1: Attachment objects serve their already-extracted content
    # (re-extracted on demand if still pending).
    from . import attachments as _att
    if not isinstance(match, dict):
        ctx = _att.AttachmentManager.build_context([match])
        return f"Contents of '{path}':\n" + ctx
    return (f"Contents of '{path}':\n"
            + aicore.attachment_context_for(path))


# ------------------------------------------------------- filesystem --
# Real file-system tools for the agent (spec v0.7.1 sections 1/10/20).
# Every mutating one below goes through workspace.resolve_writable_path
# first (raises ValueError instead of silently touching something
# unintended) and is gated by run_agent's permission dispatch — see
# MUTATING_TOOLS / TOOL_PERM_KEY / TOOL_DESCRIBE below. None of these
# functions check permissions themselves; that's the caller's job, so
# there's exactly one place (run_agent) that can possibly forget to.

_last_change: dict = {}
"""One-slot side channel for structured file-change info. The mutating
file tools put their before/after snapshot here on success; run_agent
reads (and clears) it right after spec['run'], so each executed step can
carry a 4th 'change' element without changing what tools return."""


def _mark_change(**fields):
    _last_change.clear()
    _last_change.update(fields)
    # v0.7.9.0: any known mutation instantly invalidates cached directory
    # listings (requirement: never serve stale filesystem information).
    try:
        from . import fs_cache
        for key in ("path", "new_path"):
            p = fields.get(key)
            if p:
                fs_cache.invalidate_path(p)
                fs_cache.invalidate_path(os.path.dirname(str(p)))
    except Exception:
        pass


def _tool_write_file(args):
    raw_path = str(args.get("path", "")).strip()
    content = args.get("content", "")
    overwrite = bool(args.get("overwrite", False))
    if not raw_path:
        return "No path given."
    try:
        path = workspace.resolve_writable_path(raw_path)
    except ValueError as e:
        return f"Refused: {e}"
    if os.path.exists(path) and not overwrite:
        return (f"'{path}' already exists. Call write_file again with "
                f"\"overwrite\": true if you really mean to replace it.")
    old_text = None
    if os.path.exists(path):
        # Snapshot the pre-write content so the chat can show exactly
        # what changed instead of just "Done." (spec v0.7.4: structured
        # OLD/NEW summaries for every AI code edit).
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                old_text = f.read()
        except OSError:
            old_text = None
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(content))
    except OSError as e:
        _mark_change()
        return f"Could not write '{path}': {e}"
    _mark_change(kind="create" if old_text is None else "modify",
                 path=path, old=old_text, new=str(content))
    sound.play("success")
    return f"Wrote {len(str(content))} characters to '{path}'."


def _tool_create_folder(args):
    raw_path = str(args.get("path", "")).strip()
    if not raw_path:
        return "No path given."
    try:
        path = workspace.resolve_writable_path(raw_path)
    except ValueError as e:
        return f"Refused: {e}"
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        return f"Could not create '{path}': {e}"
    try:
        from . import fs_cache
        fs_cache.invalidate_path(os.path.dirname(str(path)))
        fs_cache.invalidate_path(str(path))
    except Exception:
        pass
    return f"Created folder '{path}'."


def _tool_delete_file(args):
    raw_path = str(args.get("path", "")).strip()
    if not raw_path:
        return "No path given."
    try:
        path = workspace.resolve_writable_path(raw_path)
    except ValueError as e:
        return f"Refused: {e}"
    if not os.path.exists(path):
        return f"'{path}' does not exist — nothing to delete."
    if os.path.isdir(path):
        return (f"'{path}' is a folder — delete_file only removes single files "
                f"(to avoid a one-typo wiping a whole directory tree).")
    try:
        os.remove(path)
    except OSError as e:
        return f"Could not delete '{path}': {e}"
    _mark_change(kind="delete", path=path)
    return f"Deleted '{path}'."


def _tool_rename_file(args):
    raw_src = str(args.get("path", "")).strip()
    raw_dst = str(args.get("new_path", "")).strip()
    if not raw_src or not raw_dst:
        return "Need both 'path' (source) and 'new_path' (destination)."
    try:
        src = workspace.resolve_writable_path(raw_src)
        dst = workspace.resolve_writable_path(raw_dst)
    except ValueError as e:
        return f"Refused: {e}"
    if not os.path.exists(src):
        return f"'{src}' does not exist."
    if os.path.exists(dst):
        return f"'{dst}' already exists — refusing to overwrite it via rename."
    try:
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        os.rename(src, dst)
    except OSError as e:
        return f"Could not rename '{src}' to '{dst}': {e}"
    _mark_change(kind="rename", path=src, new_path=dst)
    return f"Renamed '{src}' to '{dst}'."


def _tool_edit_file(args):
    """Edit a file by replacing old_text with new_text. Supports find/replace
    or full content replacement. Requires path, old_text and new_text."""
    raw_path = str(args.get("path", "")).strip()
    old_text = str(args.get("old_text", "") or args.get("old", "") or "")
    new_text = str(args.get("new_text") or args.get("new") or args.get("content") or args.get("code") or "")
    reason = str(args.get("reason", "")).strip()
    if not raw_path:
        return "No path given."
    try:
        path = workspace.resolve_writable_path(raw_path)
    except ValueError as e:
        return f"Refused: {e}"
    if not os.path.exists(path):
        return f"'{path}' does not exist - use write_file to create it."
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError as e:
        return f"Could not read '{path}': {e}"
    old_snapshot = content

    norm_content = content.replace("\r\n", "\n")
    norm_old = old_text.replace("\r\n", "\n")
    norm_new = new_text.replace("\r\n", "\n")

    # If old_text is empty, '*', 'all', or matches normalized content, replace entire file
    if not old_text.strip() or old_text.strip() in ("*", "all", "whole", "full") or norm_old.strip() == norm_content.strip():
        content = norm_new
    elif norm_old in norm_content:
        content = norm_content.replace(norm_old, norm_new, 1)
    else:
        # Try line-by-line whitespace-tolerant match
        old_lines = [l.strip() for l in norm_old.split("\n") if l.strip()]
        if old_lines and old_lines[0] in norm_content and old_lines[-1] in norm_content:
            start_idx = norm_content.find(old_lines[0])
            end_idx = norm_content.find(old_lines[-1], start_idx) + len(old_lines[-1])
            content = norm_content[:start_idx] + norm_new + norm_content[end_idx:]
        else:
            return (f"The specified old_text was not found in '{path}'. "
                    f"Check the exact text. Tip: pass old_text: 'all' to overwrite the whole file.")

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as e:
        return f"Could not write '{path}': {e}"
    _mark_change(kind="modify", path=path, old=old_snapshot, new=content)
    sound.play("success")
    return f"Edited '{path}' ({len(norm_new)} chars inserted)."


def _tool_search_workspace(args):
    """Search for files or content in the workspace."""
    query = str(args.get("query", "") or args.get("pattern", "")).strip()
    path = str(args.get("path", "")).strip() or "."
    file_pattern = str(args.get("file_pattern", "")).strip()
    max_results = int(args.get("max_results", 20))
    if not query:
        return "No search query given."
    try:
        base = workspace.resolve_writable_path(path) if path != "." else os.getcwd()
    except ValueError:
        base = os.getcwd()
    results = []
    try:
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in (
                "node_modules", "__pycache__", ".git", ".venv", "venv")]
            for fname in files:
                if file_pattern and not fnmatch.fnmatch(fname, file_pattern):
                    continue
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, base)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if query.lower() in line.lower():
                                results.append(f"{rel}:{i}: {line.rstrip()[:120]}")
                                if len(results) >= max_results:
                                    break
                except (OSError, UnicodeDecodeError):
                    pass
                if len(results) >= max_results:
                    break
            if len(results) >= max_results:
                break
    except Exception as e:
        return f"Search error: {e}"
    if not results:
        return f"No matches for '{query}' in workspace."
    return f"Search results for '{query}' ({len(results)} matches):\n" + "\n".join(results)


def _resolve_tool_path(raw_path, for_write=False):
    """Resolve a model-supplied path for a tool, with the attachment
    exception: a path that IS an actively attached file is always in
    scope (the user explicitly handed CCT that file), even when it sits
    outside the workspace/home roots — e.g. an attached zip on another
    drive can still be inspected and modified."""
    raw = str(raw_path or "").strip()
    if not raw:
        raise ValueError("No path given.")
    expanded = os.path.expanduser(raw)
    norm = os.path.normpath(os.path.abspath(expanded))
    for a in _ATTACHMENTS:
        apath = getattr(a, "path", None) or (a.get("path") if isinstance(a, dict) else None)
        if apath and os.path.normpath(os.path.abspath(apath)) == norm:
            return norm
    return workspace.resolve_tool_path(expanded, for_write=for_write)


def _zip_entry_is_dir(info):
    return info.is_dir() or info.filename.endswith("/")


def _tool_archive_list(args):
    """List the real contents of an archive (requirement #9). Read-only,
    so any non-blocked location resolves."""
    raw_path = str(args.get("path", "")).strip()
    if not raw_path:
        return "No archive path given."
    try:
        path = _resolve_tool_path(raw_path)
    except ValueError as e:
        return f"Refused: {e}"
    if not os.path.exists(path):
        # Help the model recover: point at what IS attached.
        att = ", ".join(getattr(a, "name", "") for a in _ATTACHMENTS) or "none"
        return (f"Archive '{raw_path}' not found. Attached files this session: {att}. "
                f"Use read_attachment to see them, then retry with an exact path.")
    ext = os.path.splitext(path)[1].lower()
    dirs = files = 0
    if ext == ".zip":
        import zipfile
        try:
            with zipfile.ZipFile(path, "r") as zf:
                infos = zf.infolist()
                entries = [i.filename for i in infos]
                sizes = {i.filename: i.file_size for i in infos}
                dirs = sum(1 for i in infos if _zip_entry_is_dir(i))
                files = len(infos) - dirs
        except Exception as e:
            return f"Could not read '{path}': {e}"
    elif ext in (".tar", ".gz", ".tgz", ".bz2"):
        import tarfile
        try:
            with tarfile.open(path, "r:*") as tf:
                members = tf.getmembers()
                entries = [m.name for m in members]
                sizes = {m.name: m.size for m in members}
                dirs = sum(1 for m in members if m.isdir())
                files = len(members) - dirs
        except Exception as e:
            return f"Could not read '{path}': {e}"
    else:
        return f"Unsupported archive format: {ext}"
    lines = [f"Archive: {path}",
             f"Entries: {len(entries)} ({dirs} folders, {files} files)"]
    for name in sorted(entries):
        sz = sizes.get(name, 0)
        kind = "/" if name.endswith("/") else ""
        lines.append(f"  {name}{kind} ({sz} bytes)")
    if dirs:
        lines.append(f"\nThis archive contains {dirs} folder entr{'y' if dirs == 1 else 'ies'}; "
                     f"use archive_delete_entries to remove them.")
    return "\n".join(lines)


def _coerce_str_list(value):
    """Model-supplied list arguments arrive as a real JSON list, a
    JSON-encoded string ('[\\"a\\", \\"b\\"]'), or a comma/newline
    separated string depending on how the call was formatted. Coerce all
    of them into a clean python list of stripped strings."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    s = str(value).strip()
    if not s:
        return []
    if s.startswith("["):
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [str(v).strip() for v in parsed if str(v).strip()]
        except Exception:
            pass
    parts = re.split(r"[,;\n]", s)
    out = []
    for part in parts:
        p = part.strip().strip('"').strip("'").strip("[]").strip()
        if p:
            out.append(p)
    return out


def _rewrite_zip_safely(path, keep_predicate):
    """Requirement #10 safety chain: original archive → temporary working
    copy → modify → validate → replace original ONLY after success.
    Returns (True, kept_count) or (False, error_message). The original
    file is never touched unless the new copy validates cleanly; a
    post-replace validation failure rolls back from a backup."""
    import shutil
    import tempfile
    import zipfile
    backup_path = path + ".cct-bak"
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip",
                                        dir=os.path.dirname(path) or None)
    os.close(tmp_fd)
    try:
        kept = 0
        with zipfile.ZipFile(path, "r") as zf_in:
            names = zf_in.namelist()
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf_out:
                for item in zf_in.infolist():
                    if keep_predicate(item):
                        data = zf_in.read(item.filename)
                        zf_out.writestr(item, data)
                        kept += 1
        # validate the working copy BEFORE touching the original
        with zipfile.ZipFile(tmp_path, "r") as zf_chk:
            bad = zf_chk.testzip()
            if bad is not None:
                os.unlink(tmp_path)
                return False, f"modified copy failed validation (bad entry: {bad}) — original untouched"
        shutil.copy2(path, backup_path)
        shutil.move(tmp_path, path)
        # post-replace validation; roll back on any failure
        try:
            with zipfile.ZipFile(path, "r") as zf_chk2:
                if zf_chk2.testzip() is not None:
                    raise OSError("post-replace validation failed")
        except Exception:
            shutil.move(backup_path, path)
            return False, "replaced archive failed validation — original restored"
        try:
            os.unlink(backup_path)
        except OSError:
            pass
        return True, kept
    except Exception as e:
        for p in (tmp_path,):
            try:
                os.unlink(p)
            except OSError:
                pass
        return False, str(e)


def _tool_archive_delete_entries(args):
    """Delete entries (files and/or whole folders) from a ZIP by exact
    name or glob pattern. Folders are matched prefix-wise, so deleting
    'folders/' removes everything under it. Safe-replace + validated."""
    raw_path = str(args.get("path", "")).strip()
    entries_to_delete = args.get("entries") or args.get("folders") or []
    pattern = str(args.get("pattern", "")).strip()
    if not raw_path:
        return "No archive path given."
    entries_to_delete = _coerce_str_list(entries_to_delete)
    try:
        path = _resolve_tool_path(raw_path, for_write=True)
    except ValueError as e:
        return f"Refused: {e}"
    if not os.path.exists(path):
        return f"Archive '{path}' not found."
    ext = os.path.splitext(path)[1].lower()
    if ext != ".zip":
        return f"Archive deletion currently supports .zip files (got {ext})."
    import zipfile
    try:
        with zipfile.ZipFile(path, "r") as zf:
            infos = zf.infolist()
            all_entries = [i.filename for i in infos]
    except Exception as e:
        return f"Could not read '{path}': {e}"

    to_delete = set()

    def _add_match(name):
        n = str(name).strip().replace("\\", "/").strip('"\'').rstrip("/")
        if not n:
            return
        for entry in all_entries:
            e_norm = entry.rstrip("/")
            if e_norm == n or entry.startswith(n + "/"):
                to_delete.add(entry)

    for name in entries_to_delete:
        _add_match(str(name))
    if pattern:
        for entry in all_entries:
            if (fnmatch.fnmatch(entry, pattern)
                    or fnmatch.fnmatch(entry.rstrip("/"), pattern)
                    or fnmatch.fnmatch(os.path.basename(entry), pattern)):
                to_delete.add(entry)

    # never delete EVERYTHING — an empty result would silently destroy data
    if not to_delete:
        listing = "\n".join("  " + e for e in all_entries[:25])
        more = f"\n  ...and {len(all_entries) - 25} more" if len(all_entries) > 25 else ""
        return ("No matching entries found to delete. Archive contains:\n"
                + listing + more
                + "\nPass exact entry/folder names from this list (or a glob pattern).")
    if len(to_delete) >= len([e for e in all_entries if not e.endswith('/')]) \
            and not [e for e in all_entries if e not in to_delete]:
        return ("Refusing to remove every entry from the archive — that would "
                "destroy it. Leave at least one file.")

    ok, result = _rewrite_zip_safely(
        path, lambda item: item.filename not in to_delete)
    if not ok:
        return f"Archive modification FAILED — nothing was lost: {result}"
    deleted_dirs = len({e for e in to_delete if e.endswith("/")})
    deleted_files = len(to_delete) - deleted_dirs
    sample = ", ".join(sorted(to_delete)[:8])
    more = f" (+{len(to_delete) - 8} more)" if len(to_delete) > 8 else ""
    _mark_change(kind="modify", path=path,
                 old=f"<archive:{len(all_entries)} entries>",
                 new=f"<archive:{result} entries>")
    return (f"Deleted {len(to_delete)} entries ({deleted_dirs} folders, "
            f"{deleted_files} files) from '{path}': {sample}{more}. "
            f"{result} entries remain and the archive validated OK.")


def _tool_archive_extract(args):
    """Extract an archive into a destination folder (default: a sibling
    folder named after the archive)."""
    raw_path = str(args.get("path", "")).strip()
    dest_raw = str(args.get("dest", args.get("destination", ""))).strip()
    if not raw_path:
        return "No archive path given."
    try:
        path = _resolve_tool_path(raw_path)
    except ValueError as e:
        return f"Refused: {e}"
    if not os.path.exists(path):
        return f"Archive '{path}' not found."
    try:
        if dest_raw:
            dest = workspace.resolve_writable_path(dest_raw)
        else:
            dest = workspace.resolve_writable_path(
                os.path.join(workspace.root_dir(),
                             os.path.splitext(os.path.basename(path))[0] or "extracted"))
    except ValueError as e:
        return f"Refused: {e}"
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".zip":
            import zipfile
            with zipfile.ZipFile(path, "r") as zf:
                if zf.testzip() is not None:
                    return f"Archive '{path}' is corrupt — refusing to extract."
                zf.extractall(dest)
                count = len(zf.namelist())
        elif ext in (".tar", ".gz", ".tgz", ".bz2"):
            import tarfile
            with tarfile.open(path, "r:*") as tf:
                tf.extractall(dest)
                count = len(tf.getmembers())
        else:
            return f"Unsupported archive format: {ext}"
    except Exception as e:
        return f"Extraction failed: {e}"
    return f"Extracted {count} entries from '{path}' into '{dest}'."


def _tool_archive_add_entries(args):
    """Add files (from disk or text content) into an existing ZIP.
    args: path, files=[paths], or name+content pairs via entries=[{name,content}]."""
    raw_path = str(args.get("path", "")).strip()
    if not raw_path:
        return "No archive path given."
    try:
        path = _resolve_tool_path(raw_path, for_write=True)
    except ValueError as e:
        return f"Refused: {e}"
    if not os.path.exists(path):
        return f"Archive '{path}' not found."
    ext = os.path.splitext(path)[1].lower()
    if ext != ".zip":
        return f"Adding entries currently supports .zip files (got {ext})."
    import shutil
    import tempfile
    import zipfile

    file_paths = _coerce_str_list(args.get("files") or [])
    content_entries = args.get("entries") or []
    if not file_paths and not content_entries:
        return "Nothing to add: pass files=[...] (disk paths) and/or entries=[{name, content}]."

    resolved_files = []
    for fp in file_paths:
        try:
            rp = _resolve_tool_path(str(fp))
        except ValueError as e:
            return f"Refused adding '{fp}': {e}"
        if not os.path.isfile(rp):
            return f"'{rp}' is not a file — only files can be added."
        resolved_files.append(rp)

    backup_path = path + ".cct-bak"
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip",
                                        dir=os.path.dirname(path) or None)
    os.close(tmp_fd)
    try:
        added = []
        with zipfile.ZipFile(path, "r") as zin:
            existing = set(zin.namelist())
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    zout.writestr(item, zin.read(item.filename))
                for rp in resolved_files:
                    arcname = os.path.basename(rp)
                    zout.write(rp, arcname=arcname)
                    added.append(arcname + (" (overwrote)" if arcname in existing else ""))
                for ent in content_entries:
                    if not isinstance(ent, dict):
                        continue
                    nm = str(ent.get("name", "")).strip().replace("\\", "/")
                    ct = str(ent.get("content", ""))
                    if not nm:
                        continue
                    zout.writestr(nm, ct)
                    added.append(nm + (" (overwrote)" if nm in existing else ""))
        with zipfile.ZipFile(tmp_path, "r") as chk:
            if chk.testzip() is not None:
                os.unlink(tmp_path)
                return "Modified copy failed validation — original untouched."
        shutil.copy2(path, backup_path)
        shutil.move(tmp_path, path)
        try:
            os.unlink(backup_path)
        except OSError:
            pass
        _mark_change(kind="modify", path=path, old="<archive>", new="<archive+additions>")
        return f"Added {len(added)} entr{'y' if len(added) == 1 else 'ies'} to '{path}': " + ", ".join(added)
    except Exception as e:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return f"Archive modification FAILED — nothing was lost: {e}"


def _tool_archive_repack(args):
    """Rebuild an archive fresh (recompress / dedupe / drop dangling
    directory entries). args: path, optional out (new path),
    optional drop_dirs (bool, default False)."""
    raw_path = str(args.get("path", "")).strip()
    out_raw = str(args.get("out", "")).strip()
    drop_dirs = bool(args.get("drop_dirs", False))
    if not raw_path:
        return "No archive path given."
    try:
        path = _resolve_tool_path(raw_path, for_write=not out_raw)
    except ValueError as e:
        return f"Refused: {e}"
    if not os.path.exists(path):
        return f"Archive '{path}' not found."
    ext = os.path.splitext(path)[1].lower()
    if ext != ".zip":
        return f"Repack currently supports .zip files (got {ext})."
    if out_raw:
        try:
            out = workspace.resolve_writable_path(out_raw)
        except ValueError as e:
            return f"Refused: {e}"
    else:
        out = path
    import zipfile
    try:
        with zipfile.ZipFile(path, "r") as zin:
            names = zin.namelist()
            seen = set()
            payload = []
            for item in zin.infolist():
                if drop_dirs and _zip_entry_is_dir(item):
                    continue
                if item.filename in seen:
                    continue
                seen.add(item.filename)
                payload.append((item, zin.read(item.filename)))
    except Exception as e:
        return f"Could not read '{path}': {e}"
    import shutil
    import tempfile
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip",
                                        dir=os.path.dirname(out) or None)
    os.close(tmp_fd)
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item, data in payload:
                zout.writestr(item.filename, data)
        with zipfile.ZipFile(tmp_path, "r") as chk:
            if chk.testzip() is not None:
                os.unlink(tmp_path)
                return "Repacked copy failed validation — original untouched."
        if out == path:
            shutil.copy2(path, path + ".cct-bak")
            shutil.move(tmp_path, path)
            try:
                os.unlink(path + ".cct-bak")
            except OSError:
                pass
        else:
            shutil.move(tmp_path, out)
        _mark_change(kind="modify", path=out, old="<archive>", new="<archive repacked>")
        return (f"Repacked '{path}' → '{out}': {len(payload)} entries written"
                + (" (directory entries dropped)" if drop_dirs else "")
                + ", validated OK.")
    except Exception as e:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return f"Repack FAILED — original untouched: {e}"


def _tool_archive_validate(args):
    """Validate that an archive file is intact and readable."""
    raw_path = str(args.get("path", "")).strip()
    if not raw_path:
        return "No archive path given."
    try:
        path = _resolve_tool_path(raw_path)
    except ValueError as e:
        return f"Refused: {e}"
    if not os.path.exists(path):
        return f"Archive '{path}' not found."
    ext = os.path.splitext(path)[1].lower()
    if ext == ".zip":
        import zipfile
        try:
            with zipfile.ZipFile(path, "r") as zf:
                bad = zf.testzip()
                count = len(zf.namelist())
                if bad:
                    return f"Archive '{path}' is CORRUPT - bad file: {bad}"
                return f"Archive '{path}' is VALID ({count} entries, CRC check passed)."
        except Exception as e:
            return f"Archive '{path}' is INVALID: {e}"
    elif ext in (".tar", ".gz", ".tgz", ".bz2"):
        import tarfile
        try:
            with tarfile.open(path, "r:*") as tf:
                count = len(tf.getmembers())
                tf.close()
                return f"Archive '{path}' is valid ({count} entries, no errors)."
        except Exception as e:
            return f"Archive '{path}' is INVALID: {e}"
    return f"Cannot validate format {ext}."


def _make_noninteractive_command(cmd: str) -> str:
    """Auto-inject non-interactive flags for known CLI tool scaffolding commands
    so automated agent runs never hang waiting for user keyboard confirmations."""
    c = (cmd or "").strip()
    has_yes = bool(re.search(r"(?:^|\s)(?:-y|--yes)(?:\s|$)", c, re.I))
    if re.search(r"^npm\s+create\s+", c, re.I):
        if not has_yes:
            parts = c.split(None, 2)
            if len(parts) >= 3:
                c = f"npm create -y {parts[2]}"
            else:
                c = f"{c} -y"
    elif re.search(r"^npx\s+", c, re.I):
        if not has_yes:
            c = re.sub(r"^(npx\s+)", r"\1--yes ", c, flags=re.I)
    elif re.search(r"^npm\s+init\s+", c, re.I):
        if not has_yes:
            c = re.sub(r"^(npm\s+init\s+)", r"\1-y ", c, flags=re.I)
    elif re.search(r"^yarn\s+create\s+", c, re.I):
        if not re.search(r"(?:^|\s)(?:--non-interactive|-y|--yes)(?:\s|$)", c, re.I):
            c = re.sub(r"^(yarn\s+create\s+)", r"\1--non-interactive ", c, flags=re.I)
    elif re.search(r"^pnpm\s+create\s+", c, re.I):
        if not has_yes:
            c = re.sub(r"^(pnpm\s+create\s+)", r"\1-y ", c, flags=re.I)
    return c


def _kill_proc_tree(proc):
    """Safely terminate a process and all its child/grandchild processes on any OS."""
    if proc is None:
        return
    try:
        pid = proc.pid
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True, timeout=5
                )
            except Exception:
                pass
            try:
                proc.kill()
            except Exception:
                pass
        else:
            try:
                import signal
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        try:
            if proc.stdout and not proc.stdout.closed:
                proc.stdout.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=1.0)
        except Exception:
            pass
    except Exception:
        pass


_ACTIVE_TOOL_PROCESSES = set()
_ACTIVE_TOOL_PROCESSES_LOCK = threading.Lock()
_ACTIVE_DEV_SERVERS = {}
_ACTIVE_DEV_SERVERS_LOCK = threading.Lock()
_CURRENT_AGENT_SHOULD_CANCEL = None


def register_tool_process(proc):
    """Register an in-flight tool subprocess for instant interruption."""
    if proc is not None:
        with _ACTIVE_TOOL_PROCESSES_LOCK:
            _ACTIVE_TOOL_PROCESSES.add(proc)


def unregister_tool_process(proc):
    """Unregister a finished or terminated tool subprocess."""
    if proc is not None:
        with _ACTIVE_TOOL_PROCESSES_LOCK:
            _ACTIVE_TOOL_PROCESSES.discard(proc)


def kill_active_tool_processes():
    """Immediately kill all in-flight tool processes across child trees (Stop button / Esc)."""
    with _ACTIVE_TOOL_PROCESSES_LOCK:
        procs = list(_ACTIVE_TOOL_PROCESSES)
        _ACTIVE_TOOL_PROCESSES.clear()
    with _ACTIVE_DEV_SERVERS_LOCK:
        dev_procs = list(_ACTIVE_DEV_SERVERS.values())
        _ACTIVE_DEV_SERVERS.clear()
    for p in procs + dev_procs:
        try:
            _kill_proc_tree(p)
        except Exception:
            pass


_URL_REGEX = re.compile(
    r"https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]):(\d+)[^\s\"'<>]*",
    re.IGNORECASE,
)

_DEV_SERVER_PATTERNS = [
    r"\b(npm|yarn|pnpm|bun)\s+(run\s+)?(dev|start|serve)\b",
    r"\b(vite|next\s+dev)\b",
    r"\bpython3?\s+-m\s+http\.server\b",
]


def _is_dev_server_command(cmd: str) -> bool:
    return any(re.search(pat, cmd, re.IGNORECASE) for pat in _DEV_SERVER_PATTERNS)


def _extract_local_url(text: str) -> Optional[str]:
    if not text:
        return None
    clean = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)
    m = _URL_REGEX.search(clean)
    if not m:
        return None
    url = m.group(0).rstrip(".,;)'\"\x1b")
    url = url.replace("://0.0.0.0:", "://localhost:")
    url = url.replace("://[::1]:", "://localhost:")
    url = url.replace("://127.0.0.1:", "://localhost:")
    if re.match(r"^https?://[^/]+$", url):
        url += "/"
    return url


def _diagnose_command_error(
    raw_cmd: str,
    output: str,
    exit_code: Optional[int],
    timed_out: bool,
    interrupted: bool,
    timeout: float,
) -> Optional[str]:
    """Diagnose the root cause of a command failure or timeout so the AI and user understand what went wrong."""
    if interrupted:
        return "Execution was interrupted by user (Stop / Esc). Subprocess tree was cleanly terminated."
    if timed_out:
        if _is_dev_server_command(raw_cmd):
            return (
                f"Command timed out after {timeout:.0f}s. This command starts a continuous development server. "
                "Dev servers run indefinitely and do not exit. CAT detects local URLs automatically — "
                "check if dependencies are installed via 'npm install' or inspect package.json."
            )
        return (
            f"Command exceeded timeout ({timeout:.0f}s) without finishing. "
            "Terminated to prevent agent hang. Output collected prior to timeout is shown below."
        )

    if exit_code is not None and exit_code != 0:
        low = output.lower()
        if (
            "cannot find module" in low
            or "err! missing" in low
            or "command not found" in low
            or "not recognized as an internal" in low
        ):
            return (
                "Missing project dependencies or build tool. "
                "Run 'npm install' or use 'install_packages' first before running this command."
            )
        if "eaddrinuse" in low or "address already in use" in low:
            return (
                "Network port is already occupied by another running process. "
                "Stop the existing server or specify an alternate port."
            )
        if "missing script" in low:
            return (
                "Requested script is not defined in package.json. "
                "Inspect package.json using inspect_project or read_file to check available scripts."
            )
        if (
            "the system cannot find the path specified" in low
            or "no such file or directory" in low
            or "directory not found" in low
        ):
            return (
                "Target folder or file path was not found. "
                "Use inspect_project or list_directory to verify the folder layout before cd/running."
            )
        if "syntaxerror" in low or "typescript error" in low:
            return (
                "Code syntax or TypeScript compilation error. "
                "Inspect the failing source files with read_file and fix the syntax."
            )
    return None


def _tool_run_terminal(args):
    """Execute a terminal command on the user's machine (spec v0.7.4:
    every AI-triggered terminal action must be transparent in the chat).
    Permission-gated via the shell_commands key; runs in the active
    workspace root; output, exit code, and duration are captured and
    recorded as a 'terminal' change so the summary shows them.
    Output is streamed in real time to Live Activities so progress is visible live."""
    import queue

    raw_cmd = str(args.get("command", "")).strip()
    if not raw_cmd:
        return "No command given."
    cmd = _make_noninteractive_command(raw_cmd)
    try:
        timeout = min(max(float(args.get("timeout", 60) or 60), 1.0), 300.0)
    except (TypeError, ValueError):
        timeout = 60.0
    cwd = workspace.root_dir() or os.getcwd()
    t0 = time.time()

    # Prepare non-interactive, automated environment
    run_env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "CI": "true",
        "npm_config_yes": "true",
        "NONINTERACTIVE": "1",
        "DEBIAN_FRONTEND": "noninteractive",
        "TERM": "dumb",
    }

    is_dev = _is_dev_server_command(raw_cmd)

    # Fast check: If command is a dev server and one is ALREADY responding, reuse immediately!
    if is_dev:
        try:
            from .browser import devserver
            for p in (5173, 3001, 8080, 5000, 4173, 3000):
                if devserver.probe_local_server(p):
                    active_url = f"http://localhost:{p}/"
                    return (
                        f"$ {raw_cmd}\n"
                        f"\u2713 Dev server is already active and running at {active_url}\n"
                        f"You can view and preview your application at {active_url}"
                    )
        except Exception:
            pass

    from . import activity as _act
    curr_turn = _act.get_current_turn() or ""
    act_obj = None
    try:
        act_obj = _act.manager.create(
            type=_act.TYPE_COMMAND,
            action="terminal",
            title=f"Terminal: {raw_cmd[:45]}",
            status=_act.STATUS_RUNNING,
            turn_id=curr_turn,
            command=raw_cmd,
            details=f"Running in {os.path.basename(cwd) or cwd}...",
            stdout="",
            category=_act.CAT_TERMINAL,
            phase=_act.PHASE_IMPLEMENTATION,
        )
    except Exception:
        pass

    timed_out = False
    interrupted = False
    returncode = None
    output_chunks = []
    proc = None
    dev_server_url = None

    out_queue = queue.Queue()

    def _stream_reader(pipe, q):
        try:
            while True:
                line = pipe.readline()
                if not line:
                    break
                q.put(line)
        except Exception:
            pass
        finally:
            try:
                pipe.close()
            except Exception:
                pass
            q.put(None)

    try:
        proc_kwargs = {
            "shell": True,
            "cwd": cwd,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "env": run_env,
        }
        if sys.platform == "win32":
            proc_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        proc = subprocess.Popen(cmd, **proc_kwargs)
        register_tool_process(proc)

        reader_thread = threading.Thread(
            target=_stream_reader, args=(proc.stdout, out_queue), daemon=True
        )
        reader_thread.start()

        last_act_update = time.time()

        while True:
            now = time.time()
            # 1. Non-blocking check for user interruption (Stop button / Esc)
            is_cancelled = bool(_CURRENT_AGENT_SHOULD_CANCEL and _CURRENT_AGENT_SHOULD_CANCEL())
            if is_cancelled:
                interrupted = True
                _kill_proc_tree(proc)
                break

            # 2. Strict timeout check (checked every 100ms)
            if now - t0 > timeout:
                timed_out = True
                _kill_proc_tree(proc)
                break

            # 3. Read stream output non-blockingly
            try:
                line = out_queue.get(timeout=0.1)
            except queue.Empty:
                if proc.poll() is not None and out_queue.empty():
                    break
                # If dev server command, probe common ports if it outputted "ready"
                if is_dev and (now - t0 >= 1.0):
                    try:
                        from .browser import devserver
                        for cp in (5173, 3001, 8080, 5000, 4173):
                            if devserver.probe_local_server(cp):
                                dev_server_url = f"http://localhost:{cp}/"
                                break
                    except Exception:
                        pass
                    if dev_server_url:
                        break
                continue

            if line is None:
                # Pipe closed / process exited
                break

            output_chunks.append(line)
            now = time.time()

            # Check if dev server URL is printed
            if is_dev and not dev_server_url:
                detected = _extract_local_url(line)
                if detected:
                    dev_server_url = detected
                    break

            if act_obj and (now - last_act_update >= 0.2):
                last_act_update = now
                try:
                    clean_line = line.strip()
                    _act.manager.update(
                        act_obj.id,
                        stdout="".join(output_chunks[-60:]),
                        details=clean_line[:60] if clean_line else "Running...",
                        duration_ms=int((now - t0) * 1000),
                    )
                except Exception:
                    pass

        # If dev server URL detected, register in _ACTIVE_DEV_SERVERS so it keeps serving
        if dev_server_url:
            with _ACTIVE_DEV_SERVERS_LOCK:
                _ACTIVE_DEV_SERVERS[dev_server_url] = proc
            returncode = 0
        elif not timed_out and not interrupted:
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_proc_tree(proc)

        if returncode is None:
            if interrupted:
                returncode = 130
            elif timed_out:
                returncode = 124
            else:
                returncode = proc.returncode if proc.returncode is not None else 0

    except OSError as e:
        if act_obj:
            try:
                _act.manager.update(
                    act_obj.id,
                    status=_act.STATUS_FAILED,
                    details=f"Error: {e}",
                    result="failed to spawn",
                )
            except Exception:
                pass
        return f"$ {raw_cmd}\nCould not run command: {e}"
    finally:
        unregister_tool_process(proc)
        try:
            from . import terminal_identity
            terminal_identity.set_terminal_title()
        except Exception:
            pass

    duration = round(time.time() - t0, 2)
    output = "".join(output_chunks).strip()
    if len(output) > 100_000:
        output = output[:100_000] + "\n... [truncated for memory safety]"

    _mark_change(kind="terminal", command=raw_cmd, output=output,
                 exit_code=returncode, duration=duration)

    diagnostic = _diagnose_command_error(
        raw_cmd, output, returncode, timed_out, interrupted, timeout
    )

    if dev_server_url:
        if act_obj:
            try:
                _act.manager.update(
                    act_obj.id,
                    status=_act.STATUS_COMPLETED,
                    details=f"Live at {dev_server_url}",
                    stdout=output[-2000:],
                    result=f"dev server running at {dev_server_url}",
                    duration_ms=int(duration * 1000),
                    exit_code=0,
                )
            except Exception:
                pass
        lines = [f"$ {raw_cmd}"]
        if output:
            lines.extend(output.splitlines()[-20:])
        lines.append(f"\n\u2713 Dev server is live and running at {dev_server_url}")
        lines.append(
            f"You can view and preview your application by opening {dev_server_url} in your browser or CAT preview."
        )
        return "\n".join(lines)

    if interrupted:
        if act_obj:
            try:
                _act.manager.update(
                    act_obj.id,
                    status=_act.STATUS_CANCELLED,
                    details="Interrupted by user",
                    result="interrupted",
                    duration_ms=int(duration * 1000),
                    stdout=output[-2000:],
                    exit_code=130,
                )
            except Exception:
                pass
        lines = [f"$ {raw_cmd}"]
        if output:
            lines.extend(output.splitlines()[-20:])
        lines.append("\u2298 Interrupted by user (execution stopped).")
        return "\n".join(lines)

    if timed_out:
        if act_obj:
            try:
                _act.manager.update(
                    act_obj.id,
                    status=_act.STATUS_FAILED,
                    details=f"Timed out after {timeout:.0f}s",
                    result="timed out",
                    duration_ms=int(duration * 1000),
                    stdout=output[-2000:],
                    exit_code=124,
                )
            except Exception:
                pass
        lines = [f"$ {raw_cmd}"]
        if output:
            lines.extend(output.splitlines()[-30:])
        lines.append(f"\u2715 Command timed out after {timeout:.0f}s (exit 124).")
        if diagnostic:
            lines.append(f"\n[DIAGNOSTIC] {diagnostic}")
        return "\n".join(lines)

    if act_obj:
        try:
            _act.manager.update(
                act_obj.id,
                status=_act.STATUS_COMPLETED if returncode == 0 else _act.STATUS_FAILED,
                details=f"Exit {returncode} in {duration}s",
                stdout=output[-2000:],
                result=f"exit code {returncode}",
                duration_ms=int(duration * 1000),
                exit_code=returncode,
            )
        except Exception:
            pass

    tail = output.splitlines()[-40:]
    lines = [f"$ {raw_cmd}"]
    lines.extend(tail)
    if diagnostic and returncode != 0:
        lines.append(f"\n[DIAGNOSTIC] {diagnostic}")
    status = "success" if returncode == 0 else f"exit code {returncode}"
    lines.append(f"\u2713 {status} ({duration}s)" if returncode == 0 else f"\u2715 {status} ({duration}s)")
    return "\n".join(lines)


def _run_project_command(args, default_cmd, label):
    """Shared executor for run_build / run_tests: pick a real command
    (explicit arg, or auto-detected from the project's manifest files)
    and run it in the workspace root via the same subprocess path as
    run_terminal — real execution, real output, real exit codes."""
    cmd = str(args.get("command", "")).strip()
    if not cmd:
        root = workspace.root_dir()
        # detect from what actually exists on disk
        has = lambda n: os.path.isfile(os.path.join(root, n))
        if label == "build":
            if has("package.json"):
                cmd = "npm run build"
            elif has("pyproject.toml"):
                cmd = "python -m build"
            elif has("setup.py"):
                cmd = "python setup.py build"
            elif has("Cargo.toml"):
                cmd = "cargo build"
            elif has("Makefile"):
                cmd = "make"
            elif has("CMakeLists.txt"):
                cmd = "cmake --build ."
        else:
            if has("package.json"):
                cmd = "npm test"
            elif has("pyproject.toml") or has("setup.cfg") or has("pytest.ini"):
                cmd = "python -m pytest"
            elif has("Cargo.toml"):
                cmd = "cargo test"
            elif has("go.mod"):
                cmd = "go test ./..."
        if not cmd:
            return (f"No {label} command found and none given. Pass "
                    f'{{"command": "..."}} explicitly, or add a package.json / '
                    f"pyproject.toml to the workspace.")
    return _tool_run_terminal({"command": cmd,
                               "timeout": args.get("timeout", 120)})


def _tool_run_build(args):
    """Build the project in the active workspace for real."""
    return _run_project_command(args, None, "build")


def _tool_run_tests(args):
    """Run the project's test suite for real and report the result."""
    return _run_project_command(args, None, "test")


def _tool_inspect_project(args):
    """Inspect the active workspace/project: layout, key manifests, and
    entry points — so the agent grounds itself before acting instead of
    guessing or asking the user which project it is."""
    path_raw = str(args.get("path", "")).strip() or "."
    try:
        base = (_resolve_tool_path(path_raw) if path_raw != "."
                else workspace.root_dir())
    except ValueError as e:
        return f"Refused: {e}"
    if not os.path.isdir(base):
        return f"'{base}' is not a folder."
    entries = sorted(os.listdir(base))
    dirs = [e for e in entries if os.path.isdir(os.path.join(base, e))]
    files = [e for e in entries if os.path.isfile(os.path.join(base, e))]
    manifests = [f for f in files if f.lower() in (
        "package.json", "pyproject.toml", "requirements.txt", "setup.py",
        "setup.cfg", "cargo.toml", "go.mod", "makefile", "cmakelists.txt",
        "readme.md", "pipfile", "poetry.lock")]
    code_exts = {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".java",
                 ".c", ".cpp", ".rs", ".go", ".rb", ".php"}
    code_files = [f for f in files
                  if os.path.splitext(f)[1].lower() in code_exts]
    lines = [f"Project root: {base}",
             f"Folders ({len(dirs)}): " + (", ".join(dirs[:25]) or "(none)"),
             f"Files ({len(files)}):"]
    for f in files[:60]:
        try:
            size = os.path.getsize(os.path.join(base, f))
        except OSError:
            size = 0
        lines.append(f"  {f} ({size}B)")
    if len(files) > 60:
        lines.append(f"  ...and {len(files) - 60} more")
    if manifests:
        lines.append("Key manifests: " + ", ".join(manifests))
        pm = next((m for m in ("package.json", "pyproject.toml",
                               "requirements.txt") if m in manifests), None)
        if pm:
            try:
                with open(os.path.join(base, pm), "r", encoding="utf-8",
                          errors="replace") as fh:
                    head = "".join(fh.readline() for _ in range(40))
                lines.append(f"\nHead of {pm}:\n{head}")
            except OSError:
                pass
    if code_files:
        lines.append("Code files at root: " + ", ".join(code_files[:30]))
    return "\n".join(lines)


def _tool_install_packages(args):
    """Autonomous Package Manager tool — installs real packages through
    packages.py (pip/npm/cargo/brew/winget/...). Governed by the SAME
    permission engine as every other tool (requirement #7): ASK EACH
    TIME prompts via the caller's permission_callback, FULL ACCESS
    executes automatically, RESTRICTED refuses with an honest error.
    No mode-based lockout and no broken approval side-path."""
    from . import packages
    raw = str(args.get("packages") or args.get("package") or "").strip()
    if not raw:
        return "No package given. Pass {\"packages\": \"requests\"} or {\"packages\": [\"numpy\", \"pandas\"]}."
    if re.match(r"^(pip|npm|pnpm|yarn|bun|cargo|conda|brew|choco|winget|apt|dnf)\s+install\s+", raw, re.I):
        # the model passed a whole shell command — extract the package spec(s)
        raw = re.sub(r"^(pip3?|npm|pnpm|yarn|bun|cargo|conda|brew|choco|winget|apt|dnf)(\s+install|\s+add)\s+", "", raw, flags=re.I).strip()
        raw = re.sub(r"^-[\w-]+\s*", "", raw).strip() or raw
    names = [p.strip() for p in re.split(r"[,\s]+", raw) if p.strip()]
    if len(names) > 1:
        names = names[:3]
        results = [_install_one_package(n, args) for n in names]
        return "\n\n".join(results)
    return _install_one_package(names[0], args)


def _install_one_package(name, args):
    """Shared single-package install used by _tool_install_packages.
    Runs the full permission-narrowed install flow; returns the
    observation text."""
    from . import packages
    from . import permissions as perm
    from . import package_research

    # Parse a possibly-versioned name like "numpy==1.26" or "requests>=2".
    import re as _re
    m = _re.match(r"^([A-Za-z0-9_.@/-]+?)([<>=~!].*)?$", name)
    pkg = m.group(1) if m else name
    version = (m.group(2) or "latest").lstrip("=<>~!")
    req = packages.PackageRequest(name=pkg, version=version or "latest",
                                  raw=name)

    manager = packages.detect_manager(req)
    if manager is None:
        card = package_research.research_card(req)
        card_lines = package_research.render_card(req, card)
        research_note = ("Unknown package — researched it:\n"
                         + "\n".join(line.strip() for line in card_lines)
                         + "\n\nRecommendation: " + card.get("recommendation", ""))
        manager = "pip"  # sensible default for a Python terminal, still approval-gated
        req.manager = manager
        research_note += f"\n\nProceeding with {packages.MANAGERS[manager]['label']} (approval required below)."
    else:
        req.manager = manager
        research_note = f"Detected {packages.MANAGERS[manager]['label']} as the right manager."

    flow = perm.install_flow_state()
    try:
        if not flow["allow"]:
            return (f"{research_note}\n\nPermission denied: Restricted mode "
                    "— package installs are disabled, nothing was installed.")
        remembered = packages.remembered_decision(manager, req.name)
        if remembered == "deny":
            return (f"{research_note}\n\nInstall of {req.label()} was previously "
                    f"denied (remembered choice) — nothing installed.")
        events = []
        if flow["prompt"] and remembered is None:
            # ASK EACH TIME mode: the caller's permission dispatch
            # already showed the approval card for this exact install
            # before we got here (perm_key install_packages) — reaching
            # this point means the user approved. Surface the stage so
            # the activity log shows the approval happened.
            events.append({"stage": packages.STAGE_PERMISSION,
                           "message": f"Approved by the user — installing {req.label()} "
                                      f"via {packages.MANAGERS[manager]['label']}."})
        out_lines = [research_note]
        result = packages.run_install(req, on_event=lambda ev: events.append(ev))
        out_lines.append(packages.summarize(result, req))
        tail = (result.get("output_tail") or "").strip()
        if tail:
            out_lines.append("")
            out_lines.append("Last output:")
            out_lines.extend("  " + l for l in tail.splitlines()[-6:])
        return "\n".join(out_lines)
    finally:
        perm.restore_mode()


# --------------------------------------------------- change summaries --
# Git-style change reports (spec v0.7.4: every AI code modification must
# be visible in the chat as a real diff, never a silent edit). Built
# from the `change` snapshots the file tools record via _mark_change,
# rendered line-by-line with +/- markers and line numbers, capped so a
# few-line edit never floods the chat with the whole file.
#
# `markdown=True` wraps each diff in a ```diff fence so the chat's Rich
# Markdown renderer (pygments is installed) colors + green / - red;
# `markdown=False` produces plain lines for the classic terminal.

_MAX_CHANGE_ROWS = 120
_MAX_OUTPUT_LINES = 25


def _git_diff_rows(old_text, new_text, max_rows=_MAX_CHANGE_ROWS):
    """Git-style per-line diff of a rewrite. Returns rows of
    (marker, lineno, line): '+' = added (NEW line number), '-' = removed
    (OLD line number), marker '...' = truncation notice."""
    from itertools import zip_longest
    import difflib
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    rows = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            for i, j in zip_longest(range(i1, i2), range(j1, j2), fillvalue=None):
                if i is not None:
                    rows.append(("-", i + 1, old_lines[i]))
                if j is not None:
                    rows.append(("+", j + 1, new_lines[j]))
        elif tag == "delete":
            for i in range(i1, i2):
                rows.append(("-", i + 1, old_lines[i]))
        elif tag == "insert":
            for j in range(j1, j2):
                rows.append(("+", j + 1, new_lines[j]))
    if len(rows) > max_rows:
        rows = rows[:max_rows] + [("...", "", f"{len(rows) - max_rows} more changed line(s) omitted")]
    return rows


def _change_line_stats(change):
    """(added, removed, modified) line counts for one change snapshot:
    added = new lines in insert/replace hunks; removed = deleted lines;
    modified = lines whose content changed in replace hunks (old side)."""
    kind = change.get("kind")
    if kind == "create":
        return len(str(change.get("new") or "").splitlines()), 0, 0
    if kind == "modify":
        import difflib
        old = str(change.get("old") or "").splitlines()
        new = str(change.get("new") or "").splitlines()
        matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
        added = removed = modified = 0
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "replace":
                added += j2 - j1
                modified += i2 - i1
            elif tag == "delete":
                removed += i2 - i1
            elif tag == "insert":
                added += j2 - j1
        return added, removed, modified
    return 0, 0, 0


def _append_diff_block(out, rows, fence):
    if fence:
        out.append(fence)
    for marker, lineno, line in rows:
        if marker == "...":
            out.append(f"  {line}")
        else:
            out.append(f"{marker} {lineno} | {line}")
    if fence:
        out.append("```")


def summarize_file_changes(steps, markdown=False, max_rows=_MAX_CHANGE_ROWS,
                           max_output_lines=_MAX_OUTPUT_LINES):
    """Build the chat-ready change report for a completed agent run:

        ✓ Changes Applied

        Files modified: 3
        Lines added: 18
        Lines removed: 5
        Lines modified: 11

        ------------------

        ✓ Created: utils.py (24 lines added)

        ```diff
        +  1 | def calculate_mass():
        +  2 |     return moles * molar_mass
        ```

        ------------------

        ✎ Modified: main.py (+2 −1)

        ```diff
        - 62 | total = a+b
        + 62 | total = a + b
        ```

        ... then terminal actions, then the action timeline.

    Returns '' when nothing on disk actually changed.
    """
    changes = []
    for _name, _args, _obs, change in (steps or []):
        if isinstance(change, dict) and change:
            changes.append(change)
    if not changes:
        return ""
    fence = "```diff" if markdown else ""
    sep = "------------------"

    files = 0
    tot_added = tot_removed = tot_modified = 0
    for c in changes:
        if c.get("kind") in ("create", "modify", "delete", "rename"):
            files += 1
        a, r, m = _change_line_stats(c)
        tot_added += a
        tot_removed += r
        tot_modified += m

    out = ["✓ Changes Applied", "",
           f"Files modified: {files}",
           f"Lines added: {tot_added}",
           f"Lines removed: {tot_removed}",
           f"Lines modified: {tot_modified}"]

    for c in changes:
        kind = c.get("kind")
        path = c.get("path", "?")
        out.append("")
        out.append(sep)
        out.append("")
        if kind == "create":
            new = str(c.get("new") or "")
            count = len(new.splitlines())
            out.append(f"✓ Created: {path} ({count} line{'s' if count != 1 else ''} added)")
            rows = [("+", j + 1, line) for j, line in enumerate(new.splitlines()[:max_rows])]
            _append_diff_block(out, rows, fence)
        elif kind == "modify":
            rows = _git_diff_rows(str(c.get("old") or ""), str(c.get("new") or ""), max_rows)
            if not rows:
                continue
            a, r, _m = _change_line_stats(c)
            out.append(f"✎ Modified: {path} (+{a} \u2212{r})")
            _append_diff_block(out, rows, fence)
        elif kind == "delete":
            out.append(f"🗑 Deleted: {path}")
        elif kind == "rename":
            out.append(f"📄 Renamed: {path} \u2192 {c.get('new_path', '?')}")
        elif kind == "terminal":
            out.append(f"› {c.get('command', '')}")
            out.append("")
            raw_out = str(c.get("output") or "").strip()
            # Clean ANSI escape sequences and carriage returns so terminal control codes don't render as broken glyph boxes
            clean_out = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b\(B", "", raw_out)
            clean_out = clean_out.replace("\r", "")
            output = [l.rstrip() for l in clean_out.splitlines() if l.strip()]
            if output:
                if markdown:
                    out.append("```text")
                    for line in output[:max_output_lines]:
                        out.append(line)
                    if len(output) > max_output_lines:
                        out.append(f"... {len(output) - max_output_lines} more line(s) omitted")
                    out.append("```")
                else:
                    for line in output[:max_output_lines]:
                        out.append("    " + line)
                    if len(output) > max_output_lines:
                        out.append(f"    ... {len(output) - max_output_lines} more line(s) omitted")
                out.append("")
            code = c.get("exit_code")
            dur = c.get("duration")
            status = "✓" if code == 0 else "✗"
            out.append(f"{status} exit {code}" + (f" ({dur}s)" if dur is not None else ""))

    out.append("")
    out.append(sep)
    out.append("")
    out.append("**Timeline**")
    out.append("")
    for _name, _args, _obs, change in (steps or []):
        if not isinstance(change, dict) or not change:
            continue
        kind = change.get("kind")
        if kind in ("create", "modify", "delete", "rename"):
            action = {"create": "Created", "modify": "Edited",
                      "delete": "Deleted", "rename": "Renamed"}[kind]
            base = os.path.basename(str(change.get("path", "")))
            a, r, _m = _change_line_stats(change)
            extra = f" (+{a} \u2212{r})" if kind == "modify" and (a or r) else ""
            out.append(f"- ✓ {action} `{base}`{extra}")
        elif kind == "terminal":
            out.append(f"- ✓ Ran `{change.get('command', '')}`")
    out.append("- ✓ Finished")
    return "\n".join(out)


def _tool_read_file(args):
    raw_path = str(args.get("path", "")).strip()
    if not raw_path:
        return "No path given."
    try:
        path = _resolve_tool_path(raw_path)
    except ValueError as e:
        return f"Refused: {e}"
    if not os.path.isfile(path):
        return f"'{path}' is not a file (or doesn't exist)."
    content, truncated = aicore.read_text_file_for_context(path)
    if content is None:
        return f"Could not read '{path}' (binary or unreadable)."
    note = " (truncated)" if truncated else ""
    return f"Contents of '{path}'{note}:\n{content}"


def _tool_device_action(args):
    """v0.7.7 Responsible Device Control (spec section 14): plans an
    action on an authorized device through device_control.py, and
    executes it only when the provider reports it can really do the
    thing. The permission dispatch (perm_key device_control) is the
    user's explicit approval gate; every action is logged."""
    from . import device_control as dc
    provider_key = str(args.get("provider", "")).strip().lower()
    action = str(args.get("action", "run")).strip() or "run"
    target = str(args.get("target", "")).strip()
    if not provider_key:
        return ("No provider given. Available: "
                + ", ".join(f"{p['key']}" for p in dc.available_providers()) + ".")
    resolved = dc.plan_action(provider_key, action, {"target": target,
                                                      "command": args.get("command")})
    if not resolved["ok"]:
        dc.log_action(provider_key, action, target, "denied",
                      resolved.get("reason", "unavailable"))
        return resolved["reason"]
    plan = resolved["plan"]
    if plan.get("command") is None and plan.get("effect", "").startswith(
            "Runs in your terminal"):
        return "Planned: " + plan["effect"]
    result = dc.execute_approved(provider_key, plan, {"target": target,
                                                      "command": args.get("command")})
    if result.get("ok"):
        out = result.get("output")
        note = str(result.get("note") or result.get("exit_code") or "done")
        if out:
            return f"Device action approved and executed ({provider_key}/{action}): {note}\n{out}"
        return f"Device action approved and executed ({provider_key}/{action}): {note}"
    return (f"Device action planned but execution failed: "
            + str(result.get("note", "unknown error")))


def _tool_list_directory(args):
    raw_path = str(args.get("path", "") or ".").strip()
    try:
        path = workspace.resolve_writable_path(raw_path)
    except ValueError as e:
        return f"Refused: {e}"
    if not os.path.isdir(path):
        return f"'{path}' is not a folder (or doesn't exist)."

    def _scan():
        try:
            entries = sorted(os.listdir(path))
        except OSError as e:
            return None
        lines = [f"Contents of '{path}':"]
        for name in entries[:200]:
            full = os.path.join(path, name)
            kind = "dir" if os.path.isdir(full) else "file"
            size = "" if kind == "dir" else f", {os.path.getsize(full)}B"
            lines.append(f"  [{kind}] {name}{size}")
        if len(entries) > 200:
            lines.append(f"  ...and {len(entries) - 200} more entries.")
        return "\n".join(lines)

    # v0.7.9.0: repeated listings within one agent run are served from a
    # TTL+mtime-guarded cache (fs_cache) — invalidated by any CAT write/
    # delete/rename and by external directory changes (mtime probe).
    from . import fs_cache
    cached = fs_cache.cached_dir_listing(path, _scan)
    return cached or f"Could not list '{path}'."


def _tool_ask_question(args):
    """Ask the user a clarifying question with multiple-choice options or custom input."""
    q = str(args.get("question", "")).strip()
    options = args.get("options") or []
    if not q:
        return "No question provided."
    print()
    opts_lines = [f"  [{i+1}] {opt}" for i, opt in enumerate(options)]
    print(theme.panel([f"AI Inquiry: {q}"] + opts_lines,
                      title="question", color=theme.CYAN))
    ans = input(theme.dim("  ▸ ")).strip()
    if ans.isdigit() and 1 <= int(ans) <= len(options):
        ans = options[int(ans) - 1]
    return f"User response: {ans or 'No answer provided'}"


def _tool_customize_cat_cli(args):
    """Customize and edit the CAT CLI configuration directly through workflow."""
    settings = args.get("settings") or {}
    reason = str(args.get("reason", "Customizing CAT CLI via workflow"))
    try:
        from .workflow_engine import WorkflowCLICustomizer
        res = WorkflowCLICustomizer.apply_customizations(settings, reason=reason)
        if res.get("success"):
            return f"CAT CLI customized successfully: {res.get('message')}"
        return f"Failed to customize CAT CLI: {res.get('error') or res.get('ignored')}"
    except Exception as e:
        return f"Error customizing CAT CLI: {e}"


def _tool_delegate_task_to_kitty(args):
    """Share task, prompts, and code solutions to another specialized Kitty (e.g. build, debugger, automator)."""
    target = str(args.get("target_kitty", "")).strip().lower()
    objective = str(args.get("task_objective", "")).strip()
    prompt = str(args.get("prompt", "")).strip()
    solution = str(args.get("solution", "") or args.get("response", "")).strip()
    code = str(args.get("code_snippets", "")).strip()
    if not target or not objective:
        return "Must specify target_kitty (e.g. 'build', 'debugger', 'automator') and task_objective."
    try:
        from . import ai_modes
        from .workflow_engine import workflow_engine
        current = ai_modes.current_kitty()
        handoff = ai_modes.share_task_between_kitties(
            from_kitty=current,
            to_kitty=target,
            task_objective=objective,
            prompt=prompt,
            response=solution,
            code_snippets=code
        )
        workflow_engine.record_point_to_point_step(
            source_node=f"kitty.{current}",
            target_node=f"kitty.{target}",
            step_name=f"Delegate Task: {objective[:60]}",
            payload={"from_kitty": current, "to_kitty": target, "objective": objective},
            result="Handoff Queued",
            duration_ms=10
        )
        if args.get("switch_active", True):
            ai_modes.set_kitty(target)
        return (
            f"Successfully shared task and delegated to '{target}' Kitty.\n"
            f"Handoff ID: {handoff['id']}\n"
            f"Target '{target}' Kitty is now equipped with the full shared context and prompt solution."
        )
    except Exception as e:
        return f"Error delegating task to Kitty '{target}': {e}"


TOOLS = {
    "ask_question": {
        "run": _tool_ask_question,
        "desc": "Ask the user a clarifying question with options or free text input.",
        "args": '{"question": "Which architecture or framework should we use?", "options": ["Option A", "Option B"]}',
        "perm_key": "ask_question",
        "describe": lambda a: ("Ask Question", "", str(a.get("question", ""))),
    },
    "customize_cat_cli": {
        "run": _tool_customize_cat_cli,
        "desc": "Fully edit or customize CAT CLI settings and options through workflow.",
        "args": '{"settings": {"default_ai_mode": "grok", "eco_mode": false}, "reason": "Optimizing CLI"}',
        "perm_key": "write_file",
        "describe": lambda a: ("Customize CAT CLI", "config", f"Update CLI settings: {a.get('settings', {})}")
    },
    "delegate_task_to_kitty": {
        "run": _tool_delegate_task_to_kitty,
        "desc": "Share prompts, code solutions, and hand off tasks to another specialized Kitty (e.g. build, debugger, automator).",
        "args": '{"target_kitty": "build", "task_objective": "Implement code from plan", "code_snippets": "..."}',
        "describe": lambda a: ("Delegate to Kitty", str(a.get("target_kitty", "")), str(a.get("task_objective", ""))),
    },

    "list_formulas": {
        "run": _tool_list_formulas,
        "desc": "List every formula key in the library (call this if unsure of a key).",
        "args": "{}",
    },
    "solve_formula": {
        "run": _tool_solve_formula,
        "desc": "Solve a named library formula for its one unknown variable.",
        "args": '{"key": "ideal_gas", "values": {"P": 1, "n": 2, "T": 300}}  (leave exactly one variable out of values)',
    },
    "solve_custom": {
        "run": _tool_solve_custom,
        "desc": "Solve ANY formula you write, for any named variable — not limited to the library.",
        "args": '{"formula": "P*V = n*R*T", "values": {"P": 1, "n": 2, "T": 300}, "solve_for": "V"}',
    },
    "calculate": {
        "run": _tool_calculate,
        "desc": "Evaluate a plain arithmetic/scientific expression exactly (+ - * / ** sqrt log sin cos ...).",
        "args": '{"expression": "2.303/50 * log10(1.0/0.25)"}',
    },
    "generate_numerical": {
        "run": _tool_generate_numerical,
        "desc": "Generate and render a full randomized notebook-style numerical for a topic (kinetics/mole/etc).",
        "args": '{"topic": "first order half life"}',
    },
    "plot_preset": {
        "run": _tool_plot_preset,
        "desc": "Plot one of the 10 built-in animated chemistry curves (kinetics, Arrhenius, Boyle's, titration...).",
        "args": '{"preset": "arrhenius", "export": false}',
    },
    "plot_function": {
        "run": _tool_plot_function,
        "desc": "Plot/animate ANY 2D function you name yourself, e.g. a curve not in the presets.",
        "args": '{"expression": "sin(x)*exp(-x/5)", "xmin": 0, "xmax": 20, "title": "Damped oscillation", "export": false}',
    },
    "plot_surface": {
        "run": _tool_plot_surface,
        "desc": "Export a high-quality 3D surface PNG: built-in ('orbital_3d','pvt') or any z=f(x,y) you name.",
        "args": '{"kind": "custom", "expression": "exp(-(x**2+y**2)/4)", "title": "Gaussian electron density"}',
    },
    "simulate_atom_2d": {
        "run": _tool_atom_2d,
        "desc": "Run the live 2D animated Bohr atom / electron / proton / neutron simulation for an element.",
        "args": '{"element": "Fe", "frames": 220}',
    },
    "simulate_atom_3d": {
        "run": _tool_atom_3d,
        "desc": "Run the live real-time 3D atom / electron / proton simulation (rotatable) for an element.",
        "args": '{"element": "Na", "frames": 220}',
    },
    "simulate_orbital": {
        "run": _tool_orbital,
        "desc": "Run the live quantum orbital electron-cloud Monte-Carlo simulation (1s,2s,2p,3s,3p,3d).",
        "args": '{"orbital": "2p", "points": 1500}',
    },
    "orbital_grid": {
        "run": _tool_orbital_grid,
        "desc": "Export a reference-chart PNG of many hydrogen orbitals' |psi|^2 side by side (n up to 4).",
        "args": "{}",
    },
    "bonding_map": {
        "run": _tool_bonding,
        "desc": "Export a stylized chemical-bonding electron-density map (ELF-style, rainbow colormap) for a molecule.",
        "args": '{"molecule": "furan"}  (available: furan, water, methane, co2, ethanol, benzene)',
    },
    "bloch_sphere": {
        "run": _tool_bloch,
        "desc": "Export a Bloch sphere for a single qubit state, with exact Z/X/Y measurement probabilities.",
        "args": '{"theta_deg": 90, "phi_deg": 0}  (90,0 = |+>; 0,0 = |0>; 90,90 = |+i>)',
    },
    "web_search": {
        "run": _tool_web_search,
        "desc": "Search the live web for current information (no API key needed).",
        "args": '{"query": "latest IUPAC atomic weight of lithium", "max_results": 5}',
    },
    "deep_research": {
        "run": _tool_deep_research,
        "desc": "Run several web searches on different angles of a topic and synthesize a cited summary.",
        "args": '{"topic": "green hydrogen production methods", "num_queries": 3}',
    },
    "fetch_web_page": {
        "run": _tool_fetch_web_page,
        "desc": "Fetch and extract clean readable text content from a web page URL.",
        "args": '{"url": "https://en.wikipedia.org/wiki/Quantum_computing", "max_chars": 8000}',
        "describe": lambda a: ("Fetch Web Page", str(a.get("url", "")), "Extract web content"),
    },
    "read_attachment": {
        "run": _tool_read_attachment,
        "desc": "Read/analyze a file or image the user imported with /import this session.",
        "args": '{"path": "notes.txt"}  (path can be a partial match; omit to use the most recent import)',
    },
    "read_file": {
        "run": _tool_read_file,
        "desc": "Read a real file from disk by path (workspace-relative or absolute).",
        "args": '{"path": "src/main.py"}',
        "perm_key": "read_files",
    },
    "list_directory": {
        "run": _tool_list_directory,
        "desc": "List a real folder's contents by path (workspace-relative or absolute).",
        "args": '{"path": "src"}  (omit path to list the workspace root)',
        "perm_key": "read_files",
    },
    "write_file": {
        "run": _tool_write_file,
        "desc": "Create or overwrite a real file on disk with the given text content.",
        "args": '{"path": "src/main.py", "content": "print(1)", "overwrite": false, '
                '"reason": "Generate the requested script."}',
        "perm_key": "write_files",
        "describe": lambda a: ("Write file", str(a.get("path", "")),
                                str(a.get("reason") or "Generate/update requested file content.")),
    },
    "create_folder": {
        "run": _tool_create_folder,
        "desc": "Create a real folder on disk (and any missing parent folders).",
        "args": '{"path": "src/models", "reason": "Organize the new module."}',
        "perm_key": "write_files",
        "describe": lambda a: ("Create folder", str(a.get("path", "")),
                                str(a.get("reason") or "Create requested folder.")),
    },
    "delete_file": {
        "run": _tool_delete_file,
        "desc": "Permanently delete a single real file on disk (folders are refused).",
        "args": '{"path": "old_notes.txt", "reason": "No longer needed."}',
        "perm_key": "write_files",
        "describe": lambda a: ("Delete file", str(a.get("path", "")),
                                str(a.get("reason") or "Remove requested file.")),
    },
    "rename_file": {
        "run": _tool_rename_file,
        "desc": "Rename/move a real file or folder on disk.",
        "args": '{"path": "old.py", "new_path": "new.py", "reason": "Clearer name."}',
        "perm_key": "write_files",
        "describe": lambda a: (f"Rename '{a.get('path', '')}' → '{a.get('new_path', '')}'",
                                str(a.get("path", "")),
                                str(a.get("reason") or "Rename/move requested file.")),
    },
    "edit_file": {
        "run": _tool_edit_file,
        "desc": "Edit a file by replacing old_text with new_text (find/replace). "
                "The old_text must appear exactly in the file.",
        "args": '{"path": "main.py", "old_text": "old code", "new_text": "new code", "reason": "Fix bug."}',
        "perm_key": "write_files",
        "describe": lambda a: (f"Edit '{a.get('path', '')}'",
                                str(a.get("old_text", "")[:60]),
                                str(a.get("reason") or "Edit file content.")),
    },
    "search_workspace": {
        "run": _tool_search_workspace,
        "desc": "Search for files or content in the workspace. Returns matching lines with file:line.",
        "args": '{"query": "def main", "file_pattern": "*.py", "max_results": 10}',
        "describe": lambda a: (f"Search for '{a.get('query', '')}'",
                                str(a.get("query", "")),
                                "Search workspace files."),
    },
    "archive_list": {
        "run": _tool_archive_list,
        "desc": "List all entries in an archive (ZIP, tar.gz, tar.bz2) — folders and files, with sizes. Use this FIRST on any attached/compressed file.",
        "args": '{"path": "backup.zip"}',
        "describe": lambda a: (f"Inspect archive: {a.get('path', '')}",
                                str(a.get("path", "")),
                                "List archive contents."),
    },
    "archive_delete_entries": {
        "run": _tool_archive_delete_entries,
        "desc": "Delete entries from a ZIP archive by exact name or glob pattern; folder names remove the whole folder tree. Safe-replace: original preserved until the modified copy validates.",
        "args": '{"path": "backup.zip", "entries": ["folders/", "old_file.txt"]}  or {"pattern": "*.tmp"}',
        "perm_key": "write_files",
        "describe": lambda a: (f"Delete entries from archive: {a.get('path', '')}",
                                str(a.get("path", "")),
                                "Remove selected entries from the archive."),
    },
    "archive_extract": {
        "run": _tool_archive_extract,
        "desc": "Extract an archive into a real destination folder (default: a folder named after the archive in the workspace).",
        "args": '{"path": "project.zip", "dest": "extracted_project"}',
        "perm_key": "write_files",
        "describe": lambda a: (f"Extract archive: {a.get('path', '')}",
                                str(a.get("dest", "")),
                                "Extract the archive to disk."),
    },
    "archive_add_entries": {
        "run": _tool_archive_add_entries,
        "desc": "Add files (from disk) and/or new text entries into an existing ZIP archive.",
        "args": '{"path": "project.zip", "files": ["notes.txt"]}  or {"entries": [{"name": "docs/readme.md", "content": "..."}]}',
        "perm_key": "write_files",
        "describe": lambda a: (f"Add entries to archive: {a.get('path', '')}",
                                str(a.get("path", "")),
                                "Add entries into the archive."),
    },
    "archive_repack": {
        "run": _tool_archive_repack,
        "desc": "Rebuild a ZIP fresh: recompress, dedupe repeated names, optionally drop directory placeholder entries (drop_dirs).",
        "args": '{"path": "project.zip", "drop_dirs": false}',
        "perm_key": "write_files",
        "describe": lambda a: (f"Repack archive: {a.get('path', '')}",
                                str(a.get("path", "")),
                                "Rebuild/recompress the archive."),
    },
    "archive_validate": {
        "run": _tool_archive_validate,
        "desc": "Validate that an archive file is intact and readable (zip CRC test / tar read-through). Run this after any modification.",
        "args": '{"path": "backup.zip"}',
        "describe": lambda a: (f"Validate archive: {a.get('path', '')}",
                                str(a.get("path", "")),
                                "Check archive integrity."),
    },
    "run_build": {
        "run": _tool_run_build,
        "desc": "Build the project in the active workspace (auto-detects npm/pyproject/setup.py/cargo/Makefile/CMake, or pass an explicit command). Real build output and exit code.",
        "args": '{"command": "npm run build"}  (or {} to auto-detect)',
        "perm_key": "shell_commands",
        "describe": lambda a: ("Run project build", str(a.get("command", "") or "(auto-detected)"),
                                "Build the project so its result can be verified."),
    },
    "run_tests": {
        "run": _tool_run_tests,
        "desc": "Run the project's test suite (auto-detects pytest/npm test/cargo/go test, or pass an explicit command). Real results.",
        "args": '{"command": "python -m pytest"}  (or {} to auto-detect)',
        "perm_key": "shell_commands",
        "describe": lambda a: ("Run tests", str(a.get("command", "") or "(auto-detected)"),
                                "Execute the project's test suite."),
    },
    "inspect_project": {
        "run": _tool_inspect_project,
        "desc": "Inspect the active workspace/project: layout, folders, files, manifests (package.json / pyproject.toml / ...). Use this to ground yourself before acting.",
        "args": '{"path": "."}  (omit for the workspace root)',
        "describe": lambda a: ("Inspect project", str(a.get("path", "") or "."),
                                "Survey the project layout and manifests."),
    },
    "run_terminal": {
        "run": _tool_run_terminal,
        "desc": "Run a terminal command on the user's machine in the active "
                "workspace folder (e.g. 'python main.py', 'pip install ...'). "
                "The user sees the command, its output, and the exit code.",
        "args": '{"command": "python main.py", "reason": "Run the generated script."}',
        "perm_key": "shell_commands",
        "describe": lambda a: ("Run terminal command", str(a.get("command", "")),
                                str(a.get("reason") or "Execute requested terminal command.")),
    },
    "install_packages": {
        "run": _tool_install_packages,
        "desc": "Install real packages with the Autonomous Package Manager "
                "(pip/npm/cargo/brew/winget...). Governed by the active "
                "permission mode: asks in Ask-Each-Time, automatic in Full "
                "Access, refused in Restricted. Unknown packages are "
                "researched first.",
        "args": '{"packages": "requests"}  or {"packages": ["numpy", "pandas"]}',
        "perm_key": "install_packages",
        "describe": lambda a: ("Install package(s)", str(a.get("packages", a.get("package", ""))),
                                "Install the requested package(s)."),
    },
    "device_action": {
        "run": _tool_device_action,
        "desc": "Automate full computer (desktop apps, PowerShell, keystrokes, screenshot) or external devices (Android via adb, Browser navigation, in-app simulations).",
        "args": '{"provider": "desktop", "action": "run_powershell", "target": "Get-Process"}  (providers: desktop, android, browser, terminal, simulation)',
        "perm_key": "device_control",
        "describe": lambda a: (f"Device action: {a.get('provider', '?')}/{a.get('action', '?')}",
                                str(a.get("target", "") or a.get("command", "")),
                                "Automate full computer or connected device (approved)."),
    },
}

_TOOL_DOCS = "\n".join(f"- {name}({spec['args']}) \u2014 {spec['desc']}" for name, spec in TOOLS.items())

_PROTOCOL = f"""Reply with EXACTLY ONE JSON object per turn and nothing else (no markdown fences, no
commentary outside the JSON). The "action" field must be literally the
string "tool" or "final" — NEVER the tool's name itself — and every tool
argument MUST be nested inside "args", never placed at the top level:
  To use a tool:  {{"action": "tool", "tool": "<name>", "args": {{...}}, "thought": "<why>"}}
  To finish:      {{"action": "final", "text": "<answer for the user>"}}

Correct example for the calculate tool:
  {{"action": "tool", "tool": "calculate", "args": {{"expression": "2+2"}}, "thought": "..."}}
The following format is also understood, but the above is preferred:
  {{"action": "calculate", "expression": "2+2", "thought": "..."}}

Available tools:
{_TOOL_DOCS}

Rules:
- ACT, DON'T DESCRIBE. When the user asks for an operation you have a tool
  for (create/edit/delete/move files, run commands, install packages,
  inspect or modify archives, build, test), EXECUTE it with the tools.
  NEVER reply with a tutorial, a list of commands for the user to run, or a
  description of what you "would do" — you are the executor. Never emit
  fake tool-call markup (<invoke>, <parameter>, ...) as prose: real calls
  happen only through this JSON protocol, and CCT executes them for real.
- NEVER claim a file was created/edited/deleted unless a tool result in
  this conversation confirms it. Only the TOOL RESULT lines count as proof.
- INSPECT FIRST. Before touching anything, ground yourself: inspect_project
  and/or list_directory for workspace tasks; read_attachment / archive_list
  for attached files. Use the REAL paths from those results.
- ASK ONLY WHEN TRULY AMBIGUOUS. If exactly one file is attached, that IS
  the file the user means. If there is one active workspace, that IS the
  project. Do not ask "which file?" or "which project?" when context already
  answers it — pick the obvious target, act, and say what you chose.
- FILE CREATION POLICY — EXPLICIT_ONLY (STRICT v0.7.9.6). Never create a
  permanent file or directory inside a user-provided workspace/project path
  unless the user explicitly requested that file/directory OR the requested
  operation necessarily and unavoidably requires that exact file. A path
  argument means "work with the existing location and its existing contents"
  — NOT "populate it with a template". Do NOT automatically scaffold default
  folders (calculations, graphs, images, projects, reports, research,
  scripts, simulations) or placeholder/README/analysis/report files. Do NOT
  invent a project structure. Existing projects must remain structurally
  unchanged unless the task explicitly requires a change. Suggestions may be
  offered in chat, but no filesystem change occurs without explicit
  authorization. Temporary artifacts belong in the system temp directory.
- After modifying an archive, always archive_validate before reporting done.
- Prefer a tool over guessing whenever something can be computed, plotted,
  simulated, built, or tested exactly. Never invent a numeric result a tool
  could produce.
- You may call several tools across turns (one step per turn) before
  finishing. Keep going until the task is genuinely complete — inspect,
  change, verify, fix errors from real output, retry — then return "final".
- If a question requires a formula you don't have in your library, derive it
  or formulate it from first principles and use `solve_custom`.
- Always end with a "final" action summarizing what you actually did, with
  concrete results (paths, sizes, exit codes).
- If the request needs no tool (pure explanation/definition), return "final"
  immediately.
- Never give up on a hard problem — break it into a chain of small tool
  calls (one intermediate quantity per call) and keep going across turns.
- If a sub-question genuinely cannot be pinned to an exact tool result,
  reason it out yourself and state the assumption plainly, but still give a
  concrete final answer for every part of the question that was asked.
"""

AGENT_SYSTEM_PROMPT = f"""You are CAT Agent, the autonomous operator and high-agency AI agent inside CAT
(Coding Agent Terminal): a first-principles thinker, deep reasoner, AND hands-on executor.
Our default AI modes are already fully capable AI agents: you have full authority to automate
the entire laptop, computer, operating system, and CAT CLI workflows end-to-end.

Unlike a passive chatbot, you directly OPERATE real tools:
- **Full Laptop & CLI Automation**: Run shell and PowerShell terminal commands (`run_terminal`),
  automate processes, execute scripts, and control developer workflows.
- **Deep Code & Workspace Authority**: Create, edit, rewrite, move, and delete real files,
  inspect directory layouts (`inspect_project`, `list_directory`), and read attachments.
- **Autonomous Build & Quality**: Build projects, run test suites (`run_tests`), and manage
  packages (`install_packages` with pip/npm/cargo/winget/brew).
- **DeepSearch & Research**: Conduct live multi-query web search, documentation analysis,
  and synthesis with real citations (`web_search`, `deep_research`).
- **Exact Scientific & Symbolic Tools**: Solve exact formulas symbolically, run the safe calculator,
  plot 2D/3D functions, and drive live simulations.

**GROK-GRADE THINK MODE & FIRST-PRINCIPLES REASONING**:
- **Think Before Acting**: Engage in step-by-step chain-of-thought (CoT) internal reasoning.
  Deconstruct problems to fundamental truths, state your hypotheses, check syntax, audit edge
  cases, and consider potential failure modes before touching files or running destructive commands.
- **Inspect First & Ground Yourself**: Never guess file paths or structures. Use `inspect_project`
  or `list_directory` to understand the workspace before editing. When the user asks how to see, view, or test
  a project (e.g. portfolio, web application), inspect the project files first, start its dev server
  via `run_terminal` (which automatically detects the live URL and returns it immediately), and provide the URL.
- **Autonomous Self-Correction**: When a terminal command, script, or test returns an error or non-zero
  exit code, do not give up or ask the user to fix it — inspect the stderr output, diagnose the root
  cause with first principles, patch the bug, and re-verify until it succeeds.
- **Direct & High-Signal**: Be direct, witty, and intellectually honest. Avoid sycophantic corporate
  filler and fluff. Deliver production-grade, rock-solid solutions.

{_PROTOCOL}
- When the user's message contains several distinct questions (e.g. "(a)
  ... (b) ... (c) ..." or multiple sentences each asking for a value),
  solve every one of them before returning "final", and structure the
  final text so each part's answer is clearly labeled.

**HOW TO WRITE YOUR "final" TEXT — NOTEBOOK FORMAT, ALWAYS LONGER AND
THOROUGH** (this is your signature style, distinct from the quick, casual
CCT AI chat mode):
- Never answer in one bare line. Explain fully, the way a careful teacher
  writing out a notebook page would, even if the user's question was short.
- Structure the answer with short, ALL-CAPS section headers on their own
  line (no markdown symbols needed, plain text is fine), each followed by
  one or more lines of explanation:
  * For a numerical/calculation question use headers in this order:
    GIVEN DATA, FIND, FORMULA, SUBSTITUTION, CALCULATION, VERIFICATION,
    FINAL ANSWER.
  * For a conceptual/definition/"explain X" question use: OVERVIEW,
    EXPLANATION, EXAMPLE, KEY POINTS, FINAL ANSWER (a one-line takeaway).
  * For a plot/simulation request, describe what was rendered under
    OVERVIEW / WHAT WAS RUN / OBSERVATIONS / FINAL ANSWER.
  * For a build/file/archive task use: WHAT WAS FOUND, WHAT WAS DONE,
    VERIFICATION, FINAL ANSWER — with real paths and real results.
- Under CALCULATION or EXPLANATION, use several short lines/steps rather
  than one dense paragraph — one idea per line, numbered where it helps.
- Always finish with a FINAL ANSWER section giving the concrete result or
  one-sentence takeaway.
- Whenever you created or changed files this turn (write_file /
  create_folder / delete_file / rename_file / edit_file / archive_* /
  run_terminal), end your reply with a short "Why?" section of 2-5 bullet
  lines ("• ...") explaining what you changed and why. The app appends the
  exact diff separately, so keep this to the reasons, not the code itself.

{identity.IDENTITY_BLOCK}
"""

AI_SYSTEM_PROMPT = f"""You are CCT AI, the friendly quick-chat assistant embedded inside the Chemistry
Calc Terminal (CCT). You share the same real tools as CCT Agent — solve,
plot, simulate, AND create/edit/delete real files, inspect and modify
archives, run commands, build, test, install packages. Use them whenever an
exact number/plot/real action is needed; never guess a computable result and
never merely describe an operation you could just perform.

{_PROTOCOL}

**HOW TO WRITE YOUR "final" TEXT — TALK NORMAL, KEEP IT SHORT:**
- You are a conversation, not a notebook. Answer the way a knowledgeable
  friend would text back: a few natural sentences, plain language, no
  ALL-CAPS section headers, no forced GIVEN/FIND/FORMULA structure.
- Give the key number or idea straight away, then one or two sentences of
  context if useful. Skip filler and long preambles.
- It's fine to run tools and report the result conversationally, e.g.
  "That works out to k = 4.6e-3 s^-1 — nearly first order here."
- If the question is genuinely huge (a long multi-part numerical, a full
  derivation, "explain in detail/step by step", several sub-questions at
  once), you may still solve it with tools, but keep your reply here brief
  (the headline results, plainly stated) rather than writing the whole
  notebook out — the app will separately point the user to `/agent` for
  the complete step-by-step notebook version, so you don't need to.
- Whenever you created or changed files this turn (write_file /
  create_folder / delete_file / rename_file / edit_file / archive_* /
  run_terminal), end your reply with a short "Why?" section of 2-5 bullet
  lines ("• ...") explaining what you changed and why. The app appends the
  exact diff separately, so keep this to the reasons, not the code itself.

{identity.IDENTITY_BLOCK}
"""

RESEARCH_SYSTEM_PROMPT = f"""You are CAT Research AI, the deep-research, web-investigation, and technical synthesis agent inside CAT.
You have real tools to search the live web (`web_search`), fetch and read website pages and online documentation (`fetch_web_page`), conduct multi-angle synthesis (`deep_research`), automate terminal/cli workflows (`run_terminal`), read files, and write reports.

Always actively use your tools:
- When asked to search, research, verify, look up recent information, or check websites: use `web_search` and `fetch_web_page` to retrieve fresh, factual data.
- When URLs are mentioned or returned in search results, use `fetch_web_page` to read the full page content.
- Synthesize your findings clearly, providing real citations and URLs.
- If running commands or checking environments is needed, use `run_terminal`.

{_PROTOCOL}

**HOW TO WRITE YOUR "final" TEXT — THOROUGH, FACTUAL, CITED RESEARCH REPORT:**
- Structure your response with clear sections: EXECUTIVE SUMMARY, DETAILED FINDINGS, VERIFIED SOURCES, and NEXT STEPS.
- Always include the concrete URLs and references you discovered during your web search and page fetches.
- Never guess or extrapolate unsupported claims when a live search can verify them.

{identity.IDENTITY_BLOCK}
"""

BUILD_SYSTEM_PROMPT = f"""You are CAT Build, the premier autonomous software engineering, architecture, and system automation agent inside CAT (Coding Agent Terminal).
You have full capability and authority to automate the terminal, file systems, codebases, full computer, operating system, and connected devices:
- **Full Terminal & Shell Automation**: Run shell and PowerShell terminal commands (`run_terminal`), build projects (`run_build`), execute tests (`run_tests`), and install packages (`install_packages`).
- **Complete File & Directory Automation**: Create, write, edit, rewrite, move, and delete real files and folders (`read_file`, `write_file`, `edit_file`, `create_folder`, `delete_file`, `rename_file`, `list_directory`, `search_workspace`).
- **Full Computer & Device Automation**: Automate the host computer and connected devices (`device_action`: desktop automation, run PowerShell system scripts, launch applications, capture screenshots, automate Android phones/tablets via adb, and automate web browsers).
- **Autonomous Project Creation & Scaffolding**: Build production-ready, clean, modern code, scaffold projects (e.g. Vite, React, Next.js, Python, Rust, Go), configure dependencies, and verify everything works.
- **Inspect First & Ground Yourself**: Use `inspect_project` and `list_directory` before acting to inspect existing project structure. When the user asks how to see, view, or test a project (e.g. portfolio, web app), inspect its manifests (package.json) first, run its dev server via `run_terminal` (which auto-detects the local URL without hanging), and provide the localhost URL to the user.
- **Self-Correction**: When a command or test returns an error or non-zero exit code, diagnose the root cause, fix the issue, and re-run to verify.

{_PROTOCOL}

**HOW TO WRITE YOUR "final" TEXT — PRODUCTION ENGINEERING SUMMARY:**
- Summarize what you engineered, built, and automated with exact paths, files created, commands executed, and verified results.
- If you created or modified files, list them clearly with the reasons for each change.
- Provide instructions for how the user can run, test, or preview their project.

{identity.IDENTITY_BLOCK}
"""

PLAN_SYSTEM_PROMPT = f"""You are CAT Plan, the strategic planning, system architecture, and roadmap agent in CAT.
You deconstruct complex goals into clear, actionable milestones, architectural specifications, and implementation roadmaps.
You have access to all tools to inspect workspaces, research technologies, automate terminal, files, and plan execution steps.

{_PROTOCOL}

{identity.IDENTITY_BLOCK}
"""

DEBUGGER_SYSTEM_PROMPT = f"""You are CAT Debugger, the root-cause diagnosis, crash investigation, and surgical fix agent in CAT.
You analyze error logs, stack traces, reproduce issues, inspect code, and fix bugs directly using tools (`run_terminal`, `edit_file`, `run_tests`, `device_action`).

{_PROTOCOL}

{identity.IDENTITY_BLOCK}
"""

# Backward-compatible alias — existing code/imports that referenced the old
# single SYSTEM_PROMPT constant keep working (defaults to the Agent style).
SYSTEM_PROMPT = AGENT_SYSTEM_PROMPT


# --------------------------------------------------------- memory helpers --
def _guess_topic(text):
    """Cheap keyword-based topic label for the memory 'topics you ask about
    most' counter — good enough to power recall, no NLP needed."""
    t = (text or "").lower()
    keywords = [
        "first order", "second order", "third order", "zero order", "half life",
        "half-life", "arrhenius", "activation energy", "mole concept", "molar mass",
        "molarity", "nernst", "faraday", "electrochemistry", "ideal gas", "boyle",
        "orbital", "atomsim", "bohr", "titration", "equilibrium", "thermodynamics",
        "kinetics", "redox", "stoichiometry", "ph", "buffer",
    ]
    for k in keywords:
        if k in t:
            return k
    words = [w.strip(".,?!") for w in t.split() if len(w.strip(".,?!")) >= 5]
    return words[0] if words else None


_LONG_ANSWER_HINTS = re.compile(
    r"\bstep[- ]?by[- ]?step\b|\bderiv(e|ation)\b|\bexplain in detail\b|\bfull solution\b|"
    r"\bdetailed\b|\bin depth\b|\(a\)|\(b\)|\(c\)|\bevery part\b|\bmulti.?step\b|\blong answer\b",
    re.IGNORECASE,
)


def _looks_like_long_answer(user_text, final_text, steps):
    """Heuristic used by the CCT AI (chat) mode to decide whether to nudge
    the user toward /agent for the full notebook-style breakdown, instead
    of the short conversational answer /ai just gave."""
    if steps and len(steps) >= 3:
        return True
    if final_text and len(final_text) > 600:
        return True
    if user_text and _LONG_ANSWER_HINTS.search(user_text):
        return True
    return False


def _extract_json(text):
    if not text:
        return None
    text = text.strip()
    # Strip DeepSeek-R1 / Qwen reasoning thought blocks before parsing JSON
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r">\s*\*Thinking:\*.*?(?=\n\n|\Z)", "", text, flags=re.DOTALL)
    # Strip common markdown code-fence wrapping some models add anyway.
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        start_idx = text.find("{")
        if start_idx != -1:
            try:
                from .tool_call_normalizer import _repair_json_str
                repaired = _repair_json_str(text[start_idx:])
                if repaired:
                    return repaired
            except Exception:
                pass
        return None
    candidate = m.group(0)
    try:
        return json.loads(candidate, strict=False)
    except Exception:
        # String-aware balanced JSON scanning and truncated recovery
        start = candidate.find("{")
        if start != -1:
            depth = 0
            in_str = False
            escape = False
            for i in range(start, len(candidate)):
                ch = candidate[i]
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == '"':
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(candidate[start : i + 1], strict=False)
                        except Exception:
                            pass
            try:
                from .tool_call_normalizer import _repair_json_str
                return _repair_json_str(candidate[start:])
            except Exception:
                return None
        return None


def _build_prompt(convo):
    lines = []
    for turn in convo:
        lines.append(f"{turn['role'].upper()}: {turn['text']}")
    lines.append("ASSISTANT:")
    return "\n\n".join(lines)


def _normalize_action(action):
    """Coerce the model's parsed JSON into the strict
    {"action": "tool"/"final", "tool": ..., "args": {...}} shape.

    Models frequently drift from the exact protocol while still meaning
    the same thing — e.g. putting the tool name directly in "action"
    instead of wrapping it (`{"action": "calculate", "expression": ...}`
    instead of `{"action": "tool", "tool": "calculate", "args": {...}}`),
    or using a top-level "tool" key with no "action" at all, or leaving
    tool arguments unwrapped at the top level instead of nesting them
    under "args". Previously any of these caused the whole JSON blob to
    be dumped to the user verbatim as if it were the final answer,
    which looked like the agent "not solving anything" (this was the
    root cause of the reported bug). Accepting these common variants
    makes the agent robust to how a given provider/model actually talks,
    instead of requiring byte-perfect formatting.
    """
    if not isinstance(action, dict):
        return None

    # NEW: Check for implicit tool call where a tool name is a key.
    # e.g. {"solve_custom": {"formula": "...", "values": ...}, "thought": "..."}
    tool_keys = [k for k in action.keys() if k in TOOLS]
    if len(tool_keys) == 1 and "action" not in action and "tool" not in action:
        tool_name = tool_keys[0]
        tool_args = action[tool_name]
        if isinstance(tool_args, dict):
            return {
                "action": "tool",
                "tool": tool_name,
                "args": tool_args,
                "thought": action.get("thought") or "Corrected from implicit tool call format."
            }

    act = action.get("action")
    reserved = {"action", "tool", "args", "thought"}

    # Canonical shape already — nothing to do.
    if act == "final" or act == "tool":
        return action

    # {"tool": "calculate", "args": {...}, ...} with no "action" key.
    if act is None and isinstance(action.get("tool"), str) and action["tool"] in TOOLS:
        args = action.get("args")
        if not isinstance(args, dict):
            args = {k: v for k, v in action.items() if k not in reserved}
        return {"action": "tool", "tool": action["tool"], "args": args,
                "thought": action.get("thought")}

    # {"action": "calculate", "expression": ..., "thought": ...} — the
    # tool name was put straight into "action" and its arguments left
    # at the top level instead of nested under "args". This is exactly
    # the shape shown in the bug report screenshots.
    if isinstance(act, str) and act in TOOLS:
        args = action.get("args")
        if not isinstance(args, dict):
            args = {k: v for k, v in action.items() if k not in reserved}
        return {"action": "tool", "tool": act, "args": args,
                "thought": action.get("thought")}

    # A bare {"text": "..."} / {"answer": "..."} reply with no "action".
    for key in ("text", "answer", "response", "message"):
        if isinstance(action.get(key), str):
            return {"action": "final", "text": action[key]}

    return action


# v0.7.8 BONUS FIX (Section 4): users must NEVER see the internal tool
# protocol. Models occasionally drift and hand back a JSON action blob
# as if it were the answer — e.g. a raw {"action":"final","text":"..."}
# line, or prose with a JSON object glued onto it. Every path that
# hands text to the user runs through clean_final_text() so only the
# clean payload is ever rendered.


def _balanced_json_spans(text):
    """Yield (start, end) spans of brace-balanced JSON-looking objects
    in `text` (handles nested braces like {"args": {"expression": ..}}).
    Not a full JSON parser — spans are validated with json.loads later."""
    spans = []
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    spans.append((start, i + 1))
                    start = -1
    return spans


def _extract_protocol_text(data):
    """If a parsed dict is a protocol object (has an 'action' key, or is
    just a bare text/answer/response wrapper), return its text payload —
    else None."""
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("action"), str):
        payload = data.get("text") or data.get("answer") \
            or data.get("response") or data.get("message")
        return payload if isinstance(payload, str) else None
    for key in ("text", "answer", "response", "message"):
        if isinstance(data.get(key), str):
            return data[key]
    return None


def _is_protocol_blob(data):
    """True when a parsed dict is internal tool protocol (carries an
    'action' key) rather than ordinary quoted JSON the user wrote."""
    return isinstance(data, dict) and isinstance(data.get("action"), str)


def clean_final_text(text):
    """Parse any leaked tool-protocol JSON/XML out of `text` and return
    only the clean user-facing content. Pure function, never raises.

    Handles four shapes:
      1. The whole reply is one JSON object (optionally fence-wrapped)
         with a "text"/"answer"/"response" payload  -> returns payload.
      2. A JSON protocol object is glued before/after real prose
         (e.g. a tool echo)                          -> strips the blob.
      3. XML-like tool call tags (<minimax:toolcall>, <invoke>, etc.)
         are stripped from displayed text.
      4. Plain prose (no JSON/XML)                   -> returned unchanged.
    """
    if not text or not isinstance(text, str):
        return text or ""
    stripped = text.strip()
    if not stripped:
        return ""

    # Shape 1: whole-reply JSON with a text payload (also fence-wrapped).
    m = re.search(r"\{.*\}", stripped, re.S)
    if m and len(m.group(0).replace(" ", "")) >= len(stripped.replace(" ", "")) * 0.7:
        try:
            data = json.loads(m.group(0))
            payload = _extract_protocol_text(data)
            if payload and payload.strip():
                return payload.strip()
        except Exception:
            pass

    # Shape 2: strip protocol blobs wherever they're embedded, keep prose.
    out = []
    cursor = 0
    changed = False
    for start, end in _balanced_json_spans(text):
        chunk = text[start:end]
        try:
            data = json.loads(chunk)
        except Exception:
            continue
        if not _is_protocol_blob(data):
            continue
        out.append(text[cursor:start])
        cursor = end
        changed = True
    if changed:
        out.append(text[cursor:])
        cleaned = "".join(out)
        cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        text = cleaned or text.strip()

    # v0.8.0: Strip XML-like tool call tags that some providers emit
    # (e.g. <minimax:toolcall><invoke name="...">...</invoke></minimax:toolcall>)
    # These are internal protocol and must never reach the user.
    text = strip_tool_markup(text)
    # Strip <think>...</think> from final output if prose follows
    if "<think>" in text and "</think>" in text:
        post_think = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        if post_think:
            text = post_think
    # Clean up any leftover empty lines from removed tags
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


# Compiled regex patterns for streaming chunk sanitization (shared,
# avoids recompilation on every chunk).
_XML_TOOLCALL_RE = re.compile(
    r"<(?:minimax|anthropic|openai|gemini|provider)?\s*:?\s*toolcall\s*>"
    r".*?"
    r"</(?:minimax|anthropic|openai|gemini|provider)?\s*:?\s*toolcall\s*>",
    re.DOTALL | re.IGNORECASE,
)
_XML_INVOKE_RE = re.compile(
    r"<invoke\s+[^>]*>.*?</invoke>", re.DOTALL | re.IGNORECASE
)
_XML_BARE_INVOKE_RE = re.compile(
    r"<invoke\s+[^>]*>.*", re.DOTALL | re.IGNORECASE  # unclosed <invoke> — strip to EOF
)
_XML_PARAM_RE = re.compile(r"<parameter\s+[^>]*>.*?</parameter>", re.DOTALL | re.IGNORECASE)
_XML_TOOLCALL_TAG_RE = re.compile(
    r"</?tool_call>", re.IGNORECASE
)
_XML_TOOLCALL_BLOCK_RE = re.compile(
    r"<tool_call>.*?</tool_call>", re.DOTALL | re.IGNORECASE  # full block incl. contents
)
_XML_NAME_ARGS_RE = re.compile(
    r"<name>[^<]*</name>\s*<arguments>.*?</arguments>", re.DOTALL | re.IGNORECASE
)
_XML_FUNCTION_RE = re.compile(
    r"<function=\w+>.*?</function>|<function_calls>.*?</function_calls>",
    re.DOTALL | re.IGNORECASE,
)
_JSON_PROTOCOL_RE = re.compile(r"\{[^{}]*\"action\"\s*:\s*\"(?:tool|final)\"[^{}]*\}", re.DOTALL)


def strip_tool_markup(text):
    """Remove EVERY form of internal tool-call protocol from `text`
    (requirement #23/#24): wrapped and bare <invoke> blocks (including an
    unclosed trailing <invoke>), <parameter ...> blocks, <tool_call>
    wrappers, <function=...>/<function_calls> blocks, minimax-style
    toolcall envelopes, and JSON action blobs. Used by clean_final_text,
    the clipboard copy path, and history/export so raw protocol never
    leaves the app."""
    if not text or not isinstance(text, str):
        return text or ""
    text = _XML_TOOLCALL_RE.sub("", text)
    text = _XML_INVOKE_RE.sub("", text)
    text = _XML_BARE_INVOKE_RE.sub("", text) if "<invoke" in text.lower() else text
    text = _XML_PARAM_RE.sub("", text)
    text = _XML_TOOLCALL_BLOCK_RE.sub("", text)
    text = _XML_NAME_ARGS_RE.sub("", text)
    text = _XML_TOOLCALL_TAG_RE.sub("", text)
    text = _XML_FUNCTION_RE.sub("", text)
    # a leftover JSON protocol blob on its own line(s)
    text = _JSON_PROTOCOL_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def sanitize_stream_chunk(chunk):
    """Strip internal tool-call protocol from a single streaming chunk.

    During streaming, models may emit XML-like tool call tags or
    JSON protocol objects token-by-token. This function removes them
    so the user never sees raw protocol markup. Returns the cleaned
    chunk, or an empty string if the entire chunk was protocol.

    This is a lightweight per-chunk filter — the full clean_final_text()
    is still applied to the assembled complete response.
    """
    if not chunk or not isinstance(chunk, str):
        return chunk or ""
    chunk = _XML_TOOLCALL_RE.sub("", chunk)
    if "<invoke" in chunk.lower():
        # a partial <invoke> in one chunk can't be matched by the closed
        # pattern; drop from the tag onward — clean_final_text re-runs on
        # the assembled text as the final authority.
        idx = chunk.lower().find("<invoke")
        chunk = chunk[:idx]
    chunk = _XML_PARAM_RE.sub("", chunk)
    chunk = _XML_TOOLCALL_TAG_RE.sub("", chunk)
    chunk = _XML_FUNCTION_RE.sub("", chunk)
    chunk = _JSON_PROTOCOL_RE.sub("", chunk)
    return chunk


def _remember_turn(user_text, final_text, steps, mode):
    """Best-effort: log this exchange + 'every movement' into persistent
    memory so both /ai and /agent recall it (and each other's turns, plus
    facts/topics/activity) on the next question or the next session.
    Never allowed to raise — memory is a nice-to-have, not a dependency.

    v0.7.9.0: per-tool-step activity lines are written in ONE batched
    save instead of one full-file rewrite per step, and the layered
    memory uses the process-wide singleton manager (no re-init per turn).
    """
    try:
        t0 = time.perf_counter()
        activity = [("ai_question" if mode == "ai" else "agent_question",
                     user_text.strip().replace("\n", " ")[:120])]
        activity.extend(
            ("tool:" + name,
             f"ran {name} \u2014 {json.dumps(args, default=str)[:100]}")
            for name, args, _obs, _change in steps)
        memory.add_turn("user", user_text, mode=mode)
        memory.add_turn("assistant", final_text, mode=mode)
        memory.bump_topic(_guess_topic(user_text))
        fact = memory.maybe_extract_fact(user_text)
        if fact:
            memory.add_fact(fact)
        memory.add_activities(activity)
        try:
            from . import metrics
            m = metrics.current()
            if m is not None:
                m.mark_stage("memory_retrieval", t0)
        except Exception:
            pass
    except Exception:
        pass
    # v0.8.0: Also persist to the new layered memory system
    try:
        from . import memory_v2
        mm = memory_v2.get_manager()
        mm.add_session_turn("user", user_text, mode=mode)
        mm.add_session_turn("assistant", final_text, mode=mode)
        # Emit event for the event stream
        try:
            from .event_stream import stream, AGENT_COMPLETED
            stream.emit(AGENT_COMPLETED, source="agent",
                        user_text=user_text[:200], steps_count=len(steps), mode=mode)
        except Exception:
            pass
    except Exception:
        pass


def _cli_permission_prompt(key, action_label, path, reason):
    """Default permission prompt for every run_agent() caller that
    doesn't hand it a UI-specific callback (i.e. the classic REPL and
    /agent command in calc_terminal/app.py) — same card shape/colors as
    code_editor.py's _scan_and_confirm, so a mutating tool call looks
    like every other permission moment in the app instead of a special
    case. Blocks on a real input(), which is safe here because every
    caller that can't afford to block (the Textual UI's threaded
    worker) is required to pass its own non-blocking-from-the-UI's-
    perspective callback instead — see ui/app.py's
    _tool_permission_callback.
    """
    restricted = perm.manager.restricted_review(key)
    title = "Suggested action \u2014 review required" if restricted else "Permission required"
    lines = [theme.orange(title, bold=True)]
    lines.append(theme.orange("ACTION", bold=True) + f"  {action_label}")
    if path:
        lines.append(theme.orange("PATH", bold=True) + f"    {path}")
    lines.append(theme.orange("REASON", bold=True) + f"  {reason}")
    lines.append("")
    if restricted:
        lines.append(theme.dim("  [Enter] Accept   [n] Reject"))
    else:
        lines.append(theme.dim("  [Enter] Allow once   [a] Always allow   [n] Deny"))
    print()
    print(theme.panel(lines, title="permission", color=theme.ORANGE))
    choice = input(theme.dim("  \u25b8 ")).strip().lower()
    if choice == "n":
        return "deny"
    if choice == "a" and not restricted:
        return "always_allow"
    return "allow_once"


def _check_permission(name, args, permission_callback):
    """Returns (proceed: bool, observation_or_None). Looks up the
    tool's perm_key/describe metadata, asks perm.manager whether this
    call needs a prompt under the current mode, and if so resolves it
    via permission_callback (or the CLI default above) before ever
    calling the tool's real run() function.

    v0.7.7 spec section 3: package installs ALWAYS prompt, even in Full
    Access (the mode is temporarily narrowed to Ask Every Time for the
    duration of the install and restored afterwards — see
    permissions.install_flow_state / restore_mode, applied here for the
    agent-tool entry point, and in the app.py / ui/app.py install flows
    for the direct-entry point)."""
    spec = TOOLS[name]
    perm_key = spec.get("perm_key")
    if not perm_key:
        return True, None
    _trace("PERMISSION_CHECK", tool=name, key=perm_key,
           mode=perm.manager.mode)

    if perm_key == "install_packages":
        from . import packages as _pkgs
        from . import permissions as _perm
        flow = _perm.install_flow_state()
        if not flow["allow"]:
            _trace("PERMISSION_RESULT", tool=name, allowed=False,
                   reason="restricted mode")
            return False, ("Permission denied: Restricted mode — package "
                           "installs are disabled, nothing was installed.")
        raw = str(args.get("packages") or args.get("package") or "").strip()
        if "," in raw:
            raw = raw.split(",")[0].strip()
        req, _mgr = _pkgs.resolve_request(raw or "package")
        remembered = _pkgs.remembered_decision(req.manager, req.name) if req and req.manager else None
        if remembered == "deny":
            return False, (f"Install of {req.name} was previously denied (remembered "
                           f"choice) — nothing installed.")
        if remembered == "allow":
            return True, None  # user permanently approved this exact package+manager
        if perm.manager.refused_by_always_deny(perm_key):
            return False, "Blocked by permission setting — previously denied for this session."
        needs = perm.manager.needs_prompt(perm_key)
    elif perm_key == "ask_question":
        describe = spec.get("describe")
        if describe:
            action_label, path, reason = describe(args)
        else:
            action_label, path, reason = "Ask Question", "", str(args.get("question", ""))
        callback = permission_callback or _cli_permission_prompt
        try:
            decision = callback(perm_key, action_label, path, reason, options=args.get("options"))
        except TypeError:
            decision = callback(perm_key, action_label, path, reason)
        return True, f"User answered: {decision}"
    else:
        if perm.manager.refused_by_always_deny(perm_key):
            return False, "Blocked by permission setting — previously denied for this session."
        needs = perm.manager.needs_prompt(perm_key)
    if not needs:
        return True, None
    describe = spec.get("describe")
    if describe:
        action_label, path, reason = describe(args)
    else:
        action_label, path, reason = name, str(args.get("path", "")), "Requested by the AI."
    callback = permission_callback or _cli_permission_prompt
    try:
        decision = callback(perm_key, action_label, path, reason, options=args.get("options"))
    except TypeError:
        decision = callback(perm_key, action_label, path, reason)
    proceed = perm.manager.decide(perm_key, decision, action_label, reason)
    if proceed:
        return True, None
    verb = "Rejected" if perm.manager.restricted_review(perm_key) else "Denied"
    return False, (f"{verb} by the user \u2014 did not {action_label.lower()}. "
                    f"Do not retry this exact action; tell the user it was declined "
                    f"and continue only if there's another way to help.")


def _trace(event, **kw):
    """Requirement #29 diagnostic trace. Writes one structured line per
    pipeline stage (MODEL_RESPONSE / TOOL_DETECTED / TOOL_PARSED /
    PERMISSION_CHECK / PERMISSION_RESULT / TOOL_STARTED / TOOL_FINISHED /
    TOOL_FAILED / MODEL_CONTINUED) to stderr — never to the chat — so a
    broken model→tool→execution handoff is immediately visible in dev
    (`textual run --dev`, or any console run) without touching the UI."""
    try:
        import sys as _sys
        parts = [f"[CAT:AGENT] {event}"]
        for k, v in kw.items():
            v = str(v).replace("\n", "\\n")
            if len(v) > 160:
                v = v[:157] + "..."
            parts.append(f"{k}={v}")
        line = " | ".join(parts)
        # Legacy-console safe: never let diagnostics crash the pipeline.
        try:
            print(line, file=_sys.stderr)
        except UnicodeEncodeError:
            print(line.encode("ascii", "replace").decode(), file=_sys.stderr)
    except Exception:
        pass


def run_agent(user_text, max_steps=MAX_STEPS, verbose=True, on_step=None, mode="agent",
              permission_callback=None, should_cancel=None, on_tool_result=None,
              fast=False, memory_query=None, turn_id="", history=None):
    """Run the agent loop for one user request.

    `mode` selects the persona/voice: "agent" (CCT Agent — long, thorough,
    notebook-formatted answers) or "ai" (CCT AI — short, conversational
    chat). Both share the exact same tools and memory.

    v0.7.8.1: `should_cancel` is an optional zero-arg callable checked
    between loop iterations and before tool dispatch; when it returns
    truthy the loop stops immediately and hands back everything
    computed so far (the caller decides how to mark the interruption —
    the UI appends its own 'interrupted' note).

    v0.7.9.0 (speed requirements): `fast=True` skips memory retrieval and
    other per-turn overhead entirely (simple requests must not pay for
    what they don't use); `memory_query` enables relevance-filtered
    memory injection instead of a fixed recent-window dump. Every model
    call / tool call is counted into metrics.current(), and real agent
    lifecycle events are published to event_stream so the UI shows live,
    truthful activity.

    Returns (final_text, steps, meta) where steps is a list of
    (tool_name, args, observation) tuples that were actually executed, and
    meta is a dict with at least:
      - "mode": the mode this ran in
      - "suggest_agent": True if (in "ai" mode) this looked like a big
        enough question that the user should be pointed to /agent for the
        complete step-by-step notebook version.
    """
    global _CURRENT_AGENT_SHOULD_CANCEL
    _CURRENT_AGENT_SHOULD_CANCEL = should_cancel

    def _cancelled():
        try:
            return bool(should_cancel and should_cancel())
        except Exception:
            return False

    from . import metrics as _metrics
    _mreq = _metrics.current()
    if _mreq is not None:
        _mreq.stage_start("agent_loop")

    def _emit(event_type, **data):
        try:
            from .event_stream import stream as _es
            _es.emit(event_type, source="agent", **data)
        except Exception:
            pass

    if mode == "build":
        system_prompt = BUILD_SYSTEM_PROMPT
    elif mode == "agent":
        system_prompt = AGENT_SYSTEM_PROMPT
    elif mode == "research":
        system_prompt = RESEARCH_SYSTEM_PROMPT
    elif mode == "debugger":
        system_prompt = DEBUGGER_SYSTEM_PROMPT
    elif mode == "plan":
        system_prompt = PLAN_SYSTEM_PROMPT
    else:
        # Default all modes to high-agency AGENT_SYSTEM_PROMPT for full computer, terminal and file automation
        system_prompt = AGENT_SYSTEM_PROMPT
    try:
        # v0.7.8 AI Personalization: the active profile's style
        # directive rides along inside the same system prompt the tool
        # loop already uses — tools, memory and permissions untouched.
        from . import ai_personalization as _ap
        system_prompt = _ap.personalize_system_prompt(system_prompt)
    except Exception:
        pass
    mem_ctx = ""
    # Memory toggle: if user disabled memory, skip all retrieval
    _mem_enabled = True
    try:
        from . import ai_personalization as _ap2
        _mem_enabled = _ap2.is_memory_enabled()
    except Exception:
        pass
    if not fast and _mem_enabled:
        t_mem = time.perf_counter()
        try:
            mem_ctx = memory.context_block(mode=mode, query=memory_query or user_text)
        except Exception:
            mem_ctx = ""
        try:
            from . import memory_v2
            mm = memory_v2.get_manager()
            v2_ctx = mm.context_block(query=memory_query or user_text)
            if v2_ctx:
                mem_ctx = (mem_ctx + "\n\n" + v2_ctx) if mem_ctx else v2_ctx
        except Exception:
            pass
        if _mreq is not None:
            _mreq.mark_stage("memory_retrieval", t_mem)
    if mem_ctx:
        system_prompt = system_prompt + "\n\n" + mem_ctx
    attach_ctx = _attachments_context()
    if attach_ctx:
        system_prompt = system_prompt + "\n\n" + attach_ctx
    # v0.8.0: Inject REAL workspace root and attachment paths so the model
    # never invents /workspace or other fake paths. The model MUST use
    # these real paths in tool arguments.
    try:
        _ws_root = workspace.root_dir()
        _ws_info = (
            f"\n\n## ACTIVE WORKSPACE (use this for all file operations)\n"
            f"Workspace root: {_ws_root}\n"
            f"When calling file tools (read_file, write_file, list_directory, etc.), "
            f"use workspace-relative paths (e.g. 'src/main.py') or the full absolute "
            f"path shown above. NEVER invent paths like '/workspace/...' — that is "
            f"not a real directory on this system.\n"
        )
        _found_files = []
        if os.path.isdir(_ws_root):
            for r, d_list, f_list in os.walk(_ws_root):
                d_list[:] = [d for d in d_list if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".venv", "venv", ".pytest_cache", "dist", "build")]
                for f in f_list:
                    rel_p = os.path.relpath(os.path.join(r, f), _ws_root).replace("\\", "/")
                    _found_files.append(rel_p)
                    if len(_found_files) >= 40:
                        break
                if len(_found_files) >= 40:
                    break
        if _found_files:
            _ws_info += "Existing files in active workspace (use these exact relative paths):\n"
            for fp in _found_files:
                _ws_info += f"  - {fp}\n"

        if _ATTACHMENTS:
            _ws_info += "Attached files (use their REAL paths in tool calls):\n"
            for a in _ATTACHMENTS:
                if hasattr(a, 'path'):
                    _ws_info += f"  - {a.path}\n"
        system_prompt = system_prompt + _ws_info
    except Exception:
        pass

    # Historical cross-chat memory and first conversation origin
    if not fast:
        try:
            from . import chat_store
            _cross_ctx = chat_store.build_cross_chat_memory_context(
                workspace_root=_ws_root if '_ws_root' in locals() else None,
                query=memory_query or user_text,
            )
            if _cross_ctx:
                system_prompt = system_prompt + "\n\n" + _cross_ctx
        except Exception:
            pass

    # Critical Web Application Directive to prevent unpopulated boilerplate
    _web_directive = (
        "\n\n## WEB APPLICATION & PREVIEW DIRECTIVE:\n"
        "- When asked to preview, run, show, or verify a web project or dev server (e.g. Vite, React, Next.js):\n"
        "- You MUST verify that the main application entrypoint (e.g. `src/App.tsx`, `src/App.jsx`, `src/index.html`) "
        "contains the user's actual project components and UI, NOT default template boilerplate (e.g. 'Get started', 'Count is 0')!\n"
        "- If components were created in subdirectories but `App.tsx` has not mounted them, wire them up BEFORE running or previewing the server.\n"
    )
    system_prompt = system_prompt + _web_directive

    convo = []
    if history:
        for h in history:
            if isinstance(h, tuple) and len(h) >= 2:
                r, t = h[0], h[1]
            elif isinstance(h, dict):
                r = h.get("role", "user")
                t = h.get("text") or h.get("content") or ""
            else:
                continue
            if t:
                convo.append({"role": r, "text": t})
        if len(convo) > 12:
            convo = convo[-12:]
    convo.append({"role": "user", "text": user_text})
    steps = []
    last_call = None
    stall_count = 0

    # CAT Resilience: Decoupled Agent Task State
    _agent_state = None
    _task_req = None
    try:
        from .resilience.agent_state import AgentTaskState
        from .resilience.types import TaskRequirements
        _agent_state = AgentTaskState(task_id=turn_id or "", objective=user_text, convo=convo)
        _task_req = TaskRequirements(tools=True, coding=(mode in ("agent", "build")))
    except Exception:
        pass

    # v0.8.0: Emit agent started event
    try:
        from .event_stream import stream, AGENT_STARTED
        stream.emit(AGENT_STARTED, source="agent", user_text=user_text[:200], mode=mode,
                    fast=fast)
    except Exception:
        pass
    try:
        config = aicore.load_config()
        from .event_stream import stream as _es, MODEL_SELECTED
        _es.emit(MODEL_SELECTED, source="agent",
                 provider=config.get("provider"), model=config.get("model"),
                 mode=mode)
    except Exception:
        pass
    _provider_act = None

    def _finish(text):
        if _mreq is not None:
            _mreq.stage_end("agent_loop")
        _remember_turn(user_text, text, steps, mode)
        # ── v0.7.9 Live Activity: finalize turn activities if cancelled ──
        try:
            from . import activity as _act2
            if turn_id:
                if _cancelled():
                    _act2.manager.cancel_turn(turn_id)
                else:
                    for _a in _act2.manager.get_for_turn(turn_id):
                        if _a.status in (_act2.STATUS_WAITING, _act2.STATUS_WAITING_PERMISSION):
                            _act2.manager.update(_a.id, status=_act2.STATUS_CANCELLED, result="Cancelled")
        except Exception:
            pass
        meta = {
            "mode": mode,
            "suggest_agent": mode == "ai" and _looks_like_long_answer(user_text, text, steps),
            "file_changes": summarize_file_changes(steps),
            "model_calls": (_mreq.model_calls if _mreq else 0),
            "tool_calls_executed": len(steps),
        }
        _emit("final_response", mode=mode,
              steps=len(steps), text=text)
        if _mreq is not None:
            try:
                _mreq.finish(response=text, meta=meta)
            except Exception:
                try:
                    _mreq.finish()
                except Exception:
                    pass
        cleaned = clean_final_text(text)
        if not cleaned or not cleaned.strip():
            if steps:
                parts = []
                for name, args, obs, _c in steps:
                    target = (args.get("path") or args.get("command")
                              or args.get("expression") or "")
                    parts.append(f"- {name}({target}): {obs[:200]}")
                cleaned = "Here's what I did:\n" + "\n".join(parts)
            else:
                cleaned = (text or "").strip() or "I processed your request but have no summary to show."
        return cleaned, steps, meta

    def _execute_tool_call(name, args, raw):
        """The ONE place a decided tool call becomes a REAL executed tool
        (requirement #3): permission gate → spec['run'] → observation.
        Returns the observation string fed back to the model."""
        spec = TOOLS.get(name)
        args = args if isinstance(args, dict) else {}

        fingerprint = (name, json.dumps(args, sort_keys=True, default=str))
        nonlocal stall_count, last_call
        repeat = fingerprint == last_call
        stall_count = stall_count + 1 if repeat else 0
        last_call = fingerprint

        if not spec:
            _trace("TOOL_FAILED", tool=name, reason="unknown tool")
            return f"Tool '{name}' does not exist. Valid tools: {', '.join(TOOLS)}"
        if stall_count >= 1:
            return ("You already ran this exact tool call and got a result — repeating it "
                    "won't help. Use that result and move on to the NEXT step, or if every "
                    "part of the question is now answered, reply with the final JSON action.")

        _emit("tool_detected", tool=name, args=args)
        # ── v0.7.9 Live Activity: create RUNNING activity with real canonical metadata ──
        _act_obj = None
        _act_id = None
        _t_tool_start = time.perf_counter()
        try:
            from . import activity as _act
            meta = _act.meta_for_tool(name)
            ttype, taction, ttitle = meta
            category = getattr(meta, "category", _act.CAT_TERMINAL)
            phase = getattr(meta, "phase", _act.PHASE_IMPLEMENTATION)
            # human-readable title with target
            target = (args.get("path") or args.get("query") or args.get("command")
                      or args.get("packages") or args.get("expression") or args.get("preset")
                      or args.get("element") or args.get("orbital") or "")
            if target:
                ttitle = f"{ttitle} — {str(target)[:50]}"
                if name == "search_workspace" and args.get("query"):
                    ttitle = f"Searching for \"{args.get('query')}\""
                elif name == "read_file":
                    ttitle = f"Reading {target}"
                elif name == "write_file":
                    ttitle = f"Writing {target}"
                elif name == "edit_file":
                    ttitle = f"Editing {target}"
                elif name == "delete_file":
                    ttitle = f"Deleting {target}"
                elif name in ("run_terminal", "run_build", "run_tests"):
                    ttitle = f"Running {target[:40]}" if target and target != "(auto-detected)" else ttitle
                elif name == "web_search":
                    ttitle = f"Searching web for \"{args.get('query','')[:30]}\""
                elif name == "fetch_web_page":
                    ttitle = f"Fetching web page {args.get('url','')[:35]}"

            target_path_val = str(args.get("path", "") or args.get("new_path", ""))
            _act_obj = _act.manager.create(
                type=ttype, action=taction, title=ttitle,
                status=_act.STATUS_RUNNING, turn_id=turn_id or "",
                tool=name, file=target_path_val, target_path=target_path_val,
                command=str(args.get("command", "")), details=str(target)[:120],
                category=category, phase=phase, query=str(args.get("query", ""))
            )
            _act_id = _act_obj.id
            try:
                from .workflow_engine import event_bus, ExecutionEvent, EVENT_TOOL_STARTED, STATE_RUNNING
                event_bus.emit(ExecutionEvent(
                    event_id=f"evt-{uuid.uuid4().hex[:8]}",
                    trace_id=turn_id or "",
                    parent_id="",
                    event_type=EVENT_TOOL_STARTED,
                    status=STATE_RUNNING,
                    source="agent.tools",
                    tool=name,
                    description=ttitle,
                    metadata={"args": args}
                ))
            except Exception:
                pass
        except Exception:
            pass

        if verbose:
            # errors='replace': on legacy cp1252 Windows consoles a plain
            # print() of tool args containing emoji/Unicode would raise
            # UnicodeEncodeError INSIDE the agent loop and kill the whole
            # reply (surfaced by the v0.7.9.0 headless E2E probe).
            try:
                print(theme.dim(f"  \u2699 agent \u2192 {name}({args})"))
            except UnicodeEncodeError:
                safe = f"  agent -> {name}({args})".encode("ascii", "replace").decode()
                print(safe)
        if on_step:
            try:
                on_step(name, args)
            except Exception:
                pass
        _trace("TOOL_STARTED", tool=name, args=json.dumps(args, default=str)[:160])

        # permission may become WAITING
        _perm_act_id = None
        try:
            from . import activity as _actp
            _spec = TOOLS.get(name, {})
            _pk = _spec.get("perm_key")
            if _pk and perm.manager.needs_prompt(_pk):
                _perm_act = _actp.manager.create(
                    type=_actp.TYPE_PERMISSION, action="permission",
                    title=f"Permission: {name}",
                    status=_actp.STATUS_WAITING_PERMISSION, turn_id=turn_id or "",
                    tool=name, details=f"Awaiting user decision for {name}",
                    category=_actp.CAT_SYSTEM, phase=_actp.PHASE_IMPLEMENTATION,
                    permission_req={"key": _pk, "tool": name, "args": args}
                )
                _perm_act_id = _perm_act.id
        except Exception:
            pass

        proceed, denial_obs = _check_permission(name, args, permission_callback)
        _trace("PERMISSION_RESULT", tool=name, allowed=proceed)
        # resolve permission waiting activity
        if _perm_act_id:
            try:
                from . import activity as _actp2
                if proceed:
                    _actp2.manager.update(_perm_act_id, status=_actp2.STATUS_COMPLETED, result="Allowed")
                else:
                    _actp2.manager.update(_perm_act_id, status=_actp2.STATUS_FAILED, result="Denied by user")
            except Exception:
                pass
        if not proceed:
            sound.play("error")
            obs = denial_obs
            # update tool activity to failed due permission
            if _act_id:
                try:
                    from . import activity as _act3
                    _act3.manager.update(_act_id, status=_act3.STATUS_FAILED, result="Denied — " + (denial_obs[:80] if denial_obs else "permission denied"))
                except Exception:
                    pass
        else:
            sound.play("tool")
            try:
                from .event_stream import stream as _stream, TOOL_STARTED
                _stream.emit(TOOL_STARTED, source="agent", tool=name, args=args)
            except Exception:
                pass
            try:
                _last_change.clear()
                _t_tool = time.perf_counter()
                obs = spec["run"](args)
                if _mreq is not None:
                    _mreq.count_tool_call()
                    _mreq.mark_stage("tool_execution", _t_tool)
                _trace("TOOL_FINISHED", tool=name,
                       result=(obs or "")[:160].replace("\n", "\\n"))
                # success activity update with full canonical metrics
                if _act_id:
                    try:
                        from . import activity as _act4
                        res = str(obs or "")
                        summary = res.splitlines()[0][:100] if res else "Done"
                        match_cnt = None
                        line_cnt = None
                        diff_sum = ""
                        exit_c = 0
                        if name == "search_workspace" and "matches" in res.lower():
                            import re as _re
                            m = _re.search(r'(\d+)\s*matches', res, _re.I)
                            if m:
                                match_cnt = int(m.group(1))
                                summary = f"{match_cnt} matches"
                            else:
                                match_cnt = len(res.splitlines()) if len(res.splitlines()) > 1 else 1
                                summary = f"{match_cnt} results"
                        elif name == "read_file" and res:
                            lines = res.splitlines()
                            line_cnt = len(lines)
                            summary = f"{line_cnt} lines" if line_cnt > 1 else summary
                        elif name in ("write_file", "edit_file"):
                            summary = "File saved" if ("Wrote" in res or "Edited" in res) else summary
                            diff_sum = summary
                        elif name in ("run_tests", "run_build", "run_terminal"):
                            if "failed" in res.lower():
                                summary = "Failed"
                                exit_c = 1
                            elif "exit code 0" in res.lower() or "success" in res.lower()[:200]:
                                summary = "Passed" if name == "run_tests" else "Succeeded"
                                exit_c = 0
                        dur_ms = int((time.perf_counter() - _t_tool) * 1000)
                        _act4.manager.update(
                            _act_id, status=_act4.STATUS_COMPLETED, result=summary,
                            details=res[:200], duration_ms=dur_ms,
                            stdout=res[:2000], match_count=match_cnt,
                            line_count=line_cnt, diff_summary=diff_sum,
                            exit_code=exit_c
                        )
                        for line in res.splitlines()[:10]:
                            if line.strip():
                                _act4.manager.append_output(_act_id, line[:120])
                        try:
                            from .workflow_engine import event_bus, ExecutionEvent, EVENT_TOOL_COMPLETED, STATE_SUCCEEDED
                            dur_ms = int((time.perf_counter() - _t_tool_start) * 1000)
                            event_bus.emit(ExecutionEvent(
                                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                                trace_id=turn_id or "",
                                parent_id="",
                                event_type=EVENT_TOOL_COMPLETED,
                                status=STATE_SUCCEEDED,
                                source="agent.tools",
                                tool=name,
                                description=f"{name}: {summary}",
                                duration_ms=dur_ms,
                                metadata={"result": summary}
                            ))
                        except Exception:
                            pass
                    except Exception:
                        pass
            except Exception as e:
                obs = f"Tool '{name}' failed with a real error: {e}"
                _trace("TOOL_FAILED", tool=name, error=str(e))
                try:
                    from .event_stream import stream as _stream, TOOL_FINISHED, ERROR
                    _stream.emit(ERROR, source="agent", tool=name, error=str(e)[:200])
                except Exception:
                    pass
                if _act_id:
                    try:
                        from . import activity as _act5
                        dur_ms = int((time.perf_counter() - _t_tool_start) * 1000)
                        _act5.manager.update(
                            _act_id, status=_act5.STATUS_FAILED, result=str(e)[:100],
                            details=str(e)[:200], error=str(e)[:500],
                            duration_ms=dur_ms, stderr=str(e)[:1000],
                            exit_code=1
                        )
                        try:
                            from .workflow_engine import event_bus, ExecutionEvent, EVENT_TOOL_COMPLETED, STATE_FAILED
                            event_bus.emit(ExecutionEvent(
                                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                                trace_id=turn_id or "",
                                parent_id="",
                                event_type=EVENT_TOOL_COMPLETED,
                                status=STATE_FAILED,
                                source="agent.tools",
                                tool=name,
                                description=f"{name} failed: {e}",
                                duration_ms=dur_ms,
                                metadata={"error": str(e)}
                            ))
                        except Exception:
                            pass
                    except Exception:
                        pass
            if on_tool_result:
                try:
                    on_tool_result(name, args, str(obs))
                except Exception:
                    pass
            try:
                from .event_stream import stream as _stream, TOOL_FINISHED
                _stream.emit(TOOL_FINISHED, source="agent",
                             tool=name, args=args, result_preview=str(obs)[:200],
                             has_change=bool(_last_change))
                _stream.emit("tool_result", source="agent",
                             tool=name, args=args, result_preview=str(obs)[:200],
                             has_change=bool(_last_change))
            except Exception:
                pass
            # if tool failed (detected via observation prefix), ensure activity reflects
            if _act_id and obs:
                low = str(obs).lower()
                if low.startswith("could not") or "failed with a real error" in low or "refused:" in low:
                    try:
                        from . import activity as _act6
                        # only override if still running
                        cur = _act6.manager.get(_act_id)
                        if cur and cur.status == _act6.RUNNING:
                            _act6.manager.update(_act_id, status=_act6.FAILED, result=str(obs).splitlines()[0][:100])
                    except Exception:
                        pass
        change = dict(_last_change)
        _last_change.clear()
        steps.append((name, args, obs, change))
        if _agent_state is not None:
            try:
                _agent_state.record_step(name, args, obs, change)
            except Exception:
                pass
        return obs

    for i in range(max_steps):
        if _cancelled():
            return _finish(
                "*(interrupted \u2014 here is everything completed so far)*\n"
                + ("\n".join(f"- {n}: {o}" for n, _, o, _c in steps)
                   if steps else "No tools had run yet."))
        _emit("agent_thinking", step=i + 1, tools_so_far=len(steps))
        prompt = _build_prompt(convo)
        raw = aicore.query_ai(prompt, system_prompt=system_prompt, size_class="large", requirements=_task_req)
        if (not raw or not raw.strip()) and not aicore.is_error_response(raw):
            # A blank response is almost always a transient hiccup, not a
            # real "the model has nothing to say" — retry once before
            # treating it as a hard failure. v0.7.9.0: an ERROR SIGNATURE
            # ("AI not configured", quota exhausted, ...) is NOT transient —
            # retrying it just duplicated a doomed network round trip.
            raw = aicore.query_ai(prompt, system_prompt=system_prompt, size_class="large", requirements=_task_req)
        if not raw or not raw.strip():
            # Still blank after retry — if we have tool steps, summarize
            # them. Otherwise report the failure honestly.
            if steps:
                return _finish(None)
            return _finish("I wasn't able to get a response from the AI provider. "
                           "Please check your connection and try again.")
        _trace("MODEL_RESPONSE", mode=mode, step=i + 1,
               text=(raw or "")[:160].replace("\n", "\\n"))

        # ---- Tool-call detector → parser → normalizer (requirements #1/#2).
        # The provider-independent normalizer runs FIRST: it recognizes the
        # JSON protocol AND every XML dialect models actually emit
        # (<invoke name=...>, <minimax:toolcall>, <tool_call>, bare
        # <invoke>, function-call syntax). Only when it finds nothing do we
        # fall back to the strict JSON action protocol below.
        tool_calls = normalize_tool_calls(raw, list(TOOLS.keys()))
        if tool_calls:
            _trace("TOOL_PARSED", count=len(tool_calls),
                   names=",".join(tc.name for tc in tool_calls))
            convo.append({"role": "assistant", "text": raw})
            observations = []

            # Multitasking: allow executing batch of tool calls concurrently if safe
            batch = tool_calls[:10]
            read_only_tools = {
                "read_file", "list_directory", "search_workspace", "inspect_project",
                "archive_list", "calc", "calculate", "solve_custom", "plot_formula",
                "archive_validate", "web_search", "search"
            }
            can_parallel = len(batch) > 1 and all(tc.name in read_only_tools for tc in batch)

            if can_parallel:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(batch)), thread_name_prefix="cat-tool") as pool:
                    futures = [pool.submit(_execute_tool_call, tc.name, tc.arguments, raw) for tc in batch]
                    for tc, fut in zip(batch, futures):
                        if _cancelled():
                            break
                        _trace("TOOL_DETECTED", tool=tc.name, fmt=tc.source_format,
                               args=json.dumps(tc.arguments, default=str)[:160])
                        try:
                            obs = fut.result()
                        except Exception as e:
                            obs = f"Error: {e}"
                        observations.append(f"[{tc.name}] {obs}")
            else:
                for tc in batch:
                    if _cancelled():
                        break
                    _trace("TOOL_DETECTED", tool=tc.name, fmt=tc.source_format,
                           args=json.dumps(tc.arguments, default=str)[:160])
                    obs = _execute_tool_call(tc.name, tc.arguments, raw)
                    observations.append(f"[{tc.name}] {obs}")

            steps_left = max_steps - i - 1
            nudge = ""
            if steps_left <= 3:
                nudge = (f"\n\n(You have about {steps_left} step(s) left — start wrapping up: "
                         "finish any remaining sub-calculations now and prepare the final answer.")
            convo.append({"role": "user", "text": (
                f"TOOL RESULT: {' | '.join(observations)}{nudge}\n\n"
                "Continue: call another tool if needed, or reply with the final JSON action now."
            )})
            _trace("MODEL_CONTINUED", fed_back=True, tools_so_far=len(steps))
            _emit("agent_continuing", step=i + 1, tools_so_far=len(steps))
            continue

        action = _normalize_action(_extract_json(raw))

        if not action or "action" not in action:
            # Model didn't follow the JSON protocol at all and no parser
            # recognized a tool call. If it at least produced real prose,
            # that's a usable answer — only bail with the "couldn't reach"
            # message when there's truly nothing.
            _trace("NO_TOOL_IN_RESPONSE", snippet=(raw or "")[:120])
            return _finish(raw or "I couldn't reach the AI provider. Try /verify.")

        if action.get("action") == "final":
            text = action.get("text") or raw
            return _finish(text)

        if action.get("action") == "tool":
            name = action.get("tool")
            args = action.get("args") or {}
            _trace("TOOL_DETECTED", tool=name, fmt="json_protocol",
                   args=json.dumps(args, default=str)[:160])
            obs = _execute_tool_call(name, args, raw)

            convo.append({"role": "assistant", "text": raw})
            steps_left = max_steps - i - 1
            nudge = ""
            if steps_left <= 3:
                nudge = (f"\n\n(You have about {steps_left} step(s) left — start wrapping up: "
                         "finish any remaining sub-calculations now and prepare the final answer.")
            convo.append({"role": "user", "text": (
                f"TOOL RESULT [{name}]: {obs}{nudge}\n\n"
                "Continue: call another tool if needed, or reply with the final JSON action now."
            )})
            _trace("MODEL_CONTINUED", fed_back=True, tools_so_far=len(steps))
            _emit("agent_continuing", step=i + 1, tools_so_far=len(steps))
            continue

        # Unrecognised action type — fall back to treating it as final text.
        return _finish(raw)

    # Step budget exhausted — force one last, direct request for the best
    # possible final answer using everything computed so far, instead of
    # handing back an apologetic "I ran out of steps" placeholder.
    convo.append({"role": "user", "text": (
        "You're out of tool-call steps. Using every result computed above, give your single "
        "best complete numeric answer to the ORIGINAL question now — reply with the final "
        'JSON action: {"action": "final", "text": "<complete answer, every part labeled>"}.'
    )})
    raw = aicore.query_ai(_build_prompt(convo), system_prompt=system_prompt, size_class="large", requirements=_task_req)
    action = _normalize_action(_extract_json(raw))
    if action and action.get("action") == "final" and action.get("text"):
        return _finish(action["text"])
    if raw and raw.strip():
        return _finish(raw)
    summary = "\n".join(f"- {n}: {o}" for n, _, o, _c in steps) or "No tools were run."
    return _finish("Here's everything computed so far while working on that:\n" + summary)


# =============================================================================
# Multi-agent collaboration [BETA]
#
# CCT talks to exactly one configured AI provider (whatever the user set up
# in /model), so "multiple agents" here means multiple *specialized passes*
# over that same provider — a Planner pass, then one or more Specialist
# passes that actually run tools (reusing run_agent's real tool-execution
# loop above), then a Tester/Verifier pass — each with its own system
# prompt, each reported to the UI as it starts/finishes via on_agent(). This
# is honestly a sequential pipeline, not literal parallel execution (a
# single terminal session showing one live status line at a time wouldn't
# be able to show true concurrency anyway) — but each stage genuinely
# reasons with a different persona/objective and can be watched working.
# =============================================================================

AGENT_TEAM = [
    ("researcher", "Researcher", "gathers outside context via web search before the plan is made (only when the question needs it)"),
    ("planner", "Planner", "breaks the question into an ordered list of concrete sub-tasks"),
    ("specialist", "Specialist", "runs the real tools (solve/plot/simulate/search) to execute the plan"),
    ("programmer", "Programmer", "writes/refines any code the answer needs (only for coding requests)"),
    ("debugger", "Debugger", "statically scans generated code for risky patterns and sandbox-tests it (only for coding requests)"),
    ("tester", "Tester", "checks the final numbers against the given data before anything is shown"),
]

# Roles that only join the pipeline when the request actually calls for
# them — always running all six for a plain "what is molarity?" question
# would be theatre, not a real team, so membership is content-gated.
_RESEARCH_HINTS = re.compile(
    r"\b(latest|recent|current|news|today|this year|search|look up|find out|"
    r"who is|what happened|price of|update on)\b", re.I)
_CODE_HINTS = re.compile(
    r"\b(code|python|script|program|function|write a .*(class|module)|"
    r"generate.*(code|script))\b", re.I)

_PLANNER_PROMPT = """You are the PLANNER on a small AI team working inside CCT (Chemistry Calc
Terminal). You do not solve anything and you do not call tools. Read the
user's question and reply with ONLY a JSON object of the form:
{"plan": ["short step 1", "short step 2", ...]}
Keep it to 2-5 concrete, concrete steps (e.g. "solve for k using the
first-order rate formula", "plot the resulting curve"). No prose outside
the JSON."""

_TESTER_PROMPT = """You are the TESTER on a small AI team working inside CCT (Chemistry Calc
Terminal). You are handed the ORIGINAL question, the PLAN the team made,
and the SPECIALIST's final answer. Check the arithmetic and units are
internally consistent with the given data. Reply with ONLY a JSON object:
{"ok": true, "note": ""} if it checks out, or
{"ok": false, "note": "<what looks wrong, one sentence>"} if not.
Do not redo the whole calculation from scratch — spot-check it."""


def _plan_steps(user_text, system_prompt):
    """Planner pass: ask for a short JSON step list. Falls back to a
    single-step plan if the model doesn't cooperate, so the pipeline
    never blocks on this stage."""
    raw = aicore.query_ai(
        f"User's question:\n{user_text}",
        system_prompt=_PLANNER_PROMPT + "\n\n" + system_prompt,
        size_class="large",
    )
    data = _extract_json(raw) or {}
    plan = data.get("plan")
    if isinstance(plan, list) and plan:
        return [str(s) for s in plan][:6]
    return ["Work out and answer the question directly."]


def _verify_answer(user_text, plan, final_text, system_prompt):
    """Tester pass: sanity-check the specialist's answer. Never raises —
    a failed/garbled check is treated as 'ok' rather than blocking the
    user from seeing their answer."""
    raw = aicore.query_ai(
        "ORIGINAL QUESTION:\n" + user_text +
        "\n\nPLAN:\n" + "\n".join(f"- {p}" for p in plan) +
        "\n\nSPECIALIST'S FINAL ANSWER:\n" + final_text,
        system_prompt=_TESTER_PROMPT + "\n\n" + system_prompt,
        size_class="normal",
    )
    data = _extract_json(raw) or {}
    if data.get("ok") is False and data.get("note"):
        return False, str(data["note"])
    return True, ""


_PROGRAMMER_PROMPT = """You are the PROGRAMMER on a small AI team working inside CCT (Chemistry
Calc Terminal). The user wants runnable code. Write clean, correct
Python (or the requested language) in a single fenced code block, with
a one-line explanation before it. No filler, no apologies."""

_DEBUGGER_NOTE_TEMPLATE = (
    "\n\n⚠ Debugger static scan of the generated code found: {summary}\n"
    "{details}\nReview before running this yourself."
)


def _research_pass(user_text, system_prompt):
    """Researcher pass: only fires when the question has a recency/lookup
    flavor (regex-gated, see _RESEARCH_HINTS). Runs a real web search and
    folds a short synthesized brief into the context handed to the
    Planner, so downstream stages aren't reasoning from stale training
    data on a fast-moving fact."""
    if not _RESEARCH_HINTS.search(user_text):
        return ""
    try:
        results = aicore.web_search(user_text, max_results=4)
    except Exception:
        results = None
    if not results:
        return ""
    lines = [f"- {r['title']}: {r['snippet']}" for r in results[:4]]
    return "RESEARCHER'S BRIEF (live web search, use if relevant):\n" + "\n".join(lines)


def _extract_code_block(text):
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text or "", re.S)
    return m.group(1) if m else None


def _debug_pass(final_text):
    """Debugger pass: only fires when the specialist's answer actually
    contains a Python code block. Runs the real static scanner
    (security_scanner.scan_code) and, for HIGH-risk-free code, a real
    sandboxed execution (sandbox.run_sandboxed) to confirm it at least
    runs, then appends genuine findings — never fabricated ones."""
    code = _extract_code_block(final_text)
    if not code:
        return final_text, None
    findings = security_scanner.scan_code(code)
    risk = security_scanner.risk_level(findings)
    note = {"risk": risk, "findings": [repr(f) for f in findings]}
    if findings:
        details = "\n".join(f"  {repr(f)}" for f in findings[:5])
        final_text += _DEBUGGER_NOTE_TEMPLATE.format(
            summary=security_scanner.summarize(findings), details=details)
    if risk != security_scanner.HIGH:
        result = sandbox.run_sandboxed(code, timeout=8)
        note["sandbox_test"] = {
            "returncode": result["returncode"],
            "timed_out": result["timed_out"],
            "stderr_tail": (result["stderr"] or "")[-300:],
        }
        if result["returncode"] != 0 and not result["timed_out"]:
            err_tail = (result["stderr"] or "").strip().splitlines()
            err_tail = err_tail[-1] if err_tail else "unknown error"
            final_text += f"\n\n🐞 Debugger ran this in the sandbox and it raised: {err_tail}"
    else:
        note["sandbox_test"] = "skipped (high-risk code is not auto-executed)"
    return final_text, note


def run_multi_agent(user_text, max_steps=MAX_STEPS, on_agent=None, mode="agent"):
    """Runs the Planner -> Specialist -> Tester pipeline for one user
    request. `on_agent(role_key, role_label, status)` is called with
    status in {"start", "done"} so the caller can render live per-agent
    status lines. Returns (final_text, steps, meta, plan, verify_note) —
    the extra `plan` and `verify_note` let the UI show the team's work,
    not just the final answer.

    Falls back cleanly to the plain single-agent run_agent() output if
    no AI provider is configured (query_ai already returns a clear
    message in that case instead of raising).
    """
    system_prompt = BUILD_SYSTEM_PROMPT if mode == "build" else (RESEARCH_SYSTEM_PROMPT if mode == "research" else AGENT_SYSTEM_PROMPT)
    wants_code = bool(_CODE_HINTS.search(user_text))
    active_roles = ["planner", "specialist"] + (["programmer", "debugger"] if wants_code else []) + ["tester"]

    research_brief = ""
    if _RESEARCH_HINTS.search(user_text):
        active_roles.insert(0, "researcher")
        if on_agent:
            on_agent("researcher", "Researcher", "start")
        research_brief = _research_pass(user_text, system_prompt)
        if on_agent:
            on_agent("researcher", "Researcher", "done")

    if on_agent:
        on_agent("planner", "Planner", "start")
    plan = _plan_steps(user_text + ("\n\n" + research_brief if research_brief else ""), system_prompt)
    if on_agent:
        on_agent("planner", "Planner", "done")

    if on_agent:
        on_agent("specialist", "Specialist", "start")
    plan_note = "\n\nTEAM PLAN (from the Planner — follow it, adapt if needed):\n" + \
        "\n".join(f"{i+1}. {p}" for i, p in enumerate(plan))
    if research_brief:
        plan_note += "\n\n" + research_brief
    if wants_code:
        plan_note += "\n\n" + _PROGRAMMER_PROMPT
    final_text, steps, meta = run_agent(
        user_text + plan_note, max_steps=max_steps, verbose=False, mode=mode
    )
    if on_agent:
        on_agent("specialist", "Specialist", "done")

    debug_note = None
    ok = True
    note = None

    if wants_code:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="cat-verify") as pool:
            if on_agent:
                on_agent("programmer", "Programmer", "start")
                on_agent("programmer", "Programmer", "done")
                on_agent("debugger", "Debugger", "start")
                on_agent("tester", "Tester", "start")
            fut_debug = pool.submit(_debug_pass, final_text)
            fut_tester = pool.submit(_verify_answer, user_text, plan, final_text, system_prompt)

            try:
                final_text, debug_note = fut_debug.result()
            except Exception as e:
                debug_note = str(e)
            if on_agent:
                on_agent("debugger", "Debugger", "done")

            try:
                ok, note = fut_tester.result()
            except Exception as e:
                ok, note = True, str(e)
            if on_agent:
                on_agent("tester", "Tester", "done")
    else:
        if on_agent:
            on_agent("tester", "Tester", "start")
        ok, note = _verify_answer(user_text, plan, final_text, system_prompt)
        if on_agent:
            on_agent("tester", "Tester", "done")

    if not ok and note:
        final_text = final_text + f"\n\n⚠ Tester flagged this for review: {note}"

    meta = dict(meta)
    meta["team_plan"] = plan
    meta["active_roles"] = active_roles
    meta["debug_note"] = debug_note
    meta["tester_ok"] = ok
    meta["tester_note"] = note
    return final_text, steps, meta
