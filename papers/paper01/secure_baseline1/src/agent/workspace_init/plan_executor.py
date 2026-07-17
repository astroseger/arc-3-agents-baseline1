from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

import numpy as np

from game_status import GAME_OVER, LEVEL_COMPLETED, RUNNING
from script_tools import format_action
from mismatch_artifacts import next_mismatch_dir, save_mismatch_as_magneta_png, save_mismatch_region_png, save_simulated_frame
from state_reconstruction_tools import reconstruct_current_state
from session_tools import CLIENT_DIR, read_current_attempt
from world_model_engine import world_model_engine
from world_model_state_io import state_renderer


def _parse_action_arg(action_arg: str) -> dict:
    stripped = action_arg.strip()
    if stripped.startswith("{"):
        action = json.loads(stripped)
        if not isinstance(action, dict) or "name" not in action:
            raise ValueError(f"Invalid JSON action: {action_arg}")
        return action
    return {"name": action_arg}


def _client_command(action: dict) -> list[str]:
    command = ["python3", "client.py", "move", action["name"]]
    if "x" in action:
        command.extend(["--x", str(action["x"])])
    if "y" in action:
        command.extend(["--y", str(action["y"])])
    return command


def _observed_status(level: int, attempt: dict) -> str:
    if attempt["level_index"] > level:
        return LEVEL_COMPLETED
    return attempt["status"]


def _print_animation_paths(step: dict) -> None:
    if not step["intermediate_frame_png_filenames"]:
        return
    print("plan_executor.py: the step on which mismatch was detected also generated animation. The frames are:")
    for path in step["intermediate_frame_png_filenames"] + [step["final_frame_png_filename"]]:
        print(str(Path(path).resolve()))


def _raise_frame_mismatch(step: dict, predicted_frame: np.ndarray) -> None:
    mismatch_dir = next_mismatch_dir()
    simulated_ascii_path, simulated_png_path = save_simulated_frame(mismatch_dir, predicted_frame)
    mismatch_region_png_path = save_mismatch_region_png(mismatch_dir, step["final_frame"], predicted_frame)
    mismatch_as_magneta_png_path = save_mismatch_as_magneta_png(mismatch_dir, step["final_frame"], predicted_frame)

    print("plan_executor.py: frame mismatch detected")
    print(f"real ascii: {Path(step['final_frame_filename']).resolve()}")
    print(f"real png: {Path(step['final_frame_png_filename']).resolve()}")
    print(f"simulated ascii: {simulated_ascii_path.resolve()} (predicted frame as text)")
    print(f"simulated png: {simulated_png_path.resolve()} (predicted frame rendered)")
    print(f"mismatch region png: {mismatch_region_png_path.resolve()} (localized mismatch neighborhoods)")
    print(f"mismatch as magneta png: {mismatch_as_magneta_png_path.resolve()} (full frame with magenta mismatch pixels)")
    _print_animation_paths(step)

    raise AssertionError("plan_executor.py: mismatch after action")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("actions", nargs="+")
    args = parser.parse_args()

    actions = [_parse_action_arg(action_arg) for action_arg in args.actions]
    if any(action["name"] == "RESET" for action in actions):
        raise ValueError("plan_executor.py does not support RESET. Start a new attempt explicitly and then execute in-attempt actions.")

    current_attempt = read_current_attempt()
    level = int(current_attempt["level_index"])
    current_state = reconstruct_current_state()

    for action in actions:
        predicted_state, predicted_status = world_model_engine(current_state, action)
        predicted_frame = state_renderer(predicted_state) if predicted_status == RUNNING else None
        print(f"plan_executor.py: running {format_action(action)}")

        subprocess.run(_client_command(action), cwd=CLIENT_DIR, check=True)

        actual_attempt = read_current_attempt()
        actual_status = _observed_status(level, actual_attempt)

        if actual_status != predicted_status:
            raise AssertionError(
                f"plan_executor.py: status mismatch after {format_action(action)}: predicted {predicted_status}, observed {actual_status}"
            )

        if actual_status == LEVEL_COMPLETED:
            print("plan_executor.py: stopped on level completion")
            return 0
        if actual_status == GAME_OVER:
            print("plan_executor.py: stopped on GAME_OVER")
            return 0

        observed_frame = actual_attempt["steps"][-1]["final_frame"]
        if predicted_frame is None or not np.array_equal(predicted_frame, observed_frame):
            _raise_frame_mismatch(actual_attempt["steps"][-1], predicted_frame if predicted_frame is not None else observed_frame)
        current_state = predicted_state

    print("plan_executor.py: sequence executed without mismatch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
