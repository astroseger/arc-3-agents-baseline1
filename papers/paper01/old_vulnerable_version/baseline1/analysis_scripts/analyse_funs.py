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

SESSION_NAME_RE = re.compile(r"^\d+_(?P<name>.+)$")
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


@dataclass(frozen=True)
class RecordedAction:
    step_index: int
    action_id: str
    action_input: dict[str, Any]
    metadata_path: Path


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def parse_run_folder_name(folder_name: str) -> RunFolder:
    if len(folder_name) == 4:
        return RunFolder(folder_name=folder_name, game_id=folder_name.casefold(), run_id=None)
    if len(folder_name) > 5 and folder_name[4] == "_":
        return RunFolder(
            folder_name=folder_name,
            game_id=folder_name[:4].casefold(),
            run_id=folder_name[5:],
        )
    raise ValueError(
        f"Run folder name must be '<game>' or '<game>_<run_id>' with a 4-character game id: "
        f"{folder_name}"
    )


def run_folder_game_id(folder_name: str) -> str | None:
    try:
        return parse_run_folder_name(folder_name).game_id
    except ValueError:
        return None


def game_id_from_agent_log(folder: Path) -> str | None:
    for log_path in (folder / "run" / "agent.log", folder / "agent.log"):
        if not log_path.is_file():
            continue
        with log_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or not line.startswith("{"):
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                game_name = event.get("game_name")
                if isinstance(game_name, str) and game_name:
                    return game_name
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
    if (path / "client_state.json").is_file():
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


def session_game_name(session_dir: Path) -> str:
    match = SESSION_NAME_RE.match(session_dir.name)
    if match is None:
        raise ValueError(
            f"Session directory name does not match '<index>_<game>': {session_dir.name}"
        )
    return match.group("name")


def only_session_dir(sessions_dir: Path) -> Path:
    session_dirs = sorted(path for path in sessions_dir.iterdir() if path.is_dir())
    if len(session_dirs) != 1:
        names = ", ".join(path.name for path in session_dirs) or "<none>"
        raise ValueError(
            f"Expected exactly one session in {sessions_dir}, found {len(session_dirs)}: {names}"
        )
    return session_dirs[0]


def requested_game_id_from_state(state_dir: Path) -> str | None:
    state_path = state_dir / "client_state.json"
    if not state_path.is_file():
        return None
    state = read_json(state_path)
    requested_game_id = state.get("requested_game_id")
    if isinstance(requested_game_id, str) and requested_game_id:
        return requested_game_id
    return None


def game_id_for(folder: Path, location: SessionLocation) -> str:
    candidates: list[tuple[str, str]] = []

    folder_game_id = run_folder_game_id(folder.name)
    if folder_game_id is not None:
        candidates.append(("folder", folder_game_id))

    if not location.direct_session:
        candidates.append(("session", session_game_name(location.session_dir)))

    requested_game_id = requested_game_id_from_state(location.state_dir)
    if requested_game_id is not None:
        candidates.append(("client_state", requested_game_id))

    log_game_id = game_id_from_agent_log(folder)
    if log_game_id is not None:
        candidates.append(("agent.log", log_game_id))

    if not candidates:
        raise ValueError(
            "Could not determine game id from folder name, session name, "
            f"client_state.json, or agent.log for {folder}"
        )

    game_id = candidates[0][1].casefold()
    conflicts = [
        f"{source}={candidate!r}"
        for source, candidate in candidates
        if candidate.casefold() != game_id
    ]
    if conflicts:
        raise ValueError(
            "Conflicting game ids for "
            f"{folder.name}: {', '.join(f'{source}={candidate!r}' for source, candidate in candidates)}"
        )
    return game_id


def attempt_sort_key(path: Path) -> tuple[int, int, str]:
    match = ATTEMPT_DIR_RE.match(path.name)
    if match is None:
        return (sys.maxsize, sys.maxsize, path.name)
    return (int(match.group("level")), int(match.group("attempt")), path.name)


def iter_metadata_files(session_dir: Path) -> list[Path]:
    metadata_files: list[Path] = []
    for attempt_dir in sorted(
        (path for path in session_dir.iterdir() if path.is_dir()),
        key=attempt_sort_key,
    ):
        initial_metadata = attempt_dir / "initial_metadata.json"
        if initial_metadata.is_file():
            metadata_files.append(initial_metadata)
        metadata_files.extend(sorted(attempt_dir.glob("step_*_metadata.json")))
    return metadata_files


def action_from_metadata(path: Path) -> RecordedAction | None:
    metadata = read_json(path)
    if "step_index" not in metadata:
        raise ValueError(f"Missing step_index in {path}")

    step_index = int(metadata["step_index"])
    if step_index <= 0:
        return None

    action_input = metadata.get("action_input")
    if not isinstance(action_input, dict):
        raise ValueError(f"Missing action_input object in {path}")

    action_id = action_input.get("id")
    if not isinstance(action_id, str) or not action_id:
        raise ValueError(f"Missing action_input.id in {path}")

    return RecordedAction(step_index, action_id, action_input, path)


def read_actions(session_dir: Path) -> list[RecordedAction]:
    actions_by_step: dict[int, RecordedAction] = {}
    for metadata_path in iter_metadata_files(session_dir):
        action = action_from_metadata(metadata_path)
        if action is None:
            continue

        existing = actions_by_step.get(action.step_index)
        if existing is None:
            actions_by_step[action.step_index] = action
        elif existing.action_input != action.action_input:
            raise ValueError(
                f"Conflicting actions for step_index={action.step_index}: "
                f"{existing.action_input!r} in {existing.metadata_path}, "
                f"{action.action_input!r} in {action.metadata_path}"
            )

    return [actions_by_step[step_index] for step_index in sorted(actions_by_step)]


def replay_actions(game_id: str, actions: list[RecordedAction]) -> Any:
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

    for action in actions:
        try:
            game_action = getattr(GameAction, action.action_id)
        except AttributeError as exc:
            raise ValueError(
                f"Unknown GameAction {action.action_id!r} from {action.metadata_path}"
            ) from exc

        data = action.action_input.get("data")
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


def score_game_folder(game_dir: Path) -> tuple[list[RecordedAction], Any]:
    location = session_location_for(game_dir)
    game_id = game_id_for(game_dir, location)
    actions = read_actions(location.session_dir)
    return actions, replay_actions(game_id, actions)


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
    _, scorecard = score_game_folder(game_dir)
    output_path = runs_dir / f"{game_dir.name}_scorecard.json"
    output_path.write_text(
        json.dumps(scorecard_to_jsonable(scorecard), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_cost_estimation(runs_dir: Path, games: list[Path]) -> Path:
    per_game: dict[str, dict[str, Any]] = {}
    for game_dir in games:
        log_candidates = (game_dir / "run" / "agent.log", game_dir / "agent.log")
        log_path = next((path for path in log_candidates if path.is_file()), log_candidates[0])
        if log_path.is_file():
            summary = usage_summary(log_path)
            summary.pop("log_path", None)
            per_game[game_dir.name] = summary
        else:
            per_game[game_dir.name] = {"error": f"Log file does not exist: {log_path}"}

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
    payload = {
        "pricing_usd_per_1m_tokens": {
            "input": PRICE_INPUT_PER_1M,
            "cached_input": PRICE_CACHED_PER_1M,
            "output": PRICE_OUTPUT_PER_1M,
        },
        "games": per_game,
        "totals": totals,
    }

    output_path = runs_dir / "cost_estimation.json"
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path
