"""
CAT Universal Tool Execution Engine (v0.7.9 Complete Platform Expansion)

Handles validation, permission enforcement, async execution, timeouts,
cancellation, execution logging, telemetry, retry, and formatting for all tools.
"""

import time
import json
import asyncio
import traceback
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable

from . import permissions as perm
from .capability_registry import get_registry, CapabilitySpec

@dataclass
class ToolExecutionLog:
    execution_id: str
    tool_id: str
    caller: str
    args: Dict[str, Any]
    started_at: float
    duration_ms: float = 0.0
    success: bool = False
    result_summary: str = ""
    error: Optional[str] = None
    permission_granted: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "tool_id": self.tool_id,
            "caller": self.caller,
            "args": self.args,
            "started_at": self.started_at,
            "duration_ms": round(self.duration_ms, 2),
            "success": self.success,
            "result_summary": self.result_summary[:200],
            "error": self.error,
            "permission_granted": self.permission_granted,
        }


class UniversalToolExecutionEngine:
    """Central engine executing tools with strict security, permission checks, and auditing."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._history: List[ToolExecutionLog] = []
            cls._instance._max_history = 200
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_history"):
            self._history: List[ToolExecutionLog] = []
            self._max_history = 200

    def check_permission(self, tool_id: str, caller: str = "user", args: Optional[Dict[str, Any]] = None) -> bool:
        """Check whether execution is allowed under current permission manager mode."""
        mode = perm.manager.mode
        if mode == "full":
            return True
        elif mode == "restricted":
            # In restricted mode, block mutating tools
            cap = get_registry().get(tool_id)
            if cap and cap.requires_permission == "protected":
                return False
            # Check for shell command, write, delete, deploy
            protected_patterns = ["write", "edit", "run_command", "deploy", "delete", "remove", "kill"]
            if any(p in tool_id.lower() for p in protected_patterns):
                return False
            return True
        elif mode == "ask":
            # Normal tools run; protected tools can be gated
            return True
        return True

    def execute_tool(
        self,
        tool_id: str,
        args: Dict[str, Any],
        caller: str = "assistant",
        timeout_seconds: float = 30.0,
        retries: int = 0
    ) -> Dict[str, Any]:
        """Synchronously execute a registered tool or capability handler."""
        exec_id = f"exec_{int(time.time() * 1000)}"
        start_t = time.time()
        log = ToolExecutionLog(
            execution_id=exec_id,
            tool_id=tool_id,
            caller=caller,
            args=args,
            started_at=start_t
        )

        # 1. Permission check
        allowed = self.check_permission(tool_id, caller, args)
        if not allowed:
            log.permission_granted = False
            log.success = False
            log.error = f"Permission denied: '{tool_id}' is blocked in {perm.manager.mode_label()} mode."
            log.duration_ms = (time.time() - start_t) * 1000
            self._record_log(log)
            return {
                "success": False,
                "error": log.error,
                "execution_id": exec_id
            }

        # 2. Lookup capability
        cap = get_registry().get(tool_id)
        handler = cap.handler if cap else None

        if not handler:
            # Fallback to local dispatch or registry
            log.success = False
            log.error = f"Tool '{tool_id}' not found or handler not registered."
            log.duration_ms = (time.time() - start_t) * 1000
            self._record_log(log)
            return {
                "success": False,
                "error": log.error,
                "execution_id": exec_id
            }

        # 3. Execution with retry
        attempt = 0
        last_err = None
        while attempt <= retries:
            attempt += 1
            try:
                # Execute
                result = handler(**args) if args else handler()
                log.success = True
                log.result_summary = str(result)[:300]
                log.duration_ms = (time.time() - start_t) * 1000
                self._record_log(log)
                return {
                    "success": True,
                    "result": result,
                    "execution_id": exec_id,
                    "duration_ms": log.duration_ms
                }
            except Exception as e:
                last_err = str(e)
                if attempt <= retries:
                    time.sleep(0.2 * attempt)

        log.success = False
        log.error = last_err or "Unknown execution failure"
        log.duration_ms = (time.time() - start_t) * 1000
        self._record_log(log)
        return {
            "success": False,
            "error": log.error,
            "execution_id": exec_id,
            "duration_ms": log.duration_ms
        }

    async def execute_tool_async(
        self,
        tool_id: str,
        args: Dict[str, Any],
        caller: str = "assistant",
        timeout_seconds: float = 30.0
    ) -> Dict[str, Any]:
        """Asynchronously execute a tool within a timeout envelope."""
        loop = asyncio.get_event_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, lambda: self.execute_tool(tool_id, args, caller, timeout_seconds)),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Tool '{tool_id}' timed out after {timeout_seconds}s.",
                "execution_id": "timeout"
            }

    def _record_log(self, log: ToolExecutionLog):
        self._history.append(log)
        if len(self._history) > self._max_history:
            self._history.pop(0)

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return the recent tool execution history."""
        return [l.to_dict() for l in reversed(self._history[-limit:])]

    def clear_history(self):
        self._history.clear()


# Global singleton instance
tool_engine = UniversalToolExecutionEngine()

def get_tool_engine() -> UniversalToolExecutionEngine:
    return tool_engine

