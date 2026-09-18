"""
Platforms Capabilities Adapter per §40, §41, §42:
- kaggle.dataset
- huggingface.model
- github.repository
- gitlab.repository
"""

from __future__ import annotations

import json
import os
import shutil
import urllib.request
import urllib.parse
from typing import Any, Dict, Optional, Tuple

from ..schema import (
    AvailabilityStatus,
    Capability,
    CapabilityCategory,
    CapabilitySpec,
    ExecutionResult,
)


def _check_kaggle_health() -> Tuple[AvailabilityStatus, str]:
    has_key = bool(os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"))
    kaggle_json = os.path.expanduser(os.path.join("~", ".kaggle", "kaggle.json"))
    if has_key or os.path.exists(kaggle_json):
        return AvailabilityStatus.AVAILABLE, "Kaggle credentials configured"
    return AvailabilityStatus.AUTHENTICATION_REQUIRED, "Kaggle credentials not found (set KAGGLE_USERNAME/KAGGLE_KEY or ~/.kaggle/kaggle.json)"


def _check_hf_health() -> Tuple[AvailabilityStatus, str]:
    has_token = bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"))
    hf_token_file = os.path.expanduser(os.path.join("~", ".cache", "huggingface", "token"))
    if has_token or os.path.exists(hf_token_file):
        return AvailabilityStatus.AVAILABLE, "Hugging Face authenticated"
    return AvailabilityStatus.AVAILABLE, "Hugging Face public read available (unauthenticated)"


def _check_github_health() -> Tuple[AvailabilityStatus, str]:
    if shutil.which("gh"):
        return AvailabilityStatus.AVAILABLE, "GitHub CLI (gh) installed and available"
    if os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"):
        return AvailabilityStatus.AVAILABLE, "GITHUB_TOKEN configured"
    return AvailabilityStatus.AVAILABLE, "GitHub public repository access available"


def _kaggle_dataset_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    dataset_name = args.get("dataset", "")
    if not dataset_name:
        return ExecutionResult(success=False, error="dataset argument is required (e.g. 'owner/dataset-name')")

    status, msg = _check_kaggle_health()
    if status == AvailabilityStatus.AUTHENTICATION_REQUIRED:
        return ExecutionResult(
            success=False,
            error=f"Authentication required for Kaggle: {msg}",
            status=status,
        )

    # If kaggle package is installed, query via official API
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
        action = args.get("action", "metadata")
        if action == "download":
            dest = args.get("destination", ".")
            api.dataset_download_files(dataset_name, path=dest, unzip=True)
            return ExecutionResult(success=True, output=f"Downloaded dataset {dataset_name} to {dest}")
        else:
            files = api.dataset_list_files(dataset_name)
            return ExecutionResult(success=True, output={"dataset": dataset_name, "files": [f.name for f in files.files]})
    except ImportError:
        # Fallback to kaggle CLI if present
        if shutil.which("kaggle"):
            import subprocess
            proc = subprocess.run(["kaggle", "datasets", "files", dataset_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15.0)
            return ExecutionResult(success=(proc.returncode == 0), output=proc.stdout, error=proc.stderr if proc.returncode != 0 else None)
        return ExecutionResult(success=False, error="kaggle python package or CLI not installed (run: pip install kaggle)", status=AvailabilityStatus.SOFTWARE_NOT_FOUND)
    except Exception as e:
        return ExecutionResult(success=False, error=f"Kaggle API error: {e}")


def _hf_model_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    model_id = args.get("model_id", "")
    if not model_id:
        return ExecutionResult(success=False, error="model_id is required (e.g. 'meta-llama/Llama-3.2-1B')")

    try:
        # Query public Hugging Face API
        url = f"https://huggingface.co/api/models/{urllib.parse.quote(model_id, safe='/')}"
        headers = {"User-Agent": "CAT-AI-Platform/1.0"}
        token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        summary = {
            "id": data.get("id"),
            "author": data.get("author"),
            "downloads": data.get("downloads"),
            "likes": data.get("likes"),
            "pipeline_tag": data.get("pipeline_tag"),
            "tags": data.get("tags", [])[:10],
            "sha": data.get("sha"),
        }
        return ExecutionResult(success=True, output=summary, metadata=summary)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return ExecutionResult(success=False, error=f"Access denied for model '{model_id}'. Hugging Face token required.", status=AvailabilityStatus.AUTHENTICATION_REQUIRED)
        if e.code == 404:
            return ExecutionResult(success=False, error=f"Hugging Face model '{model_id}' not found.")
        return ExecutionResult(success=False, error=f"Hugging Face API HTTP error: {e}")
    except Exception as e:
        return ExecutionResult(success=False, error=f"Hugging Face query failed: {e}")


def _github_repo_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    repo = args.get("repo", "")
    if not repo:
        return ExecutionResult(success=False, error="repo argument is required (e.g. 'owner/repo')")

    try:
        url = f"https://api.github.com/repos/{urllib.parse.quote(repo, safe='/')}"
        headers = {"User-Agent": "CAT-AI-Platform/1.0"}
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        info = {
            "name": data.get("full_name"),
            "description": data.get("description"),
            "stars": data.get("stargazers_count"),
            "forks": data.get("forks_count"),
            "open_issues": data.get("open_issues_count"),
            "default_branch": data.get("default_branch"),
            "clone_url": data.get("clone_url"),
        }
        return ExecutionResult(success=True, output=info, metadata=info)
    except Exception as e:
        return ExecutionResult(success=False, error=f"GitHub API query error: {e}")


def register_platform_capabilities(bus):
    bus.register(Capability(
        spec=CapabilitySpec(
            name="kaggle.dataset",
            version="1.0.0",
            category=CapabilityCategory.PLATFORMS,
            description="Inspect metadata or download datasets from Kaggle.",
            input_schema={"dataset": "string", "action": "string?", "destination": "string?"},
            output_schema={"output": "any"},
            auth_required=True,
            permissions=["read_workspace", "modify_files"],
            documentation="Connects to Kaggle using user credentials.",
        ),
        handler=_kaggle_dataset_handler,
        health_checker=_check_kaggle_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="huggingface.model",
            version="1.0.0",
            category=CapabilityCategory.PLATFORMS,
            description="Query Hugging Face model metadata, tags, pipeline types and downloads.",
            input_schema={"model_id": "string"},
            output_schema={"output": "object"},
            permissions=["read_workspace"],
            documentation="Queries Hugging Face hub API.",
        ),
        handler=_hf_model_handler,
        health_checker=_check_hf_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="github.repository",
            version="1.0.0",
            category=CapabilityCategory.PLATFORMS,
            description="Inspect GitHub repository information, metadata, branches and clone URL.",
            input_schema={"repo": "string"},
            output_schema={"output": "object"},
            permissions=["read_workspace"],
            documentation="Queries GitHub API v3.",
        ),
        handler=_github_repo_handler,
        health_checker=_check_github_health,
    ))
