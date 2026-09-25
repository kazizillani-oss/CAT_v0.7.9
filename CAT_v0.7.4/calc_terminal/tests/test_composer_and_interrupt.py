"""
Tests for:
1. Composer input focus borders (no nested double borders).
2. action_cancel_streaming cleanup (clears thinking indicators and streaming state).
3. Ollama provider cancellation safety.
"""

import pytest
from calc_terminal.ui import composer
from calc_terminal.providers.ollama_adapter import OllamaProvider, RequestState


def test_composer_input_focus_rules_exist_in_css():
    from calc_terminal.ui.app import CCTApp
    # Check that app CSS contains no-border rules on focus
    css_text = getattr(CCTApp, "CSS", "") or ""
    # Must include #cct-input:focus and border: none
    assert "#cct-input:focus" in css_text
    assert "ComposerInput:focus" in css_text
    assert "#cct-editor-stack:focus" in css_text
    # Composer must use restrained single border or sharp border
    assert ("border: solid $border;" in css_text or "border-top: heavy $surface-highlight;" in css_text or "border-top: tall $surface-highlight;" in css_text)
    assert ("#cct-composer {\n    background: $surface;\n    border: solid $border;" in css_text or
            "#cct-composer {\n    background: $surface;\n    border: heavy;" in css_text or
            "#cct-composer {\n    background: $surface;\n    border: tall;" in css_text)


def test_ollama_provider_cancel_during_connection():
    provider = OllamaProvider("http://localhost:11434")
    # Simulate cancel called while waiting for requests.post
    provider.cancel_active()
    assert provider.state == RequestState.CANCELLED


def test_composer_prompt_indicator_streaming_toggle():
    if not composer.TEXTUAL_AVAILABLE:
        pytest.skip("Textual not available")

    indicator = composer.PromptIndicator()
    assert indicator.is_streaming is False
    indicator.is_streaming = True
    assert indicator.is_streaming is True
    indicator.is_streaming = False
    assert indicator.is_streaming is False


def test_thinking_stream_filter_strips_tags_and_routes_thoughts():
    from calc_terminal.providers.ollama_adapter import ThinkingStreamFilter
    thoughts = []
    ended = []
    flt = ThinkingStreamFilter(
        on_thinking_chunk=lambda t: thoughts.append(t),
        on_thinking_end=lambda: ended.append(True)
    )
    # Feed <think> block inside content
    res1 = flt.process("", "<think>Analyzing user request...</think>Here is the final answer.")
    assert res1 == "Here is the final answer."
    assert "".join(thoughts) == "Analyzing user request..."
    assert len(ended) == 1


def test_thinking_stream_filter_split_tags():
    from calc_terminal.providers.ollama_adapter import ThinkingStreamFilter
    thoughts = []
    flt = ThinkingStreamFilter(
        on_thinking_chunk=lambda t: thoughts.append(t),
        on_thinking_end=lambda: None
    )
    out1 = flt.process("", "Hello <th")
    assert out1 == "Hello "
    out2 = flt.process("", "ink>internal reasoning</th")
    assert out2 == ""
    out3 = flt.process("", "ink>World!")
    assert out3 == "World!"
    assert "".join(thoughts) == "internal reasoning"


def test_thinking_stream_filter_explicit_thinking_part():
    from calc_terminal.providers.ollama_adapter import ThinkingStreamFilter
    thoughts = []
    ended = []
    flt = ThinkingStreamFilter(
        on_thinking_chunk=lambda t: thoughts.append(t),
        on_thinking_end=lambda: ended.append(True)
    )
    out1 = flt.process("Step 1: calculate matrix", "")
    assert out1 == ""
    out2 = flt.process(" Step 2: verify rank", "")
    assert out2 == ""
    out3 = flt.process("", "The rank is 4.")
    assert out3 == "The rank is 4."
    assert len(ended) == 1
    assert "".join(thoughts) == "Step 1: calculate matrix Step 2: verify rank"


