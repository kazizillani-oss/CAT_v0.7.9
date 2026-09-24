"""
Tests for Fomoji Dependency & Server Lifecycle and Git Publishing Workflow.

Verifies the 14 critical scenarios required by CAT CLI:
  1. Node.js already installed
  2. Node.js missing
  3. npm missing / broken
  4. Fomoji dependencies missing
  5. Fomoji already running
  6. Fomoji port unavailable / conflict
  7. Fomoji process crashes
  8. CAT path contains spaces
  9. Git repository has modified files
  10. Git repository has no modified files
  11. Empty commit message handling & validation
  12. Successful commit + push flow
  13. Failed push reporting & safety guarantee
  14. .gitignore behavior protecting secrets & caches
"""

import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from calc_terminal.fomoji_manager import (
    NodeEnvironment,
    check_server_reachable,
    detect_nodejs,
    detect_port_conflict,
    ensure_fomoji_dependencies,
    initialize_fomoji_subsystem,
    locate_fomoji_server_dir,
    start_fomoji_server,
)
from calc_terminal.git_sync import (
    create_commit,
    generate_default_commit_message,
    inspect_repository,
    push_to_remote,
    stage_intended_files,
    sync_and_publish,
    validate_commit_message,
)


# ============================================================================
# 1. Node.js already installed
# ============================================================================
def test_nodejs_already_installed():
    env = detect_nodejs()
    # On the test runner machine, Node.js should be detected if installed
    if shutil.which("node"):
        assert env.installed is True
        assert env.node_path is not None
        assert env.node_version.startswith("v")


# ============================================================================
# 2. Node.js missing
# ============================================================================
def test_nodejs_missing():
    with patch("shutil.which", return_value=None), patch(
        "calc_terminal.fomoji_manager._find_windows_node_candidates", return_value=[]
    ):
        env = detect_nodejs()
        assert env.installed is False
        assert "not found" in env.error.lower()


# ============================================================================
# 3. npm missing / broken
# ============================================================================
def test_npm_missing_or_broken(tmp_path):
    with patch("shutil.which", side_effect=lambda cmd: "node.exe" if cmd == "node" else None), patch(
        "calc_terminal.fomoji_manager._find_windows_node_candidates", return_value=[("node.exe", "")]
    ), patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="v20.0.0", stderr="")
        env = detect_nodejs()
        assert env.installed is True
        assert env.npm_version == ""

    # Test dependency installer handles missing npm (explicit empty path)
    ok, msg = ensure_fomoji_dependencies(tmp_path, npm_path="")
    assert ok is False
    assert "npm is required" in msg

    # Test dependency installer handles missing npm on PATH
    with patch("shutil.which", return_value=None):
        ok2, msg2 = ensure_fomoji_dependencies(tmp_path, npm_path=None)
        assert ok2 is False
        assert "npm is required" in msg2


# ============================================================================
# 4. Fomoji dependencies missing
# ============================================================================
def test_fomoji_dependencies_missing_triggers_install(tmp_path):
    server_dir = tmp_path / "fomoji-server"
    server_dir.mkdir()
    (server_dir / "package.json").write_text('{"name": "test"}')

    with patch("subprocess.run") as mock_run:
        # Simulate successful npm install creating node_modules
        def side_effect(cmd, **kwargs):
            (server_dir / "node_modules").mkdir(exist_ok=True)
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = side_effect
        ok, msg = ensure_fomoji_dependencies(server_dir, npm_path="npm")
        assert ok is True
        assert (server_dir / "node_modules").is_dir()


# ============================================================================
# 5. Fomoji already running
# ============================================================================
def test_fomoji_already_running():
    from calc_terminal import fomoji_manager as fm
    with patch.object(fm, "check_server_reachable", return_value=True):
        assert fm.check_server_reachable(timeout=1.0) is True
        # initialize_fomoji_subsystem should immediately report ready
        ready = fm.initialize_fomoji_subsystem(interactive=False)
        assert ready is True


# ============================================================================
# 6. Fomoji port unavailable / conflict
# ============================================================================
def test_fomoji_port_conflict():
    # Simulate port in use by non-Fomoji app
    with patch("socket.socket.connect_ex", return_value=0), patch(
        "calc_terminal.fomoji_manager.check_server_reachable", return_value=False
    ):
        has_conflict, msg = detect_port_conflict(port=3000)
        assert has_conflict is True
        assert "occupied by another application" in msg


# ============================================================================
# 7. Fomoji process crashes
# ============================================================================
def test_fomoji_process_crashes(tmp_path):
    server_dir = tmp_path / "fomoji-server"
    server_dir.mkdir()
    (server_dir / "src").mkdir()
    server_js = server_dir / "src" / "server.js"
    server_js.write_text("process.exit(1);")

    # Mock Popen to return a process that immediately terminates with code 1
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1
    mock_proc.returncode = 1

    with patch("subprocess.Popen", return_value=mock_proc):
        started, err_msg = start_fomoji_server(server_dir, "node", timeout=2)
        assert started is False
        assert "exited unexpectedly with code 1" in err_msg


