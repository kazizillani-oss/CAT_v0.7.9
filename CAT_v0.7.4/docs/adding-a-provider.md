# Adding a New AI Provider to CAT

## Guide: Zero-Code vs Adapter-Based Provider Addition

CAT provides two ways to add new AI providers:
1. **Zero-Code Configuration**: For standard OpenAI-compatible or Ollama-compatible endpoints.
2. **Custom Provider Adapter**: For specialized APIs, proprietary schemas, or bespoke authentication.

---

## Method 1: Zero-Code Addition (via `providers.json` or TUI)

Because CAT includes a `GenericOpenAIAdapter`, any OpenAI-compatible provider can be added simply by defining it in `providers.json` or via CAT's UI `Add Provider Screen`.

### Adding to `providers.json`
Edit `calc_terminal/providers/providers.json` and append your provider configuration:

```json
{
  "id": "my-custom-provider",
  "name": "My Custom AI",
  "url": "https://api.mycustomai.com/v1",
  "api_style": "openai",
  "auth_key": "MY_CUSTOM_AI_API_KEY",
  "category": "cloud",
  "free": false,
  "paid": true,
  "fallback_models": ["custom-chat-v1", "custom-code-v1"],
  "auto_discover_models": true
}
```

Set the environment variable:
```bash
set MY_CUSTOM_AI_API_KEY=sk-...
```

CAT will automatically detect the provider, run `GenericOpenAIAdapter`, discover all models at `https://api.mycustomai.com/v1/models`, and populate the registry!

---

## Method 2: Creating a Custom Provider Adapter

If your provider requires non-standard headers, non-OpenAI JSON responses, or unique capabilities, write an adapter.

### Step 1: Create the Adapter Class
Create `calc_terminal/providers/adapters/my_adapter.py`:

```python
from typing import List, Optional, Dict, Any
import requests
from .base import BaseProviderAdapter
from ...models.schema import ModelInfo, STATUS_ACTIVE, AVAILABILITY_PAID_API

class MyCustomAdapter(BaseProviderAdapter):
    @property
    def default_base_url(self) -> str:
        return "https://api.mycustomai.com/v1"

    def discover_models(self, timeout: float = 6.0) -> List[ModelInfo]:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        resp = requests.get(f"{self.base_url}/catalog", headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        models = []
        for item in data.get("items", []):
            models.append(ModelInfo(
                provider=self.provider_id,
                model_id=item["name"],
                display_name=item.get("title", item["name"]),
                context_window=item.get("context_size", 128000),
                capabilities=["chat", "coding", "streaming"],
                status=STATUS_ACTIVE,
                availability=AVAILABILITY_PAID_API,
            ))
        return models
```

### Step 2: Register the Adapter
In `calc_terminal/providers/adapters/__init__.py`:

```python
from .my_adapter import MyCustomAdapter

register_adapter("my-custom-provider", MyCustomAdapter)
```

### Step 3: Verify with CLI
Verify the new provider immediately via the CAT CLI:

```bash
cat providers audit
cat models --provider my-custom-provider
```
