from pathlib import Path
import re


ROOT = Path(__file__).parents[1]


def test_browser_switch_does_not_apply_graphics_effect_to_webengine():
    source = (ROOT / "browser_gui" / "qt_browser.py").read_text(encoding="utf-8")
    switch = source.split("def _switch_viewport_animated", 1)[1].split("def _activate_view", 1)[0]
    assert "setGraphicsEffect" not in switch
    assert "setCurrentIndex(target_idx)" in switch


def test_background_tabs_are_deferred_and_activated_on_selection():
    source = (ROOT / "browser_gui" / "qt_browser.py").read_text(encoding="utf-8")
    create_tab = source.split("def _new_tab(", 1)[1].split("def _handle_newtab_navigate_for_view", 1)[0]
    activate = source.split("def _activate_view", 1)[1].split("def _on_current_changed", 1)[0]
    assert "view._pending_url = url" in create_tab
    assert "_pending_url" in activate
    assert "_is_suspended" in activate
    assert "_load_in_view(view, url)" in activate


def test_default_chromium_watchdogs_remain_enabled_and_limits_are_bounded():
    from calc_terminal.host.launcher import get_optimal_chromium_flags

    flags = get_optimal_chromium_flags()
    for unsafe_override in (
        "--disable-gpu-watchdog", "--disable-gpu-process-crash-limit",
        "--disable-breakpad", "--disable-hang-monitor", "--ignore-gpu-blocklist",
        "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
    ):
        assert unsafe_override not in flags
    match = re.search(r"--renderer-process-limit=(\d+)", flags)
    assert match and int(match.group(1)) <= 4


def test_fatty_mascot_size_and_composer_mount_are_not_clamped_to_40px():
    static = ROOT / "web" / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    css = (static / "css" / "mascot.css").read_text(encoding="utf-8")
    mascot_js = (static / "js" / "mascot.js").read_text(encoding="utf-8")
    assert 'id="cct-composer-mascot"' in html
    assert "init('#cct-composer-mascot'" in html
    assert "--mascot-size" in mascot_js
    assert "width: var(--mascot-size, 40px) !important" in css
    assert "this.mount.classList.add('cct-mascot-wrapper')" in mascot_js
    assert "this.mount.className = 'cct-mascot-wrapper'" not in mascot_js


def test_mascot_resolves_assets_from_the_active_page_and_throttles_pointer_work():
    static = ROOT / "web" / "static"
    mascot_js = (static / "js" / "mascot.js").read_text(encoding="utf-8")
    assert "new URL('./mascots/' + file, document.baseURI)" in mascot_js
    assert "requestAnimationFrame" in mascot_js
    assert "addEventListener('visibilitychange'" in mascot_js


def test_mobile_navigation_toggle_is_outside_the_hidden_sidebar_and_drawer_is_restored():
    static = ROOT / "web" / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    css = (static / "css" / "app.css").read_text(encoding="utf-8")
    workspace = html.split('<div id="cct-workspace">', 1)[1].split('<aside id="cct-sidebar">', 1)[0]
    assert "cct-mobile-nav-toggle" in workspace
    assert "body.mobile-nav-open #cct-sidebar { display: flex !important" in css
    assert "#cct-sidebar-nav { padding-top: 54px !important; }" in css


def test_embedded_cat_browser_uses_a_flatter_low_motion_workspace():
    static = ROOT / "web" / "static"
    app_js = (static / "js" / "app.js").read_text(encoding="utf-8")
    css = (static / "css" / "app.css").read_text(encoding="utf-8")
    assert "cat-browser-renderer" in app_js
    assert "html.cat-browser-renderer #cct-composer" in css
    assert "animation: none !important" in css
