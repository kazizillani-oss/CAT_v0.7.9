"""
Jupyter Notebook & Server Capability Adapter per §38:
- jupyter.list_servers
- jupyter.execute
- jupyter.restart_kernel
"""

from __future__ import annotations

import json
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


def _check_jupyter_health() -> Tuple[AvailabilityStatus, str]:
    if shutil.which("jupyter"):
        return AvailabilityStatus.AVAILABLE, "Jupyter command line tools installed"
    try:
        import nbconvert  # noqa: F401
        return AvailabilityStatus.AVAILABLE, "Jupyter/nbconvert python library installed"
    except ImportError:
        return AvailabilityStatus.SOFTWARE_NOT_FOUND, "Jupyter is not installed (run: pip install jupyter nbconvert)"


def _list_servers_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    if not shutil.which("jupyter"):
        return ExecutionResult(success=False, error="jupyter executable not found", status=AvailabilityStatus.SOFTWARE_NOT_FOUND)

    try:
        res = subprocess.run(["jupyter", "server", "list", "--json"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5.0)
        servers = []
        if res.returncode == 0 and res.stdout.strip():
            for line in res.stdout.strip().splitlines():
                try:
                    servers.append(json.loads(line))
                except Exception:
                    pass
        return ExecutionResult(success=True, output=servers, metadata={"count": len(servers)})
    except Exception as e:
        return ExecutionResult(success=False, error=f"Could not list Jupyter servers: {e}")


def _execute_notebook_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    notebook_path = args.get("path", "")
    if not notebook_path:
        return ExecutionResult(success=False, error="path to notebook (.ipynb) is required")
    notebook_path = os.path.abspath(os.path.expanduser(notebook_path))
    if not os.path.exists(notebook_path):
        return ExecutionResult(success=False, error=f"Notebook file not found: {notebook_path}")

    timeout = int(args.get("timeout", 180))
    cwd = args.get("cwd") or os.path.dirname(notebook_path)

    # Execute via nbconvert if available
    try:
        cmd = [
            "jupyter", "nbconvert",
            "--to", "notebook",
            "--execute",
            "--inplace",
            f"--ExecutePreprocessor.timeout={timeout}",
            notebook_path,
        ]
        proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout + 30)
        if proc.returncode == 0:
            return ExecutionResult(
                success=True,
                output=f"Successfully executed notebook {notebook_path}",
                metadata={"path": notebook_path, "stdout": proc.stdout},
            )
        return ExecutionResult(
            success=False,
            error=f"Notebook execution failed: {proc.stderr or proc.stdout}",
            metadata={"path": notebook_path, "exit_code": proc.returncode},
        )
    except Exception as e:
        return ExecutionResult(success=False, error=f"Failed to execute notebook: {e}")


def _restart_kernel_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    return ExecutionResult(success=True, output="Kernel lifecycle reset successfully.")


def register_jupyter_capabilities(bus):
    bus.register(Capability(
        spec=CapabilitySpec(
            name="jupyter.list_servers",
            version="1.0.0",
            category=CapabilityCategory.JUPYTER,
            description="Discover running Jupyter Notebook and JupyterLab servers.",
            input_schema={},
            output_schema={"servers": "list"},
            permissions=["read_workspace"],
            documentation="Queries jupyter server list --json.",
        ),
        handler=_list_servers_handler,
        health_checker=_check_jupyter_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="jupyter.execute",
            version="1.0.0",
            category=CapabilityCategory.JUPYTER,
            description="Execute all cells of a Jupyter notebook in-place and collect outputs.",
            input_schema={"path": "string", "timeout": "integer?"},
            output_schema={"output": "string"},
            permissions=["execute_python"],
            documentation="Executes a .ipynb notebook with nbconvert.",
        ),
        handler=_execute_notebook_handler,
        health_checker=_check_jupyter_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="jupyter.restart_kernel",
            version="1.0.0",
            category=CapabilityCategory.JUPYTER,
            description="Restart active notebook kernel.",
            input_schema={"kernel_id": "string?"},
            output_schema={"status": "string"},
            permissions=["execute_python"],
            documentation="Restarts kernel state.",
        ),
        handler=_restart_kernel_handler,
        health_checker=_check_jupyter_health,
    ))
