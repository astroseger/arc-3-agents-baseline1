from __future__ import annotations

import argparse
import sys
from pathlib import Path

import summarize_agent_log


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Walk a runs directory such as completed_runs and print the "
            "summarize_agent_log output for each run folder."
        )
    )
    parser.add_argument("runs_dir", type=Path, help="Folder containing run subfolders")
    return parser.parse_args(argv)


def iter_run_log_paths(runs_dir: Path) -> list[tuple[str, Path]]:
    run_logs: list[tuple[str, Path]] = []
    for child in sorted(path for path in runs_dir.iterdir() if path.is_dir()):
        log_path = child / "run" / "agent.log"
        if log_path.is_file():
            run_logs.append((child.name, log_path))
    return run_logs


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    runs_dir = args.runs_dir.resolve()
    if not runs_dir.is_dir():
        print(f"Runs folder does not exist: {runs_dir}", file=sys.stderr)
        return 1

    run_logs = iter_run_log_paths(runs_dir)
    if not run_logs:
        print(f"No run/agent.log files found under {runs_dir}", file=sys.stderr)
        return 1

    failed = False
    for index, (run_name, log_path) in enumerate(run_logs):
        print(run_name)
        try:
            events = summarize_agent_log.read_json_lines(log_path)
            summaries = summarize_agent_log.summarize_iterations(events)
            attempts_by_level = summarize_agent_log.read_attempts_by_level(
                summarize_agent_log.latest_session_dir(
                    summarize_agent_log.session_root_for_log(log_path)
                )
            )
            for summary in summaries:
                print(summarize_agent_log.format_summary(summary, attempts_by_level))
        except (ValueError, FileNotFoundError) as exc:
            failed = True
            print(f"ERROR: {exc}")

        if index != len(run_logs) - 1:
            print("----------------------")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
