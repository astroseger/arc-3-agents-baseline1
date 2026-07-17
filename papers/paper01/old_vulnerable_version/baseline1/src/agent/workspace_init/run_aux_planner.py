from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path

from game_status import LEVEL_COMPLETED, RUNNING
from script_tools import (
    add_start_source_arguments,
    format_action,
    normalize_planner_module_name,
    state_from_source_args,
)
from world_model_state_io import state_renderer
from mismatch_artifacts import next_aux_planner_dir, save_named_frame
from timeout_tools import fail_after_timeout
from world_model_engine import world_model_engine


TIMEOUT_SECONDS = 180
PLANNER_TIMEOUT_MESSAGE = "Planner too slow, please consider using a faster planner."


def _simulate_plan(current_state: dict, plan: list[dict]) -> tuple[str, Path, list[Path]]:
    artifact_dir = next_aux_planner_dir()
    written_files: list[Path] = []

    initial_frame = state_renderer(current_state)
    ascii_path, png_path = save_named_frame(artifact_dir, "step_0000_initial", initial_frame)
    written_files.extend([ascii_path, png_path])

    state = current_state
    game_status = RUNNING
    for index, action in enumerate(plan, start=1):
        state, game_status = world_model_engine(state, action)
        if game_status != RUNNING:
            break
        rendered_frame = state_renderer(state)
        ascii_path, png_path = save_named_frame(artifact_dir, f"step_{index:04d}", rendered_frame)
        written_files.extend([ascii_path, png_path])

    return game_status, artifact_dir, written_files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("planner_module", help="Python module name, for example level_4_planner_1")
    parser.add_argument("--goal", help="Optional JSON goal passed to planner(state, goal=...)")
    add_start_source_arguments(parser)
    args = parser.parse_args()

    with fail_after_timeout(TIMEOUT_SECONDS, PLANNER_TIMEOUT_MESSAGE):
        planner_module_name = normalize_planner_module_name(args.planner_module)
        planner_module = importlib.import_module(planner_module_name)
        if not hasattr(planner_module, "planner"):
            raise AttributeError(f"{planner_module_name} does not define planner(state).")
        state, description = state_from_source_args(args)
        goal = None if args.goal is None else json.loads(args.goal)
        plan = planner_module.planner(state) if goal is None else planner_module.planner(state, goal=goal)
        if not plan:
            print(f"run_aux_planner.py: no plan found from {description} using {planner_module_name}")
            return 1

        game_status, artifact_dir, written_files = _simulate_plan(state, plan)

    print(f"run_aux_planner.py: plan from {description} using {planner_module_name}")
    if game_status == LEVEL_COMPLETED:
        print("run_aux_planner.py: simulated plan reached level completion")
    print(f"run_aux_planner.py: simulated frames for the plan were written to {artifact_dir.resolve()}")
    print("run_aux_planner.py: written files")
    for path in written_files:
        print(path.name)
    print("\nACTIONS:")
    for action in plan:
        print(format_action(action))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
