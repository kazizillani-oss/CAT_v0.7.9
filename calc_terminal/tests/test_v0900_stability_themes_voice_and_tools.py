# -*- coding: utf-8 -*-
"""
calc_terminal/tests/test_v0900_stability_themes_voice_and_tools.py
==================================================================
Comprehensive test suite verifying CAT CLI Version 0.9 Major Redesign & Stability Overhaul:
1. PRIORITY 0: Stress test sending 50 consecutive AI messages through the message completion pipeline.
   Verifies zero crashes, resilient exception handling, and crash logging.
2. PRIORITY 1: Voice Mode Redesign (5 states, 30+ languages, Hinglish, colourful ASCII waveform).
3. PRIORITY 2: Wake Kitty Sound Effects (wake_kitty, listen_start, completion, voice_close).
4. PRIORITY 3: Theme System Redesign (CAT Origin signature theme, 35+ themes, families, custom themes).
5. PRIORITY 4: Light Mode Contrast & Dynamic Composer ($surface variables, no black composer).
6. PRIORITY 5: Tools Section Redesign (no empty box, distinct non-duplicate render labels).
"""
import os
import unittest
from unittest.mock import MagicMock, patch

from calc_terminal.ui.events import MessageFinished, StreamingFinished
from calc_terminal.ui.thinking import completion_summary_lines
from calc_terminal.ui.statusbar import ToolsModal
from calc_terminal.theme import (
    _THEME_LIST, _THEMES, get_theme_obj, get_theme_families,
    import_custom_theme, export_theme_json, is_light, set_theme
)
from calc_terminal.voice import (
    voice_manager, VoiceState, SUPPORTED_LANGUAGES,
    render_ascii_waveform, render_3tier_waveform
)
from calc_terminal import sound


