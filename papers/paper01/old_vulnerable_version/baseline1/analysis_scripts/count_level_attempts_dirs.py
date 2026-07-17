#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

from count_level_attempts import (
    count_level_attempts,
    count_level_steps,
    format_counts,
    format_label,
    game_completed,
    game_name_from_agent_log,
)


def natural_key(path):
    parts = re.split(r"(\d+)", path.name)
    return [int(part) if part.isdigit() else part for part in parts]


def iter_session_dirs(home_root):
    for home_dir in sorted(home_root.iterdir(), key=natural_key):
        session_dir = home_dir / "run" / "agent_run" / "client" / "session"
        try:
            is_session_dir = session_dir.is_dir()
        except OSError:
            continue

        if is_session_dir:
            yield home_dir.name, session_dir


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Scan /home/<name>/run/agent_run/client/session directories and "
            "print count_level_attempts.py results for each one."
        )
    )
    parser.add_argument(
        "home_root",
        nargs="?",
        default="/home",
        help="Root directory containing run homes (default: /home)",
    )
    args = parser.parse_args()

    home_root = Path(args.home_root)
    if not home_root.is_dir():
        parser.error(f"not a directory: {home_root}")

    found = False
    for name, session_dir in iter_session_dirs(home_root):
        found = True
        counts = count_level_attempts(session_dir)
        steps = count_level_steps(session_dir)
        label = format_label(name, game_name_from_agent_log(session_dir))
        print(f"{label}: {format_counts(counts, game_completed(session_dir), steps)}")

    if not found:
        print(f"No session directories found under {home_root}")


if __name__ == "__main__":
    main()
