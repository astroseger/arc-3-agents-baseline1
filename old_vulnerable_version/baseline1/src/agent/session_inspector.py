from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


RUNNING = "RUNNING"
LEVEL_COMPLETED = "LEVEL_COMPLETED"
GAME_OVER = "GAME_OVER"

DEFAULT_SESSION_DIR = Path(__file__).resolve().parent / "agent_run" / "client" / "session"

_ATTEMPT_DIR_RE = re.compile(r"^level_(\d+)_attempt_(\d+)$")
_STEP_METADATA_RE = re.compile(r"^step_(\d{4})_metadata\.json$")


@dataclass(frozen=True)
class AttemptInfo:
    level_index: int
    attempt_index: int
    win_levels: int
    status: str
    n_steps: int
    path: Path


@dataclass(frozen=True)
class SessionInspection:
    is_solved: bool
    is_game_over: bool
    is_level_completed: bool
    n_steps_total: int
    n_steps_current_level: int
    n_steps_current_attempt: int
    n_game_over_attempts_current_level: int
    current_level_index: int | None
    attempts_per_level: dict[int, int]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _attempt_status(level_index: int, step_metadata: dict) -> str:
    if step_metadata["state"] == GAME_OVER:
        return GAME_OVER
    if int(step_metadata["levels_completed"]) >= level_index:
        return LEVEL_COMPLETED
    return RUNNING


def _read_attempt_info(attempt_dir: Path, level_index: int, attempt_index: int) -> AttemptInfo:
    initial_metadata = _read_json(attempt_dir / "initial_metadata.json")
    step_numbers = sorted(
        int(match.group(1))
        for path in attempt_dir.glob("step_*_metadata.json")
        if (match := _STEP_METADATA_RE.match(path.name))
    )

    status = RUNNING
    if step_numbers:
        last_step_metadata = _read_json(attempt_dir / f"step_{step_numbers[-1]:04d}_metadata.json")
        status = _attempt_status(level_index, last_step_metadata)

    return AttemptInfo(
        level_index=level_index,
        attempt_index=attempt_index,
        win_levels=int(initial_metadata["win_levels"]),
        status=status,
        n_steps=len(step_numbers),
        path=attempt_dir,
    )


def read_session_attempts(session_dir: str | Path | None = None) -> dict[int, list[AttemptInfo]]:
    session_dir = DEFAULT_SESSION_DIR if session_dir is None else Path(session_dir)
    attempts_by_level: dict[int, list[AttemptInfo]] = {}

    for path in session_dir.iterdir():
        if not path.is_dir():
            continue
        match = _ATTEMPT_DIR_RE.match(path.name)
        if match is None:
            continue

        level_index = int(match.group(1))
        attempt_index = int(match.group(2))
        attempts_by_level.setdefault(level_index, []).append(
            _read_attempt_info(path, level_index, attempt_index)
        )

    for attempts in attempts_by_level.values():
        attempts.sort(key=lambda attempt: attempt.attempt_index)

    return attempts_by_level


def inspect_sessions(session_dir: str | Path = DEFAULT_SESSION_DIR) -> SessionInspection:
    session_dir = Path(session_dir)
    if not session_dir.is_dir():
        return SessionInspection(
            is_solved=False,
            is_game_over=False,
            is_level_completed=False,
            n_steps_total=0,
            n_steps_current_level=0,
            n_steps_current_attempt=0,
            n_game_over_attempts_current_level=0,
            current_level_index=None,
            attempts_per_level={},
        )

    attempts_by_level = read_session_attempts(session_dir)
    if not attempts_by_level:
        return SessionInspection(
            is_solved=False,
            is_game_over=False,
            is_level_completed=False,
            n_steps_total=0,
            n_steps_current_level=0,
            n_steps_current_attempt=0,
            n_game_over_attempts_current_level=0,
            current_level_index=None,
            attempts_per_level={},
        )

    current_level_index = max(attempts_by_level)
    current_level_attempts = attempts_by_level[current_level_index]
    latest_attempt = current_level_attempts[-1]
    n_steps_total = sum(
        attempt.n_steps for attempts in attempts_by_level.values() for attempt in attempts
    )
    n_steps_current_level = sum(attempt.n_steps for attempt in current_level_attempts)
    n_steps_current_attempt = latest_attempt.n_steps

    n_game_over_attempts_current_level = sum(
        1 for attempt in current_level_attempts if attempt.status == GAME_OVER
    )
    attempts_per_level = {
        level_index: len(attempts)
        for level_index, attempts in attempts_by_level.items()
    }
    is_solved = (
        latest_attempt.level_index == latest_attempt.win_levels
        and latest_attempt.status == LEVEL_COMPLETED
    )
    is_game_over = latest_attempt.status == GAME_OVER
    is_level_completed = latest_attempt.status == LEVEL_COMPLETED

    return SessionInspection(
        is_solved=is_solved,
        is_game_over=is_game_over,
        is_level_completed=is_level_completed,
        n_steps_total=n_steps_total,
        n_steps_current_level=n_steps_current_level,
        n_steps_current_attempt=n_steps_current_attempt,
        n_game_over_attempts_current_level=n_game_over_attempts_current_level,
        current_level_index=current_level_index,
        attempts_per_level=attempts_per_level,
    )
