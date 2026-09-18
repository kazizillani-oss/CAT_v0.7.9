"""
CAT v0.7.9.0 — metrics.py: real per-request latency instrumentation.

Requirement: "Add internal timing information ... Do not guess where the
delay comes from." This module is the single place every pipeline stage
reports into. It records REAL wall-clock measurements — never fabricated
numbers — for:

    request_received_ms    memory_retrieval_ms   routing_ms
    model_first_token_ms   tool_execution_ms     agent_loop_ms
    final_response_ms      vision_ms

plus per-request counters (model_calls, tool_calls) and a rolling
session history so bottlenecks can be found from actual data.

Design constraints:

* Thread-safe — the UI runs agent work on worker threads while the
  Textual main thread reads the session history (e.g. the /perf view).
* Zero-overhead when disabled? No: measurements are cheap (time.perf_counter
  pairs), always on. The cost is nanoseconds per stage.
* Never raises from the recording side — metrics are observability, and a
  broken recorder must not be able to break the request path.

Usage:
    from . import metrics

    m = metrics.begin_request()
    m.mark_stage("memory_retrieval", start=..., end=...)   # explicit pair
    with m.stage("routing"):                                # context form
        ...
    m.count_model_call(); m.count_tool_call()
    m.finish()                                              # stamps total
    print(m.summary_lines())                                # real numbers only

A threading.local "current" handle lets deep code (agent.py, aicore.py)
record without plumbing an object through every signature; callers that
have the object should pass it directly instead.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import threading
import time
from collections import deque
from typing import Dict, List, Optional

# Stage keys -> canonical millisecond field names. Anything recorded under
# an unknown key still lands in `stages_ms`; these are just the documented
# vocabulary shared by the whole pipeline.
STAGE_KEYS = (
    "request_received", "memory_retrieval", "routing",
    "model_first_token", "tool_execution", "agent_loop",
    "vision", "final_response", "history_summarize",
)

HISTORY_LIMIT = 50  # rolling window of finished requests


def _now_ms() -> float:
    return time.perf_counter() * 1000.0


class RequestMetrics:
    """One user request's real timing record."""

    __slots__ = ("request_id", "_t0", "_stage_pairs", "_open_stages",
                 "model_calls", "tool_calls", "streamed_chunks",
                 "first_token_ms", "total_ms", "route_path", "task_types",
                 "model_used", "finished", "_lock")

    def __init__(self, request_id: Optional[str] = None):
        self.request_id = request_id or f"req-{int(time.time() * 1000)}-{id(self) % 100000}"
        self._t0 = time.perf_counter()
        self._stage_pairs: Dict[str, List[float]] = {}
        self._open_stages: Dict[str, float] = {}
        self.model_calls = 0
        self.tool_calls = 0
        self.streamed_chunks = 0
        self.first_token_ms: Optional[float] = None
        self.total_ms: Optional[float] = None
        self.route_path = ""
        self.task_types: List[str] = []
        self.model_used = ""
        self.finished = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------- stages --
    def stage_start(self, key: str) -> None:
        """Mark the beginning of a stage (for non-context-manager call
        sites). A stage may open/close multiple times; durations add up."""
        try:
            with self._lock:
                self._open_stages[key] = time.perf_counter()
        except Exception:
            pass

    def stage_end(self, key: str) -> None:
        try:
            with self._lock:
                t0 = self._open_stages.pop(key, None)
                if t0 is None:
                    return
                self._stage_pairs.setdefault(key, []).append(
                    (time.perf_counter() - t0) * 1000.0)
                if key == "model_first_token" and self.first_token_ms is None:
                    self.first_token_ms = self._stage_pairs[key][-1]
        except Exception:
            pass

    def mark_stage(self, key: str, start: float, end: Optional[float] = None) -> None:
        """Record one completed stage duration from explicit timestamps
        (time.perf_counter values)."""
        try:
            end = time.perf_counter() if end is None else end
            with self._lock:
                self._stage_pairs.setdefault(key, []).append(max(0.0, (end - start) * 1000.0))
                if key == "model_first_token" and self.first_token_ms is None:
                    self.first_token_ms = self._stage_pairs[key][-1]
        except Exception:
            pass

    class _StageCtx:
        __slots__ = ("m", "key")

        def __init__(self, m: "RequestMetrics", key: str):
            self.m = m
            self.key = key

        def __enter__(self):
            self.m.stage_start(self.key)
            return self.m

        def __exit__(self, exc_type, exc, tb):
            self.m.stage_end(self.key)
            return False

    def stage(self, key: str) -> "RequestMetrics._StageCtx":
        """Context manager form: `with m.stage("routing"): ...`."""
        return RequestMetrics._StageCtx(self, key)

    def stages_ms(self) -> Dict[str, float]:
        """Total recorded milliseconds per stage key (summed)."""
        out: Dict[str, float] = {}
        try:
            with self._lock:
                for k, vals in self._stage_pairs.items():
                    out[k] = sum(vals)
        except Exception:
            pass
        return out

    # ----------------------------------------------------------- counters --
    def count_model_call(self, n: int = 1) -> None:
        try:
            with self._lock:
                self.model_calls += n
        except Exception:
            pass

    def count_tool_call(self, n: int = 1) -> None:
        try:
            with self._lock:
                self.tool_calls += n
        except Exception:
            pass

    def count_chunk(self, n: int = 1) -> None:
        try:
            with self._lock:
                self.streamed_chunks += n
        except Exception:
            pass

    def note_first_token(self) -> None:
        """Called by the streaming layer on the very first real token.
        Records time-to-first-token relative to request start."""
        try:
            with self._lock:
                if self.first_token_ms is None:
                    self.first_token_ms = (time.perf_counter() - self._t0) * 1000.0
        except Exception:
            pass

    # ------------------------------------------------------------- finish --
    def finish(self, *args, **kwargs) -> float:
        """Stamps total latency and files this request into the session
        history. Safely accepts optional arguments (*args, **kwargs) without error.
        Returns total ms."""
        try:
            with self._lock:
                if self.total_ms is None:
                    self.total_ms = (time.perf_counter() - self._t0) * 1000.0
                self.finished = True
        except Exception:
            pass
        try:
            _record_finished(self)
        except Exception:
            pass
        return self.total_ms or 0.0

    # ------------------------------------------------------------ reporting --
    def as_dict(self) -> Dict[str, object]:
        stages = self.stages_ms()

        def _ms(k: str) -> float:
            return round(stages.get(k, 0.0), 1)

        return {
            "request_id": self.request_id,
            "path": self.route_path,
            "task_types": list(self.task_types),
            "model": self.model_used,
            "request_received_ms": round(self.total_ms or 0.0, 1),
            "memory_retrieval_ms": _ms("memory_retrieval"),
            "routing_ms": _ms("routing"),
            "history_summarize_ms": _ms("history_summarize"),
            "model_first_token_ms": round(self.first_token_ms or 0.0, 1),
            "tool_execution_ms": _ms("tool_execution"),
            "agent_loop_ms": _ms("agent_loop"),
            "vision_ms": _ms("vision"),
            "final_response_ms": round((self.total_ms or 0.0)
                                       - sum(v for k, v in stages.items()
                                             if k != "final_response"), 1)
            if self.total_ms is not None else None,
            "model_calls": self.model_calls,
            "tool_calls": self.tool_calls,
            "streamed_chunks": self.streamed_chunks,
        }

    def summary_lines(self) -> List[str]:
        """Human-readable REAL measurement lines for the completion card.
        Only measured values appear — nothing is invented."""
        d = self.as_dict()
        bits = []
        if d["model_first_token_ms"]:
            bits.append(f"TTFB {d['model_first_token_ms']:.0f}ms")
        for label, key in (("route", None), ("memory", "memory_retrieval_ms"),
                           ("tools", "tool_execution_ms"), ("loop", "agent_loop_ms"),
                           ("vision", "vision_ms")):
            if key and d.get(key):
                bits.append(f"{label} {d[key]:.0f}ms")
        calls = f"{d['model_calls']} model call(s)"
        if d["tool_calls"]:
            calls += f", {d['tool_calls']} tool call(s)"
        if d["path"]:
            calls = f"[{d['path']}] " + calls
        lines = ["[dim]\u23f1 Real timings: " + ("  \u00b7  ".join(bits) if bits else "n/a") + "[/dim]",
                 "[dim]\U0001f4ca " + calls + "[/dim]"]
        return lines


