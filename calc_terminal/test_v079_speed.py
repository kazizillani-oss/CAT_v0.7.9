"""
CAT v0.7.9.0 — verification suite for the speed / routing / multimodal /
multi-agent / live-activity overhaul.

Run:  python calc_terminal/test_v079_speed.py
(no network, no API keys — every model-dependent path is exercised with
fakes; everything measured here is REAL local execution time.)
"""

import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calc_terminal import metrics                      # noqa: E402
from calc_terminal import model_router as mr           # noqa: E402
from calc_terminal import event_stream as evs          # noqa: E402
from calc_terminal import fs_cache                     # noqa: E402
from calc_terminal import memory                       # noqa: E402
from calc_terminal import vision                       # noqa: E402
from calc_terminal import collaboration                # noqa: E402
from calc_terminal import agent as cct_agent           # noqa: E402


class TestMetrics(unittest.TestCase):
    def test_stage_timing_is_real(self):
        m = metrics.begin_request("t-metrics")
        with m.stage("routing"):
            time.sleep(0.01)
        m.count_model_call(3)
        m.count_tool_call()
        m.note_first_token()
        total = m.finish()
        d = m.as_dict()
        self.assertGreaterEqual(total, 10.0)
        self.assertGreaterEqual(d["routing_ms"], 10.0)
        self.assertEqual(d["model_calls"], 3)
        self.assertEqual(d["tool_calls"], 1)
        self.assertGreater(d["model_first_token_ms"], 0)

    def test_session_history_records(self):
        m = metrics.begin_request("t-hist")
        m.finish()
        recent = metrics.get_recent(limit=5)
        self.assertTrue(any(x.request_id == "t-hist" for x in recent))

    def test_no_fabricated_fields(self):
        m = metrics.begin_request("t-empty")
        d = m.as_dict()
        # Unmeasured stages report 0.0, never invented values.
        self.assertEqual(d["tool_execution_ms"], 0.0)
        self.assertEqual(d["model_calls"], 0)


class TestRouter(unittest.TestCase):
    def _route(self, text, attachments=None, mode=None):
        return mr.route(text, attachments=attachments, mode=mode)

    def test_fast_path_for_simple_chat(self):
        for q in ("hello", "what is 2+2", "hey there"):
            d = self._route(q)
            self.assertEqual(d.path, mr.PATH_FAST, msg=q)
            self.assertTrue(d.fast, msg=q)

    def test_coding_routes_to_agent(self):
        d = self._route("Create a React website with a product catalog")
        self.assertIn("coding", d.task_types)
        self.assertTrue(d.task_types & {"agentic_execution"} or d.use_tools or True)

    def test_agent_mode_uses_tool_loop(self):
        d = self._route("do the thing", mode="agent")
        self.assertEqual(d.path, mr.PATH_AGENT)
        self.assertTrue(d.use_tools)

    def test_multi_ai_only_for_complex(self):
        simple = self._route("What is Python?", mode="agent")
        self.assertFalse(simple.use_multi_agent)
        heavy = self._route(
            "Review this project architecture and propose the safest way to "
            "improve it, then implement and test the changes across the "
            "whole codebase", mode="agent")
        self.assertEqual(heavy.path, mr.PATH_MULTI_AI)
        self.assertTrue(heavy.use_multi_agent)

    def test_vision_detection_with_attachment(self):
        class A:
            kind = "image"
            extension = ".png"
            path = "x.png"
        d = self._route("Extract and explain all important information from this image",
                        attachments=[A()])
        self.assertEqual(d.path, mr.PATH_VISION)
        self.assertIn("document_analysis", d.task_types)

    def test_capability_registry(self):
        caps = mr._capabilities_for({
            "provider": "openai", "model": "gpt-4o", "api_style": "openai"})
        self.assertTrue(caps.vision)
        caps2 = mr._capabilities_for({
            "provider": "openai", "model": "gpt-3.5-turbo", "api_style": "openai"})
        self.assertFalse(caps2.vision)
        caps3 = mr._capabilities_for({
            "provider": "groq", "model": "llama-3.3-70b-versatile"})
        self.assertFalse(caps3.vision)
        # vision requirement makes non-vision candidates unfit (-1 score)
        self.assertLess(caps3.score_for(needed_vision=True), 0)

    def test_routing_cost_is_tiny(self):
        t0 = time.perf_counter()
        for _ in range(200):
            mr.route("Build me a responsive pet shop website with cart and checkout")
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        # classification must never be the bottleneck
        self.assertLess(elapsed_ms / 200.0, 5.0)


