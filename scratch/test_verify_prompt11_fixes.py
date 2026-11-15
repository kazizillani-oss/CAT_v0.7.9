import sys
import os
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

class TestPrompt11Fixes(unittest.TestCase):
    def test_vercel_api_and_static_app(self):
        # 1. Test api/index.py FastAPI app
        from api.index import app
        client = TestClient(app)
        
        # Test root endpoint
        res = client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("content-type", ""))
        self.assertGreater(len(res.text), 1000)
        
        # Test health endpoint
        res_health = client.get("/health")
        self.assertEqual(res_health.status_code, 200)
        self.assertEqual(res_health.json().get("status"), "ok")
        
        # Test api/diag endpoint
        res_diag = client.get("/api/diag")
        self.assertEqual(res_diag.status_code, 200)
        self.assertEqual(res_diag.json().get("status"), "healthy")

    def test_public_assets_exist(self):
        repo_root = Path(__file__).resolve().parent.parent
        public_dir = repo_root / "public"
        self.assertTrue((public_dir / "index.html").exists())
        self.assertGreater((public_dir / "index.html").stat().st_size, 50000)
        self.assertTrue((public_dir / "manifest.json").exists())
        self.assertTrue((public_dir / "sw.js").exists())
        self.assertTrue((public_dir / "viewer.html").exists())

    def test_cli_and_tui_hotkeys(self):
        from calc_terminal.ui.app import CCTApp
        # Ensure bare 'alt' binding is NOT in CCTApp.BINDINGS
        bindings = getattr(CCTApp, "BINDINGS", [])
        for b in bindings:
            if isinstance(b, tuple):
                key = b[0]
            else:
                key = getattr(b, "key", "")
            self.assertNotEqual(key, "alt", "Bare 'alt' must NOT be registered as a binding")

    def test_terminal_guard_installed(self):
        from calc_terminal.terminal_host import install_terminal_guard
        install_terminal_guard()
        self.assertIsNotNone(sys.excepthook)
        import threading
        self.assertIsNotNone(threading.excepthook)

if __name__ == "__main__":
    unittest.main()
