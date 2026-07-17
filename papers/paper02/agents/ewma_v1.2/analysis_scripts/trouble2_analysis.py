#!/usr/bin/env python3
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from count_level_attempts import (
    LEVEL_ATTEMPT_DIR_RE,
    count_level_attempts,
    count_level_steps,
    format_label,
    game_name_from_folder_name,
)
from count_level_attempts_dirs import iter_session_dirs


DEFAULT_RESET_STEP_THRESHOLD = 200


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _level_attempt_dirs(session_dir):
    attempts_by_level = defaultdict(list)

    for path in session_dir.iterdir():
        if not path.is_dir():
            continue

        match = LEVEL_ATTEMPT_DIR_RE.match(path.name)
        if match:
            level = int(match.group(1))
            attempt = int(match.group(2))
            attempts_by_level[level].append((attempt, path))

    for attempts in attempts_by_level.values():
        attempts.sort(key=lambda item: item[0])

    return attempts_by_level


def _is_reset_attempt(metadata):
    action_input = metadata.get("action_input")
    if not isinstance(action_input, dict):
        return False
    return action_input.get("id") == "RESET"


def _step_metadata_number(path):
    match = re.match(r"^step_(\d{4})_metadata\.json$", path.name)
    if not match:
        return -1
    return int(match.group(1))


def max_levels_completed(attempts_by_level):
    max_completed = 0

    for attempts in attempts_by_level.values():
        for _attempt_number, attempt_dir in attempts:
            metadata_paths = [attempt_dir / "initial_metadata.json"]
            metadata_paths.extend(
                sorted(
                    attempt_dir.glob("step_*_metadata.json"),
                    key=_step_metadata_number,
                )
            )

            for metadata_path in metadata_paths:
                try:
                    metadata = _read_json(metadata_path)
                    completed = int(metadata.get("levels_completed", 0))
                except (OSError, json.JSONDecodeError, TypeError, ValueError):
                    continue

                max_completed = max(max_completed, completed)

                try:
                    win_levels = int(metadata.get("win_levels", 0))
                except (TypeError, ValueError):
                    win_levels = 0
                if metadata.get("state") == "WIN":
                    max_completed = max(max_completed, win_levels)

    return max_completed


def trouble_levels(session_dir, threshold=DEFAULT_RESET_STEP_THRESHOLD):
    attempts_by_level = _level_attempt_dirs(session_dir)
    counts = count_level_attempts(session_dir)
    steps = count_level_steps(session_dir)
    completed_through_level = max_levels_completed(attempts_by_level)

    selected = []
    for level, attempts in sorted(attempts_by_level.items()):
        if not attempts:
            continue

        try:
            first_metadata = _read_json(attempts[0][1] / "initial_metadata.json")
            first_step_index = int(first_metadata["step_index"])
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue

        reset_steps = []
        last_printed_reset_step = None
        for _attempt_number, attempt_dir in attempts[1:]:
            try:
                metadata = _read_json(attempt_dir / "initial_metadata.json")
                step_on_level = int(metadata["step_index"]) - first_step_index
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue

            if not _is_reset_attempt(metadata):
                continue

            if last_printed_reset_step is None:
                if step_on_level >= threshold:
                    reset_steps.append(step_on_level)
                    last_printed_reset_step = step_on_level
            elif step_on_level - last_printed_reset_step >= threshold:
                reset_steps.append(step_on_level)
                last_printed_reset_step = step_on_level

        if reset_steps:
            level_key = f"{level:02d}"
            selected.append(
                {
                    "level": level_key,
                    "solved": completed_through_level >= level,
                    "attempts": counts[level_key],
                    "steps": steps[level_key],
                    "reset_steps": reset_steps,
                }
            )

    return selected


def format_trouble_levels(levels):
    parts = []
    for item in levels:
        solved = "S" if item["solved"] else "N"
        reset_steps = ",".join(str(step) for step in item["reset_steps"])
        parts.append(
            f'{item["level"]}/{solved}/{item["attempts"]}/{item["steps"]}/resets={reset_steps}'
        )
    return ", ".join(parts)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Scan /home/<name>/run/agent_run/client/session directories and "
            "print levels where RESET started a new attempt at cumulative "
            "step_on_this_level >= threshold."
        )
    )
    parser.add_argument(
        "home_root",
        nargs="?",
        default="/home",
        help="Root directory containing run homes (default: /home)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_RESET_STEP_THRESHOLD,
        help=f"Minimum cumulative level step for a reset (default: {DEFAULT_RESET_STEP_THRESHOLD})",
    )
    args = parser.parse_args()

    home_root = Path(args.home_root)
    if not home_root.is_dir():
        parser.error(f"not a directory: {home_root}")

    found = False
    selected_any = False
    for name, session_dir in iter_session_dirs(home_root):
        found = True
        levels = trouble_levels(session_dir, args.threshold)
        if not levels:
            continue

        selected_any = True
        label = format_label(name, game_name_from_folder_name(name))
        print(f"{label}: {format_trouble_levels(levels)}")

    if not found:
        print(f"No session directories found under {home_root}")
    elif not selected_any:
        print(f"No reset levels found with step_on_this_level >= {args.threshold}")


if __name__ == "__main__":
    main()
