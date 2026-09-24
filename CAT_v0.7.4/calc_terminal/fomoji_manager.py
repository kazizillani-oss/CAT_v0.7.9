"""
CAT — Fomoji Server & Dependency Manager.

Provides comprehensive, cross-platform (PowerShell, CMD, VS Code integrated terminal)
lifecycle management for the Node.js-based Fomoji identity server:

  1. Detects Node.js and npm (on PATH and standard Windows installation directories).
  2. Offers an interactive, legitimate installation flow on Windows (winget / official MSI / web).
  3. Locates the Fomoji server files reliably using paths relative to CAT runtime, package,
     repository root, or application data directory (never hardcoded developer paths).
  4. Automatically installs npm dependencies (npm install) when missing.
  5. Gracefully handles an already-running Fomoji server.
  6. Detects port conflicts on port 3000 (or custom FOMOJI_URL) and reports actionable reasons.
  7. Captures stdout/stderr from the Node.js process with diagnostics on startup failure.
  8. Ensures CAT itself continues to start in standalone/offline mode even if Fomoji fails.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class NodeEnvironment:
    installed: bool
    node_path: Optional[str] = None
    npm_path: Optional[str] = None
    node_version: str = ""
    npm_version: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Node.js and npm detection
# ---------------------------------------------------------------------------

def _find_windows_node_candidates() -> List[Tuple[str, str]]:
    """Scan standard Windows installation directories for Node.js and npm."""
    candidates = []
    prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    app_data = os.environ.get("APPDATA", "")

    search_dirs = [
        os.path.join(prog_files, "nodejs"),
        os.path.join(prog_files_x86, "nodejs"),
        os.path.join(local_app_data, "Programs", "nodejs"),
        os.path.join(local_app_data, "nodejs"),
        os.path.join(app_data, "npm"),
    ]

    # Also check nvm-windows if present
    nvm_dir = os.environ.get("NVM_HOME")
    if nvm_dir:
        search_dirs.insert(0, nvm_dir)
    nvm_symlink = os.environ.get("NVM_SYMLINK")
    if nvm_symlink:
        search_dirs.insert(0, nvm_symlink)

    for d in search_dirs:
        if not d or not os.path.isdir(d):
            continue
        node_exe = os.path.join(d, "node.exe")
        npm_cmd = os.path.join(d, "npm.cmd")
        if not os.path.isfile(npm_cmd):
            npm_cmd = os.path.join(d, "npm.exe")
        if not os.path.isfile(npm_cmd):
            npm_cmd = os.path.join(d, "npm")
        if os.path.isfile(node_exe):
            candidates.append((node_exe, npm_cmd if os.path.isfile(npm_cmd) else ""))
    return candidates


def detect_nodejs() -> NodeEnvironment:
    """Detect whether Node.js and npm are installed and functioning.
    Checks PATH and standard Windows install paths, automatically adding
    discovered locations to the current process PATH."""
    node_bin = shutil.which("node")
    npm_bin = shutil.which("npm") or shutil.which("npm.cmd")

    # If missing on PATH on Windows, scan known standard directories
    if sys.platform == "win32" and (not node_bin or not npm_bin):
        candidates = _find_windows_node_candidates()
        for node_cand, npm_cand in candidates:
            if not node_bin and os.path.isfile(node_cand):
                node_bin = node_cand
                node_dir = os.path.dirname(node_cand)
                if node_dir not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = f"{node_dir}{os.pathsep}{os.environ.get('PATH', '')}"
            if not npm_bin and npm_cand and os.path.isfile(npm_cand):
                npm_bin = npm_cand

    if not node_bin:
        return NodeEnvironment(
            installed=False,
            error="Node.js executable ('node') was not found on PATH or standard installation locations.",
        )

    # Probe `node --version`
    try:
        proc = subprocess.run(
            [node_bin, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=6,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0,
        )
        if proc.returncode != 0:
            return NodeEnvironment(
                installed=False,
                node_path=node_bin,
                error=f"node --version exited with code {proc.returncode}: {proc.stderr.strip()}",
            )
        node_ver = proc.stdout.strip()
    except Exception as e:
        return NodeEnvironment(installed=False, node_path=node_bin, error=f"Failed to execute node: {e}")

    # Probe `npm --version`
    npm_ver = ""
    if npm_bin:
        try:
            proc = subprocess.run(
                [npm_bin, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=8,
                shell=(sys.platform == "win32" and npm_bin.lower().endswith((".cmd", ".bat"))),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0,
            )
            if proc.returncode == 0:
                npm_ver = proc.stdout.strip()
        except Exception:
            npm_ver = ""

    return NodeEnvironment(
        installed=True,
        node_path=node_bin,
        npm_path=npm_bin or "npm",
        node_version=node_ver,
        npm_version=npm_ver,
    )


# ---------------------------------------------------------------------------
# Legitimate Windows Installation Flow
# ---------------------------------------------------------------------------

def prompt_and_install_nodejs(interactive: bool = True) -> bool:
    """Guide the user through installing Node.js LTS via legitimate Windows installer.
    Never bypasses Windows security or elevates privileges silently."""
    print("\n  ⚠ Node.js is required for Fomoji\n")
    print("  Node.js is not installed.")
    print("  CAT can install/setup the required dependency through the normal Windows installation process.\n")

    if not interactive or not sys.stdin.isatty():
        print("  Non-interactive shell detected. Continuing without Fomoji.")
        print("  To enable Fomoji later, install Node.js (v20+ LTS) from https://nodejs.org\n")
        return False

    has_winget = bool(shutil.which("winget"))

    print("  Choose an installation option:")
    if has_winget:
        print("    [1] Install Node.js LTS via Windows Package Manager (winget)")
        print("    [2] Open official Node.js website (https://nodejs.org) in browser")
        print("    [3] Skip and continue CAT in standalone mode (Fomoji offline)")
    else:
        print("    [1] Open official Node.js website (https://nodejs.org) in browser")
        print("    [2] Skip and continue CAT in standalone mode (Fomoji offline)")

    print()
    try:
        choice = input("  Select an option [1]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  Installation skipped. Continuing CAT in standalone mode.\n")
        return False

    if not choice:
        choice = "1"

    if has_winget and choice == "1":
        print("\n  Starting Node.js LTS installation via winget...")
        print("  Windows may show a User Account Control (UAC) prompt to authorize the installer.")
        try:
            # Invoking winget directly triggers the official OpenJS MSI installer with UAC
            res = subprocess.run(
                ["winget", "install", "OpenJS.NodeJS.LTS", "--accept-package-agreements", "--accept-source-agreements"],
                timeout=600,
            )
            if res.returncode == 0:
                print("  ✓ Node.js installer finished.")
            else:
                print(f"  winget completed with exit code {res.returncode}.")
        except Exception as e:
            print(f"  Installation process could not be launched: {e}")

        # Re-check after installation
        print("  Re-checking Node.js installation...")
        time.sleep(2)
        node_env = detect_nodejs()
        if node_env.installed:
            print(f"  ✓ Node.js detected ({node_env.node_version})")
            if node_env.npm_version:
                print(f"  ✓ npm detected (v{node_env.npm_version})")
            return True
        else:
            print("  Node.js was not detected yet. A new terminal session may be required to refresh PATH.")
            print("  Continuing CAT in standalone mode for now.\n")
            return False

    elif (has_winget and choice == "2") or (not has_winget and choice == "1"):
        import webbrowser
        print("  Opening https://nodejs.org/en/download in your default browser...")
        try:
            webbrowser.open("https://nodejs.org/en/download")
        except Exception:
            pass
        print("  Please complete the installer, then restart CAT.")
        input("  Press Enter once Node.js is installed (or to continue without Fomoji)...")
        node_env = detect_nodejs()
        if node_env.installed:
            print(f"  ✓ Node.js detected ({node_env.node_version})")
            return True
        return False

    else:
        print("  Continuing CAT in standalone mode (Fomoji offline).\n")
        return False


# ---------------------------------------------------------------------------
# Path resolution for Fomoji server
# ---------------------------------------------------------------------------

def locate_fomoji_server_dir() -> Optional[Path]:
    """Locate the fomoji-server directory using robust relative and package paths.
    Does NOT rely on developer machine paths or assuming the current working directory."""
    candidates: List[Path] = []

    # 1. Explicit environment variable override
    env_dir = os.environ.get("FOMOJI_SERVER_DIR", "").strip()
    if env_dir:
        candidates.append(Path(env_dir))

    # 2. Package-bundled directory inside calc_terminal/fomoji_server
    try:
        here = Path(__file__).resolve().parent
        candidates.append(here / "fomoji_server")
        candidates.append(here / "fomoji-server")
    except Exception:
        pass

    # 3. Relative to repository root (source checkout layout)
    try:
        here = Path(__file__).resolve()
        # fomoji_manager.py is in calc_terminal -> parents[1] is CAT_v0.7.4 -> parents[2] is root
        for p in (here.parent, here.parents[1], here.parents[2]):
            candidates.append(p / "fomoji-updated" / "fomoji-server")
            candidates.append(p.parent / "fomoji-updated" / "fomoji-server")
            candidates.append(p / "fomoji-server")
    except Exception:
        pass

    # 4. Relative to Python executable (virtualenvs, standalone bundles)
    try:
        py_exe = Path(sys.executable).resolve()
        candidates.append(py_exe.parent / "fomoji-updated" / "fomoji-server")
        candidates.append(py_exe.parents[1] / "fomoji-updated" / "fomoji-server")
        candidates.append(py_exe.parents[2] / "fomoji-updated" / "fomoji-server")
    except Exception:
        pass

    # 5. Application data directory (%LOCALAPPDATA%/CCT/fomoji-server etc.)
    try:
        from .first_run import data_dir
        candidates.append(Path(data_dir()) / "fomoji-server")
        candidates.append(Path(data_dir()) / "fomoji-updated" / "fomoji-server")
    except Exception:
        pass

    # 6. Current working directory fallback
    try:
        cwd = Path.cwd().resolve()
        candidates.append(cwd / "fomoji-updated" / "fomoji-server")
        candidates.append(cwd / "fomoji-server")
    except Exception:
        pass

    # 7. User home fallback
    try:
        candidates.append(Path.home() / ".fomoji" / "server")
        candidates.append(Path.home() / "fomoji-server")
    except Exception:
        pass

    for cand in candidates:
        try:
            c = cand.resolve()
            if (c / "package.json").is_file() and (
                (c / "src" / "server.js").is_file() or (c / "server.js").is_file()
            ):
                return c
        except Exception:
            continue

    return None


# ---------------------------------------------------------------------------
# Dependency installation for Fomoji server
# ---------------------------------------------------------------------------

def ensure_fomoji_dependencies(server_dir: Path, npm_path: Optional[str] = None) -> Tuple[bool, str]:
    """Check if node_modules exists with required dependencies. If missing, run npm install."""
    node_modules = server_dir / "node_modules"
    express_mod = node_modules / "express"

    if node_modules.is_dir() and express_mod.is_dir():
        return True, "Dependencies already installed"

    if npm_path is not None:
        npm_bin = npm_path.strip() if npm_path else None
    else:
        npm_bin = shutil.which("npm") or shutil.which("npm.cmd")

    if not npm_bin:
        return False, "npm is required to install Fomoji server dependencies, but was not found."

    print("  Checking Fomoji dependencies...")
    print("  Installing Fomoji dependencies (npm install)...")

    cmd = [npm_bin, "install", "--no-audit", "--no-fund", "--silent"]
    kwargs: Dict[str, Any] = {
        "cwd": str(server_dir),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "timeout": 180,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if npm_bin.lower().endswith((".cmd", ".bat")):
            kwargs["shell"] = True

    try:
        proc = subprocess.run(cmd, **kwargs)
        if proc.returncode == 0 and (server_dir / "node_modules").is_dir():
            print("  ✓ Fomoji dependencies ready")
            return True, "Dependencies installed successfully"
        err_out = proc.stderr.strip() or proc.stdout.strip()
        return False, f"npm install exited with code {proc.returncode}: {err_out}"
    except subprocess.TimeoutExpired:
        return False, "npm install timed out after 180 seconds."
    except Exception as e:
        return False, f"Failed to execute npm install: {e}"


# ---------------------------------------------------------------------------
# Port conflict and Reachability checks
# ---------------------------------------------------------------------------

def check_server_reachable(timeout: float = 3.0, base_url: Optional[str] = None) -> bool:
    """Probe Fomoji server HTTP endpoint to verify it is responsive."""
    if not base_url:
        from .fomoji_auth import get_fomoji_url
        base_url = get_fomoji_url()
    base = base_url.rstrip("/")
    probe_url = f"{base}/api/connector/ping"

    req = urllib.request.Request(probe_url, headers={"User-Agent": "CAT-Fomoji-Probe"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 404, 405)
    except urllib.error.HTTPError as e:
        # If server answers with 404, 400, 401, or 405, it is actively listening Express app
        return e.code in (200, 400, 401, 403, 404, 405)
    except Exception:
        # Fallback probe to root
        try:
            req_root = urllib.request.Request(f"{base}/", headers={"User-Agent": "CAT-Fomoji-Probe"})
            with urllib.request.urlopen(req_root, timeout=timeout) as resp:
                return resp.status < 500
        except urllib.error.HTTPError as e:
            return e.code < 500
        except Exception:
            return False


def detect_port_conflict(port: int = 3000, host: str = "127.0.0.1") -> Tuple[bool, str]:
    """Check if the target port is already in use by a process that is NOT Fomoji."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        res = s.connect_ex((host, port))

    if res != 0:
        # Port is open/free
        return False, ""

    # Port is in use — check if it's our own Fomoji server
    if check_server_reachable(timeout=2.0, base_url=f"http://{host}:{port}"):
        return False, "Fomoji server already running"

    return True, (
        f"Port {port} is occupied by another application that is not responding as Fomoji. "
        f"Please free port {port} or configure FOMOJI_URL with another port."
    )


