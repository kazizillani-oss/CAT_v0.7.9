"""
CAT Model Capabilities & Profile System.

Enforces Section 13, 14, 26, 35-37 of the CAT AI Mode Reliability Contract.
Distinguishes small/base models (e.g. deepseek-coder:1.3b-base-q8_0) from
large instruction-following models, providing conservative budgets,
minimal prompting, and specialized generation parameters.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import re


@dataclass
class ModelCapabilities:
    chat: bool = True
    instruction_following: bool = True
    tool_calling: bool = True
    vision: bool = False
    reasoning: bool = False
    context_length: int = 4096
    is_small_model: bool = False
    is_base_model: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chat": self.chat,
            "instruction_following": self.instruction_following,
            "tool_calling": self.tool_calling,
            "vision": self.vision,
            "reasoning": self.reasoning,
            "context_length": self.context_length,
            "is_small_model": self.is_small_model,
            "is_base_model": self.is_base_model,
        }


@dataclass
class ModelProfile:
    provider: str
    model: str
    capabilities: ModelCapabilities
    prompt_template: str = "chat"  # "chat", "minimal", "completion"
    recommended_temperature: float = 0.7
    max_context_tokens: int = 4096
    reserved_output_tokens: int = 1024
    generation_options: Dict[str, Any] = field(default_factory=dict)

    def is_small_or_base(self) -> bool:
        return self.capabilities.is_small_model or self.capabilities.is_base_model

    def supports_tools(self) -> bool:
        return self.capabilities.tool_calling and not self.capabilities.is_base_model

    def get_effective_options(self, user_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Merge base generation options with model defaults and optional user overrides."""
        opts = dict(self.generation_options)
        if user_options:
            for k, v in user_options.items():
                if v is not None:
                    opts[k] = v
        return opts


# Regex patterns identifying small or base models
_BASE_MODEL_PATTERNS = [
    re.compile(r"[-:_]base($|[-:_])", re.IGNORECASE),
    re.compile(r"base-q\d", re.IGNORECASE),
]

_SMALL_MODEL_PATTERNS = [
    re.compile(r"[:\-_](0\.\d+|1\.[0-8]+|2|3)b($|[:\-_])", re.IGNORECASE),
    re.compile(r"(tinyllama|smollm|qwen.*0\.5b|qwen.*1\.8b|deepseek.*1\.3b)", re.IGNORECASE),
]

_VISION_PATTERNS = [
    re.compile(r"(vision|llava|gpt-4o|claude-3|gemini-1\.5|gemini-2\.0)", re.IGNORECASE),
]

_REASONING_PATTERNS = [
    re.compile(r"(o1|o3|r1|reasoning|deepseek-r1)", re.IGNORECASE),
]

_TOOL_CAPABLE_PATTERNS = [
    re.compile(r"(gpt-4|claude-3|gemini|llama-?3\.[123]|qwen2\.5.*(7b|14b|32b|72b)|mistral)", re.IGNORECASE),
]


def detect_capabilities(provider: str, model_name: str) -> ModelCapabilities:
    """Analyze provider and model string to infer capabilities safely."""
    provider_str = (provider or "").lower().strip()
    model_str = (model_name or "").lower().strip()

    is_base = any(p.search(model_str) for p in _BASE_MODEL_PATTERNS)
    is_small = any(p.search(model_str) for p in _SMALL_MODEL_PATTERNS) or ("1.3b" in model_str)

    # Base models do not reliably follow complex multi-turn instruction schemas
    instruction_following = not is_base
    tool_calling = False if (is_base or is_small) else any(p.search(model_str) for p in _TOOL_CAPABLE_PATTERNS)

    # If provider is OpenAI/Anthropic/Gemini standard models, tool calling is standard
    if provider_str in ("openai", "anthropic", "gemini") and not is_small:
        tool_calling = True
        instruction_following = True

    vision = any(p.search(model_str) for p in _VISION_PATTERNS)
    reasoning = any(p.search(model_str) for p in _REASONING_PATTERNS)

    if is_small:
        context_length = 2048
    elif is_base:
        context_length = 2048
    elif "16k" in model_str:
        context_length = 16384
    elif "32k" in model_str:
        context_length = 32768
    elif "128k" in model_str or "gpt-4o" in model_str or "gemini" in model_str:
        context_length = 131072
    else:
        context_length = 4096

    return ModelCapabilities(
        chat=True,
        instruction_following=instruction_following,
        tool_calling=tool_calling,
        vision=vision,
        reasoning=reasoning,
        context_length=context_length,
        is_small_model=is_small,
        is_base_model=is_base,
    )


def get_model_profile(provider: str, model_name: str, config: Optional[Dict[str, Any]] = None) -> ModelProfile:
    """Build a complete ModelProfile tailored to the given provider and model."""
    caps = detect_capabilities(provider, model_name)

    if caps.is_small_model or caps.is_base_model:
        # Conservative defaults for small/base local models (e.g. deepseek-coder:1.3b-base-q8_0)
        recommended_temp = 0.3
        max_context = min(caps.context_length, 1536)
        reserved_out = 512
        prompt_template = "minimal" if caps.is_base_model else "chat"
        gen_opts = {
            "temperature": recommended_temp,
            "top_p": 0.9,
            "repeat_penalty": 1.18,
            "num_predict": reserved_out,
        }
    else:
        # Standard instruction/chat model defaults
        recommended_temp = 0.7
        max_context = min(caps.context_length, 8192)
        reserved_out = 1024
        prompt_template = "chat"
        gen_opts = {
            "temperature": recommended_temp,
            "top_p": 0.95,
        }

    # Override temperature if explicitly provided in config
    if config and config.get("temperature") is not None:
        try:
            gen_opts["temperature"] = float(config["temperature"])
        except (ValueError, TypeError):
            pass

    # For Ollama models, check if model size exceeds GPU VRAM (e.g. 8B/9.6GB model on 4GB VRAM)
    # Default to num_gpu: 0 (CPU) to prevent llama-server crashing with 0xc0000409 buffer overrun
    if (provider or "").lower() == "ollama":
        if config and config.get("num_gpu") is not None:
            gen_opts["num_gpu"] = int(config["num_gpu"])
        else:
            try:
                from .. import pc_specs
                specs = pc_specs.get_specs()
                vram = specs.get("gpu_vram_gb", 0)
                is_large = any(k in (model_name or "").lower() for k in ("8b", "9b", "14b", "32b", "70b", "e4b", "gemma4", "gemma:7b", "llama3:8b"))
                if vram and vram <= 4.5 and is_large:
                    gen_opts["num_gpu"] = 0
            except Exception:
                pass

    return ModelProfile(
        provider=provider or "ollama",
        model=model_name or "default",
        capabilities=caps,
        prompt_template=prompt_template,
        recommended_temperature=recommended_temp,
        max_context_tokens=max_context,
        reserved_output_tokens=reserved_out,
        generation_options=gen_opts,
    )
