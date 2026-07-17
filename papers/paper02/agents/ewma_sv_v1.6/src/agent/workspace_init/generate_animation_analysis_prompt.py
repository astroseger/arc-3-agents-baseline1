from __future__ import annotations

import argparse
from pathlib import Path

from game_status import LEVEL_COMPLETED
from session_tools import _latest_session_dir, read_all_attempts_for_level


def _attempt_for_level(level: int, attempt_index: int, session_dir: Path) -> dict:
    attempts = read_all_attempts_for_level(level, session_dir)
    for attempt in attempts:
        if attempt["attempt_index"] == attempt_index:
            return attempt
    raise ValueError(f"Level {level} attempt {attempt_index} was not found in {session_dir}.")


def _step_for_attempt(attempt: dict, step_index: int) -> dict:
    steps = attempt["steps"]
    if step_index < 1 or step_index > len(steps):
        raise ValueError(
            f"Step {step_index} is out of range for {attempt['path']} (available: 1..{len(steps)})."
        )
    return steps[step_index - 1]


def _previous_final_paths(attempt: dict, step_index: int, count: int) -> list[str]:
    start = max(0, step_index - 1 - count)
    end = step_index - 1
    return [attempt["steps"][idx]["final_frame_png_filename"] for idx in range(start, end)]


def build_prompt(
    *,
    session_dir: Path,
    level: int,
    attempt_index: int,
    step_index: int,
    previous_count: int,
) -> str:
    attempt = _attempt_for_level(level, attempt_index, session_dir)
    step = _step_for_attempt(attempt, step_index)
    previous_paths = _previous_final_paths(attempt, step_index, previous_count)
    frame_paths = list(step["intermediate_frame_png_filenames"])
    if step["observed_status"] != LEVEL_COMPLETED:
        frame_paths.append(step["final_frame_png_filename"])

    lines = [
        "Please analyze the following short frame sequence from the game.",
        "",
        "Goal: infer what is happening in the game during this transition and what the animation is likely communicating.",
        "Assume this may be a visual puzzle, so subtle visual cues may matter.",
        "",
        "Be concise.",
        "Tell me:",
        "1. What is visibly happening frame-to-frame.",
        "2. What event this animation most likely indicates in gameplay terms.",
        "3. Your general interpretation of what the game is trying to communicate to the player.",
        "",
        "Prefer checking the frames by eye rather than reasoning only from filenames.",
        "",
        f"Session: {session_dir}",
        f"Level: {level}",
        f"Attempt: {attempt_index}",
        f"Step: {step_index}",
        f"Attempt path: {attempt['path']}",
        "",
        "Current transition frames:",
    ]
    lines.extend(frame_paths)
    if previous_paths:
        lines.extend(["", f"Previous settled frames for reference ({len(previous_paths)}):"])
        lines.extend(previous_paths)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", type=int, required=True)
    parser.add_argument("--attempt", type=int, required=True)
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--previous-count", type=int, default=2)
    parser.add_argument("--session-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    session_dir = args.session_dir.resolve() if args.session_dir is not None else _latest_session_dir()
    prompt = build_prompt(
        session_dir=session_dir,
        level=args.level,
        attempt_index=args.attempt,
        step_index=args.step,
        previous_count=args.previous_count,
    )
    if args.output is not None:
        args.output.write_text(prompt + "\n", encoding="utf-8")
    else:
        print(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
