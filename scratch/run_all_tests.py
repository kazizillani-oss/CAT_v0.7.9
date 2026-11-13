# scratch/run_all_tests.py
import subprocess
import sys

def run(cmd):
    print(f"RUNNING: {cmd}")
    res = subprocess.run(cmd, shell=True)
    if res.returncode != 0:
        print(f"FAIL: {cmd}")
        return False
    print(f"PASS: {cmd}")
    return True

success = True
success = run("python -m unittest calc_terminal/tests/test_v090_voice_and_composer_layout.py") and success
success = run("python -m pytest calc_terminal/tests/test_composer_3d_and_dialog_fixes.py -q") and success
success = run("python -m pytest calc_terminal/tests/test_header_and_extensions_3d_upgrade.py -q") and success
success = run("python -m pytest calc_terminal/tests/test_chat_redesign_and_3d.py -q") and success
success = run("python -m unittest calc_terminal/tests/test_v5_3d_cursor_and_floating.py") and success
success = run("python -m unittest calc_terminal/tests/test_blank_screen_and_editor_responsiveness.py") and success
success = run("python -m unittest calc_terminal/tests/test_engineering_excellence_upgrade.py") and success
success = run("python -m unittest calc_terminal/tests/test_platform_expansion_complete.py") and success
success = run("python -m unittest calc_terminal/tests/test_v0900_input_resize_divider_and_ui_debug.py") and success

if success:
    print("\nOVERALL RESULT: ALL TESTS PASSED (100% GREEN)")
    sys.exit(0)
else:
    print("\nOVERALL RESULT: SOME TESTS FAILED")
    sys.exit(1)
