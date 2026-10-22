"""
DEPRECATED — Developer Tools / diagnostic text browser. NOT the normal Browser Mode.

This module is a text-based HTML parser for developer diagnostics only.
It does NOT render real HTML/CSS/JavaScript — it scrapes HTML and converts
it to terminal text. This is NOT a browser.

Normal Browser Mode uses calc_terminal.host.desktop.EmbeddedBrowserPane
(QWebEngineView = real Chromium) instead.

This module remains available for:
  - Developer diagnostics (CAT_BROWSER_DEBUG=1)
  - Text extraction / page analysis
  - Offline fallback when PySide6 is not installed

Do NOT use this as the primary browser renderer.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import textwrap
import time
import urllib.parse
import urllib.request
import urllib.error
import http.cookiejar
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Optional `requests` — nicer redirect/cookie/gzip handling; fallback is stdlib.
# ---------------------------------------------------------------------------
try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except ImportError:
    requests = None  # type: ignore
    _HAS_REQUESTS = False

# Optional imaging + Chromium for visual browsing (images / WebGL / 3D)
try:
    from PIL import Image as _PILImage  # type: ignore
    _HAS_PIL = True
except ImportError:
    _PILImage = None  # type: ignore
    _HAS_PIL = False

try:
    from .browser.engine import BrowserEngine, BrowserUnavailableError, PLAYWRIGHT_AVAILABLE  # type: ignore
    _HAS_CHROMIUM = PLAYWRIGHT_AVAILABLE
except Exception:
    BrowserEngine = None  # type: ignore
    BrowserUnavailableError = RuntimeError  # type: ignore
    _HAS_CHROMIUM = False

# ---------------------------------------------------------------------------
# Paths — bookmarks + history (append-only, bounded).
# ---------------------------------------------------------------------------

_BOOKMARKS_PATH = Path.home() / ".cat_browser_bookmarks.json"
_HISTORY_PATH = Path.home() / ".cat_browser_history.json"
_DOWNLOAD_DIR = Path.home() / "Downloads"

# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

_HOME_HTML = """\
<!doctype html>
<title>CAT Browser — Home</title>
<h1>CAT Browser — Software-grade Terminal Browser</h1>
<p>No external Chrome needed. This is your full terminal browser — search, images, 3D/WebGL all inside CAT.</p>
<h2>Quick actions</h2>
<ul>
<li>Type a URL: <code>open https://example.com</code> or just <code>https://example.com</code></li>
<li>Search: <code>search cats on mars</code> (DuckDuckGo) or <code>search google cats</code> / <code>g cats</code> (Google)</li>
<li>Follow a link: type its number (e.g. <code>3</code>) or <code>open 3</code></li>
<li>Navigate: <code>back</code> <code>forward</code> <code>reload</code> <code>home</code></li>
<li>Images: <code>img 2</code> renders image #2 inline (png/jpg/webp/gif/svg/avif) — any format</li>
<li>3D/WebGL: <code>visual</code> renders the page via Chromium → ANSI (for three.js / maps / heavy canvas)</li>
<li>Inspect: <code>links</code> <code>find cats</code> <code>source</code> <code>save page.html</code></li>
<li>Bookmarks: <code>bookmark</code> <code>bookmarks</code> <code>open bookmark 1</code></li>
<li>History: <code>history</code>  — Quit: <code>q</code></li>
</ul>
<h2>Suggestions — try 3D!</h2>
<ul>
<li><a href="https://example.com">example.com — test page</a></li>
<li><a href="https://threejs.org/examples/#webgl_animation_keyframes">three.js — WebGL animation (3D test)</a></li>
<li><a href="https://news.ycombinator.com">Hacker News</a></li>
<li><a href="https://en.wikipedia.org/wiki/Main_Page">Wikipedia</a></li>
<li><a href="https://duckduckgo.com">DuckDuckGo</a> — <a href="https://www.google.com">Google</a></li>
</ul>
"""

_ABOUT_HOME_URL = "about:home"
_ABOUT_BLANK_URL = "about:blank"

_DDG_HTML_URL = "https://html.duckduckgo.com/html/?q={q}"
_GOOGLE_HTML_URL = "https://www.google.com/search?q={q}&hl=en&gbv=1"
# CAT Browser supports both search engines; default is duckduckgo (privacy),
# `search google cats` or `g cats` forces Google.
_DEFAULT_SEARCH_ENGINE = "duckduckgo"  # or "google"


def normalize_url(raw: str, base: Optional[str] = None) -> str:
    """Turn user input into an absolute URL or raise ValueError."""
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("empty url")
    if raw.lower() in ("home", "about:home", _ABOUT_HOME_URL):
        return _ABOUT_HOME_URL
    if raw.lower() in ("about:blank", "blank"):
        return _ABOUT_BLANK_URL
    # If input has no dot/slash/scheme and is not about:, treat as search.
    # Caller can force a real URL with `open`.
    if base:
        # Resolve relative against base (for link following).
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", raw) and not raw.startswith("about:"):
            return urllib.parse.urljoin(base, raw)
    # Absolute with scheme?
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw):
        return raw
    if raw.startswith("about:"):
        return raw
    # Looks like a domain or host:port without scheme?
    # Heuristic: contains a dot OR colon+port OR starts with localhost.
    if re.match(r"^(localhost(:\d+)?)(/|$)", raw, re.I) or "." in raw.split("/")[0]:
        # If it has no scheme but looks like a host, assume https.
        # Localhost gets http by default.
        if raw.lower().startswith("localhost"):
            return "http://" + raw
        return "https://" + raw
    raise ValueError(f"not a URL: {raw!r}")


def _is_search_query(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    # Obvious URL-ish -> not a query
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", t):
        return False
    if t.lower().startswith("about:"):
        return False
    # Host-like (has dot before any space) -> not a query
    first_token = t.split()[0] if " " in t else t
    if "." in first_token and " " not in first_token and "/" not in t.split(" ")[0]:
        # But "cats vs dogs" has no dot -> query; "example.com" -> url
        # Check TLD-ish: dot with 2+ char suffix
        if re.search(r"\.[a-z]{2,}($|/|:)", first_token, re.I):
            return False
    # Default: if it contains a space, it's a query. Single word without
    # dot is ambiguous — treat as query so the browser is forgiving.
    return True


def _search_url(query: str, engine: Optional[str] = None) -> str:
    q = urllib.parse.quote_plus(query.strip())
    eng = (engine or _DEFAULT_SEARCH_ENGINE).lower().strip()
    if eng in ("google", "g", "goog"):
        return _GOOGLE_HTML_URL.format(q=q)
    # duckduckgo, ddg, d, duck
    return _DDG_HTML_URL.format(q=q)


def _detect_search_engine(raw: str) -> Tuple[str, str]:
    """Return (engine, query) from raw search input.

    Supports:
      search cats                 -> (ddg, cats)
      search google cats          -> (google, cats)
      g cats                      -> (google, cats)
      ddg cats                    -> (ddg, cats)
    """
    s = raw.strip()
    low = s.lower()
    # Explicit engine prefix
    for prefix, eng in [("google ", "google"), ("g ", "google"), ("goog ", "google"),
                        ("duckduckgo ", "duckduckgo"), ("ddg ", "duckduckgo"), ("d ", "duckduckgo")]:
        if low.startswith(prefix):
            return eng, s[len(prefix):].strip()
    # "search google cats" pattern (already stripped leading search/s)
    if low.startswith("google "):
        return "google", s[7:].strip()
    if low.startswith("ddg "):
        return "duckduckgo", s[4:].strip()
    return _DEFAULT_SEARCH_ENGINE, s


# ---------------------------------------------------------------------------
# Fetch — unified over requests / urllib, with cookies + UA.
# ---------------------------------------------------------------------------

_UA = "CAT-Browser/0.7.10 (+terminal; like Lynx/2.9)"

_cookie_jar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cookie_jar))

_session = None
if _HAS_REQUESTS:
    try:
        _session = requests.Session()
        _session.headers.update({"User-Agent": _UA})
    except Exception:
        _session = None


@dataclass
class FetchResult:
    url: str               # final URL after redirects
    requested_url: str     # original request
    status: int
    headers: Dict[str, str]
    body: bytes
    text: str              # decoded
    error: Optional[str] = None
    elapsed_ms: int = 0
    from_cache: bool = False


def _decode_body(body: bytes, headers: Dict[str, str]) -> str:
    # Try charset from Content-Type, else utf-8 with replacement.
    ctype = headers.get("content-type", "") or headers.get("Content-Type", "")
    charset = "utf-8"
    m = re.search(r"charset=([^\s;\"']+)", ctype, re.I)
    if m:
        charset = m.group(1).strip().strip('"').strip("'")
    for cand in (charset, "utf-8", "windows-1252", "iso-8859-1"):
        try:
            return body.decode(cand)
        except Exception:
            continue
    return body.decode("utf-8", errors="replace")


def fetch_url(url: str, timeout: int = 18) -> FetchResult:
    """Fetch one URL. about: urls synthesize a local page without network."""
    req_url = url
    if url in (_ABOUT_HOME_URL, _ABOUT_BLANK_URL):
        body = _HOME_HTML.encode("utf-8") if url == _ABOUT_HOME_URL else b"<title>blank</title>"
        return FetchResult(
            url=url, requested_url=req_url, status=200,
            headers={"content-type": "text/html; charset=utf-8"},
            body=body, text=body.decode("utf-8"),
        )
    t0 = time.monotonic()
    # Gate: Fomoji must still be valid at fetch time (not just at launch).
    # Whitelist: the Fomoji server itself (localhost) must remain browsable
    # even before a CAT session exists — otherwise the device flow's own
    # verification page would be blocked by the gate that it's trying to
    # solve (chicken-and-egg).  Same for about: URLs (handled above).
    try:
        from . import fomoji_auth as _fa  # pylint: disable=import-outside-toplevel
        is_fomoji_local = False
        try:
            parsed_u = urllib.parse.urlparse(url)
            host = (parsed_u.hostname or "").lower()
            fomoji_host = urllib.parse.urlparse(_fa.get_fomoji_url()).hostname or ""
            if host and fomoji_host and host == fomoji_host.lower():
                is_fomoji_local = True
            if host in ("localhost", "127.0.0.1", "::1"):
                is_fomoji_local = True
        except Exception:
            pass
        if not is_fomoji_local and not _fa.is_skip_enabled() and _fa.status() != "connected":
            return FetchResult(
                url=url, requested_url=req_url, status=0,
                headers={}, body=b"", text="",
                error="Fomoji session lost — run `cat --auth login` and reopen the browser.",
                elapsed_ms=int((time.monotonic() - t0) * 1000),
            )
    except Exception:
        pass  # fomoji_auth missing in some test sandboxes — don't block fetching

    # Prefer requests (cleaner gzip/deflate + redirects)
    if _HAS_REQUESTS and _session is not None:
        try:
            resp = _session.get(url, timeout=timeout, allow_redirects=True)
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            body = resp.content or b""
            text = resp.text if resp.text else _decode_body(body, hdrs)
            return FetchResult(
                url=str(resp.url), requested_url=req_url,
                status=int(resp.status_code), headers=hdrs,
                body=body, text=text,
                elapsed_ms=int((time.monotonic() - t0) * 1000),
                error=None if resp.ok else f"HTTP {resp.status_code}",
            )
        except Exception as e:
            # Fall through to urllib for a second try on some errors.
            if isinstance(e, KeyboardInterrupt):
                raise
            # If requests fails outright (no network, DNS...), try urllib once
            # before surfacing — urllib sometimes has different proxy handling.
            pass

    # urllib fallback
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with _opener.open(req, timeout=timeout) as resp:  # type: ignore
            status = int(getattr(resp, "status", 200) or 200)
            hdrs = {k.lower(): v for k, v in (getattr(resp, "headers", {}) or {}).items()}  # type: ignore
            body = resp.read()
            text = _decode_body(body, hdrs)
            final_url = getattr(resp, "url", url) or url
            return FetchResult(
                url=str(final_url), requested_url=req_url,
                status=status, headers=hdrs, body=body, text=text,
                elapsed_ms=int((time.monotonic() - t0) * 1000),
            )
    except urllib.error.HTTPError as e:
        hdrs = {k.lower(): v for k, v in (getattr(e, "headers", {}) or {}).items()}
        body = e.read() if hasattr(e, "read") else b""
        text = _decode_body(body, hdrs) if body else ""
        return FetchResult(
            url=url, requested_url=req_url, status=int(e.code),
            headers=hdrs, body=body, text=text,
            elapsed_ms=int((time.monotonic() - t0) * 1000),
            error=f"HTTP {e.code} {e.reason}",
        )
    except urllib.error.URLError as e:
        return FetchResult(
            url=url, requested_url=req_url, status=0,
            headers={}, body=b"", text="",
            error=f"Network error: {e.reason}",
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        )
    except Exception as e:
        return FetchResult(
            url=url, requested_url=req_url, status=0,
            headers={}, body=b"", text="",
            error=f"{type(e).__name__}: {e}",
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        )


# ---------------------------------------------------------------------------
# Visual helpers — inline images (any format) + 3D/WebGL via Chromium screenshot
# ---------------------------------------------------------------------------

def _term_supports_truecolor() -> bool:
    return True  # we emit 24-bit and terminals that don't support it degrade gracefully


def render_image_to_ansi(image_bytes: bytes, term_width: int = 60, max_height: int = 24) -> str:
    """Convert any image format (png/jpg/webp/gif/svg…) to half-block ANSI art.

    Uses PIL when available (handles png/jpg/webp/gif/bmp; SVG via cairosvg
    fallback to placeholder). Falls back to a placeholder when PIL missing.
    WebGL/3D sites are handled by Chromium screenshot → this same path.
    """
    if not _HAS_PIL or not image_bytes:
        return "  [image: PIL not installed — pip install pillow to render images inline]"
    try:
        import io
        # Handle SVG separately — try cairosvg, else placeholder
        # Detect SVG by content
        head = image_bytes[:512].lstrip().lower()
        if head.startswith(b"<svg") or b"<svg" in head[:1024]:
            try:
                import cairosvg  # type: ignore
                png_bytes = cairosvg.svg2png(bytestring=image_bytes)
                img = _PILImage.open(io.BytesIO(png_bytes)).convert("RGBA")
            except Exception:
                return "  [svg image — install cairosvg to render inline]"
        else:
            img = _PILImage.open(io.BytesIO(image_bytes)).convert("RGBA")
        # Handle GIF animation — use first frame
        try:
            img.seek(0)
        except Exception:
            pass
        # Composite RGBA over white (or terminal bg) for ANSI
        bg = _PILImage.new("RGBA", img.size, (255, 255, 255, 255))
        try:
            bg.paste(img, (0, 0), img)
        except Exception:
            bg = img.convert("RGB")  # type: ignore
        else:
            bg = bg.convert("RGB")
        img = bg
        # Target size — preserve aspect, use half-block (2 pixels per row)
        w, h = img.size
        aspect = h / max(1, w)
        target_w = min(term_width, max(20, term_width - 4))
        target_h = int(target_w * aspect * 0.5)  # 0.5 because '▀' is half-height
        target_h = min(max_height * 2, max(6, target_h))
        # Ensure even height for pairing
        if target_h % 2 == 1:
            target_h += 1
        img = img.resize((target_w, target_h), _PILImage.LANCZOS)  # type: ignore
        pixels = img.load()
        lines: List[str] = []
        for y in range(0, target_h, 2):
            line = "  "
            for x in range(target_w):
                r1, g1, b1 = pixels[x, y]  # type: ignore
                r2, g2, b2 = pixels[x, y + 1]  # type: ignore
                # Use foreground for upper pixel, background for lower, char '▀'
                line += f"\x1b[38;2;{r1};{g1};{b1}m\x1b[48;2;{r2};{g2};{b2}m▀"
            line += "\x1b[0m"
            lines.append(line)
        return "\n".join(lines)
    except Exception as e:
        return f"  [image render failed: {e}]"


def _fetch_image_bytes(url: str, timeout: int = 12) -> Optional[bytes]:
    try:
        if _HAS_REQUESTS and _session is not None:
            r = _session.get(url, timeout=timeout)
            if r.ok and r.content:
                ctype = r.headers.get("content-type", "").lower()
                if "image" in ctype or len(r.content) > 100:
                    return r.content
        # urllib fallback
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with _opener.open(req, timeout=timeout) as resp:  # type: ignore
            data = resp.read(5 * 1024 * 1024)  # cap 5MB
            return data
    except Exception:
        return None
    return None


class VisualBrowser:
    """Chromium-backed visual browser for 3D/WebGL and pixel-perfect screenshots.

    Wraps `BrowserEngine` (Playwright) to load any remote URL, wait for
    WebGL/JS to settle, capture a PNG screenshot, and convert it to ANSI via
    `render_image_to_ansi`.  Falls back to text mode when Chromium not installed.
    """

    def __init__(self):
        self._engine = None
        self._ready = False

    def available(self) -> bool:
        return _HAS_CHROMIUM and BrowserEngine is not None  # type: ignore

    def ensure(self) -> bool:
        if not self.available():
            return False
        if self._ready and self._engine and getattr(self._engine, "available", False):
            return True
        try:
            eng = BrowserEngine(headless=True)  # type: ignore
            eng.start(timeout=15)
            self._engine = eng
            self._ready = True
            return True
        except Exception:
            self._ready = False
            return False

    def screenshot_ansi(self, url: str, term_width: int = 72, timeout: int = 20) -> Optional[str]:
        if not self.ensure():
            return None
        try:
            eng = self._engine
            # Navigate
            snap = eng.navigate(url, timeout=timeout * 1000)  # type: ignore
            # Take screenshot to temp file
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                tmp_path = tf.name
            ok = eng.screenshot(tmp_path)  # type: ignore
            if not ok:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except Exception:
                    pass
                return None
            try:
                data = Path(tmp_path).read_bytes()
                ansi = render_image_to_ansi(data, term_width=term_width, max_height=28)
                return ansi
            finally:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except Exception:
                    pass
        except Exception:
            return None

    def close(self):
        if self._engine:
            try:
                self._engine.close()  # type: ignore
            except Exception:
                pass
            self._engine = None
            self._ready = False


# Singleton visual browser (lazy)
_visual_browser: Optional[VisualBrowser] = None

def get_visual_browser() -> VisualBrowser:
    global _visual_browser
    if _visual_browser is None:
        _visual_browser = VisualBrowser()
    return _visual_browser


# ---------------------------------------------------------------------------
# HTML → structured page (stdlib html.parser only — no bs4 required)
# ---------------------------------------------------------------------------

@dataclass
class Link:
    href: str
    text: str
    absolute: str  # resolved against base URL


@dataclass
class ParsedPage:
    title: str
    text_lines: List[str] = field(default_factory=list)
    links: List[Link] = field(default_factory=list)
    headings: List[Tuple[int, str]] = field(default_factory=list)
    images: List[Dict[str, str]] = field(default_factory=list)
    meta_desc: str = ""
    raw_text: str = ""
    warnings: List[str] = field(default_factory=list)


class _CatHTMLParser(HTMLParser):
    """Tiny readable extractor — not a full layout engine.  Good enough for
    a terminal browser's text view and for AI / humans to follow links."""

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_parts: List[str] = []
        self.in_title = False
        self.in_script = False
        self.in_style = False
        self.in_head = False
        self.current_heading: Optional[int] = None
        self.heading_buf = ""
        self.block_stack: List[str] = []
        self.line_buf = ""
        self.lines: List[str] = []
        self.links: List[Link] = []
        self._link_href: Optional[str] = None
        self._link_text_parts: List[str] = []
        self._in_anchor = False
        self.headings: List[Tuple[int, str]] = []
        self.images: List[Dict[str, str]] = []
        self.meta_desc = ""
        self.warnings: List[str] = []

    # ---- helpers ----------------------------------------------------------
    def _flush_line(self):
        line = self.line_buf.strip()
        if line:
            # Collapse internal whitespace to single spaces for terminal.
            line = re.sub(r"\s+", " ", line)
            self.lines.append(line)
        self.line_buf = ""

    def _push_block(self, tag: str):
        if tag in ("p", "div", "section", "article", "li", "tr", "br",
                   "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre"):
            self._flush_line()
        self.block_stack.append(tag)

    def _pop_block(self, tag: str):
        if tag in ("p", "div", "section", "article", "li", "ul", "ol",
                   "blockquote", "pre", "table"):
            self._flush_line()
        if self.block_stack and self.block_stack[-1] == tag:
            self.block_stack.pop()

    # ---- parser callbacks -------------------------------------------------
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        ad = {k.lower(): (v or "") for k, v in attrs}
        if tag == "head":
            self.in_head = True
        if tag == "title":
            self.in_title = True
        if tag == "script":
            self.in_script = True
            self.warnings.append("page contains JavaScript (not executed in terminal)")
        if tag == "style":
            self.in_style = True
        if tag in ("script", "style", "noscript"):
            return

        # Head metadata
        if tag == "meta":
            name = (ad.get("name", "") or ad.get("property", "")).lower()
            if name in ("description", "og:description"):
                self.meta_desc = ad.get("content", "")[:300]

        # Images — any format (png/jpg/webp/gif/svg/avif) captured for inline ANSI
        if tag == "img":
            src = ad.get("src", "")
            alt = ad.get("alt", "") or ad.get("title", "") or (src.split("/")[-1].split("?")[0] if src else "")
            self.images.append({"src": src, "alt": alt[:120]})
            # Inline an image placeholder into the text flow
            label = f"[img: {alt[:40]}]" if alt else "[img]"
            self.line_buf += f" {label} "
        # Canvas / WebGL detection — hint to use visual mode for 3D
        if tag == "canvas":
            self.warnings.append("3D canvas detected — type `visual` for WebGL rendering (Chromium)")
        if tag == "script":
            # Quick heuristic for WebGL/three.js
            src_attr = ad.get("src", "").lower()
            if any(k in src_attr for k in ("three", "webgl", "babylon", "playcanvas")):
                self.warnings.append("3D/WebGL script detected — `visual` will render it correctly")

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._flush_line()
            self.current_heading = int(tag[1])
            self.heading_buf = ""

        if tag == "a":
            href = ad.get("href", "").strip()
            # Skip fragment-only, javascript:, mailto:
            if href and not href.lower().startswith(("javascript:", "mailto:", "tel:")):
                # Resolve now against base URL.
                try:
                    abs_href = urllib.parse.urljoin(self.base_url, href)
                except Exception:
                    abs_href = href
                self._link_href = abs_href
                self._link_text_parts = []
                self._in_anchor = True
                # Put a marker in the line so link text is visible inline.
                self.line_buf += " "

        if tag == "li":
            self.line_buf += "  • "

        if tag == "br":
            self._flush_line()

        self._push_block(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "head":
            self.in_head = False
        if tag == "title":
            self.in_title = False
        if tag == "script":
            self.in_script = False
        if tag == "style":
            self.in_style = False
        if tag in ("script", "style"):
            return

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = self.heading_buf.strip()
            if text:
                text = re.sub(r"\s+", " ", text)
                lvl = self.current_heading or 2
                self.headings.append((lvl, text))
                self.lines.append(text)  # also in flow for now; renderer prefixes #/##
                self.lines.append("")  # breathing room
            self.current_heading = None
            self.heading_buf = ""

        if tag == "a" and self._in_anchor:
            link_text = re.sub(r"\s+", " ", "".join(self._link_text_parts).strip())
            if not link_text:
                link_text = self._link_href or ""
                link_text = link_text.split("/")[-1].split("?")[0][:40] or link_text[:40]
            if self._link_href:
                self.links.append(Link(href=self._link_href, text=link_text[:120], absolute=self._link_href))
                # Update the last line fragment to carry a visible marker — the
                # renderer turns this into `text [n]` inline.
                # We do it by appending a marker token that render() can count.
                # Instead of post-processing, keep it simple: leave link_text
                # in the line_buf and let render enumerate links separately.
                pass
            self._in_anchor = False
            self._link_href = None
            self._link_text_parts = []

        self._pop_block(tag)

    def handle_data(self, data):
        if self.in_script or self.in_style:
            return
        if self.in_title:
            self.title_parts.append(data)
            return
        if self.current_heading is not None:
            self.heading_buf += data
            return
        if self._in_anchor:
            self._link_text_parts.append(data)
            self.line_buf += data
            return
        # Whitelist: only emit text outside head (or in body fallback)
        # Some pages omit explicit <body> — just accept data anywhere not in head/title.
        if self.in_head:
            return
        self.line_buf += data

    def handle_entityref(self, name):
        # html.parser convert_charrefs handles most; keep for numeric.
        self.handle_data(html.unescape(f"&{name};"))

    def close(self):
        super().close()
        self._flush_line()
        # Deduplicate warnings
        seen = set()
        uniq = []
        for w in self.warnings:
            if w not in seen:
                seen.add(w)
                uniq.append(w)
        self.warnings = uniq


def parse_html(html_text: str, base_url: str) -> ParsedPage:
    p = _CatHTMLParser(base_url)
    try:
        p.feed(html_text)
        p.close()
    except Exception as e:
        p.warnings.append(f"parse warning: {e}")
        try:
            p.close()
        except Exception:
            pass

    title = re.sub(r"\s+", " ", "".join(p.title_parts).strip())[:180]
    if not title:
        # Fallback: first heading
        title = p.headings[0][1][:80] if p.headings else ""
    # Filter empty lines, cap
    text_lines: List[str] = []
    for ln in p.lines:
        s = ln.strip()
        if not s:
            if text_lines and text_lines[-1] != "":
                text_lines.append("")
            continue
        text_lines.append(s)
    # Trim trailing empties, cap at 800 lines (terminal can't show more usefully)
    while text_lines and text_lines[-1] == "":
        text_lines.pop()
    if len(text_lines) > 800:
        text_lines = text_lines[:800] + ["", "… (truncated — save to view full source)"]

    return ParsedPage(
        title=title or "(untitled)",
        text_lines=text_lines,
        links=p.links[:120],
        headings=p.headings[:24],
        images=p.images[:48],
        meta_desc=p.meta_desc,
        raw_text="\n".join(text_lines),
        warnings=p.warnings[:6],
    )


# ---------------------------------------------------------------------------
# Browser session — history, bookmarks, rendering, I/O
# ---------------------------------------------------------------------------

@dataclass
class HistoryEntry:
    url: str
    title: str
    fetched_at: float


@dataclass
class Bookmark:
    url: str
    title: str
    added_at: float


class BrowserSession:
    """One browser session: one cookie jar, one history stack, one view."""

    def __init__(self):
        self.history: List[HistoryEntry] = []
        self.history_index: int = -1  # -1 = empty, 0..len-1
        self.bookmarks: List[Bookmark] = []
        self._cache: Dict[str, FetchResult] = {}  # url -> last fetch
        self._parsed_cache: Dict[str, ParsedPage] = {}
        self.current_url: str = ""
        self.current_result: Optional[FetchResult] = None
        self.current_parsed: Optional[ParsedPage] = None
        self.last_find_hits: List[int] = []  # line numbers
        self._load_bookmarks()
        self._load_history()

    # ---- persistence ------------------------------------------------------
    def _load_bookmarks(self):
        try:
            if _BOOKMARKS_PATH.exists():
                raw = json.loads(_BOOKMARKS_PATH.read_text(encoding="utf-8"))
                for item in raw if isinstance(raw, list) else []:
                    if isinstance(item, dict) and item.get("url"):
                        self.bookmarks.append(Bookmark(
                            url=item["url"], title=item.get("title", item["url"]),
                            added_at=item.get("added_at", time.time()),
                        ))
        except Exception:
            pass

    def _save_bookmarks(self):
        try:
            data = [{"url": b.url, "title": b.title, "added_at": b.added_at} for b in self.bookmarks]
            _BOOKMARKS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load_history(self):
        try:
            if _HISTORY_PATH.exists():
                raw = json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    # Only keep last 200
                    for item in raw[-200:]:
                        if isinstance(item, dict) and item.get("url"):
                            self.history.append(HistoryEntry(
                                url=item["url"], title=item.get("title", ""),
                                fetched_at=item.get("fetched_at", time.time()),
                            ))
                    if self.history:
                        self.history_index = len(self.history) - 1
                        self.current_url = self.history[-1].url
        except Exception:
            pass

    def _persist_history(self):
        try:
            # Keep last 200 entries
            data = [{"url": h.url, "title": h.title, "fetched_at": h.fetched_at} for h in self.history[-200:]]
            _HISTORY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ---- navigation -------------------------------------------------------
    def navigate(self, url: str, push_history: bool = True, use_cache: bool = False) -> FetchResult:
        url = url.strip()
        # Allow search queries to auto-become DDG URLs when the caller
        # passes them through open/search.
        if _is_search_query(url) and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url) and not url.lower().startswith("about:"):
            # Only auto-search when called via search path; navigate() itself
            # is for real URLs.  Callers that want search should call search().
            pass
        # about: handling — no network
        if url in (_ABOUT_HOME_URL, _ABOUT_BLANK_URL):
            result = fetch_url(url)
            parsed = parse_html(result.text, url)
        else:
            # Cache hit?
            if use_cache and url in self._cache:
                result = self._cache[url]
                parsed = self._parsed_cache.get(url) or parse_html(result.text, result.url)
            else:
                result = fetch_url(url)
                if result.text and result.status in (200, 304):
                    parsed = parse_html(result.text, result.url)
                else:
                    # Error page: still try to parse body if any, else synthetic
                    if result.text:
                        parsed = parse_html(result.text, result.url)
                    else:
                        parsed = ParsedPage(title=f"Error — {result.error or 'no content'}",
                                            text_lines=[result.error or "No content.",
                                                        f"Requested: {result.requested_url}",
                                                        f"Final: {result.url}",
                                                        f"Status: {result.status}"],
                                            warnings=[])

        final_url = result.url or url
        self.current_url = final_url
        self.current_result = result
        self.current_parsed = parsed
        self._cache[final_url] = result
        self._parsed_cache[final_url] = parsed

        if push_history:
            # Truncate forward history on new navigation (standard browser)
            if self.history_index < len(self.history) - 1:
                self.history = self.history[:self.history_index + 1]
            self.history.append(HistoryEntry(url=final_url, title=parsed.title, fetched_at=time.time()))
            self.history_index = len(self.history) - 1
            self._persist_history()
        else:
            # Replace current entry's URL/title in place (back/forward)
            if 0 <= self.history_index < len(self.history):
                self.history[self.history_index] = HistoryEntry(url=final_url, title=parsed.title, fetched_at=time.time())
                self._persist_history()

        self.last_find_hits = []
        return result

    def search(self, query: str, engine: Optional[str] = None) -> FetchResult:
        # Support `google cats` prefix inside query itself
        eng, q = _detect_search_engine(query)
        if engine:
            eng = engine
        else:
            # If caller passed "google cats" we already split; use detected
            query = q if q else query
            eng = eng if q != query else (engine or _DEFAULT_SEARCH_ENGINE)
            # Re-detect if original query had no prefix but we used fallback
            if q == query and engine is None:
                eng, q2 = _detect_search_engine(query)
                if q2 != query:
                    query = q2
                    eng = eng
        return self.navigate(_search_url(query, engine=eng), push_history=True)

    def back(self) -> Optional[FetchResult]:
        if self.history_index <= 0:
            return None
        self.history_index -= 1
        url = self.history[self.history_index].url
        return self.navigate(url, push_history=False, use_cache=True)

    def forward(self) -> Optional[FetchResult]:
        if self.history_index >= len(self.history) - 1:
            return None
        self.history_index += 1
        url = self.history[self.history_index].url
        return self.navigate(url, push_history=False, use_cache=True)

    def reload(self) -> FetchResult:
        url = self.current_url or _ABOUT_HOME_URL
        # Bust cache
        self._cache.pop(url, None)
        self._parsed_cache.pop(url, None)
        return self.navigate(url, push_history=False)

    def can_back(self) -> bool:
        return self.history_index > 0

    def can_forward(self) -> bool:
        return 0 <= self.history_index < len(self.history) - 1

    # ---- bookmarks --------------------------------------------------------
    def add_bookmark(self, url: Optional[str] = None, title: Optional[str] = None) -> Bookmark:
        u = url or self.current_url
        if not u or u in (_ABOUT_BLANK_URL, ""):
            raise ValueError("no page to bookmark")
        t = title or (self.current_parsed.title if self.current_parsed else u) or u
        # Deduplicate by URL
        for b in self.bookmarks:
            if b.url == u:
                return b
        bm = Bookmark(url=u, title=t, added_at=time.time())
        self.bookmarks.append(bm)
        self._save_bookmarks()
        return bm

    def remove_bookmark(self, index: int) -> Optional[Bookmark]:
        if 0 <= index < len(self.bookmarks):
            bm = self.bookmarks.pop(index)
            self._save_bookmarks()
            return bm
        return None

    def find_on_page(self, query: str) -> List[int]:
        if not self.current_parsed:
            return []
        q = query.lower()
        hits = [i for i, ln in enumerate(self.current_parsed.text_lines) if q in ln.lower()]
        self.last_find_hits = hits
        return hits

    # ---- save -------------------------------------------------------------
    def save_current(self, path: str) -> str:
        if not self.current_result or not self.current_result.body:
            raise ValueError("nothing to save")
        p = Path(os.path.expanduser(path)).resolve()
        if p.is_dir():
            # Derive filename from URL
            name = urllib.parse.urlparse(self.current_url).path.split("/")[-1] or "page.html"
            if not name.endswith((".html", ".htm", ".txt")):
                name += ".html"
            p = p / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(self.current_result.body)
        return str(p)


