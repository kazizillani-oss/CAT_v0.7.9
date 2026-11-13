# scratch/patch_test_composer.py
with open('calc_terminal/tests/test_composer_3d_and_dialog_fixes.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update test_composer_3d_skeuomorphic_block_geometry
old_part1 = '''        # 2. Recessed typing deck: Sunken well with #12131d background and min-height >= 2
        deck = app.query_one("#cct-prompt-row")
        assert deck is not None
        assert deck.styles.background.hex.lower() == "#12131d"
        assert deck.styles.min_height.value >= 2.0

        # 3. Prompt glyph: amber gold bold indicator
        glyph = app.query_one("#cct-prompt-glyph")
        assert glyph.styles.color.hex.lower() in ("#e0af68", "#f7d794")

        # 4. Integrated control strip: distinct bottom row
        footer = app.query_one("#cct-bottom-row")
        assert footer is not None
        assert footer.styles.border_top[0] == "solid"

        # 5. Send button: prominent 3D mechanical keycap with tall bevel and amber face
        send_btn = app.query_one("#btn-send", Button)
        assert send_btn.styles.border_top[0] == "tall"
        assert send_btn.styles.border_left[0] == "tall"
        assert send_btn.styles.background.hex.lower() == "#e0af68"

        # 6. Attachment button: 3D tactile block button
        attach_btn = app.query_one("#btn-attach", Button)
        assert attach_btn.styles.border_top[0] == "tall"'''

new_part1 = '''        # 2. Prompt row: Single border design — no duplicate inner border, transparent well
        deck = app.query_one("#cct-prompt-row")
        assert deck is not None
        assert deck.styles.border_top[0] in ("", "none")
        assert deck.styles.border_left[0] in ("", "none")

        # 3. Prompt glyph: amber gold bold indicator
        glyph = app.query_one("#cct-prompt-glyph")
        assert glyph.styles.color.hex.lower() in ("#e0af68", "#f7d794")

        # 4. Integrated control strip: distinct bottom row with single border-top divider
        footer = app.query_one("#cct-bottom-row")
        assert footer is not None
        assert footer.styles.border_top[0] == "solid"

        # 5. Send button: clean 1-row tactile keycap with amber face (no buggy wireframe clipping)
        send_btn = app.query_one("#btn-send", Button)
        assert send_btn.styles.border_top[0] in ("", "none")
        assert send_btn.styles.height.value == 1.0
        assert send_btn.styles.background.hex.lower() == "#e0af68"

        # 6. Attachment & permissions buttons: clean 1-row tactile buttons
        attach_btn = app.query_one("#btn-attach", Button)
        perm_btn = app.query_one("#btn-permissions", Button)
        assert attach_btn.styles.border_top[0] in ("", "none")
        assert attach_btn.styles.height.value == 1.0
        assert perm_btn.styles.height.value == 1.0'''

text = text.replace(old_part1, new_part1)

# 2. Update test_composer_footer_controls_always_visible_at_narrow_and_explicit_height
old_part2 = '''    assert COMPOSER_MIN_HEIGHT >= 8

    # Test on a narrow compact terminal (48 cols, matching portrait / floating screenshot)
    app = ComposerApp()
    async with app.run_test(size=(48, 25)) as pilot:
        composer = app.query_one("#cct-composer", StickyComposer)
        composer.set_model_label("ollama/deepseek-r1:latest")
        await pilot.pause(0.05)

        # 1. Base min_height >= COMPOSER_MIN_HEIGHT
        assert composer.styles.min_height.value >= COMPOSER_MIN_HEIGHT

        # 2. Footer row must be visible and have height == 3
        footer = app.query_one("#cct-bottom-row", ComposerFooter)
        assert footer.display is True
        assert footer.styles.height.value == 3.0

        # 3. Model name badge must be visible even at narrow 48 cols
        model_badge = app.query_one("#badge-model")
        assert model_badge.display is True

        # 4. AI agent mode badge must be visible
        agent_badge = app.query_one("#badge-notebook")
        assert agent_badge.display is True

        # 5. Permission button, attach button, and send button must be mounted & visible
        perm_btn = app.query_one("#btn-permissions", Button)
        attach_btn = app.query_one("#btn-attach", Button)
        send_btn = app.query_one("#btn-send", Button)

        assert perm_btn.display is True
        assert attach_btn.display is True
        assert send_btn.display is True

        # 6. Test explicit height clamping: setting lower than COMPOSER_MIN_HEIGHT resets to auto with min_height
        composer.set_explicit_height(5)
        assert composer.styles.height.is_auto
        assert composer.styles.min_height.value >= COMPOSER_MIN_HEIGHT'''

new_part2 = '''    assert COMPOSER_MIN_HEIGHT >= 5

    # Test on narrow compact terminals (48 cols & 38 cols, matching portrait & floating screenshots)
    for width in (48, 38):
        app = ComposerApp()
        async with app.run_test(size=(width, 25)) as pilot:
            composer = app.query_one("#cct-composer", StickyComposer)
            composer.set_model_label("ollama/deepseek-r1:latest")
            await pilot.pause(0.05)

            # 1. Base min_height >= COMPOSER_MIN_HEIGHT
            assert composer.styles.min_height.value >= COMPOSER_MIN_HEIGHT

            # 2. Footer row must be visible and have height == 1
            footer = app.query_one("#cct-bottom-row", ComposerFooter)
            assert footer.display is True
            assert footer.styles.height.value == 1.0

            # 3. Model name badge must be visible even at narrow cols
            model_badge = app.query_one("#badge-model")
            assert model_badge.display is True

            # 4. AI agent mode badge must be visible
            agent_badge = app.query_one("#badge-notebook")
            assert agent_badge.display is True

            # 5. Permission button, attach button, and enter/stop send button must be mounted & visible
            perm_btn = app.query_one("#btn-permissions", Button)
            attach_btn = app.query_one("#btn-attach", Button)
            send_btn = app.query_one("#btn-send", Button)

            assert perm_btn.display is True
            assert attach_btn.display is True
            assert send_btn.display is True

            # 6. Test explicit height clamping: setting lower than COMPOSER_MIN_HEIGHT resets to auto with min_height
            composer.set_explicit_height(3)
            assert composer.styles.height.is_auto
            assert composer.styles.min_height.value >= COMPOSER_MIN_HEIGHT'''

text = text.replace(old_part2, new_part2)

with open('calc_terminal/tests/test_composer_3d_and_dialog_fixes.py', 'w', encoding='utf-8', newline='') as f:
    f.write(text)
print('Updated test_composer_3d_and_dialog_fixes.py')

