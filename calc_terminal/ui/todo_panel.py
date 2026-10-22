"""
CCT UI — todo_panel.py: AI Todo Manager panel (v0.7.2 roadmap). Real
Screen push over calc_terminal/todos.py's per-workspace JSON store —
add, complete/reopen, delete, search, and filter by status, plus a
live progress bar. Priority is settable at creation (cycles low/
normal/high via a click on the priority badge); due dates and full
in-place text editing are accepted from todos.update_todo() but this
pass's UI only exposes add/toggle/delete/priority-cycle/search/filter
— see the module docstring in todos.py for what's genuinely
implemented vs. deferred.

The roadmap's own mockup nests this under a "Main Menu" (Workspace /
Recent Projects / AI Todo / Settings / Extensions / Documentation)
that doesn't exist anywhere in this codebase yet — header.py's
hamburger glyph is a plain sidebar-visibility toggle, and Settings/
Extensions/Documentation aren't panels here either. Building a whole
new main-menu hierarchy just to host this one panel would be scope
creep well beyond "add a Todo Manager", so this is exposed the same
way TimelinePanel is: a dedicated `/todo` command, following this
codebase's existing pattern for every other panel (/permissions,
/workspace, /model, etc.) rather than a menu system that has no other
reason to exist yet.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

from .. import todos

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Vertical, Horizontal, VerticalScroll
    from textual.screen import Screen
    from textual.widgets import Static, Input, Button, ProgressBar
except Exception:
    TEXTUAL_AVAILABLE = False

_PRIORITY_GLYPH = {"low": "\u25bd", "normal": "\u25cb", "high": "\u25b3"}


if TEXTUAL_AVAILABLE:

    class _TodoRow(Horizontal):
        def __init__(self, todo):
            super().__init__(classes="cct-todo-row")
            self.todo = todo

        def compose(self):
            box = "\u2611" if self.todo["status"] == "done" else "\u2610"
            style = "strike dim" if self.todo["status"] == "done" else ""
            source = " [dim](AI)[/]" if self.todo.get("source") == "ai" else ""
            yield Static(box, classes="cct-todo-check", id=f"cct-todo-check-{self.todo['id']}")
            yield Static(_PRIORITY_GLYPH.get(self.todo["priority"], "\u25cb"),
                         classes="cct-todo-priority", id=f"cct-todo-pri-{self.todo['id']}")
            label = f"[{style}]{self.todo['text']}[/]" if style else self.todo["text"]
            yield Static(label + source, classes="cct-todo-text")
            yield Button("\u2715", classes="cct-todo-delete", id=f"cct-todo-del-{self.todo['id']}")

    class TodoPanel(Screen):
        """AI Todo Manager. `workspace` scopes the list to the currently
        open project (or None for the global/no-folder list) — see
        todos.py's module docstring on why todos are per-workspace."""

        CSS = """
        TodoPanel { align: center middle; background: $app-background 60%; }
        #cct-todo-box {
            width: 84%; height: 80%; background: $surface;
            border: round $border; padding: 1 2;
        }
        #cct-todo-header { height: 1; }
        #cct-todo-progress-row { height: 1; padding: 0 0 1 0; }
        #cct-todo-add-row { height: 3; padding-bottom: 1; }
        #cct-todo-add-row Input { width: 1fr; }
        #cct-todo-filters { height: 1; padding-bottom: 1; }
        #cct-todo-filters Button { margin-right: 1; min-width: 10; }
        #cct-todo-search { margin-bottom: 1; }
        #cct-todo-list { height: 1fr; }
        .cct-todo-row { height: 1; padding: 0 1; }
        .cct-todo-row:hover { color: $accent; }
        .cct-todo-check { width: 3; }
        .cct-todo-priority { width: 3; color: $warning; }
        .cct-todo-text { width: 1fr; }
        .cct-todo-delete { min-width: 3; height: 1; border: none; color: $error; }
        #cct-todo-empty { color: $text-faint; padding: 1; }
        """

        def __init__(self, workspace=None):
            super().__init__()
            self._workspace = workspace
            self._query = ""
            self._filter = "all"  # all | pending | done

        def compose(self):
            with Vertical(id="cct-todo-box"):
                with Horizontal(id="cct-todo-header"):
                    yield Static("[b]AI Todo[/b]")
                    yield Button("Close", id="cct-todo-close")
                with Horizontal(id="cct-todo-progress-row"):
                    yield Static("", id="cct-todo-progress-label")
                    yield ProgressBar(id="cct-todo-progress", show_eta=False)
                with Horizontal(id="cct-todo-add-row"):
                    yield Input(placeholder="Add a task and press Enter\u2026", id="cct-todo-add")
                with Horizontal(id="cct-todo-filters"):
                    yield Button("All", id="cct-todo-filter-all", variant="primary")
                    yield Button("Pending", id="cct-todo-filter-pending")
                    yield Button("Done", id="cct-todo-filter-done")
                yield Input(placeholder="Search\u2026", id="cct-todo-search")
                yield VerticalScroll(id="cct-todo-list")

        def on_mount(self):
            self._render()

        def _render(self):
            frac, done, total = todos.progress(self._workspace)
            self.query_one("#cct-todo-progress-label", Static).update(
                f"{done}/{total} complete" if total else "No tasks yet")
            try:
                self.query_one("#cct-todo-progress", ProgressBar).update(total=1.0, progress=frac)
            except Exception:
                pass
            items = todos.list_todos(self._workspace)
            if self._filter == "pending":
                items = [t for t in items if t["status"] != "done"]
            elif self._filter == "done":
                items = [t for t in items if t["status"] == "done"]
            if self._query:
                q = self._query.lower()
                items = [t for t in items if q in t["text"].lower()]
            box = self.query_one("#cct-todo-list", VerticalScroll)
            for child in list(box.children):
                child.remove()
            if not items:
                box.mount(Static("Nothing here.", id="cct-todo-empty"))
                return
            for t in items:
                box.mount(_TodoRow(t))

        def on_input_submitted(self, event):
            if event.input.id == "cct-todo-add":
                todos.add_todo(event.value, workspace=self._workspace, source="manual")
                event.input.value = ""
                self._render()

        def on_input_changed(self, event):
            if event.input.id == "cct-todo-search":
                self._query = event.value
                self._render()

        def on_button_pressed(self, event):
            bid = event.button.id or ""
            if bid == "cct-todo-close":
                self.dismiss(None)
                return
            if bid.startswith("cct-todo-filter-"):
                self._filter = bid.rsplit("-", 1)[1]
                for b in self.query("#cct-todo-filters Button"):
                    b.variant = "primary" if b.id == bid else "default"
                self._render()
                return
            if bid.startswith("cct-todo-del-"):
                todo_id = int(bid.rsplit("-", 1)[1])
                todos.delete_todo(todo_id, workspace=self._workspace)
                self._render()
                return

        def on_click(self, event):
            widget = getattr(event, "widget", None)
            wid = getattr(widget, "id", "") or ""
            if wid.startswith("cct-todo-check-"):
                todo_id = int(wid.rsplit("-", 1)[1])
                current = next((t for t in todos.list_todos(self._workspace) if t["id"] == todo_id), None)
                if current:
                    new_status = "pending" if current["status"] == "done" else "done"
                    todos.set_status(todo_id, new_status, workspace=self._workspace)
                    self._render()
            elif wid.startswith("cct-todo-pri-"):
                todo_id = int(wid.rsplit("-", 1)[1])
                current = next((t for t in todos.list_todos(self._workspace) if t["id"] == todo_id), None)
                if current:
                    order = ("low", "normal", "high")
                    nxt = order[(order.index(current["priority"]) + 1) % len(order)] \
                        if current["priority"] in order else "normal"
                    todos.update_todo(todo_id, workspace=self._workspace, priority=nxt)
                    self._render()

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)

else:
    TodoPanel = None
