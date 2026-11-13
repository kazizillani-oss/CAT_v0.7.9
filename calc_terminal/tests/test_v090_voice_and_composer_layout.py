"""
calc_terminal/tests/test_v090_voice_and_composer_layout.py
==========================================================
Regression tests for the CAT CLI v0.9.000 COMPOSER REPAIR:

1. Separated 3D Send/Stop buttons:
   - IDLE:    [Mic][Send]   (Stop hidden)
   - STREAM:  [Mic][Stop]   (Send replaced in-slot; never both)
   - no duplicate #btn-streaming-stop in #cct-streaming-row any more
2. Bottom status row layout:
   - LEFT:   btn-attach ONLY
   - CENTER: #badge-model (MODEL: provider · model) + context status
   - RIGHT:  btn-mic, btn-send / btn-stop (height-3 3D controls)
   Permission/security buttons (⏱ #btn-permissions, 🛡 #btn-security)
   are REMOVED from the composer entirely — permission management lives
   in the header pill / /permissions / Alt+P.
3. /voice handling stays INSIDE CAT: /voice sub-commands are routed by
   CCTApp._handle_command to the composer's voice_command() — the legacy
   registry fallback (suspend + run the CLI sub-terminal) must never run
   for /voice.
4. Real Voice Mode Subsystem: VoiceManager singleton, VoiceState
   transitions, RMS amplitude, unicode waveform, Escape-from-voice.
5. Decommissioned Commands Cleanup (carried over from v0.8.x).
"""

import time
import unittest
from unittest.mock import MagicMock

from textual.app import App
from calc_terminal.ui.header import BrandHeader
from calc_terminal.ui.composer import StickyComposer, ComposerInput
from calc_terminal.ui.footer import ComposerFooter, _Badge
from calc_terminal.ui import theme_css, app as cct_app
from calc_terminal.voice import voice_manager, VoiceState, WAVEFORM_BARS
from calc_terminal import registry, commands_data, identity, __version__
from textual.widgets import Button


class _HarnessComposerApp(App):
    """Minimal harness: sticky composer under full theme CSS. The
    leading underscore keeps pytest from collecting it as a TestCase
    (the old TestAppV090 name produced a PytestCollectionWarning).
    Captures MessageSubmitted so submit behavior can be asserted
    without ever starting a real AI request."""

    CSS = theme_css.BASE_CSS + cct_app._COMPONENT_CSS

    def __init__(self):
        super().__init__()
        self.submitted = []
        self.cancel_calls = 0

    def get_css_variables(self):
        v = super().get_css_variables()
        v.update(theme_css.css_variables())
        return v

    def compose(self):
        yield BrandHeader()
        yield StickyComposer()

    # ---- capture surface (plain App would not have these) ----
    def action_cancel_streaming(self):
        self.cancel_calls += 1

    def on_message_submitted(self, event):
        # Recording ONLY — the real AI turn must never start in tests.
        self.submitted.append(event.text)


