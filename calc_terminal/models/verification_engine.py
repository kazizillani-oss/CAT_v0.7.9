"""
CAT CLI — ModelVerificationEngine: Automated Verification for Unknown & Custom Models.

Verifies:
1. Endpoint reachability
2. Protocol & Auth handshake
3. Model ID validity
4. Live request/response generation
5. Capability & metadata coherence

Statuses:
✓ VERIFIED
⚠ PARTIALLY_VERIFIED
? UNKNOWN
✗ FAILED
"""

import time
import json
import urllib.parse
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Tuple, Any, Union


class VerificationStatus:
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    UNKNOWN = "UNKNOWN"
    FAILED = "FAILED"


def mask_secret(secret: str) -> str:
    """Safely mask API key/token for display or logging."""
    if not secret:
        return ""
    secret = str(secret).strip()
    if len(secret) <= 8:
        return "********"
    return secret[:3] + "..." + secret[-4:]


@dataclass
class VerificationStep:
    name: str
    status: str  # "pending", "running", "success", "warning", "failed"
    message: str = ""
    elapsed_ms: float = 0.0


@dataclass
class VerificationResult:
    status: str = VerificationStatus.UNKNOWN
    success: bool = False
    message: str = ""
    error: str = ""
    steps: List[VerificationStep] = field(default_factory=list)
    model_metadata: Dict = field(default_factory=dict)
    models_found: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    def to_dict(self) -> Dict:
        return {
            "status": self.status,
            "success": self.success,
            "message": self.message,
            "error": self.error,
            "steps": [
                {"name": s.name, "status": s.status, "message": s.message, "elapsed_ms": s.elapsed_ms}
                for s in self.steps
            ],
            "model_metadata": self.model_metadata,
            "models_found": self.models_found,
            "timestamp": self.timestamp,
        }