def _render_images_inline(session: BrowserSession, cw: int, use_color: bool) -> List[str]:
    """Try to render a few page images inline as ANSI art (pillow + fetch).

    Returns lines to inject into the page render.  Fails gracefully —
    text placeholders are already in the main render, so this is additive.
    """
    lines: List[str] = []
    if not session.current_parsed or not session.current_parsed.images:
        return lines
    # Limit to first 3 images to keep terminal responsive
    for im in session.current_parsed.images[:3]:
        src = im.get("src", "")
        if not src:
            continue
        # Resolve against page URL
        try:
            abs_url = urllib.parse.urljoin(session.current_url, src)
        except Exception:
            abs_url = src
        # Only attempt http(s) images (skip data: for now)
        if not abs_url.lower().startswith(("http://", "https://")):
            continue
        # Skip tiny icons / tracking pixels quickly
        # Fetch
        data = _fetch_image_bytes(abs_url)
        if not data or len(data) < 200:
            continue
        # Check if it's actually an image (avoid fetching large non-image)
        # Quick mime check via header would be better, but we already filtered.
        # Render
        try:
            # Check if visual_browser available for heavy images? Use ANSI path regardless.
            ansi = render_image_to_ansi(data, term_width=min(60, cw), max_height=18)
            if ansi and "PIL not installed" not in ansi:
                alt = im.get("alt", "")[:36]
                lines.append("")
                lines.append(f"  [image: {alt} — {abs_url[:48]}]")
                lines.append(ansi)
            else:
                # Fallback text line already shown elsewhere, but still note
                if "PIL not installed" in ansi:
                    lines.append(f"  [image: {im.get('alt','')} — {abs_url}] (pip install pillow to see inline)")
        except Exception:
            continue
    return lines


