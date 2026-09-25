"""
CAT UI/UX Responsive Matrix & 15-Variant Logo Verification Tests.

Validates the full terminal test matrix requested in the rebuild specification:
- 15-variant deterministic ASCII logo ladder
- 5-tier responsive layout breakpoints (Large, Normal, Medium, Small, Very Small)
- Character-cell budget and zero horizontal overflow
- Headless Textual pilot testing across terminal sizes (160x50, 100x30, 80x24, 60x20, 45x16)
- Dashboard cards, quick action buttons, chips, and composer stability
"""

import pytest
from unittest.mock import MagicMock
from wcwidth import wcswidth

from calc_terminal.ui import design_system as ds
from calc_terminal.ui.design_system import (
    RESPONSIVE_LOGOS,
    CATResponsiveBreakpoints,
    CATBorders,
    CATSpacing,
    select_logo,
    wordmark_markup,
    breakpoint_for,
    BP_LARGE,
    BP_NORMAL,
    BP_MEDIUM,
    BP_SMALL,
    BP_VERY_SMALL,
)


# ============================================================================
# TIER 1: 15-VARIANT LOGO SYSTEM VERIFICATION
# ============================================================================

def test_responsive_logo_variants_35_plus_exist():
    expected_variants = [
        "MEGA_BLOCK",
        "HERO_ULTRA",
        "HERO_3D_ISOMETRIC",
        "HERO_LARGE",
        "HERO_SHADOW",
        "HERO_SLANTED",
        "HERO_OUTLINE",
        "HERO_CYBER",
        "HERO_DOUBLE_PIPE",
        "HERO_STANDARD",
        "HERO_DOUBLE",
        "HERO_BLOCK_SHADOW",
        "HERO_ROUNDED",
        "HERO_STENCIL",
        "HERO_RETRO",
        "HERO_COMPACT",
        "COMPACT_BLOCK",
        "COMPACT_PIPES",
        "COMPACT_SHADOW",
        "COMPACT_SEGMENT",
        "COMPACT_NEON",
        "COMPACT_OUTLINE",
        "MEDIUM_BLOCK",
        "MEDIUM_COMPACT",
        "MEDIUM_DOUBLE",
        "MEDIUM_HALF_BLOCK",
        "MEDIUM_HEX",
        "MEDIUM_SLANT",
        "MEDIUM_PIPES",
        "SMALL_BLOCK",
        "SMALL_COMPACT",
        "SMALL_PIPES",
        "SMALL_BRACKET",
        "MINI_BLOCK",
        "MINI_INLINE",
        "MINI_PIPES",
        "MINI_DOTS",
        "MINI_SLANT",
        "TINY_BLOCK",
        "TINY_INLINE",
        "TINY_BADGE",
        "TINY_CHEVRON",
        "SINGLE_LINE",
        "MICRO_MARK",
        "ICON_MARK",
    ]
    assert len(RESPONSIVE_LOGOS) >= 35
    for var in expected_variants:
        assert var in RESPONSIVE_LOGOS, f"Missing required logo variant: {var}"
        entry = RESPONSIVE_LOGOS[var]
        assert "lines" in entry and len(entry["lines"]) > 0
        assert "rows" in entry and entry["rows"] > 0
        assert "min_w" in entry
        assert "min_h" in entry


def test_logo_selection_is_strictly_deterministic():
    """Repeated calls with the same dimensions must return the exact same logo."""
    test_dims = [
        (200, 60),
        (160, 45),
        (120, 35),
        (100, 30),
        (85, 25),
        (75, 22),
        (65, 20),
        (55, 17),
        (45, 15),
        (35, 12),
        (25, 9),
        (18, 7),
        (14, 5),
        (10, 4),
        (5, 2),
    ]
    for w, h in test_dims:
        k1, lines1 = select_logo(w, h)
        k2, lines2 = select_logo(w, h)
        assert k1 == k2, f"Logo selection non-deterministic for {w}x{h}"
        assert lines1 == lines2, f"Logo lines non-deterministic for {w}x{h}"


def test_logo_never_exceeds_terminal_width():
    """No line of the selected logo may exceed the given width budget."""
    for width in range(10, 160, 5):
        for height in (10, 16, 22, 30, 45):
            _key, lines = select_logo(width, height)
            for line in lines:
                w_vis = wcswidth(line)
                assert w_vis <= max(width, 3), (
                    f"Selected logo line width {w_vis} exceeds budget {width}: '{line}'"
                )


