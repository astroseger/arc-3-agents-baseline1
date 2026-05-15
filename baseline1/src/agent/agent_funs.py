from __future__ import annotations

import glob
import json
import logging
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from codex_runner import CodexRunner


STANDARD_LOG_RECORD_KEYS = set(logging.makeLogRecord({}).__dict__)
STEP_NUMBER_RE = re.compile(r"_step(\d+)")
WORLD_MODEL_STATE_IO_STEP_RE = re.compile(r"^world_model_state_io_simplification_step\d+\.txt$")
ATTEMPT_DIR_RE = re.compile(r"^level_\d+_attempt_\d+$")
CLIENT_ATTEMPT_ARTIFACT_RE = re.compile(
    r"^(?:"
    r"initial_metadata\.json|"
    r"initial_frame\.(?:png|txt)|"
    r"step_\d+_metadata\.json|"
    r"step_\d+_final\.(?:png|txt)|"
    r"step_\d+_intermediate_\d+\.(?:png|txt)"
    r")$"
)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "type": "external_agent_log",
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in STANDARD_LOG_RECORD_KEYS
        }
        if extras:
            payload.update(extras)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=True)


def setup_logger(log_file: Path) -> logging.Logger:
    logger = logging.getLogger("simple_agent")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(JsonLogFormatter())
    logger.addHandler(handler)
    return logger


def prompt_path_sort_key(path: Path) -> tuple[str, int, str]:
    match = STEP_NUMBER_RE.search(path.stem)
    if match:
        prefix = path.stem[: match.start()]
        return (prefix, int(match.group(1)), path.name)
    return (path.stem, -1, path.name)


def resolve_prompt_paths(prompt_dir: Path, reference: str | Path) -> list[Path]:
    if isinstance(reference, Path):
        return [reference]

    if any(char in reference for char in "*?[]"):
        matches = sorted(
            (Path(path_str) for path_str in glob.glob(str(prompt_dir / reference))),
            key=prompt_path_sort_key,
        )
        if not matches:
            raise FileNotFoundError(f"No prompt files matched pattern: {prompt_dir / reference}")
        return matches

    return [prompt_dir / reference]


def load_prompt(prompt_dir: Path, reference: str | Path, logger: logging.Logger) -> str:
    paths = resolve_prompt_paths(prompt_dir, reference)
    if len(paths) != 1:
        raise FileNotFoundError(
            f"Expected exactly one prompt file for {reference!r}, got {len(paths)}"
        )

    path = paths[0]
    if not path.is_file():
        raise FileNotFoundError(f"Missing prompt file: {path}")

    logger.info("loaded prompt file", extra={"prompt_file": str(path.resolve())})
    return path.read_text(encoding="utf-8").strip()


def load_pgroup(prompt_dir: Path, logger: logging.Logger, *references: str | Path) -> list[str]:
    prompts: list[str] = []
    loaded_files: list[str] = []
    for reference in references:
        paths = resolve_prompt_paths(prompt_dir, reference)
        if isinstance(reference, str) and reference == "world_model_state_io_simplification*":
            invalid_paths = [
                path for path in paths if WORLD_MODEL_STATE_IO_STEP_RE.match(path.name) is None
            ]
            if invalid_paths:
                invalid_names = ", ".join(path.name for path in invalid_paths)
                raise RuntimeError(
                    f"Unexpected prompt files for group {reference!r}: {invalid_names}"
                )

        for path in paths:
            if not path.is_file():
                raise FileNotFoundError(f"Missing prompt file: {path}")
            prompts.append(path.read_text(encoding="utf-8").strip())
            loaded_files.append(str(path.resolve()))

    logger.info("loaded prompt group files", extra={"prompt_files": loaded_files})
    return prompts


def run_program(command: str, cwd: Path, logger: logging.Logger) -> str:
    argv = shlex.split(command)
    logger.info("running program", extra={"command": argv, "cwd": str(cwd)})
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.error(
            "program failed",
            extra={
                "command": argv,
                "returncode": exc.returncode,
                "stdout": exc.stdout,
                "stderr": exc.stderr,
            },
        )
        raise
    logger.info(
        "program completed",
        extra={
            "command": argv,
            "returncode": result.returncode,
            "stdout_length": len(result.stdout),
            "stderr_length": len(result.stderr),
        },
    )
    return result.stdout


def run_git_snapshot(
    agent_run_dir: Path,
    level_index: int | None,
    global_step_count: int,
    iteration_count: int,
    logger: logging.Logger,
) -> None:
    git_dir = agent_run_dir / ".git"
    if not git_dir.exists():
        run_program("git init", cwd=agent_run_dir, logger=logger)

    run_program("git config user.name simple-agent", cwd=agent_run_dir, logger=logger)
    run_program("git config user.email simple-agent@localhost", cwd=agent_run_dir, logger=logger)

    level_label = "unknown" if level_index is None else str(level_index)
    commit_message = f"level_{level_label} {global_step_count} {iteration_count}"
    tag_name = f"iteration_{iteration_count}"

    run_program("git add -A", cwd=agent_run_dir, logger=logger)
    run_program(f'git commit --allow-empty -m "{commit_message}"', cwd=agent_run_dir, logger=logger)
    run_program(f"git tag -f {tag_name}", cwd=agent_run_dir, logger=logger)


