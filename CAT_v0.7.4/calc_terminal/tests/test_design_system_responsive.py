"""CAT responsive skeuomorphic UI + stability overhaul — regression tests.

Pure-function tier (no Textual app needed):
  breakpoint_for / pick_wordmark / full_wordmark / error_card /
  RelayoutDebouncer (fake widget) / stop_timer.

Pilot tier (headless Textual, @pytest.mark.anyio like the existing
UI suites): CATButton press flash, CATWordmark variant switching,
and full-CCTApp mount smoke across terminal sizes (large/medium/
small/tiny) asserting the workspace lands in the right responsive
tier with no exception — the resize-stability contract.
"""

import pytest

from calc_terminal.ui import design_system as ds


# ---------------------------------------------------------- pure tier --

def test_breakpoint_tiers():
    assert ds.breakpoint_for(200, 70) == "large"
    assert ds.breakpoint_for(140, 50) == "large"
    assert ds.breakpoint_for(120, 40) == "large"
    assert ds.breakpoint_for(119, 40) == "medium"
    assert ds.breakpoint_for(100, 30) == "medium"
    assert ds.breakpoint_for(80, 24) == "medium"
    assert ds.breakpoint_for(79, 24) == "small"
    assert ds.breakpoint_for(68, 24) == "small"
    assert ds.breakpoint_for(56, 24) == "small"
    assert ds.breakpoint_for(55, 24) == "tiny"
    assert ds.breakpoint_for(80, 17) == "tiny"   # short counts as tiny
    assert ds.breakpoint_for(0, 0) == "tiny"


def test_breakpoint_never_raises_on_garbage():
    for bad in (None, "", "wide", -5, 3.5):
        assert ds.breakpoint_for(bad, 24) in (
            "large", "medium", "small", "tiny")
    assert ds.breakpoint_for(100, "tall") in (
        "large", "medium", "small", "tiny")


def test_pick_wordmark_variants_and_budgets():
    variant, lines = ds.pick_wordmark(200)
    assert variant == "full" and len(lines) == 6
    variant, lines = ds.pick_wordmark(34)
    assert variant == "full"
    variant, lines = ds.pick_wordmark(33)
    assert variant == "compact" and len(lines) == 3
    variant, lines = ds.pick_wordmark(22)
    assert variant == "compact"
    variant, lines = ds.pick_wordmark(21)
    assert variant == "minimal" and lines == ["CAT"]
    variant, lines = ds.pick_wordmark(0)
    assert variant == "minimal"


def test_wordmark_never_overflows_its_budget():
    # Every variant's widest visual line must fit the tier that
    # selects it (wcwidth-aware: block glyphs are double-width).
    from wcwidth import wcswidth

    def visual(line):
        return wcswidth(line)

    for width in (200, 120, 80, 34, 33, 25, 22, 21, 10, 0):
        _variant, lines = ds.pick_wordmark(width)
        widest = max(visual(line) for line in lines)
        assert widest <= max(width, 3), (width, lines)


def test_full_wordmark_matches_app_logo():
    from calc_terminal.app import LOGO
    assert ds.full_wordmark() == [line.rstrip() for line in LOGO]
    # Callers get copies — mutating the result must not poison source.
    ds.full_wordmark().append("junk")
    assert ds.full_wordmark() == [line.rstrip() for line in LOGO]


def test_error_card_contract():
    card = ds.error_card("Provider unavailable",
                         ["Backup provider is being used."])
    assert "Provider unavailable" in card
    assert "Backup provider is being used." in card
    assert "CAT" in card
    # Never raises, even on garbage.
    assert isinstance(ds.error_card(None, None, width="x"), str)
    assert isinstance(ds.error_card("t", "x" * 200, width=30), str)


def test_wordmark_markup_never_raises():
    assert isinstance(ds.wordmark_markup(200), str)
    assert isinstance(ds.wordmark_markup(10), str)
    assert "CAT" in ds.wordmark_markup(10)


class _FakeTimer:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


class _FakeWidget:
    def __init__(self):
        self.calls = 0
        self.timers = []

    def set_timer(self, delay, callback):
        timer = _FakeTimer()
        self.timers.append((delay, callback, timer))
        return timer


