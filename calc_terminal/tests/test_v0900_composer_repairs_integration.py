"""
calc_terminal/tests/test_v0900_composer_repairs_integration.py
==============================================================
Integration-level tests for the v0.9.000 composer repair work that
crosses component boundaries:

1. /voice and /permissions slash-command ROUTING inside the TUI —
   CCTApp._handle_command must intercept them BEFORE the legacy
   command-registry fallback, so the app is never suspended to run the
   classic CLI's handlers ("the /voice exit bug").
2. Failover → live model indicator: the aicore failover notes
   ("Switching to Backup Provider (prov (model))" + "✓ Connected
   successfully.") must install the backup provider/model on the
   footer's #badge-model ONLY after the connection is confirmed, and
   the reset paths must fall back to the on-disk config.
3. Capability-aware attachment warnings: a user attaching an image on
   a provider that takes no native image input gets the honest
   "text/OCR fallback only" note — no fake vision, no silent discard.
4. Mini run_test sweeps: attachment chip + submit at multiple widths.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from textual.app import App, ComposeResult
from textual.widgets import Button

from calc_terminal.ui import theme_css
from calc_terminal.ui.app import CCTApp, _COMPONENT_CSS
from calc_terminal.ui.composer import StickyComposer, ComposerInput
from calc_terminal.ui.footer import ComposerFooter
from calc_terminal.ui.attachments import _vision_warning
from calc_terminal.voice import voice_manager, VoiceState


class _FailoverStub:
    """Minimal stand-in with exactly the attributes
    CCTApp._on_failover_message touches, plus a zero-copy
    call_from_thread (we are already on a single thread here)."""

    def __init__(self):
        self._pending_failover_notes = []
        self._failover_target_pending = None
        self.applied = []
        self.composer = MagicMock()

        def _direct(fn, *args, **kwargs):
            fn(*args, **kwargs)
        self.call_from_thread = _direct


class _SubmitCatcherApp(App):
    """Harness that records MessageSubmitted without ever starting a
    real AI request, and records cancel actions."""

    CSS = theme_css.BASE_CSS + _COMPONENT_CSS

    def __init__(self):
        super().__init__()
        self.submitted = []
        self.cancel_calls = 0

    def get_css_variables(self):
        v = super().get_css_variables()
        v.update(theme_css.css_variables())
        return v

    def compose(self) -> ComposeResult:
        yield StickyComposer()

    def action_cancel_streaming(self):
        self.cancel_calls += 1

    def on_message_submitted(self, event):
        self.submitted.append(event.text)


class TestSlashCommandRouting(unittest.IsolatedAsyncioTestCase):
    """/voice and /permissions must be handled by the TUI itself."""

    def _open_app(self):
        return CCTApp(MagicMock(), [], MagicMock())

    async def test_voice_command_never_suspends_terminal(self):
        app = self._open_app()
        with patch.object(CCTApp, "_run_in_suspended_terminal",
                          autospec=True) as suspend:
            async with app.run_test() as pilot:
                await pilot.pause()
                if type(app.screen).__name__ == "WelcomeModal":
                    app.pop_screen()
                    await pilot.pause()
                # bare /voice routes to the composer's toggle
                with patch.object(StickyComposer, "toggle_voice",
                                  autospec=True) as toggle:
                    app._handle_command("/voice")
                    toggle.assert_called_once()
                # /voice off with real (IDLE) manager: honest in-app
                # feedback, no suspension, no crash
                voice_manager.state = VoiceState.IDLE
                app._handle_command("/voice off")
                app._handle_command("/voice stop")
                app._handle_command("/voice unknown-arg")
                suspend.assert_not_called()
                self.assertEqual(voice_manager.state, VoiceState.IDLE)

    async def test_permissions_command_routes_to_panel_action(self):
        app = self._open_app()
        with patch.object(CCTApp, "_run_in_suspended_terminal",
                          autospec=True) as suspend, \
             patch.object(CCTApp, "action_toggle_permissions",
                          autospec=True) as action:
            async with app.run_test() as pilot:
                await pilot.pause()
                if type(app.screen).__name__ == "WelcomeModal":
                    app.pop_screen()
                    await pilot.pause()
                app._handle_command("/permissions")
                action.assert_called_once()
                suspend.assert_not_called()


class TestFailoverModelIndicator(unittest.TestCase):

    def test_backup_installed_only_after_connected(self):
        """'Switching to Backup Provider (p (m))' arms a candidate; the
        indicator is installed ONLY on 'Connected successfully.'."""
        stub = _FailoverStub()
        from calc_terminal.ui import app as app_mod

        # switching note: arms the candidate, installs nothing
        app_mod.CCTApp._on_failover_message(
            stub,
            "⚠ Provider issue with ollama (deepseek-r1:latest). "
            "Switching to Backup Provider (groq (llama-3.3-70b))...")
        self.assertEqual(stub._failover_target_pending, ("groq", "llama-3.3-70b"))
        stub.composer.set_active_backup_model.assert_not_called()

        # un-related noise between the two notes changes nothing
        app_mod.CCTApp._on_failover_message(
            stub, "⚠ Retrying same provider...")
        self.assertEqual(stub._failover_target_pending, ("groq", "llama-3.3-70b"))
        stub.composer.set_active_backup_model.assert_not_called()

        # connection confirmed → install the backup pair
        app_mod.CCTApp._on_failover_message(stub, "✓ Connected successfully.")
        stub.composer.set_active_backup_model.assert_called_once_with(
            "groq", "llama-3.3-70b")
        self.assertIsNone(stub._failover_target_pending)

    def test_reset_indicator_clears_candidate_and_override(self):
        stub = _FailoverStub()
        from calc_terminal.ui import app as app_mod
        stub._failover_target_pending = ("gemini", "gemini-2.5-flash")
        app_mod.CCTApp._reset_model_indicator(stub)
        self.assertIsNone(stub._failover_target_pending)
        stub.composer.reset_model_indicator.assert_called_once()


class TestCapabilityAwareVisionWarning(unittest.TestCase):

    def _chip_warning_for(self, config_map):
        """_vision_warning with the capability layer faked to config_map."""
        att = MagicMock()
        att.kind = config_map.get("kind", "image")
        with patch("calc_terminal.attachments.provider_capabilities",
                   return_value={"vision": config_map.get("vision", False)}):
            return _vision_warning(att)

    def test_non_vision_provider_gets_honest_warning(self):
        warn = self._chip_warning_for({"kind": "image", "vision": False})
        self.assertIsNotNone(warn)
        self.assertIn("no native image input", warn)

    def test_vision_provider_gets_no_warning(self):
        self.assertIsNone(self._chip_warning_for(
            {"kind": "image", "vision": True}))

    def test_non_image_attachment_never_warns(self):
        self.assertIsNone(self._chip_warning_for({"kind": "file", "vision": False}))


class TestMiniUISweeps(unittest.IsolatedAsyncioTestCase):
    """Small run_test sweeps across widths: attach + submit, right
    cluster integrity, no clipping of the physical controls."""

    async def _attach_and_submit(self, width):
        app = _SubmitCatcherApp()
        async with app.run_test(size=(width, 26)) as pilot:
            comp = app.query_one(StickyComposer)
            await pilot.pause(0.05)

            # right cluster is exactly [mic, stop-slot, send]
            right = app.query_one("#cct-right-controls")
            buttons = list(right.query(Button))
            self.assertEqual([b.id for b in buttons],
                             ["btn-mic", "btn-stop", "btn-send"])
            # 1-cell physical gap between neighbours (never touch)
            self.assertTrue(all(
                int(b.styles.margin_left) == 1 for b in buttons))

            # attach a real (small) text file → chip exists; submit text
            fd, path = tempfile.mkstemp(suffix=".txt", prefix="cattest_")
            os.close(fd)
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("attachment payload")
                chip_id = comp.add_attachment(path, source="browse")
                self.assertTrue(chip_id)
                await pilot.pause(0.05)
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass

            editor = comp.query_one("#cct-input", ComposerInput)
            editor.text = "explain the attachment"
            comp.submit()
            await pilot.pause(0.05)
            self.assertEqual(len(app.submitted), 1)
            self.assertEqual(app.submitted[0], "explain the attachment")

            # multiline submit is not mangled
            editor.text = "line one\nline two"
            comp.submit()
            await pilot.pause(0.05)
            self.assertEqual(len(app.submitted), 2)
            self.assertEqual(app.submitted[1], "line one\nline two")

            # model indicator exists in the footer at every width
            footer = app.query_one(ComposerFooter)
            footer.query_one("#badge-model")
            self.assertEqual(float(footer.styles.height.value), 3.0)

    async def test_sweeps(self):
        for width in (46, 64, 90, 120):
            with self.subTest(width=width):
                await self._attach_and_submit(width)


if __name__ == "__main__":
    unittest.main()
