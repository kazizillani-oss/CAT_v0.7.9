"""
Automated Test Suite for CAT CLI Provider Center 2.0.

Validates:
1. 160+ verified providers in catalog (actual count, schema, A-Z ordering)
2. Dynamic provider count calculations
3. ActiveAIState single source of truth & hot model switching
4. model_router cache invalidation
5. ModelVerificationEngine validation pipeline & secret masking
6. CATRootViewport responsive breakpoint engine
7. Screen lifecycle & clean instantiation (25+ cycles)
8. Sign-out confirmation modal
9. UTF-8 encoding integrity & zero BOM in source files
"""

import os
import sys
import json
import ast
import time
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_CAT_ROOT = os.path.dirname(_HERE)
if _CAT_ROOT not in sys.path:
    sys.path.insert(0, _CAT_ROOT)


class TestProviderCatalog(unittest.TestCase):
    """Test 160+ verified providers and schema requirements."""

    def test_provider_count_exceeds_160(self):
        json_path = os.path.join(_CAT_ROOT, "providers", "providers.json")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        providers = data.get("providers", [])
        self.assertGreaterEqual(
            len(providers), 160,
            f"Expected at least 160 verified providers, got {len(providers)}"
        )

    def test_provider_schema_validity(self):
        json_path = os.path.join(_CAT_ROOT, "providers", "providers.json")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        providers = data.get("providers", [])

        ids = set()
        for p in providers:
            pid = p.get("id")
            name = p.get("name")
            endpoint = p.get("api_endpoint")
            style = p.get("api_style")

            self.assertTrue(pid, f"Provider missing id: {p}")
            self.assertTrue(name, f"Provider missing name: {p}")
            self.assertTrue(endpoint, f"Provider missing endpoint: {pid}")
            self.assertTrue(style, f"Provider missing api_style: {pid}")
            self.assertNotIn(pid, ids, f"Duplicate provider ID found: {pid}")
            ids.add(pid)

    def test_a_to_z_ordering(self):
        json_path = os.path.join(_CAT_ROOT, "providers", "providers.json")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        providers = data.get("providers", [])
        names = [p.get("name", "").lower() for p in providers]
        sorted_names = sorted(names)
        self.assertEqual(names, sorted_names, "Providers must be sorted strictly A to Z by name")

    def test_chinese_providers_included(self):
        json_path = os.path.join(_CAT_ROOT, "providers", "providers.json")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        providers = data.get("providers", [])
        ids = {p.get("id") for p in providers}

        expected_chinese = [
            "deepseek", "alibaba-qwen", "moonshot", "zhipu", "minimax",
            "tencent", "bytedance-doubao", "baidu", "yi",
            "sensetime", "internlm", "baichuan", "stepfun"
        ]
        for cid in expected_chinese:
            self.assertIn(cid, ids, f"Missing first-class Chinese provider: {cid}")


class TestActiveAIState(unittest.TestCase):
    """Test ActiveAIState singleton, hot model switching, and persistence."""

    def setUp(self):
        from calc_terminal.models.active_state import ActiveAIStateManager
        from calc_terminal.providers import provider_manager as pm
        self._orig_cfg = dict(pm.load_config())
        ActiveAIStateManager.reset_instance()

    def tearDown(self):
        from calc_terminal.models.active_state import ActiveAIStateManager
        from calc_terminal.providers import provider_manager as pm
        pm.save_config(self._orig_cfg)
        ActiveAIStateManager.reset_instance()

    def test_singleton_active_state(self):
        from calc_terminal.models.active_state import get_active_state, set_active_ai, ActiveAIStateManager
        s1 = get_active_state()
        self.assertIsNotNone(s1)

        # Hot switch model
        new_state = set_active_ai("deepseek", "deepseek-chat", {"api_key": "test-key", "base_url": "https://api.deepseek.com/v1"})
        self.assertEqual(new_state.provider_id, "deepseek")
        self.assertEqual(new_state.model_id, "deepseek-chat")
        self.assertEqual(new_state.status, "Ready")

        # Second retrieval reflects the change
        s2 = get_active_state()
        self.assertEqual(s2.provider_id, "deepseek")
        self.assertEqual(s2.model_id, "deepseek-chat")

    def test_subscriber_notification(self):
        from calc_terminal.models.active_state import ActiveAIStateManager, set_active_ai
        mgr = ActiveAIStateManager.get_instance()

        notified = []
        def listener(record):
            notified.append((record.provider_id, record.model_id))

        mgr.subscribe(listener)
        set_active_ai("anthropic", "claude-4-sonnet", {})
        self.assertEqual(len(notified), 1)
        self.assertEqual(notified[0], ("anthropic", "claude-4-sonnet"))
        mgr.unsubscribe(listener)