# ---------------------------------------------------------------------------
# Rendering — terminal ANSI via theme (or plain fallback when not a tty)
# ---------------------------------------------------------------------------

def _term_width(fallback: int = 88) -> int:
    try:
        import shutil
        return max(60, shutil.get_terminal_size(fallback=(fallback, 24)).columns)
    except Exception:
        return fallback


def render_page(session: BrowserSession, width: Optional[int] = None) -> str:
    """Render the current page as ANSI text for the terminal."""
    if session.current_parsed is None or session.current_result is None:
        return "  (no page loaded)\n"

    result = session.current_result
    parsed = session.current_parsed
    w = width or _term_width()
    # Content width leaves margins for rail/borders.
    cw = max(40, min(92, w - 6))

    try:
        from . import theme as _theme  # pylint: disable=import-outside-toplevel
        _theme.enable_windows_ansi()
        use_color = sys.stdout.isatty()
    except Exception:
        _theme = None  # type: ignore
        use_color = False

    def _c(text, color=None, bold=False):
        if not use_color or _theme is None or color is None:
            return text
        try:
            return _theme.fg(text, color, bold=bold)
        except Exception:
            return text

    def _dim(text):
        return _c(text, _theme.DIM if _theme else None)  # type: ignore

    def _wrap(text, indent="  ", w=cw):
        if not text.strip():
            return []
        return textwrap.wrap(text, width=w - len(indent),
                              break_long_words=False, break_on_hyphens=False)

    lines: List[str] = []

    # -- Chrome: top bar ----------------------------------------------------
    # Identity line — who is browsing (Fomoji session).
    try:
        from .fomoji_auth import get_identity as _get_ident  # pylint: disable=import-outside-toplevel
        ident = _get_ident()
        if ident:
            who = f"{ident.get('name','?')} ({ident.get('fomojiId','?')})"
        else:
            who = "Fomoji session"
    except Exception:
        who = "CAT"

    # URL bar
    url_display = session.current_url or "(no url)"
    if len(url_display) > cw + 12:
        url_display = url_display[:cw + 9] + "…"

    # Status badges: HTTP status + timings + link counts
    status_color = None
    status_text = str(result.status) if result.status else "—"
    if result.status and 200 <= result.status < 300:
        status_color = _theme.GREEN if _theme else None  # type: ignore
    elif result.status and 300 <= result.status < 400:
        status_color = _theme.ORANGE if _theme else None  # type: ignore
    elif result.status:
        status_color = _theme.RED if _theme else None  # type: ignore

    title_line = parsed.title or "(untitled)"
    if _theme and use_color:
        lines.append(_theme.panel([
            _c(title_line, _theme.CYAN, bold=True),  # type: ignore
            _dim(f"↗ {url_display}"),
            _dim(f"{who}  ·  HTTP {status_text}  ·  {result.elapsed_ms} ms  ·  {len(parsed.links)} links"
                 + (f"  ·  {len(parsed.images)} images" if parsed.images else "")),
        ], title="CAT Browser", color=_theme.CYAN, width=cw + 4))  # type: ignore
    else:
        lines.append("┌" + "─" * (cw + 2) + "┐")
        lines.append(f"│ {title_line[:cw].ljust(cw)} │")
        lines.append(f"│ {url_display[:cw].ljust(cw)} │")
        lines.append("└" + "─" * (cw + 2) + "┘")

    # Error banner if fetch failed
    if result.error and result.status not in (200, 304):
        err = result.error
        if _theme and use_color:
            lines.append("")
            lines.append(_theme.panel([_c(err, _theme.RED, bold=True)],  # type: ignore
                                      title="error", color=_theme.RED, width=cw + 4))  # type: ignore
        else:
            lines.append("")
            lines.append(f"  ! {err}")

    # Warnings (JS notice etc.)
    if parsed.warnings:
        for wmsg in parsed.warnings[:2]:
            lines.append(_dim(f"  ⚠ {wmsg}"))
        lines.append("")

    # Meta description
    if parsed.meta_desc:
        lines.append(_dim("  " + "─" * min(cw, 48)))
        for wl in _wrap(parsed.meta_desc, indent="  "):
            lines.append(_dim(wl))
        lines.append(_dim("  " + "─" * min(cw, 48)))

    # Body text — headings get #/## prefix, paragraphs flow, links enumerated.
    # Build a line-index -> link-indices map later; for now inline numbers.
    lines.append("")
    link_counter = 0
    # We will render body, then a numbered link list at the bottom.  Inline
    # link markers `[n]` are added as trailing references on lines that contained
    # that link's text — heuristic: if a body's line contains the exact link
    # text, append the index.  It's approximate but good enough for terminal.
    body_link_markers: Dict[int, List[int]] = {}  # line_idx -> [link_n]

    # Prepare a quick lookup: link text -> indices (may duplicate)
    link_text_to_nums: Dict[str, List[int]] = {}
    for idx, lk in enumerate(parsed.links, 1):
        key = lk.text.strip().lower()[:40]
        link_text_to_nums.setdefault(key, []).append(idx)

    rendered_body: List[str] = []
    heading_texts = {h[1] for h in parsed.headings}
    for ln in parsed.text_lines:
        if not ln.strip():
            rendered_body.append("")
            continue
        is_heading = ln.strip() in heading_texts
        # Find heading level for prefix
        prefix = ""
        if is_heading:
            for lvl, htxt in parsed.headings:
                if htxt == ln.strip():
                    if lvl == 1:
                        prefix = "# "
                    elif lvl == 2:
                        prefix = "## "
                    elif lvl == 3:
                        prefix = "### "
                    break
        # Color headings
        if is_heading and _theme and use_color:
            body_line = _c(prefix + ln.strip(), _theme.PURPLE, bold=True)  # type: ignore
            rendered_body.append("  " + body_line)
            continue
        for wl in _wrap(ln, indent="  "):
            rendered_body.append(wl)

    # Append body
    lines.extend(rendered_body)

    # Link list footer — always show when there are links, it's the main nav
    if parsed.links:
        lines.append("")
        sep = "─" * min(cw, 48)
        lines.append(_dim(f"  {sep}"))
        lines.append(_c(f"  Links ({len(parsed.links)}):", _theme.CYAN if _theme else None, bold=True))  # type: ignore
        for idx, lk in enumerate(parsed.links, 1):
            txt = lk.text.strip() or "(no text)"
            if len(txt) > 48:
                txt = txt[:47] + "…"
            href = lk.href
            # Shorten href for display
            if len(href) > 56:
                href = href[:53] + "…"
            # Color: internal vs external vs anchor
            if use_color and _theme:
                num = _c(f"[{idx:>2}]", _theme.CYAN, bold=True)  # type: ignore
                txt_c = _c(txt, _theme.TEXT)  # type: ignore
                href_c = _dim(href)
                lines.append(f"  {num} {txt_c}  {href_c}")
            else:
                lines.append(f"  [{idx:>2}] {txt}  —  {href}")
        lines.append(_dim(f"  {sep}"))
        lines.append(_dim(f'  Type a number (e.g. 3) or "open 3" to follow a link.  "links" to re-show this list.'))

    # Images — try inline ANSI rendering (any format via PIL), fallback to list
    inline_img_lines = _render_images_inline(session, cw, use_color) if use_color else []
    if inline_img_lines:
        lines.extend(inline_img_lines)
    # Images summary (collapsed — don't flood)
    if parsed.images:
        lines.append("")
        lines.append(_dim(f"  Images ({len(parsed.images)}): (type `img <num>` to view full-size)"))
        for idx, im in enumerate(parsed.images[:10], 1):
            alt = im.get("alt", "")[:48]
            src = im.get("src", "")[:42]
            lines.append(_dim(f"    [{idx}] • {alt or '(no alt)'}  —  {src}"))
        if len(parsed.images) > 10:
            lines.append(_dim(f"    … +{len(parsed.images) - 10} more (save page to inspect)"))

    # Find hits highlight (if active)
    if session.last_find_hits:
        lines.append("")
        lines.append(_c(f"  / find: {len(session.last_find_hits)} match(es) on lines {', '.join(str(i+1) for i in session.last_find_hits[:10])}",
                        _theme.ORANGE if _theme else None))  # type: ignore

    # Bottom chrome: status + hints + identity
    lines.append("")
    nav = []
    nav.append("back" if session.can_back() else _dim("back"))
    nav.append("forward" if session.can_forward() else _dim("forward"))
    nav.append("reload")
    nav.append("home")
    nav_line = "  " + "  ·  ".join(str(x) for x in nav)
    lines.append(nav_line)
    lines.append(_dim('  Type "open <url>", "search <query>", number, or "help".  "q" to quit.'))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Browser REPL — the main terminal UI loop
