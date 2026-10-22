"""
CAT Lab — Benchmark Studio, Model Lab & Machine Learning Environment.
Creator: Kazi Zillani (CAT Platform).

Top-level exports for CAT Lab:
- Models: ModelSpec, ModelCompatibilityReport, ModelLabRegistry, ModelRunner, check_compatibility
- Benchmarks: BenchmarkSpec, BenchmarkTask, BenchmarkRunResult, BenchmarkStudioRegistry, BenchmarkRunner
- Datasets: DatasetSpec, DatasetRegistry
- Experiments: ExperimentSpec, ExperimentTracker, ExperimentQueue
- Training: PyTorchTrainer, TrainingSafetyLimits
- Hardware: get_hardware_profile, get_hardware_status_text, get_gpu_status_text, get_cpu_status_text, get_memory_status_text
- Visualizer: render_benchmark_report_card, render_multi_model_comparison
- Stylesheets: get_stylesheet_manager, BenchmarkStylesheet
"""

from .benchmark_studio import (
    BenchmarkRunner,
    BenchmarkStudioRegistry,
    get_benchmark_registry,
)
from .datasets import (
    DatasetRegistry,
    get_dataset_registry,
)
from .experiments import (
    ExperimentQueue,
    ExperimentTracker,
    get_experiment_tracker,
)
from .hardware import (
    detect_cuda_info,
    detect_nodejs_version,
    detect_pytorch_info,
    get_cpu_status_text,
    get_gpu_status_text,
    get_hardware_profile,
    get_hardware_status_text,
    get_memory_status_text,
)
from .model_lab import (
    ModelLabRegistry,
    ModelRunner,
    check_compatibility,
    get_model_registry,
)
from .models import (
    BenchmarkRunResult,
    BenchmarkSpec,
    BenchmarkStylesheet,
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
from .stylesheets import (
    StylesheetManager,
    get_stylesheet_manager,
)
from .training import (
    PyTorchTrainer,
    TrainingSafetyLimits,
)
from .visualizer import (
    render_ascii_bar,
    render_benchmark_report_card,
    render_multi_model_comparison,
)

__all__ = [
    "ModelSpec",
    "ModelCompatibilityReport",
    "ModelType",
    "ModelFramework",
    "ModelStatus",
    "ModelLabRegistry",
    "ModelRunner",
    "check_compatibility",
    "get_model_registry",
    "BenchmarkSpec",
    "BenchmarkTask",
    "BenchmarkRunResult",
    "BenchmarkType",
    "TaskResult",
    "BenchmarkStudioRegistry",
    "BenchmarkRunner",
    "get_benchmark_registry",
    "DatasetSpec",
    "DatasetFormat",
    "DatasetRegistry",
    "get_dataset_registry",
    "ExperimentSpec",
    "ExperimentStatus",
    "TrainingProgress",
    "ExperimentTracker",
    "ExperimentQueue",
    "get_experiment_tracker",
    "PyTorchTrainer",
    "TrainingSafetyLimits",
    "get_hardware_profile",
    "get_hardware_status_text",
    "get_gpu_status_text",
    "get_cpu_status_text",
    "get_memory_status_text",
    "detect_cuda_info",
    "detect_pytorch_info",
    "detect_nodejs_version",
    "render_ascii_bar",
    "render_benchmark_report_card",
    "render_multi_model_comparison",
    "BenchmarkStylesheet",
    "StylesheetManager",
    "get_stylesheet_manager",
]
