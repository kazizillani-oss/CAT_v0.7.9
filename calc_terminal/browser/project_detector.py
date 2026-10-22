"""CAT browser/ — project detection (spec section 20).

Decide WHAT KIND of web project the workspace is before starting any
server, so the preview can REUSE the project's own dev server (Vite /
Next / CRA) instead of blindly stacking a second static one on top:

    index.html                        → STATIC   (CAT's LiveServer)
    package.json + vite.config.*      → VITE     (npm run dev)
    package.json + next.config.*      → NEXT     (npm run dev)
    package.json + react-scripts      → CRA      (npm start)
    package.json + <other>            → NODE     (best-effort npm run dev)
    nothing recognizable              → STATIC

Detection is pure filesystem reading — no subprocesses, no network —
so it is safe to call from the UI thread and trivially unit-testable.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Optional


# Recognized project kinds -------------------------------------------------
STATIC = "static"
VITE = "vite"
NEXT = "next"
CRA = "cra"
NODE = "node"

_VITE_CONFIGS = ("vite.config.js", "vite.config.ts", "vite.config.mjs",
                 "vite.config.mts", "vite.config.cjs")
_NEXT_CONFIGS = ("next.config.js", "next.config.ts", "next.config.mjs",
                 "next.config.cjs")


@dataclass
class Detection:
    """One immutable detection result for a workspace root."""
    kind: str = STATIC
    root: str = ""
    # Shell-ish command tokens to spawn (argv list, no shell).
    command: tuple = ()
    # Human explanation surfaced in the preview activity strip.
    detail: str = ""
    # Files that identified the project (for honest status lines).
    evidence: tuple = field(default_factory=tuple)

    @property
    def is_framework(self) -> bool:
        return self.kind in (VITE, NEXT, CRA, NODE)

    @property
    def label(self) -> str:
        return {"static": "Static site", VITE: "Vite", NEXT: "Next.js",
                CRA: "Create React App", NODE: "Node"}.get(
                    self.kind, self.kind)


def _read_scripts(pkg_path: str) -> dict:
    try:
        with open(pkg_path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        return data.get("scripts") or {}
    except Exception:
        return {}


def detect_project(workspace_root: str) -> Detection:
    """Detect the project type of `workspace_root`. Never raises."""
    root = os.path.abspath(os.path.expanduser(workspace_root or ""))
    if not root or not os.path.isdir(root):
        return Detection(kind=STATIC, root=root,
                         detail="Not a folder — serving statically.")

    pkg_path = os.path.join(root, "package.json")
    has_pkg = os.path.isfile(pkg_path)

    if has_pkg:
        scripts = _read_scripts(pkg_path)
        evidence = ["package.json"]

        vite_cfg = next((c for c in _VITE_CONFIGS
                         if os.path.isfile(os.path.join(root, c))), None)
        dep_vite = False
        try:
            with open(pkg_path, "r", encoding="utf-8",
                      errors="replace") as f:
                deps = json.load(f)
            all_deps = {}
            all_deps.update(deps.get("dependencies") or {})
            all_deps.update(deps.get("devDependencies") or {})
            dep_vite = "vite" in all_deps
        except Exception:
            pass
        if vite_cfg or (dep_vite and "dev" in scripts):
            if vite_cfg:
                evidence.append(vite_cfg)
            cmd = scripts.get("dev") or scripts.get("serve") or "vite"
            return Detection(kind=VITE, root=root,
                             command=("npm", "run", "dev"),
                             detail=f"Vite project (`npm run {cmd}`) — "
                                    f"reusing its own HMR dev server.",
                             evidence=tuple(evidence))

        next_cfg = next((c for c in _NEXT_CONFIGS
                         if os.path.isfile(os.path.join(root, c))), None)
        if next_cfg or "next" in (scripts.get("dev") or ""):
            if next_cfg:
                evidence.append(next_cfg)
            return Detection(kind=NEXT, root=root,
                             command=("npm", "run", "dev"),
                             detail="Next.js project (`npm run dev`) — "
                                    "reusing its own dev server.",
                             evidence=tuple(evidence))

        start_script = scripts.get("start", "")
        if "react-scripts" in start_script:
            return Detection(kind=CRA, root=root,
                             command=("npm", "start"),
                             detail="Create React App (`npm start`) — "
                                    "reusing its own dev server.",
                             evidence=tuple(evidence))

        if scripts.get("dev"):
            return Detection(kind=NODE, root=root,
                             command=("npm", "run", "dev"),
                             detail="Node project (`npm run dev`).",
                             evidence=tuple(evidence))
        # package.json but no runnable dev script → static fallback.
        return Detection(kind=STATIC, root=root,
                         detail="package.json without a dev script — "
                                "serving statically.")

    return Detection(kind=STATIC, root=root,
                     detail="Static HTML project.")


def dependencies_installed(detection: Detection) -> bool:
    """Whether the framework project can actually be started right now
    (its node_modules are present). Static projects are always ready."""
    if not detection.is_framework:
        return True
    return os.path.isdir(os.path.join(detection.root, "node_modules"))
