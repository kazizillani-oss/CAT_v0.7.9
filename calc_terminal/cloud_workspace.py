"""
CAT Cloud Workspace (v0.7.9 Complete Platform Expansion)

Remote SSH workspace connections, Docker container environment manager,
and cloud profile synchronization.
"""

import os
import subprocess
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

@dataclass
class CloudProfile:
    id: str
    name: str
    host: str
    user: str = "root"
    port: int = 22
    remote_path: str = "/workspace"
    last_connected: Optional[float] = None
    status: str = "configured"  # configured, connected, offline

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CloudWorkspaceManager:
    """Manages remote SSH environments, VPS instances, and Docker containers."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._profiles: Dict[str, CloudProfile] = {}
            cls._instance._storage_path = os.path.expanduser("~/.cat/cloud_profiles.json")
            os.makedirs(os.path.dirname(cls._instance._storage_path), exist_ok=True)
            cls._instance._load_profiles()
            cls._instance._bootstrap_defaults()
        return cls._instance

    def _load_profiles(self):
        if os.path.exists(self._storage_path):
            try:
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    p = CloudProfile(**item)
                    self._profiles[p.id] = p
            except Exception:
                self._profiles = {}

    def _save_profiles(self):
        try:
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump([p.to_dict() for p in self._profiles.values()], f, indent=2)
        except Exception:
            pass

    def _bootstrap_defaults(self):
        if not self._profiles:
            defaults = [
                CloudProfile(id="cloud_dev_vm", name="Dev Linux Box", host="192.168.1.100", user="ubuntu", remote_path="/home/ubuntu/cat-workspace"),
                CloudProfile(id="cloud_gpu_cluster", name="Remote GPU Node", host="gpu-node.internal", user="ai-engineer", remote_path="/workspace/models"),
            ]
            for d in defaults:
                self._profiles[d.id] = d
            self._save_profiles()

    def list_profiles(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self._profiles.values()]

    def add_profile(self, name: str, host: str, user: str = "root", port: int = 22, remote_path: str = "/workspace") -> CloudProfile:
        pid = f"cloud_{name.lower().replace(' ', '_')[:12]}"
        p = CloudProfile(id=pid, name=name, host=host, user=user, port=port, remote_path=remote_path)
        self._profiles[pid] = p
        self._save_profiles()
        return p

    def list_docker_containers(self) -> Dict[str, Any]:
        """Inspect local or remote Docker daemon containers."""
        try:
            res = subprocess.run(["docker", "ps", "-a", "--format", "{{json .}}"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                containers = []
                for line in res.stdout.strip().splitlines():
                    if line.strip():
                        try:
                            containers.append(json.loads(line))
                        except Exception:
                            continue
                return {"available": True, "containers": containers}
            return {"available": False, "error": res.stderr.strip() or "Docker daemon not running"}
        except Exception as e:
            return {"available": False, "error": str(e)}

    def ping_host(self, host: str) -> bool:
        """Lightweight reachability check."""
        try:
            res = subprocess.run(["ping", "-n", "1", "-w", "1000", host], capture_output=True, timeout=2)
            return res.returncode == 0
        except Exception:
            return False


# Global singleton
cloud_workspace = CloudWorkspaceManager()

def get_cloud_workspace() -> CloudWorkspaceManager:
    return cloud_workspace

