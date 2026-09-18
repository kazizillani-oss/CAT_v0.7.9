"""
Tests for Unified Agent Runtime, Loop, and Task Graph per §5, §9, §10, §61.
"""

import pytest
from calc_terminal.core.unified_runtime import unified_runtime, WorkerType
from calc_terminal.core.task_graph import TaskGraph, TaskStatus, task_manager


class TestUnifiedRuntimeAndLoop:
    def test_create_context_initializes_graph(self):
        ctx = unified_runtime.create_context("Build an authentication module")
        assert ctx.trace_id.startswith("trace-")
        assert ctx.graph is not None
        assert ctx.active_worker == WorkerType.COORDINATOR

    def test_execute_tool_via_runtime_records_provenance(self, tmp_path):
        ctx = unified_runtime.create_context("Write test file")
        test_file = str(tmp_path / "runtime_out.txt")

        res = unified_runtime.execute_tool(
            capability_name="filesystem.write",
            args={"path": test_file, "content": "Runtime written content"},
            ctx=ctx,
            worker=WorkerType.CODING,
        )
        assert res.success is True
        assert len(ctx.steps) == 1
        assert ctx.steps[0].phase == "ACT"
        assert ctx.steps[0].worker == WorkerType.CODING
        assert ctx.steps[0].verified is True

    def test_subagent_worker_delegation(self):
        ctx = unified_runtime.create_context("Complex research task")
        res = unified_runtime.run_subagent_task(
            worker_type=WorkerType.RESEARCH,
            subtask_prompt="Find relevant papers on transformer attention",
            ctx=ctx,
        )
        assert res["worker"] == "research_worker"
        assert res["status"] == "completed"
        assert any(s.worker == WorkerType.RESEARCH for s in ctx.steps)
        assert ctx.active_worker == WorkerType.COORDINATOR

    def test_task_graph_dependency_resolution(self):
        graph = TaskGraph()
        t1 = graph.add_task("Step 1: Download dataset")
        t2 = graph.add_task("Step 2: Preprocess data", dependencies=[t1])
        t3 = graph.add_task("Step 3: Train model", dependencies=[t2])

        ready = graph.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == t1

        # Complete Step 1
        graph.update_status(t1, TaskStatus.SUCCEEDED)
        ready = graph.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == t2

        # Complete Step 2
        graph.update_status(t2, TaskStatus.SUCCEEDED)
        ready = graph.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == t3

        # ASCII tree rendering
        tree = graph.render_ascii_tree()
        assert "Step 1" in tree
        assert "Step 2" in tree
        assert "Step 3" in tree
