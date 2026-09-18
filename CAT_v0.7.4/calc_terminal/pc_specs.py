"""PC capacity detection for Ollama model suggestions."""
import os
import platform
import shutil

def get_specs():
    """Return dict with ram_gb, cpu_count, gpu, os, arch."""
    ram_gb = 8
    try:
        import psutil  # type: ignore
        ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
    except Exception:
        # fallback via ctypes on Windows or via /proc on linux
        try:
            if platform.system() == "Windows":
                import ctypes
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [("dwLength", ctypes.c_ulong),("dwMemoryLoad", ctypes.c_ulong),("ullTotalPhys", ctypes.c_ulonglong),("ullAvailPhys", ctypes.c_ulonglong),("ullTotalPageFile", ctypes.c_ulonglong),("ullAvailPageFile", ctypes.c_ulonglong),("ullTotalVirtual", ctypes.c_ulonglong),("ullAvailVirtual", ctypes.c_ulonglong),("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
                stat = MEMORYSTATUSEX(dwLength=ctypes.sizeof(MEMORYSTATUSEX))
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                ram_gb = round(int(stat.ullTotalPhys) / (1024**3), 1)
        except Exception:
            pass
    cpu = os.cpu_count() or 4
    gpu = "Unknown"
    gpu_vram = 0
    # Try nvidia-smi, torch, or wmic
    try:
        import subprocess as sp
        if shutil.which("nvidia-smi"):
            out = sp.check_output(["nvidia-smi","--query-gpu=name,memory.total","--format=csv,noheader"], timeout=3, text=True)
            if out.strip():
                part = out.splitlines()[0]
                gpu = part.split(",")[0].strip()
                try:
                    vram_str = part.split(",")[1].strip().replace(" MiB","")
                    gpu_vram = round(int(vram_str)/1024,1)
                except Exception:
                    pass
        elif platform.system() == "Windows":
            try:
                out = sp.check_output("wmic path win32_VideoController get name", shell=True, timeout=3, text=True)
                lines = [l.strip() for l in out.splitlines() if l.strip() and "Name" not in l]
                if lines:
                    gpu = lines[0][:40]
            except Exception:
                pass
        # torch fallback
        if gpu == "Unknown":
            try:
                import torch  # type: ignore
                if torch.cuda.is_available():
                    gpu = torch.cuda.get_device_name(0)
                    try:
                        props = torch.cuda.get_device_properties(0)
                        gpu_vram = round(props.total_memory/(1024**3),1)
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass
    disk_free = 0
    try:
        du = shutil.disk_usage(os.path.expanduser("~"))
        disk_free = round(du.free/(1024**3),1)
    except Exception:
        pass
    return {
        "ram_gb": ram_gb,
        "cpu_count": cpu,
        "gpu": gpu,
        "gpu_vram_gb": gpu_vram,
        "disk_free_gb": disk_free,
        "os": platform.system(),
        "arch": platform.machine(),
        "platform": platform.platform(),
    }

def suggested_max_params(specs):
    """Return recommended max model size label and list of suitable models.
    Heuristic: RAM is primary, VRAM bonus if GPU present."""
    ram = specs.get("ram_gb", 8)
    vram = specs.get("gpu_vram_gb", 0)
    effective = max(ram, vram*1.2 if vram else 0)  # GPU gives headroom
    # Map to max params
    if effective >= 48:
        tier = "70B+ (you can run 70B-405B with quantization)"
        max_gb = 80
    elif effective >= 24:
        tier = "32B-34B comfortably, 70B quantized"
        max_gb = 35
    elif effective >= 16:
        tier = "13B-14B comfortably, 20B+ quantized"
        max_gb = 16
    elif effective >= 8:
        tier = "7B-8B comfortably"
        max_gb = 9
    else:
        tier = "1B-3B recommended"
        max_gb = 4
    return tier, max_gb

def is_suitable(model, max_gb):
    try:
        return float(model.get("size_gb", 99)) <= max_gb * 1.1
    except Exception:
        return True

def recommendation_reason(model, specs, max_gb):
    sz = model.get("size_gb", 0)
    ram = specs.get("ram_gb", 8)
    if sz <= max_gb:
        return "✓ Fits your PC"
    else:
        return f"⚠ Needs ~{sz}GB, you have {ram}GB RAM — may be slow / OOM"
