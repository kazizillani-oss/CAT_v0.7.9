"""
CCT UI — memory_center.py: Memory Center panel for viewing and managing
stored memories from memory_v2.MemoryManager. Real Screen push following
the same patterns as todo_panel.py and timeline_panel.py.

Features:
  - Table of all memories with Category, Content (truncated), Importance,
    Confidence, Created, and Actions columns
  - Filter by category dropdown
  - Search box to filter by text content
  - Edit button per row: inline edit mode
  - Delete button per row with confirmation
  - Clear category / Clear all with confirmation
  - Export / Import placeholders
  - Memory stats summary at top
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import json
import time
import os

from .. import memory_v2

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Vertical, Horizontal, VerticalScroll
    from textual.screen import Screen
    from textual.widgets import Static, DataTable, Button, Input, Select, Label
except Exception:
    TEXTUAL_AVAILABLE = False


def _fmt_ts(ts):
    """Format a unix timestamp to a short human-readable string."""
    if not ts:
        return "-"
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
    except Exception:
        return "-"


def _truncate(text, maxlen=60):
    """Truncate text to *maxlen*, adding an ellipsis if needed."""
    text = text.replace("\n", " ")
    if len(text) <= maxlen:
        return text
    return text[: maxlen - 1] + "\u2026"


if TEXTUAL_AVAILABLE:

    class MemoryCenterScreen(Screen):
        """Full-screen panel showing all stored memories with filtering,
        search, edit, delete, clear, and export/import actions."""

        CSS = """
        MemoryCenterScreen { align: center middle; background: $app-background 60%; }
        #cct-mem-box {
            width: 92%; height: 88%; background: $surface;
            border: round $border; padding: 0;
            overflow: hidden;
        }
        .cct-mem-titlebar {
            height: 3; padding: 1 2 0 2;
            border-bottom: solid $border;
        }
        .cct-mem-title { text-style: bold; width: 1fr; color: $text; }
        .cct-mem-close {
            width: 3; min-width: 3; height: 1; padding: 0;
            background: transparent; color: $text-faint; border: none;
        }
        .cct-mem-close:hover { color: $error; }

        #cct-mem-stats {
            height: 3; padding: 0 2; color: $text-muted;
            border-bottom: solid $border;
        }

        #cct-mem-controls {
            height: 3; padding: 1 2; gap: 1;
            border-bottom: solid $border;
        }
        #cct-mem-controls Label { color: $text-faint; width: auto; height: 1; padding-top: 1; }
        #cct-mem-category-filter { width: 28; }
        #cct-mem-search { width: 1fr; }

        #cct-mem-table-wrap { height: 1fr; }
        #cct-mem-table { height: 1fr; }
        #cct-mem-table > DataTable { height: 1fr; }

        .cct-mem-actions {
            height: 3; padding: 0 2; gap: 1;
            border-top: solid $border;
            align-horizontal: right;
        }
        .cct-mem-actions Button { margin-left: 1; }

        #cct-mem-empty {
            color: $text-faint; padding: 2 4; height: 1fr;
            content-align: center middle;
        }

        .cct-mem-edit-row {
            height: 3; padding: 0 2; gap: 1;
            border-top: solid $border;
        }
        .cct-mem-edit-row Input { width: 1fr; }
        .cct-mem-edit-row Button { min-width: 10; }
        """

        CATEGORY_CHOICES = [
            ("All", "__all__"),
            ("User Prefs", "user_preferences"),
            ("Programming Prefs", "programming_preferences"),
            ("Project Prefs", "project_preferences"),
            ("Important Instructions", "important_instructions"),
            ("Workflow Prefs", "workflow_preferences"),
            ("Conversation Facts", "conversation_facts"),
            ("Project Facts", "project_facts"),
            ("Custom", "custom"),
        ]

        def __init__(self):
            super().__init__()
            self._manager = memory_v2.MemoryManager()
            self._filter_category = "__all__"
            self._search_query = ""
            self._memories = []
            self._editing_id = None

        def compose(self):
            with Vertical(id="cct-mem-box"):
                with Horizontal(classes="cct-mem-titlebar"):
                    yield Static("[b]Memory Center[/b]", classes="cct-mem-title")
                    yield Button("\u2715", id="cct-mem-close",
                                 classes="cct-mem-close")
                yield Static("", id="cct-mem-stats")
                with Horizontal(id="cct-mem-controls"):
                    yield Label("Category:")
                    yield Select(self.CATEGORY_CHOICES, value="__all__",
                                 id="cct-mem-category-filter", allow_blank=False)
                    yield Input(placeholder="Search memories\u2026",
                                id="cct-mem-search")
                yield VerticalScroll(id="cct-mem-table-wrap")
                with Horizontal(classes="cct-mem-actions"):
                    yield Button("Export", id="cct-mem-export",
                                 classes="cct-btn-sm")
                    yield Button("Import", id="cct-mem-import",
                                 classes="cct-btn-sm")
                    yield Button("Clear Category", id="cct-mem-clear-cat",
                                 variant="error", classes="cct-btn-sm")
                    yield Button("Clear All", id="cct-mem-clear-all",
                                 variant="error")

        def on_mount(self):
            self._load_memories()

        # ── data loading ──────────────────────────────────────────────

        def _load_memories(self):
            """Load memories from MemoryManager, apply filters, populate table."""
            if self._filter_category == "__all__":
                self._memories = self._manager.get_all_memories()
            else:
                self._memories = self._manager.get_memories_by_category(
                    self._filter_category
                )

            if self._search_query:
                q = self._search_query.lower()
                self._memories = [
                    m for m in self._memories if q in m.content.lower()
                ]

            self._update_stats()
            self._render_table()

        def _update_stats(self):
            """Update the stats summary line."""
            all_mems = self._manager.get_all_memories()
            total = len(all_mems)
            cats = {}
            for m in all_mems:
                cats[m.category] = cats.get(m.category, 0) + 1
            parts = [f"Total: {total}"]
            for cat in sorted(cats):
                short = cat.replace("_", " ").title()
                parts.append(f"{short}: {cats[cat]}")
            shown = len(self._memories)
            if shown != total:
                parts.append(f"Showing: {shown}")
            self.query_one("#cct-mem-stats", Static).update(
                "  ".join(parts)
            )

        def _render_table(self):
            """Populate the DataTable with current memories."""
            wrap = self.query_one("#cct-mem-table-wrap", VerticalScroll)
            for child in list(wrap.children):
                child.remove()

            if not self._memories:
                wrap.mount(Static("No memories stored.", id="cct-mem-empty"))
                return

            table = DataTable(id="cct-mem-table")
            table.add_columns(
                "Category", "Content", "Importance", "Confidence", "Created", "Actions"
            )
            table.cursor_type = "row"

            for mem in self._memories:
                cat_short = mem.category.replace("_", " ").title()
                content_disp = _truncate(mem.content, 55)
                imp = f"{mem.importance:.0%}"
                conf = f"{mem.confidence:.0%}"
                created = _fmt_ts(mem.created_at)
                table.add_row(
                    cat_short, content_disp, imp, conf, created,
                    "",  # actions column — buttons handled via click
                    key=mem.id,
                )

            wrap.mount(table)

            # Mount action buttons for each row after the table
            for mem in self._memories:
                row_bar = Horizontal(classes="cct-mem-row-actions")
                row_bar._mem_id = mem.id
                yield_btn = row_bar.mount  # will call below
                yield_btn(Button("Edit", id=f"cct-mem-edit-{mem.id}",
                                 classes="cct-btn-sm"))
                yield_btn(Button("Del", id=f"cct-mem-del-{mem.id}",
                                 variant="error", classes="cct-btn-sm"))
                wrap.mount(row_bar)

        # ── actions ───────────────────────────────────────────────────

        def action_filter_category(self, category):
            """Filter memories by the selected category."""
            self._filter_category = category
            self._load_memories()

        def action_search(self, query):
            """Search memories by text content."""
            self._search_query = query
            self._load_memories()

        def action_delete_memory(self, memory_id):
            """Delete a memory by id after confirmation."""
            mem = next((m for m in self._memories if m.id == memory_id), None)
            if not mem:
                return
            content_short = _truncate(mem.content, 40)
            self._confirm_action(
                f"Delete memory: \"{content_short}\"?",
                lambda: self._do_delete(memory_id),
            )

        def _do_delete(self, memory_id):
            self._manager.delete_memory(memory_id)
            if self._editing_id == memory_id:
                self._editing_id = None
                self._hide_edit_row()
            self._load_memories()

        def action_edit_memory(self, memory_id):
            """Enter inline edit mode for a memory."""
            mem = next((m for m in self._memories if m.id == memory_id), None)
            if not mem:
                return
            self._editing_id = memory_id
            self._show_edit_row(mem)

        def _show_edit_row(self, mem):
            """Show an inline edit row at the bottom of the panel."""
            self._hide_edit_row()
            wrap = self.query_one("#cct-mem-table-wrap", VerticalScroll)
            edit_row = Horizontal(classes="cct-mem-edit-row", id="cct-mem-edit-row")
            edit_row.mount(Input(value=mem.content, id="cct-mem-edit-input"))
            edit_row.mount(Button("Save", id="cct-mem-edit-save"))
            edit_row.mount(Button("Cancel", id="cct-mem-edit-cancel"))
            wrap.mount(edit_row)

        def _hide_edit_row(self):
            """Remove the inline edit row if present."""
            try:
                row = self.query_one("#cct-mem-edit-row")
                row.remove()
            except Exception:
                pass

        def action_save_edit(self):
            """Save the inline-edited memory content."""
            if not self._editing_id:
                return
            try:
                inp = self.query_one("#cct-mem-edit-input", Input)
                new_content = inp.value.strip()
            except Exception:
                return
            if new_content:
                self._manager.update_memory(self._editing_id, content=new_content)
            self._editing_id = None
            self._hide_edit_row()
            self._load_memories()

        def action_cancel_edit(self):
            """Cancel inline editing."""
            self._editing_id = None
            self._hide_edit_row()

        def action_clear_category(self):
            """Clear all memories in the currently filtered category."""
            if self._filter_category == "__all__":
                self._confirm_action(
                    "Select a specific category before using Clear Category.",
                    None,
                )
                return
            count = len(self._manager.get_memories_by_category(
                self._filter_category
            ))
            cat_name = self._filter_category.replace("_", " ").title()
            self._confirm_action(
                f"Delete all {count} memories in \"{cat_name}\"?",
                lambda: self._do_clear_category(),
            )

        def _do_clear_category(self):
            mems = self._manager.get_memories_by_category(self._filter_category)
            for m in mems:
                self._manager.delete_memory(m.id)
            self._load_memories()

        def action_clear_all(self):
            """Clear every stored memory with confirmation."""
            all_mems = self._manager.get_all_memories()
            count = len(all_mems)
            self._confirm_action(
                f"Delete ALL {count} memories? This cannot be undone.",
                lambda: self._do_clear_all(),
            )

        def _do_clear_all(self):
            mems = self._manager.get_all_memories()
            for m in mems:
                self._manager.delete_memory(m.id)
            self._load_memories()

        def action_export_memories(self):
            """Export all memories to a JSON file (placeholder)."""
            mems = self._manager.get_all_memories()
            data = [m.to_dict() for m in mems]
            out_path = os.path.join(
                os.path.expanduser("~"), ".cct_memory_v2", "export.json"
            )
            try:
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                self.query_one("#cct-mem-stats", Static).update(
                    f"Exported {len(data)} memories to {out_path}"
                )
            except Exception as exc:
                self.query_one("#cct-mem-stats", Static).update(
                    f"Export failed: {exc}"
                )

        def action_import_memories(self):
            """Import memories from a JSON file (placeholder)."""
            in_path = os.path.join(
                os.path.expanduser("~"), ".cct_memory_v2", "export.json"
            )
            if not os.path.isfile(in_path):
                self.query_one("#cct-mem-stats", Static).update(
                    "No import file found at ~/.cct_memory_v2/export.json"
                )
                return
            try:
                with open(in_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                imported = 0
                for entry in data:
                    cat = entry.get("category", "custom")
                    content = entry.get("content", "")
                    if cat in memory_v2.VALID_CATEGORIES and content:
                        self._manager.store_memory(
                            category=cat,
                            content=content,
                            importance=entry.get("importance", 0.5),
                            confidence=entry.get("confidence", 1.0),
                            source=entry.get("source", "import"),
                        )
                        imported += 1
                self._load_memories()
                self.query_one("#cct-mem-stats", Static).update(
                    f"Imported {imported} memories"
                )
            except Exception as exc:
                self.query_one("#cct-mem-stats", Static).update(
                    f"Import failed: {exc}"
                )

        def action_close(self):
            """Close the Memory Center screen."""
            self.dismiss(None)

        # ── confirmation dialog (simple inline) ───────────────────────

        def _confirm_action(self, message, on_confirm):
            """Show a simple inline confirmation bar.

            Pops a horizontal bar at the bottom of the panel with the
            message and Yes/No buttons. *on_confirm* is called on Yes
            (may be None for informational messages).
            """
            try:
                old = self.query_one("#cct-mem-confirm-bar")
                old.remove()
            except Exception:
                pass

            bar = Horizontal(id="cct-mem-confirm-bar", classes="cct-mem-edit-row")
            bar.mount(Static(message, classes="cct-mem-confirm-msg"))
            if on_confirm:
                yes_btn = Button("Yes", id="cct-mem-confirm-yes",
                                 variant="error", classes="cct-btn-sm")
                yes_btn._on_confirm = on_confirm
                bar.mount(yes_btn)
            bar.mount(Button("No", id="cct-mem-confirm-no", classes="cct-btn-sm"))
            self.query_one("#cct-mem-box").mount(bar)

        # ── event handlers ────────────────────────────────────────────

        def on_button_pressed(self, event):
            bid = event.button.id or ""

            if bid == "cct-mem-close":
                self.action_close()
                return

            if bid == "cct-mem-export":
                self.action_export_memories()
                return

            if bid == "cct-mem-import":
                self.action_import_memories()
                return

            if bid == "cct-mem-clear-cat":
                self.action_clear_category()
                return

            if bid == "cct-mem-clear-all":
                self.action_clear_all()
                return

            if bid.startswith("cct-mem-edit-") and not bid.startswith("cct-mem-edit-row"):
                mem_id = bid[len("cct-mem-edit-"):]
                self.action_edit_memory(mem_id)
                return

            if bid.startswith("cct-mem-del-"):
                mem_id = bid[len("cct-mem-del-"):]
                self.action_delete_memory(mem_id)
                return

            if bid == "cct-mem-edit-save":
                self.action_save_edit()
                return

            if bid == "cct-mem-edit-cancel":
                self.action_cancel_edit()
                return

            if bid == "cct-mem-confirm-yes":
                on_confirm = getattr(event.button, "_on_confirm", None)
                try:
                    self.query_one("#cct-mem-confirm-bar").remove()
                except Exception:
                    pass
                if on_confirm:
                    on_confirm()
                return

            if bid == "cct-mem-confirm-no":
                try:
                    self.query_one("#cct-mem-confirm-bar").remove()
                except Exception:
                    pass
                return

        def on_input_changed(self, event):
            if event.input.id == "cct-mem-search":
                self.action_search(event.value)

        def on_input_submitted(self, event):
            if event.input.id == "cct-mem-search":
                self.action_search(event.value)
            elif event.input.id == "cct-mem-edit-input":
                self.action_save_edit()

        def on_select_changed(self, event):
            if event.select.id == "cct-mem-category-filter":
                self.action_filter_category(event.value)

        def on_key(self, event):
            if event.key == "escape":
                if self._editing_id:
                    self.action_cancel_edit()
                else:
                    self.dismiss(None)


def open_memory_center(app):
    """Push the MemoryCenterScreen onto the app's screen stack."""
    if TEXTUAL_AVAILABLE:
        app.push_screen(MemoryCenterScreen())