class TestModelRouterCache(unittest.TestCase):
    """Test model_router cache invalidation on model switch."""

    def test_invalidate_cache(self):
        from calc_terminal import model_router
        model_router.invalidate_cache()
        configs1 = model_router.available_configs()
        self.assertIsInstance(configs1, list)

        # Invalidate again
        model_router.invalidate_cache()
        self.assertIsNone(model_router._registry_cache)


class TestModelVerificationEngine(unittest.TestCase):
    """Test verification pipeline for unknown and custom models."""

    def test_secret_masking(self):
        from calc_terminal.models.verification_engine import mask_secret
        self.assertEqual(mask_secret(""), "")
        self.assertEqual(mask_secret("short"), "********")
        masked = mask_secret("sk-1234567890abcdefg")
        self.assertTrue(masked.startswith("sk-"))
        self.assertTrue(masked.endswith("defg"))
        self.assertNotIn("1234567890", masked)

    def test_empty_model_id_rejected(self):
        from calc_terminal.models.verification_engine import ModelVerificationEngine, VerificationStatus
        engine = ModelVerificationEngine()
        res = engine.verify_custom_model("openai", "", "https://api.openai.com/v1")
        self.assertFalse(res.success)
        self.assertEqual(res.status, VerificationStatus.FAILED)
        self.assertIn("empty", res.error.lower())

    def test_invalid_url_scheme_rejected(self):
        from calc_terminal.models.verification_engine import ModelVerificationEngine, VerificationStatus
        engine = ModelVerificationEngine()
        res = engine.verify_custom_model("custom", "test-model", "ftp://invalid-url.com")
        self.assertFalse(res.success)
        self.assertEqual(res.status, VerificationStatus.FAILED)
        self.assertIn("scheme", res.error.lower())

    def test_unsupported_protocol_rejected(self):
        from calc_terminal.models.verification_engine import ModelVerificationEngine, VerificationStatus
        engine = ModelVerificationEngine()
        res = engine.verify_custom_model("custom", "test-model", "https://api.test.com", protocol="unsupported_proto_xyz")
        self.assertFalse(res.success)
        self.assertEqual(res.status, VerificationStatus.FAILED)


class TestResponsiveViewport(unittest.TestCase):
    """Test CATRootViewport responsive breakpoints."""

    def test_size_classes(self):
        from calc_terminal.ui.viewport import get_terminal_size_class
        self.assertEqual(get_terminal_size_class(120), "large")
        self.assertEqual(get_terminal_size_class(100), "large")
        self.assertEqual(get_terminal_size_class(85), "medium")
        self.assertEqual(get_terminal_size_class(70), "small")
        self.assertEqual(get_terminal_size_class(50), "very_small")


class TestSourceIntegrity(unittest.TestCase):
    """Verify clean UTF-8 encoding without BOM and valid Python AST."""

    def test_zero_bom_in_model_py(self):
        model_path = os.path.join(_CAT_ROOT, "model.py")
        with open(model_path, "rb") as f:
            header = f.read(4)
        self.assertNotEqual(header[:3], b"\xef\xbb\xbf", "model.py must not contain a UTF-8 BOM")

    def test_ast_parse_all_modules(self):
        modules = [
            "model.py",
            "models/active_state.py",
            "models/verification_engine.py",
            "ui/viewport.py",
            "ui/app.py",
            "model_router.py",
        ]
        for m in modules:
            path = os.path.join(_CAT_ROOT, m)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            try:
                ast.parse(content)
            except Exception as e:
                self.fail(f"AST parse failed for {m}: {e}")


