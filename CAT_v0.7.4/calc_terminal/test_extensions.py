"""
CAT — Extension System regression suite (VS Code-style).
Covers spec sections 1-29:

  Gestures / CAT Vision / Personalize treated as real installable extensions,
  main-menu dynamic visibility, full lifecycle (INSTALL/ENABLE/DISABLE/UNINSTALL),
  persistence, no phantom, error isolation, future extensibility, metadata
  (creator Kazi Zillani ✓ Verified, trusted, size from filesystem).

Run:  python -m pytest calc_terminal/test_extensions.py -q
"""

import os
import sys
import json
import tempfile
import shutil
import pathlib
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestExtensionLifecycle(unittest.TestCase):
    """Sections 3, 6, 18, 19, 27 — lifecycle + menu visibility should be
    single source of truth via extensions.should_show_in_menu()."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cct_ext_test_")
        # isolate HOME so registry/config do not clobber the developer's real files
        self._orig_home = os.environ.get("HOME")
        self._orig_up = os.environ.get("USERPROFILE")
        os.environ["HOME"] = self.tmp
        os.environ["USERPROFILE"] = self.tmp

        import calc_terminal.extensions as ext
        import calc_terminal.config as cfg
        # reload to pick up new HOME if already imported (CI reuses process)
        import importlib
        importlib.reload(cfg)
        importlib.reload(ext)
        self.ext = ext
        self.cfg = cfg
        self.ext.REGISTRY_FILE = pathlib.Path(self.tmp) / ".cct_extensions_registry.json"
        self.cfg.CONFIG_PATH = os.path.join(self.tmp, ".cct_config.json")
        self.ext._cached_state = None
        self.ext._cached_mtime = 0
        self.cfg._cached = None
        # ensure fresh registry (all installed+enabled on first load per spec 20)
        self.ext._load_registry()

        # header needs fresh import to see patched ext module
        if "calc_terminal.ui.header" in sys.modules:
            importlib.reload(sys.modules["calc_terminal.ui.header"])
        from calc_terminal.ui.header import get_nav_items
        self.get_nav_items = get_nav_items

    def tearDown(self):
        if self._orig_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._orig_home
        if self._orig_up is None:
            os.environ.pop("USERPROFILE", None)
        else:
            os.environ["USERPROFILE"] = self._orig_up
        shutil.rmtree(self.tmp, ignore_errors=True)
        # reset caches so following tests (or real app) don't read tmp registry
        try:
            import calc_terminal.extensions as ext
            import calc_terminal.config as cfg
            ext._cached_state = None
            ext._cached_mtime = 0
            cfg._cached = None
        except Exception:
            pass

    # helpers
    def nav_has(self, action):
        return any(a == action for a, _, _ in self.get_nav_items())

    # --- 1. Builtin metadata (sections 9-14) ---

    def test_builtin_metadata_gestures(self):
        m = self.ext.get_metadata("gestures")
        self.assertEqual(m["publisher"], "Kazi Zillani")
        self.assertTrue(m["publisher_verified"])
        self.assertTrue(m["verified"])
        self.assertTrue(m["trusted"])
        self.assertEqual(m["publisher_type"], "individual")
        self.assertIn("version", m)
        self.assertIn("category", m)

    def test_builtin_metadata_vision(self):
        self.assertNotIn("vision", self.ext.BUILTIN_EXTENSIONS)
        self.assertNotIn("customization", self.ext.BUILTIN_EXTENSIONS)
        self.assertIsNone(self.ext.get_metadata("vision"))
        self.assertIsNone(self.ext.get_metadata("customization"))

    def test_builtin_metadata_personalize(self):
        m = self.ext.get_metadata("personalize")
        self.assertEqual(m["publisher"], "Kazi Zillani")
        self.assertTrue(m["verified"])
        self.assertTrue(m["trusted"])

    def test_verified_system_supports_unverified(self):
        # custom / third-party extensions default to unverified + untrusted (section 12-14)
        data = self.ext._load_registry()
        data["untrusted_ext"] = {"installed": True, "enabled": True, "version": "0.0.1", "install_time": 0, "size_bytes": 100}
        self.ext._save_registry(data)
        m = self.ext.get_metadata("untrusted_ext")
        self.assertFalse(m["verified"])
        self.assertFalse(m["publisher_verified"])
        self.assertFalse(m["trusted"])
        self.assertEqual(m["publisher"], "Unknown")

    def test_size_from_filesystem_not_hardcoded(self):
        for eid in ("gestures", "personalize"):
            m = self.ext.get_metadata(eid)
            self.assertGreater(m["size_bytes"], 0, f"{eid} size should be >0 from filesystem")
            self.assertIsInstance(m["size_display"], str)
            # size_display should contain a unit (B/KB/MB)
            self.assertRegex(m["size_display"], r"(B|KB|MB)")

    def test_publisher_type_future_company(self):
        # architecture must carry publisher_type field; builtins use individual,
        # but the dict supports company/organization for future (section 14)
        self.assertIn("publisher_type", self.ext.BUILTIN_EXTENSIONS["gestures"])
        # mutating a builtin definition to company should still round-trip via metadata
        orig = self.ext.BUILTIN_EXTENSIONS["gestures"]["publisher_type"]
        try:
            self.ext.BUILTIN_EXTENSIONS["gestures"]["publisher_type"] = "company"
            m = self.ext.get_metadata("gestures")
            self.assertEqual(m["publisher_type"], "company")
        finally:
            self.ext.BUILTIN_EXTENSIONS["gestures"]["publisher_type"] = orig

    # --- 3. Lifecycle / 27 gestures ---

    def test_gestures_lifecycle(self):
        # clean: uninstall first
        if self.ext.is_installed("gestures"):
            self.ext.uninstall("gestures")
        self.assertEqual(self.ext.get_state("gestures"), "NOT_INSTALLED")
        self.assertFalse(self.nav_has("gestures"))

        ok, _ = self.ext.install("gestures")
        self.assertTrue(ok)
        self.assertEqual(self.ext.get_state("gestures"), "INSTALLED_ENABLED")
        self.assertTrue(self.nav_has("gestures"))

        ok, _ = self.ext.disable("gestures")
        self.assertTrue(ok)
        self.assertEqual(self.ext.get_state("gestures"), "INSTALLED_DISABLED")
        self.assertFalse(self.nav_has("gestures"))
        self.assertTrue(self.ext.is_installed("gestures"))  # remains installed

        ok, _ = self.ext.enable("gestures")
        self.assertTrue(ok)
        self.assertEqual(self.ext.get_state("gestures"), "INSTALLED_ENABLED")
        self.assertTrue(self.nav_has("gestures"))

        ok, _ = self.ext.uninstall("gestures")
        self.assertTrue(ok)
        self.assertEqual(self.ext.get_state("gestures"), "NOT_INSTALLED")
        self.assertFalse(self.nav_has("gestures"))

    def test_vision_lifecycle(self):
        # vision is removed as a builtin extension
        self.assertFalse(self.ext.is_installed("vision"))
        self.assertFalse(self.ext.should_show_in_menu("vision"))
        self.assertFalse(self.nav_has("vision"))
        ok, msg = self.ext.install("vision")
        self.assertFalse(ok)
        self.assertIn("not found in marketplace", msg)

    def test_personalize_lifecycle(self):
        # personalize maps to action customize_ai in the menu
        if self.ext.is_installed("personalize"):
            self.ext.uninstall("personalize")
        self.assertFalse(self.nav_has("customize_ai"))
        self.ext.install("personalize")
        self.assertTrue(self.nav_has("customize_ai"))
        self.ext.disable("personalize")
        self.assertFalse(self.nav_has("customize_ai"))
        self.assertTrue(self.ext.is_installed("personalize"))
        self.ext.enable("personalize")
        self.assertTrue(self.nav_has("customize_ai"))
        self.ext.uninstall("personalize")
        self.assertFalse(self.nav_has("customize_ai"))

    def test_install_idempotency_and_messages(self):
        if not self.ext.is_installed("gestures"):
            self.ext.install("gestures")
        ok, msg = self.ext.install("gestures")
        self.assertFalse(ok)
        self.assertIn("already installed", msg)

    def test_enable_requires_install(self):
        if self.ext.is_installed("gestures"):
            self.ext.uninstall("gestures")
        ok, msg = self.ext.enable("gestures")
        self.assertFalse(ok)
        self.assertIn("not installed", msg)

    def test_uninstall_not_installed(self):
        if self.ext.is_installed("gestures"):
            self.ext.uninstall("gestures")
        ok, msg = self.ext.uninstall("gestures")
        self.assertFalse(ok)

    # --- 7. Persistence ---

    def test_persistence_disabled_survives_restart(self):
        if not self.ext.is_installed("personalize"):
            self.ext.install("personalize")
        self.ext.disable("personalize")
        self.assertEqual(self.ext.get_state("personalize"), "INSTALLED_DISABLED")
        # simulate restart: clear in-memory cache and reload from disk
        self.ext._cached_state = None
        self.ext._cached_mtime = 0
        self.cfg._cached = None
        self.assertEqual(self.ext.get_state("personalize"), "INSTALLED_DISABLED")
        self.assertFalse(self.nav_has("customize_ai"))

    def test_persistence_enabled_survives_restart(self):
        if not self.ext.is_installed("gestures"):
            self.ext.install("gestures")
        else:
            if not self.ext.is_enabled("gestures"):
                self.ext.enable("gestures")
        self.assertEqual(self.ext.get_state("gestures"), "INSTALLED_ENABLED")
        # simulate restart: clear in-memory cache and reload from disk
        self.ext._cached_state = None
        self.ext._cached_mtime = 0
        self.cfg._cached = None
        self.assertEqual(self.ext.get_state("gestures"), "INSTALLED_ENABLED")
        self.assertTrue(self.nav_has("gestures"))

    def test_persistence_uninstalled_survives_restart(self):
        if self.ext.is_installed("personalize"):
            self.ext.uninstall("personalize")
        self.assertEqual(self.ext.get_state("personalize"), "NOT_INSTALLED")
        self.ext._cached_state = None
        self.ext._cached_mtime = 0
        self.cfg._cached = None
        self.assertEqual(self.ext.get_state("personalize"), "NOT_INSTALLED")
        self.assertFalse(self.ext.is_installed("personalize"))

    # --- 2 / 18 / 19 Main menu + No phantom ---

    def test_main_menu_reflects_state_dynamically(self):
        # enable all
        for eid in ("gestures", "personalize"):
            if not self.ext.is_installed(eid):
                self.ext.install(eid)
            elif not self.ext.is_enabled(eid):
                self.ext.enable(eid)
        self.assertTrue(self.nav_has("gestures"))
        self.assertTrue(self.nav_has("customize_ai"))
        # disable all
        self.ext.disable("gestures")
        self.ext.disable("personalize")
        self.assertFalse(self.nav_has("gestures"))
        self.assertFalse(self.nav_has("customize_ai"))
        # enable only gestures
        self.ext.enable("gestures")
        self.assertTrue(self.nav_has("gestures"))
        self.assertFalse(self.nav_has("customize_ai"))

    def test_no_phantom_uninstalled_shows_in_menu(self):
        self.assertFalse(self.ext.should_show_in_menu("vision"))
        self.assertFalse(self.nav_has("vision"))
        if self.ext.is_installed("personalize"):
            self.ext.uninstall("personalize")
        self.assertFalse(self.ext.should_show_in_menu("customize_ai"))
        self.assertFalse(self.nav_has("customize_ai"))

    def test_no_phantom_disabled_shows_in_menu(self):
        if not self.ext.is_installed("gestures"):
            self.ext.install("gestures")
        self.ext.disable("gestures")
        self.assertFalse(self.ext.should_show_in_menu("gestures"))
        self.assertFalse(self.nav_has("gestures"))

    def test_uninstall_keeps_other_extensions(self):
        for eid in ("gestures", "personalize"):
            if not self.ext.is_installed(eid):
                self.ext.install(eid)
        self.ext.uninstall("gestures")
        self.assertFalse(self.ext.is_installed("gestures"))
        self.assertTrue(self.ext.is_installed("personalize"))

    # --- 15 Registry API + 16 feature registration ---

    def test_registry_api_complete(self):
        for fn in ("discover", "install", "uninstall", "enable", "disable",
                   "is_installed", "is_enabled", "get_metadata", "get_size", "list_extensions"):
            self.assertTrue(callable(getattr(self.ext, fn)), f"missing {fn}")

    def test_list_extensions_includes_states(self):
        lst = self.ext.list_extensions()
        ids = {m["id"] for m in lst}
        self.assertIn("gestures", ids)
        self.assertIn("personalize", ids)
        self.assertNotIn("vision", ids)
        self.assertNotIn("customization", ids)
        for m in lst:
            self.assertIn("installed", m)
            self.assertIn("enabled", m)
            self.assertIn("state", m)

    def test_feature_registration_gated_by_enabled(self):
        if not self.ext.is_installed("gestures"):
            self.ext.install("gestures")
        else:
            if not self.ext.is_enabled("gestures"):
                self.ext.enable("gestures")
        ok = self.ext.register_feature("gestures", "menu", "test-feature", {"label": "Test"})
        self.assertTrue(ok)
        self.ext.disable("gestures")
        ok2 = self.ext.register_feature("gestures", "menu", "test-feature2")
        self.assertFalse(ok2)
        self.ext.enable("gestures")

    # --- 24 Error isolation ---

    def test_corrupt_registry_does_not_crash(self):
        with open(self.ext.REGISTRY_FILE, "w", encoding="utf-8") as f:
            f.write("{ not json }")
        self.ext._cached_state = None
        self.ext._cached_mtime = 0
        data = self.ext._load_registry()
        self.assertIsInstance(data, dict)
        # with install-first UX corrupt yields empty (all NOT_INSTALLED) — must not crash
        # and startup must still succeed
        self.ext._cached_state = None
        self.ext._cached_mtime = 0
        try:
            self.ext.startup()
        except Exception as e:
            self.fail(f"startup crashed after corrupt: {e}")

    def test_startup_does_not_crash_on_broken_extension(self):
        # startup must isolate failures and keep CAT alive (section 24)
        try:
            self.ext.startup()
        except Exception as e:
            self.fail(f"startup crashed: {e}")

    def test_validate_all_returns_list(self):
        errs = self.ext.validate_all()
        self.assertIsInstance(errs, list)

    # --- 27 Future extensions use same infrastructure ---

    def test_future_extension_same_infrastructure(self):
        data = self.ext._load_registry()
        data["my_future_ext"] = {"installed": True, "enabled": True, "version": "1.0.0", "install_time": 0, "size_bytes": 1234}
        self.ext._save_registry(data)
        self.assertTrue(self.ext.is_installed("my_future_ext"))
        self.assertTrue(self.ext.is_enabled("my_future_ext"))
        m = self.ext.get_metadata("my_future_ext")
        self.assertIsNotNone(m)
        self.assertFalse(m["verified"])  # unverified by default
        self.assertIn("my_future_ext", {x["id"] for x in self.ext.list_extensions()})
        self.ext.disable("my_future_ext")
        self.assertEqual(self.ext.get_state("my_future_ext"), "INSTALLED_DISABLED")
        self.ext.uninstall("my_future_ext")
        self.assertFalse(self.ext.is_installed("my_future_ext"))

    # --- 21 No hard-coded visibility ---

    def test_not_hardcoded_visibility(self):
        import pathlib
        hdr_text = pathlib.Path(__file__).parent.joinpath("ui", "header.py").read_text(encoding="utf-8")
        self.assertIn("should_show_in_menu", hdr_text)
        self.assertNotIn("show_gestures", hdr_text.lower())

    # --- 5 Enable/Disable must affect real runtime, not just button (spec 5) ---

    def test_gestures_runtime_disabled(self):
        """Gestures extension disabled must actually disable shortcut handling."""
        from calc_terminal.gestures.manager import add_gesture, delete_gesture, handle_shortcut

        if not self.ext.is_installed("gestures"):
            self.ext.install("gestures")
        elif not self.ext.is_enabled("gestures"):
            self.ext.enable("gestures")

        class MockApp:
            def action_save_file(self):
                return True

        g = add_gesture(name="runtime_test", trigger="shortcut", target="editor", action="save_file", keys="ctrl+shift+y")
        self.assertIsNotNone(g)
        try:
            # enabled → shortcut fires
            app = MockApp()
            self.assertTrue(handle_shortcut("ctrl+shift+y", app=app))
            # disabled → shortcut must NOT fire (real runtime inactive)
            self.ext.disable("gestures")
            app2 = MockApp()
            self.assertFalse(handle_shortcut("ctrl+shift+y", app=app2))
            self.assertFalse(app2.__dict__.get("_called", False))
            # re-enable → fires again
            self.ext.enable("gestures")
            app3 = MockApp()
            self.assertTrue(handle_shortcut("ctrl+shift+y", app=app3))
        finally:
            if g:
                try:
                    delete_gesture(g["id"])
                except Exception:
                    pass
            if not self.ext.is_enabled("gestures"):
                try:
                    self.ext.enable("gestures")
                except Exception:
                    pass

    # --- 20 Existing functionality preserved (smoke) ---

    def test_panels_still_importable(self):
        # architectural migration must not break imports; disabled panels should
        # show the "disabled" guard instead of crashing
        from calc_terminal.ui.gestures_panel import GesturesPanel
        from calc_terminal.ui.vision_panel import VisionPanel
        from calc_terminal.ui.personalize_center import PersonalizeCenter
        self.assertIsNotNone(GesturesPanel)
        self.assertIsNotNone(VisionPanel)
        self.assertIsNotNone(PersonalizeCenter)


if __name__ == "__main__":
    unittest.main(verbosity=2)
