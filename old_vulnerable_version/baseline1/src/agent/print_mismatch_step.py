from __future__ import annotations

import argparse
import sys
from pathlib import Path


class MismatchFound(RuntimeError):
    def __init__(self, level: int, attempt: int, step: int) -> None:
        super().__init__(f"{level} {attempt} {step}")
        self.level = level
        self.attempt = attempt
        self.step = step


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "folder",
        help="Path to a workspace_init directory, or to its parent folder.",
    )
    return parser.parse_args()


def _resolve_module_dir(folder: str) -> Path:
    base = Path(folder).resolve()
    if (base / "script_tools.py").is_file():
        return base
    candidate = base / "workspace_init"
    if (candidate / "script_tools.py").is_file():
        return candidate
    raise FileNotFoundError(
        f"Could not find script_tools.py in {base} or {candidate}."
    )


def main() -> int:
    args = _parse_args()
    module_dir = _resolve_module_dir(args.folder)
    sys.path.insert(0, str(module_dir))

    import numpy as np

    from game_status import RUNNING
    from script_tools import resolve_level
    from session_tools import Attempt, read_all_attempts_for_level
    from state_reconstruction_tools import reconstruct_initial_state_from_attempt
    from world_model_engine import world_model_engine
    from world_model_state_io import apply_render_overrides, state_renderer

    def render_frame(
        state: dict,
        attempt_index: int,
        step_count: int,
    ) -> np.ndarray:
        level_index = int(state["level"])
        frame = state_renderer(state)
        return apply_render_overrides(frame.copy(), state, level_index, attempt_index, step_count)

    def predict_step(
        state: dict,
        step: dict,
        attempt_index: int,
        step_count: int,
    ) -> tuple[dict, str, np.ndarray | None]:
        next_state, next_status = world_model_engine(state, step["action"])
        next_frame = render_frame(next_state, attempt_index, step_count) if next_status == RUNNING else None
        return next_state, next_status, next_frame

    def replay_attempt(replay_level: int, attempt: Attempt) -> None:
        attempt_index = int(attempt["attempt_index"])
        initial_state = reconstruct_initial_state_from_attempt(replay_level, attempt)
        rendered_initial = render_frame(initial_state, attempt_index, 0)
        if not np.array_equal(rendered_initial, attempt["initial_frame"]):
            raise MismatchFound(replay_level, attempt_index, 0)

        state = initial_state
        for index, step in enumerate(attempt["steps"]):
            step_count = index + 1
            state, game_status, rendered = predict_step(state, step, attempt_index, step_count)
            if game_status != step["observed_status"]:
                raise MismatchFound(replay_level, attempt_index, step_count)
            if step["observed_status"] == RUNNING and not np.array_equal(rendered, step["final_frame"]):
                raise MismatchFound(replay_level, attempt_index, step_count)

    def verify_level(replay_level: int) -> None:
        attempts = read_all_attempts_for_level(replay_level)
        if not attempts:
            raise RuntimeError(f"No level-{replay_level} attempts found in the latest session.")
        for attempt in attempts:
            replay_attempt(replay_level, attempt)

    target_level = resolve_level(None)
    try:
        for replay_level in range(1, target_level + 1):
            verify_level(replay_level)
    except MismatchFound as mismatch:
        print(f"{mismatch.level} {mismatch.attempt} {mismatch.step}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
