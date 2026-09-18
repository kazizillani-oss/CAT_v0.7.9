# CAT Dynamic Model Registry (v2026.09)

## Overview

The Dynamic Model Registry (`calc_terminal/models/dynamic_registry.py`) is the single source of truth for all AI model metadata in CAT. It maintains an indexed catalog of models, capabilities, context limits, reasoning levels, pricing, and availability states.

---

## Canonical Model Identity

To prevent collisions between different providers serving identically named models (e.g. `llama-3.3-70b` available on Groq, Together, DeepInfra, and Ollama), CAT enforces a canonical format:

$$\text{canonical\_model\_id} = \text{provider\_id} : \text{model\_id}$$

Examples:
- `openai:gpt-6-astra`
- `anthropic:claude-4-sonnet-20260515`
- `deepseek:deepseek-r1`
- `moonshot:kimi-k3`
- `ollama:llama3.3`

---

## ModelInfo Schema

Every registered model is represented by a standardized `ModelInfo` dataclass (`calc_terminal/models/schema.py`):

| Field | Type | Description |
| :--- | :--- | :--- |
| `provider` | `str` | Provider ID (e.g. `openai`) |
| `model_id` | `str` | Provider's raw model identifier (e.g. `gpt-6-astra`) |
| `display_name` | `str` | Human-friendly name (e.g. `GPT-6 Astra`) |
| `family` | `str` | Architectural family (e.g. `GPT`, `Claude`, `DeepSeek`) |
| `canonical_model_id`| `str` | Fully qualified identifier (`openai:gpt-6-astra`) |
| `status` | `str` | `active`, `preview`, `beta`, `deprecated`, `retired`, `auth_required` |
| `availability` | `str` | `paid_api`, `free_api`, `local`, `open_weight` |
| `capabilities` | `List[str]`| `reasoning`, `coding`, `vision`, `tools`, `streaming`, `computer_use`, `research` |
| `context_window` | `int` | Maximum context length in tokens (e.g. `1050000`) |
| `max_output_tokens` | `int` | Maximum completion tokens (e.g. `128000`) |
| `reasoning_levels` | `List[str]`| Discrete reasoning effort levels (`low`, `medium`, `high`, `xhigh`, `max`) |
| `pricing` | `dict` | `input_price_per_1m`, `output_price_per_1m` |
| `recommendation_badges`| `List[str]`| Badges such as `Best for Coding`, `Best for Reasoning` |
| `stale` | `bool` | True if API verification failed but model is retained as fallback |

---

## Intelligent Task-Based Ranking

CAT calculates a contextual suitability score $S \in [0, 100]$ when matching models to tasks via `registry.get_ranked_models(task)`:

$$S = S_{\text{base}} + W_{\text{task}} + W_{\text{context}} + W_{\text{verified}} - P_{\text{latency}}$$

### Supported Task Dimensions:
1. **`coding`**: Heavily weights models with verified coding capabilities, computer-use support, and reasoning engines (e.g. `gpt-6-astra`, `claude-4-sonnet`, `deepseek-r1`).
2. **`reasoning`**: Prioritizes multi-step CoT reasoning models with high context windows and specialized reasoning effort flags.
3. **`fast`**: Ranks high-throughput, low-latency models for autocomplete and quick edits (e.g. `o3-mini`, `gpt-4o-mini`, `gemini-2.5-flash`).
4. **`free`**: Ranks zero-cost models and local runners (Ollama, Gemini Free tier).
5. **`multimodal` / `vision`**: Weights vision input, audio processing, and document workflows.

---

## Persistence and Atomic Writes

The catalog is stored in `%LOCALAPPDATA%/CCT/registry/models.json` (or `~/.cct/registry/models.json` on Linux/macOS):
- Writes are performed atomically using `.tmp` temporary files followed by an atomic `os.replace` to prevent file corruption during sudden terminations.
- State is preserved offline: temporary network outages mark models as `stale=True`, ensuring CAT remains functional even when disconnected.
