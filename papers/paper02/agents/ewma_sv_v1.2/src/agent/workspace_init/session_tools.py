from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, TypedDict

import numpy as np

from game_status import GAME_OVER, LEVEL_COMPLETED, RUNNING


ROOT = Path(__file__).resolve().parent
CLIENT_DIR = ROOT / "client"
SESSION_DIR = CLIENT_DIR / "session"

_ATTEMPT_DIR_RE = re.compile(r"^level_(\d+)_attempt_(\d+)$")
_STEP_METADATA_RE = re.compile(r"^step_(\d{4})_metadata\.json$")


class AttemptStep(TypedDict):
    action: dict[str, Any]
    final_frame: np.ndarray
    metadata: dict[str, Any]
    final_frame_filename: str
    final_frame_png_filename: str
    intermediate_frame_filenames: list[str]
    intermediate_frame_png_filenames: list[str]
    observed_status: str


class Attempt(TypedDict):
    level_index: int
    attempt_index: int
    path: str
    initial_frame: np.ndarray
    initial_metadata: dict[str, Any]
    initial_frame_filename: str
    initial_frame_png_filename: str
    steps: list[AttemptStep]
    status: str


def _latest_session_dir() -> Path:
    if not SESSION_DIR.is_dir():
        raise FileNotFoundError("No client session was found.")
    return SESSION_DIR


