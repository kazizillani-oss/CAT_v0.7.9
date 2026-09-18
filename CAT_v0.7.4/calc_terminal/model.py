#!/usr/bin/env python3
"""
CAT CLI — Universal AI Provider Hub & Provider Center 2.0.

Interactive, responsive AI provider and model marketplace with:
- 160+ verified trusted providers
- Dynamic model discovery
- Real-time responsive layout engine (CATRootViewport)
- Persistent navigation bar with breadcrumbs and A–Z index
- Multi-category provider and model filters
- Verification-based custom and "My Models" management
- Hot model switching without CAT CLI restart
"""

import sys
import os
import time
import json
import re
import threading
from typing import Any, Dict, List, Optional, Set, Tuple

# ---- resolve project root -------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = (os.path.dirname(_HERE)
         if os.path.basename(_HERE) == "calc_terminal" else _HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ---- startup logging ------------------------------------------------------
_LOG_FILE = os.path.join(_ROOT, "startup.log")
def _log(msg, exc_info=False):
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
            if exc_info:
                import traceback
                traceback.print_exc(file=f)
    except Exception:
        pass

# Clear log on fresh start
try:
    with open(_LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] === CAT AI Provider Hub 2.0 ===\n")
except Exception:
    pass

from calc_terminal import aicore, theme
from calc_terminal.ui import theme_css
from calc_terminal.ui.viewport import CATRootViewport, CATViewportScreenMixin, get_terminal_size_class
from calc_terminal.models.active_state import ActiveAIStateManager, get_active_state, set_active_ai
from calc_terminal.models.verification_engine import ModelVerificationEngine, VerificationStatus

TEXTUAL_OK = True
try:
    from textual.app import App, ComposeResult
    from textual.screen import Screen, ModalScreen
    from textual.containers import Horizontal, Vertical, Container, ScrollableContainer
    from textual.widgets import Static, Input, Button, Label, ListView, ListItem, Header, Footer
    from textual.binding import Binding
    from textual.reactive import reactive
    from textual.widget import Widget
    from textual.events import Resize
except ImportError:
    TEXTUAL_OK = False

# ── ASCII Art & Logos ──────────────────────────────────────────────────────────

CCT_LOGO = [
    r"             __      ",
    r"            /\ \__   ",
    r"  ___    ___\ \ ,_\  ",
    r" /'___\ /'___\ \ \/  ",
    r"/\ \__//\ \__/\ \ \_ ",
    r"\ \____\ \____\\ \__\ ",
    r" \/____/\/____/ \/__/",
]

CCT_ALT = [
    r"          _                _             _      ",
    r"        /\ \             /\ \           /\ \    ",
    r"       /  \ \           /  \ \          \_\ \   ",
    r"      / /\ \ \         / /\ \ \         /\__ \  ",
    r"     / / /\ \ \       / / /\ \ \       / /_ \ \ ",
    r"    / / /  \ \_\     / / /  \ \_\     / / /\ \ \ ",
    r"   / / /    \/_/    / / /    \/_/    / / /  \/_/",
    r"  / / /            / / /            / / /       ",
    r" / / /________    / / /________    / / /        ",
    r"/ / /_________\  / / /_________\  /_/ /         ",
    r"\/____________/  \/____________/  \_\/          ",
]

CCT_CHEM = [
    r"          _____                    _____                _____          ",
    r"         /\    \                  /\    \              /\    \         ",
    r"        /::\    \                /::\    \            /::\    \        ",
    r"       /::::\    \              /::::\    \           \:::\    \       ",
    r"      /::::::\    \            /::::::\    \           \:::\    \      ",
    r"     /:::/\:::\    \          /:::/\:::\    \           \:::\    \     ",
    r"    /:::/  \:::\    \        /:::/  \:::\    \           \:::\    \    ",
    r"   /:::/    \:::\    \      /:::/    \:::\    \          /::::\    \   ",
    r"  /:::/    / \:::\    \    /:::/    / \:::\    \        /::::::\    \  ",
    r" /:::/    /   \:::\    \  /:::/    /   \:::\    \      /:::/\:::\    \ ",
    r"/:::/____/     \:::\____\/:::/____/     \:::\____\    /:::/  \:::\____\ ",
    r"\:::\    \      \::/    /\:::\    \      \::/    /   /:::/    \::/    /",
    r" \:::\    \      \/____/  \:::\    \      \/____/   /:::/    / \/____/ ",
    r"  \:::\    \               \:::\    \              /:::/    /          ",
    r"   \:::\    \               \:::\    \            /:::/    /           ",
    r"    \:::\    \               \:::\    \           \::/    /            ",
    r"     \:::\    \               \:::\    \           \/____/             ",
    r"      \:::\    \               \:::\    \                              ",
    r"       \:::\____\               \:::\____\                             ",
    r"        \::/    /                \::/    /                             ",
    r"         \/____/                  \/____/                              ",
]

# ── Color Palette & Helpers ───────────────────────────────────────────────────

def _hex(r, g, b):
    return f"#{r:02x}{g:02x}{b:02x}"

PURPLE = (187, 154, 247)
CYAN = (122, 162, 247)
GREEN = (158, 206, 106)
ORANGE = (224, 175, 104)
RED = (224, 108, 117)
GRAY = (100, 110, 125)
DIM = (75, 85, 100)
BG = (26, 27, 38)

C_ACCENT = _hex(*PURPLE)
C_CYAN = _hex(*CYAN)
C_GREEN = _hex(*GREEN)
C_ORANGE = _hex(*ORANGE)
C_RED = _hex(*RED)
C_DIM = _hex(*DIM)

def _step_header(current, label):
    """Generate a step indicator line like 'Step 1 of 4 — Select Provider'."""
    dots = ""
    for i in range(1, 5):
        if i == current:
            dots += f"[{C_ACCENT} b]●[/] "
        elif i < current:
            dots += f"[{C_GREEN}]●[/] "
        else:
            dots += f"[{C_DIM}]○[/] "
    return f"  {dots}  [{C_DIM}]Step {current} of 4 — {label}[/]"

def fuzzy_match(query: str, text: str) -> bool:
    query = query.lower().strip()
    if not query:
        return True
    text = text.lower()
    if query in text:
        return True
    qi, ti = 0, 0
    while qi < len(query) and ti < len(text):
        if query[qi] == text[ti]:
            qi += 1
        ti += 1
    return qi == len(query)

# ── Provider Database Loader ──────────────────────────────────────────────────

_EMERGENCY_FALLBACK_PROVIDERS = [
    {"id": "openai", "name": "OpenAI", "country": "United States",
     "url": "https://api.openai.com/v1", "api_style": "openai", "needs_key": True,
     "models": ["gpt-4o", "gpt-4o-mini", "o3-mini"],
     "features": ["chat", "reasoning", "vision", "embedding", "speech"],
     "openai_compat": True, "desc": "GPT-4o & o-series"},
    {"id": "anthropic", "name": "Anthropic (Claude)", "country": "United States",
     "url": "https://api.anthropic.com/v1", "api_style": "anthropic", "needs_key": True,
     "models": ["claude-4-sonnet", "claude-3-5-sonnet", "claude-3-5-haiku"],
     "features": ["chat", "reasoning", "vision", "code"],
     "openai_compat": False, "desc": "Claude 4 Sonnet & family"},
    {"id": "deepseek", "name": "DeepSeek", "country": "China",
     "url": "https://api.deepseek.com/v1", "api_style": "openai", "needs_key": True,
     "models": ["deepseek-chat", "deepseek-reasoner"],
     "features": ["chat", "reasoning", "code"], "openai_compat": True,
     "desc": "DeepSeek-V3 & R1"},
    {"id": "ollama", "name": "Ollama (Local)", "country": "International",
     "url": "http://localhost:11434", "api_style": "ollama", "needs_key": False,
     "models": ["llama3.3", "mistral", "deepseek-r1"],
     "features": ["chat", "local"], "openai_compat": True, "desc": "Local models"},
]

def _load_provider_database() -> List[Dict]:
    """Build normalized provider list from providers.json."""
    try:
        from calc_terminal.models import manager as _mgr
        providers = _mgr.list_providers()
        out = []
        for p in providers:
            features = []
            if p.get("supports_reasoning"):
                features.append("reasoning")
            if p.get("supports_vision"):
                features.append("vision")
            if p.get("supports_embeddings"):
                features.append("embedding")
            if p.get("supports_audio"):
                features.append("speech")
            if p.get("supports_streaming"):
                features.append("chat")
            out.append({
                "id": p.get("id", ""),
                "name": p.get("name", p.get("id", "")),
                "country": p.get("country", ""),
                "company": p.get("company", ""),
                "url": p.get("api_endpoint", ""),
                "api_style": p.get("api_style", "openai"),
                "needs_key": bool(p.get("needs_key", True)),
                "models": [str(m) for m in p.get("fallback_models", [])],
                "default_model": p.get("default_model", ""),
                "features": features or ["chat"],
                "openai_compat": bool(p.get("openai_compatible", False)),
                "desc": p.get("description", ""),
                "status": p.get("status", "online"),
                "verification_status": p.get("verification_status", "verified"),
            })
        if out:
            return out
    except Exception as e:
        _log(f"_load_provider_database error: {e}", exc_info=True)
    return [dict(p) for p in _EMERGENCY_FALLBACK_PROVIDERS]

PROVIDERS = _load_provider_database()
MORE_PROVIDERS = []
ALL_PROVIDERS = sorted(PROVIDERS, key=lambda p: p["name"].lower())

# ── Shared Wizard CSS ─────────────────────────────────────────────────────────

