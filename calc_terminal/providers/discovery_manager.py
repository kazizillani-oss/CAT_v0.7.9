"""
calc_terminal/providers/discovery_manager.py
===========================================
Provider Discovery Manager for Dynamic Model and Provider Discovery.

Coordinates adapter-driven live discovery across all supported providers,
reconciles results against DynamicModelRegistry, and notifies users when
new models are detected.

Features:
  - Non-blocking asynchronous discovery loops.
  - Fail-safe timeout bounding and graceful error recovery.
  - Offline mode detection and stale cache preservation.
  - Live health status tracking (ONLINE, DEGRADED, OFFLINE, UNKNOWN).
"""

import concurrent.futures
import json
import logging
import os
import threading
import time
from typing import Dict, List, Optional, Any, Callable

from .adapters import get_adapter, list_supported_adapters
from ..models.dynamic_registry import get_registry, DynamicModelRegistry
from ..models.schema import ModelInfo

_LOG = logging.getLogger("cct.discovery_manager")


class ProviderDiscoveryManager:
    """Manages continuous background model discovery and reconciliation."""

    _instance: Optional["ProviderDiscoveryManager"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ProviderDiscoveryManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, registry: Optional[DynamicModelRegistry] = None):
        if getattr(self, "_initialized", False):
            return
        self.registry = registry or get_registry()
        self._provider_status: Dict[str, Dict[str, Any]] = {}
        self._notification_hooks: List[Callable[[List[ModelInfo]], None]] = []
        self._bg_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._initialized = True

    # ── Notification Hooks ─────────────────────────────────────────────────────

    def add_notification_hook(self, hook: Callable[[List[ModelInfo]], None]):
        """Register a callback for when new models are detected."""
        if hook not in self._notification_hooks:
            self._notification_hooks.append(hook)

    register_notification_hook = add_notification_hook

    def _notify_new_models(self, new_models: List[ModelInfo]):
        for hook in self._notification_hooks:
            try:
                hook(new_models)
            except Exception as e:
                _LOG.warning(f"Error executing discovery notification hook: {e}")

    # ── Single Provider Discovery ──────────────────────────────────────────────

    def discover_provider(
        self,
        provider_id: str,
        config: Optional[Dict[str, Any]] = None,
        timeout: float = 6.0,
    ) -> List[ModelInfo]:
        """Run discovery for a single provider and reconcile with registry."""
        pid = provider_id.lower().strip()
        adapter = get_adapter(pid, config)

        try:
            discovered = adapter.discover_models(timeout=timeout)
            if discovered:
                diff = self.registry.reconcile_models(pid, discovered)
                self._provider_status[pid] = {
                    "status": "online",
                    "models_count": len(discovered),
                    "last_checked": time.time(),
                    "diff": diff,
                }
                # Check for newly discovered models
                new_models = self.registry.pop_new_models()
                if new_models:
                    self._notify_new_models(new_models)
                return discovered
            else:
                self._provider_status[pid] = {
                    "status": "degraded",
                    "models_count": 0,
                    "last_checked": time.time(),
                    "message": "Zero models returned",
                }
        except Exception as e:
            _LOG.warning(f"Discovery failed for {pid}: {e}")
            self._provider_status[pid] = {
                "status": "offline",
                "last_checked": time.time(),
                "error": str(e),
            }

        # Fallback to previously cached registry models
        return self.registry.list_models(provider=pid)

    # ── Parallel Discovery Across All Providers ────────────────────────────────

    def discover_all(
        self,
        provider_configs: Optional[Dict[str, Dict[str, Any]]] = None,
        timeout_per_provider: float = 6.0,
        max_workers: int = 8,
    ) -> Dict[str, List[ModelInfo]]:
        """Discover models across all supported providers in parallel."""
        supported = list_supported_adapters()
        configs = provider_configs or {}
        results: Dict[str, List[ModelInfo]] = {}

        # Prioritize key providers first
        priority_pids = [
            "openai", "anthropic", "gemini", "deepseek", "alibaba",
            "moonshot", "zhipu", "ollama", "xai", "mistral", "minimax"
        ]
        all_pids = list(priority_pids) + [p for p in supported.keys() if p not in priority_pids]

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_pid = {
                executor.submit(
                    self.discover_provider, pid, configs.get(pid), timeout_per_provider
                ): pid
                for pid in all_pids
            }
            for future in concurrent.futures.as_completed(future_to_pid):
                pid = future_to_pid[future]
                try:
                    results[pid] = future.result()
                except Exception as e:
                    results[pid] = []
                    _LOG.warning(f"Exception during discovery for {pid}: {e}")

        return results

    # ── Background Worker ──────────────────────────────────────────────────────

    def start_background_discovery(self, interval_hours: float = 24.0, delay_startup: float = 1.0):
        """Launch background discovery thread."""
        if self._bg_thread and self._bg_thread.is_alive():
            return

        self._stop_event.clear()

        def _loop():
            # Initial brief delay so CAT startup finishes instantly
            self._stop_event.wait(delay_startup)
            if self._stop_event.is_set():
                return
            try:
                self.discover_all()
            except Exception as e:
                _LOG.warning(f"Background initial discovery error: {e}")

            # Periodic loop
            while not self._stop_event.is_set():
                self._stop_event.wait(interval_hours * 3600.0)
                if self._stop_event.is_set():
                    break
                try:
                    self.discover_all()
                except Exception as e:
                    _LOG.warning(f"Background periodic discovery error: {e}")

        self._bg_thread = threading.Thread(
            target=_loop,
            daemon=True,
            name="cct-discovery-manager",
        )
        self._bg_thread.start()

    def stop_background_discovery(self):
        """Stop background discovery thread."""
        self._stop_event.set()

    # ── Status Inspection ──────────────────────────────────────────────────────

    def get_provider_status(self, provider_id: str) -> Dict[str, Any]:
        pid = provider_id.lower().strip()
        return self._provider_status.get(pid, {"status": "unknown", "provider": pid})

    def get_all_provider_statuses(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._provider_status)

    get_all_provider_status = get_all_provider_statuses


# Singleton convenience accessor
def get_discovery_manager() -> ProviderDiscoveryManager:
    return ProviderDiscoveryManager()
