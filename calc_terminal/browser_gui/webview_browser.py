"""
Fallback browser via pywebview (Edge WebView2 on Windows).
Shows real HTML/CSS/JS, but with minimal chrome when Qt not available.
Still far better than terminal text — this is a real WebView2 surface.
"""

from __future__ import annotations

import os
import sys

def launch_webview_browser(start_url: str = "about:home") -> int:
    try:
        import webview  # type: ignore
    except ImportError:
        print("[CAT Browser] pywebview not installed. Run: pip install pywebview", file=sys.stderr)
        return 2

    # Normalize about:home to a data URL with new-tab HTML
    if start_url in ("about:home", "about:blank", "", None):
        # Load new-tab HTML via data URL
        try:
            from .qt_browser import _new_tab_html  # reuse same HTML
            html = _new_tab_html()
            # pywebview can load html string via data URL
            import urllib.parse
            data_url = "data:text/html;charset=utf-8," + urllib.parse.quote(html)
            start_url = data_url
        except Exception:
            start_url = "https://www.google.com"

    # Ensure localhost URLs are correct
    if start_url.startswith("localhost:"):
        start_url = "http://" + start_url

    title = "CAT Browser"
    # Try to get Fomoji title if start_url is fomoji
    if "localhost:3000" in start_url:
        title = "CAT Browser — Fomoji"

    try:
        # Create window with reasonable size, resizable, with min size
        window = webview.create_window(
            title, start_url,
            width=1200, height=800,
            min_size=(900, 600),
            text_select=True,
        )
        # Start the GUI loop (blocks until closed)
        # On Windows, this uses WebView2 and will render JS/WebGL correctly
        webview.start(debug=False)
        return 0
    except Exception as e:
        print(f"[CAT Browser] webview failed: {e}", file=sys.stderr)
        # Fallback: try to open in OS default browser as last resort? But spec says no external.
        # Instead, show error.
        return 1
