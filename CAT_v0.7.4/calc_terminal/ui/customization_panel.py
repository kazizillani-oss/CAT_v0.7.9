"""
CAT Customization — Responsive Professional Redesign (v0.8.3)
No hover-auto-start: every change is explicit click / Apply / Toggle.
Card layout, lightweight per-panel editing for performance.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import time

TEXTUAL_AVAILABLE = True
try:
    from textual.screen import Screen
    from textual.containers import Vertical, Horizontal, ScrollableContainer
    from textual.widgets import Static, Button, Input, Switch, Select
    from textual.binding import Binding
    try:
        from textual.widgets import TextArea
        _HAS_TEXTAREA = True
    except Exception:
        TextArea = None
        _HAS_TEXTAREA = False
except Exception:
    TEXTUAL_AVAILABLE = False
    _HAS_TEXTAREA = False

if TEXTUAL_AVAILABLE:
    try:
        from .. import customization as cust
        from ..customization import COMPONENT_CONSTRAINTS
    except Exception:
        cust = None
        COMPONENT_CONSTRAINTS = {}
    try:
        from . import theme_css
        if hasattr(theme_css, "_patch_rich_divide_line"):
            theme_css._patch_rich_divide_line()
    except Exception:
        theme_css = None

    def _hex(role):
        try:
            return theme_css.current_hex(role) if theme_css else "#888888"
        except Exception:
            return "#888888"

    _NAV_SECTIONS = [
        ("OVERVIEW", [("overview", "◎  Overview")]),
        ("LAYOUT", [("layout", "▦  Order"), ("position", "↔  Position"), ("size", "⧉  Size"), ("docking", "⚓  Docking")]),
        ("APPEARANCE", [("appearance", "✎  Appearance"), ("buttons", "⬢  Buttons"), ("icons", "◇  Icons"), ("header", "⬔  Header"), ("menu", "☰  Menu"), ("spacing", "⟷  Spacing")]),
        ("BEHAVIOR", [("visibility", "◉  Visibility")]),
        ("WORKSPACE", [("profiles", "★  Profiles"), ("editor", "⬙  Editor"), ("advanced", "⌘  Advanced"), ("reset", "↺  Reset")]),
    ]
    _HINTS = {
        "overview": "Overview · select panel below then edit in its section",
        "layout": "Order defines visual sequence · use ↑ ↓",
        "position": "Choose panel then click position · explicit Apply",
        "size": "Choose panel then set W/H · Apply",
        "docking": "Docked inline · Floating overlay",
        "appearance": "Appearance overview · jump to details",
        "buttons": "Shape · size · radius · padding",
        "icons": "Size · visibility",
        "header": "Height · logo · title",
        "menu": "Menu order & visibility",
        "spacing": "Padding · margin · borders",
        "visibility": "Toggle any region",
        "profiles": "Save / load layouts",
        "editor": "Visual preview · click to cycle",
        "advanced": "Raw JSON · Save to apply",
        "reset": "Restore defaults",
    }
    _PANEL_IDS = ["sidebar", "chat", "code_editor", "terminal", "file_explorer", "header", "preview", "activity_bar", "secondary_panel", "editor"]
    _POSITION_OPTS = ["left", "right", "center", "top", "bottom", "floating", "docked"]
    _BUTTON_SHAPES = ["rounded", "pill", "square", "minimal", "ghost", "outlined", "filled", "compact", "large"]
    _BUTTON_SIZES = ["small", "medium", "large", "compact"]
    _ICON_SIZES = ["small", "medium", "large"]

    def _safe_query(widget, selector, typ=None):
        try:
            if typ:
                return widget.query_one(selector, typ)
            return widget.query_one(selector)
        except Exception:
            return None

    class _Preview(Static):
        allow_select = False

        def __init__(self, manager, selected="sidebar"):
            super().__init__("", id="cust-preview")
            self._manager = manager
            self._selected = selected or "sidebar"
            self.allow_select = False

        def on_mount(self):
            self.refresh_preview()

        def on_mouse_down(self, event):
            try:
                event.stop()
                event.prevent_default()
            except Exception:
                pass

        def refresh_preview(self):
            try:
                layout = self._manager.get_layout()
                w = 50
                lines = []
                header = layout.get("header", {})
                if header.get("visible", True):
                    sel = "● " if self._selected == "header" else "  "
                    h_h = header.get("height", 3)
                    lines.append("┌" + "─" * w + "┐")
                    lines.append("│" + f"{sel}HEADER (height: {h_h})".center(w) + "│")

                panes = []
                seen = set()
                order_list = sorted([v for v in layout.values() if v.get("visible", True)], key=lambda c: c.get("order", 0))
                for p in order_list:
                    pid = p["id"]
                    if pid in ("header", "terminal"):
                        continue
                    canon = "code_editor" if pid in ("editor", "code_editor") else ("sidebar" if pid in ("sidebar", "file_explorer") else pid)
                    if canon in seen:
                        continue
                    seen.add(canon)
                    panes.append(p)

                label_map = {"sidebar": "SIDEBAR", "chat": "CHAT", "code_editor": "EDITOR", "file_explorer": "FILES"}
                n = len(panes)
                if n > 0:
                    lines.append("├" + "─" * w + "┤")
                    col_w = (w - (n - 1)) // n
                    rem = (w - (n - 1)) % n
                    widths = [col_w + (1 if i < rem else 0) for i in range(n)]

                    row1_parts = []
                    row2_parts = []
                    for i, p in enumerate(panes):
                        pw = widths[i]
                        lab = label_map.get(p["id"], p["id"][:8].upper())
                        is_sel = (p["id"] == self._selected or ("code_editor" in (p["id"], self._selected) and "editor" in (p["id"], self._selected)) or ("sidebar" in (p["id"], self._selected) and "file_explorer" in (p["id"], self._selected)))
                        sel_mark = "● " if is_sel else ""
                        pos_str = f"({p.get('position', '?')})"
                        row1_parts.append(f"{sel_mark}{lab}".center(pw))
                        row2_parts.append(pos_str.center(pw))

                    lines.append("│" + "│".join(row1_parts) + "│")
                    lines.append("│" + "│".join(row2_parts) + "│")

                term = layout.get("terminal", {})
                if term.get("visible", True):
                    sel = "● " if self._selected == "terminal" else "  "
                    lines.append("├" + "─" * w + "┤")
                    lines.append("│" + f"{sel}TERMINAL ({term.get('position', 'bottom')})".center(w) + "│")
                lines.append("└" + "─" * w + "┘")
                self.update("\n".join(lines))
            except Exception:
                self.update("Preview unavailable")

        def on_click(self, event):
            try:
                event.stop()
                event.prevent_default()
            except Exception:
                pass
            try:
                canonical_ids = ["sidebar", "chat", "code_editor", "terminal", "header"]
                cur = self._selected
                if cur in ("editor", "code_editor"):
                    cur = "code_editor"
                elif cur in ("file_explorer", "sidebar"):
                    cur = "sidebar"
                if cur in canonical_ids:
                    idx = canonical_ids.index(cur)
                    self._selected = canonical_ids[(idx + 1) % len(canonical_ids)]
                else:
                    self._selected = "sidebar"
                self.refresh_preview()
                try:
                    if hasattr(self.screen, "_on_preview_select"):
                        self.screen._on_preview_select(self._selected)
                except Exception:
                    pass
            except Exception:
                pass

    class CustomizationPanel(Screen):
        allow_select = False
        CSS = """
        CustomizationPanel { align: center middle; background: $app-background 70%; }
        #cust-box { width: 98; max-width: 98%; height: 92%; max-height: 96%; background: $surface; border: round $border; padding: 0; layout: vertical; overflow: hidden; }
        #cust-box Button { min-height: 3; height: 3; min-width: 10; padding: 0 1; }
        #cust-box Button.-style-default, #cust-box Button:ansi.-style-default { min-height: 3; height: 3; min-width: 10; padding: 0 1; }
        #cust-titlebar { height: 3; min-height: 3; padding: 0 2; border-bottom: solid $border; layout: horizontal; align: center middle; }
        #cust-title { width: 1fr; text-style: bold; color: $text; }
        #cust-subtitle { width: auto; color: $text-faint; padding-right: 1; }
        #cust-close { min-width: 3; width: 3; height: 1; min-height: 1; }
        #cust-disabled { height: auto; padding: 2 2; align: center middle; }
        .cust-disabled-msg { color: $warning; text-style: bold; height: auto; text-align: center; }
        .cust-disabled-hint { color: $text-faint; height: auto; text-align: center; padding-top: 1; }
        #cust-disabled-actions { height: auto; padding-top: 1; layout: horizontal; align: center middle; }
        #cust-disabled-actions Button { margin: 0 1; min-width: 10; padding: 0 1; }
        #cust-body { height: 1fr; min-height: 0; layout: horizontal; }
        #cust-sidebar { width: 28; min-width: 24; height: 100%; border-right: solid $border; layout: vertical; background: $surface; }
        #cust-search { height: 3; min-height: 3; padding: 0 1; border-bottom: solid $border; }
        #cust-search Input { width: 1fr; height: 3; background: $app-background; border: round $border; }
        #cust-search Input:focus { border: round $accent; }
        #cust-sidebar-inner { width: 100%; height: 1fr; overflow-y: auto; scrollbar-gutter: stable; }
        .cust-nav-section { color: $text-faint; height: 1; padding: 1 1 0 1; text-style: bold; }
        .cust-nav-btn { width: 100%; height: 1; min-height: 1; padding: 0 1; text-align: left; background: transparent; border: none; color: $text-muted; }
        .cust-nav-btn-sel { background: $accent 14%; color: $accent; text-style: bold; border-left: thick $accent; }
        #cust-content { width: 1fr; height: 1fr; min-height: 10; padding: 1 2; overflow-y: auto; overflow-x: auto; scrollbar-gutter: stable; background: $surface; }
        .cust-card { background: $surface; border: round $border; padding: 1 2; margin-bottom: 1; width: 100%; height: auto; min-height: 6; }
        .cust-card-title { color: $text; text-style: bold; height: 1; }
        .cust-card-desc { color: $text-faint; height: auto; padding-bottom: 1; }
        .cust-label { color: $text-muted; height: 1; min-height: 1; width: auto; min-width: 6; padding-right: 1; }
        .cust-hint { color: $text-faint; height: auto; min-height: 1; padding: 0 0 1 0; }
        .cust-row { height: auto; min-height: 3; layout: horizontal; align: center middle; padding: 0; margin-bottom: 1; width: 100%; overflow-x: auto; }
        .cust-row Button { margin-right: 1; min-width: 10; width: auto; height: 3; min-height: 3; padding: 0 1; }
        .cust-row Input { width: 10; min-width: 6; height: 3; min-height: 3; margin-right: 1; }
        .cust-row Select { width: 18; min-width: 12; height: 3; min-height: 3; margin-right: 1; }
        .cust-field-row { height: auto; min-height: 3; layout: horizontal; align: center middle; padding: 0; margin-bottom: 1; width: 100%; }
        .cust-field-row Input { width: 1fr; min-width: 8; height: 3; min-height: 3; margin-right: 1; }
        .cust-field-row Select { width: 1fr; min-width: 10; height: 3; min-height: 3; margin-right: 1; }
        .cust-field-row Button { height: 3; min-height: 3; min-width: 10; padding: 0 1; }
        .cust-visibility-row { height: auto; min-height: 2; layout: horizontal; align: center middle; border-bottom: solid $border 12%; padding: 1 0; }
        .cust-visibility-label { width: 1fr; color: $text; }
        .cust-drag-row { height: auto; min-height: 3; layout: horizontal; align: center middle; border-bottom: solid $border 60%; padding: 0 1; margin-bottom: 1; }
        .cust-drag-label { width: 1fr; color: $text; }
        #cust-preview { width: 100%; height: auto; padding: 0; background: $surface; color: $text-muted; margin-bottom: 1; }
        #cust-actions { height: 4; min-height: 4; padding: 0 2; border-top: solid $border; layout: horizontal; align: center middle; background: $surface; }
        #cust-actions-left { width: 1fr; layout: horizontal; }
        #cust-actions-left Button { margin-right: 1; min-width: 12; height: 3; }
        #cust-actions-right Button { margin-left: 1; min-width: 10; height: 3; }
        #cust-status { height: 1; color: $text-faint; padding: 0 2; }
        #cust-error { height: auto; color: $error; padding: 1 2; display: none; background: $surface; border: round $error; margin: 0 2; }
        #cust-error.show { display: block; }
        #cust-hint { color: $text-faint; height: 1; padding: 0 2; }
        .cct-compact #cust-body { layout: vertical; }
        .cct-compact #cust-sidebar { width: 100%; height: auto; max-height: 12; border-right: none; border-bottom: solid $border; }
        .cct-compact #cust-content { width: 100%; height: 1fr; min-height: 14; }
        .cct-compact .cust-row { layout: vertical; height: auto; }
        .cct-compact .cust-row Button { width: 100%; margin-right: 0; margin-bottom: 1; }
        .cct-compact .cust-row Input { width: 100%; margin-right: 0; margin-bottom: 1; }
        .cct-compact .cust-row Select { width: 100%; margin-right: 0; margin-bottom: 1; }
        .cct-compact .cust-field-row { layout: vertical; height: auto; }
        .cct-compact .cust-field-row Input { width: 100%; margin-right: 0; margin-bottom: 1; }
        .cct-compact .cust-field-row Select { width: 100%; margin-right: 0; margin-bottom: 1; }
        .cct-compact .cust-field-row Button { width: 100%; margin-right: 0; margin-bottom: 1; }
        .cct-compact .cust-visibility-row { layout: vertical; height: auto; }
        .cct-compact .cust-visibility-row Switch { margin-top: 1; }
        .cct-compact .cust-drag-row { layout: vertical; height: auto; padding: 1 1; }
        .cct-compact .cust-drag-row Button { width: 100%; margin: 1 0 0 0; }
        .cct-compact .cust-drag-label { width: 100%; margin-bottom: 1; }
        .cct-compact #cust-actions { layout: vertical; height: auto; padding: 1 2; }
        .cct-compact #cust-actions-left { width: 100%; layout: vertical; }
        .cct-compact #cust-actions-left Button { width: 100%; margin: 0 0 1 0; }
        .cct-compact #cust-actions-right { width: 100%; layout: vertical; margin-top: 1; }
        .cct-compact #cust-actions-right Button { width: 100%; margin: 0; }
        .cct-compact #cust-preview { height: auto; min-height: 8; }
        """
        BINDINGS = [Binding("escape", "cancel", "Cancel")]

        def __init__(self):
            super().__init__()
            self._manager = cust.get_manager() if cust else None
            self._selected_panel = "sidebar"
            self._nav_state = "overview"
            self._search_query = ""
            self._last_search_query = ""
            self._status_timer = None
            self._size_panel = "sidebar"
            self._pos_panel = "sidebar"
            self._dock_panel = "sidebar"

        def compose(self):
            try:
                from .. import extensions as _ext
                if not _ext.is_enabled("customization"):
                    with Vertical(id="cust-box"):
                        with Horizontal(id="cust-titlebar"):
                            yield Static("CAT Customization", id="cust-title")
                            yield Button("✕", id="cust-close", classes="cct-ctrl")
                        with Vertical(id="cust-disabled"):
                            yield Static("Customization is disabled.", classes="cust-disabled-msg")
                            yield Static("Enable CAT Customization in Extensions to edit layout & appearance.", classes="cust-disabled-hint")
                            with Horizontal(id="cust-disabled-actions"):
                                yield Button("Open Extensions", id="cust-open-ext", variant="primary")
                                yield Button("Close", id="cust-close2")
                    return
            except Exception:
                pass
            with Vertical(id="cust-box"):
                with Horizontal(id="cust-titlebar"):
                    yield Static("CAT Customization", id="cust-title")
                    yield Static("explicit apply", id="cust-subtitle")
                    yield Button("✕", id="cust-close", classes="cct-ctrl")
                yield Static("", id="cust-error")
                with Horizontal(id="cust-body"):
                    with Vertical(id="cust-sidebar"):
                        with Horizontal(id="cust-search"):
                            yield Input(placeholder="Filter…", id="cust-search-input")
                        yield ScrollableContainer(id="cust-sidebar-inner")
                    with ScrollableContainer(id="cust-content"):
                        pass
                yield Static("", id="cust-status")
                with Horizontal(id="cust-actions"):
                    with Horizontal(id="cust-actions-left"):
                        yield Button("Reset Current", id="cust-reset-current", classes="cct-btn-sm")
                        yield Button("Reset All", id="cust-reset-all", variant="error", classes="cct-btn-sm")
                    with Horizontal(id="cust-actions-right"):
                        yield Button("Close", id="cust-close3", variant="primary", classes="cct-btn-sm")
                yield Static("", id="cust-hint")

        def on_mount(self):
            if self.size.width < 88 or self.size.height < 28:
                try:
                    self.query_one("#cust-box").add_class("cct-compact")
                except Exception:
                    pass
            self.call_after_refresh(self._rebuild_nav)
            self.call_after_refresh(self._render_section_view)
            try:
                self.query_one("#cust-search-input", Input).focus()
            except Exception:
                pass

        def on_resize(self, event):
            try:
                want = self.size.width < 88 or self.size.height < 28
                box = self.query_one("#cust-box")
                if want != box.has_class("cct-compact"):
                    box.set_class(want, "cct-compact")
            except Exception:
                pass

        def _rebuild_nav(self):
            try:
                nav = self.query_one("#cust-sidebar-inner", ScrollableContainer)
                # lightweight: update existing buttons' selected state without full rebuild if possible
                # If nav is empty (first mount), do full rebuild
                if len(list(nav.children)) == 0:
                    q = self._search_query.lower().strip()
                    for sec, items in _NAV_SECTIONS:
                        vis = [(k,l) for k,l in items if not q or q in k.lower() or q in l.lower()]
                        if not vis:
                            continue
                        try:
                            nav.mount(Static(sec, classes="cust-nav-section"))
                        except Exception:
                            pass
                        for k,l in vis:
                            btn = Button(l, id=f"cust-nav-{k}", classes="cust-nav-btn")
                            if k==self._nav_state:
                                btn.add_class("cust-nav-btn-sel")
                            try:
                                nav.mount(btn)
                            except Exception:
                                pass
                else:
                    # update selected state only
                    for btn in nav.query(Button):
                        if btn.id and btn.id.startswith("cust-nav-"):
                            key = btn.id.replace("cust-nav-","")
                            btn.set_class(key==self._nav_state, "cust-nav-btn-sel")
                    # handle search filtering: only rebuild if search query changed and is active, or was cleared
                    cur_q = self._search_query.lower().strip()
                    last_q = getattr(self, "_last_search_query", "")
                    if cur_q != last_q and (cur_q or last_q):
                        self._last_search_query = cur_q
                        nav.remove_children()
                        for sec, items in _NAV_SECTIONS:
                            vis = [(k,l) for k,l in items if not cur_q or cur_q in k.lower() or cur_q in l.lower()]
                            if not vis:
                                continue
                            nav.mount(Static(sec, classes="cust-nav-section"))
                            for k,l in vis:
                                btn = Button(l, id=f"cust-nav-{k}", classes="cust-nav-btn")
                                if k==self._nav_state:
                                    btn.add_class("cust-nav-btn-sel")
                                nav.mount(btn)
            except Exception:
                return
            try:
                self.query_one("#cust-hint", Static).update(_HINTS.get(self._nav_state, "Esc to close"))
            except Exception:
                pass

        def _set_nav(self, key):
            self._nav_state = key
            self._rebuild_nav()
            self._render_section_view()

        def _render_section_view(self):
            try:
                c = self.query_one("#cust-content", ScrollableContainer)
                c.remove_children()
            except Exception:
                return
            h = getattr(self, f"_render_{self._nav_state}", None)
            if h:
                try:
                    h(c)
                except Exception as e:
                    try:
                        c.mount(Static(f"Error: {e}", classes="cust-hint"))
                    except Exception:
                        pass

        def _show_status(self, msg, style="success"):
            try:
                lbl = self.query_one("#cust-status", Static)
                col = _hex(style) if style in ("success","warning","error") else _hex("success")
                lbl.update(f"[{col}]{msg}[/]")
            except Exception:
                pass
        def _show_error(self, msg):
            try:
                lbl = self.query_one("#cust-error", Static)
                lbl.update(msg)
                lbl.add_class("show")
                self.set_timer(4, lambda: lbl.remove_class("show"))
            except Exception:
                pass
        def _refresh_all(self):
            self.call_after_refresh(self._render_section_view)
            try:
                for p in self.query(_Preview):
                    p.refresh_preview()
            except Exception:
                pass
        def _on_preview_select(self, comp_id):
            self._selected_panel = comp_id
            self._pos_panel = comp_id
            self._size_panel = comp_id
            self._dock_panel = comp_id

            # In-place updates for preview & overview/editor without tearing down the DOM:
            try:
                for hint in self.query(".cust-hint"):
                    if self._manager:
                        layout = self._manager.get_layout()
                        sel = layout.get(comp_id, {})
                        if self._nav_state == "editor":
                            hint.update(f"Selected: [b]{comp_id}[/]")
                        else:
                            hint.update(f"Selected: [b]{comp_id}[/] · {sel.get('position','?')} · {'Visible' if sel.get('visible',True) else 'Hidden'} · w:{sel.get('width','auto')} h:{sel.get('height','auto')}")
            except Exception:
                pass

            try:
                for pid in ("sidebar", "chat", "code_editor", "terminal"):
                    b = _safe_query(self, f"#cust-sel-{pid}", Button)
                    if b:
                        is_sel = (pid == comp_id or (pid == "code_editor" and comp_id == "editor") or (pid == "sidebar" and comp_id == "file_explorer"))
                        b.variant = "primary" if is_sel else "default"
            except Exception:
                pass

            try:
                for p in self.query(_Preview):
                    if p._selected != comp_id:
                        p._selected = comp_id
                        p.refresh_preview()
            except Exception:
                pass

            if self._nav_state in ("layout", "position", "size"):
                self.call_after_refresh(self._render_section_view)

        def _live_apply(self):
            # Refresh internal preview
            try:
                for p in self.query(_Preview):
                    p.refresh_preview()
            except Exception:
                pass
            # Immediately update live UI underneath (live preview)
            try:
                if hasattr(self.app, "_apply_customization_layout"):
                    self.app._apply_customization_layout()
            except Exception:
                pass

        def _card(self, parent, title, desc=None):
            card = Vertical(classes="cust-card")
            parent.mount(card)
            card.mount(Static(title, classes="cust-card-title"))
            if desc:
                card.mount(Static(desc, classes="cust-card-desc"))
            return card

        def _render_overview(self, container):
            card = self._card(container, "Overview", "Select a panel then edit in its section · explicit Apply only")
            if self._manager:
                layout = self._manager.get_layout()
                sel = layout.get(self._selected_panel, {})
                card.mount(Static(f"Selected: [b]{self._selected_panel}[/] · {sel.get('position','?')} · {'Visible' if sel.get('visible',True) else 'Hidden'} · w:{sel.get('width','auto')} h:{sel.get('height','auto')}", classes="cust-hint"))
                card.mount(_Preview(self._manager, selected=self._selected_panel))
                row = Horizontal(classes="cust-row")
                card.mount(row)
                for pid, label in [("sidebar", "Sidebar"), ("chat", "Chat"), ("code_editor", "Editor"), ("terminal", "Terminal")]:
                    b = Button(label, id=f"cust-sel-{pid}", classes="cct-btn-sm")
                    if pid == self._selected_panel or (pid == "code_editor" and self._selected_panel == "editor") or (pid == "sidebar" and self._selected_panel == "file_explorer"):
                        b.variant = "primary"
                    row.mount(b)

        def _render_layout(self, container):
            card = self._card(container, "Order", "Use ↑ ↓ to reorder · click to apply")
            if self._manager:
                ordered = self._manager.get_ordered_components()
                seen = set()
                idx = 0
                for c in ordered:
                    cid = c["id"]
                    canon = "code_editor" if cid in ("editor", "code_editor") else ("sidebar" if cid in ("sidebar", "file_explorer") else cid)
                    if canon in seen:
                        continue
                    seen.add(canon)
                    idx += 1
                    r = Horizontal(classes="cust-drag-row")
                    card.mount(r)
                    disp_name = cid.replace("_", " ").title()
                    r.mount(Static(f"{idx}. {disp_name} ({c.get('position','?')})", classes="cust-drag-label"))
                    r.mount(Button("↑", id=f"cust-order-up-{cid}", classes="cct-btn-sm"))
                    r.mount(Button("↓", id=f"cust-order-down-{cid}", classes="cct-btn-sm"))
                    r.mount(Button("Hide" if c.get("visible",True) else "Show", id=f"cust-order-vis-{cid}", classes="cct-btn-sm"))

        def _render_position(self, container):
            card = self._card(container, "Position", "Choose panel then choose position · click to apply (no hover)")
            row = Horizontal(classes="cust-row")
            card.mount(row)
            row.mount(Static("Panel:", classes="cust-label"))
            for pid, label in [("sidebar", "Sidebar"), ("chat", "Chat"), ("code_editor", "Editor"), ("terminal", "Terminal")]:
                b = Button(label, id=f"cust-pospick-{pid}", classes="cct-btn-sm")
                if pid == self._pos_panel or (pid == "code_editor" and self._pos_panel == "editor") or (pid == "sidebar" and self._pos_panel == "file_explorer"):
                    b.variant = "primary"
                row.mount(b)
            cur = self._manager.get_layout().get(self._pos_panel, {}).get("position","left") if self._manager else "left"
            card.mount(Static(f"Current: [b]{cur}[/] · Selected: [b]{self._pos_panel}[/]", classes="cust-hint"))
            row2 = Horizontal(classes="cust-row")
            card.mount(row2)
            for pos in _POSITION_OPTS:
                b = Button(pos.title(), id=f"cust-pos-{pos}", classes="cct-btn-sm")
                if pos == cur:
                    b.variant = "primary"
                row2.mount(b)

            # header extra
            card2 = self._card(container, "Header Alignment", "")
            hdr = self._manager.get_layout().get("header", {}) if self._manager else {}
            for key,opts in [("logo_position",["left","center","right"]), ("title_position",["left","center","right"])]:
                cur2 = hdr.get(key,"left")
                card2.mount(Static(key.replace("_"," ").title(), classes="cust-label"))
                r = Horizontal(classes="cust-row")
                card2.mount(r)
                for opt in opts:
                    b = Button(opt.title(), id=f"cust-hdr-{key}-{opt}", classes="cct-btn-sm")
                    if opt == cur2:
                        b.variant = "primary"
                    r.mount(b)

        def _render_size(self, container):
            card = self._card(container, "Size", "Choose panel then set W/H · Apply to save")
            row = Horizontal(classes="cust-row")
            card.mount(row)
            row.mount(Static("Panel:", classes="cust-label"))
            for pid, label in [("sidebar", "Sidebar"), ("chat", "Chat"), ("code_editor", "Editor"), ("terminal", "Terminal")]:
                b = Button(label, id=f"cust-sizepick-{pid}", classes="cct-btn-sm")
                if pid == self._size_panel or (pid == "code_editor" and self._size_panel == "editor") or (pid == "sidebar" and self._size_panel == "file_explorer"):
                    b.variant = "primary"
                row.mount(b)
            if self._manager:
                comp = self._manager.get_layout().get(self._size_panel, {})
                constr = COMPONENT_CONSTRAINTS.get(self._size_panel, {})
                card.mount(Static(f"Range {constr.get('min_width',12)}–{constr.get('max_width',80)} cols", classes="cust-hint"))
                row2 = Horizontal(classes="cust-row")
                card.mount(row2)
                row2.mount(Static("W:", classes="cust-label"))
                row2.mount(Input(value=str(comp.get("width") or ""), placeholder="auto", id=f"cust-w-{self._size_panel}"))
                row2.mount(Static("H:", classes="cust-label"))
                row2.mount(Input(value=str(comp.get("height") or ""), placeholder="auto", id=f"cust-h-{self._size_panel}"))
                row2.mount(Button("Apply", id=f"cust-size-apply-{self._size_panel}", variant="primary", classes="cct-btn-sm"))
                quick = Horizontal(classes="cust-row")
                card.mount(quick)
                quick.mount(Static("Quick:", classes="cust-label"))
                for pct in [20,30,40]:
                    quick.mount(Button(f"{pct}%", id=f"cust-size-pct-{self._size_panel}-{pct}", classes="cct-btn-sm"))
                quick.mount(Button("Auto", id=f"cust-size-auto-{self._size_panel}", classes="cct-btn-sm"))

        def _render_docking(self, container):
            card = self._card(container, "Docking", "Explicit click to set dock state")
            row = Horizontal(classes="cust-row")
            card.mount(row)
            row.mount(Static("Panel:", classes="cust-label"))
            for pid, label in [("sidebar", "Sidebar"), ("chat", "Chat"), ("code_editor", "Editor"), ("terminal", "Terminal")]:
                b = Button(label, id=f"cust-dockpick-{pid}", classes="cct-btn-sm")
                if pid == self._dock_panel or (pid == "code_editor" and self._dock_panel == "editor") or (pid == "sidebar" and self._dock_panel == "file_explorer"):
                    b.variant = "primary"
                row.mount(b)
            cur = self._manager.get_layout().get(self._dock_panel, {}).get("dock_state","docked") if self._manager else "docked"
            card.mount(Static(f"Current: [b]{cur}[/]", classes="cust-hint"))
            row2 = Horizontal(classes="cust-row")
            card.mount(row2)
            for opt in ["docked","floating"]:
                b = Button(opt.title(), id=f"cust-dock-{self._dock_panel}-{opt}", classes="cct-btn-sm")
                if opt == cur:
                    b.variant = "primary"
                row2.mount(b)

        def _render_appearance(self, container):
            card = self._card(container, "Appearance", "Jump to sections · all edits require click")
            row = Horizontal(classes="cust-row")
            card.mount(row)
            for sec,label in [("buttons","Buttons"),("icons","Icons"),("header","Header"),("menu","Menu"),("spacing","Spacing")]:
                row.mount(Button(label, id=f"cust-jump-{sec}", classes="cct-btn-sm"))

        def _render_buttons(self, container):
            if not self._manager: return
            btn = self._manager.get_styles().get("buttons", {})
            card = self._card(container, "Buttons", f"Current {btn.get('shape','rounded')} · {btn.get('size','medium')}")
            card.mount(Static("Shape", classes="cust-label"))
            row = Horizontal(classes="cust-row")
            card.mount(row)
            for s in _BUTTON_SHAPES[:5]:
                b = Button(s.title(), id=f"cust-btn-shape-{s}", classes="cct-btn-sm")
                if s == btn.get("shape"): b.variant = "primary"
                row.mount(b)
            row_b = Horizontal(classes="cust-row")
            card.mount(row_b)
            for s in _BUTTON_SHAPES[5:]:
                b = Button(s.title(), id=f"cust-btn-shape-{s}", classes="cct-btn-sm")
                if s == btn.get("shape"): b.variant = "primary"
                row_b.mount(b)
            card.mount(Static("Size", classes="cust-label"))
            row2 = Horizontal(classes="cust-row")
            card.mount(row2)
            for sz in _BUTTON_SIZES:
                b = Button(sz.title(), id=f"cust-btn-size-{sz}", classes="cct-btn-sm")
                if sz == btn.get("size"): b.variant = "primary"
                row2.mount(b)
            row3 = Horizontal(classes="cust-row")
            card.mount(row3)
            row3.mount(Static("Radius:", classes="cust-label")); row3.mount(Input(value=str(btn.get("border_radius",4)), id="cust-btn-radius"))
            row3.mount(Static("Padding:", classes="cust-label")); row3.mount(Input(value=str(btn.get("padding",1)), id="cust-btn-padding"))
            row3.mount(Button("Apply", id="cust-btn-apply", variant="primary", classes="cct-btn-sm"))

        def _render_icons(self, container):
            if not self._manager: return
            icons = self._manager.get_styles().get("icons", {})
            card = self._card(container, "Icons", f"Current {icons.get('size','medium')}")
            row = Horizontal(classes="cust-row")
            card.mount(row)
            for sz in _ICON_SIZES:
                b = Button(sz.title(), id=f"cust-icon-size-{sz}", classes="cct-btn-sm")
                if sz == icons.get("size"): b.variant = "primary"
                row.mount(b)
            row2 = Horizontal(classes="cust-row")
            card.mount(row2)
            row2.mount(Button("Toggle Visibility", id="cust-icon-vis", classes="cct-btn-sm"))
            row2.mount(Button("Reset", id="cust-icon-reset", classes="cct-btn-sm"))

        def _render_header(self, container):
            if not self._manager: return
            hdr = self._manager.get_layout().get("header", {})
            card = self._card(container, "Header", f"Height: {hdr.get('height',3)} lines")
            row = Horizontal(classes="cust-row")
            card.mount(row)
            row.mount(Static("Height:", classes="cust-label")); row.mount(Input(value=str(hdr.get("height",3)), id="cust-header-height"))
            row.mount(Switch(value=bool(hdr.get("logo_visible",True)), id="cust-header-logo-vis"))
            row.mount(Static("Logo visible", classes="cust-label"))
            row.mount(Button("Apply", id="cust-header-apply", variant="primary", classes="cct-btn-sm"))

        def _render_menu(self, container):
            if not self._manager: return
            mm = self._manager.get_main_menu()
            card = self._card(container, "Main Menu", "Order & toggles")
            for idx,item in enumerate(mm.get("order", [])):
                r = Horizontal(classes="cust-drag-row")
                card.mount(r)
                r.mount(Static(f"{idx+1}. {item}", classes="cust-drag-label"))
                r.mount(Button("↑", id=f"cust-menu-up-{item}", classes="cct-btn-sm"))
                r.mount(Button("↓", id=f"cust-menu-down-{item}", classes="cct-btn-sm"))
                r.mount(Switch(value=mm.get("visibility", {}).get(item,True), id=f"cust-mmvis-{item}"))

        def _render_spacing(self, container):
            if not self._manager: return
            styles = self._manager.get_styles()
            card = self._card(container, "Spacing & Borders", "Padding · margin · borders")
            spacing = styles.get("spacing", {})
            row = Horizontal(classes="cust-row")
            card.mount(row)
            row.mount(Static("Padding:", classes="cust-label")); row.mount(Input(value=str(spacing.get("padding",1)), id="cust-spacing-pad"))
            row.mount(Static("Margin:", classes="cust-label")); row.mount(Input(value=str(spacing.get("margin",0)), id="cust-spacing-margin"))
            row.mount(Static("Gap:", classes="cust-label")); row.mount(Input(value=str(spacing.get("gap",1)), id="cust-spacing-gap"))
            row.mount(Button("Apply Spacing", id="cust-spacing-apply", variant="primary", classes="cct-btn-sm"))
            borders = styles.get("borders", {})
            row2 = Horizontal(classes="cust-row")
            card.mount(row2)
            row2.mount(Static("Radius:", classes="cust-label")); row2.mount(Input(value=str(borders.get("radius",0)), id="cust-border-radius"))
            border_opts = [("Solid", "solid"), ("Round", "round"), ("Heavy", "heavy"), ("None", "none")]
            cur_style = str(borders.get("style", "solid")).lower()
            valid_styles = [opt[1] for opt in border_opts]
            if cur_style not in valid_styles:
                cur_style = "solid"
            row2.mount(Select(border_opts, value=cur_style, id="cust-border-style", allow_blank=False))
            row2.mount(Button("Apply Borders", id="cust-border-apply", variant="primary", classes="cct-btn-sm"))

        def _render_visibility(self, container):
            card = self._card(container, "Visibility", "Toggle any region · explicit switch")
            if not self._manager: return
            layout = self._manager.get_layout()
            panels_to_show = [
                ("sidebar", "Sidebar"),
                ("chat", "Chat"),
                ("code_editor", "Code Editor"),
                ("terminal", "Terminal"),
                ("header", "Header"),
            ]
            for pid, label in panels_to_show:
                comp = layout.get(pid)
                if not comp: continue
                r = Horizontal(classes="cust-visibility-row")
                card.mount(r)
                pos = comp.get("position", "?")
                r.mount(Static(f"{label} ({pos})", classes="cust-visibility-label"))
                r.mount(Switch(value=bool(comp.get("visible",True)), id=f"cust-vis-{pid}"))

        def _render_profiles(self, container):
            card = self._card(container, "Profiles", "Save / load layouts")
            if not self._manager: return
            pm = self._manager.profile_manager
            active = self._manager.get_config().get("active_profile")
            for name in pm.list_profiles():
                prof = pm.get_profile(name)
                desc = prof.get("description","") if prof else ""
                mark = "★ " if name == active else "  "
                r = Horizontal(classes="cust-drag-row")
                card.mount(r)
                r.mount(Static(f"{mark}{name} — {desc}", classes="cust-drag-label"))
                r.mount(Button("Load", id=f"cust-prof-load-{name}", variant="primary" if name!=active else None, classes="cct-btn-sm"))
                r.mount(Button("Delete", id=f"cust-prof-del-{name}", variant="error", classes="cct-btn-sm"))
            row = Horizontal(classes="cust-field-row")
            card.mount(row)
            row.mount(Input(placeholder="New Profile Name", id="cust-prof-new-name"))
            row.mount(Button("Save", id="cust-prof-save", variant="primary", classes="cct-btn-sm"))
            row2 = Horizontal(classes="cust-field-row")
            card.mount(row2)
            row2.mount(Input(placeholder="Old name", id="cust-prof-rename-old"))
            row2.mount(Input(placeholder="New name", id="cust-prof-rename-new"))
            row2.mount(Button("Rename", id="cust-prof-rename", classes="cct-btn-sm"))

        def _render_editor(self, container):
            card = self._card(container, "Editor", "Visual preview · click preview to cycle")
            if self._manager:
                card.mount(_Preview(self._manager, selected=self._selected_panel))
                card.mount(Static(f"Selected: [b]{self._selected_panel}[/]", classes="cust-hint"))
                row = Horizontal(classes="cust-row")
                for pos in ["left","right","top","bottom","floating","center"]:
                    row.mount(Button(pos.title(), id=f"cust-edit-{pos}", classes="cct-btn-sm"))
                card.mount(row)
                row2 = Horizontal(classes="cust-row")
                card.mount(row2)
                row2.mount(Button("Hide", id="cust-edit-hide", classes="cct-btn-sm"))
                row2.mount(Button("Show", id="cust-edit-show", classes="cct-btn-sm"))
                row2.mount(Button("Docked", id="cust-edit-docked", classes="cct-btn-sm"))
                row2.mount(Button("Floating", id="cust-edit-floating", classes="cct-btn-sm"))

        def _render_advanced(self, container):
            card = self._card(container, "Advanced JSON", "Edit directly · Validate then Save")
            if not self._manager: return
            import json as _json
            slim = {"layout": self._manager.get_config().get("layout"), "styles": self._manager.get_config().get("styles")}
            txt = _json.dumps(slim, indent=2)
            if _HAS_TEXTAREA:
                ta = TextArea(text=txt[:4000], id="cust-adv-json")
                ta.styles.height = 16; ta.styles.min_height = 8
                card.mount(ta)
            else:
                card.mount(Static(txt[:1500], classes="cust-hint"))
            row = Horizontal(classes="cust-row")
            card.mount(row)
            row.mount(Button("Validate", id="cust-adv-validate", classes="cct-btn-sm"))
            row.mount(Button("Save JSON", id="cust-adv-save", variant="primary", classes="cct-btn-sm"))

        def _render_reset(self, container):
            card = self._card(container, "Reset", "Restore defaults")
            row = Horizontal(classes="cust-row")
            card.mount(row)
            row.mount(Button("Reset Layout", id="cust-reset-layout", classes="cct-btn-sm"))
            row.mount(Button("Reset Panes", id="cust-reset-panes", classes="cct-btn-sm"))
            row2 = Horizontal(classes="cust-row")
            card.mount(row2)
            row2.mount(Button("Reset Appearance", id="cust-reset-appearance", classes="cct-btn-sm"))
            row2.mount(Button("Reset Buttons", id="cust-reset-buttons", classes="cct-btn-sm"))
            row3 = Horizontal(classes="cust-row")
            card.mount(row3)
            row3.mount(Button("Reset Everything", id="cust-reset-everything", variant="error", classes="cct-btn-sm"))

        def _jump(self, sec):
            self._nav_state = sec
            self._rebuild_nav()
            self._render_section_view()

        def on_input_changed(self, event):
            if getattr(event.input, "id", "") == "cust-search-input":
                self._search_query = event.value
                self._rebuild_nav()
        def on_input_submitted(self, event):
            if getattr(event.input, "id", "") == "cust-prof-new-name":
                name = event.value.strip()
                if name:
                    ok,msg = self._manager.profile_manager.save_profile(name)
                    self._show_status(msg, "success" if ok else "error")
                    self._refresh_all()
                    event.input.value = ""
        def on_button_pressed(self, event):
            bid = event.button.id or ""
            if bid in ("cust-close","cust-close2","cust-close3"):
                self.dismiss(None); return
            if bid=="cust-open-ext":
                try:
                    self.dismiss(None)
                    from .extensions_panel import ExtensionsPanel
                    self.app.push_screen(ExtensionsPanel())
                except Exception:
                    self.dismiss(None)
                return
            if bid.startswith("cust-nav-"):
                self._set_nav(bid.replace("cust-nav-","")); return
            if bid.startswith("cust-jump-"):
                self._jump(bid.replace("cust-jump-","")); return
            if bid.startswith("cust-sel-"):
                self._selected_panel = bid.replace("cust-sel-", "")
                self._pos_panel = self._selected_panel
                self._size_panel = self._selected_panel
                self._dock_panel = self._selected_panel
                self._on_preview_select(self._selected_panel)
                return
            if bid.startswith("cust-order-up-"):
                cid = bid.replace("cust-order-up-","")
                try:
                    all_ordered = [c["id"] for c in self._manager.get_ordered_components()]
                    seen = set()
                    unique_ordered = []
                    for k in all_ordered:
                        canon = "code_editor" if k in ("editor", "code_editor") else ("sidebar" if k in ("sidebar", "file_explorer") else k)
                        if canon not in seen:
                            seen.add(canon)
                            unique_ordered.append(k)
                    idx = unique_ordered.index(cid)
                    if idx > 0:
                        unique_ordered[idx], unique_ordered[idx-1] = unique_ordered[idx-1], unique_ordered[idx]
                        ok, msg = self._manager.set_order(unique_ordered)
                        self._show_status(msg, "success" if ok else "error")
                        self._live_apply()
                        self.call_after_refresh(self._render_section_view)
                except Exception as e:
                    self._show_error(str(e))
                return
            if bid.startswith("cust-order-down-"):
                cid = bid.replace("cust-order-down-","")
                try:
                    all_ordered = [c["id"] for c in self._manager.get_ordered_components()]
                    seen = set()
                    unique_ordered = []
                    for k in all_ordered:
                        canon = "code_editor" if k in ("editor", "code_editor") else ("sidebar" if k in ("sidebar", "file_explorer") else k)
                        if canon not in seen:
                            seen.add(canon)
                            unique_ordered.append(k)
                    idx = unique_ordered.index(cid)
                    if idx < len(unique_ordered) - 1:
                        unique_ordered[idx], unique_ordered[idx+1] = unique_ordered[idx+1], unique_ordered[idx]
                        ok, msg = self._manager.set_order(unique_ordered)
                        self._show_status(msg, "success" if ok else "error")
                        self._live_apply()
                        self.call_after_refresh(self._render_section_view)
                except Exception as e:
                    self._show_error(str(e))
                return
            if bid.startswith("cust-order-vis-"):
                cid = bid.replace("cust-order-vis-","")
                try:
                    comp = self._manager.get_component(cid)
                    cur_vis = comp.get("visible", True) if comp else True
                    ok, msg = self._manager.set_visibility(cid, not cur_vis)
                    self._show_status(msg, "success" if ok else "error")
                    self._live_apply()
                    self.call_after_refresh(self._render_section_view)
                except Exception as e:
                    self._show_error(str(e))
                return
            if bid.startswith("cust-pospick-"):
                pid = bid.replace("cust-pospick-","")
                self._pos_panel = pid
                self._show_status(f"Selected {pid}", "success")
                self.call_after_refresh(self._render_section_view)
                return
            if bid.startswith("cust-pos-"):
                try:
                    pos = bid.replace("cust-pos-","")
                    pid = self._pos_panel
                    if pos in _POSITION_OPTS:
                        ok,msg=self._manager.set_position(pid,pos)
                        self._show_status(msg, "success" if ok else "error")
                        try:
                            for p in self.query(_Preview):
                                p.refresh_preview()
                        except Exception:
                            pass
                except Exception as e:
                    self._show_error(str(e))
                return
            if bid.startswith("cust-hdr-"):
                try:
                    rest=bid.replace("cust-hdr-","")
                    for key in ["logo_position","title_position","alignment"]:
                        if rest.startswith(key+"-"):
                            opt=rest[len(key)+1:]
                            ok,msg=self._manager.set_header_config(**{key:opt})
                            self._show_status(msg, "success" if ok else "error"); self._live_apply(); break
                except Exception as e:
                    self._show_error(str(e))
                return
            if bid.startswith("cust-dockpick-"):
                pid = bid.replace("cust-dockpick-","")
                self._dock_panel = pid
                self._show_status(f"Selected {pid}", "success")
                self.call_after_refresh(self._render_section_view)
                return
            if bid.startswith("cust-dock-"):
                try:
                    rest=bid.replace("cust-dock-","")
                    for pid in _PANEL_IDS+["header"]:
                        if rest.startswith(pid+"-"):
                            state=rest[len(pid)+1:]
                            ok,msg=self._manager.set_dock_state(pid,state)
                            self._show_status(msg, "success" if ok else "error"); self._live_apply(); break
                except Exception as e:
                    self._show_error(str(e))
                return
            if bid.startswith("cust-sizepick-"):
                pid = bid.replace("cust-sizepick-","")
                self._size_panel = pid
                self._show_status(f"Selected {pid}", "success")
                self.call_after_refresh(self._render_section_view)
                return
            if bid.startswith("cust-size-apply-"):
                pid=bid.replace("cust-size-apply-","")
                try:
                    w=_safe_query(self, f"#cust-w-{pid}", Input)
                    h=_safe_query(self, f"#cust-h-{pid}", Input)
                    ok,msg=self._manager.set_size(pid, (w.value.strip() if w and w.value.strip() else None), (h.value.strip() if h and h.value.strip() else None))
                    self._show_status(msg, "success" if ok else "error"); self._live_apply()
                except Exception as e:
                    self._show_error(str(e))
                return
            if bid.startswith("cust-size-pct-"):
                try:
                    rest=bid.replace("cust-size-pct-","")
                    for pid in _PANEL_IDS:
                        if rest.startswith(pid+"-"):
                            pct=rest[len(pid)+1:]
                            ok,msg=self._manager.set_size(pid, width=int(pct))
                            self._show_status(msg, "success" if ok else "error"); self._live_apply(); break
                except Exception as e:
                    self._show_error(str(e))
                return
            if bid.startswith("cust-size-auto-"):
                pid=bid.replace("cust-size-auto-","")
                ok,msg=self._manager.set_size(pid, width="auto")
                self._show_status(msg, "success" if ok else "error"); self._live_apply(); return
            if bid.startswith("cust-btn-shape-"):
                ok,msg=self._manager.style_manager.set_button_style(shape=bid.replace("cust-btn-shape-",""))
                self._show_status(msg, "success" if ok else "error"); self._live_apply(); return
            if bid.startswith("cust-btn-size-"):
                ok,msg=self._manager.style_manager.set_button_style(size=bid.replace("cust-btn-size-",""))
                self._show_status(msg, "success" if ok else "error"); self._live_apply(); return
            if bid=="cust-btn-apply":
                try:
                    kwargs={}
                    for fid,key in [("cust-btn-radius","border_radius"),("cust-btn-padding","padding")]:
                        w=_safe_query(self, f"#{fid}", Input)
                        if w and w.value.strip():
                            kwargs[key]=int(w.value.strip())
                    if kwargs:
                        ok,msg=self._manager.style_manager.set_button_style(**kwargs)
                        self._show_status(msg, "success" if ok else "error"); self._live_apply()
                except Exception as e:
                    self._show_error(str(e))
                return
            if bid.startswith("cust-icon-size-"):
                ok,msg=self._manager.style_manager.set_icon_style(size=bid.replace("cust-icon-size-",""))
                self._show_status(msg, "success" if ok else "error"); self._live_apply(); return
            if bid=="cust-icon-vis":
                cur=self._manager.get_styles().get("icons", {}).get("visible",True)
                ok,msg=self._manager.style_manager.set_icon_style(visible=not cur)
                self._show_status(msg, "success" if ok else "error"); self._live_apply(); return
            if bid=="cust-icon-reset":
                ok,msg=self._manager.style_manager.set_icon_style(size="medium", visible=True)
                self._show_status("Icons reset", "success" if ok else "error"); self._live_apply(); return
            if bid=="cust-header-apply":
                try:
                    kwargs={}
                    w=_safe_query(self, "#cust-header-height", Input)
                    if w and w.value.strip(): kwargs["height"]=int(w.value.strip())
                    w=_safe_query(self, "#cust-header-logo-vis", Switch)
                    if w is not None: kwargs["logo_visible"]=bool(w.value)
                    ok,msg=self._manager.set_header_config(**kwargs)
                    self._show_status(msg, "success" if ok else "error"); self._live_apply()
                except Exception as e:
                    self._show_error(str(e))
                return
            if bid.startswith("cust-menu-up-"):
                item=bid.replace("cust-menu-up-","")
                try:
                    mm=self._manager.get_main_menu(); order=list(mm.get("order",[])); idx=order.index(item)
                    if idx>0:
                        order[idx],order[idx-1]=order[idx-1],order[idx]
                        ok,msg=self._manager.set_main_menu_config(order=order)
                        self._show_status(msg, "success" if ok else "error"); self._live_apply()
                except Exception as e:
                    self._show_error(str(e))
                return
            if bid.startswith("cust-menu-down-"):
                item=bid.replace("cust-menu-down-","")
                try:
                    mm=self._manager.get_main_menu(); order=list(mm.get("order",[])); idx=order.index(item)
                    if idx < len(order)-1:
                        order[idx],order[idx+1]=order[idx+1],order[idx]
                        ok,msg=self._manager.set_main_menu_config(order=order)
                        self._show_status(msg, "success" if ok else "error"); self._live_apply()
                except Exception as e:
                    self._show_error(str(e))
                return
            if bid=="cust-spacing-apply":
                try:
                    kwargs={}
                    for fid,key in [("cust-spacing-pad","padding"),("cust-spacing-margin","margin"),("cust-spacing-gap","gap")]:
                        w=_safe_query(self, f"#{fid}", Input)
                        if w and w.value.strip():
                            kwargs[key]=int(w.value.strip())
                    if kwargs:
                        ok,msg=self._manager.style_manager.set_spacing(**kwargs)
                        self._show_status(msg, "success" if ok else "error"); self._live_apply()
                except Exception as e:
                    self._show_error(str(e))
                return
            if bid=="cust-border-apply":
                try:
                    kwargs={}
                    w=_safe_query(self, "#cust-border-radius", Input)
                    if w and w.value.strip(): kwargs["radius"]=int(w.value.strip())
                    w=_safe_query(self, "#cust-border-style", Select)
                    if w and w.value: kwargs["style"]=w.value
                    ok,msg=self._manager.style_manager.set_borders(**kwargs)
                    self._show_status(msg, "success" if ok else "error"); self._live_apply()
                except Exception as e:
                    self._show_error(str(e))
                return
            if bid.startswith("cust-prof-load-"):
                ok,msg=self._manager.profile_manager.load_profile(bid.replace("cust-prof-load-",""))
                self._show_status(msg, "success" if ok else "error"); self._live_apply(); return
            if bid.startswith("cust-prof-del-"):
                name=bid.replace("cust-prof-del-","")
                self.app.push_screen(_ConfirmScreen(f"Delete '{name}'?", f"Delete profile '{name}' permanently."), lambda c: self._on_prof_delete(name,c))
                return
            if bid=="cust-prof-save":
                try:
                    inp=_safe_query(self, "#cust-prof-new-name", Input)
                    name=inp.value.strip() if inp else ""
                    if not name:
                        self._show_error("Enter name"); return
                    ok,msg=self._manager.profile_manager.save_profile(name)
                    self._show_status(msg, "success" if ok else "error"); self._live_apply()
                    if inp: inp.value=""
                except Exception as e:
                    self._show_error(str(e))
                return
            if bid=="cust-prof-rename":
                try:
                    o=_safe_query(self, "#cust-prof-rename-old", Input)
                    n=_safe_query(self, "#cust-prof-rename-new", Input)
                    old=o.value.strip() if o else ""; new=n.value.strip() if n else ""
                    if not old or not new:
                        self._show_error("Enter both names"); return
                    ok,msg=self._manager.profile_manager.rename_profile(old,new)
                    self._show_status(msg, "success" if ok else "error"); self._live_apply()
                except Exception as e:
                    self._show_error(str(e))
                return
            if bid.startswith("cust-edit-"):
                act=bid.replace("cust-edit-","")
                pid=self._selected_panel
                if act in ("left","right","top","bottom","floating","center","docked"):
                    ok,msg=self._manager.set_position(pid,act)
                    self._show_status(msg, "success" if ok else "error"); self._live_apply()
                elif act=="hide":
                    ok,msg=self._manager.set_visibility(pid,False)
                    self._show_status(msg, "success" if ok else "error"); self._live_apply()
                elif act=="show":
                    ok,msg=self._manager.set_visibility(pid,True)
                    self._show_status(msg, "success" if ok else "error"); self._live_apply()
                return
            if bid=="cust-adv-validate":
                try:
                    ta=_safe_query(self, "#cust-adv-json", TextArea) if _HAS_TEXTAREA else None
                    if ta:
                        import json as _json
                        _json.loads(ta.text)
                        self._show_status("JSON valid", "success")
                    else:
                        self._show_error("Editor not available")
                except Exception as e:
                    self._show_error(f"Invalid: {e}")
                return
            if bid=="cust-adv-save":
                try:
                    ta=_safe_query(self, "#cust-adv-json", TextArea) if _HAS_TEXTAREA else None
                    if not ta:
                        self._show_error("Editor not available"); return
                    import json as _json
                    data=_json.loads(ta.text)
                    cfg=self._manager.get_config()
                    if "layout" in data: cfg["layout"].update(data["layout"])
                    if "styles" in data:
                        for k,v in data["styles"].items():
                            if isinstance(v,dict) and k in cfg["styles"]: cfg["styles"][k].update(v)
                            else: cfg["styles"][k]=v
                    ok=self._manager._persist(cfg)
                    self._show_status("Saved" if ok else "Failed", "success" if ok else "error"); self._live_apply()
                except Exception as e:
                    self._show_error(str(e))
                return
            if bid in ("cust-reset-layout","cust-reset-current"):
                ok,msg=self._manager.reset_current_layout()
                self._show_status(msg, "success" if ok else "error"); self._live_apply(); return
            if bid=="cust-reset-panes":
                ok,msg=self._manager.reset_pane_positions()
                self._show_status(msg, "success" if ok else "error"); self._live_apply(); return
            if bid=="cust-reset-appearance":
                ok,msg=self._manager.reset_appearance()
                self._show_status(msg, "success" if ok else "error"); self._live_apply(); return
            if bid=="cust-reset-buttons":
                ok,msg=self._manager.reset_buttons()
                self._show_status(msg, "success" if ok else "error"); self._live_apply(); return
            if bid=="cust-reset-everything" or bid=="cust-reset-all":
                self.app.push_screen(_ConfirmScreen("Reset Everything?", "Reset ALL customization to defaults? Cannot be undone.", True), self._on_reset_everything)
                return

        def _on_prof_delete(self, name, confirmed):
            if not confirmed: return
            ok,msg=self._manager.profile_manager.delete_profile(name)
            self._show_status(msg, "success" if ok else "error"); self._live_apply()
        def _on_reset_everything(self, confirmed):
            if not confirmed: return
            ok,msg=self._manager.reset_everything()
            self._show_status(msg, "success" if ok else "error"); self._live_apply()

        def on_select_changed(self, event):
            sid = getattr(event.select, "id", "") or ""
            if sid == "cust-pos-select":
                self._pos_panel = event.value
                self.call_after_refresh(self._render_section_view)
            elif sid == "cust-size-select":
                self._size_panel = event.value
                self.call_after_refresh(self._render_section_view)
            elif sid == "cust-dock-select":
                self._dock_panel = event.value
                self.call_after_refresh(self._render_section_view)
        def on_switch_changed(self, event):
            sid=getattr(event.switch, "id", "") or ""
            if sid.startswith("cust-vis-"):
                pid=sid.replace("cust-vis-","")
                ok,msg=self._manager.set_visibility(pid, bool(event.value))
                self._show_status(msg, "success" if ok else "error"); self._live_apply()
            elif sid.startswith("cust-mmvis-"):
                item=sid.replace("cust-mmvis-","")
                try:
                    mm=self._manager.get_main_menu()
                    vis=dict(mm.get("visibility",{}))
                    vis[item]=bool(event.value)
                    ok,msg=self._manager.set_main_menu_config(visibility=vis)
                    self._show_status(msg, "success" if ok else "error"); self._live_apply()
                except Exception as e:
                    self._show_error(str(e))
            elif sid=="cust-header-logo-vis":
                ok,msg=self._manager.set_header_config(logo_visible=bool(event.value))
                self._show_status(msg, "success" if ok else "error"); self._live_apply()
        def action_cancel(self):
            self.dismiss(None)
        def on_key(self, event):
            if event.key=="escape":
                self.dismiss(None)

    class _ConfirmScreen(Screen):
        CSS = """
        _ConfirmScreen { align: center middle; background: $app-background 70%; }
        #confirm-box { width: 60; max-width: 96%; height: auto; background: $surface; border: round $border; padding: 1 2; }
        #confirm-title { color: $warning; text-style: bold; height: 1; }
        #confirm-msg { color: $text; height: auto; padding: 1 0; }
        #confirm-btns { height: 3; align: center middle; }
        #confirm-btns Button { margin: 0 1; min-width: 12; }
        """
        def __init__(self, title, msg, is_destructive=False):
            super().__init__()
            self._title=title; self._msg=msg; self._destructive=is_destructive
        def compose(self):
            with Vertical(id="confirm-box"):
                yield Static(self._title, id="confirm-title")
                yield Static(self._msg, id="confirm-msg")
                with Horizontal(id="confirm-btns"):
                    yield Button("Cancel", id="confirm-cancel")
                    yield Button("Confirm", id="confirm-ok", variant="error" if self._destructive else "primary")
        def on_button_pressed(self, event):
            self.dismiss(event.button.id=="confirm-ok")
        def on_key(self, event):
            if event.key=="escape":
                self.dismiss(False)

else:
    CustomizationPanel=None
    _ConfirmScreen=None
