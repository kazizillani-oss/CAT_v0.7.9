"""
CAT Capability System — Core Schemas and Contracts.
Defines:
- AvailabilityStatus: honest capability states per §4, §57, §86
- CapabilityCategory: functional domain
- CapabilitySpec: complete capability manifest
- ExecutionResult / ExecutionError: structured result and error models per §83
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union


class AvailabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    SOFTWARE_NOT_FOUND = "SOFTWARE_NOT_FOUND"
    LICENSE_REQUIRED = "LICENSE_REQUIRED"
    PERMISSION_DENIED = "PERMISSION_DENIED"


class CapabilityCategory(str, Enum):
    FILESYSTEM = "filesystem"
    TERMINAL = "terminal"
    PYTHON = "python"
    BROWSER = "browser"
    JUPYTER = "jupyter"
    GIT = "git"
    ML = "ml"
    BIO = "bio"
    SCIENTIFIC = "scientific"
    PLATFORMS = "platforms"
    QUANTUM = "quantum"
    CUSTOM = "custom"


@dataclass
class CapabilitySpec:
    """Full specification contract for a CAT capability."""
    name: str
    version: str
    category: CapabilityCategory
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    error_schema: Dict[str, Any] = field(default_factory=dict)
    permissions: List[str] = field(default_factory=list)
    auth_required: bool = False
    environment_requirements: List[str] = field(default_factory=list)
    documentation: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "category": self.category.value if isinstance(self.category, CapabilityCategory) else str(self.category),
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "error_schema": self.error_schema,
            "permissions": self.permissions,
            "auth_required": self.auth_required,
            "environment_requirements": self.environment_requirements,
            "documentation": self.documentation,
            "tags": self.tags,
        }


class ExecutionError(Exception):
    """Structured error raised during capability execution per §83."""

    def __init__(
        self,
        message: str,
        tool: str = "",
        task_id: str = "",
        retryable: bool = False,
        error_type: str = "ToolExecutionError",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.tool = tool
        self.task_id = task_id
        self.retryable = retryable
        self.error_type = error_type
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.error_type,
            "tool": self.tool,
            "task_id": self.task_id,
            "message": self.message,
            "retryable": self.retryable,
            "details": self.details,
        }


@dataclass
class ExecutionResult:
    """Standard execution result returned by all capability adapters."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    status: AvailabilityStatus = AvailabilityStatus.AVAILABLE
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "status": self.status.value if isinstance(self.status, AvailabilityStatus) else str(self.status),
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
            "provenance": self.provenance,
            "timestamp": self.timestamp,
        }


class Capability:
    """Callable unit representing a concrete capability implementation."""

    def __init__(
        self,
        spec: CapabilitySpec,
        handler: Callable[[Dict[str, Any], Optional[Dict[str, Any]]], ExecutionResult],
        health_checker: Optional[Callable[[], Tuple[AvailabilityStatus, str]]] = None,
    ):
        self.spec = spec
        self.handler = handler
        self.health_checker = health_checker
        self._last_status: AvailabilityStatus = AvailabilityStatus.AVAILABLE
        self._last_status_message: str = "Ready"
        self._last_check_time: float = 0.0

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def status(self) -> AvailabilityStatus:
        return self._last_status

    def check_health(self, force: bool = False) -> Tuple[AvailabilityStatus, str]:
        """Check capability availability and return (status, message)."""
        now = time.time()
        if not force and (now - self._last_check_time < 15.0) and self._last_check_time > 0:
            return self._last_status, self._last_status_message

        if self.health_checker:
            try:
                st, msg = self.health_checker()
                self._last_status = st
                self._last_status_message = msg
            except Exception as e:
                self._last_status = AvailabilityStatus.UNAVAILABLE
                self._last_status_message = f"Health check failed: {e}"
        else:
            self._last_status = AvailabilityStatus.AVAILABLE
            self._last_status_message = "Ready"

        self._last_check_time = now
        return self._last_status, self._last_status_message

    def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """Run the capability handler with error handling and timing."""
        t0 = time.perf_counter()
        # Fast health check if unknown
        if self._last_check_time == 0:
            self.check_health()

        if self._last_status in (
            AvailabilityStatus.SOFTWARE_NOT_FOUND,
            AvailabilityStatus.AUTHENTICATION_REQUIRED,
            AvailabilityStatus.LICENSE_REQUIRED,
            AvailabilityStatus.UNAVAILABLE,
        ):
            elapsed = (time.perf_counter() - t0) * 1000.0
            return ExecutionResult(
                success=False,
                error=f"Capability '{self.name}' not available: {self._last_status_message}",
                status=self._last_status,
                duration_ms=round(elapsed, 2),
                metadata={"reason": self._last_status_message},
            )

        try:
            res = self.handler(args, context)
            if not isinstance(res, ExecutionResult):
                res = ExecutionResult(success=True, output=res)
            res.duration_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return res
        except ExecutionError as ee:
            elapsed = (time.perf_counter() - t0) * 1000.0
            return ExecutionResult(
                success=False,
                error=ee.message,
                status=AvailabilityStatus.UNAVAILABLE,
                duration_ms=round(elapsed, 2),
                metadata=ee.to_dict(),
            )
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000.0
            return ExecutionResult(
                success=False,
                error=str(e),
                status=AvailabilityStatus.UNAVAILABLE,
                duration_ms=round(elapsed, 2),
                metadata={"exception": type(e).__name__},
            )
