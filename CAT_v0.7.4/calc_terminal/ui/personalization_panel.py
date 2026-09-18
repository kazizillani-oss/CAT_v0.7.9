"""
CCT UI — PersonalizationPanel (v0.7.8.1 full redesign).

Professional management screen for AI personalization profiles
(calc_terminal/ai_personalization.py). The Main Menu's "Personalize"
destination routes here.

Layout (per the v0.7.8.1 spec):
  left  — profile list (name · tone · active badge · last modified)
          + New / Duplicate / Delete / Set Active
  right — the full editor: Name, Description, Tone, Temperature,
          Top P, System prompt rules, Creativity, Reasoning,
          Response Length, Memory Preference
  footer — Active Profile · Last Modified · Provider (model label)

Honesty note: temperature, top_p, tone and the system prompt rules
are applied for real (temperature/top_p reach the provider payloads;
tone + rules reach every system prompt). Creativity, Reasoning,
Response Length and Memory Preference are stored as profile metadata
and surfaced here + in the dashboard — they describe the profile for
future wiring and are never fake "settings" that do nothing silently.
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
    from textual.widgets import Static, Button, Input
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False

if TEXTUAL_AVAILABLE:
    from .. import ai_personalization as ap
    from . import theme_css

    _TONE_BTNS = (
        ("balanced", "Balanced"),
        ("concise", "Concise"),
        ("detailed", "Detailed"),
        ("playful", "Playful"),
        ("formal", "Formal"),
    )

    _SEG_BTNS = {
        "pp-reasoning": (("low", "Low"), ("medium", "Medium"), ("high", "High")),
        "pp-length": (("short", "Short"), ("medium", "Medium"), ("long", "Long")),
        "pp-memory": (("auto", "Auto"), ("on", "On"), ("off", "Off")),
    }


    class _ProfileRow(Static):
        """One row of the profile list: name · tone · active badge · last modified."""

        def __init__(self, index, profile, selected=False):
            self.index = index
            self.profile = profile
            super().__init__("", classes="pp-row" + (" pp-row-sel" if selected else ""))
            self._redraw()

        def _redraw(self):
            name = self.profile.get("name") or "?"
            tone = self.profile.get("tone") or "balanced"
            active = self.profile.get("_active")
            updated = self.profile.get("updated_at") or 0
            when = time.strftime("%Y-%m-%d", time.localtime(updated)) if updated else "\u2014"
            badge = ""
            if active:
                badge = f" [{theme_css.current_hex('accent')}]\u2605 active[/]"
            sel = " \u25b8" if "pp-row-sel" in self.classes else ""
            self.update(
                f"  [{theme_css.current_hex('text')}]{name}[/]{badge}{sel}\n"
                f"    [{theme_css.current_hex('text-faint')}]{tone} \u00b7 modified {when}[/]")

        def set_selected(self, selected):
            self.set_class(selected, "pp-row-sel")
            self._redraw()


    class PersonalizationPanel(Screen):
        """Manage AI personalization profiles: create, edit, duplicate,
        delete, pick the active one — clean ChatGPT-style layout."""

        CSS = """
        PersonalizationPanel { align: center middle; background: $app-background 70%; }
        #pp-box {
            width: 90; max-width: 95%; height: auto; max-height: 38;
            background: $surface; border: round $border; padding: 0;
            opacity: 0; offset-y: 1;
            transition: opacity 150ms, offset 180ms;
            layout: vertical;
        }
        #pp-box.open { opacity: 1; offset-y: 0; }
        #pp-titlebar {
            height: 3; min-height: 3; padding: 1 2 0 2;
            border-bottom: solid $border;
        }
        #pp-title { text-style: bold; width: 1fr; }
        #pp-subtitle { color: $text-faint; height: 1; min-height: 1; padding: 0 2; }
        #pp-body { height: 1fr; min-height: 0; layout: horizontal; }
        #pp-sidebar { width: 24; min-width: 24; height: 100%; padding: 1 0 1 1; }
        #pp-list-scroll { width: 100%; height: 100%; min-height: 0;
                          overflow-y: auto; scrollbar-gutter: stable; }
        .pp-row { height: 2; color: $text-muted; padding: 0 1; border-left: thick transparent; }
        .pp-row-sel { color: $text; border-left: thick $accent; }
        .pp-empty { color: $text-faint; padding: 2 1; }
        #pp-edit { width: 1fr; height: 100%; min-height: 0; padding: 1 2;
                   overflow-y: auto; scrollbar-gutter: stable;
                   scrollbar-size-vertical: 1; scrollbar-size-horizontal: 0;
                   border-left: solid $border; }
        .pp-seg { color: $accent; height: auto; min-height: 1; padding-top: 1;
                  border-top: solid $border; margin-top: 1; }
        .pp-field { height: auto; min-height: 1; margin-bottom: 1; }
        .pp-flbl { color: $text-faint; height: 1; min-height: 1; }
        #pp-tone-row { height: 3; min-height: 3; padding: 0; }
        #pp-tone-row Button { margin-right: 1; }
        #pp-reasoning, #pp-length, #pp-memory { height: 3; min-height: 3; padding: 0; }
        #pp-reasoning Button, #pp-length Button, #pp-memory Button { margin-right: 1; }
        #pp-btns {
            height: auto; min-height: 3; padding: 1 2;
            border-top: solid $border;
        }
        #pp-btns-left { width: 1fr; }
        #pp-btns-left Button { margin-right: 1; }
        #pp-btns-right Button { margin-left: 1; }
        #pp-hint { color: $text-faint; height: 1; min-height: 1; padding: 0 2; }
        """

        BINDINGS = [
            Binding("escape", "cancel", "Cancel"),
            Binding("down", "move_down_sel", "Next profile"),
            Binding("up", "move_up_sel", "Previous profile"),
            Binding("page_down", "page_down_edit", "Page down"),
            Binding("page_up", "page_up_edit", "Page up"),
            Binding("home", "home_edit", "Top of form"),
            Binding("end", "end_edit", "Bottom of form"),
        ]

        def __init__(self):
            super().__init__()
            self._profiles = ap.profiles()
            self._active = ap.load_profiles().get("active", "")
            self._selected = 0

        def compose(self):
            with Vertical(id="pp-box"):
                with Horizontal(id="pp-titlebar"):
                    yield Static("\u2726  Personalize", id="pp-title")
                    yield Button("\u2715", id="pp-close", classes="cct-popup-close")
                yield Static(
                    "Customize how the AI responds to you \u00b7 tone, style, behavior.",
                    id="pp-subtitle")
                with Horizontal(id="pp-body"):
                    with Vertical(id="pp-sidebar"):
                        yield Static("My Profiles", classes="pp-seg")
                        yield ScrollableContainer(id="pp-list-scroll")
                    with ScrollableContainer(id="pp-edit"):
                        yield Static("Profile Settings", classes="pp-seg")
                        with Vertical(classes="pp-field"):
                            yield Static("Name", classes="pp-flbl")
                            yield Input(id="pp-name", placeholder="Profile name")
                        with Vertical(classes="pp-field"):
                            yield Static("What should the AI know about you?", classes="pp-flbl")
                            yield Input(id="pp-desc", placeholder="e.g. I'm a software engineer")
                        yield Static("Tone", classes="pp-seg")
                        with Horizontal(id="pp-tone-row"):
                            for tone, label in _TONE_BTNS:
                                yield Button(label, id=f"pp-tone-{tone}", classes="cct-btn cct-btn-sm")
                        yield Static("Model Parameters", classes="pp-seg")
                        with Horizontal():
                            with Vertical(classes="pp-field"):
                                yield Static("Reasoning", classes="pp-flbl")
                                with Horizontal(id="pp-reasoning"):
                                    for key, label in _SEG_BTNS["pp-reasoning"]:
                                        yield Button(label, id=f"pp-reasoning-{key}",
                                                     classes="cct-btn cct-btn-sm")
                            with Vertical(classes="pp-field"):
                                yield Static("Length", classes="pp-flbl")
                                with Horizontal(id="pp-length"):
                                    for key, label in _SEG_BTNS["pp-length"]:
                                        yield Button(label, id=f"pp-length-{key}",
                                                     classes="cct-btn cct-btn-sm")
                        with Horizontal():
                            with Vertical(classes="pp-field"):
                                yield Static("Temperature (0\u20132)", classes="pp-flbl")
                                yield Input(id="pp-temp", placeholder="0.7")
                            with Vertical(classes="pp-field"):
                                yield Static("Top P (0\u20131)", classes="pp-flbl")
                                yield Input(id="pp-topp", placeholder="0.9")
                        yield Static("Behavior", classes="pp-seg")
                        with Vertical(classes="pp-field"):
                            yield Static("Memory", classes="pp-flbl")
                            with Horizontal(id="pp-memory"):
                                for key, label in _SEG_BTNS["pp-memory"]:
                                    yield Button(label, id=f"pp-memory-{key}",
                                                 classes="cct-btn cct-btn-sm")
                        with Vertical(classes="pp-field"):
                            yield Static("Custom instructions", classes="pp-flbl")
                            yield Input(id="pp-additions", placeholder="e.g. always use SI units")
                        with Horizontal():
                            with Vertical(classes="pp-field"):
                                yield Static("Creativity (0\u20131)", classes="pp-flbl")
                                yield Input(id="pp-creativity", placeholder="0.7")
                            with Vertical(classes="pp-field"):
                                yield Static("Provider / Model", classes="pp-flbl")
                                yield Input(id="pp-model", placeholder="gpt-4o-cct")
                with Horizontal(id="pp-btns"):
                    with Horizontal(id="pp-btns-left"):
                        yield Button(" + New ", id="pp-new", classes="cct-btn cct-btn-sm")
                        yield Button(" Duplicate ", id="pp-duplicate", classes="cct-btn cct-btn-sm")
                        yield Button(" Delete ", id="pp-delete", variant="error", classes="cct-btn cct-btn-sm")
                        yield Button(" Set Active ", id="pp-active", classes="cct-btn cct-btn-sm")
                    with Horizontal(id="pp-btns-right"):
                        yield Button(" Save ", id="pp-save", variant="primary", classes="cct-btn cct-btn-sm")
                        yield Button(" Cancel ", id="pp-cancel", classes="cct-btn cct-btn-sm")
                yield Static("Up/Down navigate  \u00b7  Esc close", id="pp-hint")

        # ------------------------------------------------------------ rows
        def _rows(self):
            self._profiles = ap.profiles()
            active = self._active
            out = []
            for i, prof in enumerate(self._profiles):
                p = dict(prof)
                p["_active"] = p.get("name") == active
                out.append(_ProfileRow(i, p, selected=(i == self._selected)))
            return out

        def _rebuild_list(self):
            try:
                scroll = self.query_one("#pp-list-scroll", ScrollableContainer)
                scroll.remove_children()
                rows = self._rows()
                if not rows:
                    scroll.mount(Static("No profiles \u2014 create one.", classes="pp-empty"))
                else:
                    for row in rows:
                        scroll.mount(row)
                self._sync_form()
            except Exception:
                pass

        def _fit(self):
            """No-op: CSS handles layout with fixed height."""
            pass

        def _sync_form(self):
            prof = self._profiles[self._selected] if self._profiles else {}
            self.query_one("#pp-name", Input).value = prof.get("name", "")
            self.query_one("#pp-desc", Input).value = prof.get("description", "")
            self.query_one("#pp-temp", Input).value = (
                "" if prof.get("temperature") is None else str(prof.get("temperature")))
            self.query_one("#pp-topp", Input).value = (
                "" if prof.get("top_p") is None else str(prof.get("top_p")))
            self.query_one("#pp-additions", Input).value = prof.get("additions", "")
            self.query_one("#pp-creativity", Input).value = (
                "" if prof.get("creativity") is None else str(prof.get("creativity")))
            self.query_one("#pp-model", Input).value = prof.get("model", "")
            tone = prof.get("tone") or "balanced"
            for btone, _ in _TONE_BTNS:
                self._set_seg(f"#pp-tone-{btone}", btone == tone)
            seg_defaults = {
                "pp-reasoning": prof.get("reasoning") or "medium",
                "pp-length": prof.get("response_length") or "medium",
                "pp-memory": prof.get("memory_pref") or "auto",
            }
            for row_id, chosen in seg_defaults.items():
                for key, _label in _SEG_BTNS[row_id]:
                    self._set_seg(f"#{row_id}-{key}", key == chosen)

        def _set_seg(self, btn_id, on):
            try:
                self.query_one(btn_id, Button).variant = "primary" if on else "default"
            except Exception:
                pass

        def _seg_value(self, row_id):
            for key, _label in _SEG_BTNS[row_id]:
                btn = self.query_one(f"#{row_id}-{key}", Button)
                if btn.variant == "primary":
                    return key
            return _SEG_BTNS[row_id][1][0]

        # ------------------------------------------------------- selection
        def _editing(self):
            """True when keyboard focus sits inside the editor column —
            Up/Down then scroll the form instead of switching profiles
            (a stray Down in the Name field must never change the
            selected profile and wipe the form)."""
            focused = self.focused
            if focused is None:
                return False
            try:
                return self.query_one("#pp-edit").is_ancestor_of(focused)
            except Exception:
                return False

        def _edit_scroll(self):
            try:
                return self.query_one("#pp-edit")
            except Exception:
                return None

        def action_move_down_sel(self):
            if self._editing():
                scroll = self._edit_scroll()
                if scroll is not None and scroll.max_scroll_y > 0:
                    scroll.scroll_down(animate=False)
                return
            if len(self._profiles) > 1:
                self._selected = min(self._selected + 1, len(self._profiles) - 1)
                self._rebuild_list()

        def action_move_up_sel(self):
            if self._editing():
                scroll = self._edit_scroll()
                if scroll is not None:
                    scroll.scroll_up(animate=False)
                return
            self._selected = max(self._selected - 1, 0)
            self._rebuild_list()

        def action_page_down_edit(self):
            scroll = self._edit_scroll()
            if scroll is not None:
                scroll.scroll_page_down(animate=False)

        def action_page_up_edit(self):
            scroll = self._edit_scroll()
            if scroll is not None:
                scroll.scroll_page_up(animate=False)

        def action_home_edit(self):
            scroll = self._edit_scroll()
            if scroll is not None:
                scroll.scroll_home(animate=False)

        def action_end_edit(self):
            scroll = self._edit_scroll()
            if scroll is not None:
                scroll.scroll_end(animate=False)

        # ---------------------------------------------------------- actions
        def on_mount(self):
            self.call_after_refresh(lambda: self.query_one("#pp-box").add_class("open"))
            self.call_after_refresh(self._rebuild_list)

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)

        def action_cancel(self):
            self.dismiss(None)

        def on_button_pressed(self, event):
            eid = event.button.id
            if eid in ("pp-cancel", "pp-close"):
                self.dismiss(None)
            elif eid == "pp-new":
                self._new_profile()
            elif eid == "pp-duplicate":
                self._duplicate_profile()
            elif eid == "pp-delete":
                self._delete_profile()
            elif eid == "pp-active":
                self._make_active()
            elif eid == "pp-save":
                self._save()
                self.dismiss(None)
            elif eid and eid.startswith("pp-tone-"):
                tone = eid.split("-", 2)[2]
                for btone, _ in _TONE_BTNS:
                    self._set_seg(f"#pp-tone-{btone}", btone == tone)
            elif eid.startswith("pp-reasoning-"):
                self._seg_click("pp-reasoning", eid)
            elif eid.startswith("pp-length-"):
                self._seg_click("pp-length", eid)
            elif eid.startswith("pp-memory-"):
                self._seg_click("pp-memory", eid)

        def _seg_click(self, row_id, eid):
            key = eid.split("-", 2)[2]
            for k, _label in _SEG_BTNS[row_id]:
                self._set_seg(f"#{row_id}-{k}", k == key)

        def _new_profile(self):
            base = dict(ap.DEFAULT_PROFILE)
            base["name"] = self._unique_name("New Profile")
            ap.add_profile(base["name"], tone=base["tone"], additions="",
                           temperature=None, model="")
            self._profiles = ap.profiles()
            self._selected = len(self._profiles) - 1
            self._rebuild_list()

        def _unique_name(self, root):
            names = {p.get("name") for p in self._profiles}
            if root not in names:
                return root
            i = 2
            while f"{root} {i}" in names:
                i += 1
            return f"{root} {i}"

        def _current_prof(self):
            return self._profiles[self._selected] if self._profiles else None

        def _tone_from_buttons(self):
            tone = "balanced"
            for btone, _ in _TONE_BTNS:
                btn = self.query_one(f"#pp-tone-{btone}", Button)
                if btn.variant == "primary":
                    tone = btone
            return tone

        def _duplicate_profile(self):
            prof = self._current_prof()
            if not prof:
                return
            name = self._unique_name(prof.get("name", "Profile") + " Copy")
            ap.add_profile(name, tone=prof.get("tone", "balanced"),
                           additions=prof.get("additions", ""),
                           temperature=prof.get("temperature"),
                           model=prof.get("model", ""),
                           description=prof.get("description", ""),
                           top_p=prof.get("top_p"),
                           creativity=prof.get("creativity"),
                           reasoning=prof.get("reasoning", ""),
                           response_length=prof.get("response_length", ""),
                           memory_pref=prof.get("memory_pref", ""))
            self._profiles = ap.profiles()
            self._selected = len(self._profiles) - 1
            self._rebuild_list()

        def _delete_profile(self):
            # save first so in-panel edits aren't lost on the wrong target
            self._save_silently()
            prof = self._current_prof()
            if not prof:
                return
            ap.delete_profile(prof.get("name", ""))
            if self._active == prof.get("name"):
                self._active = ""
                ap.set_active("")
            self._profiles = ap.profiles()
            self._selected = min(self._selected, max(0, len(self._profiles) - 1))
            self._rebuild_list()

        def _make_active(self):
            prof = self._current_prof()
            if not prof:
                return
            name = prof.get("name", "")
            ap.set_active(name)
            self._active = name
            self._rebuild_list()
            try:
                self.app._system_note(f"\u2726 Personalization: '{name}' is now active.")
            except Exception:
                pass

        def _save(self):
            self._save_silently()
            try:
                self.app._system_note(
                    f"\u2713 Personalization saved \u2014 '{self._active or '(none)'}' is active.")
            except Exception:
                pass

        def _save_silently(self):
            """Persist the current form fields onto the selected profile
            (or create it if the name is brand new)."""
            name = self.query_one("#pp-name", Input).value.strip()
            if not name:
                return
            temp_raw = self.query_one("#pp-temp", Input).value.strip()
            temperature = None
            if temp_raw:
                try:
                    temperature = max(0.0, min(2.0, float(temp_raw)))
                except ValueError:
                    temperature = None
            topp_raw = self.query_one("#pp-topp", Input).value.strip()
            top_p = None
            if topp_raw:
                try:
                    top_p = max(0.0, min(1.0, float(topp_raw)))
                except ValueError:
                    top_p = None
            creat_raw = self.query_one("#pp-creativity", Input).value.strip()
            creativity = None
            if creat_raw:
                try:
                    creativity = max(0.0, min(1.0, float(creat_raw)))
                except ValueError:
                    creativity = None
            additions = self.query_one("#pp-additions", Input).value
            model = self.query_one("#pp-model", Input).value.strip()
            description = self.query_one("#pp-desc", Input).value.strip()
            tone = self._tone_from_buttons()
            ap.add_profile(name, tone=tone, additions=additions,
                           temperature=temperature, model=model,
                           description=description, top_p=top_p,
                           creativity=creativity,
                           reasoning=self._seg_value("pp-reasoning"),
                           response_length=self._seg_value("pp-length"),
                           memory_pref=self._seg_value("pp-memory"))
            self._profiles = ap.profiles()

else:
    PersonalizationPanel = None
