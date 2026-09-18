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
