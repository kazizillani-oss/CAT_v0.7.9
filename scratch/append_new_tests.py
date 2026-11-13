import sys

new_tests = '''

@pytest.mark.anyio
async def test_all_ai_modes_3d_skeuomorphic_bevels():
    """Verify all 6 AI mode chassis have authentic 3D skeuomorphic beveling (light top/left, dark bottom/right)."""
    app = ComposerApp()
    async with app.run_test(size=(90, 30)) as pilot:
        composer = app.query_one("#cct-composer", StickyComposer)
        await pilot.pause(0.05)

        modes = [
            ("cct-mode-build", "#f7d794", "#e0af68", "#5c3d14", "#8c5d20"),
            ("cct-mode-notebook", "#a5c3ff", "#7aa2f7", "#1e2850", "#344882"),
            ("cct-mode-research", "#ff94cc", "#ff69b4", "#4d1030", "#7a1c4e"),
            ("cct-mode-plan", "#bfe88e", "#9ece6a", "#233b12", "#416124"),
            ("cct-mode-debugger", "#ff5978", "#dc143c", "#450612", "#6e0d20"),
            ("cct-mode-agent", "#d8c2ff", "#bb9af7", "#302054", "#543b8a"),
        ]

        for cls, top_col, left_col, bot_col, right_col in modes:
            for c, _, _, _, _ in modes:
                composer.remove_class(c)
            composer.add_class(cls)
            await pilot.pause(0.02)

            assert composer.styles.border_top[0] == "heavy"
            assert composer.styles.border_top[1].hex.lower() == top_col.lower()
            assert composer.styles.border_left[1].hex.lower() == left_col.lower()
            assert composer.styles.border_bottom[1].hex.lower() == bot_col.lower()
            assert composer.styles.border_right[1].hex.lower() == right_col.lower()


@pytest.mark.anyio
async def test_menu_button_square_shape_and_dialog_3d_bevels():
    """Verify MenuButton has 1:1 physical square shape (width 7, height 3) and dialogs have 3D bevels."""
    app = PortraitHeaderApp()
    async with app.run_test(size=(100, 30)) as pilot:
        hdr = app.query_one(BrandHeader)
        await pilot.pause(0.05)

        menu_btn = hdr.query_one(".cct-menu-btn")
        assert menu_btn is not None
        assert menu_btn.styles.width.value == 7.0
        assert menu_btn.styles.height.value == 3.0
        assert menu_btn.styles.border_top[0] == "heavy"

    from calc_terminal.ui.header import NavPanel, PermissionModeMenu
    assert "border: heavy;" in NavPanel.CSS
    assert "border-top: heavy #8b92b2;" in NavPanel.CSS
    assert "border: heavy;" in PermissionModeMenu.CSS
    assert "border-top: heavy #8b92b2;" in PermissionModeMenu.CSS
    assert "border: round" not in PermissionModeMenu.CSS


@pytest.mark.anyio
async def test_cmdpalette_no_highlight_tint_and_no_bottom_overflow():
    """Verify Command Palette has no background tint, has square 3D borders, and footer never overflows past composer border."""
    app = ComposerApp()
    async with app.run_test(size=(90, 30)) as pilot:
        composer = app.query_one("#cct-composer", StickyComposer)
        palette = composer.palette
        await pilot.pause(0.05)

        # Open palette
        palette.open_for_query("/")
        await pilot.pause(0.05)

        # 1. Palette styling: no accent tint, dark background, square border
        assert palette.styles.tint.a == 0.0 or palette.styles.tint.hex.lower() == "#000000"
        assert palette.styles.border_top[0] == "solid"
        assert palette.styles.border_top[0] != "round"

        # 2. Composer overflow is hidden
        assert composer.styles.overflow_x == "hidden"
        assert composer.styles.overflow_y == "hidden"

        # 3. Footer row is contained inside composer
        footer = app.query_one("#cct-bottom-row")
        c_region = composer.region
        f_region = footer.region
        # Footer bottom must not exceed composer bottom
        assert f_region.y + f_region.height <= c_region.y + c_region.height
'''

with open('calc_terminal/tests/test_composer_3d_and_dialog_fixes.py', 'r', encoding='utf-8') as f:
    text = f.read()

if 'test_all_ai_modes_3d_skeuomorphic_bevels' not in text:
    text += new_tests
    with open('calc_terminal/tests/test_composer_3d_and_dialog_fixes.py', 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    print('Appended new tests!')
else:
    print('Tests already present')

