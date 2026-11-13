"""
CAT Offline Mode & Local AI Engine (v1.0.0)

Ensures robust operation without internet connectivity:
- Real-time online/offline network detection and manual offline override
- Local execution enforcement for code editing, indexing, calculations, documents, and skills
- Native local LLM integration via Ollama with function-calling capability checks
- Explicit connectivity failure messaging and graceful local fallbacks
"""

from __future__ import annotations

import os
import sys
import json
import time
import socket
import urllib.request
import subprocess
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Tuple


@dataclass
class LocalModelInfo:
    name: str
    size_gb: float
    modified_at: str
    supports_tools: bool = False
    parameter_size: str = ""
    family: str = ""


class OfflineManager:
    """Manages offline capability enforcement and local AI runtimes."""

    _instance = None

    def __init__(self):
        self._manual_offline: bool = False
        self._cached_online_state: Optional[bool] = None
        self._last_network_check: float = 0.0
        self.ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    @classmethod
    def get(cls) -> "OfflineManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # =====================================================================
    # Connectivity Detection
    # =====================================================================

    def is_online(self, force_check: bool = False) -> bool:
        if self._manual_offline:
            return False

        now = time.time()
        if not force_check and self._cached_online_state is not None and (now - self._last_network_check < 15.0):
            return self._cached_online_state

        # Socket probe to Cloudflare & Google DNS with short timeout (400ms)
        online = False
        for host, port in [("1.1.1.1", 53), ("8.8.8.8", 53)]:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.4)
                sock.connect((host, port))
                sock.close()
                online = True
                break
            except Exception:
                continue

        self._cached_online_state = online
        self._last_network_check = now
        return online

    def set_offline_mode(self, enabled: bool) -> bool:
        """Manually toggle offline operating mode."""
        self._manual_offline = enabled
        self._cached_online_state = False if enabled else None
        return self._manual_offline

    def is_manual_offline(self) -> bool:
        return self._manual_offline

    # =====================================================================
    # Local Capabilities Inventory
    # =====================================================================

    def get_offline_capabilities(self) -> Dict[str, Any]:
        """List deterministic offline capabilities that function without any cloud dependencies."""
        return {
            "code_editor": "Fully Available (local filesystem syntax highlighting, formatting, ast)",
            "file_explorer": "Fully Available (workspace directory tree, regex search, grep)",
            "mathematics_solver": "Fully Available (SymPy symbolic solving, calculus, matrices)",
            "chemistry_engine": "Fully Available (Bohr simulations, kinetics numericals, orbital density)",
            "office_suite": "Fully Available (docx, xlsx, pptx report generation via local engines)",
            "git_operations": "Fully Available (status, diff, commit, log, branch)",
            "local_skills": "Fully Available (custom skills registered in capability registry)",
            "local_ai": "Available if Ollama service is active on localhost:11434",
            "documentation": "Fully Available (built-in local documentation and cheat sheets)",
        }

    # =====================================================================
    # Local AI (Ollama) Integration
    # =====================================================================

    def check_ollama_service(self) -> Tuple[bool, str]:
        """Check if local Ollama daemon is reachable."""
        try:
            req = urllib.request.Request(f"{self.ollama_host}/api/version", method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    return True, f"Ollama running (version {data.get('version', 'unknown')})"
        except Exception as e:
            return False, f"Ollama service unreachable on {self.ollama_host} ({e})"
        return False, "Ollama service unreachable"

    def list_local_models(self) -> List[LocalModelInfo]:
        """Fetch models installed locally in Ollama."""
        ok, _ = self.check_ollama_service()
        if not ok:
            return []

        models = []
        try:
            req = urllib.request.Request(f"{self.ollama_host}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode())
                for item in data.get("models", []):
                    name = item.get("name", "")
                    size_b = item.get("size", 0)
                    size_gb = round(size_b / (1024 ** 3), 2)
                    details = item.get("details", {})
                    family = details.get("family", "")
                    param_size = details.get("parameter_size", "")

                    # Check function-calling support based on known model architectures
                    low_name = name.lower()
                    supports_tools = any(kw in low_name for kw in ("llama3.1", "llama3.2", "llama3.3", "qwen2.5", "mistral", "hermes", "deepseek-coder"))

                    models.append(
                        LocalModelInfo(
                            name=name,
                            size_gb=size_gb,
                            modified_at=item.get("modified_at", "")[:10],
                            supports_tools=supports_tools,
                            parameter_size=param_size,
                            family=family,
                        )
                    )
        except Exception:
            pass
        return models

    def test_local_model(self, model_name: str) -> Dict[str, Any]:
        """Test a local model with a simple prompt to verify latency and capability."""
        ok, msg = self.check_ollama_service()
        if not ok:
            return {"success": False, "error": msg}

        payload = {
            "model": model_name,
            "prompt": "Reply with 'OK' if you can read this.",
            "stream": False,
        }
        start = time.time()
        try:
            req = urllib.request.Request(
                f"{self.ollama_host}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                duration_ms = round((time.time() - start) * 1000.0, 1)
                data = json.loads(resp.read().decode())
                return {
                    "success": True,
                    "model": model_name,
                    "duration_ms": duration_ms,
                    "response": data.get("response", "").strip(),
                }
        except Exception as e:
            return {"success": False, "model": model_name, "error": str(e)}

    def get_status(self) -> Dict[str, Any]:
        online = self.is_online()
        ollama_ok, ollama_msg = self.check_ollama_service()
        local_models = self.list_local_models() if ollama_ok else []

        return {
            "network_status": "offline" if not online else "online",
            "manual_offline_forced": self._manual_offline,
            "ollama_available": ollama_ok,
            "ollama_status": ollama_msg,
            "local_models_count": len(local_models),
            "tool_capable_models": [m.name for m in local_models if m.supports_tools],
        }


offline_manager = OfflineManager.get()

