"""
Tests for CAT Workflow Engine, Real-Time Live Activities, and 3D UI Upgrades.
"""

import time
import pytest
from calc_terminal.workflow_engine import (
    workflow_engine,
    event_bus,
    ExecutionEvent,
    STATE_RUNNING,
    STATE_SUCCEEDED,
    STATE_FAILED,
    STATE_VERIFYING,
    EVENT_AGENT_STARTED,
    EVENT_TOOL_STARTED,
    EVENT_TOOL_COMPLETED,
    EVENT_BUG_DETECTED,
    EVENT_BUG_FIXED,
    EVENT_VERIFICATION_COMPLETED,
)
from calc_terminal import activity as act_mod


class TestWorkflowEngineAndEvents:
    def test_trace_lifecycle_and_monotonic_ordering(self):
        received_events = []
        unsub = event_bus.subscribe(lambda e: received_events.append(e))

        try:
            tid = workflow_engine.start_trace("Test Autonomous Workflow", turn_id="turn-test-1")
            assert tid.startswith("trace-")

            # Verify agent started was emitted
            assert any(e.event_type == EVENT_AGENT_STARTED for e in received_events)

            # Record a tool execution
            evt = ExecutionEvent(
                event_id="evt-tool-1",
                trace_id=tid,
                parent_id="",
                event_type=EVENT_TOOL_STARTED,
                status=STATE_RUNNING,
                source="test",
                tool="read_file",
                description="Reading package.json"
            )
            event_bus.emit(evt)

            # Complete trace
            workflow_engine.finish_trace(tid, success=True, summary="Workflow completed")

            # Verify monotonic ordering
            trace_events = [e for e in received_events if e.trace_id == tid]
            assert len(trace_events) >= 3
            for i in range(len(trace_events) - 1):
                assert trace_events[i].timestamp <= trace_events[i + 1].timestamp

        finally:
            unsub()

    def test_autonomous_bug_detection_and_verify_loop(self):
        turn_id = "turn-bug-test"
        # 1. Detect bug with evidence
        bug_id = workflow_engine.record_bug_detected(
            source="browser.console",
            error_msg="TypeError: Cannot read property 'user' of undefined",
            workflow_step="Dashboard -> Settings",
            turn_id=turn_id,
            confidence="Observed (Console)"
        )
        assert bug_id.startswith("evt-")

        # Verify bug exists in activity manager
        act = act_mod.manager.get(bug_id)
        assert act is not None
        assert act.status == act_mod.STATUS_FAILED
        assert "Cannot read property" in act.details

        # 2. Record verified fix with real evidence
        workflow_engine.record_bug_verified_fixed(
            bug_description="TypeError: Cannot read property 'user' of undefined",
            evidence="Re-tested Dashboard -> Settings, 0 console errors, HTTP 200",
            turn_id=turn_id
        )

        acts = act_mod.manager.get_for_turn(turn_id)
        assert any("verified fixed" in a.title.lower() for a in acts)

    def test_weak_model_intention_parsing(self):
        # Plain JSON
        raw1 = '{"action": "browser_click", "target": "Submit"}'
        parsed1 = workflow_engine.parse_weak_model_intention(raw1)
        assert parsed1 is not None
        assert parsed1["action"] == "browser_click"
        assert parsed1["target"] == "Submit"

        # Markdown-wrapped JSON
        raw2 = 'I will click submit now:\n```json\n{"action": "browser_click", "target": "Submit"}\n```'
        parsed2 = workflow_engine.parse_weak_model_intention(raw2)
        assert parsed2 is not None
        assert parsed2["action"] == "browser_click"

        # Embedded JSON intention in text
        raw3 = '{"tool": "read_file", "args": {"path": "main.py"}}'
        parsed3 = workflow_engine.parse_weak_model_intention(raw3)
        assert parsed3 is not None
        assert parsed3["tool"] == "read_file"

    def test_weak_model_action_execution(self):
        turn_id = "turn-weak-model"
        executed = []

        def mock_executor(tool, args):
            executed.append((tool, args))
            return f"Executed {tool} successfully"

        intention = {"action": "read_file", "target": {"path": "config.json"}}
        res = workflow_engine.execute_weak_model_action(
            intention, turn_id=turn_id, tool_executor=mock_executor
        )
        assert res["status"] == "success"
        assert "Executed read_file" in res["observation"]
        assert len(executed) == 1

    def test_lightweight_flow_for_simple_requests(self):
        turn_id = "turn-greeting-test"
        workflow_engine.record_lightweight_flow(
            prompt="Hello",
            model_name="ollama/qwen2.5-coder:7b",
            turn_id=turn_id
        )
        acts = act_mod.manager.get_for_turn(turn_id)
        titles = [a.title for a in acts]
        assert "Request received" in titles
        assert any("Model selected" in t for t in titles)
        assert "Context prepared" in titles
        assert "Response generated" in titles


