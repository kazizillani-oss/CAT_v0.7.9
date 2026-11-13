"""
CAT Crash Resilience & Auto-Recovery per §15 & Enterprise Recovery Engine (v1.0.0)

Re-exports unified RecoveryEngine from recovery_engine.py ensuring seamless
backward compatibility across all subsystems.
"""

from __future__ import annotations

from .recovery_engine import (
    RecoverySnapshot,
    ChangeRecord,
    RecoveryTransaction,
    RecoveryEngine,
    recovery_engine,
)

__all__ = [
    "RecoverySnapshot",
    "ChangeRecord",
    "RecoveryTransaction",
    "RecoveryEngine",
    "recovery_engine",
]
