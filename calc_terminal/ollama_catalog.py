"""Ollama model catalog — Authentic, curated models with dynamic local discovery.
Creator: Kazi Zillani (CAT Platform).

Provides authentic model metadata (params, size, context, capabilities, family)
without artificial dummy variants. Supports dynamic registration of locally installed
models and custom user models.
"""

from typing import List, Dict, Any, Optional
import os

# Base curated catalog of authentic, modern local models
CURATED_CATALOG: List[Dict[str, Any]] = []

def _add(name: str, params: str, size_gb: float, family: str, desc: str,
         ctx: int = 8192, caps: Optional[List[str]] = None, categories: Optional[List[str]] = None):
    CURATED_CATALOG.append({
        "name": name,
        "params": params,
        "size_gb": float(size_gb),
        "family": family,
        "desc": desc,
        "context": ctx,
        "caps": caps or ["chat"],
        "categories": categories or ["popular"],
    })

# =====================================================================
# 1. CORE LLAMA (Meta)
# =====================================================================
_add("llama3.3:70b", "70B", 42.0, "llama", "Meta Llama 3.3 70B — State of the art open weights model", 131072, ["chat", "code", "reasoning"], ["popular", "large"])
_add("llama3.3:8b", "8B", 4.7, "llama", "Meta Llama 3.3 8B — Fast, capable general assistant", 131072, ["chat", "code"], ["popular", "coding"])
_add("llama3.2:3b", "3B", 2.0, "llama", "Meta Llama 3.2 3B — Lightweight on-device assistant", 131072, ["chat", "code"], ["popular", "small"])
_add("llama3.2:1b", "1B", 1.3, "llama", "Meta Llama 3.2 1B — Ultra-lightweight edge model", 131072, ["chat"], ["small"])
_add("llama3.1:8b", "8B", 4.7, "llama", "Meta Llama 3.1 8B — High context general purpose model", 131072, ["chat", "code"], ["popular", "coding"])
_add("llama3.1:70b", "70B", 42.0, "llama", "Meta Llama 3.1 70B — Heavyweight reasoning and coding", 131072, ["chat", "code", "reasoning"], ["large"])
_add("llama3.1:405b", "405B", 243.0, "llama", "Meta Llama 3.1 405B — Frontier flagship open weights", 131072, ["chat", "code", "reasoning"], ["large"])
_add("llama3:8b", "8B", 4.7, "llama", "Meta Llama 3 8B — Original Llama 3 release", 8192, ["chat", "code"], ["popular"])
_add("llama2:7b", "7B", 3.8, "llama", "Meta Llama 2 7B — Classic foundation model", 4096, ["chat"], ["small"])
_add("llama2:13b", "13B", 7.4, "llama", "Meta Llama 2 13B — Classic balanced model", 4096, ["chat"], ["popular"])

