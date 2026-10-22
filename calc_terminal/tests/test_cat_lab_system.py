"""
Tests for CAT Lab — Benchmark Studio, Model Lab, Hardware Profiler & ML Environment.
Creator: Kazi Zillani (CAT Platform).
"""

import csv
import json
import os
import shutil
import sys
import tempfile
import time
import pytest

from calc_terminal.lab.hardware import (
    detect_cuda_info,
    detect_nodejs_version,
    detect_pytorch_info,
    get_cpu_status_text,
    get_gpu_status_text,
    get_hardware_profile,
    get_hardware_status_text,
    get_memory_status_text,
)
from calc_terminal.lab.models import (
    BenchmarkRunResult,
    BenchmarkSpec,
    BenchmarkTask,
    BenchmarkType,
    DatasetFormat,
    DatasetSpec,
    ExperimentSpec,
    ExperimentStatus,
    ModelCompatibilityReport,
    ModelFramework,
    ModelSpec,
    ModelStatus,
    ModelType,
    TaskResult,
    TrainingProgress,
)
from calc_terminal.lab.model_lab import (
    ModelLabRegistry,
    ModelRunner,
    check_compatibility,
)
from calc_terminal.lab.benchmark_studio import (
    BenchmarkRunner,
    BenchmarkStudioRegistry,
)
from calc_terminal.lab.datasets import (
    DatasetRegistry,
)
from calc_terminal.lab.experiments import (
    ExperimentQueue,
    ExperimentTracker,
)
from calc_terminal.lab.training import (
    PyTorchTrainer,
    TrainingSafetyLimits,
)
from calc_terminal.lab.visualizer import (
    render_ascii_bar,
    render_benchmark_report_card,
    render_multi_model_comparison,
)
from calc_terminal.lab.stylesheets import (
    BenchmarkStylesheet,
    get_stylesheet_manager,
)
from calc_terminal.cli_commands import (
    benchmark_cli,
    cat_file_cli,
    dataset_cli,
    experiment_cli,
    hardware_cli,
    lab_cli,
    model_cli,
)


@pytest.fixture
def temp_lab_dir():
    d = tempfile.mkdtemp(prefix="cat_lab_test_")
    old_env = os.environ.get("CAT_STORAGE_DIR")
    os.environ["CAT_STORAGE_DIR"] = d
    yield d
    if old_env:
        os.environ["CAT_STORAGE_DIR"] = old_env
    else:
        os.environ.pop("CAT_STORAGE_DIR", None)
    try:
        shutil.rmtree(d, ignore_errors=True)
    except Exception:
        pass


# =============================================================================
# 1. Hardware Profiler Tests
# =============================================================================

def test_hardware_profiler_detection():
    """Verify hardware profile returns valid structure without throwing exceptions."""
    profile = get_hardware_profile(force_refresh=True)
    assert "cpu" in profile
    assert "gpu" in profile
    assert "ram" in profile
    assert "storage" in profile
    assert "cuda" in profile
    assert "pytorch" in profile
    assert "primary_device" in profile

    assert profile["cpu"]["logical_cores"] >= 1
    assert profile["ram"]["total_gb"] > 0.0

    # Test formatted text outputs
    status_text = get_hardware_status_text()
    assert "CAT HARDWARE PROFILER" in status_text
    assert profile["primary_device"] in status_text

    gpu_text = get_gpu_status_text()
    assert "CAT GPU PROFILER" in gpu_text

    cpu_text = get_cpu_status_text()
    assert "CAT CPU PROFILER" in cpu_text

    mem_text = get_memory_status_text()
    assert "CAT MEMORY PROFILER" in mem_text


def test_cuda_and_pytorch_detectors():
    """Verify CUDA and PyTorch detectors return safe typed dictionaries."""
    c_info = detect_cuda_info()
    assert isinstance(c_info["available"], bool)
    assert isinstance(c_info["device_count"], int)

    p_info = detect_pytorch_info()
    assert isinstance(p_info["installed"], bool)
    assert isinstance(p_info["cuda_available"], bool)
    assert p_info["preferred_device"] in ("cuda", "mps", "cpu")

    node_ver = detect_nodejs_version()
    assert isinstance(node_ver, str)


