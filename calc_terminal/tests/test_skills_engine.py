import unittest
from calc_terminal.skills.engine import get_skills_engine, SkillsEngine

class TestSkillsEngine(unittest.TestCase):
    def setUp(self):
        self.engine = get_skills_engine()

    def test_official_skills_registered(self):
        skills = self.engine.list_skills()
        self.assertGreaterEqual(len(skills), 6)
        
        expected_ids = [
            "rea-reverse-engineer",
            "archify",
            "remotion-best-practices",
            "skillopt-sleep",
            "page-mascot",
            "frontend-design"
        ]
        registered_ids = [s.skill_id for s in skills]
        for sid in expected_ids:
            self.assertIn(sid, registered_ids, f"Expected {sid} to be registered in SkillsEngine")

    def test_official_attributions_and_metadata(self):
        rea = self.engine.get_skill("rea-reverse-engineer")
        self.assertIsNotNone(rea)
        self.assertEqual(rea.github_username, "@morluto")
        self.assertEqual(rea.license_name, "MIT")
        self.assertIn("morluto/rea", rea.repository)

        archify = self.engine.get_skill("archify")
        self.assertIsNotNone(archify)
        self.assertEqual(archify.github_username, "@tt-a1i")

        remotion = self.engine.get_skill("remotion-best-practices")
        self.assertIsNotNone(remotion)
        self.assertEqual(remotion.github_username, "@remotion-dev")

        skillopt = self.engine.get_skill("skillopt-sleep")
        self.assertIsNotNone(skillopt)
        self.assertEqual(skillopt.github_username, "@microsoft")

        mascot = self.engine.get_skill("page-mascot")
        self.assertIsNotNone(mascot)
        self.assertEqual(mascot.github_username, "@nilbuild")

        fed = self.engine.get_skill("frontend-design")
        self.assertIsNotNone(fed)
        self.assertEqual(fed.github_username, "@anthropic")

    def test_progressive_disclosure_lazy_loading(self):
        # Before loading, loaded_instructions should be None (or loaded only on demand)
        rea = self.engine.get_skill("rea-reverse-engineer")
        self.assertIsNotNone(rea)
        instructions = self.engine.load_skill_instructions("rea-reverse-engineer")
        self.assertTrue(len(instructions) > 100, "Expected non-empty instructions for REA")
        self.assertEqual(rea.loaded_instructions, instructions)

    def test_agent_role_prompt_routing(self):
        aria_prompts = self.engine.get_skill_prompts_for_agent("aria")
        self.assertIn("ACTIVE AGENT SKILLS", aria_prompts)
        self.assertIn("Archify", aria_prompts)

        mira_prompts = self.engine.get_skill_prompts_for_agent("mira")
        self.assertIn("REA", mira_prompts)

if __name__ == "__main__":
    unittest.main()