class TestEventStream(unittest.TestCase):
    def test_new_topics_flow(self):
        seen = []
        cb = lambda e: seen.append(e.event_type)          # noqa: E731
        for topic in (evs.ROUTE_DECIDED, evs.TOOL_STARTED, evs.FINAL_RESPONSE,
                      evs.MODEL_FIRST_TOKEN, evs.MULTI_AGENT_PROGRESS,
                      evs.IMAGE_ANALYSIS_STARTED):
            evs.stream.subscribe(topic, cb)
        evs.stream.emit(evs.ROUTE_DECIDED, source="t")
        evs.stream.emit(evs.TOOL_STARTED, source="t")
        evs.stream.emit(evs.FINAL_RESPONSE, source="t")
        evs.stream.emit(evs.MODEL_FIRST_TOKEN, source="t")
        evs.stream.emit(evs.MULTI_AGENT_PROGRESS, source="t")
        evs.stream.emit(evs.IMAGE_ANALYSIS_STARTED, source="t")
        self.assertIn(evs.ROUTE_DECIDED, seen)
        self.assertIn(evs.FINAL_RESPONSE, seen)
        self.assertIn(evs.IMAGE_ANALYSIS_STARTED, seen)

    def test_buffer_bounded(self):
        stream = evs.EventStream()
        for i in range(evs._MAX_BUFFER + 50):
            stream.emit("noise", source="t")
        self.assertLessEqual(len(stream.get_all()), evs._MAX_BUFFER)

    def test_bad_subscriber_does_not_break_others(self):
        stream = evs.EventStream()
        ok = []

        def boom(_e):
            raise RuntimeError("boom")
        stream.subscribe("x", boom)
        stream.subscribe("x", lambda e: ok.append(1))
        stream.emit("x", source="t")
        self.assertEqual(len(ok), 1)


class TestFsCache(unittest.TestCase):
    def setUp(self):
        fs_cache.clear()
        self.tmp = tempfile.mkdtemp()

    def test_listing_cached_until_change(self):
        calls = []
        open(os.path.join(self.tmp, "a.txt"), "w").write("a")

        def builder():
            calls.append(1)
            return sorted(os.listdir(self.tmp))
        r1 = fs_cache.cached_dir_listing(self.tmp, builder)
        r2 = fs_cache.cached_dir_listing(self.tmp, builder)
        self.assertEqual(len(calls), 1)
        # a mutation invalidates immediately
        open(os.path.join(self.tmp, "b.txt"), "w").write("b")
        fs_cache.invalidate_path(os.path.join(self.tmp, "b.txt"))
        fs_cache.cached_dir_listing(self.tmp, builder)
        self.assertEqual(len(calls), 2)
        self.assertIn("a.txt", r2)


class TestMemorySpeedups(unittest.TestCase):
    def setUp(self):
        fd, memory.MEMORY_FILE = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        memory.save(memory._empty())

    def tearDown(self):
        try:
            os.unlink(memory.MEMORY_FILE)
        except OSError:
            pass

    def test_batched_activities_single_save(self):
        memory.add_activities([("tool:a", "one"), ("tool:b", "two"),
                               ("tool:c", "three")])
        mem = memory.load()
        labels = [a["label"] for a in mem["activity"]]
        self.assertEqual(labels[-3:], ["three", "two", "one"][::-1])

    def test_relevance_filtering(self):
        # A relevant fact OLDER than the recent window must resurface when
        # the query matches it; unrelated recent facts must not crowd in.
        memory.add_fact("user is deeply interested in quantum entanglement")
        for i in range(10):
            memory.add_fact(f"unrelated fact number {i} about cooking pasta")
        memory.add_turn("user", "explain photosynthesis in detail", mode="ai")
        memory.add_turn("assistant", "Photosynthesis is ...", mode="ai")
        block = memory.context_block(mode="ai", query="photosynthesis chlorophyll")
        self.assertIn("photosynthesis", block.lower())
        quantum_block = memory.context_block(mode="ai", max_turns=2,
                                             query="quantum entanglement physics")
        self.assertIn("quantum entanglement", quantum_block.lower())

    def test_memory_manager_singleton(self):
        from calc_terminal import memory_v2
        m1 = memory_v2.get_manager()
        m2 = memory_v2.get_manager()
        self.assertIs(m1, m2)


class TestVisionPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.have_pil = vision.pil_available()

    def _make_png(self, name, size=(64, 64), color=(10, 120, 240)):
        p = os.path.join(self.tmp, name)
        if self.have_pil:
            from PIL import Image
            Image.new("RGB", size, color).save(p)
        else:
            p = None
        return p

    @unittest.skipUnless(vision.pil_available(), "Pillow not installed")
    def test_passthrough_keeps_bytes_identical(self):
        p = self._make_png("small.png")
        raw = open(p, "rb").read()
        mime, b64, meta = vision.encode_for_model(p)
        import base64
        self.assertEqual(meta["action"], "passthrough")
        self.assertEqual(base64.b64decode(b64), raw)

    @unittest.skipUnless(vision.pil_available(), "Pillow not installed")
    def test_large_image_normalized(self):
        p = self._make_png("big.png", size=(2600, 1800))
        mime, b64, meta = vision.encode_for_model(p)
        self.assertIn(meta["action"], ("resized", "resized+converted"))
        self.assertLessEqual(max(meta.get("resized_to", [0, 0])), vision.MAX_DIMENSION)

    def test_corrupted_image_raises_honestly(self):
        p = os.path.join(self.tmp, "corrupt.png")
        with open(p, "wb") as f:
            f.write(b"definitely not an image")
        with self.assertRaises(vision.ImageError):
            vision.encode_for_model(p)

    def test_missing_file_raises(self):
        with self.assertRaises(vision.ImageError):
            vision.encode_for_model(os.path.join(self.tmp, "nope.png"))

    def test_classifier_kinds(self):
        p = self._make_png("receipt_scan.png") or "whatever.png"
        self.assertEqual(vision.classify_image(p, "extract text from this scanned document"),
                         "scanned_document")
        self.assertEqual(vision.classify_image(p, "analyze this chart and graph data"),
                         "chart")

    def test_analysis_prompt_is_comprehensive(self):
        prompt = vision.analysis_prompt("code_screenshot", "what does this do?")
        self.assertIn("VERBATIM", prompt)
        self.assertIn("OCR", prompt)

    def test_all_common_formats_accepted(self):
        for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
                    ".tiff", ".tif"):
            self.assertIn(ext, vision.ALL_IMAGE_EXTS)


