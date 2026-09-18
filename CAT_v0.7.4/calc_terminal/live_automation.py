"""
CCT — live_automation.py: Real-time file change synchronization (v0.7.10 spec #13).

Monitors file changes and synchronizes them across:
- Editor tabs (auto-reload modified files)
- Preview panel (trigger hot reload)
- File explorer (refresh tree)
- AI activity (notify of changes)

Architecture:
    FS Watcher -> LiveAutomationManager -> [Editor, Preview, Explorer]
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os
import threading
import time
from typing import Callable, Optional, Set
from dataclasses import dataclass, field


@dataclass
class FileChangeEvent:
    """Represents a file system change event."""
    path: str
    change_type: str  # "created", "modified", "deleted", "renamed"
    timestamp: float = field(default_factory=time.time)
    is_web_file: bool = False
    is_code_file: bool = False


class LiveAutomationManager:
    """Manages real-time file synchronization across CAT components.

    This class coordinates file change events and triggers appropriate
    updates in the editor, preview, and explorer.
    """

    # File extensions that trigger web preview updates
    WEB_EXTENSIONS = {
        ".html", ".htm", ".css", ".js", ".mjs", ".json", ".svg",
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp",
        ".woff", ".woff2", ".ttf", ".otf",
    }

    # File extensions that are code files (for editor updates)
    CODE_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".scss",
        ".json", ".yaml", ".yml", ".toml", ".md", ".rs", ".go", ".java",
        ".xml", ".sql", ".sh", ".bash",
    }

    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self._callbacks = {
            "editor": [],
            "preview": [],
            "explorer": [],
            "activity": [],
        }
        self._debounce_timers = {}
        self._lock = threading.Lock()
        self._pending_events = {}
        self._debounce_interval = 0.15  # 150ms debounce

    def register_callback(self, component: str, callback: Callable):
        """Register a callback for a specific component type."""
        if component in self._callbacks:
            self._callbacks[component].append(callback)

    def on_file_changed(self, path: str, change_type: str = "modified"):
        """Handle a file change event with debouncing."""
        path = os.path.abspath(path)
        event = FileChangeEvent(
            path=path,
            change_type=change_type,
            is_web_file=self._is_web_file(path),
            is_code_file=self._is_code_file(path),
        )

        with self._lock:
            # Debounce rapid changes to the same file
            if path in self._debounce_timers:
                self._debounce_timers[path].cancel()

            self._pending_events[path] = event
            timer = threading.Timer(
                self._debounce_interval,
                self._process_event,
                args=(path,)
            )
            timer.daemon = True
            self._debounce_timers[path] = timer
            timer.start()

    def _process_event(self, path: str):
        """Process a debounced file change event."""
        with self._lock:
            event = self._pending_events.pop(path, None)
            self._debounce_timers.pop(path, None)

        if event is None:
            return

        # Notify appropriate components
        if event.is_code_file:
            self._notify("editor", event)
        if event.is_web_file:
            self._notify("preview", event)
        self._notify("explorer", event)
        self._notify("activity", event)

    def _notify(self, component: str, event: FileChangeEvent):
        """Notify all callbacks for a component type."""
        for callback in self._callbacks.get(component, []):
            try:
                callback(event)
            except Exception:
                pass

    def _is_web_file(self, path: str) -> bool:
        """Check if a file is a web file (HTML, CSS, JS, etc.)."""
        ext = os.path.splitext(path)[1].lower()
        return ext in self.WEB_EXTENSIONS

    def _is_code_file(self, path: str) -> bool:
        """Check if a file is a code file."""
        ext = os.path.splitext(path)[1].lower()
        return ext in self.CODE_EXTENSIONS

    def sync_editor(self, editor, event: FileChangeEvent):
        """Synchronize editor with file changes."""
        if event.change_type == "modified":
            editor.reload_if_open(event.path)
        elif event.change_type == "deleted":
            # Close tab if file was deleted
            if hasattr(editor, '_open_paths') and event.path in editor._open_paths:
                tab_id = editor._open_paths[event.path]
                editor.close_active(tab_id)

    def sync_preview(self, preview_controller, event: FileChangeEvent):
        """Synchronize preview with file changes."""
        if event.is_web_file and preview_controller:
            preview_controller.notify_ai_wrote(event.path)

    def sync_explorer(self, explorer, event: FileChangeEvent):
        """Synchronize explorer tree with file changes."""
        if hasattr(explorer, 'refresh_tree'):
            explorer.refresh_tree()


# Global instance
_automation_manager = None


def get_automation_manager(root: str = None) -> LiveAutomationManager:
    """Get or create the global automation manager."""
    global _automation_manager
    if _automation_manager is None or (root and _automation_manager.root != root):
        _automation_manager = LiveAutomationManager(root or os.getcwd())
    return _automation_manager
