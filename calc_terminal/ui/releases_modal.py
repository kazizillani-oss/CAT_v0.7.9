"""
CAT UI — releases_modal.py: GitHub Releases & Updates Viewer.

Fetches and displays live GitHub releases from `kazizillani-oss/CAT_v0.7.9`,
providing rich changelogs, release notes, version comparison, and direct links.
"""

import json
import urllib.request
import webbrowser
from typing import Optional, Dict, Any

TEXTUAL_AVAILABLE = True
try:
    from textual.screen import Screen
    from textual.containers import Vertical, Horizontal, VerticalScroll
    from textual.widgets import Static, Button
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False


CAT_GITHUB_REPO = "kazizillani-oss/CAT_v0.7.9"
CAT_RELEASES_API_URL = f"https://api.github.com/repos/{CAT_GITHUB_REPO}/releases/latest"
CAT_CURRENT_VERSION = "0.9.000"


def fetch_latest_release(timeout: float = 3.5) -> Dict[str, Any]:
    """Fetch the latest release metadata from GitHub API, with offline fallback."""
    headers = {
        "User-Agent": f"CAT-CLI/{CAT_CURRENT_VERSION} (github-release-client)",
        "Accept": "application/vnd.github.v3+json",
    }
    req = urllib.request.Request(CAT_RELEASES_API_URL, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "online": True,
                    "tag_name": data.get("tag_name", f"v{CAT_CURRENT_VERSION}"),
                    "name": data.get("name") or f"CAT CLI v{CAT_CURRENT_VERSION}",
                    "published_at": (data.get("published_at") or "")[:10],
                    "html_url": data.get("html_url") or f"https://github.com/{CAT_GITHUB_REPO}/releases",
                    "body": data.get("body") or "",
                }
    except Exception:
        pass

    # Offline / Local Official Release Notes Fallback
    return {
        "online": False,
        "tag_name": f"v{CAT_CURRENT_VERSION}",
        "name": f"CAT CLI v{CAT_CURRENT_VERSION} — Ecosystem Expansion & Agent Skills",
        "published_at": "2026-11-14",
        "html_url": f"https://github.com/{CAT_GITHUB_REPO}/releases",
        "body": (
            "### 🌟 CAT CLI v0.9.000 Official Release Highlights\n\n"
            "1. **Complete Built-in Skills Ecosystem**: 30+ curated production agent skills bundled offline "
            "(REA, Archify, Remotion, SkillOpt, Page Mascot, Frontend Design, Cloudflare Security, Impeccable, Superpowers, and CAT-Native diagnostics).\n"
            "2. **VS Code-Style Extensions Manager**: 4 categories (Built-in, Installed, MCP Servers, Discover) with smooth scrolling, subfilters, and instant zero-lag debouncing.\n"
            "3. **Ultra-Responsive Portrait Mode**: Fullscreen Explorer and Code Editor layout in portrait view without header/navbar overlap.\n"
            "4. **Tactile 3D Bevels & WCAG AA Themes**: 30+ dark and vibrant themes with fluid statusline transitions and non-clipping action buttons.\n"
            "5. **High-Performance Architecture**: Removed recursive layout loops, optimized typing latency, and robust crash recovery."
        ),
    }


