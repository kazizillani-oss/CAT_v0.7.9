"""Test suite for the v0.7 overhaul modules."""

import json
import os
import sys
import shutil
import tempfile
import time
import threading
import unittest

# Add parent directory so calc_terminal is importable as a package
_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from calc_terminal.tool_call_normalizer import (
    ToolCall,
    normalize_tool_calls,
    extract_final_answer,
    is_tool_call_response,
    _find_balanced_json,
)
from calc_terminal.memory_v2 import MemoryManager, Memory, _sanitize_content, VALID_CATEGORIES
from calc_terminal.event_stream import EventStream, Event, MODEL_RESPONSE, TOOL_REQUEST
from calc_terminal.agent_runtime import AgentRuntime
from calc_terminal.collaboration import FileLockManager, CollaborationContext


class TestToolCallNormalizer(unittest.TestCase):

    def test_empty_input(self):
        self.assertEqual(normalize_tool_calls(""), [])
        self.assertEqual(normalize_tool_calls(None), [])

    def test_json_protocol_tool_args(self):
        text = '{"action": "tool", "tool": "calc", "args": {"expr": "2+2"}}'
        calls = normalize_tool_calls(text, known_tools=["calc"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].name, "calc")
        self.assertEqual(calls[0].arguments["expr"], "2+2")
        self.assertEqual(calls[0].source_format, "json_protocol")
        self.assertAlmostEqual(calls[0].confidence, 0.95)

    def test_json_protocol_tool_parameters(self):
        text = '{"action": "tool", "tool": "search", "parameters": {"query": "hello"}}'
        calls = normalize_tool_calls(text, known_tools=["search"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].name, "search")
        self.assertEqual(calls[0].arguments["query"], "hello")

    def test_json_name_arguments_format(self):
        text = '{"name": "write_file", "arguments": {"path": "/tmp/x.py", "content": "print()"}}'
        calls = normalize_tool_calls(text, known_tools=["write_file"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].name, "write_file")
        self.assertEqual(calls[0].arguments["path"], "/tmp/x.py")

    def test_unknown_tool_filtered(self):
        text = '{"action": "tool", "tool": "nonexistent", "args": {}}'
        calls = normalize_tool_calls(text, known_tools=["calc"])
        self.assertEqual(len(calls), 0)

    def test_xml_minimax_toolcall(self):
        text = ('<minimax:toolcall>\n'
                '  <tool_name>calc</tool_name>\n'
                '  <parameters>{"expr": "3*7"}</parameters>\n'
                '</minimax:toolcall>')
        calls = normalize_tool_calls(text, known_tools=["calc"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].name, "calc")
        self.assertEqual(calls[0].arguments["expr"], "3*7")
        self.assertIn("xml", calls[0].source_format)

    def test_xml_tool_call_tag(self):
        text = '<tool_call>\n<name>search</name>\n<arguments>{"q": "test"}</arguments>\n</tool_call>'
        calls = normalize_tool_calls(text, known_tools=["search", "search_workspace"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].name, "search_workspace")

    def test_xml_invoke(self):
        text = '<invoke name="calc"><parameters>{"expr": "1+1"}</parameters></invoke>'
        calls = normalize_tool_calls(text, known_tools=["calc"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].name, "calc")

    def test_function_call_syntax(self):
        text = 'calc(expr="2+3")'
        calls = normalize_tool_calls(text, known_tools=["calc"])
        self.assertTrue(len(calls) >= 1)
        self.assertEqual(calls[0].name, "calc")

    def test_heuristic_fallback(self):
        text = 'Please use calc with {"expr": "5*5"}'
        calls = normalize_tool_calls(text, known_tools=["calc"])
        self.assertTrue(len(calls) >= 1)
        self.assertEqual(calls[0].name, "calc")

    def test_deduplication(self):
        text = ('{"action": "tool", "tool": "calc", "args": {"expr": "1"}}\n'
                '{"action": "tool", "tool": "calc", "args": {"expr": "1"}}')
        calls = normalize_tool_calls(text, known_tools=["calc"])
        self.assertEqual(len(calls), 1)

    def test_sorted_by_confidence(self):
        text = ('{"action": "tool", "tool": "calc", "args": {"expr": "1"}}\n'
                'calc(expr="1")')
        calls = normalize_tool_calls(text, known_tools=["calc"])
        if len(calls) >= 2:
            self.assertGreaterEqual(calls[0].confidence, calls[1].confidence)

    def test_extract_final_answer_pattern(self):
        self.assertEqual(extract_final_answer("The answer is 42."), "42")
        self.assertEqual(extract_final_answer("RESULT: 99"), "99")
        self.assertIsNone(extract_final_answer(""))

    def test_extract_final_answer_long_text(self):
        long_text = "x" * 600
        self.assertIsNone(extract_final_answer(long_text))

    def test_is_tool_call_response_true(self):
        self.assertTrue(is_tool_call_response('{"tool": "calc"}'))
        self.assertTrue(is_tool_call_response('<minimax:toolcall>'))
        self.assertTrue(is_tool_call_response('<tool_call>'))
        self.assertTrue(is_tool_call_response('<invoke name="x">'))

    def test_is_tool_call_response_false(self):
        self.assertFalse(is_tool_call_response(""))
        self.assertFalse(is_tool_call_response(None))
        self.assertFalse(is_tool_call_response("Hello world, no tools here."))

    def test_find_balanced_json(self):
        result = _find_balanced_json('prefix {"a": 1} suffix', 7)
        self.assertEqual(result, '{"a": 1}')

    def test_find_balanced_json_no_brace(self):
        result = _find_balanced_json("no braces", 0)
        self.assertIsNone(result)

    def test_tool_call_dataclass_defaults(self):
        tc = ToolCall()
        self.assertTrue(tc.id)
        self.assertEqual(tc.name, "")
        self.assertEqual(tc.arguments, {})


