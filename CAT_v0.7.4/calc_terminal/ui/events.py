"""
CCT UI events — the public contract between UI components.

Components never call each other directly (ConversationView never
calls a Composer method; Composer never reaches into ConversationView;
PermissionCard never touches ConversationView). Everything crosses
component boundaries as one of these Message subclasses, posted with
`self.post_message(...)` and handled by a parent's `on_<event_name>`
method (Textual's normal message-bubbling convention) or centrally in
calc_terminal/ui/app.py's CCTApp, which is the only place allowed to
coordinate more than one component at once.

Every event here is a plain data carrier: attributes only, no methods
that do work. Deciding what an event *means* (allow this action, call
the AI, switch the theme) is business logic and lives outside ui/.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

TEXTUAL_AVAILABLE = True
try:
    from textual.message import Message
except Exception:
    TEXTUAL_AVAILABLE = False

    class Message:  # minimal stand-in so `class X(Message)` below still
        """Textual isn't installed — these event classes still need to
        exist so `from .events import X` doesn't raise ImportError
        before the caller gets a chance to check TEXTUAL_AVAILABLE."""

        def __init__(self):
            pass


# ------------------------------------------------------------- messaging --
class MessageSubmitted(Message):
    """Composer -> app. The user submitted the composer (Send / Ctrl+Enter)."""

    def __init__(self, text, attachments=None):
        self.text = text
        self.attachments = attachments or []
        super().__init__()


class MessageStarted(Message):
    """App -> conversation. A new turn is being created for `turn_id`.
    `prompt` is the text that triggered it — optional, and only used by
    the composer's status bar for smart stage detection (thinking.py),
    so existing callers that don't pass it keep working unchanged."""

    def __init__(self, turn_id, role="assistant", prompt=""):
        self.turn_id = turn_id
        self.role = role
        self.prompt = prompt
        super().__init__()


class MessageChunk(Message):
    """App -> conversation. One streamed token/fragment for `turn_id`."""

    def __init__(self, turn_id, text):
        self.turn_id = turn_id
        self.text = text
        super().__init__()


class MessageFinished(Message):
    """App -> conversation. `turn_id` is complete; `full_text` is final."""

    def __init__(self, turn_id, full_text, duration=0.0, usage=None):
        self.turn_id = turn_id
        self.full_text = full_text
        self.duration = duration
        self.usage = usage or {}
        super().__init__()


# ------------------------------------------------------------- streaming --
class StreamingStarted(Message):
    """Brackets a streaming session (drives the footer's live indicator)."""

    def __init__(self, turn_id):
        self.turn_id = turn_id
        super().__init__()


class StreamingFinished(Message):
    def __init__(self, turn_id):
        self.turn_id = turn_id
        super().__init__()


class AgentActivity(Message):
    """App -> conversation (v0.7.9.0): a real backend agent-state
    crossing for the CAT Agent ASCII indicator. `state` is one of:

        thinking            model request in flight / processing results
        tool_execution      an agent tool is running
        waiting_permission  blocked on the user's permission decision

    The indicator starts with MessageStarted (thinking), may flip to
    tool_execution/waiting_permission and back while the agent loop
    runs, and is always removed by MessageFinished — which covers the
    success, error AND cancelled exits, because every one of those
    paths still posts MessageFinished (partial text kept on cancel).
    This is deliberately a UI-only carrier: it never rides along in
    model requests and never becomes conversation content."""

    STATES = ("thinking", "tool_execution", "tool_running",
              "waiting_permission")

    def __init__(self, turn_id, state="thinking"):
        self.turn_id = turn_id
        self.state = state if state in self.STATES else "thinking"
        super().__init__()


# ------------------------------------------------------------ permissions --
class PermissionRequested(Message):
    """Backend -> app. `request_id` is a one-shot token the eventual
    PermissionGranted/Denied must echo back so the right pending call
    resolves (see calc_terminal/permissions.py's manager.decide)."""

    def __init__(self, request_id, key, action_text, reason):
        self.request_id = request_id
        self.key = key
        self.action_text = action_text
        self.reason = reason
        super().__init__()


class PermissionGranted(Message):
    def __init__(self, request_id, key, remember=False):
        self.request_id = request_id
        self.key = key
        self.remember = remember
        super().__init__()


class PermissionDenied(Message):
    """`remember=True` means Always Deny (v0.7.7 spec section 3's
    dialog offers Deny / Always Deny / Cancel on top of the existing
    Allow Once / Always Allow) — the denied key is recorded so future
    requests are refused without prompting at all."""

    def __init__(self, request_id, key, remember=False):
        self.request_id = request_id
        self.key = key
        self.remember = remember
        super().__init__()