def _load_ascii_frame(path: Path) -> np.ndarray:
    rows = [[int(char, 16) for char in line.strip()] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        return np.zeros((0, 0), dtype=np.int16)
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError(f"Inconsistent ASCII frame row widths in {path}.")
    return np.array(rows, dtype=np.int16)


def _normalize_action(action_input: dict[str, Any]) -> dict[str, Any]:
    action = {"name": action_input["id"]}
    data = action_input.get("data") or {}
    if "x" in data:
        action["x"] = data["x"]
    if "y" in data:
        action["y"] = data["y"]
    return action


def _step_status(level_index: int, step_metadata: dict[str, Any]) -> str:
    if step_metadata["state"] == GAME_OVER:
        return GAME_OVER
    if int(step_metadata["levels_completed"]) >= level_index:
        return LEVEL_COMPLETED
    return RUNNING


def _read_step(attempt_dir: Path, level_index: int, step_number: int) -> AttemptStep:
    metadata_path = attempt_dir / f"step_{step_number:04d}_metadata.json"
    final_frame_path = attempt_dir / f"step_{step_number:04d}_final.txt"
    final_frame_png_path = attempt_dir / f"step_{step_number:04d}_final.png"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    intermediate_ascii_paths = sorted(attempt_dir.glob(f"step_{step_number:04d}_intermediate_*.txt"))
    intermediate_png_paths = sorted(attempt_dir.glob(f"step_{step_number:04d}_intermediate_*.png"))
    return {
        "action": _normalize_action(metadata["action_input"]),
        "final_frame": _load_ascii_frame(final_frame_path),
        "metadata": metadata,
        "final_frame_filename": str(final_frame_path),
        "final_frame_png_filename": str(final_frame_png_path),
        "intermediate_frame_filenames": [str(path) for path in intermediate_ascii_paths],
        "intermediate_frame_png_filenames": [str(path) for path in intermediate_png_paths],
        "observed_status": _step_status(level_index, metadata),
    }


def _read_attempt(attempt_dir: Path, level_index: int, attempt_index: int) -> Attempt:
    initial_metadata_path = attempt_dir / "initial_metadata.json"
    initial_frame_path = attempt_dir / "initial_frame.txt"
    initial_frame_png_path = attempt_dir / "initial_frame.png"
    initial_metadata = json.loads(initial_metadata_path.read_text(encoding="utf-8"))
    step_numbers = sorted(
        int(match.group(1))
        for path in attempt_dir.glob("step_*_metadata.json")
        if (match := _STEP_METADATA_RE.match(path.name))
    )
    steps: list[AttemptStep] = []
    for step_number in step_numbers:
        final_frame_path = attempt_dir / f"step_{step_number:04d}_final.txt"
        if not final_frame_path.is_file():
            if steps and steps[-1]["observed_status"] == GAME_OVER:
                continue
            raise FileNotFoundError(
                f"Missing final frame for {attempt_dir.name} step {step_number:04d} before terminal state was reached."
            )
        steps.append(_read_step(attempt_dir, level_index, step_number))
    status = RUNNING
    if steps:
        status = steps[-1]["observed_status"]
    return {
        "level_index": level_index,
        "attempt_index": attempt_index,
        "path": str(attempt_dir),
        "initial_frame": _load_ascii_frame(initial_frame_path),
        "initial_metadata": initial_metadata,
        "initial_frame_filename": str(initial_frame_path),
        "initial_frame_png_filename": str(initial_frame_png_path),
        "steps": steps,
        "status": status,
    }


def _session_dir(session_dir: Path | None = None) -> Path:
    return _latest_session_dir() if session_dir is None else session_dir


def read_session_attempts(session_dir: Path | None = None) -> dict[int, list[Attempt]]:
    session_dir = _session_dir(session_dir)
    attempts_by_level: dict[int, list[tuple[int, Attempt]]] = {}
    for path in session_dir.iterdir():
        if not path.is_dir():
            continue
        match = _ATTEMPT_DIR_RE.match(path.name)
        if match is None:
            continue
        found_level = int(match.group(1))
        attempt_index = int(match.group(2))
        attempts_by_level.setdefault(found_level, []).append((attempt_index, _read_attempt(path, found_level, attempt_index)))
    normalized: dict[int, list[Attempt]] = {}
    for level, attempts in attempts_by_level.items():
        attempts.sort(key=lambda item: item[0])
        normalized[level] = [attempt for _, attempt in attempts]
    return normalized


def read_all_attempts_for_level(level_index: int, session_dir: Path | None = None) -> list[Attempt]:
    return read_session_attempts(session_dir).get(level_index, [])


def read_latest_attempt_for_level(level_index: int, session_dir: Path | None = None) -> Attempt:
    attempts = read_all_attempts_for_level(level_index, session_dir)
    if not attempts:
        raise RuntimeError(f"No level-{level_index} attempts found in the latest session.")
    return attempts[-1]


def read_current_attempt(session_dir: Path | None = None) -> Attempt:
    attempts_by_level = read_session_attempts(session_dir)
    if not attempts_by_level:
        raise FileNotFoundError("No attempts were found in the latest client session.")
    level_index = max(attempts_by_level)
    return attempts_by_level[level_index][-1]


def read_attempt_for_level(level_index: int, attempt_index: int, session_dir: Path | None = None) -> Attempt:
    attempts = read_all_attempts_for_level(level_index, session_dir)
    for attempt in attempts:
        if int(attempt["attempt_index"]) == attempt_index:
            return attempt
    raise RuntimeError(f"No level-{level_index} attempt-{attempt_index} found in the latest session.")


def get_current_level_id() -> int:
    session_dir = _latest_session_dir()
    levels = {
        int(match.group(1))
        for path in session_dir.iterdir()
        if path.is_dir() and (match := _ATTEMPT_DIR_RE.match(path.name))
    }
    if not levels:
        raise FileNotFoundError("No attempts were found in the latest client session.")
    return max(levels)


def truncate_attempt(attempt: Attempt, step_count: int) -> Attempt:
    steps = attempt["steps"]
    if step_count < 0:
        raise ValueError("step_count must be non-negative.")
    if step_count > len(steps):
        raise ValueError(f"step_count {step_count} exceeds attempt length {len(steps)}.")

    truncated = copy.copy(attempt)
    truncated["steps"] = [copy.copy(step) for step in attempt["steps"][:step_count]]
    if step_count < len(steps):
        truncated["status"] = RUNNING
    return truncated


def read_attempt_prefix_for_level(level_index: int, attempt_index: int, step_count: int, session_dir: Path | None = None) -> Attempt:
    return truncate_attempt(read_attempt_for_level(level_index, attempt_index, session_dir), step_count)


def attempt_step_count(attempt: Attempt) -> int:
    return len(attempt["steps"])
