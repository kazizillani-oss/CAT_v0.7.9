"""
CAT Diagnostics Package per §32, §33.
"""

from __future__ import annotations

from calc_terminal.diagnostics.doctor_engine import (
    DimensionHealth,
    DoctorReport,
    DoctorEngine,
    doctor_engine,
)
from calc_terminal.diagnostics.self_test import (
    SubsystemTestResult,
    SelfTestReport,
    run_self_test,
)

__all__ = [
    "DimensionHealth",
    "DoctorReport",
    "DoctorEngine",
    "doctor_engine",
    "SubsystemTestResult",
    "SelfTestReport",
    "run_self_test",
]
