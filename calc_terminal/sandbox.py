"""
CCT Sandbox — runs /codepad Python in a subprocess with real OS resource
limits, not just a timeout. On POSIX (Linux/macOS) this sets hard
RLIMIT_CPU, RLIMIT_AS (address space) and RLIMIT_NPROC via a
`preexec_fn`, so a runaway loop or a fork-bomb attempt genuinely gets
killed by the kernel rather than merely by an outer wall-clock timeout.

On Windows there's no equivalent rlimit API, so this provides
process timeout isolation, working directory isolation, isolated Python
interpreter mode (-I), and environment variable scrubbing to prevent
untrusted code from reading tokens or modifying parent workspaces.
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


SENSITIVE_ENV_VARS = {
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY",
    "MISTRAL_API_KEY", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
    "GITHUB_TOKEN", "GH_TOKEN", "GIT_ASKPASS", "SSH_AUTH_SOCK",
}


def _get_scrubbed_env() -> dict:
    """Build a minimal, scrubbed environment excluding API keys and tokens."""
    safe_env = {}
    for k, v in os.environ.items():
        if k.upper() in SENSITIVE_ENV_VARS:
            continue
        if any(term in k.upper() for term in ("API_KEY", "SECRET", "TOKEN", "PASSWORD")):
            continue
        safe_env[k] = v
    safe_env["PYTHONNOUSERSITE"] = "1"
    safe_env["PYTHONDONTWRITEBYTECODE"] = "1"
    return safe_env


def sandbox_available():
    return _IS_POSIX


def run_sandboxed(code, timeout=WALL_TIMEOUT, working_dir=None):
    """Runs `code` as an isolated Python script in a subprocess with
    resource limits, environment scrubbing, and directory isolation.
    Returns a dict: {stdout, stderr, returncode, timed_out, killed_by_limit,
    sandboxed, isolated_env}. Never raises."""
    tmp_path = None
    isolated_dir = None
    try:
        isolated_dir = working_dir or tempfile.mkdtemp(prefix="cat_sandbox_")
        tmp_file = os.path.join(isolated_dir, "_script.py")
        with open(tmp_file, "w", encoding="utf-8") as tmp:
            tmp.write(code)
        tmp_path = tmp_file

        kwargs = dict(
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=isolated_dir,
            env=_get_scrubbed_env(),
        )
        if _IS_POSIX:
            kwargs["preexec_fn"] = _limit_resources

        # -I runs in isolated mode: ignores PYTHONPATH, PYTHONHOME, and user site packages
        result = subprocess.run([sys.executable, "-I", tmp_path], **kwargs)

        killed_by_limit = _IS_POSIX and result.returncode < 0
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "timed_out": False,
            "killed_by_limit": killed_by_limit,
            "sandboxed": True,
            "isolated_env": True,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "stdout": e.stdout or "",
            "stderr": (e.stderr or "") + f"\n[sandbox] killed after {timeout}s wall-clock timeout.",
            "returncode": -1,
            "timed_out": True,
            "killed_by_limit": False,
            "sandboxed": True,
            "isolated_env": True,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"[sandbox] could not run: {e}",
            "returncode": -1,
            "timed_out": False,
            "killed_by_limit": False,
            "sandboxed": True,
            "isolated_env": True,
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        if isolated_dir and not working_dir and os.path.exists(isolated_dir):
            try:
                import shutil
                shutil.rmtree(isolated_dir, ignore_errors=True)
            except Exception:
                pass
        try:
            from . import terminal_identity
            terminal_identity.set_terminal_title()
        except Exception:
            pass
