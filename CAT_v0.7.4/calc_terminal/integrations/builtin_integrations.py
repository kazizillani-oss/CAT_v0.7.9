"""
CAT Integrations — Built-in Integration Profiles & Live Status Probers.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Dict, List
from .models import (
    IntegrationSpec,
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    STATE_NEEDS_AUTH,
    STATE_UNAVAILABLE,
    STATE_ERROR,
)


def probe_openai() -> tuple[str, str]:
    from .. import aicore
    cfg = aicore.load_config() or {}
    key = os.environ.get("OPENAI_API_KEY") or cfg.get("openai_key")
    if key and len(key) > 5:
        return STATE_CONNECTED, "API Key detected in environment"
    return STATE_NEEDS_AUTH, "OPENAI_API_KEY not configured"


def probe_gemini() -> tuple[str, str]:
    from .. import aicore
    cfg = aicore.load_config() or {}
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or cfg.get("gemini_key")
    if key and len(key) > 5:
        return STATE_CONNECTED, "API Key detected in environment"
    return STATE_NEEDS_AUTH, "GEMINI_API_KEY not configured"


def probe_xai() -> tuple[str, str]:
    from .. import aicore
    cfg = aicore.load_config() or {}
    key = os.environ.get("XAI_API_KEY") or cfg.get("xai_key")
    if key and len(key) > 5:
        return STATE_CONNECTED, "xAI API Key detected in environment"
    return STATE_NEEDS_AUTH, "XAI_API_KEY not configured"


def probe_ollama() -> tuple[str, str]:
    from ..ollama_catalog import is_ollama_running
    try:
        if is_ollama_running(timeout=0.6):
            return STATE_CONNECTED, "Ollama daemon reachable on localhost:11434"
        return STATE_DISCONNECTED, "Ollama service offline"
    except Exception:
        return STATE_DISCONNECTED, "Ollama not running"


def probe_github() -> tuple[str, str]:
    try:
        from ..git_sync import inspect_repository
        repo = inspect_repository()
        if repo.is_repo and repo.remote_url:
            return STATE_CONNECTED, f"Git remote: {repo.remote_url}"
        if shutil.which("gh"):
            return STATE_CONNECTED, "GitHub CLI (gh) installed"
        if repo.is_repo:
            return STATE_DISCONNECTED, "Git repo initialized without remote"
        return STATE_DISCONNECTED, "No git repository active"
    except Exception as e:
        return STATE_ERROR, str(e)


def probe_gitlab() -> tuple[str, str]:
    token = os.environ.get("GITLAB_TOKEN")
    if token:
        return STATE_CONNECTED, "GitLab token configured"
    return STATE_DISCONNECTED, "Not configured"


def probe_docker() -> tuple[str, str]:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return STATE_UNAVAILABLE, "Docker CLI not found on PATH"
    try:
        res = subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.5)
        if res.returncode == 0:
            return STATE_CONNECTED, "Docker daemon active"
        return STATE_DISCONNECTED, "Docker installed but daemon not running"
    except Exception:
        return STATE_DISCONNECTED, "Docker command timed out"


def probe_jupyter() -> tuple[str, str]:
    try:
        import jupyter_core
        return STATE_CONNECTED, "Jupyter core installed"
    except ImportError:
        try:
            import IPython
            return STATE_CONNECTED, "IPython environment available"
        except ImportError:
            return STATE_UNAVAILABLE, "Jupyter / IPython not installed in active Python environment"


def probe_colab() -> tuple[str, str]:
    if "COLAB_GPU" in os.environ or "google.colab" in os.environ:
        return STATE_CONNECTED, "Running inside Google Colab environment"
    return STATE_DISCONNECTED, "Not in Colab runtime"


def probe_kaggle() -> tuple[str, str]:
    if os.path.isfile(os.path.expanduser("~/.kaggle/kaggle.json")) or os.environ.get("KAGGLE_KEY"):
        return STATE_CONNECTED, "Kaggle credentials detected"
    return STATE_DISCONNECTED, "Kaggle credentials not configured"


def probe_mcp() -> tuple[str, str]:
    try:
        from .. import mcp
        servers = mcp.load_servers()
        if servers:
            enabled = sum(1 for s in servers if s.get("enabled"))
            return STATE_CONNECTED, f"{enabled}/{len(servers)} MCP servers active"
        return STATE_DISCONNECTED, "No MCP servers configured"
    except Exception:
        return STATE_ERROR, "Error reading MCP configuration"


def probe_browser() -> tuple[str, str]:
    try:
        import PySide6
        return STATE_CONNECTED, "PySide6 Qt WebEngine browser engine ready"
    except ImportError:
        return STATE_UNAVAILABLE, "PySide6 not installed (pip install PySide6)"


def probe_database() -> tuple[str, str]:
    import sqlite3
    return STATE_CONNECTED, "SQLite native engine ready"


BUILTIN_INTEGRATIONS_DEFS = [
    # AI Providers
    {
        "id": "openai",
        "name": "OpenAI",
        "category": "ai_providers",
        "description": "GPT-4o, o1, o3-mini & embeddings via OpenAI official API.",
        "icon": "⚡",
        "capabilities": ["text", "code", "reasoning", "tools", "vision"],
        "auth_type": "token",
        "prober": probe_openai,
    },
    {
        "id": "gemini",
        "name": "Google Gemini",
        "category": "ai_providers",
        "description": "Gemini 2.5, 2.0 Flash, 1.5 Pro via Google AI official API.",
        "icon": "✨",
        "capabilities": ["text", "code", "long_context", "multimodal", "tools"],
        "auth_type": "token",
        "prober": probe_gemini,
    },
    {
        "id": "xai",
        "name": "xAI (Grok)",
        "category": "ai_providers",
        "description": "Grok models via xAI official API endpoint.",
        "icon": "🤖",
        "capabilities": ["text", "code", "reasoning", "tools"],
        "auth_type": "token",
        "prober": probe_xai,
    },
    {
        "id": "ollama",
        "name": "Ollama (Local)",
        "category": "ai_providers",
        "description": "Local privacy-first open models (Llama 3, Qwen, DeepSeek) on localhost:11434.",
        "icon": "🦙",
        "capabilities": ["local_first", "offline", "text", "code"],
        "auth_type": "url",
        "prober": probe_ollama,
    },

    # Development
    {
        "id": "github",
        "name": "GitHub",
        "category": "development",
        "description": "Repository management, commits, pull requests, and git sync.",
        "icon": "🐙",
        "capabilities": ["git", "sync", "commits", "branches"],
        "auth_type": "cli",
        "prober": probe_github,
    },
    {
        "id": "gitlab",
        "name": "GitLab",
        "category": "development",
        "description": "GitLab repositories, CI/CD pipelines, and merge requests.",
        "icon": "🦊",
        "capabilities": ["git", "sync", "ci_cd"],
        "auth_type": "token",
        "prober": probe_gitlab,
    },
    {
        "id": "docker",
        "name": "Docker",
        "category": "development",
        "description": "Container management, image building, and isolated environment execution.",
        "icon": "🐳",
        "capabilities": ["containers", "isolation", "build"],
        "auth_type": "cli",
        "prober": probe_docker,
    },

    # Research
    {
        "id": "jupyter",
        "name": "Jupyter",
        "category": "research",
        "description": "Interactive notebook computation and execution kernels.",
        "icon": "🪐",
        "capabilities": ["notebook", "kernels", "execution"],
        "auth_type": "none",
        "prober": probe_jupyter,
    },
    {
        "id": "colab",
        "name": "Google Colab",
        "category": "research",
        "description": "Cloud notebook runtime integration.",
        "icon": "🔬",
        "capabilities": ["cloud_execution", "gpu"],
        "auth_type": "url",
        "prober": probe_colab,
    },
    {
        "id": "kaggle",
        "name": "Kaggle",
        "category": "research",
        "description": "Kaggle dataset retrieval and competition notebooks.",
        "icon": "📊",
        "capabilities": ["datasets", "competitions"],
        "auth_type": "token",
        "prober": probe_kaggle,
    },

    # Tools
    {
        "id": "mcp",
        "name": "MCP (Model Context Protocol)",
        "category": "tools",
        "description": "Extensible local and remote MCP tool & resource servers.",
        "icon": "🧩",
        "capabilities": ["tools", "resources", "rpc"],
        "auth_type": "url",
        "prober": probe_mcp,
    },
    {
        "id": "browser",
        "name": "CAT Browser",
        "category": "tools",
        "description": "Embedded Chromium / Qt WebEngine browser for live web pages.",
        "icon": "🌐",
        "capabilities": ["rendering", "dom", "automation"],
        "auth_type": "none",
        "prober": probe_browser,
    },
    {
        "id": "database",
        "name": "Database (SQLite)",
        "category": "tools",
        "description": "Local embedded database storage & SQL engine.",
        "icon": "🗄️",
        "capabilities": ["sql", "persistence", "queries"],
        "auth_type": "none",
        "prober": probe_database,
    },
]
