"""
CAT v0.7.9.5 — STABILITY / THEME / REQUEST-LIFECYCLE regression suite.

Covers the major bug-fix pass end to end (pure logic + headless where
possible, mirroring the style of test_v079_speed.py):

  A. THEME CATALOG
     1. every requested theme is registered under its canonical name
     2. legacy aliases ('dark', 'light') still resolve and apply
     3. every theme compiles to a complete legacy variable set
     4. contrast validation for EVERY theme (text/muted/accent/selection)
     5. light themes are flagged light, dark themes dark
     6. set_theme persists to BOTH stores; load_saved_theme restores any
        registered name (the old loader only understood 'light')
     7. unknown theme names fall back safely instead of crashing

  B. THEME INTERACTION (picker semantics, pure-logic level)
     8. preview-then-restore leaves the saved selection untouched
     9. click-to-apply persists the clicked theme
    10. exactly one ✓ mark: ThemesPanel row prefix logic

  C. REQUEST LIFECYCLE (the '...' fix)
    11. simple response streams through unchanged
    12. streaming response arrives incrementally
    13. empty response is surfaced as an error signature
    14. provider timeout signature detected + retryable
    15. provider exception falls back to the next provider
    16. fallback walks primary -> backup and succeeds
    17. mid-stream failure keeps partial answer + honest note
    18. cancelled request stops cleanly (socket close registry)
    19. model returning no tokens yields a final error (never silent)
    20. all providers failing still returns a real error string
    21. retries bounded per provider with exponential backoff
    22. provider cooldown demotes a just-failed provider
    23. configurable timeouts by size class

  D. ROUTER CLASSES
    24. trivial/simple/normal/complex/agent/research classification
    25. 'hi' takes the fast path with zero agent machinery
    26. complex prompts still route to agent capabilities

  E. SHUTDOWN
    27. shutdown_session is idempotent (goodbye rendered once)

Run:  python -m pytest calc_terminal/test_stability.py -q
"""

import json
import os
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calc_terminal import theme  # noqa: E402
from calc_terminal import config as cct_config  # noqa: E402
from calc_terminal import aicore  # noqa: E402
from calc_terminal import model_router  # noqa: E402

REQUIRED_THEMES = [
    "ansi-dark", "ansi-light", "atom-one-dark", "atom-one-light",
    "catppuccin-frappe", "catppuccin-latte", "catppuccin-macchiato",
    "catppuccin-mocha", "dracula", "flexoki", "gruvbox", "monokai",
    "nord", "rose-pine", "rose-pine-dawn", "rose-pine-moon",
    "solarized-dark", "solarized-light", "textual-dark", "textual-light",
    "tokyo-night",
]

LIGHT_THEMES = ["ansi-light", "atom-one-light", "catppuccin-latte",
                "rose-pine-dawn", "solarized-light", "textual-light"]


def _contrast(a, b):
    return theme.contrast_ratio(a, b)