# =====================================================================
# 2. QWEN & QWEN CODER (Alibaba)
# =====================================================================
_add("qwen2.5-coder:7b", "7B", 4.7, "qwen", "Qwen 2.5 Coder 7B — Premier open-source code generation model", 32768, ["code", "chat"], ["popular", "coding"])
_add("qwen2.5-coder:14b", "14B", 9.0, "qwen", "Qwen 2.5 Coder 14B — Deep architectural coding & refactoring", 32768, ["code", "chat"], ["coding", "popular"])
_add("qwen2.5-coder:32b", "32B", 19.0, "qwen", "Qwen 2.5 Coder 32B — Enterprise-grade code intelligence", 32768, ["code", "chat", "reasoning"], ["coding", "large"])
_add("qwen2.5-coder:3b", "3B", 1.9, "qwen", "Qwen 2.5 Coder 3B — Fast on-device copilot & terminal assistant", 32768, ["code", "chat"], ["coding", "small"])
_add("qwen2.5-coder:1.5b", "1.5B", 1.0, "qwen", "Qwen 2.5 Coder 1.5B — Ultra-low latency autocomplete", 32768, ["code"], ["coding", "small"])
_add("qwen2.5:7b", "7B", 4.4, "qwen", "Qwen 2.5 7B — Multilingual general intelligence & math", 32768, ["chat", "code"], ["popular"])
_add("qwen2.5:14b", "14B", 9.0, "qwen", "Qwen 2.5 14B — Strong balanced reasoning and knowledge", 32768, ["chat", "code", "reasoning"], ["popular"])
_add("qwen2.5:32b", "32B", 19.0, "qwen", "Qwen 2.5 32B — High-fidelity analytical reasoning", 32768, ["chat", "code", "reasoning"], ["large"])
_add("qwen2.5:72b", "72B", 41.0, "qwen", "Qwen 2.5 72B — Flagship open weights generalist", 32768, ["chat", "code", "reasoning"], ["large"])
_add("qwen2.5:3b", "3B", 1.9, "qwen", "Qwen 2.5 3B — Agile compact multilingual model", 32768, ["chat"], ["small"])
_add("qwen2.5:1.5b", "1.5B", 0.9, "qwen", "Qwen 2.5 1.5B — Lightweight embedded model", 32768, ["chat"], ["small"])
_add("qwen2.5:0.5b", "0.5B", 0.4, "qwen", "Qwen 2.5 0.5B — Micro model for IoT and quick parsing", 32768, ["chat"], ["small"])
_add("qwq:32b", "32B", 20.0, "qwen", "QwQ 32B — Thinking & complex mathematical reasoning model", 32768, ["reasoning", "math", "code"], ["reasoning", "popular"])

# =====================================================================
# 3. DEEPSEEK (DeepSeek AI)
# =====================================================================
_add("deepseek-r1:1.5b", "1.5B", 1.1, "deepseek", "DeepSeek R1 Distill 1.5B — Micro step-by-step reasoning", 32768, ["reasoning"], ["reasoning", "small"])
_add("deepseek-r1:7b", "7B", 4.7, "deepseek", "DeepSeek R1 Distill 7B (Qwen) — Fast chain-of-thought", 32768, ["reasoning", "code"], ["reasoning", "popular"])
_add("deepseek-r1:8b", "8B", 4.9, "deepseek", "DeepSeek R1 Distill 8B (Llama) — Strong CoT reasoning", 32768, ["reasoning", "code"], ["reasoning", "popular"])
_add("deepseek-r1:14b", "14B", 9.0, "deepseek", "DeepSeek R1 Distill 14B — In-depth logical deduction & math", 32768, ["reasoning", "code", "math"], ["reasoning"])
_add("deepseek-r1:32b", "32B", 19.0, "deepseek", "DeepSeek R1 Distill 32B — High-end reasoning & complex problems", 32768, ["reasoning", "code", "math"], ["reasoning", "large"])
_add("deepseek-r1:70b", "70B", 42.0, "deepseek", "DeepSeek R1 Distill 70B — Top-tier open reasoning model", 32768, ["reasoning", "code", "math"], ["reasoning", "large"])
_add("deepseek-coder:6.7b", "6.7B", 3.8, "deepseek", "DeepSeek Coder 6.7B — Efficient coding specialist", 16384, ["code"], ["coding"])
_add("deepseek-coder-v2:16b", "16B", 8.9, "deepseek", "DeepSeek Coder V2 16B (MoE) — Multi-language coding engine", 32768, ["code", "chat"], ["coding"])
_add("deepseek-v3:671b", "671B", 400.0, "deepseek", "DeepSeek V3 671B (MoE) — Frontier flagship architecture", 65536, ["chat", "code", "reasoning"], ["large"])

