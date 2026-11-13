"""
CAT Workflow Builder (v0.7.9 Complete Platform Expansion)

DAG workflow execution engine, node pipelines, custom workflow templates,
and step-by-step orchestrated task execution.
"""

import os
import time
import json
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Callable

@dataclass
class WorkflowNode:
    id: str
    name: str
    node_type: str  # command, agent, tool, condition, script
    payload: str  # command string, agent prompt, or script
    depends_on: List[str] = field(default_factory=list)
    timeout_seconds: float = 30.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class WorkflowDefinition:
    id: str
    name: str
    description: str
    nodes: List[WorkflowNode] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "nodes": [n.to_dict() for n in self.nodes],
            "created_at": self.created_at
        }


class WorkflowBuilder:
    """Creates, validates, and executes DAG workflow pipelines."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._workflows: Dict[str, WorkflowDefinition] = {}
            cls._instance._storage_dir = os.path.expanduser("~/.cat/workflows")
            os.makedirs(cls._instance._storage_dir, exist_ok=True)
            cls._instance._bootstrap_templates()
        return cls._instance

    def _bootstrap_templates(self):
        """Seed high-value developer workflow pipelines."""
        templates = [
            WorkflowDefinition(
                id="wf_code_review",
                name="Automated Code Review Pipeline",
                description="Runs git diff, security scan, and reviews changes via Dexter.",
                nodes=[
                    WorkflowNode(id="step_git", name="Extract Git Diff", node_type="command", payload="git diff HEAD~1"),
                    WorkflowNode(id="step_sec", name="Scan Security Hazards", node_type="command", payload="/security", depends_on=["step_git"]),
                    WorkflowNode(id="step_review", name="Dexter Code Audit", node_type="agent", payload="Review diff and flag bugs, performance risks, or style issues.", depends_on=["step_sec"]),
                ]
            ),
            WorkflowDefinition(
                id="wf_test_and_deploy",
                name="Test & Deploy Pipeline",
                description="Executes project test suite and triggers local build if tests pass.",
                nodes=[
                    WorkflowNode(id="step_test", name="Run Test Suite", node_type="command", payload="pytest -q"),
                    WorkflowNode(id="step_build", name="Deploy Preview", node_type="command", payload="/deploy dry_run", depends_on=["step_test"]),
                ]
            ),
            WorkflowDefinition(
                id="wf_doc_generator",
                name="Project Documentation Generator",
                description="Indexes workspace symbols and generates markdown documentation.",
                nodes=[
                    WorkflowNode(id="step_index", name="Index Project Symbols", node_type="command", payload="/index"),
                    WorkflowNode(id="step_doc", name="Author Project Summary", node_type="agent", payload="Summarize project modules and document key classes.", depends_on=["step_index"]),
                ]
            ),
        ]
        for t in templates:
            self._workflows[t.id] = t

    def list_workflows(self) -> List[Dict[str, Any]]:
        return [w.to_dict() for w in self._workflows.values()]

    def get_workflow(self, wf_id: str) -> Optional[WorkflowDefinition]:
        return self._workflows.get(wf_id)

    def create_workflow(self, name: str, description: str, nodes: List[Dict[str, Any]]) -> WorkflowDefinition:
        wf_id = f"wf_{uuid.uuid4().hex[:8]}"
        node_objs = [WorkflowNode(**n) for n in nodes]
        wf = WorkflowDefinition(id=wf_id, name=name, description=description, nodes=node_objs)
        self._workflows[wf_id] = wf
        return wf

    def run_workflow(self, wf_id: str, executor_fn: Optional[Callable] = None) -> Dict[str, Any]:
        """Execute all nodes in workflow respecting DAG order."""
        wf = self._workflows.get(wf_id)
        if not wf:
            return {"success": False, "error": f"Workflow '{wf_id}' not found."}

        start_t = time.time()
        node_results = {}
        executed_nodes = set()

        for node in wf.nodes:
            # Check dependencies
            for dep in node.depends_on:
                if dep not in executed_nodes:
                    return {
                        "success": False,
                        "error": f"Unsatisfied dependency: step '{node.name}' depends on '{dep}'",
                        "completed_steps": node_results
                    }

            step_start = time.time()
            output = ""
            status = "success"
            try:
                if executor_fn:
                    output = executor_fn(node.payload)
                else:
                    output = f"Executed {node.node_type}: {node.payload}"
            except Exception as e:
                status = "failed"
                output = str(e)

            step_dur = (time.time() - step_start) * 1000
            node_results[node.id] = {
                "name": node.name,
                "type": node.node_type,
                "status": status,
                "duration_ms": round(step_dur, 2),
                "output": output
            }
            executed_nodes.add(node.id)

            if status == "failed":
                return {
                    "success": False,
                    "workflow_id": wf.id,
                    "failed_step": node.name,
                    "total_duration_ms": round((time.time() - start_t) * 1000, 2),
                    "steps": node_results
                }

        return {
            "success": True,
            "workflow_id": wf.id,
            "name": wf.name,
            "total_duration_ms": round((time.time() - start_t) * 1000, 2),
            "steps": node_results
        }


# Global singleton
workflow_builder = WorkflowBuilder()

def get_workflow_builder() -> WorkflowBuilder:
    return workflow_builder

