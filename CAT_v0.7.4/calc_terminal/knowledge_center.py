"""
CAT Knowledge Center (v0.7.9 Complete Platform Expansion)

Documentation indexer, semantic token search with citations,
preloaded offline developer cheatsheets, and knowledge collections.
"""

import os
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

@dataclass
class KnowledgeSnippet:
    collection: str
    title: str
    source_file: str
    line_number: int
    content: str
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

OFFLINE_KNOWLEDGE = [
    KnowledgeSnippet(
        collection="python",
        title="Python 3.12 Generics and Type Parameter Syntax",
        source_file="docs/python/generics.md",
        line_number=1,
        content="PEP 695 introduces type parameter syntax: `def max[T: (int, float)](args: list[T]) -> T:` and `type Point = tuple[float, float]`.",
        keywords=["type", "generics", "pep695", "alias"]
    ),
    KnowledgeSnippet(
        collection="textual",
        title="Textual CSS Responsive Modes & Events",
        source_file="docs/textual/css.md",
        line_number=15,
        content="Textual applications handle terminal resize via on_resize event. Responsive classes like `.is-portrait` can be toggled based on size.width < size.height.",
        keywords=["textual", "css", "portrait", "landscape", "responsive"]
    ),
    KnowledgeSnippet(
        collection="git",
        title="Git Rebase & Branch Management",
        source_file="docs/git/commands.md",
        line_number=40,
        content="`git rebase -i HEAD~n` to squash commits. `git switch -c <branch>` to create and switch. `git restore --staged <file>` to unstage.",
        keywords=["git", "rebase", "branch", "switch", "stash"]
    ),
    KnowledgeSnippet(
        collection="docker",
        title="Docker Container Lifecycle",
        source_file="docs/docker/cheatsheet.md",
        line_number=10,
        content="`docker run -d -p 8080:80 --name app img` runs container in detached mode. `docker logs -f <id>` streams stdout/stderr.",
        keywords=["docker", "run", "port", "logs", "container"]
    ),
]

class KnowledgeCenter:
    """Manages searchable documentation, cheatsheets, and workspace document indexing."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._snippets: List[KnowledgeSnippet] = list(OFFLINE_KNOWLEDGE)
        return cls._instance

    def index_workspace_docs(self, root_dir: str, max_files: int = 200) -> int:
        """Scan and ingest markdown, text, and doc files in workspace."""
        added = 0
        ignore_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules"}

        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".venv")]
            for file in files:
                if added >= max_files:
                    break
                if file.endswith((".md", ".txt", ".rst")):
                    fpath = os.path.join(root, file)
                    rel = os.path.relpath(fpath, root_dir).replace("\\", "/")
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()
                        # Extract sections
                        cur_title = file
                        cur_lines = []
                        start_line = 1
                        for lineno, line in enumerate(lines, 1):
                            if line.startswith("#"):
                                if cur_lines:
                                    self._snippets.append(KnowledgeSnippet(
                                        collection="workspace",
                                        title=cur_title,
                                        source_file=rel,
                                        line_number=start_line,
                                        content="".join(cur_lines)[:500],
                                        keywords=cur_title.lower().split()
                                    ))
                                    added += 1
                                cur_title = line.strip("# \t\r\n")
                                cur_lines = []
                                start_line = lineno
                            else:
                                cur_lines.append(line)
                        if cur_lines:
                            self._snippets.append(KnowledgeSnippet(
                                collection="workspace",
                                title=cur_title,
                                source_file=rel,
                                line_number=start_line,
                                content="".join(cur_lines)[:500],
                                keywords=cur_title.lower().split()
                            ))
                            added += 1
                    except Exception:
                        continue
        return added

    def search(self, query: str, collection: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Search knowledge base with relevance ranking and citations."""
        q = query.lower().strip()
        tokens = q.split()
        results = []

        for s in self._snippets:
            if collection and s.collection.lower() != collection.lower():
                continue
            haystack = f"{s.title} {s.content} {' '.join(s.keywords)}".lower()
            score = sum(haystack.count(t) for t in tokens)
            if score > 0:
                results.append((score, s))

        results.sort(key=lambda x: x[0], reverse=True)
        return [s.to_dict() for _, s in results[:limit]]

    def list_collections(self) -> List[str]:
        return list({s.collection for s in self._snippets})


# Global singleton
knowledge_center = KnowledgeCenter()

def get_knowledge_center() -> KnowledgeCenter:
    return knowledge_center

