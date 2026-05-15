from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def scorecard_path(runs_dir: Path, game: str) -> Path:
    return runs_dir / f"{game}_scorecard.json"


def format_score(value: Any) -> str:
    score = float(value or 0.0)
    return f"{score:.2f}%"


def game_name_from_scorecard(scorecard: dict[str, Any]) -> str:
    environments = scorecard.get("environments")
    if isinstance(environments, list):
        for environment in environments:
            if not isinstance(environment, dict):
                continue
            environment_id = environment.get("id")
            if isinstance(environment_id, str) and len(environment_id) >= 4:
                return environment_id[:4]

    raise ValueError("Could not determine game name from scorecard environments")


def run_index_from_name(main_folder_name: str, run_folder_name: str, game_name: str) -> str:
    prefix = f"{game_name}_"
    if run_folder_name.startswith(prefix) and len(run_folder_name) > len(prefix):
        return f"{main_folder_name}/{run_folder_name[len(prefix):]}"
    if run_folder_name == game_name:
        return main_folder_name
    return f"{main_folder_name}/{run_folder_name}"


def first_run_from_scorecard(scorecard: dict[str, Any]) -> dict[str, Any]:
    environments = scorecard.get("environments")
    if isinstance(environments, list):
        for environment in environments:
            if not isinstance(environment, dict):
                continue
            runs = environment.get("runs")
            if not isinstance(runs, list):
                continue
            for run in runs:
                if isinstance(run, dict):
                    return run

    raise ValueError("Could not determine run details from scorecard environments")


def interrupted_level_steps(run: dict[str, Any]) -> int:
    level_actions = run.get("level_actions")
    if isinstance(level_actions, list) and level_actions:
        interrupted_level_index = int(run.get("levels_completed", 0) or 0)
        if interrupted_level_index < len(level_actions):
            return int(level_actions[interrupted_level_index] or 0)
        return int(level_actions[-1] or 0)
    return int(run.get("actions", 0) or 0)


def steps_on_solved(run: dict[str, Any]) -> int:
    levels_completed = int(run.get("levels_completed", 0) or 0)
    level_actions = run.get("level_actions")
    if isinstance(level_actions, list):
        return sum(int(actions or 0) for actions in level_actions[:levels_completed])
    return int(run.get("actions", 0) or 0) if run.get("state") == "WIN" else 0


def steps_on_last(run: dict[str, Any]) -> int:
    return interrupted_level_steps(run)


def run_status(scorecard: dict[str, Any]) -> str:
    run = first_run_from_scorecard(scorecard)
    if run.get("state") == "WIN":
        return "normal termination"

    steps = steps_on_last(run)
    if steps > 1500:
        return "normal termination"
    return "interrupted"


def table_row(runs_dir: Path, game: str) -> list[str]:
    scorecard = read_json(scorecard_path(runs_dir, game))
    run = first_run_from_scorecard(scorecard)
    levels_solved = int(scorecard.get("total_levels_completed", 0) or 0)
    total_levels = int(scorecard.get("total_levels", 0) or 0)
    game_name = game_name_from_scorecard(scorecard)

    return [
        game_name,
        run_index_from_name(runs_dir.name, game, game_name),
        f"{levels_solved}/{total_levels}",
        format_score(scorecard.get("score")),
        str(steps_on_solved(run)),
        str(steps_on_last(run)),
        run_status(scorecard),
    ]


def summary_entry(runs_dir: Path, game: str) -> tuple[str, bool, float]:
    scorecard = read_json(scorecard_path(runs_dir, game))
    levels_solved = int(scorecard.get("total_levels_completed", 0) or 0)
    total_levels = int(scorecard.get("total_levels", 0) or 0)
    return (
        game_name_from_scorecard(scorecard),
        levels_solved == total_levels,
        float(scorecard.get("score") or 0.0),
    )


def rows_for_runs_dir(runs_dir: Path) -> list[list[str]]:
    cost_path = runs_dir / "cost_estimation.json"
    if not cost_path.is_file():
        raise FileNotFoundError(f"Cost estimation file does not exist: {cost_path}")

    cost_payload = read_json(cost_path)
    games = cost_payload.get("games")
    if not isinstance(games, dict):
        raise ValueError(f"Expected 'games' object in {cost_path}")

    rows: list[list[str]] = []
    for game in sorted(games):
        score_path = scorecard_path(runs_dir, game)
        if not score_path.is_file():
            raise FileNotFoundError(f"Scorecard file does not exist: {score_path}")
        rows.append(table_row(runs_dir, game))
    return rows


def summary_entries_for_runs_dir(runs_dir: Path) -> list[tuple[str, bool, float]]:
    cost_path = runs_dir / "cost_estimation.json"
    if not cost_path.is_file():
        raise FileNotFoundError(f"Cost estimation file does not exist: {cost_path}")

    cost_payload = read_json(cost_path)
    games = cost_payload.get("games")
    if not isinstance(games, dict):
        raise ValueError(f"Expected 'games' object in {cost_path}")

    entries: list[tuple[str, bool, float]] = []
    for game in sorted(games):
        score_path = scorecard_path(runs_dir, game)
        if not score_path.is_file():
            raise FileNotFoundError(f"Scorecard file does not exist: {score_path}")
        entries.append(summary_entry(runs_dir, game))
    return entries


def print_summary(entries: list[tuple[str, bool, float]]) -> None:
    by_game: dict[str, list[tuple[bool, float]]] = {}
    for game_name, solved, score in entries:
        by_game.setdefault(game_name, []).append((solved, score))

    fully_solved_games = sum(
        1
        for game_entries in by_game.values()
        if all(solved for solved, _score in game_entries)
    )
    per_game_scores = [
        sum(score for _solved, score in game_entries) / len(game_entries)
        for game_entries in by_game.values()
    ]
    mean_per_game_score = (
        sum(per_game_scores) / len(per_game_scores)
        if per_game_scores
        else 0.0
    )

    print()
    print(f"fully solved games: {fully_solved_games}/{len(by_game)}")
    print(f"mean per-game RHAE: {format_score(mean_per_game_score)}")


def print_results_md(runs_dirs: list[Path]) -> None:
    rows = [
        row
        for runs_dir in runs_dirs
        for row in rows_for_runs_dir(runs_dir)
    ]
    summary_entries = [
        entry
        for runs_dir in runs_dirs
        for entry in summary_entries_for_runs_dir(runs_dir)
    ]

    print("# Results")
    print()
    print("| Game | Run index | Levels solved | Score | Steps on Solved | Steps on Last | Run Status |")
    print("|---|---:|---:|---:|---:|---:|---|")
    for row in sorted(rows):
        print("| " + " | ".join(row) + " |")
    print_summary(summary_entries)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print a Markdown results table from generated run JSON files."
    )
    parser.add_argument(
        "runs_dirs",
        nargs="+",
        type=Path,
        help="One or more folders containing scorecard and cost JSON files",
    )
    args = parser.parse_args()

    runs_dirs = [runs_dir.resolve() for runs_dir in args.runs_dirs]
    for runs_dir in runs_dirs:
        if not runs_dir.is_dir():
            print(f"Runs folder does not exist: {runs_dir}", file=sys.stderr)
            return 1

    try:
        print_results_md(runs_dirs)
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
