"""
CAT Lab — Core Data Models & Schemas.
Creator: Kazi Zillani (CAT Platform).

Defines structured schemas for:
- Models (ModelSpec, Compatibility, Capabilities)
- Benchmarks (BenchmarkSpec, Task, RunResult, Metrics)
- Datasets (DatasetSpec, Format, Statistics)
- Experiments (ExperimentSpec, EnvironmentSnapshot, TrainingProgress)
- Stylesheets (BenchmarkStylesheet)
"""

from __future__ import annotations

import datetime
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


# =============================================================================
# 1. Model Lab Schemas
# =============================================================================

class ModelType:
    LLM = "llm"
    VISION = "vision"
    EMBEDDING = "embedding"
    AUDIO = "audio"
    CLASSIFICATION = "classification"
    CUSTOM_ML = "custom_ml"
    PYTORCH = "pytorch"


class ModelFramework:
    PYTORCH = "pytorch"
    SAFETENSORS = "safetensors"
    GGUF = "gguf"
    ONNX = "onnx"
    TRANSFORMERS = "transformers"
    OLLAMA = "ollama"
    CUSTOM = "custom"


class ModelStatus:
    LOCAL = "local"
    REMOTE = "remote"
    CUSTOM = "custom"
    EXPERIMENTAL = "experimental"


@dataclass
class ModelSpec:
    id: str
    name: str
    model_type: str = ModelType.LLM
    framework: str = ModelFramework.OLLAMA
    model_path: str = ""
    provider_runtime: str = "default"  # ollama, local, openai, etc.
    version: str = "1.0.0"
    context_size: int = 4096
    precision: str = "fp16"             # fp32, fp16, bf16, int8, int4, q4_k_m, etc.
    quantization: str = "none"          # none, 4bit, 8bit, gguf_q4, etc.
    expected_vram_gb: float = 0.0
    expected_ram_gb: float = 2.0
    input_format: str = "text"          # text, image, audio, tensor
    output_format: str = "text"         # text, embeddings, tensor, classification
    capabilities: List[str] = field(default_factory=lambda: ["generation", "chat"])
    status: str = ModelStatus.LOCAL
    description: str = ""
    author: str = "User"
    created_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "model_type": self.model_type,
            "framework": self.framework,
            "model_path": self.model_path,
            "provider_runtime": self.provider_runtime,
            "version": self.version,
            "context_size": self.context_size,
            "precision": self.precision,
            "quantization": self.quantization,
            "expected_vram_gb": self.expected_vram_gb,
            "expected_ram_gb": self.expected_ram_gb,
            "input_format": self.input_format,
            "output_format": self.output_format,
            "capabilities": list(self.capabilities),
            "status": self.status,
            "description": self.description,
            "author": self.author,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModelSpec:
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data.get("name", "Unnamed Model"),
            model_type=data.get("model_type", ModelType.LLM),
            framework=data.get("framework", ModelFramework.OLLAMA),
            model_path=data.get("model_path", ""),
            provider_runtime=data.get("provider_runtime", "default"),
            version=data.get("version", "1.0.0"),
            context_size=int(data.get("context_size", 4096)),
            precision=data.get("precision", "fp16"),
            quantization=data.get("quantization", "none"),
            expected_vram_gb=float(data.get("expected_vram_gb", 0.0)),
            expected_ram_gb=float(data.get("expected_ram_gb", 2.0)),
            input_format=data.get("input_format", "text"),
            output_format=data.get("output_format", "text"),
            capabilities=list(data.get("capabilities", ["generation"])),
            status=data.get("status", ModelStatus.LOCAL),
            description=data.get("description", ""),
            author=data.get("author", "User"),
            created_at=data.get("created_at", datetime.datetime.now(datetime.timezone.utc).isoformat()),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ModelCompatibilityReport:
    model_id: str
    model_name: str
    status: str                         # Compatible, Probably Compatible, Insufficient VRAM, Insufficient RAM, Missing Runtime, Missing Dependency, Unsupported Format, Unknown
    compatible: bool = True
    vram_ok: bool = True
    ram_ok: bool = True
    cuda_ok: bool = True
    runtime_ok: bool = True
    details: List[str] = field(default_factory=list)
    hardware_detected: Dict[str, Any] = field(default_factory=dict)
    hardware_required: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "status": self.status,
            "compatible": self.compatible,
            "vram_ok": self.vram_ok,
            "ram_ok": self.ram_ok,
            "cuda_ok": self.cuda_ok,
            "runtime_ok": self.runtime_ok,
            "details": list(self.details),
            "hardware_detected": dict(self.hardware_detected),
            "hardware_required": dict(self.hardware_required),
        }