class TestMemoryV2(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="cct_test_mem_")
        self.mm = MemoryManager(memory_dir=self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_sanitize_api_key(self):
        raw = "api_key = sk-abcdefghijklmnop1234"
        result = _sanitize_content(raw)
        self.assertNotIn("sk-abcdefghijklmnop1234", result)
        self.assertIn("[REDACTED]", result)

    def test_sanitize_bearer_token(self):
        raw = "bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abcdef"
        result = _sanitize_content(raw)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abcdef", result)

    def test_sanitize_clean_text(self):
        raw = "Just a normal sentence with no secrets."
        self.assertEqual(_sanitize_content(raw), raw)

    def test_valid_categories(self):
        self.assertIn("user_preferences", VALID_CATEGORIES)
        self.assertIn("project_facts", VALID_CATEGORIES)
        self.assertIn("custom", VALID_CATEGORIES)
        self.assertEqual(len(VALID_CATEGORIES), 8)

    def test_session_add_and_retrieve(self):
        self.mm.add_session_turn("user", "Hello", mode="chat")
        self.mm.add_session_turn("assistant", "Hi there", mode="chat")
        ctx = self.mm.get_session_context(max_turns=10)
        self.assertEqual(len(ctx), 2)
        self.assertEqual(ctx[0]["role"], "user")
        self.assertEqual(ctx[1]["role"], "assistant")

    def test_session_max_turns(self):
        for i in range(5):
            self.mm.add_session_turn("user", f"msg {i}")
        ctx = self.mm.get_session_context(max_turns=3)
        self.assertEqual(len(ctx), 3)
        self.assertEqual(ctx[0]["text"], "msg 2")

    def test_session_clear(self):
        self.mm.add_session_turn("user", "test")
        self.mm.clear_session()
        self.assertEqual(self.mm.get_session_context(), [])

    def test_store_and_retrieve_memory(self):
        mem = self.mm.store_memory("conversation_facts", "User prefers Python")
        self.assertTrue(mem.id)
        self.assertEqual(mem.category, "conversation_facts")
        self.assertEqual(mem.content, "User prefers Python")
        retrieved = self.mm.retrieve_memories(limit=10)
        self.assertEqual(len(retrieved), 1)
        self.assertEqual(retrieved[0].id, mem.id)

    def test_store_memory_sanitize(self):
        mem = self.mm.store_memory("custom", "api_key = secret123456789012345")
        self.assertNotIn("secret123456789012345", mem.content)
        self.assertIn("[REDACTED]", mem.content)

    def test_invalid_category_raises(self):
        with self.assertRaises(ValueError):
            self.mm.store_memory("invalid_category", "test")

    def test_delete_memory(self):
        mem = self.mm.store_memory("custom", "to delete")
        self.assertTrue(self.mm.delete_memory(mem.id))
        self.assertEqual(self.mm.delete_memory(mem.id), False)

    def test_search_memories(self):
        self.mm.store_memory("conversation_facts", "User likes blue color")
        self.mm.store_memory("conversation_facts", "User likes red color")
        self.mm.store_memory("custom", "Unrelated fact")
        results = self.mm.search_memories("blue")
        self.assertEqual(len(results), 1)
        self.assertIn("blue", results[0].content)

    def test_get_memories_by_category(self):
        self.mm.store_memory("custom", "c1")
        self.mm.store_memory("custom", "c2")
        self.mm.store_memory("conversation_facts", "f1")
        customs = self.mm.get_memories_by_category("custom")
        self.assertEqual(len(customs), 2)

    def test_update_memory(self):
        mem = self.mm.store_memory("custom", "original")
        updated = self.mm.update_memory(mem.id, content="updated", importance=0.9)
        self.assertIsNotNone(updated)
        self.assertEqual(updated.content, "updated")
        self.assertAlmostEqual(updated.importance, 0.9)

    def test_update_invalid_category_raises(self):
        mem = self.mm.store_memory("custom", "test")
        with self.assertRaises(ValueError):
            self.mm.update_memory(mem.id, category="bogus")

    def test_deduplicate(self):
        self.mm.store_memory("custom", "the quick brown fox jumps")
        self.mm.store_memory("custom", "the quick brown fox jumps")
        removed = self.mm.deduplicate()
        self.assertEqual(removed, 1)
        remaining = self.mm.get_all_memories()
        self.assertEqual(len(remaining), 1)

    def test_project_memory_store_and_get(self):
        self.mm.store_project_fact("/test/project", "Uses pytest", category="testing")
        facts = self.mm.get_project_context("/test/project")
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["fact"], "Uses pytest")
        self.assertEqual(facts[0]["category"], "testing")

    def test_project_memory_clear(self):
        self.mm.store_project_fact("/test/project", "fact1")
        self.mm.store_project_fact("/test/project", "fact2")
        self.mm.clear_project_memory("/test/project")
        facts = self.mm.get_project_context("/test/project")
        self.assertEqual(len(facts), 0)

    def test_context_block(self):
        self.mm.add_session_turn("user", "Hello")
        self.mm.store_memory("conversation_facts", "User likes testing")
        block = self.mm.context_block()
        self.assertIn("Recent Session", block)
        self.assertIn("Long-term Memories", block)

    def test_context_block_with_project(self):
        self.mm.store_project_fact("/proj", "Uses Flask")
        block = self.mm.context_block(project_path="/proj")
        self.assertIn("Project Facts", block)

    def test_memory_dataclass_to_dict(self):
        mem = Memory(category="custom", content="test data")
        d = mem.to_dict()
        self.assertEqual(d["category"], "custom")
        self.assertEqual(d["content"], "test data")

    def test_memory_from_dict(self):
        d = {"category": "custom", "content": "from dict", "importance": 0.8}
        mem = Memory.from_dict(d)
        self.assertEqual(mem.content, "from dict")
        self.assertAlmostEqual(mem.importance, 0.8)


