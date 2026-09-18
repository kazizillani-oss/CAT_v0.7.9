"""
calc_terminal/providers/adapters/chinese_adapters.py
===================================================
First-Class Adapters for Major Chinese AI Providers:
  - DeepSeek (V3, R1 Reasoner)
  - Alibaba Cloud / Qwen (Max, Plus, Turbo, Coder, QwQ)
  - Moonshot AI (Kimi K3, K2, moonshot-v1)
  - Z.AI / Zhipu (GLM-5.1, GLM-5.2, GLM-5.3, GLM-4)
  - MiniMax (H3, abab6.5s)
  - Tencent (Hunyuan / Hy3)
  - ByteDance (Doubao / Seed)
  - Xiaomi (MiMo)
  - Baidu (ERNIE 4.0 / Qianfan)
"""

import requests
from typing import List, Dict, Any, Optional

from .base import BaseProviderAdapter
from ...models.schema import ModelInfo, AVAILABILITY_PAID_API, AVAILABILITY_OPEN_WEIGHT
from ...models.validator import ModelValidator


class BaseOpenAICompatibleChineseAdapter(BaseProviderAdapter):
    """Reusable base for OpenAI-compatible Chinese AI endpoints."""

    catalog: Dict[str, Dict[str, Any]] = {}

    def discover_models(self, timeout: float = 8.0) -> List[ModelInfo]:
        base = self.get_api_base()
        key = self.get_api_key()
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"

        discovered_ids = []
        try:
            resp = requests.get(f"{base}/models", headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                for item in data:
                    mid = str(item.get("id", "")).strip()
                    if mid:
                        discovered_ids.append(mid)
        except Exception:
            pass

        # Ensure catalog models are present
        for cat_id in self.catalog:
            if cat_id not in discovered_ids:
                discovered_ids.append(cat_id)

        results = []
        for mid in discovered_ids:
            meta = dict(self.catalog.get(mid, {}))
            meta["model_id"] = mid
            meta["endpoint"] = base
            val = ModelValidator.validate_raw(meta, self.provider_id, self.config)
            if val.is_valid and val.model_info:
                results.append(val.model_info)
        return results


class DeepSeekAdapter(BaseOpenAICompatibleChineseAdapter):
    provider_id = "deepseek"
    display_name = "DeepSeek"
    company = "DeepSeek"
    region = "CN"
    api_base = "https://api.deepseek.com/v1"
    authentication_type = "bearer_token"
    documentation_url = "https://platform.deepseek.com/api-docs"

    catalog = {
        "deepseek-chat": {
            "display_name": "DeepSeek-V3",
            "family": "DeepSeek",
            "version": "V3",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "capabilities": ["chat", "coding", "tools", "streaming", "fast"],
            "pricing": {"input_price_per_1m": 0.14, "output_price_per_1m": 0.28},
            "availability": AVAILABILITY_OPEN_WEIGHT,
            "recommendation_badges": ["Best Budget Model", "Best Fast Model"],
        },
        "deepseek-reasoner": {
            "display_name": "DeepSeek-R1 (Reasoner)",
            "family": "DeepSeek",
            "version": "R1",
            "context_window": 128000,
            "max_output_tokens": 32768,
            "reasoning_levels": ["high"],
            "capabilities": ["reasoning", "coding", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 0.55, "output_price_per_1m": 2.19},
            "availability": AVAILABILITY_OPEN_WEIGHT,
            "recommendation_badges": ["Best for Reasoning", "Best Budget Model"],
        },
        "deepseek-r1": {
            "display_name": "DeepSeek-R1",
            "family": "DeepSeek",
            "version": "R1",
            "context_window": 128000,
            "max_output_tokens": 32768,
            "reasoning_levels": ["high"],
            "capabilities": ["reasoning", "coding", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 0.55, "output_price_per_1m": 2.19},
            "availability": AVAILABILITY_OPEN_WEIGHT,
            "recommendation_badges": ["Best for Reasoning", "Best Budget Model"],
        },
    }


class QwenAdapter(BaseOpenAICompatibleChineseAdapter):
    provider_id = "alibaba"
    display_name = "Alibaba Cloud (Qwen)"
    company = "Alibaba Cloud"
    region = "CN"
    api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    authentication_type = "bearer_token"
    documentation_url = "https://help.aliyun.com/zh/dashscope"

    catalog = {
        "qwen-max": {
            "display_name": "Qwen Max",
            "family": "Qwen",
            "context_window": 131072,
            "max_output_tokens": 8192,
            "capabilities": ["reasoning", "coding", "vision", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 2.8, "output_price_per_1m": 8.4},
            "recommendation_badges": ["Best for Coding"],
        },
        "qwen-plus": {
            "display_name": "Qwen Plus",
            "family": "Qwen",
            "context_window": 131072,
            "max_output_tokens": 8192,
            "capabilities": ["coding", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 0.4, "output_price_per_1m": 1.2},
        },
        "qwen-turbo": {
            "display_name": "Qwen Turbo",
            "family": "Qwen",
            "context_window": 1000000,
            "max_output_tokens": 8192,
            "capabilities": ["tools", "streaming", "fast", "long_context"],
            "pricing": {"input_price_per_1m": 0.05, "output_price_per_1m": 0.15},
            "recommendation_badges": ["Best Fast Model", "Best Budget Model"],
        },
        "qwen-2.5-coder-32b": {
            "display_name": "Qwen 2.5 Coder 32B",
            "family": "Qwen",
            "context_window": 131072,
            "max_output_tokens": 8192,
            "capabilities": ["coding", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 0.5, "output_price_per_1m": 1.5},
            "availability": AVAILABILITY_OPEN_WEIGHT,
            "recommendation_badges": ["Best for Coding"],
        },
        "qwen-qwq-32b": {
            "display_name": "Qwen QwQ 32B (Reasoning)",
            "family": "Qwen",
            "context_window": 131072,
            "max_output_tokens": 32768,
            "reasoning_levels": ["high"],
            "capabilities": ["reasoning", "coding", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 0.8, "output_price_per_1m": 2.4},
            "availability": AVAILABILITY_OPEN_WEIGHT,
            "recommendation_badges": ["Best for Reasoning"],
        },
    }


class MoonshotAdapter(BaseOpenAICompatibleChineseAdapter):
    provider_id = "moonshot"
    display_name = "Moonshot AI (Kimi)"
    company = "Moonshot AI"
    region = "CN"
    api_base = "https://api.moonshot.cn/v1"
    authentication_type = "bearer_token"
    documentation_url = "https://platform.moonshot.cn/docs"

    catalog = {
        "kimi-k3": {
            "display_name": "Kimi K3",
            "family": "Kimi",
            "context_window": 256000,
            "max_output_tokens": 16384,
            "capabilities": ["reasoning", "coding", "long_context", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 1.5, "output_price_per_1m": 6.0},
            "recommendation_badges": ["Best for Research"],
        },
        "kimi-k2": {
            "display_name": "Kimi K2",
            "family": "Kimi",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "capabilities": ["coding", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 1.0, "output_price_per_1m": 4.0},
        },
        "moonshot-v1-128k": {
            "display_name": "Moonshot v1 128k",
            "family": "Kimi",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "capabilities": ["long_context", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 1.2, "output_price_per_1m": 4.8},
        },
    }


class ZhipuGLMAdapter(BaseOpenAICompatibleChineseAdapter):
    provider_id = "zhipu"
    display_name = "Zhipu AI (GLM)"
    company = "Zhipu AI / Z.AI"
    region = "CN"
    api_base = "https://open.bigmodel.cn/api/paas/v4"
    authentication_type = "bearer_token"
    documentation_url = "https://open.bigmodel.cn/dev/api"

    catalog = {
        "glm-5.1": {
            "display_name": "GLM-5.1",
            "family": "GLM",
            "version": "5.1",
            "context_window": 256000,
            "max_output_tokens": 16384,
            "capabilities": ["reasoning", "coding", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 1.5, "output_price_per_1m": 5.0},
            "recommendation_badges": ["Best for Reasoning"],
        },
        "glm-5.2": {
            "display_name": "GLM-5.2",
            "family": "GLM",
            "version": "5.2",
            "context_window": 256000,
            "max_output_tokens": 16384,
            "capabilities": ["reasoning", "coding", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 2.0, "output_price_per_1m": 6.0},
        },
        "glm-5.3": {
            "display_name": "GLM-5.3",
            "family": "GLM",
            "version": "5.3",
            "context_window": 512000,
            "max_output_tokens": 32768,
            "capabilities": ["reasoning", "coding", "vision", "tools", "streaming", "long_context"],
            "pricing": {"input_price_per_1m": 2.5, "output_price_per_1m": 8.0},
            "recommendation_badges": ["Best for Coding", "Best for Research"],
        },
        "glm-4-plus": {
            "display_name": "GLM-4 Plus",
            "family": "GLM",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "capabilities": ["coding", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 1.4, "output_price_per_1m": 4.2},
        },
        "glm-4-air": {
            "display_name": "GLM-4 Air",
            "family": "GLM",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "capabilities": ["tools", "streaming", "fast"],
            "pricing": {"input_price_per_1m": 0.14, "output_price_per_1m": 0.42},
            "recommendation_badges": ["Best Fast Model"],
        },
    }


class MiniMaxAdapter(BaseOpenAICompatibleChineseAdapter):
    provider_id = "minimax"
    display_name = "MiniMax"
    company = "MiniMax"
    region = "CN"
    api_base = "https://api.minimax.chat/v1"
    authentication_type = "bearer_token"
    documentation_url = "https://platform.minimaxi.com"

    catalog = {
        "h3": {
            "display_name": "MiniMax H3",
            "family": "MiniMax",
            "context_window": 256000,
            "max_output_tokens": 16384,
            "capabilities": ["reasoning", "coding", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 1.0, "output_price_per_1m": 4.0},
        },
        "minimax-text-01": {
            "display_name": "MiniMax Text 01",
            "family": "MiniMax",
            "context_window": 1000000,
            "max_output_tokens": 16384,
            "capabilities": ["long_context", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 0.5, "output_price_per_1m": 2.0},
        },
        "abab6.5s": {
            "display_name": "MiniMax Abab 6.5s",
            "family": "MiniMax",
            "context_window": 256000,
            "max_output_tokens": 8192,
            "capabilities": ["chat", "fast", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 0.2, "output_price_per_1m": 0.8},
            "recommendation_badges": ["Best Fast Model"],
        },
    }


class TencentHunyuanAdapter(BaseOpenAICompatibleChineseAdapter):
    provider_id = "tencent"
    display_name = "Tencent Hunyuan"
    company = "Tencent"
    region = "CN"
    api_base = "https://api.hunyuan.cloud.tencent.com/v1"
    authentication_type = "bearer_token"
    documentation_url = "https://cloud.tencent.com/document/product/1729"

    catalog = {
        "hy3": {
            "display_name": "Hunyuan Hy3",
            "family": "Hunyuan",
            "context_window": 256000,
            "max_output_tokens": 16384,
            "capabilities": ["reasoning", "coding", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 1.5, "output_price_per_1m": 5.0},
        },
        "hunyuan-pro": {
            "display_name": "Hunyuan Pro",
            "family": "Hunyuan",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "capabilities": ["coding", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 1.0, "output_price_per_1m": 4.0},
        },
    }


class ByteDanceSeedAdapter(BaseOpenAICompatibleChineseAdapter):
    provider_id = "bytedance"
    display_name = "ByteDance (Doubao / Seed)"
    company = "ByteDance"
    region = "CN"
    api_base = "https://ark.cn-beijing.volces.com/api/v3"
    authentication_type = "bearer_token"
    documentation_url = "https://www.volcengine.com/docs/82379"

    catalog = {
        "doubao-pro": {
            "display_name": "Doubao Pro (Seed)",
            "family": "Seed",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "capabilities": ["chat", "coding", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 0.12, "output_price_per_1m": 0.24},
            "recommendation_badges": ["Best Budget Model"],
        },
        "doubao-lite": {
            "display_name": "Doubao Lite (Seed)",
            "family": "Seed",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "capabilities": ["chat", "fast", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 0.04, "output_price_per_1m": 0.08},
            "recommendation_badges": ["Best Fast Model"],
        },
    }


class XiaomiMiMoAdapter(BaseOpenAICompatibleChineseAdapter):
    provider_id = "xiaomi"
    display_name = "Xiaomi MiMo"
    company = "Xiaomi"
    region = "CN"
    api_base = "https://api.mimo.mi.com/v1"
    authentication_type = "bearer_token"
    documentation_url = "https://dev.mi.com"

    catalog = {
        "mimo-pro": {
            "display_name": "MiMo Pro",
            "family": "MiMo",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "capabilities": ["chat", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 0.5, "output_price_per_1m": 1.5},
        },
    }


class BaiduErnieAdapter(BaseOpenAICompatibleChineseAdapter):
    provider_id = "baidu"
    display_name = "Baidu (ERNIE)"
    company = "Baidu"
    region = "CN"
    api_base = "https://aip.baidubce.com/v2"
    authentication_type = "bearer_token"
    documentation_url = "https://cloud.baidu.com/doc/WENXINWORKSHOP"

    catalog = {
        "ernie-4.0-turbo": {
            "display_name": "ERNIE 4.0 Turbo",
            "family": "ERNIE",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "capabilities": ["reasoning", "coding", "tools", "streaming"],
            "pricing": {"input_price_per_1m": 2.0, "output_price_per_1m": 6.0},
        },
        "ernie-speed": {
            "display_name": "ERNIE Speed",
            "family": "ERNIE",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "capabilities": ["chat", "fast", "streaming"],
            "pricing": {"input_price_per_1m": 0.0, "output_price_per_1m": 0.0},
            "recommendation_badges": ["Best Free Model"],
        },
    }


# Convenience aliases
AlibabaQwenAdapter = QwenAdapter
MoonshotKimiAdapter = MoonshotAdapter
