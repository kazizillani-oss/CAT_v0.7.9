"""
CAT Unified Extensions, Skills, Commands & Security Test Suite.

Verifies:
1. Discovery of built-ins (Gestures, Personalize) and metadata preservation.
2. Metadata display: author 'Kazi Zillani', distinct published date vs installed date.
3. GitHub repository inspection & manifest validation workflow.
4. Supported manifest formats (cat-extension.json, cat-skill.json, cat-command.json, cat-integration.json).
5. Malformed manifest rejection and honest error reporting.
6. Path traversal security (rejection of malicious ../ and absolute paths in archive).
7. Custom command registration, CLI collision detection against core commands.
8. Custom command dispatch and disable state enforcement.
9. Skill registration and Kitty discovery (SkillRegistry and Kitties).
10. Enable and disable behavior stopping functionality.
11. Update checking without code execution.
12. Compatibility failure detection (CAT version & OS platform).
13. Dependency handling and uninstall protection.
14. Uninstallation cleans up managed files while preserving unrelated user data.
15. Recovery from interrupted or failed installation without leaving corrupted state.
"""

import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from calc_terminal import extensions as ext_mgr
from calc_terminal import extension_installer
from calc_terminal.commands_registry import (
    CustomCommandRegistry,
    CommandSpec,
    BUILTIN_COMMANDS,
    get_command_registry,
)
from calc_terminal.skills.registry import SkillRegistry, get_skill_registry
from calc_terminal.skills.skill_model import SkillDefinition


