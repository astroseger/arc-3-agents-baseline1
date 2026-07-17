from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# GPT-5.5
PRICE_INPUT_PER_1M = 5
PRICE_CACHED_PER_1M = 0.5
PRICE_OUTPUT_PER_1M = 30.00

ATTEMPT_DIR_RE = re.compile(r"^level_(?P<level>\d+)_attempt_(?P<attempt>\d+)$")


@dataclass
class ThreadUsage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class RunFolder:
    folder_name: str
    game_id: str
    run_id: str | None


@dataclass(frozen=True)
class SessionLocation:
    state_dir: Path
    session_dir: Path
    direct_session: bool


def parse_run_folder_name(folder_name: str) -> RunFolder:
    if len(folder_name) >= 4:
        run_id = (
            folder_name[5:]
            if len(folder_name) > 5 and folder_name[4] == "_"
            else None
        )
        return RunFolder(
            folder_name=folder_name,
            game_id=folder_name[:4].casefold(),
            run_id=run_id,
        )
    raise ValueError(
        f"Run folder name must start with a 4-character game id: {folder_name}"
    )


def run_folder_game_id(folder_name: str) -> str | None:
    try:
        return parse_run_folder_name(folder_name).game_id
    except ValueError:
        return None


def cost_breakdown(
    input_tokens: int, cached_input_tokens: int, output_tokens: int
) -> tuple[float, float, float]:
    non_cached_input_tokens = max(input_tokens - cached_input_tokens, 0)
    input_cost = (non_cached_input_tokens / 1_000_000) * PRICE_INPUT_PER_1M
    cached_cost = (cached_input_tokens / 1_000_000) * PRICE_CACHED_PER_1M
    output_cost = (output_tokens / 1_000_000) * PRICE_OUTPUT_PER_1M
    return input_cost, cached_cost, output_cost


def parse_log(log_path: Path) -> dict[str, ThreadUsage]:
    thread_usage: dict[str, ThreadUsage] = {}
    current_thread_id: str | None = None

    with log_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or not line.startswith("{"):
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                print(
                    f"Warning: skipping malformed JSON object on line {line_number}",
                    file=sys.stderr,
                )
                continue

            event_type = event.get("type")
            if event_type == "thread.started":
                thread_id = event.get("thread_id")
                if not thread_id:
                    print(
                        f"Warning: thread.started without thread_id on line {line_number}",
                        file=sys.stderr,
                    )
                    current_thread_id = None
                    continue
                thread_usage.setdefault(thread_id, ThreadUsage())
                current_thread_id = thread_id
                continue

            if event_type != "turn.completed":
                continue
            if current_thread_id is None:
                print(
                    f"Warning: turn.completed without active thread on line {line_number}",
                    file=sys.stderr,
                )
                continue

            usage_payload = event.get("usage", {})
            usage = thread_usage.setdefault(current_thread_id, ThreadUsage())
            usage.input_tokens = int(usage_payload.get("input_tokens", 0))
            usage.cached_input_tokens = int(usage_payload.get("cached_input_tokens", 0))
            usage.output_tokens = int(usage_payload.get("output_tokens", 0))

    return thread_usage


def usage_summary(log_path: Path) -> dict[str, Any]:
    thread_usage = parse_log(log_path)
    input_tokens = sum(usage.input_tokens for usage in thread_usage.values())
    cached_input_tokens = sum(usage.cached_input_tokens for usage in thread_usage.values())
    output_tokens = sum(usage.output_tokens for usage in thread_usage.values())
    input_cost, cached_input_cost, output_cost = cost_breakdown(
        input_tokens,
        cached_input_tokens,
        output_tokens,
    )
    return {
        "log_path": str(log_path),
        "threads": len(thread_usage),
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "input_cost_usd": input_cost,
        "cached_input_cost_usd": cached_input_cost,
        "output_cost_usd": output_cost,
        "estimated_cost_usd": input_cost + cached_input_cost + output_cost,
    }


def _looks_like_direct_session(path: Path) -> bool:
    if not path.is_dir():
        return False
    if path.name == "sessions":
        return False
    if (path / ".client_session.json").is_file():
        return True
    return any(
        child.is_dir() and ATTEMPT_DIR_RE.match(child.name) is not None
        for child in path.iterdir()
    )


def session_location_for(folder: Path) -> SessionLocation:
    direct_candidates = [
        folder,
        folder / "session",
        folder / "client" / "session",
        folder / "run" / "agent_run" / "client" / "session",
    ]
    for candidate in direct_candidates:
        if _looks_like_direct_session(candidate):
            return SessionLocation(
                state_dir=candidate,
                session_dir=candidate,
                direct_session=True,
            )

    plural_candidates = [
        folder,
        folder / "client" / "sessions",
        folder / "run" / "agent_run" / "client" / "sessions",
    ]
    for candidate in plural_candidates:
        if candidate.name == "sessions" and candidate.is_dir():
            return SessionLocation(
                state_dir=candidate,
                session_dir=only_session_dir(candidate),
                direct_session=False,
            )
    raise FileNotFoundError(f"Could not find a client session directory under {folder}")


def only_session_dir(sessions_dir: Path) -> Path:
    session_dirs = sorted(path for path in sessions_dir.iterdir() if path.is_dir())
    if len(session_dirs) != 1:
        names = ", ".join(path.name for path in session_dirs) or "<none>"
        raise ValueError(
            f"Expected exactly one session in {sessions_dir}, found {len(session_dirs)}: {names}"
        )
    return session_dirs[0]


