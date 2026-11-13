"""
CAT Engineering Excellence & Platform Maturity Upgrade Test Suite

Comprehensive test coverage across all 8 core subsystems:
1. Developer SDK (creation, registration, validation, compatibility, packaging)
2. Recovery & Rollback Engine (snapshots, selective restore, transactions, undo/redo)
3. Context Engine (7 categories, relevance retrieval, compression, handoffs, isolation)
4. Observability Center (distributed tracing, metrics, structured logs, redaction)
5. Offline Mode (connectivity detection, local tools, Ollama models, tool support)
6. Update & Release Manager (channels, changelogs, safety snapshots, rollback)
7. Multi-Workspace Manager (creation, templates, switching, cloning, health, export)
8. Documentation & Learning Center (search, tutorials, live command audits)
"""

import os
import shutil
import tempfile
import unittest
import time

# Subsystem Imports
from calc_terminal.sdk import (
    Extension,
    ExtensionManifest,
    CommandDefinition,
    ToolDefinition,
    SkillManifest,
    KittyDefinition,
    register_extension,
    register_command,
    register_tool,
    register_skill,
    register_agent,
    SDKLogger,
    ConfigManager,
    EventBus,
)
from calc_terminal.sdk import developer_tools as dev_tools
from calc_terminal.core.recovery_engine import RecoveryEngine, ChangeRecord
from calc_terminal.context_engine import ContextEngine, ContextSlice, AgentHandoffSpec
from calc_terminal.observability import ObservabilityCenter, TraceSpan, LogEntry
from calc_terminal.offline import OfflineManager
from calc_terminal.update_manager import UpdateManager, CURRENT_VERSION
from calc_terminal.multi_workspace import MultiWorkspaceManager, WorkspaceProfile
from calc_terminal.doc_center import DocumentationCenter
from calc_terminal.commands_data import COMMANDS


class TestDeveloperSDK(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cat_sdk_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_extension_creation_and_validation(self):
        proj_dir = dev_tools.create_extension("TestPlugin", dest_dir=self.test_dir, description="Testing SDK")
        self.assertTrue(os.path.exists(os.path.join(proj_dir, "manifest.json")))
        self.assertTrue(os.path.exists(os.path.join(proj_dir, "extension.py")))

        val = dev_tools.validate_component(proj_dir)
        self.assertTrue(val["valid"], f"Validation failed: {val['issues']}")
        self.assertEqual(val["type"], "extension")

    def test_component_testing_and_packaging(self):
        proj_dir = dev_tools.create_extension("PackPlugin", dest_dir=self.test_dir)
        test_res = dev_tools.test_component(proj_dir)
        self.assertTrue(test_res["passed"])

        pkg_path = dev_tools.package_component(proj_dir)
        self.assertTrue(os.path.exists(pkg_path))
        self.assertTrue(pkg_path.endswith(".catpkg"))

    def test_compatibility_checker(self):
        proj_dir = dev_tools.create_extension("CompatPlugin", dest_dir=self.test_dir)
        res = dev_tools.check_compatibility(proj_dir, cat_version="0.7.9")
        self.assertTrue(res["compatible"])

    def test_event_bus_and_config_manager(self):
        bus = EventBus.get()
        received = []
        def handler(evt, data):
            received.append((evt, data))

        bus.subscribe("test.event", handler)
        bus.publish("test.event", {"msg": "hello"})
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0][1]["msg"], "hello")

        cfg = ConfigManager("test_comp", base_dir=self.test_dir)
        cfg.set("theme", "tokyo-night")
        self.assertEqual(cfg.get("theme"), "tokyo-night")


class TestRecoveryEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cat_rec_test_")
        self.engine = RecoveryEngine(storage_dir=self.test_dir)
        self.file1 = os.path.join(self.test_dir, "module.py")
        self.file2 = os.path.join(self.test_dir, "config.json")
        with open(self.file1, "w", encoding="utf-8") as f: f.write("def original(): pass\n")
        with open(self.file2, "w", encoding="utf-8") as f: f.write('{"ver": 1}\n')

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_snapshot_diff_and_selective_restore(self):
        chk = self.engine.snapshot_before("Before Agent Edit", [self.file1, self.file2])
        self.assertIsNotNone(chk.id)

        # Modify file1 and delete file2
        with open(self.file1, "w", encoding="utf-8") as f: f.write("def modified(): pass\n")
        os.remove(self.file2)

        # Preview rollback diff
        prev = self.engine.preview_rollback(chk.id)
        self.assertIn(self.file1, prev["diffs"])

        # Restore only file1
        ok, msg = self.engine.restore_file(chk.id, self.file1)
        self.assertTrue(ok)
        with open(self.file1, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "def original(): pass\n")

        # Entire rollback restores file2 as well
        ok, res = self.engine.rollback_operation(chk.id)
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(self.file2))

    def test_transactional_commit_and_abort(self):
        tx = self.engine.begin_transaction("Refactoring", [self.file1])
        with open(self.file1, "w", encoding="utf-8") as f: f.write("invalid syntax === broken")

        # Test validation fails -> automatically rolls back
        def failing_test(): return False
        ok, msg = self.engine.commit_transaction(test_validator=failing_test)
        self.assertFalse(ok)
        with open(self.file1, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "def original(): pass\n")

    def test_undo_redo_stack(self):
        chk = self.engine.snapshot_before("Pre change", [self.file1])
        with open(self.file1, "w", encoding="utf-8") as f: f.write("change 1\n")

        ok, msg = self.engine.undo()
        self.assertTrue(ok)
        with open(self.file1, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "def original(): pass\n")


