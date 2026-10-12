from pathlib import Path
import re
import asyncio


WEB = Path(__file__).parent.parent / "web" / "static"


def test_shell_uses_rail_navigation_and_removes_workspace_header():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert '<header id="cct-header">' not in html
    assert "cct-brand-rail" in html
    assert "cct-sidebar-collapse" in html
    assert 'id="cct-auth-pill"' in html


def test_welcome_has_fatty_cat_hero_and_unique_mount_points():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', html)
    assert len(ids) == len(set(ids))
    assert 'id="cct-welcome-mascot-container"' in html
    assert "Welcome to Fatty Cat" in html
    assert "window.fattyMascots" in html


def test_appearance_and_sidebar_preferences_are_explicit_and_persistent():
    js = (WEB / "js" / "app.js").read_text(encoding="utf-8")
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert all(f'data-appearance-choice="{mode}"' in html for mode in ("system", "light", "dark"))
    assert "prefers-color-scheme: light" in js
    assert "fatty-appearance" in js
    assert "fatty-sidebar-collapsed" in js
    assert "classList.toggle('sidebar-collapsed'" in js


def test_mobile_drawer_and_reduced_motion_rules_exist():
    css = (WEB / "css" / "app.css").read_text(encoding="utf-8")
    assert "@media (max-width: 760px)" in css
    assert "body.mobile-nav-open #cct-sidebar" in css
    assert "env(safe-area-inset-bottom)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_reference_overview_and_model_panel_use_live_cat_apis():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    js = (WEB / "js" / "app.js").read_text(encoding="utf-8")
    assert 'id="cct-overview-panel"' in html
    assert 'id="cct-models-panel"' in html
    assert "'/api/activity/summary?days=" in js or '`/api/activity/summary?days=' in js
    assert "'/api/providers/center'" in js
    assert 'id="cct-composer-workspace"' in html
    assert 'placeholder="Ask CAT to build, debug, or explain' in html


def test_workspace_uses_glass_materials_and_tactile_interactions_without_cat_browser_blur():
    css = (WEB / "css" / "app.css").read_text(encoding="utf-8")
    assert "--fc-glass" in css
    assert "#cct-sidebar-nav .cct-sb-tab-btn:hover" in css
    assert "--fc-spring" in css
    assert ".cct-response-card" in css
    assert "html.cat-browser-renderer #cct-sidebar" in css
    assert "backdrop-filter: none !important" in css


def test_composer_matches_reference_with_one_input_surface_and_surrounding_controls():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    css = (WEB / "css" / "app.css").read_text(encoding="utf-8")
    composer = html.split('<div class="cct-kitty-dock" id="cct-composer">', 1)[1].split("</div>\n      </main>", 1)[0]
    assert composer.index('id="cct-composer-mascot"') < composer.index('<div class="cct-composer-input-row">')
    assert composer.index('id="cct-composer-mascot"') < composer.index('<div class="cct-dock-toolbar">')
    dock = composer.split('<div class="cct-dock-toolbar">', 1)[1]
    assert 'class="cct-composer-attach-btn"' in dock
    assert 'id="cct-mode-current"' in composer
    assert 'id="cct-model-badge"' in composer
    assert 'id="cct-perm-pill-btn"' in composer
    assert "grid-template-rows: 24px 42px 30px" in css
    assert "grid-template-columns: minmax(0,1fr) 34px" in css


def test_web_agent_registry_create_update_delete_and_builtin_protection(tmp_path, monkeypatch):
    from fastapi import HTTPException
    from calc_terminal.agents.registry import AgentRegistry
    from calc_terminal.web import server

    registry = AgentRegistry(str(tmp_path / "agents"))
    monkeypatch.setattr(server, "get_agent_registry", lambda: registry)

    async def exercise_routes():
        result = await server.create_agent_definition(server.AgentDefinitionRequest(
            id="ui-reviewer", name="UI Reviewer", primary_mode="research",
            system_instructions="Inspect UI changes.",
        ))
        assert result["agent"]["id"] == "ui-reviewer"
        updated = await server.update_agent_definition(
            "ui-reviewer", server.AgentDefinitionPatch(description="Review visual changes")
        )
        assert updated["agent"]["description"] == "Review visual changes"
        await server.delete_agent_definition("ui-reviewer")
        assert registry.get("ui-reviewer") is None
        try:
            await server.delete_agent_definition("cat-coder")
        except HTTPException as error:
            assert error.status_code == 403
        else:
            raise AssertionError("Built-in agents must not be deleted from the web registry")

    asyncio.run(exercise_routes())
