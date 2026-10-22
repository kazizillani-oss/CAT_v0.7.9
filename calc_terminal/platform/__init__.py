"""
CAT Platform Abstraction Layer

Provides a unified interface for platform-specific operations:
- Desktop (native Python)
- Web/PWA (browser via WebAssembly or server-bridged)
"""

from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, List, Optional, Union
from enum import Enum


class PlatformType(Enum):
    DESKTOP = "desktop"
    WEB = "web"
    PWA = "pwa"


@dataclass
class PlatformInfo:
    type: PlatformType
    name: str
    version: str
    is_mobile: bool
    supports_file_system_access: bool
    supports_notifications: bool
    supports_background_sync: bool
    user_agent: str = ""


class FileHandle(ABC):
    """Abstract file handle for platform-agnostic file operations."""
    
    @abstractmethod
    async def read(self, size: int = -1) -> bytes:
        pass
    
    @abstractmethod
    async def write(self, data: Union[bytes, str]) -> int:
        pass
    
    @abstractmethod
    async def close(self) -> None:
        pass
    
    @abstractmethod
    async def seek(self, offset: int, whence: int = 0) -> int:
        pass
    
    @abstractmethod
    def tell(self) -> int:
        pass


class DirectoryHandle(ABC):
    """Abstract directory handle for platform-agnostic directory operations."""
    
    @abstractmethod
    async def get_file_handle(self, name: str, create: bool = False) -> FileHandle:
        pass
    
    @abstractmethod
    async def get_directory_handle(self, name: str, create: bool = False) -> DirectoryHandle:
        pass
    
    @abstractmethod
    async def remove_entry(self, name: str, recursive: bool = False) -> None:
        pass
    
    @abstractmethod
    async def list_entries(self) -> List[str]:
        pass


