"""
Unit & Integration Tests for CAT Backup Provider & Resilience System
Author: Kazi Zillani

Validates:
- Primary success & error classification
- Transient retry vs immediate failover on rate limits & auth errors
- Tier 1 model fallback on same provider
- Tier 2 cross-provider failover
- Intelligent capability matching (vision, tools, context)
- Unlimited backup pool reordering & persistence
- Zero-config native Ollama local fallback
- Privacy policy (never_cloud) overriding cloud failovers
- Cost policy (free_only) skipping paid providers
- Circuit breaker state machine & cooldowns
- Agent task state preservation across mid-task failovers
- Emergency offline mode (cat offline)
- Zero credential leakage
"""

import json
import os
import time
import pytest

from calc_terminal.resilience.types import (
    FailureType,
    SecurityLevel,
    CostPolicy,
    TaskRequirements,
    ProviderHealthState,
    CandidateTarget,
)
from calc_terminal.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerState
from calc_terminal.resilience.health_monitor import (
    HealthMonitor,
    sanitize_error,
)
from calc_terminal.resilience.capability_matcher import CapabilityMatcher
from calc_terminal.resilience.failover_engine import FailoverEngine
from calc_terminal.resilience.agent_state import AgentTaskState
from calc_terminal.resilience.ollama_adapter import OllamaAdapter
from calc_terminal.resilience.orchestrator import AIOrchestrator
from calc_terminal.providers import provider_manager as pm
from calc_terminal import aicore


class TestCredentialSanitization:
    def test_sanitize_error_strips_openai_and_groq_keys(self):
        raw = "Error 401: Unauthorized for sk-1234567890abcdef1234567890abcdef and gsk_998877665544332211"
        cleaned = sanitize_error(raw)
        assert "sk-1234567890" not in cleaned
        assert "gsk_99887766" not in cleaned
        assert "[CREDENTIAL_REDACTED]" in cleaned

    def test_sanitize_error_strips_auth_headers(self):
        raw = "Request failed with Authorization: Bearer secret_token_xyz12345678"
        cleaned = sanitize_error(raw)
        assert "secret_token_xyz12345678" not in cleaned
        assert "[REDACTED]" in cleaned


class TestCircuitBreaker:
    def test_circuit_breaker_trips_and_recovers(self):
        cb = CircuitBreaker(failure_threshold=2, default_cooldown=0.1)
        endpoint = ("test_prov", "test_model")

        assert cb.can_attempt(*endpoint) is True
        assert cb.get_state(*endpoint) == CircuitBreakerState.CLOSED

        # 1st failure -> still closed
        cb.record_failure(*endpoint, error="Timeout 1")
        assert cb.can_attempt(*endpoint) is True
        assert cb.get_state(*endpoint) == CircuitBreakerState.CLOSED

        # 2nd failure -> trips to OPEN
        cb.record_failure(*endpoint, error="Timeout 2")
        assert cb.can_attempt(*endpoint) is False
        assert cb.get_state(*endpoint) == CircuitBreakerState.OPEN

        # Wait for cooldown
        time.sleep(0.12)

        # In half-open state, probe is allowed
        assert cb.can_attempt(*endpoint) is True
        assert cb.get_state(*endpoint) == CircuitBreakerState.HALF_OPEN

        # Probe success resets breaker
        cb.record_success(*endpoint, latency_ms=150)
        assert cb.can_attempt(*endpoint) is True
        assert cb.get_state(*endpoint) == CircuitBreakerState.CLOSED

    def test_circuit_breaker_rate_limit_immediate_cooldown(self):
        cb = CircuitBreaker(failure_threshold=5, rate_limit_cooldown=0.2)
        endpoint = ("groq", "llama-3.3-70b")

        cb.record_failure(*endpoint, error="429 Rate limit reached", is_rate_limit=True)
        assert cb.can_attempt(*endpoint) is False
        assert cb.get_state(*endpoint) == CircuitBreakerState.OPEN


class TestHealthMonitor:
    def test_health_monitor_recording_and_status(self):
        hm = HealthMonitor()
        hm.record_turn_start("groq", "llama3")
        hm.record_success("groq", "llama3", latency_ms=450.0)

        st = hm.get_health("groq", "llama3")
        assert st.status == "healthy"
        assert st.consecutive_failures == 0
        assert st.latency_ms == 450.0

        glyph, label = hm.get_status_badge("groq", "llama3")
        assert glyph == "🟢"
        assert label == "Healthy"

    def test_health_monitor_slow_and_failure(self):
        hm = HealthMonitor()
        hm.record_success("cerebras", "llama3", latency_ms=4200.0)
        st = hm.get_health("cerebras", "llama3")
        assert st.status == "slow"
        glyph, label = hm.get_status_badge("cerebras", "llama3")
        assert glyph == "🟡"
        assert label == "Slow"