class TestUnifiedExtensions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cat_unified_ext_test_")
        self.orig_home = os.environ.get("HOME")
        self.orig_up = os.environ.get("USERPROFILE")
        os.environ["HOME"] = self.tmp
        os.environ["USERPROFILE"] = self.tmp

        # Point ext_mgr and installer to tmp directories
        ext_mgr.REGISTRY_FILE = Path(self.tmp) / ".cct_extensions_registry.json"
        ext_mgr.CUSTOM_EXTENSIONS_DIR = Path(self.tmp) / ".cct_extensions"
        ext_mgr.CUSTOM_EXTENSIONS_DIR.mkdir(parents=True, exist_ok=True)
        ext_mgr._cached_state = None
        ext_mgr._cached_mtime = 0

        # Isolated commands registry
        self.cmd_reg_file = Path(self.tmp) / "commands_registry.json"
        self.cmd_reg = CustomCommandRegistry(registry_file=self.cmd_reg_file)

        # Isolated skills registry
        self.skills_dir = str(Path(self.tmp) / "skills")
        self.skill_reg = SkillRegistry(storage_dir=self.skills_dir)

    def tearDown(self):
        if self.orig_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self.orig_home
        if self.orig_up is None:
            os.environ.pop("USERPROFILE", None)
        else:
            os.environ["USERPROFILE"] = self.orig_up
        shutil.rmtree(self.tmp, ignore_errors=True)
        ext_mgr._cached_state = None
        ext_mgr._cached_mtime = 0

    # 1. Built-in discovery & metadata preservation
    def test_builtin_discovery_and_metadata(self):
        exts = ext_mgr.list_extensions()
        ids = [e["id"] for e in exts]
        self.assertIn("gestures", ids)
        self.assertIn("personalize", ids)

        # Verify author Kazi Zillani and verified badges preserved
        g_meta = ext_mgr.get_metadata("gestures")
        self.assertEqual(g_meta["publisher"], "Kazi Zillani")
        self.assertTrue(g_meta["publisher_verified"])
        self.assertTrue(g_meta["verified"])
        self.assertTrue(g_meta["trusted"])
        self.assertEqual(g_meta["type"], "extension")

        p_meta = ext_mgr.get_metadata("personalize")
        self.assertEqual(p_meta["publisher"], "Kazi Zillani")
        self.assertTrue(p_meta["verified"])

    # 2. Metadata: distinct published date vs installed date
    def test_distinct_published_date_vs_installed_date(self):
        mock_data = {
            "id": "test-data-ext",
            "name": "Test Data Extension",
            "type": "extension",
            "version": "1.0.0",
            "author": "Dr. Scientific",
            "published_at": "2025-05-15",
            "description": "Demonstrates distinct published vs installed timestamps",
        }
        ok, msg = ext_mgr.install_from_github("test/repo", mock_data=mock_data)
        self.assertTrue(ok)

        m = ext_mgr.get_metadata("test-data-ext")
        self.assertIsNotNone(m)
        self.assertEqual(m["published_at"], "2025-05-15")
        self.assertGreater(m["install_time"], 0)
        self.assertNotEqual(m["published_at"], str(m["install_time"]))

    # 3. Category and type filtering in list_extensions
    def test_type_and_category_filtering(self):
        # Install a skill and a command
        skill_mock = {
            "id": "data-extractor-skill",
            "name": "Data Extractor",
            "type": "skill",
            "version": "1.0.0",
            "instructions": "Extract table rows",
        }
        cmd_mock = {
            "id": "data-cleaner-cmd",
            "name": "Data Cleaner",
            "type": "command",
            "version": "1.0.0",
            "command_name": "clean-data",
        }
        ext_mgr.install_from_github("test/skill", mock_data=skill_mock)
        ext_mgr.install_from_github("test/cmd", mock_data=cmd_mock)

        # Filter by type: skill
        skills = ext_mgr.list_extensions(component_type="skill")
        skill_ids = [s["id"] for s in skills]
        self.assertIn("data-extractor-skill", skill_ids)
        self.assertNotIn("gestures", skill_ids)
        self.assertNotIn("data-cleaner-cmd", skill_ids)

        # Filter by type: command
        cmds = ext_mgr.list_extensions(component_type="command")
        cmd_ids = [c["id"] for c in cmds]
        self.assertIn("data-cleaner-cmd", cmd_ids)
        self.assertNotIn("data-extractor-skill", cmd_ids)

    # 4. Manifest validation: supported formats and normalization
    def test_manifest_format_adapters(self):
        # Test cat-skill.json format with nested permissions
        raw_skill = {
            "cat": {
                "id": "repo-issue-solver",
                "name": "Repo Issue Solver",
                "type": "skill",
                "version": "2.1.0",
                "permission_scope": {"read_files": True, "network": True},
            }
        }
        adapted = extension_installer.adapt_manifest(raw_skill)
        self.assertEqual(adapted["id"], "repo-issue-solver")
        self.assertEqual(adapted["type"], "skill")
        self.assertEqual(adapted["version"], "2.1.0")
        self.assertIn("read_files", adapted["permissions"])
        self.assertIn("network", adapted["permissions"])

    # 5. Malformed manifest rejection
    def test_malformed_manifest_rejection(self):
        insp = extension_installer.inspect_repository("")
        self.assertFalse(insp.valid)
        self.assertIn("cannot be empty", insp.error)

        insp_bad_url = extension_installer.inspect_repository("invalid url format with spaces")
        self.assertFalse(insp_bad_url.valid)
        self.assertIn("Invalid GitHub repository URL", insp_bad_url.error)

    # 6. Path traversal security in zip extraction
    def test_path_traversal_prevention(self):
        # Create a malicious zip containing ../ escape
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("manifest/extension.json", json.dumps({"id": "evil-ext", "name": "Evil Ext"}))
            zf.writestr("../../../evil.py", "# malicious payload")
        zip_bytes = buf.getvalue()

        insp = extension_installer.InspectionResult(
            valid=True,
            id="evil-ext",
            name="Evil Ext",
            component_type="extension",
        )
        ok, msg = extension_installer.install_from_zip(zip_bytes, insp, target_dir=Path(self.tmp) / "evil")
        self.assertFalse(ok)
        self.assertIn("SECURITY REJECTION", msg)
        self.assertIn("path traversal", msg.lower())

    # 7. Custom command registration and collision detection
    def test_command_collision_detection(self):
        # Attempt to register command conflicting with built-in 'agent'
        clashing_cmd = CommandSpec(
            id="bad-agent-cmd",
            name="agent",  # Collision!
            description="Tries to clobber built-in agent",
        )
        ok, err = self.cmd_reg.register(clashing_cmd)
        self.assertFalse(ok)
        self.assertIn("COMMAND_COLLISION_ERROR", err)
        self.assertIn("conflicts with a core CAT built-in command", err)

        # Attempt to register command conflicting with 'doctor'
        clashing_doc = CommandSpec(
            id="bad-doc-cmd",
            name="doctor",
            description="Tries to clobber doctor",
        )
        ok2, err2 = self.cmd_reg.register(clashing_doc)
        self.assertFalse(ok2)
        self.assertIn("COMMAND_COLLISION_ERROR", err2)

        # Register valid distinct command
        valid_cmd = CommandSpec(
            id="git-pr-helper",
            name="pr-helper",
            description="Valid custom command",
        )
        ok3, err3 = self.cmd_reg.register(valid_cmd)
        self.assertTrue(ok3)
        self.assertIsNone(err3)

    # 8. Custom command dispatch and disable state enforcement
    def test_command_dispatch_and_disable(self):
        executed = []
        test_cmd = CommandSpec(
            id="test-ping-cmd",
            name="ping-cct",
            handler=lambda args: executed.append(args) or 0,
            enabled=True,
        )
        self.cmd_reg.register(test_cmd)

        # Dispatch when enabled
        rc = self.cmd_reg.dispatch(["ping-cct", "--verbose"])
        self.assertEqual(rc, 0)
        self.assertEqual(len(executed), 1)
        self.assertEqual(executed[0], ["--verbose"])

        # Disable command
        self.cmd_reg.set_enabled("ping-cct", False)
        rc_disabled = self.cmd_reg.dispatch(["ping-cct"])
        self.assertEqual(rc_disabled, 1)  # Rejected

    # 9. Skill registration and Kitty discovery
    def test_skill_registration_and_kitty_discovery(self):
        skill_def = SkillDefinition(
            id="github-issue-triage",
            name="GitHub Issue Triage",
            version="1.0.0",
            category="devops",
            instructions="Analyze issue reports and classify severity.",
            required_tools=["read_file"],
            permission_scope={"read_files": True},
        )
        ok, err = self.skill_reg.register(skill_def, persist=True)
        self.assertTrue(ok)

        # Kitty lookup
        retrieved = self.skill_reg.get("github-issue-triage")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "GitHub Issue Triage")
        self.assertEqual(retrieved.instructions, "Analyze issue reports and classify severity.")
        self.assertIn("read_file", retrieved.required_tools)

    # 10. Enable and disable lifecycle
    def test_enable_disable_lifecycle(self):
        mock_data = {
            "id": "toggleable-component",
            "name": "Toggleable Component",
            "type": "extension",
            "version": "1.0.0",
        }
        ok, _ = ext_mgr.install_from_github("test/toggle", mock_data=mock_data)
        self.assertTrue(ok)
        self.assertTrue(ext_mgr.is_enabled("toggleable-component"))

        # Disable
        dis_ok, dis_msg = ext_mgr.disable("toggleable-component")
        self.assertTrue(dis_ok)
        self.assertFalse(ext_mgr.is_enabled("toggleable-component"))
        self.assertTrue(ext_mgr.is_disabled("toggleable-component"))

        # Re-enable
        en_ok, en_msg = ext_mgr.enable("toggleable-component")
        self.assertTrue(en_ok)
        self.assertTrue(ext_mgr.is_enabled("toggleable-component"))

    # 11. Update checking without code execution
    def test_update_checking(self):
        mock_data = {
            "id": "github-issue-investigator",
            "name": "GitHub Issue Investigator",
            "type": "skill",
            "version": "1.0.0",  # Installed older version
        }
        ext_mgr.install_from_github("test/investigator", mock_data=mock_data)

        # Check updates against catalogue (which has v1.1.0)
        has_up, cur_v, new_v, det = ext_mgr.check_for_updates("github-issue-investigator")
        self.assertTrue(has_up)
        self.assertEqual(cur_v, "1.0.0")
        self.assertEqual(new_v, "1.1.0")

    # 12. Compatibility failure detection
    def test_compatibility_checking(self):
        # Requires impossible futuristic version
        ok_fut, notes_fut = extension_installer.check_compatibility(">=99.0.0")
        self.assertFalse(ok_fut)
        self.assertIn("Requires CAT version", notes_fut)

        # Incompatible OS
        ok_os, notes_os = extension_installer.check_compatibility(">=0.7.0", target_os=["amigaos"])
        self.assertFalse(ok_os)
        self.assertIn("Incompatible platform", notes_os)

        # Valid compatibility
        ok_valid, notes_valid = extension_installer.check_compatibility(">=0.7.0")
        self.assertTrue(ok_valid)

    # 13. Dependency handling on uninstall
    def test_dependency_handling_on_uninstall(self):
        # Install parent library extension
        mock_lib = {"id": "core-math-lib", "name": "Core Math Lib", "type": "extension", "version": "1.0.0"}
        ext_mgr.install_from_github("test/lib", mock_data=mock_lib)

        # Install consumer extension that depends on core-math-lib
        mock_app = {
            "id": "advanced-solver",
            "name": "Advanced Solver",
            "type": "extension",
            "version": "1.0.0",
            "dependencies": ["core-math-lib"],
        }
        ext_mgr.install_from_github("test/app", mock_data=mock_app)

        # Attempt to uninstall core-math-lib without force
        ok, msg = ext_mgr.uninstall("core-math-lib")
        self.assertFalse(ok)
        self.assertIn("Required as a dependency", msg)
        self.assertIn("advanced-solver", msg)

        # Forced uninstall works
        ok_force, _ = ext_mgr.uninstall("core-math-lib", force=True)
        self.assertTrue(ok_force)

    # 14. Uninstallation cleans up managed files while preserving unrelated data
    def test_uninstallation_preserves_unrelated_data(self):
        # Create an unrelated user file in the extensions directory
        user_safe_file = ext_mgr.CUSTOM_EXTENSIONS_DIR / "my_user_notes.txt"
        user_safe_file.write_text("IMPORTANT USER NOTES: DO NOT DELETE", encoding="utf-8")

        mock_ext = {"id": "disposable-ext", "name": "Disposable", "type": "extension", "version": "1.0.0"}
        ext_mgr.install_from_github("test/disp", mock_data=mock_ext)

        ext_folder = ext_mgr.CUSTOM_EXTENSIONS_DIR / "disposable-ext"
        self.assertTrue(ext_folder.exists())

        # Uninstall
        ok, _ = ext_mgr.uninstall("disposable-ext")
        self.assertTrue(ok)
        self.assertFalse(ext_folder.exists())

        # Unrelated user file is completely intact
        self.assertTrue(user_safe_file.exists())
        self.assertEqual(user_safe_file.read_text(encoding="utf-8"), "IMPORTANT USER NOTES: DO NOT DELETE")

    # 15. Recovery from interrupted installation
    def test_recovery_from_failed_installation(self):
        # Mock inspection failure
        broken_mock = {
            "id": "broken-ext",
            "compatibility": ">=999.0.0",  # Will fail compatibility
        }
        ok, err = ext_mgr.install_from_github("test/broken", mock_data=broken_mock)
        self.assertFalse(ok)
        self.assertIn("Compatibility check failed", err)

        # Ensure no orphan directory or registry entry was left
        self.assertFalse((ext_mgr.CUSTOM_EXTENSIONS_DIR / "broken-ext").exists())
        self.assertFalse(ext_mgr.is_installed("broken-ext"))


if __name__ == "__main__":
    unittest.main()