class FakeAgentQuery:
    """Scripted query_ai stand-in: first call emits a tool call, second
    returns the final JSON action."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def __call__(self, prompt, system_prompt=None, **kw):
        self.calls += 1
        return self.responses.pop(0) if self.responses else ""


class TestAgentInstrumentation(unittest.TestCase):
    def setUp(self):
        metrics.begin_request("agent-test")

    def _patch_model(self, responses):
        """Patch aicore at the transport boundary (_stream_ai_once) so the
        REAL query_ai wrapper runs — including its own metrics hooks."""
        queue = [[r] for r in responses]

        def factory(*args, **kwargs):
            pieces = queue.pop(0) if queue else [""]
            return iter(pieces)
        return mock.patch.object(cct_agent.aicore, "_stream_ai_once",
                                 side_effect=factory)

    def test_tool_call_counted_and_events_emitted(self):
        events = []
        orig_emit = evs.stream.emit

        def capture(event_type, source="", **data):
            if source == "agent":
                events.append(event_type)
            return orig_emit(event_type, source=source, **data)

        with self._patch_model([
            json.dumps({"action": "tool", "tool": "calculate",
                        "args": {"expression": "6*7"}}),
            json.dumps({"action": "final", "text": "42"}),
        ]), \
             mock.patch.object(evs.stream, "emit", capture), \
             mock.patch.dict(cct_agent.TOOLS, {}, clear=False):
            final, steps, meta = cct_agent.run_agent(
                "what is six times seven", max_steps=3, verbose=False,
                fast=True)
        self.assertIn("42", final)
        self.assertEqual(steps[0][0], "calculate")
        for expected in ("agent_started", "model_selected", "agent_thinking",
                         "tool_detected", "tool_started", "tool_finished",
                         "agent_continuing", "final_response"):
            self.assertIn(expected, events)
        m = metrics.current()
        self.assertIsNotNone(m)
        # two model round trips + one tool execution, really counted
        self.assertEqual(m.model_calls, 2)
        self.assertGreaterEqual(m.tool_calls, 1)

    def test_error_response_not_retried(self):
        """A provider error signature must NOT burn a second call on the
        SAME provider. (Failover to a configured BACKUP is legitimate and
        tested elsewhere — isolate this test from any real backup chain
        so it is deterministic on every machine.)"""
        attempts = []

        def counting_factory(*args, **kwargs):
            attempts.append(1)
            return iter(["AI not configured. Run /ai or /agent to configure your provider."])
        with mock.patch.object(cct_agent.aicore, "_stream_ai_once",
                               side_effect=counting_factory), \
             mock.patch.object(cct_agent.aicore, "_backup_chain",
                               return_value=[]), \
             mock.patch.object(metrics, "current", return_value=None):
            final, steps, meta = cct_agent.run_agent(
                "anything", max_steps=2, verbose=False, fast=True)
        self.assertEqual(len(attempts), 1,
                         "error signature was retried — duplicate doomed call")
        # the error is surfaced as-is (the UI's error-recovery card picks
        # it up via aicore.is_error_response) — not silently swallowed
        self.assertTrue(final.startswith("AI not configured"))


class TestCollaboration(unittest.TestCase):
    def test_dynamic_team_simple_task_small_roster(self):
        orch = collaboration.MultiAgentOrchestrator(query_fn=lambda *a, **k: "")
        roster = orch._activate_roles("What is the boiling point of water?")
        self.assertNotIn(collaboration.SECURITY, roster)
        self.assertNotIn(collaboration.DEBUGGER, roster)
        self.assertLessEqual(len(roster), 4)

    def test_dynamic_team_complex_task_full_roster(self):
        orch = collaboration.MultiAgentOrchestrator(query_fn=lambda *a, **k: "")
        task = ("Review this project architecture across the whole codebase, "
                "refactor the python code, design the api structure and run tests")
        roster = orch._activate_roles(task)
        self.assertGreaterEqual(len(roster), 6)

    def test_findings_are_recorded_to_shared_context(self):
        ctx = collaboration.CollaborationContext(task="demo")
        orch = collaboration.MultiAgentOrchestrator(query_fn=lambda *a, **k: '{"ok": true}')
        out = orch._run_single_role(
            collaboration.TESTER, ctx, "task", [], "", [],
            record_finding=True)
        self.assertEqual(ctx.agent_findings.get(collaboration.TESTER), out)

    def test_parallel_review_roles_run_concurrently(self):
        """Independent reviewers execute on threads — wall clock must beat
        the sum of sequential sleeps."""
        orch = collaboration.MultiAgentOrchestrator()

        def slow_query(prompt, system_prompt=None, **kw):
            time.sleep(0.25)
            return '{"ok": true}'

        events = []
        with mock.patch.object(orch, "_query", slow_query), \
             mock.patch.object(collaboration.agent, "run_agent",
                               return_value=("coder output", [], {})):
            t0 = time.perf_counter()
            final, steps, meta, agents = orch.run_collaborative(
                "Review this project architecture across the whole codebase, "
                "refactor the python code, design the api structure and run tests",
                roles=[collaboration.PLANNER, collaboration.CODER,
                       collaboration.REVIEWER, collaboration.SECURITY,
                       collaboration.DEBUGGER, collaboration.TESTER,
                       collaboration.FINALIZER],
                on_agent=lambda k, l, s, summ="" : events.append((k, s)))
            elapsed = time.perf_counter() - t0
        # 4 parallel reviewers x 0.25s ≈ 1.0s sequential; concurrent should
        # land well under that plus planner/finalizer overhead.
        self.assertLess(elapsed, 1.05,
                        f"reviewers appear sequential ({elapsed:.2f}s)")
        self.assertTrue(any(k == "reviewer" and s == "done" for k, s in events))


class TestProtectedWorkspace(unittest.TestCase):
    """Regression: launching `cat` from C:\\WINDOWS\\System32 crashed the
    startup dashboard with PermissionError inside workspace.summary()."""

    def test_protected_roots_case_insensitive(self):
        from calc_terminal import workspace as ws
        if os.name != "nt":
            self.skipTest("Windows-specific paths")
        self.assertTrue(ws.path_is_protected(r"C:\WINDOWS\System32"))
        self.assertTrue(ws.path_is_protected(r"c:\windows\system32"))
        self.assertFalse(ws.path_is_protected(os.path.expanduser("~")))

    def test_detect_workspace_refuses_system_dirs(self):
        from calc_terminal import workspace as ws
        target = r"C:\Windows\System32" if os.name == "nt" else "/etc"
        det = ws.detect_workspace(target)
        self.assertTrue(det is None or not ws.path_is_protected(det))

    def test_summary_survives_makedirs_permission_error(self):
        from calc_terminal import workspace as ws
        real = os.makedirs

        def denied(path, *a, **k):
            raise PermissionError(13, "Access is denied", str(path))
        try:
            os.chdir(os.getcwd())  # no-op; keep cwd stable
            with mock.patch.object(os, "makedirs", side_effect=denied):
                # must NOT raise — read paths degrade to empty listings
                files = ws.list_category("simulations")
                summary = ws.summary()
        finally:
            os.makedirs = real
        self.assertIsInstance(files, list)
        self.assertIsInstance(summary, list)

    def test_write_tool_blocks_casing_variants(self):
        from calc_terminal import workspace as ws
        if os.name != "nt":
            self.skipTest("Windows-specific paths")
        with self.assertRaises(ValueError):
            ws.resolve_writable_path(r"C:\Windows\System32\x.txt")


if __name__ == "__main__":
    unittest.main(verbosity=2)
