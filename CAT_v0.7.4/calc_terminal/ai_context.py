"""
Centralized AI Context Pipeline & Manager for CAT.

Implements Sections 1-5, 11, 15, 16, 20-23, and 35 of the
CAT AI Mode Reliability Contract.

Guarantees strict mode isolation, token budgeting, small-model context
protection, structured message schemas, and prevents cross-mode context
contamination.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Union
import time
import uuid

from .models.profiles import ModelProfile, get_model_profile


class AIMode(str, Enum):
    CHAT = "chat"
    NOTEBOOK = "notebook"
    RESEARCH = "research"
    PLAN = "plan"
    DEBUGGER = "debugger"
    BUILD = "build"
    AGENT = "agent"
    CODE = "code"


@dataclass
class AIMessage:
    id: str
    role: str  # "system", "user", "assistant", "tool"
    content: str
    timestamp: float = field(default_factory=time.time)
    request_id: str = ""
    mode: str = "chat"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "request_id": self.request_id,
            "mode": self.mode,
            "metadata": self.metadata,
        }


@dataclass
class NotebookCell:
    id: str
    type: str  # "code" | "markdown"
    source: str
    outputs: List[str] = field(default_factory=list)
    execution_state: str = "idle"


@dataclass
class ResearchContext:
    query: str
    sources: List[Dict[str, str]] = field(default_factory=list)
    summaries: List[str] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DebuggerContext:
    file_path: str = ""
    code_snippet: str = ""
    line_number: Optional[int] = None
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    stack_trace: str = ""
    runtime_error: str = ""


@dataclass
class PlanContext:
    task: str = ""
    constraints: List[str] = field(default_factory=list)
    project_state: str = ""
    current_plan: str = ""
    previous_plan: Optional[str] = None


@dataclass
class FileReference:
    path: str
    content: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None


@dataclass
class ContextBudget:
    maximum_tokens: int
    reserved_for_output: int
    system_tokens: int
    dynamic_context_tokens: int

    @classmethod
    def create(cls, profile: ModelProfile, system_est: int = 150) -> "ContextBudget":
        max_t = profile.max_context_tokens
        reserved_out = profile.reserved_output_tokens
        dyn = max(100, max_t - reserved_out - system_est)
        return cls(
            maximum_tokens=max_t,
            reserved_for_output=reserved_out,
            system_tokens=system_est,
            dynamic_context_tokens=dyn,
        )


@dataclass
class AIRequest:
    session_id: str
    request_id: str
    mode: str
    user_message: str
    selected_files: List[FileReference] = field(default_factory=list)
    selected_code: str = ""
    selected_cells: List[NotebookCell] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    research_context: Optional[ResearchContext] = None
    debugger_context: Optional[DebuggerContext] = None
    plan_context: Optional[PlanContext] = None
    history: List[AIMessage] = field(default_factory=list)
    model: str = ""
    provider: str = ""


@dataclass
class AIContext:
    session_id: str
    request_id: str
    mode: str
    system_prompt: str
    messages: List[Dict[str, str]]
    token_estimate: int
    budget: ContextBudget
    is_minimal: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


def simple_token_estimate(text: str) -> int:
    """Fast character-based token estimator (~4 chars per token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


class AIContextManager:
    """Centralized context manager for all CAT AI operations."""

    def __init__(self):
        # session_id -> list of AIMessage
        self._sessions: Dict[str, List[AIMessage]] = {}
        # (session_id, mode) -> dict of isolated mode context
        self._mode_contexts: Dict[tuple, Dict[str, Any]] = {}

    def get_session_messages(self, session_id: str) -> List[AIMessage]:
        return self._sessions.setdefault(session_id, [])

    def record_message(self, session_id: str, message: AIMessage) -> None:
        messages = self.get_session_messages(session_id)
        messages.append(message)

    def clear_conversation(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        to_del = [k for k in self._mode_contexts if k[0] == session_id]
        for k in to_del:
            self._mode_contexts.pop(k, None)

    def clear_mode_context(self, session_id: str, mode: str) -> None:
        self._mode_contexts.pop((session_id, mode.lower()), None)

    def estimate_tokens(self, context: Union[AIContext, str, List[Dict[str, str]]]) -> int:
        if isinstance(context, str):
            return simple_token_estimate(context)
        if isinstance(context, AIContext):
            return context.token_estimate
        if isinstance(context, list):
            total = 0
            for m in context:
                total += simple_token_estimate(m.get("content", ""))
            return total
        return 0

    def build_context(self, request: AIRequest, profile: Optional[ModelProfile] = None) -> AIContext:
        """Build an isolated, budgeted, and structured context for the AI request."""
        mode = (request.mode or "chat").lower()
        if profile is None:
            profile = get_model_profile(request.provider, request.model)

        is_small = profile.is_small_or_base()
        is_minimal = profile.prompt_template == "minimal" or is_small

        # 1. Mode-specific system instructions
        system_instruction = self._build_system_instruction(mode, is_minimal)
        sys_tokens = simple_token_estimate(system_instruction)

        # 2. Token Budget calculation
        budget = ContextBudget.create(profile, system_est=sys_tokens)

        # 3. Filter and isolate conversation history
        # CRITICAL RULE: Filter history strictly to the current mode or compatible modes.
        # Do not allow massive research outputs, debugger traces, or tool dumps
        # to contaminate Chat or Notebook.
        filtered_history = self._filter_history_for_mode(request.history, mode, is_small)

        # 4. Mode-specific context blocks (selected files, debugger, notebook, research)
        mode_context_block = self._build_mode_context(request, mode, is_small)

        # 5. Assemble messages with priority budgeting
        messages = self._assemble_and_trim_messages(
            system_instruction=system_instruction,
            user_message=request.user_message,
            mode_context_block=mode_context_block,
            history=filtered_history,
            budget=budget,
            is_small=is_small,
        )

        total_tokens = sum(simple_token_estimate(m["content"]) for m in messages)

        return AIContext(
            session_id=request.session_id,
            request_id=request.request_id,
            mode=mode,
            system_prompt=system_instruction,
            messages=messages,
            token_estimate=total_tokens,
            budget=budget,
            is_minimal=is_minimal,
            metadata={
                "provider": profile.provider,
                "model": profile.model,
                "is_small_model": is_small,
            },
        )

    def _build_system_instruction(self, mode: str, is_minimal: bool) -> str:
        """Build mode-specific system prompt without bloating small models."""
        if is_minimal:
            # Minimal prompt mode for small/base models
            base = "You are CAT AI."
            if mode == "debugger":
                return f"{base} Focus on diagnosing the specific error and providing the fix."
            elif mode == "plan":
                return f"{base} Provide structured, step-by-step implementation plans."
            elif mode == "build":
                return f"{base} Write clean, working code with syntax highlighting."
            elif mode == "research":
                return f"{base} Analyze facts objectively and cite sources."
            elif mode == "notebook":
                return f"{base} Assist with scientific and analytical calculations."
            return f"{base} Answer clearly, accurately, and concisely."

        # Standard instructions per mode
        if mode == "notebook":
            return (
                "You are CAT AI in Notebook Mode. Assist with computational, "
                "scientific, and analytical workflows. Explain clearly with formulas and code."
            )
        elif mode == "research":
            return (
                "You are CAT AI in Research Mode. Conduct objective analysis using the "
                "provided sources. Cite sources explicitly. Never present unverified source text as your own words."
            )
        elif mode == "plan":
            return (
                "You are CAT AI in Plan Mode. Create clear, pragmatic architectural roadmaps "
                "and step-by-step implementation plans with explicit verification steps."
            )
        elif mode == "debugger":
            return (
                "You are CAT AI in Debugger Mode. Diagnose errors, stack traces, and bugs. "
                "Provide targeted root cause analysis and the exact fix."
            )
        elif mode == "build":
            return (
                "You are CAT AI in Build Mode. Assist with software development, "
                "code architecture, and implementation."
            )
        elif mode == "agent":
            return (
                "You are CAT AI in Agent Mode. Execute tasks systematically, "
                "leveraging available tools and verifying each step."
            )
        else:
            return (
                "You are CAT AI, a helpful coding and problem-solving assistant. "
                "Provide accurate, clear, and direct answers."
            )

    def _filter_history_for_mode(self, history: List[AIMessage], current_mode: str, is_small: bool) -> List[AIMessage]:
        """Isolate history by mode to avoid context contamination."""
        if not history:
            return []

        # For small models, heavily restrict history (at most 2-4 recent turns)
        max_turns = 4 if is_small else 12

        compatible_modes = {current_mode}
        if current_mode in ("chat", "notebook"):
            compatible_modes.update({"chat", "notebook"})
        elif current_mode in ("code", "build"):
            compatible_modes.update({"code", "build"})

        filtered = []
        for msg in reversed(history):
            if msg.role == "system":
                continue
            # Must match compatible mode
            msg_mode = (msg.mode or "chat").lower()
            if msg_mode not in compatible_modes:
                continue

            # Skip massive tool outputs or research articles from normal chat context
            if current_mode in ("chat", "notebook") and len(msg.content) > 4000:
                continue

            filtered.append(msg)
            if len(filtered) >= max_turns:
                break

        return list(reversed(filtered))

    def _build_mode_context(self, request: AIRequest, mode: str, is_small: bool) -> str:
        """Construct structured, clearly demarcated context blocks for the mode."""
        blocks = []

        # 1. Selected Files / Code Context
        if request.selected_code:
            code_cap = 600 if is_small else 2000
            snippet = request.selected_code[:code_cap]
            blocks.append(f"--- SELECTED CODE ---\n{snippet}\n---------------------")
        elif request.selected_files:
            file_limit = 1 if is_small else 3
            for f in request.selected_files[:file_limit]:
                content_cap = 800 if is_small else 3000
                content = f.content[:content_cap]
                blocks.append(f"--- FILE: {f.path} ---\n{content}\n---------------------")

        # 2. Notebook Context
        if mode == "notebook" and request.selected_cells:
            cell_limit = 2 if is_small else 6
            for cell in request.selected_cells[:cell_limit]:
                out = ("\nOutputs:\n" + "\n".join(cell.outputs[:2])) if cell.outputs else ""
                blocks.append(f"--- CELL ({cell.type}) ---\n{cell.source[:1000]}{out}\n---------------------")

        # 3. Research Context (explicitly isolated as source material)
        if mode == "research" and request.research_context:
            rc = request.research_context
            if rc.sources:
                source_lines = []
                for s in rc.sources[:(2 if is_small else 5)]:
                    title = s.get("title", "Source")
                    text = s.get("text", s.get("content", ""))[: (500 if is_small else 1500)]
                    source_lines.append(f"[{title}]: {text}")
                blocks.append("--- SOURCE DOCUMENTS (Context Only - Do not repeat verbatim) ---\n"
                              + "\n\n".join(source_lines) + "\n---------------------")

        # 4. Debugger Context
        if mode == "debugger":
            dc = request.debugger_context
            dbg_lines = []
            if dc:
                if dc.runtime_error:
                    dbg_lines.append(f"Runtime Error: {dc.runtime_error}")
                if dc.stack_trace:
                    dbg_lines.append(f"Stack Trace:\n{dc.stack_trace[: (500 if is_small else 1500)]}")
                if dc.code_snippet:
                    dbg_lines.append(f"Error Region ({dc.file_path}:{dc.line_number or '?'}):\n{dc.code_snippet[:1000]}")
            if request.diagnostics:
                for d in request.diagnostics[: (2 if is_small else 5)]:
                    dbg_lines.append(f"Diagnostic: {d}")
            if dbg_lines:
                blocks.append("--- DIAGNOSTIC CONTEXT ---\n" + "\n\n".join(dbg_lines) + "\n---------------------")

        # 5. Plan Context
        if mode == "plan" and request.plan_context:
            pc = request.plan_context
            plan_lines = []
            if pc.task:
                plan_lines.append(f"Target Task: {pc.task}")
            if pc.constraints:
                plan_lines.append("Constraints: " + ", ".join(pc.constraints))
            if pc.previous_plan:
                plan_lines.append(f"--- PREVIOUS PLAN (Reference) ---\n{pc.previous_plan[: (500 if is_small else 1500)]}")
            if plan_lines:
                blocks.append("\n".join(plan_lines))

        return "\n\n".join(blocks).strip()

    def _assemble_and_trim_messages(
        self,
        system_instruction: str,
        user_message: str,
        mode_context_block: str,
        history: List[AIMessage],
        budget: ContextBudget,
        is_small: bool,
    ) -> List[Dict[str, str]]:
        """Assemble structured chat messages respecting priority budgeting."""
        # Priority Order:
        # 1. Current user request
        # 2. System instruction
        # 3. Active code / diagnostic context block
        # 4. Recent relevant history turns
        messages = [{"role": "system", "content": system_instruction}]

        # Full final prompt combining user message and mode context
        if mode_context_block:
            final_user_content = f"{mode_context_block}\n\n{user_message}".strip()
        else:
            final_user_content = user_message.strip()

        # Check remaining budget for history
        used_tokens = simple_token_estimate(system_instruction) + simple_token_estimate(final_user_content)
        available_for_history = max(0, budget.maximum_tokens - budget.reserved_for_output - used_tokens)

        history_messages = []
        for msg in reversed(history):
            cost = simple_token_estimate(msg.content)
            if cost <= available_for_history:
                history_messages.append({"role": msg.role, "content": msg.content})
                available_for_history -= cost
            else:
                break

        history_messages.reverse()
        messages.extend(history_messages)
        messages.append({"role": "user", "content": final_user_content})

        return messages


# Global singleton instance
_GLOBAL_CONTEXT_MANAGER = AIContextManager()

def get_context_manager() -> AIContextManager:
    return _GLOBAL_CONTEXT_MANAGER
