from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ATTEMPT_DIR_RE = re.compile(r"^level_(\d+)_attempt_(\d+)$")
STEP_METADATA_RE = re.compile(r"^step_(\d{4})_metadata\.json$")


@dataclass(frozen=True)
class IterationSummary:
    iteration_id: int
    timestamp: str | None
    current_level_index: int | None
    n_steps_total: int
    n_steps_current_level: int
    n_game_over_attempts_current_level: int
    is_game_over: bool
    is_solved: bool
    protocols: tuple[str, ...]


@dataclass(frozen=True)
class AttemptInfo:
    level_index: int
    attempt_index: int
    n_steps: int


def read_json_lines(log_path: Path) -> list[dict]:
    events: list[dict] = []
    with log_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} of {log_path}: {exc}") from exc
            if not isinstance(event, dict):
                raise ValueError(f"Expected a JSON object on line {line_number} of {log_path}")
            events.append(event)
    return events


def summarize_iterations(events: list[dict]) -> list[IterationSummary]:
    summaries: list[IterationSummary] = []
    pending_index: int | None = None

    for event in events:
        message = event.get("message")

        if message == "iteration inspection":
            summaries.append(
                IterationSummary(
                    iteration_id=int(event["iteration_id"]),
                    timestamp=event.get("timestamp"),
                    current_level_index=event.get("current_level_index"),
                    n_steps_total=int(event.get("n_steps_total", 0)),
                    n_steps_current_level=int(event.get("n_steps_current_level", 0)),
                    n_game_over_attempts_current_level=int(
                        event.get("n_game_over_attempts_current_level", 0)
                    ),
                    is_game_over=bool(event.get("is_game_over", False)),
                    is_solved=bool(event.get("is_solved", False)),
                    protocols=(),
                )
            )
            pending_index = len(summaries) - 1
            continue

        if message == "selected protocol" and pending_index is not None:
            pending = summaries[pending_index]
            protocol = event.get("protocol")
            if isinstance(protocol, str) and protocol:
                summaries[pending_index] = IterationSummary(
                    iteration_id=pending.iteration_id,
                    timestamp=pending.timestamp,
                    current_level_index=pending.current_level_index,
                    n_steps_total=pending.n_steps_total,
                    n_steps_current_level=pending.n_steps_current_level,
                    n_game_over_attempts_current_level=pending.n_game_over_attempts_current_level,
                    is_game_over=pending.is_game_over,
                    is_solved=pending.is_solved,
                    protocols=pending.protocols + (protocol,),
                )

    return summaries


def latest_session_dir(sessions_root: Path) -> Path:
    if not sessions_root.is_dir():
        raise FileNotFoundError(f"Sessions directory does not exist: {sessions_root}")

    has_attempts = any(
        path.is_dir() and ATTEMPT_DIR_RE.match(path.name)
        for path in sessions_root.iterdir()
    )
    if has_attempts:
        return sessions_root

    session_dirs = sorted(path for path in sessions_root.iterdir() if path.is_dir())
    if not session_dirs:
        raise FileNotFoundError(f"No session directories found in {sessions_root}")
    return session_dirs[-1]


def session_root_for_log(log_path: Path) -> Path:
    client_dir = log_path.parent / "agent_run" / "client"
    session_dir = client_dir / "session"
    if session_dir.is_dir():
        return session_dir
    return client_dir / "sessions"


def read_attempts_by_level(session_dir: Path) -> dict[int, list[AttemptInfo]]:
    attempts_by_level: dict[int, list[AttemptInfo]] = {}

    for path in sorted(p for p in session_dir.iterdir() if p.is_dir()):
        match = ATTEMPT_DIR_RE.match(path.name)
        if match is None:
            continue
        level_index = int(match.group(1))
        attempt_index = int(match.group(2))
        n_steps = sum(
            1
            for metadata_path in path.glob("step_*_metadata.json")
            if STEP_METADATA_RE.match(metadata_path.name)
        )
        attempts_by_level.setdefault(level_index, []).append(
            AttemptInfo(level_index=level_index, attempt_index=attempt_index, n_steps=n_steps)
        )

    for attempts in attempts_by_level.values():
        attempts.sort(key=lambda attempt: attempt.attempt_index)

    if not attempts_by_level:
        raise FileNotFoundError(f"No attempt directories found in {session_dir}")
    return attempts_by_level


