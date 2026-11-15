import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_fomoji_home_html():
    paths = [
        REPO_ROOT / "calc_terminal" / "fomoji_server" / "public" / "home.html",
        REPO_ROOT / "fomoji-updated" / "fomoji-server" / "public" / "home.html",
        REPO_ROOT / "CAT_v0.7.4" / "calc_terminal" / "fomoji_server" / "public" / "home.html",
        REPO_ROOT / "build" / "lib" / "calc_terminal" / "fomoji_server" / "public" / "home.html",
    ]
    for p in paths:
        assert p.exists(), f"File does not exist: {p}"
        content = p.read_text(encoding="utf-8")
        assert "FATTY CAT" not in content, f"Found 'FATTY CAT' in {p}"
        assert "Fatty CAT" not in content, f"Found 'Fatty CAT' in {p}"
        assert "startFattyCatBtn" not in content, f"Found startFattyCatBtn in {p}"
        assert "<span>CAT CLI</span>" in content, f"Missing '<span>CAT CLI</span>' in {p}"
        assert 'id="catCard" style="margin-top:14px; display:none;' in content, f"catCard not hidden by default in {p}"
        assert "if (account || connected)" in content, f"Missing account || connected check in {p}"
        assert "FomojiAPI.connectApp(account, 'cat')" in content, f"Missing auto-connect in {p}"
    print("✓ Fomoji home.html tests passed across all 4 locations.")

def test_chromium_flags():
    from calc_terminal.host.launcher import get_optimal_chromium_flags
    flags = get_optimal_chromium_flags()
    assert "--js-flags=--max-old-space-size=1024" in flags, f"Missing V8 heap limit in flags: {flags}"
    assert "--renderer-process-limit=6" in flags, f"Missing renderer process limit in flags: {flags}"
    assert "--num-raster-threads=4" in flags, f"Missing raster threads in flags: {flags}"
    assert "NetworkServiceInProcess2" not in flags or "--disable-features=CalculateNativeWinOcclusion,Translate,OptimizationHints,NetworkServiceInProcess2" in flags, f"Invalid NetworkServiceInProcess2 in flags: {flags}"
    print("✓ Chromium RAM optimization flags verified.")

def test_quick_dials_and_crash_protection():
    desktop_py = (REPO_ROOT / "calc_terminal" / "host" / "desktop.py").read_text(encoding="utf-8")
    qt_browser_py = (REPO_ROOT / "calc_terminal" / "browser_gui" / "qt_browser.py").read_text(encoding="utf-8")
    pw_browser_py = (REPO_ROOT / "calc_terminal" / "browser_gui" / "playwright_browser.py").read_text(encoding="utf-8")

    # Verify Agent Browser tile
    assert '("🤖", "Agent Browser", "Autonomous Web Agent", "about:agent-browser", "#80cbc4")' in desktop_py
    assert '("🤖", "Agent Browser", "Autonomous Web Agent", "about:agent-browser", "#80cbc4")' in qt_browser_py
    assert '<div class="card-title">Agent Browser</div>' in pw_browser_py
    assert 'about:agent-browser' in pw_browser_py

    # Verify crash loop breaker
    assert "_crash_history" in desktop_py
    assert "_crash_history" in qt_browser_py
    assert "len(history) >= 3" in desktop_py
    assert "len(history) >= 3" in qt_browser_py

    # Verify memory cache size is capped
    assert "self.profile.setHttpCacheMaximumSize(32 * 1024 * 1024)" in desktop_py
    assert "self.profile.setHttpCacheMaximumSize(32 * 1024 * 1024)" in qt_browser_py

    # Verify no DirectX reset mask on tab switch
    assert "def _on_current_changed" in qt_browser_py
    assert "_update_window_mask()" not in qt_browser_py[qt_browser_py.find("def _on_current_changed"):qt_browser_py.find("def _on_current_changed") + 400]

    # Verify Playwright responsiveness and heartbeat
    assert "no_viewport=True" in pw_browser_py
    assert ".cat_browser_heartbeat" in pw_browser_py

    # Verify launcher prefers built-in personal CAT Browser (Arc/Zen/Firefox style)
    launcher_py = (REPO_ROOT / "calc_terminal" / "host" / "launcher.py").read_text(encoding="utf-8")
    assert "CATBrowserWindow" in launcher_py

    print("✓ Quick dials, crash protection, and cache caps verified.")

def test_agent_browser_pages():
    pages_py = (REPO_ROOT / "calc_terminal" / "browser_gui" / "browser_pages.py").read_text(encoding="utf-8")
    assert "get_agent_browser_html" in pages_py
    assert "AgentDOMTree" in pages_py
    assert "vercel-labs/agent-browser" in pages_py
    print("✓ Vercel Agent Browser DOM tree integration verified.")

if __name__ == "__main__":
    test_fomoji_home_html()
    test_chromium_flags()
    test_quick_dials_and_crash_protection()
    test_agent_browser_pages()
    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")
