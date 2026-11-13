from calc_terminal.ui.app import _COMPONENT_CSS

print("Length of _COMPONENT_CSS:", len(_COMPONENT_CSS))
print("border-top: solid #5a6585; in _COMPONENT_CSS?", "border-top: solid #5a6585;" in _COMPONENT_CSS)
if "border-top: solid #5a6585;" not in _COMPONENT_CSS:
    # Where does .cct-menu-btn appear in _COMPONENT_CSS?
    idx = _COMPONENT_CSS.find(".cct-menu-btn")
    print(".cct-menu-btn in _COMPONENT_CSS at:", idx)
    print(_COMPONENT_CSS[idx:idx+400])

