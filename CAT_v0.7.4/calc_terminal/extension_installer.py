"""
CAT Extension Installer — GitHub & Package Installation, Validation, and Lifecycle Engine.

Provides secure repository inspection, multi-format manifest validation,
path-traversal protection, compatibility evaluation, scoped permission extraction,
installation into managed locations, and automated subsystem registration.
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import storage

logger = logging.getLogger("cat.extension_installer")

CAT_VERSION = "0.7.9.10"
CUSTOM_EXTENSIONS_DIR = Path.home() / ".cct_extensions"

# Supported manifest file names in priority order
MANIFEST_FILENAMES = [
    "cat-extension.json",
    "cat-skill.json",
    "cat-command.json",
    "cat-integration.json",
    "extension.json",
    "skill.json",
    "command.json",
    "integration.json",
]

# Curated catalogue of verified, supported components
CURATED_CATALOGUE: List[Dict[str, Any]] = [
    {
        "id": "github-issue-investigator",
        "name": "GitHub Issue Investigator",
        "type": "skill",
        "version": "1.1.0",
        "author": "CAT Community",
        "publisher": "CAT Community",
        "description": "Teaches Kitties how to investigate GitHub issues, retrieve comments, and analyze PR diffs.",
        "repo_url": "https://github.com/kazizillani-oss/cat-skills-github-investigator",
        "category": "DevOps",
        "icon": "🐙",
        "permissions": ["read_files", "network"],
        "required_tools": ["fetch_web_page", "read_file"],
        "compatibility": ">=0.7.0",
        "instructions": (
            "When investigating a GitHub issue:\n"
            "1. Fetch the issue description and review labels, milestones, and linked PRs.\n"
            "2. Read the reproduction steps and affected files in the repository.\n"
            "3. Identify the root cause and draft a minimal surgical fix."
        ),
    },
    {
        "id": "git-workflow-pro",
        "name": "Git Workflow Pro",
        "type": "command",
        "version": "1.0.0",
        "author": "CAT Community",
        "publisher": "CAT Community",
        "description": "CLI command 'cat gitflow' for branch hygiene, rebase sanity, and conventional commit reviews.",
        "repo_url": "https://github.com/kazizillani-oss/cat-command-gitflow",
        "command_name": "gitflow",
        "category": "Tools",
        "icon": "🌿",
        "permissions": ["read_files", "shell_commands"],
        "compatibility": ">=0.7.0",
        "usage": "cat gitflow [status|pr-ready|clean]",
    },
    {
        "id": "arxiv-researcher",
        "name": "arXiv Scientific Literature Assistant",
        "type": "skill",
        "version": "1.2.0",
        "author": "CAT Community",
        "publisher": "CAT Community",
        "description": "Teaches Sage and Mira how to query arXiv research preprints, extract equations, and cite DOIs.",
        "repo_url": "https://github.com/kazizillani-oss/cat-skills-arxiv-researcher",
        "category": "Research",
        "icon": "📚",
        "permissions": ["read_files", "network"],
        "required_tools": ["web_search", "fetch_web_page"],
        "compatibility": ">=0.7.0",
        "instructions": (
            "When conducting academic research:\n"
            "1. Search authoritative preprints on arXiv matching the user's research question.\n"
            "2. Extract primary methodology, assumptions, and performance metrics.\n"
            "3. Synthesize findings with explicit citations and paper IDs."
        ),
    },
    {
        "id": "code-quality-auditor",
        "name": "Code Quality & Cyclomatic Auditor",
        "type": "extension",
        "version": "1.0.1",
        "author": "CAT Community",
        "publisher": "CAT Community",
        "description": "Deep AST code audit extension computing complexity metrics and security flaw warnings.",
        "repo_url": "https://github.com/kazizillani-oss/cat-ext-code-auditor",
        "category": "Quality",
        "icon": "🔍",
        "permissions": ["read_files"],
        "compatibility": ">=0.7.0",
    },
]


@dataclass
class InspectionResult:
    valid: bool
    manifest: Dict[str, Any] = field(default_factory=dict)
    component_type: str = "extension"        # "extension" | "skill" | "command" | "integration"
    id: str = ""
    name: str = ""
    version: str = "1.0.0"
    publisher: str = "Unknown"
    published_at: Optional[str] = None
    description: str = ""
    category: str = "General"
    icon: str = "🧩"
    permissions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    compatibility_ok: bool = True
    compatibility_notes: str = ""
    error: Optional[str] = None
    source_url: str = ""
    archive_bytes: Optional[bytes] = None


def parse_github_url(url_or_slug: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Parse a GitHub URL or slug into (owner, repo, branch, subpath).
    Supports:
      - https://github.com/owner/repo
      - https://github.com/owner/repo.git
      - https://github.com/owner/repo/tree/branch/subpath
      - owner/repo
    """
    clean = (url_or_slug or "").strip()
    if not clean:
        return None, None, None, None

    # Slug format: owner/repo
    if re.match(r"^[a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-]+$", clean):
        parts = clean.split("/")
        return parts[0], parts[1], None, None

    # Full GitHub URL
    match = re.match(
        r"^(?:https?://)?github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/tree/([^/]+)(?:/(.+))?)?/?$",
        clean,
        re.IGNORECASE,
    )
    if match:
        owner = match.group(1)
        repo = match.group(2)
        branch = match.group(3)
        subpath = match.group(4)
        return owner, repo, branch, subpath

    return None, None, None, None


