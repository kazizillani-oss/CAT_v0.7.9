"""
Semantic Artifact Intelligence per §51:
Understands the semantic domain and compatible tool capabilities for files:
- .pdb, .cif -> Protein 3D Structure
- .fasta, .fa -> Biological Sequence
- .safetensors, .pt -> Machine Learning Model
- .ipynb -> Jupyter Notebook
- .csv, .parquet -> Dataset
- .png, .svg -> Scientific Visualization
- .qasm -> Quantum Circuit
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ArtifactSemantics:
    path: str
    filename: str
    semantic_type: str
    domain: str
    recommended_capabilities: List[str]
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "filename": self.filename,
            "semantic_type": self.semantic_type,
            "domain": self.domain,
            "recommended_capabilities": self.recommended_capabilities,
            "description": self.description,
        }


def analyze_artifact(file_path: str) -> ArtifactSemantics:
    """Classify and return semantic domain and recommended capabilities for an artifact."""
    norm = os.path.normpath(file_path)
    base = os.path.basename(norm).lower()
    ext = os.path.splitext(base)[1].lower()

    if ext in (".pdb", ".cif", ".mmcif"):
        return ArtifactSemantics(
            path=norm,
            filename=base,
            semantic_type="protein_structure",
            domain="structural_biology",
            recommended_capabilities=["pymol.open", "chimerax.open", "biopython.parse"],
            description="3D macromolecular coordinate structure file",
        )
    elif ext in (".fasta", ".fa", ".fna", ".faa"):
        return ArtifactSemantics(
            path=norm,
            filename=base,
            semantic_type="biological_sequence",
            domain="bioinformatics",
            recommended_capabilities=["blast.search", "ncbi.query", "biopython.parse"],
            description="Nucleotide or amino acid biological sequence file",
        )
    elif ext in (".safetensors", ".pt", ".pth", ".onnx", ".bin"):
        return ArtifactSemantics(
            path=norm,
            filename=base,
            semantic_type="ml_model",
            domain="machine_learning",
            recommended_capabilities=["pytorch.eval", "huggingface.model", "ml.detect_hardware"],
            description="Trained neural network model weights or serialized computational graph",
        )
    elif ext == ".ipynb":
        return ArtifactSemantics(
            path=norm,
            filename=base,
            semantic_type="jupyter_notebook",
            domain="notebook_computing",
            recommended_capabilities=["jupyter.execute", "jupyter.list_servers", "python.execute"],
            description="Interactive literate computing Jupyter notebook",
        )
    elif ext in (".csv", ".tsv", ".parquet", ".arrow", ".jsonl"):
        return ArtifactSemantics(
            path=norm,
            filename=base,
            semantic_type="dataset",
            domain="data_science",
            recommended_capabilities=["numpy.compute", "kaggle.dataset", "python.execute"],
            description="Tabular or columnar scientific/machine learning dataset",
        )
    elif ext in (".png", ".svg", ".pdf", ".eps"):
        return ArtifactSemantics(
            path=norm,
            filename=base,
            semantic_type="scientific_figure",
            domain="scientific_visualization",
            recommended_capabilities=["browser.navigate", "filesystem.read"],
            description="Rendered scientific visualization or publication figure",
        )
    elif ext in (".qasm",):
        return ArtifactSemantics(
            path=norm,
            filename=base,
            semantic_type="quantum_circuit",
            domain="quantum_computing",
            recommended_capabilities=["qiskit.run_circuit", "quantum.bloch_sphere"],
            description="OpenQASM quantum circuit specification",
        )
    elif ext in (".py",):
        return ArtifactSemantics(
            path=norm,
            filename=base,
            semantic_type="source_code",
            domain="software_engineering",
            recommended_capabilities=["python.execute", "git.diff", "filesystem.read"],
            description="Python executable source code",
        )

    return ArtifactSemantics(
        path=norm,
        filename=base,
        semantic_type="generic_file",
        domain="general",
        recommended_capabilities=["filesystem.read"],
        description="General file",
    )
