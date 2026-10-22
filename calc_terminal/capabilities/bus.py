"""
CAT Capability Bus — Central Architecture per §4, §56, §57.
Modes request capabilities through this bus; tools and integrations are never
owned privately by individual modes.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .schema import (
    AvailabilityStatus,
    Capability,
    CapabilityCategory,
    CapabilitySpec,
    ExecutionError,
    ExecutionResult,
)

_LOG = logging.getLogger("cct.capabilities")


class CapabilityBus:
    """Central registry and execution dispatch for all CAT capabilities."""

    _instance: Optional[CapabilityBus] = None
    _lock = threading.Lock()

    def __new__(cls) -> CapabilityBus:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CapabilityBus, cls).__new__(cls)
                cls._instance._capabilities: Dict[str, Capability] = {}
                cls._instance._initialized = False
            return cls._instance

    def register(self, capability: Capability) -> None:
        """Register a new capability in the bus."""
        name = capability.name.strip().lower()
        self._capabilities[name] = capability
        _LOG.debug("Registered capability: %s (version %s)", name, capability.spec.version)

    def get(self, name: str) -> Optional[Capability]:
        """Look up a capability by canonical name."""
        canonical = (name or "").strip().lower()
        return self._capabilities.get(canonical)

    def get_capability(self, name: str) -> Optional[Capability]:
        """Look up a capability by canonical name."""
        return self.get(name)

    def has(self, name: str) -> bool:
        """Check whether a capability is registered."""
        return name.strip().lower() in self._capabilities

    def list_capabilities(
        self,
        category: Optional[Union[CapabilityCategory, str]] = None,
        status: Optional[AvailabilityStatus] = None,
    ) -> List[Capability]:
        """Return registered capabilities filtered by category or status."""
        caps = list(self._capabilities.values())
        if category:
            cat_val = category.value if isinstance(category, CapabilityCategory) else str(category).lower()
            caps = [c for c in caps if c.spec.category.value.lower() == cat_val]
        if status:
            caps = [c for c in caps if c.status == status]
        return sorted(caps, key=lambda c: c.name)

    def execute(
        self,
        name: str,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        task_id: str = "",
        mode: str = "",
        permission_callback: Optional[Callable[[str, str, str, str], str]] = None,
    ) -> ExecutionResult:
        """Execute a capability with permission checking and event emission."""
        canonical = (name or "").strip().lower()
        cap = self.get(canonical)
        if not cap:
            return ExecutionResult(
                success=False,
                error=f"Capability '{canonical}' is not registered in the Capability Bus.",
                status=AvailabilityStatus.UNAVAILABLE,
            )

        args = args or {}
        context = context or {}

        # 1. Permission check
        if cap.spec.permissions:
            try:
                from .. import permissions as perm
                for req_perm in cap.spec.permissions:
                    if perm.manager.refused_by_always_deny(req_perm):
                        return ExecutionResult(
                            success=False,
                            error=f"Permission denied: {req_perm} is permanently denied for this session.",
                            status=AvailabilityStatus.PERMISSION_DENIED,
                        )
                    if perm.manager.needs_prompt(req_perm):
                        decision = "allow_once"
                        if permission_callback:
                            decision = permission_callback(
                                req_perm,
                                f"Execute {canonical}",
                                str(args.get("path", "") or args.get("target", "")),
                                f"Required by capability {canonical}",
                            )
                        if not perm.manager.decide(req_perm, decision, canonical, "Capability execution"):
                            return ExecutionResult(
                                success=False,
                                error=f"Permission rejected by user for capability '{canonical}'.",
                                status=AvailabilityStatus.PERMISSION_DENIED,
                            )
            except Exception as e:
                _LOG.warning("Permission validation check failed: %s", e)

        # 2. Emit ToolStarted event
        try:
            from ..workflow_engine import workflow_engine, EVENT_TOOL_STARTED, ExecutionEvent, STATE_RUNNING
            workflow_engine.record_tool_start(
                tool=canonical,
                args=args,
                turn_id=task_id or context.get("turn_id", ""),
            )
        except Exception:
            pass

        # 3. Execution
        result = cap.execute(args, context)

        # 4. Attach Provenance
        result.provenance = {
            "capability": canonical,
            "version": cap.spec.version,
            "task_id": task_id,
            "mode": mode,
            "timestamp": time.time(),
            "duration_ms": result.duration_ms,
            "success": result.success,
        }

        # 5. Emit ToolFinished event
        try:
            from ..workflow_engine import workflow_engine
            workflow_engine.record_tool_completion(
                tool=canonical,
                result=str(result.output if result.success else result.error)[:200],
                turn_id=task_id or context.get("turn_id", ""),
                duration_ms=int(result.duration_ms),
            )
        except Exception:
            pass

        return result

    def health_check_all(self, force: bool = False) -> Dict[str, Dict[str, Any]]:
        """Run health check across all registered capabilities."""
        report = {}
        for name, cap in self._capabilities.items():
            status, message = cap.check_health(force=force)
            report[name] = {
                "category": cap.spec.category.value,
                "status": status.value,
                "message": message,
                "version": cap.spec.version,
                "auth_required": cap.spec.auth_required,
            }
        return report


capability_bus = CapabilityBus()
