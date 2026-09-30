import unittest
from textual.app import App
from calc_terminal import ai_modes
from calc_terminal.ui.mode_colors_panel import ModeColorsPanel, _PRESETS
from calc_terminal.ui.permission_panel import PermissionCard


class KittiesTestApp(App):
    def compose(self):
        yield ModeColorsPanel()
        yield PermissionCard("req-123", "write_files", "Write file", "Updating index.html", path="index.html")


class TestKittiesRedesign(unittest.IsolatedAsyncioTestCase):
    def test_default_modes_clean(self):
        # Ensure default modes are strictly the 6 canonical modes
        expected_defaults = ["notebook", "research", "plan", "build", "debugger", "agent"]
        self.assertEqual(ai_modes.MODE_ORDER[:6], expected_defaults)
        for mode in expected_defaults:
            self.assertIn(mode, ai_modes.MODE_META)
            info = ai_modes.get_mode_info(mode)
            self.assertTrue(len(info["purpose"]) > 10)

    def test_palette_presets_configuration(self):
        # Ensure presets list has 8 distinct curated chiclet colors
        self.assertEqual(len(_PRESETS), 8)
        for hx in _PRESETS:
            self.assertTrue(hx.startswith("#"))
            self.assertEqual(len(hx), 7)

    async def test_panel_mount_and_ui_elements(self):
        app = KittiesTestApp()
        async with app.run_test() as pilot:
            panel = app.query_one(ModeColorsPanel)
            self.assertIsNotNone(panel)
            # Verify close button
            close_btn = app.query_one("#mcc-close")
            self.assertIsNotNone(close_btn)
            self.assertEqual(str(close_btn.label).strip(), "✕ Close")

            # Verify action bar buttons
            new_btn = app.query_one("#mcc-action-new")
            self.assertIsNotNone(new_btn)
            self.assertEqual(str(new_btn.label).strip(), "＋ Create Agent")

            clone_btn = app.query_one("#mcc-action-clone")
            self.assertIsNotNone(clone_btn)
            self.assertEqual(str(clone_btn.label).strip(), "⚡ Fast Clone")

            share_btn = app.query_one("#mcc-action-share")
            self.assertIsNotNone(share_btn)
            self.assertEqual(str(share_btn.label).strip(), "🔄 Delegation")

            # Verify palette swatches are present and backgrounds set
            preset_0 = app.query_one("#mcc-preset-0")
            self.assertIsNotNone(preset_0)
            self.assertEqual(str(preset_0.styles.background), "Color(122, 162, 247)")

            # Verify PermissionCard buttons
            perm_card = app.query_one(PermissionCard)
            self.assertIsNotNone(perm_card)
            cancel_btn = perm_card.query_one("#cancel")
            self.assertIsNotNone(cancel_btn)
            self.assertEqual(str(cancel_btn.label).strip(), "✕ Cancel")

    def test_create_custom_agent_and_clone(self):
        # 1. Test creating a custom agent easily
        ok, res = ai_modes.create_mode(
            key="test_bot",
            label="Test Bot",
            icon="🚀",
            accent_hex="#38bdf8",
            purpose="Specialized test agent with full laptop automation",
            system_prompt="You are a test bot with full computer automation authority."
        )
        self.assertTrue(ok)
        self.assertIn("test_bot", ai_modes.MODE_META)
        self.assertIn("test_bot", ai_modes.MODE_ORDER)

        # 2. Test cloning an active agent
        cur = "test_bot"
        cur_info = ai_modes.get_mode_info(cur)
        clone_key = "test_bot_clone"
        ok_clone, msg_clone = ai_modes.create_mode(
            key=clone_key,
            label=f"{cur_info['label']} (Clone)",
            icon="⚡",
            accent_hex="#ff69b4",
            purpose=cur_info["purpose"],
            system_prompt=cur_info["system_prompt"]
        )
        self.assertTrue(ok_clone)
        self.assertIn(clone_key, ai_modes.MODE_META)

        # 3. Clean up custom test modes
        ai_modes.delete_mode("test_bot")
        ai_modes.delete_mode(clone_key)
        self.assertNotIn("test_bot", ai_modes.MODE_META)
        self.assertNotIn(clone_key, ai_modes.MODE_META)

    def test_weak_model_writefile_action_normalization(self):
        from calc_terminal.workflow_engine import workflow_engine
        raw = '{"action": "writefile", "path": "styles.css", "content": "/* Global Resets */\\nbody { margin: 0; }"}'
        parsed = workflow_engine.parse_weak_model_intention(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.get("action"), "writefile")
        self.assertEqual(parsed.get("path"), "styles.css")

        executed = workflow_engine.execute_weak_model_action(
            parsed,
            tool_executor=lambda a, args: {"action": a, "args": args}
        )
        self.assertEqual(executed["status"], "success")
        obs = executed["observation"]
        self.assertEqual(obs["action"], "write_file")
        self.assertEqual(obs["args"]["path"], "styles.css")
        self.assertIn("Global Resets", obs["args"]["content"])

    async def test_kitties_actions_lifecycle(self):
        app = KittiesTestApp()
        async with app.run_test() as pilot:
            panel = app.query_one(ModeColorsPanel)

            # 1. Fast Clone
            cur = ai_modes.current_mode()
            panel.on_button_pressed(type("E", (), {"button": panel.query_one("#mcc-action-clone")})())
            await pilot.pause()
            clone_key = f"{cur}_clone"
            self.assertIn(clone_key, ai_modes.MODE_ORDER)

            # 2. Delegation
            panel.on_button_pressed(type("E", (), {"button": panel.query_one("#mcc-action-share")})())
            await pilot.pause()

            # 3. Edit & Save
            panel.on_button_pressed(type("E", (), {"button": panel.query_one(f"#mcc-toggle-edit-{cur}")})())
            await pilot.pause()
            eb = panel.query_one(f"#mcc-edit-{cur}")
            self.assertIn("show", eb.classes)

            panel.query_one(f"#mcc-label-{cur}").value = "Renamed Persona"
            panel.on_button_pressed(type("E", (), {"button": panel.query_one(f"#mcc-save-{cur}")})())
            await pilot.pause()
            self.assertEqual(ai_modes.get_mode_info(cur)["label"], "Renamed Persona")

            # 4. Activate
            panel.on_button_pressed(type("E", (), {"button": panel.query_one("#mcc-activate-build")})())
            await pilot.pause()
            self.assertEqual(ai_modes.current_mode(), "build")

            # Clean up cloned mode and restore defaults so tests don't leave user modes modified
            ai_modes.delete_mode(clone_key)
            ai_modes.reset_all_modes()

    async def test_build_mode_visibility_and_meta(self):
        # Verify build mode is always in MODE_ORDER with correct icon and label
        self.assertIn("build", ai_modes.MODE_ORDER)
        info = ai_modes.get_mode_info("build")
        self.assertEqual(info["label"], "Build")
        self.assertEqual(info["icon"], "🔨")
        self.assertIn("Software Engineering", info["purpose"])

        app = KittiesTestApp()
        async with app.run_test() as pilot:
            panel = app.query_one(ModeColorsPanel)
            self.assertIsNotNone(panel)
            # Verify the build mode row exists and displays Build
            build_row = panel.query_one("#mcc-row-build")
            self.assertIsNotNone(build_row)
            lbl = build_row.query_one(".mcc-label")
            self.assertIn("Build", str(lbl.render()))
            key = build_row.query_one(".mcc-key")
            self.assertIn("/build", str(key.render()))

    async def test_ai_mode_multi_line_prompt_editing(self):
        app = KittiesTestApp()
        async with app.run_test() as pilot:
            panel = app.query_one(ModeColorsPanel)
            # 1. Expand editor on build mode
            panel.on_button_pressed(type("E", (), {"button": panel.query_one("#mcc-toggle-edit-build")})())
            await pilot.pause()

            # 2. Check prompt editor widget
            prompt_editor = panel.query_one("#mcc-prompt-build")
            self.assertIsNotNone(prompt_editor)

            # 3. Enter a multi-line system prompt
            multiline_text = (
                "You are CAT AI in Build Mode.\n"
                "Rule 1: Always write production-grade code.\n"
                "Rule 2: Never truncate files.\n"
                "Rule 3: Verify all test cases before declaring victory."
            )
            prompt_editor.value = multiline_text
            self.assertEqual(prompt_editor.value, multiline_text)

            # 4. Save
            panel.on_button_pressed(type("E", (), {"button": panel.query_one("#mcc-save-build")})())
            await pilot.pause()

            # 5. Verify saved prompt in ai_modes
            build_info = ai_modes.get_mode_info("build")
            self.assertEqual(build_info["system_prompt"], multiline_text)

            # 6. Restore defaults
            ai_modes.reset_all_modes()


if __name__ == "__main__":
    unittest.main()

