"""
Fomoji Connector (Python)
=========================

Reusable Python-side connector for CAT and any future Python project that
wants to sign in with a Fomoji identity.

Architecture
------------
    Fomoji (Node/Express, owns identity + auth)
       ^
       | HTTP, device-authorization flow
       |
    connector.py  <-- you are here
       ^
       |
    CAT / future Python project

This module does NOT implement authentication. It never sees a password,
a passkey ceremony, or a session cookie. All it ever holds is a *scoped,
revocable* connector token, handed to it once by Fomoji's server after a
real person approved the connection in their browser. That's the whole
point of the device-authorization flow (RFC 8628 shape, same as
`gh auth login` / `docker login`): a CLI/desktop Python process has no
browser of its own to redirect through, so instead it shows a short code,
a human enters/approves it on the Fomoji site, and this module polls
until that happens.

Usage
-----
    from connector import FomojiConnector

    conn = FomojiConnector(application_id="cat", fomoji_url="http://localhost:3000")
    identity = conn.connect(permissions=["IDENTITY", "CAT_ACCESS"])
    print(f"Connected as {identity['name']} ({identity['fomojiId']})")

    conn.status()        # -> "connected" | "not_connected" | "expired"
    conn.disconnect()

Or from the command line:

    python connector.py connect --app cat --permissions IDENTITY,CAT_ACCESS
    python connector.py status  --app cat
    python connector.py disconnect --app cat

Configuration is structured, not hard-coded to CAT — any Python project
can instantiate FomojiConnector with its own application_id, as long as
that application_id has been registered server-side (see
POST /api/connector/applications/register in the Node project, which is
gated by a server-to-server secret CAT/this module never needs).

Storage
-------
The connector token (and nothing else — never a password, never a
passkey secret) is cached locally per application at
``~/.fomoji/connectors/<application_id>.json``, written with 0600
permissions. Delete that file (or call ``disconnect()``) to forget the
connection locally; call ``disconnect()`` to also revoke it server-side.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_FOMOJI_URL = os.environ.get("FOMOJI_URL", "http://localhost:3000")
CONNECTOR_DIR = Path(os.environ.get("FOMOJI_CONNECTOR_DIR", str(Path.home() / ".fomoji" / "connectors")))


class FomojiConnectorError(Exception):
    """Raised for any connector request Fomoji's server refused or that
    failed outright. Always carries a clear, specific message — never a
    silent None/False."""


@dataclass
class ConnectorConfig:
    """Structured, non-hard-coded connector configuration — the same
    shape any future project's connector.py call site would fill in."""

    application_id: str
    permissions: List[str] = field(default_factory=list)
    connection_type: str = "standard"
    environment: str = "production"
    fomoji_url: str = DEFAULT_FOMOJI_URL


