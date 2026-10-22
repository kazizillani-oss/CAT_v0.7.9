"""
Playwright visible browser — fallback when Qt not available.
Launches a real Chromium window (headless=False) with the URL.
This is a real browser rendering (HTML/CSS/JS), not text.
Used for CAT Browser when PySide6/PyQt not installed but Playwright is.
"""

from __future__ import annotations

import time
import sys

def launch_playwright_browser(start_url: str = "about:home") -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[CAT Browser] Playwright not installed. Run: pip install playwright && playwright install chromium", file=sys.stderr)
        return 2

    if start_url in ("about:home", "about:blank", "", None):
        # For new-tab, show a simple CAT page via data URL with real HTML
        html = f"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CAT — New Tab</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:#1a1b26;color:#e8ebfa;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:40px}}
  .wrap{{width:640px;max-width:100%;text-align:center}}
  .logo{{font-size:42px;font-weight:800;letter-spacing:0.08em;margin-bottom:28px}}
  .logo span{{color:#82aaff}}
  .search{{display:flex;align-items:center;background:#1e2030;border:1px solid #737aa2;border-radius:999px;padding:14px 18px}}
  .search input{{flex:1;background:transparent;border:none;outline:none;color:#e8ebfa;font-size:16px}}
  .grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:28px}}
  .card{{background:#1e2030;border:1px solid #737aa2;border-radius:16px;padding:18px;text-decoration:none;color:#e8ebfa;display:flex;flex-direction:column;align-items:center;gap:10px}}
  .card:hover{{border-color:#82aaff}}
</style>
<div class="wrap">
  <div class="logo">C<span>A</span>T</div>
  <div class="search"><span>🔍</span><input id="q" placeholder="Search or enter a URL" style="flex:1;background:transparent;border:none;outline:none;color:#e8ebfa;font-size:16px;margin-left:10px"></div>
  <div class="grid">
    <a class="card" href="https://youtube.com">▶<br>YouTube</a>
    <a class="card" href="https://github.com">⬢<br>GitHub</a>
    <a class="card" href="https://mail.google.com">✉<br>Gmail</a>
    <a class="card" href="http://localhost:3000/connector.html">🔗<br>Fomoji</a>
  </div>
  <div style="margin-top:22px;color:#878caf;font-size:12px">CAT Browser · Fomoji-protected · Chromium</div>
</div>
<script>
  const inp = document.getElementById('q');
  inp.addEventListener('keydown', e=>{{
    if(e.key==='Enter'){{
      const v=inp.value.trim();
      if(!v) return;
      const hasScheme=/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(v);
      const isLocal=v.includes('localhost');
      if(hasScheme||isLocal||(v.includes('.')&&!v.includes(' '))){{
        location.href = hasScheme?v:'https://'+v;
      }} else {{
        location.href='https://www.google.com/search?q='+encodeURIComponent(v)+'&hl=en';
      }}
    }}
  }});
</script>
"""
        import urllib.parse
        start_url = "data:text/html;charset=utf-8," + urllib.parse.quote(html)

    # Normalize localhost without scheme
    if start_url.startswith("localhost:"):
        start_url = "http://" + start_url

    print(f"[CAT Browser] Opening graphical browser (Playwright Chromium) → {start_url}")
    print("[CAT Browser] Close the browser window to return to CAT.")
    try:
        from pathlib import Path
        user_data_dir = str(Path.home() / ".cat_browser_playwright_data")
        with sync_playwright() as p:
            # headless=False gives a real OS window with full rendering
            # Use persistent context so Fomoji cookies persist between sessions
            context = p.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1280, "height": 800},
            )
            # For Fomoji, we need to handle new tabs (target=_blank) — open as new page
            def handle_new_page(new_page):
                new_page.wait_for_load_state()
            context.on("page", handle_new_page)
            if context.pages:
                page = context.pages[0]
            else:
                page = context.new_page()
            page.goto(start_url, wait_until="domcontentloaded", timeout=15000)
            # Keep browser open until user closes window
            try:
                while True:
                    time.sleep(0.5)
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
                    context.close()
                except Exception:
                    pass
        return 0
    except Exception as e:
        print(f"[CAT Browser] Playwright launch failed: {e}", file=sys.stderr)
        # If chromium not downloaded, try to suggest install
        if "Executable doesn't exist" in str(e) or "chromium" in str(e).lower():
            print("Run: playwright install chromium", file=sys.stderr)
        return 1
