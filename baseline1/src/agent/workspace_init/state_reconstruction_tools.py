from __future__ import annotations

from game_status import RUNNING
from session_tools import (
    attempt_step_count,
    read_attempt_prefix_for_level,
    read_current_attempt,
    read_latest_attempt_for_level,
    truncate_attempt,
)
from world_model_engine import world_model_engine
from world_model_state_io import initial_state_reconstruction


def reconstruct_initial_state_from_attempt(level: int, attempt: dict) -> dict:
    return initial_state_reconstruction(level, attempt["initial_frame"])


def reconstruct_state(level: int, attempt_index: int, step_count: int) -> dict:
    attempt = read_attempt_prefix_for_level(level, attempt_index, step_count)
    initial_state = reconstruct_initial_state_from_attempt(level, attempt)
    return replay_attempt_prefix(initial_state, attempt, attempt_step_count(attempt))[0]


def reconstruct_initial_state(level: int) -> dict:
    attempt = truncate_attempt(read_latest_attempt_for_level(level), 0)
    return reconstruct_initial_state_from_attempt(level, attempt)


def reconstruct_current_state() -> dict:
    attempt = read_current_attempt()
    level = int(attempt["level_index"])
    return reconstruct_state(level, int(attempt["attempt_index"]), attempt_step_count(attempt))


def simulate_actions(start_state: dict, actions: list[dict]) -> tuple[dict, str]:
    state = start_state
    game_status = RUNNING
    for action in actions:
        state, game_status = world_model_engine(state, action)
        if game_status != RUNNING:
            return state, game_status
    return state, game_status


def replay_attempt_prefix(initial_state: dict, attempt: dict, step_count: int) -> tuple[dict, str]:
    return simulate_actions(initial_state, [step["action"] for step in attempt["steps"][:step_count]])


def replay_actions(start_state: dict, actions: list[dict]) -> tuple[dict, str]:
    return simulate_actions(start_state, actions)
