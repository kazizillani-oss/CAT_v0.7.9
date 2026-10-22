import os
import sys
import pytest

from calc_terminal.compute.fabric import (
    ComputeFabric,
    ComputeTarget,
    ComputeTargetType,
    ComputeTargetStatus,
    LocalCPUTarget,
    compute_fabric,
)


def test_compute_fabric_target_discovery():
    fabric = ComputeFabric()
    targets = fabric.list_targets()
    assert len(targets) >= 4

    target_types = [t.target_type for t in targets]
    assert ComputeTargetType.LOCAL_CPU in target_types
    assert ComputeTargetType.LOCAL_GPU in target_types
    assert ComputeTargetType.OLLAMA in target_types
    assert ComputeTargetType.DOCKER in target_types

    # CPU target must always be available
    cpu = fabric.get_target("local_cpu")
    assert cpu is not None
    assert cpu.status == ComputeTargetStatus.AVAILABLE
    assert "logical_cores" in cpu.hardware_details


def test_compute_routing_intelligence():
    fabric = ComputeFabric()

    # Default task routes to CPU
    target, note = fabric.route_task({})
    assert target.target_id == "local_cpu"
    assert note is None

    # GPU task routes to GPU if available, or falls back to CPU with clear warning
    target, note = fabric.route_task({"requires_gpu": True})
    gpu_target = fabric.get_target("local_gpu")
    if gpu_target and gpu_target.status == ComputeTargetStatus.AVAILABLE:
        assert target.target_id == "local_gpu"
        assert note is None
    else:
        assert target.target_id == "local_cpu"
        assert note is not None
        assert "requires GPU" in note

    # Container task routing
    target, note = fabric.route_task({"container": "pytorch/pytorch"})
    docker_target = fabric.get_target("docker")
    if docker_target and docker_target.status == ComputeTargetStatus.AVAILABLE:
        assert target.target_id == "docker"
    else:
        assert target.target_id == "local_cpu"
        assert "container environment" in note


def test_local_cpu_execution():
    cpu = LocalCPUTarget()
    assert cpu.status == ComputeTargetStatus.AVAILABLE

    # Run real python execution via target
    res = cpu.execute(f'"{sys.executable}" -c "print(\'CAT Compute Fabric Running\')"')
    assert res["success"] is True
    assert res["return_code"] == 0
    assert "CAT Compute Fabric Running" in res["stdout"]
    assert res["duration_seconds"] >= 0.0


def test_unavailable_target_execution():
    target = ComputeTarget(
        target_id="test_cloud",
        target_type=ComputeTargetType.CLOUD,
        name="Mock Cloud",
        status=ComputeTargetStatus.UNAVAILABLE,
    )
    res = target.execute("echo test")
    assert res["success"] is False
    assert "not available" in res["error"]
