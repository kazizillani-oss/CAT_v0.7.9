import os
import shutil
import unittest
from pathlib import Path
from calc_terminal import extensions as cct_ext
from calc_terminal.ui.extensions_panel import _CreateExtensionModal, ExtensionsPanel
from textual.app import App
from textual.widgets import Input, Button


class TestCustomExtensionCreation(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_ext_id = "test_custom_math_tool"
        self.test_dir = cct_ext.CUSTOM_EXTENSIONS_DIR / self.test_ext_id
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
        reg = cct_ext._load_registry()
        if self.test_ext_id in reg:
            reg.pop(self.test_ext_id, None)
            cct_ext._save_registry(reg)

    def test_create_extension_backend(self):
        ok, res = cct_ext.create_extension(
            extension_id=self.test_ext_id,
            name="Test Custom Math Tool",
            description="Performs quick calculus formulas",
            icon="📐",
            publisher="Test Dev",
            category="Mathematics",
            version="1.0.0",
            script_code="def run(): return 42\n"
        )
        self.assertTrue(ok)
        self.assertIn("created and enabled successfully", res)

        # Verify filesystem presence
        self.assertTrue((self.test_dir / "extension.json").exists())
        self.assertTrue((self.test_dir / f"{self.test_ext_id}.py").exists())

        # Verify discovery in list_extensions
        all_exts = cct_ext.list_extensions()
        found = [e for e in all_exts if e["id"] == self.test_ext_id]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["category"], "Mathematics")
        self.assertEqual(found[0]["icon"], "📐")

        # Verify enable / disable
        self.assertTrue(cct_ext.disable(self.test_ext_id))
        self.assertFalse(cct_ext.is_enabled(self.test_ext_id))
        self.assertTrue(cct_ext.enable(self.test_ext_id))
        self.assertTrue(cct_ext.is_enabled(self.test_ext_id))

    async def test_create_extension_modal_ui(self):
        class ModalHostApp(App):
            def compose(self):
                yield Button("Open", id="open-btn")

        app = ModalHostApp()
        async with app.run_test() as pilot:
            modal = _CreateExtensionModal()
            app.push_screen(modal)
            await pilot.pause()

            # Set inputs
            modal.query_one("#input-ext-name", Input).value = "Modal Created Tool"
            modal.query_one("#input-ext-id", Input).value = "modal_tool_1"
            modal.query_one("#input-ext-desc", Input).value = "Created via modal"
            modal.query_one("#input-ext-icon", Input).value = "🚀"
            modal.query_one("#input-ext-cat", Input).value = "Developer Tools"

            submit_btn = modal.query_one("#create-submit", Button)
            submit_btn.press()
            await pilot.pause()

            # Cleanup modal created tool
            clean_dir = cct_ext.CUSTOM_EXTENSIONS_DIR / "modal_tool_1"
            if clean_dir.exists():
                shutil.rmtree(clean_dir, ignore_errors=True)
            reg = cct_ext._load_registry()
            if "modal_tool_1" in reg:
                reg.pop("modal_tool_1", None)
                cct_ext._save_registry(reg)

    async def test_create_extension_web_endpoint(self):
        from calc_terminal.web.server import create_extension, ExtensionCreateRequest
        req = ExtensionCreateRequest(
            id="web_tool_1",
            name="Web Custom Tool",
            description="Created via Web API",
            icon="🌐",
            publisher="Web Dev",
            category="Utilities",
        )
        res = await create_extension(req)
        self.assertTrue(res["success"])
        self.assertIn("message", res)
        # Check in list
        exts = res["extensions"]
        found = [e for e in exts if e["id"] == "web_tool_1"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["name"], "Web Custom Tool")

        # Cleanup
        clean_dir = cct_ext.CUSTOM_EXTENSIONS_DIR / "web_tool_1"
        if clean_dir.exists():
            shutil.rmtree(clean_dir, ignore_errors=True)
        reg = cct_ext._load_registry()
        if "web_tool_1" in reg:
            reg.pop("web_tool_1", None)
            cct_ext._save_registry(reg)


if __name__ == "__main__":
    unittest.main()
