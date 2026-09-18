"""
CCT attachment pipeline (v0.7.8.1) — the ONE internal representation
every attachment takes between "user selects a file" and "the model
receives usable context".

    Attachment {
        id, name, path, extension, mime_type, size,
        kind, content, metadata, extraction_status, error
    }

The pipeline every attachment goes through:

    SELECT  ->  VALIDATE  ->  READ  ->  DETECT  ->  EXTRACT
            ->  NORMALIZED OBJECT  ->  CONTEXT BLOCK  ->  MODEL

Rules this module enforces:

- NEVER assume a file was read. `extraction_status` is only "ready"
  after validation + reading + type detection + extraction all
  succeeded; anything else is "failed" with an honest `error`, and the
  UI shows the failure instead of a false "Attached" chip.
- No random path strings flow around the application: the UI chip, the
  message Turn, the context builder and the provider adapter all
  reference the same Attachment object by `id`.
- If extraction fails, the context block still says so explicitly —
  the model is never silently handed nothing.
- Large files/projects are capped and summarized, never dumped whole:
  every context block obeys `max_chars`, and folders produce a real
  listing + only the most relevant text files' content.

The capability layer (`provider_capabilities`) lives here too: it
decides whether the active provider can receive native image payloads
(vision) or must fall back to the extracted textual context. The
fallback is ALWAYS safe — text context works for every provider.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import base64
import csv
import mimetypes
import os
import re
import time
import zlib

# ---------------------------------------------------------------------------
# Constants / registry of supported file types (spec section 4)
# ---------------------------------------------------------------------------

TEXT_FILE_MAX_CHARS = 20000
FOLDER_MAX_FILES = 40
FOLDER_MAX_BYTES = 30000

# Text/code formats read directly (content included verbatim, capped).
CODE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".yaml",
    ".yml", ".toml", ".md", ".txt", ".xml", ".sql", ".sh", ".bat", ".ps1",
    ".c", ".cpp", ".h", ".hpp", ".java", ".rs", ".go", ".php", ".rb", ".kt",
    ".swift", ".lua", ".r", ".cs", ".pl", ".m", ".vue", ".svelte", ".scss",
    ".less", ".ini", ".conf", ".cfg", ".env", ".gitignore", ".dockerfile",
    ".lock", ".log", ".csv", ".tsv", ".graphql", ".proto",
}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".svg", ".tiff", ".tif"}
ARCHIVE_EXTS = {".zip", ".tar", ".gz", ".bz2", ".tgz", ".rar", ".7z", ".xz", ".zst"}
PDF_EXTS = {".pdf"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".wma", ".opus"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".m4v", ".mpg", ".mpeg"}
BINARY_EXTS = {".exe", ".dll", ".so", ".dylib", ".bin", ".dat", ".db", ".sqlite",
               ".sqlite3", ".pyc", ".pdb", ".iso", ".img", ".parquet", ".h5", ".hdf5",
               ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt"}

# Structured formats that get a real parse (not just raw text).
STRUCTURED_EXTS = {".json", ".yaml", ".yml", ".toml", ".csv", ".tsv", ".xml", ".sql"}

KIND_LABELS = {
    "code": "Code", "markdown": "Markdown", "data": "Data",
    "config": "Config", "text": "Text", "image": "Image", "pdf": "PDF",
    "archive": "Archive", "folder": "Folder", "audio": "Audio",
    "video": "Video", "binary": "Binary", "document": "Document",
    "unknown": "File",
}

# Extraction statuses the whole app shares.
STATUS_SELECTING = "selecting"
STATUS_READING = "reading"
STATUS_READY = "ready"
STATUS_FAILED = "failed"


class Attachment:
    """One normalized attachment. `id` is the stable key the UI chip,
    the message Turn, the context builder and the provider adapter all
    share — no random path strings anywhere.

    `content` is the model-usable extracted payload (text for text-like
    files, a real listing for archives, metadata for binary, etc.).
    `extraction_status` is only `ready` when every stage succeeded;
    otherwise `failed` and `error` says why.
    """

    __slots__ = ("id", "name", "path", "extension", "mime_type", "size",
                 "kind", "content", "metadata", "extraction_status",
                 "error", "created_at", "source")

    def __init__(self, path, kind="unknown"):
        self.id = f"att-{int(time.time() * 1000)}-{abs(hash(os.path.normpath(path))) % 1000000}"
        self.path = os.path.abspath(os.path.expanduser(path))
        self.name = os.path.basename(self.path.rstrip(os.sep)) or self.path
        self.extension = os.path.splitext(self.name)[1].lower()
        try:
            self.mime_type = mimetypes.guess_type(self.name)[0] or "application/octet-stream"
        except Exception:
            self.mime_type = "application/octet-stream"
        try:
            self.size = os.path.getsize(self.path) if os.path.isfile(self.path) else 0
        except Exception:
            self.size = 0
        self.kind = kind if kind != "unknown" else detect_kind(self.path)
        self.content = None
        self.metadata = {}
        self.extraction_status = STATUS_SELECTING
        self.error = None
        self.created_at = time.time()
        # How this file arrived: "browse" | "drag_and_drop" | "paste" |
        # "sidebar". Recorded for every attachment (requirement #16).
        self.source = "browse"

    # ---------------------------------------------------------- helpers
    def is_ready(self):
        return self.extraction_status == STATUS_READY

    def is_failed(self):
        return self.extraction_status == STATUS_FAILED

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "path": self.path,
            "extension": self.extension, "mime_type": self.mime_type,
            "size": self.size, "kind": self.kind,
            "extraction_status": self.extraction_status, "error": self.error,
        }

    @staticmethod
    def from_dict(data):
        if isinstance(data, Attachment):
            return data
        if not isinstance(data, dict) or not data.get("path"):
            return None
        att = Attachment(data["path"])
        for key in ("id", "kind", "extraction_status", "error", "content", "metadata"):
            if key in data:
                setattr(att, key, data[key])
        return att

    def __repr__(self):
        return (f"<Attachment id={self.id} name={self.name!r} kind={self.kind} "
                f"status={self.extraction_status}>")


# ---------------------------------------------------------------------------
# Type detection
# ---------------------------------------------------------------------------

def detect_kind(path):
    """Automatic kind detection from the path/extension (spec section 4).
    A directory is a 'folder'; everything else is decided by extension,
    with a final text/unknown fallback."""
    if os.path.isdir(path):
        return "folder"
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in PDF_EXTS:
        return "pdf"
    if ext in ARCHIVE_EXTS:
        return "archive"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in BINARY_EXTS:
        return "document"
    if ext == ".md":
        return "markdown"
    if ext in STRUCTURED_EXTS or ext in {".ini", ".conf", ".cfg", ".env", ".gitignore", ".dockerfile", ".lock"}:
        return "data"
    if ext in CODE_EXTS:
        return "code"
    # Extension-less file: sniff the head for printable text.
    try:
        with open(path, "rb") as f:
            head = f.read(2048)
        if head and not bytes(head).translate(None, b"\x00\x01\x02\x03\x04\x05\x06\x07"
                                              b"\x08\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17"
                                              b"\x18\x19\x1a\x1c\x1d\x1e\x1f").lstrip(b" \t\r\n"):
            return "text"
    except Exception:
        pass
    return "unknown"


def human_size(n):
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    return f"{n / 1024 ** 3:.1f} GB"


# ---------------------------------------------------------------------------
# Extractors — every one returns (content, metadata, error) and NEVER
# fabricates data. A failure is an explicit error string, never silence.
# ---------------------------------------------------------------------------

def _read_text(path, max_chars=TEXT_FILE_MAX_CHARS):
    """Read a UTF-8 (or best-effort) text file, capped at max_chars.
    Returns (content, truncated, error)."""
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                content = f.read(max_chars + 1)
            truncated = len(content) > max_chars
            if truncated:
                content = content[:max_chars]
            return content, truncated, None
        except UnicodeDecodeError:
            continue
        except Exception as e:
            return None, False, str(e)
    return None, False, "could not decode the file as text"


def _extract_structured(path, ext, max_chars):
    """Structured formats get a real parse where useful (spec section 4:
    'For structured formats: PARSE WHEN APPROPRIATE') — JSON is
    pretty-printed (and schema-flattened when huge), CSV gets a genuine
    header/sample/count. Unknown structure falls back to raw text."""
    if ext == ".json":
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read(max_chars + 1)
            try:
                import json
                data = json.loads(raw)
                pretty = json.dumps(data, indent=2, ensure_ascii=False)
                truncated = len(pretty) > max_chars
                if truncated:
                    pretty = pretty[:max_chars]
                return pretty, truncated, None
            except Exception:
                truncated = len(raw) > max_chars
                return (raw[:max_chars] if truncated else raw), truncated, None
        except Exception as e:
            return None, False, f"could not parse JSON: {e}"
    if ext in (".csv", ".tsv"):
        delimiter = "\t" if ext == ".tsv" else ","
        header, sample, total = None, [], 0
        capped = False
        try:
            with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
                for i, row in enumerate(csv.reader(f, delimiter=delimiter)):
                    if i == 0:
                        header = row
                    elif len(sample) < 5:
                        sample.append(row)
                    total += 1
                    if total >= 5000:
                        capped = True
                        break
        except Exception as e:
            return None, False, f"could not parse CSV: {e}"
        lines = [f"CSV {path}: {len(header) if header else 0} columns, "
                 f"{total} rows{' (capped at 5000)' if capped else ''}"]
        if header:
            lines.append("header: " + " | ".join(header))
        if sample:
            lines.append("first rows:")
            lines += ["  " + " | ".join(row) for row in sample]
        body = "\n".join(lines)
        truncated = len(body) > max_chars
        if truncated:
            body = body[:max_chars]
        return body, truncated, None
    # yaml/toml/xml/sql/etc. — the plain text is the useful parse here.
    content, truncated, err = _read_text(path, max_chars)
    return content, truncated, err


def _extract_archive(path, ext, max_chars):
    name = os.path.basename(path)
    size_txt = human_size(os.path.getsize(path) if os.path.isfile(path) else 0)
    if ext == ".zip":
        try:
            import zipfile
            with zipfile.ZipFile(path) as zf:
                infos = zf.infolist()
                files = [i for i in infos if not i.is_dir()]
                total = sum(i.file_size for i in files)
                listing = "\n".join(i.filename for i in files[:40])
                more = f"\n\u2026 and {len(files) - 40} more files" if len(files) > 40 else ""
                body = (f"zip archive: {len(files)} files, {human_size(total)} uncompressed\n"
                        f"{listing}{more}" if files else "zip archive: empty.")
                return f"[attachment: {name} ({size_txt})]\n{body}"[:max_chars], False, None
        except Exception as e:
            return None, False, f"not a readable zip archive: {e}"
    try:
        import tarfile
        with tarfile.open(path) as tf:
            files = [m for m in tf.getmembers() if m.isfile()]
            listing = "\n".join(m.name for m in files[:40])
            more = f"\n\u2026 and {len(files) - 40} more files" if len(files) > 40 else ""
            body = (f"tar archive: {len(files)} files\n{listing}{more}" if files
                    else "tar archive: empty.")
            return f"[attachment: {name} ({size_txt})]\n{body}"[:max_chars], False, None
    except Exception as e:
        return None, False, f"not a readable tar archive: {e}"


def _extract_pdf(path, max_chars):
    name = os.path.basename(path)
    size_txt = human_size(os.path.getsize(path) if os.path.isfile(path) else 0)
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except Exception as e:
        return None, False, f"unreadable PDF: {e}"
    counts = [int(m) for m in re.findall(rb"/Count\s+(\d+)", raw)]
    page_txt = f"{max(counts)} pages" if counts else "page count unknown"
    meta_bits = []
    for key in (b"Title", b"Author", b"Subject", b"Creator", b"Producer"):
        m = re.search(key + rb"\s*\(([^()\\]*(?:\\.[^()\\]*)*)\)", raw[:200000])
        if m:
            val = m.group(1)[:120].decode("latin-1", "replace")
            meta_bits.append(f"{key.decode()}: {val}")
    meta_txt = ("; ".join(meta_bits) + ".") if meta_bits else "no document metadata."
    texts = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.DOTALL):
        data = m.group(1).lstrip(b"\r\n")
        try:
            payload = zlib.decompress(data)
        except Exception:
            payload = data
        texts += re.findall(rb"\(((?:[^()\\]|\\.)*)\)\s*Tj", payload)
    plain = " ".join(
        t.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
        .decode("latin-1", "replace") for t in texts)
    plain = re.sub(r"\s+", " ", plain).strip()
    if plain:
        if len(plain) > max_chars:
            plain = plain[:max_chars] + " \u2026[truncated]"
        body = f"[attachment: {name} ({size_txt}) \u2014 PDF, {page_txt}; {meta_txt}]\n{plain}"
    else:
        body = (f"[attachment: {name} ({size_txt}) \u2014 PDF, {page_txt}; {meta_txt} "
                f"No extractable text layer (scanned image or glyph-encoded PDF).]")
    return body, False, None


def _extract_image(path):
    """Images: real dimensions/format metadata when PIL exists; never
    fabricated content. Whether the image itself travels natively is
    decided by the capability layer at request time — this metadata
    block is the always-safe textual fallback."""
    name = os.path.basename(path)
    size_txt = human_size(os.path.getsize(path) if os.path.isfile(path) else 0)
    dims = ""
    try:
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
            fmt = (im.format or "").upper()
        dims = f" {w}x{h} {fmt}"
    except Exception:
        pass
    body = (f"[Attached image: {name} ({size_txt}{dims}) \u2014 image metadata; "
            f"if the active model supports vision the image is also sent natively, "
            f"otherwise analyze it from this metadata.]")
    return body, False, None


def _extract_folder(path, max_chars):
    """Folders: a real recursive listing (capped), plus the content of
    the most relevant text/code files (capped), never the whole tree.
    This is what 'attach a project/folder' means — the model gets the
    shape of the project and its key files, not megabytes of dumps."""
    files = []
    dirs = 0
    for dp, dnames, fnames in os.walk(path):
        dnames[:] = [d for d in dnames
                     if d not in (".git", "node_modules", "__pycache__", ".venv",
                                  "venv", "dist", "build", ".idea", ".vscode")]
        dirs += len(dnames)
        for f in fnames:
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, path)
            files.append(rel)
    files.sort(key=lambda r: (os.path.basename(r).lower(), r))
    listing = files[:FOLDER_MAX_FILES]
    more = len(files) - FOLDER_MAX_FILES
    lines = [
        f"[attachment: folder {os.path.basename(path.rstrip(os.sep))} "
        f"\u2014 {len(files)} files, {dirs} folders]",
    ]
    lines += ["  " + r for r in listing]
    if more > 0:
        lines.append(f"  \u2026 and {more} more files (listing capped)")
    body = "\n".join(lines)
    # Read a few of the most relevant text files so the model can
    # actually answer questions about the project.
    budget = max_chars - len(body) - 512
    included = 0
    if budget > 0:
        for rel in listing:
            ext = os.path.splitext(rel)[1].lower()
            if ext not in CODE_EXTS and ext not in {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".csv"}:
                continue
            full = os.path.join(path, rel)
            content, truncated, _err = _read_text(full, min(6000, budget))
            if content is None:
                continue
            block = (f"\n--- {rel}{' [truncated]' if truncated else ''} ---\n{content}")
            if len(block) > budget:
                block = block[:budget]
            body += block
            budget -= len(block)
            included += 1
            if budget < 2000 or included >= 6:
                break
    if len(body) > max_chars:
        body = body[:max_chars]
    return body, False, None


def _extract_media(path, kind, max_chars):
    name = os.path.basename(path)
    size_txt = human_size(os.path.getsize(path) if os.path.isfile(path) else 0)
    return (f"[attachment: {name} ({size_txt}) \u2014 {kind} file; duration and tags "
            f"would need a media library, which isn't available in this environment. "
            f"Only the file's existence/size can be reported honestly.]", False, None)


def extract_attachment(path, max_chars=TEXT_FILE_MAX_CHARS):
    """VALIDATE -> READ -> DETECT -> EXTRACT for one path. Returns
    (content, metadata, kind, error). content is None on failure (error
    is set) — never a silent empty string."""
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.lexists(path):
        return None, {}, "unknown", "the path does not exist on disk"
    if os.path.isdir(path):
        kind = "folder"
        try:
            content, _trunc, err = _extract_folder(path, max_chars)
        except Exception as e:
            content, err = None, f"could not read folder: {e}"
        if content is None:
            return None, {}, kind, err or "could not read folder"
        return content, {"items": "recursive listing"}, kind, None
    if not os.path.isfile(path):
        return None, {}, "unknown", "the path is neither a file nor a folder"
    try:
        size = os.path.getsize(path)
    except Exception as e:
        return None, {}, "unknown", f"could not stat the file: {e}"
    ext = os.path.splitext(path)[1].lower()
    kind = detect_kind(path)
    meta = {"size": size, "mime": mimetypes.guess_type(path)[0] or "application/octet-stream"}

    if kind == "image":
        content, _trunc, err = _extract_image(path)
        if err:
            return None, meta, kind, err
        return content, meta, kind, None
    if kind == "pdf":
        content, _trunc, err = _extract_pdf(path, max_chars)
        if err:
            return None, meta, kind, err
        return content, meta, kind, None
    if kind == "archive":
        content, _trunc, err = _extract_archive(path, ext, max_chars)
        if err:
            return None, meta, kind, err
        return content, meta, kind, None
    if kind == "audio":
        content, _trunc, err = _extract_media(path, "audio", max_chars)
        return content, meta, kind, err
    if kind == "video":
        content, _trunc, err = _extract_media(path, "video", max_chars)
        return content, meta, kind, err
    if kind in ("code", "markdown", "text", "data"):
        content, truncated, err = _extract_structured(path, ext, max_chars) \
            if ext in STRUCTURED_EXTS else _read_text(path, max_chars)
        if err:
            return None, meta, kind, f"the file exists, but CAT could not extract its contents: {err}"
        if truncated:
            meta["truncated"] = True
        return content, meta, kind, None
    # document/binary/unknown
    return (f"[attachment: {os.path.basename(path)} ({human_size(size)}) \u2014 {kind} "
            f"file, content not readable as text. Only metadata is available.]",
            meta, kind, None)


# ---------------------------------------------------------------------------
# Manager + context building
# ---------------------------------------------------------------------------

class AttachmentManager:
    """The single entry point for creating/validating attachments and
    turning them into model context. The UI, the session and aicore all
    use this — never ad-hoc path handling."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def create(cls, path, max_chars=TEXT_FILE_MAX_CHARS):
        """SELECT -> VALIDATE -> READ -> DETECT -> EXTRACT -> object.
        Blocks for IO; call from a worker thread, never the UI thread.
        The returned Attachment is always usable: READY with real
        content, or FAILED with an honest error."""
        path = os.path.abspath(os.path.expanduser(path))
        att = Attachment(path)
        if not os.path.lexists(path):
            att.extraction_status = STATUS_FAILED
            att.error = "the file does not exist"
            return att
        if not (os.path.isfile(path) or os.path.isdir(path)):
            att.extraction_status = STATUS_FAILED
            att.error = "the path is neither a file nor a folder"
            return att
        att.extraction_status = STATUS_READING
        content, meta, kind, err = extract_attachment(path, max_chars=max_chars)
        att.kind = kind
        att.metadata.update(meta or {})
        if err is not None:
            att.extraction_status = STATUS_FAILED
            att.error = err
            return att
        att.content = content
        att.extraction_status = STATUS_READY
        return att

    @classmethod
    def ensure_extracted(cls, att, max_chars=TEXT_FILE_MAX_CHARS):
        """Re-run extraction when an attachment is still pending (e.g.
        the user sent the message before the async extraction finished)
        so the request NEVER carries an unverified attachment. Returns
        the same object, updated in place."""
        if att is None:
            return att
        if att.extraction_status == STATUS_READY and att.content is not None:
            return att
        if att.extraction_status == STATUS_FAILED:
            return att
        fresh = cls.create(att.path, max_chars=max_chars)
        att.content = fresh.content
        att.kind = fresh.kind
        att.metadata = fresh.metadata
        att.extraction_status = fresh.extraction_status
        att.error = fresh.error
        return att

    @classmethod
    def build_context(cls, attachments, max_chars=TEXT_FILE_MAX_CHARS):
        """Turns attachment objects into one model-readable context
        block each (spec section 5 fallback format). Unverifiable
        attachments produce an explicit '[could not be read]' block —
        NEVER a silent omission."""
        if not attachments:
            return ""
        blocks = []
        for att in attachments:
            att = cls.ensure_extracted(att, max_chars=max_chars)
            if att is None:
                continue
            if att.extraction_status != STATUS_READY or att.content is None:
                blocks.append(
                    f"--- ATTACHMENT ---\nFile: {att.name}\nPath: {att.path}\n"
                    f"Status: unavailable\n"
                    f"Error: {att.error or 'content could not be extracted'}\n"
                    f"--- END ATTACHMENT ---")
                continue
            body = att.content
            if len(body) > max_chars:
                body = body[:max_chars] + " \u2026[truncated]"
            blocks.append(
                f"--- ATTACHMENT ---\n"
                f"File: {att.name}\nType: {KIND_LABELS.get(att.kind, att.kind)}\n"
                f"Path: {att.path}\n"
                f"Content:\n{body}\n"
                f"--- END ATTACHMENT ---")
        return "\n\n".join(blocks)

    @classmethod
    def verify(cls, attachments, log=None):
        """Attachment context verification (spec section 7): every
        attachment must have a valid id/path/type and successful
        extraction (or a valid native payload) before the request goes
        out. Returns True when every attachment is verified. `log` is a
        callable(message) for debug output — never file contents."""
        if log is None:
            log = lambda _m: None
        if not attachments:
            return True
        log(f"AttachmentManager: verifying {len(attachments)} attachment(s)")
        ok = True
        for att in attachments:
            if att is None or not getattr(att, "id", None):
                log("AttachmentManager: INVALID attachment (no id)")
                ok = False
                continue
            valid_path = bool(getattr(att, "path", "")) and os.path.lexists(att.path)
            cls.ensure_extracted(att)
            if not valid_path:
                log(f"AttachmentManager: {att.id} INVALID path")
                ok = False
            elif att.extraction_status != STATUS_READY or not att.content:
                log(f"AttachmentManager: {att.id} NOT extracted ({att.error or 'unknown'})")
                ok = False
            else:
                log(f"AttachmentManager: {att.id} verified (kind={att.kind}, "
                    f"{len(att.content)} chars)")
        log(f"AttachmentManager: {'all attachments verified' if ok else 'attachment verification FAILED'}")
        return ok