def is_safe_relpath(path: str) -> bool:
    """Security check: Prevent path traversal attacks (../, absolute paths, drive letters)."""
    if not path:
        return False
    # Check absolute path
    if os.path.isabs(path) or path.startswith("/") or path.startswith("\\"):
        return False
    # Check Windows drive letters
    if re.match(r"^[a-zA-Z]:", path):
        return False
    # Check traversal segments
    parts = Path(path).parts
    if ".." in parts or "." in parts:
        # Check normalized
        norm = os.path.normpath(path)
        if norm.startswith("..") or "/../" in norm or "\\..\\" in norm:
            return False
    return True


def compare_semver(v1: str, v2: str) -> int:
    """Compare two semantic version strings. Returns: 1 if v1 > v2, -1 if v1 < v2, 0 if equal."""
    def _parse(v: str) -> List[int]:
        clean = re.sub(r"[^0-9.]", "", v).split(".")
        return [int(x) if x.isdigit() else 0 for x in clean]
    
    p1 = _parse(v1)
    p2 = _parse(v2)
    # Pad to equal length
    maxlen = max(len(p1), len(p2))
    p1 += [0] * (maxlen - len(p1))
    p2 += [0] * (maxlen - len(p2))
    
    for a, b in zip(p1, p2):
        if a > b:
            return 1
        elif a < b:
            return -1
    return 0


def check_compatibility(cat_compat: str, target_os: Optional[List[str]] = None) -> Tuple[bool, str]:
    """Check CAT version and host OS compatibility."""
    # Check OS
    if target_os and isinstance(target_os, list):
        current_os = sys.platform
        normalized_os = "windows" if current_os.startswith("win") else "darwin" if current_os.startswith("darwin") else "linux"
        allowed = [x.lower() for x in target_os]
        if normalized_os not in allowed:
            return False, f"Incompatible platform: requires one of {target_os}, current host is '{normalized_os}'."

    # Check CAT version
    if cat_compat and isinstance(cat_compat, str):
        cat_compat = cat_compat.strip()
        m = re.match(r"^(>=|<=|>|<|==)?\s*([0-9.]+)", cat_compat)
        if m:
            op = m.group(1) or ">="
            req_ver = m.group(2)
            cmp = compare_semver(CAT_VERSION, req_ver)
            if op == ">=" and cmp < 0:
                return False, f"Requires CAT version {cat_compat}, current version is {CAT_VERSION}."
            elif op == ">" and cmp <= 0:
                return False, f"Requires CAT version {cat_compat}, current version is {CAT_VERSION}."
            elif op == "==" and cmp != 0:
                return False, f"Requires exact CAT version {req_ver}, current version is {CAT_VERSION}."

    return True, f"Compatible with CAT {CAT_VERSION} on {sys.platform}."


