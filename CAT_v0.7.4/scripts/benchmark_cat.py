#!/usr/bin/env python3
"""
CAT v0.7.9.0 — internal performance benchmark (requirement #37).

Measures REAL latencies of every local pipeline stage:

    request classification / smart routing
    model capability registry build
    memory retrieval (v1 + layered v2, relevance-filtered)
    image validation -> normalization -> encode
    event bus publish/subscribe throughput
    agent tool execution (calculate tool)
    end-to-end agent loop with a scripted model (no network)

Nothing here is fabricated: every number is a wall-clock measurement of
actual code paths on this machine. Run it any time to find bottlenecks:

    python scripts/benchmark_cat.py
"""

import os
import statistics
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calc_terminal import metrics                      # noqa: E402
from calc_terminal import model_router as mr           # noqa: E402
from calc_terminal import event_stream as evs          # noqa: E402
from calc_terminal import fs_cache                     # noqa: E402
from calc_terminal import vision                       # noqa: E402


def bench(label, fn, repeats=30):
    """Runs fn `repeats` times; returns real timing stats in ms."""
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000.0)
    return {
        "label": label,
        "mean_ms": statistics.mean(times),
        "median_ms": statistics.median(times),
        "p95_ms": sorted(times)[max(0, int(round(0.95 * len(times))) - 1)],
        "min_ms": min(times),
    }


def main():
    print("=" * 64)
    print("CAT v0.7.9.0 — pipeline benchmark (real measurements)")
    print("=" * 64)

    rows = []

    # ---- routing ------------------------------------------------------
    prompts = [
        ("simple: 'hello'", "hello"),
        ("simple math: 'what is 12*7'", "what is 12*7"),
        ("coding: React website", "Create a responsive pet shop website "
         "with product cards and a cart"),
        ("multi-agent: architecture review", "Review this project "
         "architecture and propose the safest way to improve it, then "
         "implement and test the changes across the whole codebase"),
        ("debugging", "why is this function failing with a traceback? fix this bug"),
        ("research", "compare the latest react vs vue frameworks with sources"),
    ]
    for label, p in prompts:
        rows.append(bench(f"classify+route  [{label}]", lambda p=p: mr.route(p)))

    # ---- capability registry ------------------------------------------
    def build_registry():
        mr.available_configs(force_refresh=True)
    rows.append(bench("capability registry (primary+backups)", build_registry))

    # ---- memory --------------------------------------------------------
    from calc_terminal import memory as mem_mod
    fd, mem_mod.MEMORY_FILE = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        mem_mod.save(mem_mod._empty())
        for i in range(24):
            mem_mod.add_turn("user", f"question {i} about kinetics and rates", mode="agent")
            mem_mod.add_turn("assistant", f"answer {i}", mode="agent")
        for i in range(10):
            mem_mod.add_fact(f"fact {i}")
        rows.append(bench("memory context (relevance query)",
                          lambda: mem_mod.context_block(mode="agent",
                                                        query="kinetics")))
        rows.append(bench("memory context (no query)",
                          lambda: mem_mod.context_block(mode="agent")))
        from calc_terminal import memory_v2
        mgr = memory_v2.get_manager()
        rows.append(bench("memory_v2 singleton re-fetch", lambda: memory_v2.get_manager()))
        rows.append(bench("memory_v2 relevance retrieval",
                          lambda: mgr.context_block(query="kinetics rates")))
    finally:
        try:
            os.unlink(mem_mod.MEMORY_FILE)
        except OSError:
            pass

    # ---- image pipeline -------------------------------------------------
    if vision.pil_available():
        from PIL import Image
        tmp = tempfile.mkdtemp()
        big = os.path.join(tmp, "big.png")
        Image.new("RGB", (3000, 2200), (90, 120, 200)).save(big)
        small = os.path.join(tmp, "small.png")
        Image.new("RGB", (400, 300), (200, 100, 50)).save(small)
        rows.append(bench("image normalize (large, resize+convert)",
                          lambda: vision.encode_for_model(big), repeats=10))
        rows.append(bench("image normalize (small passthrough)",
                          lambda: vision.encode_for_model(small)))
        rows.append(bench("image classify",
                          lambda: vision.classify_image(small, "extract text")))
    else:
        print("(Pillow not installed — image benchmarks skipped)")

    # ---- event bus -------------------------------------------------------
    evs.stream.subscribe("bench_topic", lambda e: None)

    def publish():
        evs.stream.emit("bench_topic", source="benchmark")
    rows.append(bench("event bus emit+dispatch", publish))

    # ---- fs cache ---------------------------------------------------------
    tmpd = tempfile.mkdtemp()
    for i in range(200):
        open(os.path.join(tmpd, f"f{i}.txt"), "w").write("x")
    builder = lambda: sorted(os.listdir(tmpd))          # noqa: E731
    fs_cache.clear()

    def cached_listing():
        fs_cache.cached_dir_listing(tmpd, builder)
    rows.append(bench("dir listing (cache HIT)", cached_listing))
    fs_cache.invalidate_path(tmpd)
    rows.append(bench("dir listing (cache MISS, real scan)", cached_listing))

    # ---- agent tool + scripted end-to-end loop ----------------------------
    from calc_terminal import agent as cct_agent
    rows.append(bench("tool: calculate 6*7",
                      lambda: cct_agent.TOOLS["calculate"]["run"](
                          {"expression": "6*7"})))

    import json
    from unittest import mock
    responses = [
        json.dumps({"action": "final", "text": "42"}),
    ]

    def scripted_once(*a, **k):
        return iter([responses[0]])

    m = metrics.begin_request("bench-agent-loop")

    def agent_loop():
        with mock.patch.object(cct_agent.aicore, "_stream_ai_once",
                               side_effect=scripted_once):
            cct_agent.run_agent("what is six times seven?", max_steps=2,
                                verbose=False, fast=True)
    rows.append(bench("agent loop (scripted model, fast path)", agent_loop, repeats=5))
    total = m.finish()

    # ---- report ------------------------------------------------------------
    print()
    print(f"{'stage':<48}{'mean':>9}{'median':>9}{'p95':>9}")
    print("-" * 75)
    for r in rows:
        print(f"{r['label']:<48}{r['mean_ms']:>8.2f}ms{r['median_ms']:>8.2f}ms"
              f"{r['p95_ms']:>8.2f}ms")
    print("-" * 75)
    totals = metrics.session_totals()
    print(f"\nsession totals so far: {totals.get('requests', 0)} request(s) recorded,")
    print(f"mean TTFB {totals.get('ttfb_mean_ms', 0):.1f} ms, "
          f"mean total {totals.get('total_mean_ms', 0):.1f} ms")
    print("\nAll numbers above are real wall-clock measurements of this")
    print("machine's execution of the actual CAT code paths.")


if __name__ == "__main__":
    main()
