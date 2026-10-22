"""
Unit and integration tests for:
1. Dynamic temporal calculation & date range resolution (no stale/hardcoded years).
2. Web search result parsing, URL validation, and placeholder domain rejection.
3. Honest zero-result and provider failure reporting.
4. CAT Browser History integration: AI searches vs page visits, persistence, search, deletion, clearing, deduplication.
5. Multi-tab preservation and navigation tracking.
6. Agent activity reporting (accurate Live Activities status and evidence citation in research).
"""

import datetime
import json
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QApplication
_qapp = QApplication.instance()
if not _qapp:
    _qapp = QApplication([])

from calc_terminal.temporal import (
    get_temporal_context,
    resolve_temporal_query,
    get_system_prompt_temporal_block,
)
from calc_terminal.browser.browser_state import (
    BrowserState,
    HistoryEntry,
    is_placeholder_url,
)
from calc_terminal.aicore import (
    is_valid_article_url,
    web_search_detailed,
    web_search,
    fetch_web_page,
    deep_research,
)
from calc_terminal.agent import (
    TOOLS,
    _tool_web_search,
    _tool_cat_browser,
)


# ============================================================================
# Section A: Search Behavior & Dynamic Date Calculations
# ============================================================================

def test_temporal_context_dynamic_calculation():
    """Verify dynamic temporal context calculates last month and rolling 30 days without hardcoding."""
    # Test for October 11, 2026
    dt_oct_2026 = datetime.datetime(2026, 10, 11, 14, 30, 0)
    ctx = get_temporal_context(dt_oct_2026)

    assert ctx["current_year"] == 2026
    assert ctx["current_month"] == 10
    assert ctx["current_month_name"] == "October"
    assert ctx["last_month_name"] == "September"
    assert ctx["last_month_year"] == 2026
    assert ctx["last_month_range"] == ("2026-09-01", "2026-09-30")
    assert ctx["rolling_30_days_range"] == ("2026-09-11", "2026-10-11")

    # Test year rollover in January: January 2027 -> Last month should be December 2026
    dt_jan_2027 = datetime.datetime(2027, 1, 5)
    ctx_jan = get_temporal_context(dt_jan_2027)
    assert ctx_jan["current_year"] == 2027
    assert ctx_jan["last_month_name"] == "December"
    assert ctx_jan["last_month_year"] == 2026
    assert ctx_jan["last_month_range"] == ("2026-12-01", "2026-12-31")


def test_resolve_temporal_query_last_month():
    """Verify 'last month' queries resolve to the previous calendar month of the dynamic system date."""
    dt = datetime.datetime(2026, 10, 11)
    res = resolve_temporal_query("what happened in last month ai tech news ?", dt)

    assert res["temporal_type"] == "last_month"
    assert res["start_date"] == "2026-09-01"
    assert res["end_date"] == "2026-09-30"
    assert "September 2026" in res["refined_query"]
    assert "2024" not in res["refined_query"]


def test_resolve_temporal_query_rolling_30_days():
    """Verify explicit rolling 30-day request resolves to rolling window."""
    dt = datetime.datetime(2026, 10, 11)
    res = resolve_temporal_query("AI news past 30 days", dt)

    assert res["temporal_type"] == "rolling_30_days"
    assert res["start_date"] == "2026-09-11"
    assert res["end_date"] == "2026-10-11"
    assert "2026" in res["refined_query"]


def test_system_prompt_temporal_block_anchoring():
    """Verify system prompt block anchors models to current year and prevents 2024 cutoff hallucination."""
    dt = datetime.datetime(2026, 10, 11)
    block = get_system_prompt_temporal_block(dt)

    assert "October 11, 2026" in block
    assert "2026" in block
    assert "September 2026" in block
    assert "NEVER hallucinate older training-cutoff years" in block