# =====================================================================
# 4. GOOGLE GEMMA
# =====================================================================
_add("gemma3:1b", "1B", 0.8, "gemma", "Google Gemma 3 1B — Next-gen multimodal compact model", 32768, ["chat", "vision"], ["small", "vision"])
_add("gemma3:4b", "4B", 3.3, "gemma", "Google Gemma 3 4B — State-of-the-art multimodal lightweight model", 32768, ["chat", "vision", "code"], ["popular", "vision", "small"])
_add("gemma3:12b", "12B", 8.1, "gemma", "Google Gemma 3 12B — Advanced multimodal reasoning", 32768, ["chat", "vision", "code"], ["popular", "vision"])
_add("gemma3:27b", "27B", 17.0, "gemma", "Google Gemma 3 27B — High-capacity multimodal reasoning", 32768, ["chat", "vision", "reasoning"], ["large", "vision"])
_add("gemma2:2b", "2B", 1.6, "gemma", "Google Gemma 2 2B — High-efficiency on-device text generator", 8192, ["chat"], ["small"])
_add("gemma2:9b", "9B", 5.4, "gemma", "Google Gemma 2 9B — Outstanding performance-per-parameter", 8192, ["chat", "code"], ["popular"])
_add("gemma2:27b", "27B", 16.0, "gemma", "Google Gemma 2 27B — Powerful analytical text model", 8192, ["chat", "reasoning"], ["large"])
_add("codegemma:7b", "7B", 5.0, "gemma", "Google CodeGemma 7B — Code completion and synthesis", 8192, ["code"], ["coding"])

# =====================================================================
# 5. MISTRAL AI
# =====================================================================
_add("mistral:7b", "7B", 4.1, "mistral", "Mistral 7B — The classic high-performance 7B standard", 32768, ["chat", "code"], ["popular"])
_add("mistral-nemo:12b", "12B", 7.1, "mistral", "Mistral NeMo 12B — 128k context multilingual model with NVIDIA", 128000, ["chat", "code"], ["popular"])
_add("codestral:22b", "22B", 12.0, "mistral", "Mistral Codestral 22B — Fast 80+ language coding model", 32768, ["code"], ["coding", "popular"])
_add("mixtral:8x7b", "47B", 26.0, "mistral", "Mixtral 8x7B (MoE) — Fast sparse Mixture-of-Experts", 32768, ["chat", "code"], ["popular", "large"])
_add("mixtral:8x22b", "141B", 80.0, "mistral", "Mixtral 8x22B (MoE) — High-end reasoning Mixture-of-Experts", 65536, ["chat", "code", "reasoning"], ["large"])
_add("mathstral:7b", "7B", 4.1, "mistral", "Mistral Mathstral 7B — Mathematical reasoning and science", 32768, ["math", "reasoning"], ["reasoning"])

# =====================================================================
# 6. MICROSOFT PHI
# =====================================================================
_add("phi4:14b", "14B", 9.1, "phi", "Microsoft Phi-4 14B — Premier synthetic reasoning & STEM benchmark leader", 16384, ["reasoning", "math", "code"], ["popular", "reasoning"])
_add("phi3.5:3.8b", "3.8B", 2.2, "phi", "Microsoft Phi-3.5 Mini 3.8B — 128k context high-efficiency model", 128000, ["chat", "code"], ["small", "popular"])
_add("phi3:14b", "14B", 7.9, "phi", "Microsoft Phi-3 Medium 14B — Analytical reasoning", 16384, ["chat", "reasoning"], ["popular"])
_add("phi3:3.8b", "3.8B", 2.2, "phi", "Microsoft Phi-3 Mini 3.8B — Compact logic model", 8192, ["chat"], ["small"])

# =====================================================================
# 7. VISION & MULTIMODAL
# =====================================================================
_add("llava:7b", "7B", 4.7, "vision", "LLaVA 1.5 7B — Visual question answering and image inspection", 4096, ["vision", "chat"], ["vision", "popular"])
_add("llava:13b", "13B", 8.0, "vision", "LLaVA 1.5 13B — High-detail image understanding", 4096, ["vision", "chat"], ["vision"])
_add("llava-llama3:8b", "8B", 5.0, "vision", "LLaVA Llama-3 8B — Multimodal assistant on Llama 3", 8192, ["vision", "chat"], ["vision", "popular"])
_add("minicpm-v:8b", "8B", 5.5, "vision", "MiniCPM-V 2.6 8B — Outstanding OCR & high-res image analysis", 8192, ["vision", "chat"], ["vision"])
_add("moondream:1.8b", "1.8B", 1.0, "vision", "Moondream 2 1.8B — Fast edge-ready visual model", 4096, ["vision"], ["vision", "small"])
_add("bakllava:7b", "7B", 4.7, "vision", "BakLLaVA 7B — Mistral-backed visual assistant", 4096, ["vision"], ["vision"])