# ------------------------------------------------------------- session log --

_history_lock = threading.Lock()
_history: deque = deque(maxlen=HISTORY_LIMIT)


def _record_finished(m: RequestMetrics) -> None:
    with _history_lock:
        _history.append(m)


def get_recent(limit: int = 10) -> List[RequestMetrics]:
    with _history_lock:
        return list(_history)[-limit:]


def session_totals() -> Dict[str, float]:
    """Aggregate REAL session-wide measurements (mean/median/p95 over the
    rolling window). Used by /perf and scripts/benchmark_cat.py."""
    with _history_lock:
        items = list(_history)

    def _stats(vals: List[float]) -> Dict[str, float]:
        if not vals:
            return {"mean": 0.0, "p95": 0.0}
        s = sorted(vals)
        mean = sum(s) / len(s)
        p95 = s[min(len(s) - 1, int(round(0.95 * len(s))) - 1)] if s else 0.0
        return {"mean": mean, "p95": p95}

    out: Dict[str, float] = {
        "requests": len(items),
        "model_calls": sum(i.model_calls for i in items),
        "tool_calls": sum(i.tool_calls for i in items),
        "total_mean_ms": _stats([i.total_ms or 0.0 for i in items])["mean"],
        "ttfb_mean_ms": _stats([i.first_token_ms or 0.0 for i in items])["mean"],
        "ttfb_p95_ms": _stats([i.first_token_ms or 0.0 for i in items])["p95"],
    }
    agg: Dict[str, List[float]] = {}
    for it in items:
        for k, v in it.stages_ms().items():
            agg.setdefault(k, []).append(v)
    for k, vals in agg.items():
        st = _stats(vals)
        out[f"{k}_mean_ms"] = st["mean"]
    return out


# ------------------------------------------------------ thread-local current --

_local = threading.local()


def begin_request(request_id: Optional[str] = None) -> RequestMetrics:
    """Starts a fresh RequestMetrics and binds it to the calling thread as
    'current' (worker threads run one request at a time)."""
    m = RequestMetrics(request_id)
    _local.current = m
    return m


def current() -> Optional[RequestMetrics]:
    """The calling thread's active request, if any. Deep code uses this to
    record without signature changes; returns None outside a request."""
    return getattr(_local, "current", None)


def clear_current() -> None:
    _local.current = None


def format_duration(ms: Optional[float]) -> str:
    if ms is None or ms <= 0:
        return "n/a"
    if ms < 1000:
        return f"{ms:.0f} ms"
    return f"{ms / 1000:.2f} s"
