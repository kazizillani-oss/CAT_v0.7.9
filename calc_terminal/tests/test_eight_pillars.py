"""
Automated Verification Suite for the 8 Pillars of CAT Platform (v0.9.000).

Validates:
  1. Model Agnostic (200+ Providers): Catalog count, A-Z sort, flagship models, dynamic updater.
  2. Plan (Mira) & Build (Aria) Modes: Read-only inspection guard on Mira, implementation on Aria.
  3. Multi-Session & Parallel Background Jobs: BackgroundJobManager and parallel build & review.
  4. Custom Agents & Sub-Agents: TDD workflow and Brainstorming workflow registered.
  5. MCP Servers: Built-in presets for SQLite, Postgres, Filesystem, Git, Brave, Context Streams.
  6. Cross-Platform Interfaces: SDK high-level methods (chat, plan, build, run_parallel, etc.).
  7. Integrations & Plugins: 12 developer SaaS connectors and plugins (GitHub, Linear, Figma, Sentry, Supabase, Stripe, Memory, Quota).
  8. Command & Control Utilities: Slash commands (/new, /variance, /compact, /connect, /undo, /bg, /parallel).
"""

import os
import sys
import unittest
import json

_HERE = os.path.dirname(os.path.abspath(__file__))
_CAT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _CAT_ROOT not in sys.path:
    sys.path.insert(0, _CAT_ROOT)


class TestEightPillars(unittest.TestCase):

    def test_pillar_1_200_plus_providers(self):
        """Pillar 1: 200+ Providers, sorted A-Z, flagship models, updater available."""
        from calc_terminal.models.manager import load_providers
        from calc_terminal import aicore
        
        providers = load_providers()
        self.assertGreaterEqual(len(providers), 200, f"Expected 200+ providers, got {len(providers)}")
        
        # Test A-Z sorting
        names = [p.get("name", "").lower() for p in providers]
        self.assertEqual(names, sorted(names), "Providers must be sorted strictly A-Z by name")
        
        # Test flagship models
        p_ids = {p.get("id"): p for p in providers}
        self.assertIn("anthropic", p_ids)
        self.assertIn("openai", p_ids)
        self.assertIn("deepseek", p_ids)
        self.assertIn("ollama", p_ids)
        
        # Verify updater function
        self.assertTrue(hasattr(aicore, "update_providers_and_models"))
        res = aicore.update_providers_and_models(force=False)
        self.assertEqual(res.get("status"), "success")
        self.assertGreaterEqual(res.get("provider_count", 0), 200)

    def test_pillar_2_plan_mira_and_build_aria(self):
        """Pillar 2: Plan (Mira) inspects without altering files, Aria implements changes."""
        from calc_terminal import ai_modes
        
        plan_meta = ai_modes.meta("plan")
        self.assertEqual(plan_meta["label"], "Mira")
        self.assertIn("inspect and review projects without altering files", plan_meta["purpose"].lower())
        
        build_meta = ai_modes.meta("build")
        self.assertEqual(build_meta["label"], "Aria")
        self.assertIn("production code implementation", build_meta["purpose"].lower())
        
        plan_prompt = ai_modes.system_prompt_for("plan")
        self.assertIn("WITHOUT ALTERING FILES", plan_prompt)
        self.assertIn("Switch to Aria (Build mode)", plan_prompt)
        
        build_prompt = ai_modes.system_prompt_for("build")
        self.assertIn("PRIMARY DIRECTIVE: Implement code changes", build_prompt)

    def test_pillar_3_multi_session_and_parallel_jobs(self):
        """Pillar 3: Multi-session tabs and parallel background jobs."""
        from calc_terminal.parallel_runner import BackgroundJobManager, run_parallel_build_and_review
        
        mgr = BackgroundJobManager.get_instance()
        job = mgr.submit_job("Calculate quick fibonacci in background", role="persistent helper")
        self.assertTrue(job.job_id.startswith("job-"))
        self.assertEqual(job.status, "running")
        
        found = mgr.get_job(job.job_id)
        self.assertIsNotNone(found)
        self.assertIn(found, mgr.list_jobs())
        
        # Cancel test
        mgr.cancel_job(job.job_id)
        self.assertEqual(found.status, "cancelled")

    def test_pillar_4_custom_agents_and_structured_skills(self):
        """Pillar 4: Structured agent skills (TDD & Brainstorming) registered."""
        from calc_terminal.skills.registry import get_skill_registry
        reg = get_skill_registry()
        
        tdd = reg.get("tdd-workflow")
        self.assertIsNotNone(tdd, "tdd-workflow skill must be registered")
        self.assertIn("Red-Green-Refactor", tdd.description)
        
        brainstorm = reg.get("brainstorming-workflow")
        self.assertIsNotNone(brainstorm, "brainstorming-workflow skill must be registered")
        self.assertIn("Brainstorming", brainstorm.name)

    def test_pillar_5_mcp_servers(self):
        """Pillar 5: Built-in MCP server support and presets."""
        from calc_terminal import mcp
        presets = mcp.list_presets()
        preset_ids = [p["id"] for p in presets]
        
        self.assertIn("mcp-sqlite", preset_ids)
        self.assertIn("mcp-postgres", preset_ids)
        self.assertIn("mcp-filesystem", preset_ids)
        self.assertIn("mcp-git", preset_ids)
        self.assertIn("mcp-brave", preset_ids)
        self.assertIn("mcp-context-stream", preset_ids)

    def test_pillar_6_cross_platform_sdk(self):
        """Pillar 6: High-level Python SDK automation."""
        import calc_terminal.sdk as cat
        self.assertTrue(callable(cat.chat))
        self.assertTrue(callable(cat.plan))
        self.assertTrue(callable(cat.build))
        self.assertTrue(callable(cat.review))
        self.assertTrue(callable(cat.run_parallel))
        self.assertTrue(callable(cat.list_providers))
        self.assertGreaterEqual(len(cat.list_providers()), 200)

    def test_pillar_7_integrations_and_plugins(self):
        """Pillar 7: 12 developer SaaS connectors and community plugins."""
        from calc_terminal.app_connectors import AppConnectorCenter
        acc = AppConnectorCenter()
        conns = acc.list_connectors()
        c_ids = {c["id"] for c in conns}
        
        expected = [
            "conn_github_api", "conn_linear", "conn_figma", "conn_sentry",
            "conn_notion", "conn_slack", "conn_supabase", "conn_stripe",
            "conn_persistent_memory", "conn_quota_tracker"
        ]
        for exp in expected:
            self.assertIn(exp, c_ids, f"Connector {exp} must be registered")

    def test_pillar_8_command_and_control_utilities(self):
        """Pillar 8: Slash commands (/new, /variance, /compact, /connect, /undo, /bg, /parallel)."""
        from calc_terminal.commands_data import COMMANDS
        cmd_dict = dict(COMMANDS)
        
        self.assertIn("/new", cmd_dict)
        self.assertIn("/variance", cmd_dict)
        self.assertIn("/compact", cmd_dict)
        self.assertIn("/connect", cmd_dict)
        self.assertIn("/undo", cmd_dict)
        self.assertIn("/bg", cmd_dict)
        self.assertIn("/parallel", cmd_dict)
        self.assertIn("/platform", cmd_dict)
        self.assertIn("/connectors", cmd_dict)


if __name__ == "__main__":
    unittest.main()