def test_stop_timer_helper():
    assert ds.stop_timer(None) is False
    assert ds.stop_timer(_FakeTimer()) is True
    assert ds.stop_timer(object()) is False  # no .stop() -> False


def test_relayout_debouncer_leading_and_trailing():
    widget = _FakeWidget()
    deb = ds.RelayoutDebouncer(delay=0.06)
    calls = []
    deb.request(widget, lambda: calls.append(1))
    assert calls == [1]  # leading edge: immediate
    deb.request(widget, lambda: calls.append(2))
    deb.request(widget, lambda: calls.append(3))
    assert calls == [1]  # burst coalesced, nothing extra yet
    # Fire the trailing timer: exactly one catch-up layout.
    _delay, callback, _timer = widget.timers[-1]
    callback()
    assert calls == [1, 3]
    deb.cancel()


def test_relayout_debouncer_survives_callback_errors():
    widget = _FakeWidget()
    deb = ds.RelayoutDebouncer(delay=0.06)

    def boom():
        raise RuntimeError("layout blew up")

    deb.request(widget, boom)  # must not propagate
    deb.cancel()


# --------------------------------------------------------- pilot tier --

pytestmark = pytest.mark.anyio


async def _dismiss_welcome_if_present(app, pilot):
    try:
        if type(app.screen).__name__ == "WelcomeModal":
            app.pop_screen()
            await pilot.pause()
    except Exception:
        pass


@pytest.mark.anyio
async def test_cat_button_press_flash_lifecycle():
    from textual.app import App
    from calc_terminal.ui.design_system import CATButton

    class BtnApp(App):
        def compose(self):
            yield CATButton("Press me", id="flash-btn")

    app = BtnApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        btn = app.query_one("#flash-btn", CATButton)
        assert "cat-btn" in btn.classes
        btn.press()
        await pilot.pause()
        assert "cat-pressed" in btn.classes
        await pilot.pause(0.3)
        assert "cat-pressed" not in btn.classes


@pytest.mark.anyio
async def test_cat_wordmark_switches_variant_by_width():
    from textual.app import App
    from calc_terminal.ui.design_system import CATWordmark

    class MarkApp(App):
        def compose(self):
            yield CATWordmark(id="mark")

    app = MarkApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        mark = app.query_one("#mark", CATWordmark)
        assert mark.refresh_for_width(200) == "full"
        assert mark.variant == "full"
        assert mark.refresh_for_width(30) == "compact"
        assert mark.variant == "compact"
        assert mark.refresh_for_width(10) == "minimal"
        assert mark.variant == "minimal"
        # Idempotent: same width repaints nothing (no exception, same variant).
        assert mark.refresh_for_width(10) == "minimal"


@pytest.mark.anyio
@pytest.mark.parametrize("size,expected_bp", [
    ((200, 70), "large"),
    ((160, 60), "large"),
    ((140, 50), "large"),
    ((120, 40), "large"),
    ((100, 30), "medium"),
    ((80, 24), "medium"),
    ((60, 24), "small"),
    ((50, 20), "tiny"),
])
async def test_workspace_responsive_tiers_no_crash(size, expected_bp):
    """Full-app mount smoke at five terminal sizes: the workspace
    must land in the expected responsive tier without exceptions,
    with exactly one of chat/right visible in tiny mode (no overlap)
    and the chat column always on (chat-first fallback)."""
    from unittest.mock import MagicMock
    from calc_terminal.ui.app import CCTApp
    from calc_terminal.ui.workspace import WorkspaceShell

    app = CCTApp(MagicMock(), [], MagicMock())
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        await _dismiss_welcome_if_present(app, pilot)
        await pilot.pause()
        shell = app.query_one("#cct-workspace", WorkspaceShell)
        assert f"cat-bp-{expected_bp}" in shell.classes
        chat_col = app.query_one("#cct-chat-col")
        assert chat_col.display is True
        if expected_bp == "tiny":
            right = app.query_one("#cct-right-pane")
            assert right.display is False
            switcher = app.query_one("#cct-workspace-switcher")
            assert switcher.display is False
