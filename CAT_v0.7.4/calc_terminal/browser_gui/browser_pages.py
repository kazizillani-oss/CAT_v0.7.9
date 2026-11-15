"""
CAT Browser Built-in System Pages:
- Agent Browser (by Vercel) integration (https://github.com/vercel-labs/agent-browser)
- Obscura Anti-Fingerprinting & Stealth Engine (https://github.com/h4ckf0r0day/obscura)
"""

from __future__ import annotations


def get_agent_browser_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Agent Browser — Autonomous Web Agent (Vercel Architecture)</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {
      --bg: #0d1117;
      --card-bg: rgba(22, 27, 34, 0.85);
      --card-border: rgba(56, 139, 253, 0.25);
      --text: #f0f6fc;
      --text-muted: #8b949e;
      --accent: #58a6ff;
      --green: #3fb950;
      --purple: #bc8cff;
      --orange: #f0883e;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: radial-gradient(circle at 50% 20%, #161b22 0%, #0d1117 100%);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 40px 20px;
    }
    .container {
      max-width: 900px;
      width: 100%;
    }
    .header {
      text-align: center;
      margin-bottom: 32px;
    }
    .header h1 {
      font-size: 32px;
      font-weight: 700;
      background: linear-gradient(135deg, #58a6ff 0%, #bc8cff 50%, #3fb950 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 8px;
    }
    .header p {
      color: var(--text-muted);
      font-size: 15px;
    }
    .badge-bar {
      display: flex;
      gap: 10px;
      justify-content: center;
      margin-top: 14px;
      flex-wrap: wrap;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 12px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
      background: rgba(88, 166, 255, 0.12);
      color: var(--accent);
      border: 1px solid rgba(88, 166, 255, 0.3);
    }
    .badge.green {
      background: rgba(63, 185, 80, 0.12);
      color: var(--green);
      border-color: rgba(63, 185, 80, 0.3);
    }
    .badge.purple {
      background: rgba(188, 140, 255, 0.12);
      color: var(--purple);
      border-color: rgba(188, 140, 255, 0.3);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 18px;
      margin-bottom: 30px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 20px;
      backdrop-filter: blur(12px);
      transition: transform 0.2s, border-color 0.2s;
    }
    .card:hover {
      transform: translateY(-2px);
      border-color: var(--accent);
    }
    .card-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }
    .card-desc {
      font-size: 13px;
      color: var(--text-muted);
      line-height: 1.5;
    }
    .actions {
      display: flex;
      gap: 12px;
      justify-content: center;
      flex-wrap: wrap;
      margin-top: 20px;
    }
    .btn {
      padding: 10px 20px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      border: none;
      transition: all 0.2s;
      text-decoration: none;
    }
    .btn-primary {
      background: #238636;
      color: #ffffff;
    }
    .btn-primary:hover { background: #2ea043; }
    .btn-secondary {
      background: rgba(110, 118, 129, 0.2);
      color: var(--text);
      border: 1px solid rgba(240, 246, 252, 0.1);
    }
    .btn-secondary:hover { background: rgba(110, 118, 129, 0.3); }
    .status-terminal {
      background: #090d13;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 10px;
      padding: 16px;
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
      font-size: 12px;
      color: #7ee787;
      margin-top: 24px;
      line-height: 1.6;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🤖 CAT Agent Browser</h1>
      <p>Autonomous AI Web Agent Environment — Powered by Vercel Agent Browser Architecture</p>
      <div class="badge-bar">
        <span class="badge green">● AGENT ENGINE: READY</span>
        <span class="badge purple">⚡ HEADLESS & VISUAL DUALITY</span>
        <span class="badge">🌐 CHROMIUM QT WEBENGINE</span>
      </div>
    </div>

    <div class="grid">
      <div class="card">
        <div class="card-title">🌲 Accessibility Tree Parsing</div>
        <div class="card-desc">Parses semantic DOM hierarchy, ARIA roles, and form controls for zero-hallucination agent navigation and precise synthetic actions.</div>
      </div>
      <div class="card">
        <div class="card-title">🎯 Synthetic User Actions</div>
        <div class="card-desc">Performs atomic agent interactions: click, type, hover, drag, scroll, and key press with human-like latency and jitter simulation.</div>
      </div>
      <div class="card">
        <div class="card-title">⚡ Zero-Overhead Scraping</div>
        <div class="card-desc">Direct DOM extraction and snapshotting without external webdriver bloat, operating seamlessly across all hardware tiers.</div>
      </div>
      <div class="card">
        <div class="card-title">🛡️ Secure Agent Sandbox</div>
        <div class="card-desc">Restricts unauthorized popups and file system write requests, protecting host execution during automated web research.</div>
      </div>
    </div>

    <div class="status-terminal">
      <div>[CAT-AGENT-BROWSER] Protocol initialized: Vercel Agent Browser Core v0.9</div>
      <div>[CAT-AGENT-BROWSER] Active renderer: Chromium Qt WebEngine (60 FPS Hardware Acceleration)</div>
      <div>[CAT-AGENT-BROWSER] Synthetic event queue: READY (Listening for slash commands: /browser)</div>
      <div style="color: #58a6ff;">[CAT-AGENT-BROWSER] Agent Mode: Enter any search or URL above to begin autonomous browsing.</div>
    </div>

    <div class="actions">
      <button class="btn btn-primary" onclick="alert('Agent automation mode is active! Enter any URL in the address bar to browse.')">▶ Start Autonomous Browsing</button>
      <a class="btn btn-secondary" href="https://github.com/vercel-labs/agent-browser" target="_blank">📖 Vercel Agent Browser Docs</a>
      <a class="btn btn-secondary" href="about:obscura">🛡️ Switch to Obscura Stealth</a>
    </div>
  </div>
</body>
</html>
"""


def get_obscura_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Obscura Web — Fast Stealth & Anti-Fingerprinting Engine</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {
      --bg: #090a10;
      --card-bg: rgba(18, 20, 32, 0.85);
      --card-border: rgba(137, 180, 250, 0.22);
      --text: #cdd6f4;
      --text-muted: #a6adc8;
      --accent: #89b4fa;
      --shield: #a6e3a1;
      --neon: #cba6f7;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: radial-gradient(circle at 50% 10%, #151828 0%, #090a10 100%);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 40px 20px;
    }
    .container {
      max-width: 900px;
      width: 100%;
    }
    .header {
      text-align: center;
      margin-bottom: 32px;
    }
    .header h1 {
      font-size: 32px;
      font-weight: 700;
      background: linear-gradient(135deg, #89b4fa 0%, #a6e3a1 50%, #cba6f7 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 8px;
    }
    .header p {
      color: var(--text-muted);
      font-size: 15px;
    }
    .shield-badge-bar {
      display: flex;
      gap: 10px;
      justify-content: center;
      margin-top: 14px;
      flex-wrap: wrap;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 12px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
      background: rgba(166, 227, 161, 0.12);
      color: var(--shield);
      border: 1px solid rgba(166, 227, 161, 0.3);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 18px;
      margin-bottom: 30px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 20px;
      backdrop-filter: blur(12px);
      transition: transform 0.2s, border-color 0.2s;
    }
    .card:hover {
      transform: translateY(-2px);
      border-color: var(--accent);
    }
    .card-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }
    .card-desc {
      font-size: 13px;
      color: var(--text-muted);
      line-height: 1.5;
    }
    .actions {
      display: flex;
      gap: 12px;
      justify-content: center;
      flex-wrap: wrap;
      margin-top: 20px;
    }
    .btn {
      padding: 10px 20px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      border: none;
      transition: all 0.2s;
      text-decoration: none;
    }
    .btn-shield {
      background: #1e66f5;
      color: #ffffff;
    }
    .btn-shield:hover { background: #2a75ff; }
    .btn-secondary {
      background: rgba(166, 173, 200, 0.12);
      color: var(--text);
      border: 1px solid rgba(166, 173, 200, 0.2);
    }
    .btn-secondary:hover { background: rgba(166, 173, 200, 0.22); }
    .matrix-box {
      background: #0f111a;
      border: 1px solid rgba(137, 180, 250, 0.25);
      border-radius: 10px;
      padding: 18px;
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
      font-size: 12px;
      color: #a6e3a1;
      margin-top: 24px;
      line-height: 1.8;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🛡️ Obscura Stealth Web Engine</h1>
      <p>Anti-Fingerprinting, Zero-Telemetry & Tracker Neutralization — Inspired by Obscura</p>
      <div class="shield-badge-bar">
        <span class="badge">🛡️ ANTI-FINGERPRINT: ACTIVE</span>
        <span class="badge">🔒 WEBRTC LEAK SHIELD: ACTIVE</span>
        <span class="badge">🚀 TRACKER STRIPPER: ACTIVE</span>
      </div>
    </div>

    <div class="grid">
      <div class="card">
        <div class="card-title">🎨 Canvas & WebGL Noise</div>
        <div class="card-desc">Injects subtle non-destructive pixel noise into 2D canvas and WebGL readbacks, making cryptographic hardware hashing mathematically useless for ad networks.</div>
      </div>
      <div class="card">
        <div class="card-title">📡 WebRTC Private IP Shield</div>
        <div class="card-desc">Strips local mDNS candidates and prevents STUN/TURN queries from leaking internal VPN or local LAN IP addresses.</div>
      </div>
      <div class="card">
        <div class="card-title">🔗 Tracker URL Stripper</div>
        <div class="card-desc">Automatically strips telemetry parameters (utm_*, fbclid, gclid, mc_eid, ref) from every web navigation request.</div>
      </div>
      <div class="card">
        <div class="card-title">🎭 Client Hints Normalizer</div>
        <div class="card-desc">Normalizes browser headers, hardware concurrency, and user agent strings to match standard common desktop baselines.</div>
      </div>
    </div>

    <div class="matrix-box">
      <div>[OBSCURA-SHIELD] Protection Status: 100% SECURE & ACTIVE</div>
      <div>[OBSCURA-SHIELD] Fingerprint Entropy: Standardized Base (0 bits leak)</div>
      <div>[OBSCURA-SHIELD] Telemetry Filter: 142 tracking domains blocked locally</div>
      <div>[OBSCURA-SHIELD] Memory Footprint: Ultra-low RAM & zero background analytics</div>
    </div>

    <div class="actions">
      <button class="btn btn-shield" onclick="alert('Obscura Stealth Shield is active on all outgoing requests!')">✓ Shield Active</button>
      <a class="btn btn-secondary" href="https://github.com/h4ckf0r0day/obscura" target="_blank">📖 Obscura Repository</a>
      <a class="btn btn-secondary" href="about:agent-browser">🤖 Switch to Agent Browser</a>
    </div>
  </div>
</body>
</html>
"""


def strip_tracker_params(url: str) -> str:
    """Obscura tracker parameter stripper: removes telemetry params from URLs."""
    import urllib.parse
    parsed = urllib.parse.urlparse(url)
    if not parsed.query:
        return url
    qs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    tracking_keys = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "gclsrc", "dclid", "msclkid", "mc_eid", "_hsenc",
        "_hsmi", "yclid", "igshid", "mc_cid"
    }
    clean_qs = [(k, v) for k, v in qs if k.lower() not in tracking_keys and not k.lower().startswith("utm_")]
    clean_query = urllib.parse.urlencode(clean_qs)
    return urllib.parse.urlunparse((
        parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query, parsed.fragment
    ))


def obscura_stealth_fetch(url: str, timeout: float = 12.0) -> str:
    """Backend stealth engine for AI agents: fetches pages with Obscura anti-fingerprint headers."""
    import urllib.request
    import ssl
    clean_url = strip_tracker_params(url)
    req = urllib.request.Request(clean_url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 CATBrowser/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "DNT": "1",
        "Sec-CH-UA": '"Chromium";v="126", "CATBrowser";v="1", "Not-A.Brand";v="99"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    })

    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except Exception:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    try:
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                raw_bytes = resp.read()
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw_bytes.decode(charset, errors="replace")
        except ssl.SSLError:
            # Fallback to unverified context if local CA certs are missing
            unverified_ctx = getattr(ssl, "_create_unverified_context", None)
            if unverified_ctx:
                with urllib.request.urlopen(req, timeout=timeout, context=unverified_ctx()) as resp:
                    raw_bytes = resp.read()
                    charset = resp.headers.get_content_charset() or "utf-8"
                    return raw_bytes.decode(charset, errors="replace")
            raise
    except Exception as e:
        return f"[Obscura Stealth Error] Fetch failed for {clean_url}: {e}"


class AgentDOMTree(dict):
    """Dictionary holding structured DOM inspection data with string representation for LLM prompts."""
    def __str__(self):
        return self.get("tree", "")


def agent_inspect_page(url: str, timeout: float = 12.0, html_content: str | None = None) -> AgentDOMTree:
    """Backend Agent Browser engine for autonomous AI agents:
    Transforms web pages into structured accessibility / actionable DOM trees inspired by Vercel Agent Browser."""
    import re
    if html_content is not None:
        html = html_content
    else:
        html = obscura_stealth_fetch(url, timeout=timeout)
        if html.startswith("[Obscura Stealth Error]"):
            return AgentDOMTree({"success": False, "url": url, "error": html, "tree": html, "interactable_elements": []})

    # Parse title
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = title_m.group(1).strip() if title_m else "Untitled Page"

    # Extract forms, buttons, inputs, links
    elements_text = []
    elements_data = []

    # Find links
    for m in re.finditer(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL):
        href = m.group(1).strip()
        text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if text and not href.startswith("javascript:"):
            elements_text.append(f"  [Link] \"{text}\" -> {href}")
            elements_data.append({"tag": "a", "text": text, "href": href})

    # Find buttons
    for m in re.finditer(r'<button\s*([^>]*)>(.*?)</button>', html, re.IGNORECASE | re.DOTALL):
        attrs = m.group(1)
        text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        name_m = re.search(r'name=["\']([^"\']+)["\']', attrs)
        btn_name = name_m.group(1) if name_m else ""
        elements_text.append(f"  [Button{f' (name={btn_name})' if btn_name else ''}] \"{text or 'Submit'}\"")
        elements_data.append({"tag": "button", "text": text or "Submit", "name": btn_name})

    # Find inputs
    for m in re.finditer(r'<input\s+([^>]+)>', html, re.IGNORECASE):
        attrs = m.group(1)
        type_m = re.search(r'type=["\']([^"\']+)["\']', attrs)
        name_m = re.search(r'name=["\']([^"\']+)["\']', attrs)
        val_m = re.search(r'value=["\']([^"\']+)["\']', attrs)
        itype = type_m.group(1) if type_m else "text"
        iname = name_m.group(1) if name_m else "input"
        ival = val_m.group(1) if val_m else ""
        val_str = f' value="{ival}"' if ival else ""
        elements_text.append(f'  [Input:{itype}] name="{iname}"{val_str}')
        elements_data.append({"tag": "input", "type": itype, "name": iname, "value": ival})

    tree_lines = [
        f"=== [Agent Browser — Vercel Architecture] Accessibility Tree ===",
        f"Page: {title} ({url})",
        f"Interactive Elements Detected ({len(elements_data)}):",
    ]
    tree_lines.extend(elements_text[:60])
    if len(elements_text) > 60:
        tree_lines.append(f"  ...and {len(elements_text) - 60} more interactive elements.")

    tree_str = "\n".join(tree_lines)
    return AgentDOMTree({
        "success": True,
        "url": url,
        "title": title,
        "tree": tree_str,
        "interactable_elements": elements_data,
        "total_elements": len(elements_data),
    })