class TestFailoverEngineClassification:
    def test_failure_classification(self):
        fe = FailoverEngine()

        assert fe.classify_failure("Rate limit reached for requests per minute (429)") == FailureType.RATE_LIMIT
        assert fe.classify_failure("401 Unauthorized: Invalid API key") == FailureType.AUTH_FAILURE
        assert fe.classify_failure("Connection timed out after 30s") == FailureType.TRANSIENT
        assert fe.classify_failure("Model not found in provider registry") == FailureType.MODEL_UNAVAILABLE
        assert fe.classify_failure("The prompt exceeds maximum context length") == FailureType.CONTEXT_TOO_LARGE
        assert fe.classify_failure("503 Service Unavailable") == FailureType.TRANSIENT

    def test_retryable_classification(self):
        fe = FailoverEngine()
        assert fe.is_retryable(FailureType.TRANSIENT) is True
        assert fe.is_retryable(FailureType.TIMEOUT) is True
        assert fe.is_retryable(FailureType.RATE_LIMIT) is False
        assert fe.is_retryable(FailureType.AUTH_FAILURE) is False


class TestCapabilityMatching:
    def test_vision_filtering(self):
        cm = CapabilityMatcher()
        req_vision = TaskRequirements(vision=True)

        # Config without vision
        text_cfg = {"provider": "groq", "model": "llama-3.1-8b-instant", "api_key": "dummy"}
        target = cm.evaluate_target(text_cfg, req_vision)
        assert target is None

        # Config with vision
        vision_cfg = {"provider": "openai", "model": "gpt-4o", "api_key": "dummy"}
        target_v = cm.evaluate_target(vision_cfg, req_vision)
        assert target_v is not None
        assert target_v.provider == "openai"

    def test_tools_filtering_skips_base_models(self):
        cm = CapabilityMatcher()
        req_tools = TaskRequirements(tools=True)

        # Non-instruct base model
        base_cfg = {"provider": "ollama", "model": "llama3:base", "api_key": ""}
        assert cm.evaluate_target(base_cfg, req_tools) is None

        # Instruct model
        instruct_cfg = {"provider": "ollama", "model": "qwen2.5-coder:7b", "api_key": ""}
        assert cm.evaluate_target(instruct_cfg, req_tools) is not None

    def test_privacy_policy_never_cloud_enforcement(self):
        cm = CapabilityMatcher()
        req = TaskRequirements()

        cloud_cfg = {"provider": "groq", "model": "llama-3.3-70b", "api_key": "gsk_test"}
        local_cfg = {"provider": "ollama", "model": "qwen2.5-coder:7b", "api_key": ""}

        # under never_cloud
        assert cm.evaluate_target(cloud_cfg, req, privacy_policy="never_cloud") is None
        assert cm.evaluate_target(local_cfg, req, privacy_policy="never_cloud") is not None

    def test_cost_policy_free_only(self):
        cm = CapabilityMatcher()
        req = TaskRequirements()

        paid_cfg = {"provider": "anthropic", "model": "claude-3-opus", "api_key": "sk-ant"}
        free_cfg = {"provider": "ollama", "model": "llama3.3", "api_key": ""}

        assert cm.evaluate_target(paid_cfg, req, cost_policy=CostPolicy.FREE_ONLY) is None
        assert cm.evaluate_target(free_cfg, req, cost_policy=CostPolicy.FREE_ONLY) is not None


class TestBackupPoolManagement:
    def test_unlimited_backup_providers_crud_and_reorder(self, monkeypatch, tmp_path):
        tmp_file = str(tmp_path / "test_backups.json")
        monkeypatch.setattr(pm, "BACKUP_PROVIDERS_FILE", tmp_file)

        initial = [
            {"provider": "groq", "model": "m1", "enabled": True},
            {"provider": "cerebras", "model": "m2", "enabled": True},
            {"provider": "ollama", "model": "m3", "enabled": True},
        ]
        pm.save_backup_providers(initial)

        loaded = pm.load_backup_providers()
        assert len(loaded) == 3
        assert loaded[0]["provider"] == "groq"

        # Add 4th and 5th provider (unlimited dynamic collection)
        pm.add_backup_provider({"provider": "openrouter", "model": "m4", "enabled": True})
        pm.add_backup_provider({"provider": "deepseek", "model": "m5", "enabled": True})
        loaded = pm.load_backup_providers()
        assert len(loaded) == 5
        assert loaded[4]["provider"] == "deepseek"

        # Reorder: move deepseek (index 4) to front (index 0)
        pm.reorder_backup_provider(4, 0)
        loaded = pm.load_backup_providers()
        assert loaded[0]["provider"] == "deepseek"
        assert loaded[1]["provider"] == "groq"

        # Disable groq
        pm.set_backup_provider_enabled("groq", False)
        loaded = pm.load_backup_providers()
        assert loaded[1]["enabled"] is False

        # Remove cerebras
        pm.remove_backup_provider("cerebras")
        loaded = pm.load_backup_providers()
        assert not any(p["provider"] == "cerebras" for p in loaded)
        assert len(loaded) == 4


