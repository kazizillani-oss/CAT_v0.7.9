"""Pure metadata helpers for the Fatty CAT provider center."""

from typing import List, Set


def provider_center_categories(provider: dict, popular_ids: Set[str]) -> List[str]:
    """Return honest, catalog-backed provider-center filter tags."""
    pid = str(provider.get("id", "")).lower()
    tags: List[str] = []
    if pid == "ollama":
        tags.append("local")
    if provider.get("free_models_available") or not provider.get("needs_key", True):
        tags.append("free")
    if pid in popular_ids:
        tags.append("popular")
    if provider.get("supports_reasoning"):
        tags.append("reasoning")
    if provider.get("supports_vision"):
        tags.extend(["vision", "multimodal"])
    if provider.get("supports_audio"):
        tags.append("multimodal")
    description = f"{provider.get('name', '')} {provider.get('description', '')}".lower()
    if any(term in description for term in ("code", "coding", "developer", "programming")):
        tags.append("coding")
    if pid in {"groq", "cerebras", "sambanova", "together", "fireworks", "deepinfra"}:
        tags.append("fast")
    return list(dict.fromkeys(tags))