# ---------------------------------------------------------------------------

_HELP_TEXT = """
CAT Browser — terminal software browser (no external Chrome needed)
────────────────────────────────────
  Navigation
    open <url> | go <url> | <url>     open a URL
    <number> | open <number>          follow link #number
    back | b                          go back
    forward | f | fwd                 go forward
    reload | r | refresh              reload current page
    home | h                          CAT Browser home
    history | hist                    show navigation history
    search <query> | s <query>        web search (DuckDuckGo by default)
    search google <query> | g <query> Google search
    search ddg <query>                DuckDuckGo search
    find <text> | /<text>             find text on current page

  Visual / Images / 3D
    visual | v                        render page visually via Chromium (screenshots → ANSI)
                                      — needed for WebGL / 3D / canvas-heavy sites
    img <num>                         render image #num inline (png/jpg/webp/gif/svg/avif)
    images                            re-show image list
    screenshot | shot                 save Chromium screenshot to ~/Downloads

  Page
    links | l                         re-show numbered link list
    source | src                      show raw HTML source
    text | view                       re-render current page (text mode)
    save [path] | download [path]     save current page to file
    copy <num>                        copy link #num URL to clipboard (if available)

  Bookmarks
    bookmark | bm                     bookmark current page
    bookmarks | bms                   list bookmarks
    open bookmark <num> | bm open <n> open bookmark #num
    bookmark rm <num> | bm rm <num>   remove bookmark #num

  Session
    info | status                     show status (url, title, auth, stats)
    help | ?                          this help
    quit | q | exit | bye             leave browser (returns to CAT)

  Tips
    • Paste a full URL and press Enter — it opens immediately.
    • Type a phrase without a scheme (e.g. "cats on mars") to search.
    • The browser respects your Fomoji identity — no login = no fetch.
""".strip()