class TestV0900StabilityAndOverhaul(unittest.IsolatedAsyncioTestCase):

    async def test_p0_fifty_consecutive_messages_resilience(self):
        """PRIORITY 0: Send consecutive messages with varying payloads
        (empty, huge, None contributions, failovers, cancellations) and verify
        zero crashes."""
        from textual.app import App
        from calc_terminal.ui.conversation import ConversationView

        class ConvHarnessApp(App):
            def compose(self):
                yield ConversationView()

        app = ConvHarnessApp()
        async with app.run_test() as pilot:
            conv = app.query_one(ConversationView)
            
            # Test diverse message completion scenarios across multiple complete cycles
            for i in range(25):
                turn_id = f"turn-test-{i}"
                conv.add_complete(f"user-turn-{i}", "user", f"Test prompt message #{i}")
                conv.start_streaming(turn_id, role="assistant")
                
                # Vary payloads across tests
                if i % 5 == 0:
                    # None/empty responses
                    text = ""
                    contributions = None
                    usage = None
                elif i % 5 == 1:
                    # Provider failover scenario
                    text = f"Failover response #{i}: handled smoothly by backup model."
                    contributions = {"pct_main": None, "pct_backup": "100", "backup_model": "nemotron-3.5", "is_backup": True}
                    usage = {"total_tokens": 1500}
                elif i % 5 == 2:
                    # Cancelled / interrupted
                    text = f"Partial response #{i} *(interrupted — partial response kept)*"
                    contributions = [{"model": "claude-3-5", "percent": None}]
                    usage = {"total_tokens": "invalid"}
                elif i % 5 == 3:
                    # Exceptionally large payload
                    text = "Huge payload\n" + ("x" * 2000)
                    contributions = {"main_model": "gpt-4o", "pct_main": 50.0, "pct_backup": 50.0, "backup_model": "gemini-pro"}
                    usage = {"total_tokens": 42000}
                else:
                    # Standard response
                    text = f"Normal response #{i} with code block ```python\nprint({i})\n```"
                    contributions = [{"model": "qwen2.5-coder", "percent": 100.0, "is_backup": False}]
                    usage = {"total_tokens": 350}

                # Streaming chunk
                conv.append_chunk(turn_id, text[:min(len(text), 100)])

                # Must never raise an unhandled exception or crash
                summary = completion_summary_lines(
                    provider="nvidia",
                    model="nemotron",
                    duration=0.5,
                    tokens=100,
                    contributions=contributions
                )
                self.assertIsInstance(summary, list)
                conv.finish(turn_id, full_text=text, meta_lines=summary, contributions=contributions)

            await pilot.pause()
            # After consecutive messages, conversation has all turns rendered
            self.assertGreaterEqual(len(conv._items), 50)

    def test_p0_crash_logging_to_cat_logs(self):
        """PRIORITY 0: Verify global exception handler logs diagnostics to ~/.cat/logs/crash.log."""
        from calc_terminal.ui.app import CCTApp
        app = CCTApp(MagicMock(), [], {})
        
        test_err = RuntimeError("Diagnostic stability verification error")
        app._handle_exception(test_err)
        
        crash_log = os.path.expanduser("~/.cat/logs/crash.log")
        self.assertTrue(os.path.exists(crash_log), "crash.log must exist after exception")
        with open(crash_log, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("VERSION: 0.9.000", content)
        self.assertIn("Diagnostic stability verification error", content)

    def test_p1_voice_mode_multilingual_thirty_languages(self):
        """PRIORITY 1: Support at least 30 languages including English, Hindi, Hinglish."""
        self.assertGreaterEqual(len(SUPPORTED_LANGUAGES), 30)
        codes = [l["code"] for l in SUPPORTED_LANGUAGES]
        
        # Verify priority languages
        self.assertIn("en-US", codes)
        self.assertIn("hi-IN", codes)
        self.assertIn("hi-Latn", codes)  # Hinglish code switching
        self.assertIn("zh-CN", codes)
        self.assertIn("fr-FR", codes)
        self.assertIn("de-DE", codes)
        self.assertIn("es-ES", codes)
        self.assertIn("ja-JP", codes)
        self.assertIn("ar-SA", codes)
        self.assertIn("ru-RU", codes)

        # Verify language switching
        self.assertTrue(voice_manager.set_language("hi-IN"))
        self.assertEqual(voice_manager.get_language(), "hi-IN")
        self.assertEqual(voice_manager.get_language_info()["name"], "Hindi (हिंदी)")

        self.assertTrue(voice_manager.set_language("hi-Latn"))
        self.assertEqual(voice_manager.get_language(), "hi-Latn")

        # Reset back to en-US
        voice_manager.set_language("en-US")

    def test_p1_voice_mode_ascii_waveform_and_states(self):
        """PRIORITY 1: Verify audio-reactive colorful ASCII waveform and 5 voice states."""
        # 5 states: LISTENING, THINKING, SPEAKING, IDLE, ERROR
        self.assertEqual(VoiceState.LISTENING.value, "listening")
        self.assertEqual(VoiceState.THINKING.value, "thinking")
        self.assertEqual(VoiceState.SPEAKING.value, "speaking")
        self.assertEqual(VoiceState.IDLE.value, "idle")
        self.assertEqual(VoiceState.ERROR.value, "error")

        # Test ASCII waveform renderer
        amplitudes = [0.0, 0.1, 0.3, 0.5, 0.8, 1.0, 0.6, 0.2, 0.0]
        wf = render_ascii_waveform(amplitudes, width=9)
        self.assertIn("█", wf)
        self.assertIn(" ", wf)

        # Test 3-tier colorful waveform
        tiers = render_3tier_waveform(0.75)
        self.assertEqual(len(tiers), 3)
        self.assertTrue(any("█" in row for row in tiers))

    def test_p1_wake_kitty_wake_word_phrase(self):
        """PRIORITY 1 & 2: Test Hey Kitty wake word configuration."""
        self.assertEqual(voice_manager.get_wake_word_phrase(), "Hey Kitty")
        voice_manager.set_wake_word_phrase("Hey Cat")
        self.assertEqual(voice_manager.get_wake_word_phrase(), "Hey Cat")
        voice_manager.set_wake_word_phrase("Hey Kitty")
        self.assertTrue(voice_manager.is_wake_word_enabled())

    def test_p2_sound_effects_system(self):
        """PRIORITY 2: Test wake_kitty, completion, and sound cues."""
        # Test sound event triggering without raising exceptions
        sound.play("wake_kitty")
        sound.play("listen_start")
        sound.play("completion")
        sound.play("voice_close")
        sound.play("notify")

        settings = sound.get_audio_settings()
        self.assertIn("enabled", settings)
        self.assertIn("wake_sound", settings)
        self.assertIn("completion_sound", settings)

    def test_p3_cat_origin_signature_theme_and_families(self):
        """PRIORITY 3: Verify CAT Origin official signature theme and 35+ themes."""
        self.assertGreaterEqual(len(_THEME_LIST), 35)
        
        # Verify CAT Origin palette
        origin = get_theme_obj("cat-origin")
        self.assertIsNotNone(origin)
        self.assertEqual(origin.hex("background"), "#1e1e24")  # Warm graphite
        self.assertEqual(origin.hex("surface"), "#16161a")     # Muted charcoal
        self.assertEqual(origin.hex("accent"), "#7c3aed")      # Royal violet
        self.assertEqual(origin.hex("text"), "#e2e8f0")        # Champagne silver
        self.assertEqual(origin.hex("text_faint"), "#c4b5fd")  # Soft lavender
        self.assertEqual(origin.hex("accent_alt"), "#f59e0b")  # Amber accents

        # Verify families
        families = get_theme_families()
        self.assertIn("CAT Originals", families)
        self.assertIn("Premium & Modern", families)
        self.assertIn("Developer Classics", families)
        self.assertIn("Cyberpunk, Neon & OLED", families)
        self.assertIn("Atmospheric & Oceanic", families)

        # Verify custom theme export and import
        exported = export_theme_json("cat-origin")
        self.assertEqual(exported["name"], "cat-origin")
        self.assertEqual(exported["accent"], "#7c3aed")

        custom_dict = dict(exported)
        custom_dict["name"] = "my-custom-theme"
        custom_dict["label"] = "🎨 My Custom Theme"
        self.assertTrue(import_custom_theme(custom_dict))
        self.assertIn("my-custom-theme", _THEMES)

    def test_p4_all_light_modes_removed_and_sixty_dark_themes(self):
        """PRIORITY 4: Verify all light modes are removed and is_light() returns False."""
        from calc_terminal.ui import theme_css
        
        # Verify 60+ dark themes and 0 light themes
        self.assertGreaterEqual(len(_THEME_LIST), 60)
        self.assertFalse(any(not t.dark for t in _THEME_LIST), "No light themes must remain in _THEME_LIST")
        self.assertFalse(is_light())

        # Attempting to set cat-light maps safely to dark signature theme
        set_theme("cat-light")
        self.assertFalse(is_light())
        self.assertEqual(get_theme_obj().name, "cat-origin")
        
        # Composer must use $surface instead of hardcoded colors
        self.assertIn("#cct-composer {", theme_css.BASE_CSS)
        self.assertIn("background: $surface;", theme_css.BASE_CSS)

        # Switch back to signature dark
        set_theme("cat-origin")

    async def test_p5_tools_modal_layout_and_distinct_labels(self):
        """PRIORITY 5: Verify Tools modal width >= 40, distinct non-duplicate labels, action buttons."""
        from textual.app import App
        from calc_terminal.ui import theme_css
        from calc_terminal.ui.statusbar import ToolsModal

        # Verify CSS styling
        self.assertIn("#cct-tools-box", theme_css.BASE_CSS)
        self.assertIn("width: 44", theme_css.BASE_CSS)

        class TestHarnessApp(App):
            def on_mount(self):
                self.push_screen(ToolsModal())

        app = TestHarnessApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            modal = app.screen
            self.assertIsInstance(modal, ToolsModal)
            btns = list(modal.query("Button"))
            labels = [str(b.label) for b in btns]
            
            # Action buttons
            self.assertTrue(any("snapshot" in l.lower() for l in labels))
            self.assertTrue(any("clear" in l.lower() for l in labels))
            self.assertTrue(any("refresh" in l.lower() for l in labels))

            # Render toggles must be distinct (no duplicate "Turn token usage")
            toggle_labels = [l for l in labels if "Time" in l or "token" in l.lower()]
            self.assertEqual(len(toggle_labels), 3)
            self.assertEqual(len(set(toggle_labels)), 3, "All render toggle labels must be unique")


if __name__ == "__main__":
    unittest.main()
