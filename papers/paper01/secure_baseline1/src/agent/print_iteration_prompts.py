from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


def parse_iteration_prompts(lines: Iterable[str]) -> list[tuple[int, list[str]]]:
    prompts_by_iteration: dict[int, list[str]] = {}
    iteration_order: list[int] = []
    current_iteration = 0

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("type") != "external_agent_log":
            continue

        if record.get("message") == "iteration inspection":
            iteration_id = int(record["iteration_id"])
            current_iteration = iteration_id
            if iteration_id not in prompts_by_iteration:
                prompts_by_iteration[iteration_id] = []
                iteration_order.append(iteration_id)
            continue

        if record.get("message") != "prompt body":
            continue

        prompt = record.get("prompt")
        if not isinstance(prompt, str):
            continue

        if current_iteration not in prompts_by_iteration:
            prompts_by_iteration[current_iteration] = []
            iteration_order.append(current_iteration)
        prompts_by_iteration[current_iteration].append(prompt)

    return [(iteration_id, prompts_by_iteration[iteration_id]) for iteration_id in iteration_order]


def render_iteration_prompts(groups: list[tuple[int, list[str]]]) -> str:
    chunks: list[str] = []
    for iteration_id, prompts in groups:
        chunks.append("========================")
        chunks.append(f"iteration {iteration_id}")
        for prompt in prompts:
            chunks.append("------------------------")
            chunks.append(prompt)
    if chunks:
        chunks.append("========================")
    return "\n".join(chunks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read agent.log and print prompts grouped by iteration.",
    )
    parser.add_argument(
        "--log-file",
        default="agent.log",
        help="Path to the JSONL agent log file. Defaults to ./agent.log",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    log_path = Path(args.log_file)
    groups = parse_iteration_prompts(log_path.read_text(encoding="utf-8").splitlines())
    output = render_iteration_prompts(groups)
    if output:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
