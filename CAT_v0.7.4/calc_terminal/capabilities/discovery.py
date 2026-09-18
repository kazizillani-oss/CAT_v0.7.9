"""
CAT Environment & Capability Discovery per §34, §35, §36, §46, §57, §86.
Performs real runtime environment inspection.
Never returns fake capabilities or simulated states.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .schema import AvailabilityStatus


@dataclass
class EnvironmentSnapshot:
    """Snapshot of discovered execution targets and software availability."""
    python_version: str
    virtual_env: Optional[str]
    git_installed: bool
    git_version: str
    jupyter_installed: bool
    playwright_installed: bool
    chromium_installed: bool
    torch_installed: bool
    cuda_available: bool
    gpu_name: str
    vram_gb: float
    matlab_available: bool
    pymol_available: bool
    chimerax_available: bool
    blast_available: bool
    kaggle_configured: bool
    huggingface_configured: bool
    github_configured: bool
    qiskit_installed: bool
    cirq_installed: bool
    pennylane_installed: bool
    discovered_packages: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "python_version": self.python_version,
            "virtual_env": self.virtual_env,
            "git_installed": self.git_installed,
            "git_version": self.git_version,
            "jupyter_installed": self.jupyter_installed,
            "playwright_installed": self.playwright_installed,
            "chromium_installed": self.chromium_installed,
            "torch_installed": self.torch_installed,
            "cuda_available": self.cuda_available,
            "gpu_name": self.gpu_name,
            "vram_gb": self.vram_gb,
            "matlab_available": self.matlab_available,
            "pymol_available": self.pymol_available,
            "chimerax_available": self.chimerax_available,
            "blast_available": self.blast_available,
            "kaggle_configured": self.kaggle_configured,
            "huggingface_configured": self.huggingface_configured,
            "github_configured": self.github_configured,
            "qiskit_installed": self.qiskit_installed,
            "cirq_installed": self.cirq_installed,
            "pennylane_installed": self.pennylane_installed,
            "discovered_packages": self.discovered_packages,
        }


def _pkg_version(pkg_name: str) -> Optional[str]:
    """Return installed package version if present, else None."""
    try:
        mod = importlib.import_module(pkg_name)
        return getattr(mod, "__version__", "installed")
    except Exception:
        return None


def _has_command(cmd: str) -> bool:
    """Check if command is on system PATH."""
    return shutil.which(cmd) is not None


def _get_command_output(cmd: List[str], timeout: float = 3.0) -> str:
    """Execute command and return stdout safely."""
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            shell=False,
        )
        return res.stdout.strip()
    except Exception:
        return ""


def discover_environment() -> EnvironmentSnapshot:
    """Perform real discovery of local runtime tools, libraries, and hardware."""
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    venv = os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_PREFIX")

    # Git
    git_installed = _has_command("git")
    git_ver = _get_command_output(["git", "--version"]) if git_installed else ""

    # Jupyter
    jupyter_installed = _has_command("jupyter") or (_pkg_version("jupyter") is not None) or (_pkg_version("notebook") is not None)

    # Playwright & Chromium
    playwright_installed = _pkg_version("playwright") is not None
    chromium_installed = False
    if playwright_installed:
        try:
            from ..browser.engine import PLAYWRIGHT_AVAILABLE
            chromium_installed = PLAYWRIGHT_AVAILABLE
        except Exception:
            chromium_installed = False

    # PyTorch & Accelerators
    torch_ver = _pkg_version("torch")
    torch_installed = torch_ver is not None
    cuda_avail = False
    gpu_name = ""
    vram_gb = 0.0

    if torch_installed:
        try:
            import torch
            cuda_avail = torch.cuda.is_available()
            if cuda_avail:
                gpu_name = torch.cuda.get_device_name(0)
                vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
        except Exception:
            pass

    if not gpu_name and _has_command("nvidia-smi"):
        smi = _get_command_output(["nvidia-smi", "--query-gpu=gpu_name,memory.total", "--format=csv,noheader,nounits"])
        if smi and "," in smi:
            parts = smi.split(",")
            gpu_name = parts[0].strip()
            try:
                vram_gb = round(float(parts[1].strip()) / 1024.0, 2)
            except Exception:
                pass

    # Scientific packages
    pkgs = {}
    candidate_pkgs = [
        "numpy", "scipy", "pandas", "sympy", "matplotlib", "sklearn",
        "transformers", "biopython", "qiskit", "cirq", "pennylane",
        "requests", "textual", "rich"
    ]
    for p in candidate_pkgs:
        v = _pkg_version(p)
        if v:
            pkgs[p] = v

    # MATLAB
    matlab_available = _has_command("matlab") or (_pkg_version("matlab") is not None)

    # PyMOL / ChimeraX
    pymol_available = _has_command("pymol") or os.path.exists(r"C:\Program Files\PyMOL\PyMOLWin.exe") or os.path.exists(r"C:\Program Files (x86)\Schrodinger\PyMOL")
    chimerax_available = _has_command("chimerax") or os.path.exists(r"C:\Program Files\ChimeraX\bin\ChimeraX.exe")

    # BLAST
    blast_available = _has_command("blastn") or _has_command("blastp") or (_pkg_version("Bio") is not None)

    # Platforms / Credentials
    kaggle_path = os.path.expanduser(os.path.join("~", ".kaggle", "kaggle.json"))
    kaggle_configured = os.path.exists(kaggle_path) or bool(os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"))

    hf_token_path = os.path.expanduser(os.path.join("~", ".cache", "huggingface", "token"))
    hf_configured = os.path.exists(hf_token_path) or bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"))

    github_configured = bool(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or _has_command("gh"))

    return EnvironmentSnapshot(
        python_version=py_ver,
        virtual_env=venv,
        git_installed=git_installed,
        git_version=git_ver,
        jupyter_installed=jupyter_installed,
        playwright_installed=playwright_installed,
        chromium_installed=chromium_installed,
        torch_installed=torch_installed,
        cuda_available=cuda_avail,
        gpu_name=gpu_name,
        vram_gb=vram_gb,
        matlab_available=matlab_available,
        pymol_available=pymol_available,
        chimerax_available=chimerax_available,
        blast_available=blast_available,
        kaggle_configured=kaggle_configured,
        huggingface_configured=hf_configured,
        github_configured=github_configured,
        qiskit_installed="qiskit" in pkgs,
        cirq_installed="cirq" in pkgs,
        pennylane_installed="pennylane" in pkgs,
        discovered_packages=pkgs,
    )
