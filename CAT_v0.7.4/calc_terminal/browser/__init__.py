"""
CAT — browser/ package: the Live Web Preview subsystem.

A real local development server + a REAL Chromium engine (via Playwright)
embedded in CAT's right workspace pane, with debounced live reload driven
by the file watcher (including AI writes) and a WebSocket hot-reload
channel.

    CAT
     ├── Terminal UI            (calc_terminal/ui/)
     ├── AI Agent               (calc_terminal/agent.py)
     ├── Code Editor            (ui/editor.py)
     └── Browser Preview        (THIS package)
           ├── preview.py       PreviewController — owns lifecycle/state
           ├── server.py        LiveServer — 127.0.0.1 static server + WS channel
           ├── engine.py        BrowserEngine — Playwright Chromium worker
           ├── watcher.py       PreviewFileWatcher — debounced web-file watch
           ├── navigation.py    NavigationHistory — back/forward/reload
           └── state.py         WorkspaceMode / PaneMode / *State enums

Terminal-first: nothing here opens an external browser window.
"""

from .state import (WorkspaceMode, PaneMode, PreviewState, ServerState,
                    EditorState, PreviewSnapshot)
from .navigation import NavigationHistory
from .preview import PreviewController
from .project_detector import detect_project, Detection
from .devserver import DevServerProcess, extract_local_url

__all__ = [
    "WorkspaceMode", "PaneMode", "PreviewState", "ServerState",
    "EditorState", "PreviewSnapshot", "NavigationHistory",
    "PreviewController", "detect_project", "Detection",
    "DevServerProcess", "extract_local_url",
]
