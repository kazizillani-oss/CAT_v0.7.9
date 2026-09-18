"""Anthropic Messages API provider."""

import json
import time
from typing import Optional

import requests

from .base_provider import BaseProvider


class AnthropicProvider(BaseProvider):
    ID = "anthropic"
    NAME = "Anthropic (Claude)"
    NEEDS_KEY = True
    DEFAULT_MODEL = "claude-3-5-sonnet-20240620"  # fallback only — resolved from providers.json when available
    API_STYLE = "anthropic"
    supports_tools = True
    supports_reasoning = True
    supports_vision = True
    supports_streaming = True

    @classmethod
    def _default_url(cls):
        return "https://api.anthropic.com/v1"

    @classmethod
    def default_model(cls):
        """Data-driven default from providers.json; DEFAULT_MODEL as fallback."""
        from ..models import manager as _mgr
        return _mgr.default_model_for(cls.ID, cls.DEFAULT_MODEL)

    def _headers(self):
        return {
            "x-api-key": self.get_api_key(),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _build_messages(self, history, prompt):
        messages = [{"role": role, "content": text} for role, text in (history or [])]
        messages.append({"role": "user", "content": prompt})
        return messages

    def fetch_models(self) -> list[str]:
        return []

    def connect(self) -> tuple[bool, str, list[str]]:
        base = self.get_base_url()
        if not base:
            return False, "No base URL configured", []
        try:
            resp = requests.get(f"{base}/models", headers=self._headers(), timeout=8)
            if resp.status_code >= 400 and resp.status_code != 404:
                if resp.status_code == 401:
                    return False, "Invalid API key (HTTP 401)", []
                if resp.status_code == 403:
                    return False, "Access forbidden (HTTP 403)", []
                return False, f"HTTP {resp.status_code}", []
            return True, f"Connected to {base}", []
        except requests.exceptions.ConnectionError:
            return False, f"Cannot reach {base}", []
        except requests.exceptions.Timeout:
            return False, "Connection timed out", []
        except Exception as e:
            return False, f"Connection failed: {e}"

    def chat(self, prompt, system_prompt="", history=None) -> str:
        base = self.get_base_url()
        if not base:
            return "AI not configured."
        try:
            payload = {
                "model": self.get_model(),
                "max_tokens": 1024,
                "system": system_prompt or "",
                "messages": self._build_messages(history, prompt),
            }
            temp = self.config.get("temperature")
            if temp is not None:
                payload["temperature"] = temp
            top_p = self.config.get("top_p")
            if top_p is not None:
                payload["top_p"] = top_p
            resp = requests.post(f"{base}/messages", headers=self._headers(),
                                 json=payload, timeout=30)
            self._raise_for_status(resp)
            return resp.json()["content"][0]["text"]
        except Exception as e:
            return f"Error: {e}"

    def stream(self, prompt, system_prompt="", history=None):
        base = self.get_base_url()
        if not base:
            yield "AI not configured."
            return
        try:
            payload = {
                "model": self.get_model(),
                "max_tokens": 1024,
                "system": system_prompt or "",
                "messages": self._build_messages(history, prompt),
                "stream": True,
            }
            temp = self.config.get("temperature")
            if temp is not None:
                payload["temperature"] = temp
            top_p = self.config.get("top_p")
            if top_p is not None:
                payload["top_p"] = top_p
            resp = requests.post(f"{base}/messages", headers=self._headers(),
                                 json=payload, timeout=60, stream=True)
            self._raise_for_status(resp)
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                try:
                    obj = json.loads(line[5:].strip())
                except ValueError:
                    continue
                if obj.get("type") == "content_block_delta":
                    piece = (obj.get("delta") or {}).get("text")
                    if piece:
                        yield piece
        except Exception as e:
            yield f"Error: {e}"

    def vision(self, prompt, image_b64, mime) -> str:
        base = self.get_base_url()
        if not base:
            return "AI not configured."
        try:
            payload = {
                "model": self.get_model(),
                "max_tokens": 1024,
                "system": ("You are CAT AI. Describe and analyze "
                           "the attached image precisely."),
                "messages": [{"role": "user", "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": mime, "data": image_b64}},
                    {"type": "text", "text": prompt},
                ]}],
            }
            resp = requests.post(f"{base}/messages", headers=self._headers(),
                                 json=payload, timeout=60)
            self._raise_for_status(resp)
            return resp.json()["content"][0]["text"]
        except Exception as e:
            return f"Vision error: {e}"

    def health_check(self) -> dict:
        start = time.time()
        ok, msg, models = self.connect()
        elapsed = time.time() - start
        return {
            "provider": self.ID,
            "status": "ok" if ok else "error",
            "latency_ms": round(elapsed * 1000),
            "message": msg,
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
