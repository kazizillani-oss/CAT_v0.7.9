"""
Persistent memory for CCT's AI & Agent (v0.5.2).

Gives the AI and the Chemistry Agent a real, on-disk memory that survives
across restarts, so they can:

  * recall the previous turns of the *current* conversation (recent N),
  * remember durable facts about the user (their name, exam board, the
    topics they find hard, preferred units...) that either the user asked
    the AI to remember explicitly, or the AI proactively stashed,
  * recall "every movement of the person" — a lightweight activity log of
    what the user has solved/asked/simulated so far (topic frequencies +
    a timestamped recent-activity stream),
  * surface a short "what I know about you / what we just talked about"
    preamble that both /ai and /agent inject into their system prompt, so
    follow-up questions actually feel continuous instead of amnesiac.

Storage is one JSON file in the user's home dir (~/.cct_memory.json),
written defensively (temp-file + atomic replace) so a crash mid-write
never corrupts the whole memory. Everything here is best-effort: any I/O
failure degrades to an empty in-memory store rather than crashing the app.
"""

if __name__ == '__main__':
    print("This is a library file and is not meant to be run directly.")
    print("Please run 'python main.py' or 'python model.py' from the project root directory.")
    import sys
    sys.exit(1)

import json
import os
import re
import time

MEMORY_FILE = os.path.join(os.path.expanduser("~"), ".cct_memory.json")

# How much to keep in RAM / inject into prompts. Kept modest so the
# injected context never bloats a request past a provider's token budget.
MAX_TURNS = 24        # recent conversation turns (user+assistant pairs counted as 2)
MAX_FACTS = 40        # durable user facts
MAX_ACTIVITY = 60     # timestamped "what the person did" events
MAX_TOPICS = 30       # distinct topic frequency counters


# ------------------------------------------------------------------- load/save
def _empty():
    return {
        "turns": [],      # [{"role":"user"/"assistant", "text":..., "t": epoch, "mode": "ai"/"agent"}]
        "facts": [],      # ["the user's name is Aarav", "exam board: CBSE class 12", ...]
        "activity": [],   # [{"type":..., "label":..., "t": epoch}]
        "topics": {},     # {"first order": 5, "mole concept": 2, ...}
        "created": time.time(),
        "updated": time.time(),
    }


def load():
    """Load the memory dict, or a fresh empty one if none/invalid."""
    if not os.path.exists(MEMORY_FILE):
        return _empty()
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _empty()
        # Backfill any missing keys (forward-compatible with older files).
        base = _empty()
        base.update(data)
        for k in ("turns", "facts", "activity"):
            if not isinstance(base.get(k), list):
                base[k] = []
        if not isinstance(base.get("topics"), dict):
            base["topics"] = {}
        return base
    except Exception:
        return _empty()


def save(mem):
    """Atomic write: serialize to a temp file in the same dir, then
    os.replace() onto the real path. Avoids the half-written-file
    corruption window a plain open(w)+dump leaves open."""
    try:
        mem["updated"] = time.time()
        d = os.path.dirname(MEMORY_FILE) or "."
        tmp = MEMORY_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(mem, f, ensure_ascii=False, indent=1)
        os.replace(tmp, MEMORY_FILE)
    except Exception:
        # Memory is best-effort; never let a write failure break the chat.
        pass


# ------------------------------------------------------------------- mutations
def add_turn(role, text, mode="ai"):
    """Append a conversation turn (role: 'user' or 'assistant') and trim
    to the last MAX_TURNS entries. Persists immediately so a crash right
    after a reply still keeps it."""
    if not text:
        return
    mem = load()
    mem["turns"].append({
        "role": role,
        "text": str(text).strip()[:4000],   # cap each turn so one huge
        "t": time.time(),                    # notebook answer can't
        "mode": mode,                        # crowd out all the others
    })
    mem["turns"] = mem["turns"][-MAX_TURNS:]
    save(mem)