# ---------------------------------------------------------------------------
# Provider/model capability layer (spec section 6)
# ---------------------------------------------------------------------------

# Provider styles that can receive a native image payload in CCT's
# current transport (see aicore._stream_ai_once).
_VISION_API_STYLES = ("openai", "anthropic", "gemini")

# Well-known model families that do NOT accept image content blocks —
# anything unknown defaults to "no vision", which is the safe choice
# (falls back to textual context).
_NON_VISION_MODEL_HINTS = (
    "gpt-3.5", "llama", "mixtral", "mistral", "deepseek", "phi-3", "phi3",
    "qwen", "command", "gemma", "granite", "codex", "o1-mini", "o3-mini",
)
_VISION_MODEL_HINTS = (
    "gpt-4o", "gpt-4.1", "gpt-5", "o3", "o4", "claude-3", "claude-4",
    "gemini-1.5", "gemini-2.0", "gemini-2.5", "gemini-3", "qwen2.5-vl",
    "llava", "llama-3.2-vision",
)


def provider_capabilities(config=None):
    """Detect what the active provider/model can do (spec section 6):
    returns a dict with `vision` (native image payloads supported) and
    `native_attachments` (structured file attachments — always False in
    this transport; the extracted-text fallback is universal).

    v0.7.9.0: the dict is now backed by the model_router's capability
    registry, so it also carries tools/streaming/reasoning/
    context_window/latency_score — the same record the Smart Router
    consults BEFORE a request goes out."""
    caps = {"vision": False, "native_attachments": False,
            "tools": True, "streaming": True, "reasoning": False,
            "context_window": 32000, "latency_score": 0.5}
    try:
        if not config:
            from . import aicore
            config = aicore.load_config()
        config = config or {}
        # Preferred source of truth: the shared capability registry.
        try:
            from . import model_router as _mr
            rc = _mr._capabilities_for(config)
            caps.update({
                "vision": bool(rc.vision),
                "tools": bool(rc.tools),
                "streaming": bool(rc.streaming),
                "reasoning": bool(rc.reasoning),
                "context_window": int(rc.context_window),
                "latency_score": float(rc.latency_score),
            })
            return caps
        except Exception:
            pass
        provider = str(config.get("provider", "")).lower()
        model = str(config.get("model", "")).lower()
        api_style = str(config.get("api_style", "")).lower()
        if not api_style:
            try:
                from . import aicore as _a
                info = _a.PROVIDERS.get(provider)
                api_style = (info["api_style"] if info else "openai") or "openai"
            except Exception:
                api_style = "openai"
        if api_style not in _VISION_API_STYLES:
            return caps
        if any(h in model for h in _NON_VISION_MODEL_HINTS):
            return caps
        if any(h in model for h in _VISION_MODEL_HINTS):
            caps["vision"] = True
            return caps
        # Unknown model on a vision-capable provider: default to no
        # vision (safe fallback to textual context).
        return caps
    except Exception:
        return caps


def attachment_has_image_payload(att):
    return att is not None and att.kind == "image"


def encode_image_data_url(path):
    """Base64 data URL for a local image — used by the native vision
    path when the provider supports it.

    v0.7.9.0 (requirement #15): the image is NORMALIZED first via the
    vision pipeline — EXIF orientation applied, oversized dimensions
    downscaled with a high-quality filter, exotic formats (TIFF/BMP)
    converted to provider-compatible PNG/JPEG — so a 20 MB photo no
    longer ships as a ~27 MB base64 blob. Quality is preserved: images
    already within budget pass through byte-for-byte."""
    ext = os.path.splitext(str(path))[1].lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp",
            "svg": "image/svg+xml", "ico": "image/x-icon"}.get(ext, "image/png")
    try:
        from . import vision as _vision
        n_mime, b64, _meta = _vision.encode_for_model(path)
        return n_mime or mime, b64
    except Exception:
        # Honest fallback: send the original bytes untouched for native
        # formats; anything exotic without Pillow fails at the API with
        # its own message rather than here.
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return mime, b64