# =============================================================================
# 2. Benchmark Studio Schemas
# =============================================================================

class BenchmarkType:
    GENERATION = "generation"
    CLASSIFICATION = "classification"
    REASONING = "reasoning"
    CODING = "coding"
    CODE_REPAIR = "code_repair"
    QUESTION_ANSWERING = "question_answering"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    CONTEXT_WINDOW = "context_window"
    MEMORY = "memory"
    GPU_PERFORMANCE = "gpu_performance"
    CPU_PERFORMANCE = "cpu_performance"
    MODEL_CAPACITY = "model_capacity"
    CUSTOM = "custom"


@dataclass
class BenchmarkTask:
    id: str
    prompt: str
    expected_output: str = ""
    evaluation_method: str = "exact_or_contains"  # exact, contains, regex, code_exec, similarity, custom
    weight: float = 1.0
    timeout_sec: float = 15.0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "expected_output": self.expected_output,
            "evaluation_method": self.evaluation_method,
            "weight": self.weight,
            "timeout_sec": self.timeout_sec,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BenchmarkTask:
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            prompt=data.get("prompt", ""),
            expected_output=data.get("expected_output", ""),
            evaluation_method=data.get("evaluation_method", "contains"),
            weight=float(data.get("weight", 1.0)),
            timeout_sec=float(data.get("timeout_sec", 15.0)),
            tags=list(data.get("tags", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class BenchmarkSpec:
    id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    benchmark_type: str = BenchmarkType.CODING
    dataset_id: Optional[str] = None
    tasks: List[BenchmarkTask] = field(default_factory=list)
    prompt_template: str = "{prompt}"
    expected_output: str = ""
    evaluation_method: str = "contains"
    models: List[str] = field(default_factory=list)
    providers: List[str] = field(default_factory=list)
    runs: int = 1
    concurrency: int = 1
    timeout: float = 30.0
    max_tokens: int = 512
    temperature: float = 0.2
    context_size: int = 4096
    hardware_metrics: bool = True
    output_metrics: List[str] = field(default_factory=lambda: [
        "accuracy", "pass_rate", "latency", "tokens_per_second", "ram_usage", "cpu_usage"
    ])
    created_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "benchmark_type": self.benchmark_type,
            "dataset_id": self.dataset_id,
            "tasks": [t.to_dict() for t in self.tasks],
            "prompt_template": self.prompt_template,
            "expected_output": self.expected_output,
            "evaluation_method": self.evaluation_method,
            "models": list(self.models),
            "providers": list(self.providers),
            "runs": self.runs,
            "concurrency": self.concurrency,
            "timeout": self.timeout,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "context_size": self.context_size,
            "hardware_metrics": self.hardware_metrics,
            "output_metrics": list(self.output_metrics),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BenchmarkSpec:
        tasks = [BenchmarkTask.from_dict(t) for t in data.get("tasks", [])]
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data.get("name", "Unnamed Benchmark"),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            benchmark_type=data.get("benchmark_type", BenchmarkType.CODING),
            dataset_id=data.get("dataset_id"),
            tasks=tasks,
            prompt_template=data.get("prompt_template", "{prompt}"),
            expected_output=data.get("expected_output", ""),
            evaluation_method=data.get("evaluation_method", "contains"),
            models=list(data.get("models", [])),
            providers=list(data.get("providers", [])),
            runs=int(data.get("runs", 1)),
            concurrency=int(data.get("concurrency", 1)),
            timeout=float(data.get("timeout", 30.0)),
            max_tokens=int(data.get("max_tokens", 512)),
            temperature=float(data.get("temperature", 0.2)),
            context_size=int(data.get("context_size", 4096)),
            hardware_metrics=bool(data.get("hardware_metrics", True)),
            output_metrics=list(data.get("output_metrics", ["accuracy", "latency"])),
            created_at=data.get("created_at", datetime.datetime.now(datetime.timezone.utc).isoformat()),
        )


@dataclass
class TaskResult:
    task_id: str
    prompt: str
    expected: str
    output: str
    passed: bool
    latency_sec: float
    input_tokens: int
    output_tokens: int
    tokens_per_sec: float
    error: Optional[str] = None
    cpu_percent: Optional[float] = None
    ram_mb: Optional[float] = None
    vram_mb: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "prompt": self.prompt,
            "expected": self.expected,
            "output": self.output,
            "passed": self.passed,
            "latency_sec": self.latency_sec,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "tokens_per_sec": self.tokens_per_sec,
            "error": self.error,
            "cpu_percent": self.cpu_percent,
            "ram_mb": self.ram_mb,
            "vram_mb": self.vram_mb,
        }


