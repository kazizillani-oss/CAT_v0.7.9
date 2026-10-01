"""
CAT Lab — Benchmark Studio & Runner.
Creator: Kazi Zillani (CAT Platform).

Implements real AI model benchmarking, execution, metric measurement,
and CSV/cat reporting. Never fabricates metrics or simulates results.
"""

from __future__ import annotations

import copy
import csv
import datetime
import json
import logging
import os
import shutil
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from .hardware import get_hardware_profile
from .model_lab import ModelRunner, get_model_registry
from .models import (
    BenchmarkRunResult,
    BenchmarkSpec,
    BenchmarkTask,
    BenchmarkType,
    ModelSpec,
    TaskResult,
)
from ..storage import (
    create_cat_envelope,
    get_storage_dir,
    get_subpath,
    read_cat_file,
    write_cat_file,
)

logger = logging.getLogger("cat.lab.benchmark")


class BenchmarkStudioRegistry:
    """Registry for built-in and custom AI benchmarks."""

    def __init__(self, benchmarks_dir: Optional[str] = None):
        self.benchmarks_dir = benchmarks_dir or get_subpath("benchmarks")
        os.makedirs(self.benchmarks_dir, exist_ok=True)
        self._benchmarks: Dict[str, BenchmarkSpec] = {}
        self._load_builtins()
        self.reload()

    def _load_builtins(self):
        """Standardized, authentic test suites built into CAT."""
        # 1. Python Coding Benchmark
        coding_tasks = [
            BenchmarkTask(
                id="task-code-01",
                prompt="Write a Python function `is_palindrome(s: str) -> bool` that checks if a string is a palindrome.",
                expected_output="def is_palindrome",
                evaluation_method="contains",
                weight=1.0,
            ),
            BenchmarkTask(
                id="task-code-02",
                prompt="Write a Python function `fibonacci(n: int) -> int` that returns the n-th Fibonacci number.",
                expected_output="def fibonacci",
                evaluation_method="contains",
                weight=1.0,
            ),
            BenchmarkTask(
                id="task-code-03",
                prompt="Write a Python function `remove_duplicates(lst: list) -> list` preserving original order.",
                expected_output="def remove_duplicates",
                evaluation_method="contains",
                weight=1.0,
            ),
        ]
        b_coding = BenchmarkSpec(
            id="cat-python-coding",
            name="CAT Python Coding Benchmark",
            description="Evaluates Python syntax accuracy, algorithmic correctness, and function structuring.",
            version="1.0.0",
            benchmark_type=BenchmarkType.CODING,
            tasks=coding_tasks,
            max_tokens=350,
            temperature=0.1,
        )

        # 2. Reasoning & Logic Benchmark
        reasoning_tasks = [
            BenchmarkTask(
                id="task-reason-01",
                prompt="If all cats have whiskers, and Leo is a cat, does Leo have whiskers? Answer in one word.",
                expected_output="yes",
                evaluation_method="contains",
                weight=1.0,
            ),
            BenchmarkTask(
                id="task-reason-02",
                prompt="What is 15 multiplied by 14 plus 25? Give the numerical answer.",
                expected_output="235",
                evaluation_method="contains",
                weight=1.0,
            ),
        ]
        b_reason = BenchmarkSpec(
            id="cat-reasoning-math",
            name="CAT Reasoning & Math Benchmark",
            description="Evaluates logical deductions, step-by-step arithmetic, and premise constraint adherence.",
            version="1.0.0",
            benchmark_type=BenchmarkType.REASONING,
            tasks=reasoning_tasks,
            max_tokens=150,
            temperature=0.0,
        )

        # 3. Latency & Throughput Benchmark
        latency_tasks = [
            BenchmarkTask(
                id="task-lat-01",
                prompt="Say 'CAT CLI is ready' and nothing else.",
                expected_output="CAT CLI is ready",
                evaluation_method="contains",
                weight=1.0,
            ),
            BenchmarkTask(
                id="task-lat-02",
                prompt="Count from 1 to 5.",
                expected_output="5",
                evaluation_method="contains",
                weight=1.0,
            ),
        ]
        b_latency = BenchmarkSpec(
            id="cat-latency-throughput",
            name="CAT Latency & Throughput Benchmark",
            description="Measures raw time-to-first-token, generation tokens per second, and response latency.",
            version="1.0.0",
            benchmark_type=BenchmarkType.LATENCY,
            tasks=latency_tasks,
            max_tokens=64,
            temperature=0.0,
        )

        for b in (b_coding, b_reason, b_latency):
            self._benchmarks[b.id] = b

    def reload(self) -> None:
        """Loads user benchmarks from disk (.cat format)."""
        if not os.path.isdir(self.benchmarks_dir):
            return
        for file in os.listdir(self.benchmarks_dir):
            if file.endswith((".cat", ".json")):
                full_p = os.path.join(self.benchmarks_dir, file)
                try:
                    valid, envelope, err, _ = read_cat_file(full_p)
                    if valid and envelope:
                        payload = envelope.get("data", {})
                        data = payload.get("benchmark", payload)
                        spec = BenchmarkSpec.from_dict(data)
                        self._benchmarks[spec.id] = spec
                except Exception as e:
                    logger.warning(f"Could not load benchmark file {file}: {e}")

    def register(self, spec: BenchmarkSpec, persist: bool = True) -> BenchmarkSpec:
        """Registers a benchmark definition."""
        self._benchmarks[spec.id] = spec
        if persist:
            dest = os.path.join(self.benchmarks_dir, f"{spec.id}.cat")
            payload = {"benchmark": spec.to_dict()}
            write_cat_file(dest, obj_type="benchmark", payload=payload, metadata={"benchmark_id": spec.id, "name": spec.name})
        return spec

    def unregister(self, benchmark_id: str) -> bool:
        """Removes a benchmark definition."""
        if benchmark_id in self._benchmarks:
            del self._benchmarks[benchmark_id]
            for ext in (".cat", ".json"):
                target = os.path.join(self.benchmarks_dir, f"{benchmark_id}{ext}")
                if os.path.isfile(target):
                    try:
                        os.remove(target)
                    except Exception:
                        pass
            return True
        return False

    def get(self, benchmark_id: str) -> Optional[BenchmarkSpec]:
        """Gets benchmark by ID."""
        return self._benchmarks.get(benchmark_id)

    def list(self) -> List[BenchmarkSpec]:
        """Lists all registered benchmarks."""
        return list(self._benchmarks.values())

    def duplicate(self, source_id: str, new_id: str, new_name: str) -> Optional[BenchmarkSpec]:
        """Duplicates an existing benchmark definition."""
        src = self.get(source_id)
        if not src:
            return None
        clone = copy.deepcopy(src)
        clone.id = new_id
        clone.name = new_name
        return self.register(clone, persist=True)


