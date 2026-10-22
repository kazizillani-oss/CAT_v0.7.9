"""Unit and integration test suite for the CAT Master Architecture.
Validates:
1. HardwareAnalyzer (CPU, RAM, GPU, OS, tier)
2. ModelCompatibilityEngine (5 tiers, VRAM/RAM offload, recommendation logic)
3. CATBenchmarkSystem (7 categories, transparent attribution, leaderboard)
4. Ollama Catalog & Dynamic Discovery
5. Smart Model Router & Privacy Policies (never_cloud, local_first, cloud_first, best_available)
6. Granular Permissions (delete_files, browser_automation)
7. CLI Model UX handlers
"""

import pytest
from calc_terminal.hardware_analyzer import HardwareAnalyzer, HardwareProfile, CPUInfo, RAMInfo, GPUInfo
from calc_terminal.compatibility_engine import ModelCompatibilityEngine, CompatibilityReport
from calc_terminal.benchmark_system import CATBenchmarkSystem, BenchmarkScore, BenchmarkSource
import calc_terminal.ollama_catalog as catalog
import calc_terminal.model_router as router
from calc_terminal.permissions import PERMISSION_DEFS, MUTATING_KEYS, PermissionManager
from calc_terminal.cli import _models_cli


class TestHardwareAnalyzer:
    def test_detect_runs_and_returns_profile(self):
        profile = HardwareAnalyzer.analyze()
        assert isinstance(profile, HardwareProfile)
        assert profile.cpu.logical_cores >= 1
        assert profile.ram.total_gb > 0
        assert profile.ai_capability in ("EXCELLENT", "GOOD", "MODERATE", "LIMITED")
        assert profile.local_ai_tier.value == profile.ai_capability

    def test_profile_to_dict_contains_all_keys(self):
        profile = HardwareAnalyzer.analyze()
        d = profile.to_dict()
        assert "cpu" in d
        assert "ram" in d
        assert "gpu" in d
        assert "storage" in d
        assert "ai_capability" in d


class TestModelCompatibilityEngine:
    def test_small_model_on_gpu_is_excellent(self):
        # Synthetic profile with 8GB VRAM
        mock_hw = HardwareProfile(
            cpu=CPUInfo(logical_cores=16),
            ram=RAMInfo(total_gb=32.0, available_gb=20.0),
            gpu=GPUInfo(detected=True, name="Test GPU", vram_total_gb=8.0, vram_free_gb=7.0, backend="CUDA"),
            ai_capability="EXCELLENT",
        )
        engine = ModelCompatibilityEngine(hw=mock_hw)
        rep = engine.evaluate({"name": "qwen2.5-coder:1.5b", "params": "1.5B", "size_gb": 1.0, "context": 8192})
        assert rep.tier in (ModelCompatibilityEngine.TIER_EXCELLENT, ModelCompatibilityEngine.TIER_RECOMMENDED)
        assert rep.ram_offload_gb <= 0.05
        assert rep.estimated_tps >= 25.0

    def test_massive_model_exceeding_ram_is_not_recommended(self):
        mock_hw = HardwareProfile(
            cpu=CPUInfo(logical_cores=8),
            ram=RAMInfo(total_gb=16.0, available_gb=8.0),
            gpu=GPUInfo(detected=False),
            ai_capability="LIMITED",
        )
        engine = ModelCompatibilityEngine(hw=mock_hw)
        rep = engine.evaluate({"name": "deepseek-v3:671b", "params": "671B", "size_gb": 400.0, "context": 32768})
        assert rep.tier == ModelCompatibilityEngine.TIER_NOT_RECOMMENDED
        assert rep.tier_label_ascii == "[NOT RECOMMENDED]"

    def test_recommend_models_categorization(self):
        engine = ModelCompatibilityEngine()
        models = catalog.all_models(include_dynamic=True)
        recs = engine.recommend_models(models)
        assert "best_coding" in recs
        assert "best_reasoning" in recs
        assert "best_fast" in recs
        assert len(recs["best_coding"]) > 0
        assert len(recs["best_fast"]) > 0


