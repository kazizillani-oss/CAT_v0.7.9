"""
Tests for CAT CLI Real-Time Live Activities Redesign and AI Model Failover.
"""

import os
import time
import pytest
from calc_terminal import activity as act_mod
from calc_terminal.ui import live_activities
from calc_terminal.providers import provider_manager
from calc_terminal import aicore


class TestActivitySystem:
    def test_canonical_categories_and_statuses(self):
        # Spec Section 1: Event categories
        expected_cats = {
            "SEARCH", "FILE_READ", "EDIT", "TERMINAL", "TEST", "BUILD",
            "ANALYSIS", "GIT", "PLANNING", "SUBAGENT", "SYSTEM", "MODEL"
        }
        for cat in expected_cats:
            assert cat in act_mod.CATEGORIES
            assert getattr(act_mod, f"CAT_{cat}") == cat

        # Spec Section 3: Statuses
        assert act_mod.STATUS_RUNNING == "running"
        assert act_mod.STATUS_COMPLETED == "completed"
        assert act_mod.STATUS_FAILED == "failed"
        assert act_mod.STATUS_CANCELLED == "cancelled"
        assert act_mod.STATUS_WAITING_PERMISSION == "waiting_permission"

        # Backwards compat aliases
        assert act_mod.RUNNING == "running"
        assert act_mod.COMPLETED == "completed"
        assert act_mod.FAILED == "failed"

    def test_phases_and_icons(self):
        assert act_mod.PHASE_DISCOVERY == "DISCOVERY"
        assert act_mod.PHASE_ANALYSIS == "ANALYSIS"
        assert act_mod.PHASE_IMPLEMENTATION == "IMPLEMENTATION"
        assert act_mod.PHASE_VALIDATION == "VALIDATION"
        assert act_mod.PHASE_COMPLETE == "COMPLETE"

        assert act_mod.PHASE_ICONS[act_mod.PHASE_DISCOVERY] == "⌕"
        assert act_mod.PHASE_ICONS[act_mod.PHASE_ANALYSIS] == "🧠"
        assert act_mod.PHASE_ICONS[act_mod.PHASE_IMPLEMENTATION] == "✎"
        assert act_mod.PHASE_ICONS[act_mod.PHASE_VALIDATION] == "▶"
        assert act_mod.PHASE_ICONS[act_mod.PHASE_COMPLETE] == "✓"

    def test_tool_meta_unpacking_and_phases(self):
        # 3-tuple unpacking compatibility
        meta = act_mod.meta_for_tool("read_file")
        ttype, taction, ttitle = meta
        assert taction == "read"
        assert meta.category == act_mod.CAT_FILE_READ
        assert meta.phase == act_mod.PHASE_DISCOVERY

        meta_edit = act_mod.meta_for_tool("edit_file")
        assert meta_edit.category == act_mod.CAT_EDIT
        assert meta_edit.phase == act_mod.PHASE_IMPLEMENTATION

        meta_test = act_mod.meta_for_tool("run_tests")
        assert meta_test.category == act_mod.CAT_TEST
        assert meta_test.phase == act_mod.PHASE_VALIDATION

        meta_search = act_mod.meta_for_tool("search_workspace")
        assert meta_search.category == act_mod.CAT_SEARCH
        assert meta_search.phase == act_mod.PHASE_DISCOVERY

    def test_activity_lifecycle(self):
        turn_id = "test-turn-lifecycle"
        act = act_mod.manager.create(
            type="file", action="read", title="Reading test.py",
            status=act_mod.STATUS_RUNNING, turn_id=turn_id,
            tool="read_file", target_path="test.py",
            category=act_mod.CAT_FILE_READ, phase=act_mod.PHASE_DISCOVERY
        )
        assert act.id is not None
        assert act.category == act_mod.CAT_FILE_READ
        assert act.phase == act_mod.PHASE_DISCOVERY
        assert act.target_path == "test.py"
        assert act.file == "test.py"

        # Update with result and line count
        updated = act_mod.manager.update(
            act.id, status=act_mod.STATUS_COMPLETED,
            result="145 lines", line_count=145, duration_ms=25
        )
        assert updated is not None
        assert updated.status == act_mod.STATUS_COMPLETED
        assert updated.line_count == 145
        assert updated.duration_ms == 25

        summary = act_mod.manager.turn_summary(turn_id)
        assert summary["count"] == 1
        assert summary["completed"] == 1
        assert summary["failed"] == 0


class TestLiveActivitiesUI:
    def test_live_activities_block_init(self):
        if not live_activities.TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        block = live_activities.LiveActivitiesBlock(turn_id="test-ui-turn")
        # Block should start with display = False per empty state spec
        # (Only made visible when real activities arrive)
        assert block.turn_id == "test-ui-turn"
        assert block.activity_count() == 0

    def test_activity_row_content_rendering(self):
        if not live_activities.TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        act = act_mod.Activity(
            id="act-test-1",
            type="tool",
            action="search",
            status=act_mod.STATUS_RUNNING,
            title="Searching for \"calc_terminal\"",
            category=act_mod.CAT_SEARCH,
            phase=act_mod.PHASE_DISCOVERY,
            query="calc_terminal"
        )
        row = live_activities.ActivityRow(act)
        content = row._build_markup()
        # Should contain spinner or search title
        assert "Searching for" in content

        # Update to completed
        act.status = act_mod.STATUS_COMPLETED
        act.result = "12 matches"
        act.duration_ms = 45
        row.update_activity(act)
        content_completed = row._build_markup()
        assert "✓" in content_completed
        assert "12 matches" in content_completed
        assert "45ms" in content_completed

        # Test expand detail view
        row.toggle_expand()
        expanded_content = row._build_markup()
        assert "Phase:" in expanded_content
        assert "DISCOVERY" in expanded_content
        assert "Query:" in expanded_content
        assert "calc_terminal" in expanded_content
        assert "tap to collapse" in expanded_content

    def test_waiting_permission_card_rendering(self):
        if not live_activities.TEXTUAL_AVAILABLE:
            pytest.skip("Textual not available")

        act = act_mod.Activity(
            id="act-perm-1",
            type="permission",
            action="run_terminal",
            status=act_mod.STATUS_WAITING_PERMISSION,
            title="Execute terminal command: npm test",
            command="npm test",
            category=act_mod.CAT_SYSTEM,
            phase=act_mod.PHASE_IMPLEMENTATION
        )
        row = live_activities.ActivityRow(act)
        content = row._build_markup()
        assert "Permission Required" in content
        assert "Allow" in content
        assert "Deny" in content


class TestFailoverAndEnvKeys:
    def test_get_env_api_key(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEY", "nv-test-key-12345")
        assert provider_manager.get_env_api_key("nvidia") == "nv-test-key-12345"

        monkeypatch.setenv("GROQ_API_KEY", "gsk-test-key-67890")
        assert provider_manager.get_env_api_key("groq") == "gsk-test-key-67890"

        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-11111")
        assert provider_manager.get_env_api_key("openrouter") == "sk-or-test-11111"

    def test_backup_configs_auto_resolves_env_keys(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk-groq-live")
        backups = provider_manager.backup_configs()
        groq_cfg = next((cfg for cfg, entry in backups if cfg.get("provider") == "groq"), None)
        if groq_cfg:
            assert groq_cfg.get("api_key") == "gsk-groq-live"
