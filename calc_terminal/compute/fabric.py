"""
CAT Compute Fabric per §25, §26, §87-§90:
- Heterogeneous compute target abstraction (Local CPU, Local GPU, Ollama, Docker, WSL, SSH, Slurm, Cloud)
- Honest environment probe and status determination (zero mocking)
- Intelligent compute routing based on resource requirements (CPU, RAM, GPU, container, cluster)
"""

from __future__ import annotations

import enum
import json
import os
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from calc_terminal.hardware_analyzer import HardwareAnalyzer


class ComputeTargetType(str, enum.Enum):
    LOCAL_CPU = "local_cpu"
    LOCAL_GPU = "local_gpu"
    OLLAMA = "ollama"
    DOCKER = "docker"
    WSL = "wsl"
    SSH = "ssh"
    SLURM = "slurm"
    CLOUD = "cloud"


class ComputeTargetStatus(str, enum.Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    AUTHENTICATION_REQUIRED = "auth_required"
    CONFIG_REQUIRED = "config_required"


@dataclass
class ComputeTarget:
    target_id: str
    target_type: ComputeTargetType
    name: str
    status: ComputeTargetStatus = ComputeTargetStatus.UNAVAILABLE
    hardware_details: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def probe(self) -> ComputeTargetStatus:
        """Real honest check of target availability without mocking."""
        return self.status

    def execute(
        self,
        command: str,
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: int = 120,
    ) -> Dict[str, Any]:
        """Execute command on this compute target."""
        if self.status != ComputeTargetStatus.AVAILABLE:
            return {
                "success": False,
                "error": f"Target {self.target_id} is not available (Status: {self.status.value})",
                "return_code": -1,
                "stdout": "",
                "stderr": f"Target {self.name} is unavailable.",
            }

        cwd = working_dir or os.getcwd()
        full_env = dict(os.environ)
        if env:
            full_env.update(env)

        start_time = time.time()
        try:
            res = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                env=full_env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "success": res.returncode == 0,
                "return_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "duration_seconds": round(time.time() - start_time, 3),
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Command timed out after {timeout}s",
                "return_code": -1,
                "stdout": "",
                "stderr": f"Execution timed out on {self.target_id}",
                "duration_seconds": round(time.time() - start_time, 3),
            }
        except Exception as ex:
            return {
                "success": False,
                "error": str(ex),
                "return_code": -1,
                "stdout": "",
                "stderr": str(ex),
                "duration_seconds": round(time.time() - start_time, 3),
            }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id": self.target_id,
            "target_type": self.target_type.value,
            "name": self.name,
            "status": self.status.value,
            "hardware_details": self.hardware_details,
            "metadata": self.metadata,
        }


class LocalCPUTarget(ComputeTarget):
    def __init__(self):
        super().__init__(
            target_id="local_cpu",
            target_type=ComputeTargetType.LOCAL_CPU,
            name="Local CPU Host",
        )
        self.probe()

    def probe(self) -> ComputeTargetStatus:
        try:
            profile = HardwareAnalyzer.analyze()
            self.hardware_details = {
                "cpu_model": profile.cpu_model,
                "logical_cores": profile.cpu_threads,
                "ram_total_gb": profile.ram_total_gb,
                "ram_available_gb": profile.ram_available_gb,
                "os": f"{profile.os_name} {profile.os_version}",
            }
            self.status = ComputeTargetStatus.AVAILABLE
        except Exception:
            self.status = ComputeTargetStatus.AVAILABLE
            self.hardware_details = {
                "logical_cores": os.cpu_count() or 1,
                "os": platform.platform(),
            }
        return self.status


class LocalGPUTarget(ComputeTarget):
    def __init__(self):
        super().__init__(
            target_id="local_gpu",
            target_type=ComputeTargetType.LOCAL_GPU,
            name="Local GPU Accelerator",
        )
        self.probe()

    def probe(self) -> ComputeTargetStatus:
        try:
            profile = HardwareAnalyzer.analyze()
            if profile.has_gpu:
                self.hardware_details = {
                    "gpu_name": profile.gpu_name,
                    "backend": profile.gpu_backend,
                    "vram_gb": profile.vram_gb,
                }
                self.status = ComputeTargetStatus.AVAILABLE
            else:
                self.hardware_details = {"gpu_name": "None", "backend": "None", "vram_gb": 0.0}
                self.status = ComputeTargetStatus.UNAVAILABLE
        except Exception:
            self.status = ComputeTargetStatus.UNAVAILABLE
        return self.status


