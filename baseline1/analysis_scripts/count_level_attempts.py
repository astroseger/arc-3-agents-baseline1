#!/usr/bin/env python3
import argparse
import json
import re
from collections import Counter
from pathlib import Path


LEVEL_DIR_RE = re.compile(r"^level_(\d+)")
LEVEL_ATTEMPT_DIR_RE = re.compile(r"^level_(\d+)_attempt_(\d+)$")
STEP_METADATA_RE = re.compile(r"^step_(\d+)_metadata\.json$")


def count_level_attempts(session_dir):
    counts = Counter()

    for path in session_dir.iterdir():
        if not path.is_dir():
            continue

        match = LEVEL_DIR_RE.match(path.name)
        if match:
            counts[match.group(1).zfill(2)] += 1

    return counts


def count_level_steps(session_dir):
    steps = Counter()

    for path in session_dir.iterdir():
        if not path.is_dir():
            continue

        match = LEVEL_ATTEMPT_DIR_RE.match(path.name)
        if match:
            level = match.group(1).zfill(2)
            steps[level] += _attempt_step_count(path)

    return steps


def _attempt_step_count(attempt_dir):
    max_step = 0

    for path in attempt_dir.iterdir():
        if not path.is_file():
            continue

        match = STEP_METADATA_RE.match(path.name)
        if match:
            max_step = max(max_step, int(match.group(1)))

    return max_step


def _last_attempt_dir(session_dir):
    attempts = []

    for path in session_dir.iterdir():
        if not path.is_dir():
            continue

        match = LEVEL_ATTEMPT_DIR_RE.match(path.name)
        if match:
            level = int(match.group(1))
            attempt = int(match.group(2))
            attempts.append((level, attempt, path))

    if not attempts:
        return None

    return max(attempts, key=lambda item: (item[0], item[1]))[2]


def _last_step_metadata(attempt_dir):
    metadata_files = []

    for path in attempt_dir.iterdir():
        if not path.is_file():
            continue

        match = STEP_METADATA_RE.match(path.name)
        if match:
            metadata_files.append((int(match.group(1)), path))

    if not metadata_files:
        return None

    return max(metadata_files, key=lambda item: item[0])[1]


def game_completed(session_dir):
    attempt_dir = _last_attempt_dir(session_dir)
    if attempt_dir is None:
        return False

    metadata_path = _last_step_metadata(attempt_dir)
    if metadata_path is None:
        return False

    try:
        with metadata_path.open() as file:
            metadata = json.load(file)
    except (OSError, json.JSONDecodeError):
        return False

    return metadata.get("state") == "WIN"


def game_name_from_agent_log(session_dir):
    agent_log = session_dir.parent.parent.parent / "agent.log"
    try:
        with agent_log.open() as file:
            first_line = file.readline()
    except OSError:
        return None

    try:
        log_entry = json.loads(first_line)
    except json.JSONDecodeError:
        return None

    game_name = log_entry.get("game_name")
    if isinstance(game_name, str) and game_name:
        return game_name
    return None


def format_label(name, game_name):
    if game_name:
        return f"{name} ({game_name})"
    return name


def format_counts(counts, completed=False, steps=None):
    parts = [
        f"{level}/{counts[level]}/{steps[level]}"
        if steps is not None
        else f"{level}/{counts[level]}"
        for level in sorted(counts)
    ]
    if completed:
        parts.append("WIN")
    return ", ".join(parts)


def main():
    parser = argparse.ArgumentParser(
        description="Count attempts per level in a session directory."
    )
    parser.add_argument("session_dir", help="Path to the session directory")
    args = parser.parse_args()

    session_dir = Path(args.session_dir)
    if not session_dir.is_dir():
        parser.error(f"not a directory: {session_dir}")

    counts = count_level_attempts(session_dir)
    steps = count_level_steps(session_dir)
    label = format_label(session_dir.name, game_name_from_agent_log(session_dir))
    print(f"{label}: {format_counts(counts, game_completed(session_dir), steps)}")


if __name__ == "__main__":
    main()