class TestNativeOllamaAdapter:
    def test_ollama_adapter_zero_config_and_discovery(self, monkeypatch):
        oa = OllamaAdapter()

        class MockResp:
            status_code = 200
            def json(self):
                return {
                    "models": [
                        {"name": "qwen2.5-coder:7b", "size": 4000000000},
                        {"name": "llama3.3:latest", "size": 8000000000},
                        {"name": "llama3:base", "size": 8000000000},
                    ]
                }

        import requests
        monkeypatch.setattr(requests, "get", lambda *args, **kwargs: MockResp())

        assert oa.is_available() is True
        models = oa.get_model_names()
        assert "qwen2.5-coder:7b" in models
        assert "llama3:base" in models

        # Instruct model selection for coding
        best_coder = oa.select_best_model(coding=True)
        assert best_coder == "qwen2.5-coder:7b"

        # Backup entry construction requires no API key
        entry = oa.build_backup_entry()
        assert entry["api_key"] == ""
        assert entry["provider"] == "ollama"
        assert entry["base_url"] == "http://localhost:11434"


class TestAgentTaskStatePreservation:
    def test_agent_state_decoupled_from_provider(self):
        state = AgentTaskState(task_id="turn-42", objective="Refactor auth module")

        # Record step 1: read file
        state.record_step(
            "read_file",
            {"path": "auth/login.py"},
            "def login(): pass",
            {"path": "auth/login.py"}
        )
        assert "auth/login.py" in state.files_inspected

        # Record step 2: write file
        state.record_step(
            "write_file",
            {"path": "auth/login.py", "reason": "Add JWT verification"},
            "File written successfully",
            {"path": "auth/login.py"}
        )
        assert "auth/login.py" in state.files_modified
        assert state.files_modified["auth/login.py"] == "Add JWT verification"

        # Record step 3: run test
        state.record_step(
            "run_tests",
            {"command": "pytest tests/test_login.py"},
            "1 passed in 0.04s",
            {}
        )
        assert len(state.tests_run) == 1
        assert state.tests_run[0]["passed"] is True

        # Simulate provider failover mid-task
        state.record_failover("gemini", "groq", reason="Gemini rate limited (429)")
        assert len(state.failover_log) == 1
        assert state.active_provider == "groq"

        # Generate continuation context for the backup provider
        ctx = state.format_continuation_context()
        assert "Refactor auth module" in ctx
        assert "auth/login.py (Add JWT verification)" in ctx
        assert "Latest test status: PASSED" in ctx
        assert "Do NOT repeat already completed actions" in ctx


class TestFailoverExecution:
    def test_aicore_failover_targets_with_tier1_and_tier2(self, monkeypatch, tmp_path):
        tmp_file = str(tmp_path / "test_backups.json")
        monkeypatch.setattr(pm, "BACKUP_PROVIDERS_FILE", tmp_file)

        from calc_terminal import model_router
        monkeypatch.setattr(model_router, "get_privacy_policy", lambda: "local_first")

        # Primary provider
        prim_cfg = {"provider": "gemini", "model": "gemini-1.5-pro", "api_key": "dummy_key"}
        # Backups
        pm.save_backup_providers([
            {"provider": "groq", "model": "llama-3.3-70b-versatile", "api_key": "gsk_dummy", "enabled": True},
            {"provider": "ollama", "model": "llama3.3", "api_key": "", "enabled": True},
        ])

        targets = aicore._failover_targets(prim_cfg)
        assert len(targets) >= 2
        provs = [t[0]["provider"] for t in targets]
        assert provs[0] == "gemini"
        assert "groq" in provs[1:]
        assert "ollama" in provs[1:]

    def test_query_ai_failover_when_primary_fails(self, monkeypatch):
        attempts = []

        def mock_query_ai_once(prompt, system_prompt="", history=None, config=None, attachments=None, size_class="normal"):
            prov = config.get("provider")
            attempts.append(prov)
            if prov == "failing_primary":
                return "429: Too Many Requests - Rate limit reached"
            elif prov == "backup_groq":
                return "Hello from Groq backup!"
            return "Unexpected"

        monkeypatch.setattr(aicore, "_query_ai_once", mock_query_ai_once)

        notified = []
        notifications = []
        aicore.set_failover_hook(lambda msg: notifications.append(msg))

        prim = {"provider": "failing_primary", "model": "m1", "api_key": "dummy"}
        targets = [
            (prim, None, False),
            ({"provider": "backup_groq", "model": "m2", "api_key": "dummy"}, None, True),
        ]
        monkeypatch.setattr(aicore, "_failover_targets", lambda *args, **kwargs: targets)

        res = aicore.query_ai("Hello CAT", config=prim)
        assert res == "Hello from Groq backup!"
        assert attempts == ["failing_primary", "backup_groq"]
        assert any("Switching to Backup" in n for n in notifications)


class TestEmergencyOfflineMode:
    def test_emergency_offline_mode_switches_policies(self):
        from calc_terminal import model_router
        orig_pol = model_router.get_privacy_policy()
        try:
            orch = AIOrchestrator()
            ok, msg = orch.enable_emergency_offline_mode()
            assert orch.get_privacy_policy() == "never_cloud"
            assert orch.cost_policy == CostPolicy.LOCAL_ONLY
            assert "Offline Local Mode active" in msg
        finally:
            model_router.set_privacy_policy(orig_pol)