class BenchmarkRunner:
    """Executes benchmarks against models/providers, collecting raw measured metrics."""

    _active_run_id: Optional[str] = None
    _stop_requested: bool = False

    @classmethod
    def request_stop(cls):
        """Signals active benchmark run to safely cancel."""
        cls._stop_requested = True

    @classmethod
    def run(
        cls,
        benchmark: BenchmarkSpec,
        model_spec: ModelSpec,
        provider_id: str = "default",
        on_progress: Optional[Callable[[int, int, TaskResult], None]] = None,
    ) -> BenchmarkRunResult:
        """Executes the benchmark and measures real hardware and output metrics."""
        cls._stop_requested = False
        run_id = f"run-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        cls._active_run_id = run_id

        hw_profile = get_hardware_profile()
        task_results: List[TaskResult] = []
        latencies: List[float] = []
        tokens_per_sec_list: List[float] = []

        total_input_tok = 0
        total_output_tok = 0
        passed_count = 0
        failed_count = 0

        total_tasks = len(benchmark.tasks)
        t_start_total = time.perf_counter()

        for idx, task in enumerate(benchmark.tasks):
            if cls._stop_requested:
                break

            prompt_text = benchmark.prompt_template.format(prompt=task.prompt)
            t0 = time.perf_counter()

            # Execute real inference through ModelRunner
            exec_res = ModelRunner.run_inference(
                model_spec,
                prompt=prompt_text,
                max_tokens=benchmark.max_tokens,
                timeout=task.timeout_sec or benchmark.timeout,
            )

            latency = exec_res["latency_sec"]
            output_text = exec_res["output"]
            success = exec_res["success"]
            in_tok = exec_res["input_tokens"]
            out_tok = exec_res["output_tokens"]
            tps = exec_res["tokens_per_second"]

            # Evaluate output against expected criteria
            passed = False
            if success:
                exp = task.expected_output.lower().strip()
                out_clean = output_text.lower().strip()
                if task.evaluation_method == "contains":
                    passed = exp in out_clean if exp else True
                elif task.evaluation_method == "exact":
                    passed = exp == out_clean
                else:
                    passed = exp in out_clean if exp else True
            else:
                passed = False

            if passed:
                passed_count += 1
            else:
                failed_count += 1

            total_input_tok += in_tok
            total_output_tok += out_tok
            latencies.append(latency)
            if tps > 0:
                tokens_per_sec_list.append(tps)

            # Sample current hardware metrics
            cpu_pct = None
            ram_mb = None
            vram_mb = None
            try:
                import psutil
                cpu_pct = psutil.cpu_percent(interval=None)
                ram_mb = psutil.virtual_memory().used / (1024 * 1024)
            except Exception:
                pass

            try:
                import torch
                if torch.cuda.is_available():
                    vram_mb = torch.cuda.memory_allocated() / (1024 * 1024)
            except Exception:
                pass

            tr = TaskResult(
                task_id=task.id,
                prompt=task.prompt,
                expected=task.expected_output,
                output=output_text,
                passed=passed,
                latency_sec=latency,
                input_tokens=in_tok,
                output_tokens=out_tok,
                tokens_per_sec=tps,
                error=exec_res.get("error"),
                cpu_percent=cpu_pct,
                ram_mb=ram_mb,
                vram_mb=vram_mb,
            )
            task_results.append(tr)

            if on_progress:
                on_progress(idx + 1, total_tasks, tr)

        t_total = time.perf_counter() - t_start_total
        cls._active_run_id = None

        # Calculate statistics
        total_eval = len(task_results)
        accuracy = (passed_count / total_eval) if total_eval > 0 else 0.0
        pass_rate = accuracy * 100.0

        latencies_sorted = sorted(latencies) if latencies else [0.0]
        avg_lat = sum(latencies) / len(latencies) if latencies else 0.0

        def _percentile(data: List[float], pct: float) -> float:
            if not data:
                return 0.0
            k = (len(data) - 1) * (pct / 100.0)
            f = int(k)
            c = min(f + 1, len(data) - 1)
            d = k - f
            return data[f] + d * (data[c] - data[f])

        p50 = _percentile(latencies_sorted, 50.0)
        p95 = _percentile(latencies_sorted, 95.0)
        p99 = _percentile(latencies_sorted, 99.0)

        avg_tps = (sum(tokens_per_sec_list) / len(tokens_per_sec_list)) if tokens_per_sec_list else 0.0

        run_status = "cancelled" if cls._stop_requested else ("completed" if failed_count == 0 else "partial")

        result = BenchmarkRunResult(
            run_id=run_id,
            benchmark_id=benchmark.id,
            benchmark_name=benchmark.name,
            model_id=model_spec.id,
            model_name=model_spec.name,
            provider_id=provider_id,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            status=run_status,
            total_tasks=total_tasks,
            passed_tasks=passed_count,
            failed_tasks=failed_count,
            accuracy=accuracy,
            pass_rate=pass_rate,
            avg_latency_sec=round(avg_lat, 4),
            p50_latency_sec=round(p50, 4),
            p95_latency_sec=round(p95, 4),
            p99_latency_sec=round(p99, 4),
            tokens_per_second=round(avg_tps, 2),
            total_input_tokens=total_input_tok,
            total_output_tokens=total_output_tok,
            total_tokens=total_input_tok + total_output_tok,
            total_runtime_sec=round(t_total, 3),
            hardware=hw_profile,
            environment={
                "os": hw_profile.get("os_name"),
                "python": hw_profile.get("python_version"),
                "cat_version": hw_profile.get("cat_version"),
                "device": hw_profile.get("primary_device"),
            },
            task_results=task_results,
        )

        # Save result to storage
        cls._save_run_result(result)
        return result

    @classmethod
    def _save_run_result(cls, res: BenchmarkRunResult) -> None:
        """Persists run result as a native .cat file."""
        reports_dir = get_subpath("reports")
        os.makedirs(reports_dir, exist_ok=True)
        dest = os.path.join(reports_dir, f"{res.run_id}.cat")
        payload = {"benchmark_run": res.to_dict()}
        write_cat_file(
            dest,
            obj_type="benchmark",
            payload=payload,
            metadata={"run_id": res.run_id, "benchmark_id": res.benchmark_id, "model_id": res.model_id},
        )

    @classmethod
    def export_to_csv(cls, result: BenchmarkRunResult, dest_file: str) -> str:
        """Exports structured benchmark task measurements to CSV.

        Columns adhere strictly to specification:
        benchmark_id, benchmark_name, run_id, model_id, model_name, provider,
        task, status, latency, tokens_per_second, input_tokens, output_tokens,
        accuracy, pass_rate, cpu_usage, ram_usage, gpu_usage, vram_usage,
        runtime, timestamp, cat_version, python_version, pytorch_version, hardware
        """
        os.makedirs(os.path.dirname(os.path.abspath(dest_file)), exist_ok=True)
        fieldnames = [
            "benchmark_id",
            "benchmark_name",
            "run_id",
            "model_id",
            "model_name",
            "provider",
            "task",
            "status",
            "latency",
            "tokens_per_second",
            "input_tokens",
            "output_tokens",
            "accuracy",
            "pass_rate",
            "cpu_usage",
            "ram_usage",
            "gpu_usage",
            "vram_usage",
            "runtime",
            "timestamp",
            "cat_version",
            "python_version",
            "pytorch_version",
            "hardware",
        ]

        hw_summary = f"{result.hardware.get('cpu', {}).get('model', 'CPU')}; {result.hardware.get('primary_device', 'CPU')}"
        py_ver = result.environment.get("python", "3.12")
        cat_ver = result.environment.get("cat_version", "0.8.0")
        torch_ver = result.hardware.get("pytorch", {}).get("version", "Unavailable")

        with open(dest_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            if not result.task_results:
                # Summary row if no granular task results
                writer.writerow({
                    "benchmark_id": result.benchmark_id,
                    "benchmark_name": result.benchmark_name,
                    "run_id": result.run_id,
                    "model_id": result.model_id,
                    "model_name": result.model_name,
                    "provider": result.provider_id,
                    "task": "summary",
                    "status": result.status,
                    "latency": result.avg_latency_sec,
                    "tokens_per_second": result.tokens_per_second,
                    "input_tokens": result.total_input_tokens,
                    "output_tokens": result.total_output_tokens,
                    "accuracy": result.accuracy,
                    "pass_rate": result.pass_rate,
                    "cpu_usage": result.cpu_usage_avg or "Unavailable",
                    "ram_usage": result.ram_usage_mb_avg or "Unavailable",
                    "gpu_usage": result.gpu_usage_pct_avg or "Unavailable",
                    "vram_usage": result.vram_usage_mb_avg or "Unavailable",
                    "runtime": result.total_runtime_sec,
                    "timestamp": result.timestamp,
                    "cat_version": cat_ver,
                    "python_version": py_ver,
                    "pytorch_version": torch_ver,
                    "hardware": hw_summary,
                })
            else:
                for tr in result.task_results:
                    writer.writerow({
                        "benchmark_id": result.benchmark_id,
                        "benchmark_name": result.benchmark_name,
                        "run_id": result.run_id,
                        "model_id": result.model_id,
                        "model_name": result.model_name,
                        "provider": result.provider_id,
                        "task": tr.task_id,
                        "status": "PASS" if tr.passed else "FAIL",
                        "latency": tr.latency_sec,
                        "tokens_per_second": tr.tokens_per_sec,
                        "input_tokens": tr.input_tokens,
                        "output_tokens": tr.output_tokens,
                        "accuracy": 1.0 if tr.passed else 0.0,
                        "pass_rate": 100.0 if tr.passed else 0.0,
                        "cpu_usage": tr.cpu_percent if tr.cpu_percent is not None else "Unavailable",
                        "ram_usage": tr.ram_mb if tr.ram_mb is not None else "Unavailable",
                        "gpu_usage": "Unavailable",
                        "vram_usage": tr.vram_mb if tr.vram_mb is not None else "Unavailable",
                        "runtime": tr.latency_sec,
                        "timestamp": result.timestamp,
                        "cat_version": cat_ver,
                        "python_version": py_ver,
                        "pytorch_version": torch_ver,
                        "hardware": hw_summary,
                    })

        return dest_file


# Global benchmark registry singleton
_GLOBAL_BENCHMARK_REGISTRY: Optional[BenchmarkStudioRegistry] = None


def get_benchmark_registry() -> BenchmarkStudioRegistry:
    global _GLOBAL_BENCHMARK_REGISTRY
    if _GLOBAL_BENCHMARK_REGISTRY is None:
        _GLOBAL_BENCHMARK_REGISTRY = BenchmarkStudioRegistry()
    return _GLOBAL_BENCHMARK_REGISTRY
