"""
CCT Sandbox — runs /codepad Python in a subprocess with real OS resource
limits, not just a timeout. On POSIX (Linux/macOS) this sets hard
RLIMIT_CPU, RLIMIT_AS (address space) and RLIMIT_NPROC via a
`preexec_fn`, so a runaway loop or a fork-bomb attempt genuinely gets
killed by the kernel rather than merely by an outer wall-clock timeout.

On Windows there's no equivalent rlimit API, so this honestly falls
back to timeout-only isolation (same as before) and says so — it does
not pretend to sandbox on a platform where it structurally can't.
"""

import os
import subprocess
import sys
import tempfile

CPU_SECONDS = 10
MEMORY_BYTES = 256 * 1024 * 1024  # 256MB
MAX_PROCESSES = 16
WALL_TIMEOUT = 15

_IS_POSIX = os.name == "posix"

if _IS_POSIX:
    import resource

    def _limit_resources():
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
        except Exception:
            pass
        try:
            resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
        except Exception:
            pass
        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (MAX_PROCESSES, MAX_PROCESSES))
        except Exception:
            pass
else:
    _limit_resources = None


def sandbox_available():
    return _IS_POSIX


def run_sandboxed(code, timeout=WALL_TIMEOUT):
    """Runs `code` as a standalone Python script in a subprocess. Returns
    a dict: {stdout, stderr, returncode, timed_out, killed_by_limit,
    sandboxed}. Never raises."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
            tmp.write(code)
            tmp_path = tmp.name

        kwargs = dict(capture_output=True, text=True, timeout=timeout)
        if _IS_POSIX:
            kwargs["preexec_fn"] = _limit_resources
        result = subprocess.run([sys.executable, tmp_path], **kwargs)

        killed_by_limit = _IS_POSIX and result.returncode < 0
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "timed_out": False,
            "killed_by_limit": killed_by_limit,
            "sandboxed": _IS_POSIX,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "stdout": e.stdout or "",
            "stderr": (e.stderr or "") + f"\n[sandbox] killed after {timeout}s wall-clock timeout.",
            "returncode": -1,
            "timed_out": True,
            "killed_by_limit": False,
            "sandboxed": _IS_POSIX,
        }
    except Exception as e:
        return {
            "stdout": "", "stderr": f"[sandbox] could not run: {e}",
            "returncode": -1, "timed_out": False, "killed_by_limit": False,
            "sandboxed": _IS_POSIX,
        }
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        try:
            from . import terminal_identity
            terminal_identity.set_terminal_title()
        except Exception:
            pass