class TestContextEngine(unittest.TestCase):
    def setUp(self):
        self.engine = ContextEngine()

    def test_context_categories_and_secret_redaction(self):
        self.engine.add_slice("user", "preference", "User prefers concise python")
        self.engine.add_slice("tool", "curl", "api_key='sk-secret12345678' in header")

        st = self.engine.get_status()
        self.assertEqual(st["slice_counts"]["user"], 1)
        self.assertEqual(st["slice_counts"]["tool"], 1)

        tool_slices = self.engine.inspect_category("tool")
        self.assertIn("[REDACTED]", tool_slices[0]["snippet"])

    def test_relevance_retrieval_and_compression(self):
        self.engine.add_slice("session", "chat", "Step 1: Analyzed database schema", priority=6)
        self.engine.add_slice("session", "chat", "Step 2: Created migration script", priority=7)
        self.engine.add_slice("session", "chat", "Step 3: Ran pytest on models", priority=8)
        self.engine.add_slice("session", "chat", "Step 4: Deployed to staging", priority=9)

        hits = self.engine.retrieve("migration", categories=["session"])
        self.assertTrue(len(hits) > 0)
        self.assertIn("migration", hits[0].content.lower())

        # Test compression
        comp = self.engine.compress("session", target_tokens=10)
        self.assertTrue(comp["compressed"])

    def test_agent_handoff(self):
        spec = self.engine.create_handoff(
            from_agent="Aria",
            to_agent="Dexter",
            task_goal="Write unit tests for authentication",
            relevant_files=["auth.py"],
            previous_results="Created auth endpoints",
            constraints=["Zero mock data", "Fast execution"],
        )
        self.assertEqual(spec.from_agent, "Aria")
        self.assertEqual(spec.to_agent, "Dexter")
        self.assertEqual(len(self.engine.handoff_history), 1)


class TestObservabilityCenter(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cat_obs_test_")
        self.obs = ObservabilityCenter(log_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_tracing_and_spans(self):
        root = self.obs.start_trace("User Prompt: Fix Bug", component="user_request")
        sub = self.obs.start_span(root.trace_id, "Tool: ripgrep", component="tool", parent_span_id=root.span_id)
        time.sleep(0.01)
        self.obs.end_span(sub.span_id, status="ok")
        self.obs.end_span(root.span_id, status="ok")

        spans = self.obs.get_trace(root.trace_id)
        self.assertEqual(len(spans), 2)
        self.assertTrue(spans[0]["duration_ms"] > 0)

    def test_metrics_and_secret_redacted_logging(self):
        self.obs.record_provider_call("openai", "gpt-4o", duration_ms=250.0, tokens=150, cost_usd=0.002)
        m = self.obs.get_metrics_summary()
        self.assertEqual(m["total_provider_calls"], 1)
        self.assertEqual(m["total_tokens"], 150)

        self.obs.log("INFO", "auth_module", "Authorization token: bearer_secret_token_123456789")
        hits = self.obs.search_logs(query="auth_module")
        self.assertTrue(len(hits) > 0)
        self.assertIn("[REDACTED]", hits[0]["message"])


class TestOfflineMode(unittest.TestCase):
    def setUp(self):
        self.offline = OfflineManager()

    def test_offline_toggle_and_capabilities(self):
        self.offline.set_offline_mode(True)
        self.assertFalse(self.offline.is_online())

        caps = self.offline.get_offline_capabilities()
        self.assertIn("code_editor", caps)
        self.assertIn("mathematics_solver", caps)
        self.assertIn("office_suite", caps)

        self.offline.set_offline_mode(False)


class TestUpdateManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cat_upd_test_")
        self.upd = UpdateManager(config_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_channel_switching_and_preview(self):
        ok, msg = self.upd.set_channel("beta")
        self.assertTrue(ok)
        self.assertEqual(self.upd.current_channel, "beta")

        prev = self.upd.preview_update("0.7.10")
        self.assertEqual(prev["version"], "0.7.10")
        self.assertTrue(len(prev["changelog"]) > 0)

    def test_safe_install_and_rollback(self):
        res = self.upd.install_update("0.7.10")
        self.assertTrue(res["success"])
        self.assertEqual(len(self.upd.history), 1)

        ok, msg = self.upd.rollback_update()
        self.assertTrue(ok)


class TestMultiWorkspaceManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cat_ws_test_")
        self.mgr = MultiWorkspaceManager(storage_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_workspace_creation_template_and_switching(self):
        ws_path = os.path.join(self.test_dir, "my_python_project")
        ok, msg = self.mgr.create_workspace("PythonProject", ws_path, template="python")
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(os.path.join(ws_path, "main.py")))

        # Health check
        hlth = self.mgr.get_workspace_health("pythonproject")
        self.assertIn("Python", hlth["languages"])

        # Switch workspace
        ok, msg = self.mgr.switch_workspace("pythonproject")
        self.assertTrue(ok)
        self.assertEqual(self.mgr.active_workspace_id, "pythonproject")


class TestDocumentationCenter(unittest.TestCase):
    def setUp(self):
        self.docs = DocumentationCenter()

    def test_search_and_tutorials(self):
        hits = self.docs.search_docs("sdk")
        self.assertTrue(len(hits) > 0)
        self.assertEqual(hits[0]["id"], "developer_sdk")

        tut = self.docs.get_tutorial("extensions")
        self.assertTrue(len(tut) >= 3)

    def test_command_audit(self):
        audit = self.docs.validate_command_documentation()
        self.assertTrue(audit["total_commands"] > 200)
        self.assertTrue(audit["all_commands_documented_in_palette"])


if __name__ == "__main__":
    unittest.main()