# =============================================================================
# 2. Model Lab & Compatibility Tests
# =============================================================================

def test_model_lab_registry_and_persistence(temp_lab_dir):
    """Verify ModelLabRegistry registers, searches, duplicates, and persists models."""
    models_dir = os.path.join(temp_lab_dir, "models")
    reg = ModelLabRegistry(models_dir=models_dir)

    # Check built-in reference models
    builtins = reg.list()
    assert len(builtins) >= 3
    assert any(m.id == "deepseek-r1-local" for m in builtins)

    # Register custom model
    spec = ModelSpec(
        id="custom-vision-v1",
        name="Custom Vision ViT",
        model_type=ModelType.VISION,
        framework=ModelFramework.PYTORCH,
        expected_vram_gb=2.0,
        expected_ram_gb=4.0,
        capabilities=["vision", "classification"],
        status=ModelStatus.CUSTOM,
    )
    reg.register(spec, persist=True)

    # Verify disk persistence as .cat
    target_cat = os.path.join(models_dir, "custom-vision-v1.cat")
    assert os.path.isfile(target_cat)

    # Search
    matches = reg.search(query="vision")
    assert len(matches) >= 1
    assert matches[0].id == "custom-vision-v1"

    # Duplicate
    clone = reg.duplicate("custom-vision-v1", "custom-vision-v2", "Custom Vision ViT v2")
    assert clone is not None
    assert clone.id == "custom-vision-v2"
    assert reg.get("custom-vision-v2") is not None

    # Unregister
    assert reg.unregister("custom-vision-v2") is True
    assert reg.get("custom-vision-v2") is None


def test_model_compatibility_checks():
    """Verify model compatibility checks handle RAM, VRAM, and runtime requirements."""
    mock_hw = {
        "ram": {"total_gb": 16.0, "available_gb": 8.0},
        "gpu": {"detected": False, "vram_total_gb": 0.0, "vram_free_gb": 0.0},
        "cuda": {"available": False},
        "pytorch": {"installed": False},
    }

    # 1. Fits within RAM
    m_ok = ModelSpec(id="m1", name="Light Model", expected_ram_gb=2.0, expected_vram_gb=0.0, framework=ModelFramework.OLLAMA)
    r_ok = check_compatibility(m_ok, mock_hw)
    assert r_ok.status in ("Compatible", "Probably Compatible")
    assert r_ok.ram_ok is True

    # 2. Exceeds host RAM
    m_huge = ModelSpec(id="m2", name="Massive Model", expected_ram_gb=64.0, framework=ModelFramework.OLLAMA)
    r_huge = check_compatibility(m_huge, mock_hw)
    assert r_huge.status == "Insufficient RAM"
    assert r_huge.compatible is False

    # 3. Missing PyTorch runtime
    m_torch = ModelSpec(id="m3", name="PyTorch Model", expected_ram_gb=2.0, framework=ModelFramework.PYTORCH)
    r_torch = check_compatibility(m_torch, mock_hw)
    assert r_torch.status == "Missing Runtime"
    assert r_torch.runtime_ok is False


def test_model_capacity_progression():
    """Verify progressive capacity testing across token tiers."""
    spec = ModelSpec(
        id="test-model",
        name="Test Model",
        framework=ModelFramework.OLLAMA,
        context_size=2048,
    )
    cap_res = ModelRunner.run_capacity_test(spec, max_tokens_limit=500, timeout=1.0)
    assert cap_res["model_id"] == "test-model"
    assert "tier_results" in cap_res
    assert len(cap_res["tier_results"]) == 4


# =============================================================================
# 3. Benchmark Studio & Runner Tests
# =============================================================================