def _print_help():
    try:
        from . import theme as _theme  # pylint: disable=import-outside-toplevel
        _theme.enable_windows_ansi()
        print(_theme.panel(_HELP_TEXT.split("\n"), title="browser help", color=_theme.CYAN, width=78))
    except Exception:
        print(_HELP_TEXT)
    print()


def _print_status(session: BrowserSession):
    try:
        from . import theme as _theme
        _theme.enable_windows_ansi()
        ident = None
        try:
            from .fomoji_auth import get_identity  # pylint: disable=import-outside-toplevel
            ident = get_identity()
        except Exception:
            pass
        who = f"{ident['name']} ({ident['fomojiId']})" if ident else "no identity"
        lines = [
            _theme.text("CAT Browser — status", bold=True),
            f"  URL:   {_theme.cyan(session.current_url or '(none)')}",
            f"  Title: {session.current_parsed.title if session.current_parsed else '(none)'}",
            f"  Auth:  {_theme.green(who, bold=True) if ident else _theme.red(who, bold=True)}",
            f"  History: {len(session.history)} page(s), index {session.history_index + 1}",
            f"  Bookmarks: {len(session.bookmarks)}",
            f"  Links: {len(session.current_parsed.links) if session.current_parsed else 0}",
            f"  Engine: terminal (no JS)  ·  Fetcher: {'requests' if _HAS_REQUESTS else 'urllib'}",
        ]
        print(_theme.panel(lines, title="status", color=_theme.PURPLE, width=76))
    except Exception:
        print(f"  URL: {session.current_url}")
        print(f"  History: {len(session.history)} @ {session.history_index}")


