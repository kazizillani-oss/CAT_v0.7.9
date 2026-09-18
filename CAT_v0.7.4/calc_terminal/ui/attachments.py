"""
CCT UI — attachment + smart-paste chips, living in the composer's
AttachmentBar. Renders state (what's attached, what's collapsed) and
dispatches events (AttachmentAdded/Removed, PasteCollapsed/Expanded);
StickyComposer/CCTApp decide what those events mean.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Horizontal
except Exception:
    TEXTUAL_AVAILABLE = False

from .widgets import Chip, TEXTUAL_AVAILABLE as _WIDGETS_OK
from .events import (AttachmentAdded, AttachmentRemoved, PasteCollapsed,
                     PasteExpanded, AttachmentChipDoubleClicked)

try:
    from .. import attachments as _core
except Exception:  # pragma: no cover — import-time fallback
    _core = None

TEXTUAL_AVAILABLE = TEXTUAL_AVAILABLE and _WIDGETS_OK

# Paste thresholds from the redesign brief: under these a paste inserts
# normally into the editor; at/above either one, collapse into a chip.
PASTE_COLLAPSE_THRESHOLD = 10
PASTE_WORD_THRESHOLD = 100

# Favorite folders for the attach browser (v0.7.8.1): a tiny, honest
# store — just a JSON list of folder paths the user starred in the
# Attach panel's Favorites tab.
FAVORITES_FILE = os.path.join(os.path.expanduser("~"), ".cct_attach_favorites.json")


def favorite_folders() -> list[str]:
    """Starred folders for the Attach browser. Never raises."""
    try:
        if os.path.exists(FAVORITES_FILE):
            with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
                import json
                data = json.load(f)
            if isinstance(data, list):
                return [p for p in data if isinstance(p, str) and os.path.isdir(p)]
    except Exception:
        pass
    return []


def toggle_favorite_folder(path: str) -> bool:
    """Star/unstar a folder. Returns True when it is now a favorite."""
    path = os.path.normpath(path)
    favs = favorite_folders()
    if path in favs:
        favs = [p for p in favs if p != path]
        added = False
    else:
        favs.append(path)
        added = True
    try:
        import json
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(favs, f, indent=2)
    except Exception:
        pass
    return added


def list_drives() -> list[str]:
    """Windows drive letters that exist (A:, C:, ...). Empty elsewhere."""
    try:
        import string
        return [f"{c}:\\" for c in string.ascii_uppercase
                if os.path.exists(f"{c}:\\")]
    except Exception:
        return []


def paths_from_paste(text):
    """Drag & drop / paste → attachment paths (v0.7.6 Patch 1, Fix 5;
    hardened v0.8.1).

    Textual 8.2.8 has no OS file-drop event, but dragging a file into a
    Windows terminal inserts its path into the input buffer anyway —
    which arrives here as a paste. So "drag & drop" is realised as
    path-paste detection, and multi-file drops are covered too:
    Explorer copies/drops NUL-separated paths (`\x00`); some hosts use
    CRLF or quoted single-line forms.

    Returns a list of existing absolute paths when the whole paste is
    nothing but paths (one per line / NUL-separated, optional quotes),
    else None so the caller falls back to a normal text paste. A path
    must exist on disk — a stale/typo'd path is treated as prose."""
    if not text:
        return None
    normalized = text.replace("\x00", "\n").replace("\r\n", "\n")
    paths = []
    for part in normalized.split("\n"):
        p = part.strip().strip('"').strip("'").strip()
        if not p:
            continue
        # tolerate the "file:///C:/..." URI form some apps put on the clipboard
        if p.lower().startswith("file:///"):
            from urllib.parse import unquote, urlparse
            try:
                p = unquote(urlparse(p).path).lstrip("/") or p
                if len(p) > 1 and p[1] != ":" and os.name == "nt":
                    p = "C:" + p  # unlikely; keep best-effort
            except Exception:
                pass
        if not os.path.isabs(p) or not os.path.lexists(p):
            return None
        paths.append(os.path.normpath(p))
    return paths or None