def test_benchmark_studio_registry(temp_lab_dir):
    """Verify BenchmarkStudioRegistry registers and manages test suites."""
    b_dir = os.path.join(temp_lab_dir, "benchmarks")
    reg = BenchmarkStudioRegistry(benchmarks_dir=b_dir)

    # Built-in benchmarks
    blist = reg.list()
    assert len(blist) >= 3
    assert any(b.id == "cat-python-coding" for b in blist)

    # Register custom benchmark
    spec = BenchmarkSpec(
        id="custom-math-bench",
        name="Custom Math Benchmark",
        benchmark_type=BenchmarkType.REASONING,
        tasks=[
            BenchmarkTask(id="task-01", prompt="What is 10 + 20?", expected_output="30"),
            BenchmarkTask(id="task-02", prompt="What is 50 / 2?", expected_output="25"),
        ],
    )
    reg.register(spec, persist=True)

    # Verify persistence
    assert os.path.isfile(os.path.join(b_dir, "custom-math-bench.cat"))
    assert reg.get("custom-math-bench") is not None


def test_benchmark_runner_and_csv_export(temp_lab_dir):
    """Verify real benchmark execution, metric gathering, and CSV export."""
    bench = BenchmarkSpec(
        id="test-mini-bench",
        name="Test Mini Benchmark",
        tasks=[
            BenchmarkTask(id="t1", prompt="Return hello", expected_output="hello"),
            BenchmarkTask(id="t2", prompt="Return world", expected_output="world"),
        ],
    )
    model = ModelSpec(id="test-agent", name="Test Agent", framework="custom")

    # Run benchmark
    result = BenchmarkRunner.run(bench, model)
    assert result.benchmark_id == "test-mini-bench"
    assert result.total_tasks == 2
    assert result.total_runtime_sec >= 0.0
    assert result.status in ("completed", "partial")

    # Export to CSV
    csv_out = os.path.join(temp_lab_dir, "benchmark_export.csv")
    BenchmarkRunner.export_to_csv(result, csv_out)
    assert os.path.isfile(csv_out)

    with open(csv_out, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 2
        row = rows[0]
        # Verify required spec columns
        for col in [
            "benchmark_id", "benchmark_name", "run_id", "model_id", "model_name", "provider",
            "task", "status", "latency", "tokens_per_second", "input_tokens", "output_tokens",
            "accuracy", "pass_rate", "cpu_usage", "ram_usage", "runtime", "timestamp",
            "cat_version", "python_version", "pytorch_version", "hardware"
        ]:
            assert col in row, f"Missing required CSV column: {col}"


def test_visualizer_and_multi_model_comparison():
    """Verify terminal visualizer and multi-model comparison table."""
    r1 = BenchmarkRunResult(
        run_id="run-01",
        benchmark_id="b1",
        benchmark_name="Python Code",
        model_id="m1",
        model_name="Model A",
        provider_id="local",
        timestamp="2026-10-01T12:00:00Z",
        status="completed",
        total_tasks=10,
        passed_tasks=9,
        failed_tasks=1,
        accuracy=0.9,
        pass_rate=90.0,
        avg_latency_sec=1.2,
        p50_latency_sec=1.1,
        p95_latency_sec=1.8,
        p99_latency_sec=1.9,
        tokens_per_second=42.5,
        total_input_tokens=100,
        total_output_tokens=250,
        total_tokens=350,
        environment={"device": "CUDA", "python": "3.12"},
    )
    r2 = BenchmarkRunResult(
        run_id="run-02",
        benchmark_id="b1",
        benchmark_name="Python Code",
        model_id="m2",
        model_name="Model B",
        provider_id="local",
        timestamp="2026-10-01T12:05:00Z",
        status="completed",
        total_tasks=10,
        passed_tasks=8,
        failed_tasks=2,
        accuracy=0.8,
        pass_rate=80.0,
        avg_latency_sec=2.4,
        p50_latency_sec=2.2,
        p95_latency_sec=3.1,
        p99_latency_sec=3.2,
        tokens_per_second=22.1,
        total_input_tokens=100,
        total_output_tokens=230,
        total_tokens=330,
        environment={"device": "CPU", "python": "3.12"},
    )

    card = render_benchmark_report_card(r1)
    assert "BENCHMARK REPORT" in card
    assert "Pass Rate" in card

    comp = render_multi_model_comparison([r1, r2])
    assert "MULTI-MODEL COMPARISON" in comp
    assert "Model A" in comp
    assert "Model B" in comp
    # Discrepancy warning because r1 was on CUDA and r2 was on CPU
    assert "FAIRNESS & COMPARABILITY NOTICES" in comp


# =============================================================================
# 4. Dataset Registry Tests
# =============================================================================

def test_dataset_inspection_and_registration(temp_lab_dir):
    """Verify dataset registry inspects files without reading huge content into memory."""
    datasets_dir = os.path.join(temp_lab_dir, "datasets")
    reg = DatasetRegistry(datasets_dir=datasets_dir)

    # Create dummy CSV dataset
    dummy_csv = os.path.join(temp_lab_dir, "test_dataset.csv")
    with open(dummy_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["feature_a", "feature_b", "label"])
        for i in range(25):
            writer.writerow([i * 1.5, f"text_{i}", 1 if i % 2 == 0 else 0])

    spec = reg.inspect_file(dummy_csv)
    assert spec.num_samples == 25
    assert spec.num_features == 3
    assert spec.labels == ["feature_a", "feature_b", "label"]
    assert spec.format == DatasetFormat.CSV

    # Add to registry
    reg.add(spec, persist=True)
    assert reg.get(spec.id) is not None
    assert os.path.isfile(os.path.join(datasets_dir, f"{spec.id}.cat"))


# =============================================================================
# 5. Experiment Tracking Tests
# =============================================================================

def test_experiment_tracking_and_queue(temp_lab_dir):
    """Verify reproducible experiment tracking and queuing."""
    exp_dir = os.path.join(temp_lab_dir, "experiments")
    tracker = ExperimentTracker(experiments_dir=exp_dir)

    # Create experiment
    exp = tracker.create(
        name="MNIST Classification Run",
        model_id="pytorch-mlp-classifier",
        description="Testing neural net classification",
    )
    assert exp.id.startswith("exp-")
    assert exp.environment.get("os") is not None

    # Checkpoint
    cp = tracker.add_checkpoint(exp.id, name="Epoch 1 Checkpoint", metrics={"loss": 0.42, "acc": 0.88})
    assert cp is not None
    assert cp["checkpoint_id"] == "cp-001"

    # Queue
    queue = ExperimentQueue(tracker)
    assert queue.enqueue(exp.id) is True
    assert len(queue.list_queue()) == 1


# =============================================================================
# 6. Safe Training Tests
# =============================================================================

def test_training_safety_limits():
    """Verify trainer safety limits handle missing or active PyTorch safely."""
    limits = TrainingSafetyLimits(max_runtime_sec=2.0, max_epochs=2)
    trainer = PyTorchTrainer(limits=limits)
    exp = ExperimentSpec(id="dummy", name="Dummy")

    # Run safe experiment
    res = trainer.run_training_experiment(exp, epochs=2)
    assert "success" in res
    if not res["success"]:
        assert "PyTorch is not installed" in res["error"]
    else:
        assert res["completed_epochs"] <= 2


# =============================================================================
# 7. CLI Commands Tests
# =============================================================================

def test_lab_cli_commands(temp_lab_dir):
    """Verify lab, hardware, benchmark, model, and dataset CLI entrypoints."""
    # cat lab
    rc_lab = lab_cli([])
    assert rc_lab == 0

    # cat hardware
    rc_hw = hardware_cli([])
    assert rc_hw == 0

    rc_gpu = hardware_cli(["hardware", "gpu"])
    assert rc_gpu == 0

    rc_cpu = hardware_cli(["hardware", "cpu"])
    assert rc_cpu == 0

    rc_mem = hardware_cli(["hardware", "memory"])
    assert rc_mem == 0

    # cat benchmark list
    rc_b = benchmark_cli(["benchmark", "list"])
    assert rc_b == 0

    # cat model list & info
    rc_m = model_cli(["model", "list"])
    assert rc_m == 0

    rc_info = model_cli(["model", "info", "deepseek-r1-local"])
    assert rc_info == 0

    # cat dataset list
    rc_d = dataset_cli(["dataset", "list"])
    assert rc_d == 0

    # cat experiment list
    rc_e = experiment_cli(["experiment", "list"])
    assert rc_e == 0