def send_pgroup(
    runner: CodexRunner,
    prompts: Sequence[str],
    logger: logging.Logger,
) -> None:
    if isinstance(prompts, str):
        raise TypeError("prompts must be a sequence of strings, not a single string")

    for prompt in prompts:
        if not isinstance(prompt, str):
            raise TypeError(f"each prompt must be a string, got {type(prompt).__name__}")
        send_prompt(runner, prompt, logger)


def send_prompt(
    runner: CodexRunner,
    prompt: str,
    logger: logging.Logger,
) -> None:
    if not isinstance(prompt, str):
        raise TypeError(f"prompt must be a string, got {type(prompt).__name__}")
    logger.info("prompt body", extra={"prompt": prompt})
    runner.send(prompt)


def _is_client_attempt_artifact(path: Path) -> bool:
    return path.is_file() and CLIENT_ATTEMPT_ARTIFACT_RE.fullmatch(path.name) is not None


def _attempt_dirs(session_dir: Path) -> list[Path]:
    return sorted(
        path for path in session_dir.iterdir() if path.is_dir() and ATTEMPT_DIR_RE.fullmatch(path.name)
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def copy_attempt_to_follower(
    master_dir: str | Path,
    follower_dir: str | Path,
    level_index: int,
    attempt_index: int,
) -> Path:
    master_dir = Path(master_dir)
    follower_dir = Path(follower_dir)

    master_session_dir = master_dir / "client" / "session"
    follower_session_dir = follower_dir / "client" / "session"

    attempt_dir_name = f"level_{level_index:02d}_attempt_{attempt_index:02d}"
    source_attempt_dir = master_session_dir / attempt_dir_name
    if not source_attempt_dir.is_dir():
        raise FileNotFoundError(f"Attempt directory does not exist: {source_attempt_dir}")

    destination_attempt_dir = follower_session_dir / attempt_dir_name
    destination_attempt_dir.mkdir(parents=True, exist_ok=True)

    for source_path in source_attempt_dir.iterdir():
        if not _is_client_attempt_artifact(source_path):
            continue
        shutil.copy2(source_path, destination_attempt_dir / source_path.name)

    return destination_attempt_dir


def switch_to_new_master(
    follower_dir: str | Path,
    master_dir: str | Path,
) -> Path:
    follower_dir = Path(follower_dir)
    master_dir = Path(master_dir)

    master_session_dir = master_dir / "client" / "session"
    follower_session_dir = follower_dir / "client" / "session"
    master_client_state_path = master_session_dir / "client_state.json"
    if not master_client_state_path.is_file():
        raise RuntimeError(
            f"Logical error: master client_state.json is missing: {master_client_state_path}"
        )

    for master_attempt_dir in _attempt_dirs(master_session_dir):
        follower_attempt_dir = follower_session_dir / master_attempt_dir.name
        if not follower_attempt_dir.is_dir():
            raise RuntimeError(
                f"Logical error: follower attempt directory is missing: {follower_attempt_dir}"
            )
        for master_artifact in sorted(master_attempt_dir.iterdir()):
            if not _is_client_attempt_artifact(master_artifact):
                continue
            follower_artifact = follower_attempt_dir / master_artifact.name
            if not follower_artifact.is_file():
                raise RuntimeError(
                    f"Logical error: follower artifact is missing: {follower_artifact}"
                )
            if master_artifact.read_bytes() != follower_artifact.read_bytes():
                raise RuntimeError(
                    f"Logical error: follower artifact differs from master: {follower_artifact}"
                )

    follower_session_dir.mkdir(parents=True, exist_ok=True)
    follower_client_state_path = follower_session_dir / "client_state.json"
    if follower_client_state_path.exists():
        raise RuntimeError(
            f"Logical error: follower client_state.json already exists: {follower_client_state_path}"
        )
    shutil.move(str(master_client_state_path), str(follower_client_state_path))
    return follower_client_state_path


def get_diverge_step_on_last_attempt(
    follower_dir: str | Path,
    level_index: int,
    attempt_index: int,
    logger: logging.Logger,
) -> int | None:
    script_path = Path(__file__).resolve().parent / "print_mismatch_step.py"
    command = [sys.executable, str(script_path), str(follower_dir)]
    logger.info(
        "running mismatch step helper",
        extra={
            "command": command,
            "follower_dir": str(Path(follower_dir).resolve()),
            "level_index": level_index,
            "attempt_index": attempt_index,
        },
    )

    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
    )
    if result.returncode == 0:
        return None

    output = result.stdout.strip()
    match = re.fullmatch(r"(\d+)\s+(\d+)\s+(\d+)", output)
    if match is None:
        logger.warning(
            "mismatch step helper failed without a parseable mismatch triple; defaulting divergence step to 0",
            extra={
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "follower_dir": str(Path(follower_dir).resolve()),
                "level_index": level_index,
                "attempt_index": attempt_index,
            },
        )
        return 0

    mismatch_level, mismatch_attempt, mismatch_step = map(int, match.groups())
    logger.info(
        "mismatch step helper reported divergence",
        extra={
            "mismatch_level": mismatch_level,
            "mismatch_attempt": mismatch_attempt,
            "mismatch_step": mismatch_step,
        },
    )

    if mismatch_level == level_index and mismatch_attempt == attempt_index:
        return mismatch_step
    return 0
