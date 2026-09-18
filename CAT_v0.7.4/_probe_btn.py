"""Reproduce the bottom-button rendering bug headlessly and dump SVG."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUT = os.path.join(os.environ.get("TEMP", "/tmp"), "cct_btn_probe")
os.makedirs(OUT, exist_ok=True)


async def main():
    from textual.app import App

    from calc_terminal.ui import theme_css
    from calc_terminal.ui.mcp_panel import McpServersPanel, _AddMcpForm
    from calc_terminal.ui.backup_panel import BackupProvidersPanel, _AddProviderForm
    from calc_terminal.ui.personalization_panel import PersonalizationPanel
    from calc_terminal.ui.welcome_modal import WelcomeModal
    from calc_terminal.ui.attach_panel import AttachPanel

    # patch saved servers so the panel shows rows
    import calc_terminal.mcp as mcp

    real_load = mcp.load_servers
    mcp.load_servers = lambda: [
        {"id": "srv1", "name": "Math Tools", "kind": "remote",
         "url": "http://localhost:3000/mcp", "status": "connected",
         "version": "2024-11-05", "latency_ms": 42, "tools": ["add", "mul"],
         "last_connected": 1755300000},
        {"id": "srv2", "name": "Git Helper", "kind": "local",
         "command": "npx git-mcp", "status": "disconnected",
         "version": "", "latency_ms": None, "tools": []},
    ]

    from calc_terminal.providers import provider_manager as pm
    real_bp = pm.load_backup_providers
    pm.load_backup_providers = lambda: [
        {"provider": "openai", "model": "gpt-4o-mini", "api_key": "k",
         "status": "connected", "latency_ms": 120, "enabled": True,
         "last_used": 1755300000, "base_url": "", "api_style": "openai"},
        {"provider": "anthropic", "model": "claude-3-5-haiku", "api_key": "k",
         "status": "disconnected", "latency_ms": None, "enabled": True,
         "last_used": 0, "base_url": "", "api_style": "anthropic"},
    ]

    # avoid writing config during probe
    try:
        import calc_terminal.ai_personalization as pers
        real_profiles = pers.load_profiles
        pers.load_profiles = lambda: {"profiles": [
            {"name": "Concise Coder", "tone": "concise", "temperature": 0.2,
             "model": "", "style_rules": "short answers",
             "active": True},
            {"name": "Lab Partner", "tone": "detailed", "temperature": 0.6,
             "model": "", "style_rules": "explain chemistry", "active": False},
        ]}
        real_save = pers.save_profiles
        pers.save_profiles = lambda *a, **k: None
    except Exception as e:
        print("pers skip", e)

    # Stub profile-backed calls used by personalization panel
    try:
        from calc_terminal.ui import personalization_panel as pp
        pp_lib = sys.modules.get("calc_terminal.ai_personalization")
    except Exception:
        pass

    class ProbeApp(App):
        CSS = theme_css.BASE_CSS

        def get_css_variables(self):
            variables = dict(super().get_css_variables())
            variables.update(theme_css.css_variables())
            return variables

    screens = {
        "mcp": McpServersPanel(),
        "mcp_add": _AddMcpForm(),
        "backup": BackupProvidersPanel(),
        "backup_add": _AddProviderForm(),
        "welcome": WelcomeModal(),
        "personalize": PersonalizationPanel(),
    }

    for name, screen in screens.items():
        app = ProbeApp()
        async with app.run_test(size=(110, 36), headless=True) as pilot:
            await app.push_screen(screen)
            for _ in range(15):
                await pilot.pause()
                await asyncio.sleep(0.12)
            path = os.path.join(OUT, f"{name}.svg")
            app.save_screenshot(path)
            print("saved", path)
            # fallback: export_screenshot
            try:
                svg = await app.export_screenshot()
                if not os.path.exists(path) or os.path.getsize(path) == 0:
                    with open(os.path.join(OUT, f"{name}_exp.svg"), "w", encoding="utf-8") as f:
                        f.write(svg)
                    print("exported", f"{name}_exp.svg", len(svg))
            except Exception as e:
                print("export failed", e)


asyncio.run(main())