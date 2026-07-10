from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CLIENT_SESSION_DIR_RELATIVE_PATH = (
    Path("run") / "agent_run" / "client" / "session"
)
CLIENT_SESSION_RELATIVE_PATHS = (
    CLIENT_SESSION_DIR_RELATIVE_PATH / ".client_session.json",
    CLIENT_SESSION_DIR_RELATIVE_PATH / "client_state.json",
)
CLIENT_METADATA_RELATIVE_PATH = CLIENT_SESSION_DIR_RELATIVE_PATH
SERVER_LOG_RELATIVE_PATH = Path("server") / "server.log"
APPLIED_ACTION_RE = re.compile(
    r"\barc-server: applied action "
    r"session=(?P<session>\S+) "
    r"action=(?P<action>.*?) "
    r"step_index=(?P<step_index>\d+)\b"
)
ATTEMPT_DIR_RE = re.compile(r"^level_(?P<level>\d+)_attempt_(?P<attempt>\d+)$")
STEP_METADATA_RE = re.compile(r"^step_(?P<step>\d+)_metadata\.json$")


@dataclass(frozen=True)
class ServerAction:
    step_index: int
    action_id: str
    line_number: int
    action_input: dict[str, Any] | None = None


@dataclass(frozen=True)
class ClientAction:
    step_index: int
    action_input: dict[str, Any]
    metadata_path: Path

    @property
    def action_id(self) -> str:
        action_id = self.action_input.get("id")
        if not isinstance(action_id, str):
            raise ValueError(f"Missing action_input.id in {self.metadata_path}")
        return action_id


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def parse_server_action(
    action_text: str,
    server_log_path: Path,
    line_number: int,
) -> tuple[str, dict[str, Any] | None]:
    action_text = action_text.strip()
    if not action_text:
        raise ValueError(f"Missing action in {server_log_path}:{line_number}")

    if not action_text.startswith("{"):
        return action_text, None

    try:
        payload = json.loads(action_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid action JSON in {server_log_path}:{line_number}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(
            f"Expected action JSON object in {server_log_path}:{line_number}"
        )

    action_id = payload.get("id")
    if not isinstance(action_id, str) or not action_id:
        raise ValueError(
            f"Missing action id in action JSON at {server_log_path}:{line_number}"
        )

    if "data" in payload:
        data = payload["data"]
        if data is not None and not isinstance(data, dict):
            raise ValueError(
                f"Expected action data object/null at {server_log_path}:{line_number}"
            )

    return action_id, dict(payload)


def client_session_paths(game_dir: Path) -> list[Path]:
    return [game_dir / relative_path for relative_path in CLIENT_SESSION_RELATIVE_PATHS]


def read_session_token(game_dir: Path) -> str:
    session_paths = client_session_paths(game_dir)
    session_path = next((path for path in session_paths if path.is_file()), None)
    if session_path is None:
        candidates = ", ".join(str(path) for path in session_paths)
        raise FileNotFoundError(f"Missing client session file; tried: {candidates}")

    payload = read_json_object(session_path)
    for key in ("session_token", "session_tag"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value

    raise ValueError(f"Missing session_token/session_tag in {session_path}")


def read_server_actions_by_session(
    server_log_path: Path,
) -> dict[str, list[ServerAction]]:
    if not server_log_path.is_file():
        raise FileNotFoundError(f"Missing server log: {server_log_path}")

    actions_by_session: dict[str, list[ServerAction]] = {}
    with server_log_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            match = APPLIED_ACTION_RE.search(line)
            if match is None:
                continue

            action_id, action_input = parse_server_action(
                match.group("action"),
                server_log_path,
                line_number,
            )
            session = match.group("session")
            actions_by_session.setdefault(session, []).append(
                ServerAction(
                    step_index=int(match.group("step_index")),
                    action_id=action_id,
                    line_number=line_number,
                    action_input=action_input,
                )
            )

    for actions in actions_by_session.values():
        actions.sort(key=lambda action: (action.step_index, action.line_number))
    return actions_by_session


def verify_consecutive_server_steps(
    game_name: str,
    session_token: str,
    server_actions: list[ServerAction],
) -> list[str]:
    errors: list[str] = []
    seen_steps: dict[int, ServerAction] = {}
    for action in server_actions:
        existing = seen_steps.get(action.step_index)
        if existing is not None:
            errors.append(
                f"{game_name}: duplicate server step_index={action.step_index} "
                f"session={session_token} "
                f"lines={existing.line_number},{action.line_number}"
            )
        seen_steps[action.step_index] = action

    expected_steps = list(range(1, len(server_actions) + 1))
    actual_steps = [action.step_index for action in server_actions]
    if actual_steps != expected_steps:
        missing = sorted(set(expected_steps) - set(actual_steps))
        unexpected = sorted(set(actual_steps) - set(expected_steps))
        details = []
        if missing:
            details.append(f"missing={missing[:20]}")
        if unexpected:
            details.append(f"unexpected={unexpected[:20]}")
        details_text = f" ({'; '.join(details)})" if details else ""
        errors.append(
            f"{game_name}: server step_index sequence is not 1..{len(server_actions)} "
            f"session={session_token}{details_text}"
        )

    return errors


def attempt_sort_key(path: Path) -> tuple[int, int, str]:
    match = ATTEMPT_DIR_RE.match(path.name)
    if match is None:
        return (sys.maxsize, sys.maxsize, path.name)
    return (int(match.group("level")), int(match.group("attempt")), path.name)


def metadata_sort_key(path: Path) -> tuple[int, str]:
    if path.name == "initial_metadata.json":
        return (0, path.name)

    match = STEP_METADATA_RE.match(path.name)
    if match is not None:
        return (int(match.group("step")), path.name)

    return (sys.maxsize, path.name)


def iter_client_metadata_files(game_dir: Path) -> list[Path]:
    session_dir = game_dir / CLIENT_METADATA_RELATIVE_PATH
    if not session_dir.is_dir():
        raise FileNotFoundError(f"Missing client session directory: {session_dir}")

    metadata_files: list[Path] = []
    attempt_dirs = sorted(
        (
            path
            for path in session_dir.iterdir()
            if path.is_dir() and ATTEMPT_DIR_RE.match(path.name)
        ),
        key=attempt_sort_key,
    )
    for attempt_dir in attempt_dirs:
        metadata_files.extend(
            sorted(attempt_dir.glob("*_metadata.json"), key=metadata_sort_key)
        )

    return metadata_files


def client_action_from_metadata(path: Path) -> ClientAction | None:
    payload = read_json_object(path)
    if "step_index" not in payload:
        raise ValueError(f"Missing step_index in {path}")

    step_index = int(payload["step_index"])
    if step_index <= 0:
        return None

    action_input = payload.get("action_input")
    if not isinstance(action_input, dict):
        raise ValueError(f"Missing action_input object in {path}")

    action_id = action_input.get("id")
    if not isinstance(action_id, str) or not action_id:
        raise ValueError(f"Missing action_input.id in {path}")

    return ClientAction(step_index, action_input, path)


def read_client_actions(game_dir: Path) -> list[ClientAction]:
    actions_by_step: dict[int, ClientAction] = {}
    for metadata_path in iter_client_metadata_files(game_dir):
        action = client_action_from_metadata(metadata_path)
        if action is None:
            continue

        existing = actions_by_step.get(action.step_index)
        if existing is None:
            actions_by_step[action.step_index] = action
            continue

        if existing.action_input != action.action_input:
            raise ValueError(
                f"Conflicting action_input for step_index={action.step_index}: "
                f"{existing.action_input!r} in {existing.metadata_path}, "
                f"{action.action_input!r} in {action.metadata_path}"
            )

    return [actions_by_step[step_index] for step_index in sorted(actions_by_step)]


def first_action_mismatch(
    server_actions: list[ServerAction],
    client_actions: list[ClientAction],
) -> str | None:
    for index, (server_action, client_action) in enumerate(
        zip(server_actions, client_actions),
        start=1,
    ):
        if server_action.action_id != client_action.action_id:
            return (
                f"action mismatch at position={index} step_index={server_action.step_index}: "
                f"server={server_action.action_id} client={client_action.action_id} "
                f"server_log_line={server_action.line_number} "
                f"client_metadata={client_action.metadata_path}"
            )
    return None


def server_action6_has_data_field(action: ServerAction) -> bool:
    return (
        action.action_id == "ACTION6"
        and action.action_input is not None
        and "data" in action.action_input
    )


def server_actions_have_all_action6_data(server_actions: list[ServerAction]) -> bool:
    return all(
        action.action_id != "ACTION6" or server_action6_has_data_field(action)
        for action in server_actions
    )


def build_output_actions(
    server_actions: list[ServerAction],
    client_actions: list[ClientAction] | None,
) -> list[Any]:
    if client_actions is None:
        output_actions: list[Any] = []
        for action in server_actions:
            if server_action6_has_data_field(action):
                output_actions.append(action.action_input)
            else:
                output_actions.append(action.action_id)
        return output_actions

    return [action.action_input for action in client_actions]


def output_action_id(action: Any) -> str | None:
    if isinstance(action, str):
        return action
    if isinstance(action, dict):
        action_id = action.get("id")
        if isinstance(action_id, str):
            return action_id
    return None


def truncate_after_consecutive_reset(
    game_name: str,
    actions: list[Any],
) -> list[Any]:
    previous_action_id: str | None = None
    for index, action in enumerate(actions, start=1):
        action_id = output_action_id(action)
        if previous_action_id == "RESET" and action_id == "RESET":
            print(
                f"{game_name}: WARNING: consecutive RESET at actions "
                f"{index - 1},{index}; dropping action {index} and all later actions",
                file=sys.stderr,
            )
            return actions[: index - 1]
        previous_action_id = action_id
    return actions


def game_folders(runs_dir: Path) -> list[Path]:
    folders: list[Path] = []
    for path in runs_dir.iterdir():
        if not path.is_dir() or path.name.startswith(".") or path.name == "__pycache__":
            continue
        if any(session_path.is_file() for session_path in client_session_paths(path)):
            folders.append(path)
    return sorted(folders)


def process_game(
    game_dir: Path,
    runs_dir: Path,
    server_actions_by_session: dict[str, list[ServerAction]],
) -> tuple[Path | None, list[str], int]:
    session_token = read_session_token(game_dir)
    server_actions = server_actions_by_session.get(session_token, [])
    if not server_actions:
        return None, [f"{game_dir.name}: no server actions for session={session_token}"], 0

    errors = verify_consecutive_server_steps(
        game_dir.name,
        session_token,
        server_actions,
    )
    if errors:
        return None, errors, len(server_actions)

    client_actions: list[ClientAction] | None = None
    has_action6 = any(action.action_id == "ACTION6" for action in server_actions)
    if has_action6 and not server_actions_have_all_action6_data(server_actions):
        missing_data_count = sum(
            1
            for action in server_actions
            if action.action_id == "ACTION6" and not server_action6_has_data_field(action)
        )
        print(
            f"{game_dir.name}: WARNING: reading client metadata for ACTION6 data "
            f"because server log lacks ACTION6 data for {missing_data_count} "
            f"action(s) session={session_token}",
            file=sys.stderr,
        )
        client_actions = read_client_actions(game_dir)
        if len(client_actions) != len(server_actions):
            return (
                None,
                [
                    f"{game_dir.name}: action count mismatch "
                    f"server={len(server_actions)} client={len(client_actions)} "
                    f"session={session_token}"
                ],
                len(server_actions),
            )

        mismatch = first_action_mismatch(server_actions, client_actions)
        if mismatch is not None:
            return None, [f"{game_dir.name}: {mismatch}"], len(server_actions)

    output_actions = truncate_after_consecutive_reset(
        game_dir.name,
        build_output_actions(server_actions, client_actions),
    )
    output_path = runs_dir / f"{game_dir.name}_actions.json"
    output_path.write_text(
        json.dumps(output_actions, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path, [], len(output_actions)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Extract per-game action lists from server/server.log. ACTION6 data "
            "is read from server JSON when available, with client metadata fallback."
        )
    )
    parser.add_argument("runs_dir", type=Path, help="Folder containing one subfolder per game")
    args = parser.parse_args()

    runs_dir = args.runs_dir.resolve()
    if not runs_dir.is_dir():
        print(f"Runs folder does not exist: {runs_dir}", file=sys.stderr)
        return 1

    try:
        server_actions_by_session = read_server_actions_by_session(
            runs_dir / SERVER_LOG_RELATIVE_PATH
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    games = game_folders(runs_dir)
    if not games:
        print(f"No game folders found in {runs_dir}", file=sys.stderr)
        return 1

    failed = False
    for game_dir in games:
        try:
            output_path, errors, action_count = process_game(
                game_dir,
                runs_dir,
                server_actions_by_session,
            )
        except (FileNotFoundError, OSError, ValueError) as exc:
            failed = True
            print(f"{game_dir.name}: ERROR: {exc}", file=sys.stderr)
            continue

        if errors:
            failed = True
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            continue

        print(f"{game_dir.name}: wrote {output_path.name} actions={action_count}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
