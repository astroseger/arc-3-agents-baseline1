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


def format_score(value: Any) -> str:
    score = float(value or 0.0)
    return f"{score:.2f}%"


def format_cost_tokens(value: Any) -> str:
    cost_tokens = float(value or 0.0)
    return f"{cost_tokens / 1_000_000:,.2f}"


def cost_tokens(usage: dict[str, Any], context: str) -> float:
    required_fields = (
        "cached_input_tokens",
        "input_tokens",
        "output_tokens",
    )
    for field in required_fields:
        if field not in usage:
            raise ValueError(f"Missing {context}.{field}")

    cached_input = float(usage["cached_input_tokens"] or 0.0)
    total_input = float(usage["input_tokens"] or 0.0)
    output = float(usage["output_tokens"] or 0.0)
    return cached_input / 60 + (total_input - cached_input) / 6 + output


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


def steps_on_solved(run: dict[str, Any]) -> int:
    levels_completed = int(run.get("levels_completed", 0) or 0)
    level_actions = run.get("level_actions")
    if isinstance(level_actions, list):
        return sum(int(actions or 0) for actions in level_actions[:levels_completed])
    return int(run.get("actions", 0) or 0) if run.get("state") == "WIN" else 0


def cost_tokens_for_game(cost_payload: dict[str, Any], game: str) -> str:
    games = cost_payload.get("games")
    if not isinstance(games, dict):
        raise ValueError("Expected 'games' object in cost estimation payload")

    game_usage = games.get(game)
    if not isinstance(game_usage, dict):
        raise ValueError(f"Expected usage object for game {game}")

    return format_cost_tokens(cost_tokens(game_usage, f"games.{game}"))


def table_row(runs_dir: Path, game: str, game_cost_tokens: str) -> list[str]:
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
        game_cost_tokens,
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
    rows: list[list[str]] = []
    for game in cost_estimation_games(runs_dir):
        cost_path = cost_estimation_path(runs_dir, game)
        if not cost_path.is_file():
            raise FileNotFoundError(f"Cost estimation file does not exist: {cost_path}")
        cost_payload = read_json(cost_path)
        score_path = scorecard_path(runs_dir, game)
        if not score_path.is_file():
            raise FileNotFoundError(f"Scorecard file does not exist: {score_path}")
        rows.append(table_row(runs_dir, game, cost_tokens_for_game(cost_payload, game)))
    return rows


def total_cost_tokens_for_runs_dir(runs_dir: Path) -> float:
    total_cost_tokens = 0.0
    for game in cost_estimation_games(runs_dir):
        cost_path = cost_estimation_path(runs_dir, game)
        if not cost_path.is_file():
            raise FileNotFoundError(f"Cost estimation file does not exist: {cost_path}")
        cost_payload = read_json(cost_path)
        totals = cost_payload.get("totals")
        if not isinstance(totals, dict):
            raise ValueError(f"Expected 'totals' object in {cost_path}")
        total_cost_tokens += cost_tokens(totals, "totals")
    return total_cost_tokens


def summary_entries_for_runs_dir(runs_dir: Path) -> list[tuple[str, bool, float]]:
    entries: list[tuple[str, bool, float]] = []
    for game in cost_estimation_games(runs_dir):
        cost_path = cost_estimation_path(runs_dir, game)
        if not cost_path.is_file():
            raise FileNotFoundError(f"Cost estimation file does not exist: {cost_path}")
        score_path = scorecard_path(runs_dir, game)
        if not score_path.is_file():
            raise FileNotFoundError(f"Scorecard file does not exist: {score_path}")
        entries.append(summary_entry(runs_dir, game))
    return entries


def print_summary(
    entries: list[tuple[str, bool, float]], total_cost_tokens: float
) -> None:
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
    print(
        "total cost tokens (millions): "
        f"{format_cost_tokens(total_cost_tokens)}"
    )


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
    total_cost_tokens = sum(
        total_cost_tokens_for_runs_dir(runs_dir) for runs_dir in runs_dirs
    )

    show_run_index = len({row[0] for row in rows}) != len(rows)

    print("# Results")
    print()
    if show_run_index:
        print("| Game | Run index | Levels solved | Score | Steps on Solved | Cost Tokens (Millions) |")
        print("|---|---:|---:|---:|---:|---:|")
        sorted_rows = sorted(rows)
    else:
        print("| Game | Levels solved | Score | Steps on Solved | Cost Tokens (Millions) |")
        print("|---|---:|---:|---:|---:|")
        sorted_rows = [[row[0], *row[2:]] for row in sorted(rows)]

    for row in sorted_rows:
        print("| " + " | ".join(row) + " |")
    print_summary(summary_entries, total_cost_tokens)


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
