import inspect
import calc_terminal.ui.mcp_panel as m
import calc_terminal.ui.backup_panel as b
import calc_terminal.ui.attach_panel as a
import calc_terminal.ui.activity_panel as act
import calc_terminal.ui.personalization_panel as pp
import calc_terminal.ui.welcome_modal as wm

mods = {
    "McpServersPanel": m.McpServersPanel,
    "BackupProvidersPanel": b.BackupProvidersPanel,
    "AttachPanel": a.AttachPanel,
    "ActivityPanel": act.ActivityPanel,
    "PersonalizationPanel": pp.PersonalizationPanel,
    "WelcomeModal": wm.WelcomeModal,
}
for name, cls in mods.items():
    css = getattr(cls, "CSS", None)
    src = inspect.getsource(cls)
    has_css = "CSS =" in src
    print(f"{name}: CSS len={len(css) if css else 0} css_in_class_source={has_css}")
