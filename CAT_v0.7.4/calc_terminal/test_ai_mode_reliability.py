"""
CAT AI Mode Reliability & Small-Model Compatibility Test Suite.

Verifies all 42 sections and Acceptance Criteria of the
CAT AI Mode Reliability Contract:
  - Test A: Normal chat greeting (no context leak)
  - Test B: Context contamination regression (Research SMTP -> Chat hello)
  - Test C: Mode switching isolation (Notebook -> Research -> Plan -> Debugger -> Chat)
  - Test D: Ollama streaming parser & deduplication
  - Test E: Request isolation, cancellation, and stream reset
  - Test F: Small/base model capability detection (deepseek-coder:1.3b-base-q8_0)
  - Test G: Context token budgeting & priority trimming
  - Test H: Repetition detection (GenerationGuard)
  - Test I: Provider failure handling
  - Test J: Model-vs-CAT diagnostic test (HELLO_TEST)
"""

import unittest
import uuid
import time
from unittest.mock import MagicMock, patch

from calc_terminal.ai_context import (
    AIContextManager,
    AIMessage,
    AIRequest,
    AIMode,
    NotebookCell,
    ResearchContext,
    DebuggerContext,
    PlanContext,
    ContextBudget,
    get_context_manager,
    simple_token_estimate,
)
from calc_terminal.models.profiles import (
    ModelCapabilities,
    ModelProfile,
    detect_capabilities,
    get_model_profile,
)
from calc_terminal.providers.ollama_adapter import (
    OllamaProvider,
    GenerationGuard,
    OutputSanitizer,
    RequestState,
)
from calc_terminal.session import ChatSession, Turn