# =====================================================================
# 8. SMALL, FAST & ON-DEVICE
# =====================================================================
_add("smollm2:1.7b", "1.7B", 1.0, "smollm", "SmolLM2 1.7B — HuggingFace curated small model for edge devices", 8192, ["chat", "code"], ["small"])
_add("smollm2:360m", "360M", 0.3, "smollm", "SmolLM2 360M — Ultra-compact local language model", 8192, ["chat"], ["small"])
_add("smollm2:135m", "135M", 0.15, "smollm", "SmolLM2 135M — Micro test model with near-zero memory footprint", 2048, ["chat"], ["small"])
_add("tinyllama:1.1b", "1.1B", 0.6, "other", "TinyLlama 1.1B — 3T token trained compact architecture", 2048, ["chat"], ["small"])
_add("orca-mini:3b", "3B", 1.9, "other", "Orca Mini 3B — Microsoft Orca dataset instruction tuned", 4096, ["chat"], ["small"])
_add("granite3.1:2b", "2B", 1.3, "granite", "IBM Granite 3.1 2B — Enterprise small language model", 8192, ["chat", "code"], ["small"])
_add("granite3.1:8b", "8B", 4.9, "granite", "IBM Granite 3.1 8B — Enterprise general and tool-use model", 8192, ["chat", "code"], ["popular"])

# =====================================================================
# 9. SPECIALIZED CODING & ENTERPRISE
# =====================================================================
_add("codellama:7b", "7B", 3.8, "codellama", "CodeLlama 7B — Meta coding specialist", 16384, ["code"], ["coding"])
_add("codellama:13b", "13B", 7.4, "codellama", "CodeLlama 13B — Medium-footprint coding model", 16384, ["code"], ["coding"])
_add("codellama:34b", "34B", 19.0, "codellama", "CodeLlama 34B — High accuracy code completion", 16384, ["code"], ["coding", "large"])
_add("starcoder2:7b", "7B", 4.0, "starcoder", "StarCoder2 7B — BigCode consortium model for 600+ languages", 16384, ["code"], ["coding"])
_add("starcoder2:15b", "15B", 9.0, "starcoder", "StarCoder2 15B — High precision code assistant", 16384, ["code"], ["coding"])
_add("sqlcoder:15b", "15B", 8.5, "other", "Defog SQLCoder 15B — Natural language to SQL query engine", 4096, ["code", "sql"], ["coding"])
_add("command-r:35b", "35B", 19.0, "cohere", "Cohere Command R 35B — Optimized for RAG and tool execution", 128000, ["chat", "rag"], ["popular", "large"])
_add("command-r-plus:104b", "104B", 60.0, "cohere", "Cohere Command R+ 104B — Frontier enterprise RAG model", 128000, ["chat", "rag", "reasoning"], ["large"])

# =====================================================================
# 10. EMBEDDINGS & RETRIEVAL (RAG)
# =====================================================================
_add("nomic-embed-text:latest", "137M", 0.3, "nomic", "Nomic Embed Text — 8192 context high-quality text embedding", 8192, ["embedding"], ["embedding", "small"])
_add("bge-m3:latest", "567M", 1.2, "bge", "BAAI BGE-M3 — Multilingual, multi-granularity dense/sparse embedding", 8192, ["embedding"], ["embedding", "small"])
_add("all-minilm:latest", "33M", 0.1, "minilm", "All-MiniLM L6 v2 — Ultra-fast embedding model for semantic search", 512, ["embedding"], ["embedding", "small"])
_add("mxbai-embed-large:latest", "335M", 0.7, "mxbai", "MixedBread Embed Large — Top MTEB benchmark embedding model", 512, ["embedding"], ["embedding", "small"])


