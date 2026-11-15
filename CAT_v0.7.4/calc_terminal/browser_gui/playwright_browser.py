"""
Playwright-powered graphical CAT Browser engine.
Provides a modern Chromium browser experience powered by the Playwright package,
fully integrated with Fomoji cryptographic authentication, Agent Browser,
and sleek glassmorphism styling with 12px rounded corners.
"""

from __future__ import annotations

import os
import sys
import time
import pathlib
import urllib.parse


def can_launch_playwright() -> bool:
    """Return True if Playwright is installed and ready to launch."""
    try:
        import playwright
        return True
    except Exception:
        return False


def _get_fomoji_vault_token() -> str:
    """Retrieve the cryptographic vault token for Fomoji server authorization."""
    try:
        from ..fomoji_manager import read_vault_token
        tok = read_vault_token()
        if tok:
            return tok
    except Exception:
        pass
    token_file = pathlib.Path.home() / ".cat_fomoji_vault.key"
    try:
        if token_file.exists():
            return token_file.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return "cat_vault_token_authorized_session"


def _generate_start_page_html() -> str:
    """Generate the modern CAT Browser start page with 12px rounded cards and glassmorphic UI."""
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CAT Browser</title>
  <style>
    :root {
      --bg: #0a0d14;
      --card-bg: rgba(22, 27, 39, 0.72);
      --card-border: rgba(255, 255, 255, 0.12);
      --accent: #82aaff;
      --accent-hover: #c792ea;
      --text: #e8ebfa;
      --text-muted: #8c95b3;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: radial-gradient(circle at 50% 20%, #151a28 0%, #080a10 100%);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 30px 20px;
      overflow-x: hidden;
    }
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: rgba(0, 0, 0, 0.2); }
    ::-webkit-scrollbar-thumb { background: rgba(130, 170, 255, 0.3); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(130, 170, 255, 0.6); }

    .container {
      width: 780px;
      max-width: 100%;
      text-align: center;
      animation: fadeIn 0.4s ease-out;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(12px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .logo-badge {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 24px;
    }
    .cat-avatar {
      font-size: 38px;
      filter: drop-shadow(0 4px 16px rgba(130, 170, 255, 0.4));
    }
    .brand-title {
      font-size: 34px;
      font-weight: 800;
      letter-spacing: 0.22em;
      text-transform: uppercase;
      background: linear-gradient(135deg, #82aaff 0%, #c792ea 50%, #80cbc4 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .status-capsule {
      display: inline-flex;
      align-items: center;
      gap: 14px;
      padding: 5px 16px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 999px;
      font-size: 11.5px;
      color: var(--text-muted);
      margin-bottom: 26px;
      backdrop-filter: blur(10px);
    }
    .status-capsule span { display: inline-flex; align-items: center; gap: 4px; }
    .status-dot { width: 6px; height: 6px; border-radius: 50%; background: #00d4aa; }

    .search-box {
      display: flex;
      align-items: center;
      background: rgba(18, 23, 35, 0.82);
      border: 1.5px solid rgba(130, 170, 255, 0.35);
      border-radius: 14px;
      padding: 12px 18px;
      margin-bottom: 30px;
      backdrop-filter: blur(12px);
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.15);
      transition: all 0.25s ease;
    }
    .search-box:focus-within {
      border-color: var(--accent);
      box-shadow: 0 10px 40px rgba(130, 170, 255, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.25);
      transform: translateY(-2px);
    }
    .search-icon { font-size: 18px; margin-right: 12px; color: var(--accent); }
    .search-input {
      flex: 1;
      background: transparent;
      border: none;
      outline: none;
      color: var(--text);
      font-size: 16px;
    }
    .search-input::placeholder { color: #697394; }
    .search-enter {
      padding: 4px 10px;
      border-radius: 6px;
      background: rgba(130, 170, 255, 0.15);
      border: 1px solid rgba(130, 170, 255, 0.3);
      color: var(--accent);
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
      margin-bottom: 24px;
    }
    .card {
      display: flex;
      align-items: center;
      gap: 14px;
      padding: 16px 18px;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      text-decoration: none;
      color: var(--text);
      backdrop-filter: blur(14px);
      text-align: left;
      transition: all 0.2s cubic-bezier(0.2, 0.8, 0.2, 1);
    }
    .card:hover {
      border-color: var(--accent);
      background: rgba(30, 37, 56, 0.88);
      transform: translateY(-3px);
      box-shadow: 0 8px 24px rgba(130, 170, 255, 0.2);
    }
    .card-icon {
      font-size: 24px;
      width: 44px;
      height: 44px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.08);
      flex-shrink: 0;
    }
    .card-info { flex: 1; min-width: 0; }
    .card-title { font-size: 14.5px; font-weight: 600; color: #fff; margin-bottom: 2px; }
    .card-desc { font-size: 11.5px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    .footer {
      font-size: 12px;
      color: #697394;
      margin-top: 10px;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="logo-badge">
      <div class="cat-avatar">🐱</div>
      <h1 class="brand-title">CAT BROWSER</h1>
    </div>

    <div class="status-capsule">
      <span><div class="status-dot"></div> PLAYWRIGHT ENGINE</span>
      <span>•</span>
      <span>🔒 FOMOJI HARDWARE VAULT</span>
      <span>•</span>
      <span>⚡ 60 FPS SMOOTH SCROLL</span>
    </div>

    <div class="search-box">
      <span class="search-icon">🔍</span>
      <input id="q" class="search-input" placeholder="Search the web or enter URL (e.g. localhost:8765, github.com)..." autofocus autocomplete="off">
      <button class="search-enter" id="goBtn">↵ Enter</button>
    </div>

    <div class="grid">
      <a class="card" href="about:agent-browser">
        <div class="card-icon" style="color: #80cbc4;">🤖</div>
        <div class="card-info">
          <div class="card-title">Agent Browser</div>
          <div class="card-desc">Autonomous Web Agent</div>
        </div>
      </a>

      <a class="card" href="http://localhost:3000/home.html">
        <div class="card-icon" style="color: #89b4fa;">🔒</div>
        <div class="card-info">
          <div class="card-title">Fomoji Portal</div>
          <div class="card-desc">Auth &amp; Passkeys</div>
        </div>
      </a>

      <a class="card" href="http://localhost:3000/cat-manual.html">
        <div class="card-icon" style="color: #f9e2af;">📖</div>
        <div class="card-info">
          <div class="card-title">CAT Manual</div>
          <div class="card-desc">CLI Docs &amp; Guide</div>
        </div>
      </a>

      <a class="card" href="http://localhost:8765/viewer.html">
        <div class="card-icon" style="color: #cba6f7;">📄</div>
        <div class="card-info">
          <div class="card-title">Media Viewer</div>
          <div class="card-desc">Images, PDFs &amp; Docs</div>
        </div>
      </a>

      <a class="card" href="http://localhost:3000/settings.html">
        <div class="card-icon" style="color: #fab387;">⚙</div>
        <div class="card-info">
          <div class="card-title">Settings</div>
          <div class="card-desc">Browser &amp; System</div>
        </div>
      </a>

      <a class="card" href="about:home">
        <div class="card-icon" style="color: #b4befe;">○</div>
        <div class="card-info">
          <div class="card-title">New Window</div>
          <div class="card-desc">Open Blank Tab</div>
        </div>
      </a>
    </div>

    <div class="footer">
      CAT Browser · Ultra-Fast · Playwright Chromium · 12px Rounded Window Frame
    </div>
  </div>

  <script>
    const inp = document.getElementById('q');
    const goBtn = document.getElementById('goBtn');
    function navigate() {
      const v = inp.value.trim();
      if (!v) return;
      const hasScheme = /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(v);
      const isLocal = v.includes('localhost') || v.startsWith('127.0.0.1');
      if (hasScheme || isLocal || (v.includes('.') && !v.includes(' '))) {
        location.href = hasScheme ? v : ('http://' + v);
      } else {
        location.href = 'https://www.google.com/search?q=' + encodeURIComponent(v) + '&hl=en';
      }
    }
    inp.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') navigate();
    });
    if (goBtn) goBtn.addEventListener('click', navigate);
  </script>
</body>
</html>"""


def launch_playwright_browser(start_url: str = "about:home") -> int:
    """Launch Playwright Chromium browser with full Fomoji vault integration and 12px UI."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[CAT Browser] Playwright is not installed. Run: pip install playwright && playwright install chromium", file=sys.stderr)
        return 2

    # Auto-start local servers if the target URL requires them
    if start_url and ("8765" in start_url or "workspace" in start_url.lower()):
        try:
            import threading
            from ..web.server import ensure_fatty_server, is_server_running
            if not is_server_running(timeout=0.3):
                threading.Thread(target=lambda: ensure_fatty_server(timeout=3.0, auto_start=True), daemon=True).start()
        except Exception:
            pass

    if start_url and ("3000" in start_url or "fomoji" in start_url.lower()):
        try:
            from ..fomoji_manager import check_server_reachable, initialize_fomoji_subsystem
            if not check_server_reachable(timeout=0.6):
                initialize_fomoji_subsystem(interactive=False)
        except Exception:
            pass

    if start_url in ("about:home", "about:blank", "", None):
        html = _generate_start_page_html()
        start_url = "data:text/html;charset=utf-8," + urllib.parse.quote(html)
    elif start_url.startswith("localhost:"):
        start_url = "http://" + start_url

    vault_token = _get_fomoji_vault_token()
    user_data_dir = str(pathlib.Path.home() / ".cat_browser_playwright_data")
    pathlib.Path(user_data_dir).mkdir(parents=True, exist_ok=True)

    hb_path = pathlib.Path.home() / ".cat_browser_heartbeat"
    pending_path = pathlib.Path.home() / ".cat_pending_verification.json"
    last_pending_ts = time.time()

    print(f"[CAT Browser] Opening ultra-smooth Playwright Chromium \u2192 {start_url}")
    print("[CAT Browser] Close the browser window to return to CAT.")

    try:
        import json
        with sync_playwright() as p:
            args = [
                "--disable-blink-features=AutomationControlled",
                "--enable-features=OverlayScrollbar",
                "--window-size=1280,840",
                "--no-default-browser-check",
                "--no-first-run",
            ]
            context = p.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                args=args,
                no_viewport=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 CATBrowser/0.9.0 (PlaywrightEngine; FomojiAuthorized)",
                extra_http_headers={
                    "X-CAT-Browser": "1",
                    "X-CAT-Vault-Token": vault_token,
                },
            )

            def handle_new_page(new_page):
                try:
                    new_page.wait_for_load_state()
                except Exception:
                    pass

            context.on("page", handle_new_page)

            page = context.pages[0] if context.pages else context.new_page()
            try:
                page.goto(start_url, wait_until="domcontentloaded", timeout=15000)
            except Exception:
                pass

            # Keep process alive until user closes the window & sync heartbeats + external navigations
            last_hb = 0.0
            try:
                while True:
                    time.sleep(0.3)
                    now = time.time()
                    if now - last_hb > 1.5:
                        last_hb = now
                        try:
                            hb_path.write_text(json.dumps({"ts": now, "pid": os.getpid()}), encoding="utf-8")
                        except Exception:
                            pass

                    # Check for external navigation requests (e.g. from CLI or Fomoji auth)
                    if pending_path.exists():
                        try:
                            p_data = json.loads(pending_path.read_text(encoding="utf-8"))
                            p_ts = float(p_data.get("ts", 0))
                            if p_ts > last_pending_ts:
                                last_pending_ts = p_ts
                                target_url = p_data.get("url")
                                if target_url:
                                    np = context.new_page()
                                    np.goto(target_url)
                                    np.bring_to_front()
                        except Exception:
                            pass

                    if len(context.pages) == 0:
                        break
                    try:
                        _ = context.browser
                    except Exception:
                        break
            except KeyboardInterrupt:
                pass
            finally:
                try:
                    hb_path.unlink(missing_ok=True)
                except Exception:
                    pass
                try:
                    context.close()
                except Exception:
                    pass
        return 0
    except Exception as e:
        print(f"[CAT Browser] Playwright launch error: {e}", file=sys.stderr)
        return 1