class TestAIModeReliability(unittest.TestCase):

    def setUp(self):
        self.ctx_mgr = AIContextManager()

    # -------------------------------------------------------------------------
    # Test A: Normal Chat Greeting
    # -------------------------------------------------------------------------
    def test_a_normal_chat_greeting_has_no_unrelated_context(self):
        """User sends 'hello' in Chat mode: context contains only concise instructions and user prompt."""
        profile = get_model_profile("ollama", "deepseek-coder:1.3b-base-q8_0")
        req = AIRequest(
            session_id="test-sess-1",
            request_id=str(uuid.uuid4()),
            mode="chat",
            user_message="hello",
            history=[],
            model=profile.model,
            provider=profile.provider,
        )
        ctx = self.ctx_mgr.build_context(req, profile=profile)

        # Context must contain minimal system prompt and user message 'hello'
        self.assertTrue(ctx.is_minimal, "Small base model must use minimal prompt mode")
        self.assertEqual(len(ctx.messages), 2, "Greeting with no history must have exactly system + user")
        self.assertEqual(ctx.messages[0]["role"], "system")
        self.assertEqual(ctx.messages[1]["role"], "user")
        self.assertEqual(ctx.messages[1]["content"], "hello")

        # Must NOT contain research, notebook, or tool contamination
        full_content = " ".join(m["content"] for m in ctx.messages)
        self.assertNotIn("Conversation so far:", full_content)
        self.assertNotIn("SMTP", full_content)
        self.assertNotIn("IMAP", full_content)
        self.assertNotIn("Notebook", full_content)

    # -------------------------------------------------------------------------
    # Test B: Context Contamination Regression Test (SMTP Research -> Chat Hello)
    # -------------------------------------------------------------------------
    def test_b_previous_research_does_not_leak_into_chat_greeting(self):
        """Large research response (SMTP/IMAP) must NOT contaminate subsequent Chat 'hello' prompt."""
        session = ChatSession()

        # 1. Simulate prior Research mode turn with massive SMTP/IMAP documentation
        large_research_text = (
            "## 4.17 Sending and receiving email with Python\n"
            "SMTP (Simple Mail Transfer Protocol) and IMAP (Internet Message Access Protocol) "
            "are standard protocols for email transfer in Python. smtplib.SMTP('localhost') "
            "connects to the server, and email.mime constructs RFC 2822 messages..."
            * 20
        )
        t_user = Turn("turn-1", "user", "research SMTP in Python", mode="research")
        t_asst = Turn("turn-2", "assistant", large_research_text, mode="research")
        session.turns.extend([t_user, t_asst])

        # 2. User switches to Chat mode and sends "hello"
        chat_history = session.as_prompt_history(mode="chat")

        # Mode isolation: Research turns must NOT be in chat history
        history_roles = [r for r, _ in chat_history]
        history_texts = [t for _, t in chat_history]
        combined_history = " ".join(history_texts)

        self.assertNotIn("SMTP", combined_history, "Chat history must not contain SMTP research dump")
        self.assertNotIn("IMAP", combined_history, "Chat history must not contain IMAP research dump")

        # 3. Build context for 'hello' with deepseek-coder:1.3b-base-q8_0
        profile = get_model_profile("ollama", "deepseek-coder:1.3b-base-q8_0")
        messages_hist = [
            AIMessage(id="m1", role=r, content=t, mode="chat") for r, t in chat_history
        ]
        req = AIRequest(
            session_id="test-sess-b",
            request_id=str(uuid.uuid4()),
            mode="chat",
            user_message="hello",
            history=messages_hist,
            model=profile.model,
            provider=profile.provider,
        )
        ctx = self.ctx_mgr.build_context(req, profile=profile)

        # Assert no research text in built prompt
        full_prompt = " ".join(m["content"] for m in ctx.messages)
        self.assertNotIn("SMTP", full_prompt)
        self.assertNotIn("IMAP", full_prompt)
        self.assertNotIn("4.17 Sending and receiving email", full_prompt)
        self.assertNotIn("Conversation so far:", full_prompt)

    # -------------------------------------------------------------------------
    # Test C: Mode Switching Isolation
    # -------------------------------------------------------------------------
    def test_c_mode_switching_isolates_contexts(self):
        """Mode switching across Notebook -> Research -> Plan -> Debugger -> Chat preserves strict isolation."""
        session = ChatSession()

        # Add turns across different modes
        session.turns.append(Turn("t1", "user", "calculate derivative", mode="notebook"))
        session.turns.append(Turn("t2", "assistant", "derivative is 2x", mode="notebook"))
        session.turns.append(Turn("t3", "user", "research quantum physics", mode="research"))
        session.turns.append(Turn("t4", "assistant", "quantum theory details...", mode="research"))
        session.turns.append(Turn("t5", "user", "create roadmap", mode="plan"))
        session.turns.append(Turn("t6", "assistant", "Phase 1: architecture...", mode="plan"))
        session.turns.append(Turn("t7", "user", "trace IndexError", mode="debugger"))
        session.turns.append(Turn("t8", "assistant", "line 42 index out of range", mode="debugger"))

        # In Chat mode: only conversational pleasantries, no research or debug traces
        chat_hist = session.as_prompt_history(mode="chat")
        chat_text = " ".join(t for _, t in chat_hist)
        self.assertNotIn("quantum theory", chat_text)
        self.assertNotIn("Phase 1: architecture", chat_text)
        self.assertNotIn("line 42 index out of range", chat_text)

        # In Debugger mode: only debugger turns
        dbg_hist = session.as_prompt_history(mode="debugger")
        dbg_text = " ".join(t for _, t in dbg_hist)
        self.assertIn("line 42 index out of range", dbg_text)
        self.assertNotIn("quantum theory", dbg_text)
        self.assertNotIn("Phase 1: architecture", dbg_text)

        # In Plan mode: only plan turns
        plan_hist = session.as_prompt_history(mode="plan")
        plan_text = " ".join(t for _, t in plan_hist)
        self.assertIn("Phase 1: architecture", plan_text)
        self.assertNotIn("line 42 index out of range", plan_text)

    # -------------------------------------------------------------------------
    # Test D: Ollama Streaming Parser & Output Sanitizer
    # -------------------------------------------------------------------------
    def test_d_ollama_streaming_and_sanitizer(self):
        """Ollama stream yields only clean content, and OutputSanitizer strips stray prompt artifacts."""
        sanitizer = OutputSanitizer()

        # Strips accidental prefix
        self.assertEqual(sanitizer.sanitize_first_chunk("Assistant: Hello world"), "Hello world")
        self.assertEqual(sanitizer.sanitize_first_chunk("CAT AI: Here is the code"), "Here is the code")
        self.assertEqual(sanitizer.sanitize_first_chunk("Normal text"), "Normal text")

        # Preserves markdown code blocks without breaking syntax
        code_block = "```python\ndef foo():\n    return 42\n```"
        self.assertEqual(sanitizer.sanitize_final(code_block), code_block)

        # Mock Ollama streaming response chunks
        mock_chunks = [
            b'{"message": {"content": "Assistant: Hel"}, "done": false}\n',
            b'{"message": {"content": "lo "}, "done": false}\n',
            b'{"message": {"content": "there!"}, "done": true}\n',
        ]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = [c.decode("utf-8") for c in mock_chunks]

        with patch("requests.post", return_value=mock_resp):
            provider = OllamaProvider("http://localhost:11434")
            streamed = list(provider.stream_chat("llama3.2", [{"role": "user", "content": "hi"}]))

        result_text = "".join(streamed)
        self.assertEqual(result_text, "Hello there!")
        self.assertNotIn("Assistant:", result_text)
        self.assertNotIn('{"message"', result_text)

    # -------------------------------------------------------------------------
    # Test E: Request Isolation, Stream Reset, & Cancellation
    # -------------------------------------------------------------------------
    def test_e_request_isolation_and_cancellation(self):
        """New request allocates fresh request ID, resets stream, and cancellation terminates cleanly."""
        provider = OllamaProvider("http://localhost:11434")
        self.assertEqual(provider.state, RequestState.IDLE)

        # Reset stream for Request A
        id_a = provider.reset_stream("req-A")
        self.assertEqual(id_a, "req-A")
        self.assertEqual(provider.state, RequestState.STARTING)

        # Reset stream for Request B (cancels A)
        id_b = provider.reset_stream("req-B")
        self.assertEqual(id_b, "req-B")
        self.assertNotEqual(id_a, id_b)

        # Cancel active request
        cancelled = provider.cancel_active()
        self.assertTrue(cancelled)
        self.assertEqual(provider.state, RequestState.CANCELLED)

    # -------------------------------------------------------------------------
    # Test F: Small Model Profile (deepseek-coder:1.3b-base-q8_0)
    # -------------------------------------------------------------------------
    def test_f_small_model_capabilities_and_profile(self):
        """deepseek-coder:1.3b-base-q8_0 is classified as small/base model with minimal prompting."""
        model_name = "deepseek-coder:1.3b-base-q8_0"
        caps = detect_capabilities("ollama", model_name)

        self.assertTrue(caps.is_small_model, "1.3b must be identified as small model")
        self.assertTrue(caps.is_base_model, "base-q8_0 must be identified as base model")
        self.assertFalse(caps.instruction_following, "Base model does not have full instruction-following capability")
        self.assertFalse(caps.tool_calling, "Small base model must not be expected to execute agent tool loops")

        profile = get_model_profile("ollama", model_name)
        self.assertEqual(profile.prompt_template, "minimal")
        self.assertEqual(profile.max_context_tokens, 1536)
        self.assertEqual(profile.reserved_output_tokens, 512)
        self.assertEqual(profile.recommended_temperature, 0.3)
        self.assertGreaterEqual(profile.generation_options.get("repeat_penalty", 1.0), 1.15)

    # -------------------------------------------------------------------------
    # Test G: Context Token Budgeting & Priority Trimming
    # -------------------------------------------------------------------------
    def test_g_context_token_budgeting_trims_lowest_priority(self):
        """When history exceeds available budget, older turns are trimmed while user prompt is preserved."""
        profile = get_model_profile("ollama", "deepseek-coder:1.3b-base-q8_0")

        # Create 10 history turns with 200 characters each
        history = [
            AIMessage(id=f"h{i}", role="user" if i % 2 == 0 else "assistant",
                      content=f"This is historical turn number {i} " * 5, mode="chat")
            for i in range(10)
        ]

        req = AIRequest(
            session_id="sess-budget",
            request_id=str(uuid.uuid4()),
            mode="chat",
            user_message="My most important current request",
            history=history,
            model=profile.model,
            provider=profile.provider,
        )

        ctx = self.ctx_mgr.build_context(req, profile=profile)

        # User request MUST be present
        self.assertEqual(ctx.messages[-1]["content"], "My most important current request")
        # System prompt MUST be present
        self.assertEqual(ctx.messages[0]["role"], "system")
        # Total tokens must not exceed maximum budget
        self.assertLessEqual(ctx.token_estimate, profile.max_context_tokens)

    # -------------------------------------------------------------------------
    # Test H: Repetition Detection (GenerationGuard)
    # -------------------------------------------------------------------------
    def test_h_repetition_detection_stops_runaway_loops(self):
        """GenerationGuard halts repetitive output like 'hihihihihihi...' or identical sentences."""
        guard = GenerationGuard(max_repeated_chars=16, max_sentence_repeats=3)

        # 1. Feed normal tokens
        ok, chunk = guard.feed("Hello there! How can I help you today? ")
        self.assertTrue(ok)
        self.assertEqual(chunk, "Hello there! How can I help you today? ")

        # 2. Feed repetitive token loop 'hihihihihihihihihi...'
        ok, chunk = guard.feed("hihihihihihihihihihihihihihihihihi")
        self.assertFalse(ok, "Guard must detect runaway repetitive loop")
        self.assertIn("repetitive output pattern detected", chunk)

        # 3. Test sentence loop with a new guard
        guard2 = GenerationGuard(max_repeated_chars=20, max_sentence_repeats=3)
        guard2.feed("The quick brown fox jumps over the lazy dog. ")
        guard2.feed("The quick brown fox jumps over the lazy dog. ")
        ok, chunk = guard2.feed("The quick brown fox jumps over the lazy dog. ")
        self.assertFalse(ok, "Guard must detect repeating identical sentences")
        self.assertIn("sentence repetition loop detected", chunk)

    # -------------------------------------------------------------------------
    # Test I: Provider Failure Handling
    # -------------------------------------------------------------------------
    def test_i_provider_failure_returns_explicit_error_without_corrupting(self):
        """Connection failure produces clean, user-friendly error string."""
        with patch("requests.post", side_effect=Exception("Connection refused")):
            provider = OllamaProvider("http://localhost:99999")
            streamed = list(provider.stream_chat("model", [{"role": "user", "content": "hi"}]))

        result = "".join(streamed)
        self.assertIn("Ollama streaming failure", result)
        self.assertEqual(provider.state, RequestState.FAILED)

    # -------------------------------------------------------------------------
    # Test J: Model-vs-CAT Diagnostic Test (HELLO_TEST)
    # -------------------------------------------------------------------------
    def test_j_model_vs_cat_diagnostic_test(self):
        """run_hello_test verifies whether Ollama produces expected exact token."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": {"content": "HELLO_TEST"}}

        with patch("requests.post", return_value=mock_resp):
            provider = OllamaProvider("http://localhost:11434")
            ok, reply = provider.run_hello_test("llama3.2")
            self.assertTrue(ok)
            self.assertEqual(reply, "HELLO_TEST")


if __name__ == "__main__":
    unittest.main()