class _FakeResponse:
    """Minimal stand-in for requests.Response (cancel path)."""

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class TestThemeCatalog(unittest.TestCase):
    """A — every requested theme exists with the normalized schema."""

    def test_all_requested_themes_registered(self):
        available = theme.available_themes()
        for name in REQUIRED_THEMES:
            self.assertIn(name, available,
                          f"required theme missing from registry: {name}")

    def test_legacy_aliases_resolve(self):
        self.assertEqual(theme.resolve_theme_name("dark"), "tokyo-night")
        self.assertEqual(theme.resolve_theme_name("light"), "github-light")
        # fuzzy variants users may type
        self.assertEqual(theme.resolve_theme_name("Tokyo Night"), "tokyo-night")
        self.assertEqual(theme.resolve_theme_name("Rose_Pine Dawn"),
                         "rose-pine-dawn")

    def test_legacy_dark_look_preserved(self):
        theme.set_theme("dark", persist=False, paint_bg=False)
        # byte-for-byte parity with the pre-overhaul Tokyo Night palette
        self.assertEqual(theme.CYAN, (125, 207, 255))
        self.assertEqual(theme.TEXT, (232, 235, 250))
        self.assertEqual(theme.OC_BG_PANEL, (30, 32, 48))
        self.assertEqual(theme.BG_USER, (40, 62, 92))

    def test_legacy_light_look_preserved(self):
        theme.set_theme("light", persist=False, paint_bg=False)
        self.assertEqual(theme.TEXT, (24, 28, 34))
        self.assertEqual(theme.OC_BG_ELEMENT, (240, 243, 247))
        self.assertTrue(theme.is_light())

    def test_every_theme_compiles_full_variable_set(self):
        required_vars = set(theme._THEME_COLOR_VARS)
        for name in theme.available_themes():
            t = theme.get_theme_obj(name)
            compiled = theme.compile_theme_vars(t)
            missing = required_vars - set(compiled)
            self.assertFalse(missing, f"{name}: uncompiled vars {missing}")
            for var in required_vars:
                v = compiled[var]
                self.assertIsInstance(v, tuple, f"{name}.{var} not rgb")
                self.assertEqual(len(v), 3, f"{name}.{var} not rgb triple")

    def test_normalized_schema_fields(self):
        for name in theme.available_themes():
            t = theme.get_theme_obj(name)
            for field in ("background", "surface", "surface_hover", "text",
                          "text_muted", "border", "accent", "input_background",
                          "selection_background", "selection_text",
                          "success", "warning", "error"):
                v = getattr(t, field)
                self.assertIsInstance(v, tuple, f"{name}.{field}")
                self.assertEqual(len(v), 3, f"{name}.{field}")

    def test_polarity_flags(self):
        for name in LIGHT_THEMES:
            self.assertTrue(theme.get_theme_obj(name).dark is False,
                            f"{name} must be flagged light")
        for name in REQUIRED_THEMES:
            if name not in LIGHT_THEMES:
                self.assertTrue(theme.get_theme_obj(name).dark is True,
                                f"{name} must be flagged dark")

    def test_contrast_every_theme(self):
        """Requirement #17: no invisible text in ANY shipped theme."""
        failures = []
        for name in theme.available_themes():
            t = theme.get_theme_obj(name)
            checks = {
                "text/background": (_contrast(t.text, t.background), 4.5),
                "text/surface": (_contrast(t.text, t.surface), 4.0),
                "muted/background": (_contrast(t.text_muted, t.background), 2.5),
                "accent/background": (
                    _contrast(theme.fit_contrast(t.accent, t.background, 3.0),
                              t.background), 3.0),
                "success/background": (
                    _contrast(theme.fit_contrast(t.success, t.background, 3.0),
                              t.background), 3.0),
                "warning/background": (
                    _contrast(theme.fit_contrast(t.warning, t.background, 3.0),
                              t.background), 3.0),
                "error/background": (
                    _contrast(theme.fit_contrast(t.error, t.background, 3.0),
                              t.background), 3.0),
                "selection": (_contrast(t.selection_text, t.selection_background), 3.0),
            }
            for key, (ratio, floor) in checks.items():
                if ratio < floor:
                    failures.append(f"{name}/{key}={ratio:.2f}<{floor}")
        self.assertEqual(failures, [], "contrast violations: " + "; ".join(failures))


class TestThemePersistence(unittest.TestCase):
    """A6/A7 + B9 — persistence across both stores, safe fallbacks."""

    def setUp(self):
        import tempfile
        fd, self._tmp = tempfile.mkstemp(prefix="cct_theme_", suffix=".json")
        os.close(fd)
        self._orig_file = theme._THEME_FILE
        theme._THEME_FILE = self._tmp
        self._orig_cfg = cct_config._cached
        cct_config._cached = None

    def tearDown(self):
        theme._THEME_FILE = self._orig_file
        cct_config._cached = self._orig_cfg
        try:
            os.remove(self._tmp)
        except OSError:
            pass
        theme.set_theme("tokyo-night", persist=False, paint_bg=False)

    def test_set_theme_persists_both_stores(self):
        cfg = cct_config.get_config()
        cfg.default_theme = "tokyo-night"
        theme.set_theme("nord", persist=True, paint_bg=False)
        with open(self._tmp, encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved["theme"], "nord")
        self.assertEqual(cct_config.get_config().default_theme, "nord")

    def test_load_saved_theme_restores_any_name(self):
        with open(self._tmp, "w", encoding="utf-8") as f:
            json.dump({"theme": "dracula"}, f)
        theme.load_saved_theme()
        self.assertEqual(theme.get_theme(), "dracula")

    def test_preview_does_not_persist(self):
        """B8 — hover preview applies temporarily only."""
        theme.set_theme("gruvbox", persist=True, paint_bg=False)
        theme.set_theme("monokai", persist=False, paint_bg=False)  # preview
        self.assertEqual(theme.get_theme(), "monokai")
        with open(self._tmp, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["theme"], "gruvbox")
        theme.set_theme("gruvbox", persist=False, paint_bg=False)  # restore
        self.assertEqual(theme.get_theme(), "gruvbox")

    def test_unknown_theme_falls_back_safely(self):
        theme.set_theme("tokyo-night", persist=False, paint_bg=False)
        result = theme.set_theme("no-such-theme", persist=False, paint_bg=False)
        self.assertEqual(result, "tokyo-night")

    def test_is_light_matches_registry(self):
        theme.set_theme("solarized-light", persist=False, paint_bg=False)
        self.assertTrue(theme.is_light())
        theme.set_theme("solarized-dark", persist=False, paint_bg=False)
        self.assertFalse(theme.is_light())


