"""
CAT Lab — Benchmark Visualizer & Multi-Model Comparison.
Creator: Kazi Zillani (CAT Platform).

Provides terminal-native Unicode/ASCII charts and honest, multi-model
comparison tables with fairness & comparability discrepancy warnings.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from .models import BenchmarkRunResult


def render_ascii_bar(value: float, max_val: float, bar_width: int = 24, fill_char: str = "█") -> str:
    """Renders a single horizontal bar."""
    if max_val <= 0:
        return ""
    ratio = min(1.0, max(0.0, value / max_val))
    filled_len = int(round(ratio * bar_width))
    return fill_char * filled_len + "░" * (bar_width - filled_len)


def render_benchmark_report_card(result: BenchmarkRunResult, width: int = 70) -> str:
    """Generates a terminal-friendly summary card with metrics and bar charts."""
    lines = [
        "=" * width,
        f"  CAT LAB — BENCHMARK REPORT: {result.benchmark_name.upper()}",
        "=" * width,
        f"  Run ID       : {result.run_id}",
        f"  Model        : {result.model_name} ({result.model_id})",
        f"  Provider     : {result.provider_id}",
        f"  Timestamp    : {result.timestamp}",
        f"  Status       : {result.status.upper()}",
        f"  Tasks        : {result.passed_tasks}/{result.total_tasks} passed ({result.failed_tasks} failed)",
        "-" * width,
        "  [CORE METRICS]",
        f"    Pass Rate  : {result.pass_rate:5.1f}%  [{render_ascii_bar(result.pass_rate, 100.0, 20)}]",
        f"    Avg Latency: {result.avg_latency_sec:5.2f}s  (p50: {result.p50_latency_sec:.2f}s, p95: {result.p95_latency_sec:.2f}s)",
        f"    Throughput : {result.tokens_per_second:5.1f} tok/s",
        f"    Total Tok  : {result.total_tokens} tokens ({result.total_input_tokens} in / {result.total_output_tokens} out)",
        f"    Total Time : {result.total_runtime_sec:5.2f}s",
        "-" * width,
        "  [HARDWARE ENVIRONMENT AT RUN]",
        f"    Device     : {result.environment.get('device', 'CPU')}",
        f"    CPU        : {result.hardware.get('cpu', {}).get('model', 'Unknown CPU')}",
        f"    GPU        : {result.hardware.get('gpu', {}).get('name', 'None')}",
        f"    Python     : v{result.environment.get('python', 'Unknown')}",
        "=" * width,
    ]
    return "\n".join(lines)


def render_multi_model_comparison(results: List[BenchmarkRunResult], width: int = 78) -> str:
    """Renders a comparative table across multiple benchmark runs with fairness warnings."""
    if not results:
        return "No benchmark results provided for comparison."

    lines = [
        "=" * width,
        "                   CAT LAB — MULTI-MODEL COMPARISON",
        "=" * width,
        f"  {'Model Name':<20} | {'Pass Rate':<9} | {'Avg Lat':<8} | {'p95 Lat':<8} | {'Tokens/s':<9} | {'Device'}",
        "-" * width,
    ]

    devices_seen = set()
    quantizations_seen = set()
    max_tps = max((r.tokens_per_second for r in results), default=1.0) or 1.0

    for r in results:
        dev = r.environment.get("device", "CPU")
        devices_seen.add(dev)
        lines.append(
            f"  {r.model_name[:20]:<20} | "
            f"{r.pass_rate:6.1f}%  | "
            f"{r.avg_latency_sec:6.2f}s | "
            f"{r.p95_latency_sec:6.2f}s | "
            f"{r.tokens_per_second:7.1f}   | "
            f"{dev}"
        )

    lines.append("-" * width)
    lines.append("  [THROUGHPUT COMPARISON (tok/s)]")
    for r in results:
        bar = render_ascii_bar(r.tokens_per_second, max_tps, bar_width=20)
        lines.append(f"    {r.model_name[:16]:<16} : {bar} {r.tokens_per_second:.1f} tok/s")

    # Fairness & Comparability Checks
    warnings = []
    if len(devices_seen) > 1:
        dev_list = ", ".join(sorted(devices_seen))
        warnings.append(
            f"Hardware Discrepancy: Models ran on differing compute devices ({dev_list}). "
            "Raw throughput and latencies are not directly comparable."
        )

    if warnings:
        lines.append("-" * width)
        lines.append("  [FAIRNESS & COMPARABILITY NOTICES]")
        for w in warnings:
            lines.append(f"    ⚠ {w}")

    lines.append("=" * width)
    lines.append("Note: CAT displays raw measured metrics without subjective ranking bias.")
    return "\n".join(lines)
