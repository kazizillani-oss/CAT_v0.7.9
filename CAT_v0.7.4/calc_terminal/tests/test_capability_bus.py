"""
Tests for CAT Central Capability Bus & Adapters per §4, §56, §57, §86.
"""

import pytest
from calc_terminal.capabilities import (
    capability_bus,
    Capability,
    CapabilitySpec,
    CapabilityCategory,
    AvailabilityStatus,
    ExecutionResult,
    discover_environment,
)


class TestCapabilityBus:
    def test_builtin_capabilities_registered(self):
        caps = capability_bus.list_capabilities()
        assert len(caps) >= 15
        names = [c.name for c in caps]
        assert "filesystem.read" in names
        assert "filesystem.write" in names
        assert "terminal.execute" in names
        assert "python.execute" in names
        assert "git.status" in names
        assert "browser.navigate" in names
        assert "jupyter.list_servers" in names
        assert "ml.detect_hardware" in names
        assert "quantum.bloch_sphere" in names

    def test_get_capability_case_insensitive(self):
        cap1 = capability_bus.get("FILESYSTEM.READ")
        cap2 = capability_bus.get("filesystem.read")
        assert cap1 is not None
        assert cap1 == cap2
        assert cap1.name == "filesystem.read"

    def test_filter_by_category(self):
        fs_caps = capability_bus.list_capabilities(category=CapabilityCategory.FILESYSTEM)
        assert len(fs_caps) >= 3
        for c in fs_caps:
            assert c.spec.category == CapabilityCategory.FILESYSTEM

    def test_execute_filesystem_read_write(self, tmp_path):
        test_file = str(tmp_path / "test_cap.txt")
        # Write
        res_write = capability_bus.execute(
            "filesystem.write",
            {"path": test_file, "content": "Hello from Capability Bus\nLine 2"},
        )
        assert res_write.success is True
        assert "Successfully wrote" in res_write.output

        # Read
        res_read = capability_bus.execute(
            "filesystem.read",
            {"path": test_file},
        )
        assert res_read.success is True
        assert "Hello from Capability Bus" in res_read.output

    def test_execute_python_capability(self):
        code = "print(sum([1, 2, 3, 4, 5]))"
        res = capability_bus.execute("python.execute", {"code": code})
        assert res.success is True
        assert "15" in res.output.strip()

    def test_bloch_sphere_capability(self):
        res = capability_bus.execute("quantum.bloch_sphere", {"theta": 90.0, "phi": 0.0})
        assert res.success is True
        assert "state_vector" in res.output
        assert "probabilities" in res.output

    def test_honest_health_check_reporting(self):
        report = capability_bus.health_check_all()
        assert "filesystem.read" in report
        assert report["filesystem.read"]["status"] == AvailabilityStatus.AVAILABLE.value
        # No fake status: each cap has a valid string status
        for k, v in report.items():
            assert v["status"] in (
                AvailabilityStatus.AVAILABLE.value,
                AvailabilityStatus.UNAVAILABLE.value,
                AvailabilityStatus.AUTHENTICATION_REQUIRED.value,
                AvailabilityStatus.SOFTWARE_NOT_FOUND.value,
                AvailabilityStatus.LICENSE_REQUIRED.value,
            )

    def test_environment_discovery_real_values(self):
        env = discover_environment()
        assert env.python_version is not None
        assert isinstance(env.git_installed, bool)
        assert isinstance(env.discovered_packages, dict)
        assert "rich" in env.discovered_packages or "textual" in env.discovered_packages
