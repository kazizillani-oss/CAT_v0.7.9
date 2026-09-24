"""
Git Capabilities Adapter:
- git.status
- git.diff
- git.commit
- git.branch
- git.rollback
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Dict, Optional, Tuple

from ..schema import (
    AvailabilityStatus,
    Capability,
    CapabilityCategory,
    CapabilitySpec,
    ExecutionResult,
)


def _check_git_health() -> Tuple[AvailabilityStatus, str]:
    if not shutil.which("git"):
        return AvailabilityStatus.SOFTWARE_NOT_FOUND, "git executable not found on PATH"
    try:
        res = subprocess.run(["git", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3.0)
        if res.returncode == 0:
            return AvailabilityStatus.AVAILABLE, res.stdout.strip()
        return AvailabilityStatus.UNAVAILABLE, res.stderr.strip()
    except Exception as e:
        return AvailabilityStatus.UNAVAILABLE, str(e)


def _run_git(args_list: list[str], cwd: str) -> Tuple[bool, str, str, int]:
    try:
        proc = subprocess.run(
            ["git"] + args_list,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15.0,
        )
        return (proc.returncode == 0), proc.stdout.strip(), proc.stderr.strip(), proc.returncode
    except Exception as e:
        return False, "", str(e), -1


def _status_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    cwd = args.get("cwd", os.getcwd())
    ok, out, err, code = _run_git(["status", "--porcelain", "-b"], cwd)
    if not ok:
        return ExecutionResult(success=False, error=err or "Not a git repository", metadata={"exit_code": code})
    lines = out.splitlines()
    branch = lines[0].replace("## ", "") if lines else ""
    changes = lines[1:] if len(lines) > 1 else []
    return ExecutionResult(
        success=True,
        output=out,
        metadata={"branch": branch, "changed_files_count": len(changes), "changes": changes},
    )


def _diff_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    cwd = args.get("cwd", os.getcwd())
    cached = ["--cached"] if args.get("staged") else []
    file_path = [args["path"]] if args.get("path") else []
    ok, out, err, code = _run_git(["diff"] + cached + file_path, cwd)
    if not ok:
        return ExecutionResult(success=False, error=err, metadata={"exit_code": code})
    return ExecutionResult(success=True, output=out, metadata={"diff_length": len(out)})


def _commit_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    cwd = args.get("cwd", os.getcwd())
    raw_message = args.get("message", "").strip()

    from ...git_sync import stage_intended_files, validate_commit_message

    # Stage intended files if requested
    if args.get("all", True):
        stage_ok, staged_files, stage_err = stage_intended_files(cwd)
        if not stage_ok:
            return ExecutionResult(success=False, error=stage_err or "Failed to stage intended files")
    else:
        staged_files = []

    valid_ok, valid_msg = validate_commit_message(raw_message, staged_files)
    if not valid_ok or not valid_msg:
        return ExecutionResult(success=False, error="Commit message is required and cannot be empty")

    task_id = args.get("task_id", "")
    full_message = f"{valid_msg}\n\nTask-Id: {task_id}" if task_id else valid_msg
    ok, out, err, code = _run_git(["commit", "-m", full_message], cwd)
    if not ok:
        return ExecutionResult(success=False, error=err or out, metadata={"exit_code": code})
    return ExecutionResult(success=True, output=out, metadata={"commit_message": full_message})


def _push_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    cwd = args.get("cwd", os.getcwd())
    remote = args.get("remote", "origin")
    branch = args.get("branch")

    from ...git_sync import push_to_remote
    push_ok, out, err = push_to_remote(cwd, remote=remote, branch=branch)
    if not push_ok:
        return ExecutionResult(success=False, error=err or out or "Git push failed")
    return ExecutionResult(success=True, output=out or "Push completed successfully")


def _publish_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    cwd = args.get("cwd", os.getcwd())
    message = args.get("message")
    remote = args.get("remote", "origin")

    from ...git_sync import sync_and_publish
    rc = sync_and_publish(repo_path=cwd, message=message, remote=remote)
    return ExecutionResult(
        success=(rc == 0),
        output="GitHub update completed" if rc == 0 else "GitHub update failed",
        error=None if rc == 0 else f"Publish workflow failed with exit code {rc}",
        metadata={"exit_code": rc},
    )


def _branch_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    cwd = args.get("cwd", os.getcwd())
    action = args.get("action", "list")
    if action == "list":
        ok, out, err, code = _run_git(["branch", "-a"], cwd)
        return ExecutionResult(success=ok, output=out, error=err if not ok else None)
    elif action == "create":
        name = args.get("name", "")
        if not name:
            return ExecutionResult(success=False, error="Branch name is required")
        ok, out, err, code = _run_git(["checkout", "-b", name], cwd)
        return ExecutionResult(success=ok, output=out, error=err if not ok else None)
    elif action == "switch":
        name = args.get("name", "")
        if not name:
            return ExecutionResult(success=False, error="Branch name is required")
        ok, out, err, code = _run_git(["checkout", name], cwd)
        return ExecutionResult(success=ok, output=out, error=err if not ok else None)
    return ExecutionResult(success=False, error=f"Unknown branch action: {action}")


def _rollback_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    cwd = args.get("cwd", os.getcwd())
    target = args.get("target", "HEAD")
    # Rollback unstaged changes or revert to commit
    if args.get("hard", False):
        ok, out, err, code = _run_git(["reset", "--hard", target], cwd)
    else:
        ok, out, err, code = _run_git(["restore", "."], cwd)
    return ExecutionResult(success=ok, output=out or "Rollback completed", error=err if not ok else None)


def register_git_capabilities(bus):
    bus.register(Capability(
        spec=CapabilitySpec(
            name="git.status",
            version="1.0.0",
            category=CapabilityCategory.GIT,
            description="Get current working directory git status and modified files.",
            input_schema={"cwd": "string?"},
            output_schema={"output": "string", "branch": "string", "changed_files_count": "integer"},
            permissions=["read_workspace"],
            documentation="Inspects repository status using git status --porcelain.",
        ),
        handler=_status_handler,
        health_checker=_check_git_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="git.diff",
            version="1.0.0",
            category=CapabilityCategory.GIT,
            description="Inspect git diff for working tree or staged changes.",
            input_schema={"cwd": "string?", "staged": "boolean?", "path": "string?"},
            output_schema={"output": "string"},
            permissions=["read_workspace"],
            documentation="Generates diff output for current changes.",
        ),
        handler=_diff_handler,
        health_checker=_check_git_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="git.commit",
            version="1.0.0",
            category=CapabilityCategory.GIT,
            description="Create a git commit with provenance task attribution.",
            input_schema={"message": "string?", "all": "boolean?", "task_id": "string?"},
            output_schema={"output": "string"},
            permissions=["modify_git"],
            documentation="Stages and commits changes with validated commit message.",
        ),
        handler=_commit_handler,
        health_checker=_check_git_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="git.push",
            version="1.0.0",
            category=CapabilityCategory.GIT,
            description="Push current branch to remote repository.",
            input_schema={"remote": "string?", "branch": "string?"},
            output_schema={"output": "string"},
            permissions=["modify_git"],
            documentation="Pushes local commits to the remote Git branch.",
        ),
        handler=_push_handler,
        health_checker=_check_git_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="git.publish",
            version="1.0.0",
            category=CapabilityCategory.GIT,
            description="Synchronize, stage, commit, and push changes to GitHub with strict verification.",
            input_schema={"message": "string?", "remote": "string?"},
            output_schema={"output": "string"},
            permissions=["modify_git"],
            documentation="Executes end-to-end Git verification and GitHub publish workflow.",
        ),
        handler=_publish_handler,
        health_checker=_check_git_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="git.branch",
            version="1.0.0",
            category=CapabilityCategory.GIT,
            description="List, create or switch git branches.",
            input_schema={"action": "string", "name": "string?"},
            output_schema={"output": "string"},
            permissions=["modify_git"],
            documentation="Branch management.",
        ),
        handler=_branch_handler,
        health_checker=_check_git_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="git.rollback",
            version="1.0.0",
            category=CapabilityCategory.GIT,
            description="Rollback unstaged changes or revert to checkpoint.",
            input_schema={"target": "string?", "hard": "boolean?"},
            output_schema={"output": "string"},
            permissions=["modify_git"],
            documentation="Reverts modified files.",
        ),
        handler=_rollback_handler,
        health_checker=_check_git_health,
    ))

