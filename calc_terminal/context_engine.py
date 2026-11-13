"""
CAT Centralized Context Engine (v1.0.0)

Universal multi-category context pipeline for all CAT AI agents, Kitties, skills, and tools:
- 7 Context Categories: User, Project, Session, Agent, Workflow, Tool, Knowledge
- Relevance scoring, prioritization, and project-aware retrieval
- Context compression, deduplication, and conversation summarization
- Strict token budgeting with small-model protection and source tracking
- Structured agent handoff protocol preventing context loss during delegation
- Privacy, isolation, and sensitive token redaction
"""

from __future__ import annotations

import os
import re
import time
import json
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Tuple, Set

from .ai_context import (
    AIMessage,
    AIRequest,
    AIContext,
    ContextBudget,
    simple_token_estimate,
    AIContextManager,
)


# Secret redaction pattern
SECRET_REGEX = re.compile(
    r"(?i)(api[_-]?key|secret|password|token|bearer|private[_-]?key)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-.~+/]{8,})['\"]?"
)


@dataclass
class ContextSlice:
    id: str
    category: str  # "user", "project", "session", "agent", "workflow", "tool", "knowledge"
    source: str    # file path, command, tool name, or memory ID
    content: str
    priority: int = 5  # 1 (lowest) to 10 (highest)
    timestamp: float = field(default_factory=time.time)
    ttl_seconds: Optional[float] = None  # None = permanent, float = expires
    tokens: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        if self.ttl_seconds is None:
            return False
        return (time.time() - self.timestamp) > self.ttl_seconds


@dataclass
class AgentHandoffSpec:
    from_agent: str
    to_agent: str
    task_goal: str
    relevant_files: List[str]
    previous_results: str
    constraints: List[str]
    shared_state: Dict[str, Any] = field(default_factory=dict)
    handoff_id: str = field(default_factory=lambda: f"hnd_{int(time.time())}_{uuid.uuid4().hex[:4]}")