class TestBenchmarkSystem:
    def test_scores_have_transparent_attribution(self):
        scores = CATBenchmarkSystem.load_all_scores()
        assert len(scores) >= 5
        valid_sources = {
            BenchmarkSource.CAT_MEASURED,
            BenchmarkSource.PROVIDER_REPORTED,
            BenchmarkSource.THIRD_PARTY,
            BenchmarkSource.COMMUNITY,
        }
        for s in scores.values():
            assert s.source in valid_sources
            assert s.overall > 0
            assert s.coding > 0

    def test_leaderboard_formatting(self):
        bench = CATBenchmarkSystem()
        table = bench.format_leaderboard()
        assert "CAT MODEL BENCHMARK RANKING" in table
        assert "Attribution Note" in table
        assert "Claude" in table or "GPT" in table or "Gemini" in table or "Llama" in table


class TestOllamaCatalog:
    def test_no_synthetic_padded_variants(self):
        models = catalog.all_models(include_dynamic=False)
        for m in models:
            assert "-variant" not in m["name"], f"Synthetic variant found: {m['name']}"

    def test_categories_filtering(self):
        cats = catalog.categories()
        assert "all" in cats
        assert "coding" in cats
        assert "reasoning" in cats
        coding_models = catalog.search_models(category="coding")
        assert len(coding_models) >= 10
        assert any("coder" in m["name"].lower() for m in coding_models)

    def test_dynamic_registration(self):
        catalog.register_custom_model({
            "name": "custom-researcher:7b",
            "params": "7B",
            "size_gb": 4.5,
            "family": "custom",
            "desc": "Custom test model",
        })
        m = catalog.get_model("custom-researcher:7b")
        assert m is not None
        assert m["name"] == "custom-researcher:7b"


class TestSmartModelRouter:
    def test_never_cloud_filters_cloud_providers(self):
        chain = router.build_candidate_chain(task_types={"coding"}, policy=router.POLICY_NEVER_CLOUD)
        for cand in chain:
            assert cand["provider"].lower() in ("ollama", "local", "vllm")

    def test_local_first_prioritizes_local(self):
        chain = router.build_candidate_chain(task_types={"simple_chat"}, policy=router.POLICY_LOCAL_FIRST)
        if any(c["provider"] == "ollama" for c in chain) and any(c["provider"] != "ollama" for c in chain):
            first_provider = chain[0]["provider"]
            assert first_provider in ("ollama", "local", "vllm")

    def test_route_stamps_privacy_policy(self):
        dec = router.route("solve this integral equation: integral of x^2 dx")
        assert hasattr(dec, "privacy_policy")
        assert dec.privacy_policy in router.POLICIES
        desc = router.describe_decision(dec)
        assert "Router:" in desc or "[Router]" in desc


class TestPermissions:
    def test_delete_files_and_browser_automation_present(self):
        keys = [k for k, _, _ in PERMISSION_DEFS]
        assert "delete_files" in keys
        assert "browser_automation" in keys
        assert "delete_files" in MUTATING_KEYS
        assert "browser_automation" in MUTATING_KEYS

    def test_permission_manager_initial_state(self):
        pm = PermissionManager()
        items = {k: v for k, _, v in pm.snapshot()}
        assert "delete_files" in items
        assert "browser_automation" in items
        assert items["delete_files"] is False  # False by default for safety
        assert items["browser_automation"] is False


class TestCLIModelUX:
    def test_cli_models_help(self, capsys):
        code = _models_cli(["models", "--help"])
        assert code == 0
        captured = capsys.readouterr()
        assert "cat models" in captured.out
        assert "recommend" in captured.out
        assert "benchmark" in captured.out

    def test_cli_models_recommend(self, capsys):
        code = _models_cli(["models", "recommend"])
        assert code == 0
        captured = capsys.readouterr()
        assert "HARDWARE ANALYZER" in captured.out
        assert "Recommended for Coding" in captured.out

    def test_cli_models_search(self, capsys):
        code = _models_cli(["models", "search", "qwen"])
        assert code == 0
        captured = capsys.readouterr()
        assert "CAT Model Search" in captured.out
        assert "qwen" in captured.out.lower()
