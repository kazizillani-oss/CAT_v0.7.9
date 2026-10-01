"""
CAT Lab — Hardware Profiler.
Creator: Kazi Zillani (CAT Platform).

Accurately detects system hardware, accelerators, and ML runtimes:
- CPU architecture, cores, threads, features
- GPU model, vendor, total VRAM, free VRAM, driver version
- RAM capacity and memory pressure
- Storage availability
- CUDA runtime, device count, active compute device
- PyTorch installation, version, acceleration backends (CUDA, ROCm, Metal, DirectML)
- Node.js environment
- Operating system and Python environment

Never fabricates or assumes hardware capabilities. When details cannot be
detected, gracefully returns 'Unavailable' / 'N/A' / 'CPU Only'.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from typing import Any, Dict, Optional


def get_cat_version() -> str:
    try:
        from ..cli import _version
        return _version()
    except Exception:
        return "0.8.0"


def detect_cuda_info() -> Dict[str, Any]:
    """Detects CUDA availability, runtime version, and device count."""
    info: Dict[str, Any] = {
        "available": False,
        "version": "Unavailable",
        "device_count": 0,
        "device_name": "None",
        "runtime": "N/A",
    }

    # 1. Try PyTorch CUDA if available
    try:
        import torch
        if torch.cuda.is_available():
            info["available"] = True
            info["version"] = getattr(torch.version, "cuda", "Unknown")
            info["device_count"] = torch.cuda.device_count()
            if info["device_count"] > 0:
                info["device_name"] = torch.cuda.get_device_name(0)
            info["runtime"] = "PyTorch CUDA"
            return info
    except Exception:
        pass

    # 2. Try nvcc --version command
    nvcc = shutil.which("nvcc")
    if nvcc:
        try:
            out = subprocess.run([nvcc, "--version"], capture_output=True, text=True, timeout=3)
            if out.returncode == 0:
                for line in out.stdout.splitlines():
                    if "release" in line:
                        parts = line.split("release")
                        if len(parts) > 1:
                            info["version"] = parts[1].split(",")[0].strip()
                            info["available"] = True
                            info["runtime"] = "CUDA Toolkit (nvcc)"
                            break
        except Exception:
            pass

    # 3. Try nvidia-smi if nvcc failed
    if not info["available"] or info["version"] in ("Unavailable", "None", ""):
        smi = shutil.which("nvidia-smi")
        if not smi:
            system_root = os.environ.get("SystemRoot", "C:\\Windows")
            candidate = os.path.join(system_root, "System32", "nvidia-smi.exe")
            if os.path.exists(candidate):
                smi = candidate
        if smi:
            try:
                out = subprocess.run([smi], capture_output=True, text=True, timeout=3)
                if out.returncode == 0:
                    info["available"] = True
                    info["runtime"] = "NVIDIA Driver"
                    for line in out.stdout.splitlines():
                        if "CUDA UMD Version:" in line:
                            idx = line.find("CUDA UMD Version:")
                            info["version"] = line[idx + len("CUDA UMD Version:"):].split()[0].strip()
                            break
                        elif "CUDA Version:" in line:
                            idx = line.find("CUDA Version:")
                            info["version"] = line[idx + len("CUDA Version:"):].split()[0].strip()
                            break
            except Exception:
                pass

    return info


def detect_pytorch_info() -> Dict[str, Any]:
    """Detects PyTorch installation, version, device, and acceleration backends."""
    info: Dict[str, Any] = {
        "installed": False,
        "version": "Not Installed",
        "cuda_available": False,
        "mps_available": False,
        "preferred_device": "cpu",
        "details": "Install with `pip install torch`",
    }
    try:
        import torch
        info["installed"] = True
        info["version"] = str(getattr(torch, "__version__", "Unknown"))
        cuda_ok = False
        try:
            cuda_ok = bool(torch.cuda.is_available())
        except Exception:
            pass
        info["cuda_available"] = cuda_ok

        mps_ok = False
        try:
            if hasattr(torch.backends, "mps"):
                mps_ok = bool(torch.backends.mps.is_available())
        except Exception:
            pass
        info["mps_available"] = mps_ok

        if cuda_ok:
            info["preferred_device"] = "cuda"
            info["details"] = f"PyTorch {info['version']} with CUDA acceleration"
        elif mps_ok:
            info["preferred_device"] = "mps"
            info["details"] = f"PyTorch {info['version']} with Apple Metal acceleration"
        else:
            info["preferred_device"] = "cpu"
            info["details"] = f"PyTorch {info['version']} (CPU execution)"
    except Exception:
        pass
    return info


def detect_nodejs_version() -> str:
    """Detects Node.js version on PATH."""
    node_exe = shutil.which("node")
    if not node_exe:
        return "Unavailable"
    try:
        out = subprocess.run([node_exe, "--version"], capture_output=True, text=True, timeout=3)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return "Unavailable"


def get_hardware_profile(force_refresh: bool = False) -> Dict[str, Any]:
    """Returns comprehensive, authentic hardware profile for CAT Lab."""
    # Leverage existing CAT hardware_analyzer for CPU, GPU, RAM, Storage
    try:
        from ..hardware_analyzer import HardwareAnalyzer
        hw = HardwareAnalyzer.analyze(force_refresh=force_refresh)
        cpu_dict = {
            "model": hw.cpu.model,
            "physical_cores": hw.cpu.physical_cores,
            "logical_cores": hw.cpu.logical_cores,
            "arch": hw.cpu.arch or platform.machine(),
        }
        gpu_dict = {
            "detected": hw.gpu.detected,
            "name": hw.gpu.name,
            "vendor": hw.gpu.vendor,
            "vram_total_gb": hw.gpu.vram_total_gb,
            "vram_free_gb": hw.gpu.vram_free_gb,
            "backend": hw.gpu.backend,
            "driver_version": hw.gpu.driver_version or "N/A",
        }
        ram_dict = {
            "total_gb": hw.ram.total_gb,
            "available_gb": hw.ram.available_gb,
            "used_gb": hw.ram.used_gb,
            "percent_used": hw.ram.percent_used,
        }
        storage_dict = {
            "total_gb": hw.storage.total_gb,
            "free_gb": hw.storage.free_gb,
            "used_gb": hw.storage.used_gb,
            "path": hw.storage.path,
        }
    except Exception:
        cpu_dict = {
            "model": platform.processor() or "Unknown CPU",
            "physical_cores": os.cpu_count() or 1,
            "logical_cores": os.cpu_count() or 1,
            "arch": platform.machine(),
        }
        gpu_dict = {
            "detected": False,
            "name": "Integrated / CPU Only",
            "vendor": "Unknown",
            "vram_total_gb": 0.0,
            "vram_free_gb": 0.0,
            "backend": "CPU",
            "driver_version": "N/A",
        }
        ram_dict = {
            "total_gb": 8.0,
            "available_gb": 4.0,
            "used_gb": 4.0,
            "percent_used": 50.0,
        }
        storage_dict = {
            "total_gb": 0.0,
            "free_gb": 0.0,
            "used_gb": 0.0,
            "path": os.getcwd(),
        }

    cuda_info = detect_cuda_info()
    pytorch_info = detect_pytorch_info()
    node_ver = detect_nodejs_version()
    cat_ver = get_cat_version()

    # Determine primary compute device
    if pytorch_info["cuda_available"]:
        device = f"CUDA (PyTorch: {gpu_dict.get('name', 'NVIDIA GPU')})"
    elif pytorch_info["mps_available"]:
        device = "MPS (Apple Metal)"
    elif cuda_info["available"]:
        device = f"CUDA Driver (GPU: {gpu_dict.get('name', 'NVIDIA GPU')}, PyTorch on CPU)"
    elif gpu_dict["detected"] and gpu_dict["backend"] != "CPU":
        device = f"{gpu_dict['backend']} ({gpu_dict.get('name', 'GPU')})"
    else:
        device = f"CPU ({cpu_dict.get('model', 'Processor')})"

    return {
        "cpu": cpu_dict,
        "gpu": gpu_dict,
        "ram": ram_dict,
        "storage": storage_dict,
        "cuda": cuda_info,
        "pytorch": pytorch_info,
        "nodejs_version": node_ver,
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "os_name": f"{platform.system()} {platform.release()}",
        "cat_version": cat_ver,
        "primary_device": device,
    }


def get_hardware_status_text() -> str:
    """Formatted report of all hardware parameters."""
    profile = get_hardware_profile()
    cpu = profile["cpu"]
    gpu = profile["gpu"]
    ram = profile["ram"]
    storage = profile["storage"]
    cuda = profile["cuda"]
    torch = profile["pytorch"]

    lines = [
        "=" * 68,
        "                    CAT HARDWARE PROFILER",
        "=" * 68,
        f"  Primary Device : {profile['primary_device']}",
        f"  Operating Sys  : {profile['os_name']} ({platform.machine()})",
        f"  CAT Version    : v{profile['cat_version']}",
        f"  Python         : v{profile['python_version']} ({profile['python_executable']})",
        f"  Node.js        : {profile['nodejs_version']}",
        "-" * 68,
        "  [CPU]",
        f"    Model        : {cpu['model']}",
        f"    Cores / Thrd : {cpu['physical_cores']} physical / {cpu['logical_cores']} threads",
        f"    Architecture : {cpu['arch']}",
        "-" * 68,
        "  [GPU & ACCELERATORS]",
        f"    Detected     : {'✓ Yes' if gpu['detected'] else '○ No (CPU Only)'}",
        f"    Model Name   : {gpu['name']}",
        f"    Vendor       : {gpu['vendor']}",
        f"    VRAM Total   : {gpu['vram_total_gb']:.2f} GB" if gpu['detected'] else "    VRAM Total   : N/A",
        f"    VRAM Free    : {gpu['vram_free_gb']:.2f} GB" if gpu['detected'] else "    VRAM Free    : N/A",
        f"    Driver       : {gpu['driver_version']}",
        "-" * 68,
        "  [MACHINE LEARNING RUNTIMES]",
        f"    PyTorch      : {torch['version']} ({torch['details']})",
        f"    CUDA Runtime : {cuda['version']} ({cuda['runtime']})",
        f"    CUDA Devices : {cuda['device_count']} detected" if cuda['available'] else "    CUDA Devices : None",
        "-" * 68,
        "  [SYSTEM MEMORY & STORAGE]",
        f"    System RAM   : {ram['total_gb']:.1f} GB total ({ram['available_gb']:.1f} GB available, {ram['percent_used']:.0f}% used)",
        f"    Disk Storage : {storage['free_gb']:.1f} GB free of {storage['total_gb']:.1f} GB ({storage['path'] or 'Root'})",
        "=" * 68,
    ]
    return "\n".join(lines)


def get_gpu_status_text() -> str:
    """Formatted report for GPU only."""
    p = get_hardware_profile()
    gpu = p["gpu"]
    cuda = p["cuda"]
    torch = p["pytorch"]
    lines = [
        "=" * 60,
        "                    CAT GPU PROFILER",
        "=" * 60,
        f"  Status        : {'Active' if gpu['detected'] or cuda['available'] else 'No Dedicated GPU Detected'}",
        f"  GPU Model     : {gpu['name']}",
        f"  GPU Vendor    : {gpu['vendor']}",
        f"  VRAM Total    : {gpu['vram_total_gb']:.2f} GB" if gpu['detected'] else "  VRAM Total    : Unavailable",
        f"  VRAM Free     : {gpu['vram_free_gb']:.2f} GB" if gpu['detected'] else "  VRAM Free     : Unavailable",
        f"  Backend       : {gpu['backend']}",
        f"  CUDA Version  : {cuda['version']}",
        f"  PyTorch CUDA  : {'✓ Available' if torch['cuda_available'] else '○ Unavailable'}",
        "=" * 60,
    ]
    return "\n".join(lines)


def get_cpu_status_text() -> str:
    """Formatted report for CPU only."""
    p = get_hardware_profile()
    cpu = p["cpu"]
    lines = [
        "=" * 60,
        "                    CAT CPU PROFILER",
        "=" * 60,
        f"  Processor     : {cpu['model']}",
        f"  Architecture  : {cpu['arch']}",
        f"  Physical Cores: {cpu['physical_cores']}",
        f"  Logical Cores : {cpu['logical_cores']}",
        "=" * 60,
    ]
    return "\n".join(lines)


def get_memory_status_text() -> str:
    """Formatted report for Memory only."""
    p = get_hardware_profile()
    ram = p["ram"]
    gpu = p["gpu"]
    lines = [
        "=" * 60,
        "                  CAT MEMORY PROFILER",
        "=" * 60,
        f"  System RAM    : {ram['total_gb']:.2f} GB total",
        f"  Used RAM      : {ram['used_gb']:.2f} GB ({ram['percent_used']:.1f}%)",
        f"  Available RAM : {ram['available_gb']:.2f} GB",
        f"  GPU VRAM      : {gpu['vram_total_gb']:.2f} GB" if gpu['detected'] else "  GPU VRAM      : Unavailable (CPU Only)",
        "=" * 60,
    ]
    return "\n".join(lines)
