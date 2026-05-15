from __future__ import annotations

from game_status import LEVEL_COMPLETED
from script_tools import main_planner, resolve_level
from session_tools import read_all_attempts_for_level
from state_reconstruction_tools import reconstruct_initial_state, simulate_actions
from timeout_tools import fail_after_timeout


TIMEOUT_SECONDS = 180
PLANNER_TIMEOUT_MESSAGE = "Planner too slow, please consider using a faster planner."


class PlannerVerificationError(AssertionError):
    """Expected planner verification failure; distinct from planner implementation failures."""


def _verify_level(level: int) -> bool:
    attempts = read_all_attempts_for_level(level)
    if not attempts:
        print(f"verify_main_planner.py: No level-{level} attempts found, we skip this level")
        return False
    if not any(attempt["status"] == LEVEL_COMPLETED for attempt in attempts):
        print(f"verify_main_planner.py: No completed level-{level} attempt found, we skip this level")
        return False

    initial_state = reconstruct_initial_state(level)
    plan = main_planner(initial_state)
    if not plan:
        raise PlannerVerificationError(f"Main planner did not find a plan from the level-{level} initial state.")

    _, game_status = simulate_actions(initial_state, plan)
    if game_status != LEVEL_COMPLETED:
        raise PlannerVerificationError(f"Main planner plan from the level-{level} initial state did not reach completion.")
    return True


def main() -> int:
    target_level = resolve_level(None)
    verified_up_to_level = 0
    replay_level: int | None = None

    try:
        with fail_after_timeout(TIMEOUT_SECONDS, PLANNER_TIMEOUT_MESSAGE):
            for replay_level in range(1, target_level + 1):
                if not _verify_level(replay_level):
                    break
                print(f"verify_main_planner.py: level {replay_level} verified")
                verified_up_to_level = replay_level
    except PlannerVerificationError as exc:
        level_label = replay_level if replay_level is not None else "unknown"
        print(f"verify_main_planner.py: verification failed for level {level_label}")
        print(exc)
        return 1

    if verified_up_to_level:
        print(f"verify_main_planner.py: levels 1..{verified_up_to_level} planner verification passed")
    else:
        print("verify_main_planner.py: no completed levels to verify")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
