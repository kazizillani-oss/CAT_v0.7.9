"""OpenAI-compatible provider — works with OpenAI, Groq, OpenRouter,
DeepSeek, Together AI, Perplexity, and any other /v1 endpoint."""

import json
import time
from typing import Optional

import requests

from .base_provider import BaseProvider


class OpenAIProvider(BaseProvider):
    ID = "openai"
    NAME = "OpenAI"
    NEEDS_KEY = True
    DEFAULT_MODEL = "gpt-4o-mini"  # fallback only — resolved from providers.json when available
    API_STYLE = "openai"
    supports_tools = True
    supports_reasoning = True
    supports_vision = True
    supports_audio = True
    supports_images = True
    supports_embeddings = True
    supports_streaming = True

    @classmethod
    def _default_url(cls):
        return "https://api.openai.com/v1"

    @classmethod
    def default_model(cls):
        """Data-driven default from providers.json; DEFAULT_MODEL as fallback."""
        from ..models import manager as _mgr
        return _mgr.default_model_for(cls.ID, cls.DEFAULT_MODEL)

    def _headers(self):
        h = {"Content-Type": "application/json"}
        key = self.get_api_key()
        if key:
            h["Authorization"] = f"Bearer {key}"
        h.update(self.get_extra_headers())
        return h

    def _build_messages(self, system_prompt, history, prompt):
        messages = [{"role": "system", "content": system_prompt}] if system_prompt else []
        for role, text in (history or []):
            messages.append({"role": role, "content": text})
        messages.append({"role": "user", "content": prompt})
        return messages

    def fetch_models(self) -> list[str]:
        return self._fetch_models_paginated()

    def fetch_models_paginated(self, cancel_event=None) -> list[str]:
        return self._fetch_models_paginated(cancel_event)

    def _fetch_models_paginated(self, cancel_event=None) -> list[str]:
        base = self.get_base_url()
        if not base:
            return []
        all_models = []
        after = None
        limit = 100
        try:
            while True:
                if cancel_event and cancel_event.is_set():
                    return all_models or []
                url = f"{base}/models"
                params = {"limit": limit}
                if after:
                    params["after"] = after
                resp = requests.get(url, headers=self._headers(),
                                    params=params, timeout=10)
                if resp.status_code >= 400:
                    return all_models or []
                data = resp.json()
                items = data.get("data", [])
                for m in items:
                    if isinstance(m, dict) and m.get("id"):
                        all_models.append(m["id"])
                # Check for pagination
                if "has_more" in data:
                    if not data.get("has_more"):
                        break
                after = None
                if items:
                    after = items[-1].get("id")
                if not after:
                    break
            return sorted(set(all_models))
        except Exception:
            return all_models or []

    def connect(self) -> tuple[bool, str, list[str]]:
        models = self.fetch_models()
        if models:
            return True, f"Connected \u2014 {len(models)} model(s) visible", models
        base = self.get_base_url()
        if not base:
            return False, "No base URL configured", []
        try:
            resp = requests.get(f"{base}/models", headers=self._headers(), timeout=8)
            if resp.status_code == 401:
                return False, "Invalid or missing API key (HTTP 401)", []
            if resp.status_code == 403:
                return False, "Access forbidden (HTTP 403)", []
            if resp.status_code >= 400:
                return False, f"Server returned HTTP {resp.status_code}", []
            return True, f"Connected to {base}", []
        except requests.exceptions.ConnectionError:
            return False, f"Cannot reach {base} \u2014 check URL or internet", []
        except requests.exceptions.Timeout:
            return False, "Connection timed out", []
        except Exception as e:
            return False, f"Connection failed: {e}", []

    def chat(self, prompt, system_prompt="", history=None) -> str:
        base = self.get_base_url()
        if not base:
            return "AI not configured \u2014 no base URL set."
        try:
            payload = {
                "model": self.get_model(),
                "messages": self._build_messages(system_prompt, history, prompt),
            }
            temp = self.config.get("temperature")
            if temp is not None:
                payload["temperature"] = temp
            top_p = self.config.get("top_p")
            if top_p is not None:
                payload["top_p"] = top_p
            resp = requests.post(f"{base}/chat/completions",
                                 headers=self._headers(), json=payload, timeout=30)
            self._raise_for_status(resp)
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.ConnectionError:
            return "Could not reach the AI server."
        except requests.exceptions.Timeout:
            return "The AI request timed out."
        except Exception as e:
            return f"Error: {e}"

    def stream(self, prompt, system_prompt="", history=None):
        base = self.get_base_url()
        if not base:
            yield "AI not configured \u2014 no base URL set."
            return
        try:
            payload = {
                "model": self.get_model(),
                "messages": self._build_messages(system_prompt, history, prompt),
                "stream": True,
            }
            temp = self.config.get("temperature")
            if temp is not None:
                payload["temperature"] = temp
            top_p = self.config.get("top_p")
            if top_p is not None:
                payload["top_p"] = top_p
            resp = requests.post(f"{base}/chat/completions",
                                 headers=self._headers(), json=payload,
                                 timeout=60, stream=True)
            self._raise_for_status(resp)
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    obj = json.loads(data_str)
                except ValueError:
                    continue
                choices = obj.get("choices") or []
                if choices:
                    piece = (choices[0].get("delta") or {}).get("content")
                    if piece:
                        yield piece
        except requests.exceptions.ConnectionError:
            yield "Could not reach the AI server."
        except requests.exceptions.Timeout:
            yield "The AI request timed out."
        except Exception as e:
            yield f"Error: {e}"

    def vision(self, prompt, image_b64, mime) -> str:
        base = self.get_base_url()
        if not base:
            return "AI not configured."
        try:
            payload = {
                "model": self.get_model(),
                "messages": [
                    {"role": "system",
                     "content": ("You are CAT AI. Describe and analyze "
                                 "the attached image precisely.")},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url",
                         "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                    ]},
                ],
            }
            resp = requests.post(f"{base}/chat/completions",
                                 headers=self._headers(), json=payload, timeout=60)
            self._raise_for_status(resp)
            return resp.json()["choices"][0]["message"]["content"]
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
                       or body.get("error", {}).get("status")
                       or str(body)[:300])
            except Exception:
                err = resp.text[:300] if resp.text else resp.reason
            raise RuntimeError(f"HTTP {resp.status_code}: {err}")


class CustomOpenAIProvider(OpenAIProvider):
    """For user-defined OpenAI-compatible endpoints."""

    ID = "custom_openai"
    NAME = "OpenAI Compatible"
    NEEDS_KEY = True
    DEFAULT_MODEL = ""
    API_STYLE = "openai"
    supports_tools = True
    supports_vision = True
    supports_streaming = True
    supports_embeddings = True
    supports_reasoning = False  # depends on backend

    @classmethod
    def _default_url(cls):
        return "https://api.openai.com/v1"