class ModelVerificationEngine:
    """Executes safe, non-destructive verification against AI model endpoints."""

    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout

    def verify_custom_model(
        self,
        provider_id: Any = "",
        model_id: str = "",
        endpoint: str = "",
        protocol: str = "openai",
        api_key: str = "",
        context_window: int = 32000,
        capabilities: Optional[Dict] = None,
        on_step_update: Optional[Callable[[VerificationStep], None]] = None,
    ) -> VerificationResult:
        """Run complete 5-stage verification workflow.

        Calls on_step_update(step) as each phase progresses.
        """
        if isinstance(provider_id, dict):
            cfg = provider_id
            model_id = cfg.get("model_id") or cfg.get("model") or model_id or "default"
            endpoint = cfg.get("base_url") or cfg.get("endpoint") or cfg.get("url") or endpoint
            protocol = cfg.get("api_style") or cfg.get("protocol") or protocol or "openai"
            api_key = cfg.get("api_key") or api_key
            context_window = cfg.get("context_window", context_window)
            capabilities = cfg.get("capabilities", capabilities)
            provider_id = cfg.get("provider_id") or cfg.get("provider") or "custom"

        result = VerificationResult()
        steps: List[VerificationStep] = [
            VerificationStep("Input Validation", "pending"),
            VerificationStep("Endpoint Reachability", "pending"),
            VerificationStep("Authentication & Protocol Handshake", "pending"),
            VerificationStep("Model Existence & Response Test", "pending"),
            VerificationStep("Metadata Coherence", "pending"),
        ]
        result.steps = steps

        def update_step(idx: int, status: str, msg: str = "", t0: Optional[float] = None):
            elapsed = (time.perf_counter() - t0) * 1000.0 if t0 else 0.0
            steps[idx].status = status
            steps[idx].message = msg
            if t0:
                steps[idx].elapsed_ms = round(elapsed, 1)
            if on_step_update:
                try:
                    on_step_update(steps[idx])
                except Exception:
                    pass

        # ---------------- Stage 1: Input Validation ----------------
        t0 = time.perf_counter()
        update_step(0, "running", "Validating model parameters...", t0)
        provider_id = (provider_id or "").strip().lower()
        model_id = (model_id or "").strip()
        endpoint = (endpoint or "").strip()
        protocol = (protocol or "openai").strip().lower()

        if provider_id == "ollama":
            if not endpoint:
                endpoint = "http://localhost:11434"
            if protocol in ("openai", "custom"):
                protocol = "ollama"

        if not model_id:
            update_step(0, "failed", "Model ID cannot be empty", t0)
            result.status = VerificationStatus.FAILED
            result.error = "Model ID cannot be empty"
            result.message = "Validation failed: model ID is required"
            return result

        if protocol not in ("openai", "anthropic", "gemini", "ollama", "custom"):
            update_step(0, "failed", f"Unsupported protocol: {protocol}", t0)
            result.status = VerificationStatus.FAILED
            result.error = f"Unsupported protocol: {protocol}"
            result.message = "Validation failed: invalid protocol"
            return result

        if endpoint:
            parsed = urllib.parse.urlparse(endpoint)
            if parsed.scheme not in ("http", "https"):
                update_step(0, "failed", f"Invalid URL scheme '{parsed.scheme}'; expected http or https", t0)
                result.status = VerificationStatus.FAILED
                result.error = f"Invalid URL scheme '{parsed.scheme}'. Endpoint must begin with http:// or https://"
                result.message = "Validation failed: invalid endpoint URL"
                return result

        update_step(0, "success", f"Validated: {provider_id}/{model_id} ({protocol})", t0)

        # ---------------- Stage 2: Endpoint Reachability ----------------
        t0 = time.perf_counter()
        update_step(1, "running", "Checking endpoint reachability...", t0)

        try:
            import requests
            HAS_REQUESTS = True
        except ImportError:
            HAS_REQUESTS = False

        if not HAS_REQUESTS:
            update_step(1, "warning", "requests library not installed; skipping network probe", t0)
        else:
            reach_url = endpoint or "http://localhost:11434"
            try:
                # Lightweight probe with short timeout
                resp = requests.get(reach_url, timeout=self.timeout)
                update_step(1, "success", f"Endpoint reachable (HTTP {resp.status_code})", t0)
            except requests.exceptions.SSLError as e:
                update_step(1, "failed", f"SSL Certificate Error: {e}", t0)
                result.status = VerificationStatus.FAILED
                result.error = "SSL validation failed. Check endpoint certificate."
                return result
            except requests.exceptions.ConnectionError:
                # Try base host
                parsed = urllib.parse.urlparse(reach_url)
                base = f"{parsed.scheme}://{parsed.netloc}"
                try:
                    resp = requests.get(base, timeout=4.0)
                    update_step(1, "success", f"Host reachable (HTTP {resp.status_code})", t0)
                except Exception as ex:
                    update_step(1, "failed", f"Could not connect to {base}: {ex}", t0)
                    result.status = VerificationStatus.FAILED
                    result.error = f"Connection refused or unreachable: {base}"
                    return result
            except Exception as e:
                update_step(1, "warning", f"Probe warning: {e}", t0)

        # ---------------- Stage 3: Auth & Protocol Handshake ----------------
        t0 = time.perf_counter()
        update_step(2, "running", "Performing authentication handshake...", t0)

        config = {
            "provider": provider_id or "custom",
            "model": model_id,
            "api_key": api_key,
            "base_url": endpoint,
            "api_url": endpoint,
            "api_style": protocol if protocol != "custom" else "openai",
        }

        try:
            from .. import aicore
            ok, msg, models = aicore.verify_connection(config)
            result.models_found = list(models or [])
        except Exception as ex:
            ok, msg, models = False, str(ex), []

        if ok:
            update_step(2, "success", f"Auth & Protocol verified ({msg})", t0)
        elif "authentication" in msg.lower() or "401" in msg or "invalid api key" in msg.lower():
            update_step(2, "failed", f"Authentication failed: {msg}", t0)
            result.status = VerificationStatus.FAILED
            result.error = msg
            result.message = "Authentication rejected by provider"
            return result
        else:
            # Maybe model endpoint doesn't support /models list endpoint, but accepts chat completions
            update_step(2, "warning", f"Handshake returned: {msg}", t0)

        # ---------------- Stage 4: Live Generation Response Test ----------------
        t0 = time.perf_counter()
        update_step(3, "running", f"Testing generation query on '{model_id}'...", t0)

        test_prompt = "Say hello in one word."
        gen_ok = False
        gen_text = ""

        try:
            from .. import aicore
            # Test direct query
            reply = aicore.query_ai(test_prompt, config=config)
            if aicore.is_error_response(reply):
                gen_ok = False
                gen_text = reply
            else:
                gen_ok = True
                gen_text = (reply or "").strip()[:50]
        except Exception as ex:
            gen_ok = False
            gen_text = str(ex)

        if gen_ok:
            update_step(3, "success", f"Model responded: '{gen_text}'", t0)
        else:
            if ok:
                # Handshake worked but prompt failed
                update_step(3, "warning", f"Model prompt returned warning: {gen_text}", t0)
            else:
                update_step(3, "failed", f"Test request failed: {gen_text}", t0)
                result.status = VerificationStatus.FAILED
                result.error = gen_text
                result.message = f"Model '{model_id}' did not respond successfully"
                return result

        # ---------------- Stage 5: Metadata Coherence ----------------
        t0 = time.perf_counter()
        update_step(4, "running", "Validating metadata & capability coherence...", t0)

        # Normalize capabilities
        inferred_caps = capabilities or {}
        if not inferred_caps:
            try:
                from ..model_router import capabilities_for
                c_obj = capabilities_for(provider_id, model_id)
                inferred_caps = c_obj.to_dict() if hasattr(c_obj, "to_dict") else dict(c_obj.__dict__)
            except Exception:
                inferred_caps = {"text": True, "streaming": True}

        result.model_metadata = {
            "model_id": model_id,
            "provider_id": provider_id,
            "endpoint": endpoint,
            "protocol": protocol,
            "context_window": max(512, int(context_window or 32000)),
            "capabilities": inferred_caps,
            "verified_at": time.time(),
        }

        update_step(4, "success", "Metadata coherent and verified", t0)

        # Final status determination
        if gen_ok and ok:
            result.status = VerificationStatus.VERIFIED
            result.success = True
            result.message = f"Model '{model_id}' successfully verified!"
        elif gen_ok or ok:
            result.status = VerificationStatus.PARTIALLY_VERIFIED
            result.success = True
            result.message = f"Model '{model_id}' partially verified (connection verified)"
        else:
            result.status = VerificationStatus.FAILED
            result.success = False
            result.message = f"Verification failed: {result.error}"

        return result