def adapt_manifest(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format Adapter: Normalizes upstream repository manifests into CAT's unified format.
    Handles standard manifests, package.json with 'cat' section, and skill specs.
    """
    manifest = dict(raw)
    
    # If nested under 'cat' or 'cct' key
    if "cat" in manifest and isinstance(manifest["cat"], dict):
        for k, v in manifest["cat"].items():
            manifest.setdefault(k, v)
    elif "cct" in manifest and isinstance(manifest["cct"], dict):
        for k, v in manifest["cct"].items():
            manifest.setdefault(k, v)

    # Normalize ID
    raw_id = manifest.get("id") or manifest.get("name") or ""
    clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "-", str(raw_id).lower().strip())
    manifest["id"] = clean_id

    # Normalize Type
    mtype = str(manifest.get("type", "")).lower().strip()
    if not mtype:
        if "instructions" in manifest or "required_tools" in manifest:
            mtype = "skill"
        elif "command_name" in manifest or "usage" in manifest or "args_spec" in manifest:
            mtype = "command"
        elif "capabilities" in manifest or "auth_type" in manifest:
            mtype = "integration"
        else:
            mtype = "extension"
    manifest["type"] = mtype

    # Normalize Name
    if not manifest.get("display_name"):
        manifest["display_name"] = manifest.get("name") or clean_id.title()
    manifest["name"] = manifest["display_name"]

    # Normalize Publisher / Author
    author = manifest.get("author") or manifest.get("publisher") or "Unknown"
    manifest["publisher"] = author
    manifest["author"] = author

    # Normalize Version
    if not manifest.get("version") or not re.match(r"^\d+\.\d+\.\d+", str(manifest.get("version"))):
        manifest["version"] = "1.0.0"

    # Normalize Permissions
    perms = manifest.get("permissions") or manifest.get("permission_scope") or []
    if isinstance(perms, dict):
        perms = [k for k, v in perms.items() if v]
    manifest["permissions"] = list(perms)

    # Normalize Dependencies
    deps = manifest.get("dependencies") or []
    if isinstance(deps, dict):
        deps = list(deps.keys())
    manifest["dependencies"] = list(deps)

    return manifest


def inspect_repository(url_or_slug: str, mock_data: Optional[Dict[str, Any]] = None) -> InspectionResult:
    """
    Step 1-6: Inspect a GitHub repository or catalogue item without running untrusted code.
    Extracts manifest, validates compatibility, permissions, dependencies.
    """
    clean_url = (url_or_slug or "").strip()
    if not clean_url:
        return InspectionResult(valid=False, error="Repository URL or slug cannot be empty.")

    # 1. Check curated catalogue first
    for item in CURATED_CATALOGUE:
        if clean_url in (item["id"], item.get("repo_url"), item["name"]):
            manifest = adapt_manifest(item)
            compat_ok, compat_notes = check_compatibility(manifest.get("compatibility", ""))
            return InspectionResult(
                valid=True,
                manifest=manifest,
                component_type=manifest["type"],
                id=manifest["id"],
                name=manifest["name"],
                version=manifest["version"],
                publisher=manifest["publisher"],
                published_at=manifest.get("published_at"),
                description=manifest.get("description", ""),
                category=manifest.get("category", "General"),
                icon=manifest.get("icon", "🧩"),
                permissions=manifest.get("permissions", []),
                dependencies=manifest.get("dependencies", []),
                compatibility_ok=compat_ok,
                compatibility_notes=compat_notes,
                source_url=item.get("repo_url", clean_url),
            )

    # 2. If mock data is provided (for testing / simulated repositories)
    if mock_data is not None:
        manifest = adapt_manifest(mock_data)
        compat_ok, compat_notes = check_compatibility(
            manifest.get("compatibility", ""),
            manifest.get("platforms"),
        )
        return InspectionResult(
            valid=True,
            manifest=manifest,
            component_type=manifest["type"],
            id=manifest["id"],
            name=manifest["name"],
            version=manifest["version"],
            publisher=manifest["publisher"],
            published_at=manifest.get("published_at"),
            description=manifest.get("description", ""),
            category=manifest.get("category", "General"),
            icon=manifest.get("icon", "🧩"),
            permissions=manifest.get("permissions", []),
            dependencies=manifest.get("dependencies", []),
            compatibility_ok=compat_ok,
            compatibility_notes=compat_notes,
            source_url=clean_url,
        )

    # 3. Parse GitHub URL
    owner, repo, branch, subpath = parse_github_url(clean_url)
    if not owner or not repo:
        return InspectionResult(
            valid=False,
            error=f"Invalid GitHub repository URL or slug: '{clean_url}'. Expected format: 'owner/repo' or 'https://github.com/owner/repo'",
        )

    branch = branch or "main"
    raw_base = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}"
    if subpath:
        raw_base += f"/{subpath.strip('/')}"

    manifest = None
    manifest_source = None

    # Probe raw manifests sequentially without downloading full zip
    for mfile in MANIFEST_FILENAMES:
        raw_url = f"{raw_base}/{mfile}"
        try:
            req = urllib.request.Request(raw_url, headers={"User-Agent": f"CAT-CLI/{CAT_VERSION}"})
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                if resp.status == 200:
                    data = resp.read().decode("utf-8")
                    manifest = json.loads(data)
                    manifest_source = raw_url
                    break
        except Exception:
            continue

    if not manifest:
        # Fallback to 'master' branch if 'main' yielded 404
        if branch == "main":
            raw_base_master = f"https://raw.githubusercontent.com/{owner}/{repo}/master"
            if subpath:
                raw_base_master += f"/{subpath.strip('/')}"
            for mfile in MANIFEST_FILENAMES:
                raw_url = f"{raw_base_master}/{mfile}"
                try:
                    req = urllib.request.Request(raw_url, headers={"User-Agent": f"CAT-CLI/{CAT_VERSION}"})
                    with urllib.request.urlopen(req, timeout=8.0) as resp:
                        if resp.status == 200:
                            data = resp.read().decode("utf-8")
                            manifest = json.loads(data)
                            manifest_source = raw_url
                            branch = "master"
                            break
                except Exception:
                    continue

    if not manifest:
        return InspectionResult(
            valid=False,
            error=(
                f"No supported CAT manifest found in '{owner}/{repo}'. "
                f"Repository must include one of: {', '.join(MANIFEST_FILENAMES)}"
            ),
            source_url=clean_url,
        )

    manifest = adapt_manifest(manifest)
    compat_ok, compat_notes = check_compatibility(
        manifest.get("compatibility", ""),
        manifest.get("platforms"),
    )

    return InspectionResult(
        valid=True,
        manifest=manifest,
        component_type=manifest["type"],
        id=manifest["id"],
        name=manifest["name"],
        version=manifest["version"],
        publisher=manifest["publisher"],
        published_at=manifest.get("published_at"),
        description=manifest.get("description", ""),
        category=manifest.get("category", "General"),
        icon=manifest.get("icon", "🧩"),
        permissions=manifest.get("permissions", []),
        dependencies=manifest.get("dependencies", []),
        compatibility_ok=compat_ok,
        compatibility_notes=compat_notes,
        source_url=f"https://github.com/{owner}/{repo}",
    )


def install_from_zip(
    zip_bytes: bytes,
    inspection: InspectionResult,
    target_dir: Optional[Path] = None,
) -> Tuple[bool, str]:
    """
    Step 7-10: Safely extract zip archive with path traversal checks,
    install to managed directory, and register in subsystem.
    """
    comp_id = inspection.id
    if not comp_id:
        return False, "Component ID cannot be empty."

    dest_dir = target_dir or (CUSTOM_EXTENSIONS_DIR / comp_id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            # First pass: validate all archive paths for traversal safety
            for member in zf.infolist():
                filename = member.filename
                # Strip root directory prefix if zip contains a single top-level folder
                parts = Path(filename).parts
                if not parts:
                    continue
                # If first part is a top-level folder name (common in GitHub tarballs/zips)
                if len(parts) > 1:
                    clean_subpath = os.path.join(*parts[1:])
                else:
                    clean_subpath = parts[0]

                if not is_safe_relpath(clean_subpath):
                    return False, f"SECURITY REJECTION: Malicious path traversal detected in archive: '{filename}'"

            # Second pass: safe extraction
            for member in zf.infolist():
                if member.is_dir():
                    continue
                parts = Path(member.filename).parts
                if len(parts) > 1:
                    rel_dest = Path(*parts[1:])
                else:
                    rel_dest = Path(parts[0])

                out_path = dest_dir / rel_dest
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(out_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)

        # Write canonical manifest.json
        with open(dest_dir / "extension.json", "w", encoding="utf-8") as f:
            json.dump(inspection.manifest, f, indent=2)

        return True, f"Extracted to {dest_dir}"
    except Exception as e:
        # Cleanup failed extraction
        shutil.rmtree(dest_dir, ignore_errors=True)
        return False, f"Installation extraction failed: {e}"


def register_component_in_subsystems(inspection: InspectionResult, comp_dir: Path) -> Tuple[bool, str]:
    """
    Step 8-9: Registers the installed component in its target CAT subsystem:
      - Skill -> SkillRegistry (immediately discoverable by Kitties)
      - Command -> CustomCommandRegistry (immediately discoverable by CLI)
      - Integration -> IntegrationRegistry
      - Extension -> extensions.py registry
    """
    m = inspection.manifest
    cid = inspection.id
    ctype = inspection.component_type

    # 1. Register in SkillRegistry if it's a Skill
    if ctype == "skill":
        try:
            from .skills.registry import get_skill_registry
            from .skills.skill_model import SkillDefinition

            perm_scope = {}
            for p in inspection.permissions:
                perm_scope[p] = True

            skill_def = SkillDefinition(
                id=cid,
                name=inspection.name,
                version=inspection.version,
                description=inspection.description,
                category=inspection.category.lower(),
                required_tools=m.get("required_tools", []),
                permission_scope=perm_scope,
                instructions=m.get("instructions", ""),
                tags=m.get("tags", [inspection.category.lower()]),
                enabled=True,
                builtin=False,
            )
            reg = get_skill_registry()
            ok, err = reg.register(skill_def, persist=True)
            if not ok:
                return False, f"Failed to register Skill with Kitty runtime: {err}"
        except Exception as e:
            return False, f"Error registering Skill with Kitty runtime: {e}"

    # 2. Register in CustomCommandRegistry if it's a Command
    elif ctype == "command":
        try:
            from .commands_registry import get_command_registry, CommandSpec

            cmd_name = m.get("command_name") or cid
            cmd_spec = CommandSpec(
                id=cid,
                name=cmd_name,
                description=inspection.description,
                extension_id=cid,
                usage=m.get("usage", f"cat {cmd_name}"),
                args_spec=m.get("args_spec", []),
                script_path=str(comp_dir / f"{cmd_name}.py") if (comp_dir / f"{cmd_name}.py").exists() else None,
                permissions=inspection.permissions,
                enabled=True,
                builtin=False,
            )
            cmd_reg = get_command_registry()
            ok, err = cmd_reg.register(cmd_spec, persist=True)
            if not ok:
                return False, f"Failed to register custom command: {err}"
        except Exception as e:
            return False, f"Error registering custom command: {e}"

    # 3. Register in extensions.py source-of-truth registry
    try:
        from . import extensions as ext_mgr
        data = ext_mgr._load_registry()
        data[cid] = {
            "installed": True,
            "enabled": True,
            "version": inspection.version,
            "install_time": time.time(),
            "published_at": inspection.published_at,
            "type": ctype,
            "source": inspection.source_url,
            "permissions": inspection.permissions,
            "dependencies": inspection.dependencies,
            "size_bytes": ext_mgr._calc_size([comp_dir]) if comp_dir.exists() else 1024 * 50,
            "manifest": m,
        }
        ext_mgr._save_registry(data)
    except Exception as e:
        return False, f"Failed to record extension in registry: {e}"

    return True, f"✓ Successfully registered {ctype} '{inspection.name}' in CAT subsystems."


def check_for_updates(extension_id: str) -> Tuple[bool, str, str, Dict[str, Any]]:
    """
    Check for component updates without downloading or executing code.
    Returns: (update_available, current_version, latest_version, details)
    """
    from . import extensions as ext_mgr

    meta = ext_mgr.get_metadata(extension_id)
    if not meta:
        return False, "", "", {"error": f"Extension '{extension_id}' not found."}

    current_ver = meta.get("version", "1.0.0")
    source_url = meta.get("install_source") or meta.get("source") or ""

    # Check curated catalogue first
    for item in CURATED_CATALOGUE:
        if item["id"] == extension_id:
            cat_ver = item.get("version", "1.0.0")
            has_update = compare_semver(cat_ver, current_ver) > 0
            return has_update, current_ver, cat_ver, {
                "source": "curated_catalogue",
                "notes": f"New version {cat_ver} available in curated catalogue.",
            }

    # If GitHub URL, inspect repository manifest remotely
    if source_url and "github.com" in source_url:
        try:
            insp = inspect_repository(source_url)
            if insp.valid and insp.version:
                has_update = compare_semver(insp.version, current_ver) > 0
                return has_update, current_ver, insp.version, {
                    "source": source_url,
                    "published_at": insp.published_at,
                    "notes": f"Latest remote version is {insp.version}.",
                }
        except Exception as e:
            return False, current_ver, current_ver, {"error": f"Failed to check updates: {e}"}

    return False, current_ver, current_ver, {"notes": "Already up to date."}