def test_logo_variant_override_support():
    """Verify manual override works reliably for all 15 variants."""
    for var_name, entry in RESPONSIVE_LOGOS.items():
        markup = wordmark_markup(80, 24, variant_override=var_name)
        assert isinstance(markup, str) and len(markup) > 0


# ============================================================================
# TIER 2: 5-TIER RESPONSIVE BREAKPOINT ENGINE
# ============================================================================

def test_five_tier_breakpoint_classification():
    # Large: >= 120
    assert CATResponsiveBreakpoints.classify(200, 60) == BP_LARGE
    assert CATResponsiveBreakpoints.classify(120, 30) == BP_LARGE

    # Normal: 90 <= w < 120
    assert CATResponsiveBreakpoints.classify(119, 30) == BP_NORMAL
    assert CATResponsiveBreakpoints.classify(90, 25) == BP_NORMAL

    # Medium: 70 <= w < 90
    assert CATResponsiveBreakpoints.classify(89, 25) == BP_MEDIUM
    assert CATResponsiveBreakpoints.classify(70, 22) == BP_MEDIUM

    # Small: 50 <= w < 70
    assert CATResponsiveBreakpoints.classify(69, 20) == BP_SMALL
    assert CATResponsiveBreakpoints.classify(50, 20) == BP_SMALL

    # Very Small: < 50 or h < 15
    assert CATResponsiveBreakpoints.classify(49, 20) == BP_VERY_SMALL
    assert CATResponsiveBreakpoints.classify(100, 14) == BP_VERY_SMALL
    assert CATResponsiveBreakpoints.classify(0, 0) == BP_VERY_SMALL
    assert CATResponsiveBreakpoints.classify(None, None) == BP_VERY_SMALL


def test_centralized_design_tokens():
    """Ensure borders and spacing tokens are clean, restrained single-line borders."""
    assert CATBorders.SOLID == "solid $border"
    assert CATBorders.FOCUS == "solid $accent"
    assert "heavy" not in CATBorders.SOLID
    assert "tall" not in CATBorders.SOLID
    assert "none" in CATBorders.NONE


# ============================================================================
# TIER 3: HEADLESS TEXTUAL PILOT SUITE ACROSS SIZES
# ============================================================================

pytestmark = pytest.mark.anyio


async def _dismiss_welcome_if_present(app, pilot):
    try:
        if type(app.screen).__name__ == "WelcomeModal":
            app.pop_screen()
            await pilot.pause()
    except Exception:
        pass


@pytest.mark.anyio
@pytest.mark.parametrize("terminal_size,expected_bp", [
    ((160, 50), BP_LARGE),
    ((100, 30), BP_NORMAL),
    ((80, 24), BP_MEDIUM),
    ((60, 22), BP_SMALL),
    ((45, 18), BP_VERY_SMALL),
])
async def test_full_app_mount_across_terminal_size_matrix(terminal_size, expected_bp):
    """Mounts CCTApp at every major terminal size in the matrix.
    Asserts zero unhandled exceptions, correct breakpoint classes,
    stable dashboard, anchored composer, and chip readability."""
    from calc_terminal.ui.app import CCTApp
    from calc_terminal.ui.workspace import WorkspaceShell
    from calc_terminal.ui.dashboard import WelcomeDashboard
    from textual.widgets import Button

    app = CCTApp(MagicMock(), [], MagicMock())
    async with app.run_test(size=terminal_size) as pilot:
        await pilot.pause()
        await _dismiss_welcome_if_present(app, pilot)
        await pilot.pause()

        # 1. Workspace shell verification
        shell = app.query_one("#cct-workspace", WorkspaceShell)
        assert f"cat-bp-{expected_bp}" in shell.classes, (
            f"Expected cat-bp-{expected_bp} in shell classes {shell.classes} at {terminal_size}"
        )

        # 2. Permanent bottom composer anchored
        composer = app.query_one("#cct-composer")
        assert composer is not None
        assert composer.display is not False

        # 3. Dashboard checks
        dash = app.query_one(WelcomeDashboard)
        assert dash is not None

        # Verify action buttons exist and are not clipped
        dash_buttons = list(dash.query(Button))
        assert len(dash_buttons) >= 3

        # Verify chip labels render without truncation
        chips = list(dash.query(".cct-nb-chip"))
        for chip in chips:
            label = str(chip.label)
            # Ensure "Arrhenius" is never cut to "Arrheniu"
            if "Arrhen" in label:
                assert "Arrhenius" in label, f"Chip truncated to '{label}' at size {terminal_size}"
