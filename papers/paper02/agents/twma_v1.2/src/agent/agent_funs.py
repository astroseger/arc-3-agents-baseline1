from __future__ import annotations

import json
import logging
import shlex
import subprocess
from pathlib import Path
from typing import Sequence

from codex_runner import CodexRunner


STANDARD_LOG_RECORD_KEYS = set(logging.makeLogRecord({}).__dict__)

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


def _prompt_path(prompt_dir: Path, reference: str | Path) -> Path:
    if isinstance(reference, Path):
        return reference
    return prompt_dir / reference


def load_prompt(prompt_dir: Path, reference: str | Path, logger: logging.Logger) -> str:
    path = _prompt_path(prompt_dir, reference)
    if not path.is_file():
        raise FileNotFoundError(f"Missing prompt file: {path}")

    logger.info("loaded prompt file", extra={"prompt_file": str(path.resolve())})
    return path.read_text(encoding="utf-8").strip()


def load_pgroup(
    prompt_dir: Path,
    logger: logging.Logger,
    references: Sequence[str | Path],
) -> list[str]:
    prompts: list[str] = []
    loaded_files: list[str] = []
    for reference in references:
        path = _prompt_path(prompt_dir, reference)
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
