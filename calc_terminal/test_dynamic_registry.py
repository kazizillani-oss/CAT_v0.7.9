"""
calc_terminal/test_dynamic_registry.py
======================================
Comprehensive test suite for CAT Universal AI Provider & Automatic Model Discovery System.
Tests:
  - ModelInfo schema, canonical model identity, categories, reasoning levels.
  - 8-stage ModelValidator pipeline.
  - DynamicModelRegistry: atomic persistence, offline integrity, reconciliation, ranking.
  - 2026 Model Catalog: GPT-6 Astra, Claude 4, DeepSeek-R1, Kimi K3, Gemini 2.5.
  - Chinese Provider Adapters: DeepSeek, Alibaba Qwen, Moonshot, Zhipu, MiniMax, Tencent, ByteDance, Xiaomi, Baidu.
  - Ollama Adapter: local vs cloud categorization.
  - ProviderDiscoveryManager: parallel execution, health tracking, new-model hooks.
  - CLI commands: cat models, cat providers audit, cat providers list.
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from calc_terminal.models.schema import (
    ModelInfo,
    STATUS_ACTIVE,
    STATUS_PREVIEW,
    STATUS_DEPRECATED,
    STATUS_AUTH_REQUIRED,
    AVAILABILITY_PAID_API,
    AVAILABILITY_FREE_API,
    AVAILABILITY_LOCAL,
    AVAILABILITY_OPEN_WEIGHT,
    CATEGORY_CODING,
    CATEGORY_REASONING,
    CATEGORY_FAST,
)
from calc_terminal.models.validator import ModelValidator
from calc_terminal.models.dynamic_registry import (
    DynamicModelRegistry,
    get_registry,
    get_dynamic_registry,
)
from calc_terminal.providers.adapters.base import BaseProviderAdapter
from calc_terminal.providers.adapters.openai_adapter import OpenAIAdapter
from calc_terminal.providers.adapters.anthropic_adapter import AnthropicAdapter
from calc_terminal.providers.adapters.gemini_adapter import GeminiAdapter
from calc_terminal.providers.adapters.chinese_adapters import (
    DeepSeekAdapter,
    AlibabaQwenAdapter,
    MoonshotKimiAdapter,
    ZhipuGLMAdapter,
    MiniMaxAdapter,
    TencentHunyuanAdapter,
    ByteDanceSeedAdapter,
    XiaomiMiMoAdapter,
    BaiduErnieAdapter,
)
from calc_terminal.providers.adapters.ollama_adapter import OllamaAdapter
from calc_terminal.providers.adapters import get_adapter
from calc_terminal.providers.discovery_manager import (
    ProviderDiscoveryManager,
    get_discovery_manager,
)
from calc_terminal.cli import main as cli_main


class TestModelSchemaAndValidator(unittest.TestCase):
    """Test standard schema, canonical identity, and 8-stage validation."""

    def test_model_info_canonical_id_and_family(self):
        m = ModelInfo(
            provider="openai",
            model_id="gpt-6-astra",
            context_window=1050000,
            max_output_tokens=128000,
            capabilities=["reasoning", "coding", "vision", "computer_use"],
            reasoning_levels=["low", "medium", "high", "xhigh", "max"],
        )
        self.assertEqual(m.canonical_model_id, "openai:gpt-6-astra")
        self.assertEqual(m.family, "GPT")
        self.assertEqual(m.availability_state, STATUS_ACTIVE)
        self.assertTrue(m.matches_category("coding"))
        self.assertTrue(m.matches_category("reasoning"))
        self.assertTrue(m.matches_category("vision"))

    def test_validator_rejects_invalid_identifiers(self):
        v = ModelValidator()
        bad_models = [
            ModelInfo(provider="", model_id="gpt-4"),  # empty provider
            ModelInfo(provider="openai", model_id=""),  # empty model id
            ModelInfo(provider="openai", model_id="*"),  # wildcard
            ModelInfo(provider="openai", model_id="default"),  # placeholder
        ]
        for bm in bad_models:
            valid, msg = v.validate(bm)
            self.assertFalse(valid, f"Expected {bm} to be rejected: {msg}")

    def test_validator_normalizes_capabilities(self):
        v = ModelValidator()
        m = ModelInfo(
            provider="deepseek",
            model_id="deepseek-r1",
            capabilities=["cot", "code", "streaming"],
            endpoint="https://api.deepseek.com/v1",
        )
        valid, msg = v.validate(m)
        self.assertTrue(valid, msg)
        self.assertIn("reasoning", m.capabilities)
        self.assertIn("coding", m.capabilities)

    def test_validator_rejects_insecure_urls(self):
        v = ModelValidator()
        m = ModelInfo(
            provider="untrusted",
            model_id="malicious-model",
            endpoint="file:///etc/passwd",
        )
        valid, msg = v.validate(m)
        self.assertFalse(valid)
        self.assertIn("Insecure endpoint", msg)


class TestDynamicModelRegistry(unittest.TestCase):
    """Test registry indexing, persistence, ranking, and reconciliation."""

    def setUp(self):
        DynamicModelRegistry.reset_instance()
        self.test_dir = tempfile.mkdtemp(prefix="cat_reg_test_")
        self.reg = DynamicModelRegistry(registry_dir=self.test_dir)

    def tearDown(self):
        DynamicModelRegistry.reset_instance()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_seeded_flagship_models_present(self):
        gpt6 = self.reg.get_model("gpt-6-astra", "openai")
        self.assertIsNotNone(gpt6, "GPT-6 Astra must be registered")
        self.assertEqual(gpt6.context_window, 1050000)
        self.assertEqual(gpt6.max_output_tokens, 128000)
        self.assertIn("max", gpt6.reasoning_levels)
        self.assertIn("computer_use", gpt6.capabilities)

        claude4 = self.reg.get_model("claude-4-sonnet-20260515", "anthropic")
        self.assertIsNotNone(claude4, "Claude 4 Sonnet must be registered")

        r1 = self.reg.get_model("deepseek-r1", "deepseek")
        self.assertIsNotNone(r1, "DeepSeek-R1 must be registered")

        k3 = self.reg.get_model("kimi-k3", "moonshot")
        self.assertIsNotNone(k3, "Kimi K3 must be registered")

    def test_ranking_scoring(self):
        coding_ranked = self.reg.get_ranked_models(task="coding", limit=5)
        self.assertGreater(len(coding_ranked), 0)
        top_coding_ids = [m.model_id for m in coding_ranked]
        # Flagship coding models should score near the top
        self.assertTrue(
            any(cand in top_coding_ids for cand in ("gpt-6-astra", "claude-4-sonnet-20260515", "deepseek-r1", "gpt-4o"))
        )

        fast_ranked = self.reg.get_ranked_models(task="fast", limit=5)
        self.assertGreater(len(fast_ranked), 0)

    def test_reconciliation_added_and_deprecated(self):
        # Simulate remote discovery returning a brand new model
        discovered = [
            ModelInfo(
                provider="mock-ai",
                model_id="mock-v1",
                capabilities=["chat"],
            ),
            ModelInfo(
                provider="mock-ai",
                model_id="mock-v2-next",
                capabilities=["chat", "coding"],
            ),
        ]
        diff1 = self.reg.reconcile_models("mock-ai", discovered)
        self.assertIn("mock-v1", diff1["added"])
        self.assertIn("mock-v2-next", diff1["added"])

        # Simulate second poll where mock-v1 was deprecated by vendor
        discovered_dep = [
            ModelInfo(
                provider="mock-ai",
                model_id="mock-v1",
                status=STATUS_DEPRECATED,
            ),
            ModelInfo(
                provider="mock-ai",
                model_id="mock-v2-next",
                status=STATUS_ACTIVE,
            ),
        ]
        diff2 = self.reg.reconcile_models("mock-ai", discovered_dep)
        self.assertIn("mock-v1", diff2["deprecated"])

    def test_offline_stale_protection(self):
        # When empty remote models are passed, existing models must NOT be deleted
        initial_count = len(self.reg.list_models(provider="openai"))
        self.assertGreater(initial_count, 0)

        # Provider fails or returns empty:
        diff = self.reg.reconcile_models("openai", [])
        self.assertEqual(len(diff["added"]), 0)
        # Verify models still exist in registry (marked stale)
        remaining = self.reg.list_models(provider="openai")
        self.assertEqual(len(remaining), initial_count)
        self.assertTrue(all(m.stale for m in remaining))

    def test_audit_summary(self):
        audit = self.reg.get_audit_summary()
        self.assertIn("total_models", audit)
        self.assertIn("total_providers", audit)
        self.assertGreater(audit["total_models"], 50)
        self.assertIn("openai", audit["models_by_provider"])


class TestProviderAdapters(unittest.TestCase):
    """Test built-in and Chinese adapters."""

    def test_openai_adapter_catalog(self):
        adapter = OpenAIAdapter("openai", {"api_key": ""})
        models = adapter.discover_models()
        self.assertGreater(len(models), 0)
        model_ids = [m.model_id for m in models]
        self.assertIn("gpt-6-astra", model_ids)
        self.assertIn("gpt-4o", model_ids)

    def test_anthropic_adapter_catalog(self):
        adapter = AnthropicAdapter("anthropic", {"api_key": ""})
        models = adapter.discover_models()
        self.assertGreater(len(models), 0)
        model_ids = [m.model_id for m in models]
        self.assertIn("claude-4-sonnet-20260515", model_ids)

    def test_chinese_adapters_catalog(self):
        # DeepSeek
        ds_adapter = DeepSeekAdapter("deepseek", {})
        ds_models = ds_adapter.discover_models()
        self.assertTrue(any(m.model_id == "deepseek-r1" for m in ds_models))

        # Moonshot Kimi
        kimi_adapter = MoonshotKimiAdapter("moonshot", {})
        kimi_models = kimi_adapter.discover_models()
        self.assertTrue(any("kimi" in m.model_id for m in kimi_models))

        # Alibaba Qwen
        qwen_adapter = AlibabaQwenAdapter("alibaba-qwen", {})
        qwen_models = qwen_adapter.discover_models()
        self.assertTrue(any("qwen" in m.model_id for m in qwen_models))

        # Zhipu GLM
        glm_adapter = ZhipuGLMAdapter("zhipu", {})
        glm_models = glm_adapter.discover_models()
        self.assertTrue(any("glm" in m.model_id for m in glm_models))

    def test_ollama_adapter_distinguishes_local_vs_cloud(self):
        local_adapter = OllamaAdapter("ollama", {"base_url": "http://localhost:11434"})
        self.assertTrue(local_adapter.is_local)

        cloud_adapter = OllamaAdapter("ollama", {"base_url": "https://ollama.cloud/api"})
        self.assertFalse(cloud_adapter.is_local)


class TestProviderDiscoveryManager(unittest.TestCase):
    """Test Discovery Manager coordination and notification hooks."""

    def test_discovery_manager_singleton(self):
        dm1 = get_discovery_manager()
        dm2 = get_discovery_manager()
        self.assertIs(dm1, dm2)

    def test_notification_hook_on_new_models(self):
        dm = get_discovery_manager()
        notifications_received = []

        def _hook(new_models):
            notifications_received.extend(new_models)

        dm.register_notification_hook(_hook)
        # Directly trigger notification
        mock_model = ModelInfo(provider="test-p", model_id="test-m-2026")
        dm._notify_new_models([mock_model])
        self.assertIn(mock_model, notifications_received)


class TestCLISubcommands(unittest.TestCase):
    """Test cat models and cat providers CLI subcommands."""

    def test_cli_models_provider_filter(self):
        ret = cli_main(["models", "--provider", "openai"])
        self.assertEqual(ret, 0)

    def test_cli_providers_audit(self):
        ret = cli_main(["providers", "audit"])
        self.assertEqual(ret, 0)

    def test_cli_providers_list(self):
        ret = cli_main(["providers", "list"])
        self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()
