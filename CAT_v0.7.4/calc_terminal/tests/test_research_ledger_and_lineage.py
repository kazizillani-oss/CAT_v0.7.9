import os
import shutil
import tempfile
import pytest

from calc_terminal.research.experiment_ledger import (
    ExperimentLedger,
    ExperimentRecord,
    ExperimentVersion,
)
from calc_terminal.research.data_lineage import (
    DataLineageGraph,
    LineageNode,
)
from calc_terminal.research.artifact_intel import (
    analyze_artifact,
)
from calc_terminal.research.reproducibility import (
    ReproducibilityEngine,
    ReproductionReport,
)


def test_experiment_ledger_lifecycle_and_time_machine():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = os.path.join(tmpdir, "test_ledger.json")
        ledger = ExperimentLedger(storage_path=storage_path)

        # 1. Record experiment
        exp = ledger.record_experiment(
            question="Can GNN predict molecular solubility?",
            hypothesis="Graph Convolutional Network improves MSE over Random Forest baseline",
            dataset="ESOL",
            parameters={"lr": 0.001, "batch_size": 32, "epochs": 50},
            code_version="git:a1b2c3d",
            environment={"python": "3.10.12"},
            hardware={"cuda": True, "device": "NVIDIA RTX 4090"},
            results={"val_loss": 0.42, "r2": 0.88},
            model="GCNNet",
        )

        assert exp.id.startswith("EXP-")
        assert exp.question == "Can GNN predict molecular solubility?"
        assert exp.results["r2"] == 0.88

        # 2. Add new versions (Scientific Time Machine V1, V2)
        v2 = ledger.add_version(
            experiment_id=exp.id,
            parameters={"lr": 0.0005, "batch_size": 64, "epochs": 100},
            code_version="git:e4f5a6b",
            results={"val_loss": 0.31, "r2": 0.93},
            figures=["loss_curve_v2.png"],
            notes="Reduced learning rate and increased batch size",
        )
        assert v2.version == 2
        assert len(exp.versions) == 2

        # 3. Compare versions
        comparison = ledger.compare_versions(exp.id, 1, 2)
        assert "parameter_diffs" in comparison
        assert "result_diffs" in comparison
        assert comparison["parameter_diffs"]["lr"] == {"v1": 0.001, "v2": 0.0005}
        assert comparison["result_diffs"]["r2"] == {"v1": 0.88, "v2": 0.93}

        # 4. Save and reload
        reloaded = ExperimentLedger(storage_path=storage_path)
        fetched = reloaded.get_experiment(exp.id)
        assert fetched is not None
        assert fetched.question == exp.question
        assert len(fetched.versions) == 2

        # 5. Natural language query
        query_res = ledger.query_experiments("Show experiments run on GPU")
        assert len(query_res) == 1
        assert query_res[0].id == exp.id


def test_data_lineage_graph():
    graph = DataLineageGraph()

    # Track raw data -> features -> model -> predictions -> figure
    graph.record_transformation(
        output_path="data/raw.csv",
        artifact_type="dataset",
        sources=[],
        transform_tool="fetch_data",
    )
    graph.record_transformation(
        output_path="data/features.parquet",
        artifact_type="features",
        sources=["data/raw.csv"],
        transform_tool="feature_pipeline.py",
    )
    graph.record_transformation(
        output_path="models/best_model.pt",
        artifact_type="model",
        sources=["data/features.parquet"],
        transform_tool="train.py",
        experiment_id="EXP-101",
    )
    graph.record_transformation(
        output_path="figures/roc_curve.png",
        artifact_type="figure",
        sources=["models/best_model.pt"],
        transform_tool="evaluate.py",
    )

    # Check upstream lineage of figure
    upstream = graph.get_upstream("figures/roc_curve.png")
    assert any("best_model.pt" in p for p in upstream)
    assert any("features.parquet" in p for p in upstream)
    assert any("raw.csv" in p for p in upstream)

    # Check downstream impact if raw.csv changes
    downstream = graph.get_downstream("data/raw.csv")
    assert any("features.parquet" in p for p in downstream)
    assert any("best_model.pt" in p for p in downstream)
    assert any("roc_curve.png" in p for p in downstream)

    # Explain chain
    explanation = graph.explain_chain("figures/roc_curve.png")
    assert "roc_curve.png" in explanation
    assert "evaluate.py" in explanation
    assert "best_model.pt" in explanation


def test_artifact_intelligence_classification():
    cases = [
        ("protein.pdb", "protein_structure", "structural_biology"),
        ("sample.fasta", "biological_sequence", "bioinformatics"),
        ("model.safetensors", "ml_model", "machine_learning"),
        ("analysis.ipynb", "jupyter_notebook", "notebook_computing"),
        ("circuit.qasm", "quantum_circuit", "quantum_computing"),
        ("data.csv", "dataset", "data_science"),
        ("plot.png", "scientific_figure", "scientific_visualization"),
    ]

    for filename, expected_type, expected_domain in cases:
        semantics = analyze_artifact(filename)
        assert semantics.semantic_type == expected_type
        assert semantics.domain == expected_domain
        assert len(semantics.recommended_capabilities) > 0


def test_reproducibility_package_generation():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some dummy code and data files
        code_file = os.path.join(tmpdir, "train.py")
        with open(code_file, "w") as f:
            f.write("print('training...')")

        data_file = os.path.join(tmpdir, "dataset.csv")
        with open(data_file, "w") as f:
            f.write("x,y\n1,2\n3,4")

        engine = ReproducibilityEngine()
        pkg_dir = engine.create_reproducible_package(
            experiment_id="EXP-101",
            files=[code_file, data_file],
            environment={"python": "3.10.12"},
            parameters={"epochs": 10},
            results={"accuracy": 0.95},
            output_dir=os.path.join(tmpdir, "pkg"),
        )

        assert os.path.exists(pkg_dir)
        assert os.path.exists(os.path.join(pkg_dir, "manifest.json"))
        assert os.path.exists(os.path.join(pkg_dir, "README.md"))
        assert os.path.exists(os.path.join(pkg_dir, "train.py"))
        assert os.path.exists(os.path.join(pkg_dir, "dataset.csv"))
