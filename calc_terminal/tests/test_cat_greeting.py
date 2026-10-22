"""Unit tests for CAT 3D ASCII Block Art and Routine Time-Based Greetings."""

import datetime
import unittest

from calc_terminal.ui.cat_greeting import (
    GREETINGS_NUMBERED,
    GREETINGS_ACTION,
    GREETINGS_FELINE,
    GREETING_3D_ART,
    extract_greeting_keyword,
    get_cat_routine_data,
    get_cat_routine_display,
)


class TestCatGreeting(unittest.TestCase):
    def test_greetings_counts(self):
        """Verify the exact requested count of all greeting lists."""
        self.assertEqual(len(GREETINGS_NUMBERED), 50)
        self.assertEqual(len(GREETINGS_ACTION), 30)
        self.assertEqual(len(GREETINGS_FELINE), 10)

    def test_greetings_content_samples(self):
        """Ensure specific phrases requested by the user are present."""
        self.assertEqual(GREETINGS_NUMBERED[0], "[01]  > CAT is ready.")
        self.assertEqual(GREETINGS_NUMBERED[49], "[50]  > CAT ready. Your move.")
        self.assertIn("> Ready.", GREETINGS_ACTION)
        self.assertIn("> Online.", GREETINGS_ACTION)
        self.assertIn("> *meow* — ready.", GREETINGS_FELINE)
        self.assertIn("> 🐾 Ready to build.", GREETINGS_FELINE)

    def test_time_periods(self):
        """Verify time-of-day dynamic routine detection."""
        # Morning (5am - 12pm)
        morning_dt = datetime.datetime(2026, 9, 25, 8, 30)
        m_data = get_cat_routine_data(morning_dt)
        self.assertEqual(m_data["period_name"], "Morning Build")
        self.assertEqual(m_data["period_icon"], "🌅")
        self.assertEqual(m_data["time_str"], "8:30 AM")

        # Afternoon (12pm - 5pm)
        afternoon_dt = datetime.datetime(2026, 9, 25, 14, 15)
        a_data = get_cat_routine_data(afternoon_dt)
        self.assertEqual(a_data["period_name"], "Afternoon Focus")
        self.assertEqual(a_data["period_icon"], "☀️")
        self.assertEqual(a_data["time_str"], "2:15 PM")

        # Evening (5pm - 10pm)
        evening_dt = datetime.datetime(2026, 9, 25, 19, 45)
        e_data = get_cat_routine_data(evening_dt)
        self.assertEqual(e_data["period_name"], "Evening Session")
        self.assertEqual(e_data["period_icon"], "🌆")
        self.assertEqual(e_data["time_str"], "7:45 PM")

        # Night (10pm - 5am)
        night_dt = datetime.datetime(2026, 9, 25, 23, 10)
        n_data = get_cat_routine_data(night_dt)
        self.assertEqual(n_data["period_name"], "Night Ops")
        self.assertEqual(n_data["period_icon"], "🌙")
        self.assertEqual(n_data["time_str"], "11:10 PM")

    def test_greeting_3d_art_is_greeting_not_cat_logo(self):
        """Verify that 3D block ASCII art displays the greeting (READY, BUILD, etc.), not CAT."""
        # Verify keywords in 3D art library
        self.assertIn("READY", GREETING_3D_ART)
        self.assertIn("ONLINE", GREETING_3D_ART)
        self.assertIn("AWAKE", GREETING_3D_ART)
        self.assertIn("BUILD", GREETING_3D_ART)
        self.assertIn("CODE", GREETING_3D_ART)
        self.assertIn("HELLO", GREETING_3D_ART)
        self.assertIn("MEOW", GREETING_3D_ART)

        # Keyword extraction for specific phrases
        self.assertEqual(extract_greeting_keyword("[01] > CAT is ready.", "> Ready.", "> Paws ready."), "READY")
        self.assertEqual(extract_greeting_keyword("[05] > Let's build.", "> Let's build.", "> 🐾 Ready to build."), "BUILD")
        self.assertEqual(extract_greeting_keyword("[06] > Let's code.", "> Let's code.", "> Meow. Let's code."), "CODE")
        self.assertEqual(extract_greeting_keyword("[11] > CAT online.", "> Online.", "> CAT is purring."), "ONLINE")
        self.assertEqual(extract_greeting_keyword("[03] > CAT is awake.", "> Awake.", "> Paws on keyboard."), "AWAKE")

    def test_cycle_offset(self):
        """Verify manual cycling offset increments correctly through the 50 greetings."""
        dt = datetime.datetime(2026, 9, 25, 12, 0)
        d0 = get_cat_routine_data(dt, offset=0)
        d1 = get_cat_routine_data(dt, offset=1)
        self.assertNotEqual(d0["numbered"], d1["numbered"])

    def test_display_markup_generation(self):
        """Verify get_cat_routine_display generates valid rich text markup."""
        markup = get_cat_routine_display(accent_hex="#5599ff")
        self.assertIn("[#5599ff", markup)
        self.assertIn("Routine", markup)
        self.assertTrue(len(markup) > 20)

    def test_mode_accent_and_dashboard_cat_section(self):
        """Verify that passing mode_key reflects mode accent and mode label in CAT section."""
        from calc_terminal import ai_modes
        # Test build mode and agent mode
        build_accent = ai_modes.accent_hex("build")
        agent_accent = ai_modes.accent_hex("agent")

        m_build = get_cat_routine_display(accent_hex=build_accent, mode_key="build")
        self.assertIn(f"[{build_accent} b]", m_build)
        self.assertIn("Build Mode", m_build)

        m_agent = get_cat_routine_display(accent_hex=agent_accent, mode_key="agent")
        self.assertIn(f"[{agent_accent} b]", m_agent)
        self.assertIn("Agent Mode", m_agent)
        self.assertNotEqual(m_build, m_agent)

        # Test dashboard cat section markup generator
        from calc_terminal.ui.dashboard import WelcomeDashboard
        dash = WelcomeDashboard(logo_lines=[], version="0.7.9.0", model_label="test", notebook_count=1)
        markup_build = dash._cat_section_markup(mode_key="build")
        markup_agent = dash._cat_section_markup(mode_key="agent")
        self.assertIn(build_accent, markup_build)
        self.assertIn(agent_accent, markup_agent)
        self.assertNotEqual(markup_build, markup_agent)


if __name__ == "__main__":
    unittest.main()