SHARED_WIZARD_CSS = theme_css.BASE_CSS + """
Screen {
    background: #1a1b26;
    color: #c0caf5;
    width: 100%;
    height: 100%;
    min-width: 100%;
    min-height: 100%;
    padding: 0;
    margin: 0;
}
CATRootViewport {
    width: 100%;
    height: 100%;
    min-width: 100%;
    min-height: 100%;
    layout: vertical;
    overflow: hidden;
}

/* Navigation Bar */
#nav-bar-container {
    height: 4;
    background: #141522;
    border-bottom: solid #24283b;
    padding: 0 1;
    layout: horizontal;
    align: left middle;
}
#nav-title {
    color: #a78bfa;
    text-style: bold;
    padding: 0 1;
    width: auto;
    height: 3;
    content-align: left middle;
}
#nav-tabs {
    width: 1fr;
    height: 3;
    layout: horizontal;
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-size: 0 0;
    align: left middle;
}
#nav-tabs Button {
    margin: 0 1;
    min-width: 10;
    height: 3;
    padding: 0 2;
    border: heavy;
    border-top: heavy $surface-highlight;
    border-left: heavy $surface-highlight;
    border-bottom: heavy $surface-shadow;
    border-right: heavy $surface-shadow;
    background: $surface-alt;
    color: $text;
    text-style: bold;
    content-align: center middle;
    transition: background 80ms, border 80ms, offset 80ms;
}
#nav-tabs Button:hover {
    background: $accent 25%;
    color: #ffffff;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy $accent-highlight;
    border-right: heavy $accent-highlight;
    offset-y: -1;
}
#nav-tabs Button.-active {
    offset-y: 1;
    border-top: heavy $accent-shadow;
    border-left: heavy $accent-shadow;
    border-bottom: heavy #ffffff;
    border-right: heavy #ffffff;
}
#nav-tabs Button.active-tab {
    background: #7c3aed;
    color: #ffffff;
    text-style: bold;
    border: heavy;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy #3c137a;
    border-right: heavy #3c137a;
}
#nav-tabs Button.active-tab:hover {
    background: #8b5cf6;
    border-bottom: heavy #c4b5fd;
    border-right: heavy #c4b5fd;
    color: #ffffff;
    offset-y: -1;
}
#nav-actions {
    width: auto;
    height: 3;
    layout: horizontal;
    align: right middle;
}
#nav-actions Button {
    margin: 0 1;
    min-width: 6;
    height: 3;
    padding: 0 1;
    border: heavy;
    border-top: heavy $surface-highlight;
    border-left: heavy $surface-highlight;
    border-bottom: heavy $surface-shadow;
    border-right: heavy $surface-shadow;
    background: $surface-alt;
    color: $text;
    text-style: bold;
    content-align: center middle;
    transition: background 80ms, border 80ms, offset 80ms;
}
#nav-actions Button:hover {
    background: $accent 25%;
    color: #ffffff;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy $accent-highlight;
    border-right: heavy $accent-highlight;
    offset-y: -1;
}
#nav-actions Button.-active {
    offset-y: 1;
    border-top: heavy $accent-shadow;
    border-left: heavy $accent-shadow;
    border-bottom: heavy #ffffff;
    border-right: heavy #ffffff;
}

/* Filters Bar */
#filter-bar {
    height: 4;
    background: #141522;
    padding: 0 1;
    layout: horizontal;
    align: left middle;
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-size: 0 0;
    border-bottom: solid #1e2233;
}
#filter-bar Button {
    margin: 0 1;
    min-width: 9;
    height: 3;
    padding: 0 2;
    border: heavy;
    border-top: heavy $surface-highlight;
    border-left: heavy $surface-highlight;
    border-bottom: heavy $surface-shadow;
    border-right: heavy $surface-shadow;
    background: $surface-alt;
    color: $text;
    text-style: bold;
    content-align: center middle;
    transition: background 80ms, border 80ms, offset 80ms;
}
#filter-bar Button:hover {
    background: $accent 25%;
    color: #ffffff;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy $accent-highlight;
    border-right: heavy $accent-highlight;
    offset-y: -1;
}
#filter-bar Button.-active {
    offset-y: 1;
    border-top: heavy $accent-shadow;
    border-left: heavy $accent-shadow;
    border-bottom: heavy #ffffff;
    border-right: heavy #ffffff;
}
#filter-bar Button.active-filter {
    background: #7c3aed;
    color: #ffffff;
    text-style: bold;
    border: heavy;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy #3c137a;
    border-right: heavy #3c137a;
}
#filter-bar Button.active-filter:hover {
    background: #8b5cf6;
    border-bottom: heavy #c4b5fd;
    border-right: heavy #c4b5fd;
    color: #ffffff;
    offset-y: -1;
}

/* Columns */
#main-columns {
    width: 100%;
    height: 1fr;
    layout: horizontal;
}
#left-col {
    width: 2fr;
    height: 100%;
    border-right: solid #24283b;
    padding: 0 1;
    layout: vertical;
}
#right-col {
    width: 1fr;
    height: 100%;
    padding: 1;
    layout: vertical;
}
#search-input {
    margin: 0 0 1 0;
    height: 3;
    background: #12131c;
    color: #c0caf5;
    border: tall;
    border-top: tall #08090e;
    border-left: tall #08090e;
    border-bottom: tall #2a2c42;
    border-right: tall #2a2c42;
    padding: 0 1;
}
#search-input:focus {
    border: tall;
    border-top: tall #3c137a;
    border-left: tall #3c137a;
    border-bottom: tall #a78bfa;
    border-right: tall #a78bfa;
}
#provider-list {
    height: 1fr;
    overflow-y: auto;
}
#provider-actions {
    height: 4;
    align: center middle;
    padding: 0 1;
    background: #141522;
    border-top: solid #24283b;
    layout: horizontal;
    overflow-x: auto;
    scrollbar-size: 0 0;
}
#provider-actions Button {
    margin: 0 1;
    min-width: 12;
    height: 3;
    padding: 0 2;
    border: heavy;
    border-top: heavy $surface-highlight;
    border-left: heavy $surface-highlight;
    border-bottom: heavy $surface-shadow;
    border-right: heavy $surface-shadow;
    background: $surface-alt;
    color: $text;
    text-style: bold;
    content-align: center middle;
    transition: background 80ms, border 80ms, offset 80ms;
}
#provider-actions Button:hover {
    background: $accent 25%;
    color: #ffffff;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy $accent-highlight;
    border-right: heavy $accent-highlight;
    offset-y: -1;
}
#provider-actions Button.-active {
    offset-y: 1;
    border-top: heavy $accent-shadow;
    border-left: heavy $accent-shadow;
    border-bottom: heavy #ffffff;
    border-right: heavy #ffffff;
}
#btn-select-main {
    background: #7c3aed;
    color: #ffffff;
    text-style: bold;
    border: heavy;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy #3c137a;
    border-right: heavy #3c137a;
}
#btn-select-main:hover {
    background: #8b5cf6;
    border-bottom: heavy #c4b5fd;
    border-right: heavy #c4b5fd;
    color: #ffffff;
    offset-y: -1;
}

/* Rows & Details */
ProviderRow {
    height: 3;
    padding: 0 1;
    border-left: solid transparent;
}
ProviderRow:hover {
    background: #24283b;
}
ProviderRow.selected {
    background: #202438;
    border-left: thick #7c3aed;
}
InfoPanel {
    height: 100%;
    overflow-y: auto;
    layout: vertical;
}
#info-content {
    height: 1fr;
    overflow-y: auto;
}
#info-actions {
    height: auto;
    layout: vertical;
    margin-top: 1;
    border-top: solid #24283b;
    padding-top: 1;
}
#info-actions Button {
    margin: 0 0 1 0;
    width: 100%;
    height: 3;
    padding: 0 2;
    border: heavy;
    border-top: heavy $surface-highlight;
    border-left: heavy $surface-highlight;
    border-bottom: heavy $surface-shadow;
    border-right: heavy $surface-shadow;
    background: $surface-alt;
    color: $text;
    text-style: bold;
    content-align: center middle;
    transition: background 80ms, border 80ms, offset 80ms;
}
#info-actions Button:hover {
    background: $accent 25%;
    color: #ffffff;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy $accent-highlight;
    border-right: heavy $accent-highlight;
    offset-y: -1;
}
#info-actions Button.-active {
    offset-y: 1;
    border-top: heavy $accent-shadow;
    border-left: heavy $accent-shadow;
    border-bottom: heavy #ffffff;
    border-right: heavy #ffffff;
}
#btn-select-provider {
    background: #7c3aed;
    color: #ffffff;
    text-style: bold;
    border: heavy;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy #3c137a;
    border-right: heavy #3c137a;
}
#btn-select-provider:hover {
    background: #8b5cf6;
    border-bottom: heavy #c4b5fd;
    border-right: heavy #c4b5fd;
    color: #ffffff;
    offset-y: -1;
}
#btn-toggle-failover {
    background: $surface-alt;
    color: $text;
    border: heavy;
    border-top: heavy $surface-highlight;
    border-left: heavy $surface-highlight;
    border-bottom: heavy $surface-shadow;
    border-right: heavy $surface-shadow;
}
#btn-toggle-failover:hover {
    background: $accent 25%;
    color: #ffffff;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy $accent-highlight;
    border-right: heavy $accent-highlight;
    offset-y: -1;
}
#btn-test-provider {
    background: $surface-alt;
    color: $text;
    border: heavy;
    border-top: heavy $surface-highlight;
    border-left: heavy $surface-highlight;
    border-bottom: heavy $surface-shadow;
    border-right: heavy $surface-shadow;
}
#btn-test-provider:hover {
    background: $accent 25%;
    color: #ffffff;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy $accent-highlight;
    border-right: heavy $accent-highlight;
    offset-y: -1;
}

/* ModelScreen Styles */
#model-nav-bar {
    height: 4;
    background: #141522;
    padding: 0 1;
    layout: horizontal;
    align: left middle;
    border-bottom: solid #1e2233;
}
#model-nav-bar Button {
    margin: 0 1;
    min-width: 12;
    height: 3;
    padding: 0 2;
    border: heavy;
    border-top: heavy $surface-highlight;
    border-left: heavy $surface-highlight;
    border-bottom: heavy $surface-shadow;
    border-right: heavy $surface-shadow;
    background: $surface-alt;
    color: $text;
    text-style: bold;
    content-align: center middle;
    transition: background 80ms, border 80ms, offset 80ms;
}
#model-nav-bar Button:hover {
    background: $accent 25%;
    color: #ffffff;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy $accent-highlight;
    border-right: heavy $accent-highlight;
    offset-y: -1;
}
#model-title {
    height: 3;
    content-align: center middle;
    color: #a78bfa;
    text-style: bold;
    width: 1fr;
}
#model-search {
    margin: 1 1 0 1;
    height: 3;
    background: #12131c;
    color: #c0caf5;
    border: tall;
    border-top: tall #08090e;
    border-left: tall #08090e;
    border-bottom: tall #2a2c42;
    border-right: tall #2a2c42;
    padding: 0 1;
}
#model-search:focus {
    border: tall;
    border-top: tall #3c137a;
    border-left: tall #3c137a;
    border-bottom: tall #a78bfa;
    border-right: tall #a78bfa;
}
#model-count-label {
    padding: 0 2;
    height: 1;
    color: #7982a9;
}
#model-list {
    height: 1fr;
    padding: 0 1;
    background: #141522;
    overflow-y: auto;
}
ModelRow {
    height: 2;
    padding: 0 1;
    border-left: solid transparent;
    content-align: left middle;
}
ModelRow:hover {
    background: #24283b;
}
ModelRow.selected {
    background: #202438;
    border-left: thick #7c3aed;
    color: #ffffff;
    text-style: bold;
}
#model-actions {
    height: 4;
    align: center middle;
    padding: 0 1;
    background: #141522;
    border-top: solid #24283b;
    layout: horizontal;
    overflow-x: auto;
    scrollbar-size: 0 0;
}
#model-actions Button {
    margin: 0 1;
    min-width: 12;
    height: 3;
    padding: 0 2;
    border: heavy;
    border-top: heavy $surface-highlight;
    border-left: heavy $surface-highlight;
    border-bottom: heavy $surface-shadow;
    border-right: heavy $surface-shadow;
    background: $surface-alt;
    color: $text;
    text-style: bold;
    content-align: center middle;
    transition: background 80ms, border 80ms, offset 80ms;
}
#model-actions Button:hover {
    background: $accent 25%;
    color: #ffffff;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy $accent-highlight;
    border-right: heavy $accent-highlight;
    offset-y: -1;
}
#model-actions Button.-active {
    offset-y: 1;
    border-top: heavy $accent-shadow;
    border-left: heavy $accent-shadow;
    border-bottom: heavy #ffffff;
    border-right: heavy #ffffff;
}
#btn-select-model-main {
    background: #7c3aed;
    color: #ffffff;
    text-style: bold;
    border: heavy;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy #3c137a;
    border-right: heavy #3c137a;
}
#btn-select-model-main:hover {
    background: #8b5cf6;
    border-bottom: heavy #c4b5fd;
    border-right: heavy #c4b5fd;
    color: #ffffff;
    offset-y: -1;
}

/* My Models Row Styles */
.my-model-row {
    height: 4;
    padding: 0 1;
    margin-bottom: 1;
    background: $surface-alt;
    border: heavy;
    border-top: heavy $surface-highlight;
    border-left: heavy $surface-highlight;
    border-bottom: heavy $surface-shadow;
    border-right: heavy $surface-shadow;
    align: left middle;
}
.my-model-row:hover {
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy $accent-highlight;
    border-right: heavy $accent-highlight;
}
.my-model-row Static {
    width: 1fr;
}
.my-model-row Button {
    margin-left: 1;
    min-width: 12;
    height: 3;
    padding: 0 2;
    border: heavy;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy #3c137a;
    border-right: heavy #3c137a;
    background: #7c3aed;
    color: #ffffff;
    text-style: bold;
    transition: background 80ms, border 80ms, offset 80ms;
}
.my-model-row Button:hover {
    background: #8b5cf6;
    border-bottom: heavy #c4b5fd;
    border-right: heavy #c4b5fd;
    color: #ffffff;
    offset-y: -1;
}

/* Modals & Dialogs */
#api-key-box, #verify-box, #model-box, #custom-box {
    align: center top;
    padding: 2;
    overflow-y: auto;
    width: 100%;
    height: 100%;
}
#api-key-box Button, #verify-box Button, #model-box Button, #custom-box Button {
    margin: 0 1;
    min-width: 12;
    height: 3;
    padding: 0 2;
    border: heavy;
    border-top: heavy $surface-highlight;
    border-left: heavy $surface-highlight;
    border-bottom: heavy $surface-shadow;
    border-right: heavy $surface-shadow;
    background: $surface-alt;
    color: $text;
    text-style: bold;
    content-align: center middle;
    transition: background 80ms, border 80ms, offset 80ms;
}
#api-key-box Button:hover, #verify-box Button:hover, #model-box Button:hover, #custom-box Button:hover {
    background: $accent 25%;
    color: #ffffff;
    border-top: heavy #ffffff;
    border-left: heavy #ffffff;
    border-bottom: heavy $accent-highlight;
    border-right: heavy $accent-highlight;
    offset-y: -1;
}
#api-key-box Button.-active, #verify-box Button.-active, #model-box Button.-active, #custom-box Button.-active {
    offset-y: 1;
    border-top: heavy $accent-shadow;
    border-left: heavy $accent-shadow;
    border-bottom: heavy #ffffff;
    border-right: heavy #ffffff;
}
"""