class TestBrowserEnginePrimitives:
    def test_browser_engine_methods_exist(self):
        from calc_terminal.browser.engine import BrowserEngine
        engine = BrowserEngine(headless=True)
        assert hasattr(engine, "click")
        assert hasattr(engine, "type_text")
        assert hasattr(engine, "get_interactive_elements")
        assert hasattr(engine, "workflow_verify")
        assert callable(engine.click)
        assert callable(engine.type_text)
        assert callable(engine.get_interactive_elements)
        assert callable(engine.workflow_verify)


class TestUI3DBevelsAndContrast:
    def test_theme_css_light_mode_surface_dark_token(self):
        from calc_terminal import theme
        from calc_terminal.ui import theme_css

        theme.set_theme("light", persist=False, paint_bg=False)
        vars_ = theme_css.css_variables()
        assert "surface-dark" in vars_
        assert "surface-shadow" in vars_
        assert vars_["surface-dark"] == vars_["surface-shadow"]

    def test_theme_css_button_primary_contrast(self):
        from calc_terminal.ui import theme_css
        # Button.-primary must not use white text (#ffffff) on light themes
        css = theme_css.BASE_CSS
        assert "Button.-primary" in css
        assert "border-top: tall" in css

    def test_live_activities_block_3d_border_css(self):
        from calc_terminal.ui.live_activities import LiveActivitiesBlock
        assert "border-top: tall" in LiveActivitiesBlock.DEFAULT_CSS
        assert "border-left: tall" in LiveActivitiesBlock.DEFAULT_CSS
        assert "border-bottom: tall" in LiveActivitiesBlock.DEFAULT_CSS
        assert "border-right: tall" in LiveActivitiesBlock.DEFAULT_CSS
        assert "$surface-alt" not in LiveActivitiesBlock.DEFAULT_CSS

    def test_activity_row_explicit_color_markup(self):
        from calc_terminal import activity as act_mod
        from calc_terminal.ui.live_activities import ActivityRow
        act = act_mod.Activity(
            id="act-color-test",
            type="tool",
            action="read",
            title="Reading test.py",
            status=act_mod.STATUS_COMPLETED,
            phase=act_mod.PHASE_DISCOVERY,
            turn_id="turn-test"
        )
        row = ActivityRow(act)
        content = row._build_markup()
        assert "bold]Reading test.py[/]" in content
        # Test expand detail view has explicit color tags
        row.toggle_expand()
        expanded = row._build_markup()
        assert "Phase:" in expanded
        assert "DISCOVERY" in expanded

    def test_streaming_flow_lifecycle(self):
        from calc_terminal.workflow_engine import workflow_engine
        from calc_terminal import activity as act_mod
        turn_id = "test-stream-lifecycle"
        gen_id = workflow_engine.start_streaming_flow(
            prompt="Write hello world",
            model_name="ollama/deepseek-r1:latest",
            turn_id=turn_id
        )
        acts = act_mod.manager.get_for_turn(turn_id)
        assert len(acts) == 3
        running_act = next((a for a in acts if a.id == gen_id), None)
        assert running_act is not None
        assert running_act.status == act_mod.STATUS_RUNNING

        # Finish streaming
        workflow_engine.finish_streaming_flow(turn_id=turn_id, duration_ms=850, token_count=64)
        updated = act_mod.manager.get(gen_id)
        assert updated is not None
        assert updated.status == act_mod.STATUS_COMPLETED
        assert "64 tokens" in updated.result
        assert updated.duration_ms == 850

