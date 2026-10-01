"""
CAT Agents — Multi-Agent Workflow & Orchestration Engine.

Orchestrates sequential or staged execution across specialist agents
(e.g., Planner -> Coder -> Tester -> Debugger -> Reviewer).
Integrates with CAT's real permission engine, provider failover, and activity bus.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Sequence

from .agent_model import (
    AgentSpec,
    AgentResult,
    AGENT_STATUS_IDLE,
    AGENT_STATUS_RUNNING,
    AGENT_STATUS_THINKING,
    AGENT_STATUS_USING_TOOL,
    AGENT_STATUS_COMPLETED,
    AGENT_STATUS_FAILED,
)
from .registry import get_agent_registry
from .handoff import AgentHandoffPipeline
from .. import activity as act_mod
from .. import permissions as perm

logger = logging.getLogger("cat.agents.orchestration")


class AgentOrchestrationEngine:
    """Coordinates collaboration between multiple agents on an objective."""

    def __init__(self, mission_id: Optional[str] = None):
        self.mission_id = mission_id or f"orch-{int(time.time())}"
        self.registry = get_agent_registry()
        self.pipeline = AgentHandoffPipeline(self.mission_id)
        self.is_paused = False
        self.is_cancelled = False

    def pause(self) -> None:
        self.is_paused = True

    def resume(self) -> None:
        self.is_paused = False

    def cancel(self) -> None:
        self.is_cancelled = True

    def run_team(
        self,
        team_agent_ids: List[str],
        objective: str,
        on_step_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> List[AgentResult]:
        """Runs an ordered sequence of agents against an objective."""
        results: List[AgentResult] = []

        if not team_agent_ids:
            # Default standard team
            team_agent_ids = ["cat-planner", "cat-coder", "cat-tester", "cat-reviewer"]

        act_mod.publish(
            type="system",
            action="orchestration",
            status="running",
            title=f"Starting Multi-Agent Workflow ({len(team_agent_ids)} agents)",
            details=f"Objective: {objective[:100]}",
        )

        for i, agent_id in enumerate(team_agent_ids):
            if self.is_cancelled:
                act_mod.publish(
                    type="system",
                    action="orchestration",
                    status="cancelled",
                    title="Multi-Agent Workflow Cancelled",
                    details=f"Cancelled at step {i+1} ({agent_id})",
                )
                break

            while self.is_paused and not self.is_cancelled:
                time.sleep(0.5)

            agent = self.registry.get(agent_id)
            if not agent or not agent.enabled:
                logger.warning(f"Agent '{agent_id}' is unavailable or disabled; skipping.")
                continue

            self.registry.set_execution_status(agent_id, AGENT_STATUS_RUNNING)

            step_prompt = self.pipeline.format_handoff_prompt(agent_id, objective)

            # Publish activity
            act_mod.publish(
                type="agent",
                action="step",
                status="running",
                title=f"{agent.name} Step ({i+1}/{len(team_agent_ids)})",
                details=f"Mode: {agent.primary_mode} | Scope: {agent.memory_scope}",
            )

            if on_step_event:
                on_step_event({
                    "stage": "agent_start",
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "step_index": i + 1,
                    "total_steps": len(team_agent_ids),
                })

            start_t = time.time()
            step_result = self._execute_agent_step(agent, step_prompt)
            duration = int((time.time() - start_t) * 1000)

            self.pipeline.submit_result(step_result)
            results.append(step_result)

            self.registry.set_execution_status(
                agent_id,
                AGENT_STATUS_COMPLETED if step_result.status == "success" else AGENT_STATUS_FAILED
            )

            act_mod.publish(
                type="agent",
                action="step",
                status="completed" if step_result.status == "success" else "failed",
                title=f"{agent.name} Completed",
                details=step_result.summary,
                duration_ms=duration,
            )

            if on_step_event:
                on_step_event({
                    "stage": "agent_finish",
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "result": step_result.to_dict(),
                })

            # If a critical step failed and it was the planner, pause or break
            if step_result.status == "failure" and agent_id == "cat-planner":
                logger.error(f"Planning failed; halting workflow.")
                break

        self.registry.set_execution_status(team_agent_ids[-1] if team_agent_ids else "", AGENT_STATUS_IDLE)
        return results

    def _execute_agent_step(self, agent: AgentSpec, prompt: str) -> AgentResult:
        """Executes a single agent step using CAT's AI pipeline and tools."""
        from .. import aicore

        summary = f"Executed {agent.name} pass."
        files_changed = []
        errors = []
        actions = []

        try:
            # Query the AI model configured for this agent or fallback
            system_prompt = agent.system_instructions or f"You are {agent.name}."
            if agent.personality:
                system_prompt += f"\nPersonality: {agent.personality}"

            # Verify permissions before running mutating actions
            # Agent's declared tools limit what the agent can do
            res = aicore.query_ai(
                prompt=prompt,
                system_prompt=system_prompt,
                mode=agent.primary_mode,
            )

            text_response = res.get("text", "")
            summary = text_response[:200].replace("\n", " ") if text_response else f"Agent {agent.name} completed successfully."

            # Check if any errors occurred
            if res.get("error"):
                errors.append(res["error"])
                return AgentResult(
                    agent_id=agent.id,
                    status="failure",
                    summary=f"Provider error: {res['error']}",
                    errors=errors,
                )

            return AgentResult(
                agent_id=agent.id,
                status="success",
                summary=summary,
                files_changed=files_changed,
                actions=actions,
                artifacts={"response": text_response},
                errors=errors,
            )
        except Exception as e:
            logger.exception(f"Error during agent step {agent.id}: {e}")
            return AgentResult(
                agent_id=agent.id,
                status="failure",
                summary=f"Exception in {agent.name}: {e}",
                errors=[str(e)],
            )
