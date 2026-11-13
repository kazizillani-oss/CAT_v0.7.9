import ctypes
from ctypes import wintypes

class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]

pmc = PROCESS_MEMORY_COUNTERS()
pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
success = ctypes.windll.psapi.GetProcessMemoryInfo(
    ctypes.windll.kernel32.GetCurrentProcess(),
    ctypes.byref(pmc),
    pmc.cb
)
if success:
    print(f"Memory: {pmc.WorkingSetSize / (1024 * 1024):.1f} MB")
else:
    print("Failed")

