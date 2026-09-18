"""
CAT Activity System — centralized real-time Activity/Event bus.

Every real agent operation, tool call, command, file op, permission check,
question, or system event publishes a structured Activity here.
The Textual UI subscribes and renders live — never fake animations.

Spec section 1 event shape:
{
    "id": "unique-activity-id",
    "type": "tool | command | file | permission | question | status | system",
    "action": "search | grep | glob | read | edit | write | create | delete | run | test | build | web | provider | etc.",
    "status": "pending | running | completed | failed | cancelled | paused | waiting",
    "title": "Human-readable activity title",
    "details": "Optional additional information",
    "file": "Optional file path",
    "command": "Optional command",
    "tool": "Optional tool name",
    "result": "Optional summarized result",
    "timestamp": "...",
    "duration_ms": 0
}
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
import uuid
import threading
import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("cct.activity")

# ── diagnostic event debug flag (spec section 31: cat --debug-events)
_DEBUG_EVENTS = False

def set_debug_events(enable: bool = True) -> None:
    global _DEBUG_EVENTS
    _DEBUG_EVENTS = bool(enable)

def is_debug_events() -> bool:
    return _DEBUG_EVENTS

# ── helper duration formatter ──────────────────────────────────────────────
def _fmt_duration(ms: int) -> str:
    if ms < 1000:
        return f"{ms}ms"
    s = ms / 1000.0
    if s < 60:
        return f"{s:.1f}s"
    m = int(s // 60)
    r = s % 60
    return f"{m}m {r:.0f}s"

# ── thread-local current turn (so any nested tool call without explicit turn_id still binds to the active UI turn)
_thread_local = threading.local()

def set_current_turn(turn_id: str) -> None:
    try:
        _thread_local.current_turn = turn_id or ""
    except Exception:
        pass

def get_current_turn() -> str:
    try:
        return getattr(_thread_local, "current_turn", "") or ""
    except Exception:
        return ""

def clear_current_turn() -> None:
    try:
        _thread_local.current_turn = ""
    except Exception:
        pass

# ── canonical status values (spec section 3) ───────────────────────────────
STATUS_QUEUED = "queued"
STATUS_PENDING = "pending"
STATUS_STARTED = "started"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
STATUS_WAITING_PERMISSION = "waiting_permission"
STATUS_PAUSED = "paused"
STATUS_RETRYING = "retrying"
STATUS_WAITING = "waiting"
STATUS_WARNING = "warning"

# Backwards compat aliases
QUEUED = STATUS_QUEUED
PENDING = STATUS_PENDING
STARTED = STATUS_STARTED
RUNNING = STATUS_RUNNING
COMPLETED = STATUS_COMPLETED
FAILED = STATUS_FAILED
CANCELLED = STATUS_CANCELLED
WAITING_PERMISSION = STATUS_WAITING_PERMISSION
PAUSED = STATUS_PAUSED
RETRYING = STATUS_RETRYING
WAITING = STATUS_WAITING
WARNING = STATUS_WARNING

STATUSES = frozenset({
    STATUS_QUEUED, STATUS_PENDING, STATUS_STARTED, STATUS_RUNNING, STATUS_COMPLETED,
    STATUS_FAILED, STATUS_CANCELLED, STATUS_WAITING_PERMISSION,
    STATUS_PAUSED, STATUS_RETRYING, STATUS_WAITING, STATUS_WARNING
})

# ── canonical event types (spec section 3) ───────────────────────────────────
EVENT_TASK_STARTED = "task.started"
EVENT_TASK_COMPLETED = "task.completed"
EVENT_TASK_FAILED = "task.failed"

EVENT_PLAN_CREATED = "plan.created"
EVENT_PLAN_STEP_STARTED = "plan.step_started"
EVENT_PLAN_STEP_COMPLETED = "plan.step_completed"

EVENT_MODEL_REQUEST_STARTED = "model.request_started"
EVENT_MODEL_TOKEN_STREAMING = "model.token_streaming"
EVENT_MODEL_REQUEST_COMPLETED = "model.request_completed"
EVENT_MODEL_REQUEST_FAILED = "model.request_failed"

EVENT_TOOL_STARTED = "tool.started"
EVENT_TOOL_PROGRESS = "tool.progress"
EVENT_TOOL_COMPLETED = "tool.completed"
EVENT_TOOL_FAILED = "tool.failed"

EVENT_FILE_READ_STARTED = "file.read_started"
EVENT_FILE_READ_COMPLETED = "file.read_completed"
EVENT_FILE_WRITE_STARTED = "file.write_started"
EVENT_FILE_WRITE_COMPLETED = "file.write_completed"
EVENT_FILE_DELETE_STARTED = "file.delete_started"
EVENT_FILE_DELETE_COMPLETED = "file.delete_completed"

EVENT_TERMINAL_STARTED = "terminal.started"
EVENT_TERMINAL_OUTPUT = "terminal.output"
EVENT_TERMINAL_COMPLETED = "terminal.completed"
EVENT_TERMINAL_FAILED = "terminal.failed"

EVENT_BROWSER_STARTED = "browser.started"
EVENT_BROWSER_NAVIGATION = "browser.navigation"
EVENT_BROWSER_CLICK = "browser.click"
EVENT_BROWSER_INPUT = "browser.input"
EVENT_BROWSER_SCREENSHOT = "browser.screenshot"
EVENT_BROWSER_COMPLETED = "browser.completed"

EVENT_TEST_STARTED = "test.started"
EVENT_TEST_PROGRESS = "test.progress"
EVENT_TEST_PASSED = "test.passed"
EVENT_TEST_FAILED = "test.failed"

EVENT_MEMORY_READ = "memory.read"
EVENT_MEMORY_WRITE = "memory.write"

EVENT_PERMISSION_REQUESTED = "permission.requested"
EVENT_PERMISSION_GRANTED = "permission.granted"
EVENT_PERMISSION_DENIED = "permission.denied"

EVENT_AGENT_PAUSED = "agent.paused"
EVENT_AGENT_RESUMED = "agent.resumed"
EVENT_AGENT_RETRYING = "agent.retrying"
EVENT_AGENT_CANCELLED = "agent.cancelled"

EVENT_RESOURCE_SAMPLE = "resource.sample"
EVENT_SYSTEM_WARNING = "system.warning"
EVENT_SYSTEM_ERROR = "system.error"

# ── canonical categories (spec section 1) ───────────────────────────────────
CAT_SEARCH = "SEARCH"
CAT_FILE_READ = "FILE_READ"
CAT_EDIT = "EDIT"
CAT_TERMINAL = "TERMINAL"
CAT_TEST = "TEST"
CAT_BUILD = "BUILD"
CAT_ANALYSIS = "ANALYSIS"
CAT_GIT = "GIT"
CAT_PLANNING = "PLANNING"
CAT_SUBAGENT = "SUBAGENT"
CAT_SYSTEM = "SYSTEM"
CAT_MODEL = "MODEL"

CATEGORIES = frozenset({
    CAT_SEARCH, CAT_FILE_READ, CAT_EDIT, CAT_TERMINAL, CAT_TEST,
    CAT_BUILD, CAT_ANALYSIS, CAT_GIT, CAT_PLANNING, CAT_SUBAGENT,
    CAT_SYSTEM, CAT_MODEL
})

# ── canonical phases ────────────────────────────────────────────────────────
PHASE_DISCOVERY = "DISCOVERY"
PHASE_ANALYSIS = "ANALYSIS"
PHASE_IMPLEMENTATION = "IMPLEMENTATION"
PHASE_VALIDATION = "VALIDATION"
PHASE_COMPLETE = "COMPLETE"

PHASE_ICONS = {
    PHASE_DISCOVERY: "⌕",
    PHASE_ANALYSIS: "🧠",
    PHASE_IMPLEMENTATION: "✎",
    PHASE_VALIDATION: "▶",
    PHASE_COMPLETE: "✓",
}

# ── canonical type values (spec section 1) ─────────────────────────────────
TYPE_TOOL = "tool"
TYPE_COMMAND = "command"
TYPE_FILE = "file"
TYPE_PERMISSION = "permission"
TYPE_QUESTION = "question"
TYPE_STATUS = "status"
TYPE_SYSTEM = "system"
TYPE_PROVIDER = "provider"
TYPE_SEARCH = "search"
TYPE_WORKSPACE = "workspace"

TYPES = frozenset({TYPE_TOOL, TYPE_COMMAND, TYPE_FILE, TYPE_PERMISSION, TYPE_QUESTION, TYPE_STATUS, TYPE_SYSTEM, TYPE_PROVIDER, TYPE_SEARCH, TYPE_WORKSPACE})

# status -> static icon (spec section 3, accessibility: icon+text not color alone)
STATUS_ICONS = {
    STATUS_PENDING: "⏳",
    STATUS_STARTED: "◐",
    STATUS_RUNNING: "◐",
    STATUS_COMPLETED: "✓",
    STATUS_FAILED: "✕",
    STATUS_CANCELLED: "⊘",
    STATUS_WAITING_PERMISSION: "⚠",
    STATUS_PAUSED: "⏸",
    STATUS_WAITING: "?",
    STATUS_WARNING: "⚠",
}

# Backwards compat alias for older search of icons
STATE_ICONS = STATUS_ICONS

# throttle: if > N events per second for same turn, coalesce
_THROTTLE_WINDOW = 0.05  # 50ms
_MAX_PER_TURN = 120
_MAX_TOTAL = 500
_MAX_BUFFER = 500


@dataclass
class ResourceSample:
    timestamp: float
    system_ram_used_gb: float
    system_ram_total_gb: float
    system_ram_percent: float
    process_ram_mb: float
    cpu_percent: float
    disk_percent: float = 0.0
    gpu_vram_used_gb: Optional[float] = None
    gpu_vram_total_gb: Optional[float] = None
    gpu_name: Optional[str] = None
    warning_level: str = "normal"  # normal | elevated | high | critical


class ResourceMonitor:
    """
    Real-time system resource monitor.
    Non-blocking, configurable background daemon sampler.
    Measures actual RAM, CPU, and process RSS without guessing.
    """

    def __init__(self, interval_sec: float = 1.0, on_sample: Optional[Callable[[ResourceSample], None]] = None):
        self.interval_sec = interval_sec
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._latest_sample: Optional[ResourceSample] = None
        self._on_sample = on_sample
        self._last_warning_time = 0.0
        self._last_warning_level = "normal"
        self._cooldown_sec = 30.0

    def sample_now(self) -> ResourceSample:
        sys_used_gb = 0.0
        sys_total_gb = 0.0
        sys_pct = 0.0
        proc_mb = 0.0
        cpu_pct = 0.0
        disk_pct = 0.0
        gpu_name = None
        gpu_used_gb = None
        gpu_total_gb = None

        try:
            import psutil
            vm = psutil.virtual_memory()
            sys_total_gb = round(vm.total / (1024 ** 3), 2)
            sys_used_gb = round(vm.used / (1024 ** 3), 2)
            sys_pct = round(vm.percent, 1)

            proc = psutil.Process(os.getpid())
            proc_mb = round(proc.memory_info().rss / (1024 ** 2), 1)

            cpu_pct = round(psutil.cpu_percent(interval=None), 1)
            try:
                disk = psutil.disk_usage(os.getcwd() if os.path.exists(os.getcwd()) else "/")
                disk_pct = round(disk.percent, 1)
            except Exception:
                disk_pct = 0.0
        except Exception:
            try:
                if platform.system() == "Windows":
                    import ctypes
                    class MEMORYSTATUSEX(ctypes.Structure):
                        _fields_ = [
                            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)
                        ]
                    stat = MEMORYSTATUSEX(dwLength=ctypes.sizeof(MEMORYSTATUSEX))
                    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                    sys_total_gb = round(int(stat.ullTotalPhys) / (1024 ** 3), 2)
                    avail_gb = round(int(stat.ullAvailPhys) / (1024 ** 3), 2)
                    sys_used_gb = round(sys_total_gb - avail_gb, 2)
                    sys_pct = round((sys_used_gb / sys_total_gb) * 100, 1) if sys_total_gb > 0 else 0.0
            except Exception:
                pass

        # Try real GPU query via nvidia-smi if available (never fake!)
        try:
            if shutil.which("nvidia-smi"):
                out = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader,nounits"],
                    timeout=1.5, text=True
                )
                lines = [l.strip() for l in out.splitlines() if l.strip()]
                if lines:
                    parts = [p.strip() for p in lines[0].split(",")]
                    if len(parts) >= 3:
                        gpu_name = parts[0]
                        gpu_used_gb = round(float(parts[1]) / 1024.0, 2)
                        gpu_total_gb = round(float(parts[2]) / 1024.0, 2)
        except Exception:
            pass

        # Thresholds per spec:
        # <70% normal, 70-85% elevated, 85-95% high, >95% critical
        warn_level = "normal"
        if sys_pct > 95.0:
            warn_level = "critical"
        elif sys_pct > 85.0:
            warn_level = "high"
        elif sys_pct > 70.0:
            warn_level = "elevated"

        sample = ResourceSample(
            timestamp=time.time(),
            system_ram_used_gb=sys_used_gb,
            system_ram_total_gb=sys_total_gb,
            system_ram_percent=sys_pct,
            process_ram_mb=proc_mb,
            cpu_percent=cpu_pct,
            disk_percent=disk_pct,
            gpu_vram_used_gb=gpu_used_gb,
            gpu_vram_total_gb=gpu_total_gb,
            gpu_name=gpu_name,
            warning_level=warn_level,
        )

        with self._lock:
            self._latest_sample = sample

        # Check threshold warnings with cooldown
        now = time.time()
        if warn_level != "normal":
            if (now - self._last_warning_time > self._cooldown_sec) or (warn_level != self._last_warning_level and warn_level in ("high", "critical")):
                self._last_warning_time = now
                self._last_warning_level = warn_level
                try:
                    mgr = globals().get("manager")
                    if mgr:
                        mgr.create(
                            type=TYPE_SYSTEM,
                            action="resource_warning",
                            title=f"⚠ System RAM {warn_level.upper()}: {sys_used_gb:.1f}/{sys_total_gb:.1f} GB ({sys_pct:.1f}%)",
                            status=STATUS_WARNING,
                            details=f"System RAM: {sys_used_gb:.1f}/{sys_total_gb:.1f} GB ({sys_pct:.1f}%), CAT Process: {proc_mb:.1f} MB, CPU: {cpu_pct:.1f}%",
                            event_type=EVENT_SYSTEM_WARNING,
                            category=CAT_SYSTEM,
                            phase=PHASE_IMPLEMENTATION,
                        )
                except Exception:
                    pass

        return sample

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="CCT-ResourceMonitor")
            self._thread.start()

    def stop(self):
        with self._lock:
            self._running = False

    def _run_loop(self):
        while self._running:
            try:
                sample = self.sample_now()
                if self._on_sample:
                    self._on_sample(sample)
            except Exception as e:
                logger.debug("Resource sampler loop error: %s", e)
            time.sleep(self.interval_sec)

    def get_latest(self) -> ResourceSample:
        with self._lock:
            if self._latest_sample is not None:
                return self._latest_sample
        return self.sample_now()


@dataclass
class Activity:
    id: str
    type: str  # activity_type
    action: str
    status: str
    title: str
    details: str = ""
    file: str = ""
    command: str = ""
    tool: str = ""
    result: str = ""
    timestamp: float = field(default_factory=time.time)  # updated_time
    duration_ms: int = 0
    turn_id: str = ""
    # internal helpers not in spec but needed for UI
    start_time: float = field(default_factory=time.time)
    output_lines: List[str] = field(default_factory=list)
    expanded: bool = False
    parent_id: str = ""
    progress: Optional[float] = None  # nullable per spec
    # --- canonical category & phase ---
    category: str = ""
    phase: str = ""
    # --- execution details ---
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    target_path: str = ""
    line_count: Optional[int] = None
    diff_summary: str = ""
    query: str = ""
    match_count: Optional[int] = None
    permission_req: Optional[Dict[str, Any]] = None
    # --- spec-required extended fields (all real, never fake) ---
    description: str = ""  # alias for details, human-readable
    updated_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    model: str = ""  # real provider model, e.g. nvidia/nemotron-3-ultra-550b
    provider: str = ""  # real provider id, e.g. nvidia
    workspace: str = ""  # real workspace path
    current_step: str = ""  # real current step description
    error: str = ""  # real error message when FAILED
    cancellable: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    # --- 100% real event schema extensions ---
    event_id: str = ""
    task_id: str = ""
    parent_event_id: str = ""
    event_type: str = ""
    source: str = ""
    duration: float = 0.0
    operation_id: str = ""
    pid: Optional[int] = None
    lines_added: int = 0
    lines_removed: int = 0

    def __post_init__(self):
        # keep aliases in sync - description/details, timestamp/updated_time
        if self.description and not self.details:
            self.details = self.description
        elif self.details and not self.description:
            self.description = self.details
        if not self.updated_time:
            self.updated_time = self.timestamp
        else:
            self.timestamp = self.updated_time
        if self.file and not self.target_path:
            self.target_path = self.file
        elif self.target_path and not self.file:
            self.file = self.target_path
        # keep event schema aliases in sync
        if not self.event_id:
            self.event_id = self.id
        elif not self.id:
            self.id = self.event_id
        if not self.task_id:
            self.task_id = self.turn_id
        elif not self.turn_id:
            self.turn_id = self.task_id
        if not self.parent_event_id:
            self.parent_event_id = self.parent_id
        elif not self.parent_id:
            self.parent_id = self.parent_event_id
        if not self.event_type:
            self.event_type = f"{self.type}.{self.action}" if self.type and self.action else (self.type or "task.operation")
        if self.duration == 0 and self.duration_ms > 0:
            self.duration = self.duration_ms / 1000.0
        elif self.duration > 0 and self.duration_ms == 0:
            self.duration_ms = int(self.duration * 1000)
        # auto-infer category if not given
        if not self.category:
            if self.tool in ("search_workspace", "list_directory", "web_search", "deep_research") or self.type == TYPE_SEARCH:
                self.category = CAT_SEARCH
            elif self.tool in ("read_file", "read_attachment", "archive_list") or (self.type == TYPE_FILE and self.action in ("read", "list")):
                self.category = CAT_FILE_READ
            elif self.tool in ("write_file", "create_folder", "delete_file", "rename_file", "edit_file") or (self.type == TYPE_FILE and self.action in ("write", "edit", "create", "delete", "rename")):
                self.category = CAT_EDIT
            elif self.tool in ("run_terminal", "install_packages", "device_action") or self.type == TYPE_COMMAND:
                self.category = CAT_TERMINAL
            elif self.tool in ("run_tests",) or self.action == "test":
                self.category = CAT_TEST
            elif self.tool in ("run_build", "archive_validate") or self.action == "build":
                self.category = CAT_BUILD
            elif self.type == TYPE_PROVIDER:
                self.category = CAT_MODEL
            elif self.type == TYPE_PERMISSION:
                self.category = CAT_SYSTEM
            else:
                self.category = CAT_ANALYSIS
        # auto-infer phase if not given
        if not self.phase:
            if self.category in (CAT_SEARCH, CAT_FILE_READ):
                self.phase = PHASE_DISCOVERY
            elif self.category in (CAT_ANALYSIS, CAT_PLANNING, CAT_MODEL):
                self.phase = PHASE_ANALYSIS
            elif self.category in (CAT_EDIT, CAT_TERMINAL, CAT_GIT):
                self.phase = PHASE_IMPLEMENTATION
            elif self.category in (CAT_TEST, CAT_BUILD):
                self.phase = PHASE_VALIDATION
            else:
                self.phase = PHASE_IMPLEMENTATION

    @property
    def activity_id(self) -> str:
        return self.id

    @property
    def activity_type(self) -> str:
        return self.type

    @property
    def elapsed_time(self) -> float:
        return self.elapsed_ms / 1000.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # spec expects timestamp as iso or float; keep float for now
        # add computed elapsed
        d["elapsed_time"] = self.elapsed_time
        d["activity_id"] = self.id
        d["activity_type"] = self.type
        return d

    @property
    def icon(self) -> str:
        return STATUS_ICONS.get(self.status, "·")

    @property
    def elapsed_ms(self) -> int:
        if self.status in (COMPLETED, FAILED, CANCELLED, WARNING):
            return self.duration_ms
        return int((time.time() - self.start_time) * 1000)

    @property
    def summary(self) -> str:
        """Human-readable one-liner for collapsed history."""
        base = f"{self.icon} {self.title}"
        if self.result:
            base += f" — {self.result[:80]}"
        elif self.details:
            base += f" — {self.details[:80]}"
        return base


class ActivityManager:
    """
    Central activity bus. Thread-safe. Backend emits, UI subscribes.
    Synchronous delivery (callbacks fire in emit thread) — UI callbacks
    must use call_from_thread if they touch Textual widgets.
    """

    def __init__(self):
        self._activities: Dict[str, Activity] = {}
        self._turn_order: Dict[str, List[str]] = {}  # turn_id -> [activity_id] in creation order
        self._global_order: List[str] = []  # all activity ids in order
        self._subscribers: List[Callable[[Activity, str], None]] = []
        self._lock = threading.RLock()
        self._throttle_last: Dict[str, float] = {}  # activity_id -> last notify time
        self._pending_throttle: Dict[str, Activity] = {}
        # deduplication & mapping
        self._operation_map: Dict[str, str] = {}  # operation_id -> activity_id
        self._active_dedup_keys: Dict[str, str] = {}  # dedup_key -> activity_id
        # real-time resource monitor daemon
        self.resource_monitor = ResourceMonitor(interval_sec=1.0)
        try:
            self.resource_monitor.start()
        except Exception as e:
            logger.debug("Failed to start resource monitor daemon: %s", e)

    # ── subscription ───────────────────────────────────────────────────
    def subscribe(self, callback: Callable[[Activity, str], None]) -> Callable:
        with self._lock:
            self._subscribers.append(callback)
        return callback

    def unsubscribe(self, callback: Callable) -> None:
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def _notify(self, activity: Activity, change: str) -> None:
        # change: "created" | "updated" | "removed"
        subs = list(self._subscribers)
        for cb in subs:
            try:
                cb(activity, change)
            except Exception as e:
                logger.debug("Activity subscriber error: %s", e)

    # ── creation ───────────────────────────────────────────────────────
    def create(
        self,
        type: str,
        action: str,
        title: str,
        status: str = RUNNING,
        details: str = "",
        file: str = "",
        command: str = "",
        tool: str = "",
        result: str = "",
        turn_id: str = "",
        parent_id: str = "",
        duration_ms: int = 0,
        # spec extended fields - all from real runtime, never fake
        category: str = "",
        phase: str = "",
        stdout: str = "",
        stderr: str = "",
        exit_code: Optional[int] = None,
        target_path: str = "",
        line_count: Optional[int] = None,
        diff_summary: str = "",
        query: str = "",
        match_count: Optional[int] = None,
        permission_req: Optional[Dict[str, Any]] = None,
        description: str = "",
        progress: Optional[float] = None,
        model: str = "",
        provider: str = "",
        workspace: str = "",
        current_step: str = "",
        error: str = "",
        cancellable: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        id: Optional[str] = "",
        # 100% real event schema extensions
        operation_id: str = "",
        event_id: str = "",
        task_id: str = "",
        parent_event_id: str = "",
        event_type: str = "",
        source: str = "",
        pid: Optional[int] = None,
        lines_added: int = 0,
        lines_removed: int = 0,
    ) -> Activity:
        if not turn_id:
            turn_id = task_id or get_current_turn()
        if not parent_id and parent_event_id:
            parent_id = parent_event_id
        if not id and event_id:
            id = event_id
        if status not in STATUSES:
            status = RUNNING

        now = time.time()
        # description aliases details
        if description and not details:
            details = description
        elif details and not description:
            description = details

        # ── Deduplication Guard: Check existing operation or running signature ──
        with self._lock:
            if operation_id and operation_id in self._operation_map:
                existing_id = self._operation_map[operation_id]
                existing = self._activities.get(existing_id)
                if existing:
                    # Update existing activity instead of creating duplicate card
                    updates: Dict[str, Any] = {"title": title, "status": status}
                    if details:
                        updates["details"] = details
                    if result:
                        updates["result"] = result
                    if duration_ms > 0:
                        updates["duration_ms"] = duration_ms
                    if exit_code is not None:
                        updates["exit_code"] = exit_code
                    if lines_added > 0:
                        updates["lines_added"] = lines_added
                    if lines_removed > 0:
                        updates["lines_removed"] = lines_removed
                    return self.update(existing_id, **updates) or existing

            # Signature deduplication for active/running operations in the same turn
            target_key = target_path or file or command or title
            dedup_key = f"{turn_id}:{type}:{tool}:{target_key}"
            if status in (STATUS_RUNNING, STATUS_PENDING, STATUS_STARTED, STATUS_QUEUED) and dedup_key in self._active_dedup_keys:
                existing_id = self._active_dedup_keys[dedup_key]
                existing = self._activities.get(existing_id)
                if existing and existing.status in (STATUS_RUNNING, STATUS_PENDING, STATUS_STARTED, STATUS_QUEUED):
                    if details and details != existing.details:
                        existing.details = details
                        existing.description = details
                    if title and title != existing.title:
                        existing.title = title
                    if progress is not None:
                        existing.progress = progress
                    existing.updated_time = now
                    self._notify(existing, "updated")
                    return existing

        # Generate canonical EVT-<hex> if not specified
        act_id = id or f"EVT-{uuid.uuid4().hex[:8].upper()}"

        # try to fill workspace/model/provider from real context if not provided
        if not workspace:
            try:
                from . import workspace as _ws
                workspace = _ws.root_dir() or ""
            except Exception:
                pass
        if not provider or not model:
            try:
                from . import aicore as _ac
                cfg = _ac.load_config()
                if not provider:
                    provider = cfg.get("provider") or ""
                if not model:
                    model = cfg.get("model") or ""
            except Exception:
                pass

        act = Activity(
            id=act_id,
            type=type,
            action=action,
            status=status,
            title=title,
            details=details,
            description=description,
            file=file,
            command=command,
            tool=tool,
            result=result,
            timestamp=now,
            updated_time=now,
            start_time=now,
            duration_ms=duration_ms,
            turn_id=turn_id or "",
            parent_id=parent_id or "",
            progress=progress,
            category=category,
            phase=phase,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            target_path=target_path or file,
            line_count=line_count,
            diff_summary=diff_summary,
            query=query,
            match_count=match_count,
            permission_req=permission_req,
            model=model,
            provider=provider,
            workspace=workspace,
            current_step=current_step,
            error=error,
            cancellable=cancellable,
            metadata=metadata or {},
            # 100% real event fields
            event_id=act_id,
            task_id=turn_id or "",
            parent_event_id=parent_id or "",
            event_type=event_type or f"{type}.{action}",
            source=source or "cat.core",
            duration=duration_ms / 1000.0 if duration_ms > 0 else 0.0,
            operation_id=operation_id,
            pid=pid,
            lines_added=lines_added,
            lines_removed=lines_removed,
        )

        with self._lock:
            self._activities[act_id] = act
            self._global_order.append(act_id)
            if operation_id:
                self._operation_map[operation_id] = act_id
            if status in (STATUS_RUNNING, STATUS_PENDING, STATUS_STARTED, STATUS_QUEUED):
                self._active_dedup_keys[dedup_key] = act_id

            if turn_id:
                self._turn_order.setdefault(turn_id, []).append(act_id)
                # bound per-turn
                if len(self._turn_order[turn_id]) > _MAX_PER_TURN:
                    oldest = self._turn_order[turn_id].pop(0)
                    self._activities.pop(oldest, None)
                    if oldest in self._global_order:
                        self._global_order.remove(oldest)
            # bound total
            if len(self._global_order) > _MAX_TOTAL:
                oldest = self._global_order.pop(0)
                self._activities.pop(oldest, None)
                # also remove from turn index if there
                for tid, lst in list(self._turn_order.items()):
                    if oldest in lst:
                        lst.remove(oldest)
                        if not lst:
                            self._turn_order.pop(tid, None)
                        break

        self._notify(act, "created")
        # also mirror to legacy event_stream for debugging/logging
        try:
            from . import event_stream as _es
            _es.stream.emit("activity_created", source="activity", activity_id=act_id, title=title, status=status, turn_id=turn_id)
        except Exception:
            pass
        return act

    # ── update ─────────────────────────────────────────────────────────
    def update(
        self,
        activity_id: str,
        status: Optional[str] = None,
        title: Optional[str] = None,
        details: Optional[str] = None,
        file: Optional[str] = None,
        command: Optional[str] = None,
        tool: Optional[str] = None,
        result: Optional[str] = None,
        duration_ms: Optional[int] = None,
        expanded: Optional[bool] = None,
        progress: Optional[float] = None,
        # extended spec fields
        category: Optional[str] = None,
        phase: Optional[str] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        exit_code: Optional[int] = None,
        target_path: Optional[str] = None,
        line_count: Optional[int] = None,
        diff_summary: Optional[str] = None,
        query: Optional[str] = None,
        match_count: Optional[int] = None,
        permission_req: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        workspace: Optional[str] = None,
        current_step: Optional[str] = None,
        error: Optional[str] = None,
        cancellable: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
        # real event fields
        event_type: Optional[str] = None,
        source: Optional[str] = None,
        duration: Optional[float] = None,
        operation_id: Optional[str] = None,
        pid: Optional[int] = None,
        lines_added: Optional[int] = None,
        lines_removed: Optional[int] = None,
    ) -> Optional[Activity]:
        with self._lock:
            act = self._activities.get(activity_id)
            if act is None:
                return None
            if status is not None:
                act.status = status
                # compute duration on terminal states if not supplied
                if status in (COMPLETED, FAILED, CANCELLED, WARNING, PAUSED, WAITING,
                              STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED, STATUS_WARNING):
                    if duration_ms is not None:
                        act.duration_ms = duration_ms
                        act.duration = duration_ms / 1000.0
                    elif duration is not None:
                        act.duration = duration
                        act.duration_ms = int(duration * 1000)
                    elif act.duration_ms == 0:
                        act.duration_ms = int((time.time() - act.start_time) * 1000)
                        act.duration = act.duration_ms / 1000.0
                    act.end_time = time.time()
                    if status in (FAILED, STATUS_FAILED) and error is None and act.error == "" and result:
                        # capture real error from result if not provided
                        act.error = result[:500]

                    # Release deduplication lock for terminal states
                    for k, aid in list(self._active_dedup_keys.items()):
                        if aid == activity_id:
                            self._active_dedup_keys.pop(k, None)
                else:
                    act.end_time = None
            if title is not None:
                act.title = title
            if details is not None:
                act.details = details
                act.description = details
            if description is not None:
                act.description = description
                act.details = description
            if file is not None:
                act.file = file
                if target_path is None:
                    act.target_path = file
            if target_path is not None:
                act.target_path = target_path
                act.file = target_path
            if command is not None:
                act.command = command
            if tool is not None:
                act.tool = tool
            if result is not None:
                act.result = result
            if category is not None:
                act.category = category
            if phase is not None:
                act.phase = phase
            if stdout is not None:
                act.stdout = stdout
            if stderr is not None:
                act.stderr = stderr
            if exit_code is not None:
                act.exit_code = exit_code
            if line_count is not None:
                act.line_count = line_count
            if diff_summary is not None:
                act.diff_summary = diff_summary
            if query is not None:
                act.query = query
            if match_count is not None:
                act.match_count = match_count
            if permission_req is not None:
                act.permission_req = permission_req
            if duration_ms is not None and status is None:
                act.duration_ms = duration_ms
                act.duration = duration_ms / 1000.0
            if duration is not None and status is None:
                act.duration = duration
                act.duration_ms = int(duration * 1000)
            if expanded is not None:
                act.expanded = expanded
            if progress is not None:
                try:
                    v = float(progress)
                    act.progress = max(0.0, min(1.0, v))
                except Exception:
                    pass
            if model is not None:
                act.model = model
            if provider is not None:
                act.provider = provider
            if workspace is not None:
                act.workspace = workspace
            if current_step is not None:
                act.current_step = current_step
            if error is not None:
                act.error = error
            if cancellable is not None:
                act.cancellable = cancellable
            if metadata is not None:
                act.metadata.update(metadata)
            if event_type is not None:
                act.event_type = event_type
            if source is not None:
                act.source = source
            if operation_id is not None:
                act.operation_id = operation_id
                self._operation_map[operation_id] = activity_id
            if pid is not None:
                act.pid = pid
            if lines_added is not None:
                act.lines_added = lines_added
            if lines_removed is not None:
                act.lines_removed = lines_removed

            act.timestamp = time.time()
            act.updated_time = act.timestamp

        # throttling: if high-frequency updates for same id, coalesce within window
        now = time.time()
        last = self._throttle_last.get(activity_id, 0)
        if status in (COMPLETED, FAILED, CANCELLED, WARNING, WAITING, PAUSED,
                      STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED, STATUS_WARNING) or (now - last) >= _THROTTLE_WINDOW:
            self._throttle_last[activity_id] = now
            self._pending_throttle.pop(activity_id, None)
            self._notify(act, "updated")
        else:
            # store pending and schedule a delayed flush after the throttle window
            self._pending_throttle[activity_id] = act
            if not getattr(self, '_flush_timer_active', False):
                self._flush_timer_active = True
                def _deferred_flush():
                    self._flush_timer_active = False
                    self.flush_throttled()
                timer = threading.Timer(_THROTTLE_WINDOW, _deferred_flush)
                timer.daemon = True
                timer.start()
        try:
            from . import event_stream as _es
            _es.stream.emit("activity_updated", source="activity", activity_id=activity_id, status=act.status, title=act.title)
        except Exception:
            pass
        return act

    def check_stale_activities(self, stale_threshold_sec: float = 15.0) -> List[Activity]:
        """
        Watchdog: detects running/pending activities with no heartbeat or update for
        longer than stale_threshold_sec. Marks them as WARNING to prevent stuck UI spinners.
        """
        now = time.time()
        stale: List[Activity] = []
        with self._lock:
            for act in self._activities.values():
                if act.status in (STATUS_RUNNING, STATUS_PENDING, STATUS_STARTED, RUNNING, PENDING) and (now - act.updated_time) > stale_threshold_sec:
                    stale.append(act)

        for act in stale:
            self.update(
                act.id,
                status=STATUS_WARNING,
                result=act.result or f"Operation timed out ({stale_threshold_sec:.0f}s with no updates).",
                error=act.error or "Execution timed out / unresponsive",
            )
        return stale

    def get_resource_sample(self) -> ResourceSample:
        """Fetch latest actual system/process resource sample."""
        return self.resource_monitor.get_latest()

    def get_session_summary(self, turn_id: str = "") -> Dict[str, Any]:
        """
        Returns an authentic, non-simulated execution summary of all events for a turn or session.
        """
        with self._lock:
            if turn_id:
                acts = self.get_for_turn(turn_id)
            else:
                acts = self.get_all()

        sample = self.get_resource_sample()
        if not acts:
            return {
                "count": 0,
                "total_events": 0,
                "duration_ms": 0,
                "duration_str": "0s",
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
                "warning": 0,
                "running": 0,
                "waiting": 0,
                "files_read": [],
                "files_modified": [],
                "commands_executed": [],
                "tools_used": [],
                "errors": [],
                "ram_used_gb": sample.system_ram_used_gb,
                "ram_total_gb": sample.system_ram_total_gb,
                "ram_percent": sample.system_ram_percent,
                "process_ram_mb": sample.process_ram_mb,
                "cpu_percent": sample.cpu_percent,
                "gpu_name": sample.gpu_name,
            }

        start_time = min(a.start_time for a in acts)
        end_time = max(a.updated_time for a in acts)
        total_ms = int((end_time - start_time) * 1000)

        files_read = sorted(list({a.file or a.target_path for a in acts if a.category == CAT_FILE_READ and (a.file or a.target_path)}))
        files_mod = sorted(list({a.file or a.target_path for a in acts if a.category == CAT_EDIT and (a.file or a.target_path)}))
        commands = sorted(list({a.command for a in acts if a.command}))
        tools = sorted(list({a.tool for a in acts if a.tool}))
        errors = [a.error or a.result for a in acts if a.status in (STATUS_FAILED, STATUS_WARNING, FAILED, WARNING) and (a.error or a.result)]

        return {
            "count": len(acts),
            "total_events": len(acts),
            "duration_ms": total_ms,
            "duration_str": _fmt_duration(total_ms),
            "start_time": start_time,
            "end_time": end_time,
            "completed": sum(1 for a in acts if a.status in (STATUS_COMPLETED, COMPLETED)),
            "failed": sum(1 for a in acts if a.status in (STATUS_FAILED, FAILED)),
            "cancelled": sum(1 for a in acts if a.status in (STATUS_CANCELLED, CANCELLED)),
            "warning": sum(1 for a in acts if a.status in (STATUS_WARNING, WARNING)),
            "running": sum(1 for a in acts if a.status in (STATUS_RUNNING, STATUS_PENDING, STATUS_STARTED, RUNNING, PENDING)),
            "waiting": sum(1 for a in acts if a.status in (STATUS_WAITING, STATUS_WAITING_PERMISSION, WAITING, "waiting")),
            "files_read": files_read,
            "files_modified": files_mod,
            "commands_executed": commands,
            "tools_used": tools,
            "errors": errors,
            "ram_used_gb": sample.system_ram_used_gb,
            "ram_total_gb": sample.system_ram_total_gb,
            "ram_percent": sample.system_ram_percent,
            "process_ram_mb": sample.process_ram_mb,
            "cpu_percent": sample.cpu_percent,
            "gpu_name": sample.gpu_name,
        }

    def append_output(self, activity_id: str, line: str, max_lines: int = 200) -> Optional[Activity]:
        with self._lock:
            act = self._activities.get(activity_id)
            if act is None:
                return None
            act.output_lines.append(line)
            if len(act.output_lines) > max_lines:
                # keep tail
                act.output_lines = act.output_lines[-max_lines:]
            act.timestamp = time.time()
        # throttled output: directly notify but UI should coalesce
        self._notify(act, "updated")
        return act

    def get(self, activity_id: str) -> Optional[Activity]:
        with self._lock:
            return self._activities.get(activity_id)

    def get_for_turn(self, turn_id: str, limit: Optional[int] = None) -> List[Activity]:
        with self._lock:
            ids = list(self._turn_order.get(turn_id, []))
            if limit is not None:
                ids = ids[-limit:]
            return [self._activities[i] for i in ids if i in self._activities]

    def get_all(self, limit: Optional[int] = None) -> List[Activity]:
        with self._lock:
            ids = list(self._global_order)
            if limit is not None:
                ids = ids[-limit:]
            return [self._activities[i] for i in ids if i in self._activities]

    def get_recent(self, limit: int = 50) -> List[Activity]:
        return self.get_all(limit=limit)

    def turn_summary(self, turn_id: str) -> Dict[str, Any]:
        return self.get_session_summary(turn_id)

    def cancel_turn(self, turn_id: str) -> int:
        """Transition all running/pending activities for turn_id to CANCELLED."""
        count = 0
        with self._lock:
            ids = list(self._turn_order.get(turn_id, []))
            for aid in ids:
                act = self._activities.get(aid)
                if act and act.status in (PENDING, RUNNING, PAUSED, STATUS_RUNNING, STATUS_PENDING, STATUS_STARTED):
                    act.status = CANCELLED
                    act.result = act.result or "Cancelled"
                    act.duration_ms = int((time.time() - act.start_time) * 1000)
                    act.duration = act.duration_ms / 1000.0
                    act.timestamp = time.time()
                    count += 1
        if count:
            for aid in self._turn_order.get(turn_id, []):
                act = self._activities.get(aid)
                if act and act.status in (CANCELLED, STATUS_CANCELLED):
                    self._notify(act, "updated")
        return count

    def clear_turn(self, turn_id: str) -> int:
        with self._lock:
            ids = self._turn_order.pop(turn_id, [])
            for aid in ids:
                self._activities.pop(aid, None)
                if aid in self._global_order:
                    self._global_order.remove(aid)
            return len(ids)

    def clear_all(self) -> None:
        with self._lock:
            self._activities.clear()
            self._turn_order.clear()
            self._global_order.clear()
            self._throttle_last.clear()
            self._pending_throttle.clear()
            self._operation_map.clear()
            self._active_dedup_keys.clear()

    def flush_throttled(self) -> None:
        pending = list(self._pending_throttle.values())
        self._pending_throttle.clear()
        for act in pending:
            self._notify(act, "updated")
            self._throttle_last[act.id] = time.time()

# ── global singleton ───────────────────────────────────────────────────
manager = ActivityManager()

# ── convenience helpers ────────────────────────────────────────────────
def create_activity(type: str, action: str, title: str, **kwargs) -> Activity:
    return manager.create(type=type, action=action, title=title, **kwargs)

def update_activity(activity_id: str, **kwargs) -> Optional[Activity]:
    return manager.update(activity_id, **kwargs)

def append_output(activity_id: str, line: str) -> Optional[Activity]:
    return manager.append_output(activity_id, line)

def get_for_turn(turn_id: str) -> List[Activity]:
    return manager.get_for_turn(turn_id)

# ── context manager for scoped activities ──────────────────────────────
class ActivitySpan:
    """
    Context manager that creates a RUNNING activity on entry and
    completes/fails it on exit. Use when the real operation is bracketed:

        with ActivitySpan(type=TYPE_FILE, action="read", title="Reading x", turn_id=tid) as act:
            ... do real IO ...
            act.details = "2,184 lines"
    On exception, marks FAILED automatically.
    """

    def __init__(self, type: str, action: str, title: str, turn_id: str = "", **kwargs):
        self.type = type
        self.action = action
        self.title = title
        self.turn_id = turn_id
        self.kwargs = kwargs
        self.activity: Optional[Activity] = None

    def __enter__(self) -> Activity:
        self.activity = manager.create(
            type=self.type, action=self.action, title=self.title, status=RUNNING, turn_id=self.turn_id, **self.kwargs
        )
        return self.activity

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.activity is None:
            return False
        if exc_type is not None:
            manager.update(self.activity.id, status=FAILED, result=str(exc_val)[:400] if exc_val else "Failed")
        else:
            # only auto-complete if still running/pending
            if self.activity.status in (RUNNING, PENDING):
                dur = int((time.time() - self.activity.start_time) * 1000)
                manager.update(self.activity.id, status=COMPLETED, duration_ms=dur)
        return False

# ── human helpers: map tool name -> activity meta ──────────────────────
class ToolMeta(tuple):
    def __new__(cls, category: str, action: str, title: str, phase: str = PHASE_IMPLEMENTATION, type: str = ""):
        t = type or category.lower()
        return super().__new__(cls, (t, action, title))

    def __init__(self, category: str, action: str, title: str, phase: str = PHASE_IMPLEMENTATION, type: str = ""):
        self.category = category
        self.action = action
        self.title = title
        self.phase = phase
        self.type = type or category.lower()

TOOL_ACTIVITY_META: Dict[str, ToolMeta] = {
    # search / discovery
    "search_workspace": ToolMeta(CAT_SEARCH, "search", "Searching workspace", PHASE_DISCOVERY, TYPE_SEARCH),
    "inspect_project": ToolMeta(CAT_ANALYSIS, "inspect", "Inspecting project", PHASE_DISCOVERY, TYPE_WORKSPACE),
    "list_directory": ToolMeta(CAT_SEARCH, "list", "Listing directory", PHASE_DISCOVERY, TYPE_FILE),
    "read_file": ToolMeta(CAT_FILE_READ, "read", "Reading file", PHASE_DISCOVERY, TYPE_FILE),
    "read_attachment": ToolMeta(CAT_FILE_READ, "read", "Reading attachment", PHASE_DISCOVERY, TYPE_FILE),
    # file mutation
    "write_file": ToolMeta(CAT_EDIT, "write", "Writing file", PHASE_IMPLEMENTATION, TYPE_FILE),
    "create_folder": ToolMeta(CAT_EDIT, "create", "Creating folder", PHASE_IMPLEMENTATION, TYPE_FILE),
    "delete_file": ToolMeta(CAT_EDIT, "delete", "Deleting file", PHASE_IMPLEMENTATION, TYPE_FILE),
    "rename_file": ToolMeta(CAT_EDIT, "rename", "Renaming file", PHASE_IMPLEMENTATION, TYPE_FILE),
    "edit_file": ToolMeta(CAT_EDIT, "edit", "Editing file", PHASE_IMPLEMENTATION, TYPE_FILE),
    "archive_list": ToolMeta(CAT_FILE_READ, "archive", "Listing archive", PHASE_DISCOVERY, TYPE_FILE),
    "archive_delete_entries": ToolMeta(CAT_EDIT, "archive", "Updating archive", PHASE_IMPLEMENTATION, TYPE_FILE),
    "archive_extract": ToolMeta(CAT_EDIT, "archive", "Extracting archive", PHASE_IMPLEMENTATION, TYPE_FILE),
    "archive_add_entries": ToolMeta(CAT_EDIT, "archive", "Adding to archive", PHASE_IMPLEMENTATION, TYPE_FILE),
    "archive_repack": ToolMeta(CAT_EDIT, "archive", "Repacking archive", PHASE_IMPLEMENTATION, TYPE_FILE),
    "archive_validate": ToolMeta(CAT_BUILD, "archive", "Validating archive", PHASE_VALIDATION, TYPE_FILE),
    # execution
    "run_terminal": ToolMeta(CAT_TERMINAL, "run", "Running command", PHASE_IMPLEMENTATION, TYPE_COMMAND),
    "run_build": ToolMeta(CAT_BUILD, "build", "Running build", PHASE_VALIDATION, TYPE_COMMAND),
    "run_tests": ToolMeta(CAT_TEST, "test", "Running tests", PHASE_VALIDATION, TYPE_COMMAND),
    "install_packages": ToolMeta(CAT_TERMINAL, "install", "Installing packages", PHASE_IMPLEMENTATION, TYPE_COMMAND),
    "device_action": ToolMeta(CAT_TERMINAL, "device", "Device action", PHASE_IMPLEMENTATION, TYPE_COMMAND),
    # chemistry / compute
    "calculate": ToolMeta(CAT_ANALYSIS, "calculate", "Calculating", PHASE_ANALYSIS, TYPE_TOOL),
    "solve_formula": ToolMeta(CAT_ANALYSIS, "solve", "Solving formula", PHASE_ANALYSIS, TYPE_TOOL),
    "solve_custom": ToolMeta(CAT_ANALYSIS, "solve", "Solving custom formula", PHASE_ANALYSIS, TYPE_TOOL),
    "list_formulas": ToolMeta(CAT_ANALYSIS, "list", "Listing formulas", PHASE_ANALYSIS, TYPE_TOOL),
    "generate_numerical": ToolMeta(CAT_ANALYSIS, "generate", "Generating numerical", PHASE_ANALYSIS, TYPE_TOOL),
    "plot_preset": ToolMeta(CAT_ANALYSIS, "plot", "Plotting preset", PHASE_ANALYSIS, TYPE_TOOL),
    "plot_function": ToolMeta(CAT_ANALYSIS, "plot", "Plotting function", PHASE_ANALYSIS, TYPE_TOOL),
    "plot_surface": ToolMeta(CAT_ANALYSIS, "plot", "Exporting surface", PHASE_ANALYSIS, TYPE_TOOL),
    "simulate_atom_2d": ToolMeta(CAT_ANALYSIS, "simulate", "Simulating atom (2D)", PHASE_ANALYSIS, TYPE_TOOL),
    "simulate_atom_3d": ToolMeta(CAT_ANALYSIS, "simulate", "Simulating atom (3D)", PHASE_ANALYSIS, TYPE_TOOL),
    "simulate_orbital": ToolMeta(CAT_ANALYSIS, "simulate", "Simulating orbital", PHASE_ANALYSIS, TYPE_TOOL),
    "orbital_grid": ToolMeta(CAT_ANALYSIS, "simulate", "Exporting orbital grid", PHASE_ANALYSIS, TYPE_TOOL),
    "bonding_map": ToolMeta(CAT_ANALYSIS, "simulate", "Rendering bonding map", PHASE_ANALYSIS, TYPE_TOOL),
    "bloch_sphere": ToolMeta(CAT_ANALYSIS, "simulate", "Rendering Bloch sphere", PHASE_ANALYSIS, TYPE_TOOL),
    # web
    "web_search": ToolMeta(CAT_SEARCH, "web", "Searching web", PHASE_DISCOVERY, TYPE_TOOL),
    "deep_research": ToolMeta(CAT_SEARCH, "web", "Researching", PHASE_DISCOVERY, TYPE_TOOL),
}

def meta_for_tool(tool_name: str) -> ToolMeta:
    return TOOL_ACTIVITY_META.get(
        tool_name,
        ToolMeta(CAT_TERMINAL, tool_name, f"Running {tool_name}", PHASE_IMPLEMENTATION, TYPE_TOOL)
    )

# ── provider / model activity helper ───────────────────────────────────
def emit_provider_activity(title: str, status: str = RUNNING, turn_id: str = "", details: str = "", result: str = "") -> Activity:
    return manager.create(type=TYPE_PROVIDER, action="provider", title=title, status=status, turn_id=turn_id, details=details, result=result)
