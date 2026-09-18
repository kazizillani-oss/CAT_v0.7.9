"""
Web/PWA Platform Implementation

Runs in browser via Pyodide (WASM) or bridges to a server for native execution.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Union

from . import (
    PlatformBase,
    PlatformInfo,
    PlatformType,
    FileHandle,
    DirectoryHandle,
    CommandResult,
    ProcessHandle,
)


class WebFileHandle(FileHandle):
    """File handle for web platform (uses IndexedDB/File System Access API)."""
    
    def __init__(self, file_id: str, path: str, writable: bool = False):
        self._file_id = file_id
        self._path = path
        self._writable = writable
        self._position = 0
        self._closed = False
        self._buffer: bytearray = bytearray()
    
    async def read(self, size: int = -1) -> bytes:
        if self._closed:
            raise ValueError("File handle closed")
        
        # Request file content from browser
        from js import CATBridge  # type: ignore
        result = await CATBridge.readFile(self._file_id, self._position, size)
        data = bytes(result.to_py())
        self._position += len(data)
        return data
    
    async def write(self, data: Union[bytes, str]) -> int:
        if self._closed:
            raise ValueError("File handle closed")
        if not self._writable:
            raise PermissionError("File not opened for writing")
        
        if isinstance(data, str):
            data = data.encode("utf-8")
        
        self._buffer.extend(data)
        self._position += len(data)
        return len(data)
    
    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        
        if self._writable and self._buffer:
            from js import CATBridge  # type: ignore
            await CATBridge.writeFile(self._file_id, bytes(self._buffer))
            self._buffer.clear()
    
    async def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:  # SEEK_SET
            self._position = offset
        elif whence == 1:  # SEEK_CUR
            self._position += offset
        elif whence == 2:  # SEEK_END
            # Need to get file size
            from js import CATBridge  # type: ignore
            size = await CATBridge.getFileSize(self._file_id)
            self._position = size + offset
        return self._position
    
    def tell(self) -> int:
        return self._position


class WebDirectoryHandle(DirectoryHandle):
    """Directory handle for web platform."""
    
    def __init__(self, dir_id: str, path: str):
        self._dir_id = dir_id
        self._path = path
    
    async def get_file_handle(self, name: str, create: bool = False) -> FileHandle:
        from js import CATBridge  # type: ignore
        file_id = await CATBridge.getFileHandle(self._dir_id, name, create)
        return WebFileHandle(file_id, f"{self._path}/{name}", writable=create)
    
    async def get_directory_handle(self, name: str, create: bool = False) -> DirectoryHandle:
        from js import CATBridge  # type: ignore
        dir_id = await CATBridge.getDirectoryHandle(self._dir_id, name, create)
        return WebDirectoryHandle(dir_id, f"{self._path}/{name}")
    
    async def remove_entry(self, name: str, recursive: bool = False) -> None:
        from js import CATBridge  # type: ignore
        await CATBridge.removeEntry(self._dir_id, name, recursive)
    
    async def list_entries(self) -> List[str]:
        from js import CATBridge  # type: ignore
        result = await CATBridge.listDirectory(self._dir_id)
        return list(result.to_py())


class WebProcessHandle(ProcessHandle):
    """Process handle for web platform (runs on server via bridge)."""
    
    def __init__(self, process_id: str):
        self._process_id = process_id
        self._returncode: Optional[int] = None
    
    async def wait(self, timeout: Optional[float] = None) -> CommandResult:
        from js import CATBridge  # type: ignore
        try:
            result = await asyncio.wait_for(
                CATBridge.waitProcess(self._process_id),
                timeout=timeout,
            )
            data = result.to_py()
            self._returncode = data["returncode"]
            return CommandResult(
                returncode=data["returncode"],
                stdout=data["stdout"],
                stderr=data["stderr"],
                success=data["returncode"] == 0,
            )
        except asyncio.TimeoutError:
            await self.kill()
            return CommandResult(
                returncode=-1,
                stdout="",
                stderr="Process timed out",
                success=False,
            )
    
    async def terminate(self) -> None:
        from js import CATBridge  # type: ignore
        await CATBridge.terminateProcess(self._process_id)
    
    async def kill(self) -> None:
        from js import CATBridge  # type: ignore
        await CATBridge.killProcess(self._process_id)
    
    @property
    def pid(self) -> Optional[int]:
        # Not applicable in web context
        return None
    
    @property
    def returncode(self) -> Optional[int]:
        return self._returncode


class WebPlatform(PlatformBase):
    """Web/PWA platform implementation."""
    
    def __init__(self):
        self._info = PlatformInfo(
            type=PlatformType.WEB,
            name="FATTY CAT",
            version="0.7.9.0",
            is_mobile=self._detect_mobile(),
            supports_file_system_access=self._check_fs_access(),
            supports_notifications="Notification" in globals(),
            supports_background_sync="serviceWorker" in globals() and "sync" in globals().get("serviceWorker", {}),
            user_agent=globals().get("navigator", {}).userAgent if "navigator" in globals() else "",
        )
        self._root_handle: Optional[WebDirectoryHandle] = None
    
    def _detect_mobile(self) -> bool:
        try:
            from js import navigator  # type: ignore
            return "Mobi" in navigator.userAgent or "Android" in navigator.userAgent
        except Exception:
            return False
    
    def _check_fs_access(self) -> bool:
        try:
            from js import window  # type: ignore
            return hasattr(window, "showDirectoryPicker")
        except Exception:
            return False
    
    @property
    def info(self) -> PlatformInfo:
        return self._info
    
    # --- Filesystem ---
    
    async def get_root_directory(self) -> DirectoryHandle:
        if self._root_handle:
            return self._root_handle
        
        from js import CATBridge  # type: ignore
        # Try to get persisted workspace directory
        dir_id = await CATBridge.getWorkspaceRoot()
        if not dir_id:
            # Request directory permission
            dir_id = await CATBridge.requestWorkspaceAccess()
        
        self._root_handle = WebDirectoryHandle(dir_id, "/workspace")
        return self._root_handle
    
    async def pick_directory(self, title: str = "Select folder") -> Optional[DirectoryHandle]:
        from js import CATBridge  # type: ignore
        dir_id = await CATBridge.pickDirectory(title)
        if dir_id:
            return WebDirectoryHandle(dir_id, "/selected")
        return None
    
    async def pick_file(self, title: str = "Select file", accept: Optional[dict] = None) -> Optional[FileHandle]:
        from js import CATBridge  # type: ignore
        accept_list = []
        if accept:
            for desc, exts in accept.items():
                accept_list.append({"description": desc, "extensions": exts})
        
        file_id = await CATBridge.pickFile(title, accept_list)
        if file_id:
            return WebFileHandle(file_id, "/selected/file", writable=False)
        return None
    
    async def resolve_path(self, path: str) -> str:
        # In web, paths are relative to workspace root
        if path.startswith("/"):
            return path
        root = await self.get_root_directory()
        return f"{root._path}/{path}"
    
    async def path_exists(self, path: str) -> bool:
        from js import CATBridge  # type: ignore
        return await CATBridge.pathExists(path)
    
    async def is_directory(self, path: str) -> bool:
        from js import CATBridge  # type: ignore
        return await CATBridge.isDirectory(path)
    
    async def is_file(self, path: str) -> bool:
        from js import CATBridge  # type: ignore
        return await CATBridge.isFile(path)
    
    async def list_directory(self, path: str) -> List[str]:
        from js import CATBridge  # type: ignore
        result = await CATBridge.listDirectory(path)
        return list(result.to_py())
    
    async def read_file(self, path: str, encoding: Optional[str] = None) -> Union[str, bytes]:
        from js import CATBridge  # type: ignore
        result = await CATBridge.readFileByPath(path)
        data = bytes(result.to_py())
        if encoding:
            return data.decode(encoding, errors="replace")
        return data
    
    async def write_file(self, path: str, data: Union[str, bytes], encoding: Optional[str] = None) -> int:
        from js import CATBridge  # type: ignore
        if isinstance(data, str):
            data = data.encode(encoding or "utf-8")
        return await CATBridge.writeFileByPath(path, list(data))
    
    async def delete_file(self, path: str) -> None:
        from js import CATBridge  # type: ignore
        await CATBridge.deleteFile(path)
    
    async def delete_directory(self, path: str, recursive: bool = False) -> None:
        from js import CATBridge  # type: ignore
        await CATBridge.deleteDirectory(path, recursive)
    
    async def create_directory(self, path: str, parents: bool = True) -> None:
        from js import CATBridge  # type: ignore
        await CATBridge.createDirectory(path, parents)
    
    async def copy_file(self, src: str, dst: str) -> None:
        from js import CATBridge  # type: ignore
        await CATBridge.copyFile(src, dst)
    
    async def move_file(self, src: str, dst: str) -> None:
        from js import CATBridge  # type: ignore
        await CATBridge.moveFile(src, dst)
    
    async def get_file_size(self, path: str) -> int:
        from js import CATBridge  # type: ignore
        return await CATBridge.getFileSize(path)
    
    async def get_file_mtime(self, path: str) -> float:
        from js import CATBridge  # type: ignore
        return await CATBridge.getFileMTime(path)
    
    # --- Process Execution ---
    
    async def run_command(
        self,
        cmd: Union[str, List[str]],
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
        capture_output: bool = True,
        timeout: Optional[float] = None,
    ) -> CommandResult:
        from js import CATBridge  # type: ignore
        
        if isinstance(cmd, list):
            cmd_str = " ".join(cmd)
        else:
            cmd_str = cmd
        
        result = await CATBridge.runCommand(cmd_str, cwd or "/workspace", env or {}, capture_output, timeout or 30)
        data = result.to_py()
        return CommandResult(
            returncode=data["returncode"],
            stdout=data["stdout"],
            stderr=data["stderr"],
            success=data["returncode"] == 0,
        )
    
    async def start_process(
        self,
        cmd: Union[str, List[str]],
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ) -> ProcessHandle:
        from js import CATBridge  # type: ignore
        
        if isinstance(cmd, list):
            cmd_str = " ".join(cmd)
        else:
            cmd_str = cmd
        
        process_id = await CATBridge.startProcess(cmd_str, cwd or "/workspace", env or {})
        return WebProcessHandle(process_id)
    
    # --- Clipboard ---
    
    async def read_clipboard(self) -> str:
        from js import CATBridge  # type: ignore
        return await CATBridge.readClipboard()
    
    async def write_clipboard(self, text: str) -> None:
        from js import CATBridge  # type: ignore
        await CATBridge.writeClipboard(text)
    
    # --- Notifications ---
    
    async def show_notification(self, title: str, body: str, icon: Optional[str] = None) -> None:
        from js import CATBridge  # type: ignore
        await CATBridge.showNotification(title, body, icon or "/icons/icon-192.png")
    
    async def request_notification_permission(self) -> bool:
        from js import CATBridge  # type: ignore
        return await CATBridge.requestNotificationPermission()
    
    # --- Browser/URL ---
    
    async def open_url(self, url: str) -> bool:
        from js import window  # type: ignore
        try:
            window.open(url, "_blank")
            return True
        except Exception:
            return False
    
    # --- Keyboard/Input ---
    
    async def show_keyboard(self) -> None:
        # Handled by browser automatically when input is focused
        pass
    
    async def hide_keyboard(self) -> None:
        from js import document  # type: ignore
        try:
            active = document.activeElement
            if active:
                active.blur()
        except Exception:
            pass
    
    # --- Storage ---
    
    async def get_storage_estimate(self) -> dict:
        from js import CATBridge  # type: ignore
        result = await CATBridge.getStorageEstimate()
        return result.to_py()
    
    async def request_persistent_storage(self) -> bool:
        from js import CATBridge  # type: ignore
        return await CATBridge.requestPersistentStorage()
    
    # --- App Lifecycle ---
    
    async def minimize_app(self) -> None:
        # Not applicable in web
        pass
    
    async def close_app(self) -> None:
        from js import window  # type: ignore
        window.close()
    
    # --- Platform-specific ---
    
    def get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        # In web, env vars come from server config or localStorage
        try:
            from js import localStorage  # type: ignore
            return localStorage.getItem(f"cat_env_{key}") or default
        except Exception:
            return default
    
    def set_env(self, key: str, value: str) -> None:
        try:
            from js import localStorage  # type: ignore
            localStorage.setItem(f"cat_env_{key}", value)
        except Exception:
            pass


# Server-bridge platform for when running via HTTP server (not WASM)
class ServerBridgePlatform(PlatformBase):
    """Platform that bridges to a backend server via WebSocket/HTTP."""
    
    def __init__(self, bridge_url: str = "/api/bridge"):
        self._bridge_url = bridge_url
        self._info = PlatformInfo(
            type=PlatformType.WEB,
            name="FATTY CAT",
            version="0.7.9.0",
            is_mobile=self._detect_mobile(),
            supports_file_system_access=True,  # Via server
            supports_notifications=True,  # Via server push
            supports_background_sync=True,
            user_agent=globals().get("navigator", {}).userAgent if "navigator" in globals() else "",
        )
        self._ws: Optional[Any] = None
        self._pending: Dict[str, asyncio.Future] = {}
        self._msg_id = 0
    
    def _detect_mobile(self) -> bool:
        try:
            from js import navigator  # type: ignore
            return "Mobi" in navigator.userAgent or "Android" in navigator.userAgent
        except Exception:
            return False
    
    @property
    def info(self) -> PlatformInfo:
        return self._info
    
    async def _connect(self):
        if self._ws is None:
            from js import WebSocket  # type: ignore
            self._ws = WebSocket(f"ws://{location.host}{self._bridge_url}/ws")
            
            def on_message(event):
                data = json.loads(event.data)
                msg_id = data.get("id")
                if msg_id in self._pending:
                    fut = self._pending.pop(msg_id)
                    if data.get("error"):
                        fut.set_exception(Exception(data["error"]))
                    else:
                        fut.set_result(data.get("result"))
            
            self._ws.onmessage = on_message
            
            await asyncio.get_event_loop().run_in_executor(None, lambda: None)  # Yield
    
    async def _call(self, method: str, params: dict) -> Any:
        await self._connect()
        self._msg_id += 1
        msg_id = str(self._msg_id)
        fut = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = fut
        
        self._ws.send(json.dumps({"id": msg_id, "method": method, "params": params}))
        return await fut
    
    # --- Filesystem ---
    
    async def get_root_directory(self) -> DirectoryHandle:
        result = await self._call("fs.get_root", {})
        return ServerBridgeDirectoryHandle(self, result["handle_id"], result["path"])
    
    async def pick_directory(self, title: str = "Select folder") -> Optional[DirectoryHandle]:
        result = await self._call("fs.pick_directory", {"title": title})
        if result.get("handle_id"):
            return ServerBridgeDirectoryHandle(self, result["handle_id"], result["path"])
        return None
    
    async def pick_file(self, title: str = "Select file", accept: Optional[dict] = None) -> Optional[FileHandle]:
        result = await self._call("fs.pick_file", {"title": title, "accept": accept})
        if result.get("handle_id"):
            return ServerBridgeFileHandle(self, result["handle_id"], result["path"], writable=False)
        return None
    
    async def resolve_path(self, path: str) -> str:
        result = await self._call("fs.resolve_path", {"path": path})
        return result["path"]
    
    async def path_exists(self, path: str) -> bool:
        result = await self._call("fs.exists", {"path": path})
        return result["exists"]
    
    async def is_directory(self, path: str) -> bool:
        result = await self._call("fs.is_dir", {"path": path})
        return result["is_dir"]
    
    async def is_file(self, path: str) -> bool:
        result = await self._call("fs.is_file", {"path": path})
        return result["is_file"]
    
    async def list_directory(self, path: str) -> List[str]:
        result = await self._call("fs.list_dir", {"path": path})
        return result["entries"]
    
    async def read_file(self, path: str, encoding: Optional[str] = None) -> Union[str, bytes]:
        result = await self._call("fs.read_file", {"path": path, "encoding": encoding})
        if encoding:
            return result["content"]
        return bytes(result["content"])
    
    async def write_file(self, path: str, data: Union[str, bytes], encoding: Optional[str] = None) -> int:
        if isinstance(data, str):
            content = data
        else:
            content = list(data)
        result = await self._call("fs.write_file", {"path": path, "content": content, "encoding": encoding})
        return result["bytes_written"]
    
    async def delete_file(self, path: str) -> None:
        await self._call("fs.delete_file", {"path": path})
    
    async def delete_directory(self, path: str, recursive: bool = False) -> None:
        await self._call("fs.delete_dir", {"path": path, "recursive": recursive})
    
    async def create_directory(self, path: str, parents: bool = True) -> None:
        await self._call("fs.create_dir", {"path": path, "parents": parents})
    
    async def copy_file(self, src: str, dst: str) -> None:
        await self._call("fs.copy_file", {"src": src, "dst": dst})
    
    async def move_file(self, src: str, dst: str) -> None:
        await self._call("fs.move_file", {"src": src, "dst": dst})
    
    async def get_file_size(self, path: str) -> int:
        result = await self._call("fs.file_size", {"path": path})
        return result["size"]
    
    async def get_file_mtime(self, path: str) -> float:
        result = await self._call("fs.file_mtime", {"path": path})
        return result["mtime"]
    
    # --- Process Execution ---
    
    async def run_command(
        self,
        cmd: Union[str, List[str]],
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
        capture_output: bool = True,
        timeout: Optional[float] = None,
    ) -> CommandResult:
        if isinstance(cmd, list):
            cmd_str = " ".join(cmd)
        else:
            cmd_str = cmd
        
        result = await self._call("process.run", {
            "cmd": cmd_str,
            "cwd": cwd,
            "env": env,
            "capture_output": capture_output,
            "timeout": timeout,
        })
        return CommandResult(
            returncode=result["returncode"],
            stdout=result["stdout"],
            stderr=result["stderr"],
            success=result["returncode"] == 0,
        )
    
    async def start_process(
        self,
        cmd: Union[str, List[str]],
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ) -> ProcessHandle:
        if isinstance(cmd, list):
            cmd_str = " ".join(cmd)
        else:
            cmd_str = cmd
        
        result = await self._call("process.start", {"cmd": cmd_str, "cwd": cwd, "env": env})
        return ServerBridgeProcessHandle(self, result["process_id"])
    
    # --- Clipboard ---
    
    async def read_clipboard(self) -> str:
        result = await self._call("clipboard.read", {})
        return result["text"]
    
    async def write_clipboard(self, text: str) -> None:
        await self._call("clipboard.write", {"text": text})
    
    # --- Notifications ---
    
    async def show_notification(self, title: str, body: str, icon: Optional[str] = None) -> None:
        await self._call("notification.show", {"title": title, "body": body, "icon": icon})
    
    async def request_notification_permission(self) -> bool:
        result = await self._call("notification.request_permission", {})
        return result["granted"]
    
    # --- Browser/URL ---
    
    async def open_url(self, url: str) -> bool:
        from js import window  # type: ignore
        try:
            window.open(url, "_blank")
            return True
        except Exception:
            return False
    
    # --- Keyboard/Input ---
    
    async def show_keyboard(self) -> None:
        pass
    
    async def hide_keyboard(self) -> None:
        from js import document  # type: ignore
        try:
            active = document.activeElement
            if active:
                active.blur()
        except Exception:
            pass
    
    # --- Storage ---
    
    async def get_storage_estimate(self) -> dict:
        result = await self._call("storage.estimate", {})
        return result
    
    async def request_persistent_storage(self) -> bool:
        result = await self._call("storage.request_persistent", {})
        return result["granted"]
    
    # --- App Lifecycle ---
    
    async def minimize_app(self) -> None:
        pass
    
    async def close_app(self) -> None:
        from js import window  # type: ignore
        window.close()
    
    # --- Platform-specific ---
    
    def get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        try:
            from js import localStorage  # type: ignore
            return localStorage.getItem(f"cat_env_{key}") or default
        except Exception:
            return default
    
    def set_env(self, key: str, value: str) -> None:
        try:
            from js import localStorage  # type: ignore
            localStorage.setItem(f"cat_env_{key}", value)
        except Exception:
            pass


class ServerBridgeFileHandle(FileHandle):
    def __init__(self, platform: ServerBridgePlatform, handle_id: str, path: str, writable: bool = False):
        self._platform = platform
        self._handle_id = handle_id
        self._path = path
        self._writable = writable
        self._position = 0
        self._closed = False
    
    async def read(self, size: int = -1) -> bytes:
        result = await self._platform._call("fs.read", {"handle_id": self._handle_id, "position": self._position, "size": size})
        data = bytes(result["data"])
        self._position += len(data)
        return data
    
    async def write(self, data: Union[bytes, str]) -> int:
        if not self._writable:
            raise PermissionError("Not writable")
        if isinstance(data, str):
            data = data.encode("utf-8")
        result = await self._platform._call("fs.write", {"handle_id": self._handle_id, "data": list(data), "position": self._position})
        self._position += result["bytes_written"]
        return result["bytes_written"]
    
    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            await self._platform._call("fs.close", {"handle_id": self._handle_id})
    
    async def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self._position = offset
        elif whence == 1:
            self._position += offset
        elif whence == 2:
            result = await self._platform._call("fs.seek_end", {"handle_id": self._handle_id, "offset": offset})
            self._position = result["position"]
        return self._position
    
    def tell(self) -> int:
        return self._position


class ServerBridgeDirectoryHandle(DirectoryHandle):
    def __init__(self, platform: ServerBridgePlatform, handle_id: str, path: str):
        self._platform = platform
        self._handle_id = handle_id
        self._path = path
    
    async def get_file_handle(self, name: str, create: bool = False) -> FileHandle:
        result = await self._platform._call("fs.get_file_handle", {"dir_handle_id": self._handle_id, "name": name, "create": create})
        return ServerBridgeFileHandle(self._platform, result["handle_id"], f"{self._path}/{name}", writable=create)
    
    async def get_directory_handle(self, name: str, create: bool = False) -> DirectoryHandle:
        result = await self._platform._call("fs.get_dir_handle", {"dir_handle_id": self._handle_id, "name": name, "create": create})
        return ServerBridgeDirectoryHandle(self._platform, result["handle_id"], f"{self._path}/{name}")
    
    async def remove_entry(self, name: str, recursive: bool = False) -> None:
        await self._platform._call("fs.remove_entry", {"dir_handle_id": self._handle_id, "name": name, "recursive": recursive})
    
    async def list_entries(self) -> List[str]:
        result = await self._platform._call("fs.list_dir", {"path": self._path})
        return result["entries"]


class ServerBridgeProcessHandle(ProcessHandle):
    def __init__(self, platform: ServerBridgePlatform, process_id: str):
        self._platform = platform
        self._process_id = process_id
        self._returncode: Optional[int] = None
    
    async def wait(self, timeout: Optional[float] = None) -> CommandResult:
        try:
            result = await asyncio.wait_for(
                self._platform._call("process.wait", {"process_id": self._process_id}),
                timeout=timeout,
            )
            self._returncode = result["returncode"]
            return CommandResult(
                returncode=result["returncode"],
                stdout=result["stdout"],
                stderr=result["stderr"],
                success=result["returncode"] == 0,
            )
        except asyncio.TimeoutError:
            await self.kill()
            return CommandResult(returncode=-1, stdout="", stderr="Timeout", success=False)
    
    async def terminate(self) -> None:
        await self._platform._call("process.terminate", {"process_id": self._process_id})
    
    async def kill(self) -> None:
        await self._platform._call("process.kill", {"process_id": self._process_id})
    
    @property
    def pid(self) -> Optional[int]:
        return None
    
    @property
    def returncode(self) -> Optional[int]:
        return self._returncode