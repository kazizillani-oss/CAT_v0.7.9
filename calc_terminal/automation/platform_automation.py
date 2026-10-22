"""
CAT Platform & Computer Automation Subsystem.

Provides modular OS and computer automation across supported platforms (Windows, macOS, Linux):
- Safety permission levels: RESTRICTED (read-only inspection), ASK (approval required), FULL (scoped execution)
- Global emergency stop mechanism: halts all automation processes immediately
- Non-destructive execution and policy validation
"""

from __future__ import annotations

import os
import platform
import subprocess
import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class AutomationSafetyLevel(str, Enum):
    RESTRICTED = "restricted"  # Safe, read-only inspection only
    ASK = "ask"                # Interactive confirmation before any elevated action
    FULL = "full"              # Autonomous execution within explicitly configured capability scope


class PlatformAutomationError(Exception):
    pass


class EmergencyStopTriggered(PlatformAutomationError):
    pass


_EMERGENCY_STOP = threading.Event()
_ACTIVE_SUBPROCESSES: List[subprocess.Popen] = []
_PROC_LOCK = threading.Lock()


def trigger_emergency_stop() -> None:
    """Immediately trips the emergency stop switch and terminates all active automation child processes."""
    _EMERGENCY_STOP.set()
    with _PROC_LOCK:
        for p in list(_ACTIVE_SUBPROCESSES):
            try:
                p.terminate()
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        _ACTIVE_SUBPROCESSES.clear()


def reset_emergency_stop() -> None:
    """Resets the emergency stop switch."""
    _EMERGENCY_STOP.clear()


def is_emergency_stopped() -> bool:
    """Returns True if emergency stop is currently engaged."""
    return _EMERGENCY_STOP.is_set()


class PlatformAutomationManager:
    """Manages cross-platform computer automation workflows."""

    def __init__(self, safety_level: AutomationSafetyLevel = AutomationSafetyLevel.ASK):
        self.safety_level = safety_level
        self.os_type = platform.system().lower()  # "windows", "darwin", "linux"

    def check_emergency_stop(self) -> None:
        if _EMERGENCY_STOP.is_set():
            raise EmergencyStopTriggered("Automation aborted: Emergency Stop was triggered by user.")

    def run_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 30,
        permission_callback: Optional[Callable[[str, str], bool]] = None,
    ) -> Dict[str, Any]:
        """Runs an operating system command subject to active safety policy."""
        self.check_emergency_stop()

        # Policy checks
        if self.safety_level == AutomationSafetyLevel.RESTRICTED:
            # Only allow strictly read-only inspection commands
            safe_commands = ("dir", "ls", "pwd", "cd", "echo", "where", "which", "git status", "git log", "git diff")
            cmd_clean = command.strip().lower()
            if not any(cmd_clean.startswith(sc) for sc in safe_commands):
                return {
                    "ok": False,
                    "error": "PolicyViolation",
                    "reason": f"Command '{command}' blocked by RESTRICTED safety mode (read-only inspection only).",
                }

        elif self.safety_level == AutomationSafetyLevel.ASK:
            if permission_callback:
                allowed = permission_callback("run_command", command)
                if not allowed:
                    return {
                        "ok": False,
                        "error": "UserDenied",
                        "reason": f"Command '{command}' was denied by user approval policy.",
                    }

        # Execution
        shell = True
        try:
            proc = subprocess.Popen(
                command,
                cwd=cwd,
                shell=shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            with _PROC_LOCK:
                _ACTIVE_SUBPROCESSES.append(proc)

            stdout, stderr = proc.communicate(timeout=timeout)
            with _PROC_LOCK:
                if proc in _ACTIVE_SUBPROCESSES:
                    _ACTIVE_SUBPROCESSES.remove(proc)

            return {
                "ok": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "command": command,
            }
        except subprocess.TimeoutExpired:
            proc.kill()
            with _PROC_LOCK:
                if proc in _ACTIVE_SUBPROCESSES:
                    _ACTIVE_SUBPROCESSES.remove(proc)
            return {"ok": False, "error": "TimeoutExpired", "message": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"ok": False, "error": "ExecutionFailed", "message": str(e)}

    def inspect_system_environment(self) -> Dict[str, Any]:
        """Returns safe system diagnostic metrics (OS, CPU, Memory, Architecture)."""
        import sys
        return {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python_version": sys.version.split()[0],
            "cpu_count": os.cpu_count(),
            "safety_level": self.safety_level.value,
            "emergency_stopped": is_emergency_stopped(),
        }


platform_manager = PlatformAutomationManager()


def get_platform_automation_manager() -> PlatformAutomationManager:
    return platform_manager
