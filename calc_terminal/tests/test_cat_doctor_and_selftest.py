import pytest

from calc_terminal.diagnostics.doctor_engine import doctor_engine, DoctorReport
from calc_terminal.diagnostics.self_test import run_self_test, SelfTestReport


def test_doctor_engine_all_19_dimensions():
    report: DoctorReport = doctor_engine.run_diagnostics()
    assert isinstance(report, DoctorReport)
    assert len(report.dimensions) == 19

    dim_ids = [d.dimension_id for d in report.dimensions]
    expected_ids = [
        "python_env",
        "package_managers",
        "git_repo",
        "hardware_compute",
        "local_inference",
        "remote_providers",
        "storage",
        "browser_automation",
        "terminal_host",
        "mode_registry",
        "capability_bus",
        "task_runtime",
        "experiment_ledger",
        "data_lineage",
        "security_policy",
        "network",
        "scientific_software",
        "quantum_sdks",
        "workspace_health",
    ]
    for expected in expected_ids:
        assert expected in dim_ids, f"Missing dimension: {expected}"

    # Verify formatted text renders without error
    text = report.format_text()
    assert "CAT SYSTEM DOCTOR REPORT" in text
    assert len(text) > 200


def test_automated_self_test_suite():
    report: SelfTestReport = run_self_test()
    assert isinstance(report, SelfTestReport)
    assert len(report.results) == 7
    assert report.all_passed is True

    table = report.format_table()
    assert "CAT AUTOMATED SELF-TEST SUITE" in table
    assert "ALL SUBSYSTEMS OPERATIONAL" in table
    for r in report.results:
        assert r.passed is True
        assert r.duration_ms >= 0.0