@dataclass
class BenchmarkRunResult:
    run_id: str
    benchmark_id: str
    benchmark_name: str
    model_id: str
    model_name: str
    provider_id: str
    timestamp: str
    status: str                         # completed, partial, failed, cancelled
    total_tasks: int
    passed_tasks: int
    failed_tasks: int
    accuracy: float                     # 0.0 - 1.0
    pass_rate: float                    # 0.0 - 100.0 %
    avg_latency_sec: float
    p50_latency_sec: float
    p95_latency_sec: float
    p99_latency_sec: float
    tokens_per_second: float
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    time_to_first_token_sec: Optional[float] = None
    total_runtime_sec: float = 0.0
    cpu_usage_avg: Optional[float] = None
    ram_usage_mb_avg: Optional[float] = None
    gpu_usage_pct_avg: Optional[float] = None
    vram_usage_mb_avg: Optional[float] = None
    hardware: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)
    task_results: List[TaskResult] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "benchmark_id": self.benchmark_id,
            "benchmark_name": self.benchmark_name,
            "model_id": self.model_id,
            "model_name": self.model_name,
            "provider_id": self.provider_id,
            "timestamp": self.timestamp,
            "status": self.status,
            "total_tasks": self.total_tasks,
            "passed_tasks": self.passed_tasks,
            "failed_tasks": self.failed_tasks,
            "accuracy": self.accuracy,
            "pass_rate": self.pass_rate,
            "avg_latency_sec": self.avg_latency_sec,
            "p50_latency_sec": self.p50_latency_sec,
            "p95_latency_sec": self.p95_latency_sec,
            "p99_latency_sec": self.p99_latency_sec,
            "tokens_per_second": self.tokens_per_second,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "time_to_first_token_sec": self.time_to_first_token_sec,
            "total_runtime_sec": self.total_runtime_sec,
            "cpu_usage_avg": self.cpu_usage_avg,
            "ram_usage_mb_avg": self.ram_usage_mb_avg,
            "gpu_usage_pct_avg": self.gpu_usage_pct_avg,
            "vram_usage_mb_avg": self.vram_usage_mb_avg,
            "hardware": dict(self.hardware),
            "environment": dict(self.environment),
            "task_results": [t.to_dict() for t in self.task_results],
            "artifacts": list(self.artifacts),
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BenchmarkRunResult:
        tasks = [
            TaskResult(
                task_id=t.get("task_id", ""),
                prompt=t.get("prompt", ""),
                expected=t.get("expected", ""),
                output=t.get("output", ""),
                passed=bool(t.get("passed", False)),
                latency_sec=float(t.get("latency_sec", 0.0)),
                input_tokens=int(t.get("input_tokens", 0)),
                output_tokens=int(t.get("output_tokens", 0)),
                tokens_per_sec=float(t.get("tokens_per_sec", 0.0)),
                error=t.get("error"),
                cpu_percent=t.get("cpu_percent"),
                ram_mb=t.get("ram_mb"),
                vram_mb=t.get("vram_mb"),
            )
            for t in data.get("task_results", [])
        ]
        return cls(
            run_id=data.get("run_id", str(uuid.uuid4())[:8]),
            benchmark_id=data.get("benchmark_id", ""),
            benchmark_name=data.get("benchmark_name", ""),
            model_id=data.get("model_id", ""),
            model_name=data.get("model_name", ""),
            provider_id=data.get("provider_id", ""),
            timestamp=data.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat()),
            status=data.get("status", "completed"),
            total_tasks=int(data.get("total_tasks", 0)),
            passed_tasks=int(data.get("passed_tasks", 0)),
            failed_tasks=int(data.get("failed_tasks", 0)),
            accuracy=float(data.get("accuracy", 0.0)),
            pass_rate=float(data.get("pass_rate", 0.0)),
            avg_latency_sec=float(data.get("avg_latency_sec", 0.0)),
            p50_latency_sec=float(data.get("p50_latency_sec", 0.0)),
            p95_latency_sec=float(data.get("p95_latency_sec", 0.0)),
            p99_latency_sec=float(data.get("p99_latency_sec", 0.0)),
            tokens_per_second=float(data.get("tokens_per_second", 0.0)),
            total_input_tokens=int(data.get("total_input_tokens", 0)),
            total_output_tokens=int(data.get("total_output_tokens", 0)),
            total_tokens=int(data.get("total_tokens", 0)),
            time_to_first_token_sec=data.get("time_to_first_token_sec"),
            total_runtime_sec=float(data.get("total_runtime_sec", 0.0)),
            cpu_usage_avg=data.get("cpu_usage_avg"),
            ram_usage_mb_avg=data.get("ram_usage_mb_avg"),
            gpu_usage_pct_avg=data.get("gpu_usage_pct_avg"),
            vram_usage_mb_avg=data.get("vram_usage_mb_avg"),
            hardware=dict(data.get("hardware", {})),
            environment=dict(data.get("environment", {})),
            task_results=tasks,
            artifacts=list(data.get("artifacts", [])),
            error=data.get("error"),
        )


