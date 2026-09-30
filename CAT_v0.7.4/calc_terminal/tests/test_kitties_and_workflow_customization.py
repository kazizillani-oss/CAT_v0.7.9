import unittest
from calc_terminal import ai_modes
from calc_terminal.workflow_engine import workflow_engine, WorkflowCLICustomizer, event_bus
from calc_terminal.agent import TOOLS
from calc_terminal.ui.permission_panel import PermissionCard, QuestionCard
from calc_terminal.ui.mode_colors_panel import ModeColorsPanel, _ModeRow


class TestKittiesAndWorkflowCustomization(unittest.TestCase):
    def test_kitties_and_bot_presets(self):
        # 1. Verify Kitty aliases
        self.assertEqual(ai_modes.current_kitty(), ai_modes.current_mode())
        self.assertIn("grok", ai_modes.AGENT_PRESET_TEMPLATES)
        self.assertIn("dots", ai_modes.AGENT_PRESET_TEMPLATES)

        # 2. Test spawning Grok Kitty
        ok, msg = ai_modes.spawn_preset_kitty("grok")
        self.assertTrue(ok)
        self.assertIn("grok", ai_modes.MODE_META)
        grok_meta = ai_modes.MODE_META["grok"]
        self.assertEqual(grok_meta["label"], "Grok Kitty")
        self.assertEqual(grok_meta["icon"], "⚡")

        # 3. Test spawning Dots Kitty
        ok, msg = ai_modes.spawn_preset_kitty("dots")
        self.assertTrue(ok)
        self.assertIn("dots", ai_modes.MODE_META)
        dots_meta = ai_modes.MODE_META["dots"]
        self.assertEqual(dots_meta["label"], "Dots Kitty")
        self.assertEqual(dots_meta["icon"], "⚪")

        # 4. Verify system prompt routing for custom kitties
        prompt_grok = ai_modes.system_prompt_for("grok")
        self.assertIn("Grok Kitty", prompt_grok)

        prompt_dots = ai_modes.system_prompt_for("dots")
        self.assertIn("Dots Kitty", prompt_dots)

    def test_workflow_point_to_point_and_cli_customizer(self):
        # 1. Test point-to-point event recording
        p2p_id = workflow_engine.record_point_to_point_step(
            source_node="source_test_node",
            target_node="target_test_node",
            step_name="Validate Code Transform",
            payload={"input_key": "input_val"},
            result="Success",
            duration_ms=42
        )
        self.assertTrue(p2p_id.startswith("evt-p2p-"))

        # Verify event on event bus
        events = event_bus.get_events()
        matching = [e for e in events if e.event_id == p2p_id]
        self.assertEqual(len(matching), 1)
        evt = matching[0]
        self.assertEqual(evt.source_node, "source_test_node")
        self.assertEqual(evt.target_node, "target_test_node")
        self.assertEqual(evt.payload.get("input_key"), "input_val")

        # 2. Test WorkflowCLICustomizer
        custom_res = WorkflowCLICustomizer.apply_customizations(
            {"eco_mode": True, "low_end_device_optimization": True},
            reason="Test CLI Workflow Optimization"
        )
        self.assertTrue(custom_res.get("success"))
        self.assertTrue(custom_res["applied"].get("eco_mode"))

        settings = WorkflowCLICustomizer.get_current_settings()
        self.assertTrue(settings.get("eco_mode"))

    def test_agent_tools_registered(self):
        self.assertIn("ask_question", TOOLS)
        self.assertIn("customize_cat_cli", TOOLS)

        # Test customize_cat_cli tool execution
        tool_fn = TOOLS["customize_cat_cli"]["run"]
        res = tool_fn({"settings": {"eco_mode": False}, "reason": "Revert test"})
        self.assertIn("customized successfully", res)

    def test_permission_and_question_cards(self):
        perm_card = PermissionCard(
            request_id="test-req-1",
            key="write_file",
            action_text="Write File",
            reason_text="Testing permission card buttons",
            path="test.py"
        )
        self.assertEqual(perm_card.request_id, "test-req-1")

        q_card = QuestionCard(
            request_id="test-q-1",
            question="Which database engine do you want to configure?",
            options=["SQLite", "PostgreSQL", "DuckDB"]
        )
        self.assertEqual(len(q_card.options), 3)


if __name__ == "__main__":
    unittest.main()
