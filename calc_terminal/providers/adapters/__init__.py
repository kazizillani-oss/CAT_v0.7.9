"""
calc_terminal/providers/adapters/__init__.py
===========================================
Provider Adapter Registry and Factory for CAT.
"""

from typing import Dict, Type, Optional, Any

from .base import BaseProviderAdapter
from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter
from .gemini_adapter import GeminiAdapter
from .chinese_adapters import (
    DeepSeekAdapter,
    QwenAdapter,
    MoonshotAdapter,
    ZhipuGLMAdapter,
    MiniMaxAdapter,
    TencentHunyuanAdapter,
    ByteDanceSeedAdapter,
    XiaomiMiMoAdapter,
    BaiduErnieAdapter,
)
from .ollama_adapter import OllamaAdapter
from .other_adapters import (
    XAIAdapter,
    MistralAdapter,
    CohereAdapter,
    GenericOpenAIAdapter,
)

_ADAPTER_REGISTRY: Dict[str, Type[BaseProviderAdapter]] = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "gemini": GeminiAdapter,
    "google": GeminiAdapter,
    "deepseek": DeepSeekAdapter,
    "alibaba": QwenAdapter,
    "qwen": QwenAdapter,
    "moonshot": MoonshotAdapter,
    "kimi": MoonshotAdapter,
    "zhipu": ZhipuGLMAdapter,
    "glm": ZhipuGLMAdapter,
    "minimax": MiniMaxAdapter,
    "tencent": TencentHunyuanAdapter,
    "hunyuan": TencentHunyuanAdapter,
    "bytedance": ByteDanceSeedAdapter,
    "seed": ByteDanceSeedAdapter,
    "doubao": ByteDanceSeedAdapter,
    "xiaomi": XiaomiMiMoAdapter,
    "mimo": XiaomiMiMoAdapter,
    "baidu": BaiduErnieAdapter,
    "ernie": BaiduErnieAdapter,
    "ollama": OllamaAdapter,
    "xai": XAIAdapter,
    "grok": XAIAdapter,
    "mistral": MistralAdapter,
    "cohere": CohereAdapter,
}


def register_adapter(provider_id: str, adapter_cls: Type[BaseProviderAdapter]):
    """Allow registering external or custom provider adapters."""
    _ADAPTER_REGISTRY[provider_id.lower().strip()] = adapter_cls


def get_adapter(provider_id: str, config: Optional[Dict[str, Any]] = None) -> BaseProviderAdapter:
    """Instantiate the appropriate adapter for the given provider."""
    pid = (provider_id or "").lower().strip()
    cls = _ADAPTER_REGISTRY.get(pid)
    if cls is None:
        adapter = GenericOpenAIAdapter(config)
        adapter.provider_id = pid
        adapter.display_name = pid.capitalize()
        return adapter
    return cls(config)


def list_supported_adapters() -> Dict[str, Type[BaseProviderAdapter]]:
    return dict(_ADAPTER_REGISTRY)
