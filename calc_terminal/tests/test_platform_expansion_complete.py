"""
Unit & Integration Tests for CAT Platform Expansion Complete
(Universal Foundation Engines, Critical Systems, High Priority Systems, UI Screens & Header Polish)
"""

import os
import unittest
import tempfile
import shutil

class TestPlatformExpansionComplete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="cat_platform_test_")
        # Create dummy python files for indexing & security testing
        cls.sample_py = os.path.join(cls.test_dir, "sample.py")
        with open(cls.sample_py, "w", encoding="utf-8") as f:
            f.write('''"""Sample module for testing."""
import os
import math

class CalculatorEngine:
    """Core calculation engine."""
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b

def unused_dead_function():
    return "dead"

def active_function():
    calc = CalculatorEngine()
    return calc.add(1, 2)
''')
        # Create sample requirements.txt
        cls.req_txt = os.path.join(cls.test_dir, "requirements.txt")
        with open(cls.req_txt, "w", encoding="utf-8") as f:
            f.write("textual>=0.40.0\nurllib3==1.25.10\nrequests>=2.28.0\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_01_capability_registry(self):
        from calc_terminal.capability_registry import get_registry, CapabilitySpec
        reg = get_registry()
        self.assertIsNotNone(reg)

        # Test registration
        cap = CapabilitySpec(
            id="test_cap_01",
            name="Test Tool",
            type="core_tool",
            description="A test capability",
            category="testing"
        )
        self.assertTrue(reg.register(cap))
        self.assertEqual(reg.get("test_cap_01").name, "Test Tool")

        # Test search
        res = reg.search("Test Tool")
        self.assertTrue(len(res) >= 1)

        # Test agent isolation
        aria_caps = reg.get_agent_capabilities("aria")
        dexter_caps = reg.get_agent_capabilities("dexter")
        self.assertTrue(len(aria_caps) >= len(dexter_caps))

        # Test toggle
        reg.disable("test_cap_01")
        self.assertFalse(reg.get("test_cap_01").enabled)
        reg.enable("test_cap_01")
        self.assertTrue(reg.get("test_cap_01").enabled)

    def test_02_tool_execution_engine(self):
        from calc_terminal.tool_engine import get_tool_engine
        from calc_terminal.capability_registry import get_registry, CapabilitySpec
        from calc_terminal import permissions as perm

        engine = get_tool_engine()
        reg = get_registry()

        def sample_handler(x=1, y=2):
            return x + y

        reg.register(CapabilitySpec(
            id="tool_math_add",
            name="Add Numbers",
            type="core_tool",
            handler=sample_handler
        ))

        # Normal execution
        res = engine.execute_tool("tool_math_add", {"x": 5, "y": 10})
        self.assertTrue(res["success"])
        self.assertEqual(res["result"], 15)

        # History log
        history = engine.get_history(limit=5)
        self.assertTrue(len(history) >= 1)
        self.assertEqual(history[0]["tool_id"], "tool_math_add")

        # Restricted mode test
        old_mode = perm.manager.mode
        try:
            perm.manager.set_mode("restricted")
            reg.register(CapabilitySpec(
                id="tool_file_delete",
                name="Delete File",
                type="core_tool",
                requires_permission="protected"
            ))
            res_denied = engine.execute_tool("tool_file_delete", {})
            self.assertFalse(res_denied["success"])
            self.assertIn("Permission denied", res_denied["error"])
        finally:
            perm.manager.set_mode(old_mode)

    def test_03_code_intelligence_engine(self):
        from calc_terminal.code_intel import get_code_intel
        intel = get_code_intel()
        idx = intel.index_workspace(self.test_dir)
        self.assertTrue(idx["total_files"] >= 1)
        self.assertTrue(idx["total_lines"] >= 10)

        # Find symbol
        syms = intel.find_symbol("CalculatorEngine", root_dir=self.test_dir)
        self.assertTrue(len(syms) >= 1)
        self.assertEqual(syms[0]["name"], "CalculatorEngine")

        # Project summary
        summ = intel.get_project_summary(self.test_dir)
        self.assertTrue(summ["total_classes"] >= 1)
        self.assertTrue(summ["total_functions"] >= 3)

        # Code search
        results = intel.search_code("subtract", self.test_dir)
        self.assertTrue(len(results) >= 1)

        # Dead code candidate detection
        dead = intel.detect_dead_code(self.test_dir)
        self.assertTrue(dead["potentially_unused_count"] >= 1)

    def test_04_ai_eval_engine(self):
        from calc_terminal.ai_eval import get_ai_eval
        eval_engine = get_ai_eval()
        res = eval_engine.run_benchmark("test-model-alpha")
        self.assertIsNotNone(res)
        self.assertEqual(res.model, "test-model-alpha")
        self.assertTrue(res.score_percent > 0)
        self.assertTrue(len(res.task_details) >= 4)

        # Compare
        comp = eval_engine.compare_models(["test-model-alpha", "test-model-beta"])
        self.assertIn("test-model-alpha", comp["results"])
        self.assertIn("test-model-beta", comp["results"])

    def test_05_automation_engine(self):
        from calc_terminal.automation_engine import get_automation_engine
        auto = get_automation_engine()
        job = auto.add_job(
            name="Test Auto Job",
            trigger_type="interval",
            trigger_config={"interval_seconds": 60},
            action_type="command",
            action_payload="echo 'hello'",
            assigned_agent="Dexter"
        )
        self.assertIsNotNone(job)
        self.assertEqual(job.name, "Test Auto Job")

        # Run job
        run_res = auto.run_job_now(job.id)
        self.assertTrue(run_res["success"])

        # Delegation
        del_res = auto.delegate_task("Refactor auth", "Dexter")
        self.assertEqual(del_res["assigned_agent"], "Dexter")
        self.assertEqual(del_res["status"], "delegated")

        # Cleanup
        auto.remove_job(job.id)

    def test_06_security_center(self):
        from calc_terminal.security_center import get_security_center
        sec = get_security_center()
        audit = sec.run_full_security_audit(self.test_dir)
        self.assertIn("security_score", audit)
        self.assertIn("secrets", audit)
        self.assertIn("code_safety", audit)
        self.assertIn("dependencies", audit)
        # Check vulnerable urllib3 was caught
        vulns = audit["dependencies"]["vulnerabilities"]
        self.assertTrue(any(v["package"] == "urllib3" for v in vulns))

    def test_07_deployment_center(self):
        from calc_terminal.deployment_center import get_deployment_center
        dc = get_deployment_center()
        proj = dc.detect_project_type(self.test_dir)
        self.assertIsNotNone(proj["project_type"])

        # Dry run deploy
        rec = dc.deploy("local_build", self.test_dir, dry_run=True)
        self.assertEqual(rec.status, "success")
        self.assertIn("DRY-RUN", rec.log_summary)

    def test_08_database_studio(self):
        from calc_terminal.db_studio import get_db_studio
        db = get_db_studio()
        conn_res = db.connect_sqlite(":memory:")
        self.assertTrue(conn_res["success"])

        # Create table & insert
        db.execute_query("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT);")
        db.execute_query("INSERT INTO users (name, email) VALUES ('Alice', 'alice@cat.local'), ('Bob', 'bob@cat.local');")

        tables = db.get_tables()
        self.assertTrue(any(t["name"] == "users" for t in tables))

        schema = db.get_schema("users")
        self.assertTrue(any(c["name"] == "name" for c in schema))

        res = db.execute_query("SELECT * FROM users")
        self.assertEqual(res["row_count"], 2)

        csv_out = db.export_table_csv("users")
        self.assertIn("Alice", csv_out)
        self.assertIn("bob@cat.local", csv_out)

    def test_09_ai_cost_manager(self):
        from calc_terminal.ai_cost_manager import get_ai_cost_manager
        mgr = get_ai_cost_manager()
        mgr.reset_usage()
        entry = mgr.record_usage("gpt-4o", prompt_tokens=1000, completion_tokens=500)
        self.assertTrue(entry.estimated_cost_usd > 0)
        self.assertEqual(entry.total_tokens, 1500)

        summary = mgr.get_summary()
        self.assertEqual(summary["total_tokens"], 1500)
        self.assertTrue(summary["total_cost_usd"] > 0)
        self.assertIn("gpt-4o", summary["by_model"])

    def test_10_workflow_builder(self):
        from calc_terminal.workflow_builder import get_workflow_builder
        wfb = get_workflow_builder()
        wfs = wfb.list_workflows()
        self.assertTrue(len(wfs) >= 3)

        # Run template
        res = wfb.run_workflow(wfs[0]["id"])
        self.assertTrue(res["success"])
        self.assertEqual(len(res["steps"]), len(wfs[0]["nodes"]))

    def test_11_github_cloud_knowledge_apps(self):
        from calc_terminal.github_studio import get_github_studio
        from calc_terminal.cloud_workspace import get_cloud_workspace
        from calc_terminal.knowledge_center import get_knowledge_center
        from calc_terminal.app_connectors import get_app_connectors
        from calc_terminal.agent_studio import get_agent_studio

        # GitHub
        gh = get_github_studio()
        info = gh.get_repo_info(self.test_dir)
        self.assertIsNotNone(info)

        # Cloud
        cw = get_cloud_workspace()
        profs = cw.list_profiles()
        self.assertTrue(len(profs) >= 1)

        # Knowledge
        kc = get_knowledge_center()
        kc.index_workspace_docs(self.test_dir)
        hits = kc.search("python")
        self.assertTrue(len(hits) >= 1)

        # App Connectors
        ac = get_app_connectors()
        conns = ac.list_connectors()
        self.assertTrue(len(conns) >= 3)

        # Agent Studio
        studio = get_agent_studio()
        agents = studio.list_agents()
        self.assertTrue(len(agents) >= 6)
        new_agent = studio.create_agent(
            name="test_bot",
            display_name="TestBot",
            role="Tester",
            system_prompt="You are a test agent."
        )
        self.assertEqual(new_agent.name, "test_bot")
        self.assertTrue(studio.delete_agent("test_bot"))

    def test_12_ui_screens_and_css(self):
        from calc_terminal.ui.platform_screens import (
            SecurityCenterScreen,
            DatabaseStudioScreen,
            AICostManagerScreen,
            DeploymentCenterScreen
        )
        # Verify screens instantiate cleanly
        s1 = SecurityCenterScreen()
        s2 = DatabaseStudioScreen()
        s3 = AICostManagerScreen()
        s4 = DeploymentCenterScreen()
        self.assertIsNotNone(s1)
        self.assertIsNotNone(s2)
        self.assertIsNotNone(s3)
        self.assertIsNotNone(s4)

    def test_13_header_styles_and_extensions_filters(self):
        # 1. Verify app.py has clean rounded borders for landscape header (Image 5)
        with open("calc_terminal/ui/app.py", "r", encoding="utf-8") as f:
            app_code = f.read()
        self.assertIn("border-top: tall #6b7596;", app_code)
        self.assertIn(".cct-menu-btn {", app_code)
        self.assertIn(".cct-perm-pill {", app_code)
        self.assertIn("#cct-header-right {", app_code)

        # 2. Verify extensions_panel.py has NO #ext-filters
        with open("calc_terminal/ui/extensions_panel.py", "r", encoding="utf-8") as f:
            ext_code = f.read()
        self.assertNotIn("id=\"ext-filters\"", ext_code)
        self.assertNotIn("filter-all", ext_code)
        self.assertNotIn("filter-skills", ext_code)

if __name__ == "__main__":
    unittest.main()

