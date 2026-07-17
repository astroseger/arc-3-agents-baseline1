from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}"
    r"(?:[,.]\d{1,6})?"
    r"(?:Z|[+-]\d{2}:?\d{2})?"
)


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def cost_estimation_path(runs_dir: Path, game: str) -> Path:
    return runs_dir / f"{game}_cost_estimation.json"


def cost_estimation_games(runs_dir: Path) -> list[str]:
    suffix = "_cost_estimation.json"
    games = [
        path.name[:-len(suffix)]
        for path in runs_dir.glob(f"*{suffix}")
        if path.name != "cost_estimation.json"
    ]
    if not games:
        raise FileNotFoundError(
            f"No per-game cost estimation files found in {runs_dir}"
        )
    return sorted(games)


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None

    timestamp = value.strip().replace(",", ".")
    if timestamp.endswith("Z"):
        timestamp = f"{timestamp[:-1]}+00:00"

    try:
        return datetime.fromisoformat(timestamp)
    except ValueError:
        return None


def timestamp_from_line(line: str) -> datetime | None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, dict):
        timestamp = parse_timestamp(payload.get("timestamp"))
        if timestamp is not None:
            return timestamp

    match = TIMESTAMP_RE.search(line)
    if match is None:
        return None
    return parse_timestamp(match.group(0))


def first_last_timestamps(log_path: Path) -> tuple[datetime, datetime]:
    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            timestamp = timestamp_from_line(line)
            if timestamp is None:
                continue
            if first_timestamp is None:
                first_timestamp = timestamp
            last_timestamp = timestamp

    if first_timestamp is None or last_timestamp is None:
        raise ValueError(f"No timestamped log entries found in {log_path}")
    return first_timestamp, last_timestamp


def estimated_cost_for_game(cost_payload: dict[str, Any], game: str) -> float:
    games = cost_payload.get("games")
    if not isinstance(games, dict):
        raise ValueError("Expected 'games' object in cost estimation payload")

    game_cost = games.get(game)
    if not isinstance(game_cost, dict):
        raise ValueError(f"Expected cost object for game {game}")
    if "estimated_cost_usd" not in game_cost:
        raise ValueError(f"Missing estimated_cost_usd for game {game}")

    return float(game_cost["estimated_cost_usd"] or 0.0)


def format_cost_per_hour(value: float) -> str:
    return f"${value:,.2f}/h"


def cost_per_hour_for_game(runs_dir: Path, cost_payload: dict[str, Any], game: str) -> str:
    log_path = runs_dir / game / "run" / "agent.log"
    if not log_path.is_file():
        raise FileNotFoundError(f"Log file does not exist: {log_path}")

    started_at, finished_at = first_last_timestamps(log_path)
    duration_seconds = (finished_at - started_at).total_seconds()
    if duration_seconds <= 0:
        raise ValueError(f"Non-positive duration for {log_path}")

    estimated_cost = estimated_cost_for_game(cost_payload, game)
    return format_cost_per_hour(estimated_cost / (duration_seconds / 3600.0))


def rows_for_runs_dir(runs_dir: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    for game in cost_estimation_games(runs_dir):
        cost_path = cost_estimation_path(runs_dir, game)
        if not cost_path.is_file():
            raise FileNotFoundError(f"Cost estimation file does not exist: {cost_path}")
        rows.append([game, cost_per_hour_for_game(runs_dir, read_json(cost_path), game)])
    return rows


def print_cost_per_hours(runs_dirs: list[Path]) -> None:
    rows = [
        row
        for runs_dir in runs_dirs
        for row in rows_for_runs_dir(runs_dir)
    ]

    print("| Game | Estimated cost per hour |")
    print("|---|---:|")
    for row in rows:
        print("| " + " | ".join(row) + " |")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print estimated cost per hour for each game in a run folder."
    )
    parser.add_argument(
        "runs_dirs",
        nargs="+",
        type=Path,
        help="One or more folders containing per-game cost JSON files and game run folders",
    )
    args = parser.parse_args()

    runs_dirs = [runs_dir.resolve() for runs_dir in args.runs_dirs]
    for runs_dir in runs_dirs:
        if not runs_dir.is_dir():
            print(f"Runs folder does not exist: {runs_dir}", file=sys.stderr)
            return 1

    try:
        print_cost_per_hours(runs_dirs)
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
