"""
CCT — eventbus.py: the Workspace Event Bus the v0.7.2 roadmap doc asks
every backend module to communicate through ("Avoid placing all logic
inside one file... every module should communicate through the
Workspace Manager and Event Bus").

Deliberately separate from ui/events.py's Textual `Message` classes,
which stay exactly as they are — those are UI-thread widget-to-widget
messages, already working, and this pass isn't rewriting that
architecture. This bus is for the plain-Python backend modules
(todos.py, timeline.py, and anything future — TodoManager/
TimelineManager/DashboardManager in the roadmap's own suggested
naming) that have no reason to depend on Textual at all. CCTApp is the
one place that bridges the two: it subscribes bus topics to its own UI
updates in ui/app.py's on_mount, the same way it already turns worker-
thread results into posted ui/events.py Messages via call_from_thread.

Plain pub/sub, synchronous, in-process. No persistence, no cross-
process delivery, no priority/ordering guarantees beyond "subscribers
fire in the order they subscribed" — this is a lightweight backbone
for wiring already-in-process modules together, not a message queue.
A single module-level `bus` instance is the one every module below
imports and uses (`from .. import eventbus` / `from . import
eventbus`, then `eventbus.bus.publish(...)`), mirroring the
existing single-module-level-store convention projects.py/config.py
already use instead of a class the caller has to instantiate.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import time
import traceback

# Topic names — the roadmap's own "Track events such as" list for the
# Session Timeline doubles as a reasonable topic vocabulary for the
# whole bus, since nearly everything else (Todo, Dashboard) wants to
# react to the same underlying happenings.
FILE_CREATED = "file_created"
FILE_DELETED = "file_deleted"
FILE_RENAMED = "file_renamed"
FILE_SAVED = "file_saved"
AI_RESPONSE_GENERATED = "ai_response_generated"
AI_FILE_EDIT = "ai_file_edit"
TERMINAL_COMMAND = "terminal_command"
WORKSPACE_OPENED = "workspace_opened"
WORKSPACE_CLOSED = "workspace_closed"
TODO_CREATED = "todo_created"
TODO_COMPLETED = "todo_completed"
TODO_UPDATED = "todo_updated"
TODO_DELETED = "todo_deleted"

# v0.7.7 autonomous-preview topics.
PACKAGE_INSTALLED = "package_installed"
PACKAGE_FAILED = "package_failed"
PIPELINE_STAGE = "pipeline_stage"
PIPELINE_COMPLETED = "pipeline_completed"
MODE_SWITCHED = "mode_switched"
DEVICE_ACTION = "device_action"

# v0.7.9.0 explicit agent-tool filesystem topics (requirement: CAT's own
# file tools must announce their changes immediately, so the Explorer can
# react while the OS watcher confirms the real on-disk state):
TOOL_FILE_CREATED = "tool_file_created"
TOOL_FILE_DELETED = "tool_file_deleted"
TOOL_FILE_MOVED = "tool_file_moved"
TOOL_DIRECTORY_CHANGED = "tool_directory_changed"

# Vision topics (v0.8.a — spec 41, mirrored with event_stream names)
VISION_SESSION_STARTED = "VISION_SESSION_STARTED"
VISION_SESSION_STOPPED = "VISION_SESSION_STOPPED"
VISION_CAPTURE_STARTED = "VISION_CAPTURE_STARTED"
VISION_CAPTURE_ENDED = "VISION_CAPTURE_ENDED"
VISION_FRAME_SELECTED = "VISION_FRAME_SELECTED"
VISION_FRAME_ANALYZED = "VISION_FRAME_ANALYZED"
VISION_CURSOR_EVENT = "VISION_CURSOR_EVENT"
VISION_ANNOTATION_CREATED = "VISION_ANNOTATION_CREATED"
VISION_ANNOTATION_UPDATED = "VISION_ANNOTATION_UPDATED"
VISION_ANNOTATION_DELETED = "VISION_ANNOTATION_DELETED"
VISION_USER_MESSAGE = "VISION_USER_MESSAGE"
VISION_AI_ANALYSIS = "VISION_AI_ANALYSIS"
VISION_FIX_PROPOSED = "VISION_FIX_PROPOSED"
VISION_FIX_APPLIED = "VISION_FIX_APPLIED"
VISION_PREVIEW_REFRESHED = "VISION_PREVIEW_REFRESHED"
VISION_VERIFICATION_COMPLETE = "VISION_VERIFICATION_COMPLETE"


class EventBus:
    def __init__(self):
        self._subs = {}  # topic -> list[callable]

    def subscribe(self, topic, callback):
        """Registers `callback(**data)` for `topic`. Returns `callback`
        unchanged so a caller can do
        `self._sub = bus.subscribe(TOPIC, self._on_topic)` and later
        pass that same reference to unsubscribe()."""
        self._subs.setdefault(topic, []).append(callback)
        return callback

    def unsubscribe(self, topic, callback):
        subs = self._subs.get(topic)
        if not subs:
            return
        try:
            subs.remove(callback)
        except ValueError:
            pass

    def publish(self, topic, **data):
        """Fires every subscriber for `topic` synchronously, in
        subscribe order. `data.setdefault("ts", ...)` stamps every
        event with a publish time so a subscriber (Timeline, mainly)
        never has to remember to do it itself. A subscriber that
        raises is logged (via Python's stdlib logging, not print() —
        printing anything to stdout inside a running Textual app
        corrupts the alt-screen, same reason ui/composer.py's own
        error path uses self.log.error() instead) and does not stop
        the remaining subscribers from still running — one broken
        listener (e.g. a Timeline panel mid-teardown) must not be able
        to silently break Todo/Dashboard updates too."""
        data.setdefault("ts", time.time())
        for callback in list(self._subs.get(topic, [])):
            try:
                callback(**data)
            except Exception:
                import logging
                logging.getLogger("cct.eventbus").error(
                    "subscriber for %r raised:\n%s", topic, traceback.format_exc())


bus = EventBus()
