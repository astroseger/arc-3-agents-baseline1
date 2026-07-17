from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from agent import LOG_FILE
from session_inspector import DEFAULT_SESSION_DIR, SessionInspection, inspect_sessions


ROOT = Path(__file__).resolve().parent
AGENT_PATH = ROOT / "agent.py"
RUNNER_LOG_FILE = ROOT / "agent_runner.log"

RECOVERY_LOG_STALE_SECONDS = 30 * 60.0
MAX_RECOVERY_ATTEMPTS = 10
POLL_SECONDS = 5.0
TERMINATE_GRACE_SECONDS = 30.0


def log(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S %z")
    line = f"{timestamp} {message}"
    print(line, flush=True)
    with RUNNER_LOG_FILE.open("a", encoding="utf-8") as log_fh:
        log_fh.write(line + "\n")


def build_agent_command(
    *,
    game_name: str | None,
    recovery: bool,
    model: str,
    reasoning_effort: str,
) -> list[str]:
    command = [
        sys.executable,
        str(AGENT_PATH),
        "--model",
        model,
        "--reasoning-effort",
        reasoning_effort,
    ]
    if recovery:
        command.append("--recovery")
    else:
        if game_name is None:
            raise RuntimeError("game_name is required for master mode.")
        command.extend(["--master", game_name])
    return command


def start_agent(command: list[str]) -> subprocess.Popen[bytes]:
    log(f"agent_runner.py: starting {' '.join(command)}")
    return subprocess.Popen(command, cwd=ROOT, start_new_session=True)


def terminate_agent(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return

    log(f"agent_runner.py: terminating stale agent pid={process.pid}")
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return

    try:
        process.wait(timeout=TERMINATE_GRACE_SECONDS)
        return
    except subprocess.TimeoutExpired:
        pass

    log(f"agent_runner.py: killing stale agent pid={process.pid}")
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    process.wait()


def stop_conditions_met(inspection: SessionInspection) -> bool:
    if inspection.current_level_index is None:
        return True
    if inspection.n_steps_current_level >= 1500:
        return True
    if inspection.is_solved:
        return True
    return False


def inspect_and_should_stop() -> bool:
    inspection = inspect_sessions(DEFAULT_SESSION_DIR)
    log_inspection(inspection)
    return stop_conditions_met(inspection)


def log_inspection(inspection: SessionInspection) -> None:
    log(
        "agent_runner.py: inspection "
        f"level={inspection.current_level_index} "
        f"steps_total={inspection.n_steps_total} "
        f"steps_current_level={inspection.n_steps_current_level} "
        f"solved={inspection.is_solved} "
        f"game_over={inspection.is_game_over}"
    )


def log_idle_seconds(started_at: float) -> float:
    try:
        last_activity_at = max(LOG_FILE.stat().st_mtime, started_at)
    except FileNotFoundError:
        last_activity_at = started_at
    return time.time() - last_activity_at


def wait_for_agent(process: subprocess.Popen[bytes], label: str) -> str:
    started_at = time.time()
    while True:
        return_code = process.poll()
        if return_code is not None:
            log(f"agent_runner.py: {label} stopped with exit code {return_code}")
            return "exited"

        idle_seconds = log_idle_seconds(started_at)
        if idle_seconds >= RECOVERY_LOG_STALE_SECONDS:
            if inspect_and_should_stop():
                log("agent_runner.py: stop condition met during stale-log check; stopping supervisor")
                terminate_agent(process)
                return "stop"

            log(
                "agent_runner.py: agent.log is stale for "
                f"{int(idle_seconds)} seconds; stopping {label}"
            )
            terminate_agent(process)
            return "stale"

        time.sleep(POLL_SECONDS)


def has_made_at_least_one_step() -> bool:
    inspection = inspect_sessions(DEFAULT_SESSION_DIR)
    log_inspection(inspection)
    return inspection.n_steps_total > 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the ARC agent with recovery supervision.")
    parser.add_argument("GAME_NAME")
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument("--reasoning-effort", default="medium")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    try:
        master_process = start_agent(
            build_agent_command(
                game_name=args.GAME_NAME,
                recovery=False,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
            )
        )
        master_status = wait_for_agent(master_process, "master")
        if master_status == "stop":
            return 0

        if not has_made_at_least_one_step():
            log("agent_runner.py: master stopped before any step was made; not entering recovery")
            return master_process.returncode or 0

        recovery_attempts = 0
        while True:
            if inspect_and_should_stop():
                log("agent_runner.py: stop condition met; stopping supervisor")
                return 0

            if recovery_attempts >= MAX_RECOVERY_ATTEMPTS:
                log(
                    "agent_runner.py: recovery attempt limit reached "
                    f"({MAX_RECOVERY_ATTEMPTS}); stopping supervisor"
                )
                return 0

            recovery_attempts += 1
            log(
                "agent_runner.py: recovery attempt "
                f"{recovery_attempts}/{MAX_RECOVERY_ATTEMPTS}"
            )
            recovery_process = start_agent(
                build_agent_command(
                    game_name=None,
                    recovery=True,
                    model=args.model,
                    reasoning_effort=args.reasoning_effort,
                )
            )
            recovery_status = wait_for_agent(recovery_process, "recovery")
            if recovery_status == "stop":
                return 0

    except KeyboardInterrupt:
        log("agent_runner.py: interrupted")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
