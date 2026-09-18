import inspect
import calc_terminal.ui.mcp_panel as m
import calc_terminal.ui.backup_panel as b
import calc_terminal.ui.attach_panel as a

for mod, names in ((m, ("McpServersPanel", "_AddMcpForm")),
                   (b, ("BackupProvidersPanel", "_AddProviderForm")),
                   (a, ("AttachPanel",))):
    for n in names:
        cls = getattr(mod, n, None)
        if cls is None:
            print(f"{mod.__name__}.{n}: None")
            continue
        css = getattr(cls, "CSS", None)
        src = inspect.getsource(cls)
        has_css = "CSS =" in src or "CSS=" in src
        print(f"{mod.__name__}.{n}: CSS len={len(css) if css else 0!r} css_in_source={has_css} def_line={src.splitlines()[0][:60]!r}")
