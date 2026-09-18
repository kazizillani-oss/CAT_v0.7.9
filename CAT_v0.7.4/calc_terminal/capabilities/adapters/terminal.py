"""
Terminal / Process Execution Capability Adapter:
- terminal.execute
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any, Dict, Optional, Tuple

from ..schema import (
    AvailabilityStatus,
    Capability,
    CapabilityCategory,
    CapabilitySpec,
    ExecutionResult,
)


def _check_terminal_health() -> Tuple[AvailabilityStatus, str]:
    return AvailabilityStatus.AVAILABLE, "System shell execution available"


def _execute_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    command = args.get("command", "")
    if not command:
        return ExecutionResult(success=False, error="command argument is required")

    cwd = args.get("cwd", os.getcwd())
    timeout = float(args.get("timeout", 60.0))
    env_overrides = args.get("env", {})

    env = os.environ.copy()
    if isinstance(env_overrides, dict):
        env.update(env_overrides)

    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            shell=True,
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
            metadata={
                "exit_code": proc.returncode,
                "command": command,
                "cwd": cwd,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            },
        )
    except subprocess.TimeoutExpired as e:
        duration = round((time.perf_counter() - t0) * 1000.0, 2)
        return ExecutionResult(
            success=False,
            error=f"Command timed out after {timeout} seconds",
            duration_ms=duration,
            metadata={"exit_code": -1, "command": command, "timeout": timeout},
        )
    except Exception as e:
        duration = round((time.perf_counter() - t0) * 1000.0, 2)
        return ExecutionResult(
            success=False,
            error=str(e),
            duration_ms=duration,
            metadata={"exit_code": -1, "command": command},
        )


def register_terminal_capabilities(bus):
    bus.register(Capability(
        spec=CapabilitySpec(
            name="terminal.execute",
            version="1.0.0",
            category=CapabilityCategory.TERMINAL,
            description="Execute a shell command with stdout, stderr and exit code capture.",
            input_schema={"command": "string", "cwd": "string?", "timeout": "number?", "env": "object?"},
            output_schema={"output": "string", "exit_code": "integer"},
            permissions=["execute_terminal"],
            documentation="Executes a command line string in the host shell.",
        ),
        handler=_execute_handler,
        health_checker=_check_terminal_health,
    ))