class PlatformBase(ABC):
    """Abstract base class for platform implementations."""
    
    @property
    @abstractmethod
    def info(self) -> PlatformInfo:
        pass
    
    # --- Filesystem ---
    
    @abstractmethod
    async def get_root_directory(self) -> DirectoryHandle:
        """Get the root directory handle (workspace root for web, home for desktop)."""
        pass
    
    @abstractmethod
    async def pick_directory(self, title: str = "Select folder") -> Optional[DirectoryHandle]:
        """Show directory picker dialog."""
        pass
    
    @abstractmethod
    async def pick_file(self, title: str = "Select file", accept: Optional[dict] = None) -> Optional[FileHandle]:
        """Show file picker dialog."""
        pass
    
    @abstractmethod
    async def resolve_path(self, path: str) -> str:
        """Resolve a path to absolute form."""
        pass
    
    @abstractmethod
    async def path_exists(self, path: str) -> bool:
        """Check if path exists."""
        pass
    
    @abstractmethod
    async def is_directory(self, path: str) -> bool:
        """Check if path is a directory."""
        pass
    
    @abstractmethod
    async def is_file(self, path: str) -> bool:
        """Check if path is a file."""
        pass
    
    @abstractmethod
    async def list_directory(self, path: str) -> List[str]:
        """List directory contents."""
        pass
    
    @abstractmethod
    async def read_file(self, path: str, encoding: Optional[str] = None) -> Union[str, bytes]:
        """Read file contents."""
        pass
    
    @abstractmethod
    async def write_file(self, path: str, data: Union[str, bytes], encoding: Optional[str] = None) -> int:
        """Write file contents."""
        pass
    
    @abstractmethod
    async def delete_file(self, path: str) -> None:
        """Delete a file."""
        pass
    
    @abstractmethod
    async def delete_directory(self, path: str, recursive: bool = False) -> None:
        """Delete a directory."""
        pass
    
    @abstractmethod
    async def create_directory(self, path: str, parents: bool = True) -> None:
        """Create a directory."""
        pass
    
    @abstractmethod
    async def copy_file(self, src: str, dst: str) -> None:
        """Copy a file."""
        pass
    
    @abstractmethod
    async def move_file(self, src: str, dst: str) -> None:
        """Move/rename a file."""
        pass
    
    @abstractmethod
    async def get_file_size(self, path: str) -> int:
        """Get file size in bytes."""
        pass
    
    @abstractmethod
    async def get_file_mtime(self, path: str) -> float:
        """Get file modification time."""
        pass
    
    # --- Process Execution ---
    
    @abstractmethod
    async def run_command(
        self,
        cmd: Union[str, List[str]],
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
        capture_output: bool = True,
        timeout: Optional[float] = None,
    ) -> "CommandResult":
        """Run a command and return result."""
        pass
    
    @abstractmethod
    async def start_process(
        self,
        cmd: Union[str, List[str]],
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ) -> "ProcessHandle":
        """Start a background process."""
        pass
    
    # --- Clipboard ---
    
    @abstractmethod
    async def read_clipboard(self) -> str:
        """Read text from clipboard."""
        pass
    
    @abstractmethod
    async def write_clipboard(self, text: str) -> None:
        """Write text to clipboard."""
        pass
    
    # --- Notifications ---
    
    @abstractmethod
    async def show_notification(
        self,
        title: str,
        body: str,
        icon: Optional[str] = None,
    ) -> None:
        """Show a system notification."""
        pass
    
    @abstractmethod
    async def request_notification_permission(self) -> bool:
        """Request permission for notifications."""
        pass
    
    # --- Browser/URL ---
    
    @abstractmethod
    async def open_url(self, url: str) -> bool:
        """Open a URL in the default browser."""
        pass
    
    # --- Keyboard/Input ---
    
    @abstractmethod
    async def show_keyboard(self) -> None:
        """Show virtual keyboard (mobile)."""
        pass
    
    @abstractmethod
    async def hide_keyboard(self) -> None:
        """Hide virtual keyboard (mobile)."""
        pass
    
    # --- Storage ---
    
    @abstractmethod
    async def get_storage_estimate(self) -> dict:
        """Get storage usage estimate."""
        pass
    
    @abstractmethod
    async def request_persistent_storage(self) -> bool:
        """Request persistent storage (web)."""
        pass
    
    # --- App Lifecycle ---
    
    @abstractmethod
    async def minimize_app(self) -> None:
        """Minimize the app."""
        pass
    
    @abstractmethod
    async def close_app(self) -> None:
        """Close the app."""
        pass
    
    # --- Platform-specific ---
    
    @abstractmethod
    def get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get environment variable."""
        pass
    
    @abstractmethod
    def set_env(self, key: str, value: str) -> None:
        """Set environment variable."""
        pass


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    success: bool


class ProcessHandle(ABC):
    """Handle for a running background process."""
    
    @abstractmethod
    async def wait(self, timeout: Optional[float] = None) -> CommandResult:
        pass
    
    @abstractmethod
    async def terminate(self) -> None:
        pass
    
    @abstractmethod
    async def kill(self) -> None:
        pass
    
    @property
    @abstractmethod
    def pid(self) -> Optional[int]:
        pass
    
    @property
    @abstractmethod
    def returncode(self) -> Optional[int]:
        pass


# Global platform instance
_platform: Optional[PlatformBase] = None


def get_platform() -> PlatformBase:
    """Get the current platform implementation."""
    global _platform
    if _platform is None:
        _platform = _detect_platform()
    return _platform


def set_platform(platform: PlatformBase) -> None:
    """Set the platform implementation (for testing/override)."""
    global _platform
    _platform = platform


def _detect_platform() -> PlatformBase:
    """Auto-detect the platform."""
    # Check if running in browser (Pyodide/WASM)
    if "pyodide" in sys.modules or hasattr(sys, "implementation") and sys.implementation.name == "pyodide":
        from .web import WebPlatform
        return WebPlatform()
    
    # Check if running in a PWA context (served via HTTP)
    if os.environ.get("CAT_PLATFORM") == "web":
        from .web import WebPlatform
        return WebPlatform()
    
    # Default to desktop
    from .desktop import DesktopPlatform
    return DesktopPlatform()


# Convenience functions that delegate to the platform
async def get_root_directory() -> DirectoryHandle:
    return await get_platform().get_root_directory()


async def pick_directory(title: str = "Select folder") -> Optional[DirectoryHandle]:
    return await get_platform().pick_directory(title)


async def pick_file(title: str = "Select file", accept: Optional[dict] = None) -> Optional[FileHandle]:
    return await get_platform().pick_file(title, accept)


async def resolve_path(path: str) -> str:
    return await get_platform().resolve_path(path)


async def path_exists(path: str) -> bool:
    return await get_platform().path_exists(path)


async def is_directory(path: str) -> bool:
    return await get_platform().is_directory(path)


async def is_file(path: str) -> bool:
    return await get_platform().is_file(path)


async def list_directory(path: str) -> List[str]:
    return await get_platform().list_directory(path)


async def read_file(path: str, encoding: Optional[str] = None) -> Union[str, bytes]:
    return await get_platform().read_file(path, encoding)


async def write_file(path: str, data: Union[str, bytes], encoding: Optional[str] = None) -> int:
    return await get_platform().write_file(path, data, encoding)


async def delete_file(path: str) -> None:
    return await get_platform().delete_file(path)


async def delete_directory(path: str, recursive: bool = False) -> None:
    return await get_platform().delete_directory(path, recursive)


async def create_directory(path: str, parents: bool = True) -> None:
    return await get_platform().create_directory(path, parents)


async def copy_file(src: str, dst: str) -> None:
    return await get_platform().copy_file(src, dst)


async def move_file(src: str, dst: str) -> None:
    return await get_platform().move_file(src, dst)


async def get_file_size(path: str) -> int:
    return await get_platform().get_file_size(path)


async def get_file_mtime(path: str) -> float:
    return await get_platform().get_file_mtime(path)


async def run_command(
    cmd: Union[str, List[str]],
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    capture_output: bool = True,
    timeout: Optional[float] = None,
) -> CommandResult:
    return await get_platform().run_command(cmd, cwd, env, capture_output, timeout)


async def start_process(
    cmd: Union[str, List[str]],
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
) -> ProcessHandle:
    return await get_platform().start_process(cmd, cwd, env)


async def read_clipboard() -> str:
    return await get_platform().read_clipboard()


async def write_clipboard(text: str) -> None:
    return await get_platform().write_clipboard(text)


async def show_notification(title: str, body: str, icon: Optional[str] = None) -> None:
    return await get_platform().show_notification(title, body, icon)


async def request_notification_permission() -> bool:
    return await get_platform().request_notification_permission()


async def open_url(url: str) -> bool:
    return await get_platform().open_url(url)


async def show_keyboard() -> None:
    return await get_platform().show_keyboard()


async def hide_keyboard() -> None:
    return await get_platform().hide_keyboard()


async def get_storage_estimate() -> dict:
    return await get_platform().get_storage_estimate()


async def request_persistent_storage() -> bool:
    return await get_platform().request_persistent_storage()


async def minimize_app() -> None:
    return await get_platform().minimize_app()


async def close_app() -> None:
    return await get_platform().close_app()


def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    return get_platform().get_env(key, default)


def set_env(key: str, value: str) -> None:
    return get_platform().set_env(key, value)