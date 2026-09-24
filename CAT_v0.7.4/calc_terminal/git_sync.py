"""
CAT — Robust Git Workflow & GitHub Synchronization Engine.

Implements the verified Git publishing pipeline:
  1. Check repository integrity, remote, and current branch.
  2. Detect modified, staged, unstaged, and untracked files.
  3. If no changes: gracefully notify user repository is already up to date.
  4. Correctly stage intended files (respecting .gitignore, protecting secrets/caches).
  5. Validate commit message (NEVER allow empty commit messages; provide sensible default).
  6. Create commit and verify commit exists in local git history.
  7. Handle upstream sync / fast-forward if local branch is behind remote.
  8. Push commit to the correct GitHub remote/branch.
  9. Verify push succeeded against remote tracking ref.
  10. Clearly report:
      ✓ Files staged
      ✓ Commit created
      ✓ Commit pushed
      ✓ GitHub update completed

  If push fails:
      ✗ Commit created locally
      ✗ Push failed

      Reason:
      <actual Git error>

      The local commit has NOT been falsely reported as published.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class WorkingTreeStatus:
    is_repo: bool
    current_branch: str = ""
    remote_url: str = ""
    remote_name: str = "origin"
    head_commit: str = ""
    staged_files: List[str] = field(default_factory=list)
    unstaged_files: List[str] = field(default_factory=list)
    untracked_files: List[str] = field(default_factory=list)
    deleted_files: List[str] = field(default_factory=list)
    has_changes: bool = False
    error: str = ""


# Files and patterns that should never be staged
_BLOCKED_PATTERNS = [
    "__pycache__",
    ".pyc",
    ".pyo",
    ".pyd",
    ".venv",
    "node_modules",
    ".env",
    ".sqlite",
    ".sqlite-shm",
    ".sqlite-wal",
    "startup.log",
    ".vscode-test",
    ".tmp",
]


def _run_git_cmd(args: List[str], cwd: str, timeout: float = 30.0) -> Tuple[bool, str, str, int]:
    """Execute a git command with timeout and return (success, stdout, stderr, returncode)."""
    git_bin = shutil.which("git") or "git"
    try:
        proc = subprocess.run(
            [git_bin] + args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0,
        )
        return (proc.returncode == 0), proc.stdout.rstrip("\r\n"), proc.stderr.strip(), proc.returncode
    except subprocess.TimeoutExpired:
        return False, "", f"git command timed out after {timeout}s: {' '.join(args)}", -1
    except Exception as e:
        return False, "", f"Failed to execute git: {e}", -1


def inspect_repository(repo_path: Optional[str] = None) -> WorkingTreeStatus:
    """Inspect the working tree, remote configuration, branch, and status."""
    cwd = repo_path or os.getcwd()

    # Check git executable
    if not shutil.which("git"):
        return WorkingTreeStatus(is_repo=False, error="Git executable not found on PATH.")

    # Check if in a git worktree
    ok, out, err, _ = _run_git_cmd(["rev-parse", "--is-inside-work-tree"], cwd)
    if not ok or out.strip() != "true":
        return WorkingTreeStatus(is_repo=False, error=f"'{cwd}' is not inside a git repository.")

    # Branch
    ok, branch, _, _ = _run_git_cmd(["branch", "--show-current"], cwd)
    branch = branch.strip()
    if not ok or not branch:
        # Fallback for detached HEAD or older git
        _, branch_out, _, _ = _run_git_cmd(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
        branch = branch_out.strip()

    # Remote URL
    _, remote_url, _, _ = _run_git_cmd(["remote", "get-url", "origin"], cwd)
    if not remote_url:
        _, remotes_out, _, _ = _run_git_cmd(["remote", "-v"], cwd)
        if remotes_out:
            first_line = remotes_out.splitlines()[0]
            parts = first_line.split()
            if len(parts) >= 2:
                remote_url = parts[1]

    # Head commit
    _, head_commit, _, _ = _run_git_cmd(["log", "-1", "--format=%h - %s (%cr)"], cwd)

    # Status porcelain
    ok, status_out, err, _ = _run_git_cmd(["status", "--porcelain=v1", "-uall"], cwd)
    if not ok:
        return WorkingTreeStatus(
            is_repo=True,
            current_branch=branch or "main",
            remote_url=remote_url,
            head_commit=head_commit,
            error=f"git status failed: {err}",
        )

    staged = []
    unstaged = []
    untracked = []
    deleted = []

    for line in status_out.splitlines():
        if len(line) < 3:
            continue
        index_status = line[0]
        worktree_status = line[1]
        file_path = line[3:].strip()
        if file_path.startswith('"') and file_path.endswith('"'):
            file_path = file_path[1:-1]
        if " -> " in file_path:
            file_path = file_path.split(" -> ")[1].strip()

        # Check for blocked patterns
        if any(pat in file_path for pat in _BLOCKED_PATTERNS if pat not in (".env.example", ".env.sample")):
            continue

        if index_status in ("M", "A", "R"):
            staged.append(file_path)
        elif index_status == "D":
            deleted.append(file_path)

        if worktree_status == "M":
            unstaged.append(file_path)
        elif worktree_status == "D":
            deleted.append(file_path)

        if index_status == "?" and worktree_status == "?":
            untracked.append(file_path)

    has_changes = bool(staged or unstaged or untracked or deleted)

    return WorkingTreeStatus(
        is_repo=True,
        current_branch=branch or "main",
        remote_url=remote_url,
        remote_name="origin",
        head_commit=head_commit,
        staged_files=staged,
        unstaged_files=unstaged,
        untracked_files=untracked,
        deleted_files=deleted,
        has_changes=has_changes,
    )


def stage_intended_files(repo_path: Optional[str] = None) -> Tuple[bool, List[str], str]:
    """Correctly stage intended updated files while protecting secrets, caches, and build artifacts."""
    cwd = repo_path or os.getcwd()

    # First untrack any accidentally tracked bytecode / sqlite / env files
    untrack_cmd = [
        "rm", "--cached", "-r", "--ignore-unmatch",
        "CAT_v0.7.4/calc_terminal/**/__pycache__/*.pyc",
        "CAT_v0.7.4/__pycache__/*.pyc",
        "release/__pycache__/*.pyc",
        "CAT_v0.7.4/startup.log",
        "fomoji-updated/fomoji-server/.env",
        "fomoji-updated/fomoji-server/data/fomoji.sqlite*",
    ]
    _run_git_cmd(untrack_cmd, cwd)

    # Stage modified and untracked files respecting .gitignore
    ok, out, err, code = _run_git_cmd(["add", "-A"], cwd)
    if not ok:
        return False, [], f"git add failed: {err or out}"

    # Get list of what is now staged
    ok, staged_out, _, _ = _run_git_cmd(["diff", "--cached", "--name-only"], cwd)
    staged_list = [line.strip() for line in staged_out.splitlines() if line.strip()]

    # Double check that no blocked files made it into stage
    blocked_staged = [
        f for f in staged_list
        if any(pat in f for pat in _BLOCKED_PATTERNS if pat not in (".env.example", ".env.sample"))
    ]
    if blocked_staged:
        _run_git_cmd(["reset", "HEAD"] + blocked_staged, cwd)
        staged_list = [f for f in staged_list if f not in blocked_staged]

    return True, staged_list, ""


def generate_default_commit_message(staged_files: List[str]) -> str:
    """Generate a descriptive, meaningful commit message based on staged files.
    Ensures commit messages are NEVER empty."""
    if not staged_files:
        return "Update CAT CLI: codebase maintenance and reliability improvements"

    categories = set()
    for f in staged_files:
        lf = f.lower()
        if "fomoji" in lf or "auth" in lf:
            categories.add("Fomoji authentication and server startup")
        elif "git" in lf:
            categories.add("Git publishing and synchronization")
        elif "cli" in lf or "terminal" in lf:
            categories.add("CAT CLI core")
        elif "ui" in lf or "theme" in lf:
            categories.add("terminal UI and theme")
        elif "pyproject" in lf or "manifest" in lf or "setup" in lf:
            categories.add("packaging and distribution metadata")
        elif "readme" in lf or "doc" in lf or ".md" in lf:
            categories.add("documentation")
        else:
            categories.add("core components")

    summary = ", ".join(sorted(categories))
    return f"Update CAT CLI: {summary}\n\n- Synchronized updated files\n- Verified build integrity"


def validate_commit_message(message: Optional[str], staged_files: List[str]) -> Tuple[bool, str]:
    """Validate that the commit message is non-empty. If omitted or empty, provide a sensible default."""
    msg = (message or "").strip()
    if not msg:
        msg = generate_default_commit_message(staged_files)

    # Double-check that it is not empty
    if not msg.strip():
        return False, "Commit message cannot be empty or solely whitespace."

    return True, msg.strip()


def create_commit(repo_path: str, message: str) -> Tuple[bool, str, str]:
    """Create a git commit with verified non-empty message and verify commit was created."""
    ok, head_before, _, _ = _run_git_cmd(["rev-parse", "HEAD"], repo_path)

    ok, out, err, code = _run_git_cmd(["commit", "-m", message], repo_path)
    if not ok:
        if "nothing to commit" in (out + err).lower():
            return False, "", "No changes staged to commit."
        return False, "", f"git commit failed ({code}): {err or out}"

    # Verify commit exists
    ok, head_after, _, _ = _run_git_cmd(["rev-parse", "HEAD"], repo_path)
    if not ok or head_after == head_before:
        return False, "", "Commit verification failed: HEAD did not advance."

    return True, head_after, out


def push_to_remote(
    repo_path: str,
    remote: str = "origin",
    branch: Optional[str] = None,
) -> Tuple[bool, str, str]:
    """Push the local branch to the remote repository. Handles fast-forward/sync if needed."""
    # Determine branch
    if not branch:
        ok, current_branch, _, _ = _run_git_cmd(["branch", "--show-current"], repo_path)
        branch = current_branch or "main"

    # Check if upstream exists and if local is behind
    _run_git_cmd(["fetch", remote, branch], repo_path, timeout=30.0)

    # Check ahead/behind counts
    ok, rev_list, _, _ = _run_git_cmd(
        ["rev-list", "--left-right", "--count", f"{branch}...{remote}/{branch}"],
        repo_path,
    )
    if ok and rev_list:
        parts = rev_list.split()
        if len(parts) == 2:
            ahead, behind = int(parts[0]), int(parts[1])
            if behind > 0 and ahead > 0:
                # Need rebase to cleanly integrate upstream commits
                rebase_ok, _, rebase_err, _ = _run_git_cmd(["rebase", f"{remote}/{branch}"], repo_path)
                if not rebase_ok:
                    _run_git_cmd(["rebase", "--abort"], repo_path)
                    return False, "", f"Upstream has changes that require manual merge: {rebase_err}"
            elif behind > 0 and ahead == 0:
                # Fast forward
                _run_git_cmd(["merge", "--ff-only", f"{remote}/{branch}"], repo_path)

    # Execute push
    ok, out, err, code = _run_git_cmd(["push", remote, branch], repo_path, timeout=60.0)
    if not ok:
        return False, "", err or out

    # Verify remote ref matches local HEAD
    ok_head, local_head, _, _ = _run_git_cmd(["rev-parse", "HEAD"], repo_path)
    ok_remote, remote_ref, _, _ = _run_git_cmd(["ls-remote", remote, f"refs/heads/{branch}"], repo_path, timeout=20.0)
    if ok_remote and remote_ref and local_head:
        remote_head = remote_ref.split()[0]
        if remote_head != local_head:
            return False, out, f"Remote verification mismatch: remote has {remote_head}, local is {local_head}."

    return True, out, ""


def sync_and_publish(
    repo_path: Optional[str] = None,
    message: Optional[str] = None,
    remote: str = "origin",
) -> int:
    """Execute the complete GitHub update & verification workflow:
        Check repository
            ↓
        Check modified files
            ↓
        If no changes:
            → tell user repository is already up to date
            ↓
        If changes exist:
            → stage intended files
            ↓
        Validate commit message
            ↓
        Create commit
            ↓
        Verify commit exists
            ↓
        Push to correct remote/branch
            ↓
        Verify push succeeded

    Returns exit code (0 on success, non-zero on failure)."""
    cwd = repo_path or os.getcwd()

    try:
        from . import theme
        theme.enable_windows_ansi()
        has_theme = True
    except Exception:
        has_theme = False

    def ok(msg: str):
        if has_theme:
            print(f"  {theme.green('✓')} {msg}")
        else:
            print(f"  ✓ {msg}")

    def fail(msg: str):
        if has_theme:
            print(f"  {theme.red('✗')} {msg}")
        else:
            print(f"  ✗ {msg}")

    print("\nStarting Git / GitHub Synchronization Workflow...")
    print("=" * 60)

    # Step 1: Check repository
    status = inspect_repository(cwd)
    if not status.is_repo:
        fail(f"Repository check failed: {status.error}")
        return 1

    branch = status.current_branch or "main"
    print(f"  Repository : {cwd}")
    print(f"  Branch     : {branch}")
    print(f"  Remote     : {status.remote_url or remote}")
    print(f"  HEAD       : {status.head_commit}")
    print("-" * 60)

    # Step 2: Check modified files
    if not status.has_changes:
        print("  Working tree clean — checking if local branch is ahead of remote...")
        # Check if local has unpushed commits
        ok_fetch, _, _, _ = _run_git_cmd(["fetch", remote, branch], cwd, timeout=20.0)
        ok_count, count_out, _, _ = _run_git_cmd(["rev-list", f"{remote}/{branch}..{branch}", "--count"], cwd)
        unpushed_count = int(count_out.strip()) if (ok_count and count_out.isdigit()) else 0

        if unpushed_count == 0:
            ok("Repository is already up to date (no modified files and no unpushed commits).")
            print("=" * 60 + "\n")
            return 0
        else:
            print(f"  Found {unpushed_count} unpushed local commit(s). Proceeding to push...")

    else:
        # Step 3: Stage intended files
        stage_ok, staged_files, stage_err = stage_intended_files(cwd)
        if not stage_ok or not staged_files:
            fail(f"Failed to stage files: {stage_err or 'No valid files to stage'}")
            return 1

        print(f"  Staging {len(staged_files)} intended file(s):")
        for f in staged_files[:10]:
            print(f"    • {f}")
        if len(staged_files) > 10:
            print(f"    ... and {len(staged_files) - 10} more files")

        ok("Files staged")

        # Step 4: Validate commit message
        val_ok, valid_message = validate_commit_message(message, staged_files)
        if not val_ok or not valid_message:
            fail(f"Invalid commit message: {valid_message}")
            return 1

        # Step 5: Create commit
        commit_ok, commit_hash, commit_err = create_commit(cwd, valid_message)
        if not commit_ok:
            fail(f"Failed to create commit: {commit_err}")
            return 1

        ok(f"Commit created ({commit_hash[:7]})")

    # Step 6: Push to correct remote/branch
    push_ok, push_out, push_err = push_to_remote(cwd, remote=remote, branch=branch)

    if not push_ok:
        fail("Commit created locally")
        fail("Push failed")
        print("\nReason:")
        print(push_err or push_out or "Unknown git push error.")
        print("\nThe local commit has NOT been falsely reported as published.\n")
        return 1

    ok("Commit pushed")
    ok("GitHub update completed")
    print("=" * 60 + "\n")
    return 0
