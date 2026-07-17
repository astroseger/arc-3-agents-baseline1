#!/usr/bin/env python3
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


LEVEL_DIR_RE = re.compile(r"^level_(\d+)")
LEVEL_ATTEMPT_DIR_RE = re.compile(r"^level_(\d+)_attempt_(\d+)$")
STEP_METADATA_RE = re.compile(r"^step_(\d{4})_metadata\.json$")


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
    attempts_by_level = defaultdict(list)

    for path in session_dir.iterdir():
        if not path.is_dir():
            continue

        match = LEVEL_ATTEMPT_DIR_RE.match(path.name)
        if match:
            level = int(match.group(1))
            attempt = int(match.group(2))
            attempts_by_level[level].append((attempt, path))

    for level, attempts in attempts_by_level.items():
        attempts.sort(key=lambda item: item[0])
        steps[str(level).zfill(2)] = _level_step_count([path for _, path in attempts])

    return steps


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _step_metadata_numbers(attempt_dir):
    return sorted(
        int(match.group(1))
        for path in attempt_dir.glob("step_*_metadata.json")
        if (match := STEP_METADATA_RE.match(path.name))
    )


def _latest_metadata_path(attempt_dir, n_steps):
    if n_steps == 0:
        return attempt_dir / "initial_metadata.json"
    return attempt_dir / f"step_{n_steps:04d}_metadata.json"


def _level_step_count(attempt_dirs):
    first_attempt = attempt_dirs[0]
    latest_attempt = attempt_dirs[-1]
    latest_attempt_steps = len(_step_metadata_numbers(latest_attempt))
    first_metadata = _read_json(first_attempt / "initial_metadata.json")
    latest_metadata = _read_json(_latest_metadata_path(latest_attempt, latest_attempt_steps))
    return int(latest_metadata["step_index"]) - int(first_metadata["step_index"])


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


def game_name_from_folder_name(folder_name):
    if len(folder_name) >= 4:
        return folder_name[:4]
    return None


def game_name_from_session_folder(session_dir):
    try:
        folder_name = session_dir.parents[3].name
    except IndexError:
        return None
    return game_name_from_folder_name(folder_name)


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
    label = format_label(session_dir.name, game_name_from_session_folder(session_dir))
    print(f"{label}: {format_counts(counts, game_completed(session_dir), steps)}")


if __name__ == "__main__":
    main()