class ContextEngine:
    """Enterprise context management engine powering all CAT agents."""

    _instance = None

    def __init__(self):
        # Category -> list of ContextSlice
        self._slices: Dict[str, List[ContextSlice]] = {
            "user": [],
            "project": [],
            "session": [],
            "agent": [],
            "workflow": [],
            "tool": [],
            "knowledge": [],
        }
        self.handoff_history: List[AgentHandoffSpec] = []
        self.compression_events: List[Dict[str, Any]] = []
        self._current_project: str = os.getcwd()

    @classmethod
    def get(cls) -> "ContextEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_project(self, project_path: str):
        self._current_project = os.path.abspath(project_path)
        # Clear project-specific slices when changing projects to ensure isolation
        self._slices["project"].clear()
        self._slices["knowledge"].clear()

    # =====================================================================
    # Context Ingestion & Storage
    # =====================================================================

    def add_slice(
        self,
        category: str,
        source: str,
        content: str,
        priority: int = 5,
        ttl_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ContextSlice:
        cat = category.lower()
        if cat not in self._slices:
            self._slices[cat] = []

        # Redact secrets
        cleaned = SECRET_REGEX.sub(r"\1: [REDACTED]", content)
        tokens = simple_token_estimate(cleaned)

        c_slice = ContextSlice(
            id=f"ctx_{cat}_{uuid.uuid4().hex[:6]}",
            category=cat,
            source=source,
            content=cleaned,
            priority=priority,
            timestamp=time.time(),
            ttl_seconds=ttl_seconds,
            tokens=tokens,
            metadata=metadata or {},
        )
        self._slices[cat].append(c_slice)
        return c_slice

    def clear(self, category: Optional[str] = None):
        if category:
            cat = category.lower()
            if cat in self._slices:
                self._slices[cat].clear()
        else:
            for cat in self._slices:
                self._slices[cat].clear()

    # =====================================================================
    # Intelligent Retrieval & Scoring
    # =====================================================================

    def retrieve(
        self,
        query: str = "",
        categories: Optional[List[str]] = None,
        max_tokens: int = 4000,
    ) -> List[ContextSlice]:
        """Retrieve prioritized, non-expired, scored context slices within token budget."""
        cats = [c.lower() for c in categories] if categories else list(self._slices.keys())
        candidates: List[Tuple[float, ContextSlice]] = []

        query_terms = [w.lower() for w in query.split()] if query else []

        for cat in cats:
            for sl in list(self._slices.get(cat, [])):
                if sl.is_expired():
                    self._slices[cat].remove(sl)
                    continue

                # Relevance scoring: priority * 10 + keyword overlap score + recency bonus
                score = sl.priority * 10.0
                if query_terms:
                    content_lower = sl.content.lower()
                    matches = sum(1 for term in query_terms if term in content_lower)
                    score += (matches * 60.0)

                # Recency bonus (within last 10 minutes)
                age = time.time() - sl.timestamp
                if age < 600:
                    score += 5.0

                candidates.append((score, sl))

        # Sort descending by score
        candidates.sort(key=lambda t: t[0], reverse=True)

        selected: List[ContextSlice] = []
        total_tokens = 0
        seen_content_hashes: Set[int] = set()

        for _, sl in candidates:
            # Deduplication
            content_hash = hash(sl.content.strip())
            if content_hash in seen_content_hashes:
                continue

            if total_tokens + sl.tokens > max_tokens and selected:
                continue

            seen_content_hashes.add(content_hash)
            selected.append(sl)
            total_tokens += sl.tokens

        return selected

    # =====================================================================
    # Context Compression & Summarization
    # =====================================================================

    def compress(self, category: str = "session", target_tokens: int = 1000) -> Dict[str, Any]:
        """Compress context in category by eliminating duplicates and consolidating history."""
        cat = category.lower()
        slices = self._slices.get(cat, [])
        if not slices:
            return {"compressed": False, "reason": "No slices to compress", "tokens_saved": 0}

        initial_tokens = sum(s.tokens for s in slices)
        if initial_tokens <= target_tokens:
            return {"compressed": False, "reason": "Already within target budget", "tokens_saved": 0}

        # Summarize older slices into a consolidated bullet summary
        older = slices[:-3] if len(slices) > 3 else slices
        keep = slices[-3:] if len(slices) > 3 else []

        summary_lines = []
        for s in older:
            # Extract first sentence or headline
            line = s.content.strip().split("\n")[0][:120]
            summary_lines.append(f"• [{s.source}] {line}…")

        consolidated_content = "Context Summary of earlier steps:\n" + "\n".join(summary_lines)
        consolidated_slice = ContextSlice(
            id=f"ctx_{cat}_summary_{uuid.uuid4().hex[:4]}",
            category=cat,
            source="compression_engine",
            content=consolidated_content,
            priority=8,
            tokens=simple_token_estimate(consolidated_content),
        )

        self._slices[cat] = [consolidated_slice] + keep
        final_tokens = sum(s.tokens for s in self._slices[cat])
        saved = max(0, initial_tokens - final_tokens)

        event = {
            "category": cat,
            "timestamp": time.time(),
            "initial_tokens": initial_tokens,
            "final_tokens": final_tokens,
            "tokens_saved": saved,
        }
        self.compression_events.append(event)
        return {"compressed": True, "tokens_saved": saved, "final_tokens": final_tokens}

    # =====================================================================
    # Agent Handoff Protocol
    # =====================================================================

    def create_handoff(
        self,
        from_agent: str,
        to_agent: str,
        task_goal: str,
        relevant_files: List[str],
        previous_results: str,
        constraints: List[str],
        shared_state: Optional[Dict[str, Any]] = None,
    ) -> AgentHandoffSpec:
        """Create a structured handoff specification for cross-agent collaboration."""
        spec = AgentHandoffSpec(
            from_agent=from_agent,
            to_agent=to_agent,
            task_goal=task_goal,
            relevant_files=relevant_files,
            previous_results=previous_results,
            constraints=constraints,
            shared_state=shared_state or {},
        )
        self.handoff_history.append(spec)

        # Ingest as Agent Context Slice
        self.add_slice(
            category="agent",
            source=f"handoff:{from_agent}->{to_agent}",
            content=(
                f"Agent Handoff from {from_agent} to {to_agent}:\n"
                f"Goal: {task_goal}\n"
                f"Files: {', '.join(relevant_files)}\n"
                f"Constraints: {', '.join(constraints)}\n"
                f"Previous Work: {previous_results[:500]}"
            ),
            priority=9,
        )
        return spec

    # =====================================================================
    # Status & Inspection
    # =====================================================================

    def get_status(self) -> Dict[str, Any]:
        counts = {cat: len(sl) for cat, sl in self._slices.items()}
        tokens = {cat: sum(s.tokens for s in sl) for cat, sl in self._slices.items()}
        total_tokens = sum(tokens.values())

        return {
            "current_project": self._current_project,
            "slice_counts": counts,
            "tokens_by_category": tokens,
            "total_tokens": total_tokens,
            "active_handoffs": len(self.handoff_history),
            "compression_events": len(self.compression_events),
        }

    def inspect_category(self, category: str) -> List[Dict[str, Any]]:
        cat = category.lower()
        res = []
        for s in self._slices.get(cat, []):
            res.append({
                "id": s.id,
                "source": s.source,
                "priority": s.priority,
                "tokens": s.tokens,
                "snippet": s.content[:150] + ("…" if len(s.content) > 150 else ""),
                "timestamp": s.timestamp,
                "expired": s.is_expired(),
            })
        return res


context_engine = ContextEngine.get()
