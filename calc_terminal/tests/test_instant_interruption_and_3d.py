"""
Automated unit and integration tests for:
1. Instant chat interruption (clicking pause ⏸ / double pressing Esc)
2. Interruption notice / error rendering
3. 3D chat bubbles
4. Redesigned BackupProvidersPanel layout and rendering
"""

import pytest
import time
from unittest.mock import MagicMock, patch
from rich.console import Console

from calc_terminal.ui.conversation import ConversationItem, MessageRow, _bevel_colors
from calc_terminal.ui.backup_panel import BackupProvidersPanel, _ProviderCard
from calc_terminal.providers.ollama_adapter import OllamaProvider, RequestState
from calc_terminal import aicore


def test_ollama_adapter_cancellation_and_registration():
    prov = OllamaProvider("http://localhost:11434")
    assert prov.state == RequestState.IDLE
    
    # Check registration mechanism
    aicore._register_provider(prov)
    assert prov in aicore._ACTIVE_PROVIDERS
    
    # Cancel active
    prov.cancel_active()
    assert prov.state == RequestState.CANCELLED
    
    # Unregister
    aicore._unregister_provider(prov)
    assert prov not in aicore._ACTIVE_PROVIDERS


def test_aicore_cancel_active_requests_calls_provider_cancel():
    mock_prov = MagicMock()
    mock_prov.cancel_active = MagicMock()
    aicore._register_provider(mock_prov)
    try:
        count = aicore.cancel_active_requests()
        assert count >= 1
        mock_prov.cancel_active.assert_called_once()
    finally:
        aicore._unregister_provider(mock_prov)


@pytest.mark.anyio
async def test_3d_bubble_styling_and_hover():
    from textual.app import App, ComposeResult
    
    class BubbleApp(App):
        def compose(self) -> ComposeResult:
            yield ConversationItem("turn-u1", "user", "What is quantum entanglement?", mode_snapshot={"accent_hex": "#38bdf8", "icon": "📓", "label": "Notebook"})
            yield ConversationItem("turn-a1", "assistant", "Quantum entanglement is a phenomenon...", mode_snapshot={"accent_hex": "#38bdf8", "icon": "🤖", "label": "Notebook"})

    app = BubbleApp()
    async with app.run_test(size=(100, 30)) as pilot:
        user_item = pilot.app.screen.query(ConversationItem)[0]
        asst_item = pilot.app.screen.query(ConversationItem)[1]
        
        # User bubble has 3D bevel borders
        assert user_item.styles.border_top[0] in ("tall", "round", "heavy")
        assert user_item.styles.border_bottom[0] in ("tall", "heavy")
        assert user_item.styles.border_top[1].hex.lower() != "#000000"
        assert user_item.styles.border_bottom[1].hex.lower() != "#000000"
        
        # Assistant bubble has 3D bevel borders
        assert asst_item.styles.border_top[0] in ("tall", "round", "heavy")
        assert asst_item.styles.border_bottom[0] in ("tall", "heavy")
        
        # Hover elevation changes top border to luminous highlight
        await pilot.hover(user_item)
        await pilot.pause(0.05)
        assert user_item.styles.border_top[1].hex.lower() == "#ffffff"


@pytest.mark.anyio
async def test_instant_interruption_in_app():
    from calc_terminal.ui.app import CCTApp
    
    app = CCTApp(MagicMock(), [], MagicMock())
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        if type(app.screen).__name__ == "WelcomeModal":
            app.pop_screen()
            await pilot.pause()
            
        # Simulate active assistant turn in flight
        tid = "turn-interrupt-test"
        item = app.conversation.start_streaming(tid, "assistant")
        item.append_chunk("Partial thought...")
        app._is_streaming = True
        app._streaming_turn_id = tid
        app.composer.set_streaming(True, turn_id=tid)
        
        # Verify initial streaming state
        assert app.composer.prompt_indicator.is_streaming is True
        send_btn = app.composer.query_one("#btn-send")
        assert send_btn.label == "⏸"
        
        # Trigger interruption via action_cancel_streaming (same as ⏸ click or double Esc)
        app.action_cancel_streaming()
        await pilot.pause(0.1)
        
        # Verify immediate state reset
        assert app._is_streaming is False
        assert app.composer.prompt_indicator.is_streaming is False
        assert send_btn.label != "⏸"
        
        # Verify interrupted message rendered on bubble
        assert "interrupted by user" in item._text.lower()
        assert "⚠️" in item._text


@pytest.mark.anyio
async def test_backup_providers_panel_3d_render():
    from calc_terminal.ui.app import CCTApp
    
    app = CCTApp(MagicMock(), [], MagicMock())
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        if type(app.screen).__name__ == "WelcomeModal":
            app.pop_screen()
            await pilot.pause()
            
        panel = BackupProvidersPanel()
        await app.push_screen(panel)
        await pilot.pause(0.1)
        
        # Verify box and cards mounted
        box = panel.query_one("#bpp-box")
        assert box is not None
        assert box.styles.border_top[0] == "tall"
        
        # Check add buttons and action buttons exist and are styled
        add_btn = panel.query_one("#bpp-add")
        assert add_btn is not None
        save_btn = panel.query_one("#bpp-save")
        assert save_btn is not None
        
        cards = panel.query(_ProviderCard)
        for c in cards:
            assert c.styles.border_top[0] == "tall"
            assert c.styles.border_bottom[0] == "tall"


@pytest.mark.anyio
async def test_double_escape_and_pause_button_interruption():
    from calc_terminal.ui.app import CCTApp
    
    app = CCTApp(MagicMock(), [], MagicMock())
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        if type(app.screen).__name__ == "WelcomeModal":
            app.pop_screen()
            await pilot.pause()
            
        # 1. Test clicking pause ⏸ button
        tid1 = "turn-pause-click"
        item1 = app.conversation.start_streaming(tid1, "assistant")
        item1.append_chunk("Thinking...")
        app._is_streaming = True
        app._streaming_turn_id = tid1
        app.composer.set_streaming(True, turn_id=tid1)
        
        send_btn = app.composer.query_one("#btn-send")
        assert send_btn.label == "⏸"
        
        # Click ⏸
        send_btn.press()
        await pilot.pause(0.1)
        
        assert app._is_streaming is False
        assert app.composer.prompt_indicator.is_streaming is False
        assert send_btn.label != "⏸"
        assert "interrupted by user" in item1._text.lower()
        
        # 2. Test pressing Escape while streaming
        tid2 = "turn-esc-press"
        item2 = app.conversation.start_streaming(tid2, "assistant")
        item2.append_chunk("Generating response...")
        app._is_streaming = True
        app._streaming_turn_id = tid2
        app.composer.set_streaming(True, turn_id=tid2)
        
        assert send_btn.label == "⏸"
        
        # Press Escape
        await pilot.press("escape")
        await pilot.pause(0.1)
        
        assert app._is_streaming is False
        assert app.composer.prompt_indicator.is_streaming is False
        assert "interrupted by user" in item2._text.lower()

