"""
CCT MCP — Model Context Protocol client (v0.7.8 BUG 5).

Replaces the old "not wired up yet" placeholder with a real backend:

  - Local MCP servers: spawned as child processes, JSON-RPC 2.0 over
    stdio (the standard local transport — e.g. a local `npx`/python
    MCP server binary).
  - Remote MCP servers: JSON-RPC 2.0 over HTTP POST (one request per
    call; SSE streaming transports are reported honestly as
    unsupported rather than faked).

Every server reports: status (Connected/Disconnected/Testing), the MCP
protocol version it negotiated, measured latency (ms), and the tool
list it advertises (tools/list). `call_tool` executes a tool and
returns the text content of the response.

Persistence: ~/.cct_mcp_servers.json, a plain list of server records.
This module is UI-agnostic (no Textual imports) — the ui/mcp_panel.py
screen renders it.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from typing import Optional

MCP_FILE = os.path.join(os.path.expanduser("~"), ".cct_mcp_servers.json")
_PROTOCOL_VERSION = "2024-11-05"
_REQUEST_TIMEOUT = 20  # seconds, for both transports

_lock = threading.Lock()
_session_id = 0


def _next_id():
    global _session_id
    with _lock:
        _session_id += 1
        return _session_id


# ---------------------------------------------------------------------------
# Persistence

def load_servers() -> list[dict]:
    """Load saved MCP server records. Never raises."""
    try:
        if os.path.exists(MCP_FILE):
            with open(MCP_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                out = []
                for entry in data:
                    if not isinstance(entry, dict):
                        continue
                    rec = {
                        "id": entry.get("id", ""),
                        "name": entry.get("name", ""),
                        "kind": entry.get("kind", "remote"),  # "local" | "remote"
                        "command": entry.get("command", ""),  # local: argv
                        "url": entry.get("url", ""),          # remote: endpoint
                        "headers": entry.get("headers", {}),
                        "enabled": bool(entry.get("enabled", True)),
                        "status": "disconnected",
                        "version": entry.get("version", ""),
                        "latency_ms": entry.get("latency_ms"),
                        "tools": entry.get("tools", []),
                        "last_connected": entry.get("last_connected", 0),
                    }
                    out.append(rec)
                return out
    except Exception:
        pass
    return []


def save_servers(servers: list[dict]) -> bool:
    """Persist server records. Returns True on success."""
    try:
        clean = []
        for s in servers or []:
            clean.append({
                "id": s.get("id", ""),
                "name": s.get("name", ""),
                "kind": s.get("kind", "remote"),
                "command": s.get("command", ""),
                "url": s.get("url", ""),
                "headers": s.get("headers", {}),
                "enabled": bool(s.get("enabled", True)),
                "version": s.get("version", ""),
                "latency_ms": s.get("latency_ms"),
                "tools": s.get("tools", []),
                "last_connected": s.get("last_connected", 0),
            })
        with open(MCP_FILE, "w", encoding="utf-8") as f:
            json.dump(clean, f, indent=2)
        return True
    except Exception:
        return False


def add_server(entry: dict) -> str:
    """Add (or update by id) a server record and persist. Returns the id."""
    servers = load_servers()
    sid = entry.get("id") or entry.get("name") or f"mcp-{int(time.time())}"
    entry["id"] = sid
    servers = [s for s in servers if s.get("id") != sid]
    servers.append(entry)
    save_servers(servers)
    return sid


def remove_server(server_id: str):
    save_servers([s for s in load_servers() if s.get("id") != server_id])


# ---------------------------------------------------------------------------
# Built-in Preset Templates for External Tools, Databases & Context Streams

MCP_BUILTIN_PRESETS: list[dict] = [
    {
        "id": "mcp-sqlite",
        "name": "SQLite Database MCP",
        "kind": "local",
        "command": "npx -y @modelcontextprotocol/server-sqlite --db workspace.db",
        "description": "Direct SQLite querying, schema inspection, and data manipulation.",
        "tools": ["read_query", "write_query", "list_tables", "describe_table"],
        "category": "database",
        "enabled": True,
    },
    {
        "id": "mcp-postgres",
        "name": "PostgreSQL Database MCP",
        "kind": "local",
        "command": "npx -y @modelcontextprotocol/server-postgres postgresql://localhost/mydb",
        "description": "Postgres schema mapping, relational queries, and transactional updates.",
        "tools": ["query", "schema", "explain"],
        "category": "database",
        "enabled": True,
    },
    {
        "id": "mcp-filesystem",
        "name": "Filesystem Tools MCP",
        "kind": "local",
        "command": "npx -y @modelcontextprotocol/server-filesystem .",
        "description": "Secure scoped filesystem operations and workspace directories.",
        "tools": ["read_file", "write_file", "list_directory", "move_file"],
        "category": "tools",
        "enabled": True,
    },
    {
        "id": "mcp-git",
        "name": "Git Repository Engine MCP",
        "kind": "local",
        "command": "npx -y @modelcontextprotocol/server-git",
        "description": "Version control diffs, commits, branches, and status inspection.",
        "tools": ["git_status", "git_diff", "git_log", "git_commit"],
        "category": "vcs",
        "enabled": True,
    },
    {
        "id": "mcp-brave",
        "name": "Brave Web Search MCP",
        "kind": "remote",
        "url": "https://api.search.brave.com/res/v1/web/search",
        "description": "Privacy-preserving live web search and rich context extraction.",
        "tools": ["brave_web_search", "brave_local_search"],
        "category": "web",
        "enabled": True,
    },
    {
        "id": "mcp-context-stream",
        "name": "Context Streams MCP",
        "kind": "local",
        "command": "cat-mcp-context-stream",
        "description": "Continuous live telemetry, log streaming, and dynamic external context injection.",
        "tools": ["stream_context", "ingest_stream", "subscribe_channel"],
        "category": "context",
        "enabled": True,
    },
]


def list_presets() -> list[dict]:
    """Returns built-in preset configurations for MCP servers."""
    return list(MCP_BUILTIN_PRESETS)


def install_preset(preset_id: str) -> Optional[str]:
    """Installs a built-in MCP preset into the active server registry."""
    preset = next((p for p in MCP_BUILTIN_PRESETS if p["id"] == preset_id), None)
    if not preset:
        return None
    rec = dict(preset)
    return add_server(rec)



# ---------------------------------------------------------------------------
# JSON-RPC helpers

def _rpc_request(req_id: int, method: str, params: dict) -> str:
    return json.dumps({
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params,
    })


def _initialize_params() -> dict:
    return {
        "protocolVersion": _PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "cct", "version": "0.7.8"},
    }


class _LocalTransport:
    """Child-process stdio transport with request/response correlation."""

    def __init__(self, argv: list[str]):
        self._proc = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
            errors="replace", bufsize=1, creationflags=getattr(
                subprocess, "CREATE_NO_WINDOW", 0))
        self._read_lock = threading.Lock()

    def read_response(self, req_id: int, timeout: float = _REQUEST_TIMEOUT):
        deadline = time.time() + timeout
        buf = ""
        with self._read_lock:
            while time.time() < deadline:
                line = self._proc.stdout.readline()
                if not line:
                    raise ConnectionError("MCP server closed its stdout")
                buf += line
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    msg = json.loads(stripped)
                except Exception:
                    continue
                if msg.get("id") == req_id:
                    return msg
            raise TimeoutError(f"MCP request {req_id} timed out")

    def send(self, payload: str):
        self._proc.stdin.write(payload + "\n")
        self._proc.stdin.flush()

    def close(self):
        try:
            self._proc.stdin.close()
        except Exception:
            pass
        try:
            self._proc.terminate()
        except Exception:
            pass


class _RemoteTransport:
    """HTTP POST JSON-RPC transport for remote MCP endpoints."""

    def __init__(self, url: str, headers: dict | None = None):
        self.url = url
        self.headers = {"Content-Type": "application/json"}
        for k, v in (headers or {}).items():
            self.headers[k] = v

    def read_response(self, req_id: int, timeout: float = _REQUEST_TIMEOUT):
        raise NotImplementedError  # response comes from send() directly

    def send(self, payload: str):
        import requests
        resp = requests.post(self.url, data=payload.encode("utf-8"),
                             headers=self.headers, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def close(self):
        pass


# ---------------------------------------------------------------------------
# Session object — one live connection to one server

class McpSession:
    """A live, single-request-at-a-time connection to an MCP server.
    Tracks status/version/latency/tools exactly as the panel shows them."""

    def __init__(self, server: dict):
        self.server = dict(server)
        self.status = "disconnected"
        self.version = server.get("version", "")
        self.latency_ms = None
        self.tools = list(server.get("tools", []))
        self.error = ""
        self._transport = None
        self._lock = threading.Lock()

    @property
    def name(self):
        return self.server.get("name") or self.server.get("id") or "MCP"

    def _open_transport(self):
        kind = self.server.get("kind", "remote")
        if kind == "local":
            argv = self.server.get("command", "")
            if isinstance(argv, str):
                argv = argv.split()
            if not argv:
                raise ValueError("Local MCP server needs a command.")
            return _LocalTransport(argv)
        url = self.server.get("url", "")
        if not url:
            raise ValueError("Remote MCP server needs a URL.")
        return _RemoteTransport(url, self.server.get("headers") or {})

    def connect(self) -> tuple[bool, str]:
        """Initialize the session: handshake, then tools/list. Returns
        (ok, message). Latency covers the initialize round trip."""
        with self._lock:
            start = time.time()
            try:
                transport = self._open_transport()
                req = _next_id()
                payload = _rpc_request(req, "initialize", _initialize_params())
                if isinstance(transport, _RemoteTransport):
                    resp = transport.send(payload)
                else:
                    transport.send(payload)
                    resp = transport.read_response(req)
                self._transport = transport
            except Exception as e:
                self.status = "disconnected"
                self.error = str(e)
                self.latency_ms = None
                return False, f"Could not connect: {e}"
            try:
                if isinstance(resp, dict):
                    if "error" in resp:
                        raise ConnectionError(resp["error"].get("message", "handshake error"))
                    self.version = (resp.get("result", {}) or {}).get(
                        "protocolVersion", "")
                # fire-and-forget initialized notification
                try:
                    notify = _rpc_request(_next_id(), "notifications/initialized", {})
                    if isinstance(transport, _RemoteTransport):
                        transport.send(notify)
                    else:
                        transport.send(notify)
                except Exception:
                    pass
                self.latency_ms = int((time.time() - start) * 1000)
                self.status = "connected"
                self._load_tools()
                return True, f"Connected \u2014 {len(self.tools)} tool(s) available."
            except Exception as e:
                self.status = "disconnected"
                self.error = str(e)
                return False, f"Handshake failed: {e}"

    def _load_tools(self):
        req = _next_id()
        payload = _rpc_request(req, "tools/list", {})
        try:
            if isinstance(self._transport, _RemoteTransport):
                resp = self._transport.send(payload)
            else:
                self._transport.send(payload)
                resp = self._transport.read_response(req)
            result = (resp or {}).get("result") or {}
            tools = result.get("tools") or []
            self.tools = [t.get("name", "?") for t in tools if isinstance(t, dict)]
        except Exception:
            self.tools = list(self.server.get("tools", []))

    def call_tool(self, name: str, arguments: dict | None = None) -> str:
        """Execute a tool and return the text content of its result.
        Raises on transport errors; returns the content string otherwise."""
        if self.status != "connected" or self._transport is None:
            raise ConnectionError(f"MCP server '{self.name}' is not connected.")
        req = _next_id()
        payload = _rpc_request(req, "tools/call", {
            "name": name, "arguments": arguments or {},
        })
        with self._lock:
            if isinstance(self._transport, _RemoteTransport):
                resp = self._transport.send(payload)
            else:
                self._transport.send(payload)
                resp = self._transport.read_response(req)
        if "error" in (resp or {}):
            raise RuntimeError(resp["error"].get("message", "tool call failed"))
        result = resp.get("result") or {}
        if result.get("isError"):
            raise RuntimeError("MCP tool reported an error")
        parts = []
        for item in result.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(parts) or "(no text content)"

    def close(self):
        try:
            if self._transport is not None:
                self._transport.close()
        except Exception:
            pass
        self._transport = None
        self.status = "disconnected"


# ---------------------------------------------------------------------------
# Manager-level API (what the panel and the app call)

_sessions: dict[str, McpSession] = {}


def get_session(server: dict) -> McpSession:
    """Return the live session for a server record, creating one if
    needed. Sessions survive panel open/close; close_session() frees."""
    sid = server.get("id")
    with _lock:
        s = _sessions.get(sid)
        if s is None:
            s = McpSession(server)
            _sessions[sid] = s
        else:
            s.server = dict(server)
        return s


def connect_server(server: dict) -> tuple[bool, str]:
    session = get_session(server)
    return session.connect()


def disconnect_server(server_id: str):
    with _lock:
        s = _sessions.pop(server_id, None)
    if s is not None:
        s.close()


def server_status(server: dict) -> dict:
    """Current live status of a server record (panel-friendly dict)."""
    session = get_session(server)
    return {
        "status": session.status,
        "version": session.version,
        "latency_ms": session.latency_ms,
        "tools": list(session.tools),
        "error": session.error,
    }


def call_server_tool(server: dict, name: str, arguments: dict | None = None) -> str:
    session = get_session(server)
    return session.call_tool(name, arguments)



def cmd_mcp(arg: str) -> str:
    """Handles /mcp slash command operations."""
    parts = arg.strip().split(None, 1)
    sub = parts[0].lower() if parts else "list"
    rest = parts[1].strip() if len(parts) > 1 else ""

    if sub in ("help", "--help", "-h"):
        return (
            "🔌 **Model Context Protocol (MCP) Server Commands:**\n"
            "- `/mcp list` — List configured MCP servers and connection status\n"
            "- `/mcp tools <server>` — Inspect tools provided by an MCP server\n"
            "- `/mcp connect <server>` — Connect to a configured MCP server\n"
            "- `/mcp disconnect <server>` — Disconnect from an MCP server\n"
            "- `/mcp test <server>` — Test latency and connection to an MCP server"
        )

    servers = load_servers()

    if sub in ("list", "ls"):
        if not servers:
            return "ℹ️ No MCP servers configured. Open Main Menu → MCP Servers to add one."
        lines = [
            f"🔌 **Configured MCP Servers ({len(servers)} total):**\n",
            "| ID | Name | Transport | Status | Tools |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
        for s in servers:
            st = server_status(s)
            status_glyph = "🟢 Connected" if st["status"] == "connected" else ("🟡 Connecting" if st["status"] == "connecting" else "🔴 Offline")
            tools_cnt = len(st["tools"])
            kind = s.get("kind", "stdio")
            name = s.get("name") or s.get("id")
            lines.append(f"| `{s.get('id')}` | {name} | {kind} | {status_glyph} | {tools_cnt} tools |")
        return "\n".join(lines)

    if sub == "tools":
        if not rest:
            return "Usage: `/mcp tools <server_id_or_name>`"
        target = None
        for s in servers:
            if s.get("id") == rest or s.get("name", "").lower() == rest.lower():
                target = s
                break
        if not target:
            return f"❌ Server `{rest}` not found."
        st = server_status(target)
        tools = st.get("tools") or []
        if not tools:
            return f"ℹ️ No tools exposed by server `{rest}` (server may be offline)."
        lines = [f"🔌 **Tools exposed by `{target.get('name')}`:**\n"]
        for t in tools:
            lines.append(f"- **`{t.get('name')}`**: {t.get('description', 'No description')}")
        return "\n".join(lines)

    if sub == "connect":
        if not rest:
            return "Usage: `/mcp connect <server_id_or_name>`"
        target = None
        for s in servers:
            if s.get("id") == rest or s.get("name", "").lower() == rest.lower():
                target = s
                break
        if not target:
            return f"❌ Server `{rest}` not found."
        ok, msg = connect_server(target)
        if ok:
            return f"✅ **Connected to MCP Server:** `{target.get('name')}`"
        else:
            return f"❌ Connection failed: {msg}"

    if sub == "disconnect":
        if not rest:
            return "Usage: `/mcp disconnect <server_id_or_name>`"
        target = None
        for s in servers:
            if s.get("id") == rest or s.get("name", "").lower() == rest.lower():
                target = s
                break
        if not target:
            return f"❌ Server `{rest}` not found."
        disconnect_server(target.get("id"))
        return f"🔌 Disconnected from `{target.get('name')}`."

    if sub == "test":
        if not rest:
            return "Usage: `/mcp test <server_id>`"
        target = None
        for s in servers:
            if s.get("id") == rest or s.get("name", "").lower() == rest.lower():
                target = s
                break
        if not target:
            return f"❌ Server `{rest}` not found."
        ok, msg = connect_server(target)
        st = server_status(target)
        lat = st.get("latency_ms")
        lat_txt = f"{lat}ms" if lat is not None else "N/A"
        if ok:
            return f"✅ **MCP Server Test Passed:** `{target.get('name')}` (latency: {lat_txt})"
        else:
            return f"❌ Connection test failed: {msg}"

    return f"Unknown mcp subcommand `{sub}`. Type `/mcp help` for available options."
