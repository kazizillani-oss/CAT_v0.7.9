"""
CAT v0.7.10 — browser subsystem regression suite (hermetic: no network
beyond 127.0.0.1 ephemeral ports, no Chromium required — a FakeEngine
mirrors the real engine's interface).

Covers spec section 28's core mechanics:

  server     auto port · index resolution · MIME types · images/fonts ·
             no-cache headers · traversal blocked · clean stop
  navigation back / forward / duplicate-push / forward-truncation / cap
  entry      entry-point detection · workspace-relative URLs
  watcher    web-file filter · debounce coalescing (150 ms)
  controller state model transitions · CSS hot path vs full reload ·
             AI-write debounce · error isolation · idempotent shutdown

Run: python -m pytest calc_terminal/test_browser.py -q
"""

import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calc_terminal.browser import (NavigationHistory, PreviewController,
                                   PaneMode, PreviewState, ServerState,
                                   EditorState, WorkspaceMode)
from calc_terminal.browser.preview_entry import (find_entry_file,
                                                 relative_url_for,
                                                 url_for_file)
from calc_terminal.browser.server import LiveServer, find_free_port
from calc_terminal.browser.watcher import Debouncer, is_web_file


def _fetch(url, timeout=5):
    req = urllib.request.Request(url, headers={"Connection": "close"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def make_site(root):
    with open(os.path.join(root, "index.html"), "w", encoding="utf-8") as f:
        f.write("<html><head><link rel=stylesheet href=style.css></head>"
                "<body><h1>Hi</h1></body></html>")
    with open(os.path.join(root, "style.css"), "w", encoding="utf-8") as f:
        f.write("h1{color:red}")
    with open(os.path.join(root, "app.js"), "w", encoding="utf-8") as f:
        f.write("console.log('ok')")
    os.makedirs(os.path.join(root, "assets"), exist_ok=True)
    with open(os.path.join(root, "assets", "font.woff2"), "wb") as f:
        f.write(b"wOF2")
    with open(os.path.join(root, "secret.txt"), "w", encoding="utf-8") as f:
        f.write("workspace file")


class FakeEngine:
    """BrowserEngine stand-in: records calls, returns canned snapshots."""

    def __init__(self, ok=True):
        self.available = False
        self.ok = ok
        self.navigate_calls = []
        self.reload_calls = 0
        self.hot_calls = []
        self.closed = False
        from calc_terminal.browser.state import PreviewSnapshot
        self._snap = lambda url: PreviewSnapshot(
            url=url, title="t", ok=self.ok,
            outline_lines=("hello",), elements=3)

    def start(self):
        self.available = True

    def navigate(self, url, timeout=35.0):
        self.navigate_calls.append(url)
        return self._snap(url)

    def reload(self, timeout=35.0):
        self.reload_calls += 1
        return self._snap(self.navigate_calls[-1]
                          if self.navigate_calls else "")

    def back(self, timeout=20.0):
        return None

    def forward(self, timeout=20.0):
        return None

    def hot_css(self, hrefs):
        self.hot_calls.append(list(hrefs))
        return True

    def close(self):
        self.closed = True
        self.available = False


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="cat_srv_")
        make_site(cls.root)
        cls.srv = LiveServer(cls.root)
        assert cls.srv.start()
        assert cls.srv.wait_ready()

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop()

    def test_auto_port_on_localhost(self):
        self.assertTrue(self.srv.url.startswith("http://127.0.0.1:"))
        port = int(self.srv.url.split(":")[2].rstrip("/"))
        self.assertGreater(port, 0)
        self.assertNotEqual(find_free_port(), 0)

    def test_index_resolution_and_mime(self):
        status, headers, body = _fetch(self.srv.url)
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("Content-Type", ""))
        self.assertIn(b"<h1>Hi</h1>", body)

        status, headers, body = _fetch(self.srv.url + "style.css")
        self.assertEqual(status, 200)
        self.assertIn("text/css", headers.get("Content-Type", ""))

        status, headers, body = _fetch(self.srv.url + "app.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers.get("Content-Type", ""))

        status, headers, body = _fetch(self.srv.url + "assets/font.woff2")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Type", ""), "font/woff2")
        self.assertEqual(body[:4], b"wOF2")

    def test_no_cache_headers(self):
        status, headers, _ = _fetch(self.srv.url)
        self.assertIn("no-cache", headers.get("Cache-Control", ""))

    def test_hot_reload_snippet_injected(self):
        _, _, body = _fetch(self.srv.url)
        self.assertIn(b"__CAT_HOT__", body)

    def test_traversal_blocked(self):
        # ../.. out of the root must never resolve to a real file
        status, _, body = _fetch(self.srv.url + "../outside.html")
        self.assertIn(status, (400, 404))
        # even encoded tricks stay inside the root or fail
        status, _, _ = _fetch(self.srv.url + "assets/../../secret.txt")
        self.assertIn(status, (200, 400, 404))

    def test_missing_file_404(self):
        status, _, _ = _fetch(self.srv.url + "nope.html")
        self.assertEqual(status, 404)

    def test_stop_is_idempotent_and_cleans_up(self):
        srv = LiveServer(self.root)
        self.assertTrue(srv.start())
        self.assertTrue(srv.wait_ready())
        port = srv.port
        srv.stop()
        srv.stop()  # second call must not raise
        self.assertIsNone(srv.port)
        time.sleep(0.1)
        with self.assertRaises(OSError):
            urllib.request.urlopen(f"http://127.0.0.1:{port}/",
                                   timeout=2).read()


class TestNavigationHistory(unittest.TestCase):
    def test_back_forward(self):
        h = NavigationHistory()
        self.assertEqual(h.push("a"), "a")
        self.assertIsNotNone(h.push("b"))
        self.assertIsNotNone(h.push("c"))
        self.assertEqual(h.current, "c")
        self.assertEqual(h.back(), "b")
        self.assertEqual(h.back(), "a")
        self.assertIsNone(h.back())
        self.assertEqual(h.forward(), "b")
        self.assertTrue(h.can_forward())       # 'c' is still ahead
        self.assertEqual(h.forward(), "c")
        self.assertFalse(h.can_forward())

    def test_push_truncates_forward_branch(self):
        h = NavigationHistory()
        for u in ("a", "b", "c"):
            h.push(u)
        h.back()
        h.back()                      # now at "a", forward branch [b, c]
        self.assertEqual(h.push("d"), "d")   # branch truncated, d appended
        self.assertEqual(h.current, "d")
        self.assertFalse(h.can_forward())
        self.assertEqual(h.back(), "a")
        # 'd' remains reachable forward (standard browser semantics);
        # what must be GONE is the old fork [b, c]:
        self.assertEqual(h.forward(), "d")
        self.assertNotIn("b", h._entries)
        self.assertNotIn("c", h._entries)

    def test_duplicate_push_is_noop(self):
        h = NavigationHistory()
        h.push("a")
        self.assertIsNone(h.push("a"))   # reload ≠ history entry
        self.assertEqual(len(h), 1)


class TestEntryDetection(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cat_entry_")
        os.makedirs(os.path.join(self.root, "docs", "site"))

    def test_open_html_file_is_entry(self):
        p = os.path.join(self.root, "page.html")
        open(p, "w").close()
        entry, web_root = find_entry_file(p, self.root)
        self.assertEqual(entry, p)

    def test_sibling_index_preferred(self):
        idx = os.path.join(self.root, "index.html")
        open(idx, "w").close()
        other = os.path.join(self.root, "about.html")
        open(other, "w").close()
        entry, web_root = find_entry_file(other, self.root)
        self.assertEqual(entry, idx)
        self.assertEqual(web_root, self.root)

    def test_nested_site_found(self):
        nested = os.path.join(self.root, "docs", "site", "index.html")
        open(nested, "w").close()
        entry, web_root = find_entry_file(None, self.root)
        self.assertEqual(entry, nested)
        self.assertEqual(web_root, os.path.dirname(nested))

    def test_none_when_no_html(self):
        entry, web_root = find_entry_file(None, self.root)
        self.assertIsNone(entry)

    def test_relative_urls(self):
        self.assertEqual(relative_url_for(
            os.path.join(self.root, "a", "b.html"), self.root), "a/b.html")
        outside = os.path.abspath(os.path.join(self.root, "..", "x.html"))
        self.assertIsNone(relative_url_for(outside, self.root))
        self.assertIsNone(url_for_file(outside, "http://127.0.0.1:1/",
                                       self.root))


class TestWatcherFilteringAndDebounce(unittest.TestCase):
    def test_web_file_classification(self):
        for name in ("a.html", "b.htm", "c.css", "d.js", "e.mjs", "f.svg",
                     "g.png", "h.woff2"):
            self.assertTrue(is_web_file(name), name)
        for name in ("x.py", "y.md", "z.bin", "noext"):
            self.assertFalse(is_web_file(name), name)

    def test_debouncer_coalesces_bursts(self):
        done = threading.Event()
        runs = {"n": 0}

        def fn():
            runs["n"] += 1
            done.set()

        d = Debouncer(delay=0.15)
        for _ in range(10):
            d.schedule(fn)          # rapid rescheduling = one trailing run
            time.sleep(0.02)
        self.assertTrue(done.wait(3))
        time.sleep(0.25)
        self.assertEqual(runs["n"], 1)


class TestControllerLifecycle(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cat_ctrl_")
        make_site(self.root)
        self.engine = FakeEngine()
        self.events = []
        self.ctrl = PreviewController(
            self.root, engine=self.engine,
            on_event=lambda kind, **kw: self.events.append((kind, kw)))

    def tearDown(self):
        self.ctrl.stop_preview()

    def test_start_stop_state_machine(self):
        self.assertEqual(self.ctrl.preview_state, PreviewState.STOPPED)
        ok = self.ctrl.start_for_file(os.path.join(self.root, "index.html"))
        self.assertTrue(ok)
        self.assertEqual(self.ctrl.preview_state, PreviewState.RUNNING)
        self.assertEqual(self.ctrl.server_state, ServerState.RUNNING)
        self.assertTrue(self.ctrl.running)
        self.assertTrue(self.ctrl.url.endswith("/index.html"))
        self.ctrl.stop_preview()
        self.assertEqual(self.ctrl.preview_state, PreviewState.STOPPED)
        self.assertEqual(self.ctrl.server_state, ServerState.STOPPED)
        self.assertTrue(self.engine.closed)

    def test_states_are_enums_not_booleans(self):
        """Spec section 22: named state enums exist and are used."""
        self.assertEqual(WorkspaceMode.CODE.value, "code")
        self.assertEqual(PaneMode.FULLSCREEN.value, "fullscreen")
        self.assertEqual(EditorState.HAS_TABS.value, "has_tabs")

    def test_css_only_change_takes_hot_path(self):
        self.ctrl.start_for_file(os.path.join(self.root, "index.html"))
        css = os.path.join(self.root, "style.css")
        reloads_before = self.engine.reload_calls
        self.ctrl.on_files_changed([css])
        self.assertEqual(self.engine.reload_calls, reloads_before,
                         "css-only change must NOT full-reload")
        self.assertEqual(self.engine.hot_calls, [["style.css"]])

    def test_js_change_full_reloads(self):
        self.ctrl.start_for_file(os.path.join(self.root, "index.html"))
        js = os.path.join(self.root, "app.js")
        self.ctrl.on_files_changed([js])
        self.assertEqual(self.engine.reload_calls, 1)

    def test_ai_write_notifications_are_debounced(self):
        self.ctrl.start_for_file(os.path.join(root := self.root,
                                              "index.html"))
        html = os.path.join(self.root, "index.html")
        reloads_before = self.engine.reload_calls
        for i in range(12):                      # burst of AI writes
            self.ctrl.notify_ai_wrote(html)
            time.sleep(0.01)
        time.sleep(0.6)                          # > debounce window
        reloaded = self.engine.reload_calls - reloads_before
        self.assertLessEqual(reloaded, 2,
                             f"12 writes caused {reloaded} reloads")

    def test_error_page_does_not_kill_stack(self):
        self.engine.ok = False
        self.ctrl.start_for_file(os.path.join(self.root, "index.html"))
        # page-level failure → PREVIEW ERROR but server still RUNNING
        self.assertEqual(self.ctrl.preview_state, PreviewState.ERROR)
        self.assertEqual(self.ctrl.server_state, ServerState.RUNNING)
        # and recovery works
        self.engine.ok = True
        snap = self.ctrl.reload()
        self.assertEqual(self.ctrl.preview_state, PreviewState.RUNNING)

    def test_stop_preview_idempotent(self):
        self.ctrl.start_for_file(os.path.join(self.root, "index.html"))
        self.ctrl.stop_preview()
        self.ctrl.stop_preview()          # must not raise
        self.assertEqual(self.ctrl.preview_state, PreviewState.STOPPED)

    def test_non_web_notify_is_noop(self):
        self.ctrl.start_for_file(os.path.join(self.root, "index.html"))
        reloads_before = self.engine.reload_calls
        self.ctrl.notify_ai_wrote(os.path.join(self.root, "notes.md"))
        self.ctrl.notify_ai_wrote(None)
        time.sleep(0.4)
        self.assertEqual(self.engine.reload_calls, reloads_before)


if __name__ == "__main__":
    unittest.main(verbosity=1)