class TestThemePickerSemantics(unittest.TestCase):
    """B10 — exactly one permanent ✓, hover marker never shifts width."""

    def test_row_marks_have_equal_cell_width(self):
        from calc_terminal.ui.nav_screens import _ThemeRow
        for current, hovered in ((False, False), (True, False),
                                 (False, True), (True, True)):
            row = _ThemeRow("nord", "Nord", "nord" if current else "dracula")
            if hovered and not current:
                row.on_enter(event=None)
            rendered = row.render()
            plain = rendered.plain if hasattr(rendered, "plain") else str(rendered)
            label_cells = len(plain) - len(row.label)
            self.assertEqual(label_cells, _ThemeRow.MARK_W,
                             f"current={current} hovered={hovered}: "
                             f"mark width {label_cells}")

    def test_sync_current_moves_single_checkmark(self):
        from calc_terminal.ui.nav_screens import _ThemeRow
        rows = [_ThemeRow(n, n, "a") for n in ("a", "b", "c")]
        marks = []
        for r in rows:
            r.sync_current("b")
            rendered = r.render()
            plain = rendered.plain if hasattr(rendered, "plain") else str(rendered)
            marks.append("\u2713" in plain)
        self.assertEqual(marks, [False, True, False])


class TestRequestLifecycle(unittest.TestCase):
    """C — the '...' bug: every path terminates with real content or a
    real error, loading states can always clear."""

    def setUp(self):
        self._orig_once = aicore._stream_ai_once
        self._orig_backoff = aicore._backoff_sleep
        self._orig_chain = aicore._backup_chain
        aicore._backoff_sleep = lambda attempt: None  # tests stay fast
        # Hermetic backup chain — never depends on the machine's real
        # provider configuration.
        aicore._backup_chain = lambda: [
            ({"provider": "backup1", "model": "b1"}, {"id": "b1"}),
            ({"provider": "backup2", "model": "b2"}, {"id": "b2"}),
        ]
        aicore._PROVIDER_LAST_FAILURE.clear()

    def tearDown(self):
        aicore._stream_ai_once = self._orig_once
        aicore._backoff_sleep = self._orig_backoff
        aicore._backup_chain = self._orig_chain
        aicore._PROVIDER_LAST_FAILURE.clear()

    def _patch_once(self, fn):
        aicore._stream_ai_once = fn

    # -- simple / streaming ------------------------------------------------
    def test_simple_response(self):
        calls = []

        def once(prompt, system_prompt=None, history=None, config=None,
                 attachments=None, size_class="normal"):
            calls.append(config["provider"])
            yield "42"
        self._patch_once(once)
        out = "".join(aicore.stream_ai("hi", config={"provider": "p"}))
        self.assertEqual(out, "42")
        self.assertEqual(calls, ["p"])

    def test_streaming_response_incremental(self):
        def once(prompt, system_prompt=None, history=None, config=None,
                 attachments=None, size_class="normal"):
            for token in ("hel", "lo ", "wor", "ld"):
                yield token
        self._patch_once(once)
        chunks = list(aicore.stream_ai("hi", config={"provider": "p"}))
        self.assertEqual(chunks, ["hel", "lo ", "wor", "ld"])

    # -- empty / timeout / exception ----------------------------------------
    def test_empty_response_becomes_error_signature(self):
        def empty(prompt, system_prompt=None, history=None, config=None,
                  attachments=None, size_class="normal"):
            return
            yield  # pragma: no cover
        self._patch_once(empty)
        out = "".join(aicore.stream_ai("hi", config={"provider": "p"}))
        self.assertTrue(aicore.is_error_response(out))
        self.assertIn("No model response received.", out)

    def test_timeout_signature_detected_and_retryable(self):
        err = "The AI request timed out. Try again, or use a faster model."
        self.assertTrue(aicore.is_error_response(err))
        self.assertTrue(aicore._retryable_failure(err))
        quota = "Error connecting to AI: HTTP 429: quota exceeded"
        self.assertTrue(aicore.is_error_response(quota))
        self.assertFalse(aicore._retryable_failure(quota))

    def test_provider_exception_falls_back(self):
        seen = []

        def once(prompt, system_prompt=None, history=None, config=None,
                 attachments=None, size_class="normal"):
            seen.append(config["provider"])
            if config["provider"] == "primary":
                yield "Could not reach the AI server. down"
            else:
                yield "recovered answer"
        self._patch_once(once)
        out = "".join(aicore.stream_ai(
            "hi", config={"provider": "primary"},
        ))
        self.assertEqual(out, "recovered answer")
        self.assertGreater(len(seen), 1, "fallback never engaged")

    def test_query_ai_fallback_success(self):
        def once(prompt, system_prompt=None, history=None, config=None,
                 attachments=None, size_class="normal"):
            if config["provider"] == "primary":
                yield "The AI request timed out."
            else:
                yield "backup ok"
        self._patch_once(once)
        out = aicore.query_ai("q", config={"provider": "primary"})
        self.assertEqual(out, "backup ok")

    # -- mid-stream ----------------------------------------------------------
    def test_midstream_drop_keeps_partial_without_failover(self):
        providers = []

        def once(prompt, system_prompt=None, history=None, config=None,
                 attachments=None, size_class="normal"):
            providers.append(config["provider"])
            yield "partial data "
            yield "Could not reach the AI server. dropped"
        self._patch_once(once)
        out = "".join(aicore.stream_ai("q", config={"provider": "p1"}))
        self.assertEqual(providers, ["p1"], "mid-stream drop must not re-run")
        self.assertTrue(out.startswith("partial data"))
        self.assertIn("Connection lost mid-response", out)

    def test_partial_stream_then_cancel_note(self):
        """Cancelled request: worker-side flag is UI territory; here we
        verify the transport-level cancel closes sockets and stops."""
        resp = _FakeResponse()
        aicore._register_response(resp)
        closed_count = aicore.cancel_active_requests()
        try:
            self.assertGreaterEqual(closed_count, 1)
            self.assertTrue(resp.closed)
            self.assertTrue(aicore._just_cancelled())
        finally:
            aicore._unregister_response(resp)
        self.assertEqual(aicore.cancel_active_requests(), 0)

    def test_no_tokens_all_providers_yields_error_not_silence(self):
        def dead(prompt, system_prompt=None, history=None, config=None,
                 attachments=None, size_class="normal"):
            yield "Error connecting to AI: HTTP 500: dead"
        self._patch_once(dead)
        out = "".join(aicore.stream_ai("q", config={"provider": "p"}))
        self.assertTrue(aicore.is_error_response(out))
        self.assertTrue(out.strip(), "final failure must surface SOMETHING")

    def test_empty_generator_all_providers_still_terminates(self):
        def nothing(prompt, system_prompt=None, history=None, config=None,
                    attachments=None, size_class="normal"):
            return
            yield  # pragma: no cover
        self._patch_once(nothing)
        out = "".join(aicore.stream_ai("q", config={"provider": "p"}))
        self.assertTrue(aicore.is_error_response(out))

    # -- retry/backoff/cooldown ----------------------------------------------
    def test_retries_bounded_with_backoff_ordering(self):
        sleeps = []
        aicore._backoff_sleep = lambda attempt: sleeps.append(attempt)
        attempts = []

        def flaky(prompt, system_prompt=None, history=None, config=None,
                  attachments=None, size_class="normal"):
            attempts.append(config["provider"])
            if config["provider"] == "p":
                yield "Could not reach the AI server. blip"
            else:
                yield "ok-backup"
        self._patch_once(flaky)
        out = "".join(aicore.stream_ai("q", config={"provider": "p"}))
        self.assertEqual(out, "ok-backup")
        p_attempts = attempts.count("p")
        self.assertEqual(p_attempts, 2,
                         "expected exactly initial attempt + 1 retry")
        self.assertEqual(sleeps, [0], "exponential backoff starts at base")

    def test_non_retryable_skips_same_provider_retry(self):
        attempts = []

        def quota(prompt, system_prompt=None, history=None, config=None,
                  attachments=None, size_class="normal"):
            attempts.append(config["provider"])
            yield "Error connecting to AI: HTTP 429: quota exhausted"
        self._patch_once(quota)
        aicore.query_ai("q", config={"provider": "p"})
        self.assertEqual(attempts.count("p"), 1,
                         "quota errors must move on, not retry")

    def test_provider_cooldown_demotes_failed_provider(self):
        cfg = {"provider": "flaky", "model": "m"}
        aicore._PROVIDER_LAST_FAILURE.clear()
        self.assertFalse(aicore._provider_in_cooldown(cfg))
        aicore._mark_provider_failed(cfg)
        self.assertTrue(aicore._provider_in_cooldown(cfg))
        aicore._mark_provider_ok(cfg)
        self.assertFalse(aicore._provider_in_cooldown(cfg))

    def test_configurable_timeouts_by_size_class(self):
        cfg = cct_config.CCTConfig()
        simple = aicore.request_timeouts(cfg, "simple")
        normal = aicore.request_timeouts(cfg, "normal")
        large = aicore.request_timeouts(cfg, "large")
        self.assertLess(simple[2], normal[2])
        self.assertLess(normal[2], large[2])
        connect, idle, total = large
        self.assertGreaterEqual(total, 120)   # big tasks get room
        self.assertLessEqual(idle, total)     # idle can't exceed total