def game_id_for(folder: Path, _location: SessionLocation) -> str:
    folder_game_id = run_folder_game_id(folder.name)
    if folder_game_id is None:
        raise ValueError(
            f"Could not determine game id from the first 4 characters of folder name: {folder}"
        )
    return folder_game_id



def read_actions_file(action_path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(action_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {action_path}: {exc}") from exc

    if not isinstance(payload, list):
        raise ValueError(f"Expected JSON list in {action_path}")

    actions: list[dict[str, Any]] = []
    for index, item in enumerate(payload, start=1):
        if isinstance(item, str):
            if not item:
                raise ValueError(f"Empty action id at {action_path}[{index}]")
            actions.append({"id": item, "data": {}})
            continue

        if not isinstance(item, dict):
            raise ValueError(
                f"Expected action string or object at {action_path}[{index}], "
                f"got {type(item).__name__}"
            )

        action_id = item.get("id")
        if not isinstance(action_id, str) or not action_id:
            raise ValueError(f"Missing action id at {action_path}[{index}]")

        data = item.get("data", {})
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ValueError(f"Expected action data object at {action_path}[{index}]")

        action_input = dict(item)
        action_input["data"] = data
        actions.append(action_input)

    return actions


def replay_actions(
    game_id: str,
    actions: list[dict[str, Any]],
    action_path: Path | None = None,
) -> Any:
    try:
        import arc_agi
        from arcengine import GameAction
    except ImportError as exc:
        raise RuntimeError(
            "Could not import arc_agi/arcengine. Run this script in an environment "
            "where the ARC engine packages are installed."
        ) from exc

    arc = arc_agi.Arcade()
    env = arc.make(game_id, render_mode=None)
    if env is None:
        raise RuntimeError(f"Could not create environment for game {game_id!r}")

    source = f" from {action_path}" if action_path is not None else ""
    for index, action in enumerate(actions, start=1):
        action_id = action["id"]
        try:
            game_action = getattr(GameAction, action_id)
        except AttributeError as exc:
            raise ValueError(
                f"Unknown GameAction {action_id!r} at action {index}{source}"
            ) from exc

        data = action.get("data", {})
        if isinstance(data, dict) and data:
            env.step(game_action, data=data)
        else:
            env.step(game_action)

    return arc.get_scorecard()

def scorecard_to_jsonable(scorecard: Any) -> dict[str, Any]:
    if scorecard is None:
        return {"scorecard": None}
    if hasattr(scorecard, "model_dump"):
        return scorecard.model_dump(mode="json")
    return json.loads(json.dumps(scorecard, default=str))



def game_folders(runs_dir: Path) -> list[Path]:
    folders: list[Path] = []
    for path in runs_dir.iterdir():
        if not path.is_dir() or path.name.startswith(".") or path.name == "__pycache__":
            continue
        try:
            session_location_for(path)
        except (FileNotFoundError, OSError):
            continue
        folders.append(path)
    return sorted(folders)


def write_scorecard(game_dir: Path, runs_dir: Path) -> Path:
    location = session_location_for(game_dir)
    game_id = game_id_for(game_dir, location)
    action_path = runs_dir / f"{game_dir.name}_actions.json"
    if not action_path.is_file():
        raise FileNotFoundError(f"Missing extracted actions file: {action_path}")

    actions = read_actions_file(action_path)
    scorecard = replay_actions(game_id, actions, action_path)
    output_path = runs_dir / f"{game_dir.name}_scorecard.json"
    output_path.write_text(
        json.dumps(scorecard_to_jsonable(scorecard), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def cost_estimation_payload(per_game: dict[str, dict[str, Any]]) -> dict[str, Any]:
    totals = {
        "games": len(per_game),
        "threads": sum(item.get("threads", 0) for item in per_game.values()),
        "input_tokens": sum(item.get("input_tokens", 0) for item in per_game.values()),
        "cached_input_tokens": sum(item.get("cached_input_tokens", 0) for item in per_game.values()),
        "output_tokens": sum(item.get("output_tokens", 0) for item in per_game.values()),
        "input_cost_usd": sum(item.get("input_cost_usd", 0.0) for item in per_game.values()),
        "cached_input_cost_usd": sum(
            item.get("cached_input_cost_usd", 0.0) for item in per_game.values()
        ),
        "output_cost_usd": sum(item.get("output_cost_usd", 0.0) for item in per_game.values()),
        "estimated_cost_usd": sum(
            item.get("estimated_cost_usd", 0.0) for item in per_game.values()
        ),
    }
    return {
        "pricing_usd_per_1m_tokens": {
            "input": PRICE_INPUT_PER_1M,
            "cached_input": PRICE_CACHED_PER_1M,
            "output": PRICE_OUTPUT_PER_1M,
        },
        "games": per_game,
        "totals": totals,
    }


def write_cost_estimations(runs_dir: Path, games: list[Path]) -> list[Path]:
    output_paths: list[Path] = []
    for game_dir in games:
        log_candidates = (game_dir / "run" / "agent.log", game_dir / "agent.log")
        log_path = next((path for path in log_candidates if path.is_file()), log_candidates[0])
        if log_path.is_file():
            summary = usage_summary(log_path)
            summary.pop("log_path", None)
        else:
            summary = {"error": f"Log file does not exist: {log_path}"}

        payload = cost_estimation_payload({game_dir.name: summary})
        output_path = runs_dir / f"{game_dir.name}_cost_estimation.json"
        output_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        output_paths.append(output_path)
    return output_paths
