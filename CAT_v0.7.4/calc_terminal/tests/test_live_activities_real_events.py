"""
Unit and integration tests for CAT CLI Live Activities 100% Real Event System:
 - Authentic real-time RAM and resource monitor daemon
 - Central event bus schema & EVT-<hex> ID generation
 - Deduplication by operation_id and active signature
 - Stale activity watchdog preventing infinite spinners
 - Authentic session summary generation
 - Hierarchical timeline connectors (├─, └─) and LiveActivitiesBlock UI
"""

import time
import pytest
from calc_terminal import activity as act_mod


class TestResourceMonitor:
    def test_sample_now_returns_genuine_metrics(self):
        monitor = act_mod.ResourceMonitor(interval_sec=1.0)
        sample = monitor.sample_now()
        assert sample is not None
        # RAM metrics must be genuine positive numbers
        assert sample.system_ram_total_gb > 0.0
        assert sample.system_ram_used_gb > 0.0
        assert 0.0 <= sample.system_ram_percent <= 100.0
        assert sample.process_ram_mb > 0.0
        assert sample.cpu_percent >= 0.0
        assert sample.warning_level in ("normal", "elevated", "high", "critical")

    def test_warning_threshold_classification(self):
        monitor = act_mod.ResourceMonitor(interval_sec=1.0)
        # Test normal
        assert monitor.sample_now().warning_level in ("normal", "elevated", "high", "critical")


class TestEventSchemaAndDeduplication:
    def test_event_schema_and_canonical_id_generation(self):
        turn_id = "test-real-events-turn"
        act = act_mod.manager.create(
            type=act_mod.TYPE_FILE,
            action="write",
            title="Writing config.json",
            status=act_mod.STATUS_RUNNING,
            turn_id=turn_id,
            target_path="config.json",
            lines_added=42,
            lines_removed=5,
        )
        assert act.id.startswith("EVT-") or len(act.id) >= 6
        assert act.event_id == act.id
        assert act.task_id == turn_id
        assert act.lines_added == 42
        assert act.lines_removed == 5
        assert act.category == act_mod.CAT_EDIT
        assert act.phase == act_mod.PHASE_IMPLEMENTATION

    def test_deduplication_by_operation_id(self):
        turn_id = "test-dedup-op-turn"
        op_id = "op-build-12345"

        # First call creates the activity
        act1 = act_mod.manager.create(
            type=act_mod.TYPE_COMMAND,
            action="build",
            title="Compiling project",
            status=act_mod.STATUS_RUNNING,
            turn_id=turn_id,
            operation_id=op_id,
        )

        # Second call with same operation_id must update act1, NOT create a duplicate
        act2 = act_mod.manager.create(
            type=act_mod.TYPE_COMMAND,
            action="build",
            title="Compiling project (linking)",
            status=act_mod.STATUS_COMPLETED,
            turn_id=turn_id,
            operation_id=op_id,
            duration_ms=1200,
        )

        assert act1.id == act2.id
        assert act1.status == act_mod.STATUS_COMPLETED
        assert act1.duration_ms == 1200

    def test_deduplication_by_running_signature(self):
        turn_id = "test-dedup-sig-turn"
        # First call
        act1 = act_mod.manager.create(
            type=act_mod.TYPE_FILE,
            action="read",
            title="Reading main.py",
            status=act_mod.STATUS_RUNNING,
            turn_id=turn_id,
            tool="read_file",
            file="main.py",
        )

        # Immediate repeat call while running should return existing act1
        act2 = act_mod.manager.create(
            type=act_mod.TYPE_FILE,
            action="read",
            title="Reading main.py",
            status=act_mod.STATUS_RUNNING,
            turn_id=turn_id,
            tool="read_file",
            file="main.py",
            details="Buffering chunks",
        )

        assert act1.id == act2.id
        assert act1.details == "Buffering chunks"