class TestRouterClasses(unittest.TestCase):
    """D — complexity classes drive fast paths AND timeout budgets."""

    def test_trivial_greeting(self):
        cls = model_router.complexity_class({"simple_chat"}, "hi")
        self.assertEqual(cls, model_router.CLASS_TRIVIAL)

    def test_simple_question(self):
        dec = model_router.route("what is recursion?")
        self.assertEqual(dec.path, model_router.PATH_FAST)
        self.assertTrue(dec.fast)
        self.assertEqual(dec.size_class, "simple")

    def test_trivial_takes_fast_path(self):
        dec = model_router.route("hi")
        self.assertEqual(dec.path, model_router.PATH_FAST)
        self.assertTrue(dec.fast)

    def test_arithmetic_trivial(self):
        dec = model_router.route("12*7")
        self.assertEqual(dec.path, model_router.PATH_FAST)

    def test_coding_normal_size_class(self):
        dec = model_router.route(
            "write a python function to parse this csv file properly")
        self.assertIn(dec.size_class, ("normal", "large"))

    def test_agent_task_gets_large_budget(self):
        dec = model_router.route("analyze and repair every broken import "
                                 "in this entire repository", mode="agent")
        self.assertEqual(dec.path, model_router.PATH_AGENT)
        self.assertEqual(dec.size_class, "large")

    def test_research_label(self):
        cls = model_router.complexity_class({"research"},
                                            "research latest news about x")
        self.assertEqual(cls, model_router.CLASS_RESEARCH)

    def test_complex_document_analysis(self):
        types = {"document_analysis", "long_context"}
        cls = model_router.complexity_class(types, "summarize this 200 page pdf")
        self.assertEqual(cls, model_router.CLASS_COMPLEX)


class TestShutdownOnce(unittest.TestCase):
    """E — goodbye ASCII renders EXACTLY once across exit paths."""

    def test_shutdown_session_idempotent(self):
        from calc_terminal import goodbye
        goodbye.reset_for_tests()
        renders = {"n": 0}

        class FakeRepl:
            history = []

        with mock.patch.object(goodbye, "render_goodbye",
                               side_effect=lambda **k:
                                   renders.__setitem__("n", renders["n"] + 1)):
            first = goodbye.shutdown_session(FakeRepl(), reason="exit")
            second = goodbye.shutdown_session(FakeRepl(), reason="exit")  # Ctrl+Q then /quit
        goodbye.reset_for_tests()
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(renders["n"], 1,
                         "double shutdown must render goodbye ONCE")


if __name__ == "__main__":
    unittest.main(verbosity=1)
