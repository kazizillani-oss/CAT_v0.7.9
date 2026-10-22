"""
CAT Data Lineage Graph per §58, §97:
Tracks end-to-end transformation lineage from raw source to figures and publication reports.
Explains dependency chains when upstream or downstream artifacts change.
"""

from __future__ import annotations

import time
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class LineageNode:
    path: str
    artifact_type: str  # dataset, features, model, predictions, figure, report
    sources: List[str] = field(default_factory=list)  # parent artifact paths
    transform_tool: str = ""  # tool or script that produced this artifact
    experiment_id: Optional[str] = None
    task_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "artifact_type": self.artifact_type,
            "sources": self.sources,
            "transform_tool": self.transform_tool,
            "experiment_id": self.experiment_id,
            "task_id": self.task_id,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class DataLineageGraph:
    """DAG tracking artifact generation, transformations, and dependency explanations."""

    def __init__(self):
        self.nodes: Dict[str, LineageNode] = {}

    def record_transformation(
        self,
        target_path: Optional[str] = None,
        sources: Optional[List[str]] = None,
        transform_tool: str = "",
        artifact_type: str = "artifact",
        experiment_id: Optional[str] = None,
        task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None,
    ) -> LineageNode:
        actual_path = target_path or output_path or ""
        norm_target = os.path.normpath(actual_path)
        norm_sources = [os.path.normpath(s) for s in (sources or [])]
        node = LineageNode(
            path=norm_target,
            artifact_type=artifact_type,
            sources=norm_sources,
            transform_tool=transform_tool,
            experiment_id=experiment_id,
            task_id=task_id,
            metadata=metadata or {},
        )
        self.nodes[norm_target] = node
        return node

    def get_upstream_lineage(self, target_path: str) -> List[str]:
        """Return list of all ancestor artifacts that produced target_path."""
        norm_target = os.path.normpath(target_path)
        visited = []
        queue = [norm_target]
        while queue:
            curr = queue.pop(0)
            node = self.nodes.get(curr)
            if node:
                for s in node.sources:
                    if s not in visited:
                        visited.append(s)
                        queue.append(s)
        return visited

    def get_upstream(self, target_path: str) -> List[str]:
        return self.get_upstream_lineage(target_path)

    def get_downstream_impact(self, source_path: str) -> List[str]:
        """Return list of all downstream artifacts dependent on source_path."""
        norm_source = os.path.normpath(source_path)
        impacted = []
        for path, node in self.nodes.items():
            if norm_source in node.sources:
                impacted.append(path)
                impacted.extend(self.get_downstream_impact(path))
        return list(dict.fromkeys(impacted))

    def get_downstream(self, source_path: str) -> List[str]:
        return self.get_downstream_impact(source_path)

    def explain_chain(self, target_path: str) -> str:
        """Human-readable explanation of how this artifact was generated."""
        norm = os.path.normpath(target_path)
        node = self.nodes.get(norm)
        if not node:
            return f"No recorded lineage for artifact: {os.path.basename(target_path)}"

        lines = [f"Artifact: {os.path.basename(norm)} ({node.artifact_type})"]
        if node.transform_tool:
            lines.append(f"Produced by: {node.transform_tool}")
        if node.experiment_id:
            lines.append(f"Experiment: {node.experiment_id}")
        if node.sources:
            lines.append("Source dependencies:")
            for s in node.sources:
                src_node = self.nodes.get(s)
                tool_note = f" (via {src_node.transform_tool})" if src_node and src_node.transform_tool else ""
                lines.append(f"  └── {os.path.basename(s)}{tool_note}")
        return "\n".join(lines)


data_lineage = DataLineageGraph()