class PermissionCancelled(Message):
    """The user picked Cancel instead of Allow/Deny — the pending call
    is resolved as a cancellation (nothing ran, nothing was recorded as
    denied)."""

    def __init__(self, request_id, key):
        self.request_id = request_id
        self.key = key
        super().__init__()


# ------------------------------------------------------------ attachments --
class AttachmentAdded(Message):
    def __init__(self, chip_id, label, kind="file"):
        self.chip_id = chip_id
        self.label = label
        self.kind = kind  # "file" | "paste" | "image"
        super().__init__()


class AttachmentRemoved(Message):
    def __init__(self, chip_id):
        self.chip_id = chip_id
        super().__init__()


class PasteCollapsed(Message):
    def __init__(self, chip_id, line_count):
        self.chip_id = chip_id
        self.line_count = line_count
        super().__init__()


class PasteExpanded(Message):
    def __init__(self, chip_id, text):
        self.chip_id = chip_id
        self.text = text
        super().__init__()


class AttachmentChipDoubleClicked(Message):
    """AttachmentBar -> app. An attachment chip's label was double-
    clicked. For .txt attachments this means "import the text into the
    chat now" (requirement #18); single-click stays normal behavior."""

    def __init__(self, chip_id, path, name):
        self.chip_id = chip_id
        self.path = path
        self.name = name
        super().__init__()


# ----------------------------------------------------------- commands/etc --
class CommandExecuted(Message):
    def __init__(self, command, args=""):
        self.command = command
        self.args = args
        super().__init__()


class ConversationLoaded(Message):
    def __init__(self, turn_count):
        self.turn_count = turn_count
        super().__init__()


class ConversationSaved(Message):
    def __init__(self, path):
        self.path = path
        super().__init__()


class ConversationCleared(Message):
    def __init__(self):
        super().__init__()


class NotebookChanged(Message):
    def __init__(self, mode):
        self.mode = mode
        super().__init__()


class WorkspaceChanged(Message):
    def __init__(self, workspace):
        self.workspace = workspace
        super().__init__()


class ModelChanged(Message):
    def __init__(self, model_name):
        self.model_name = model_name
        super().__init__()


class ThemeChanged(Message):
    def __init__(self, theme_name):
        self.theme_name = theme_name
        super().__init__()


class ErrorOccurred(Message):
    def __init__(self, message, detail=""):
        self.message = message
        self.detail = detail
        super().__init__()


class RetryRequested(Message):
    def __init__(self, turn_id):
        self.turn_id = turn_id
        super().__init__()


class SessionEnded(Message):
    def __init__(self):
        super().__init__()


# ------------------------------------------------------- v0.7 IDE events --
class PermissionModeChanged(Message):
    """HeaderPermissionSelector -> app. `mode` is one of
    permissions.MODES ('ask' | 'restricted' | 'full')."""

    def __init__(self, mode):
        self.mode = mode
        super().__init__()


class FolderOpened(Message):
    """Sidebar/app -> app. A project folder was opened as the IDE
    workspace root (spec section 16's "Open Folder")."""

    def __init__(self, path):
        self.path = path
        super().__init__()


class SidebarToggled(Message):
    def __init__(self, visible):
        self.visible = visible
        super().__init__()


class FileOpenRequested(Message):
    """Sidebar (or drag & drop) -> app: open this path in the editor."""

    def __init__(self, path):
        self.path = path
        super().__init__()


class FileSaved(Message):
    def __init__(self, path):
        self.path = path
        super().__init__()


class MessageRewritten(Message):
    """StickyComposer -> app: posted instead of MessageSubmitted when
    the composer was in Rewrite edit mode (see
    StickyComposer.start_edit, triggered by the context menu's
    'rewrite' action) and the user pressed Enter to save.

    Deliberately a separate event rather than an optional field on
    MessageSubmitted: a plain submit always APPENDS a new user turn
    and a new assistant turn (on_message_submitted), while this always
    REPLACES the existing `turn_id`'s text and regenerates its paired
    assistant reply in place (on_message_rewritten /
    CCTApp._regenerate_turn) — different enough handling that
    overloading one event with an if-branch would just move the
    duplicate-vs-replace bug this fixes from the UI into the event
    handler instead of removing it."""

    def __init__(self, turn_id, text, attachments=None):
        self.turn_id = turn_id
        self.text = text
        self.attachments = attachments or []
        super().__init__()


class MessageContextAction(Message):
    """ConversationItem (via context_menu.MessageContextMenu) -> app.
    `action` is one of: 'new_session', 'retry:<mode>' (mode is one of
    ai_modes.MODE_ORDER), 'rewrite', 'revert', 'fork' — 'copy' is
    deliberately NOT posted here: it needs no cross-component
    coordination (clipboard + a local confirmation flash), so
    ConversationItem handles it entirely itself and never posts this
    for it. `turn_id` is the turn the menu was opened on."""

    def __init__(self, action, turn_id):
        self.action = action
        self.turn_id = turn_id
        super().__init__()


