"""
CAT v0.7.10 — project detection + external dev-server unit tests
(hermetic: pure filesystem + pure regex; NO npm/node required).

Covers spec sections 19-20:

  detector   static · vite (config) · vite (dependency) · next · CRA ·
             node-without-dev-script · package.json-without-scripts ·
             missing folder · dependencies_installed()
  url parse  Vite/Next/CRA output lines → local URL, 0.0.0.0/[::1]
             normalization, punctuation trimming, non-URL lines
  controller framework detection routes through DevServerProcess and
             never starts CAT's static LiveServer in that mode (a fake
             DevServerProcess proves the wiring without spawning npm)

Run: python -m pytest calc_terminal/test_project_detect.py -q
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calc_terminal.browser.project_detector import (
    detect_project, dependencies_installed,
    STATIC, VITE, NEXT, CRA, NODE)
from calc_terminal.browser.devserver import DevServerProcess, extract_local_url


def _write(root, name, content=""):
    path = os.path.join(root, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


class TestProjectDetection(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cat_detect_")

    def test_static_by_default(self):
        _write(self.root, "index.html", "<h1>hi</h1>")
        d = detect_project(self.root)
        self.assertEqual(d.kind, STATIC)
        self.assertFalse(d.is_framework)
        self.assertTrue(dependencies_installed(d))

    def test_vite_config_file_wins(self):
        _write(self.root, "index.html")
        _write(self.root, "package.json",
               '{"scripts": {"dev": "vite"}}')
        _write(self.root, "vite.config.ts", "export default {}")
        d = detect_project(self.root)
        self.assertEqual(d.kind, VITE)
        self.assertEqual(d.command, ("npm", "run", "dev"))
        self.assertIn("vite.config.ts", d.evidence)

    def test_vite_dependency_only(self):
        _write(self.root, "package.json",
               '{"scripts": {"dev": "vite"},'
               ' "devDependencies": {"vite": "^5.0.0"}}')
        d = detect_project(self.root)
        self.assertEqual(d.kind, VITE)

    def test_nextjs(self):
        _write(self.root, "package.json",
               '{"scripts": {"dev": "next dev"}}')
        _write(self.root, "next.config.js", "module.exports = {}")
        d = detect_project(self.root)
        self.assertEqual(d.kind, NEXT)

    def test_cra(self):
        _write(self.root, "package.json",
               '{"scripts": {"start": "react-scripts start"}}')
        d = detect_project(self.root)
        self.assertEqual(d.kind, CRA)
        self.assertEqual(d.command, ("npm", "start"))

    def test_node_without_framework(self):
        _write(self.root, "package.json",
               '{"scripts": {"dev": "node server.js"}}')
        d = detect_project(self.root)
        self.assertEqual(d.kind, NODE)

    def test_package_without_scripts_falls_back_static(self):
        _write(self.root, "package.json", '{"name": "x"}')
        _write(self.root, "index.html")
        d = detect_project(self.root)
        self.assertEqual(d.kind, STATIC)

    def test_missing_folder_is_safe(self):
        d = detect_project(os.path.join(self.root, "nope"))
        self.assertEqual(d.kind, STATIC)

    def test_dependencies_installed_check(self):
        _write(self.root, "package.json", '{"scripts": {"dev": "vite"}}')
        _write(self.root, "vite.config.js")
        d = detect_project(self.root)
        self.assertTrue(d.is_framework)
        self.assertFalse(dependencies_installed(d))
        os.makedirs(os.path.join(self.root, "node_modules"))
        self.assertTrue(dependencies_installed(d))


class TestExtractLocalUrl(unittest.TestCase):
    def test_vite_line(self):
        self.assertEqual(
            extract_local_url("  ➜  Local:   http://localhost:5173/"),
            "http://localhost:5173/")

    def test_next_line(self):
        self.assertEqual(
            extract_local_url("- Local:        http://localhost:3000"),
            "http://localhost:3000/")

    def test_loopback_ip(self):
        self.assertEqual(
            extract_local_url("[1] Web server available at "
                              "http://127.0.0.1:8080/main/ ok"),
            "http://127.0.0.1:8080/main/")

    def test_bind_address_normalized(self):
        url = extract_local_url("listening on http://0.0.0.0:4000/")
        self.assertEqual(url, "http://127.0.0.1:4000/")

    def test_ipv6_normalized(self):
        url = extract_local_url("ready on http://[::1]:4321/")
        self.assertEqual(url, "http://127.0.0.1:4321/")

    def test_trailing_punctuation_trimmed(self):
        self.assertEqual(extract_local_url("at http://localhost:5000."),
                         "http://localhost:5000/")

    def test_non_url_lines_rejected(self):
        self.assertIsNone(extract_local_url(""))
        self.assertIsNone(extract_local_url("VITE v5.0.0  ready in 320 ms"))
        self.assertIsNone(extract_local_url("https://example.com/remote-only"))


class TestControllerFrameworkRouting(unittest.TestCase):
    """The controller must reuse the project's own dev server instead
    of stacking CAT's static LiveServer on top of it (spec §19)."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cat_fw_")
        _write(self.root, "index.html")
        _write(self.root, "package.json", '{"scripts": {"dev": "vite"}}')
        _write(self.root, "vite.config.js")
        os.makedirs(os.path.join(self.root, "node_modules"), exist_ok=True)

    def test_framework_routes_through_devserver(self):
        from calc_terminal.browser.preview import PreviewController
        from calc_terminal.browser.state import PreviewSnapshot

        class FakeDevServer:
            def __init__(self, root, command, on_activity=None):
                self.root, self.command = root, tuple(command)
                self.url = ""
                self.stopped = False

            def start(self, timeout=45.0):
                self.url = "http://localhost:5173/"
                return True

            @property
            def running(self):
                return bool(self.url) and not self.stopped

            def stop(self):
                self.stopped = True

        created = []

        def factory(root, command, on_activity=None):
            ds = FakeDevServer(root, command, on_activity)
            created.append(ds)
            return ds

        class FakeEngine:
            available = True
            started = False
            navigate_calls = []

            def start(self):
                self.started = True

            def navigate(self, url, timeout=35.0):
                self.navigate_calls.append(url)
                return PreviewSnapshot(url=url, ok=True, elements=1)

            def close(self, timeout=6.0):
                pass

        ctrl = PreviewController(self.root, engine=FakeEngine(),
                                 on_event=lambda *a, **k: None,
                                 devserver_factory=factory)

        ok = ctrl.start_for_file(os.path.join(self.root, "index.html"))

        self.assertTrue(ok)
        self.assertEqual(ctrl.detection.kind, VITE)
        self.assertEqual(len(created), 1)
        # The engine was pointed at the DEV SERVER URL, not a static one.
        self.assertEqual(FakeEngine.navigate_calls,
                         ["http://localhost:5173/"])
        # And CAT's own static LiveServer stayed idle.
        self.assertFalse(ctrl.server.running)
        self.assertTrue(ctrl.running)
        # stop_preview must tear the dev-server down too.
        ctrl.stop_preview()
        self.assertTrue(created[0].stopped)

    def test_framework_without_deps_uses_static_path(self):
        """node_modules missing: no fake success — the honest fallback
        is CAT's static server for the plain index.html at the root."""
        import shutil
        from calc_terminal.browser.preview import PreviewController
        from calc_terminal.browser.state import PreviewSnapshot

        shutil.rmtree(os.path.join(self.root, "node_modules"),
                      ignore_errors=True)

        created = []

        def factory(root, command, on_activity=None):
            created.append(1)
            raise AssertionError("devserver must NOT be started without "
                                 "node_modules")

        class NoStartEngine:
            available = False

            def close(self, timeout=6.0):
                pass

        ctrl = PreviewController(self.root, engine=NoStartEngine(),
                                 on_event=lambda *a, **k: None,
                                 devserver_factory=factory)
        self.assertTrue(ctrl.detection.is_framework)
        self.assertFalse(dependencies_installed(ctrl.detection))
        # Engine unavailable → start fails honestly AFTER choosing the
        # static path; crucially the dev-server factory was never used.
        try:
            ctrl.start_for_file(os.path.join(self.root, "index.html"))
        except Exception:
            pass
        self.assertEqual(created, [])
        ctrl.stop_preview()  # must not raise


if __name__ == "__main__":
    unittest.main()