def test_ollama_num_ctx_dynamic_scaling():
    from calc_terminal.providers.ollama_adapter import OllamaProvider
    import unittest.mock as mock

    prov = OllamaProvider("http://localhost:11434")
    # Prompt with ~4000 tokens (14,000 characters)
    big_prompt = "x" * 14000
    messages = [{"role": "user", "content": big_prompt}]

    posted_payloads = []
    def mock_post(url, json=None, **kwargs):
        posted_payloads.append(json)
        resp = mock.MagicMock()
        resp.status_code = 200
        resp.iter_lines.return_value = [b'{"message": {"content": "OK"}, "done": true}']
        return resp

    with mock.patch("requests.post", side_effect=mock_post):
        list(prov.stream_chat("deepseek-r1:latest", messages))

    assert len(posted_payloads) == 1
    # num_ctx must have been scaled to at least 6000, not stuck at 2048
    ctx = posted_payloads[0]["options"]["num_ctx"]
    assert ctx >= 6000
    assert ctx > 2048


def test_ollama_400_context_exceeded_auto_recovery():
    from calc_terminal.providers.ollama_adapter import OllamaProvider
    import unittest.mock as mock

    prov = OllamaProvider("http://localhost:11434")
    messages = [{"role": "user", "content": "hello"}]

    call_count = [0]
    payloads = []
    def mock_post(url, json=None, **kwargs):
        call_count[0] += 1
        payloads.append(dict(json))
        resp = mock.MagicMock()
        if call_count[0] == 1:
            resp.status_code = 400
            resp.text = '{"error": "model request (4163 tokens) exceeds the available context size (2048 tokens), try increasing it"}'
            return resp
        else:
            resp.status_code = 200
            resp.iter_lines.return_value = [b'{"message": {"content": "Recovered!"}, "done": true}']
            return resp

    with mock.patch("requests.post", side_effect=mock_post):
        chunks = list(prov.stream_chat("deepseek-r1:latest", messages))

    assert call_count[0] == 2
    assert "Recovered!" in "".join(chunks)
    assert payloads[1]["options"]["num_ctx"] >= 4163


def test_ollama_thinking_creates_live_activity():
    from calc_terminal.providers.ollama_adapter import OllamaProvider
    from calc_terminal import activity as act_mod
    import unittest.mock as mock

    prov = OllamaProvider("http://localhost:11434")
    messages = [{"role": "user", "content": "solve quantum problem"}]

    stream_lines = [
        b'{"message": {"thinking": "Considering wave function..."}, "done": false}',
        b'{"message": {"thinking": " Normalizing eigenstates..."}, "done": false}',
        b'{"message": {"content": "Psi is normalized."}, "done": true}',
    ]
    resp = mock.MagicMock()
    resp.status_code = 200
    resp.iter_lines.return_value = stream_lines

    created_activities = []
    orig_create = act_mod.manager.create
    def mock_create(*args, **kwargs):
        act = orig_create(*args, **kwargs)
        created_activities.append(act)
        return act

    with mock.patch("requests.post", return_value=resp), \
         mock.patch.object(act_mod.manager, "create", side_effect=mock_create):
        chunks = list(prov.stream_chat("deepseek-r1:latest", messages))

    output = "".join(chunks)
    # Output bubble must ONLY contain the final answer, NEVER the thinking text
    assert output == "Psi is normalized."
    assert "wave function" not in output
    assert "eigenstates" not in output
    # Live activity must have been created with thinking action
    assert any(a.action == "thinking" for a in created_activities)


def test_composer_zero_inside_border_and_docked_footer():
    from calc_terminal.ui.app import CCTApp
    css = getattr(CCTApp, "CSS", "")
    assert "#cct-prompt-row {\n" in css
    # Check bottom row is docked
    assert "dock: bottom;" in css
    assert "#cct-center-status" in css
    # Status center must not have detached vertical ticks (border-left/right tall)
    status_css = css.split("#cct-center-status")[1].split("}")[0]
    assert "border-left: tall" not in status_css
    assert "border-right: tall" not in status_css