def level_step_totals(attempts_by_level: dict[int, list[AttemptInfo]]) -> dict[int, int]:
    return {
        level_index: sum(attempt.n_steps for attempt in attempts)
        for level_index, attempts in attempts_by_level.items()
    }


def steps_before_level(level_index: int, totals_by_level: dict[int, int]) -> int:
    return sum(total for level, total in totals_by_level.items() if level < level_index)


def locate_iteration_position(
    summary: IterationSummary,
    attempts_by_level: dict[int, list[AttemptInfo]],
    totals_by_level: dict[int, int],
) -> tuple[int | None, int | None, int | None, int | None]:
    level_index = summary.current_level_index
    if level_index is None:
        return None, None, None, None

    attempts = attempts_by_level.get(level_index)
    if not attempts:
        raise ValueError(f"Level {level_index} from iteration {summary.iteration_id} is missing in session")

    prior_total = steps_before_level(level_index, totals_by_level)
    if prior_total + summary.n_steps_current_level != summary.n_steps_total:
        raise ValueError(
            f"Iteration {summary.iteration_id}: log/session mismatch for n_steps_total "
            f"(log={summary.n_steps_total}, session_prefix={prior_total + summary.n_steps_current_level})"
        )

    step_on_level = summary.n_steps_current_level
    total_steps_on_level = totals_by_level[level_index]
    if step_on_level > total_steps_on_level:
        raise ValueError(
            f"Iteration {summary.iteration_id}: n_steps_current_level={step_on_level} exceeds "
            f"session total {total_steps_on_level} for level {level_index}"
        )

    if step_on_level == 0:
        return 1, len(attempts), 0, attempts[0].n_steps

    completed_before_attempt = 0
    for attempt in attempts:
        next_completed = completed_before_attempt + attempt.n_steps
        if step_on_level <= next_completed:
            step_on_attempt = step_on_level - completed_before_attempt
            return attempt.attempt_index, len(attempts), step_on_attempt, attempt.n_steps
        completed_before_attempt = next_completed

    raise ValueError(
        f"Iteration {summary.iteration_id}: failed to locate level position for "
        f"n_steps_current_level={step_on_level}"
    )


def format_summary(summary: IterationSummary, attempts_by_level: dict[int, list[AttemptInfo]]) -> str:
    protocol = ",".join(summary.protocols) if summary.protocols else "-"

    if summary.current_level_index is None:
        return f"iteration={summary.iteration_id} level=? attempt=? step_a=? step_l=? protocol={protocol}"

    totals_by_level = level_step_totals(attempts_by_level)
    attempt_index, total_attempts, step_on_attempt, total_steps_on_attempt = locate_iteration_position(
        summary,
        attempts_by_level,
        totals_by_level,
    )
    total_steps_on_level = totals_by_level[summary.current_level_index]

    return (
        f"iteration={summary.iteration_id} "
        f"level={summary.current_level_index} "
        f"attempt={attempt_index}/{total_attempts} "
        f"step_a={step_on_attempt}/{total_steps_on_attempt} "
        f"step_l={summary.n_steps_current_level}/{total_steps_on_level} "
        f"protocol={protocol}"
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read an agent.log JSONL file and print a short per-iteration summary "
            "using the actual session data next to that log."
        )
    )
    parser.add_argument("log_path", type=Path, help="Path to agent.log")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    log_path = args.log_path.resolve()
    if not log_path.is_file():
        print(f"Log file does not exist: {log_path}", file=sys.stderr)
        return 1

    try:
        events = read_json_lines(log_path)
        summaries = summarize_iterations(events)
        attempts_by_level = read_attempts_by_level(latest_session_dir(session_root_for_log(log_path)))
        for summary in summaries:
            print(format_summary(summary, attempts_by_level))
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
