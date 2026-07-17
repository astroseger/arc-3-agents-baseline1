from __future__ import annotations

import argparse

from script_tools import (
    add_start_source_arguments,
    format_action,
    main_planner,
    state_from_source_args,
)
from state_reconstruction_tools import simulate_actions
from timeout_tools import fail_after_timeout
from game_status import LEVEL_COMPLETED


TIMEOUT_SECONDS = 180
PLANNER_TIMEOUT_MESSAGE = "Planner too slow, please consider using a faster planner."


def main() -> int:
    parser = argparse.ArgumentParser()
    add_start_source_arguments(parser)
    args = parser.parse_args()

    with fail_after_timeout(TIMEOUT_SECONDS, PLANNER_TIMEOUT_MESSAGE):
        state, description = state_from_source_args(args)

        plan = main_planner(state)
        if not plan:
            print(f"run_main_planner.py: no plan found from {description}")
            return 1

        _, game_status = simulate_actions(state, plan)

        if game_status != LEVEL_COMPLETED:
            raise AssertionError(
                f"run_main_planner.py: planner returned a plan from {description}, "
                f"but world model execution ended with {game_status}."
            )

    print(f"run_main_planner.py: plan from {description}")
    for action in plan:
        print(format_action(action))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