class GitHubReleasesModal(Screen if TEXTUAL_AVAILABLE else object):
    """Interactive modal dialog displaying latest GitHub releases and changelog."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close", show=False),
        Binding("enter", "dismiss_modal", "Close", show=False),
    ]

    DEFAULT_CSS = """
    GitHubReleasesModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.78);
    }
    #cct-rel-box {
        width: 78;
        max-width: 96%;
        height: auto;
        max-height: 88%;
        background: $surface;
        border: tall;
        border-top: tall $surface-highlight;
        border-left: tall $surface-highlight;
        border-bottom: tall $surface-shadow;
        border-right: tall $surface-shadow;
        padding: 0;
        layout: vertical;
        overflow: hidden;
    }
    #cct-rel-header {
        height: 3;
        min-height: 3;
        max-height: 3;
        padding: 0 2;
        layout: horizontal;
        align-vertical: middle;
        background: $surface-dark;
        border-bottom: solid $border;
    }
    #cct-rel-title {
        width: 1fr;
        color: $accent;
        text-style: bold;
        align-vertical: middle;
    }
    #cct-rel-esc {
        width: auto;
        color: $text-muted;
        text-style: italic;
        align-vertical: middle;
    }
    #cct-rel-scroll {
        height: 1fr;
        min-height: 12;
        padding: 1 2;
        overflow-y: auto;
        scrollbar-gutter: stable;
        scrollbar-size: 1 1;
    }
    .cct-rel-meta-card {
        height: auto;
        padding: 1;
        margin-bottom: 1;
        background: $surface-alt;
        border: tall;
        border-top: tall $surface-highlight;
        border-left: tall $surface-highlight;
        border-bottom: tall $surface-shadow;
        border-right: tall $surface-shadow;
    }
    .cct-rel-tag {
        color: #5af78e;
        text-style: bold;
    }
    .cct-rel-name {
        color: $text;
        text-style: bold;
        margin: 1 0 0 0;
    }
    .cct-rel-date {
        color: $text-faint;
        margin-bottom: 1;
    }
    .cct-rel-body {
        color: $text-muted;
        height: auto;
    }
    #cct-rel-footer {
        height: 4;
        min-height: 4;
        max-height: 4;
        padding: 0 2;
        layout: horizontal;
        align: right middle;
        background: $surface-dark;
        border-top: solid $border;
    }
    #cct-rel-footer Button {
        margin-left: 1;
        height: 3;
        min-width: 12;
        padding: 0 1;
        border: tall;
        border-top: tall $surface-highlight;
        border-left: tall $surface-highlight;
        border-bottom: tall $surface-shadow;
        border-right: tall $surface-shadow;
        text-style: bold;
    }
    #cct-rel-footer #cct-rel-gh-btn {
        background: $surface;
        color: $accent;
    }
    #cct-rel-footer #cct-rel-close-btn {
        background: $surface;
        color: $text;
    }
    """

    def __init__(self, release_data: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.release_data = release_data or fetch_latest_release()

    def compose(self):
        if not TEXTUAL_AVAILABLE:
            return
        rel = self.release_data
        tag = rel.get("tag_name", f"v{CAT_CURRENT_VERSION}")
        name = rel.get("name", "CAT CLI Release")
        date_str = rel.get("published_at", "")
        body_text = rel.get("body", "No release notes available.")
        is_online = rel.get("online", False)
        status_tag = "● GitHub Live" if is_online else "○ Offline Cached"

        with Vertical(id="cct-rel-box"):
            with Horizontal(id="cct-rel-header"):
                yield Static(f"🚀  GitHub Releases — {name}", id="cct-rel-title")
                yield Static(f"[{status_tag}]  [esc]", id="cct-rel-esc")
            with VerticalScroll(id="cct-rel-scroll"):
                with Vertical(classes="cct-rel-meta-card"):
                    yield Static(f"Installed Version: v{CAT_CURRENT_VERSION}  •  Latest Release: {tag}", classes="cct-rel-tag")
                    yield Static(f"Repository: https://github.com/{CAT_GITHUB_REPO}", classes="cct-rel-name")
                    if date_str:
                        yield Static(f"Published Date: {date_str}", classes="cct-rel-date")
                yield Static(body_text, classes="cct-rel-body")
            with Horizontal(id="cct-rel-footer"):
                yield Button("🌐 Open in GitHub", id="cct-rel-gh-btn")
                yield Button("Close", id="cct-rel-close-btn", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "cct-rel-gh-btn":
            url = self.release_data.get("html_url") or f"https://github.com/{CAT_GITHUB_REPO}/releases"
            try:
                webbrowser.open(url)
            except Exception:
                pass
            if hasattr(self.app, "_system_note"):
                self.app._system_note(f"Opened GitHub Releases: {url}")
            self.dismiss(None)
        elif bid == "cct-rel-close-btn":
            self.dismiss(None)

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)
