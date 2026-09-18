"""v0.7.8.2 panel pilot: open every redesigned screen headlessly and
check no exception/duplicate-id/mount failure occurs. Exercises:
AttachPanel, McpServersPanel (+ Add form), BackupProvidersPanel
(+ Add form), SettingsPanel, OpenWorkspaceScreen (untouched control).
"""
import asyncio
import os
import sys

sys.path.insert(0, ".")

fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


async def main():
    from calc_terminal.ui.app import CCTApp
    from calc_terminal.ui.attach_panel import AttachPanel
    from calc_terminal.ui.mcp_panel import McpServersPanel, _AddMcpForm
    from calc_terminal.ui.backup_panel import BackupProvidersPanel, _AddProviderForm
    from calc_terminal.ui.nav_screens import SettingsPanel
    from calc_terminal.ui.sidebar import OpenWorkspaceScreen

    class StubRepl:
        VERSION = "v0.7.8.2-test"
        def handle(self, raw):
            pass

    app = CCTApp(StubRepl(), [], {})
    async with app.run_test() as pilot:
        # AttachPanel: open, browse a real dir, attach a file.
        panel = AttachPanel()
        app.push_screen(panel)
        await pilot.pause()
        check("attach panel mounted", panel.query_one("#ap-box") is not None)
        await pilot.pause(0.1)
        # switch to files tab, load a directory
        panel._set_mode("files")
        panel._load_dir(os.path.dirname(os.path.abspath(__file__)))
        await pilot.pause()
        check("attach browser lists entries", len(panel._entries) > 0,
              f"{len(panel._entries)} entries")
        panel.action_move_down_sel()
        await pilot.pause()
        panel.action_move_down_sel()
        await pilot.pause()
        entry = panel._current_entry()
        check("attach rows selectable", entry is not None)
        if entry and not entry["is_dir"]:
            panel.action_toggle_pick()
            await pilot.pause()
            check("attach multi-pick works", len(panel._picked) == 1)
        app.pop_screen()

        # MCP panel + add form.
        panel = McpServersPanel()
        app.push_screen(panel)
        await pilot.pause()
        check("mcp panel mounted", panel.query_one("#mcp-box") is not None)
        app.push_screen(_AddMcpForm())
        await pilot.pause()
        form = app.screen
        check("mcp form mounted", form.query_one("#amf-box") is not None)
        # toggle to STDIO and back
        form._kind = "local"
        form._apply_kind()
        await pilot.pause()
        check("mcp stdio fields shown",
              form.query_one("#amf-command").display is True)
        form._kind = "remote"
        form._apply_kind()
        await pilot.pause()
        check("mcp remote fields shown",
              form.query_one("#amf-url").display is True)
        app.pop_screen()
        app.pop_screen()

        # Backup panel + add form.
        panel = BackupProvidersPanel()
        app.push_screen(panel)
        await pilot.pause()
        check("backup panel mounted", panel.query_one("#bpp-box") is not None)
        app.push_screen(_AddProviderForm())
        await pilot.pause()
        form = app.screen
        check("backup form mounted", form.query_one("#apf-box") is not None)
        app.pop_screen()
        app.pop_screen()

        # Settings panel.
        panel = SettingsPanel(lambda: {"perm_mode": "ask", "theme": "dark",
                                       "ai_mode": "notebook", "autosave": True,
                                       "sound": False, "animation": True,
                                       "anim_speed": 1.0, "precision": 4})
        app.push_screen(panel)
        await pilot.pause()
        check("settings panel mounted", panel.query_one("#cct-navpanel-box") is not None)
        panel.refresh_rows()
        await pilot.pause()
        app.pop_screen()

        # OpenWorkspaceScreen must remain intact.
        panel = OpenWorkspaceScreen()
        app.push_screen(panel)
        await pilot.pause()
        check("open workspace screen mounted", panel.query_one("#ows-box") is not None)
        app.pop_screen()

        # Escape-close on every panel works.
        for label, cls, qid in (
            ("attach esc", AttachPanel, "#ap-box"),
            ("mcp esc", McpServersPanel, "#mcp-box"),
            ("backup esc", BackupProvidersPanel, "#bpp-box"),
        ):
            p = cls()
            app.push_screen(p)
            await pilot.pause()
            p.on_key(type("e", (), {"key": "escape"})())
            await pilot.pause()
            check(label + " closes", not any(isinstance(s, cls) for s in app.screen_stack))


asyncio.run(main())

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("PANEL PILOT ALL PASSED")