# Dynamic local model registry (persisted or populated from Ollama API)
DYNAMIC_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_custom_model(model_dict: Dict[str, Any]):
    """Register a custom or dynamically discovered model."""
    name = model_dict.get("name")
    if not name:
        return
    DYNAMIC_REGISTRY[name] = {
        "name": name,
        "params": model_dict.get("params", "Unknown"),
        "size_gb": float(model_dict.get("size_gb", 4.0)),
        "family": model_dict.get("family", "custom"),
        "desc": model_dict.get("desc", f"Local model {name}"),
        "context": int(model_dict.get("context", 8192)),
        "caps": model_dict.get("caps", ["chat"]),
        "categories": model_dict.get("categories", ["custom"]),
        "installed": bool(model_dict.get("installed", False)),
    }


def register_installed_models(installed_names: List[str]):
    """Ensure any locally installed model in Ollama is present in the catalog."""
    for raw_name in installed_names:
        name = raw_name.strip()
        if not name:
            continue
        # If already in curated catalog, mark as installed in memory
        existing = get_model(name)
        if not existing:
            # Estimate size / params from tag if possible
            params = "Unknown"
            size_gb = 4.0
            if ":" in name:
                tag = name.split(":")[-1].lower()
                if tag.endswith("b") and tag[:-1].replace(".", "").isdigit():
                    params = tag.upper()
                    try:
                        num = float(tag[:-1])
                        size_gb = round(num * 0.65, 1)
                    except Exception:
                        size_gb = 4.0

            register_custom_model({
                "name": name,
                "params": params,
                "size_gb": size_gb,
                "family": name.split(":")[0],
                "desc": f"Installed Ollama model: {name}",
                "context": 8192,
                "caps": ["chat"],
                "categories": ["installed"],
                "installed": True,
            })


def all_models(include_dynamic: bool = True) -> List[Dict[str, Any]]:
    """Return all catalog models, combining curated entries and dynamic/installed models."""
    combined: Dict[str, Dict[str, Any]] = {}
    for m in CURATED_CATALOG:
        combined[m["name"]] = dict(m)

    if include_dynamic:
        for name, m in DYNAMIC_REGISTRY.items():
            if name in combined:
                combined[name].update(m)
            else:
                combined[name] = dict(m)

    return list(combined.values())


# Compatibility alias for legacy callers
CATALOG = all_models()


def categories() -> List[str]:
    """Return list of standard navigation categories."""
    return ["all", "popular", "coding", "reasoning", "vision", "small", "large", "embedding"]


def search_models(
    query: str = "",
    category: Optional[str] = None,
    family: Optional[str] = None,
    cap: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search models with optional category, family, and capability filters."""
    q = (query or "").lower().strip()
    cat = (category or "").lower().strip()
    out = []

    for m in all_models(include_dynamic=True):
        if family and m.get("family") != family:
            continue
        if cap and cap not in m.get("caps", []):
            continue
        if cat and cat != "all":
            cats = [c.lower() for c in m.get("categories", [])]
            # Match either direct category list or family/caps
            if cat not in cats and cat not in m.get("caps", []) and cat != m.get("family"):
                continue
        if q:
            name_match = q in m.get("name", "").lower()
            fam_match = q in m.get("family", "").lower()
            desc_match = q in m.get("desc", "").lower()
            params_match = q in m.get("params", "").lower()
            if not (name_match or fam_match or desc_match or params_match):
                continue
        out.append(m)

    return out


def get_model(name: str) -> Optional[Dict[str, Any]]:
    """Look up a model by exact name or base prefix."""
    if not name:
        return None
    name_clean = name.strip()
    
    # Check dynamic first
    if name_clean in DYNAMIC_REGISTRY:
        return dict(DYNAMIC_REGISTRY[name_clean])

    # Check curated exact match
    for m in CURATED_CATALOG:
        if m["name"] == name_clean:
            return dict(m)

    # Check if tag omitted (e.g. "qwen2.5-coder" matches "qwen2.5-coder:7b" or latest)
    for m in CURATED_CATALOG:
        if m["name"].startswith(name_clean + ":") or m["name"] == f"{name_clean}:latest":
            return dict(m)

    return None