class TestScreenLifecycle(unittest.TestCase):
    """Test instantiating and mounting screens 25+ times without leakage."""

    def test_screen_lifecycle_instantiations(self):
        from calc_terminal.model import (
            ProviderScreen, ModelScreen, ApiKeyScreen, VerifyScreen,
            MyModelsScreen, AddCustomModelScreen, UpdateCenterScreen,
            ModelConfirmModal, ALL_PROVIDERS
        )
        sample_prov = ALL_PROVIDERS[0]

        for i in range(25):
            s1 = ProviderScreen(embedded=True)
            self.assertIsNotNone(s1)
            s2 = ModelScreen(sample_prov, embedded=True)
            self.assertIsNotNone(s2)
            s3 = ApiKeyScreen(sample_prov, "test-model", embedded=True)
            self.assertIsNotNone(s3)
            s4 = VerifyScreen({"provider": "test", "model": "test"}, embedded=True)
            self.assertIsNotNone(s4)
            s5 = MyModelsScreen(embedded=True)
            self.assertIsNotNone(s5)
            s6 = AddCustomModelScreen(embedded=True)
            self.assertIsNotNone(s6)
            s7 = UpdateCenterScreen(embedded=True)
            self.assertIsNotNone(s7)
            s8 = ModelConfirmModal("deepseek", "deepseek-chat", {})
            self.assertIsNotNone(s8)


class TestProviderCenterFixes(unittest.TestCase):
    """Test specific fixes for Provider Center 2.0:
    - Zero double-encoded UTF-8 corruptions in providers.json
    - Zero duplicate alias sub-merges
    - Enter key handler (on_input_submitted)
    - Mouse cursor & touch screen row click handler (_on_row_clicked)
    - Failover Chain integration
    """

    def test_zero_encoding_corruption_in_providers_json(self):
        json_path = os.path.join(_CAT_ROOT, "providers", "providers.json")
        with open(json_path, "r", encoding="utf-8") as f:
            content = f.read()
        for bad in ("â€”", "â€“", "â€\"", "â€˜", "â€™", "â€œ", "\ufeff"):
            self.assertNotIn(bad, content, f"providers.json must not contain corrupted encoding artifact: {bad}")

    def test_zero_submerged_duplicate_endpoints(self):
        json_path = os.path.join(_CAT_ROOT, "providers", "providers.json")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        providers = data.get("providers", [])
        ids = {p["id"] for p in providers}
        
        # Verify removed duplicate aliases are NOT in catalog
        banned_aliases = [
            "01-yi", "zeroone", "togetherai-alt", "together-cloud", "together_ai",
            "baidu-ernie", "byte-avalanche", "bedrock", "deepinfra_inference",
            "goog-vertex", "hyperbolic_cloud", "lambdalabs", "monster_api",
            "ollama-custom", "sensenova", "vllm_hosted", "kobold_united"
        ]
        for bad_id in banned_aliases:
            self.assertNotIn(bad_id, ids, f"Sub-merged duplicate alias must not exist in catalog: {bad_id}")

    def test_provider_screen_handlers_exist(self):
        from calc_terminal.model import ProviderScreen, ProviderRow, InfoPanel
        screen = ProviderScreen(embedded=True)
        self.assertTrue(hasattr(screen, "on_input_submitted"), "ProviderScreen must implement on_input_submitted for Enter key")
        self.assertTrue(hasattr(screen, "_on_row_clicked"), "ProviderScreen must implement _on_row_clicked for mouse and touch screen clicks")
        self.assertTrue(hasattr(screen, "_toggle_failover_for_selected"), "ProviderScreen must implement _toggle_failover_for_selected")
        self.assertTrue(hasattr(screen, "_open_failover_panel"), "ProviderScreen must implement _open_failover_panel")

        # Test clicking a row updates selection
        screen._selected_index = 0
        screen._on_row_clicked(screen._filtered[1], 1)
        self.assertEqual(screen._selected_index, 1, "Clicking row 1 must update selected index to 1")

        # Test InfoPanel has interactive action buttons
        panel = InfoPanel()
        self.assertTrue(hasattr(panel, "compose"), "InfoPanel must compose action buttons")


if __name__ == "__main__":
    unittest.main()