def test_url_validation_and_placeholder_rejection():
    """Verify placeholder and invalid URLs are rejected and legitimate URLs are accepted."""
    # Placeholders must be rejected
    assert is_placeholder_url("https://example.com")
    assert is_placeholder_url("https://example.com/1")
    assert is_placeholder_url("http://example.org/test")
    assert is_placeholder_url("https://www.iana.org/help/example-domains")

    # Legitimate non-placeholder URLs must NOT be classified as placeholder
    assert not is_placeholder_url("https://www.iana.org")
    assert not is_placeholder_url("https://iana.org/protocols")
    assert not is_placeholder_url("http://localhost:3000")
    assert not is_placeholder_url("http://127.0.0.1:8080")

    # Articles validation: placeholders and loopback addresses cannot be public articles
    assert not is_valid_article_url("https://example.com/1")
    assert not is_valid_article_url("https://example.org/article")
    assert not is_valid_article_url("https://www.iana.org/help/example-domains")
    assert not is_valid_article_url("http://localhost:3000")
    assert not is_valid_article_url("http://127.0.0.1:8080")
    assert not is_valid_article_url("not_a_url")
    assert not is_valid_article_url("ftp://ftp.example.com")
    assert not is_valid_article_url("")

    # Legitimate public articles must be accepted
    assert is_valid_article_url("https://techcrunch.com/2026/09/15/ai-announcements")
    assert is_valid_article_url("https://en.wikipedia.org/wiki/Artificial_intelligence")
    assert is_valid_article_url("https://www.theverge.com/ai/article123")
    assert is_valid_article_url("https://www.iana.org/protocols")


