"""
calc_terminal/hardware_analyzer.py
==================================
CAT Hardware Analyzer — Comprehensive cross-platform device capability detection.

Part of CAT (Created by Kazi Zillani).
Detects:
  - CPU: Model, physical cores, logical threads, architecture.
  - System RAM: Total, available, used, percent.
  - GPU: Model name, total VRAM, free VRAM, vendor, compute platform (CUDA, ROCm, Metal, DirectML, CPU).
  - Storage: Available disk capacity on the user's primary/models storage drive.
  - Platform / OS / Python environment.
  - Local AI Capability Rating: EXCELLENT / GOOD / MODERATE / LIMITED.

Designed to be lightweight, fail-safe (never raises unhandled exceptions), and
runs with standard library fallbacks if third-party modules are unavailable.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass
class CPUInfo:
    model: str = "Unknown CPU"
    physical_cores: int = 1
    logical_cores: int = 1
    arch: str = ""
    features: list[str] = field(default_factory=list)


@dataclass
class RAMInfo:
    total_gb: float = 8.0
    available_gb: float = 4.0
    used_gb: float = 4.0
    percent_used: float = 50.0


@dataclass
class GPUInfo:
    detected: bool = False
    name: str = "Integrated / CPU Only"
    vendor: str = "Unknown"  # NVIDIA, AMD, Apple, Intel, Unknown
    vram_total_gb: float = 0.0
    vram_free_gb: float = 0.0
    backend: str = "CPU"     # CUDA, ROCm, Metal, DirectML, CPU
    driver_version: str = ""


@dataclass
class StorageInfo:
    total_gb: float = 0.0
    free_gb: float = 0.0
    used_gb: float = 0.0
    path: str = ""


@dataclass
class HardwareProfile:
    cpu: CPUInfo = field(default_factory=CPUInfo)
    ram: RAMInfo = field(default_factory=RAMInfo)
    gpu: GPUInfo = field(default_factory=GPUInfo)
    storage: StorageInfo = field(default_factory=StorageInfo)
    os_name: str = ""
    os_version: str = ""
    python_version: str = ""
    ai_capability: str = "MODERATE"  # EXCELLENT, GOOD, MODERATE, LIMITED
    ai_capability_notes: list[str] = field(default_factory=list)

    @property
    def cpu_model(self) -> str:
        return self.cpu.model

    @property
    def cpu_threads(self) -> int:
        return self.cpu.logical_cores

    @property
    def ram_total_gb(self) -> float:
        return self.ram.total_gb

    @property
    def ram_available_gb(self) -> float:
        return self.ram.available_gb

    @property
    def has_gpu(self) -> bool:
        return self.gpu.detected

    @property
    def gpu_name(self) -> str:
        return self.gpu.name

    @property
    def vram_gb(self) -> float:
        return self.gpu.vram_total_gb

    @property
    def gpu_backend(self) -> str:
        return self.gpu.backend

    @property
    def local_ai_tier(self):
        class _Tier:
            def __init__(self, val):
                self.value = val
            def __str__(self):
                return self.value
        return _Tier(self.ai_capability)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu": {
                "model": self.cpu.model,
                "physical_cores": self.cpu.physical_cores,
                "logical_cores": self.cpu.logical_cores,
                "arch": self.cpu.arch,
            },
            "ram": {
                "total_gb": self.ram.total_gb,
                "available_gb": self.ram.available_gb,
                "used_gb": self.ram.used_gb,
                "percent_used": self.ram.percent_used,
            },
            "gpu": {
                "detected": self.gpu.detected,
                "name": self.gpu.name,
                "vendor": self.gpu.vendor,
                "vram_total_gb": self.gpu.vram_total_gb,
                "vram_free_gb": self.gpu.vram_free_gb,
                "backend": self.gpu.backend,
                "driver_version": self.gpu.driver_version,
            },
            "storage": {
                "total_gb": self.storage.total_gb,
                "free_gb": self.storage.free_gb,
                "used_gb": self.storage.used_gb,
                "path": self.storage.path,
            },
            "os_name": self.os_name,
            "os_version": self.os_version,
            "python_version": self.python_version,
            "ai_capability": self.ai_capability,
            "ai_capability_notes": self.ai_capability_notes,
        }


class HardwareAnalyzer:
    """Analyzes the local environment and grades local inference capability."""

    _cached_profile: Optional[HardwareProfile] = None

    @classmethod
    def analyze(cls, force_refresh: bool = False) -> HardwareProfile:
        """Run full hardware analysis, returning a structured HardwareProfile."""
        if cls._cached_profile is not None and not force_refresh:
            return cls._cached_profile

        cpu_info = cls._detect_cpu()
        ram_info = cls._detect_ram()
        gpu_info = cls._detect_gpu()
        storage_info = cls._detect_storage()
        os_name = platform.system()
        os_version = platform.platform()
        python_ver = platform.python_version()

        capability, notes = cls._evaluate_capability(ram_info, gpu_info, cpu_info)

        profile = HardwareProfile(
            cpu=cpu_info,
            ram=ram_info,
            gpu=gpu_info,
            storage=storage_info,
            os_name=os_name,
            os_version=os_version,
            python_version=python_ver,
            ai_capability=capability,
            ai_capability_notes=notes,
        )

        cls._cached_profile = profile
        return profile

    @classmethod
    def detect(cls, force_refresh: bool = False) -> HardwareProfile:
        return cls.analyze(force_refresh=force_refresh)

    @classmethod
    def _detect_cpu(cls) -> CPUInfo:
        model = "Unknown CPU"
        logical = os.cpu_count() or 4
        physical = logical
        arch = platform.machine() or "x86_64"

        # Try psutil for physical cores
        try:
            import psutil
            p = psutil.cpu_count(logical=False)
            if p:
                physical = p
            l = psutil.cpu_count(logical=True)
            if l:
                logical = l
        except Exception:
            pass

        # Try OS specific name lookups
        try:
            if sys.platform == "win32":
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                if val and str(val).strip():
                    model = str(val).strip()
            elif sys.platform == "darwin":
                out = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True, timeout=2)
                if out.strip():
                    model = out.strip()
            elif sys.platform.startswith("linux"):
                with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if "model name" in line:
                            model = line.split(":", 1)[1].strip()
                            break
        except Exception:
            pass

        if model == "Unknown CPU":
            model = f"{arch} Processor ({logical} threads)"

        return CPUInfo(model=model, physical_cores=physical, logical_cores=logical, arch=arch)

    @classmethod
    def _detect_ram(cls) -> RAMInfo:
        total_gb = 8.0
        avail_gb = 4.0
        used_gb = 4.0
        percent = 50.0

        try:
            import psutil
            vm = psutil.virtual_memory()
            total_gb = round(vm.total / (1024**3), 1)
            avail_gb = round(vm.available / (1024**3), 1)
            used_gb = round(vm.used / (1024**3), 1)
            percent = round(vm.percent, 1)
            return RAMInfo(total_gb=total_gb, available_gb=avail_gb, used_gb=used_gb, percent_used=percent)
        except Exception:
            pass

        # Windows ctypes fallback
        if sys.platform == "win32":
            try:
                import ctypes
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]
                stat = MEMORYSTATUSEX(dwLength=ctypes.sizeof(MEMORYSTATUSEX))
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    total_gb = round(stat.ullTotalPhys / (1024**3), 1)
                    avail_gb = round(stat.ullAvailPhys / (1024**3), 1)
                    used_gb = round((stat.ullTotalPhys - stat.ullAvailPhys) / (1024**3), 1)
                    percent = float(stat.dwMemoryLoad)
            except Exception:
                pass

        return RAMInfo(total_gb=total_gb, available_gb=avail_gb, used_gb=used_gb, percent_used=percent)

    @classmethod
    def _detect_gpu(cls) -> GPUInfo:
        # 1. Check NVIDIA via nvidia-smi
        if shutil.which("nvidia-smi"):
            try:
                cmd = ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv,noheader"]
                out = subprocess.check_output(cmd, timeout=3, text=True)
                lines = [l.strip() for l in out.splitlines() if l.strip()]
                if lines:
                    parts = [p.strip() for p in lines[0].split(",")]
                    name = parts[0]
                    vram_total = 0.0
                    vram_free = 0.0
                    driver = ""
                    if len(parts) > 1:
                        try:
                            vram_total = round(float(parts[1].replace("MiB", "").strip()) / 1024, 1)
                        except Exception:
                            pass
                    if len(parts) > 2:
                        try:
                            vram_free = round(float(parts[2].replace("MiB", "").strip()) / 1024, 1)
                        except Exception:
                            pass
                    if len(parts) > 3:
                        driver = parts[3]
                    return GPUInfo(
                        detected=True,
                        name=name,
                        vendor="NVIDIA",
                        vram_total_gb=vram_total,
                        vram_free_gb=vram_free,
                        backend="CUDA",
                        driver_version=driver,
                    )
            except Exception:
                pass

        # 2. Check Apple Silicon via sysctl
        if sys.platform == "darwin":
            try:
                out = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True, timeout=2)
                if "Apple" in out:
                    # Apple unified memory shares system RAM
                    import psutil
                    total_ram = round(psutil.virtual_memory().total / (1024**3), 1)
                    return GPUInfo(
                        detected=True,
                        name=out.strip() + " GPU (Unified)",
                        vendor="Apple",
                        vram_total_gb=total_ram,
                        vram_free_gb=round(total_ram * 0.7, 1),
                        backend="Metal",
                        driver_version="Metal 3",
                    )
            except Exception:
                pass

        # 3. Check AMD ROCm / Linux
        if shutil.which("rocm-smi"):
            try:
                out = subprocess.check_output(["rocm-smi", "--showmeminfo", "vram"], text=True, timeout=3)
                return GPUInfo(detected=True, name="AMD Radeon (ROCm)", vendor="AMD", backend="ROCm")
            except Exception:
                pass

        # 4. Windows WMIC / DirectX VideoController fallback
        if sys.platform == "win32":
            try:
                out = subprocess.check_output("wmic path win32_VideoController get name,adapterram", shell=True, timeout=3, text=True)
                lines = [l.strip() for l in out.splitlines() if l.strip() and "Name" not in l and "AdapterRAM" not in l]
                for line in lines:
                    parts = line.split()
                    if parts:
                        name = " ".join(parts[:-1]) if len(parts) > 1 else parts[0]
                        vram_bytes = parts[-1] if len(parts) > 1 and parts[-1].isdigit() else "0"
                        vram_gb = round(int(vram_bytes) / (1024**3), 1) if vram_bytes.isdigit() else 0.0
                        vendor = "NVIDIA" if "NVIDIA" in name.upper() else ("AMD" if "AMD" in name.upper() or "RADEON" in name.upper() else ("Intel" if "INTEL" in name.upper() else "Unknown"))
                        backend = "CUDA" if vendor == "NVIDIA" else "DirectML"
                        if vram_gb > 0.5 or "GeForce" in name or "Radeon" in name or "RTX" in name:
                            return GPUInfo(
                                detected=True,
                                name=name[:40],
                                vendor=vendor,
                                vram_total_gb=vram_gb,
                                vram_free_gb=vram_gb,
                                backend=backend,
                            )
            except Exception:
                pass

        return GPUInfo()

    @classmethod
    def _detect_storage(cls) -> StorageInfo:
        path = os.path.expanduser("~")
        total_gb = 0.0
        free_gb = 0.0
        used_gb = 0.0
        try:
            du = shutil.disk_usage(path)
            total_gb = round(du.total / (1024**3), 1)
            free_gb = round(du.free / (1024**3), 1)
            used_gb = round(du.used / (1024**3), 1)
        except Exception:
            pass
        return StorageInfo(total_gb=total_gb, free_gb=free_gb, used_gb=used_gb, path=path)

    @classmethod
    def _evaluate_capability(cls, ram: RAMInfo, gpu: GPUInfo, cpu: CPUInfo) -> Tuple[str, list[str]]:
        notes = []
        effective_vram = gpu.vram_total_gb if gpu.detected else 0.0
        total_ram = ram.total_gb

        # High-end GPU or high unified memory
        if (gpu.detected and effective_vram >= 12.0) or (gpu.backend == "Metal" and total_ram >= 32.0):
            capability = "EXCELLENT"
            notes.append(f"High-speed {gpu.backend} acceleration with {effective_vram}GB memory.")
            notes.append("Can comfortably run 8B-14B models with zero offloading, and 32B-70B with partial quantization.")
        elif (gpu.detected and effective_vram >= 4.0) or total_ram >= 24.0:
            capability = "GOOD"
            notes.append(f"Solid local AI foundation: {gpu.name} ({effective_vram}GB VRAM) + {total_ram}GB RAM.")
            notes.append("Ideal for 3B-8B parameter models with near-instant interactive token generation.")
            if total_ram >= 32.0 and effective_vram < 8.0:
                notes.append("Ample System RAM enables running 14B-32B models with hybrid CPU/GPU offloading.")
        elif total_ram >= 12.0:
            capability = "MODERATE"
            notes.append(f"Capable of running compact 1B-4B models locally via CPU/RAM.")
            notes.append("Cloud models recommended for multi-file coding or complex reasoning tasks.")
        else:
            capability = "LIMITED"
            notes.append("Hardware is resource-constrained for large local inference.")
            notes.append("Recommended to use lightweight 1B models or cloud AI providers.")

        return capability, notes

    @classmethod
    def summary_text(cls) -> str:
        """Returns a concise, beautifully formatted human-readable hardware card."""
        p = cls.analyze()
        gpu_str = f"{p.gpu.name} ({p.gpu.vram_total_gb} GB {p.gpu.backend})" if p.gpu.detected else "None (CPU inference)"
        lines = [
            "CAT HARDWARE & ACCELERATION ANALYSIS",
            "----------------------------------------------",
            f"CPU           : {p.cpu.model} ({p.cpu.logical_cores} threads)",
            f"System RAM    : {p.ram.total_gb} GB ({p.ram.available_gb} GB available)",
            f"GPU           : {gpu_str}",
            f"Model Storage : {p.storage.free_gb} GB free on {p.storage.path}",
            f"Operating Sys : {p.os_name} ({p.cpu.arch})",
            "----------------------------------------------",
            f"Local AI Tier : {p.ai_capability}",
        ]
        for note in p.ai_capability_notes:
            lines.append(f"  * {note}")
        return "\n".join(lines)
