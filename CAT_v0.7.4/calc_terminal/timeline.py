"""
CCT — timeline.py: Session Timeline (v0.7.2 roadmap). A chronological
log of development activity for the CURRENT run of the app — file
changes, AI replies, terminal commands, workspace changes, todo
completions — each with a timestamp, event type, related file (where
one applies), and the AI mode active when it happened.

Populated entirely by subscribing to eventbus.bus (module docstring:
"every module should communicate through... the Event Bus") rather
than every caller remembering to call into this file directly — see
`wire_to_bus()`, called once from ui/app.py's on_mount. Nothing in
here imports Textual; ui/timeline_panel.py is the render layer.

Honest scope, stated up front rather than discovered later:
- In-memory only, capped at MAX_EVENTS (oldest dropped first). The
  roadmap's own list explicitly marks "Restore previous state" as a
  FUTURE feature, and persisting an unbounded activity log to disk by
  default has real cost/growth implications a first pass shouldn't
  quietly commit to — this can follow the exact JSON-store pattern
  projects.py/todos.py already use if that's wanted later.
- "Git Commits" as a tracked event type isn't populated: nothing in
  this codebase currently shells out to git or watches .git/ for new
  commits (a real implementation would need either a git plugin/hook
  or a polling watcher, both out of scope for what's otherwise a
  simple event-log feature) — the type is defined for completeness
  but nothing publishes it in this pass.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import time

from . import eventbus

MAX_EVENTS = 500

# Display labels for the roadmap's own tracked-event list, keyed by
# the eventbus topic that produces them.
_LABELS = {
    eventbus.FILE_CREATED: ("\U0001f4c4", "File Created"),
    eventbus.FILE_DELETED: ("\U0001f5d1", "File Deleted"),
    eventbus.FILE_RENAMED: ("\u270f\ufe0f", "File Renamed"),
    eventbus.FILE_SAVED: ("\U0001f4be", "File Saved"),
    eventbus.AI_RESPONSE_GENERATED: ("\U0001f916", "AI Response Generated"),
    eventbus.AI_FILE_EDIT: ("\u2728", "AI File Edit"),
    eventbus.TERMINAL_COMMAND: ("\u2318", "Terminal Command"),
    eventbus.WORKSPACE_OPENED: ("\U0001f4c1", "Workspace Opened"),
    eventbus.WORKSPACE_CLOSED: ("\U0001f4c1", "Workspace Closed"),
    eventbus.TODO_CREATED: ("\u2610", "Todo Created"),
    eventbus.TODO_COMPLETED: ("\u2611", "Todo Completed"),
    # v0.7.7 autonomous-preview events.
    eventbus.PACKAGE_INSTALLED: ("\U0001f4e6", "Package Installed"),
    eventbus.PACKAGE_FAILED: ("\u274c", "Package Install Failed"),
    eventbus.PIPELINE_STAGE: ("\U0001f501", "Pipeline Stage"),
    eventbus.PIPELINE_COMPLETED: ("\U0001f389", "Pipeline Completed"),
    eventbus.MODE_SWITCHED: ("\U0001f504", "AI Mode Switched"),
    eventbus.DEVICE_ACTION: ("\U0001f5a5\ufe0f", "Device Action"),
}


class TimelineEvent:
    __slots__ = ("timestamp", "topic", "icon", "label", "related_file", "ai_mode", "detail")

    def __init__(self, topic, related_file=None, ai_mode=None, detail="", timestamp=None):
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.topic = topic
        icon, label = _LABELS.get(topic, ("\u2022", topic))
        self.icon = icon
        self.label = label
        self.related_file = related_file
        self.ai_mode = ai_mode
        self.detail = detail

    def line(self):
        ts = time.strftime("%H:%M:%S", time.localtime(self.timestamp))
        parts = [f"{self.icon} [{ts}] {self.label}"]
        if self.related_file:
            parts.append(f"\u2014 {self.related_file}")
        if self.detail:
            parts.append(f"({self.detail})")
        return " ".join(parts)


_events = []
_wired = False


def record(topic, related_file=None, ai_mode=None, detail=""):
    ev = TimelineEvent(topic, related_file=related_file, ai_mode=ai_mode, detail=detail)
    _events.append(ev)
    del _events[:-MAX_EVENTS]
    return ev


def events():
    """Newest first — the natural reading order for an activity log."""
    return list(reversed(_events))


def clear():
    _events.clear()


def search(query):
    q = (query or "").strip().lower()
    if not q:
        return events()
    return [e for e in events() if q in e.label.lower()
            or (e.related_file and q in e.related_file.lower())
            or (e.detail and q in e.detail.lower())]


def filter_by_topic(topic):
    return [e for e in events() if e.topic == topic]


def wire_to_bus():
    """Subscribes this module to eventbus.bus so every publish() from
    anywhere in the app becomes a timeline entry automatically —
    callers of eventbus.bus.publish() never need to know Timeline
    exists. Safe to call more than once (only wires once)."""
    global _wired
    if _wired:
        return
    _wired = True
    for topic in _LABELS:
        eventbus.bus.subscribe(topic, _make_handler(topic))


def _make_handler(topic):
    def _handler(**data):
        record(topic,
               related_file=data.get("path") or data.get("related_file"),
               ai_mode=data.get("mode"),
               detail=data.get("detail", ""))
    return _handler