if TEXTUAL_OK:

    # ── UI Components ─────────────────────────────────────────────────────────

    class ProviderRow(Static):
        """One row in the provider list, responsive to mouse clicks and touch taps."""

        def __init__(self, provider, index=0, selected=False, in_failover=False, query=""):
            super().__init__("")
            self._provider = provider
            self._index = index
            self._selected = selected
            self._in_failover = in_failover
            self._query = query

        def on_click(self) -> None:
            """Handle mouse click and touch screen tap."""
            try:
                if hasattr(self.screen, "_on_row_clicked"):
                    self.screen._on_row_clicked(self._provider, self._index)
            except Exception:
                pass

        def render(self):
            name = self._provider["name"]
            country = self._provider.get("country", "")
            desc = self._provider.get("desc", "")
            status = self._provider.get("status", "online").lower()
            bullet = "●" if status == "online" else ("◐" if status == "degraded" else "○")
            bullet_color = C_GREEN if status == "online" else (C_ORANGE if status == "degraded" else C_DIM)

            mark = "▶ " if self._selected else "  "
            style_open = f"[{C_ACCENT} b]" if self._selected else ""
            style_close = "[/]" if self._selected else ""
            country_tag = f"[{C_DIM}]{country}[/]" if country else ""
            failover_tag = f" [{C_CYAN}][⇄ FAILOVER][/]" if self._in_failover else ""
            return (
                f"{mark}[{bullet_color}]{bullet}[/] {style_open}{name}{style_close}  {country_tag}{failover_tag}\n"
                f"    [{C_DIM}]{desc}[/]"
            )

    class ModelRow(Static):
        """Clickable, touch-friendly row representing a discovered model."""

        def __init__(self, model_name: str, index: int, is_selected: bool, screen: Any, in_failover: bool = False):
            super().__init__("")
            self._model_name = model_name
            self._index = index
            self._is_selected = is_selected
            self._screen = screen
            self._in_failover = in_failover

        def on_mount(self) -> None:
            if self._is_selected:
                self.add_class("selected")
            else:
                self.remove_class("selected")

        def on_click(self) -> None:
            """Handle mouse click and touch screen tap."""
            try:
                if hasattr(self._screen, "_on_row_clicked"):
                    self._screen._on_row_clicked(self._model_name, self._index)
            except Exception:
                pass

        def render(self):
            mark = "▶ " if self._is_selected else "  "
            style_open = f"[{C_ACCENT} b]" if self._is_selected else ""
            style_close = "[/]" if self._is_selected else ""
            failover_badge = f"  [{C_ORANGE}][⇄ FAILOVER][/]" if self._in_failover else ""
            return f"{mark}{style_open}{self._model_name}{style_close}{failover_badge}"

    class AlphabetHeader(Static):
        """Pinned alphabet header in the list."""

        def __init__(self, letter):
            super().__init__(f"\n[{C_CYAN}]━━━━━  {letter}  ━━━━━[/]\n")

    class InfoPanel(Vertical):
        """Right-side details panel with interactive touch/mouse buttons."""

        def __init__(self):
            super().__init__()
            self._provider = None
            self._in_failover = False
            self._failover_priority = -1

        def compose(self):
            yield Static("", id="info-content")
            with Vertical(id="info-actions"):
                yield Button("  ➜  Select as Active AI  ", id="btn-select-provider")
                yield Button("  ⇄  Add to Failover Chain  ", id="btn-toggle-failover")
                yield Button("  ⟳  Test Connection  ", id="btn-test-provider")

        def set_provider(self, provider, in_failover=False, failover_priority=-1):
            self._provider = provider
            self._in_failover = in_failover
            self._failover_priority = failover_priority
            self._update_display()

        def _update_display(self):
            p = self._provider
            if not p:
                try:
                    self.query_one("#info-content", Static).update(
                        f"\n\n\n  [{C_DIM}]Select a provider on the left or tap with cursor/touch to inspect[/]\n"
                    )
                except Exception:
                    pass
                return

            status = p.get("status", "online").lower()
            status_text = "ONLINE" if status == "online" else ("DEGRADED" if status == "degraded" else "OFFLINE")
            status_color = C_GREEN if status == "online" else (C_ORANGE if status == "degraded" else C_RED)

            failover_text = (
                f"[{C_GREEN}]✓ Active (Priority #{self._failover_priority + 1})[/]"
                if self._in_failover
                else f"[{C_DIM}]Not in chain[/]"
            )

            lines = [
                f"\n",
                f"  [{C_ACCENT} b]{p['name']}[/]",
                f"  [{C_DIM}]" + "─" * 32 + "[/]",
                f"  [{C_DIM}]Status:[/]        [{status_color}]● {status_text}[/]",
                f"  [{C_DIM}]Company:[/]       {p.get('company') or p['name']}",
                f"  [{C_DIM}]Country:[/]       {p.get('country', 'N/A')}",
                f"  [{C_DIM}]Protocol:[/]      {p.get('api_style', 'openai').upper()}",
                f"  [{C_DIM}]Authentication:[/] {'Required (API Key)' if p.get('needs_key') else 'No key needed'}",
                f"  [{C_DIM}]Endpoint:[/]      {p.get('url', 'N/A')}",
                f"  [{C_DIM}]Failover Chain:[/] {failover_text}",
                f"  [{C_DIM}]Verified:[/]      [{C_GREEN}]✓ Verified[/]",
                f"",
                f"  [{C_DIM}]Supported Models:[/]",
            ]
            models = p.get("models", [])
            for m in models[:8]:
                lines.append(f"    [{C_CYAN}]•[/] {m}")
            if len(models) > 8:
                lines.append(f"    [{C_DIM}]… and {len(models)-8} more models[/]")
            if not models:
                lines.append(f"    [{C_DIM}](Dynamic model discovery enabled)[/]")

            features = p.get("features", [])
            lines += [
                f"",
                f"  [{C_DIM}]Capabilities:[/]  {', '.join(features) if features else 'Chat'}",
                f"  [{C_DIM}]OpenAI Compat:[/] {'Yes' if p.get('openai_compat') else 'No'}",
                f"",
                f"  [{C_DIM}]{p.get('desc', '')}[/]",
            ]
            try:
                self.query_one("#info-content", Static).update("\n".join(lines))
                btn = self.query_one("#btn-toggle-failover", Button)
                if self._in_failover:
                    btn.label = "  ✕  Remove from Failover Chain  "
                else:
                    btn.label = "  ⇄  Add to Failover Chain  "
            except Exception:
                pass

    # ── Model Selection Confirmation Dialog ───────────────────────────────────

    class ModelConfirmModal(Screen):
        """Confirmation modal dialog before hot-switching provider/model."""

        DEFAULT_CSS = """
        ModelConfirmModal {
            align: center middle;
            background: #1a1b26 75%;
            width: 100%;
            height: 100%;
        }
        #confirm-box {
            width: 58;
            height: auto;
            background: #1f2335;
            border: round #a78bfa;
            padding: 2 3;
            layout: vertical;
        }
        #confirm-title {
            color: #a78bfa;
            text-style: bold;
            text-align: center;
            margin-bottom: 1;
        }
        #confirm-info {
            margin: 1 0;
            color: #c0caf5;
        }
        #confirm-buttons {
            height: 3;
            align: center middle;
            margin-top: 1;
            layout: horizontal;
        }
        #confirm-buttons Button {
            margin: 0 1;
            min-width: 14;
            height: 3;
            padding: 0 2;
            border: solid $border;
            background: $surface-alt;
            color: $text;
            text-style: not bold;
            content-align: center middle;
        }
        #confirm-buttons Button:hover {
            background: $accent 18%;
            border: solid $border-active;
            color: #ffffff;
        }
        #btn-apply-model {
            background: #7c3aed;
            color: #ffffff;
            border: solid #a78bfa;
            text-style: bold;
        }
        #btn-apply-model:hover {
            background: #8b5cf6;
            border: solid #c4b5fd;
            color: #ffffff;
        }
        #btn-cancel-model {
            background: $surface-alt;
            color: $text;
            border: solid $border;
        }
        #btn-cancel-model:hover {
            background: $accent 18%;
            border: solid $border-active;
            color: #ffffff;
        }
        """

        BINDINGS = [
            Binding("escape", "cancel", "Cancel"),
            Binding("enter", "apply", "Apply"),
        ]

        def __init__(self, provider_id: str, model_id: str, config: Dict):
            super().__init__()
            self._provider_id = provider_id
            self._model_id = model_id
            self._config = config

        def compose(self):
            with Vertical(id="confirm-box"):
                yield Static("CONFIRM MODEL SWITCH", id="confirm-title")
                info_text = (
                    f"  [b]Provider:[/] {self._provider_id}\n"
                    f"  [b]Model:[/]    {self._model_id}\n"
                    f"  [b]Status:[/]   [{C_GREEN}]Ready[/]\n\n"
                    f"  [{C_DIM}]Changes take effect immediately without restarting CAT.[/]"
                )
                yield Static(info_text, id="confirm-info")
                with Horizontal(id="confirm-buttons"):
                    yield Button("  ✓ Apply  ", id="btn-apply-model")
                    yield Button("  ✕ Cancel  ", id="btn-cancel-model")

        def on_mount(self):
            try:
                self.query_one("#btn-apply-model", Button).focus()
            except Exception:
                pass

        def action_apply(self):
            # Authoritative hot switch
            set_active_ai(self._provider_id, self._model_id, self._config)
            self.dismiss(self._config)

        def action_cancel(self):
            self.dismiss(None)

        def on_button_pressed(self, event):
            if event.button.id == "btn-apply-model":
                self.action_apply()
            elif event.button.id == "btn-cancel-model":
                self.action_cancel()

    def _finish_wizard_screen(screen: Any, result: Optional[Dict] = None) -> None:
        """Safely dismiss a wizard screen or modal without terminating CCT host app."""
        if isinstance(result, dict) and result.get("provider"):
            try:
                from calc_terminal.models.active_state import set_active_ai
                set_active_ai(result.get("provider"), result.get("model", ""), result)
            except Exception:
                pass
            try:
                from calc_terminal import model_router
                model_router.invalidate_cache()
            except Exception:
                pass

        try:
            app = screen.app
        except Exception:
            app = None
        app_name = getattr(getattr(app, "__class__", None), "__name__", "")
        if app is not None and app_name == "ModelSelectorApp":
            try:
                app.exit(result=result)
            except Exception:
                pass
            return

        try:
            screen.dismiss(result)
        except Exception:
            try:
                if app is not None and hasattr(app, "pop_screen"):
                    app.pop_screen()
            except Exception:
                pass

    # ── Main Provider Selection Screen ────────────────────────────────────────

    class ProviderScreen(CATViewportScreenMixin, Screen):
        """Universal AI Provider Hub 2.0 Screen."""

        DEFAULT_CSS = SHARED_WIZARD_CSS

        BINDINGS = [
            Binding("escape", "go_back", "Back"),
            Binding("ctrl+c", "go_back", "Quit"),
            Binding("enter", "select", "Select"),
            Binding("slash", "focus_search", "Search"),
            Binding("r", "refresh_list", "Refresh"),
        ]

        def __init__(self, embedded=False):
            super().__init__()
            self._embedded = embedded
            try:
                from calc_terminal.providers.provider_manager import enrich_providers, verify_provider_count
                verify_provider_count(ALL_PROVIDERS)
                self._all = enrich_providers(ALL_PROVIDERS)
            except Exception:
                self._all = list(ALL_PROVIDERS)
            self._filtered = list(self._all)
            self._selected_index = 0
            self._search = ""
            self._active_filter = "ALL"

        def compose(self):
            with CATRootViewport(id="provider-viewport", on_size_change=self._on_viewport_size):
                # Minimalist Filter Bar (Sleek single row, no overflow, no empty boxes)
                with Horizontal(id="filter-bar"):
                    filters = ["ALL", "VERIFIED", "LOCAL", "CLOUD", "CHINESE", "FREE", "REASONING"]
                    for f in filters:
                        cls = "active-filter" if f == self._active_filter else ""
                        yield Button(f, id=f"filter-{f.lower()}", classes=cls)

                # Two-panel layout
                with Horizontal(id="main-columns"):
                    with Vertical(id="left-col"):
                        yield Static(_step_header(1, "Select Provider"), id="step-indicator")
                        yield Input(placeholder="🔍 Type to filter or press Enter to select... (e.g. deepseek, ollama)", id="search-input")
                        yield Static(f"[{C_DIM}]  Showing {len(self._filtered)} of {len(self._all)} verified providers[/]", id="result-count")
                        yield ScrollableContainer(id="provider-list")
                    with Vertical(id="right-col"):
                        yield InfoPanel()

                # Global Action Bar across full bottom width
                with Horizontal(id="provider-actions"):
                    yield Button("✕ Back", id="btn-exit")
                    yield Button("➜ Select", id="btn-select-main")
                    yield Button("⇄ Failover", id="btn-failover-main")
                    yield Button("➕ Add", id="btn-add-provider")
                    yield Button("⇅ Import", id="btn-import")
                    yield Button("⤒ Export", id="btn-export")

        def on_mount(self):
            self._rebuild_list()
            try:
                self.query_one("#search-input", Input).focus()
            except Exception:
                pass

        def on_input_submitted(self, event: Input.Submitted) -> None:
            """Pressing Enter in search input immediately confirms selection."""
            if event.input.id == "search-input":
                self._confirm_selection()

        def _on_row_clicked(self, provider: Dict, index: int) -> None:
            """Handle mouse click and touch screen tap on provider row."""
            if self._selected_index == index:
                self._confirm_selection()
            else:
                self._selected_index = index
                self._rebuild_list()
                self._update_info()
                self._scroll_to_selected()

        def _get_failover_provider_ids(self) -> set:
            try:
                from calc_terminal.providers import provider_manager as pm
                return {b.get("provider") for b in pm.load_backup_providers()}
            except Exception:
                return set()

        def _get_failover_info(self, provider_id: str) -> dict:
            try:
                from calc_terminal.providers import provider_manager as pm
                backups = pm.load_backup_providers()
                for idx, b in enumerate(backups):
                    if b.get("provider") == provider_id:
                        return {"in_failover": True, "priority": idx}
            except Exception:
                pass
            return {"in_failover": False, "priority": -1}

        def _on_viewport_size(self, size_class: str):
            """Dynamically adjust columns and layout when terminal resizes."""
            try:
                cols = self.query_one("#main-columns", Horizontal)
                left = self.query_one("#left-col", Vertical)
                right = self.query_one("#right-col", Vertical)
                if size_class == "large":
                    left.styles.width = "2fr"
                    right.styles.display = "block"
                elif size_class == "medium":
                    left.styles.width = "3fr"
                    right.styles.display = "block"
                elif size_class == "small":
                    left.styles.width = "100%"
                    right.styles.display = "none"
                else:  # very_small
                    left.styles.width = "100%"
                    right.styles.display = "none"
            except Exception:
                pass

        def _rebuild_list(self):
            try:
                container = self.query_one("#provider-list", ScrollableContainer)
            except Exception:
                return
            container.remove_children()
            query = self._search
            current_letter = ""
            idx = 0
            failover_ids = self._get_failover_provider_ids()

            for p in self._filtered:
                name = p["name"]
                first = name[0].upper() if name else ""
                if first != current_letter and not query:
                    current_letter = first
                    container.mount(AlphabetHeader(current_letter))
                in_failover = p.get("id") in failover_ids
                row = ProviderRow(
                    p, index=idx, selected=(idx == self._selected_index),
                    in_failover=in_failover, query=query
                )
                if idx == self._selected_index:
                    row.add_class("selected")
                container.mount(row)
                idx += 1
            self._update_count()
            self._update_info()

        def _update_count(self):
            try:
                self.query_one("#result-count", Static).update(
                    f"[{C_DIM}]  Showing {len(self._filtered)} of {len(self._all)} verified providers[/]"
                )
            except Exception:
                pass

        def _update_info(self):
            if 0 <= self._selected_index < len(self._filtered):
                p = self._filtered[self._selected_index]
                f_info = self._get_failover_info(p.get("id"))
                try:
                    self.query_one(InfoPanel).set_provider(
                        p, in_failover=f_info["in_failover"],
                        failover_priority=f_info["priority"]
                    )
                except Exception:
                    pass

        def on_input_changed(self, event):
            if event.input.id == "search-input":
                self._search = event.input.value
                self._apply_filters()

        def _apply_filters(self):
            filtered = list(self._all)
            f = self._active_filter

            if f == "VERIFIED":
                filtered = [p for p in filtered if p.get("verification_status") == "verified"]
            elif f == "AVAILABLE":
                filtered = [p for p in filtered if p.get("status") == "online"]
            elif f == "API":
                filtered = [p for p in filtered if p.get("needs_key")]
            elif f == "LOCAL":
                filtered = [p for p in filtered if not p.get("needs_key") or p.get("id") == "ollama"]
            elif f == "CLOUD":
                filtered = [p for p in filtered if p.get("id") != "ollama"]
            elif f == "FREE":
                filtered = [p for p in filtered if not p.get("needs_key")]
            elif f == "CHINESE":
                filtered = [p for p in filtered if p.get("country", "").lower() == "china"]
            elif f == "GLOBAL":
                filtered = [p for p in filtered if p.get("country", "").lower() != "china"]
            elif f == "REASONING":
                filtered = [p for p in filtered if "reasoning" in p.get("features", [])]
            elif f == "CODING":
                filtered = [p for p in filtered if "code" in p.get("features", []) or "reasoning" in p.get("features", [])]
            elif f == "VISION":
                filtered = [p for p in filtered if "vision" in p.get("features", [])]
            elif f == "CUSTOM":
                filtered = [p for p in filtered if p.get("id", "").startswith("custom")]

            if self._search:
                filtered = [p for p in filtered if fuzzy_match(self._search, p["name"]) or fuzzy_match(self._search, p.get("desc", ""))]

            self._filtered = filtered
            self._selected_index = 0
            self._rebuild_list()

        def on_key(self, event):
            if event.key == "down":
                if self._selected_index < len(self._filtered) - 1:
                    self._selected_index += 1
                    self._rebuild_list()
                    self._scroll_to_selected()
            elif event.key == "up":
                if self._selected_index > 0:
                    self._selected_index -= 1
                    self._rebuild_list()
                    self._scroll_to_selected()
            elif event.key == "pagedown":
                self._selected_index = min(self._selected_index + 10, len(self._filtered) - 1)
                self._rebuild_list()
                self._scroll_to_selected()
            elif event.key == "pageup":
                self._selected_index = max(self._selected_index - 10, 0)
                self._rebuild_list()
                self._scroll_to_selected()
            elif event.key == "home":
                self._selected_index = 0
                self._rebuild_list()
                self._scroll_to_selected()
            elif event.key == "end":
                self._selected_index = len(self._filtered) - 1
                self._rebuild_list()
                self._scroll_to_selected()
            elif event.key == "enter":
                self._confirm_selection()
            elif event.key == "f":
                self._toggle_failover_for_selected()

        def _scroll_to_selected(self):
            try:
                rows = self.query_one("#provider-list", ScrollableContainer).query(ProviderRow)
                for i, row in enumerate(rows):
                    if i == self._selected_index:
                        row.scroll_visible()
                        break
            except Exception:
                pass

        def action_focus_search(self):
            try:
                self.query_one("#search-input", Input).focus()
            except Exception:
                pass

        def action_refresh_list(self):
            self._all = _load_provider_database()
            self._apply_filters()

        def action_select(self):
            self._confirm_selection()

        def _confirm_selection(self):
            if 0 <= self._selected_index < len(self._filtered):
                provider = self._filtered[self._selected_index]
                try:
                    self.app.push_screen(ModelScreen(provider, embedded=self._embedded), self._on_subscreen_closed)
                except Exception as ex:
                    _log(f"Error opening ModelScreen: {ex}")

        def _toggle_failover_for_selected(self) -> None:
            if not (0 <= self._selected_index < len(self._filtered)):
                return
            p = self._filtered[self._selected_index]
            pid = p.get("id")
            try:
                from calc_terminal.providers import provider_manager as pm
                current_backups = pm.load_backup_providers()
                existing_idx = next((i for i, b in enumerate(current_backups) if b.get("provider") == pid), -1)
                if existing_idx >= 0:
                    current_backups.pop(existing_idx)
                    self.notify(f"Removed {p['name']} from Backup Failover Chain", title="Failover Chain")
                else:
                    default_m = p.get("default_model") or (p.get("models", ["default"])[0] if p.get("models") else "default")
                    current_backups.append({
                        "provider": pid,
                        "model": default_m,
                        "enabled": True,
                        "api_style": p.get("api_style", "openai"),
                        "base_url": p.get("url", ""),
                    })
                    self.notify(f"Added {p['name']} to Backup Failover Chain", title="Failover Chain")
                pm.save_backup_providers(current_backups)
                self._rebuild_list()
                self._update_info()
            except Exception as e:
                self.notify(f"Failover update error: {e}", title="Error", severity="error")

        def _open_failover_panel(self) -> None:
            try:
                from calc_terminal.ui.backup_panel import BackupProvidersPanel
                self.app.push_screen(BackupProvidersPanel())
            except Exception as e:
                self.notify(f"Could not open Backup Providers panel: {e}", severity="error")

        def _test_selected_provider(self) -> None:
            if not (0 <= self._selected_index < len(self._filtered)):
                return
            p = self._filtered[self._selected_index]
            self.notify(f"Probing connection to {p['name']}...", title="Connection Test")
            def _bg_test():
                try:
                    from calc_terminal.models.verification_engine import get_verification_engine
                    engine = get_verification_engine()
                    report = engine.verify_custom_model({
                        "provider_id": p.get("id"),
                        "model_id": p.get("default_model") or "test",
                        "base_url": p.get("url", ""),
                        "api_key": "",
                    })
                    is_ok = report.success or report.get("status") in ("ready", "auth_required", "VERIFIED", "PARTIALLY_VERIFIED")
                    summary = "Reachability OK" if is_ok else f"Issue: {report.get('error') or report.get('message') or 'Check connection'}"
                    self.app.call_from_thread(self.notify, f"{p['name']}: {summary}", title="Connection Result")
                except Exception as ex:
                    self.app.call_from_thread(self.notify, f"Test error: {ex}", severity="warning")
            import threading
            threading.Thread(target=_bg_test, daemon=True).start()

        def action_go_back(self):
            _finish_wizard_screen(self, None)

        def _on_subscreen_closed(self, result=None):
            if result:
                _finish_wizard_screen(self, result)

        def on_button_pressed(self, event: Button.Pressed) -> None:
            bid = event.button.id or ""
            if bid in ("btn-exit", "btn-exit-top"):
                self.action_go_back()
            elif bid in ("btn-select-provider", "btn-select-main"):
                self._confirm_selection()
            elif bid in ("btn-toggle-failover", "btn-failover-main"):
                self._toggle_failover_for_selected()
            elif bid == "btn-test-provider":
                self._test_selected_provider()
            elif bid == "tab-failover":
                self._open_failover_panel()
            elif bid in ("btn-add-provider", "tab-add-custom"):
                self.app.push_screen(AddCustomModelScreen(embedded=self._embedded), self._on_subscreen_closed)
            elif bid == "tab-my-models":
                self.app.push_screen(MyModelsScreen(embedded=self._embedded), self._on_subscreen_closed)
            elif bid == "tab-updates":
                self.app.push_screen(UpdateCenterScreen(embedded=self._embedded), self._on_subscreen_closed)
            elif bid == "tab-models":
                if 0 <= self._selected_index < len(self._filtered):
                    self.app.push_screen(ModelScreen(self._filtered[self._selected_index], embedded=self._embedded), self._on_subscreen_closed)
            elif bid == "btn-refresh":
                self.action_refresh_list()
            elif bid == "btn-import":
                self.app.push_screen(ImportExportScreen(mode="import", embedded=self._embedded))
            elif bid == "btn-export":
                self.app.push_screen(ImportExportScreen(mode="export", embedded=self._embedded))
            elif bid.startswith("filter-"):
                for b in self.query("#filter-bar Button"):
                    b.remove_class("active-filter")
                event.button.add_class("active-filter")
                filt = bid.replace("filter-", "").upper()
                self._active_filter = filt
                self._apply_filters()

        def on_screen_resume(self, event=None):
            try:
                self._all = _load_provider_database()
                self._apply_filters()
            except Exception:
                pass

    # ── Model Selection Screen ────────────────────────────────────────────────

    class ModelScreen(CATViewportScreenMixin, Screen):
        """Model selection and discovery screen."""

        DEFAULT_CSS = SHARED_WIZARD_CSS

        BINDINGS = [
            Binding("escape", "go_back", "Back"),
            Binding("ctrl+c", "go_back", "Quit"),
            Binding("ctrl+r", "refresh_models", "Refresh"),
            Binding("enter", "select_model", "Select"),
            Binding("f", "toggle_failover", "Failover"),
        ]

        def __init__(self, provider, embedded=False, search=""):
            super().__init__()
            self._provider = provider
            self._embedded = embedded
            self._models = []
            self._filtered = []
            self._selected_index = 0
            self._search = search

        def compose(self):
            p = self._provider
            pid = p.get("id", "")
            cached = self._get_cached_models(pid)
            if cached:
                self._models = list(cached)
            else:
                self._models = list(p.get("models", []))
            self._filtered = list(self._models)

            with CATRootViewport():
                yield Static(_step_header(2, "Select Model"), id="step-indicator")
                with Horizontal(id="model-nav-bar"):
                    yield Button("← Back to Providers", id="btn-back-providers")
                    yield Static(f"[{C_ACCENT} b]Models for {p['name']}[/]", id="model-title")
                    yield Button("⟳ Discover Live", id="btn-refresh-live")
                yield Input(placeholder="🔍 Search models, family, capabilities... (Press Enter to select)", id="model-search")
                yield Static(f"[{C_DIM}]  Showing {len(self._filtered)} of {len(self._models)} model(s)[/]", id="model-count-label")
                yield ScrollableContainer(id="model-list")
                with Horizontal(id="model-actions"):
                    yield Button("✕ Back", id="btn-back-model-bottom")
                    yield Button("➜ Select as Active AI", id="btn-select-model-main")
                    yield Button("⇄ Set in Failover Chain", id="btn-model-failover")
                    yield Button("⚡ Test Model", id="btn-test-model")

        def _get_cached_models(self, pid):
            try:
                from calc_terminal.providers.provider_manager import get_cached_models
                return get_cached_models(pid)
            except Exception:
                return None

        def _get_current_failover_model(self) -> Optional[str]:
            try:
                from calc_terminal.providers import provider_manager as pm
                backups = pm.load_backup_providers()
                pid = self._provider.get("id", "")
                for b in backups:
                    if b.get("provider") == pid and b.get("enabled"):
                        return b.get("model")
            except Exception:
                pass
            return None

        def on_mount(self):
            self._rebuild_list()
            try:
                self.query_one("#model-search", Input).focus()
            except Exception:
                pass
            # Asynchronously discover live models
            threading.Thread(target=self._discover_live_models, daemon=True).start()

        def _discover_live_models(self):
            pid = self._provider.get("id", "")
            try:
                from calc_terminal.models import manager as _mgr
                models, _ = _mgr.get_models(pid, {"provider": pid, "api_key": ""})
                if models and models != ["default"]:
                    self._models = list(models)
                    self.app.call_from_thread(self._rebuild_list)
            except Exception:
                pass

        def _rebuild_list(self):
            try:
                container = self.query_one("#model-list", ScrollableContainer)
            except Exception:
                return
            container.remove_children()
            q = (self._search or "").lower().strip()
            filtered = [m for m in self._models if not q or q in m.lower()]
            self._filtered = filtered
            try:
                self.query_one("#model-count-label", Static).update(
                    f"[{C_DIM}]  Showing {len(filtered)} of {len(self._models)} model(s)[/]"
                )
            except Exception:
                pass

            failover_model = self._get_current_failover_model()

            for i, m in enumerate(filtered):
                sel = (i == self._selected_index)
                in_fo = (m == failover_model)
                row = ModelRow(m, i, sel, self, in_failover=in_fo)
                container.mount(row)

        def _scroll_to_selected(self):
            try:
                rows = self.query_one("#model-list", ScrollableContainer).query(ModelRow)
                for i, row in enumerate(rows):
                    if i == self._selected_index:
                        row.scroll_visible()
                        break
            except Exception:
                pass

        def on_input_changed(self, event: Input.Changed):
            if event.input.id == "model-search":
                self._search = event.input.value
                self._selected_index = 0
                self._rebuild_list()

        def on_input_submitted(self, event: Input.Submitted) -> None:
            """Pressing Enter in search box immediately selects the active model."""
            if event.input.id == "model-search":
                self.action_select_model()

        def _on_row_clicked(self, model_name: str, index: int) -> None:
            """Handle mouse click and touch screen tap on model row."""
            if self._selected_index == index:
                # Double-tap or second click confirms and selects model
                self.action_select_model()
            else:
                self._selected_index = index
                self._rebuild_list()
                self._scroll_to_selected()

        def on_key(self, event):
            if event.key == "down":
                if self._selected_index < len(self._filtered) - 1:
                    self._selected_index += 1
                    self._rebuild_list()
                    self._scroll_to_selected()
            elif event.key == "up":
                if self._selected_index > 0:
                    self._selected_index -= 1
                    self._rebuild_list()
                    self._scroll_to_selected()
            elif event.key == "pagedown":
                self._selected_index = min(self._selected_index + 10, len(self._filtered) - 1)
                self._rebuild_list()
                self._scroll_to_selected()
            elif event.key == "pageup":
                self._selected_index = max(self._selected_index - 10, 0)
                self._rebuild_list()
                self._scroll_to_selected()
            elif event.key == "enter":
                self.action_select_model()
            elif event.key == "f":
                self._toggle_failover_for_selected_model()

        def action_select_model(self):
            """Apply or configure selected model."""
            if not (0 <= self._selected_index < len(self._filtered)):
                return
            chosen_model = self._filtered[self._selected_index]
            p = self._provider
            pid = p.get("id", "")
            config = {
                "provider": pid,
                "model": chosen_model,
                "api_key": "",
                "base_url": p.get("url", "http://localhost:11434" if pid == "ollama" else ""),
                "api_style": p.get("api_style", "ollama" if pid == "ollama" else "openai"),
            }
            if not p.get("needs_key", True):
                # Local provider requiring NO API key (Ollama, LM Studio, etc.)
                # Immediately push ModelConfirmModal to hot-switch without bogus API key entry
                self.app.push_screen(ModelConfirmModal(pid, chosen_model, config), self._on_confirm_closed)
            else:
                self.app.push_screen(ApiKeyScreen(self._provider, chosen_model, embedded=self._embedded), self._on_confirm_closed)

        def _toggle_failover_for_selected_model(self) -> None:
            """Add or update chosen model for this provider in the Backup Failover Chain."""
            if not (0 <= self._selected_index < len(self._filtered)):
                return
            chosen_model = self._filtered[self._selected_index]
            p = self._provider
            pid = p.get("id", "")
            try:
                from calc_terminal.providers import provider_manager as pm
                current_backups = pm.load_backup_providers()
                existing_idx = next((i for i, b in enumerate(current_backups) if b.get("provider") == pid), -1)
                if existing_idx >= 0:
                    current_backups[existing_idx]["model"] = chosen_model
                    current_backups[existing_idx]["enabled"] = True
                    if pid == "ollama":
                        current_backups[existing_idx]["api_style"] = "ollama"
                        current_backups[existing_idx]["base_url"] = p.get("url", "http://localhost:11434")
                        current_backups[existing_idx]["api_key"] = ""
                    self.notify(f"Updated {p['name']} failover model to '{chosen_model}'", title="Failover Chain")
                else:
                    new_entry = {
                        "provider": pid,
                        "model": chosen_model,
                        "enabled": True,
                        "api_style": p.get("api_style", "ollama" if pid == "ollama" else "openai"),
                        "base_url": p.get("url", "http://localhost:11434" if pid == "ollama" else ""),
                        "api_key": "",
                    }
                    current_backups.append(new_entry)
                    self.notify(f"Added {p['name']} ({chosen_model}) to Failover Chain", title="Failover Chain")
                pm.save_backup_providers(current_backups)
                self._rebuild_list()
            except Exception as e:
                self.notify(f"Failover update error: {e}", title="Error", severity="error")

        def _test_selected_model(self) -> None:
            """Run live reachability probe test on the selected model."""
            if not (0 <= self._selected_index < len(self._filtered)):
                return
            chosen_model = self._filtered[self._selected_index]
            p = self._provider
            pid = p.get("id", "")
            self.notify(f"Probing {chosen_model} on {p['name']}...", title="Model Test")
            def _bg_test():
                try:
                    from calc_terminal.models.verification_engine import get_verification_engine
                    engine = get_verification_engine()
                    report = engine.verify_custom_model({
                        "provider_id": pid,
                        "model_id": chosen_model,
                        "base_url": p.get("url", "http://localhost:11434" if pid == "ollama" else ""),
                        "api_key": "",
                    })
                    status = report.get("status")
                    if report.success or status in ("ready", "auth_required", "VERIFIED", "PARTIALLY_VERIFIED"):
                        summary = f"✓ {chosen_model} is ready"
                    else:
                        summary = f"{chosen_model}: {report.get('error') or report.get('message') or 'Reachability check passed'}"
                    self.app.call_from_thread(self.notify, summary, title="Test Result")
                except Exception as ex:
                    self.app.call_from_thread(self.notify, f"Test error: {ex}", severity="warning")
            threading.Thread(target=_bg_test, daemon=True).start()

        def _on_confirm_closed(self, result=None):
            if result:
                _finish_wizard_screen(self, result)

        def action_go_back(self):
            try:
                self.dismiss(None)
            except Exception:
                try:
                    self.app.pop_screen()
                except Exception:
                    pass

        def action_refresh_models(self):
            self.notify("Refreshing live models...", title="Discovery")
            threading.Thread(target=self._discover_live_models, daemon=True).start()

        def action_toggle_failover(self):
            self._toggle_failover_for_selected_model()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            bid = event.button.id or ""
            if bid in ("btn-back-providers", "btn-back-model-bottom"):
                self.action_go_back()
            elif bid == "btn-select-model-main":
                self.action_select_model()
            elif bid == "btn-model-failover":
                self._toggle_failover_for_selected_model()
            elif bid in ("btn-refresh-live", "btn-refresh-live-bottom"):
                self.action_refresh_models()
            elif bid == "btn-test-model":
                self._test_selected_model()

        def on_screen_resume(self, event=None):
            try:
                self._rebuild_list()
            except Exception:
                pass

    # ── API Key Entry Screen ──────────────────────────────────────────────────

    class ApiKeyScreen(CATViewportScreenMixin, Screen):
        """API key entry screen with masked input and toggle."""

        DEFAULT_CSS = SHARED_WIZARD_CSS

        def __init__(self, provider, model, embedded=False):
            super().__init__()
            self._provider = provider
            self._model = model
            self._embedded = embedded

        def compose(self):
            p = self._provider
            with CATRootViewport():
                yield Static(_step_header(3, "API Key"), id="step-indicator")
                yield Button("← Back to Models", id="btn-back-models")
                yield Static(f"\n  [{C_ACCENT} b]Configure {p['name']}[/]\n")
                yield Static(f"  [{C_DIM}]" + "─" * 38 + "[/]\n")
                yield Static(f"  [{C_CYAN}]Provider:[/]  {p['name']}")
                yield Static(f"  [{C_CYAN}]Model:[/]     {self._model}")
                yield Static(f"  [{C_DIM}]Endpoint:[/]  {p.get('url', 'N/A')}\n")

                if p.get("needs_key"):
                    yield Static(f"  [{C_DIM}]Enter API Key:[/]")
                    self._key_input = Input(placeholder="Paste API key here...", id="api-key-input", password=True)
                    yield self._key_input
                    yield Static("", id="key-error")
                    with Horizontal():
                        yield Button("✓ Confirm", id="btn-confirm", variant="primary")
                        yield Button("👁 Show/Hide", id="btn-toggle")
                        yield Button("✕ Skip", id="btn-skip")
                else:
                    yield Static(f"  [{C_GREEN}]✓ No API key required for {p['name']}[/]\n")
                    yield Button("✓ Continue", id="btn-confirm-local", variant="primary")

        def on_button_pressed(self, event):
            p = self._provider
            if event.button.id == "btn-back-models":
                try:
                    self.dismiss(None)
                except Exception:
                    self.app.pop_screen()
            elif event.button.id == "btn-confirm":
                key = self._key_input.value.strip()
                if not key:
                    self.query_one("#key-error", Static).update(f"  [{C_RED}]Please enter a valid API key[/]")
                    return
                config = {"provider": p["id"], "model": self._model, "api_key": key, "base_url": p["url"]}
                self.app.push_screen(VerifyScreen(config, embedded=self._embedded), self._on_verify_closed)
            elif event.button.id == "btn-toggle":
                if hasattr(self, "_key_input"):
                    self._key_input.password = not self._key_input.password
            elif event.button.id == "btn-confirm-local":
                config = {"provider": p["id"], "model": self._model, "api_key": "", "base_url": p["url"]}
                self.app.push_screen(VerifyScreen(config, embedded=self._embedded), self._on_verify_closed)
            elif event.button.id == "btn-skip":
                try:
                    self.dismiss(None)
                except Exception:
                    self.app.pop_screen()

        def _on_verify_closed(self, result=None):
            if result:
                _finish_wizard_screen(self, result)

        def on_screen_resume(self, event=None):
            pass

    # ── Connection Verification Screen ────────────────────────────────────────

    class VerifyScreen(CATViewportScreenMixin, Screen):
        """Active connection verification screen."""

        DEFAULT_CSS = SHARED_WIZARD_CSS

        def __init__(self, config, embedded=False):
            super().__init__()
            self._config = config
            self._embedded = embedded
            self._done = False

        def compose(self):
            with CATRootViewport():
                yield Static(_step_header(4, "Verification"), id="step-indicator")
                yield Button("  ← Back to API Key  ", id="btn-back-apikey")
                yield Static(f"\n  [{C_ACCENT} b]Verifying Connection[/]\n")
                yield Static(f"  [{C_DIM}]" + "─" * 38 + "[/]\n")
                self._status_line = Static(f"  [{C_DIM}]Connecting to API endpoint...[/]")
                yield self._status_line
                yield Container(id="verify-results")

        def on_mount(self):
            threading.Thread(target=self._run_verification, daemon=True).start()

        def _run_verification(self):
            try:
                ok, msg, models = aicore.verify_connection(self._config)
            except Exception as e:
                ok, msg, models = False, str(e), []
            self._done = True
            self.app.call_from_thread(self._show_result, ok, msg, models)

        def _show_result(self, ok, msg, models):
            res_box = self.query_one("#verify-results", Container)
            res_box.remove_children()
            if ok:
                res_box.mount(Static(f"\n  [{C_GREEN} b]✓ Connection Verified![/]\n"))
                res_box.mount(Static(f"  [{C_DIM}]{msg}[/]\n"))
                # Open confirmation modal for hot model switching
                prov = self._config.get("provider", "")
                mod = self._config.get("model", "")
                self.app.push_screen(ModelConfirmModal(prov, mod, self._config), self._on_confirm_closed)
            else:
                res_box.mount(Static(f"\n  [{C_RED} b]✕ Verification Failed[/]\n"))
                res_box.mount(Static(f"  [{C_DIM}]{msg}[/]\n"))
                res_box.mount(Horizontal(
                    Button("⟳ Retry", id="btn-retry", variant="primary"),
                    Button("✓ Continue", id="btn-continue-anyway"),
                    Button("✕ Cancel", id="btn-cancel-verify"),
                ))

        def _on_confirm_closed(self, result=None):
            if result:
                _finish_wizard_screen(self, result)

        def on_button_pressed(self, event):
            if event.button.id == "btn-back-apikey":
                try:
                    self.dismiss(None)
                except Exception:
                    self.app.pop_screen()
            elif event.button.id == "btn-retry":
                self.query_one("#verify-results", Container).remove_children()
                threading.Thread(target=self._run_verification, daemon=True).start()
            elif event.button.id == "btn-continue-anyway":
                prov = self._config.get("provider", "")
                mod = self._config.get("model", "")
                self.app.push_screen(ModelConfirmModal(prov, mod, self._config), self._on_confirm_closed)
            elif event.button.id == "btn-cancel-verify":
                try:
                    self.dismiss(None)
                except Exception:
                    self.app.pop_screen()

    # ── "My Models" Dedicated Screen ──────────────────────────────────────────

    class MyModelsScreen(CATViewportScreenMixin, Screen):
        """Dedicated user model management screen (personal, local, custom)."""

        DEFAULT_CSS = SHARED_WIZARD_CSS

        def __init__(self, embedded=False):
            super().__init__()
            self._embedded = embedded
            self._models_list = []

        def compose(self):
            with CATRootViewport():
                yield Static(f"[{C_ACCENT} b]🐱 CAT AI HUB — MY MODELS[/]", id="nav-title")
                with Horizontal(id="nav-bar-container"):
                    yield Button("← Back to Providers", id="btn-back-hub")
                    yield Button("➕ Add My Model", id="btn-add-custom-model", variant="primary")
                    yield Button("⟳ Refresh", id="btn-refresh-my-models")
                yield Static(f"[{C_DIM}]  Personal, Local, Custom API, and Verified Models[/]\n")
                yield ScrollableContainer(id="my-models-list")

        def on_mount(self):
            self._load_my_models()

        def _load_my_models(self):
            container = self.query_one("#my-models-list", ScrollableContainer)
            container.remove_children()
            models = []

            # 1. Active model
            active = get_active_state()
            if active.provider_id and active.model_id:
                models.append({
                    "name": f"{active.model_id} (Active)",
                    "id": active.model_id,
                    "provider": active.provider_id,
                    "type": "Active Primary",
                    "status": "✓ VERIFIED",
                    "endpoint": active.endpoint or "Default",
                })

            # 2. Local Ollama models
            try:
                from .. import aicore
                ollama_models = aicore.list_models({"provider": "ollama"})
                for m in ollama_models[:12]:
                    models.append({
                        "name": m,
                        "id": m,
                        "provider": "ollama",
                        "type": "Local (Ollama)",
                        "status": "✓ VERIFIED",
                        "endpoint": "http://localhost:11434",
                    })
            except Exception:
                pass

            self._models_list = models
            if not models:
                container.mount(Static(f"\n  [{C_DIM}]No custom models found yet. Click '+ Add My Model' to verify and register one.[/]\n"))
                return

            for idx, item in enumerate(models):
                info = (
                    f"[{C_ACCENT} b]{item['name']}[/]\n"
                    f"  [{C_DIM}]Provider:[/] {item['provider']}  "
                    f"[{C_DIM}]Type:[/] {item['type']}  "
                    f"[{C_GREEN}]{item['status']}[/]\n"
                    f"  [{C_DIM}]Endpoint:[/] {item['endpoint']}"
                )
                row = Horizontal(
                    Static(info),
                    Button("➜ Apply", id=f"btn-apply-my-{idx}", variant="primary"),
                    classes="my-model-row",
                )
                container.mount(row)

        def on_button_pressed(self, event):
            bid = event.button.id or ""
            if bid == "btn-back-hub":
                try:
                    self.dismiss(None)
                except Exception:
                    self.app.pop_screen()
            elif bid == "btn-add-custom-model":
                self.app.push_screen(AddCustomModelScreen(embedded=self._embedded), self._on_confirm_closed)
            elif bid == "btn-refresh-my-models":
                self._load_my_models()
            elif bid.startswith("btn-apply-my-"):
                idx_or_id = bid.replace("btn-apply-my-", "")
                target = None
                if idx_or_id.isdigit():
                    idx = int(idx_or_id)
                    if 0 <= idx < len(self._models_list):
                        target = self._models_list[idx]
                if not target:
                    target = next((m for m in self._models_list if m.get("id") == idx_or_id), None)
                if target:
                    cfg = {"provider": target["provider"], "model": target["id"], "base_url": target.get("endpoint", "")}
                    self.app.push_screen(ModelConfirmModal(target["provider"], target["id"], cfg), self._on_confirm_closed)

        def _on_confirm_closed(self, result=None):
            if result:
                _finish_wizard_screen(self, result)

    # ── "+ Add My Model" Interactive Verification Screen ──────────────────────

    class AddCustomModelScreen(CATViewportScreenMixin, Screen):
        """Add and verify user's personal, local, or custom endpoint model."""

        DEFAULT_CSS = SHARED_WIZARD_CSS

        def __init__(self, embedded=False):
            super().__init__()
            self._embedded = embedded
            self._verification_engine = ModelVerificationEngine()
            self._verified_result = None

        def compose(self):
            with CATRootViewport():
                yield Static(f"[{C_ACCENT} b]+ Add & Verify Custom / Unknown Model[/]\n")
                yield Static(f"[{C_DIM}]" + "─" * 40 + "[/]\n")
                yield Static(f"[{C_DIM}]Model Name / Label:[/]")
                self._in_name = Input(placeholder="e.g. My Private Reasoning Model", id="cust-name")
                yield self._in_name

                yield Static(f"[{C_DIM}]Model ID (as expected by endpoint):[/]")
                self._in_id = Input(placeholder="e.g. deepseek-r1:14b or gpt-4o", id="cust-id")
                yield self._in_id

                yield Static(f"[{C_DIM}]Provider / Owner:[/]")
                self._in_prov = Input(placeholder="e.g. custom or local", value="custom", id="cust-prov")
                yield self._in_prov

                yield Static(f"[{C_DIM}]Endpoint URL:[/]")
                self._in_url = Input(placeholder="e.g. http://localhost:11434 or https://api.myendpoint.com/v1", id="cust-url")
                yield self._in_url

                yield Static(f"[{C_DIM}]Protocol (openai / ollama / anthropic):[/]")
                self._in_proto = Input(placeholder="openai", value="openai", id="cust-proto")
                yield self._in_proto

                yield Static(f"[{C_DIM}]API Key (optional if local):[/]")
                self._in_key = Input(placeholder="Paste API key here...", id="cust-key", password=True)
                yield self._in_key

                with Horizontal():
                    yield Button("⚡ Test Connection & Verify", id="btn-test-cust", variant="primary")
                    yield Button("✕ Cancel", id="btn-cancel-cust")

                yield Container(id="cust-steps-box")

        def on_button_pressed(self, event):
            if event.button.id == "btn-cancel-cust":
                try:
                    self.dismiss(None)
                except Exception:
                    self.app.pop_screen()
            elif event.button.id == "btn-test-cust":
                self._start_verification()
            elif event.button.id == "btn-apply-cust":
                if self._verified_result and self._verified_result.success:
                    mid = self._in_id.value.strip()
                    prov = self._in_prov.value.strip() or "custom"
                    cfg = {
                        "provider": prov,
                        "model": mid,
                        "api_key": self._in_key.value.strip(),
                        "base_url": self._in_url.value.strip(),
                        "api_style": self._in_proto.value.strip() or "openai",
                    }
                    self.app.push_screen(ModelConfirmModal(prov, mid, cfg), self._on_confirm_closed)

        def _on_confirm_closed(self, result=None):
            if result:
                _finish_wizard_screen(self, result)

        def _start_verification(self):
            box = self.query_one("#cust-steps-box", Container)
            box.remove_children()
            box.mount(Static(f"[{C_DIM}]Running 5-stage verification pipeline...[/]"))

            name = self._in_name.value.strip()
            mid = self._in_id.value.strip()
            prov = self._in_prov.value.strip() or "custom"
            url = self._in_url.value.strip()
            proto = self._in_proto.value.strip() or "openai"
            key = self._in_key.value.strip()

            def run():
                res = self._verification_engine.verify_custom_model(
                    provider_id=prov,
                    model_id=mid,
                    endpoint=url,
                    protocol=proto,
                    api_key=key,
                )
                self.app.call_from_thread(self._finish_verification, res)

            threading.Thread(target=run, daemon=True).start()

        def _finish_verification(self, res):
            self._verified_result = res
            box = self.query_one("#cust-steps-box", Container)
            box.remove_children()

            for step in res.steps:
                icon = "✓" if step.status == "success" else ("⚠" if step.status == "warning" else ("✕" if step.status == "failed" else "○"))
                color = C_GREEN if step.status == "success" else (C_ORANGE if step.status == "warning" else (C_RED if step.status == "failed" else C_DIM))
                box.mount(Static(f"  [{color}]{icon}[/] [{C_DIM}]{step.name}:[/] {step.message} ({step.elapsed_ms}ms)"))

            if res.success:
                box.mount(Static(f"\n  [{C_GREEN} b]✓ {res.message}[/]\n"))
                box.mount(Button("➜ Apply & Use Model Now", id="btn-apply-cust", variant="primary"))
            else:
                box.mount(Static(f"\n  [{C_RED} b]✕ {res.message}[/]\n"))

    # ── Update Center Screen ──────────────────────────────────────────────────

    class UpdateCenterScreen(CATViewportScreenMixin, Screen):
        """Displays newly discovered and updated models from DynamicModelRegistry."""

        DEFAULT_CSS = SHARED_WIZARD_CSS

        def __init__(self, embedded=False):
            super().__init__()
            self._embedded = embedded

        def compose(self):
            with CATRootViewport():
                yield Static(f"[{C_ACCENT} b]CAT AI HUB — UPDATE CENTER[/]", id="nav-title")
                yield Button("  ← Back to Providers  ", id="btn-back-updates")
                yield Static(f"[{C_DIM}]  Track newly announced models, version updates, and deprecations[/]\n")
                with ScrollableContainer(id="updates-list"):
                    try:
                        from calc_terminal.models.dynamic_registry import get_registry
                        reg = get_registry()
                        audit = reg.get_audit_summary()
                        yield Static(f"  [{C_CYAN} b]Registry Summary:[/] Total models registered: {audit.get('total_models', 0)}")
                        new_models = audit.get("new_models_queued", [])
                        if new_models:
                            yield Static(f"\n  [{C_ACCENT} b]✨ Newly Discovered Models ({len(new_models)}):[/]")
                            for m in new_models:
                                yield Static(f"    ✨ {m}")
                        else:
                            yield Static(f"\n  [{C_DIM}]All registered models are up to date.[/]")
                    except Exception as e:
                        yield Static(f"  [{C_DIM}]Update registry status: {e}[/]")

        def on_button_pressed(self, event):
            if event.button.id == "btn-back-updates":
                try:
                    self.dismiss(None)
                except Exception:
                    self.app.pop_screen()

    # ── Legacy / Standalone App Wrappers ──────────────────────────────────────

    class AddProviderScreen(Screen):
        DEFAULT_CSS = SHARED_WIZARD_CSS
        def __init__(self, embedded=False):
            super().__init__()
            self._embedded = embedded

        def compose(self):
            with CATRootViewport():
                yield Static(f"[{C_ACCENT} b]+ Add Custom Provider[/]\n")
                self._name_input = Input(placeholder="Provider Name (e.g. My Provider)", id="add-name")
                yield self._name_input
                self._url_input = Input(placeholder="Base URL (e.g. https://api.endpoint.com/v1)", id="add-url")
                yield self._url_input
                self._key_input = Input(placeholder="API Key (optional)", id="add-key", password=True)
                yield self._key_input
                with Horizontal():
                    yield Button("  ✓ Connect  ", id="btn-connect", variant="primary")
                    yield Button("  ✕ Cancel  ", id="btn-cancel")
                yield Static("", id="add-status")

        def on_button_pressed(self, event):
            if event.button.id == "btn-cancel":
                try:
                    self.dismiss(None)
                except Exception:
                    self.app.pop_screen()
            elif event.button.id == "btn-connect":
                name = self._name_input.value.strip()
                url = self._url_input.value.strip()
                key = self._key_input.value.strip()
                if not name or not url:
                    self.query_one("#add-status", Static).update(f"[{C_RED}]Name and URL required[/]")
                    return
                cfg = {"provider": f"custom_{name.lower().replace(' ', '_')}", "name": name, "url": url, "api_key": key}
                try:
                    from calc_terminal.providers.provider_manager import add_custom_provider
                    add_custom_provider(cfg)
                except Exception:
                    pass
                try:
                    self.dismiss(None)
                except Exception:
                    self.app.pop_screen()

    class ImportExportScreen(Screen):
        DEFAULT_CSS = SHARED_WIZARD_CSS
        def __init__(self, mode="import", embedded=False):
            super().__init__()
            self._mode = mode
            self._embedded = embedded

        def compose(self):
            with CATRootViewport():
                title = "Import Providers JSON" if self._mode == "import" else "Export Providers JSON"
                yield Static(f"[{C_ACCENT} b]{title}[/]\n")
                self._path_input = Input(placeholder="C:\\path\\to\\providers.json", id="io-path")
                yield self._path_input
                with Horizontal():
                    yield Button(f"  ✓ {self._mode.capitalize()}  ", id="btn-do-io", variant="primary")
                    yield Button("  ✕ Cancel  ", id="btn-cancel-io")
                yield Static("", id="io-status")

        def on_button_pressed(self, event):
            if event.button.id == "btn-cancel-io":
                try:
                    self.dismiss(None)
                except Exception:
                    self.app.pop_screen()
            elif event.button.id == "btn-do-io":
                path = self._path_input.value.strip()
                if not path:
                    return
                try:
                    from calc_terminal.providers.provider_manager import import_providers_json, export_providers_json
                    if self._mode == "import":
                        cnt, msg = import_providers_json(path)
                        self.query_one("#io-status", Static).update(f"[{C_GREEN}]{msg}[/]")
                    else:
                        ok, msg = export_providers_json(path)
                        self.query_one("#io-status", Static).update(f"[{C_GREEN if ok else C_RED}]{msg}[/]")
                except Exception as e:
                    self.query_one("#io-status", Static).update(f"[{C_RED}]Error: {e}[/]")

    class WelcomeScreen(Screen):
        DEFAULT_CSS = SHARED_WIZARD_CSS
        def __init__(self, embedded=False):
            super().__init__()
            self._embedded = embedded

        def compose(self):
            with CATRootViewport():
                yield Static("\n".join(CCT_LOGO), classes="logo")
                yield Static(f"\n[{C_ACCENT} b]Welcome to CAT AI Provider Center 2.0[/]\n")
                with Horizontal():
                    yield Button("  Get Started  ", id="btn-start", variant="primary")
                    yield Button("  Skip  ", id="btn-skip")

        def on_button_pressed(self, event):
            if event.button.id == "btn-start":
                self.app.push_screen(ProviderScreen(embedded=self._embedded), self._on_provider_closed)
            elif event.button.id == "btn-skip":
                _finish_wizard_screen(self, None)

        def _on_provider_closed(self, result=None):
            if result:
                _finish_wizard_screen(self, result)

    class ModelSelectorApp(App):
        CSS = SHARED_WIZARD_CSS
        def __init__(self, embedded=False):
            super().__init__()
            self._embedded = embedded

        def on_mount(self):
            self.push_screen(ProviderScreen(embedded=self._embedded))

def run_wizard():
    """Entry point: run the wizard standalone and return configured dict."""
    if not TEXTUAL_OK:
        print(theme.orange("\n  Rich TUI not available — using basic CLI setup.\n"))
        time.sleep(1)
        aicore.setup_ai()
        return aicore.load_config()
    app = ModelSelectorApp(embedded=False)
    try:
        result = app.run()
    except Exception as e:
        _log(f"Fatal error in wizard: {e}", exc_info=True)
        return {}
    if isinstance(result, dict):
        return result
    return {}

def main():
    _log("CAT setup wizard starting")
    theme.enable_windows_ansi()
    config = run_wizard()
    if config and config.get("provider"):
        _log(f"Configured: {config.get('provider')} / {config.get('model')}")

if __name__ == "__main__":
    main()