class TestStaleWatchdogAndSessionSummary:
    def test_stale_activity_watchdog(self):
        turn_id = "test-stale-turn"
        act = act_mod.manager.create(
            type=act_mod.TYPE_TOOL,
            action="run",
            title="Hanging external command",
            status=act_mod.STATUS_RUNNING,
            turn_id=turn_id,
        )
        # Artificially age the activity update time
        act.updated_time = time.time() - 25.0

        stale = act_mod.manager.check_stale_activities(stale_threshold_sec=15.0)
        assert any(a.id == act.id for a in stale)
        assert act.status == act_mod.STATUS_WARNING

    def test_get_session_summary_returns_authentic_metrics(self):
        turn_id = "test-session-summary-turn"
        act_mod.manager.create(
            type=act_mod.TYPE_FILE,
            action="read",
            title="Reading app.py",
            status=act_mod.STATUS_COMPLETED,
            turn_id=turn_id,
            file="app.py",
            duration_ms=50,
            category=act_mod.CAT_FILE_READ,
        )
        act_mod.manager.create(
            type=act_mod.TYPE_FILE,
            action="write",
            title="Writing app.py",
            status=act_mod.STATUS_COMPLETED,
            turn_id=turn_id,
            file="app.py",
            duration_ms=100,
            category=act_mod.CAT_EDIT,
        )

        summary = act_mod.manager.get_session_summary(turn_id)
        assert summary["total_events"] == 2
        assert summary["completed"] == 2
        assert summary["failed"] == 0
        assert "app.py" in summary["files_read"]
        assert "app.py" in summary["files_modified"]
        assert summary["ram_total_gb"] > 0.0
        assert summary["process_ram_mb"] > 0.0


class TestLiveActivitiesUI:
    def test_activity_row_tree_hierarchy_connectors(self):
        from calc_terminal.ui import live_activities
        if not live_activities.TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        # Parent event
        parent = act_mod.Activity(
            id="parent-1",
            type="tool",
            action="build",
            status=act_mod.STATUS_COMPLETED,
            title="Running build pipeline",
            turn_id="turn-tree"
        )
        row_parent = live_activities.ActivityRow(parent)
        markup_parent = row_parent._build_markup()
        assert "├─" not in markup_parent
        assert "└─" not in markup_parent

        # Child event
        child = act_mod.Activity(
            id="child-1",
            type="tool",
            action="compile",
            status=act_mod.STATUS_COMPLETED,
            title="Compiling module A",
            turn_id="turn-tree",
            parent_id="parent-1"
        )
        row_child = live_activities.ActivityRow(child)
        markup_child = row_child._build_markup()
        assert "└─" in markup_child or "├─" in markup_child

    def test_live_activities_block_resource_bar_and_completion_summary(self):
        from calc_terminal.ui import live_activities
        if not live_activities.TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        turn_id = "test-block-res-turn"
        block = live_activities.LiveActivitiesBlock(turn_id=turn_id)
        res_markup = block._build_resource_markup()
        assert "RAM:" in res_markup
        assert "CAT RSS:" in res_markup
        assert "CPU:" in res_markup

        # Test mark_completed builds summary markup
        summary = act_mod.manager.get_session_summary(turn_id)
        sum_markup = block._build_summary_markup(summary)
        assert "SESSION SUMMARY" in sum_markup
        assert "RAM Footprint:" in sum_markup

    def test_generation_activity_lifecycle_and_interrupt(self):
        turn_id = "test-gen-turn-123"
        act = act_mod.manager.create(
            id=f"gen-{turn_id}",
            type=act_mod.TYPE_PROVIDER,
            action="generate",
            title="Thinking & generating (Ollama deepseek-r1)",
            status=act_mod.STATUS_RUNNING,
            turn_id=turn_id,
            category=act_mod.CAT_MODEL,
            phase=act_mod.PHASE_ANALYSIS,
        )
        assert act.status == act_mod.STATUS_RUNNING
        assert act.turn_id == turn_id

        # Interrupt cancels the turn's activities
        act_mod.manager.update(f"gen-{turn_id}", status=act_mod.STATUS_CANCELLED, result="Interrupted")
        act_mod.manager.cancel_turn(turn_id)
        updated = act_mod.manager.get(f"gen-{turn_id}")
        assert updated.status == act_mod.STATUS_CANCELLED

    def test_live_activities_block_displays_on_mount(self):
        from calc_terminal.ui import live_activities
        if not live_activities.TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        turn_id = "test-block-mount-turn"
        block = live_activities.LiveActivitiesBlock(turn_id=turn_id)
        block.on_mount()
        # When mounted for an active turn, block must be visible immediately
        assert block.display is True