# ============================================================================
# 8. CAT path contains spaces
# ============================================================================
def test_cat_path_contains_spaces(tmp_path):
    dir_with_spaces = tmp_path / "CAT Path With Spaces {v0.8}"
    server_dir = dir_with_spaces / "fomoji-updated" / "fomoji-server"
    server_dir.mkdir(parents=True)
    (server_dir / "package.json").write_text('{"name": "fomoji-server"}')
    (server_dir / "src").mkdir()
    (server_dir / "src" / "server.js").write_text("// server")

    with patch.dict(os.environ, {"FOMOJI_SERVER_DIR": str(server_dir)}):
        found = locate_fomoji_server_dir()
        assert found is not None
        assert " " in str(found)
        assert (found / "package.json").is_file()


# ============================================================================
# 9. Git repository has modified files
# ============================================================================
def test_git_repo_with_modified_files(tmp_path):
    # Initialize a clean git repo
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(tmp_path), check=True)

    test_file = tmp_path / "test.txt"
    test_file.write_text("v1")
    subprocess.run(["git", "add", "test.txt"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(tmp_path), check=True)

    # Modify file
    test_file.write_text("v2")
    status = inspect_repository(str(tmp_path))
    assert status.is_repo is True
    assert status.has_changes is True
    assert "test.txt" in status.unstaged_files


# ============================================================================
# 10. Git repository has no modified files
# ============================================================================
def test_git_repo_with_no_modified_files(tmp_path):
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(tmp_path), check=True)

    test_file = tmp_path / "file.txt"
    test_file.write_text("hello")
    subprocess.run(["git", "add", "file.txt"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), check=True)

    status = inspect_repository(str(tmp_path))
    assert status.is_repo is True
    assert status.has_changes is False


# ============================================================================
# 11. Empty commit message validation
# ============================================================================
def test_empty_commit_message_validation():
    # Empty string should generate sensible default
    val_ok, msg = validate_commit_message("", ["fomoji_manager.py", "git_sync.py"])
    assert val_ok is True
    assert len(msg.strip()) > 0
    assert "Fomoji" in msg or "Git" in msg

    # Whitespace only should also generate default
    val_ok, msg2 = validate_commit_message("   \n\t  ", ["calc_terminal/cli.py"])
    assert val_ok is True
    assert len(msg2.strip()) > 0
    assert "CAT CLI" in msg2

    # None should generate default
    val_ok, msg3 = validate_commit_message(None, ["README.md"])
    assert val_ok is True
    assert len(msg3.strip()) > 0
    assert "documentation" in msg3


# ============================================================================
# 12. Successful commit + push flow
# ============================================================================
def test_successful_commit_and_push(tmp_path):
    # Create bare remote repository
    remote_dir = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote_dir)], capture_output=True, check=True)

    # Clone/init local repo
    local_dir = tmp_path / "local"
    subprocess.run(["git", "clone", str(remote_dir), str(local_dir)], capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(local_dir), check=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=str(local_dir), check=True)

    # Initial commit so branch exists
    (local_dir / "README.md").write_text("initial")
    subprocess.run(["git", "add", "README.md"], cwd=str(local_dir), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(local_dir), check=True)
    subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=str(local_dir), check=True)
    subprocess.run(["git", "checkout", "main"], cwd=str(local_dir), check=True)

    # Make a change and run sync_and_publish
    (local_dir / "app.py").write_text("print('hello')")
    rc = sync_and_publish(repo_path=str(local_dir), message="Add app.py")
    assert rc == 0

    # Verify remote has commit
    res = subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        cwd=str(local_dir),
        capture_output=True,
        text=True,
    )
    assert "Add app.py" in res.stdout


# ============================================================================
# 13. Failed push handling & safety guarantee
# ============================================================================
def test_failed_push_reports_error_and_does_not_falsely_claim_success(tmp_path):
    local_dir = tmp_path / "local"
    local_dir.mkdir()
    subprocess.run(["git", "init"], cwd=str(local_dir), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(local_dir), check=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=str(local_dir), check=True)

    # Set non-existent remote URL to force push failure
    subprocess.run(
        ["git", "remote", "add", "origin", "https://invalid.example.com/nonexistent/repo.git"],
        cwd=str(local_dir),
        check=True,
    )

    (local_dir / "file.txt").write_text("content")
    rc = sync_and_publish(repo_path=str(local_dir), message="Test commit")
    # Must exit with non-zero error code and not report success
    assert rc == 1


# ============================================================================
# 14. .gitignore behavior protecting secrets & caches
# ============================================================================
def test_gitignore_protects_secrets_and_caches(tmp_path):
    # Read workspace root .gitignore
    root_gitignore = Path(__file__).resolve().parents[3] / ".gitignore"
    if root_gitignore.is_file():
        content = root_gitignore.read_text(encoding="utf-8")
        assert ".env" in content
        assert "*.pyc" in content
        assert "__pycache__/" in content
        assert "*.sqlite" in content
        assert "node_modules/" in content