def add_activity(event_type, label):
    """Record one 'movement' — anything the person did: asked a question,
    solved a numerical, ran a simulation, played the quiz..."""
    if not label:
        return
    add_activities([(event_type, label)])


def add_activities(pairs):
    """v0.7.9.0 batch form of add_activity: one load→append→save cycle for
    N events instead of one full-file rewrite per event. `pairs` is an
    iterable of (event_type, label)."""
    pairs = [(str(t), str(l).strip()[:200]) for t, l in (pairs or []) if l]
    if not pairs:
        return
    mem = load()
    now = time.time()
    for event_type, label in pairs:
        mem["activity"].append({"type": event_type, "label": label, "t": now})
    mem["activity"] = mem["activity"][-MAX_ACTIVITY:]
    save(mem)


def bump_topic(topic):
    """Increment a topic's frequency counter — powers the 'you've asked
    about X a lot' recall."""
    topic = (topic or "").strip().lower()
    if not topic:
        return
    mem = load()
    mem["topics"][topic] = mem["topics"].get(topic, 0) + 1
    # Keep the dict bounded by dropping the least-used once it grows.
    if len(mem["topics"]) > MAX_TOPICS:
        for k, _ in sorted(mem["topics"].items(), key=lambda kv: kv[1])[: len(mem["topics"]) - MAX_TOPICS]:
            del mem["topics"][k]
    save(mem)


def add_fact(fact):
    """Store a durable user fact (the AI's long-term memory about the
    person). De-duplicated case-insensitively so 'remember my name is X'
    twice doesn't leave two copies."""
    fact = (fact or "").strip()
    if not fact:
        return False
    mem = load()
    existing = {f.lower().rstrip(".") for f in mem["facts"]}
    if fact.lower().rstrip(".") in existing:
        return False
    mem["facts"].append(fact[:400])
    mem["facts"] = mem["facts"][-MAX_FACTS:]
    save(mem)
    return True


def clear():
    """Wipe the entire memory (used by /memory -> clear)."""
    save(_empty())


# ------------------------------------------------------- fact auto-detection
_REMEMBER_RE = re.compile(
    r"\b(?:remember|note|don'?t forget|keep in mind|fyi|for your info|"
    r"my name is|i am|i'm|call me|my exam|my board|my class|my grade|"
    r"i prefer|i like|i find|i struggle|i'm weak|i'm good)\b",
    re.IGNORECASE,
)


def maybe_extract_fact(text):
    """Heuristic: if the user phrases something as something to remember
    ('remember my exam is in may', 'my name is aarav', 'i prefer SI
    units'), stash the whole sentence as a durable fact. Returns the fact
    string if one was stored, else None.

    Intentionally permissive — it's better to over-remember a harmless
    sentence than to miss 'my name is X'. The AI can also stash facts
    deliberately via the agent's 'remember' field."""
    if not text:
        return None
    # Only short, declarative-looking lines make good facts — a full
    # multi-line numerical isn't something to "remember" wholesale.
    sentences = re.split(r"(?<=[.!?])\s+|\n", text.strip())
    for s in sentences:
        s = s.strip(" -\u2022")
        if 4 <= len(s) <= 160 and _REMEMBER_RE.search(s):
            return s
    return None


# ------------------------------------------------------------ prompt building
def recent_turns(n=8, mode=None):
    """Return the last `n` turns as a list of dicts, optionally filtered
    to a single mode ('ai' or 'agent')."""
    mem = load()
    turns = mem["turns"]
    if mode:
        turns = [t for t in turns if t.get("mode") == mode]
    return turns[-n:]


def _fmt_ago(epoch):
    """Human 'x min/h/d ago' for the activity log."""
    try:
        secs = max(0, int(time.time() - float(epoch)))
    except Exception:
        return ""
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


