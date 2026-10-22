"""
Structural Biology Capability Adapter per §44:
- pymol.open
- chimerax.open
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Dict, Optional, Tuple

from ..schema import (
    AvailabilityStatus,
    Capability,
    CapabilityCategory,
    CapabilitySpec,
    ExecutionResult,
)


def _find_pymol() -> Optional[str]:
    cmd = shutil.which("pymol")
    if cmd:
        return cmd
    candidates = [
        r"C:\Program Files\PyMOL\PyMOLWin.exe",
        r"C:\Program Files\PyMOL\PyMOL.exe",
        r"C:\Program Files (x86)\Schrodinger\PyMOL\PyMOLWin.exe",
        "/usr/bin/pymol",
        "/usr/local/bin/pymol",
        "/Applications/PyMOL.app/Contents/MacOS/PyMOL",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def _find_chimerax() -> Optional[str]:
    cmd = shutil.which("chimerax")
    if cmd:
        return cmd
    candidates = [
        r"C:\Program Files\ChimeraX\bin\ChimeraX.exe",
        r"C:\Program Files\ChimeraX 1.7\bin\ChimeraX.exe",
        "/usr/bin/chimerax",
        "/usr/local/bin/chimerax",
        "/Applications/ChimeraX.app/Contents/MacOS/ChimeraX",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def _check_structural_health() -> Tuple[AvailabilityStatus, str]:
    pymol = _find_pymol()
    chimerax = _find_chimerax()
    if pymol or chimerax:
        found = []
        if pymol:
            found.append(f"PyMOL: {pymol}")
        if chimerax:
            found.append(f"ChimeraX: {chimerax}")
        return AvailabilityStatus.AVAILABLE, ", ".join(found)
    return AvailabilityStatus.SOFTWARE_NOT_FOUND, "Neither PyMOL nor ChimeraX executable found on system"


def _pymol_open_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    structure_path = args.get("path", "")
    if not structure_path:
        return ExecutionResult(success=False, error="path argument (PDB/mmCIF) is required")
    structure_path = os.path.abspath(os.path.expanduser(structure_path))
    if not os.path.exists(structure_path):
        return ExecutionResult(success=False, error=f"Structure file not found: {structure_path}")

    exe = _find_pymol()
    if not exe:
        return ExecutionResult(
            success=False,
            error="PyMOL executable not found on host machine. Please install PyMOL.",
            status=AvailabilityStatus.SOFTWARE_NOT_FOUND,
        )

    script = args.get("script", "")
    cmd = [exe, structure_path]
    if script:
        cmd.extend(["-d", script])

    try:
        # Launch non-blocking
        subprocess.Popen(cmd)
        return ExecutionResult(
            success=True,
            output=f"Opened {structure_path} in PyMOL ({exe})",
            metadata={"executable": exe, "structure": structure_path},
        )
    except Exception as e:
        return ExecutionResult(success=False, error=f"Failed to launch PyMOL: {e}")


def _chimerax_open_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    structure_path = args.get("path", "")
    if not structure_path:
        return ExecutionResult(success=False, error="path argument (PDB/mmCIF) is required")
    structure_path = os.path.abspath(os.path.expanduser(structure_path))
    if not os.path.exists(structure_path):
        return ExecutionResult(success=False, error=f"Structure file not found: {structure_path}")

    exe = _find_chimerax()
    if not exe:
        return ExecutionResult(
            success=False,
            error="ChimeraX executable not found on host machine. Please install ChimeraX.",
            status=AvailabilityStatus.SOFTWARE_NOT_FOUND,
        )

    cmd = [exe, structure_path]
    try:
        subprocess.Popen(cmd)
        return ExecutionResult(
            success=True,
            output=f"Opened {structure_path} in ChimeraX ({exe})",
            metadata={"executable": exe, "structure": structure_path},
        )
    except Exception as e:
        return ExecutionResult(success=False, error=f"Failed to launch ChimeraX: {e}")


def register_structural_bio_capabilities(bus):
    bus.register(Capability(
        spec=CapabilitySpec(
            name="pymol.open",
            version="1.0.0",
            category=CapabilityCategory.BIO,
            description="Open protein/molecular structure in PyMOL for 3D visualization.",
            input_schema={"path": "string", "script": "string?"},
            output_schema={"status": "string"},
            permissions=["execute_terminal"],
            documentation="Launches PyMOL with the target structure.",
        ),
        handler=_pymol_open_handler,
        health_checker=_check_structural_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="chimerax.open",
            version="1.0.0",
            category=CapabilityCategory.BIO,
            description="Open biomolecular structure in UCSF ChimeraX for visualization and analysis.",
            input_schema={"path": "string"},
            output_schema={"status": "string"},
            permissions=["execute_terminal"],
            documentation="Launches ChimeraX with the target structure.",
        ),
        handler=_chimerax_open_handler,
        health_checker=_check_structural_health,
    ))
