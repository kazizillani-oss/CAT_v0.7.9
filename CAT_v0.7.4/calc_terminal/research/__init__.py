"""
CAT Research Subsystem per §48-§51, §58-§63, §97-§98:
- Experiment Ledger & Scientific Time Machine
- Data Lineage Graph
- Semantic Artifact Intelligence
- Reproducibility Engine & Package Generation
"""

from __future__ import annotations

from calc_terminal.research.experiment_ledger import (
    ExperimentRecord,
    ExperimentVersion,
    ExperimentLedger,
    experiment_ledger,
)
from calc_terminal.research.data_lineage import (
    LineageNode,
    DataLineageGraph,
    data_lineage,
)
from calc_terminal.research.artifact_intel import (
    ArtifactSemantics,
    analyze_artifact,
)
from calc_terminal.research.reproducibility import (
    ReproductionReport,
    ReproducibilityEngine,
    reproducibility_engine,
)

__all__ = [
    "ExperimentRecord",
    "ExperimentVersion",
    "ExperimentLedger",
    "experiment_ledger",
    "LineageNode",
    "DataLineageGraph",
    "data_lineage",
    "ArtifactSemantics",
    "analyze_artifact",
    "ReproductionReport",
    "ReproducibilityEngine",
    "reproducibility_engine",
]
