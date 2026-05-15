from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from game_status import RUNNING
from mismatch_artifacts import next_mismatch_dir, save_mismatch_as_magneta_png, save_mismatch_region_png, save_simulated_frame
from script_tools import resolve_level
from session_tools import Attempt, read_all_attempts_for_level, truncate_attempt
from state_reconstruction_tools import reconstruct_initial_state_from_attempt
from timeout_tools import fail_after_timeout
from world_model_engine import world_model_engine
from world_model_state_io import apply_render_overrides, state_renderer


TIMEOUT_SECONDS = 180
WORLD_MODEL_TIMEOUT_MESSAGE = "Your world model is too slow, please consider refactoring it."
_WARNED_RENDER_OVERRIDE_LEVELS: set[int] = set()


class VerificationMismatchError(AssertionError):
    """Expected verification mismatch; distinct from world-model implementation failures."""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--till-level-attempt-step",
        nargs=3,
        required=True,
        type=int,
        metavar=("LEVEL", "ATTEMPT", "STEP_INSIDE_ATTEMPT"),
    )
    args = parser.parse_args()
    if args.till_level_attempt_step[2] < 0:
        parser.error("--till-level-attempt-step STEP_INSIDE_ATTEMPT must be non-negative")
    return args


def _render_frame(
    state: dict,
    attempt_index: int | None,
    step_count: int | None,
) -> np.ndarray:
    level_index = int(state["level"])
    base_frame = state_renderer(state)
    patched_frame = apply_render_overrides(base_frame.copy(), state, level_index, attempt_index, step_count)
    if not np.array_equal(base_frame, patched_frame) and level_index not in _WARNED_RENDER_OVERRIDE_LEVELS:
        print(
            f"verify_world_model_follower.py: warning: level {level_index} uses apply_render_overrides; "
            "treat this as temporary and as a clue to a missing puzzle mechanic"
        )
        _WARNED_RENDER_OVERRIDE_LEVELS.add(level_index)
    return patched_frame


def _predict_step(
    state: dict,
    step: dict,
    attempt_index: int,
    step_count: int,
) -> tuple[dict, str, np.ndarray | None]:
    next_state, next_status = world_model_engine(state, step["action"])
    next_frame = _render_frame(next_state, attempt_index, step_count) if next_status == RUNNING else None
    return next_state, next_status, next_frame


def _frame_mismatch_message(context: str, real_ascii_path: str) -> str:
    return f"{context}\nreal ascii: {Path(real_ascii_path).resolve()}"


def _raise_frame_mismatch(
    context: str,
    real_frame: np.ndarray,
    real_ascii_path: str,
    real_png_path: str,
    predicted_frame: np.ndarray,
) -> None:
    message = _frame_mismatch_message(context, real_ascii_path)
    mismatch_dir = next_mismatch_dir()
    simulated_ascii_path, simulated_png_path = save_simulated_frame(mismatch_dir, predicted_frame)
    mismatch_region_png_path = save_mismatch_region_png(mismatch_dir, real_frame, predicted_frame)
    mismatch_as_magneta_png_path = save_mismatch_as_magneta_png(mismatch_dir, real_frame, predicted_frame)
    raise VerificationMismatchError(
        "\n".join(
            [
                message,
                f"real png: {Path(real_png_path).resolve()}",
                f"simulated ascii: {simulated_ascii_path.resolve()} (predicted frame as text)",
                f"simulated png: {simulated_png_path.resolve()} (predicted frame rendered)",
                f"mismatch region png: {mismatch_region_png_path.resolve()} (localized mismatch neighborhoods)",
                f"mismatch as magneta png: {mismatch_as_magneta_png_path.resolve()} (full frame with magenta mismatch pixels)",
            ]
        )
    )


def _raise_status_mismatch(context: str, real_ascii_path: str) -> None:
    raise VerificationMismatchError(_frame_mismatch_message(context, real_ascii_path))


def _replay_attempt(
    model_level: int,
    replay_level: int,
    attempt: Attempt,
) -> None:
    initial_frame = attempt["initial_frame"]
    initial_state = reconstruct_initial_state_from_attempt(replay_level, attempt)

    rendered_initial = _render_frame(initial_state, int(attempt["attempt_index"]), 0)
    if not np.array_equal(rendered_initial, initial_frame):
        _raise_frame_mismatch(
            f"Model level {model_level}, replay level {replay_level}, attempt {attempt['attempt_index']}, replay, initial state: rendered initial frame mismatch.",
            initial_frame,
            attempt["initial_frame_filename"],
            attempt["initial_frame_png_filename"],
            rendered_initial,
        )

    state = initial_state
    for index, step in enumerate(attempt["steps"]):
        state, game_status, rendered = _predict_step(state, step, int(attempt["attempt_index"]), index + 1)
        if game_status != step["observed_status"]:
            _raise_status_mismatch(
                f"Model level {model_level}, replay level {replay_level}, attempt {attempt['attempt_index']}, replay, step {index + 1}: "
                f"predicted status {game_status}, observed {step['observed_status']}.",
                step["final_frame_filename"],
            )
        if step["observed_status"] == RUNNING and not np.array_equal(rendered, step["final_frame"]):
            _raise_frame_mismatch(
                f"Model level {model_level}, replay level {replay_level}, attempt {attempt['attempt_index']}, replay, step {index + 1}: rendered frame mismatch.",
                step["final_frame"],
                step["final_frame_filename"],
                step["final_frame_png_filename"],
                rendered,
            )


def _attempts_to_verify_through_step(
    replay_level: int,
    till_level: int,
    till_attempt: int,
    till_step_inside_attempt: int,
) -> list[Attempt]:
    attempts = read_all_attempts_for_level(replay_level)
    if not attempts:
        raise RuntimeError(f"No level-{replay_level} attempts found in the latest session.")
    if replay_level < till_level:
        return attempts

    selected_attempts: list[Attempt] = []
    found_target_attempt = False
    for attempt in attempts:
        attempt_index = int(attempt["attempt_index"])
        if attempt_index < till_attempt:
            selected_attempts.append(attempt)
            continue
        if attempt_index == till_attempt:
            selected_attempts.append(truncate_attempt(attempt, till_step_inside_attempt))
            found_target_attempt = True
            break
        break
    if not found_target_attempt:
        raise RuntimeError(f"No level-{till_level} attempt-{till_attempt} found in the latest session.")
    return selected_attempts


def main() -> int:
    args = _parse_args()
    till_level, till_attempt, till_step_inside_attempt = args.till_level_attempt_step
    model_level = resolve_level(None)
    replay_level: int | None = None

    try:
        with fail_after_timeout(TIMEOUT_SECONDS, WORLD_MODEL_TIMEOUT_MESSAGE):
            for replay_level in range(1, till_level + 1):
                attempts_to_verify = _attempts_to_verify_through_step(
                    replay_level,
                    till_level,
                    till_attempt,
                    till_step_inside_attempt,
                )
                for attempt in attempts_to_verify:
                    _replay_attempt(model_level, replay_level, attempt)
                print(f"verify_world_model_follower.py: level {replay_level} verified")
    except VerificationMismatchError as exc:
        level_label = replay_level if replay_level is not None else "unknown"
        print(f"verify_world_model_follower.py: verification failed for level {level_label}")
        print(exc)
        return 1

    print(
        "verify_world_model_follower.py: "
        f"verified through level {till_level} attempt {till_attempt} step {till_step_inside_attempt}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
