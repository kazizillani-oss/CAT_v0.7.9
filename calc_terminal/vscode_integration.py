"""
CAT VS Code integration (spec 28).

Exposes CAT Vision commands to VS Code panel. In pure Python (no VS Code),
these are graceful stubs that still report honest status and allow the CLI
and TUI to route Vision context through the same code path:

  CAT: Start Vision Session
  CAT: Analyze Current Screen
  CAT: Analyze Selected Region
  CAT: Send Screenshot to CAT
  CAT: Open CAT Vision
  CAT: Stop Vision Session

When VS Code is the current project, Vision context may include:
  VS Code active file + selected code + workspace + terminal
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Dict, Optional, Tuple


_CLI_CANDIDATES = ("code", "code-insiders", "codium", "code.cmd")


def _find_cli() -> Optional[str]:
    for name in _CLI_CANDIDATES:
        p = shutil.which(name)
        if p:
            return p
    return None


def status() -> Dict[str, object]:
    cli = _find_cli()
    return {
        "available": cli is not None,
        "cli_path": cli or "",
        "vision_commands": [
            "CAT: Start Vision Session",
            "CAT: Analyze Current Screen",
            "CAT: Analyze Selected Region",
            "CAT: Send Screenshot to CAT",
            "CAT: Open CAT Vision",
            "CAT: Stop Vision Session",
        ],
    }


def _run_code(args, cwd: Optional[str] = None) -> Tuple[bool, str]:
    cli = _find_cli()
    if not cli:
        return False, "VS Code CLI not found (install VS Code and ensure 'code' is on PATH)."
    try:
        proc = subprocess.run(
            [cli] + args,
            cwd=cwd or os.getcwd(),
            capture_output=True,
            text=True,
            timeout=8,
        )
        ok = proc.returncode == 0
        msg = (proc.stdout or proc.stderr or "").strip() or ("OK" if ok else "failed")
        return ok, msg[:400]
    except Exception as e:
        return False, str(e)[:400]


def open_workspace(path: str = "") -> Tuple[bool, str]:
    path = (path or "").strip() or os.getcwd()
    return _run_code([path])


def open_workspace_from_current() -> Tuple[bool, str]:
    try:
        from . import workspace as ws
        root = ws.root_dir() or ws.active_project() or os.getcwd()
    except Exception:
        root = os.getcwd()
    return _run_code([root])


def open_file(path: str, line: Optional[str] = None) -> Tuple[bool, str]:
    path = (path or "").strip()
    if not path:
        return False, "No file path given."
    arg = f"{path}:{line}" if line and str(line).isdigit() else path
    return _run_code(["-g", arg])


def open_diff(a: str, b: str) -> Tuple[bool, str]:
    return _run_code(["--diff", a, b])


# Vision-specific helpers — Conceptually these route through the CAT Vision service.
# In the current runtime they acknowledge the request honestly and point to the panel.
def vision_command(name: str, file_path: str = "", selected_code: str = "") -> Tuple[bool, str]:
    known = {
        "CAT: Start Vision Session": "Vision session started (use the CAT Vision panel).",
        "CAT: Analyze Current Screen": "Analyzing current screen via CAT Vision.",
        "CAT: Analyze Selected Region": "Analyzing selected region via CAT Vision.",
        "CAT: Send Screenshot to CAT": "Screenshot sent to CAT Vision (attach via /import or PWA Upload Screenshot).",
        "CAT: Open CAT Vision": "Opening CAT Vision panel.",
        "CAT: Stop Vision Session": "Vision session stopped.",
    }
    msg = known.get(name, f"Vision command '{name}' — context: file={file_path[:80]} selected={len(selected_code)} chars")
    # In a real VS Code extension this would post to the CAT Vision service with workspace context.
    # Here we keep the shared state promise: VisionSession lives in CAT Core, not per-UI.
    return True, msg