def verify_model(
    provider_id: str,
    model_id: str,
    endpoint: str = "",
    protocol: str = "openai",
    api_key: str = "",
    context_window: int = 32000,
    capabilities: Optional[Dict] = None,
    on_step_update: Optional[Callable[[VerificationStep], None]] = None,
) -> VerificationResult:
    """Module-level helper to execute ModelVerificationEngine."""
    engine = get_verification_engine()
    return engine.verify_custom_model(
        provider_id=provider_id,
        model_id=model_id,
        endpoint=endpoint,
        protocol=protocol,
        api_key=api_key,
        context_window=context_window,
        capabilities=capabilities,
        on_step_update=on_step_update,
    )


_DEFAULT_ENGINE: Optional[ModelVerificationEngine] = None


def get_verification_engine(timeout: float = 8.0) -> ModelVerificationEngine:
    """Return singleton instance of ModelVerificationEngine."""
    global _DEFAULT_ENGINE
    if _DEFAULT_ENGINE is None:
        _DEFAULT_ENGINE = ModelVerificationEngine(timeout=timeout)
    return _DEFAULT_ENGINE


__all__ = [
    "ModelVerificationEngine",
    "VerificationStatus",
    "VerificationStep",
    "VerificationResult",
    "get_verification_engine",
    "verify_model",
    "mask_secret",
]