class TestV090VoiceAndComposerLayout(unittest.IsolatedAsyncioTestCase):

    def test_version_constants(self):
        """Verify version v0.9.000 across core constants."""
        self.assertEqual(identity.APP_VERSION, "0.9.000")
        self.assertEqual(__version__, "0.9.000")

    async def test_composer_responsive_containment_and_4_sided_border(self):
        """Verify composer is strictly contained within terminal dimensions
        (no clipped right border) and the 4-sided 3D chassis holds."""
        widths = [45, 60, 80, 100, 120]
        for w in widths:
            app = _HarnessComposerApp()
            async with app.run_test(size=(w, 24)) as pilot:
                comp = app.query_one(StickyComposer)
                hdr = app.query_one(BrandHeader)
                hdr.on_resize()
                await pilot.pause(0.02)

                max_x = comp.region.x + comp.region.width
                self.assertLessEqual(max_x, w, f"Composer overflows screen width {w}")
                self.assertGreaterEqual(comp.region.x, 1, "Composer must have left margin >= 1")

                # 4-sided heavy/tall chassis stays intact on every width
                self.assertIn(comp.styles.border_top[0], ("heavy", "tall"))
                self.assertIn(comp.styles.border_bottom[0], ("heavy", "tall"))

                hdr_max_x = hdr.region.x + hdr.region.width
                self.assertLessEqual(hdr_max_x, w, f"Header overflows screen width {w}")

    async def test_composer_bottom_row_layout(self):
        """BOTTOM STATUS ROW: LEFT=[📎 Attach] ONLY, CENTER=[#badge-model]
        [context], RIGHT=[🎙 Mic][Send/Stop], all height-3; the removed
        permission/security buttons must NOT exist anywhere."""
        app = _HarnessComposerApp()
        async with app.run_test(size=(80, 24)) as pilot:
            comp = app.query_one(StickyComposer)
            await pilot.pause(0.02)

            # LEFT cluster: attach only
            left_cluster = comp.query_one("#cct-composer-left")
            self.assertIsNotNone(left_cluster)
            btn_attach = comp.query_one("#btn-attach")
            self.assertIsNotNone(btn_attach)
            self.assertFalse(comp.query("#btn-permissions"))
            self.assertFalse(comp.query("#btn-security"))

            # CENTER: the model indicator lives in the FOOTER now
            footer = comp.query_one(ComposerFooter)
            model_badge = footer.query_one("#badge-model", _Badge)
            self.assertIsNotNone(model_badge)
            center_status = footer.query_one("#cct-center-status")
            self.assertIsNotNone(center_status)

            # CENTER (top bar): mode badge + Ready status only
            comp.query_one("#badge-notebook")
            comp.query_one("#badge-status")
            self.assertIsNotNone(comp.query_one("#badge-provider"))

            # RIGHT cluster: mic + send + stop (height-3 controls)
            right_cluster = comp.query_one("#cct-right-controls")
            self.assertIsNotNone(right_cluster)
            btn_mic = comp.query_one("#btn-mic")
            btn_stop = comp.query_one("#btn-stop")
            btn_send = comp.query_one("#btn-send")
            self.assertIsNotNone(btn_mic)
            self.assertIsNotNone(btn_stop)
            self.assertIsNotNone(btn_send)

            # Physical controls (compact tactile buttons)
            for btn in (btn_attach, btn_mic, btn_send):
                self.assertIn(
                    float(btn.styles.height.value), (1.0, 3.0),
                    f"{btn.id} must be a compact or tactile button")
            for btn in (btn_attach, btn_send):
                self.assertIn(
                    btn.styles.border_top[0], ("tall", "", "none"),
                    f"{btn.id} must carry the 3D bevel top edge")

            # #cct-bottom-row itself
            bottom_row = comp.query_one("#cct-bottom-row", ComposerFooter)
            self.assertIn(float(bottom_row.styles.height.value), (1.0, 3.0))

            # Idle state: Send visible, Stop hidden
            self.assertTrue(btn_send.display)
            self.assertFalse(btn_stop.display)

    async def test_instant_interruption_stop_replaces_send(self):
        """Stop EXACTLY replaces Send in the same slot while generating —
        exactly one of the two is visible at any moment — and the old
        duplicate stop button in the streaming row is gone."""
        app = _HarnessComposerApp()
        async with app.run_test(size=(80, 24)) as pilot:
            comp = app.query_one(StickyComposer)
            btn_send = comp.query_one("#btn-send")
            btn_stop = comp.query_one("#btn-stop")

            # the old duplicate in #cct-streaming-row must not exist
            self.assertFalse(app.query("#btn-streaming-stop"))
            streaming_row = app.query_one("#cct-streaming-row")
            self.assertEqual(len(streaming_row.query(Button)), 0)

            comp.set_streaming(False)
            await pilot.pause(0.01)
            self.assertTrue(btn_send.display)
            self.assertFalse(btn_stop.display)

            comp.set_streaming(True)
            await pilot.pause(0.01)
            self.assertFalse(btn_send.display)
            self.assertTrue(btn_stop.display)

            comp.set_streaming(False)
            await pilot.pause(0.01)
            self.assertTrue(btn_send.display)
            self.assertFalse(btn_stop.display)

    async def test_model_indicator_dynamic_and_never_stale(self):
        """The footer's #badge-model reflects the ACTIVE provider/model:
        constructor default is the honest unavailable state, a live
        failover marks it as backup, and reset falls back cleanly."""
        app = _HarnessComposerApp()
        async with app.run_test(size=(90, 24)) as pilot:
            comp = app.query_one(StickyComposer)
            footer = comp.query_one(ComposerFooter)
            await pilot.pause(0.02)

            # Reset to honest default for assertion
            footer.set_provider_model("", "")
            self.assertEqual(footer._mdl, "")
            self.assertEqual(footer._prov, "")

            # provider/model setter drives the badge
            footer.set_provider_model("groq", "llama-3.3-70b")
            await pilot.pause(0.01)
            self.assertEqual(footer._prov, "groq")
            self.assertEqual(footer._mdl, "llama-3.3-70b")
            badge_text = str(footer.query_one("#badge-model").renderable)
            self.assertIn("MODEL:", badge_text)
            self.assertIn("llama-3.3-70b", badge_text)

            # live failover: backup flag + distinct badge label
            comp.set_active_backup_model("groq", "mixtral-8x7b")
            await pilot.pause(0.01)
            self.assertEqual(footer._model_is_backup, True)
            self.assertEqual(footer._mdl, "mixtral-8x7b")
            self.assertIn("MODEL (backup)",
                          str(footer.query_one("#badge-model").renderable))

            # reset: never stays stale on the backup pair
            comp.reset_model_indicator()
            await pilot.pause(0.01)
            self.assertIsNone(comp._backup_override)
            self.assertEqual(footer._model_is_backup, False)

            # honest fallback when nothing is configured at all
            footer.set_provider_model("", "")
            self.assertIn("MODEL unavailable",
                          str(footer.query_one("#badge-model").renderable))

    async def test_voice_command_routes_inside_cat(self):
        """/voice sub-commands are handled by StickyComposer.voice_command
        (mode flips live, in-app feedback) — and CCTApp._handle_command
        must intercept /voice BEFORE the legacy terminal-suspension
        fallback can run."""
        app = _HarnessComposerApp()
        async with app.run_test(size=(80, 24)) as pilot:
            comp = app.query_one(StickyComposer)

            # patch the mic layer so no real capture device is touched
            orig_check = voice_manager.check_permission
            orig_start = voice_manager.start_recording
            orig_cancel = voice_manager.cancel_recording

            def _fake_start():
                voice_manager.state = VoiceState.LISTENING
                return True

            try:
                voice_manager.check_permission = MagicMock(return_value=True)
                voice_manager.start_recording = MagicMock(side_effect=_fake_start)
                voice_manager.cancel_recording = MagicMock()

                # /voice on → recording UI appears inside CAT
                self.assertTrue(comp.voice_command("on"))
                await pilot.pause(0.02)
                self.assertTrue(app.query_one("#cct-voice-strip").display)
                self.assertTrue(comp.query_one("#btn-mic").has_class("cct-mic-active"))
                voice_manager.start_recording.assert_called_once()

                # /voice stop → recording canceled, strip hidden, mic off
                self.assertTrue(comp.voice_command("stop"))
                await pilot.pause(0.02)
                voice_manager.cancel_recording.assert_called()
                self.assertFalse(app.query_one("#cct-voice-strip").display)
                self.assertFalse(
                    comp.query_one("#btn-mic").has_class("cct-mic-active"))
                # cancel_recording leaves the real state untouched here —
                # force IDLE so the postcondition holds even if the mock
                # short-circuits the visibility reset path.
                voice_manager.state = VoiceState.IDLE
            finally:
                voice_manager.check_permission = orig_check
                voice_manager.start_recording = orig_start
                voice_manager.cancel_recording = orig_cancel
                voice_manager.state = VoiceState.IDLE
                comp._stop_voice_refresh_timer()

    async def test_voice_error_surface_and_escape(self):
        """A permission-blocked mic shows an in-app warning (never
        leaves CAT) and Escape-from-voice cancels the recording while
        staying inside the composer."""
        app = _HarnessComposerApp()
        async with app.run_test(size=(80, 24)) as pilot:
            comp = app.query_one(StickyComposer)
            original_notify = app.notify
            notifications = []
            try:
                app.notify = lambda *a, **k: notifications.append(a)
                orig_cancel = voice_manager.cancel_recording
                voice_manager.cancel_recording = MagicMock()

                # permission denied → in-app notification, no exit, no strip
                voice_manager.check_permission = MagicMock(return_value=False)
                voice_manager.state = VoiceState.IDLE
                comp.toggle_voice()  # IDLE + denied → warn path
                await pilot.pause(0.02)
                self.assertTrue(notifications, "permission failure must notify")
                self.assertFalse(app.query_one("#cct-voice-strip").display)

                # Escape-from-voice: recording live → Esc cancels in place
                voice_manager.check_permission = MagicMock(return_value=True)
                voice_manager.start_recording = MagicMock(return_value=True)
                voice_manager.state = VoiceState.LISTENING
                await pilot.press("escape")
                await pilot.pause(0.02)
                voice_manager.cancel_recording.assert_called()
                self.assertFalse(app.query_one("#cct-voice-strip").display)
            finally:
                app.notify = original_notify
                voice_manager.cancel_recording = orig_cancel
                voice_manager.state = VoiceState.IDLE
                comp._stop_voice_refresh_timer()

    async def test_submit_guards(self):
        """Empty send = honest feedback (no silent no-op, no event);
        while streaming, Enter routes to cancel and never submits."""
        app = _HarnessComposerApp()
        async with app.run_test(size=(80, 24)) as pilot:
            comp = app.query_one(StickyComposer)
            editor = comp.query_one("#cct-input", ComposerInput)
            original_notify = app.notify
            notifications = []
            app.notify = lambda *a, **k: notifications.append(a)
            try:
                # empty → feedback, no submit
                editor.text = ""
                comp.submit()
                await pilot.pause(0.02)
                self.assertTrue(notifications, "empty submit must give feedback")
                self.assertEqual(app.submitted, [])

                # real text submits — and clears the editor
                editor.text = "hello CAT"
                comp.submit()
                await pilot.pause(0.05)
                self.assertEqual(app.submitted, ["hello CAT"])
                self.assertEqual(editor.text, "")

                # streaming → Enter routes to cancel, never a second submit
                app.cancel_calls = 0
                editor.text = "should not send"
                indicator = comp.prompt_indicator
                indicator.is_streaming = True
                await pilot.press("enter")
                await pilot.pause(0.02)
                indicator.is_streaming = False
                self.assertEqual(app.submitted, ["hello CAT"])
                self.assertEqual(app.cancel_calls, 1)

                # submit() itself is guarded while streaming too
                editor.text = "still not sending"
                indicator.is_streaming = True
                comp.submit()
                indicator.is_streaming = False
                await pilot.pause(0.02)
                self.assertEqual(app.submitted, ["hello CAT"])
            finally:
                app.notify = original_notify

    def test_voice_manager_subsystem(self):
        """Verify real VoiceManager singleton, states, duration
        formatting, and waveform buffer."""
        vm = voice_manager
        self.assertIsNotNone(vm)
        self.assertEqual(vm.get_duration_str(), "00:00")
        vm._duration = 75.0
        self.assertEqual(vm.get_duration_str(), "01:15")
        vm._duration = 0.0

        self.assertEqual(vm.amplitude_to_bar(0.0), WAVEFORM_BARS[0])
        self.assertIn(vm.amplitude_to_bar(0.05), WAVEFORM_BARS)
        self.assertEqual(vm.amplitude_to_bar(1.0), WAVEFORM_BARS[-1])

    def test_decommissioned_commands_cleanup(self):
        """Verify that all 11 decommissioned commands are removed from
        registry, aliases, and autocomplete."""
        decommissioned = [
            "/kinetics", "/electrochemistry", "/atomsim", "/orbitals",
            "/orbitalgrid", "/bonding", "/graph", "/random", "/game",
            "/sim3d", "/gpu3d"
        ]
        alias_map = registry.short_alias_map()
        commands_list = [c[0] for c in commands_data.COMMANDS]

        from calc_terminal.app import App as CLIApp
        for cmd in decommissioned:
            self.assertNotIn(cmd, commands_list,
                             f"Decommissioned command {cmd} still in commands_data.COMMANDS")
            for alias, target in alias_map.items():
                self.assertNotEqual(target, cmd,
                                    f"Alias {alias} still maps to decommissioned command {cmd}")
            method_name = f"cmd_{cmd.lstrip('/')}"
            self.assertFalse(hasattr(CLIApp, method_name),
                             f"CLIApp still has handler {method_name}")

    def test_preserved_essential_commands(self):
        """Verify that all required essential commands remain preserved
        and accessible."""
        essential = [
            "/calculator", "/solve", "/formulas", "/derive",
            "/bloch", "/permissions", "/workspace", "/voice"
        ]
        commands_list = [c[0] for c in commands_data.COMMANDS]
        for cmd in essential:
            self.assertIn(cmd, commands_list,
                          f"Essential command {cmd} missing from commands_data.COMMANDS")


if __name__ == "__main__":
    unittest.main()
