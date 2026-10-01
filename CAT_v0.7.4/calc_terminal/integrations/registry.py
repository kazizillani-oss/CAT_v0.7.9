"""
CAT Integrations — Central Integration Registry.

Manages connection states, authentication, discovery, and capability queries
across AI Providers, Development platforms, Research environments, and Tools.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    IntegrationSpec,
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    STATE_NEEDS_AUTH,
    STATE_UNAVAILABLE,
    STATE_ERROR,
)
from .builtin_integrations import BUILTIN_INTEGRATIONS_DEFS
from .. import storage

logger = logging.getLogger("cat.integrations.registry")

_REGISTRY_LOCK = threading.RLock()
_INSTANCE: Optional[IntegrationRegistry] = None


class IntegrationRegistry:
    """Thread-safe registry of CAT integrations."""

    def __init__(self, store_dir: Optional[str] = None):
        self.store_dir = store_dir or storage.get_subpath("integrations")
        self._integrations: Dict[str, IntegrationSpec] = {}
        self._probers: Dict[str, Any] = {}
        self._bootstrap()

    def _bootstrap(self) -> None:
        for item in BUILTIN_INTEGRATIONS_DEFS:
            spec = IntegrationSpec(
                id=item["id"],
                name=item["name"],
                category=item["category"],
                description=item["description"],
                icon=item["icon"],
                capabilities=item["capabilities"],
                auth_type=item["auth_type"],
                status=STATE_DISCONNECTED,
                builtin=True,
            )
            self._integrations[spec.id] = spec
            if "prober" in item:
                self._probers[spec.id] = item["prober"]

        # Run initial status probes lazily
        self.refresh_statuses()

    def refresh_statuses(self) -> Dict[str, str]:
        """Runs live connection probes without blocking UI."""
        with _REGISTRY_LOCK:
            res = {}
            for iid, prober in self._probers.items():
                spec = self._integrations.get(iid)
                if not spec:
                    continue
                try:
                    st, details = prober()
                    spec.status = st
                    spec.details = details
                    spec.last_checked = time.time()
                    res[iid] = st
                except Exception as e:
                    spec.status = STATE_ERROR
                    spec.details = str(e)
                    res[iid] = STATE_ERROR
            return res

    def register(self, spec: IntegrationSpec) -> IntegrationSpec:
        with _REGISTRY_LOCK:
            self._integrations[spec.id] = spec
            return spec

    def remove(self, integration_id: str) -> bool:
        with _REGISTRY_LOCK:
            spec = self._integrations.get(integration_id)
            if not spec or spec.builtin:
                return False
            del self._integrations[integration_id]
            return True

    def get(self, integration_id: str) -> Optional[IntegrationSpec]:
        with _REGISTRY_LOCK:
            return self._integrations.get(integration_id)

    def list(self, category: Optional[str] = None) -> List[IntegrationSpec]:
        with _REGISTRY_LOCK:
            items = list(self._integrations.values())
            if category:
                items = [i for i in items if i.category == category]
            return items

    def status(self, integration_id: str) -> Dict[str, Any]:
        with _REGISTRY_LOCK:
            spec = self.get(integration_id)
            if not spec:
                return {"id": integration_id, "status": STATE_UNAVAILABLE, "error": "Not registered"}
            return spec.to_dict()

    def capabilities(self, integration_id: str) -> List[str]:
        with _REGISTRY_LOCK:
            spec = self.get(integration_id)
            return list(spec.capabilities) if spec else []

    def connect(self, integration_id: str, credentials: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """Attempts to establish connection with an integration."""
        with _REGISTRY_LOCK:
            spec = self.get(integration_id)
            if not spec:
                return False, f"Integration '{integration_id}' not found."

            # If a prober exists, probe it
            prober = self._probers.get(integration_id)
            if prober:
                st, details = prober()
                spec.status = st
                spec.details = details
                if st == STATE_CONNECTED:
                    return True, f"Connected to {spec.name}: {details}"
                return False, f"Cannot connect to {spec.name}: {details}"

            spec.status = STATE_CONNECTED
            return True, f"Connected to {spec.name}"

    def disconnect(self, integration_id: str) -> bool:
        with _REGISTRY_LOCK:
            spec = self.get(integration_id)
            if not spec:
                return False
            spec.status = STATE_DISCONNECTED
            spec.details = "Disconnected by user"
            return True


def get_integration_registry() -> IntegrationRegistry:
    global _INSTANCE
    if _INSTANCE is None:
        with _REGISTRY_LOCK:
            if _INSTANCE is None:
                _INSTANCE = IntegrationRegistry()
    return _INSTANCE
