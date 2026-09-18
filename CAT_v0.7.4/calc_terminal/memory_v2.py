"""Layered memory system for CCT: session, long-term (SQLite), and per-project memory."""

import json
import os
import re
import sqlite3
import threading
import time
import hashlib
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


VALID_CATEGORIES = {
    "user_preferences",
    "programming_preferences",
    "project_preferences",
    "important_instructions",
    "workflow_preferences",
    "conversation_facts",
    "project_facts",
    "custom",
}

API_KEY_PATTERNS = [
    re.compile(r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?([A-Za-z0-9_\-]{16,})["\']?'),
    re.compile(r'(?i)(secret|token|password|passwd|pwd)\s*[:=]\s*["\']?([^\s"\']{8,})["\']?'),
    re.compile(r'(?i)(bearer)\s+([A-Za-z0-9_\-\.]{20,})'),
    re.compile(r'["\']([A-Za-z0-9_\-]{32,})["\']'),
]

REDACTED_PLACEHOLDER = "[REDACTED]"


def _sanitize_content(text: str) -> str:
    """Detect and redact API keys, passwords, tokens before storage."""
    sanitized = text
    for pattern in API_KEY_PATTERNS:
        sanitized = pattern.sub(lambda m: f"{m.group(1)}={REDACTED_PLACEHOLDER}", sanitized)
    return sanitized


def _similarity(a: str, b: str) -> float:
    """Simple lowercase token-based similarity (Jaccard)."""
    set_a = set(a.lower().split())
    set_b = set(b.lower().split())
    if not set_a or not set_b:
        return 1.0 if a.lower() == b.lower() else 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


@dataclass
class Memory:
    id: str = ""
    category: str = "conversation_facts"
    content: str = ""
    source: str = "user"
    created_at: float = 0.0
    updated_at: float = 0.0
    importance: float = 0.5
    confidence: float = 1.0
    last_used: float = 0.0
    project_path: str = ""

    def __post_init__(self):
        now = time.time()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        if not self.id:
            raw = f"{self.content}{self.created_at}{os.urandom(8).hex()}"
            self.id = hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Memory":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class MemoryManager:
    """Manages session, long-term, and per-project memory."""

    def __init__(self, memory_dir: Optional[str] = None):
        self.memory_dir = memory_dir or os.path.join(os.path.expanduser("~"), ".cct_memory_v2")
        os.makedirs(self.memory_dir, exist_ok=True)

        self._session: List[Dict[str, str]] = []

        self._db_path = os.path.join(self.memory_dir, "cct_memory.db")
        self._init_db()

        self._project_memories: Dict[str, List[Dict[str, Any]]] = {}
        self._load_all_project_memories()

    # ── SQLite setup ──────────────────────────────────────────────────────

    def _get_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_db()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT DEFAULT 'user',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    importance REAL DEFAULT 0.5,
                    confidence REAL DEFAULT 1.0,
                    last_used REAL DEFAULT 0.0,
                    project_path TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC)"
            )
            conn.commit()
        finally:
            conn.close()

    # ── Session memory ────────────────────────────────────────────────────

    def add_session_turn(self, role: str, text: str, mode: str = "chat") -> None:
        """Append a turn to the in-memory session log."""
        self._session.append({
            "role": role,
            "text": text,
            "mode": mode,
            "timestamp": str(time.time()),
        })

    def get_session_context(self, max_turns: int = 20) -> List[Dict[str, str]]:
        """Return the last *max_turns* session turns."""
        return self._session[-max_turns:]

    def clear_session(self) -> None:
        """Clear all session turns."""
        self._session.clear()

    # ── Long-term memory (SQLite) ─────────────────────────────────────────

    def store_memory(
        self,
        category: str,
        content: str,
        importance: float = 0.5,
        confidence: float = 1.0,
        source: str = "user",
    ) -> Memory:
        """Store a new memory record. Returns the created Memory."""
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category '{category}'. Must be one of {VALID_CATEGORIES}")

        sanitized = _sanitize_content(content)
        mem = Memory(
            category=category,
            content=sanitized,
            source=source,
            importance=importance,
            confidence=confidence,
        )

        conn = self._get_db()
        try:
            conn.execute(
                """
                INSERT INTO memories (id, category, content, source, created_at,
                                      updated_at, importance, confidence, last_used, project_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mem.id, mem.category, mem.content, mem.source,
                    mem.created_at, mem.updated_at, mem.importance,
                    mem.confidence, mem.last_used, mem.project_path,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return mem

    def retrieve_memories(self, query: str = "", limit: int = 10) -> List[Memory]:
        """Retrieve memories, optionally filtered by a query string."""
        conn = self._get_db()
        try:
            if query:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE content LIKE ? ORDER BY importance DESC, created_at DESC LIMIT ?",
                    (f"%{query}%", limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memories ORDER BY importance DESC, created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()

            results = []
            for row in rows:
                mem = Memory(**dict(row))
                mem.last_used = time.time()
                results.append(mem)

            if results:
                ids = [r.id for r in results]
                placeholders = ",".join("?" for _ in ids)
                conn.execute(
                    f"UPDATE memories SET last_used = ? WHERE id IN ({placeholders})",
                    [time.time()] + ids,
                )
                conn.commit()

            return results
        finally:
            conn.close()

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by id. Returns True if a row was removed."""
        conn = self._get_db()
        try:
            cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def deduplicate(self) -> int:
        """Remove duplicate memories by text similarity. Returns count removed."""
        conn = self._get_db()
        try:
            rows = conn.execute(
                "SELECT id, content FROM memories ORDER BY created_at"
            ).fetchall()

            to_remove: List[str] = []
            seen: List[str] = []

            for row in rows:
                rid = row["id"]
                content = row["content"]
                is_dup = False
                for existing in seen:
                    if _similarity(content, existing) > 0.85:
                        is_dup = True
                        break
                if is_dup:
                    to_remove.append(rid)
                else:
                    seen.append(content)

            if to_remove:
                placeholders = ",".join("?" for _ in to_remove)
                conn.execute(
                    f"DELETE FROM memories WHERE id IN ({placeholders})", to_remove
                )
                conn.commit()

            return len(to_remove)
        finally:
            conn.close()

    def search_memories(self, query: str) -> List[Memory]:
        """Search memories whose content contains the query."""
        conn = self._get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM memories WHERE content LIKE ? ORDER BY importance DESC",
                (f"%{query}%",),
            ).fetchall()
            return [Memory(**dict(r)) for r in rows]
        finally:
            conn.close()

    def get_all_memories(self) -> List[Memory]:
        """Return every stored memory."""
        conn = self._get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY importance DESC"
            ).fetchall()
            return [Memory(**dict(r)) for r in rows]
        finally:
            conn.close()

    def get_memories_by_category(self, category: str) -> List[Memory]:
        """Return all memories in *category*."""
        conn = self._get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM memories WHERE category = ? ORDER BY importance DESC",
                (category,),
            ).fetchall()
            return [Memory(**dict(r)) for r in rows]
        finally:
            conn.close()

    def update_memory(self, memory_id: str, **kwargs) -> Optional[Memory]:
        """Update fields on an existing memory. Returns updated Memory or None."""
        allowed = {
            "category", "content", "source", "importance",
            "confidence", "project_path", "last_used",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return None

        if "category" in updates and updates["category"] not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category '{updates['category']}'")

        if "content" in updates:
            updates["content"] = _sanitize_content(updates["content"])

        updates["updated_at"] = time.time()

        conn = self._get_db()
        try:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [memory_id]
            cur = conn.execute(
                f"UPDATE memories SET {set_clause} WHERE id = ?", values
            )
            conn.commit()

            if cur.rowcount == 0:
                return None

            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            return Memory(**dict(row)) if row else None
        finally:
            conn.close()

    # ── Project memory (per-project JSON) ─────────────────────────────────

    def _project_file(self, project_path: str) -> str:
        safe = hashlib.sha256(project_path.encode()).hexdigest()[:12]
        return os.path.join(self.memory_dir, f"project_{safe}.json")

    def _load_all_project_memories(self) -> None:
        """Pre-load all project JSON files into memory."""
        for fname in os.listdir(self.memory_dir):
            if fname.startswith("project_") and fname.endswith(".json"):
                fpath = os.path.join(self.memory_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    path_key = data.get("_project_path", fname)
                    self._project_memories[path_key] = data.get("facts", [])
                except (json.JSONDecodeError, OSError):
                    continue

    def _save_project(self, project_path: str) -> None:
        fpath = self._project_file(project_path)
        data = {
            "_project_path": project_path,
            "facts": self._project_memories.get(project_path, []),
        }
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def store_project_fact(
        self, project_path: str, fact: str, category: str = "general"
    ) -> None:
        """Store a fact associated with a specific project."""
        sanitized = _sanitize_content(fact)
        entry = {
            "fact": sanitized,
            "category": category,
            "timestamp": time.time(),
        }
        self._project_memories.setdefault(project_path, []).append(entry)
        self._save_project(project_path)

    def get_project_context(self, project_path: str) -> List[Dict[str, Any]]:
        """Return all stored facts for *project_path*."""
        return list(self._project_memories.get(project_path, []))

    def clear_project_memory(self, project_path: str) -> None:
        """Remove all facts for *project_path* and delete the backing file."""
        self._project_memories.pop(project_path, None)
        fpath = self._project_file(project_path)
        if os.path.exists(fpath):
            os.remove(fpath)

    # ── Prompt context helper ─────────────────────────────────────────────

    def context_block(self, project_path: Optional[str] = None,
                      query: str = "", limit: int = 6) -> str:
        """Generate a formatted context block suitable for LLM prompts.

        v0.7.9.0 — memory must not make CAT slow: retrieval is
        RELEVANCE-BASED and SMALL (requirement #13). When `query` is
        given, long-term memories are keyword-scored against it (top
        `limit`) instead of dumping the top-10 by importance; session
        turns shrink to the last few; project facts stay capped.
        """
        parts: List[str] = []

        # Session
        session = self.get_session_context(max_turns=4)
        if session:
            lines = [f"  [{t['role']}] {t['text'][:200]}" for t in session]
            parts.append("Recent Session:\n" + "\n".join(lines))

        # Long-term — relevance-filtered when a query is available.
        ltm = self.retrieve_relevant(query or "", limit=limit)
        if ltm:
            lines = [f"  [{m.category}] {m.content}" for m in ltm]
            parts.append("Long-term Memories:\n" + "\n".join(lines))

        # Project
        if project_path:
            pfacts = self.get_project_context(project_path)[-8:]
            if pfacts:
                lines = [f"  [{f.get('category','general')}] {f['fact']}" for f in pfacts]
                parts.append("Project Facts:\n" + "\n".join(lines))

        return "\n\n".join(parts) if parts else ""

    def retrieve_relevant(self, query: str, limit: int = 6) -> List[Memory]:
        """Keyword-overlap relevance retrieval over long-term memories.
        Falls back to the plain importance-ordered list when there is no
        usable query. Cheap: pulls a bounded window and scores locally."""
        try:
            pool = self.get_all_memories()[-120:]
        except Exception:
            return []
        if not pool:
            return []
        words = {w for w in str(query or "").lower().split() if len(w) >= 3}
        if not words:
            return sorted(pool,
                          key=lambda m: m.importance, reverse=True)[:limit]
        scored = []
        for m in pool:
            content_words = set(str(m.content).lower().split())
            overlap = len(words & content_words)
            if overlap > 0:
                scored.append((overlap + m.importance, m))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [m for _s, m in scored[:limit]]


# ---------------------------------------------------------------------------
# v0.7.9.0 — process-wide singleton. run_agent used to construct TWO fresh
# MemoryManagers per user turn; each __init__ re-created the schema and
# re-parsed every project_*.json file. One shared instance per memory_dir
# keeps that cost at exactly once per process (thread-safe).
# ---------------------------------------------------------------------------

_manager_lock = threading.Lock()
_manager_cache: Dict[str, "MemoryManager"] = {}


def get_manager(memory_dir: Optional[str] = None) -> MemoryManager:
    key = os.path.normpath(memory_dir or os.path.join(
        os.path.expanduser("~"), ".cct_memory_v2"))
    mgr = _manager_cache.get(key)
    if mgr is not None:
        return mgr
    with _manager_lock:
        mgr = _manager_cache.get(key)
        if mgr is None:
            mgr = MemoryManager(memory_dir=memory_dir)
            _manager_cache[key] = mgr
    return mgr