def test_web_search_rejects_placeholder_results():
    """Verify that search parsing filters out placeholder domains even if returned by a mock provider."""
    mock_rss = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Real AI News</title>
          <link>https://techcrunch.com/2026/09/ai-update</link>
          <description>Real update on models.</description>
          <pubDate>Mon, 15 Sep 2026 12:00:00 GMT</pubDate>
          <source>TechCrunch</source>
        </item>
        <item>
          <title>Fake Example News</title>
          <link>https://example.com/1</link>
          <description>Placeholder domain example.</description>
          <pubDate>Mon, 15 Sep 2026 12:00:00 GMT</pubDate>
          <source>Example</source>
        </item>
      </channel>
    </rss>"""

    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = mock_rss
        mock_get.return_value = mock_resp

        results = web_search("AI technology news September 2026")
        assert len(results) == 1
        assert results[0]["title"] == "Real AI News"
        assert results[0]["url"] == "https://techcrunch.com/2026/09/ai-update"
        assert all("example.com" not in r["url"] for r in results)


def test_honest_zero_results_and_failure_reporting():
    """Verify that searches returning zero results or network failures are reported honestly."""
    # 1. Zero results
    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        # Google News returns empty XML
        mock_resp_g = MagicMock()
        mock_resp_g.status_code = 200
        mock_resp_g.content = b"<rss><channel></channel></rss>"
        mock_get.return_value = mock_resp_g

        # DDG returns empty HTML
        mock_resp_ddg = MagicMock()
        mock_resp_ddg.status_code = 200
        mock_resp_ddg.text = "<html><body>No results</body></html>"
        mock_post.return_value = mock_resp_ddg

        res = web_search_detailed("unheard_query_xyz_9999")
        assert res["ok"] is True
        assert res["status"] == "zero_results"
        assert res["results"] == []

    # 2. Rate limit / bot block failure
    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        mock_get.side_effect = Exception("Connection timed out")
        mock_resp_ddg = MagicMock()
        mock_resp_ddg.status_code = 202  # Bot challenge
        mock_post.return_value = mock_resp_ddg

        res = web_search_detailed("ai news query")
        assert res["status"] in ("rate_limited", "failed")
        assert res["results"] == []


# ============================================================================
# Section B & C: CAT Browser History Integration & Multi-Tab Isolation
# ============================================================================

def test_browser_history_ai_search_recording(tmp_path):
    """Verify AI web searches record structured entries in BrowserState history."""
    h_file = tmp_path / "test_hist.json"
    t_file = tmp_path / "test_tabs.json"
    state = BrowserState(tabs_file=t_file, history_file=h_file)

    entry = state.add_ai_search(
        query="AI tech news September 2026",
        provider="Google News",
        search_url="https://news.google.com/search?q=AI",
        result_count=5,
        destination_urls=["https://techcrunch.com/article1", "https://theverge.com/article2"],
        status="success",
        tab_id="tab-123",
    )

    assert entry.entry_type == "ai_search"
    assert entry.query == "AI tech news September 2026"
    assert entry.provider == "Google News"
    assert entry.result_count == 5
    assert len(entry.destination_urls) == 2
    assert entry.tab_id == "tab-123"

    # Persistence verification
    assert h_file.exists()
    reloaded_state = BrowserState(tabs_file=t_file, history_file=h_file)
    assert len(reloaded_state.history) == 1
    loaded_entry = reloaded_state.history[0]
    assert loaded_entry.entry_type == "ai_search"
    assert loaded_entry.query == "AI tech news September 2026"
    assert loaded_entry.provider == "Google News"


def test_browser_history_visit_recording_and_deduplication(tmp_path):
    """Verify visited pages are recorded, distinguished from AI search, and deduplicated against rapid rerenders."""
    h_file = tmp_path / "test_hist.json"
    t_file = tmp_path / "test_tabs.json"
    state = BrowserState(tabs_file=t_file, history_file=h_file)

    # Initial visit
    v1 = state.add_visit("https://techcrunch.com/article1", title="Initial Title", tab_id="tab-1")
    assert v1 is not None
    assert v1.entry_type == "visit"
    assert len(state.history) == 1

    # Second event on same URL within 20s (e.g. title updated or component rerendered)
    v2 = state.add_visit("https://techcrunch.com/article1", title="Final Loaded Title", tab_id="tab-1")
    assert len(state.history) == 1  # Deduplicated!
    assert state.history[0].title == "Final Loaded Title"

    # Visit to a different URL
    v3 = state.add_visit("https://theverge.com/article2", title="The Verge", tab_id="tab-1")
    assert len(state.history) == 2


def test_browser_history_search_and_deletion(tmp_path):
    """Verify history search, individual deletion, and clear history."""
    h_file = tmp_path / "test_hist.json"
    t_file = tmp_path / "test_tabs.json"
    state = BrowserState(tabs_file=t_file, history_file=h_file)

    e1 = state.add_ai_search("Quantum Computing 2026", provider="Wikipedia", result_count=3)
    e2 = state.add_visit("https://techcrunch.com/quantum", title="Quantum Tech Breakthrough")

    # Search
    matches = state.search_history("quantum")
    assert len(matches) == 2

    matches_wiki = state.search_history("Wikipedia")
    assert len(matches_wiki) == 1

    # Delete individual entry
    deleted = state.remove_history_entry(e1.id)
    assert deleted is True
    assert len(state.history) == 1
    assert state.history[0].id == e2.id

    # Clear history
    state.clear_history()
    assert len(state.history) == 0


def test_browser_state_sanitizes_placeholder_test_tabs(tmp_path):
    """Verify that poisoned tabs.json containing dummy example.com tabs are sanitized on restore."""
    t_file = tmp_path / "tabs.json"
    h_file = tmp_path / "hist.json"
    poisoned_data = {
        "active_tab_id": "tab-1",
        "tab_position": "top",
        "sidebar_width": 240,
        "tabs": [
            {"id": "tab-1", "title": "Example Domain", "url": "https://example.com/1"},
            {"id": "tab-2", "title": "Real Page", "url": "https://en.wikipedia.org/wiki/Main_Page"},
            {"id": "tab-3", "title": "Example Domains", "url": "https://www.iana.org/help/example-domains"},
        ]
    }
    t_file.write_text(json.dumps(poisoned_data), encoding="utf-8")

    state = BrowserState(tabs_file=t_file, history_file=h_file)
    # The example.com and iana.org placeholder tabs must be sanitized away
    assert len(state.tabs) == 1
    assert state.tabs[0].url == "https://en.wikipedia.org/wiki/Main_Page"


# ============================================================================
# Section D: Agent Activity & Tool Reporting
# ============================================================================

def test_cat_browser_tool_registered_in_tools():
    """Verify cat_browser is registered in TOOLS and supports authorized navigation."""
    assert "cat_browser" in TOOLS
    cat_tool = TOOLS["cat_browser"]
    assert callable(cat_tool["run"])
    assert "agentic mode" in cat_tool["desc"].lower()

    # Authorized local development navigation must be permitted
    with patch("calc_terminal.device_control.BrowserProvider.execute") as mock_exec:
        mock_exec.return_value = {"ok": True, "note": "Opened localhost"}
        res = _tool_cat_browser({"action": "new_tab", "url": "http://localhost:3000"})
        assert "opened" in res.lower() or "succeeded" in res.lower()

    # Standard web navigation must be permitted
    with patch("calc_terminal.device_control.BrowserProvider.execute") as mock_exec:
        mock_exec.return_value = {"ok": True, "note": "Navigated to IANA"}
        res = _tool_cat_browser({"action": "open", "url": "https://www.iana.org"})
        assert "navigated" in res.lower() or "succeeded" in res.lower()


def test_search_results_rich_metadata_persistence_and_search(tmp_path):
    """Verify that search result articles, titles, sources, and dates are persisted in history
    and can be queried directly via search_history."""
    h_file = tmp_path / "rich_hist.json"
    t_file = tmp_path / "rich_tabs.json"
    state = BrowserState(tabs_file=t_file, history_file=h_file)

    articles = [
        {
            "title": "Anthropic Claude 4.5 Reasoning Breakthrough",
            "url": "https://news.google.com/articles/123",
            "snippet": "New frontier benchmark analysis.",
            "source": "TechCrunch",
            "date": "Wed, 16 Sep 2026 10:00:00 GMT",
        },
        {
            "title": "DeepMind AlphaGeometry 2 Insights",
            "url": "https://news.google.com/articles/456",
            "snippet": "Mathematical olympiad breakthroughs.",
            "source": "Nature",
            "date": "Thu, 17 Sep 2026 14:00:00 GMT",
        }
    ]

    entry = state.add_ai_search(
        query="AI reasoning September 2026",
        provider="Google News",
        search_url="https://news.google.com/search?q=AI",
        result_count=2,
        destination_urls=[a["url"] for a in articles],
        status="success",
        tab_id="tab-456",
        search_results=articles,
    )

    assert len(entry.search_results) == 2
    assert entry.search_results[0]["source"] == "TechCrunch"
    assert entry.search_results[1]["source"] == "Nature"

    # Verify search_history can discover the entry by article title or publisher source
    matched_title = state.search_history("AlphaGeometry")
    assert len(matched_title) == 1
    assert matched_title[0].id == entry.id

    matched_src = state.search_history("TechCrunch")
    assert len(matched_src) == 1
    assert matched_src[0].id == entry.id

    # Verify disk reload preserves search_results
    reloaded = BrowserState(tabs_file=t_file, history_file=h_file)
    assert len(reloaded.history) == 1
    rel_entry = reloaded.history[0]
    assert len(rel_entry.search_results) == 2
    assert rel_entry.search_results[0]["title"] == "Anthropic Claude 4.5 Reasoning Breakthrough"


def test_calendar_month_vs_rolling_30_days_differentiation():
    """Verify that 'last month' and 'last 30 days' resolve to distinct date ranges."""
    dt = datetime.datetime(2026, 10, 11)

    # 1. Calendar month: Sept 1 to Sept 30, 2026
    res_cal = resolve_temporal_query("ai tech news last month", dt)
    assert res_cal["temporal_type"] == "last_month"
    assert res_cal["start_date"] == "2026-09-01"
    assert res_cal["end_date"] == "2026-09-30"
    assert "September 2026" in res_cal["refined_query"]

    # 2. Rolling 30 days: Sept 11 to Oct 11, 2026
    res_roll = resolve_temporal_query("ai tech news past 30 days", dt)
    assert res_roll["temporal_type"] == "rolling_30_days"
    assert res_roll["start_date"] == "2026-09-11"
    assert res_roll["end_date"] == "2026-10-11"

    # Strict differentiation: calendar month != rolling window
    assert res_cal["start_date"] != res_roll["start_date"]
    assert res_cal["end_date"] != res_roll["end_date"]


def test_background_tab_isolation_in_qt_browser(tmp_path):
    """Verify that title and URL changes in background tabs do not mutate active tab state."""
    from calc_terminal.browser_gui.qt_browser import CATBrowserWindow
    from PySide6.QtCore import QUrl

    t_file = tmp_path / "tabs.json"
    h_file = tmp_path / "hist.json"
    state = BrowserState(tabs_file=t_file, history_file=h_file)

    win = CATBrowserWindow(state=state)
    win.agent_new_tab("https://active-page.org")
    win.agent_new_tab("https://background-page.org")
    win.agent_switch_tab(0)

    # Tab 0 is active, Tab 1 is in background
    assert win.tab_bar.currentIndex() == 0

    # Simulate background tab title change
    bg_view = win._views[1]
    win._on_title_changed(bg_view, "Background Page Updated Title")

    # Active tab title and window title must NOT be modified by background tab
    assert win.state.tabs[1].title == "Background Page Updated Title"
    assert win.state.tabs[0].url != "https://background-page.org"
    assert "Background Page" not in win.windowTitle()


def test_live_google_news_provider_real_execution():
    """Real live integration test against Google News RSS provider (distinguished from mocks).
    Validates live HTTP response, parsing, titles, dates, source names, and URLs."""
    import requests
    headers = {"User-Agent": "Mozilla/5.0 CAT-CLI/0.7.9"}
    try:
        r = requests.get(
            "https://news.google.com/rss/search?q=AI+technology+news+September+2026&hl=en-US&gl=US&ceid=US:en",
            headers=headers, timeout=6
        )
        if r.status_code != 200:
            pytest.skip(f"Live Google News RSS returned HTTP {r.status_code}")
    except Exception as e:
        pytest.skip(f"Live network unavailable: {e}")

    # Perform real live search
    res = web_search_detailed("AI technology news September 2026", max_results=3)
    assert res["ok"] is True
    assert res["provider"] == "Google News"
    assert res["result_count"] > 0
    assert len(res["results"]) > 0

    first = res["results"][0]
    assert first["title"] != ""
    assert first["url"].startswith("https://")
    assert first["source"] != ""
    assert first["date"] != ""


def test_agent_tool_web_search_honest_reporting():
    """Verify _tool_web_search distinguishes success, zero-results, and failures."""
    # 1. Success with real results
    with patch("calc_terminal.aicore.web_search_detailed") as mock_det:
        mock_det.return_value = {
            "ok": True,
            "query": "ai news September 2026",
            "provider": "Google News",
            "results": [
                {"title": "Meta Llama Release", "url": "https://techcrunch.com/llama", "snippet": "New model preview."}
            ],
            "result_count": 1,
            "search_url": "https://news.google.com/search?q=ai",
            "status": "success",
            "error_message": "",
        }
        res = _tool_web_search({"query": "what happened last month in ai?"})
        assert "Web search results (Google News):" in res
        assert "Meta Llama Release" in res

    # 2. Honest zero results
    with patch("calc_terminal.aicore.web_search_detailed") as mock_det:
        mock_det.return_value = {
            "ok": True,
            "query": "unmatched query",
            "provider": "Google News",
            "results": [],
            "result_count": 0,
            "search_url": "",
            "status": "zero_results",
            "error_message": "",
        }
        res = _tool_web_search({"query": "unmatched query"})
        assert "found 0 results" in res

    # 3. Honest failure
    with patch("calc_terminal.aicore.web_search_detailed") as mock_det:
        mock_det.return_value = {
            "ok": False,
            "query": "blocked query",
            "provider": "DuckDuckGo",
            "results": [],
            "result_count": 0,
            "search_url": "",
            "status": "rate_limited",
            "error_message": "HTTP 429 Too Many Requests",
        }
        res = _tool_web_search({"query": "blocked query"})
        assert "Web search failed" in res
        assert "rate_limited" in res


def test_deep_research_honest_zero_source_handling():
    """Verify deep_research does NOT synthesize a fake report when 0 sources are retrieved."""
    with patch("calc_terminal.aicore.web_search") as mock_search, patch("calc_terminal.aicore.load_config") as mock_cfg:
        mock_cfg.return_value = {"provider": "mock"}
        mock_search.return_value = []  # 0 results found for all angles

        summary, sources = deep_research("obscure topic xyz")
        assert len(sources) == 0
        assert "0 verified web sources found" in summary
        assert "Cannot synthesize unverified claims without evidence" in summary
