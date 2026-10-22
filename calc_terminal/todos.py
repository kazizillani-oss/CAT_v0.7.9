"""
CCT — todos.py: AI Todo Manager (v0.7.2 roadmap). Manual + AI-detected
project tasks, persisted the same way projects.py persists recent
folders — a small dedicated JSON store, not part of config.py's
scalar-settings dataclass.

Todos are keyed by workspace path (`"__global__"` when no folder is
open), so opening a different project shows that project's own list
instead of one global bucket everything piles into.

AI-detection scope, stated plainly: "The AI should automatically
create... todos based on the conversation" is implemented here as a
real, working PATTERN-BASED scanner (detect_ai_todos below) over an
assistant reply's own text — Markdown checkbox lines (`- [ ] ...`) and
TODO/FIXME-style lines. It is NOT a dedicated LLM call that reasons
about "what should the user do next" — that would be a genuinely
different (and much more expensive, one-more-API-call-per-turn)
feature, and building it silently under the same name would overstate
what this does. The pattern scanner is real and useful (it catches
exactly the todo-shaped output AI replies already tend to produce in
Build/Agent mode), just narrower than a bespoke extraction model.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import json
import os
import re
import time

from . import eventbus

STORE_PATH = os.path.join(os.path.expanduser("~"), ".cct_todos.json")
GLOBAL_KEY = "__global__"
PRIORITIES = ("low", "normal", "high")

# v0.7.7: the live-todo vocabulary the autonomous pipeline (pipeline.py)
# drives — "done" stays for backward compatibility with existing stored
# todos; pipeline runs use the richer set below.
STATUSES = ("pending", "running", "researching", "coding", "testing",
            "completed", "skipped", "failed", "done")
DONE_STATUSES = ("completed", "done")


def _load():
    if not os.path.exists(STORE_PATH):
        return {}
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data):
    try:
        with open(STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


def _key(workspace):
    return workspace or GLOBAL_KEY


def _next_id(items):
    return (max((t["id"] for t in items), default=0)) + 1


def list_todos(workspace=None, include_done=True):
    data = _load()
    items = data.get(_key(workspace), [])
    if not include_done:
        items = [t for t in items if t["status"] not in DONE_STATUSES]
    return sorted(items, key=lambda t: (t["status"] in DONE_STATUSES, -PRIORITIES.index(t["priority"])
                                         if t["priority"] in PRIORITIES else 0, t["id"]))


def add_todo(text, workspace=None, priority="normal", due_date=None,
             tags=None, source="manual", status="pending"):
    text = (text or "").strip()
    if not text:
        return None
    data = _load()
    key = _key(workspace)
    items = data.setdefault(key, [])
    todo = {
        "id": _next_id(items),
        "text": text,
        "status": status if status in STATUSES else "pending",
        "priority": priority if priority in PRIORITIES else "normal",
        "due_date": due_date,
        "tags": tags or [],
        "source": source,   # "manual" | "ai"
        "created_at": time.time(),
        "completed_at": None,
    }
    items.append(todo)
    _save(data)
    eventbus.bus.publish(eventbus.TODO_CREATED, detail=text[:80])
    return todo


def update_todo(todo_id, workspace=None, **fields):
    """Edits any of text/priority/due_date/tags in place. Returns the
    updated todo, or None if todo_id isn't found."""
    data = _load()
    items = data.get(_key(workspace), [])
    for t in items:
        if t["id"] == todo_id:
            for k in ("text", "priority", "due_date", "tags"):
                if k in fields:
                    t[k] = fields[k]
            _save(data)
            eventbus.bus.publish(eventbus.TODO_UPDATED, detail=t["text"][:80])
            return t
    return None


def set_status(todo_id, status, workspace=None):
    data = _load()
    items = data.get(_key(workspace), [])
    for t in items:
        if t["id"] == todo_id:
            t["status"] = status
            t["completed_at"] = time.time() if status in DONE_STATUSES else None
            _save(data)
            if status in DONE_STATUSES:
                eventbus.bus.publish(eventbus.TODO_COMPLETED, detail=t["text"][:80])
            else:
                eventbus.bus.publish(eventbus.TODO_UPDATED, detail=t["text"][:80])
            return t
    return None


def delete_todo(todo_id, workspace=None):
    data = _load()
    key = _key(workspace)
    items = data.get(key, [])
    remaining = [t for t in items if t["id"] != todo_id]
    if len(remaining) == len(items):
        return False
    data[key] = remaining
    _save(data)
    eventbus.bus.publish(eventbus.TODO_DELETED)
    return True