class TestEventStream(unittest.TestCase):

    def setUp(self):
        self.es = EventStream()

    def test_emit_and_get_recent(self):
        self.es.emit("test_event", source="unit", msg="hello")
        events = self.es.get_recent("test_event")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "test_event")
        self.assertEqual(events[0].data["msg"], "hello")
        self.assertEqual(events[0].source, "unit")

    def test_emit_returns_event(self):
        ev = self.es.emit("x")
        self.assertIsInstance(ev, Event)
        self.assertGreater(ev.timestamp, 0)

    def test_subscribe_receives_events(self):
        received = []
        self.es.subscribe("test_event", lambda e: received.append(e))
        self.es.emit("test_event")
        self.es.emit("other_event")
        self.assertEqual(len(received), 1)

    def test_unsubscribe(self):
        received = []
        cb = lambda e: received.append(e)
        self.es.subscribe("test_event", cb)
        self.es.emit("test_event")
        self.es.unsubscribe("test_event", cb)
        self.es.emit("test_event")
        self.assertEqual(len(received), 1)

    def test_get_recent_no_filter(self):
        self.es.emit("a")
        self.es.emit("b")
        self.es.emit("c")
        all_ev = self.es.get_recent()
        self.assertEqual(len(all_ev), 3)

    def test_get_recent_limit(self):
        for i in range(10):
            self.es.emit("e")
        recent = self.es.get_recent(limit=3)
        self.assertEqual(len(recent), 3)

    def test_get_all_filtered(self):
        self.es.emit("a")
        self.es.emit("b")
        self.es.emit("a")
        a_events = self.es.get_all("a")
        self.assertEqual(len(a_events), 2)

    def test_clear(self):
        self.es.emit("a")
        self.es.emit("b")
        self.es.clear()
        self.assertEqual(self.es.get_recent(), [])

    def test_subscriber_count(self):
        self.es.subscribe("a", lambda e: None)
        self.es.subscribe("a", lambda e: None)
        self.es.subscribe("b", lambda e: None)
        self.assertEqual(self.es.subscriber_count("a"), 2)
        self.assertEqual(self.es.subscriber_count(), 3)

    def test_subscriber_error_does_not_crash(self):
        def bad_callback(e):
            raise RuntimeError("boom")
        self.es.subscribe("test", bad_callback)
        event = self.es.emit("test")
        self.assertIsNotNone(event)

    def test_multiple_data_kwargs(self):
        self.es.emit("calc", x=1, y=2, z=3)
        ev = self.es.get_recent("calc")[0]
        self.assertEqual(ev.data["x"], 1)
        self.assertEqual(ev.data["z"], 3)


