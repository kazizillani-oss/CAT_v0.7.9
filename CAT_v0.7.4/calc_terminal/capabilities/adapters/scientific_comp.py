"""
Scientific Computing Capability Adapter per §43:
- matlab.execute
- numpy.compute
- scipy.optimize
"""

from __future__ import annotations

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


def _check_matlab_health() -> Tuple[AvailabilityStatus, str]:
    if shutil.which("matlab"):
        return AvailabilityStatus.AVAILABLE, "MATLAB CLI executable found"
    try:
        import matlab.engine  # noqa: F401
        return AvailabilityStatus.AVAILABLE, "MATLAB Python Engine available"
    except ImportError:
        return AvailabilityStatus.SOFTWARE_NOT_FOUND, "MATLAB is not installed on this system"


def _check_scientific_health() -> Tuple[AvailabilityStatus, str]:
    try:
        import numpy  # noqa: F401
        import scipy  # noqa: F401
        return AvailabilityStatus.AVAILABLE, f"NumPy {numpy.__version__}, SciPy {scipy.__version__} ready"
    except ImportError as e:
        return AvailabilityStatus.SOFTWARE_NOT_FOUND, f"Scientific packages missing: {e}"


def _matlab_execute_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    script = args.get("script", "")
    code = args.get("code", "")
    if not script and not code:
        return ExecutionResult(success=False, error="script or code argument is required")

    exe = shutil.which("matlab")
    if not exe:
        return ExecutionResult(
            success=False,
            error="MATLAB executable not found on host machine. Please install and license MATLAB.",
            status=AvailabilityStatus.SOFTWARE_NOT_FOUND,
        )

    matlab_cmd = f"-batch \"{code}\"" if code else f"-batch \"run('{script}')\""
    try:
        proc = subprocess.run([exe, "-nodisplay", "-nosplash", "-batch", code or f"run('{script}')"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
        return ExecutionResult(
            success=(proc.returncode == 0),
            output=proc.stdout,
            error=proc.stderr if proc.returncode != 0 else None,
            metadata={"exit_code": proc.returncode},
        )
    except Exception as e:
        return ExecutionResult(success=False, error=f"MATLAB execution failed: {e}")


def _numpy_compute_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    expr = args.get("expression", "")
    if not expr:
        return ExecutionResult(success=False, error="expression argument is required")

    try:
        import numpy as np
        # Evaluate safely within numpy scope
        scope = {"np": np}
        # Disallow dangerous builtins
        res = eval(expr, {"__builtins__": {}}, scope)
        if isinstance(res, np.ndarray):
            out = {
                "shape": list(res.shape),
                "dtype": str(res.dtype),
                "data": res.tolist() if res.size <= 1000 else "Array too large to serialize; summary displayed",
                "mean": float(np.mean(res)) if res.size > 0 else None,
            }
        else:
            out = res
        return ExecutionResult(success=True, output=out)
    except Exception as e:
        return ExecutionResult(success=False, error=f"NumPy computation error: {e}")


def register_scientific_capabilities(bus):
    bus.register(Capability(
        spec=CapabilitySpec(
            name="matlab.execute",
            version="1.0.0",
            category=CapabilityCategory.SCIENTIFIC,
            description="Execute MATLAB script or expressions in non-display batch mode.",
            input_schema={"code": "string?", "script": "string?"},
            output_schema={"output": "string"},
            permissions=["execute_terminal"],
            documentation="Executes MATLAB commands where licensed.",
        ),
        handler=_matlab_execute_handler,
        health_checker=_check_matlab_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="numpy.compute",
            version="1.0.0",
            category=CapabilityCategory.SCIENTIFIC,
            description="Perform numerical array calculations using NumPy.",
            input_schema={"expression": "string"},
            output_schema={"result": "any"},
            permissions=["read_workspace"],
            documentation="Evaluates mathematical numpy expressions.",
        ),
        handler=_numpy_compute_handler,
        health_checker=_check_scientific_health,
    ))
