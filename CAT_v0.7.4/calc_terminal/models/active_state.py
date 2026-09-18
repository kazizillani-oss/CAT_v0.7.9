"""
CAT CLI — ActiveAIState: Authoritative Single Source of Truth for Active Model/Provider.

Ensures hot model switching across Chat, Agent, Build, Plan, Research, Notebook,
Debugger, and Code Editor without restarting CAT CLI.
"""

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class ActiveAIStateRecord:
    """Authoritative snapshot of the active AI provider and model."""
    provider_id: str = ""
    model_id: str = ""
    deployment_id: str = ""
    endpoint: str = ""
    status: str = "Not Configured"
    capabilities: Dict = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "deployment_id": self.deployment_id,
            "endpoint": self.endpoint,
            "status": self.status,
            "capabilities": dict(self.capabilities),
            "last_updated": self.last_updated,
        }


class ActiveAIStateManager:
    """Manages the singular active AI state and distributes updates

    to UI, Router, and Runtime.
    """
    _instance: Optional["ActiveAIStateManager"] = None

    def __init__(self):
        self._state = ActiveAIStateRecord()
        self._subscribers: List[Callable[[ActiveAIStateRecord], None]] = []
        self._initialized = False
        self.reload_from_config()

    @classmethod
    def get_instance(cls) -> "ActiveAIStateManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def reload_from_config(self) -> ActiveAIStateRecord:
        """Hydrate active state from disk configuration."""
        try:
            from ..providers import provider_manager as pm
            cfg = pm.load_config()
        except Exception:
            cfg = {}

        provider = cfg.get("provider") or ""
        model = cfg.get("model") or ""
        endpoint = cfg.get("base_url") or cfg.get("api_url") or cfg.get("ollama_url") or ""
        status = "Ready" if provider and model else ("Not Configured" if not provider else "Model Needed")

        caps = {}
        if provider:
            try:
                from ..model_router import capabilities_for
                caps_obj = capabilities_for(provider, model)
                if hasattr(caps_obj, "to_dict"):
                    caps = caps_obj.to_dict()
                elif hasattr(caps_obj, "__dict__"):
                    caps = dict(caps_obj.__dict__)
            except Exception:
                pass

        self._state = ActiveAIStateRecord(
            provider_id=provider,
            model_id=model,
            deployment_id=cfg.get("deployment_id") or "",
            endpoint=endpoint,
            status=status,
            capabilities=caps,
            last_updated=time.time(),
        )
        self._initialized = True
        return self._state

    def get_state(self) -> ActiveAIStateRecord:
        if not self._initialized:
            self.reload_from_config()
        return self._state

    def set_active_model(self, provider_id: str, model_id: str,
                         config_updates: Optional[Dict] = None) -> ActiveAIStateRecord:
        """Authoritative hot-switch function.

        1. Updates persistent disk config
        2. Updates in-memory ActiveAIState
        3. Invalidates model router cache
        4. Notifies subscribers (UI, session, etc.)
        """
        provider_id = (provider_id or "").strip()
        model_id = (model_id or "").strip()

        try:
            from ..providers import provider_manager as pm
            cfg = pm.load_config()
        except Exception:
            cfg = {}

        cfg["provider"] = provider_id
        cfg["model"] = model_id
        if config_updates:
            for k, v in config_updates.items():
                if v is not None:
                    cfg[k] = v

        try:
            from ..providers import provider_manager as pm
            pm.save_config(cfg)
        except Exception:
            pass

        # Invalidate model router cache
        try:
            from .. import model_router
            model_router.invalidate_cache()
        except Exception:
            pass

        # Calculate capabilities
        caps = {}
        try:
            from ..model_router import capabilities_for
            caps_obj = capabilities_for(provider_id, model_id)
            if hasattr(caps_obj, "to_dict"):
                caps = caps_obj.to_dict()
            elif hasattr(caps_obj, "__dict__"):
                caps = dict(caps_obj.__dict__)
        except Exception:
            pass

        endpoint = cfg.get("base_url") or cfg.get("api_url") or cfg.get("ollama_url") or ""
        self._state = ActiveAIStateRecord(
            provider_id=provider_id,
            model_id=model_id,
            deployment_id=cfg.get("deployment_id") or "",
            endpoint=endpoint,
            status="Ready" if provider_id and model_id else "Not Configured",
            capabilities=caps,
            last_updated=time.time(),
        )

        # Notify subscribers
        for sub in list(self._subscribers):
            try:
                sub(self._state)
            except Exception:
                pass

        return self._state

    def subscribe(self, callback: Callable[[ActiveAIStateRecord], None]) -> None:
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[ActiveAIStateRecord], None]) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)


def get_active_state() -> ActiveAIStateRecord:
    """Convenience helper to retrieve current ActiveAIStateRecord."""
    return ActiveAIStateManager.get_instance().get_state()


def set_active_ai(provider_id: str, model_id: str, config: Optional[Dict] = None) -> ActiveAIStateRecord:
    """Convenience helper to hot switch active AI provider & model."""
    return ActiveAIStateManager.get_instance().set_active_model(provider_id, model_id, config)