class TestAgentRuntime(unittest.TestCase):

    def test_init(self):
        tools = {"calc": {"run": lambda a: "42"}}
        ar = AgentRuntime(tools, max_steps=5)
        self.assertEqual(ar.tools, tools)
        self.assertEqual(ar.max_steps, 5)

    def test_init_defaults(self):
        ar = AgentRuntime({})
        self.assertEqual(ar.max_steps, 18)

    def test_build_prompt(self):
        ar = AgentRuntime({})
        convo = [
            {"role": "user", "text": "What is 2+2?"},
            {"role": "assistant", "text": "Let me calculate."},
        ]
        prompt = ar._build_prompt(convo)
        self.assertIn("USER: What is 2+2?", prompt)
        self.assertIn("ASSISTANT:", prompt)

    def test_extract_json_simple(self):
        ar = AgentRuntime({})
        result = ar._extract_json('Here is JSON: {"action": "final", "text": "done"}')
        self.assertEqual(result["action"], "final")
        self.assertEqual(result["text"], "done")

    def test_extract_json_none(self):
        ar = AgentRuntime({})
        self.assertIsNone(ar._extract_json(None))
        self.assertIsNone(ar._extract_json("no json here"))

    def test_extract_json_with_code_block(self):
        ar = AgentRuntime({})
        text = '```json\n{"action": "final", "text": "42"}\n```'
        result = ar._extract_json(text)
        self.assertEqual(result["action"], "final")

    def test_normalize_action_tool(self):
        tools = {"calc": {"run": lambda a: "ok"}}
        ar = AgentRuntime(tools)
        action = ar._normalize_action({"action": "tool", "tool": "calc", "args": {"expr": "1"}})
        self.assertEqual(action["action"], "tool")
        self.assertEqual(action["tool"], "calc")

    def test_normalize_action_final(self):
        ar = AgentRuntime({})
        action = ar._normalize_action({"action": "final", "text": "answer"})
        self.assertEqual(action["action"], "final")
        self.assertEqual(action["text"], "answer")

    def test_normalize_action_implicit_tool(self):
        tools = {"calc": {"run": lambda a: "ok"}}
        ar = AgentRuntime(tools)
        action = ar._normalize_action({"calc": {"expr": "1"}})
        self.assertIsNotNone(action)
        self.assertEqual(action["tool"], "calc")

    def test_normalize_action_text_key(self):
        ar = AgentRuntime({})
        action = ar._normalize_action({"text": "the answer"})
        self.assertEqual(action["action"], "final")

    def test_clean_final_text_empty(self):
        ar = AgentRuntime({})
        self.assertEqual(ar.clean_final_text(""), "")
        self.assertEqual(ar.clean_final_text(None), "")

    def test_clean_final_text_plain(self):
        ar = AgentRuntime({})
        result = ar.clean_final_text("Just a normal answer")
        self.assertEqual(result, "Just a normal answer")

    def test_extract_protocol_text(self):
        ar = AgentRuntime({})
        result = ar._extract_protocol_text({"action": "final", "text": "hello"})
        self.assertEqual(result, "hello")
        result2 = ar._extract_protocol_text({"text": "fallback"})
        self.assertEqual(result2, "fallback")
        result3 = ar._extract_protocol_text("not a dict")
        self.assertIsNone(result3)

    def test_find_balanced_json_method(self):
        ar = AgentRuntime({})
        result = ar._find_balanced_json('{"a": 1}', 0)
        self.assertEqual(result, '{"a": 1}')
        self.assertIsNone(ar._find_balanced_json("x", 0))

    def test_balanced_json_spans(self):
        ar = AgentRuntime({})
        spans = ar._balanced_json_spans('text {"a":1} more {"b":2} end')
        self.assertEqual(len(spans), 2)

    def test_is_protocol_blob(self):
        ar = AgentRuntime({})
        self.assertTrue(ar._is_protocol_blob({"action": "tool"}))
        self.assertFalse(ar._is_protocol_blob({"text": "hi"}))
        self.assertFalse(ar._is_protocol_blob("string"))