def launch_browser(start_url: Optional[str] = None, require_auth: bool = True) -> int:
    """
    Main terminal browser loop.  Returns exit code for `cat browse` (0 = ok).

    This is the ONLY browser entrypoint for `cat browse` and for `/browser`
    inside the CAT REPL (which calls this while the Textual UI is suspended).

    The loop is intentionally a simple blocking input() loop — it mirrors
    CAT's own fallback CLI so it works identically whether the primary
    Textual UI is running or not.

    `require_auth=False` is used for the Fomoji verification flow itself
    (so the user can open the Fomoji login/approve page even before CAT is
    authenticated — otherwise we'd block the very page that grants auth).
    """
    # -- Gate (again, belt-and-suspenders — cli.main already gates, but a
    # direct `from cat_browser import launch_browser` should also fail closed).
    # For the Fomoji verification flow we intentionally skip the gate when
    # the start URL is a localhost Fomoji URL.
    _is_fomoji_verification = False
    if start_url:
        try:
            from .fomoji_auth import get_fomoji_url as _get_url
            fomoji_host = urllib.parse.urlparse(_get_url()).hostname or ""
            parsed = urllib.parse.urlparse(start_url)
            if parsed.hostname and fomoji_host and parsed.hostname.lower() == fomoji_host.lower():
                _is_fomoji_verification = True
            if parsed.hostname in ("localhost", "127.0.0.1", "::1"):
                _is_fomoji_verification = True
        except Exception:
            pass
    if require_auth and not _is_fomoji_verification:
        try:
            from .fomoji_auth import enforce_or_exit  # pylint: disable=import-outside-toplevel
            enforce_or_exit(interactive=True, auto_prompt=True)
        except SystemExit as e:
            return int(e.code) if e.code is not None else 1
        except Exception as e:
            print(f"CAT Browser: auth gate error ({e}) — refusing to launch.", file=sys.stderr)
            return 1

    try:
        from . import theme as _theme
        _theme.enable_windows_ansi()
        _theme.clear_screen()
        # Identity banner
        try:
            from .fomoji_auth import get_identity as _get_ident
            ident = _get_ident()
            who = f"{ident['name']} ({ident['fomojiId']})" if ident else "unknown"
        except Exception:
            who = "CAT"
            ident = None
        print()
        print(_theme.panel([
            _theme.text("CAT Browser", bold=True) + _theme.dim("  —  full terminal web browser"),
            _theme.dim(f"Signed in as {who}  ·  Fomoji-protected"),
            "",
            _theme.dim("Type a URL or search query and press Enter.  Type `help` for commands."),
        ], title="browser", color=_theme.CYAN, width=78))
        print()
    except Exception:
        print("\n  CAT Browser — terminal web browser\n")

    session = BrowserSession()

    # Initial navigation: explicit URL > last history entry > home
    first = (start_url or "").strip()
    if first:
        # Allow bare search query as first arg via `cat browse cats on mars`
        # — normalize_url will turn it into https://cats... which is wrong,
        # so treat multi-word first args as search?  But launch_browser only
        # gets one url arg, so we handle it faithfully: single-token with dot
        # or scheme => navigate, else search.
        try:
            # If it parses as a URL, navigate; otherwise search.
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", first) or first.lower().startswith("about:"):
                session.navigate(normalize_url(first))
            elif _is_search_query(first) and " " in first:
                session.search(first)
            else:
                session.navigate(normalize_url(first))
        except ValueError:
            # Fallback to search for ambiguous input
            try:
                session.search(first)
            except Exception:
                session.navigate(_ABOUT_HOME_URL)
        except Exception as e:
            print(f"  Could not open {first}: {e}")
            session.navigate(_ABOUT_HOME_URL)
    else:
        session.navigate(_ABOUT_HOME_URL)

    # First render
    print(render_page(session))
    print()

    while True:
        # Address prompt — show truncated URL + history position
        url_hint = session.current_url or "about:home"
        if len(url_hint) > 42:
            url_hint = "…" + url_hint[-41:]
        hist_hint = f"[{session.history_index + 1}/{len(session.history)}]" if session.history else ""
        try:
            raw = input(f"  \x1b[2m{url_hint} {hist_hint}\x1b[0m  \x1b[1m▶\x1b[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Leaving CAT Browser.\n")
            break

        if not raw:
            continue

        low = raw.lower().strip()
        first_tok = low.split()[0] if low else ""

        # -- Quit ----------------------------------------------------------
        if low in ("q", "quit", "exit", "bye", ":q", ":quit"):
            print("\n  Leaving CAT Browser.\n")
            break

        # -- Help ----------------------------------------------------------
        if low in ("help", "?", "h help", "--help"):
            _print_help()
            continue

        # -- Status / info -------------------------------------------------
        if low in ("info", "status", ":info"):
            _print_status(session)
            print()
            continue

        # -- View / re-render ----------------------------------------------
        if low in ("view", "text", "render", "show"):
            print(render_page(session))
            print()
            continue

        # -- Source ---------------------------------------------------------
        if low in ("source", "src", "html", "view source", "view-source"):
            if not session.current_result or not session.current_result.text:
                print("  (no source — page had no body)\n")
            else:
                src = session.current_result.text
                # Paginate: 40 lines at a time
                lines = src.splitlines()
                for i in range(0, len(lines), 40):
                    chunk = "\n".join(lines[i:i + 40])
                    print(chunk)
                    if i + 40 < len(lines):
                        try:
                            more = input("  -- more -- (Enter to continue, q to stop) ").strip().lower()
                            if more in ("q", "quit"):
                                break
                        except (EOFError, KeyboardInterrupt):
                            break
                print()
            continue

        # -- Links ----------------------------------------------------------
        if low in ("links", "l", "list links", "show links"):
            if not session.current_parsed or not session.current_parsed.links:
                print("  (no links on this page)\n")
            else:
                # Re-print link section only (avoid re-rendering whole page)
                session.last_find_hits = []
                print(render_page(session))
                print()
            continue

        # -- History --------------------------------------------------------
        if low in ("history", "hist", "h"):
            if not session.history:
                print("  (no history)\n")
            else:
                try:
                    from . import theme as _theme
                    _theme.enable_windows_ansi()
                    lines = [_theme.text("Navigation history", bold=True), ""]
                    for idx, h in enumerate(session.history):
                        marker = "▶" if idx == session.history_index else " "
                        title = h.title or h.url
                        if len(title) > 52:
                            title = title[:51] + "…"
                        url_s = h.url
                        if len(url_s) > 56:
                            url_s = url_s[:55] + "…"
                        lines.append(f"{marker} {idx + 1:>2}. {_theme.cyan(title)}  {_theme.dim(url_s)}")
                    print(_theme.panel(lines, title="history", color=_theme.PURPLE, width=78))
                    print(_theme.dim('  Type "open <num>" with the history number, or "back"/"forward".'))
                    print()
                except Exception:
                    for idx, h in enumerate(session.history):
                        print(f"  {idx + 1:>2}. {h.title}  —  {h.url}")
                    print()
            continue

        # Numeric history access: `open 12` when history exists — disambiguate
        # from link numbers by requiring >=2 digits? No — better to handle via
        # explicit `history open <n>` or keep `open <num>` meaning link first.
        # We keep link semantics for plain numbers.

        # -- Visual / Images / Screenshot / 3D -------------------------------
        if low in ("visual", "v", "chromium", "render", "3d"):
            # Visual mode uses real Chromium to render JS/WebGL, then shows screenshot as ANSI
            vb = get_visual_browser()
            if not vb.available():
                print("  Visual mode needs Chromium: pip install playwright && playwright install chromium\n")
                print("  Falling back to text mode — try `img <n>` for individual images.\n")
                continue
            print(f"  ◉ Rendering {session.current_url} visually (Chromium + WebGL)...\n")
            ansi = vb.screenshot_ansi(session.current_url, term_width=_term_width() - 2)
            if ansi:
                print(ansi)
                print()
                # Also show text overlay below for navigation (links still work)
                print(render_page(session))
                print()
                print("  Visual render above — links still work by number, `text` to return to text-only.\n")
            else:
                print("  Visual render failed (Chromium error or timeout). Text mode still available.\n")
                print(render_page(session))
                print()
            continue
        if first_tok in ("img", "image", "images", "showimg"):
            # `images` alone -> list, `img 3` -> render image #3 inline
            if low in ("images", "showimg"):
                if not session.current_parsed or not session.current_parsed.images:
                    print("  (no images on this page)\n")
                else:
                    for idx, im in enumerate(session.current_parsed.images, 1):
                        print(f"  [{idx}] {im.get('alt','')[:48]} — {im.get('src','')[:64]}")
                    print('  Use `img <num>` to render that image inline.\n')
                continue
            arg = raw.split(None, 1)[1].strip() if " " in raw else ""
            if not arg.isdigit():
                print("  Usage: img <num>  (e.g. img 2) — or `images` to list all\n")
                continue
            idx = int(arg) - 1
            if not session.current_parsed or not (0 <= idx < len(session.current_parsed.images)):
                print("  No such image.\n")
                continue
            src = session.current_parsed.images[idx].get("src", "")
            try:
                abs_url = urllib.parse.urljoin(session.current_url, src)
            except Exception:
                abs_url = src
            print(f"  Fetching image {idx+1}: {abs_url[:80]} ...\n")
            data = _fetch_image_bytes(abs_url)
            if not data:
                print("  Could not fetch image.\n")
                continue
            ansi = render_image_to_ansi(data, term_width=_term_width() - 4, max_height=28)
            print(ansi)
            print(f"\n  Image {idx+1}: {session.current_parsed.images[idx].get('alt','')}\n")
            continue
        if low in ("screenshot", "shot", "capture"):
            vb = get_visual_browser()
            if not vb.available():
                print("  Screenshot needs Chromium: pip install playwright && playwright install chromium\n")
                continue
            print(f"  Capturing {session.current_url} ...\n")
            ansi = vb.screenshot_ansi(session.current_url, term_width=_term_width() - 2)
            if ansi:
                print(ansi)
                # Also save to file
                try:
                    import tempfile
                    import datetime
                    out = Path.home() / "Downloads" / f"cat_screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    # Also save raw PNG via engine screenshot
                    vb.ensure()
                    if vb._engine:
                        ok = vb._engine.screenshot(str(out))  # type: ignore
                        if ok:
                            print(f"\n  Saved PNG to {out}\n")
                except Exception:
                    pass
            else:
                print("  Screenshot failed.\n")
            continue

        # -- Back / forward / reload / home --------------------------------
        if low in ("back", "b", "<", "prev", "previous"):
            res = session.back()
            if res is None:
                print("  (already at oldest page)\n")
            else:
                print(render_page(session))
                print()
            continue
        if low in ("forward", "fwd", "f", ">", "next"):
            res = session.forward()
            if res is None:
                print("  (already at newest page)\n")
            else:
                print(render_page(session))
                print()
            continue
        if low in ("reload", "r", "refresh", "again"):
            print("  ⟳ Reloading...\n")
            session.reload()
            print(render_page(session))
            print()
            continue
        if low in ("home", "about:home"):
            session.navigate(_ABOUT_HOME_URL)
            print(render_page(session))
            print()
            continue

        # -- Find on page ---------------------------------------------------
        if first_tok in ("find", "search-on-page") or low.startswith("/"):
            if low.startswith("/"):
                query = raw[1:].strip()
            else:
                query = raw.split(None, 1)[1].strip() if " " in raw else ""
            if not query:
                print("  Usage: find <text>  or  /<text>\n")
                continue
            hits = session.find_on_page(query)
            if not hits:
                print(f"  No matches for {query!r} on this page.\n")
            else:
                print(f"  Found {len(hits)} match(es) for {query!r}:")
                for ln_idx in hits[:12]:
                    line = session.current_parsed.text_lines[ln_idx] if session.current_parsed else ""
                    # Highlight query
                    try:
                        from . import theme as _theme
                        hi = _theme.fg(query, _theme.ORANGE, bold=True)
                        shown = re.sub(re.escape(query), hi, line, flags=re.I)
                        print(f"    line {ln_idx + 1:>3}: {shown}")
                    except Exception:
                        print(f"    line {ln_idx + 1:>3}: {line}")
                print()
                # Keep marks for next render
            continue

        # -- Search (web) ---------------------------------------------------
        if first_tok in ("search", "s", "query", "google", "ddg", "g"):
            # Support `search google cats` / `g cats` / `search cats`
            rest = raw.split(None, 1)[1].strip() if " " in raw else ""
            if not rest:
                print("  Usage: search <query>  ·  search google <query>  ·  g <query>\n")
                continue
            # Detect engine prefix inside rest (e.g. `google cats`)
            eng, q = _detect_search_engine(rest)
            # If user typed `g cats` where g was the first_tok, rest is already `cats`
            # but _detect would default to ddg; we need to propagate engine from first_tok
            if first_tok == "g" and eng == _DEFAULT_SEARCH_ENGINE:
                eng = "google"
            if first_tok == "google" and eng == _DEFAULT_SEARCH_ENGINE:
                eng = "google"
            if not q:
                q = rest
            print(f"  Searching {eng} for {q!r}...\n")
            try:
                session.search(q, engine=eng)
                print(render_page(session))
            except Exception as e:
                print(f"  Search failed: {e}\n")
            print()
            continue

        # -- Bookmarks ------------------------------------------------------
        if first_tok in ("bookmark", "bm", "bookmarks", "bms"):
            parts = low.split()
            # `bookmarks` / `bms` alone -> list
            if first_tok in ("bookmarks", "bms") and len(parts) == 1:
                if not session.bookmarks:
                    print("  (no bookmarks yet — `bookmark` to save current page)\n")
                else:
                    try:
                        from . import theme as _theme
                        _theme.enable_windows_ansi()
                        lines = [_theme.text("Bookmarks", bold=True), ""]
                        for idx, bm in enumerate(session.bookmarks, 1):
                            title = bm.title[:48] + ("…" if len(bm.title) > 48 else "")
                            lines.append(f"  {idx:>2}. {_theme.cyan(title)}  {_theme.dim(bm.url)}")
                        print(_theme.panel(lines, title="bookmarks", color=_theme.PURPLE, width=78))
                        print(_theme.dim('  open bookmark <num>  ·  bookmark rm <num>'))
                        print()
                    except Exception:
                        for idx, bm in enumerate(session.bookmarks, 1):
                            print(f"  {idx:>2}. {bm.title}  —  {bm.url}")
                        print()
                continue
            # `bookmark` alone -> add
            if low in ("bookmark", "bm"):
                try:
                    bm = session.add_bookmark()
                    print(f"  ★ Bookmarked: {bm.title}  —  {bm.url}\n")
                except Exception as e:
                    print(f"  Could not bookmark: {e}\n")
                continue
            # `bookmark rm <n>` / `bm rm <n>` -> remove
            if len(parts) >= 2 and parts[1] in ("rm", "remove", "del", "delete"):
                if len(parts) < 3 or not parts[2].isdigit():
                    print("  Usage: bookmark rm <num>\n")
                    continue
                idx = int(parts[2]) - 1
                bm = session.remove_bookmark(idx)
                if bm:
                    print(f"  Removed bookmark: {bm.title}\n")
                else:
                    print("  No such bookmark.\n")
                continue
            # `open bookmark <n>` alternate form handled below; fall through
            if low in ("bookmarks", "bms"):
                continue
            print('  Usage: bookmark | bookmarks | bookmark rm <num> | open bookmark <num>\n')
            continue

        if low.startswith("open bookmark") or low.startswith("bm open") or low.startswith("open bm"):
            # Extract number after "bookmark"
            m = re.search(r"bookmark\s+(\d+)", low)
            if not m:
                print('  Usage: open bookmark <num>\n')
                continue
            idx = int(m.group(1)) - 1
            if not (0 <= idx < len(session.bookmarks)):
                print("  No such bookmark.\n")
                continue
            url = session.bookmarks[idx].url
            print(f"  Opening bookmark {idx + 1}: {url}\n")
            try:
                session.navigate(url)
                print(render_page(session))
            except Exception as e:
                print(f"  Failed to open bookmark: {e}\n")
            print()
            continue

        # -- Open bookmark short: `bm 3` -> bookmark #3
        if first_tok == "bm" and len(raw.split()) == 2 and raw.split()[1].isdigit():
            idx = int(raw.split()[1]) - 1
            if 0 <= idx < len(session.bookmarks):
                url = session.bookmarks[idx].url
                session.navigate(url)
                print(render_page(session))
                print()
                continue
            print("  No such bookmark.\n")
            continue

        # -- Save / download -----------------------------------------------
        if first_tok in ("save", "download", "write"):
            dest = raw.split(None, 1)[1].strip().strip('"').strip("'") if " " in raw else ""
            if not dest:
                dest = str(_DOWNLOAD_DIR)
                print(f"  Saving to {dest}/ ...")
            try:
                saved = session.save_current(dest)
                print(f"  ✓ Saved to {saved}\n")
            except Exception as e:
                print(f"  Save failed: {e}\n")
            continue

        # -- Copy link -------------------------------------------------------
        if first_tok in ("copy", "cp"):
            arg = raw.split(None, 1)[1].strip() if " " in raw else ""
            if not arg.isdigit():
                print("  Usage: copy <link-number>\n")
                continue
            idx = int(arg) - 1
            if not session.current_parsed or not (0 <= idx < len(session.current_parsed.links)):
                print("  No such link.\n")
                continue
            url = session.current_parsed.links[idx].href
            # Try clipboard, then fallback to printing
            copied = False
            try:
                import pyperclip  # type: ignore
                pyperclip.copy(url)
                copied = True
            except Exception:
                pass
            if not copied:
                # Try native OS clipboards before giving up
                try:
                    import subprocess
                    if sys.platform == "win32":
                        subprocess.run("clip", input=url.encode("utf-8"), check=False)
                        copied = True
                    elif sys.platform == "darwin":
                        subprocess.run(["pbcopy"], input=url.encode("utf-8"), check=False)
                        copied = True
                except Exception:
                    pass
            if copied:
                print(f"  ✓ Copied to clipboard: {url}\n")
            else:
                print(f"  Link URL (copy manually): {url}\n")
            continue

        # -- Open / navigate -------------------------------------------------
        # Forms:
        #   open <url|num>   / go <url|num>  / o <url>
        #   bare <url>       (input itself is a URL)
        #   bare number      (follow link)
        if first_tok in ("open", "go", "o", "visit", "navigate"):
            target = raw.split(None, 1)[1].strip() if " " in raw else ""
            if not target:
                print("  Usage: open <url>  or  open <number>\n")
                continue
            # `open <number>` -> follow link
            if target.isdigit():
                idx = int(target) - 1
                if not session.current_parsed or not (0 <= idx < len(session.current_parsed.links)):
                    print(f"  No link #{target} on this page.\n")
                    continue
                href = session.current_parsed.links[idx].absolute or session.current_parsed.links[idx].href
                print(f"  → Following [{target}] {session.current_parsed.links[idx].text[:48]} ...\n")
                try:
                    session.navigate(href)
                    print(render_page(session))
                except Exception as e:
                    print(f"  Navigation failed: {e}\n")
                print()
                continue
            # `open bookmark <n>` already handled above; check again quickly
            if target.lower().startswith("bookmark"):
                m = re.search(r"(\d+)", target)
                if m:
                    idx = int(m.group(1)) - 1
                    if 0 <= idx < len(session.bookmarks):
                        session.navigate(session.bookmarks[idx].url)
                        print(render_page(session))
                        print()
                        continue
            # Otherwise treat as URL or search query
            # If it looks like a search phrase (spaces + no scheme/dot-TLD), search
            if " " in target and _is_search_query(target):
                print(f"  Searching for {target!r}...\n")
                try:
                    session.search(target)
                    print(render_page(session))
                except Exception as e:
                    print(f"  Search failed: {e}\n")
                print()
                continue
            try:
                url = normalize_url(target, base=session.current_url)
                session.navigate(url)
                print(render_page(session))
            except ValueError as e:
                print(f"  Could not parse URL: {e}\n")
            except Exception as e:
                print(f"  Navigation failed: {e}\n")
            print()
            continue

        # Bare number -> follow link
        if raw.strip().isdigit():
            idx = int(raw.strip()) - 1
            if not session.current_parsed or not (0 <= idx < len(session.current_parsed.links)):
                print(f"  No link #{raw.strip()} on this page. Type `links` to see links.\n")
                continue
            href = session.current_parsed.links[idx].absolute or session.current_parsed.links[idx].href
            print(f"  → Following [{raw.strip()}] {session.current_parsed.links[idx].text[:48]} ...\n")
            try:
                session.navigate(href)
                print(render_page(session))
            except Exception as e:
                print(f"  Navigation failed: {e}\n")
            print()
            continue

        # Bare input that looks like a URL -> navigate directly
        # (convenience so you can paste https://example.com and hit Enter)
        bare = raw.strip()
        looks_like_url = (
            re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", bare) or
            bare.lower().startswith("about:") or
            ("." in bare.split("/")[0].split(" ")[0] and " " not in bare and "/" in bare) or
            re.match(r"^(localhost(:\d+)?)(/|$)", bare, re.I)
        )
        if looks_like_url:
            try:
                url = normalize_url(bare, base=session.current_url)
                session.navigate(url)
                print(render_page(session))
                print()
                continue
            except Exception as e:
                print(f"  Could not open {bare!r}: {e}\n")
                continue

        # Bare search-ish phrase (contains space, not a URL) -> web search
        if " " in bare and _is_search_query(bare):
            print(f"  Searching for {bare!r}...\n")
            try:
                session.search(bare)
                print(render_page(session))
            except Exception as e:
                print(f"  Search failed: {e}\n")
            print()
            continue

        # Single-token without scheme: try URL, fallback to search
        if " " not in bare and "." in bare:
            # Looks host-like, try as https URL
            try:
                url = normalize_url(bare)
                session.navigate(url)
                print(render_page(session))
                print()
                continue
            except Exception:
                pass

        # Unknown command — treat as search from anywhere (forgiving), otherwise help
        if len(bare.split()) >= 1:
            # One-word unknown: show help rather than blind search to avoid
            # surprise navigation on a typo like "helo".
            if " " not in bare and len(bare) < 20 and bare.isalpha():
                print(f"  Unknown command: {bare!r} — type `help` for commands, or `search {bare}` to search.\n")
                continue
            # Multi-word unknown outside known commands -> search fallback
            if " " in bare:
                print(f"  Searching for {bare!r} (type `help` to see commands)...\n")
                try:
                    session.search(bare)
                    print(render_page(session))
                except Exception as e:
                    print(f"  Search failed: {e}\n")
                print()
                continue

        print(f"  Unknown command: {bare!r} — type `help`.\n")

    return 0


# ---------------------------------------------------------------------------
# Entry for `python -m calc_terminal.cat_browser` — DEPRECATED CLI
# Normal browser is graphical (browser_shell.py). This CLI is now
# Developer Tools only (hidden). Use `cat browse` for the graphical browser.
# To force the old text CLI, set CAT_BROWSER_DEBUG=1.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if os.environ.get("CAT_BROWSER_DEBUG", "").lower() not in ("1","true","yes"):
        # Normal users should never see numbered Links. Redirect to graphical.
        try:
            from .host.launcher import launch_cat_host, can_launch_host
            if can_launch_host():
                url_arg = sys.argv[1] if len(sys.argv) > 1 else "about:home"
                raise SystemExit(launch_cat_host(start_browser_url=url_arg, start_mode="browser", block=True))
        except SystemExit:
            raise
        except Exception:
            pass
        # Fallback message when Textual missing
        print("CAT Browser — graphical mode is the normal browser.")
        print("The text/CLI browser (Links, numbered navigation) is Developer Tools only.")
        print("Run: cat browse https://example.com")
        print("Or set CAT_BROWSER_DEBUG=1 to force the old CLI (not recommended).")
        raise SystemExit(1)
    url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    raise SystemExit(launch_browser(start_url=url_arg))
