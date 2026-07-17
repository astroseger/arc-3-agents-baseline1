from __future__ import annotations

import json

from state_reconstruction_tools import reconstruct_current_state, reconstruct_initial_state, reconstruct_state
from session_tools import get_current_level_id
from world_model_main_planner import planner as main_planner


def resolve_level(level: int | None) -> int:
    return get_current_level_id() if level is None else level


def format_action(action: dict) -> str:
    if set(action.keys()) == {"name"}:
        return action["name"]
    return json.dumps(action, separators=(",", ":"))


def normalize_planner_module_name(planner_module: str) -> str:
    return planner_module[:-3] if planner_module.endswith(".py") else planner_module


def add_start_source_arguments(parser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--from-current", action="store_true")
    group.add_argument("--from-initial", type=int, metavar="LEVEL")
    group.add_argument("--from-attempt", nargs=3, type=int, metavar=("LEVEL", "ATTEMPT", "STEP"))


def parse_start_source(args) -> tuple[int, str, int | None, int | None]:
    if args.from_current:
        return resolve_level(None), "current", None, None
    if args.from_initial is not None:
        return int(args.from_initial), "initial", None, None
    level, attempt_index, step_count = args.from_attempt
    return int(level), "attempt", int(attempt_index), int(step_count)


def source_description(source: str, level: int, attempt_index: int | None = None, step_count: int | None = None) -> str:
    if source == "current":
        return "current state"
    if source == "initial":
        return f"initial state of level {level}"
    if source == "attempt":
        return f"level {level} attempt {attempt_index} step {step_count}"
    raise ValueError(f"Unknown source: {source}")


def state_from_source(source: str, level: int, attempt_index: int | None = None, step_count: int | None = None) -> tuple[dict, str]:
    if source == "current":
        return reconstruct_current_state(), source_description(source, level)
    if source == "initial":
        return reconstruct_initial_state(level), source_description(source, level)
    if source == "attempt":
        if attempt_index is None or step_count is None:
            raise ValueError("attempt_index and step_count are required for source='attempt'.")
        return reconstruct_state(level, attempt_index, step_count), source_description(source, level, attempt_index, step_count)
    raise ValueError(f"Unknown source: {source}")


def state_from_source_args(args) -> tuple[dict, str]:
    level, source, attempt_index, step_count = parse_start_source(args)
    return state_from_source(source, level, attempt_index, step_count)
