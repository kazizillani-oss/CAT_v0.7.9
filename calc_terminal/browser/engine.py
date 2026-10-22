"""CAT browser/ — the REAL browser engine: Chromium via Playwright.

A dedicated worker thread owns the Playwright sync API (its only
supported mode outside asyncio). Every public call marshals a job onto
that thread and waits for the result, so callers (UI workers) never
touch Playwright from the wrong thread and never block the UI.

What runs is genuine Chromium: HTML, CSS, JavaScript, animations,
responsive layout, images, SVG, fonts, fetch, WebSockets — everything
the real engine supports. The terminal pane renders a structured
snapshot of the LIVE DOM (see dom_outline) plus console/errors, which
keeps CAT terminal-first while the actual rendering work happens in
Chromium. The architecture keeps a screenshot hook so a graphical
embedded surface can be added later without touching callers.

If playwright/chromium isn't installed, start() raises
BrowserUnavailableError with the exact fix; nothing else in CAT breaks.
"""

from __future__ import annotations

import threading
import time
import queue as _queue
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .state import PreviewSnapshot

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    PLAYWRIGHT_AVAILABLE = True
except Exception:
    PLAYWRIGHT_AVAILABLE = False


class BrowserUnavailableError(RuntimeError):
    pass


_OUTLINE_JS = """
() => {
  const out = [];
  const push = (tag, cls, text, extra) => {
    text = (text || '').replace(/\\s+/g, ' ').trim();
    if (!text && !extra) return;
    out.push({t: tag, c: cls || '', x: text.slice(0, 160), e: extra || ''});
  };
  document.querySelectorAll(
    'h1,h2,h3,h4,p,li,a,button,input,textarea,select,img,section,nav,footer,header'
  ).forEach(el => {
    if (el.offsetParent === null && el.tagName !== 'INPUT') {
      // skip hidden nodes but keep form fields (they have no offsetParent)
      const st = getComputedStyle(el);
      if (st.display === 'none' || st.visibility === 'hidden') return;
    }
    const tag = el.tagName.toLowerCase();
    if (tag === 'img') {
      const ok = el.complete && el.naturalWidth > 0;
      push('img', '', el.alt || el.src.split('/').pop(), ok ? '' : 'BROKEN');
      return;
    }
    if (tag === 'input' || tag === 'textarea' || tag === 'select') {
      push(tag, el.type || '', el.placeholder ||
           el.getAttribute('aria-label') || tag.toUpperCase(), '');
      return;
    }
    let text = '';
    if (tag === 'a' || tag === 'button') text = el.textContent;
    else if (tag === 'li') text = el.textContent;
    else text = el.textContent;
    push(tag, el.className && String(el.className).slice(0, 40),
         text,
         tag === 'a' ? (el.getAttribute('href') || '').slice(0, 80) : '');
  });
  return out.slice(0, 400);
}
"""

_COUNTS_JS = """
() => ({
  elements: document.querySelectorAll('*').length,
  imagesLoaded: Array.from(document.images)
      .filter(i => i.complete && i.naturalWidth > 0).length,
  imagesBroken: Array.from(document.images)
      .filter(i => i.complete && i.naturalWidth === 0).length,
})
"""


@dataclass
class _Job:
    fn: Callable
    result: list = field(default_factory=list)
    done: threading.Event = field(default_factory=threading.Event)


