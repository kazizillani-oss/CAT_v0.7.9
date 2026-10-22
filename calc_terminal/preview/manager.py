"""CAT Live Preview — Preview Manager (calc_terminal/preview/manager.py).

High-level session coordinator according to Preview API contract:
- start(), stop(), restart(), reload(), get(), get_active().
- Coordinates between DevServerManager, LiveReloadManager, and UI.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Dict, Optional

from .dev_server import DevServerManager, ServerState


@dataclass
class PreviewSession:
    """Represents an active preview session for a project."""
    id: str
    project_path: str
    url: str
    port: int
    status: str
    framework: Optional[str] = None
    created_at: float = 0.0


class PreviewManager:
    """Manages active preview sessions across CAT IDE."""

    def __init__(self) -> None:
        self._sessions: Dict[str, PreviewSession] = {}
        self._path_to_session_id: Dict[str, str] = {}

    def start(self, project_path: str, options: Optional[dict] = None) -> PreviewSession:
        """Start or reuse an existing preview session for a project path."""
        norm_path = DevServerManager(project_path).root
        existing = self.get_active(norm_path)
        if existing and existing.status == ServerState.RUNNING:
            return existing

        dev_mgr = DevServerManager.get_or_create(norm_path)
        ok, url = dev_mgr.start()
        session_id = self._path_to_session_id.get(norm_path) or uuid.uuid4().hex

        status = dev_mgr.state
        port = dev_mgr.port or 5173
        framework = dev_mgr.project_info.kind if dev_mgr.project_info.is_framework else None

        session = PreviewSession(
            id=session_id,
            project_path=norm_path,
            url=url if ok else "",
            port=port,
            status=status,
            framework=framework,
            created_at=time.time(),
        )
        self._sessions[session_id] = session
        self._path_to_session_id[norm_path] = session_id
        return session

    def stop(self, session_id: str) -> None:
        """Stop a preview session."""
        session = self.get(session_id)
        if session:
            dev_mgr = DevServerManager.get_or_create(session.project_path)
            dev_mgr.stop()
            session.status = ServerState.STOPPED

    def restart(self, session_id: str) -> Optional[PreviewSession]:
        """Restart a preview session."""
        session = self.get(session_id)
        if not session:
            return None
        dev_mgr = DevServerManager.get_or_create(session.project_path)
        ok, url = dev_mgr.restart()
        session.status = dev_mgr.state
        session.url = url
        return session

    def reload(self, session_id: str) -> bool:
        """Trigger reload of the active preview."""
        session = self.get(session_id)
        if not session:
            return False
        # Notify connected preview clients through LiveServer ws channel if static
        dev_mgr = DevServerManager.get_or_create(session.project_path)
        if dev_mgr._server_instance is not None and hasattr(dev_mgr._server_instance, "broadcast"):
            try:
                dev_mgr._server_instance.broadcast({"cmd": "reload"})
                return True
            except Exception:
                pass
        return False

    def get(self, session_id: str) -> Optional[PreviewSession]:
        """Look up a preview session by its ID."""
        return self._sessions.get(session_id)

    def get_active(self, project_path: str) -> Optional[PreviewSession]:
        """Return the active preview session for a project path if any exists."""
        norm_path = DevServerManager(project_path).root
        sid = self._path_to_session_id.get(norm_path)
        if sid:
            return self._sessions.get(sid)
        return None

    def cleanup_all(self) -> None:
        """Clean up all active preview sessions and dev servers."""
        for sid in list(self._sessions.keys()):
            self.stop(sid)
        self._sessions.clear()
        self._path_to_session_id.clear()
        DevServerManager.cleanup_all()


# Global preview manager singleton
_GLOBAL_PREVIEW_MANAGER: Optional[PreviewManager] = None


def get_preview_manager() -> PreviewManager:
    """Return the global PreviewManager singleton."""
    global _GLOBAL_PREVIEW_MANAGER
    if _GLOBAL_PREVIEW_MANAGER is None:
        _GLOBAL_PREVIEW_MANAGER = PreviewManager()
    return _GLOBAL_PREVIEW_MANAGER
