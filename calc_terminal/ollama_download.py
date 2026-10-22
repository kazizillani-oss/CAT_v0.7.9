"""Background Ollama download manager with progress streaming.
Uses Ollama's POST /api/pull streaming JSON lines.
"""
import json
import time
import threading
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, Tuple

def ollama_base_url():
    try:
        from . import config as _cfg
        return _cfg.load_config().ollama_endpoint.rstrip("/")
    except Exception:
        return "http://localhost:11434"

def is_ollama_installed():
    import shutil
    return bool(shutil.which("ollama"))

def is_ollama_running(base_url=None, timeout=3):
    import urllib.request
    base = (base_url or ollama_base_url()).rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=timeout) as r:
            return r.status in (200, 204)
    except Exception:
        return False

def ensure_ollama_running(base_url=None, timeout=12, auto_start=True):
    """Ensure Ollama is reachable; if not and auto_start, try `ollama serve`."""
    if is_ollama_running(base_url, timeout=3):
        return True, "already running"
    if not auto_start:
        return False, "not running"
    if not is_ollama_installed():
        return False, "Ollama not installed — get it from https://ollama.com/download"
    # Try to start ollama serve as background process
    try:
        import subprocess, shutil, sys, os
        ollama_bin = shutil.which("ollama")
        if not ollama_bin:
            return False, "ollama binary not found"
        # Use CREATE_NO_WINDOW on Windows to avoid popup
        kwargs = {}
        if sys.platform == "win32":
            try:
                import subprocess as sp
                kwargs["creationflags"] = getattr(sp, "CREATE_NO_WINDOW", 0)
                si = sp.STARTUPINFO()
                si.dwFlags |= sp.STARTF_USESHOWWINDOW
                kwargs["startupinfo"] = si
            except Exception:
                pass
        else:
            kwargs["start_new_session"] = True
        # Start serve detached
        try:
            subprocess.Popen([ollama_bin, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
        except Exception as e:
            return False, f"failed to start: {e}"
        # Wait for it to be reachable
        import time
        for _ in range(timeout):
            time.sleep(1)
            if is_ollama_running(base_url, timeout=2):
                return True, "started"
        return False, "started but not reachable yet — wait a moment and retry"
    except Exception as e:
        return False, str(e)

def installed_models(base_url=None):
    """Return set of installed model names via /api/tags."""
    base = (base_url or ollama_base_url()).rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
            return {m.get("name","") for m in data.get("models",[]) if m.get("name")}
    except Exception:
        return set()

def pull_model(model_name, on_progress=None, on_done=None, base_url=None):
    """
    Background pull. Calls on_progress dict with keys:
      status, completed, total, percent, speed, eta_seconds
    Streaming is done on a daemon thread.
    Returns thread.
    """
    base = (base_url or ollama_base_url()).rstrip("/")
    url = f"{base}/api/pull"

    def _worker():
        payload = json.dumps({"name": model_name, "stream": True}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type","application/json")
        start = time.time()
        last_completed = 0
        last_time = start
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                # Ollama streams JSON lines: {"status":"pulling manifest", "completed":..., "total":...}
                buf = b""
                for chunk in iter(lambda: resp.read(8192), b""):
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n",1)
                        line=line.strip()
                        if not line:
                            continue
                        try:
                            js = json.loads(line.decode("utf-8"))
                        except Exception:
                            continue
                        status = js.get("status","")
                        completed = js.get("completed")
                        total = js.get("total")
                        percent = None
                        if isinstance(completed,int) and isinstance(total,int) and total>0:
                            percent = int(completed*100/total)
                        # speed / eta
                        now = time.time()
                        dt = now - last_time
                        speed = None
                        eta = None
                        if isinstance(completed,int) and dt>0.5:
                            delta = completed - last_completed
                            if delta>0:
                                speed = delta/dt  # bytes/s
                                if isinstance(total,int) and total>completed and speed>0:
                                    eta = int((total - completed)/speed)
                            last_completed = completed if isinstance(completed,int) else last_completed
                            last_time = now
                        prog = {"status": status, "completed": completed, "total": total, "percent": percent, "speed": speed, "eta": eta, "raw": js}
                        if on_progress:
                            try:
                                on_progress(prog)
                            except Exception:
                                pass
                        if status and "success" in status.lower():
                            break
                if on_done:
                    try:
                        on_done(True, None)
                    except Exception:
                        pass
        except urllib.error.HTTPError as e:
            msg = f"HTTP {e.code}"
            try:
                body = e.read().decode("utf-8")
                j = json.loads(body)
                msg = j.get("error", msg)
            except Exception:
                pass
            if on_done:
                try:
                    on_done(False, msg)
                except Exception:
                    pass
        except Exception as e:
            if on_done:
                try:
                    on_done(False, str(e))
                except Exception:
                    pass

    th = threading.Thread(target=_worker, daemon=True, name=f"ollama-pull-{model_name}")
    th.start()
    return th

def estimate_minutes(size_gb, speed_mbps=50):
    """Very rough estimate: size_gb at speed_mbps megabits."""
    try:
        # speed in MB/s
        mbps = speed_mbps # megabits
        mbytes = float(size_gb)*1024
        # assume 50 Mbps ~ 6.25 MB/s
        secs = mbytes / (mbps/8) if mbps>0 else 0
        return max(1, int(secs/60))
    except Exception:
        return 5

def pull_model_sync(model_name, base_url=None):
    """Blocking pull for CLI, returns (ok, msg)."""
    done = {}
    def _done(ok, msg):
        done["ok"]=ok
        done["msg"]=msg
    th = pull_model(model_name, base_url=base_url, on_done=lambda ok,msg: done.update(ok=ok,msg=msg))
    th.join(timeout=600)
    return done.get("ok", False), done.get("msg")


def delete_model(model_name: str, base_url=None) -> tuple[bool, Optional[str]]:
    """Delete a model locally via Ollama DELETE /api/delete."""
    base = (base_url or ollama_base_url()).rstrip("/")
    url = f"{base}/api/delete"
    payload = json.dumps({"name": model_name}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="DELETE")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (200, 204):
                return True, None
            return False, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        msg = f"HTTP {e.code}"
        try:
            body = e.read().decode("utf-8")
            j = json.loads(body)
            msg = j.get("error", msg)
        except Exception:
            pass
        return False, msg
    except Exception as e:
        return False, str(e)


def inspect_model(model_name: str, base_url=None) -> Optional[dict]:
    """Retrieve detailed model metadata via Ollama POST /api/show."""
    base = (base_url or ollama_base_url()).rstrip("/")
    url = f"{base}/api/show"
    payload = json.dumps({"name": model_name}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