class BrowserEngine:
    """Chromium worker. All calls are synchronous from the caller's
    perspective and executed on the engine's own thread."""

    def __init__(self, headless: bool = True):
        self._headless = headless
        self._queue: "_queue.Queue[Optional[_Job]]" = _queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._stop = False
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self.console: List[str] = []
        self.js_errors: List[str] = []
        self.last_status: Optional[int] = None
        self._nav_error: Optional[str] = None
        self.viewport = {"width": 1024, "height": 700}

    # ------------------------------------------------------------ jobs --
    def _submit(self, fn, timeout=30.0):
        if self._thread is None or not self._thread.is_alive():
            raise RuntimeError("engine not started")
        job = _Job(fn=fn)
        self._queue.put(job)
        if not job.done.wait(timeout):
            raise TimeoutError("browser engine did not respond")
        if job.result and isinstance(job.result[0], Exception):
            raise job.result[0]
        return job.result[0] if job.result else None

    def _loop(self):
        try:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=self._headless)
            self._context = self._browser.new_context(viewport=self.viewport)
            self._page = self._context.new_page()
            page = self._page

            def _on_console(msg):
                kind = msg.type
                if kind in ("error", "warning"):
                    line = f"[{kind}] {msg.text}"
                    self.console.append(line)
                    del self.console[:-100:]
                elif kind == "log" and len(self.console) < 200:
                    self.console.append(f"[log] {msg.text}")

            def _on_pageerror(err):
                line = f"ReferenceError-class: {err}" \
                    if "ReferenceError" in str(err) else str(err)
                self.js_errors.append(str(err))
                del self.js_errors[:-50:]
                self.console.append(f"[pageerror] {line}")
                del self.console[:-100:]

            def _on_response(resp):
                try:
                    if resp.url == page.url:
                        self.last_status = resp.status
                except Exception:
                    pass

            page.on("console", _on_console)
            page.on("pageerror", _on_pageerror)
            page.on("response", _on_response)
        except BrowserUnavailableError:
            raise
        except Exception as e:
            self._launch_error = e
        finally:
            self._ready.set()
        while not self._stop:
            try:
                job = self._queue.get(timeout=0.25)
            except _queue.Empty:
                continue
            if job is None:
                break
            try:
                res = job.fn()
                job.result.append(res)
            except Exception as e:
                job.result.append(e)
            finally:
                job.done.set()

    # ----------------------------------------------------------- start --
    def start(self, timeout=45.0):
        """Launch Chromium on the engine thread. Raises
        BrowserUnavailableError when the stack isn't installed."""
        if self._thread is not None and self._thread.is_alive():
            return True
        if not PLAYWRIGHT_AVAILABLE:
            raise BrowserUnavailableError(
                "Playwright is not installed. Run:\n"
                "  pip install playwright\n"
                "  playwright install chromium")
        self._launch_error = None
        self._thread = threading.Thread(
            target=self._loop, name="cat-browser-engine", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout):
            raise TimeoutError("Chromium did not launch in time")
        if not PLAYWRIGHT_AVAILABLE or self._browser is None:
            err = getattr(self, "_launch_error", None)
            raise BrowserUnavailableError(
                f"Chromium failed to launch: {err}. "
                "Try: playwright install chromium")
        return True

    # -------------------------------------------------------- internals --
    def _navigate(self, url):
        page = self._page
        del self.console[:]
        del self.js_errors[:]
        self._nav_error = None
        self.last_status = None
        try:
            resp = page.goto(url, wait_until="load", timeout=25000)
            if resp is not None:
                self.last_status = resp.status
        except Exception as e:
            self._nav_error = str(e).split("\n")[0][:200]
        try:
            page.wait_for_timeout(120)   # let late JS paint settle briefly
        except Exception:
            pass
        return self._snapshot_locked(url)

    def _snapshot_locked(self, url: str) -> PreviewSnapshot:
        page = self._page
        snap = PreviewSnapshot(url=url)
        snap.console_tail = tuple(self.console[-8:])
        snap.js_errors = tuple(self.js_errors[-5:])
        if self._nav_error:
            snap.ok = False
            snap.error = self._nav_error
            return snap
        try:
            snap.title = page.title() or ""
        except Exception:
            pass
        snap.status_code = self.last_status
        if self.last_status and self.last_status >= 400:
            snap.ok = False
            snap.error = f"HTTP {self.last_status} while loading {url}"
            return snap
        try:
            counts = page.evaluate(_COUNTS_JS) or {}
            snap.elements = int(counts.get("elements", 0))
            snap.images_loaded = int(counts.get("imagesLoaded", 0))
            snap.images_broken = int(counts.get("imagesBroken", 0))
            raw = page.evaluate(_OUTLINE_JS) or []
            lines = []
            for item in raw[:160]:
                t, x = item.get("t", ""), item.get("x", "")
                e = item.get("e", "")
                prefix = {
                    "h1": "# ", "h2": "## ", "h3": "### ",
                    "a": "  ↗ ", "button": "  [ ] ",
                    "li": "  • ", "input": "  ⌨ ", "textarea": "  ⌨ ",
                    "select": "  ⌨ ", "img": "  🖼 ", "p": "  ",
                    "nav": "§ nav", "header": "§ header",
                    "footer": "§ footer", "section": "§ section",
                }.get(t, "  ")
                line = f"{prefix}{x}".rstrip()
                if t == "img":
                    line += "" if e != "BROKEN" else " ✗"
                if line.strip():
                    lines.append(line)
            snap.outline_lines = tuple(lines)
        except Exception as e:
            snap.error = f"snapshot failed: {e}"
        return snap

    # ----------------------------------------------------------- public --
    @property
    def available(self) -> bool:
        return self._thread is not None and self._thread.is_alive() \
            and self._page is not None

    def navigate(self, url: str, timeout=35.0) -> PreviewSnapshot:
        return self._submit(lambda: self._navigate(url), timeout)

    def reload(self, timeout=35.0) -> PreviewSnapshot:
        def do_reload():
            url = self._page.url
            try:
                self._page.reload(wait_until="load", timeout=25000)
            except Exception:
                pass
            return self._snapshot_locked(url)
        return self._submit(do_reload, timeout)

    def back(self, timeout=20.0) -> Optional[PreviewSnapshot]:
        def go_back():
            page = self._page
            try:
                page.go_back(wait_until="load", timeout=15000)
            except Exception:
                return None
            time.sleep(0.05)
            return self._snapshot_locked(page.url)
        return self._submit(go_back, timeout)

    def forward(self, timeout=20.0) -> Optional[PreviewSnapshot]:
        def go_fwd():
            page = self._page
            try:
                page.go_forward(wait_until="load", timeout=15000)
            except Exception:
                return None
            time.sleep(0.05)
            return self._snapshot_locked(page.url)
        return self._submit(go_fwd, timeout)

    def hot_css(self, hrefs) -> bool:
        """CSS-only hot update through the page's own WebSocket channel
        listener (server.notify_hot_css triggers it); falls back to a
        direct style re-fetch when no WS client is connected."""
        def inject():
            page = self._page
            try:
                page.evaluate(
                    """(hrefs) => {
                        document.querySelectorAll(
                            'link[rel=\\"stylesheet\\"]').forEach(l => {
                            const key = (l.getAttribute('href') || '');
                            if (!hrefs.length || hrefs.some(h =>
                                key.indexOf(h.split('?')[0]) !== -1)) {
                                const clone = l.cloneNode();
                                clone.href = l.href.replace(/([?&])__cat=\\d+/, '')
                                    + (l.href.indexOf('?') === -1 ? '?' : '&')
                                    + '__cat=' + Date.now();
                                l.parentNode.replaceChild(clone, l);
                            }
                        });
                    }""", list(hrefs or []))
                return True
            except Exception:
                return False
        try:
            return bool(self._submit(inject, timeout=10.0))
        except Exception:
            return False

    def evaluate(self, js: str, timeout=10.0):
        return self._submit(lambda: self._page.evaluate(js), timeout)

    def screenshot(self, path: str) -> bool:
        def shot():
            try:
                self._page.screenshot(path=path, full_page=False)
                return True
            except Exception:
                return False
        try:
            return bool(self._submit(shot, timeout=15.0))
        except Exception:
            return False

    def resize_viewport(self, width: int, height: int):
        def do_resize():
            try:
                self._page.set_viewport_size({"width": int(width),
                                              "height": int(height)})
            except Exception:
                pass
        try:
            self._submit(do_resize, timeout=8.0)
        except Exception:
            pass

    def click(self, selector_or_text: str, timeout: float = 10.0) -> bool:
        def do_click():
            page = self._page
            try:
                if selector_or_text.startswith(("#", ".", "[", "button", "a", "input")):
                    page.click(selector_or_text, timeout=int(timeout * 1000))
                    return True
            except Exception:
                pass
            try:
                page.get_by_text(selector_or_text, exact=False).first.click(timeout=int(timeout * 1000))
                return True
            except Exception:
                pass
            try:
                page.click(f"text={selector_or_text}", timeout=int(timeout * 1000))
                return True
            except Exception as e:
                raise RuntimeError(f"Could not click '{selector_or_text}': {e}")
        return bool(self._submit(do_click, timeout=timeout + 2.0))

    def type_text(self, selector_or_placeholder: str, text: str, timeout: float = 10.0) -> bool:
        def do_type():
            page = self._page
            try:
                if selector_or_placeholder.startswith(("#", ".", "[", "input", "textarea")):
                    page.fill(selector_or_placeholder, text, timeout=int(timeout * 1000))
                    return True
            except Exception:
                pass
            try:
                page.get_by_placeholder(selector_or_placeholder).first.fill(text, timeout=int(timeout * 1000))
                return True
            except Exception:
                pass
            try:
                page.fill(f"input[name='{selector_or_placeholder}']", text, timeout=int(timeout * 1000))
                return True
            except Exception as e:
                raise RuntimeError(f"Could not type into '{selector_or_placeholder}': {e}")
        return bool(self._submit(do_type, timeout=timeout + 2.0))

    def get_interactive_elements(self, timeout: float = 10.0) -> list:
        js = """
        () => {
            const els = [];
            document.querySelectorAll('a, button, input, textarea, select, [role="button"]').forEach((el, idx) => {
                if (el.offsetParent === null && el.tagName !== 'INPUT') return;
                const tag = el.tagName.toLowerCase();
                const text = (el.textContent || el.placeholder || el.value || el.getAttribute('aria-label') || '').trim();
                const id = el.id ? '#' + el.id : '';
                const href = el.getAttribute('href') || '';
                els.push({
                    tag: tag,
                    text: text.slice(0, 80),
                    id: id,
                    selector: id || (tag + (el.className ? '.' + el.className.trim().split(/\\s+/)[0] : '')),
                    href: href,
                    type: el.type || ''
                });
            });
            return els.slice(0, 100);
        }
        """
        return self._submit(lambda: self._page.evaluate(js), timeout) or []

    def workflow_verify(self, expected_selectors: list = None, timeout: float = 10.0) -> dict:
        def do_verify():
            page = self._page
            res = {
                "url": page.url,
                "title": page.title() or "",
                "console_errors": len(self.js_errors),
                "js_errors": list(self.js_errors),
                "http_status": self.last_status,
                "missing_selectors": [],
                "verified": True,
            }
            if self.last_status and self.last_status >= 400:
                res["verified"] = False
                res["error"] = f"HTTP {self.last_status}"
            if self.js_errors:
                res["verified"] = False
            if expected_selectors:
                for sel in expected_selectors:
                    try:
                        count = page.locator(sel).count()
                        if count == 0:
                            res["missing_selectors"].append(sel)
                            res["verified"] = False
                    except Exception:
                        res["missing_selectors"].append(sel)
                        res["verified"] = False
            return res
        return self._submit(do_verify, timeout)

    # ------------------------------------------------------------- stop --
    def close(self, timeout=6.0):
        """Idempotent shutdown: kills Chromium + the worker thread."""
        self._stop = True
        try:
            if self._thread is not None and self._thread.is_alive():
                self._queue.put(None)
                self._thread.join(timeout=timeout)
        except Exception:
            pass
        for closer in ("_page", "_context", "_browser", "_pw"):
            obj = getattr(self, closer, None)
            setattr(self, closer, None)
            if obj is None:
                continue
            try:
                if closer == "_page":
                    obj.close()
                elif closer in ("_context", "_browser"):
                    obj.close()
                else:
                    obj.stop()
            except Exception:
                pass
        self._thread = None
