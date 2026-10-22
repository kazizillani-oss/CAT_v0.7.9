"""
CAT Capabilities Package per §4, §56, §57:
Central Capability Bus, schema definitions, environment discovery, and adapters.
"""

from .schema import (
    AvailabilityStatus,
    Capability,
    CapabilityCategory,
    CapabilitySpec,
    ExecutionError,
    ExecutionResult,
)
from .bus import CapabilityBus, capability_bus
from .discovery import EnvironmentSnapshot, discover_environment
from .adapters import register_all_adapters

# Auto-register all built-in adapters into the singleton bus
if not capability_bus._initialized:
    register_all_adapters(capability_bus)
    capability_bus._initialized = True

__all__ = [
    "AvailabilityStatus",
    "CapabilityCategory",
    "CapabilitySpec",
    "ExecutionError",
    "ExecutionResult",
    "Capability",
    "CapabilityBus",
    "capability_bus",
    "EnvironmentSnapshot",
    "discover_environment",
    "register_all_adapters",
]
