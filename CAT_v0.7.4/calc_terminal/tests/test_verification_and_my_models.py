import pytest
from calc_terminal.models.verification_engine import get_verification_engine, VerificationResult
from calc_terminal.model import MyModelsScreen
from textual.app import App
from calc_terminal.ui.theme_css import css_variables


def test_get_verification_engine_factory():
    engine = get_verification_engine()
    assert engine is not None
    # Dict call
    res = engine.verify_custom_model({"provider_id": "ollama", "model_id": "deepseek-r1:latest"})
    assert isinstance(res, VerificationResult)
    assert res.get("status") is not None
    assert res["status"] == res.status
    assert hasattr(res, "success")


class _AppWithTheme(App):
    def get_css_variables(self):
        v = dict(super().get_css_variables())
        v.update(css_variables())
        return v


@pytest.mark.anyio
async def test_my_models_screen_mount_and_no_index_error():
    app = _AppWithTheme()
    async with app.run_test() as pilot:
        await app.push_screen(MyModelsScreen())
        await pilot.pause(0.2)
        screen = app.screen
        assert isinstance(screen, MyModelsScreen)
        assert isinstance(screen._models_list, list)


def test_nvidia_nemotron_model_resolution():
    from calc_terminal.aicore import _normalize_provider_model
    from calc_terminal.providers.lifecycle import _MODEL_ALIASES

    # Canonical resolutions
    ultra = "nvidia/nemotron-3-ultra-550b-a55b"
    lightning = "nvidia/nemotron-3.5-lightning-30b-a3b"

    assert _normalize_provider_model("nvidia", "nemotron-3-ultra", "https://integrate.api.nvidia.com/v1") == ultra
    assert _normalize_provider_model("nvidia", "3-ultra", "https://integrate.api.nvidia.com/v1") == ultra
    assert _normalize_provider_model("nvidia", "nemotron 3 ultra", "https://integrate.api.nvidia.com/v1") == ultra
    assert _normalize_provider_model("nvidia", "nemotron-3.5-lightning", "https://integrate.api.nvidia.com/v1") == lightning
    assert _normalize_provider_model("nvidia", "3.5-lightning", "https://integrate.api.nvidia.com/v1") == lightning
    assert _normalize_provider_model("nvidia", "3.5 lightning ai", "https://integrate.api.nvidia.com/v1") == lightning

    # Lifecycle table checks
    assert _MODEL_ALIASES.get(("nvidia", "nemotron-3-ultra")) == ultra
    assert _MODEL_ALIASES.get(("nvidia", "3.5-lightning")) == lightning


def test_nvidia_nemotron_metadata_and_providers_config():
    import json
    import os

    meta_path = os.path.join(os.path.dirname(__file__), "..", "models", "model_metadata.json")
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    models_list = meta.get("models", [])
    aliases_list = meta.get("aliases", [])

    models_map = {m["id"]: m for m in models_list if "id" in m}
    aliases_map = {a["from"]: a["to"] for a in aliases_list if "from" in a}

    ultra = "nvidia/nemotron-3-ultra-550b-a55b"
    lightning = "nvidia/nemotron-3.5-lightning-30b-a3b"

    assert ultra in models_map
    assert lightning in models_map
    assert models_map[ultra]["context_length"] == 131072
    assert models_map[lightning]["context_length"] == 131072

    assert aliases_map.get("nemotron-3-ultra") == ultra
    assert aliases_map.get("3.5-lightning") == lightning

    prov_path = os.path.join(os.path.dirname(__file__), "..", "providers", "providers.json")
    with open(prov_path, "r", encoding="utf-8") as f:
        prov = json.load(f)

    providers_list = prov.get("providers", [])
    nvidia_cfg = next((p for p in providers_list if p.get("id") == "nvidia"), {})
    fallback_models = nvidia_cfg.get("fallback_models", [])
    assert ultra in fallback_models
    assert lightning in fallback_models
    assert nvidia_cfg.get("default_model") == ultra