class TestCollaboration(unittest.TestCase):

    def test_file_lock_acquire_release(self):
        flm = FileLockManager()
        self.assertTrue(flm.lock("/test.py", "agent1"))
        self.assertTrue(flm.is_locked("/test.py"))
        self.assertEqual(flm.get_lock_owner("/test.py"), "agent1")
        flm.unlock("/test.py", "agent1")
        self.assertFalse(flm.is_locked("/test.py"))

    def test_file_lock_contention(self):
        flm = FileLockManager()
        self.assertTrue(flm.lock("/test.py", "agent1"))
        self.assertFalse(flm.lock("/test.py", "agent2"))
        self.assertEqual(flm.get_lock_owner("/test.py"), "agent1")

    def test_file_lock_wrong_owner_cannot_unlock(self):
        flm = FileLockManager()
        flm.lock("/test.py", "agent1")
        flm.unlock("/test.py", "agent2")
        self.assertTrue(flm.is_locked("/test.py"))

    def test_file_lock_release_all(self):
        flm = FileLockManager()
        flm.lock("/a.py", "agent1")
        flm.lock("/b.py", "agent1")
        flm.lock("/c.py", "agent2")
        released = flm.release_all("agent1")
        self.assertEqual(len(released), 2)
        self.assertIn("/a.py", released)
        self.assertIn("/b.py", released)
        self.assertFalse(flm.is_locked("/a.py"))
        self.assertTrue(flm.is_locked("/c.py"))

    def test_file_lock_unlock_unowned(self):
        flm = FileLockManager()
        flm.unlock("/nonexistent.py", "agent1")
        self.assertFalse(flm.is_locked("/nonexistent.py"))

    def test_collaboration_context_defaults(self):
        ctx = CollaborationContext()
        self.assertEqual(ctx.task, "")
        self.assertEqual(ctx.decisions, [])
        self.assertEqual(ctx.issues, [])

    def test_collaboration_context_to_prompt_block(self):
        ctx = CollaborationContext(
            task="Plot the curve",
            decisions=["Use matplotlib"],
            issues=["Need data"],
            relevant_files=["plot.py"],
        )
        block = ctx.to_prompt_block()
        self.assertIn("TASK: Plot the curve", block)
        self.assertIn("DECISIONS:", block)
        self.assertIn("Use matplotlib", block)
        self.assertIn("OPEN ISSUES:", block)
        self.assertIn("Need data", block)
        self.assertIn("plot.py", block)

    def test_collaboration_context_exclude_roles(self):
        ctx = CollaborationContext(
            task="test",
            agent_findings={"planner": "plan here", "coder": "code here"},
        )
        block = ctx.to_prompt_block(exclude_roles=["planner"])
        self.assertNotIn("PLAN HERE", block.upper())
        self.assertIn("CODER FINDING", block)
        self.assertIn("code here", block)

    def test_collaboration_context_with_findings(self):
        ctx = CollaborationContext(
            task="test",
            agent_findings={"researcher": "found info about X"},
        )
        block = ctx.to_prompt_block()
        self.assertIn("RESEARCHER FINDING:", block)
        self.assertIn("found info about X", block)


if __name__ == "__main__":
    unittest.main(verbosity=2)