def attachment_kind(path):
    """Fix 6 (chat attachment cards): an icon + kind label for an
    attachment path, chosen purely from its extension. Presentation
    only — the AI-side reading/analysis (Fix 7) lives in aicore."""
    ext = os.path.splitext(path)[1].lower()
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico"}:
        return "\U0001f5bc\ufe0f", "image"
    if ext == ".pdf":
        return "\U0001f4d5", "pdf"
    if ext in {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"}:
        return "\U0001f4e6", "archive"
    if ext in {".csv", ".tsv", ".xlsx", ".xls", ".json", ".xml", ".yaml", ".yml",
               ".toml", ".ini", ".conf", ".env"}:
        return "\U0001f4ca", "data"
    if ext == ".md":
        return "\U0001f4dd", "markdown"
    if ext in {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h", ".hpp",
               ".cs", ".go", ".rs", ".rb", ".php", ".sh", ".ps1", ".bat", ".html", ".css",
               ".sql", ".lua", ".r", ".swift", ".kt"}:
        return "\U0001f4dc", "code"
    if ext in {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"}:
        return "\U0001f3b5", "audio"
    if ext in {".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv"}:
        return "\U0001f3ac", "video"
    return "\U0001f4c4", "file"


def format_size(path):
    try:
        size = os.path.getsize(path)
    except Exception:
        return ""
    if size < 1024:
        return f"{size} B"
    if size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    if size < 1024 ** 3:
        return f"{size / 1024 ** 2:.1f} MB"
    return f"{size / 1024 ** 3:.1f} GB"


def _size_label(size):
    try:
        size = int(size or 0)
    except Exception:
        size = 0
    if size < 1024:
        return f"{size} B"
    if size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    if size < 1024 ** 3:
        return f"{size / 1024 ** 2:.1f} MB"
    return f"{size / 1024 ** 3:.1f} GB"


def _status_label(att):
    """v0.7.8.1: the status half of an attachment chip — 'reading…'
    while extraction runs, 'kind · size' when ready, the honest error
    when it failed. The color lives in the chip markup, not here."""
    status = getattr(att, "extraction_status", None)
    if status == _core.STATUS_READING:
        return "reading\u2026"
    if status == _core.STATUS_READY:
        label = _core.KIND_LABELS.get(getattr(att, "kind", ""), "File")
        return f"{label.lower()} \u00b7 {_size_label(getattr(att, 'size', 0))}"
    if status == _core.STATUS_FAILED:
        return getattr(att, "error", None) or "could not be read"
    return "reading\u2026"


def _status_color(att):
    """Dim for pending/ready, the theme's error color for failures."""
    if getattr(att, "extraction_status", None) == _core.STATUS_FAILED:
        from . import theme_css
        return theme_css.current_hex("error")
    from . import theme_css
    return theme_css.current_hex("text-faint")


def _vision_warning(att):
    """CAT automatically extracts OCR, multimodal features, and metadata
    for all attached images and files across all models. Returns None so no
    false warnings are displayed."""
    return None


def _chip_label(att):
    """One chip's full markup: icon + name + status + weak-model note."""
    from . import theme_css
    icon, _k = attachment_kind(att.path)
    name = att.name
    label = (f"{icon} [{theme_css.current_hex('text')}]{name}[/]"
             f"[{_status_color(att)}]\u00b7{_status_label(att)}[/]")
    warn = _vision_warning(att)
    if warn:
        label += f"[{theme_css.current_hex('warning')}] \u26a0 {warn}[/]"
    return label


if TEXTUAL_AVAILABLE:

    class AttachmentBar(Horizontal):
        """Row of attachment + paste chips, living inside the composer
        card under the editor. Empty (height: auto collapses to 0) until
        something is attached.

        Holds two kinds of chips:
          - file attachments (label = filename; delete removes it)
          - collapsed pastes (label = "[Pasted ~N lines]"; clicking the
            label re-expands the full text via PasteExpanded; delete
            discards it for good)

        v0.7.8.1: every attached path is normalized into an Attachment
        object (calc_terminal/attachments.py) the moment it's added.
        Extraction runs off the UI thread; the chip shows 'reading…'
        until it resolves to 'ready' (kind · size) or 'failed' (honest
        error). The Attachment objects travel with the message via
        pop_attachment_objects() — the AI pipeline receives real
        objects, never bare path strings.

        Every state change posts the matching event instead of being
        polled — StickyComposer/CCTApp react to those, they never reach
        back into this bar's internals.
        """

        DEFAULT_CSS = """
        AttachmentBar {
            height: auto;
            width: 100%;
            padding: 0 1;
            margin: 0;
            display: none;
        }
        """

        def __init__(self):
            super().__init__(id="cct-chips")
            self._attachments = {}   # chip_id -> Attachment object
            self._pastes = {}        # chip_id -> full pasted text
            self._next_file_id = 1
            self._next_paste_id = 1
            self.display = False

        def _sync_visibility(self):
            has_items = bool(self._attachments or self._pastes)
            self.display = has_items

        def on_mount(self):
            self._sync_visibility()

        def add_file(self, path, kind="file", source="browse"):
            """Validate → normalize → chip (requirements #14-16).

            Returns the new chip_id, or None when the path was rejected.
            Directories are rejected with an honest reason — only real
            files attach. `source` records how the file arrived
            ("browse" | "drag_and_drop" | "paste" | "sidebar")."""
            try:
                exists = os.path.lexists(path)
                is_dir = os.path.isdir(path)
            except OSError:
                return None
            if not exists:
                return None
            if is_dir:
                return None  # directories never attach as files
            chip_id = f"file-{self._next_file_id}"
            self._next_file_id += 1
            att = _core.Attachment(path)
            att.source = source  # Attachment uses __slots__; see below
            if kind not in ("file",) and kind != att.kind:
                att.kind = kind
            att.extraction_status = _core.STATUS_READING
            self._attachments[chip_id] = att
            self._mount_file_chip(chip_id)
            # active drop/attach feedback: flash the bar so a dropped or
            # pasted batch visibly landed (never just an animation on an
            # empty handler)
            try:
                self.add_class("cct-drop-active")
                self.set_timer(0.6, lambda: self.remove_class("cct-drop-active"))
            except Exception:
                pass
            self.post_message(AttachmentAdded(chip_id, att.name, kind=att.kind))
            # Extraction off the UI thread; the chip flips to ready /
            # failed when it lands (async worker, safe to await here).
            self.run_worker(self._extract_worker(chip_id), group="attachments")
            return chip_id

        def get_attachment(self, chip_id):
            return self._attachments.get(chip_id)

        def _mount_file_chip(self, chip_id):
            att = self._attachments.get(chip_id)
            if att is None:
                return
            self._sync_visibility()
            self.mount(Chip(chip_id, _chip_label(att),
                            on_delete=self._remove_file,
                            on_double_click=self._double_clicked))
            return chip_id

        def _double_clicked(self, chip_id):
            att = self._attachments.get(chip_id)
            if att is None:
                return
            self.post_message(AttachmentChipDoubleClicked(
                chip_id, att.path, att.name))

        def _refresh_chip(self, chip_id):
            """Re-render one chip's label from its Attachment's current
            state — the status chips' reading -> ready/failed flip."""
            for child in list(self.children):
                if isinstance(child, Chip) and child.chip_id == chip_id:
                    att = self._attachments.get(chip_id)
                    if att is None:
                        return
                    child.update_label(_chip_label(att))
                    return

        async def _extract_worker(self, chip_id):
            import asyncio
            att = self._attachments.get(chip_id)
            if att is None or _core is None:
                return
            fresh = await asyncio.to_thread(_core.AttachmentManager.create, att.path)
            att.kind = fresh.kind
            att.metadata = fresh.metadata
            att.content = fresh.content
            att.extraction_status = fresh.extraction_status
            att.error = fresh.error
            if chip_id in self._attachments:
                self._refresh_chip(chip_id)

        def add_paste(self, text, line_count, word_count=0):
            chip_id = f"paste-{self._next_paste_id}"
            self._next_paste_id += 1
            self._pastes[chip_id] = text
            if line_count > 1:
                label = f"[Pasted ~{line_count} lines]"
            else:
                label = f"[Pasted {len(text):,} characters]"
            self._sync_visibility()
            self.mount(Chip(chip_id, label, on_click=self._expand_paste,
                             on_delete=self._remove_paste))
            self.post_message(PasteCollapsed(chip_id, line_count))
            return chip_id

        def pop_attachment_objects(self):
            """v0.7.8.1: returns every attached Attachment object (in
            insertion order) and clears the bar's file chips (pastes are
            left alone) — called right before a message is sent, so
            attachments travel with that one message as real objects,
            not bare paths. A chip still mid-extraction returns its
            object anyway; the AI pipeline re-extracts if needed."""
            out = list(self._attachments.values())
            ids = set(self._attachments)
            self._attachments = {}
            for child in list(self.children):
                if isinstance(child, Chip) and child.chip_id in ids:
                    child.remove()
            self._sync_visibility()
            return out

        def pop_attachment_paths(self):
            """Backward-compatible shim — the pre-0.7.8.1 shape (paths).
            New code should use pop_attachment_objects()."""
            return [a.path for a in self.pop_attachment_objects()]

        def _remove_file(self, chip_id):
            if chip_id not in self._attachments:
                return
            self._attachments.pop(chip_id, None)
            for child in list(self.children):
                if isinstance(child, Chip) and child.chip_id == chip_id:
                    child.remove()
            self._sync_visibility()
            self.post_message(AttachmentRemoved(chip_id))

        def _expand_paste(self, chip_id):
            text = self._pastes.pop(chip_id, None)
            if text is None:
                return
            for child in list(self.children):
                if isinstance(child, Chip) and child.chip_id == chip_id:
                    child.remove()
            self._sync_visibility()
            self.post_message(PasteExpanded(chip_id, text))

        def _remove_paste(self, chip_id):
            if chip_id not in self._pastes:
                return
            self._pastes.pop(chip_id, None)
            for child in list(self.children):
                if isinstance(child, Chip) and child.chip_id == chip_id:
                    child.remove()
            self._sync_visibility()
            self.post_message(AttachmentRemoved(chip_id))

else:
    AttachmentBar = None
