"""
CAT Compute Fabric Package per §25, §26, §87-§90.
"""

from __future__ import annotations

from calc_terminal.compute.fabric import (
    ComputeTarget,
    ComputeTargetType,
    ComputeTargetStatus,
    LocalCPUTarget,
    LocalGPUTarget,
    OllamaTarget,
    DockerTarget,
    WSLTarget,
    ComputeFabric,
    compute_fabric,
)

__all__ = [
    "ComputeTarget",
    "ComputeTargetType",
    "ComputeTargetStatus",
    "LocalCPUTarget",
    "LocalGPUTarget",
    "OllamaTarget",
    "DockerTarget",
    "WSLTarget",
    "ComputeFabric",
    "compute_fabric",
]
