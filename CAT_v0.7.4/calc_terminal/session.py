"""
CCT chat session state — a plain data model for the conversation, with
no rendering and no widget dependencies. calc_terminal/ui/ renders this;
this module owns it.

Deliberately separate from `App.history` (calc_terminal/app.py), which
is the list of *solved notebooks* (numerical results the calculator
commands produce) — a different, older concept this refactor doesn't
touch. `ChatSession` is specifically the turn-by-turn chat transcript
the primary UI shows.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import itertools
import time

from . import ai_modes

_id_counter = itertools.count(1)


def next_turn_id():
    """One monotonically increasing id per process — good enough to key
    widgets and correlate MessageStarted/Chunk/Finished events; not
    persisted, so it resets each run."""
    return f"turn-{next(_id_counter)}"


class Turn:
    """One conversation turn: a user message, or an assistant reply
    (streaming or finished), or a system/permission note.

    `role` is one of "user", "assistant", "system".
    `status` is one of "complete" (default), "streaming", "error".

    Every Turn is also a permanent snapshot of the AI mode that created
    it. `mode` and `mode_snapshot` are captured exactly once, in
    __init__, from whatever ai_modes.current_mode() is *at that
    instant* — never re-read afterwards. That's deliberate: this is the
    fix for the old bug where switching AI modes (Notebook -> Agent ->
    Build -> ...) repainted every message already on screen, not just
    new ones. A Turn's mode never changes after creation, so anything
    that renders from `turn.mode_snapshot` (see ui/conversation.py)
    renders the mode the message was actually created in, forever,
    regardless of how many times the user switches modes afterwards.
    `mode_snapshot` is a plain dict from ai_modes.snapshot() — label,
    icon, accent hex/rgb — with no live reference back to ai_modes, so
    it can't drift even if ai_modes.MODE_META itself is ever mutated.

    `provider`/`model`/`workspace`/`simulation_id` are likewise
    point-in-time metadata the caller may supply at creation (e.g. the
    AI provider/model configured when an assistant reply was
    generated, or the active workspace) — plain data, not live lookups.

    `parent_turn_id` is the "Conversation Architecture" metadata the
    v0.7.2 context-menu spec asks for: for an assistant turn, the id
    of the user turn that prompted it (set by
    ui/app.py._begin_assistant_turn). This is what lets "Try Again in
    <mode>" retrieve the original prompt reliably by id instead of
    guessing from list position, which breaks the moment any turn is
    removed (see Revert) or reordered.
    """

    __slots__ = ("turn_id", "role", "text", "status", "created_at",
                 "duration", "usage", "attachments",
                 "mode", "mode_snapshot", "provider", "model",
                 "workspace", "simulation_id", "parent_turn_id")

    def __init__(self, turn_id, role, text="", status="complete",
                 attachments=None, mode=None, provider=None, model=None,
                 workspace=None, simulation_id=None, parent_turn_id=None):
        self.turn_id = turn_id
        self.role = role
        self.text = text
        self.status = status
        self.created_at = time.time()
        self.duration = 0.0
        self.usage = {}
        self.attachments = attachments or []
        # Frozen at creation — see class docstring. `mode` defaults to
        # whatever's active right now (the normal case); callers that
        # already know the mode a turn belongs to (e.g. restoring one)
        # can pass it explicitly instead.
        self.mode = mode if mode in ai_modes.MODE_META else ai_modes.current_mode()
        self.mode_snapshot = ai_modes.snapshot(self.mode)
        self.provider = provider
        self.model = model
        self.workspace = workspace
        self.simulation_id = simulation_id
        self.parent_turn_id = parent_turn_id

    def append(self, fragment):
        self.text += fragment

    def finish(self, full_text=None, duration=0.0, usage=None):
        if full_text is not None:
            self.text = full_text
        self.status = "complete"
        self.duration = duration
        self.usage = usage or {}


class ChatSession:
    """The full transcript for one run of the primary UI. Holds every
    `Turn` in order; the UI only ever appends to what it mounts — this
    object is the record it appends *from*, so scrollback beyond what's
    currently mounted can be regenerated instead of staying resident as
    live widgets (see ui/conversation.py's virtualization notes)."""

    # How many recent turns stay verbatim in every AI request. Once the
    # un-folded backlog grows past KEEP_VERBATIM + FOLD_HEADROOM, the
    # oldest excess turns get condensed into `older_summary` instead of
    # being sent (or dropped) raw — see summarize_older_turns().
    KEEP_VERBATIM = 16
    FOLD_HEADROOM = 8

    def __init__(self):
        self.turns = []
        self.notebook_mode = "NOTEBOOK"
        self.workspace = None
        self.model_name = None
        self.older_summary = ""   # condensed memory of turns older than what's kept verbatim
        self._folded_count = 0    # how many leading non-system turns are already folded in

    def add_user_turn(self, text, attachments=None, mode=None, workspace=None):
        turn = Turn(next_turn_id(), "user", text, status="complete",
                    attachments=attachments, mode=mode, workspace=workspace)
        self.turns.append(turn)
        return turn

    def start_assistant_turn(self, mode=None, provider=None, model=None,
                              workspace=None, simulation_id=None, parent_turn_id=None):
        turn = Turn(next_turn_id(), "assistant", "", status="streaming",
                    mode=mode, provider=provider, model=model,
                    workspace=workspace, simulation_id=simulation_id,
                    parent_turn_id=parent_turn_id)
        self.turns.append(turn)
        return turn

    def index_of(self, turn_id):
        """Position of `turn_id` in self.turns, or None. Used by Revert
        to truncate the transcript at the right point."""
        for i, t in enumerate(self.turns):
            if t.turn_id == turn_id:
                return i
        return None

    def add_system_turn(self, text, mode=None):
        turn = Turn(next_turn_id(), "system", text, status="complete", mode=mode)
        self.turns.append(turn)
        return turn

    def get(self, turn_id):
        for t in self.turns:
            if t.turn_id == turn_id:
                return t
        return None

    def clear(self):
        self.turns = []
        self.older_summary = ""
        self._folded_count = 0

    def __len__(self):
        return len(self.turns)

    def fork_upto(self, turn_id):
        """Fork Conversation (context-menu spec): returns a brand-new
        ChatSession carrying a shallow copy of every turn up to and
        including `turn_id`, plus the same workspace/model_name/
        older_summary state — so the fork starts with identical
        context instead of an empty transcript. `self` (the original
        session) is left completely untouched, which is what makes
        this a real fork rather than a rename/move of the current one.
        Returns None if turn_id isn't found."""
        idx = self.index_of(turn_id)
        if idx is None:
            return None
        new_session = ChatSession()
        new_session.turns = list(self.turns[:idx + 1])
        new_session.notebook_mode = self.notebook_mode
        new_session.workspace = self.workspace
        new_session.model_name = self.model_name
        new_session.older_summary = self.older_summary
        new_session._folded_count = min(self._folded_count, len(new_session.turns))
        return new_session

    def as_prompt_history(self, limit=None, before_turn_id=None,
                          include_attachment_context=True, mode=None):
        """Plain (role, text) pairs for callers (e.g. aicore) that want
        conversational context rather than a single one-shot prompt.
        Business logic reads this; it does not itself talk to the AI.

        v0.7.9.6 (AI Reliability Contract - Mode Isolation):
        When `mode` is specified, turns from unrelated AI modes (such as
        large research papers, debugger stack traces, or planning trees)
        are excluded to prevent cross-mode context contamination.
        """
        non_system = [t for t in self.turns if t.role != "system"]
        if before_turn_id is not None:
            idx = next((i for i, t in enumerate(non_system) if t.turn_id == before_turn_id),
                       len(non_system))
            non_system = non_system[:idx]
        unfolded = non_system[self._folded_count:]

        # Mode isolation filtering
        if mode:
            target_mode = str(mode).lower()
            compatible = {target_mode}
            if target_mode in ("chat", "notebook"):
                compatible.update({"chat", "notebook"})
            elif target_mode in ("code", "build"):
                compatible.update({"code", "build"})

            # Filter turns to compatible modes only
            isolated = []
            for t in unfolded:
                t_mode = str(getattr(t, "mode", "chat") or "chat").lower()
                if t_mode in compatible:
                    isolated.append(t)
                elif len(t.text or "") < 200 and t_mode in ("chat", "notebook"):
                    # Allow short conversational pleasantries across modes
                    isolated.append(t)
            unfolded = isolated

        if limit is not None:
            unfolded = unfolded[-limit:]
        out = []
        for t in unfolded:
            if not t.text and not t.attachments:
                continue
            text = t.text
            if include_attachment_context and t.role == "user" and t.attachments:
                from . import attachments as _att
                ctx = _att.AttachmentManager.build_context(t.attachments)
                if ctx:
                    text = (text + "\n\n" + ctx).strip() if text else ctx
            out.append((t.role, text))
        if self.older_summary and (mode is None or str(mode).lower() in ("chat", "notebook")):
            out.insert(0, ("user", f"[Summary of earlier conversation, for context — "
                                     f"do not repeat it back verbatim]\n{self.older_summary}"))
        return out

    def needs_summarization(self):
        """True once there's enough un-folded backlog to be worth the
        extra summarization call — leaves headroom so this doesn't
        trigger on every single message once it crosses the line."""
        non_system = [t for t in self.turns if t.role != "system"]
        unfolded_count = len(non_system) - self._folded_count
        return unfolded_count > (self.KEEP_VERBATIM + self.FOLD_HEADROOM)

    def summarize_older_turns(self, summarizer):
        """Folds everything but the most recent KEEP_VERBATIM turns into
        `older_summary`, using `summarizer(prompt, system_prompt=...)`
        (e.g. aicore.query_ai) to condense them. Safe to call on every
        turn — it's a no-op unless needs_summarization() is True, and
        it never touches self.turns, so the UI's scrollback is
        unaffected either way; only what gets *sent* to the model
        changes. Best-effort: if the summarizer call fails or returns
        an error string, the un-folded turns are simply left as-is and
        get sent verbatim (or re-attempted next turn) instead of being
        silently lost."""
        if not self.needs_summarization():
            return
        non_system = [t for t in self.turns if t.role != "system"]
        unfolded = non_system[self._folded_count:]
        to_fold = unfolded[:-self.KEEP_VERBATIM]
        if not to_fold:
            return
        transcript = "\n".join(f"{t.role}: {t.text}" for t in to_fold)
        prior = f"Existing summary so far:\n{self.older_summary}\n\n" if self.older_summary else ""
        prompt = (
            f"{prior}Condense the following older chat turns into a short, factual "
            f"summary (plain text, under 200 words) that preserves names, numbers, "
            f"decisions, and any options/lists the assistant offered — so a later "
            f"reply like 'option 3' or 'the second one' still makes sense against "
            f"it:\n\n{transcript}"
        )
        try:
            summary = summarizer(
                prompt, system_prompt="You compress chat history into a short, factual summary. "
                                       "Be concise; preserve specifics, not vibes.")
        except Exception:
            return  # best-effort — verbatim turns stay un-folded and get sent as-is
        if not summary or summary.startswith((
                "Error", "AI not configured", "Could not reach", "The AI request timed out",
                "Provider '", "The 'requests' library")):
            return  # looks like an error string from aicore, not a real summary
        self.older_summary = summary.strip()
        self._folded_count += len(to_fold)