# ---------------------------------------------------------------------------
# Server startup orchestration
# ---------------------------------------------------------------------------

def start_fomoji_server(
    server_dir: Path,
    node_path: str,
    timeout: int = 15,
) -> Tuple[bool, str]:
    """Spawn the Node.js Fomoji server and verify it becomes reachable.
    Captures stdout/stderr for diagnostics if startup fails."""
    # Ensure data directory exists
    try:
        (server_dir / "data").mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    script_path = server_dir / "src" / "server.js"
    if not script_path.is_file():
        script_path = server_dir / "server.js"

    if not script_path.is_file():
        return False, f"Server entrypoint script not found in {server_dir}"

    from .first_run import logs_dir
    log_file = Path(logs_dir()) / "fomoji_server.log"
    try:
        lf = open(log_file, "a+", encoding="utf-8")
        lf.write(f"\n--- Fomoji server starting at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        lf.flush()
    except Exception:
        lf = subprocess.DEVNULL  # type: ignore

    cmd = [node_path, str(script_path)]
    kwargs: Dict[str, Any] = {
        "cwd": str(server_dir),
        "stdout": lf,
        "stderr": lf,
    }

    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = si
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kwargs["start_new_session"] = True

    try:
        proc = subprocess.Popen(cmd, **kwargs)
    except Exception as e:
        return False, f"Failed to spawn Fomoji process: {e}"

    # Poll server reachability with process liveness detection
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            # Process terminated early!
            diagnostic = ""
            try:
                if log_file.is_file():
                    content = log_file.read_text(encoding="utf-8", errors="replace")
                    lines = content.strip().splitlines()
                    diagnostic = "\n".join(lines[-15:])
            except Exception:
                pass
            return False, (
                f"Fomoji server process exited unexpectedly with code {proc.returncode}.\n"
                f"Diagnostic:\n{diagnostic or 'No log output captured.'}"
            )

        if check_server_reachable(timeout=1.5):
            return True, "Fomoji server ready"

        time.sleep(1)

    # Timed out
    diagnostic = ""
    try:
        if log_file.is_file():
            content = log_file.read_text(encoding="utf-8", errors="replace")
            lines = content.strip().splitlines()
            diagnostic = "\n".join(lines[-15:])
    except Exception:
        pass

    return False, (
        f"Fomoji server did not become reachable within {timeout}s.\n"
        f"Diagnostic:\n{diagnostic or 'No response from http://localhost:3000'}"
    )


# ---------------------------------------------------------------------------
# Master Startup Coordinator
# ---------------------------------------------------------------------------

def initialize_fomoji_subsystem(interactive: bool = True) -> bool:
    """Master Fomoji initialization flow for CAT startup:
      ✓ CAT core initialized
      ✓ Checking Node.js...
      ✓ Node.js detected
      ✓ Checking Fomoji dependencies...
      ✓ Starting Fomoji server...
      ✓ Fomoji server ready

    If Fomoji is unavailable for any reason, CAT itself will still proceed
    in standalone/offline mode without crashing."""
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

    def warn(msg: str):
        if has_theme:
            print(f"  {theme.orange('⚠')} {msg}")
        else:
            print(f"  ⚠ {msg}")

    def fail(msg: str):
        if has_theme:
            print(f"  {theme.red('✗')} {msg}")
        else:
            print(f"  ✗ {msg}")

    # Step 1: Check if server is ALREADY running
    if check_server_reachable(timeout=2):
        ok("Fomoji server ready (already running)")
        return True

    # Step 2: Check Node.js
    node_env = detect_nodejs()
    if not node_env.installed:
        warn("Node.js is required for Fomoji")
        installed = prompt_and_install_nodejs(interactive=interactive)
        if installed:
            node_env = detect_nodejs()

    if not node_env.installed:
        warn("Node.js is not available. Starting CAT in standalone mode (Fomoji offline).")
        os.environ["CAT_ALLOW_NO_AUTH"] = "1"
        return False

    ok(f"Node.js detected ({node_env.node_version})")

    # Step 3: Locate Fomoji Server files
    server_dir = locate_fomoji_server_dir()
    if not server_dir:
        warn("Fomoji server files could not be located. Starting CAT in standalone mode.")
        os.environ["CAT_ALLOW_NO_AUTH"] = "1"
        return False

    # Step 4: Check and install npm dependencies
    deps_ok, deps_msg = ensure_fomoji_dependencies(server_dir, node_env.npm_path)
    if not deps_ok:
        warn(f"Fomoji dependencies could not be prepared: {deps_msg}")
        warn("Starting CAT in standalone mode (Fomoji offline).")
        os.environ["CAT_ALLOW_NO_AUTH"] = "1"
        return False

    ok("Fomoji dependencies ready")

    # Step 5: Check port conflicts
    port = 3000
    env_url = os.environ.get("FOMOJI_URL", "")
    if env_url:
        import urllib.parse
        parsed = urllib.parse.urlparse(env_url)
        if parsed.port:
            port = parsed.port

    has_conflict, conflict_msg = detect_port_conflict(port=port)
    if has_conflict:
        fail(f"Fomoji port conflict on port {port}: {conflict_msg}")
        warn("Starting CAT in standalone mode (Fomoji offline).")
        os.environ["CAT_ALLOW_NO_AUTH"] = "1"
        return False

    # Step 6: Start Fomoji server
    if has_theme:
        print(f"  {theme.cyan('⠋')} Starting Fomoji server...")
    else:
        print("  Starting Fomoji server...")

    server_started, server_msg = start_fomoji_server(
        server_dir=server_dir,
        node_path=node_env.node_path or "node",
        timeout=15,
    )

    if server_started:
        ok("Fomoji server ready")
        return True
    else:
        fail(f"Fomoji server could not be started:\n{server_msg}")
        warn("Starting CAT in standalone mode (Fomoji offline).")
        os.environ["CAT_ALLOW_NO_AUTH"] = "1"
        return False