class NavAction(Message):
    """NavPanel (opened from the header's menu button) -> app. `action`
    is one of the panel's item ids: 'dashboard', 'open_folder',
    'recent_workspaces', 'mcp_servers', 'customize_ai', 'diff_viewer',
    'settings', 'themes', 'extensions', 'keyboard_shortcuts', 'help'.
    Deliberately a single generic event (like MessageContextAction)
    rather than one Message subclass per item — eleven near-identical
    classes would add nothing an `action` string doesn't already say,
    and CCTApp.on_nav_action is the one place allowed to decide what
    each id actually does."""

    def __init__(self, action):
        self.action = action
        super().__init__()


class SettingChanged(Message):
    """Merged Settings window (v0.7.6 Patch 1) -> app. `category` is
    one of the setting ids the window renders ('perm_mode', 'theme',
    'ai_mode', 'model', 'workspace', 'autosave', 'sound', 'animation',
    'anim_speed', 'precision', 'clear_history'); `value` is the
    proposed new value for choice-style categories (the mode/theme/AI
    mode key, etc.) and None for pure actions and toggles. The window
    never applies anything itself — CCTApp.on_setting_changed is the
    only place that decides what a change means, then asks the window
    to re-render its current values."""

    def __init__(self, category, value=None):
        self.category = category
        self.value = value
        super().__init__()


class WorkspaceFilesChanged(Message):
    """Backend (agent tool loop) -> app: one or more files/folders on
    disk were created/deleted/renamed by the AI during this turn, so the
    Explorer tree (and, if the affected path is open, the Editor) need
    to refresh. Deliberately coarse (a set of touched paths, not a
    typed per-file event bus) — see CHANGELOG_v0.7.2 for why the full
    "Workspace Event Bus" the spec describes is out of scope for this
    slice."""

    def __init__(self, paths=None):
        self.paths = list(paths or [])
        super().__init__()


class EditorTabsChanged(Message):
    """EditorPane -> WorkspaceShell (and anything else listening): the
    set of open file tabs changed (a file was opened or closed).
    `count` is the number of open *files* (the placeholder Welcome tab
    never counts). The shell uses this to decide whether the editor
    pane should claim layout space at all and whether the narrow-
    terminal Chat/Files switcher needs to exist — the shell never
    reaches into EditorPane's private dicts for that, this event is the
    only channel."""

    def __init__(self, count):
        self.count = count
        super().__init__()


class ChatRequested(Message):
    """WorkspaceShell's Chat/Files switcher -> app: the user asked to
    see the AI chat (the one-click switch on narrow terminals, or the
    editor's Esc "back to chat" step). The shell flips the panes
    itself; the app only uses this to re-focus the composer so the user
    can start typing right away — no other coordination crosses this
    boundary."""

    def __init__(self):
        super().__init__()


# --------------------------------------------------------------------------
# v0.7.10 Live Web Preview — editor ⇄ browser pane events
#
class PreviewRequested(Message):
    """EditorPane (▷ pill) / explorer -> app: preview this file as a
    website. `path` is an absolute filesystem path to an HTML file (or
    any file inside the site) — the controller detects the entry point
    and web root from it."""

    def __init__(self, path=None):
        self.path = path
        super().__init__()


class PreviewClosed(Message):
    """PreviewPanel (⏻) / app -> shell: close Web Preview and return
    the right pane to the Code Editor. The server/browser teardown and
    any confirmation happen on the app side; the shell only flips its
    WorkspaceMode when this arrives."""

    def __init__(self):
        super().__init__()


class BuildActivity(Message):
    """Preview subsystem -> UI: one lightweight line of what CAT is
    doing to the website ('● Writing style.css', '✓ Preview
    synchronized'). Rendered in the PreviewPanel's activity strip —
    NEVER dumped into the chat conversation (spec section 16)."""

    def __init__(self, text, done=False):
        self.text = text
        self.done = done
        super().__init__()


# v0.7.10 Live Diff Viewer events
class DiffViewerRequested(Message):
    """EditorPane -> app: show the diff viewer for a file. `path` is
    the absolute path to the file, `diff` is the computed diff lines."""

    def __init__(self, path, diff=None):
        self.path = path
        self.diff = diff or []
        super().__init__()


class DiffViewerClosed(Message):
    """Diff viewer -> app: close the diff viewer panel."""

    def __init__(self):
        super().__init__()


class FileChangeTracked(Message):
    """Editor -> app: a file was modified and the change was tracked.
    Used for Live File Automation (#13) to notify other components."""

    def __init__(self, path, change_type="modified"):
        self.path = path
        self.change_type = change_type  # "created", "modified", "deleted"
        super().__init__()