def progress(workspace=None):
    items = list_todos(workspace)
    if not items:
        return 0.0, 0, 0
    done = sum(1 for t in items if t["status"] in DONE_STATUSES)
    return done / len(items), done, len(items)


def sync_pipeline_todos(pipeline_run, workspace=None):
    """Persists a pipeline's live todos into this workspace's todo store
    (pipeline.py drives the in-memory statuses; this mirrors them to the
    persistent store + eventbus so the Todo panel shows the same run).
    Reuses the persistent IDs where the text already exists. Returns the
    list of stored todo dicts."""
    stored = list_todos(workspace, include_done=True)
    for pt in pipeline_run.todos:
        match = next((t for t in stored
                      if t["text"] == pt["text"] and t.get("pipeline_run") == True), None)
        if match is None:
            stored.append(add_todo(pt["text"], workspace=workspace,
                                   source="ai", status=pt["status"],
                                   tags=["pipeline"]))
        else:
            set_status(match["id"], pt["status"], workspace=workspace)
    return stored


# ------------------------------------------------------- AI detection --
# Markdown checkbox: "- [ ] fix the thing" / "* [ ] fix the thing"
_CHECKBOX_RE = re.compile(r"^[ \t]*[-*][ \t]+\[ \][ \t]+(.+)$", re.MULTILINE)
# "TODO: fix the thing" / "FIXME - fix the thing" (line-anchored so it
# doesn't fire on the word "todo" mid-sentence)
_TODO_LINE_RE = re.compile(r"^[ \t]*(?:TODO|FIXME)[:\-][ \t]+(.+)$", re.MULTILINE | re.IGNORECASE)

# v0.7.10: Extended patterns for better AI todo extraction
# Task items: "- [ ] do something" (already covered by _CHECKBOX_RE)
# Action items: "ACTION: do something" or "Action: do something"
_ACTION_RE = re.compile(r"^[ \t]*(?:ACTION|ACTION ITEM)[:\-][ \t]+(.+)$", re.MULTILINE | re.IGNORECASE)
# Steps: "1. do something" or "Step 1: do something" (numbered lists)
_STEP_RE = re.compile(r"^[ \t]*(?:Step\s+)?(\d+)[\.\):\-][ \t]+(.+)$", re.MULTILINE | re.IGNORECASE)
# Recommendations: "I recommend you ..." or "You should ..."
_RECOMMENDATION_RE = re.compile(r"^[ \t]*(?:I recommend you|You should|You'll want to|Consider)[:\-][ \t]+(.+)$", re.MULTILINE | re.IGNORECASE)
# Next steps: "Next steps:" followed by a list
_NEXT_STEPS_RE = re.compile(r"^[ \t]*Next steps?:?\s*$", re.MULTILINE | re.IGNORECASE)
# Implementation items: "Implementation:" or "To implement:"
_IMPLEMENTATION_RE = re.compile(r"^[ \t]*(?:Implementation|To implement)[:\-][ \t]+(.+)$", re.MULTILINE | re.IGNORECASE)


def detect_ai_todos(assistant_text):
    """Enhanced AI-suggestion detector (v0.7.10): scans one assistant
    reply's text for multiple todo patterns:
    - Markdown checkbox lines (- [ ] ...)
    - TODO/FIXME-style lines
    - ACTION items
    - Numbered steps (1. do something)
    - Recommendations (I recommend, You should)
    - Implementation items

    Returns a list of plain-text candidates, deduplicated and capped
    at 15 per reply so one runaway response can't flood the list.
    Does not touch the todo store itself — callers decide whether/how
    to add them."""
    if not assistant_text:
        return []
    found = []
    # Original patterns
    for m in _CHECKBOX_RE.finditer(assistant_text):
        found.append(m.group(1).strip())
    for m in _TODO_LINE_RE.finditer(assistant_text):
        found.append(m.group(1).strip())
    # v0.7.10: New patterns
    for m in _ACTION_RE.finditer(assistant_text):
        found.append(m.group(1).strip())
    for m in _STEP_RE.finditer(assistant_text):
        text = m.group(2).strip()
        if len(text) > 5:  # Skip very short items
            found.append(text)
    for m in _RECOMMENDATION_RE.finditer(assistant_text):
        found.append(m.group(1).strip())
    for m in _IMPLEMENTATION_RE.finditer(assistant_text):
        found.append(m.group(1).strip())
    # Deduplicate and cap
    seen = set()
    out = []
    for text in found:
        key = text.lower()
        if key in seen or not text:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= 15:
            break
    return out
