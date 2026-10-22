"""
CCT UI — small shared presentational widgets with no owner module of
their own: a generic dismissible Chip (attachments.py builds
AttachmentChip/PasteChip on top of this) and a StatusPill used by both
the footer and inline conversation notices. Render state, dispatch
events — nothing here decides what an action means.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Horizontal
    from textual.widgets import Static, Button
except Exception:
    TEXTUAL_AVAILABLE = False


if TEXTUAL_AVAILABLE:
    import time as _time

    class _ChipLabel(Static):
        """The clickable label half of a Chip. Its own on_click handler
        (rather than one on the parent) means a click on the × button —
        which consumes its own click as a Button.Pressed — never also
        triggers the label's action.

        Double-click support (v0.8.1): two clicks on the label within
        0.5s invoke `on_double_click` instead of the single-click
        action. Textual's Click event carries no chain counter, so the
        timing lives here."""

        DOUBLE_CLICK_SECONDS = 0.5

        def __init__(self, text, chip_id, on_click, on_double_click=None):
            super().__init__(text, classes="cct-chip-label")
            self.chip_id = chip_id
            self._on_click = on_click
            self._on_double_click = on_double_click
            self._last_click_at = 0.0

        def set_label(self, text):
            self.update(text)

        def on_click(self, event):
            now = _time.monotonic()
            is_double = (now - self._last_click_at) <= self.DOUBLE_CLICK_SECONDS
            self._last_click_at = 0.0 if is_double else now
            if is_double and self._on_double_click:
                self._on_double_click(self.chip_id)
                return
            if is_double:
                # a double click with no handler still counts as one click
                pass
            if self._on_click:
                self._on_click(self.chip_id)

    class _ChipClose(Static):
        """Crisp borderless close icon for chips. Subclasses Static so it never
        inherits Button height: 3 rules from theme_css or clips into empty brackets."""

        DEFAULT_CSS = """
        _ChipClose {
            width: 3;
            min-width: 3;
            max-width: 3;
            height: 1;
            min-height: 1;
            max-height: 1;
            padding: 0;
            margin: 0;
            background: transparent;
            color: $text-muted;
            content-align: center middle;
        }
        _ChipClose:hover {
            color: $error;
            background: $error 20%;
            text-style: bold;
        }
        """

        def __init__(self, chip_id, on_delete=None):
            super().__init__("\u2715", classes="cct-chip-close", id=f"chip-close-{chip_id}")
            self.chip_id = chip_id
            self._on_delete = on_delete
            self.tooltip = "Remove attachment (\u2715)"

        @property
        def label(self):
            return "\u2715"

        def on_click(self, event):
            event.stop()
            if self._on_delete:
                self._on_delete(self.chip_id)

    class Chip(Horizontal):
        """One dismissible chip: a clickable label + a small × button.
        Used directly for generic chips, and as the base shape for
        AttachmentChip / PasteChip in ui/attachments.py."""

        def __init__(self, chip_id, label_text, *, on_click=None, on_delete=None,
                     on_double_click=None, classes="cct-chip"):
            super().__init__(classes=classes)
            self.chip_id = chip_id
            self._label_text = label_text
            self._on_click = on_click
            self._on_delete = on_delete
            self._on_double_click = on_double_click

        def compose(self):
            yield _ChipLabel(self._label_text, self.chip_id, self._on_click,
                             on_double_click=self._on_double_click)
            yield _ChipClose(self.chip_id, on_delete=self._on_delete)

        def update_label(self, text):
            """v0.7.8.1: swap a chip's label in place (attachment status
            chips use this to go reading -> ready/failed)."""
            self._label_text = text
            try:
                label = self.query_one(_ChipLabel)
            except Exception:
                return
            label.set_label(text)

        def on_button_pressed(self, event):
            if event.button.id == f"chip-close-{self.chip_id}":
                event.stop()
                if self._on_delete:
                    self._on_delete(self.chip_id)

    class StatusPill(Static):
        """One small `label value` pill with a tone color (ready/warn/err),
        used by ui/footer.py's StatusLine and inline system notices.

        Rich markup (used for the colored `value` span) needs a literal
        color, not a Textual `$variable` — so this pulls the hex straight
        from theme_css.current_hex(), the same single palette source
        every CSS rule in this package resolves against.
        """

        _TONE_ROLE = {"ready": "success", "warn": "warning", "err": "error", "": "text-muted"}

        def __init__(self, label, value, tone=""):
            from . import theme_css
            color = theme_css.current_hex(self._TONE_ROLE.get(tone, "text-muted"))
            super().__init__(f"{label} [{color}]{value}[/]", classes="cct-status-pill")

        def set_value(self, value, tone=""):
            from . import theme_css
            color = theme_css.current_hex(self._TONE_ROLE.get(tone, "text-muted"))
            self.update(f"[{color}]{value}[/]")

else:
    Chip = None
    StatusPill = None
