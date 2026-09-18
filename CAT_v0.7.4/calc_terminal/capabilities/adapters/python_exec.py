"""
Python Execution Capability Adapter:
- python.execute
"""

from __future__ import annotations

import os
import sys
import subprocess
import tempfile
import time
from typing import Any, Dict, Optional, Tuple

from ..schema import (
    AvailabilityStatus,
    Capability,
    CapabilityCategory,
    CapabilitySpec,
    ExecutionResult,
)


def _check_python_health() -> Tuple[AvailabilityStatus, str]:
    ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return AvailabilityStatus.AVAILABLE, f"Python {ver} ({sys.executable})"


def _python_execute_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    code = args.get("code", "")
    if not code:
        return ExecutionResult(success=False, error="code argument is required")

    timeout = float(args.get("timeout", 30.0))
    cwd = args.get("cwd", os.getcwd())

    t0 = time.perf_counter()
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        temp_file = f.name

    try:
        proc = subprocess.run(
            [sys.executable, temp_file],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        duration = round((time.perf_counter() - t0) * 1000.0, 2)
        success = (proc.returncode == 0)

        return ExecutionResult(
            success=success,
            output=proc.stdout,
            error=proc.stderr if not success else None,
            duration_ms=duration,
            metadata={"exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr},
        )
    except subprocess.TimeoutExpired:
        duration = round((time.perf_counter() - t0) * 1000.0, 2)
        return ExecutionResult(
            success=False,
            error=f"Python script execution timed out after {timeout} seconds",
            duration_ms=duration,
        )
    except Exception as e:
        duration = round((time.perf_counter() - t0) * 1000.0, 2)
        return ExecutionResult(success=False, error=str(e), duration_ms=duration)
    finally:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception:
            pass


def register_python_capabilities(bus):
    bus.register(Capability(
        spec=CapabilitySpec(
            name="python.execute",
            version="1.0.0",
            category=CapabilityCategory.PYTHON,
            description="Execute Python code in an isolated subprocess with stdout/stderr capture.",
            input_schema={"code": "string", "timeout": "number?", "cwd": "string?"},
            output_schema={"output": "string", "exit_code": "integer"},
            permissions=["execute_python"],
            documentation="Executes arbitrary Python code using the active Python interpreter.",
        ),
        handler=_python_execute_handler,
        health_checker=_check_python_health,
    ))