# =============================================================================
# 3. Dataset Schemas
# =============================================================================

class DatasetFormat:
    JSON = "json"
    JSONL = "jsonl"
    CSV = "csv"
    TEXT = "text"
    PARQUET = "parquet"
    CUSTOM = "custom"


@dataclass
class DatasetSpec:
    id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    format: str = DatasetFormat.JSON
    file_path: str = ""
    num_samples: int = 0
    num_features: int = 0
    labels: List[str] = field(default_factory=list)
    file_size_bytes: int = 0
    missing_values: int = 0
    created_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "format": self.format,
            "file_path": self.file_path,
            "num_samples": self.num_samples,
            "num_features": self.num_features,
            "labels": list(self.labels),
            "file_size_bytes": self.file_size_bytes,
            "missing_values": self.missing_values,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DatasetSpec:
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data.get("name", "Unnamed Dataset"),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            format=data.get("format", DatasetFormat.JSON),
            file_path=data.get("file_path", ""),
            num_samples=int(data.get("num_samples", 0)),
            num_features=int(data.get("num_features", 0)),
            labels=list(data.get("labels", [])),
            file_size_bytes=int(data.get("file_size_bytes", 0)),
            missing_values=int(data.get("missing_values", 0)),
            created_at=data.get("created_at", datetime.datetime.now(datetime.timezone.utc).isoformat()),
            metadata=dict(data.get("metadata", {})),
        )


# =============================================================================
# 4. Experiment Schemas
# =============================================================================

class ExperimentStatus:
    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class TrainingProgress:
    epoch: int = 0
    total_epochs: int = 10
    step: int = 0
    loss: float = 0.0
    val_loss: Optional[float] = None
    accuracy: Optional[float] = None
    val_accuracy: Optional[float] = None
    learning_rate: float = 0.001
    vram_mb: Optional[float] = None
    ram_mb: Optional[float] = None
    elapsed_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "epoch": self.epoch,
            "total_epochs": self.total_epochs,
            "step": self.step,
            "loss": self.loss,
            "val_loss": self.val_loss,
            "accuracy": self.accuracy,
            "val_accuracy": self.val_accuracy,
            "learning_rate": self.learning_rate,
            "vram_mb": self.vram_mb,
            "ram_mb": self.ram_mb,
            "elapsed_sec": self.elapsed_sec,
        }