def _keywords(text):
    """Small keyword set for relevance scoring (lowercased, len>=3,
    deduped). Deliberately tiny — this must stay microseconds-cheap."""
    return {w for w in re.findall(r"[a-z0-9]{3,}", (text or "").lower())}


def context_block(mode="ai", max_turns=8, query=None):
    """Build the 'memory' preamble injected into the AI/Agent system
    prompt. Returns a single string (empty if there's genuinely nothing
    worth recalling), e.g.:

        ## What you remember about the user
        - the user's name is Aarav
        - exam board: CBSE class 12

        ## Recent conversation (last 6 turns)
        USER: what is a first order reaction?
        ASSISTANT: A first order reaction is one whose rate...

        ## User's recent activity
        - solved a first order numerical (12m ago)

        Use this context to make your answer continuous and personal.
        Refer to earlier turns by all means; don't re-ask what's known.

    v0.7.9.0 — memory must not make CAT slow (requirement #13): when a
    `query` is given, facts and turns are RELEVANCE-FILTERED by cheap
    keyword overlap instead of dumping everything, and the activity log /
    topic list are only included when they actually relate to the query.
    """
    mem = load()
    qk = _keywords(query) if query else set()
    parts = []

    facts = mem.get("facts", [])
    if qk:
        def _rel(text):
            return len(qk & _keywords(text))
        scored = [(f, _rel(f)) for f in facts[-24:]]
        relevant = [f for f, s in scored if s > 0]
        facts = (relevant + facts[-4:]) if relevant else facts[-6:]
    if facts:
        seen = set()
        uniq = []
        for f in facts:
            k = f.lower()
            if k not in seen:
                seen.add(k)
                uniq.append(f)
        parts.append("## What you remember about the user")
        parts.extend(f"- {f}" for f in uniq[-12:])
        parts.append("")

    turns = mem.get("turns", [])
    if mode:
        turns = [t for t in turns if t.get("mode") == mode]
    recent = turns[-max_turns:]
    if qk:
        # Relevant-but-older turns first, then the most recent few for
        # conversational continuity — capped so the block stays small.
        older = [t for t in turns[:-max_turns] if qk & _keywords(t.get("text", ""))][-3:]
        turns = (older + recent)[-max_turns:] if older else recent
    else:
        turns = recent
    if turns:
        parts.append(f"## Recent conversation ({len(turns)} turn(s))")
        for t in turns:
            who = "USER" if t.get("role") == "user" else "ASSISTANT"
            txt = t.get("text", "").replace("\n", " ")
            if len(txt) > 280:
                txt = txt[:277] + "..."
            parts.append(f"{who}: {txt}")
        parts.append("")

    # Activity + topics only when they relate to the query — otherwise
    # they're pure token cost on every request.
    if qk:
        rel_activity = [a for a in mem.get("activity", [])[-30:]
                        if qk & _keywords(a.get("label", ""))][-5:]
    else:
        rel_activity = mem.get("activity", [])[-8:]
    if rel_activity:
        parts.append("## User's recent activity")
        for a in reversed(rel_activity):
            parts.append(f"- {a.get('label', a.get('type', ''))} ({_fmt_ago(a.get('t'))})")
        parts.append("")

    topics = sorted(mem.get("topics", {}).items(), key=lambda kv: kv[1], reverse=True)
    if topics:
        top = ", ".join(f"{k} ({v})" for k, v in topics[:5])
        parts.append(f"## Topics the user asks about most\n{top}")
        parts.append("")

    if parts:
        parts.append("Use this context to make your answer continuous and personal. "
                     "Refer to earlier turns by all means; do not re-ask anything already known.")
    return "\n".join(parts)


def stats():
    """A small summary dict for the /memory view screen."""
    mem = load()
    return {
        "turns": len(mem.get("turns", [])),
        "facts": len(mem.get("facts", [])),
        "activity": len(mem.get("activity", [])),
        "topics": len(mem.get("topics", {})),
        "updated": mem.get("updated", mem.get("created", 0)),
    }
