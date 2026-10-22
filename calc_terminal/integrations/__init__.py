"""
CAT Integrations — Central Modular Integrations Subsystem.
"""

from .models import (
    IntegrationSpec,
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    STATE_NEEDS_AUTH,
    STATE_UNAVAILABLE,
    STATE_ERROR,
    ALL_INTEGRATION_STATES,
)
from .registry import IntegrationRegistry, get_integration_registry

__all__ = [
    "IntegrationSpec",
    "IntegrationRegistry",
    "get_integration_registry",
    "STATE_CONNECTED",
    "STATE_DISCONNECTED",
    "STATE_NEEDS_AUTH",
    "STATE_UNAVAILABLE",
    "STATE_ERROR",
    "ALL_INTEGRATION_STATES",
]