@dataclass
class ExperimentSpec:
    id: str
    name: str
    description: str = ""
    model_id: str = ""
    dataset_id: Optional[str] = None
    benchmark_id: Optional[str] = None
    status: str = ExperimentStatus.DRAFT
    created_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    config: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)
    progress: TrainingProgress = field(default_factory=TrainingProgress)
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "model_id": self.model_id,
            "dataset_id": self.dataset_id,
            "benchmark_id": self.benchmark_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "config": dict(self.config),
            "environment": dict(self.environment),
            "progress": self.progress.to_dict(),
            "checkpoints": list(self.checkpoints),
            "results": dict(self.results),
            "artifacts": list(self.artifacts),
            "logs": list(self.logs),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExperimentSpec:
        p_raw = data.get("progress", {})
        progress = TrainingProgress(
            epoch=int(p_raw.get("epoch", 0)),
            total_epochs=int(p_raw.get("total_epochs", 10)),
            step=int(p_raw.get("step", 0)),
            loss=float(p_raw.get("loss", 0.0)),
            val_loss=p_raw.get("val_loss"),
            accuracy=p_raw.get("accuracy"),
            val_accuracy=p_raw.get("val_accuracy"),
            learning_rate=float(p_raw.get("learning_rate", 0.001)),
            vram_mb=p_raw.get("vram_mb"),
            ram_mb=p_raw.get("ram_mb"),
            elapsed_sec=float(p_raw.get("elapsed_sec", 0.0)),
        )
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data.get("name", "Unnamed Experiment"),
            description=data.get("description", ""),
            model_id=data.get("model_id", ""),
            dataset_id=data.get("dataset_id"),
            benchmark_id=data.get("benchmark_id"),
            status=data.get("status", ExperimentStatus.DRAFT),
            created_at=data.get("created_at", datetime.datetime.now(datetime.timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.datetime.now(datetime.timezone.utc).isoformat()),
            config=dict(data.get("config", {})),
            environment=dict(data.get("environment", {})),
            progress=progress,
            checkpoints=list(data.get("checkpoints", [])),
            results=dict(data.get("results", {})),
            artifacts=list(data.get("artifacts", [])),
            logs=list(data.get("logs", [])),
        )


# =============================================================================
# 5. Benchmark Stylesheet Schemas
# =============================================================================

@dataclass
class BenchmarkStylesheet:
    name: str = "default_terminal"
    version: str = "1.0.0"
    layout: str = "compact"             # compact, detailed, grid, minimal
    typography: str = "ansi"            # ansi, unicode, ascii
    chart_style: str = "bar_unicode"    # bar_unicode, bar_ascii, line, dots
    table_style: str = "rounded"        # rounded, heavy, ascii, simple
    dark_presentation: bool = True
    metric_precision: int = 2
    show_hardware: bool = True
    header_branding: str = "🐱 CAT Lab — Benchmark Report"
    footer_notes: str = "Generated by CAT (Coding Agent Terminal)"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "layout": self.layout,
            "typography": self.typography,
            "chart_style": self.chart_style,
            "table_style": self.table_style,
            "dark_presentation": self.dark_presentation,
            "metric_precision": self.metric_precision,
            "show_hardware": self.show_hardware,
            "header_branding": self.header_branding,
            "footer_notes": self.footer_notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BenchmarkStylesheet:
        return cls(
            name=data.get("name", "default_terminal"),
            version=data.get("version", "1.0.0"),
            layout=data.get("layout", "compact"),
            typography=data.get("typography", "ansi"),
            chart_style=data.get("chart_style", "bar_unicode"),
            table_style=data.get("table_style", "rounded"),
            dark_presentation=bool(data.get("dark_presentation", True)),
            metric_precision=int(data.get("metric_precision", 2)),
            show_hardware=bool(data.get("show_hardware", True)),
            header_branding=data.get("header_branding", "🐱 CAT Lab — Benchmark Report"),
            footer_notes=data.get("footer_notes", "Generated by CAT (Coding Agent Terminal)"),
        )
