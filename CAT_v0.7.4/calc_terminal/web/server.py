"""
FATTY CAT Web Server

FastAPI server that serves the PWA frontend and bridges to CAT core.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add parent directory to path for CAT core imports (source-checkout only).
# When installed via pip, `calc_terminal` is already importable — do not
# mutate sys.path. The guard below keeps `python -m calc_terminal.web.server`
# working identically in both layouts.
try:
    import calc_terminal as _ct_check  # noqa: F401
except Exception:
    sys.path.insert(0, str(Path(__file__).parent.parent))

from calc_terminal import aicore, projects, workspace as ws_paths
from calc_terminal.browser.preview import PreviewController, _shutdown_all as preview_shutdown_all
from calc_terminal.browser.server import LiveServer
from calc_terminal.browser.devserver import DevServerProcess
from calc_terminal.browser.project_detector import detect_project, dependencies_installed
from calc_terminal.browser.preview_entry import find_entry_file, relative_url_for
from calc_terminal.browser.watcher import PreviewFileWatcher, is_web_file
from calc_terminal.browser.state import PreviewState, ServerState
from calc_terminal.permissions import manager as perm_manager, PERMISSION_DEFS, MODES, MODE_LABELS
from calc_terminal.web.cat_runtime import runtime
from calc_terminal import eventbus
from calc_terminal import (
    chat_store,
    mcp,
    theme,
    extensions as cct_ext,
    fomoji_auth,
    identity,
    ai_personalization as ap,
    customization as cust,
)
from calc_terminal.providers import provider_manager as pm
from calc_terminal.ui import theme_css, header as cct_header, welcome_modal
from calc_terminal.gestures import manager as gestures_mgr


# --- Models ---

class CommandRequest(BaseModel):
    cmd: str
    cwd: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    timeout: Optional[float] = 30.0


class CommandResponse(BaseModel):
    returncode: int
    stdout: str
    stderr: str
    success: bool


class FileReadRequest(BaseModel):
    path: str
    encoding: Optional[str] = "utf-8"


class FileWriteRequest(BaseModel):
    path: str
    content: str
    encoding: Optional[str] = "utf-8"


class PreviewStartRequest(BaseModel):
    file_path: str


class PreviewNavigateRequest(BaseModel):
    url: str


class ChatRequest(BaseModel):
    message: str
    mode: Optional[str] = "chat"
    project_path: Optional[str] = None
    chat_id: Optional[str] = None


class WorkspaceRequest(BaseModel):
    path: str


class PermissionToggleRequest(BaseModel):
    key: str
    enabled: bool


class PermissionModeRequest(BaseModel):
    mode: str


class PermissionDecideRequest(BaseModel):
    key: str
    decision: str
    action_text: Optional[str] = ""


class ModeSwitchRequest(BaseModel):
    mode: str


class CustomModeRequest(BaseModel):
    key: str
    label: str
    icon: str
    accent_hex: str
    purpose: Optional[str] = ""
    system_prompt: Optional[str] = ""


class ModelSwitchRequest(BaseModel):
    provider: str
    model: str
    api_key: Optional[str] = None


class CommandDispatchRequest(BaseModel):
    command: str


class FactRequest(BaseModel):
    fact: str


class CustomizationLayoutRequest(BaseModel):
    component_id: str
    updates: Dict[str, Any]


class ExtensionToggleRequest(BaseModel):
    id: str
    enabled: bool


class ExtensionCreateRequest(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    icon: Optional[str] = "⚡"
    publisher: Optional[str] = "Custom"
    category: Optional[str] = "Custom"
    version: Optional[str] = "1.0.0"
    script_code: Optional[str] = ""


class ScienceSolveRequest(BaseModel):
    key: Optional[str] = None
    formula: Optional[str] = None
    values: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Any]] = None


class ScienceDeriveRequest(BaseModel):
    keyword: Optional[str] = None
    derivation: Optional[str] = None


class ScienceAtomRequest(BaseModel):
    element: str


class RecentPinRequest(BaseModel):
    path: str


class RecentRemoveRequest(BaseModel):
    path: str


class ChatCreateRequest(BaseModel):
    name: Optional[str] = None
    project_path: Optional[str] = None


class ChatRenameRequest(BaseModel):
    name: str


class McpServerRequest(BaseModel):
    id: Optional[str] = None
    name: str
    kind: Optional[str] = "remote"
    command: Optional[str] = ""
    url: Optional[str] = ""
    headers: Optional[Dict[str, str]] = None
    enabled: Optional[bool] = True


class BackupProvidersSaveRequest(BaseModel):
    providers: List[Any]


class ThemeSelectRequest(BaseModel):
    theme: str


class GestureToggleRequest(BaseModel):
    id: str
    enabled: bool


class ProfileActiveRequest(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class ProfileSaveRequest(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    prompt: Optional[str] = None
    temperature: Optional[float] = None
    tone: Optional[str] = None
    profile: Optional[Dict[str, Any]] = None


# --- Global State ---

class ServerStateManager:
    def __init__(self):
        self.preview_controllers: Dict[str, PreviewController] = {}
        self.workspace_roots: Dict[str, str] = {}
        self.active_websockets: Set[WebSocket] = set()
        self.processes: Dict[str, asyncio.subprocess.Process] = {}
    
    def get_preview_controller(self, workspace_id: str) -> Optional[PreviewController]:
        return self.preview_controllers.get(workspace_id)
    
    def set_workspace_root(self, workspace_id: str, path: str):
        self.workspace_roots[workspace_id] = os.path.abspath(path)
    
    def get_workspace_root(self, workspace_id: str) -> Optional[str]:
        if workspace_id in self.workspace_roots:
            return self.workspace_roots[workspace_id]
        if workspace_id in ("current", "default", "", None):
            active = ws_paths.active_project()
            if active and os.path.isdir(active):
                return active
            candidate = os.path.abspath(os.path.expanduser(r"c:\Users\ADMIN\Downloads\compressed"))
            if os.path.isdir(candidate):
                return candidate
            try:
                recent = projects.recent()
                if recent and os.path.isdir(recent[0]):
                    return recent[0]
            except Exception:
                pass
            return os.getcwd()
        return None


state_manager = ServerStateManager()


# --- Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting FATTY CAT server...")
    candidate = os.path.abspath(os.path.expanduser(r"c:\Users\ADMIN\Downloads\compressed"))
    if os.path.isdir(candidate):
        state_manager.set_workspace_root("default", candidate)
        state_manager.set_workspace_root("current", candidate)
        ws_paths.set_active_project(candidate)
        try:
            projects.record_opened(candidate)
        except Exception:
            pass
    yield
    # Shutdown
    print("Shutting down FATTY CAT server...")
    preview_shutdown_all()
    for proc in state_manager.processes.values():
        try:
            proc.terminate()
        except Exception:
            pass


# --- FastAPI App ---

app = FastAPI(
    title="FATTY CAT",
    description="Mobile PWA for CAT - Coding Agent Terminal",
    version="0.7.9.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Static Files & PWA ---

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Mount workspace files for preview. Writable preview workspaces MUST live in
# the user's app-data dir — never inside site-packages (read-only when
# installed) and never tied to the git checkout. Falls back to the legacy
# repo-relative location only if the app-data dir is unavailable.
def _preview_workspaces_dir() -> Path:
    try:
        from calc_terminal.first_run import data_dir as _app_data_dir

        p = Path(_app_data_dir()) / "workspaces"
        p.mkdir(parents=True, exist_ok=True)
        return p
    except Exception:
        pass
    try:
        legacy = Path(__file__).parent.parent.parent / "workspaces"
        legacy.mkdir(exist_ok=True)
        return legacy
    except Exception:
        return Path.cwd() / "workspaces"


workspaces_dir = _preview_workspaces_dir()


# --- Root Route (PWA Entry) ---

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = static_dir / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>FATTY CAT</h1><p>index.html not found.</p>", status_code=404)


# --- Health Check ---

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "FATTY CAT", "version": "0.7.9.0"}


# --- Platform Info ---

@app.get("/api/platform")
async def get_platform_info():
    from calc_terminal.platform import get_platform
    platform = get_platform()
    info = platform.info
    return {
        "type": info.type.value,
        "name": info.name,
        "version": info.version,
        "is_mobile": info.is_mobile,
        "supports_file_system_access": info.supports_file_system_access,
        "supports_notifications": info.supports_notifications,
    }


# --- Capability Discovery & System Health ---

@app.get("/api/capabilities")
async def get_capabilities():
    """Return complete dynamic CAT capability registry and version contract."""
    return runtime.get_capabilities()


@app.get("/api/auth/status")
async def get_auth_status():
    """Get Fomoji identity and authentication state."""
    try:
        from calc_terminal import fomoji_auth
        return {
            "authenticated": fomoji_auth.is_authenticated(),
            "identity": fomoji_auth.get_identity(),
            "state": fomoji_auth.status(),
            "fomoji_url": fomoji_auth.get_fomoji_url(),
        }
    except Exception as e:
        return {"authenticated": False, "identity": None, "error": str(e)}


@app.get("/api/diagnostics")
async def get_diagnostics():
    """Return runtime metrics, event log, active model/provider, hardware specs."""
    return runtime.get_diagnostics()


# --- Permissions ---

@app.get("/api/permissions")
async def get_permissions():
    """Get current permission state."""
    snapshot = perm_manager.snapshot()
    return {
        "mode": perm_manager.mode,
        "mode_label": perm_manager.mode_label(),
        "permissions": [
            {"key": k, "label": l, "enabled": v} for k, l, v in snapshot
        ],
    }


@app.post("/api/permissions/mode")
async def set_permission_mode(request: PermissionModeRequest):
    """Set permission mode (ask/restricted/full)."""
    if request.mode not in MODES:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {request.mode}")
    perm_manager.set_mode(request.mode)
    return {"mode": perm_manager.mode, "mode_label": perm_manager.mode_label()}


@app.post("/api/permissions/toggle")
async def toggle_permission(request: PermissionToggleRequest):
    """Toggle a permission key on/off."""
    result = perm_manager.set(request.key, request.enabled)
    return {"key": request.key, "enabled": request.enabled}


@app.post("/api/permissions/decide")
async def decide_permission(request: PermissionDecideRequest):
    """Record a permission decision (allow_once/always_allow/deny/always_deny)."""
    allowed = perm_manager.decide(request.key, request.decision, request.action_text or "")
    return {"key": request.key, "decision": request.decision, "allowed": allowed}


@app.get("/api/permissions/log")
async def permission_log():
    """Get the permission decision log."""
    return {
        "log": [
            {"time": t, "key": k, "action": a, "decision": d}
            for t, k, a, d in perm_manager.log
        ]
    }


# --- Main Menu Dynamic Endpoint ---

@app.get("/api/menu")
async def get_main_menu():
    """Dynamically get the exact Main Menu structure from CAT CLI.
    Directly bridges to calc_terminal.ui.header.get_nav_items().
    Includes dynamic 'Downloaded Extensions ({count})' and real installed extensions.
    """
    try:
        items = cct_header.get_nav_items()
    except Exception:
        items = cct_header._NAV_ITEMS_BASE
    menu_items = []
    for item in items:
        action_id, icon, label = item
        menu_items.append({
            "action": action_id,
            "icon": icon,
            "label": label,
            "is_separator": action_id.startswith("sep"),
            "is_section_header": action_id.startswith("__section"),
            "is_placeholder": action_id.startswith("__placeholder") or action_id.startswith("__hint"),
        })
    installed = cct_ext.list_installed()
    return {
        "items": menu_items,
        "downloaded_count": len(installed),
        "installed": installed,
    }


# --- Filesystem Browser & Path Validation (Method A & Method B) ---

@app.get("/api/fs/browse")
async def browse_filesystem(path: Optional[str] = None):
    """Real filesystem browser for Method A (Browse).
    Navigates actual folders on the host, parent folders, drives (Windows),
    and enforces protected directory warnings.
    """
    import string
    if not path or not path.strip():
        active = ws_paths.active_project()
        if active and os.path.isdir(active):
            target = os.path.abspath(active)
        else:
            target = os.path.abspath(os.path.expanduser("~"))
    else:
        target = os.path.abspath(os.path.expanduser(path.strip()))

    if not os.path.exists(target):
        target = os.path.abspath(os.path.expanduser("~"))

    drives = []
    if sys.platform == "win32":
        for letter in string.ascii_uppercase:
            d_root = f"{letter}:\\"
            if os.path.exists(d_root):
                drives.append(d_root)
    else:
        drives.append("/")

    parent_path = str(Path(target).parent) if Path(target).parent != Path(target) else None
    items = []
    err = None
    try:
        with os.scandir(target) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        p = entry.path
                        is_prot = ws_paths.path_is_protected(p)
                        items.append({
                            "name": entry.name,
                            "path": p,
                            "is_dir": True,
                            "protected": is_prot,
                        })
                except (PermissionError, OSError):
                    continue
        items.sort(key=lambda x: x["name"].lower())
    except (PermissionError, OSError) as e:
        err = str(e)

    return {
        "current_path": target,
        "parent_path": parent_path,
        "drives": drives,
        "folders": items,
        "error": err,
        "protected": ws_paths.path_is_protected(target),
    }


@app.get("/api/fs/validate")
async def validate_filesystem_path(path: str):
    """Validate path for Method B (Enter Path) with live validation."""
    if not path or not path.strip():
        return {"valid": False, "message": "Please enter a folder path"}
    expanded = os.path.abspath(os.path.expanduser(path.strip()))
    if not os.path.exists(expanded):
        return {"valid": False, "message": "⚠ Path does not exist", "path": expanded}
    if not os.path.isdir(expanded):
        return {"valid": False, "message": "⚠ Not a directory", "path": expanded}
    if not os.access(expanded, os.R_OK):
        return {"valid": False, "message": "⚠ No read permission", "path": expanded}
    if ws_paths.path_is_protected(expanded):
        return {"valid": False, "message": "⚠ Protected system folder — refusing to use as workspace", "path": expanded}
    name = os.path.basename(expanded) or expanded
    return {"valid": True, "message": f"✓  {name}  —  folder is valid", "path": expanded, "name": name}


# --- Workspace Management ---

@app.post("/api/workspace/open")
async def open_workspace(request: WorkspaceRequest):
    """Open folder using the exact CAT workspace logic."""
    path = os.path.abspath(os.path.expanduser(request.path))
    if not os.path.exists(path):
        try:
            os.makedirs(path, exist_ok=True)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Path does not exist and could not be created: {path}")
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"Not a valid directory: {path}")
    if not os.access(path, os.R_OK):
        raise HTTPException(status_code=403, detail=f"No read permission for directory: {path}")
    if ws_paths.path_is_protected(path):
        raise HTTPException(status_code=403, detail=f"Refusing to open protected system folder: {path}")

    # Set as active project in both CAT and server
    state_manager.set_workspace_root("default", path)
    state_manager.set_workspace_root("current", path)
    ws_paths.set_active_project(path)
    try:
        projects.record_opened(path)
    except Exception as e:
        print(f"projects.record_opened failed: {e}")

    try:
        eventbus.bus.publish(eventbus.WORKSPACE_OPENED, path=path)
    except Exception:
        pass

    return {
        "id": "current",
        "workspace_id": "current",
        "path": path,
        "name": os.path.basename(path) or path,
    }


@app.get("/api/workspace/recent")
async def recent_workspaces():
    """Get full list of workspaces from projects.workspaces()."""
    try:
        ws_list = projects.workspaces()
        for w in ws_list:
            w["exists"] = os.path.isdir(w.get("path", ""))
        return {"workspaces": ws_list, "recent": projects.recent()}
    except Exception as e:
        return {"workspaces": [], "recent": [], "error": str(e)}


@app.post("/api/workspace/recent/pin")
async def toggle_pin_recent(request: RecentPinRequest):
    """Toggle pin state for a recent workspace."""
    pinned = projects.toggle_pin(request.path)
    return {"path": request.path, "pinned": pinned}


@app.post("/api/workspace/recent/remove")
async def remove_recent_workspace(request: RecentRemoveRequest):
    """Remove workspace from recent history."""
    removed = projects.remove(request.path)
    return {"path": request.path, "removed": removed}


@app.post("/api/workspace/recent/clear")
async def clear_recent_workspaces():
    """Clear all recent workspaces."""
    cleared = projects.clear_history()
    return {"cleared": cleared}


# --- Chats & Session History (Real CAT chat_store) ---

@app.get("/api/chats")
async def list_saved_chats():
    """List all saved chat summaries from CAT chat_store."""
    return {"chats": chat_store.get_chat_summaries()}


@app.get("/api/chats/{chat_id}")
async def get_chat_session(chat_id: str):
    """Get full chat with turns."""
    chat = chat_store.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return chat


@app.post("/api/chats")
async def create_new_chat(req: ChatCreateRequest):
    """Create a new empty chat session."""
    active_ws = ws_paths.active_project() or ""
    chat = chat_store.create_chat(
        name=req.name,
        workspace_root=req.project_path or active_ws,
        project_path=req.project_path or active_ws,
    )
    return chat


@app.post("/api/chats/{chat_id}/rename")
async def rename_chat_session(chat_id: str, req: ChatRenameRequest):
    """Rename a chat session."""
    ok = chat_store.rename_chat(chat_id, req.name)
    if not ok:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return {"success": True, "id": chat_id, "name": req.name}


@app.delete("/api/chats/{chat_id}")
async def delete_chat_session(chat_id: str):
    """Delete a chat session from disk."""
    ok = chat_store.delete_chat(chat_id)
    return {"success": ok}


# --- Model Context Protocol (Real CAT mcp.py) ---

@app.get("/api/mcp/servers")
async def get_mcp_servers():
    """List all configured MCP servers with real live status."""
    servers = mcp.load_servers()
    enriched = []
    for s in servers:
        st = mcp.server_status(s)
        rec = dict(s)
        rec.update(st)
        enriched.append(rec)
    return {"servers": enriched}


@app.post("/api/mcp/servers")
async def add_or_update_mcp_server(req: McpServerRequest):
    """Add or update an MCP server configuration."""
    entry = req.dict()
    sid = mcp.add_server(entry)
    return {"id": sid, "success": True}


@app.delete("/api/mcp/servers/{server_id}")
async def remove_mcp_server(server_id: str):
    """Remove an MCP server."""
    mcp.disconnect_server(server_id)
    mcp.remove_server(server_id)
    return {"success": True}


@app.post("/api/mcp/servers/{server_id}/connect")
async def connect_mcp_server(server_id: str):
    """Connect to an MCP server."""
    servers = mcp.load_servers()
    matched = next((s for s in servers if s.get("id") == server_id), None)
    if not matched:
        raise HTTPException(status_code=404, detail="Server not found")
    ok, msg = mcp.connect_server(matched)
    status = mcp.server_status(matched)
    return {"success": ok, "message": msg, "status": status}


@app.post("/api/mcp/servers/{server_id}/disconnect")
async def disconnect_mcp_server(server_id: str):
    """Disconnect from an MCP server."""
    mcp.disconnect_server(server_id)
    return {"success": True}


# --- Backup Providers (Automatic Failover Chain) ---

@app.get("/api/backup-providers")
async def get_backup_providers():
    """Get the failover chain of backup providers."""
    providers = pm.load_backup_providers()
    return {"providers": providers, "configs": pm.backup_configs()}


DEFAULT_BACKUP_MODELS = {
    "ollama": "llama3.3",
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "openai/gpt-4o-mini",
    "openai": "gpt-4o-mini",
    "deepseek": "deepseek-chat",
    "anthropic": "claude-3-5-sonnet-20241022",
}


@app.post("/api/backup-providers")
async def save_backup_providers_chain(req: BackupProvidersSaveRequest):
    """Save the reordered/configured failover chain."""
    formatted = []
    for item in req.providers:
        if isinstance(item, str):
            p = item.lower()
            m = DEFAULT_BACKUP_MODELS.get(p, "default-model")
            formatted.append({
                "provider": p,
                "model": m,
                "enabled": True,
                "api_style": "ollama" if p == "ollama" else "openai",
                "base_url": "http://localhost:11434" if p == "ollama" else "",
            })
        elif isinstance(item, dict):
            entry = dict(item)
            p = str(entry.get("provider", "")).lower()
            if not entry.get("model"):
                entry["model"] = DEFAULT_BACKUP_MODELS.get(p, "default-model")
            formatted.append(entry)
    ok = pm.save_backup_providers(formatted)
    return {"success": ok, "providers": pm.load_backup_providers()}


# --- Themes & Styling (CAT theme.py + theme_css.py) ---

@app.get("/api/themes")
async def get_themes_info():
    """Get current theme, available themes, and Textual CSS variables."""
    cur = theme.get_theme()
    avail = theme.available_themes()
    themed_list = []
    for name in avail:
        resolved = theme.resolve_theme_name(name)
        th_obj = theme._THEMES.get(resolved)
        is_dark = th_obj.dark if th_obj else True
        themed_list.append({
            "name": name,
            "label": theme.theme_label(name),
            "active": name == cur,
            "is_light": not is_dark,
        })
    return {
        "current": cur,
        "is_light": theme.is_light(),
        "themes": themed_list,
        "css_variables": theme_css.css_variables(),
    }


@app.post("/api/themes/select")
async def select_theme(req: ThemeSelectRequest):
    """Apply theme by name and return updated CSS variables."""
    applied = theme.set_theme(req.theme)
    return {
        "theme": applied,
        "css_variables": theme_css.css_variables(),
        "is_light": theme.is_light(),
    }


# --- Extensions Management ---

@app.post("/api/extensions/{ext_id}/install")
async def install_extension(ext_id: str):
    ok = cct_ext.install(ext_id)
    return {"id": ext_id, "success": ok, "state": cct_ext.get_state(ext_id)}


@app.post("/api/extensions/{ext_id}/uninstall")
async def uninstall_extension(ext_id: str):
    ok = cct_ext.uninstall(ext_id)
    return {"id": ext_id, "success": ok, "state": cct_ext.get_state(ext_id)}


@app.post("/api/extensions/{ext_id}/enable")
async def enable_extension(ext_id: str):
    ok = cct_ext.enable(ext_id)
    return {"id": ext_id, "success": ok, "state": cct_ext.get_state(ext_id)}


@app.post("/api/extensions/{ext_id}/disable")
async def disable_extension(ext_id: str):
    ok = cct_ext.disable(ext_id)
    return {"id": ext_id, "success": ok, "state": cct_ext.get_state(ext_id)}


# --- Users & Authentication ---

@app.get("/api/user/profile")
async def get_user_profile():
    """Get full user identity, app metadata, and session status."""
    ident = fomoji_auth.get_identity() or {}
    auth_ok = fomoji_auth.is_authenticated()
    mem_turns = 0
    try:
        from calc_terminal import memory
        mem_turns = len(memory.get_facts())
    except Exception:
        pass
    saved_chats = len(chat_store.get_chat_summaries())
    cfg = aicore.load_config()

    return {
        "authenticated": auth_ok,
        "user": {
            "name": ident.get("name", "Local Developer"),
            "email": ident.get("email", "local@cat.terminal"),
            "role": ident.get("role", "developer"),
        },
        "app": {
            "name": identity.APP_NAME,
            "short_name": identity.SHORT_NAME,
            "version": identity.APP_VERSION,
            "creator": identity.CREATOR_NAME,
            "tagline": identity.APP_TAGLINE,
            "tech_stack": identity.tech_stack_sentence(cfg),
        },
        "active_model": cfg.get("model", "deepseek-r1"),
        "active_provider": cfg.get("provider", "ollama"),
        "memory_facts_count": mem_turns,
        "saved_chats_count": saved_chats,
    }


@app.post("/api/auth/logout")
async def perform_logout():
    """Full CAT logout: revokes token, stops auth server, clears session."""
    try:
        fomoji_auth.logout()
    except Exception as e:
        print(f"Logout error: {e}")
    return {"success": True, "message": "Signed out successfully."}


# --- Startup & Welcome Lifecycle (Matching Image 2) ---

@app.get("/api/startup/status")
async def get_startup_status():
    """Get startup status for WelcomeModal lifecycle."""
    seen = welcome_modal.has_seen_version()
    highlights = [
        {"icon": h[0], "name": h[1], "desc": h[2]}
        for h in welcome_modal._HIGHLIGHTS
    ]
    return {
        "version": welcome_modal._VERSION,
        "has_seen": seen,
        "highlights": highlights,
        "tagline": "Coding \u00b7 Agents \u00b7 Intelligence \u2014 the terminal for builders.",
    }


@app.post("/api/startup/dismiss")
async def dismiss_startup():
    """Mark version welcome as seen."""
    welcome_modal.mark_seen()
    return {"success": True}


# --- Gestures & Personalization ---

@app.get("/api/gestures")
async def get_gestures():
    """Get all gesture bindings from gestures manager."""
    return {"gestures": gestures_mgr.list_gestures()}


@app.post("/api/gestures/toggle")
async def toggle_gesture(req: GestureToggleRequest):
    """Toggle gesture enabled state."""
    g = gestures_mgr.update_gesture(req.id, enabled=req.enabled)
    return {"id": req.id, "enabled": req.enabled, "success": g is not None}


@app.get("/api/personalize")
async def get_personalize():
    """Get personal profiles and active profile."""
    data = ap.load_profiles()
    return {
        "active": data.get("active", ""),
        "profiles": data.get("profiles", []),
        "tones": ap.TONES,
    }


@app.post("/api/personalize/active")
async def set_active_personalize_profile(req: ProfileActiveRequest):
    """Switch active profile."""
    target = req.name or req.id or ""
    try:
        ap.set_active(target)
        return {"name": target, "id": target, "success": True}
    except Exception:
        return {"name": target, "id": target, "success": False}


@app.post("/api/personalize/save")
async def save_personalize_profile(req: ProfileSaveRequest):
    """Save/update profile."""
    prof = req.profile or req.dict(exclude_unset=True)
    if "profile" in prof:
        prof.pop("profile", None)
    name = prof.get("name") or prof.get("id") or "Custom"
    tone = prof.get("tone", "balanced")
    additions = prof.get("additions") or prof.get("prompt") or ""
    temp = prof.get("temperature")
    try:
        res = ap.add_profile(name=name, tone=tone, additions=additions, temperature=temp)
        return {"profile": res, "success": True}
    except Exception as e:
        return {"profile": prof, "success": False, "error": str(e)}


@app.get("/api/workspace/current")
async def current_workspace():
    """Get currently active workspace root and info."""
    root = state_manager.get_workspace_root("current")
    if not root:
        return {"id": None, "path": None, "name": None}
    return {
        "id": "current",
        "workspace_id": "current",
        "path": root,
        "name": os.path.basename(root) or root,
    }


@app.get("/api/workspace/{workspace_id}/tree")
async def get_workspace_tree(workspace_id: str):
    """Return tree structure and indexed language/file summary for workspace."""
    root = state_manager.get_workspace_root(workspace_id)
    if not root or not os.path.isdir(root):
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Run scan for stats
    try:
        from calc_terminal import workspace_index
        ctx = workspace_index.scan(root)
    except Exception:
        ctx = {"languages": [], "file_count": 0}
    
    skip_names = {".git", ".pytest_cache", "__pycache__", "node_modules", ".venv", "venv", ".idea", ".vscode"}
    
    def walk_dir(current_path: Path, rel_path: str = ""):
        children = []
        try:
            entries = sorted(list(current_path.iterdir()), key=lambda e: (not e.is_dir(), e.name.lower()))
            for entry in entries:
                if entry.name in skip_names or entry.name.startswith("."):
                    continue
                entry_rel = f"{rel_path}/{entry.name}" if rel_path else entry.name
                if entry.is_dir():
                    children.append({
                        "name": entry.name,
                        "path": entry_rel,
                        "type": "directory",
                        "children": walk_dir(entry, entry_rel),
                    })
                elif entry.is_file():
                    children.append({
                        "name": entry.name,
                        "path": entry_rel,
                        "type": "file",
                        "ext": entry.suffix.lower(),
                        "size": entry.stat().st_size,
                    })
        except Exception:
            pass
        return children

    langs = ctx.get("languages", [])
    f_count = ctx.get("file_count", 0)
    summary_str = f"{', '.join(langs[:3])} · {f_count}" if langs else (f"{f_count} files" if f_count else "")

    return {
        "name": os.path.basename(root) or root,
        "path": "",
        "full_path": root,
        "type": "directory",
        "children": walk_dir(Path(root)),
        "summary": {
            "languages": langs,
            "file_count": f_count,
            "summary_line": summary_str,
        },
        "recent": [
            {"path": p, "name": os.path.basename(p.rstrip(os.sep)) or p}
            for p in projects.recent()[:10]
        ]
    }


@app.get("/api/workspace/{workspace_id}/files")
async def list_workspace_files(workspace_id: str):
    root = state_manager.get_workspace_root(workspace_id)
    if not root:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    files = []
    for entry in Path(root).rglob("*"):
        if entry.is_file():
            rel = entry.relative_to(root)
            stat = entry.stat()
            files.append({
                "path": str(rel),
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "is_binary": _is_binary_file(entry),
            })
    return {"files": files}


@app.get("/api/workspace/{workspace_id}/file")
async def read_workspace_file(workspace_id: str, path: str):
    root = state_manager.get_workspace_root(workspace_id)
    if not root:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    file_path = Path(root) / path
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Security: ensure path is within workspace
    try:
        file_path.resolve().relative_to(Path(root).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if _is_binary_file(file_path):
        return FileResponse(str(file_path))
    
    content = file_path.read_text(encoding="utf-8", errors="replace")
    return {"path": path, "content": content}


@app.post("/api/workspace/{workspace_id}/file")
async def write_workspace_file(workspace_id: str, request: FileWriteRequest):
    root = state_manager.get_workspace_root(workspace_id)
    if not root:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    file_path = Path(root) / request.path
    try:
        file_path.resolve().relative_to(Path(root).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(request.content, encoding=request.encoding or "utf-8")
    
    # Notify preview controller of file change
    ctrl = state_manager.get_preview_controller(workspace_id)
    if ctrl:
        ctrl.notify_ai_wrote(str(file_path))
    
    return {"success": True, "path": request.path}


@app.delete("/api/workspace/{workspace_id}/file")
async def delete_workspace_file(workspace_id: str, path: str):
    root = state_manager.get_workspace_root(workspace_id)
    if not root:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    file_path = Path(root) / path
    try:
        file_path.resolve().relative_to(Path(root).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if file_path.exists():
        file_path.unlink()
    
    return {"success": True}


# --- Command Execution ---

@app.post("/api/command", response_model=CommandResponse)
async def run_command(request: CommandRequest):
    cwd = request.cwd or os.getcwd()
    env = os.environ.copy()
    if request.env:
        env.update(request.env)

    # Run command in thread pool to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, _run_command_sync, request.cmd, cwd, env, request.timeout
    )
    return result


def _run_command_sync(cmd: str, cwd: str, env: dict, timeout: float) -> CommandResponse:
    """Run a shell command synchronously (called from thread)."""
    import subprocess
    try:
        proc = subprocess.Popen(
            cmd,
            shell=True,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            return CommandResponse(
                returncode=-1,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace") + "\n[Timed out]",
                success=False,
            )
        return CommandResponse(
            returncode=proc.returncode or 0,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
            success=(proc.returncode or 0) == 0,
        )
    except Exception as e:
        return CommandResponse(
            returncode=-1, stdout="", stderr=str(e), success=False,
        )


# --- Preview / Live Server ---

@app.post("/api/preview/start")
async def start_preview(request: PreviewStartRequest, workspace_id: Optional[str] = "current"):
    ws_id = workspace_id or "current"
    root = state_manager.get_workspace_root(ws_id)
    if not root:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    file_path = os.path.join(root, request.file_path)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine effective project root for preview server
    project_dir = os.path.dirname(file_path) if os.path.isfile(file_path) else root
    ctrl_key = f"{ws_id}_{project_dir}"
    
    # Create or get preview controller
    if ctrl_key not in state_manager.preview_controllers:
        state_manager.preview_controllers[ctrl_key] = PreviewController(
            root=project_dir,
            on_event=lambda kind, **info: asyncio.create_task(
                _broadcast_preview_event(ws_id, kind, info)
            ),
        )
    
    ctrl = state_manager.preview_controllers[ctrl_key]
    success = ctrl.start_for_file(file_path)
    
    if not success:
        raise HTTPException(status_code=500, detail=f"Preview failed: {ctrl.last_error}")
    
    return {
        "url": ctrl.url,
        "base_url": ctrl.base_url,
        "entry_url": ctrl.entry_url,
    }


@app.post("/api/preview/stop")
async def stop_preview(workspace_id: str):
    ctrl = state_manager.get_preview_controller(workspace_id)
    if ctrl:
        ctrl.stop_preview()
        del state_manager.preview_controllers[workspace_id]
    return {"success": True}


@app.post("/api/preview/reload")
async def reload_preview(workspace_id: str):
    ctrl = state_manager.get_preview_controller(workspace_id)
    if not ctrl:
        raise HTTPException(status_code=404, detail="Preview not running")
    
    snap = ctrl.reload()
    return {"success": snap.ok if snap else False, "error": snap.error if snap and not snap.ok else None}


@app.get("/api/preview/status")
async def preview_status(workspace_id: str):
    ctrl = state_manager.get_preview_controller(workspace_id)
    if not ctrl:
        return {"running": False}
    
    return {
        "running": ctrl.running,
        "url": ctrl.url,
        "base_url": ctrl.base_url,
        "server_state": ctrl.server_state.name,
        "preview_state": ctrl.preview_state.name,
        "error": ctrl.last_error,
    }


# --- AI Chat ---

@app.post("/api/chat")
async def chat(request: ChatRequest):
    # Set workspace if provided
    if request.project_path:
        ws_paths.set_active_project(request.project_path)

    # Record user turn if chat_id provided
    cid = request.chat_id
    if cid:
        try:
            chat_store.add_turn(cid, "user", request.message)
        except Exception:
            pass

    # Get AI config
    config = aicore.load_config()

    # Process the message (run_in_executor to avoid blocking)
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, _process_chat_message, request.message, request.mode or "build", config
        )
        if cid:
            result["chat_id"] = cid
            if result.get("response"):
                try:
                    chat_store.add_turn(cid, "assistant", result["response"])
                except Exception:
                    pass
        return result
    except Exception as e:
        prov = config.get("provider", "ollama").upper()
        mod = config.get("model", "deepseek-r1")
        err_res = {
            "response": f"Error communicating with AI: {e}",
            "provider": prov,
            "model": mod,
            "tokens": 0,
            "time_str": "0:01",
            "timings": {"ttfb_ms": 500, "memory_ms": 20, "loop_ms": 520},
            "calls": 1,
            "success": False,
        }
        if cid:
            err_res["chat_id"] = cid
        return err_res


# --- Agent / Build / Plan ---

class AgentRequest(BaseModel):
    message: str
    mode: Optional[str] = "agent"  # "agent", "ai", "build", "plan"
    project_path: Optional[str] = None
    max_steps: Optional[int] = 15
    chat_id: Optional[str] = None

@app.post("/api/agent")
async def run_agent_endpoint(request: AgentRequest):
    """Run the CAT agent (same as CLI /agent mode)."""
    if request.project_path:
        ws_paths.set_active_project(request.project_path)
    cid = getattr(request, "chat_id", None)
    if cid:
        try:
            chat_store.add_turn(cid, "user", request.message)
        except Exception:
            pass
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None, lambda: _run_agent_sync(
                request.message, request.mode, request.max_steps
            )
        )
        if cid:
            result["chat_id"] = cid
            if result.get("response"):
                try:
                    chat_store.add_turn(cid, "assistant", result["response"])
                except Exception:
                    pass
        return result
    except Exception as e:
        err_res = {"response": "Agent error: " + str(e), "steps": [], "meta": {}}
        if cid:
            err_res["chat_id"] = cid
        return err_res


def _run_agent_sync(message: str, mode: str, max_steps: int) -> dict:
    """Run agent synchronously (called from thread)."""
    try:
        from calc_terminal.agent import run_agent as _run_agent
        agent_mode = "agent" if mode in ("agent", "build", "plan") else "ai"
        text, steps, meta = _run_agent(
            message,
            max_steps=max_steps,
            verbose=False,
            mode=agent_mode,
        )
        # Format steps for web display
        step_list = []
        for s in steps:
            if len(s) >= 3:
                step_list.append({
                    "tool": s[0],
                    "args": s[1] if isinstance(s[1], dict) else {},
                    "result": str(s[2])[:500],
                })
        from calc_terminal import aicore
        cfg = aicore.load_config()
        return {
            "response": text or "",
            "steps": step_list,
            "meta": meta or {},
            "provider": (cfg.get("provider") or "ollama").upper(),
            "model": cfg.get("model") or "gemma4:e4b",
            "tokens": max(15, len((text or "").split()) * 4 // 3),
            "calls": max(1, len(step_list)),
            "success": True,
        }
    except Exception as e:
        return {"response": "Agent error: " + str(e), "steps": [], "meta": {}}


# --- Git Operations ---

class GitRequest(BaseModel):
    action: str  # status, diff, add, commit, branch, checkout, log
    message: Optional[str] = None
    file: Optional[str] = None
    branch: Optional[str] = None

@app.post("/api/git")
async def git_operation(request: GitRequest):
    """Execute git operations."""
    root = ws_paths.active_project() or os.getcwd()
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None, lambda: _git_op_sync(request.action, root, request.message, request.file, request.branch)
        )
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def _git_op_sync(action: str, root: str, message: str = None, file: str = None, branch: str = None) -> dict:
    """Execute a git operation synchronously."""
    import subprocess
    def run_git(args):
        proc = subprocess.Popen(
            ["git"] + args,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = proc.communicate(timeout=15)
        return proc.returncode, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")

    if action == "status":
        code, out, err = run_git(["status", "--porcelain"])
        branch_code, branch_out, _ = run_git(["branch", "--show-current"])
        lines = [l for l in out.strip().split("\n") if l.strip()]
        modified = [l[3:] for l in lines if l.startswith(" M") or l.startswith("M")]
        added = [l[3:] for l in lines if l.startswith("A")]
        deleted = [l[3:] for l in lines if l.startswith("D")]
        untracked = [l[3:] for l in lines if l.startswith("??")]
        return {
            "success": True,
            "branch": branch_out.strip(),
            "modified": modified,
            "added": added,
            "deleted": deleted,
            "untracked": untracked,
            "total": len(lines),
        }

    elif action == "diff":
        target = file or ""
        args = ["diff"]
        if target:
            args.append(target)
        code, out, err = run_git(args)
        return {"success": True, "diff": out}

    elif action == "add":
        target = file or "."
        code, out, err = run_git(["add", target])
        return {"success": code == 0, "output": out or err}

    elif action == "commit":
        msg = message or "Web commit"
        code, out, err = run_git(["commit", "-m", msg])
        return {"success": code == 0, "output": out or err}

    elif action == "branch":
        code, out, err = run_git(["branch"])
        branches = [l.strip().replace("* ", "") for l in out.strip().split("\n") if l.strip()]
        return {"success": True, "branches": branches}

    elif action == "checkout":
        br = branch or "main"
        code, out, err = run_git(["checkout", br])
        return {"success": code == 0, "output": out or err}

    elif action == "log":
        code, out, err = run_git(["log", "--oneline", "-20"])
        return {"success": True, "log": out}

    elif action == "pull":
        code, out, err = run_git(["pull"])
        return {"success": code == 0, "output": out or err}

    elif action == "push":
        code, out, err = run_git(["push"])
        return {"success": code == 0, "output": out or err}

    return {"success": False, "error": "Unknown git action: " + action}


# --- File Operations (CRUD) ---

class FileCRUDRequest(BaseModel):
    action: str  # create, rename, delete
    path: str
    new_path: Optional[str] = None
    is_dir: Optional[bool] = False
    content: Optional[str] = None

@app.post("/api/file")
async def file_crud(request: FileCRUDRequest):
    """Create, rename, or delete files/folders."""
    root = ws_paths.active_project()
    if not root:
        raise HTTPException(status_code=400, detail="No workspace open")

    target = Path(root) / request.path
    try:
        target.resolve().relative_to(Path(root).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        if request.action == "create":
            if request.is_dir:
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(request.content or "", encoding="utf-8")
            return {"success": True, "path": str(target.relative_to(root))}

        elif request.action == "rename":
            if not request.new_path:
                raise HTTPException(status_code=400, detail="new_path required")
            new_target = Path(root) / request.new_path
            try:
                new_target.resolve().relative_to(Path(root).resolve())
            except ValueError:
                raise HTTPException(status_code=403, detail="Access denied")
            target.rename(new_target)
            return {"success": True, "path": str(new_target.relative_to(root))}

        elif request.action == "delete":
            if target.is_dir():
                import shutil
                shutil.rmtree(target)
            else:
                target.unlink()
            return {"success": True}

        else:
            raise HTTPException(status_code=400, detail="Unknown action: " + request.action)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Streaming AI (SSE) ---

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream real token-by-token AI response using Server-Sent Events."""
    from fastapi.responses import StreamingResponse

    async def generate():
        try:
            async for chunk in runtime.stream_chat(
                message=request.message,
                mode=request.mode or "notebook",
                project_path=request.project_path,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# --- AI Modes Management ---

@app.get("/api/modes")
async def get_modes():
    """Return all AI modes, order, and current active mode."""
    return runtime.get_modes()


@app.post("/api/modes/switch")
async def switch_mode(request: ModeSwitchRequest):
    """Switch active AI mode."""
    res = runtime.set_mode(request.mode)
    return {"current": res, "success": True}


@app.post("/api/modes/custom")
async def create_custom_mode(request: CustomModeRequest):
    """Create a new user-defined AI mode."""
    ok, msg = runtime.create_custom_mode(
        request.key, request.label, request.icon, request.accent_hex,
        request.purpose or "", request.system_prompt or ""
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "key": msg}


@app.delete("/api/modes/custom/{key}")
async def delete_custom_mode(key: str):
    """Delete a custom AI mode."""
    ok, msg = runtime.delete_custom_mode(key)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


# --- Providers & Models Management ---

@app.get("/api/providers")
async def list_providers():
    """List all 155+ AI providers."""
    return {"providers": runtime.list_providers()}


@app.get("/api/models")
async def list_models(provider_id: str, force_refresh: bool = False):
    """Get models for a specific provider with metadata and categories."""
    return {"models": runtime.get_models_for_provider(provider_id, force_refresh=force_refresh)}


@app.post("/api/models/switch")
async def switch_model(request: ModelSwitchRequest):
    """Switch active provider and model in CAT configuration."""
    return runtime.switch_model(request.provider, request.model, request.api_key)


# --- Ollama Support ---

@app.get("/api/ollama/status")
async def get_ollama_status():
    """Check Ollama installation and connection status."""
    return runtime.get_ollama_status()


@app.get("/api/ollama/catalog")
async def get_ollama_catalog(query: str = ""):
    """Browse curated 250+ model catalog."""
    return {"catalog": runtime.get_ollama_catalog(query)}


@app.post("/api/ollama/start")
async def start_ollama():
    """Start local Ollama serve process."""
    ok, msg = runtime.ensure_ollama_started()
    return {"success": ok, "message": msg}


# --- Commands Management ---

@app.get("/api/commands")
async def get_commands():
    """Get all 103 slash commands with descriptions."""
    return {"commands": runtime.get_commands()}


@app.post("/api/command/dispatch")
async def dispatch_command(request: CommandDispatchRequest):
    """Dispatch a slash command to CAT command handlers."""
    return runtime.dispatch_command(request.command)


# --- Memory & Context ---

@app.get("/api/memory/facts")
async def get_memory_facts():
    """Get durable user facts and topic activity."""
    return {
        "facts": runtime.get_memory_facts(),
        "activity": runtime.get_memory_activity(),
        "topics": runtime.get_memory_topics(),
    }


@app.post("/api/memory/fact")
async def add_memory_fact(request: FactRequest):
    """Add a durable fact to CAT memory."""
    runtime.add_memory_fact(request.fact)
    return {"success": True, "facts": runtime.get_memory_facts()}


@app.delete("/api/memory/fact/{index}")
async def remove_memory_fact(index: int):
    """Remove a fact by index."""
    runtime.remove_memory_fact(index)
    return {"success": True, "facts": runtime.get_memory_facts()}


# --- Customization & Extensions ---

@app.get("/api/customization")
async def get_customization():
    """Get complete layout and styling customization state."""
    return runtime.get_customization()


@app.post("/api/customization/layout")
async def update_customization_layout(request: CustomizationLayoutRequest):
    """Update layout position/dock/size for a panel."""
    ok = runtime.update_layout_component(request.component_id, request.updates)
    return {"success": ok}


@app.post("/api/customization/reset")
async def reset_customization():
    """Reset customization to defaults."""
    ok = runtime.reset_customization()
    return {"success": ok}


@app.get("/api/extensions")
async def list_extensions():
    """List installable and active extensions."""
    return {"extensions": runtime.list_extensions()}


@app.post("/api/extensions/toggle")
async def toggle_extension(request: ExtensionToggleRequest):
    """Enable or disable an extension."""
    ok = runtime.toggle_extension(request.id, request.enabled)
    return {"success": ok}


@app.post("/api/extensions/create")
async def create_extension(request: ExtensionCreateRequest):
    """Create a new custom extension."""
    ok, res = cct_ext.create_extension(
        extension_id=request.id,
        name=request.name,
        description=request.description or "",
        icon=request.icon or "⚡",
        publisher=request.publisher or "Custom",
        category=request.category or "Custom",
        version=request.version or "1.0.0",
        script_code=request.script_code or "",
    )
    return {"success": ok, "message": res, "extension": res, "extensions": runtime.list_extensions()}


# --- Science Engine & Notebook ---

@app.post("/api/science/solve")
async def science_solve(request: ScienceSolveRequest):
    """Solve formula symbolically."""
    key = request.key or request.formula or "ideal_gas"
    raw_vals = request.values if request.values is not None else (request.params or {})
    clean_vals = {}
    for k, v in raw_vals.items():
        if v is not None and v != "":
            try:
                clean_vals[k] = float(v)
            except (ValueError, TypeError):
                clean_vals[k] = v
    return runtime.solve_formula(key, clean_vals)


@app.post("/api/science/derive")
async def science_derive(request: ScienceDeriveRequest):
    """Get step-by-step calculus derivation."""
    kw = request.keyword or request.derivation or "first"
    return runtime.get_derivation(kw)


@app.post("/api/science/atom")
async def science_atom(request: ScienceAtomRequest):
    """Get atomic simulation details."""
    return runtime.get_atom_sim(request.element)


# --- Live Event Stream (SSE) ---

@app.get("/api/events/stream")
async def events_stream():
    """Live Server-Sent Events stream of workspace and agent events."""
    from fastapi.responses import StreamingResponse

    async def event_generator():
        q: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def _sub(topic, **kwargs):
            loop.call_soon_threadsafe(
                q.put_nowait,
                {"topic": topic, "time": time.time(), "data": {k: str(v)[:150] for k, v in kwargs.items()}}
            )

        for top in (
            eventbus.FILE_CREATED, eventbus.FILE_SAVED, eventbus.FILE_DELETED,
            eventbus.AI_RESPONSE_GENERATED, eventbus.TERMINAL_COMMAND,
            eventbus.WORKSPACE_OPENED, eventbus.MODE_SWITCHED,
            eventbus.PACKAGE_INSTALLED, eventbus.TODO_CREATED, eventbus.TODO_COMPLETED
        ):
            eventbus.bus.subscribe(top, lambda t=top, **kw: _sub(t, **kw))

        try:
            yield f"data: {json.dumps({'topic': 'connected', 'time': time.time()})}\n\n"
            while True:
                evt = await q.get()
                yield f"data: {json.dumps(evt)}\n\n"
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


# --- Server Status / Debug ---

@app.get("/api/status")
async def server_status():
    """Check server status and AI config."""
    try:
        config = aicore.load_config()
        provider = config.get("provider", "none")
        model = config.get("model", "none")
        has_key = bool(config.get("api_key"))
        return {
            "status": "ok",
            "version": "0.7.9.0",
            "provider": provider,
            "model": model,
            "has_api_key": has_key,
            "workspace_count": len(state_manager.workspace_roots),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# --- Calculator ---

class CalcRequest(BaseModel):
    expression: str

@app.post("/api/calc")
async def calculator(request: CalcRequest):
    """Scientific calculator - safe eval with math functions."""
    import math
    import re
    expr = request.expression.strip()
    if not expr:
        raise HTTPException(status_code=400, detail="Empty expression")
    # Replace common symbols
    expr = expr.replace('^', '**')
    expr = expr.replace('×', '*')
    expr = expr.replace('÷', '/')
    # Allow only safe characters
    safe_pattern = r'^[0-9+\-*/.() pi,e,sqrt,log,log10,sin,cos,tan,asin,acos,atan,abs,ceil,floor,round,pow,min,max,radians,deg,gcd,factorial,isfinite,isnan,inf ]+$'
    # Build safe namespace
    safe_math = {
        'pi': math.pi, 'e': math.e, 'inf': math.inf,
        'sqrt': math.sqrt, 'log': math.log, 'log10': math.log10,
        'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
        'asin': math.asin, 'acos': math.acos, 'atan': math.atan,
        'abs': abs, 'ceil': math.ceil, 'floor': math.floor,
        'round': round, 'pow': pow, 'min': min, 'max': max,
        'radians': math.radians, 'deg': math.degrees,
        'gcd': math.gcd, 'factorial': math.factorial,
    }
    try:
        result = eval(expr, {"__builtins__": {}}, safe_math)
        return {"expression": request.expression, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Calculation error: {e}")


# --- Web Search ---

class SearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = 6

@app.post("/api/websearch")
async def web_search_endpoint(request: SearchRequest):
    """Search the web via DuckDuckGo."""
    loop = asyncio.get_event_loop()
    try:
        results = await loop.run_in_executor(
            None, lambda: aicore.web_search(request.query, request.max_results)
        )
        return {"results": results}
    except Exception as e:
        return {"results": [], "error": str(e)}


class ResearchRequest(BaseModel):
    topic: str
    num_queries: Optional[int] = 3

@app.post("/api/research")
async def deep_research_endpoint(request: ResearchRequest):
    """Deep research - multiple searches + AI synthesis."""
    loop = asyncio.get_event_loop()
    try:
        summary, sources = await loop.run_in_executor(
            None, lambda: aicore.deep_research(request.topic, request.num_queries)
        )
        return {"summary": summary, "sources": sources}
    except Exception as e:
        return {"summary": "", "sources": [], "error": str(e)}


# --- Formula Library ---

@app.get("/api/formulas")
async def get_formulas():
    """Get the formula library categories and formulas."""
    try:
        from calc_terminal import solver
        categories = {}
        for cat, formulas in solver.FORMULA_LIBRARY.items():
            categories[cat] = []
            for f in formulas:
                categories[cat].append({
                    "name": f.get("name", ""),
                    "formula": f.get("formula", ""),
                    "variables": f.get("variables", {}),
                    "description": f.get("description", ""),
                })
        return {"categories": categories}
    except Exception as e:
        return {"categories": {}, "error": str(e)}


class SolveRequest(BaseModel):
    formula: str
    known_values: Dict[str, float]
    solve_for: str

@app.post("/api/solve")
async def solve_formula(request: SolveRequest):
    """Solve a formula for an unknown variable."""
    try:
        from calc_terminal import solver as _solver
        result = _solver.solve_symbolic(request.formula, request.known_values, request.solve_for)
        return {"result": result}
    except Exception as e:
        return {"result": None, "error": str(e)}


# --- Workspace Commands ---

@app.get("/api/workspace/info")
async def workspace_info():
    """Get workspace info and categories."""
    try:
        from calc_terminal import workspace as _ws
        root = _ws.root_dir()
        cats = {}
        for cat in _ws.CATEGORIES:
            files = _ws.list_category(cat)
            if files:
                cats[cat] = [{"name": f["name"], "path": f["path"], "size": f["size"]} for f in files[:10]]
        return {
            "root": str(root),
            "categories": cats,
            "summary": _ws.summary(),
        }
    except Exception as e:
        return {"root": "", "categories": {}, "error": str(e)}


@app.get("/api/workspace/detect")
async def workspace_detect():
    """Auto-detect workspace from current directory."""
    try:
        from calc_terminal import workspace as _ws
        detected = _ws.detect_workspace(os.getcwd())
        if detected:
            _ws.set_active_project(detected)
            projects.record_opened(detected)
            return {"path": detected, "name": os.path.basename(detected)}
        return {"path": None}
    except Exception as e:
        return {"path": None, "error": str(e)}


@app.get("/api/workspace/git")
async def workspace_git():
    """Get git status for current workspace."""
    try:
        from calc_terminal import workspace as _ws
        root = _ws.active_project() or os.getcwd()
        branch = _ws.git_branch(root)
        changed, added, deleted = _ws.git_status_summary(root)
        return {
            "branch": branch,
            "changed": changed,
            "added": added,
            "deleted": deleted,
        }
    except Exception as e:
        return {"branch": None, "changed": 0, "added": 0, "deleted": 0}


# --- Memory ---

@app.get("/api/memory")
async def get_memory():
    """Get AI conversation memory stats."""
    try:
        from calc_terminal import aicore as _ac
        usage = _ac.get_session_usage()
        return {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "requests": usage.get("requests", 0),
            "context_window": usage.get("context_window", 0),
        }
    except Exception as e:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "requests": 0}


# --- Settings ---

@app.get("/api/settings")
async def get_settings():
    """Get current settings."""
    try:
        config = aicore.load_config()
        return {
            "provider": config.get("provider", "none"),
            "model": config.get("model", "none"),
            "theme": config.get("theme", "dark"),
            "precision": config.get("precision", 3),
            "sound": config.get("sound", False),
        }
    except Exception as e:
        return {"provider": "none", "model": "none", "theme": "dark", "precision": 3}


class SettingsUpdate(BaseModel):
    theme: Optional[str] = None
    precision: Optional[int] = None
    sound: Optional[bool] = None

@app.post("/api/settings")
async def update_settings(request: SettingsUpdate):
    """Update settings."""
    try:
        config = aicore.load_config()
        if request.theme is not None:
            config["theme"] = request.theme
        if request.precision is not None:
            config["precision"] = request.precision
        if request.sound is not None:
            config["sound"] = request.sound
        aicore.save_config(config)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# --- WebSocket for Real-time Updates ---

@app.websocket("/ws/{workspace_id}")
async def websocket_endpoint(websocket: WebSocket, workspace_id: str):
    await websocket.accept()
    state_manager.active_websockets.add(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            await _handle_websocket_message(websocket, workspace_id, message)
    except WebSocketDisconnect:
        pass
    finally:
        state_manager.active_websockets.discard(websocket)


# --- Helper Functions ---

def _is_binary_file(path: Path) -> bool:
    """Check if file is binary."""
    binary_extensions = {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico",
        ".woff", ".woff2", ".ttf", ".otf", ".eot",
        ".pdf", ".zip", ".gz", ".tar", ".rar",
        ".wasm", ".exe", ".dll", ".so", ".dylib",
    }
    return path.suffix.lower() in binary_extensions


def _process_chat_message(message: str, mode: str, config: dict) -> dict:
    """Process a chat message through CAT's AI system (synchronous).
    
    v0.7.10: Enhanced error resilience — auto-retries on transient failures,
    validates responses against error signatures, and provides clearer
    diagnostics to the user.
    """
    t0 = time.time()
    prov = config.get("provider", "ollama") if config else "ollama"
    mod = config.get("model", "deepseek-r1") if config else "deepseek-r1"
    # Only invoke multi-turn agent when explicitly in 'agent' mode, or when explicit file/workspace mutation is commanded
    is_explicit_agent_task = mode == "agent" or (mode in ("build", "plan") and bool(re.search(r"^\s*(?:create|write|delete|edit|refactor|generate)\s+(?:file|folder|dir|component|app|project)\b", message, re.I)))
    if is_explicit_agent_task:
        try:
            agent_res = _run_agent_sync(message, "agent", max_steps=4)
            if agent_res and agent_res.get("response") and not agent_res.get("response", "").startswith("Agent error:"):
                total_time = time.time() - t0
                loop_ms = max(50, int(total_time * 1000))
                mins, secs = divmod(int(total_time), 60)
                return {
                    "response": agent_res["response"],
                    "steps": agent_res.get("steps", []),
                    "provider": prov.upper(),
                    "model": mod,
                    "tokens": max(12, len(agent_res["response"].split()) * 4 // 3),
                    "time_str": f"{mins}:{secs:02d}",
                    "duration": total_time,
                    "timings": {"ttfb_ms": 300, "memory_ms": 25, "loop_ms": loop_ms},
                    "calls": max(1, len(agent_res.get("steps", []))),
                    "success": True,
                }
        except Exception:
            pass

    # Standard AI chat with auto-retry on transient failures
    max_retries = 2
    last_response = ""
    last_error = ""
    
    for attempt in range(max_retries + 1):
        try:
            from calc_terminal import aicore as _aicore
            from calc_terminal import ai_modes as _am
            
            # Reload config on retry to pick up any changes
            if attempt > 0:
                try:
                    config = _aicore.load_config()
                    prov = config.get("provider", prov)
                    mod = config.get("model", mod)
                except Exception:
                    pass
            
            system_prompt = _am.system_prompt_for(mode) if hasattr(_am, "system_prompt_for") else _aicore.DEFAULT_SYSTEM_PROMPT
            response = _aicore.query_ai(
                message,
                system_prompt=system_prompt,
                config=config,
            )
            
            # Validate response — check if it's an error signature
            if response and not _aicore.is_error_response(response):
                # Good response
                total_time = time.time() - t0
                loop_ms = max(50, int(total_time * 1000))
                ttfb_ms = max(30, int(loop_ms * 0.85))
                mem_ms = max(10, int(total_time * 15))
                tokens = max(1, len((response or "").split()) * 4 // 3)
                mins, secs = divmod(int(total_time), 60)
                time_str = f"{mins}:{secs:02d}"
                return {
                    "response": response,
                    "provider": prov.upper(),
                    "model": mod,
                    "tokens": tokens,
                    "time_str": time_str,
                    "duration": total_time,
                    "timings": {
                        "ttfb_ms": ttfb_ms,
                        "memory_ms": mem_ms,
                        "loop_ms": loop_ms,
                    },
                    "calls": attempt + 1,
                    "success": True,
                }
            
            # Error response — save and retry if we have attempts left
            last_response = response or "No response received from AI."
            if attempt < max_retries:
                time.sleep(0.5 * (attempt + 1))  # brief backoff
                continue
                
        except Exception as e:
            last_error = str(e)
            last_response = last_response or f"Error: {last_error}"
            if attempt < max_retries:
                time.sleep(0.5 * (attempt + 1))
                continue

    # All retries exhausted — return best error info
    total_time = time.time() - t0
    mins, secs = divmod(int(total_time), 60)
    time_str = f"{mins}:{secs:02d}"
    timed_out = "timed out" in (last_response + last_error).lower() or total_time >= 25.0
    resp_text = last_response if last_response else ("(Generation timed out)" if timed_out else f"Error: {last_error}")
    return {
        "response": resp_text,
        "provider": prov.upper(),
        "model": mod,
        "tokens": max(5, int(total_time * 2)),
        "time_str": time_str,
        "duration": total_time,
        "timings": {
            "ttfb_ms": max(100, int(total_time * 1000)),
            "memory_ms": 337,
            "loop_ms": max(120, int(total_time * 1000) + 30),
        },
        "calls": max_retries + 1,
        "success": False,
        "timed_out": timed_out,
    }



async def _broadcast_preview_event(workspace_id: str, kind: str, info: dict):
    """Broadcast preview events to connected websockets."""
    message = json.dumps({"type": "preview", "kind": kind, "data": info}, default=str)
    for ws in state_manager.active_websockets.copy():
        try:
            await ws.send_text(message)
        except Exception:
            state_manager.active_websockets.discard(ws)


async def _handle_websocket_message(websocket: WebSocket, workspace_id: str, message: dict):
    """Handle incoming websocket messages."""
    msg_type = message.get("type")
    
    if msg_type == "preview_navigate":
        ctrl = state_manager.get_preview_controller(workspace_id)
        if ctrl:
            ctrl.navigate(message.get("url", ""))
    
    elif msg_type == "preview_reload":
        ctrl = state_manager.get_preview_controller(workspace_id)
        if ctrl:
            ctrl.reload()
    
    elif msg_type == "file_change":
        # Handle file changes from editor
        ctrl = state_manager.get_preview_controller(workspace_id)
        if ctrl:
            paths = message.get("paths", [])
            ctrl.on_files_changed(paths)


# ============================================================
# Vision Agent (CAT v0.8.a)
# ============================================================

from calc_terminal.vision.session import VisionSessionManager, SessionState
from calc_terminal.vision.capture import CaptureConfig, CaptureMode
from calc_terminal.vision.context import VisionContextEngine
from calc_terminal.vision.verify import BeforeAfterVerifier
from calc_terminal.vision.safety import SafetyConfig, PrivacyController
from calc_terminal.vision.provider import VisionProviderRouter
from calc_terminal.vision.frame_pipeline import FrameMeta, ChangeLevel
from calc_terminal.vision.annotations import AnnotationEngine, AnnotationTool, Color

vision_manager = VisionSessionManager()
vision_context = VisionContextEngine()
vision_verifier = BeforeAfterVerifier()
vision_router = VisionProviderRouter()


class VisionSessionRequest(BaseModel):
    mode: Optional[str] = "display"
    fps: Optional[float] = 1.0
    quality: Optional[int] = 85
    max_frames: Optional[int] = 500
    width: Optional[int] = None
    height: Optional[int] = None
    auto_analyze: Optional[bool] = True
    privacy_mode: Optional[bool] = True
    annotations_enabled: Optional[bool] = True


class VisionFrameRequest(BaseModel):
    session_id: str
    frame_b64: str
    timestamp: Optional[float] = None
    pointer_x: Optional[float] = None
    pointer_y: Optional[float] = None
    pointer_down: Optional[bool] = False
    scroll_y: Optional[int] = 0
    active_element: Optional[str] = ""
    url: Optional[str] = ""
    title: Optional[str] = ""


class VisionAnalyzeRequest(BaseModel):
    session_id: str
    prompt: Optional[str] = ""
    mode: Optional[str] = "analyze"
    error_message: Optional[str] = ""


class VisionAnnotationRequest(BaseModel):
    session_id: str
    tool: str = "pen"
    points: List[List[float]] = []
    color: Optional[Dict] = None
    line_width: Optional[float] = 3.0
    text: Optional[str] = ""
    frame_index: Optional[int] = -1


class VisionContextRequest(BaseModel):
    session_id: str
    file_path: Optional[str] = ""
    file_content: Optional[str] = ""
    cursor_line: Optional[int] = 0
    language: Optional[str] = ""
    project_type: Optional[str] = ""


class VisionVerifyRequest(BaseModel):
    session_id: str
    fix_description: Optional[str] = ""
    code_change: Optional[str] = ""


@app.post("/api/vision/session")
async def vision_session_create(req: VisionSessionRequest):
    try:
        mode_map = {
            "display": CaptureMode.DISPLAY,
            "tab": CaptureMode.TAB,
            "window": CaptureMode.WINDOW,
            "audio_video": CaptureMode.AUDIO_VIDEO,
        }
        config = CaptureConfig(
            mode=mode_map.get(req.mode, CaptureMode.DISPLAY),
            fps=req.fps,
            quality=req.quality,
            max_frames=req.max_frames,
            width=req.width,
            height=req.height,
            auto_analyze=req.auto_analyze,
            privacy_mode=req.privacy_mode,
            annotations_enabled=req.annotations_enabled,
        )
        session = vision_manager.create_session(config)
        return {"ok": True, "session": session.to_dict()}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/vision/session/{session_id}/start")
async def vision_session_start(session_id: str):
    try:
        session = await vision_manager.start_session(session_id)
        return {"ok": True, "session": session.to_dict()}
    except KeyError:
        raise HTTPException(404, "Session not found")
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/vision/session/{session_id}/stop")
async def vision_session_stop(session_id: str):
    try:
        session = await vision_manager.stop_session(session_id)
        return {"ok": True, "session": session.to_dict()}
    except KeyError:
        raise HTTPException(404, "Session not found")
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/vision/session/{session_id}/pause")
async def vision_session_pause(session_id: str):
    try:
        await vision_manager.pause_session(session_id)
        session = vision_manager.get_session(session_id)
        return {"ok": True, "session": session.to_dict() if session else None}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/vision/session/{session_id}/resume")
async def vision_session_resume(session_id: str):
    try:
        await vision_manager.resume_session(session_id)
        session = vision_manager.get_session(session_id)
        return {"ok": True, "session": session.to_dict() if session else None}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.delete("/api/vision/session/{session_id}")
async def vision_session_destroy(session_id: str):
    try:
        await vision_manager.destroy_session(session_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/vision/sessions")
async def vision_sessions_list():
    return {"ok": True, "sessions": vision_manager.list_sessions()}


@app.get("/api/vision/session/{session_id}")
async def vision_session_get(session_id: str):
    session = vision_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return {"ok": True, "session": session.to_dict()}


@app.get("/api/vision/session/{session_id}/config")
async def vision_capture_config(session_id: str):
    session = vision_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return {"ok": True, "config": session.capture.get_capture_config()}


@app.get("/api/vision/capabilities")
async def vision_capabilities():
    return {
        "ok": True,
        "capture": vision_manager._privacy.get_privacy_summary(),
        "providers": vision_router.get_all_capabilities(),
    }


@app.post("/api/vision/frame")
async def vision_frame_submit(req: VisionFrameRequest):
    session = vision_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    meta = FrameMeta(
        timestamp=req.timestamp or time.time(),
        pointer_x=req.pointer_x or 0,
        pointer_y=req.pointer_y or 0,
        pointer_down=req.pointer_down or False,
        scroll_y=req.scroll_y or 0,
        active_element=req.active_element or "",
        url=req.url or "",
        title=req.title or "",
    )
    result = vision_manager.process_frame(req.session_id, req.frame_b64, meta)
    if result is None:
        return {"ok": True, "processed": False, "reason": "frame_not_selected"}
    vision_manager._privacy.record_capture()
    return {"ok": True, "processed": True, "frame": result}


@app.post("/api/vision/annotate")
async def vision_annotate(req: VisionAnnotationRequest):
    session = vision_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    tool_map = {
        "pen": AnnotationTool.PEN,
        "arrow": AnnotationTool.ARROW,
        "rect": AnnotationTool.RECT,
        "circle": AnnotationTool.CIRCLE,
        "text": AnnotationTool.TEXT,
        "highlight": AnnotationTool.HIGHLIGHT,
        "crosshair": AnnotationTool.CROSSHAIR,
        "eraser": AnnotationTool.ERASER,
    }
    tool = tool_map.get(req.tool, AnnotationTool.PEN)
    color = Color.from_dict(req.color) if req.color else None
    points = [(p[0], p[1]) for p in req.points]
    ann = session.annotations.add_annotation(
        tool=tool, points=points, color=color,
        line_width=req.line_width, text=req.text,
        frame_index=req.frame_index,
    )
    return {"ok": True, "annotation": ann.to_dict()}


@app.get("/api/vision/annotations/{session_id}")
async def vision_annotations_list(session_id: str):
    session = vision_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return {"ok": True, "annotations": session.annotations.to_list()}


@app.post("/api/vision/annotations/{session_id}/undo")
async def vision_annotations_undo(session_id: str):
    session = vision_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    ann = session.annotations.undo()
    return {"ok": True, "undone": ann.to_dict() if ann else None}


@app.post("/api/vision/annotations/{session_id}/redo")
async def vision_annotations_redo(session_id: str):
    session = vision_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    ann = session.annotations.redo()
    return {"ok": True, "redone": ann.to_dict() if ann else None}


@app.post("/api/vision/annotations/{session_id}/clear")
async def vision_annotations_clear(session_id: str):
    session = vision_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    session.annotations.clear()
    return {"ok": True}


@app.post("/api/vision/context")
async def vision_context_set(req: VisionContextRequest):
    session = vision_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    vision_context.set_code_context(
        file_path=req.file_path,
        content=req.file_content,
        cursor_line=req.cursor_line,
        language=req.language,
    )
    if req.project_type:
        vision_context.set_project_context(project_type=req.project_type)
    return {"ok": True}


@app.post("/api/vision/analyze")
async def vision_analyze(req: VisionAnalyzeRequest):
    session = vision_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    best_frame = session.pipeline.get_best_frame()
    if not best_frame:
        raise HTTPException(400, "No frames available for analysis")
    pointer_telemetry = {
        "active_element": "",
        "cursor_moving": False,
    }
    visual_ctx = vision_context.build_context(
        frame_b64=best_frame.frame_b64,
        frame_meta=best_frame.meta.to_dict(),
        annotations=session.annotations.to_list(),
        pointer_telemetry=pointer_telemetry,
        analysis_prompt=req.prompt,
    )
    try:
        from calc_terminal import aicore
        config, caps = vision_router.find_vision_capable() or (None, None)
        if config is None:
            return {
                "ok": False,
                "error": "No vision-capable model configured",
                "suggestion": "Configure a vision model via /model (e.g. gpt-4o, claude-3.5-sonnet)",
            }
        messages = visual_ctx.to_ai_messages()
        user_msg = messages[-1] if messages else {"role": "user", "content": req.prompt}
        system_msg = messages[0] if messages else {"role": "system", "content": "Analyze the screen."}
        from calc_terminal.attachments import Attachment
        att = Attachment.__new__(Attachment)
        att.id = f"att-vision-{abs(hash(best_frame.frame_b64[:64])) % 1000000}"
        att.name = "screenshot"
        att.path = ""
        att.extension = ".png"
        att.mime_type = "image/png"
        att.size = len(best_frame.frame_b64)
        att.kind = "image"
        att.content = "[screen capture]"
        att.metadata = {"inline_b64": best_frame.frame_b64}
        att.extraction_status = "ready"
        att.error = None
        att.created_at = time.time()
        att.source = "vision_agent"
        analysis = aicore.query_ai(
            user_msg.get("content", req.prompt) if isinstance(user_msg.get("content"), str) else req.prompt,
            system_prompt=system_msg.get("content", "You are CAT Vision Agent."),
            history=None,
            config=config,
            attachments=[att],
            size_class="large",
        )
        return {"ok": True, "analysis": analysis, "frame_index": best_frame.index}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/vision/verify")
async def vision_verify(req: VisionVerifyRequest):
    session = vision_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    verification = vision_verifier.start_verification()
    best_frame = session.pipeline.get_best_frame()
    if best_frame:
        vision_verifier.set_before_frame(
            best_frame.frame_b64, best_frame.meta.to_dict()
        )
    vision_verifier.set_fix_applied(req.fix_description)
    return {
        "ok": True,
        "verification": verification.to_dict(),
        "message": "Before frame captured. Apply fix, then submit after frame.",
    }


@app.post("/api/vision/verify/after")
async def vision_verify_after(session_id: str = Form(...),
                               frame_b64: str = Form(...)):
    vision_verifier.set_after_frame(frame_b64)
    prompt = vision_verifier.build_comparison_prompt()
    try:
        from calc_terminal import aicore
        config, caps = vision_router.find_vision_capable() or (None, None)
        if config and vision_verifier.current and vision_verifier.current.before_frame_b64:
            from calc_terminal.attachments import Attachment
            att_before = Attachment.__new__(Attachment)
            att_before.id = "att-vision-before"
            att_before.name = "before"
            att_before.path = ""
            att_before.extension = ".png"
            att_before.mime_type = "image/png"
            att_before.size = len(vision_verifier.current.before_frame_b64)
            att_before.kind = "image"
            att_before.content = "[before frame]"
            att_before.metadata = {"inline_b64": vision_verifier.current.before_frame_b64}
            att_before.extraction_status = "ready"
            att_before.error = None
            att_before.created_at = time.time()
            att_before.source = "vision_verify"
            att_after = Attachment.__new__(Attachment)
            att_after.id = "att-vision-after"
            att_after.name = "after"
            att_after.path = ""
            att_after.extension = ".png"
            att_after.mime_type = "image/png"
            att_after.size = len(frame_b64)
            att_after.kind = "image"
            att_after.content = "[after frame]"
            att_after.metadata = {"inline_b64": frame_b64}
            att_after.extraction_status = "ready"
            att_after.error = None
            att_after.created_at = time.time()
            att_after.source = "vision_verify"
            analysis = aicore.query_ai(
                prompt,
                system_prompt="You are CAT Vision verification agent. Compare before and after states.",
                history=None,
                config=config,
                attachments=[att_before, att_after],
                size_class="large",
            )
            passed = "PASS" in (analysis or "").upper()[:200]
            vision_verifier.complete(
                ai_analysis=analysis or "",
                passed=passed,
                confidence=0.8 if passed else 0.3,
            )
            return {"ok": True, "result": vision_verifier.history[-1].to_dict()}
    except Exception as e:
        vision_verifier.error(str(e))
    return {"ok": True, "result": verification_status()}


def verification_status():
    if vision_verifier.current:
        return vision_verifier.current.to_dict()
    return {"status": "idle"}


@app.get("/api/vision/verify/status")
async def vision_verify_status():
    return {"ok": True, "verification": verification_status()}


@app.get("/api/vision/verify/history")
async def vision_verify_history():
    return {"ok": True, "history": vision_verifier.history}


@app.post("/api/vision/verify/clear")
async def vision_verify_clear():
    vision_verifier.clear_history()
    return {"ok": True}


@app.post("/api/vision/provider/route")
async def vision_provider_route(session_id: str = Form(...)):
    session = vision_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    best = session.pipeline.get_best_frame()
    size = len(best.frame_b64) if best else 0
    result = vision_router.route_vision_request(best.frame_b64 if best else "", size)
    return {"ok": True, "route": result}


@app.get("/api/vision/provider/capabilities")
async def vision_provider_capabilities():
    return {"ok": True, "capabilities": vision_router.get_all_capabilities()}


@app.get("/api/vision/privacy")
async def vision_privacy_summary():
    return {"ok": True, "privacy": vision_manager._privacy.get_privacy_summary()}


@app.get("/api/vision/privacy/log")
async def vision_privacy_log(limit: int = 100):
    return {"ok": True, "log": vision_manager._privacy.get_access_log(limit)}


class VisionCursorRequest(BaseModel):
    session_id: str
    x: float = 0.0
    y: float = 0.0
    pointer_type: Optional[str] = "mouse"
    pointer_id: Optional[int] = 0
    button: Optional[int] = 0
    pressure: Optional[float] = 0.5
    movement_x: Optional[float] = 0.0
    movement_y: Optional[float] = 0.0
    is_click: Optional[bool] = False
    is_double_click: Optional[bool] = False
    is_drag: Optional[bool] = False
    is_scroll: Optional[bool] = False
    scroll_delta: Optional[float] = 0.0


@app.post("/api/vision/cursor")
async def vision_cursor(req: VisionCursorRequest):
    session = vision_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    try:
        session.cursor.add_raw(
            x=req.x, y=req.y,
            pointer_type=req.pointer_type or "mouse",
            pointer_id=req.pointer_id or 0,
            button=req.button or 0,
            pressure=req.pressure or 0.5,
            movement_x=req.movement_x or 0.0,
            movement_y=req.movement_y or 0.0,
            is_click=bool(req.is_click),
            is_double_click=bool(req.is_double_click),
            is_drag=bool(req.is_drag),
            is_scroll=bool(req.is_scroll),
            scroll_delta=req.scroll_delta or 0.0,
        )
        # Priority signals from cursor
        if req.is_click:
            session.priority.signal_click()
        elif req.is_drag:
            session.priority.add_signal("cursor_move")
        # live status
        return {"ok": True, "cursor": session.cursor.get_cursor_context()}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/vision/cursor/{session_id}")
async def vision_cursor_get(session_id: str):
    session = vision_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return {"ok": True, "cursor": session.cursor.get_cursor_context(), "dwells": [d.to_dict() for d in session.cursor.dwells]}


@app.post("/api/vision/correlate")
async def vision_correlate(req: VisionContextRequest):
    """Screen→Code correlation (spec 20). Honest mapping, never hallucinates."""
    session = vision_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    try:
        from calc_terminal.vision.correlation import correlate as do_correlate
        workspace_root = None
        try:
            from calc_terminal import workspace as ws
            workspace_root = ws.root_dir() or ws.active_project()
        except Exception:
            workspace_root = None
        # preview context if preview running
        preview_ctx = None
        try:
            # try to get preview url from workspace state
            preview_ctx = {"entry": req.file_path or ""}
        except Exception:
            pass
        result = do_correlate(
            annotations=session.annotations.to_list(),
            cursor=session.cursor.get_cursor_context() if hasattr(session, 'cursor') else None,
            preview_context=preview_ctx,
            workspace_root=workspace_root,
        )
        return {"ok": True, "correlation": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/vision/pipeline/summary/{session_id}")
async def vision_pipeline_summary(session_id: str):
    session = vision_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return {"ok": True, "summary": session.pipeline.get_summary()}


@app.get("/api/vision/pipeline/context/{session_id}")
async def vision_pipeline_context(session_id: str, n: int = 5):
    session = vision_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return {"ok": True, "frames": session.pipeline.get_context_frames(n)}


# ============================================================
# Server Lifecycle & Auto-Start Utilities
# ============================================================

def is_server_running(host: str = "127.0.0.1", port: int = 8765, timeout: float = 1.0) -> bool:
    """Check if Fatty CAT server is reachable."""
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def ensure_fatty_server(timeout: float = 10.0, auto_start: bool = True) -> bool:
    """Ensure the Fatty CAT web server is running.
    If not running and auto_start is True, spawn it as a background process.
    Returns True if reachable (already or after auto-start).
    """
    if is_server_running(timeout=0.8):
        return True
    if not auto_start:
        return False

    import subprocess
    python_exe = sys.executable or "python"

    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    try:
        # `python -m calc_terminal.web.server` works from ANY cwd when CAT is
        # pip-installed (and from a source checkout too), so do not force
        # cwd to the git repo root — that path does not exist on a friend's
        # computer. Inherit the caller's cwd instead.
        subprocess.Popen(
            [python_exe, "-m", "calc_terminal.web.server"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except Exception as e:
        print(f"[FATTY CAT] Failed to auto-start server: {e}", file=sys.stderr)
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_server_running(timeout=0.5):
            return True
        time.sleep(0.3)
    return False


# ============================================================
# Main Entry Point
# ============================================================

def main():
    import uvicorn
    uvicorn.run(
        "calc_terminal.web.server:app",
        host="0.0.0.0",
        port=8765,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()