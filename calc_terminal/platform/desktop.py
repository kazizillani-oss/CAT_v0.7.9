"""
Desktop Platform Implementation

Native Python implementation for Windows/Linux/macOS.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, BinaryIO, List, Optional, Union

try:
    import tkinter as tk
    from tkinter import filedialog
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

from . import (
    PlatformBase,
    PlatformInfo,
    PlatformType,
    FileHandle,
    DirectoryHandle,
    CommandResult,
    ProcessHandle,
)


class DesktopFileHandle(FileHandle):
    """File handle for desktop platform."""
    
    def __init__(self, file: BinaryIO, path: str):
        self._file = file
        self._path = path
    
    async def read(self, size: int = -1) -> bytes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._file.read(size))
    
    async def write(self, data: Union[bytes, str]) -> int:
        loop = asyncio.get_event_loop()
        if isinstance(data, str):
            data = data.encode("utf-8")
        return await loop.run_in_executor(None, lambda: self._file.write(data))
    
    async def close(self) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._file.close)
    
    async def seek(self, offset: int, whence: int = 0) -> int:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._file.seek(offset, whence))
    
    def tell(self) -> int:
        return self._file.tell()


class DesktopDirectoryHandle(DirectoryHandle):
    """Directory handle for desktop platform."""
    
    def __init__(self, path: str):
        self._path = Path(path).resolve()
    
    async def get_file_handle(self, name: str, create: bool = False) -> FileHandle:
        path = self._path / name
        mode = "w+b" if create else "r+b"
        if not path.exists() and not create:
            raise FileNotFoundError(f"File not found: {path}")
        file = await asyncio.get_event_loop().run_in_executor(None, lambda: open(path, mode))
        return DesktopFileHandle(file, str(path))
    
    async def get_directory_handle(self, name: str, create: bool = False) -> DirectoryHandle:
        path = self._path / name
        if create:
            await asyncio.get_event_loop().run_in_executor(None, lambda: path.mkdir(parents=True, exist_ok=True))
        elif not path.exists():
            raise FileNotFoundError(f"Directory not found: {path}")
        return DesktopDirectoryHandle(str(path))
    
    async def remove_entry(self, name: str, recursive: bool = False) -> None:
        path = self._path / name
        if path.is_dir():
            if recursive:
                await asyncio.get_event_loop().run_in_executor(None, lambda: shutil.rmtree(path))
            else:
                await asyncio.get_event_loop().run_in_executor(None, lambda: path.rmdir())
        else:
            await asyncio.get_event_loop().run_in_executor(None, lambda: path.unlink())
    
    async def list_entries(self) -> List[str]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: [p.name for p in self._path.iterdir()])


class DesktopProcessHandle(ProcessHandle):
    """Process handle for desktop platform."""
    
    def __init__(self, process: subprocess.Popen):
        self._process = process
    
    async def wait(self, timeout: Optional[float] = None) -> CommandResult:
        loop = asyncio.get_event_loop()
        try:
            returncode = await loop.run_in_executor(
                None, lambda: self._process.wait(timeout=timeout)
            )
            stdout, stderr = await loop.run_in_executor(None, self._process.communicate)
            return CommandResult(
                returncode=returncode,
                stdout=stdout.decode("utf-8", errors="replace") if stdout else "",
                stderr=stderr.decode("utf-8", errors="replace") if stderr else "",
                success=returncode == 0,
            )
        except subprocess.TimeoutExpired:
            return CommandResult(
                returncode=-1,
                stdout="",
                stderr="Process timed out",
                success=False,
            )
    
    async def terminate(self) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._process.terminate)
    
    async def kill(self) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._process.kill)
    
    @property
    def pid(self) -> Optional[int]:
        return self._process.pid
    
    @property
    def returncode(self) -> Optional[int]:
        return self._process.returncode


class DesktopPlatform(PlatformBase):
    """Desktop platform implementation."""
    
    def __init__(self):
        self._info = PlatformInfo(
            type=PlatformType.DESKTOP,
            name="CAT Desktop",
            version="0.7.9.0",
            is_mobile=False,
            supports_file_system_access=True,
            supports_notifications=True,
            supports_background_sync=False,
            user_agent="",
        )
        self._tk_root: Optional[tk.Tk] = None
    
    @property
    def info(self) -> PlatformInfo:
        return self._info
    
    # --- Filesystem ---
    
    async def get_root_directory(self) -> DirectoryHandle:
        # Use current working directory as workspace root
        cwd = os.getcwd()
        return DesktopDirectoryHandle(cwd)
    
    async def pick_directory(self, title: str = "Select folder") -> Optional[DirectoryHandle]:
        if not HAS_TKINTER:
            return None
        
        loop = asyncio.get_event_loop()
        
        def _pick():
            if self._tk_root is None:
                root = tk.Tk()
                root.withdraw()
                self._tk_root = root
            else:
                root = self._tk_root
            
            path = filedialog.askdirectory(title=title, master=root)
            return path if path else None
        
        path = await loop.run_in_executor(None, _pick)
        if path:
            return DesktopDirectoryHandle(path)
        return None
    
    async def pick_file(self, title: str = "Select file", accept: Optional[dict] = None) -> Optional[FileHandle]:
        if not HAS_TKINTER:
            return None
        
        loop = asyncio.get_event_loop()
        
        def _pick():
            if self._tk_root is None:
                root = tk.Tk()
                root.withdraw()
                self._tk_root = root
            else:
                root = self._tk_root
            
            filetypes = []
            if accept:
                for desc, exts in accept.items():
                    filetypes.append((desc, " ".join(f"*{ext}" for ext in exts)))
            filetypes.append(("All files", "*.*"))
            
            path = filedialog.askopenfilename(title=title, filetypes=filetypes, master=root)
            return path if path else None
        
        path = await loop.run_in_executor(None, _pick)
        if path:
            file = await loop.run_in_executor(None, lambda: open(path, "r+b"))
            return DesktopFileHandle(file, path)
        return None
    
    async def resolve_path(self, path: str) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: str(Path(path).expanduser().resolve()))
    
    async def path_exists(self, path: str) -> bool:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: Path(path).exists())
    
    async def is_directory(self, path: str) -> bool:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: Path(path).is_dir())
    
    async def is_file(self, path: str) -> bool:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: Path(path).is_file())
    
    async def list_directory(self, path: str) -> List[str]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: [p.name for p in Path(path).iterdir()])
    
    async def read_file(self, path: str, encoding: Optional[str] = None) -> Union[str, bytes]:
        loop = asyncio.get_event_loop()
        if encoding:
            return await loop.run_in_executor(None, lambda: Path(path).read_text(encoding=encoding))
        return await loop.run_in_executor(None, lambda: Path(path).read_bytes())
    
    async def write_file(self, path: str, data: Union[str, bytes], encoding: Optional[str] = None) -> int:
        loop = asyncio.get_event_loop()
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, str):
            return await loop.run_in_executor(None, lambda: p.write_text(data, encoding=encoding or "utf-8"))
        return await loop.run_in_executor(None, lambda: p.write_bytes(data))
    
    async def delete_file(self, path: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: Path(path).unlink(missing_ok=True))
    
    async def delete_directory(self, path: str, recursive: bool = False) -> None:
        loop = asyncio.get_event_loop()
        if recursive:
            await loop.run_in_executor(None, lambda: shutil.rmtree(path, ignore_errors=True))
        else:
            await loop.run_in_executor(None, lambda: Path(path).rmdir())
    
    async def create_directory(self, path: str, parents: bool = True) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: Path(path).mkdir(parents=parents, exist_ok=True))
    
    async def copy_file(self, src: str, dst: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: shutil.copy2(src, dst))
    
    async def move_file(self, src: str, dst: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: shutil.move(src, dst))
    
    async def get_file_size(self, path: str) -> int:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: Path(path).stat().st_size)
    
    async def get_file_mtime(self, path: str) -> float:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: Path(path).stat().st_mtime)
    
    # --- Process Execution ---
    
    async def run_command(
        self,
        cmd: Union[str, List[str]],
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
        capture_output: bool = True,
        timeout: Optional[float] = None,
    ) -> CommandResult:
        loop = asyncio.get_event_loop()
        
        def _run():
            if isinstance(cmd, str):
                shell = True
                cmd_str = cmd
            else:
                shell = False
                cmd_str = cmd
            
            merged_env = os.environ.copy()
            if env:
                merged_env.update(env)
            
            proc = subprocess.Popen(
                cmd_str,
                shell=shell,
                cwd=cwd,
                env=merged_env,
                stdout=subprocess.PIPE if capture_output else None,
                stderr=subprocess.PIPE if capture_output else None,
                stdin=subprocess.DEVNULL,
            )
            
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
                return CommandResult(
                    returncode=proc.returncode,
                    stdout=stdout.decode("utf-8", errors="replace") if stdout else "",
                    stderr=stderr.decode("utf-8", errors="replace") if stderr else "",
                    success=proc.returncode == 0,
                )
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                return CommandResult(
                    returncode=-1,
                    stdout=stdout.decode("utf-8", errors="replace") if stdout else "",
                    stderr=stderr.decode("utf-8", errors="replace") if stderr else "",
                    success=False,
                )
        
        return await loop.run_in_executor(None, _run)
    
    async def start_process(
        self,
        cmd: Union[str, List[str]],
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ) -> ProcessHandle:
        loop = asyncio.get_event_loop()
        
        def _start():
            if isinstance(cmd, str):
                shell = True
                cmd_str = cmd
            else:
                shell = False
                cmd_str = cmd
            
            merged_env = os.environ.copy()
            if env:
                merged_env.update(env)
            
            proc = subprocess.Popen(
                cmd_str,
                shell=shell,
                cwd=cwd,
                env=merged_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
            )
            return proc
        
        proc = await loop.run_in_executor(None, _start)
        return DesktopProcessHandle(proc)
    
    # --- Clipboard ---
    
    async def read_clipboard(self) -> str:
        if not HAS_TKINTER:
            return ""
        
        loop = asyncio.get_event_loop()
        
        def _read():
            if self._tk_root is None:
                root = tk.Tk()
                root.withdraw()
                self._tk_root = root
            else:
                root = self._tk_root
            
            try:
                return root.clipboard_get()
            except tk.TclError:
                return ""
        
        return await loop.run_in_executor(None, _read)
    
    async def write_clipboard(self, text: str) -> None:
        if not HAS_TKINTER:
            return
        
        loop = asyncio.get_event_loop()
        
        def _write():
            if self._tk_root is None:
                root = tk.Tk()
                root.withdraw()
                self._tk_root = root
            else:
                root = self._tk_root
            
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
        
        await loop.run_in_executor(None, _write)
    
    # --- Notifications ---
    
    async def show_notification(self, title: str, body: str, icon: Optional[str] = None) -> None:
        # Use plyer or platform-specific notification
        try:
            from plyer import notification
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: notification.notify(
                title=title,
                message=body,
                app_name="CAT",
                timeout=5,
            ))
        except ImportError:
            # Fallback: print to console
            print(f"[NOTIFICATION] {title}: {body}")
    
    async def request_notification_permission(self) -> bool:
        # On desktop, notifications usually work without explicit permission
        return True
    
    # --- Browser/URL ---
    
    async def open_url(self, url: str) -> bool:
        import webbrowser
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, lambda: webbrowser.open(url))
        except Exception:
            return False
    
    # --- Keyboard/Input ---
    
    async def show_keyboard(self) -> None:
        # No-op on desktop
        pass
    
    async def hide_keyboard(self) -> None:
        # No-op on desktop
        pass
    
    # --- Storage ---
    
    async def get_storage_estimate(self) -> dict:
        import shutil
        total, used, free = shutil.disk_usage(os.getcwd())
        return {
            "quota": total,
            "usage": used,
            "available": free,
        }
    
    async def request_persistent_storage(self) -> bool:
        # Always persistent on desktop
        return True
    
    # --- App Lifecycle ---
    
    async def minimize_app(self) -> None:
        # Not easily done cross-platform, no-op
        pass
    
    async def close_app(self) -> None:
        sys.exit(0)
    
    # --- Platform-specific ---
    
    def get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return os.environ.get(key, default)
    
    def set_env(self, key: str, value: str) -> None:
        os.environ[key] = value