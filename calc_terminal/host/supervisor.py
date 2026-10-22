"""Restart CAT Browser once with safer compositing after a native Qt crash."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

from .diagnostics import log_event, log_exception


# A prior renderer fault may justify one short compatibility session. A full
# day of software compositing leaves the browser permanently slower after the
# original driver fault has passed.
_COMPAT_WINDOW_SECONDS = 5 * 60


def _state_paths() -> tuple[pathlib.Path, pathlib.Path]:
    root = pathlib.Path.home()
    return root / ".cat_browser_gpu_fallback.json", root / ".cat_browser_recovery.log"


def _fallback_is_active(state_path: pathlib.Path, now: float) -> bool:
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        remaining = float(state.get("fallback_until", 0)) - now
        # Ignore legacy 24-hour fallback records written by older versions.
        return 0 < remaining <= _COMPAT_WINDOW_SECONDS
    except Exception:
        return False


def _clear_fallback(state_path: pathlib.Path) -> None:
    try:
        state_path.unlink(missing_ok=True)
    except Exception:
        pass


def _record_fallback(state_path: pathlib.Path, log_path: pathlib.Path, exit_code: int) -> None:
    now = time.time()
    try:
        temp_path = state_path.with_suffix(state_path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps({"fallback_until": now + _COMPAT_WINDOW_SECONDS}), encoding="utf-8"
        )
        temp_path.replace(state_path)
    except Exception:
        pass
    try:
        if log_path.exists() and log_path.stat().st_size > 256 * 1024:
            log_path.unlink()
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} native browser exit={exit_code}; retrying with GPU compositing fallback\n")
    except Exception:
        pass


def _browser_command(url: str) -> tuple[list[str], dict[str, str], dict[str, object]]:
    executable = sys.executable
    if sys.platform == "win32" and pathlib.Path(executable).name.lower() == "python.exe":
        windowless = pathlib.Path(executable).with_name("pythonw.exe")
        if windowless.is_file():
            executable = str(windowless)

    env = os.environ.copy()
    env["CAT_BROWSER_SUPERVISED_CHILD"] = "1"
    env.pop("CAT_BROWSER_GPU_COMPOSITING", None)
    kwargs: dict[str, object] = {}

    candidate_root = pathlib.Path(__file__).resolve().parent.parent.parent
    if (candidate_root / "calc_terminal").is_dir() and (candidate_root / "main.py").exists():
        ws_root = str(candidate_root)
        inherited = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = ws_root + (os.pathsep + inherited if inherited else "")
        kwargs["cwd"] = ws_root

    return [executable, "-m", "calc_terminal.host.launcher", "--url", url, "--mode", "browser"], env, kwargs


def _run_child(url: str, compatibility_compositing: bool) -> int:
    command, env, kwargs = _browser_command(url)
    if compatibility_compositing:
        env["CAT_BROWSER_GPU_COMPOSITING"] = "compat"
    run_kwargs: dict[str, object] = {
        "env": env,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        **kwargs,
    }
    if sys.platform == "win32":
        run_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        run_kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(command, **run_kwargs)
        log_event(
            "browser_child_started",
            child_pid=process.pid,
            compositor_mode="compatibility" if compatibility_compositing else "default",
        )
        exit_code = int(process.wait())
        log_event(
            "browser_child_exited",
            child_pid=process.pid,
            exit_code=exit_code,
            exit_hex=f"0x{exit_code & 0xFFFFFFFF:08X}",
            compositor_mode="compatibility" if compatibility_compositing else "default",
        )
        return exit_code
    except Exception:
        log_exception(
            "browser_child_spawn_failed",
            compositor_mode="compatibility" if compatibility_compositing else "default",
        )
        return 1


def run_supervisor(url: str = "about:home") -> int:
    """Retry one native failure in short-lived software-compositing mode."""
    state_path, log_path = _state_paths()
    compatibility = _fallback_is_active(state_path, time.time())
    log_event(
        "supervisor_started",
        compositor_mode="compatibility" if compatibility else "default",
        initial_url="[not logged]",
    )
    exit_code = _run_child(url or "about:home", compatibility)
    if compatibility:
        # Compatibility is a one-session recovery, never a persistent default.
        _clear_fallback(state_path)
        return exit_code
    if exit_code == 0:
        _clear_fallback(state_path)
        return exit_code

    _record_fallback(state_path, log_path, exit_code)
    log_event("gpu_compositing_fallback_enabled", prior_exit_code=exit_code)
    fallback_exit = _run_child(url or "about:home", compatibility_compositing=True)
    return fallback_exit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Supervise CAT Browser native renderer failures")
    parser.add_argument("--url", default="about:home")
    args = parser.parse_args(argv)
    return run_supervisor(args.url)


if __name__ == "__main__":
    raise SystemExit(main())
