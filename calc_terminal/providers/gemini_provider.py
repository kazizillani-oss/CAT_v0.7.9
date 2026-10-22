"""Google Gemini provider."""

import json
import time
from typing import Optional

import requests

from .base_provider import BaseProvider


class GeminiProvider(BaseProvider):
    ID = "gemini"
    NAME = "Google Gemini"
    NEEDS_KEY = True
    DEFAULT_MODEL = "gemini-1.5-flash-latest"  # fallback only — resolved from providers.json when available
    API_STYLE = "gemini"
    supports_tools = True
    supports_reasoning = True
    supports_vision = True
    supports_streaming = True
    supports_audio = True
    supports_embeddings = True

    @classmethod
    def _default_url(cls):
        return "https://generativelanguage.googleapis.com/v1beta"

    @classmethod
    def default_model(cls):
        """Data-driven default from providers.json; DEFAULT_MODEL as fallback."""
        from ..models import manager as _mgr
        return _mgr.default_model_for(cls.ID, cls.DEFAULT_MODEL)

    def _key_suffix(self):
        return f"?key={self.get_api_key()}"

    def _build_contents(self, history, prompt):
        contents = []
        for role, text in (history or []):
            r = "model" if role == "assistant" else "user"
            contents.append({"role": r, "parts": [{"text": text}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        return contents

    def fetch_models(self) -> list[str]:
        base = self.get_base_url()
        key = self.get_api_key()
        if not base or not key:
            return []
        try:
            resp = requests.get(f"{base}/models{self._key_suffix()}", timeout=10)
            if resp.status_code >= 400:
                return []
            out = []
            for m in resp.json().get("models", []):
                methods = m.get("supportedGenerationMethods", [])
                if not methods or "generateContent" in methods:
                    out.append(m.get("name", "").split("/")[-1])
            return sorted(set(n for n in out if n))
        except Exception:
            return []

    def connect(self) -> tuple[bool, str, list[str]]:
        models = self.fetch_models()
        if models:
            return True, f"Connected \u2014 {len(models)} model(s) visible", models
        return False, "Could not connect \u2014 check API key", []

    def chat(self, prompt, system_prompt="", history=None) -> str:
        base = self.get_base_url()
        if not base:
            return "AI not configured."
        model = self.get_model()
        try:
            url = f"{base}/models/{model}:generateContent{self._key_suffix()}"
            payload = {
                "contents": self._build_contents(history, prompt),
                "systemInstruction": {"parts": [{"text": system_prompt or ""}]},
            }
            temp = self.config.get("temperature")
            top_p = self.config.get("top_p")
            if temp is not None or top_p is not None:
                gen = {}
                if temp is not None:
                    gen["temperature"] = temp
                if top_p is not None:
                    gen["topP"] = top_p
                payload["generationConfig"] = gen
            resp = requests.post(url, json=payload, timeout=30)
            self._raise_for_status(resp)
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            return f"Error: {e}"

    def stream(self, prompt, system_prompt="", history=None):
        base = self.get_base_url()
        if not base:
            yield "AI not configured."
            return
        model = self.get_model()
        try:
            url = (f"{base}/models/{model}:streamGenerateContent"
                   f"?alt=sse{self._key_suffix()}")
            payload = {
                "contents": self._build_contents(history, prompt),
                "systemInstruction": {"parts": [{"text": system_prompt or ""}]},
            }
            temp = self.config.get("temperature")
            top_p = self.config.get("top_p")
            if temp is not None or top_p is not None:
                gen = {}
                if temp is not None:
                    gen["temperature"] = temp
                if top_p is not None:
                    gen["topP"] = top_p
                payload["generationConfig"] = gen
            resp = requests.post(url, json=payload, timeout=60, stream=True)
            self._raise_for_status(resp)
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                try:
                    obj = json.loads(line[5:].strip())
                except ValueError:
                    continue
                candidates = obj.get("candidates") or []
                if candidates:
                    parts = (candidates[0].get("content") or {}).get("parts") or []
                    for part in parts:
                        piece = part.get("text")
                        if piece:
                            yield piece
        except Exception as e:
            yield f"Error: {e}"

    def vision(self, prompt, image_b64, mime) -> str:
        base = self.get_base_url()
        if not base:
            return "AI not configured."
        model = self.get_model()
        try:
            url = f"{base}/models/{model}:generateContent{self._key_suffix()}"
            payload = {
                "contents": [{"role": "user", "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime, "data": image_b64}},
                ]}],
            }
            resp = requests.post(url, json=payload, timeout=60)
            self._raise_for_status(resp)
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            return f"Vision error: {e}"

    def health_check(self) -> dict:
        start = time.time()
        models = self.fetch_models()
        elapsed = time.time() - start
        return {
            "provider": self.ID,
            "status": "ok" if models else "error",
            "latency_ms": round(elapsed * 1000),
            "models_count": len(models),
            "base_url": self.get_base_url(),
        }

    @staticmethod
    def _raise_for_status(resp):
        if resp.status_code >= 400:
            try:
                body = resp.json()
                err = (body.get("error", {}).get("message")
                       or str(body)[:300])
            except Exception:
                err = resp.text[:300] if resp.text else resp.reason
            raise RuntimeError(f"HTTP {resp.status_code}: {err}")
