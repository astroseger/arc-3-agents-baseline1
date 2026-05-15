from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from analyse_funs import (
    PRICE_CACHED_PER_1M,
    PRICE_INPUT_PER_1M,
    PRICE_OUTPUT_PER_1M,
    usage_summary,
)


def money(value: float) -> str:
    return f"${value:.4f}"


def int_with_commas(value: Any) -> str:
    return f"{int(value):,}"


def format_summary(summary: dict[str, Any]) -> str:
    pricing = (
        f"pricing: input=${PRICE_INPUT_PER_1M:g}/1M, "
        f"cached_input=${PRICE_CACHED_PER_1M:g}/1M, "
        f"output=${PRICE_OUTPUT_PER_1M:g}/1M"
    )
    return "\n".join(
        [
            f"log_path: {summary['log_path']}",
            f"threads: {int_with_commas(summary['threads'])}",
            f"input_tokens: {int_with_commas(summary['input_tokens'])}",
            f"cached_input_tokens: {int_with_commas(summary['cached_input_tokens'])}",
            f"output_tokens: {int_with_commas(summary['output_tokens'])}",
            f"input_cost_usd: {money(summary['input_cost_usd'])}",
            f"cached_input_cost_usd: {money(summary['cached_input_cost_usd'])}",
            f"output_cost_usd: {money(summary['output_cost_usd'])}",
            f"estimated_cost_usd: {money(summary['estimated_cost_usd'])}",
            pricing,
        ]
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Estimate token cost from an agent.log JSONL file."
    )
    parser.add_argument("log_path", type=Path, help="Path to agent.log")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the raw usage summary as JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    log_path = args.log_path.resolve()
    if not log_path.is_file():
        print(f"Log file does not exist: {log_path}", file=sys.stderr)
        return 1

    try:
        summary = usage_summary(log_path)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(format_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