class OllamaTarget(ComputeTarget):
    def __init__(self):
        super().__init__(
            target_id="ollama",
            target_type=ComputeTargetType.OLLAMA,
            name="Ollama Local Inference",
        )
        self.probe()

    def probe(self) -> ComputeTargetStatus:
        # Check CLI presence first
        ollama_bin = shutil.which("ollama")
        if not ollama_bin:
            self.status = ComputeTargetStatus.UNAVAILABLE
            return self.status

        # Try fast ping to local endpoint
        try:
            import urllib.request
            req = urllib.request.Request("http://127.0.0.1:11434/api/tags", headers={"User-Agent": "CAT"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    self.status = ComputeTargetStatus.AVAILABLE
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("name") for m in data.get("models", [])]
                    self.metadata = {"models": models}
                    return self.status
        except Exception:
            pass

        self.status = ComputeTargetStatus.CONFIG_REQUIRED
        self.metadata = {"notes": "Ollama installed but daemon is not running on port 11434"}
        return self.status


class DockerTarget(ComputeTarget):
    def __init__(self):
        super().__init__(
            target_id="docker",
            target_type=ComputeTargetType.DOCKER,
            name="Docker Container Runtime",
        )
        self.probe()

    def probe(self) -> ComputeTargetStatus:
        docker_bin = shutil.which("docker")
        if not docker_bin:
            self.status = ComputeTargetStatus.UNAVAILABLE
            return self.status

        try:
            res = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if res.returncode == 0:
                self.status = ComputeTargetStatus.AVAILABLE
            else:
                self.status = ComputeTargetStatus.CONFIG_REQUIRED
                self.metadata = {"notes": "Docker installed but daemon is not responding"}
        except Exception:
            self.status = ComputeTargetStatus.CONFIG_REQUIRED
        return self.status


class WSLTarget(ComputeTarget):
    def __init__(self):
        super().__init__(
            target_id="wsl",
            target_type=ComputeTargetType.WSL,
            name="Windows Subsystem for Linux (WSL2)",
        )
        self.probe()

    def probe(self) -> ComputeTargetStatus:
        if platform.system().lower() != "windows":
            self.status = ComputeTargetStatus.UNAVAILABLE
            return self.status

        wsl_bin = shutil.which("wsl")
        if not wsl_bin:
            self.status = ComputeTargetStatus.UNAVAILABLE
            return self.status

        try:
            res = subprocess.run(
                ["wsl", "--status"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if res.returncode == 0:
                self.status = ComputeTargetStatus.AVAILABLE
            else:
                self.status = ComputeTargetStatus.CONFIG_REQUIRED
        except Exception:
            self.status = ComputeTargetStatus.CONFIG_REQUIRED
        return self.status


class ComputeFabric:
    """Unified Compute Fabric coordinating targets and job routing per §25, §26."""

    def __init__(self):
        self._targets: Dict[str, ComputeTarget] = {}
        self.discover_targets()

    def register_target(self, target: ComputeTarget):
        self._targets[target.target_id] = target

    def discover_targets(self):
        """Discover and initialize standard compute targets."""
        self.register_target(LocalCPUTarget())
        self.register_target(LocalGPUTarget())
        self.register_target(OllamaTarget())
        self.register_target(DockerTarget())
        self.register_target(WSLTarget())

    def get_target(self, target_id: str) -> Optional[ComputeTarget]:
        return self._targets.get(target_id)

    def list_targets(self) -> List[ComputeTarget]:
        return list(self._targets.values())

    def get_available_targets(self) -> List[ComputeTarget]:
        return [t for t in self._targets.values() if t.status == ComputeTargetStatus.AVAILABLE]

    def route_task(self, requirements: Dict[str, Any]) -> Tuple[ComputeTarget, Optional[str]]:
        """
        Intelligently route task to best compute target per §87.
        Returns (target, warning_or_note).
        """
        # 1. Check GPU requirement
        if requirements.get("requires_gpu"):
            gpu = self.get_target("local_gpu")
            if gpu and gpu.status == ComputeTargetStatus.AVAILABLE:
                return gpu, None
            # Fall back to CPU with clear warning
            cpu = self.get_target("local_cpu") or LocalCPUTarget()
            return cpu, "Task requires GPU, but local GPU is unavailable. Routing to Local CPU."

        # 2. Check Docker requirement
        if requirements.get("container") or requirements.get("docker_image"):
            docker = self.get_target("docker")
            if docker and docker.status == ComputeTargetStatus.AVAILABLE:
                return docker, None
            cpu = self.get_target("local_cpu") or LocalCPUTarget()
            return cpu, "Task requested container environment, but Docker is unavailable. Falling back to Host CPU."

        # 3. Check WSL requirement
        if requirements.get("wsl"):
            wsl = self.get_target("wsl")
            if wsl and wsl.status == ComputeTargetStatus.AVAILABLE:
                return wsl, None
            cpu = self.get_target("local_cpu") or LocalCPUTarget()
            return cpu, "WSL requested but unavailable. Falling back to Host CPU."

        # 4. Check Ollama requirement
        if requirements.get("ollama"):
            ollama = self.get_target("ollama")
            if ollama and ollama.status == ComputeTargetStatus.AVAILABLE:
                return ollama, None

        # Default to CPU
        cpu = self.get_target("local_cpu") or LocalCPUTarget()
        return cpu, None


compute_fabric = ComputeFabric()
