import unittest
from unittest.mock import MagicMock
from calc_terminal.model import (
    ProviderScreen, ModelScreen, ApiKeyScreen, VerifyScreen,
    MyModelsScreen, AddCustomModelScreen, ModelConfirmModal,
    _finish_wizard_screen
)
from calc_terminal.models.active_state import get_active_state, set_active_ai

class TestScreenDismissal(unittest.TestCase):
    def test_finish_wizard_screen_in_cctapp(self):
        class MockCCTApp:
            def __init__(self):
                self.exited = False
                self.dismissed = False
                self.popped = False
                self.screens = []
            def exit(self, result=None):
                self.exited = True
            def pop_screen(self):
                self.popped = True

        mock_app = MockCCTApp()
        mock_screen = MagicMock()
        mock_screen.app = mock_app

        config = {"provider": "ollama", "model": "deepseek-r1:latest"}
        _finish_wizard_screen(mock_screen, config)

        self.assertFalse(mock_app.exited, "CCTApp must NEVER be exited by _finish_wizard_screen")
        mock_screen.dismiss.assert_called_once_with(config)
        
        # Verify active state was set
        active = get_active_state()
        self.assertEqual(active.provider_id, "ollama")
        self.assertEqual(active.model_id, "deepseek-r1:latest")

    def test_screen_callbacks_chain(self):
        sample_prov = {
            "id": "ollama",
            "name": "Ollama",
            "needs_key": False,
            "models": ["deepseek-r1:latest"],
            "url": "http://localhost:11434",
            "api_style": "ollama",
        }
        prov_screen = ProviderScreen(embedded=True)
        model_screen = ModelScreen(sample_prov, embedded=True)
        
        # Test ProviderScreen._on_subscreen_closed
        prov_screen.dismiss = MagicMock()
        mock_cct_app = MagicMock()
        mock_cct_app.__class__.__name__ = "CCTApp"
        prov_screen._app = mock_cct_app
        
        selected_cfg = {"provider": "ollama", "model": "deepseek-r1:latest"}
        prov_screen._on_subscreen_closed(selected_cfg)
        
        # Verify prov_screen dismissed with selected_cfg and did NOT call app.exit
        prov_screen.dismiss.assert_called_once_with(selected_cfg)
        self.assertFalse(mock_cct_app.exit.called, "mock_cct_app.exit must not be called")

    def test_model_screen_confirm_closed(self):
        sample_prov = {
            "id": "ollama",
            "name": "Ollama",
            "needs_key": False,
            "models": ["deepseek-r1:latest"],
            "url": "http://localhost:11434",
            "api_style": "ollama",
        }
        model_screen = ModelScreen(sample_prov, embedded=True)
        model_screen.dismiss = MagicMock()
        mock_app = MagicMock()
        mock_app.__class__.__name__ = "CCTApp"
        model_screen._app = mock_app

        selected_cfg = {"provider": "ollama", "model": "deepseek-r1:latest"}
        model_screen._on_confirm_closed(selected_cfg)
        model_screen.dismiss.assert_called_once_with(selected_cfg)
        self.assertFalse(mock_app.exit.called)

    def test_model_confirm_modal_apply(self):
        cfg = {"provider": "ollama", "model": "deepseek-r1:latest"}
        modal = ModelConfirmModal("ollama", "deepseek-r1:latest", cfg)
        modal.dismiss = MagicMock()
        modal.action_apply()
        modal.dismiss.assert_called_once_with(cfg)
        active = get_active_state()
        self.assertEqual(active.provider_id, "ollama")
        self.assertEqual(active.model_id, "deepseek-r1:latest")

if __name__ == "__main__":
    unittest.main()
