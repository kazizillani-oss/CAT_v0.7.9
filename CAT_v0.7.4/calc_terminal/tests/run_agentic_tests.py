import sys
import os
import pathlib
import tempfile

# Add CAT_v0.7.4 to sys.path
sys.path.insert(0, os.path.abspath("CAT_v0.7.4"))

from calc_terminal.tests import test_agentic_kitties_and_runtime as t

def run():
    print("=" * 60)
    print("RUNNING AGENTIC KITTIES & RUNTIME TEST SUITE")
    print("=" * 60)

    print("\n1. test_six_canonical_kitties_exist...")
    t.test_six_canonical_kitties_exist()
    print("   [PASS] Six canonical kitties verified.")

    print("\n2. test_ai_modes_metadata_reflection...")
    t.test_ai_modes_metadata_reflection()
    print("   [PASS] ai_modes metadata correctly reflects all 6 Kitties.")

    print("\n3. test_custom_kitty_crud_and_validation...")
    with tempfile.TemporaryDirectory() as td:
        t.test_custom_kitty_crud_and_validation(pathlib.Path(td))
    print("   [PASS] Custom Kitty validation, storage, export, import pass.")

    print("\n4. test_agent_lifecycle_transitions...")
    t.test_agent_lifecycle_transitions()
    print("   [PASS] Agent lifecycle transitions & verification evidence pass.")

    print("\n5. test_qala_notebook_operations...")
    with tempfile.TemporaryDirectory() as td:
        t.test_qala_notebook_operations(pathlib.Path(td))
    print("   [PASS] Qala notebook inspection, cell addition & execution pass.")

    print("\n6. test_qala_symbolic_mathematics...")
    t.test_qala_symbolic_mathematics()
    print("   [PASS] Qala SymPy symbolic algebra & calculus pass.")

    print("\n7. test_latex_validation_and_terminal_rendering...")
    t.test_latex_validation_and_terminal_rendering()
    print("   [PASS] LaTeX validation and terminal Unicode rendering pass.")

    print("\n8. test_platform_automation_safety_and_emergency_stop...")
    t.test_platform_automation_safety_and_emergency_stop()
    print("   [PASS] Platform automation safety policies & emergency stop pass.")

    print("\n9. test_task_scheduler_lifecycle...")
    with tempfile.TemporaryDirectory() as td:
        t.test_task_scheduler_lifecycle(pathlib.Path(td))
    print("   [PASS] 24/7 background scheduler lifecycle pass.")

    print("\n10. test_email_automation_confirmation_policy...")
    t.test_email_automation_confirmation_policy()
    print("   [PASS] Email search, thread summary & send confirmation gate pass.")

    print("\n11. test_run_agent_lifecycle_and_verification_recording...")
    class MockMonkeyPatch:
        def setattr(self, target, name, val):
            setattr(target, name, val)
    t.test_run_agent_lifecycle_and_verification_recording(MockMonkeyPatch())
    print("   [PASS] run_agent lifecycle integration and verification pass.")

    print("\n12. test_tool_terminal_and_device_emergency_stop...")
    t.test_tool_terminal_and_device_emergency_stop()
    print("   [PASS] Tool terminal and device emergency stop pass.")

    print("\n13. test_skills_system_registry_and_validation...")
    with tempfile.TemporaryDirectory() as td:
        t.test_skills_system_registry_and_validation(pathlib.Path(td))
    print("   [PASS] Skills system definitions, validation, and registry pass.")

    print("\n14. test_skills_assigned_to_canonical_kitties...")
    t.test_skills_assigned_to_canonical_kitties()
    print("   [PASS] Built-in Kitties skills assignments pass.")

    print("\n15. test_artifact_manager_tracking_and_hashing...")
    with tempfile.TemporaryDirectory() as td:
        t.test_artifact_manager_tracking_and_hashing(pathlib.Path(td))
    print("   [PASS] Artifact manager SHA-256 and task provenance pass.")

    print("\n16. test_memory_governance_task_preference_and_export...")
    with tempfile.TemporaryDirectory() as td:
        t.test_memory_governance_task_preference_and_export(pathlib.Path(td))
    print("   [PASS] Memory governance (task isolation, approval, export) pass.")

    print("\n17. test_central_policy_delegation_clamping...")
    t.test_central_policy_delegation_clamping()
    print("   [PASS] Central policy enforcement & delegation clamping pass.")

    print("\n18. test_sandbox_isolated_execution...")
    t.test_sandbox_isolated_execution()
    print("   [PASS] Subprocess sandboxing & env scrubbing pass.")

    print("\n19. test_agent_evals_suite_and_controlled_improvement...")
    t.test_agent_evals_suite_and_controlled_improvement()
    print("   [PASS] Agent evaluation suite & controlled improvement pass.")

    print("\n" + "=" * 60)
    print("ALL 19 ARCHITECTURAL & AGENTIC TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run()
