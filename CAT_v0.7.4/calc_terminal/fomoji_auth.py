"""
CAT — Fomoji Authentication Gate.

Every CAT entrypoint (cat CLI, python main.py, python -m calc_terminal)
MUST pass through this module before any UI or REPL is shown.

Architecture:
    Fomoji (Node/Express) ── owns identity + auth, never sees CAT's code
        ^  HTTP device-authorization flow (RFC 8628 shape)
        |
    fomoji_auth.py  <-- you are here (CAT side gate)
        ^
        |
    CAT (calc_terminal.cli)

Why a device flow and not a redirect?
A CLI/desktop Python process has no browser of its own to redirect through,
so it shows a short code + verification URL, a human approves it in their
browser on the Fomoji site, and this module polls until that happens — the
same pattern `gh auth login` / `docker login` use.

Storage:
The connector token (and nothing else) lives at:
    ~/.fomoji/connectors/cat.json   (0600, per application)
No password, no passkey secret, no session cookie is ever stored here.

Enforcement:
Without a valid `connected` status, CAT refuses to start.  See
`require_auth()` / `enforce_or_exit()` — there is NO silent bypass.
The only intentional overrides are:
  * CAT_SKIP_AUTH=1  (or CAT_ALLOW_NO_AUTH=1) — for automated tests / CI.
  * --help / --version / --doctor — never gated.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Config — keep these in sync with fomoji-connector-py/connector.py and
# fomoji-server/src/db.js (where `cat` is seeded as the first-party app).
# ---------------------------------------------------------------------------

APPLICATION_ID = os.environ.get("FOMOJI_APP_ID", "cat")
DEFAULT_FOMOJI_URL = os.environ.get("FOMOJI_URL", "http://localhost:3000").rstrip("/")
CONNECTOR_DIR = Path(
    os.environ.get(
        "FOMOJI_CONNECTOR_DIR",
        str(Path.home() / ".fomoji" / "connectors"),
    )
)
TOKEN_PATH = CONNECTOR_DIR / f"{APPLICATION_ID}.json"

# Permissions CAT asks for by default.  Must be a subset of the
# `permissions_available` seeded for `cat` in fomoji-server/src/db.js:
#   ['IDENTITY','PROFILE','CAT_ACCESS','PROJECT']
DEFAULT_PERMISSIONS = ["IDENTITY", "CAT_ACCESS"]

# Skip flag — intentionally env-only, never a CLI flag that a script could
# pass accidentally and leave a machine wide-open.
_SKIP_ENV = {"CAT_SKIP_AUTH", "CAT_ALLOW_NO_AUTH"}


class FomojiAuthError(RuntimeError):
    """Raised when Fomoji auth is required but cannot be completed."""


# ---------------------------------------------------------------------------
# Local token store — 0600, same as connector.py.
# ---------------------------------------------------------------------------

def _load_local() -> Optional[Dict[str, Any]]:
    if not TOKEN_PATH.exists():
        return None
    try:
        return json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _save_local(data: Dict[str, Any]) -> None:
    CONNECTOR_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(TOKEN_PATH, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _clear_local() -> None:
    try:
        TOKEN_PATH.unlink()
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# HTTP helpers — stdlib only, no extra deps.
# ---------------------------------------------------------------------------

def get_fomoji_url() -> str:
    return os.environ.get("FOMOJI_URL", DEFAULT_FOMOJI_URL).rstrip("/")


def _request(
    method: str,
    path: str,
    body: Optional[Dict[str, Any]] = None,
    auth_token: Optional[str] = None,
    query: Optional[Dict[str, str]] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    base = get_fomoji_url()
    url = f"{base}{path}"
    if query:
        from urllib.parse import urlencode
        url = f"{url}?{urlencode(query)}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if auth_token:
        req.add_header("Authorization", f"Bearer {auth_token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            parsed = json.loads(raw)
            message = parsed.get("error", raw)
        except json.JSONDecodeError:
            message = raw or str(e)
        raise FomojiAuthError(f"Fomoji request failed ({e.code}): {message}") from None
    except urllib.error.URLError as e:
        raise FomojiAuthError(f"Could not reach Fomoji at {base}: {e.reason}") from None


# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------

def is_skip_enabled() -> bool:
    for key in _SKIP_ENV:
        v = os.environ.get(key, "").strip().lower()
        if v in ("1", "true", "yes", "on"):
            return True
    return False


def _find_fomoji_server_dir() -> Optional[Path]:
    """Locate the fomoji-server directory using robust relative and package paths."""
    try:
        from .fomoji_manager import locate_fomoji_server_dir
        return locate_fomoji_server_dir()
    except Exception:
        pass
    candidates: List[Path] = []
    env_dir = os.environ.get("FOMOJI_SERVER_DIR", "").strip()
    if env_dir:
        candidates.append(Path(env_dir))
    try:
        here = Path(__file__).resolve()
        candidates.append(here.parent / "fomoji_server")
        candidates.append(here.parents[1].parent / "fomoji-updated" / "fomoji-server")
        candidates.append(here.parents[2] / "fomoji-updated" / "fomoji-server")
    except Exception:
        pass
    for cand in candidates:
        try:
            c = cand.resolve()
            if (c / "package.json").exists():
                return c
        except Exception:
            continue
    return None


def _is_server_process_running() -> bool:
    # Lightweight: just probe, don't cache PID yet.
    return check_server_reachable(timeout=2)


_SERVER_LOADING_STEPS = [
    (0, "Initializing"),
    (10, "Finding server files"),
    (25, "Starting Node.js"),
    (45, "Waiting for server"),
    (65, "Checking connection"),
    (80, "Verifying endpoints"),
    (95, "Almost ready"),
    (100, "Connected"),
]

def _show_server_loading(quiet: bool = False):
    """Show a loading animation while the Fomoji server starts up."""
    if quiet:
        return lambda: None
    try:
        from . import theme
        theme.enable_windows_ansi()
        is_themed = True
    except Exception:
        is_themed = False

    _frame_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    _state = {"frame": 0, "step": 0, "running": True}

    def _tick():
        if not _state["running"]:
            return
        ch = _frame_chars[_state["frame"] % len(_frame_chars)]
        _state["frame"] += 1
        step_idx = min(_state["step"], len(_SERVER_LOADING_STEPS) - 1)
        pct, label = _SERVER_LOADING_STEPS[step_idx]
        bar_width = 24
        filled = int(bar_width * pct / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        if is_themed:
            print(
                f"\r  {theme.cyan(ch)}  {theme.text(label + '...'):40s} "
                f"{theme.dim('[')}{theme.text(bar)}{theme.dim(']')} "
                f"{theme.text(str(pct) + '%')}",
                end="", flush=True,
            )
        else:
            print(
                f"\r  {ch}  {label:40s} [{bar}] {pct}%",
                end="", flush=True,
            )

    def _advance(msg: str = ""):
        _state["step"] = min(_state["step"] + 1, len(_SERVER_LOADING_STEPS) - 1)
        _tick()

    def _finish(success: bool = True, msg: str = ""):
        _state["running"] = False
        if is_themed:
            if success:
                print(f"\r  {theme.green('✓')}  {'Server ready':40s} [{'█' * 24}] 100%   ")
            else:
                print(f"\r  {theme.red('✗')}  {'Server failed to start':40s}                  ")
        else:
            sym = "OK" if success else "FAIL"
            print(f"\r  {sym}  {'Server ready' if success else 'Failed'}")

    return _advance, _finish


def ensure_fomoji_server(auto_start: bool = True, timeout: int = 18) -> bool:
    """Ensure Fomoji server is reachable. If not and auto_start is True,
    use the robust fomoji_manager to check dependencies, handle ports,
    and start the server. Never raises."""
    if check_server_reachable(timeout=3):
        return True
    if not auto_start:
        return False
    env_url = os.environ.get("FOMOJI_URL", "").strip()
    if env_url and "localhost" not in env_url and "127.0.0.1" not in env_url:
        return False
    try:
        from .fomoji_manager import initialize_fomoji_subsystem
        return initialize_fomoji_subsystem(interactive=False)
    except Exception:
        return False


def check_server_reachable(timeout: int = 4) -> bool:
    """Best-effort liveness probe — hits a public endpoint, never auth."""
    base = get_fomoji_url()
    url = f"{base}/api/connector/applications"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False


def status() -> str:
    """
    Returns: 'connected' | 'not_connected' | 'expired' | 'server_unreachable'
    Never raises just because there is no local connection yet.
    """
    local = _load_local()
    if not local or not local.get("token"):
        return "not_connected"

    # Enforce strict 2-hour guest limit locally
    if local.get("is_guest") or (local.get("identity", {}) and local["identity"].get("identityType") == "TEMPORARY"):
        exp = local.get("expires_at")
        if exp and time.time() >= exp:
            _clear_local()
            return "expired"

    token = local["token"]
    try:
        result = _request(
            "GET",
            "/api/connector/status",
            auth_token=token,
            query={"applicationId": APPLICATION_ID},
            timeout=8,
        )
    except FomojiAuthError as e:
        msg = str(e)
        if "Could not reach Fomoji" in msg:
            return "server_unreachable"
        return "not_connected"
    s = result.get("status", "not_connected")
    if s != "connected":
        # Token is stale — clean up so the next launch re-prompts instead
        # of looping on an expired token forever.
        if s == "expired":
            _clear_local()
            return "expired"
        # not_connected — also clear stale file
        if s == "not_connected":
            _clear_local()
            return s
        return s
    return "connected"


def guest_login(timeout: int = 15) -> Dict[str, Any]:
    """Create and activate a 2-hour guest session with automatic 2-hour expiration."""
    ensure_fomoji_server(auto_start=True, timeout=timeout)
    result = _request(
        "POST",
        "/api/connector/guest",
        {"applicationId": APPLICATION_ID},
        timeout=timeout,
    )
    token = result.get("token") or result.get("connectorToken")
    identity = result.get("identity", {})
    now = time.time()
    expires_at = now + 7200  # exactly 2 hours (7200 seconds)
    data = {
        "token": token,
        "identity": identity,
        "is_guest": True,
        "issued_at": now,
        "expires_at": expires_at,
        "expires_at_iso": result.get("expiresAt"),
    }
    _save_local(data)
    return identity


def get_guest_remaining_seconds() -> Optional[float]:
    local = _load_local()
    if not local or not local.get("is_guest"):
        return None
    exp = local.get("expires_at")
    if not exp:
        return None
    rem = exp - time.time()
    return max(0.0, rem)


def start_guest_watchdog(on_expire=None):
    """Starts a background daemon thread that monitors the 2-hour guest session limit.
    When 2 hours elapse, it clears credentials and terminates cleanly."""
    local = _load_local()
    if not local or not local.get("is_guest"):
        return None

    import threading

    def _watch():
        while True:
            time.sleep(15)
            rem = get_guest_remaining_seconds()
            if rem is not None and rem <= 0:
                _clear_local()
                if on_expire:
                    try:
                        on_expire()
                    except Exception:
                        pass
                else:
                    try:
                        from . import theme
                        theme.enable_windows_ansi()
                        print(theme.red("\n\n  [CAT Guest Session Expired] 2-hour guest limit reached. Automatically signing out...\n", bold=True))
                    except Exception:
                        print("\n\n  [CAT Guest Session Expired] 2-hour guest limit reached. Automatically signing out...\n")
                    os._exit(0)
                break

    t = threading.Thread(target=_watch, daemon=True, name="cat_guest_watchdog")
    t.start()
    return t


def get_oauth_config() -> Dict[str, Any]:
    """Fetch OAuth provider configuration status from Fomoji server."""
    ensure_fomoji_server(auto_start=True, timeout=8)
    return _request("GET", "/api/oauth/config", timeout=8)


def set_oauth_credentials(provider: str, client_id: str, client_secret: str) -> Dict[str, Any]:
    """Configure Client ID and Client Secret for an OAuth provider."""
    ensure_fomoji_server(auto_start=True, timeout=8)
    return _request(
        "POST",
        f"/api/oauth/config/{provider.strip().lower()}",
        {"clientId": client_id.strip(), "clientSecret": client_secret.strip()},
        timeout=8,
    )


def delete_oauth_credentials(provider: str) -> Dict[str, Any]:
    """Remove configured credentials for an OAuth provider."""
    ensure_fomoji_server(auto_start=True, timeout=8)
    return _request(
        "DELETE",
        f"/api/oauth/config/{provider.strip().lower()}",
        timeout=8,
    )


def is_authenticated() -> bool:
    if is_skip_enabled():
        return True
    return status() == "connected"


def get_identity() -> Optional[Dict[str, Any]]:
    local = _load_local()
    if not local:
        return None
    if status() != "connected":
        return None
    return local.get("identity")


def get_identity_display() -> str:
    ident = get_identity()
    if not ident:
        return "Unknown (not connected)"
    name = ident.get("name", "?")
    fid = ident.get("fomojiId", "?")
    itype = ident.get("identityType", "PERSON")
    return f"{name} ({fid}) [{itype}]"


# ---------------------------------------------------------------------------
# Device flow — the ONLY way a non-browser client pairs.
# ---------------------------------------------------------------------------

def _device_start(permissions) -> Dict[str, Any]:
    return _request(
        "POST",
        "/api/connector/device/start",
        {
            "applicationId": APPLICATION_ID,
            "permissions": permissions or DEFAULT_PERMISSIONS,
            "connectionType": "standard",
            "environment": "production",
        },
    )


def _device_poll(device_code: str) -> Dict[str, Any]:
    return _request("POST", "/api/connector/device/poll", {"deviceCode": device_code})


def _launch_cat_browser_for_verification(verification_url: str, user_code: str) -> None:
    """Show the verification code in the terminal.

    Browser navigation is handled by bootstrap() — this function only
    prints the code prompt so the user can see it. The CAT browser
    (QWebEngineView) is already open and will navigate to the
    verification page automatically.
    """
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return
    try:
        print()
        try:
            from . import theme
            theme.enable_windows_ansi()
            print(theme.dim("  ┌─────────────────────────────────────────────────────────┐"))
            print(theme.dim("  │ FOMOJI VERIFICATION (CAT Browser)                      │"))
            print(theme.dim("  └─────────────────────────────────────────────────────────┘"))
            print()
            print(theme.cyan(f"  CAT Browser is opening the verification page"))
            print(theme.dim(f"    (URL hidden for security)"))
            print()
            print(theme.cyan(f"  Your code:"))
            print(theme.text(f"    {user_code}", bold=True))
            print()
            print(theme.faint("  Approve the request in CAT's browser, then return here."))
            print(theme.faint("  CAT will detect approval automatically."))
        except Exception:
            print(f"\n  FOMOJI VERIFICATION (CAT Browser)")
            print(f"  Code: {user_code}")
            print(f"  Approve in CAT's browser, then return here.")
    except Exception:
        pass


def device_login(
    permissions=None,
    timeout_seconds: int = 300,
    on_prompt=None,
) -> Dict[str, Any]:
    """
    Run the full device-authorization flow:
      1. POST /device/start  -> device_code, user_code, verificationUrl
      2. Show user_code + verificationUrl for human approval in browser
      3. Poll /device/poll until approved / denied / expired

    Returns the identity dict on success and caches the token locally.
    Raises FomojiAuthError on any terminal failure.
    """
    perms = permissions if permissions is not None else DEFAULT_PERMISSIONS
    # Ensure server is up before starting (auto-start if needed)
    ensure_fomoji_server(auto_start=True, timeout=12)
    start = _device_start(perms)
    device_code = start["deviceCode"]
    user_code = start["userCode"]
    verification_url = f"{get_fomoji_url()}{start.get('verificationUrl', '/connector.html')}"
    poll_interval = int(start.get("pollIntervalSeconds", 3))

    if on_prompt:
        try:
            on_prompt(user_code=user_code, verification_url=verification_url)
        except Exception:
            pass
    else:
        _print_device_prompt(user_code, verification_url)
        # Offer to handle verification inside CAT's own browser (no external browser needed)
        # Only when interactive and polling hasn't yet begun, and user hasn't supplied custom on_prompt.
        if sys.stdin.isatty() and sys.stdout.isatty():
            try:
                _launch_cat_browser_for_verification(verification_url, user_code)
            except Exception:
                pass

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = _device_poll(device_code)
        st = result.get("status")
        if st == "approved":
            identity = {
                "fomojiId": result.get("fomojiId"),
                "name": result.get("name"),
                "identityType": result.get("identityType", "PERSON"),
                "permissions": result.get("permissions", perms),
                "applicationId": result.get("applicationId", APPLICATION_ID),
            }
            _save_local({"token": result["connectorToken"], "identity": identity})
            return identity
        if st == "denied":
            raise FomojiAuthError("Connection request was denied in Fomoji.")
        if st == "expired":
            raise FomojiAuthError("Connection request expired before approval (5 min). Run again.")
        # pending — wait and retry
        time.sleep(poll_interval)

    raise FomojiAuthError("Timed out waiting for approval (no response in time).")


def _print_device_prompt(user_code: str, verification_url: str) -> None:
    """Show the connector code in terminal with easy copy + Windows notification."""
    import subprocess

    # --- Step 1: Print code in terminal FIRST (always visible) ---
    try:
        from . import theme
        theme.enable_windows_ansi()
        print()
        print(theme.panel([
            theme.text("CAT CONNECTOR CODE", bold=True),
            "",
            theme.text(f"     {user_code}     ", bold=True),
            "",
            theme.dim("  1. Log in or create an account on Fomoji"),
            theme.dim("  2. Paste this code on the Connect page"),
            theme.dim("  3. Click Approve"),
            "",
            theme.faint("  Waiting for approval... (Ctrl+C to cancel)"),
        ], title="fomoji auth", color=theme.CYAN, width=60))
        print()
    except Exception:
        print()
        print("=" * 50)
        print("  CAT CONNECTOR CODE")
        print()
        print(f"  >>> {user_code} <<<")
        print()
        print("  1. Log in or create an account on Fomoji")
        print("  2. Paste this code on the Connect page")
        print("  3. Click Approve")
        print("=" * 50)
        print()

    # --- Step 2: Copy to clipboard (background, non-blocking) ---
    def _copy_to_clipboard():
        # Method 1: pyperclip (most reliable)
        try:
            import pyperclip
            pyperclip.copy(user_code)
            return
        except Exception:
            pass
        # Method 2: powershell Set-Clipboard
        try:
            subprocess.run(
                ["powershell", "-Command", f'Set-Clipboard -Value "{user_code}"'],
                capture_output=True, timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            return
        except Exception:
            pass
        # Method 3: clip.exe
        try:
            p = subprocess.Popen(
                ["clip"],
                stdin=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            p.communicate(input=user_code.encode("utf-16le"), timeout=5)
        except Exception:
            pass

    import threading
    threading.Thread(target=_copy_to_clipboard, daemon=True).start()

    # --- Step 3: Show Windows notification (background, non-blocking) ---
    if sys.platform == "win32":
        def _show_notification():
            # Write a .ps1 file to avoid PowerShell escaping issues
            try:
                import tempfile as _tf
                _code = user_code
                _ps1 = _tf.NamedTemporaryFile(
                    suffix=".ps1", prefix="cat_notify_", delete=False, mode="w",
                    encoding="utf-8"
                )
                _ps1.write('Add-Type -AssemblyName System.Windows.Forms\n')
                _ps1.write('$n = New-Object System.Windows.Forms.NotifyIcon\n')
                _ps1.write('$n.Icon = [System.Drawing.SystemIcons]::Information\n')
                _ps1.write('$n.BalloonTipTitle = "CAT - Your Connector Code"\n')
                _ps1.write('$n.BalloonTipText = "' + _code + '"\n')
                _ps1.write('$n.Visible = $true\n')
                _ps1.write('$n.ShowBalloonTip(10000)\n')
                _ps1.write('Start-Sleep -Seconds 3\n')
                _ps1.close()
                subprocess.run(
                    ["powershell", "-ExecutionPolicy", "Bypass", "-File", _ps1.name],
                    capture_output=True, timeout=15,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
                try:
                    os.unlink(_ps1.name)
                except Exception:
                    pass
            except Exception:
                pass

        threading.Thread(target=_show_notification, daemon=True).start()


def stop_fomoji_server() -> bool:
    """Best-effort stop the auto-started Node.js Fomoji server.
    Called on sign-out so the background node process does not linger.
    Returns True if we attempted a stop."""
    stopped = False
    # 1) Try graceful port-based kill via marker + common ports
    try:
        import subprocess as _sp
        import shutil as _sh
        # Try to find node process running fomoji server
        if sys.platform == "win32":
            # taskkill any node running server.js
            for cmd in [
                'taskkill /F /IM node.exe 2>nul',
                'wmic process where "commandline like \'%fomoji%server.js%\'" delete 2>nul',
            ]:
                try:
                    _sp.run(cmd, shell=True, timeout=4, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                            creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0))
                    stopped = True
                except Exception:
                    pass
            # Also try to kill by port 3000 via netstat
            try:
                out = _sp.check_output('netstat -ano | findstr :3000', shell=True, timeout=4, stderr=_sp.DEVNULL, text=True)
                for line in out.splitlines():
                    parts = line.strip().split()
                    if parts:
                        pid = parts[-1]
                        if pid.isdigit():
                            _sp.run(f'taskkill /F /PID {pid}', shell=True, timeout=3, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                                    creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0))
                            stopped = True
            except Exception:
                pass
        else:
            # Unix: pkill / kill
            for kcmd in [['pkill', '-f', 'fomoji.*server.js'], ['pkill', '-f', 'node.*server.js']]:
                try:
                    if _sh.which(kcmd[0]):
                        _sp.run(kcmd, timeout=4, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
                        stopped = True
                except Exception:
                    pass
            # Also try fuser on port 3000
            try:
                if _sh.which('fuser'):
                    _sp.run(['fuser', '-k', '3000/tcp'], timeout=4, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
                    stopped = True
            except Exception:
                pass
    except Exception:
        pass
    # Clean marker/log regardless
    try:
        (Path.home() / ".cat_fomoji_autostart.pid").unlink(missing_ok=True)
    except Exception:
        try:
            (Path.home() / ".cat_fomoji_autostart.pid").unlink()
        except Exception:
            pass
    try:
        (Path.home() / ".cat_fomoji_server.log").unlink(missing_ok=True)
    except Exception:
        try:
            (Path.home() / ".cat_fomoji_server.log").unlink()
        except Exception:
            pass
    return stopped


def logout(clear_local_only: bool = False) -> None:
    """
    Revoke server-side and clear local. If the server is unreachable,
    still clears locally (so the user is not stuck).
    """
    local = _load_local()
    if local and local.get("token") and not clear_local_only:
        try:
            _request(
                "POST",
                "/api/connector/disconnect",
                {"applicationId": APPLICATION_ID},
                auth_token=local["token"],
            )
        except FomojiAuthError:
            pass  # already revoked / server down — still clear locally
    _clear_local()
    # Also stop background Node.js server so it does not linger after sign-out
    try:
        stop_fomoji_server()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Gate — called by cli.main() before ANY UI/REPL/business logic runs.
# ---------------------------------------------------------------------------

def _print_locked_message(reason: str = "") -> None:
    base = get_fomoji_url()
    try:
        from . import theme
        theme.enable_windows_ansi()
        lines = [
            theme.red("CAT IS LOCKED — Fomoji authentication required", bold=True),
            "",
            theme.dim("No valid Fomoji session was found for this device."),
            theme.dim(f"Fomoji server: {base}"),
        ]
        if reason:
            lines.append(theme.orange(f"Reason: {reason}"))
        lines += [
            "",
            theme.text("To authenticate:", bold=True),
            theme.cyan(f"  1. Ensure Fomoji server is running at {base}"),
            theme.dim("     (in fomoji-updated/fomoji-server:  npm install && npm start)"),
            theme.cyan("  2. Run:  cat --auth login"),
            theme.cyan("     or:  python -m calc_terminal.fomoji_auth login"),
            theme.dim("  3. Open the shown URL, enter the code, and approve"),
            "",
            theme.faint("After approval, run `cat` again. Your session is cached at:"),
            theme.faint(f"  {TOKEN_PATH}"),
            "",
            theme.faint("Tip: `cat --auth status` checks the current session."),
        ]
        print()
        print(theme.panel(lines, title="locked", color=theme.RED, width=76))
        print()
    except Exception:
        print("\n[CAT LOCKED] Fomoji authentication required.", file=sys.stderr)
        if reason:
            print(f"Reason: {reason}", file=sys.stderr)
        print(f"Fomoji server: {base}", file=sys.stderr)
        print("Run: cat --auth login  (then open the URL and approve)\n", file=sys.stderr)


def _print_unreachable_help() -> None:
    base = get_fomoji_url()
    try:
        from . import theme
        lines = [
            theme.red("FOMOJI SERVER UNREACHABLE", bold=True),
            theme.dim("Could not reach the Fomoji server"),
            "",
            theme.text("Start the Fomoji server first:", bold=True),
            theme.dim("  cd fomoji-updated/fomoji-server"),
            theme.dim("  npm install"),
            theme.dim("  npm start"),
            "",
            theme.faint("CAT will try to start the server automatically on next launch."),
        ]
        print(theme.panel(lines, title="fomoji", color=theme.RED, width=72))
        print()
    except Exception:
        print(f"\n[FOMOJI] Could not reach the Fomoji server.", file=sys.stderr)
        print("Start it: cd fomoji-updated/fomoji-server && npm start\n", file=sys.stderr)


def require_auth(
    interactive: bool = True,
    auto_prompt: bool = True,
    permissions=None,
) -> bool:
    """
    Ensure a valid Fomoji session exists.  Returns True if authenticated.

    If no session exists and `auto_prompt` is True, this runs the device flow
    interactively (requires a TTY).  When that succeeds it returns True.
    When it cannot (no TTY, user cancelled, server unreachable), it returns
    False — the caller should refuse to start CAT.

    When `auto_prompt` is False it only *checks* and never prompts.

    Persistent session: once `~/.fomoji/connectors/cat.json` is written, every
    future `cat` launch reuses it (status()==connected) and never asks for a
    code again until the server revokes/expires it.
    """
    if is_skip_enabled():
        return True

    # Auto-start server if needed (so `cat` never requires manual `npm start`)
    # This is best-effort and respects FOMOJI_URL remote overrides.
    had_to_start = False
    if not check_server_reachable(timeout=2):
        had_to_start = ensure_fomoji_server(auto_start=True, timeout=10)
        if had_to_start and check_server_reachable(timeout=2):
            try:
                from . import theme
                theme.enable_windows_ansi()
                print(theme.green(f"\n  ✓ Fomoji server auto-started at {get_fomoji_url()}", bold=True))
                print(theme.dim("    (npm start in fomoji-updated/fomoji-server)"))
            except Exception:
                print(f"\n  Fomoji server auto-started at {get_fomoji_url()}")
            # Give it a moment to finish seeding DB
            import time as _t
            _t.sleep(0.5)

    st = status()

    if st == "connected":
        if had_to_start:
            try:
                from . import theme as _th
                print(_th.dim("  Session still valid — no code needed.\n"))
            except Exception:
                pass
        return True

    if st == "server_unreachable":
        # One more auto-start attempt with longer timeout before giving up
        if ensure_fomoji_server(auto_start=True, timeout=15) and check_server_reachable():
            st = status()
            if st == "connected":
                return True
        _print_unreachable_help()
        return False

    if st == "expired":
        print("\n  Your Fomoji session has expired. Re-authenticating...\n")

    if not interactive or not sys.stdin.isatty():
        _print_locked_message(reason=f"status={st} (non-interactive — run `cat --auth login` in a real terminal)")
        return False

    if not auto_prompt:
        _print_locked_message(reason=f"status={st}")
        return False

    # Interactive device flow — ensure server still reachable (auto-start race)
    if not check_server_reachable():
        if not ensure_fomoji_server(auto_start=True, timeout=12) or not check_server_reachable():
            _print_unreachable_help()
            return False

    try:
        ident = device_login(permissions=permissions)
        try:
            from . import theme
            print(theme.green(f"\n  ✓ Authenticated as {ident.get('name')} ({ident.get('fomojiId')})", bold=True))
            print(theme.dim(f"    Permissions: {', '.join(ident.get('permissions', []))}"))
            print(theme.green("    Session cached at ~/.fomoji/connectors/cat.json — next `cat` will start instantly, no code needed.", bold=True))
            print()
        except Exception:
            print(f"\n  Authenticated as {ident.get('name')} ({ident.get('fomojiId')})")
            print("  Session cached — next `cat` will start instantly, no code needed.\n")
        return True
    except KeyboardInterrupt:
        print("\n  Authentication cancelled.\n")
        return False
    except FomojiAuthError as e:
        _print_locked_message(reason=str(e))
        return False
    except Exception as e:
        _print_locked_message(reason=f"{type(e).__name__}: {e}")
        return False


def enforce_or_exit(
    interactive: bool = True,
    auto_prompt: bool = True,
    permissions=None,
) -> None:
    """
    Gate helper for cli.main(): if auth is required and missing, print a
    clear locked message and exit the process with code 1.  Does NOT return
    on failure — the process never reaches bootstrap().
    """
    if require_auth(interactive=interactive, auto_prompt=auto_prompt, permissions=permissions):
        return
    # If skip is enabled we already returned True above, so reaching here
    # means real enforcement.  Exit hard — no fallback path.
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# CLI for `python -m calc_terminal.fomoji_auth`  and  `cat --auth ...`
# ---------------------------------------------------------------------------

def _auth_cli(argv=None) -> int:
    """
    Standalone auth CLI.  Returns exit code.

    Usage:
      cat --auth status
      cat --auth login [--guest | --passkey | --permissions ID,...]
      cat --auth guest
      cat --auth passkey
      cat --auth config [--provider <name> --client-id <id> --client-secret <sec>]
      cat --auth logout
      cat --auth whoami
      python -m calc_terminal.fomoji_auth status|login|guest|passkey|config|logout|whoami
    """
    import argparse

    argv = list(argv if argv is not None else sys.argv[1:])
    # Drop a leading --auth or auth if present
    if argv and argv[0] in ("--auth", "auth"):
        argv = argv[1:]

    # No args -> status
    if not argv:
        argv = ["status"]

    action = argv[0].lower() if argv else "status"
    rest = argv[1:]

    # Parse optional --permissions for login
    perms = None
    if "--permissions" in rest:
        idx = rest.index("--permissions")
        if idx + 1 < len(rest):
            perms = [p.strip() for p in rest[idx + 1].split(",") if p.strip()]
        rest = [a for a in rest if a not in ("--permissions", rest[idx + 1] if idx + 1 < len(rest) else "")]

    if action in ("status", "check"):
        st = status()
        try:
            from . import theme
            theme.enable_windows_ansi()
            if st == "connected":
                ident = get_identity()
                name = ident.get("name", "?") if ident else "?"
                fid = ident.get("fomojiId", "?") if ident else "?"
                itype = ident.get("identityType", "PERSON") if ident else "PERSON"
                is_gst = ident.get("isGuest") or itype == "TEMPORARY"
                print(theme.green(f"  ✓ Connected as {name} ({fid}) [{itype}]", bold=True))
                print(theme.dim(f"    Status: {st}"))
                print(theme.dim(f"    Token:  {TOKEN_PATH}"))
                if is_gst:
                    rem_sec = get_guest_remaining_seconds()
                    if rem_sec is not None:
                        mins = int(rem_sec // 60)
                        hrs = mins // 60
                        rem_m = mins % 60
                        time_str = f"{hrs}h {rem_m}m" if hrs > 0 else f"{mins}m"
                        print(theme.orange(f"    ⏱ Guest Limit: {time_str} remaining (auto-signs out after 2 hours)", bold=True))
                if ident and ident.get("permissions"):
                    print(theme.dim(f"    Permissions: {', '.join(ident['permissions'])}"))
            elif st == "server_unreachable":
                print(theme.red(f"  ✗ Fomoji server unreachable", bold=True))
                print(theme.dim("    Start it: cd fomoji-updated/fomoji-server && npm start"))
            elif st == "expired":
                print(theme.orange(f"  ○ Session expired (2-hour limit reached or revoked)", bold=True))
                print(theme.dim("    Run: cat --auth login  or  cat --auth guest"))
            else:
                print(theme.orange(f"  ○ Not connected (status: {st})", bold=True))
                print(theme.dim(f"    Run: cat --auth login  or  cat --auth guest"))
        except Exception:
            print(st)
        return 0 if st == "connected" else 1

    if action in ("guest", "--guest"):
        if is_authenticated():
            ident = get_identity()
            name = ident.get("name", "?") if ident else "?"
            print(f"  Already connected as {name}. Use `cat --auth logout` to switch.\n")
            return 0
        try:
            ident = guest_login()
            try:
                from . import theme
                theme.enable_windows_ansi()
                print(theme.green("\n  ✓ Connected in Guest Mode (Temporary 2-Hour Session)", bold=True))
                print(theme.dim(f"    Identifier: {ident.get('fomojiId')}"))
                print(theme.orange("    ⏱ Note: Guest access automatically expires in 2 hours.", bold=True))
                print(theme.dim("    After 2 hours, CAT CLI will automatically sign out.\n"))
            except Exception:
                print("\n  ✓ Connected in Guest Mode (Temporary 2-Hour Session)")
                print(f"    Identifier: {ident.get('fomojiId')}")
                print("    ⏱ Note: Guest access automatically expires in 2 hours.\n")
            return 0
        except Exception as e:
            print(f"\n  ✗ Guest login failed: {e}\n")
            return 1

    if action in ("passkey", "--passkey"):
        if not check_server_reachable():
            ensure_fomoji_server(auto_start=True, timeout=12)
        url = f"{get_fomoji_url()}/passkey.html"
        print(f"\n  Opening Fomoji Passkey Authentication in browser...")
        print(f"  URL: {url}\n")
        try:
            from .host.launcher import launch_cat_host, can_launch_host
            if can_launch_host():
                return launch_cat_host(start_browser_url=url, start_mode="browser")
        except Exception:
            pass
        import webbrowser
        webbrowser.open(url)
        return 0

    if action in ("config", "--config", "providers", "--providers", "oauth"):
        p_name = None
        c_id = None
        c_sec = None
        is_del = any(a in ("--delete", "--clear", "--remove", "-d") for a in rest)
        for i, a in enumerate(rest):
            if a in ("--provider", "-p") and i + 1 < len(rest):
                p_name = rest[i + 1]
            elif a in ("--client-id", "--id") and i + 1 < len(rest):
                c_id = rest[i + 1]
            elif a in ("--client-secret", "--secret") and i + 1 < len(rest):
                c_sec = rest[i + 1]

        if p_name and is_del:
            try:
                delete_oauth_credentials(p_name)
                print(f"\n  ✓ Successfully removed OAuth credentials for {p_name.upper()}!\n")
                return 0
            except Exception as e:
                print(f"\n  ✗ Failed to remove OAuth credentials: {e}\n")
                return 1

        if p_name and c_id and c_sec:
            try:
                set_oauth_credentials(p_name, c_id, c_sec)
                print(f"\n  ✓ Successfully configured OAuth credentials for {p_name.upper()}!")
                print(f"    Redirect URI: {get_fomoji_url()}/api/oauth/{p_name.lower()}/callback\n")
                return 0
            except Exception as e:
                print(f"\n  ✗ Failed to save OAuth credentials: {e}\n")
                return 1

        try:
            cfg = get_oauth_config()
            providers = cfg.get("providers", [])
            try:
                from . import theme
                theme.enable_windows_ansi()
                print()
                print(theme.text("  FOMOJI OAUTH AUTHENTICATION CONFIGURATIONS", bold=True))
                print(theme.dim("  " + "─" * 68))
                print(f"  {'Provider':<14} | {'Status':<16} | {'Client ID':<20} | {'Source'}")
                print(theme.dim("  " + "─" * 68))
                for p in providers:
                    label = p.get("label", p.get("key"))
                    sec = p.get("secretSet", False)
                    status_str = theme.green("Configured") if sec else theme.dim("Not configured")
                    cid = p.get("clientId", "") or "-"
                    if len(cid) > 18:
                        cid = cid[:15] + "..."
                    src = p.get("source", "none")
                    print(f"  {label:<14} | {status_str:<25} | {cid:<20} | {src}")
                print(theme.dim("  " + "─" * 68))
                print(theme.faint(f"\n  To configure a provider from CLI:"))
                print(theme.cyan(f"    cat auth config --provider <google|github|microsoft|facebook|apple> --client-id <id> --client-secret <secret>"))
                print(theme.faint(f"  Or open in browser: {get_fomoji_url()}/oauth-config.html\n"))
            except Exception:
                print("\n  OAuth Providers Status:")
                for p in providers:
                    print(f"  - {p.get('label')}: {'Configured' if p.get('secretSet') else 'Not configured'}")
                print(f"\n  Configure via: {get_fomoji_url()}/oauth-config.html\n")
            return 0
        except Exception as e:
            print(f"\n  ✗ Could not load OAuth configuration: {e}\n")
            return 1

    if action in ("login", "connect", "auth"):
        if is_authenticated():
            ident = get_identity()
            name = ident.get("name", "?") if ident else "?"
            print(f"  Already connected as {name}. Use `cat --auth logout` to switch identity.\n")
            return 0

        # Shortcut flags
        if "--guest" in rest or "-g" in rest:
            return _auth_cli(["guest"])
        if "--passkey" in rest:
            return _auth_cli(["passkey"])

        # Interactive selection if running in an interactive terminal
        if sys.stdin.isatty() and sys.stdout.isatty() and not perms:
            try:
                from . import theme
                theme.enable_windows_ansi()
                print()
                print(theme.text("  SELECT AUTHENTICATION METHOD FOR CAT", bold=True))
                print(theme.dim("  " + "─" * 52))
                print(theme.cyan("  [1] Passkey") + theme.dim(" (Face ID / Windows Hello / Security Key)"))
                print(theme.cyan("  [2] OAuth") + theme.dim(" (Google, GitHub, Microsoft, Facebook, Apple)"))
                print(theme.cyan("  [3] Device Approval") + theme.dim(" (Standard code approval in browser)"))
                print(theme.cyan("  [4] Guest Access") + theme.orange(" (2 Hours Temporary — auto-signout)"))
                print(theme.dim("  " + "─" * 52))
                choice = input("  Select [1-4, default=3]: ").strip()
                if choice == "1":
                    return _auth_cli(["passkey"])
                elif choice == "2":
                    url = f"{get_fomoji_url()}/index.html"
                    print(f"\n  Opening OAuth login at {url} ...")
                    import webbrowser
                    webbrowser.open(url)
                    # And start device flow for completion
                    choice = "3"
                elif choice == "4":
                    return _auth_cli(["guest"])
            except (KeyboardInterrupt, EOFError):
                print("\n  Cancelled.\n")
                return 1
            except Exception:
                pass

        if not check_server_reachable():
            _print_unreachable_help()
            return 1
        try:
            ident = device_login(permissions=perms)
            print(f"\n  ✓ Connected as {ident.get('name')} ({ident.get('fomojiId')})\n")
            return 0
        except KeyboardInterrupt:
            print("\n  Cancelled.\n")
            return 1
        except FomojiAuthError as e:
            print(f"\n  ✗ Login failed: {e}\n")
            return 1

    if action in ("logout", "disconnect", "revoke"):
        if not _load_local():
            print("  Not connected — nothing to do.\n")
            return 0
        logout()
        print("  ✓ Disconnected. Run `cat --auth login` to sign in again.\n")
        return 0

    if action in ("whoami", "identity", "me"):
        ident = get_identity()
        if not ident:
            print(f"  Not connected (status: {status()}). Run `cat --auth login`.\n")
            return 1
        print(json.dumps(ident, indent=2))
        return 0

    print(f"  Unknown auth action: {action}")
    print("  Usage: cat --auth <status|login|guest|passkey|config|logout|whoami>")
    return 2


if __name__ == "__main__":
    raise SystemExit(_auth_cli())
