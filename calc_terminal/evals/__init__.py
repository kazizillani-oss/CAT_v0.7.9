"""
calc_terminal.evals package
Repeatable evaluation and benchmarking suite for CAT Kitties.
"""

from .agent_evals import (
    EvalTask,
    EvalResult,
    AgentEvaluator,
    get_standard_eval_suite,
)

__all__ = [
    "EvalTask",
    "EvalResult",
    "AgentEvaluator",
    "get_standard_eval_suite",
]
