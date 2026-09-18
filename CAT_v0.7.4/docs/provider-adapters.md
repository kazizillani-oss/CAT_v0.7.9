# CAT Provider Adapters (v2026.09)

## Overview

Provider Adapters (`calc_terminal/providers/adapters/`) bridge CAT's standardized discovery interface with the heterogeneous APIs of external AI vendors. Every adapter inherits from `BaseProviderAdapter`.

---

## The `BaseProviderAdapter` Interface

Defined in `calc_terminal/providers/adapters/base.py`:

```python
class BaseProviderAdapter(ABC):
    def __init__(self, provider_id: str, config: Optional[Dict[str, Any]] = None):
        self.provider_id = provider_id.lower().strip()
        self.config = config or {}
        self.base_url = self.config.get("base_url") or self.default_base_url
        self.api_key = self.config.get("api_key") or self._resolve_api_key()

    @property
    @abstractmethod
    def default_base_url(self) -> str:
        """Default base URL if not customized in config."""
        pass

    @abstractmethod
    def discover_models(self, timeout: float = 6.0) -> List[ModelInfo]:
        """Perform live discovery, normalize metadata, and return ModelInfo instances."""
        pass

    def health_check(self, timeout: float = 3.0) -> bool:
        """Return True if provider API endpoint is reachable."""
        pass
```

---

## Built-In Adapters

| Provider Adapter | Module | Models Discovered / Supported |
| :--- | :--- | :--- |
| `OpenAIAdapter` | `openai_adapter.py` | Official catalog: `gpt-6-astra`, `gpt-5.6`, `o1`, `o3`, `gpt-4o` + live `/v1/models` |
| `AnthropicAdapter` | `anthropic_adapter.py` | Official catalog: `claude-4-sonnet`, `claude-4-opus`, `claude-3-7-sonnet` + live `/v1/models` |
| `GeminiAdapter` | `gemini_adapter.py` | Official catalog: `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.0` + live Google API |
| `DeepSeekAdapter` | `chinese_adapters.py` | `deepseek-chat`, `deepseek-reasoner` (R1) via `https://api.deepseek.com/v1` |
| `AlibabaQwenAdapter` | `chinese_adapters.py` | `qwen-max-2026`, `qwen-plus-2026`, `qwen2.5-coder` via DashScope API |
| `MoonshotKimiAdapter`| `chinese_adapters.py` | `kimi-k3`, `moonshot-v1-128k` via `https://api.moonshot.cn/v1` |
| `ZhipuGLMAdapter` | `chinese_adapters.py` | `glm-5.1`, `glm-5.2`, `glm-4-plus` via `https://open.bigmodel.cn/api/paas/v4` |
| `MiniMaxAdapter` | `chinese_adapters.py` | `minimax-h3`, `abab6.5s` via `https://api.minimax.chat/v1` |
| `TencentHunyuanAdapter` | `chinese_adapters.py` | `hunyuan-hy3`, `hunyuan-pro` via Tencent Cloud API |
| `ByteDanceSeedAdapter` | `chinese_adapters.py` | `seed-v2`, `doubao-pro-256k` via Volcengine API |
| `XiaomiMiMoAdapter` | `chinese_adapters.py` | `mimo-v1-flash` via Xiaomi MiMo platform |
| `BaiduErnieAdapter` | `chinese_adapters.py` | `ernie-4.5`, `ernie-speed` via Qianfan API |
| `OllamaAdapter` | `ollama_adapter.py` | Local & Cloud: fetches tags via `http://localhost:11434/api/tags` |
| `XAIAdapter` | `other_adapters.py` | `grok-3`, `grok-2` via `https://api.x.ai/v1` |
| `MistralAdapter` | `other_adapters.py` | `mistral-large-2411`, `codestral-2501` via `https://api.mistral.ai/v1` |
| `GenericOpenAIAdapter`| `other_adapters.py` | Fallback adapter for any OpenAI-compatible API endpoint |

---

## Safe Live Discovery Guidelines

When implementing or extending an adapter:
1. **Short Timeouts**: All discovery network requests MUST enforce timeouts (default `6.0s`, max `10.0s`).
2. **Safe JSON Parsing**: Always safely deserialize responses and validate required fields before creating `ModelInfo`.
3. **Graceful Fallbacks**: If the endpoint fails or requires authentication that is absent, return catalog defaults rather than raising uncaught exceptions.
4. **No Side Effects**: `discover_models` must only perform read-only GET requests on models/tags endpoints. It must NEVER execute prompts or generate tokens.