class FomojiConnector:
    """Client for one (application_id, Fomoji server) pair. Create one
    instance per application your Python project registers as."""

    def __init__(
        self,
        application_id: str,
        fomoji_url: str = DEFAULT_FOMOJI_URL,
        connection_type: str = "standard",
        environment: str = "production",
    ):
        if not application_id:
            raise FomojiConnectorError("application_id is required")
        self.application_id = application_id
        self.fomoji_url = fomoji_url.rstrip("/")
        self.connection_type = connection_type
        self.environment = environment
        self._token_path = CONNECTOR_DIR / f"{application_id}.json"

    # ---- local token storage -------------------------------------------------

    def _load_local(self) -> Optional[Dict[str, Any]]:
        if not self._token_path.exists():
            return None
        try:
            return json.loads(self._token_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def _save_local(self, data: Dict[str, Any]) -> None:
        CONNECTOR_DIR.mkdir(parents=True, exist_ok=True)
        self._token_path.write_text(json.dumps(data, indent=2))
        # Never leave the connector token world/group-readable.
        try:
            os.chmod(self._token_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

    def _clear_local(self) -> None:
        try:
            self._token_path.unlink()
        except FileNotFoundError:
            pass

    # ---- HTTP plumbing ---------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        auth_token: Optional[str] = None,
        query: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.fomoji_url}{path}"
        if query:
            from urllib.parse import urlencode

            url = f"{url}?{urlencode(query)}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if auth_token:
            req.add_header("Authorization", f"Bearer {auth_token}")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8")
            try:
                parsed = json.loads(raw)
                message = parsed.get("error", raw)
            except json.JSONDecodeError:
                message = raw or str(e)
            raise FomojiConnectorError(f"Fomoji connector request failed ({e.code}): {message}") from None
        except urllib.error.URLError as e:
            raise FomojiConnectorError(f"Could not reach Fomoji at {self.fomoji_url}: {e.reason}") from None

    # ---- public API --------------------------------------------------------

    def connect(
        self,
        permissions: Optional[List[str]] = None,
        timeout_seconds: int = 300,
        on_prompt=None,
    ) -> Dict[str, Any]:
        """Pair this Python process with a Fomoji identity.

        Prints (or passes to ``on_prompt``) a short user code and
        verification URL for the person to open in a browser and
        approve, then polls until they do (or the request expires).
        Returns the identity dict Fomoji sends back on success and
        caches the connector token locally for future calls.
        """
        existing = self._load_local()
        if existing and self.status() == "connected":
            return existing["identity"]

        start = self._request(
            "POST",
            "/api/connector/device/start",
            {
                "applicationId": self.application_id,
                "permissions": permissions or [],
                "connectionType": self.connection_type,
                "environment": self.environment,
            },
        )
        device_code = start["deviceCode"]
        user_code = start["userCode"]
        verification_url = f"{self.fomoji_url}{start['verificationUrl']}"
        poll_interval = start.get("pollIntervalSeconds", 3)

        prompt = (
            f"To connect {self.application_id!r} to your Fomoji identity:\n"
            f"  1. Open {verification_url}\n"
            f"  2. Enter code: {user_code}\n"
            f"  3. Approve the request\n"
            f"Waiting for approval..."
        )
        if on_prompt:
            on_prompt(user_code=user_code, verification_url=verification_url)
        else:
            print(prompt, file=sys.stderr)

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            result = self._request("POST", "/api/connector/device/poll", {"deviceCode": device_code})
            status = result.get("status")
            if status == "approved":
                identity = {
                    "fomojiId": result["fomojiId"],
                    "name": result["name"],
                    "identityType": result["identityType"],
                    "permissions": result["permissions"],
                    "applicationId": result["applicationId"],
                }
                self._save_local({"token": result["connectorToken"], "identity": identity})
                return identity
            if status == "denied":
                raise FomojiConnectorError("Connection request was denied.")
            if status == "expired":
                raise FomojiConnectorError("Connection request expired before it was approved.")
            time.sleep(poll_interval)

        raise FomojiConnectorError("Timed out waiting for approval.")

    def status(self) -> str:
        """Returns 'connected', 'not_connected', or 'expired' — never
        raises just because there's no local connection yet."""
        local = self._load_local()
        if not local:
            return "not_connected"
        try:
            result = self._request(
                "GET", "/api/connector/status", auth_token=local["token"], query={"applicationId": self.application_id}
            )
        except FomojiConnectorError:
            return "not_connected"
        status = result.get("status", "not_connected")
        if status != "connected":
            self._clear_local()
        return status

    def request_permission(self, permissions: List[str], timeout_seconds: int = 300) -> Dict[str, Any]:
        """Ask for an updated permission set — runs the same device flow
        again (a person always re-approves a changed scope; permissions
        are never silently escalated)."""
        return self.connect(permissions=permissions, timeout_seconds=timeout_seconds)

    def disconnect(self) -> None:
        """Revoke the connection server-side and forget it locally."""
        local = self._load_local()
        if local:
            try:
                self._request(
                    "POST",
                    "/api/connector/disconnect",
                    {"applicationId": self.application_id},
                    auth_token=local["token"],
                )
            except FomojiConnectorError:
                pass  # already gone server-side (e.g. revoked elsewhere) — still clear locally
        self._clear_local()


# ---- CLI -------------------------------------------------------------------


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Fomoji connector — pair a Python app with a Fomoji identity.")
    parser.add_argument("action", choices=["connect", "status", "disconnect"])
    parser.add_argument("--app", required=True, dest="application_id", help="application_id, e.g. 'cat'")
    parser.add_argument("--permissions", default="", help="comma-separated, e.g. IDENTITY,CAT_ACCESS")
    parser.add_argument("--fomoji-url", default=DEFAULT_FOMOJI_URL)
    args = parser.parse_args()

    conn = FomojiConnector(application_id=args.application_id, fomoji_url=args.fomoji_url)

    if args.action == "connect":
        perms = [p.strip() for p in args.permissions.split(",") if p.strip()]
        identity = conn.connect(permissions=perms)
        print(json.dumps(identity, indent=2))
    elif args.action == "status":
        print(conn.status())
    elif args.action == "disconnect":
        conn.disconnect()
        print("disconnected")


if __name__ == "__main__":
    _cli()
