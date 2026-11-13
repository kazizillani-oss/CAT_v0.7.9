"""
CAT Observability Center (v1.0.0)

Unified observability, distributed execution tracing, real measured telemetry,
and structured log management across all CAT subsystems:
- End-to-end execution tracing with Trace IDs and parent-child span trees
- Metrics engine tracking provider latency, token usage, actual costs, tool failure rates
- Structured logging with log rotation, search, export, and sensitive secret redaction
- Application health & diagnostics bridge
"""

from __future__ import annotations

import os
import re
import time
import json
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Tuple

SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|secret|password|token|bearer|authorization)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-.~+/]{8,})['\"]?"
)


@dataclass
class TraceSpan:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    component: str  # "ai_call", "agent", "tool", "extension", "mcp", "workflow", "deploy", "file"
    started_at: float
    ended_at: Optional[float] = None
    duration_ms: float = 0.0
    status: str = "running"  # "running", "ok", "error"
    attributes: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    def finish(self, status: str = "ok", error: Optional[str] = None):
        self.ended_at = time.time()
        self.duration_ms = max(0.0, (self.ended_at - self.started_at) * 1000.0)
        self.status = status
        self.error_message = error


@dataclass
class LogEntry:
    timestamp: float
    level: str  # "DEBUG", "INFO", "WARN", "ERROR"
    component: str
    message: str
    trace_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ObservabilityCenter:
    """Central observability, tracing, metrics, and logging hub for CAT."""

    _instance = None

    def __init__(self, log_dir: Optional[str] = None):
        self.log_dir = log_dir or os.path.join(os.path.expanduser("~"), ".cat_observability")
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, "cat_structured.log")
        self.traces_file = os.path.join(self.log_dir, "traces.json")

        self.spans: Dict[str, TraceSpan] = {}  # span_id -> TraceSpan
        self.active_traces: Dict[str, List[str]] = {}  # trace_id -> list of span_ids
        self.recent_logs: List[LogEntry] = []
        self.max_memory_logs = 1000
        self.max_memory_traces = 500

        # Telemetry aggregations
        self.metrics = {
            "total_requests": 0,
            "successful_tool_calls": 0,
            "failed_tool_calls": 0,
            "total_tokens_consumed": 0,
            "total_cost_usd": 0.0,
            "provider_calls": 0,
            "provider_latencies_ms": [],
            "extension_errors": 0,
            "mcp_errors": 0,
        }

    @classmethod
    def get(cls) -> "ObservabilityCenter":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # =====================================================================
    # Distributed Execution Tracing
    # =====================================================================

    def start_trace(self, name: str, component: str = "user_request") -> TraceSpan:
        trace_id = f"tr_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        return self.start_span(trace_id=trace_id, name=name, component=component)

    def start_span(
        self,
        trace_id: str,
        name: str,
        component: str,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> TraceSpan:
        span_id = f"sp_{uuid.uuid4().hex[:8]}"
        span = TraceSpan(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name,
            component=component,
            started_at=time.time(),
            attributes=attributes or {},
        )
        self.spans[span_id] = span
        if trace_id not in self.active_traces:
            self.active_traces[trace_id] = []
        self.active_traces[trace_id].append(span_id)
        return span

    def end_span(self, span_id: str, status: str = "ok", error: Optional[str] = None):
        span = self.spans.get(span_id)
        if span:
            span.finish(status=status, error=error)
            if status == "error":
                if span.component == "tool":
                    self.metrics["failed_tool_calls"] += 1
                elif span.component == "extension":
                    self.metrics["extension_errors"] += 1
                elif span.component == "mcp":
                    self.metrics["mcp_errors"] += 1
            elif status == "ok" and span.component == "tool":
                self.metrics["successful_tool_calls"] += 1

    def get_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        span_ids = self.active_traces.get(trace_id, [])
        return [asdict(self.spans[sid]) for sid in span_ids if sid in self.spans]

    def list_recent_traces(self, limit: int = 15) -> List[Dict[str, Any]]:
        res = []
        for tid, sids in list(self.active_traces.items())[-limit:]:
            if sids and sids[0] in self.spans:
                root = self.spans[sids[0]]
                res.append({
                    "trace_id": tid,
                    "name": root.name,
                    "component": root.component,
                    "started_at": root.started_at,
                    "duration_ms": root.duration_ms,
                    "status": root.status,
                    "span_count": len(sids),
                })
        return list(reversed(res))

    # =====================================================================
    # Telemetry & Metrics Collection
    # =====================================================================

    def record_provider_call(self, provider: str, model: str, duration_ms: float, tokens: int, cost_usd: float = 0.0):
        self.metrics["provider_calls"] += 1
        self.metrics["total_tokens_consumed"] += tokens
        self.metrics["total_cost_usd"] += cost_usd
        self.metrics["provider_latencies_ms"].append(duration_ms)
        if len(self.metrics["provider_latencies_ms"]) > 100:
            self.metrics["provider_latencies_ms"].pop(0)

    def get_metrics_summary(self) -> Dict[str, Any]:
        lats = self.metrics["provider_latencies_ms"]
        avg_lat = sum(lats) / len(lats) if lats else 0.0
        p95_lat = sorted(lats)[int(len(lats) * 0.95)] if len(lats) >= 5 else avg_lat
        tools_total = self.metrics["successful_tool_calls"] + self.metrics["failed_tool_calls"]
        tool_success_rate = (self.metrics["successful_tool_calls"] / tools_total * 100.0) if tools_total > 0 else 100.0

        return {
            "total_provider_calls": self.metrics["provider_calls"],
            "avg_latency_ms": round(avg_lat, 1),
            "p95_latency_ms": round(p95_lat, 1),
            "total_tokens": self.metrics["total_tokens_consumed"],
            "estimated_cost_usd": round(self.metrics["total_cost_usd"], 4),
            "tool_executions": tools_total,
            "tool_success_rate_percent": round(tool_success_rate, 1),
            "extension_errors": self.metrics["extension_errors"],
            "mcp_errors": self.metrics["mcp_errors"],
        }

    # =====================================================================
    # Structured Logging & Redaction
    # =====================================================================

    def log(self, level: str, component: str, message: str, trace_id: Optional[str] = None, **extra):
        # Redact secrets
        safe_msg = SECRET_PATTERN.sub(r"\1: [REDACTED]", message)
        entry = LogEntry(
            timestamp=time.time(),
            level=level.upper(),
            component=component,
            message=safe_msg,
            trace_id=trace_id,
            extra=extra,
        )
        self.recent_logs.append(entry)
        if len(self.recent_logs) > self.max_memory_logs:
            self.recent_logs.pop(0)

        # File append
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
        except Exception:
            pass

    def search_logs(self, query: str = "", level: Optional[str] = None, component: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        results = []
        q = query.lower()
        lvl = level.upper() if level else None
        comp = component.lower() if component else None

        for entry in reversed(self.recent_logs):
            if lvl and entry.level != lvl:
                continue
            if comp and entry.component.lower() != comp:
                continue
            if q and q not in entry.message.lower() and q not in entry.component.lower():
                continue
            results.append(entry.to_dict())
            if len(results) >= limit:
                break
        return results

    def export_logs(self, output_path: Optional[str] = None) -> str:
        out = output_path or os.path.join(self.log_dir, f"export_logs_{int(time.time())}.json")
        data = {
            "exported_at": time.time(),
            "metrics": self.get_metrics_summary(),
            "logs": [e.to_dict() for e in self.recent_logs],
            "traces": self.list_recent_traces(30),
        }
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return out

    def get_health_status(self) -> Dict[str, Any]:
        """Aggregate application health status across providers, tools, and memory."""
        metrics = self.get_metrics_summary()
        status = "healthy"
        issues = []

        if metrics["extension_errors"] > 5:
            status = "degraded"
            issues.append(f"{metrics['extension_errors']} extension errors recorded")
        if metrics["mcp_errors"] > 5:
            status = "degraded"
            issues.append(f"{metrics['mcp_errors']} MCP errors recorded")
        if metrics["tool_success_rate_percent"] < 80.0 and metrics["tool_executions"] > 5:
            status = "degraded"
            issues.append(f"Tool success rate is low ({metrics['tool_success_rate_percent']}%)")

        return {
            "status": status,
            "issues": issues,
            "metrics": metrics,
            "active_traces_count": len(self.active_traces),
            "log_entries_count": len(self.recent_logs),
        }


observability_center = ObservabilityCenter.get()

