from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import analyse_funs


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Analyse a runs directory: replay each game into <game>_scorecard.json "
            "and write <game>_cost_estimation.json."
        )
    )
    parser.add_argument("runs_dir", type=Path, help="Folder containing one subfolder per game")
    args = parser.parse_args()

    runs_dir = args.runs_dir.resolve()
    if not runs_dir.is_dir():
        print(f"Runs folder does not exist: {runs_dir}", file=sys.stderr)
        return 1

    games = analyse_funs.game_folders(runs_dir)
    if not games:
        print(f"No game folders found in {runs_dir}", file=sys.stderr)
        return 1

    extractor_path = Path(__file__).with_name("extract_actions_from_server_log.py")
    try:
        subprocess.run(
            [sys.executable, str(extractor_path), str(runs_dir)],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"Failed to extract actions from server log: {exc}", file=sys.stderr)
        return exc.returncode or 1

    failed = False
    for game_dir in games:
        try:
            output_path = analyse_funs.write_scorecard(game_dir, runs_dir)
        except (FileNotFoundError, RuntimeError, ValueError, OSError) as exc:
            failed = True
            print(f"{game_dir.name}: failed to write scorecard: {exc}", file=sys.stderr)
            continue
        print(f"{game_dir.name}: wrote {output_path.name}")

    try:
        cost_paths = analyse_funs.write_cost_estimations(runs_dir, games)
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"Failed to write cost estimation: {exc}", file=sys.stderr)
        return 1
    for cost_path in cost_paths:
        print(f"wrote {cost_path.name}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
