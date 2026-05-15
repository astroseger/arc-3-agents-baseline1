from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import signal
from typing import Any

import numpy as np
from PIL import Image
import requests

CLIENT_ROOT = Path(os.environ.get("ARC_CLIENT_ROOT", Path(__file__).resolve().parent))
SESSION_DIR = CLIENT_ROOT / "session"
CLIENT_STATE_PATH = SESSION_DIR / "client_state.json"
CLIENT_LOCK_PATH = CLIENT_ROOT / ".client.lock"
SERVER_URL = os.environ.get("ARC_SERVER_URL", "http://127.0.0.1:8879")

CLIENT_STATE_KEYS = {
    "current_level",
    "current_attempt",
    "current_attempt_step",
    "session_token",
    "server_url",
}

COLOR_MAP: dict[int, str] = {
    0: "#FFFFFFFF",
    1: "#CCCCCCFF",
    2: "#999999FF",
    3: "#666666FF",
    4: "#333333FF",
    5: "#000000FF",
    6: "#E53AA3FF",
    7: "#FF7BCCFF",
    8: "#F93C31FF",
    9: "#1E93FFFF",
    10: "#88D8F1FF",
    11: "#FFDC00FF",
    12: "#FF851BFF",
    13: "#921231FF",
    14: "#4FCC30FF",
    15: "#A356D6FF",
}

OFFICIAL_ACTIONS = {"RESET", "ACTION1", "ACTION2", "ACTION3", "ACTION4", "ACTION5", "ACTION6", "ACTION7"}

ACTION_SEMANTICS = {
    1: "usual semantics: up",
    2: "usual semantics: down",
    3: "usual semantics: left",
    4: "usual semantics: right",
    5: "usual semantics: primary interaction",
    6: "usual semantics: coordinate action",
    7: "usual semantics: undo",
}
DEFAULT_PNG_SCALE = 8


def ignore_interrupt_and_term_signals() -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))


def frame_to_rgb_array(frame: np.ndarray, scale: int = DEFAULT_PNG_SCALE) -> np.ndarray:
    height, width = frame.shape
    rgb_array = np.zeros((height * scale, width * scale, 3), dtype=np.uint8)
    for y in range(height):
        for x in range(width):
            rgb = hex_to_rgb(COLOR_MAP.get(int(frame[y, x]), "#000000FF"))
            for dy in range(scale):
                for dx in range(scale):
                    rgb_array[y * scale + dy, x * scale + dx] = rgb
    return rgb_array


def frame_to_ascii(frame: np.ndarray) -> str:
    return "\n".join("".join(format(int(value), "X") for value in row) for row in frame) + "\n"


def compact_frame_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    frame_payload = json.loads(json.dumps(payload["frame"]))
    frame_payload.pop("frame", None)
    frame_payload.pop("game_id", None)
    frame_payload.pop("guid", None)
    frame_payload.pop("full_reset", None)
    action_input = frame_payload.get("action_input")
    if isinstance(action_input, dict):
        action_input.pop("reasoning", None)
    return frame_payload


def current_level_from_frame(frame_payload: dict[str, Any]) -> int:
    completed = int(frame_payload["levels_completed"])
    win_levels = int(frame_payload.get("win_levels") or 0)
    if win_levels:
        return min(completed + 1, win_levels)
    return completed + 1


def attempt_dir(level_id: int, attempt_id: int) -> Path:
    return SESSION_DIR / f"level_{level_id:02d}_attempt_{attempt_id:02d}"


def metadata_path_for_state(state: dict[str, Any]) -> Path:
    current_attempt_step = int(state["current_attempt_step"])
    directory = attempt_dir(int(state["current_level"]), int(state["current_attempt"]))
    if current_attempt_step == 0:
        return directory / "initial_metadata.json"
    return directory / f"step_{current_attempt_step:04d}_metadata.json"


def save_initial_artifacts(attempt_dir: Path, payload: dict[str, Any]) -> list[Path]:
    attempt_dir.mkdir(parents=True, exist_ok=True)
    metadata = compact_frame_metadata(payload)
    created_paths: list[Path] = []

    metadata_path = attempt_dir / "initial_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    created_paths.append(metadata_path)

    frames = payload["frame"].get("frame", [])
    if not frames:
        return created_paths
    array = np.array(frames[-1], dtype=np.int16)
    rgb = frame_to_rgb_array(array)
    png_path = attempt_dir / "initial_frame.png"
    txt_path = attempt_dir / "initial_frame.txt"
    Image.fromarray(rgb, mode="RGB").save(png_path)
    txt_path.write_text(frame_to_ascii(array), encoding="utf-8")
    created_paths.extend([png_path, txt_path])
    return created_paths


def save_step_artifacts(attempt_dir: Path, payload: dict[str, Any], attempt_step_index: int) -> list[Path]:
    step_index = attempt_step_index
    attempt_dir.mkdir(parents=True, exist_ok=True)

    frame_payload = compact_frame_metadata(payload)

    created_paths: list[Path] = []

    metadata_path = attempt_dir / f"step_{step_index:04d}_metadata.json"
    metadata_path.write_text(json.dumps(frame_payload, indent=2), encoding="utf-8")
    created_paths.append(metadata_path)

    frames = payload["frame"].get("frame", [])
    for frame_index, frame in enumerate(frames):
        array = np.array(frame, dtype=np.int16)
        rgb = frame_to_rgb_array(array)
        if frame_index == len(frames) - 1:
            png_path = attempt_dir / f"step_{step_index:04d}_final.png"
            txt_path = attempt_dir / f"step_{step_index:04d}_final.txt"
        else:
            png_path = attempt_dir / f"step_{step_index:04d}_intermediate_{frame_index:02d}.png"
            txt_path = attempt_dir / f"step_{step_index:04d}_intermediate_{frame_index:02d}.txt"
        Image.fromarray(rgb, mode="RGB").save(png_path)
        txt_path.write_text(frame_to_ascii(array), encoding="utf-8")
        created_paths.extend([png_path, txt_path])

    return created_paths


def saved_artifacts_for_state(state: dict[str, Any], response: dict[str, Any]) -> list[Path]:
    directory = attempt_dir(int(state["current_level"]), int(state["current_attempt"]))
    current_attempt_step = int(state["current_attempt_step"])
    if current_attempt_step == 0:
        paths = [
            directory / "initial_metadata.json",
            directory / "initial_frame.png",
            directory / "initial_frame.txt",
        ]
    else:
        prefix = f"step_{current_attempt_step:04d}"
        paths = [directory / f"{prefix}_metadata.json"]
        frames = response["frame"].get("frame", [])
        for frame_index, _frame in enumerate(frames):
            if frame_index == len(frames) - 1:
                paths.extend([directory / f"{prefix}_final.png", directory / f"{prefix}_final.txt"])
            else:
                paths.extend(
                    [
                        directory / f"{prefix}_intermediate_{frame_index:02d}.png",
                        directory / f"{prefix}_intermediate_{frame_index:02d}.txt",
                    ]
                )
    return [path for path in paths if path.exists()]


def read_client_state() -> dict[str, Any]:
    if not CLIENT_STATE_PATH.is_file():
        raise FileNotFoundError("No active client session. Start a game first.")
    state = json.loads(CLIENT_STATE_PATH.read_text(encoding="utf-8"))
    keys = set(state)
    if keys != CLIENT_STATE_KEYS:
        extra = sorted(keys - CLIENT_STATE_KEYS)
        missing = sorted(CLIENT_STATE_KEYS - keys)
        details = []
        if missing:
            details.append(f"missing keys: {', '.join(missing)}")
        if extra:
            details.append(f"unexpected keys: {', '.join(extra)}")
        raise RuntimeError(f"Invalid client_state.json ({'; '.join(details)}).")

    for key in ("current_level", "current_attempt", "current_attempt_step"):
        value = int(state[key])
        if value < 0:
            raise RuntimeError(f"Invalid client_state.json: {key} must be non-negative.")
        state[key] = value
    if int(state["current_level"]) < 1 or int(state["current_attempt"]) < 1:
        raise RuntimeError("Invalid client_state.json: current_level and current_attempt must be positive.")
    if not str(state["session_token"]).strip():
        raise RuntimeError("Invalid client_state.json: session_token is required.")
    if not str(state["server_url"]).strip():
        raise RuntimeError("Invalid client_state.json: server_url is required.")
    return state


def write_client_state(state: dict[str, Any]) -> None:
    if set(state) != CLIENT_STATE_KEYS:
        raise RuntimeError("Refusing to write client_state.json with unexpected keys.")
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = CLIENT_STATE_PATH.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temp_path.replace(CLIENT_STATE_PATH)


def clear_client_state() -> None:
    if CLIENT_STATE_PATH.exists():
        CLIENT_STATE_PATH.unlink()


@contextmanager
def client_lock():
    CLIENT_ROOT.mkdir(parents=True, exist_ok=True)
    with CLIENT_LOCK_PATH.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def print_step_summary(response: dict[str, Any], created_paths: list[Path]) -> None:
    frame = response["frame"]
    action_input = frame.get("action_input") or {}
    action_name = action_input.get("id", "UNKNOWN")
    available_actions = frame.get("available_actions", [])
    available_actions_human = ", ".join(
        f"{action}(ACTION{action}, {ACTION_SEMANTICS.get(int(action), 'usual semantics: unknown')})"
        for action in available_actions
    )

    print(f"step: {frame['step_index']}")
    print(f"state: {frame['state']}")
    print(
        f"level: {min(int(frame['levels_completed']) + 1, int(frame['win_levels']) or int(frame['levels_completed']) + 1)} / {frame['win_levels']} "
        f"(completed: {frame['levels_completed']})"
    )
    print(f"action: {action_name}")
    print(f"available_actions_next: [{available_actions_human}]")
    grouped_paths: dict[Path, list[str]] = {}
    for path in created_paths:
        grouped_paths.setdefault(path.parent, []).append(path.name)
    for directory, file_names in grouped_paths.items():
        print(f"path: {directory}")
        print("files:")
        for file_name in file_names:
            print(f"  {file_name}")


def canonical_action(value: str) -> str:
    action = value.strip()
    if action not in OFFICIAL_ACTIONS:
        raise ValueError(
            f"Unknown action: {value}. Use official names only: RESET, ACTION1, ACTION2, ACTION3, ACTION4, ACTION5, ACTION6, ACTION7."
        )
    return action


def session_token_from_state(state: dict[str, Any], *, allow_missing: bool = False) -> str | None:
    token = state.get("session_token")
    if token is None or str(token).strip() == "":
        if allow_missing:
            return None
        raise RuntimeError("No session_token in client_state.json. Start a game first.")
    return str(token).strip()


def post_json(
    path: str, payload: dict[str, Any], session_token: str | None = None, server_url: str = SERVER_URL
) -> dict[str, Any]:
    headers: dict[str, str] = {}
    if session_token:
        headers["X-Session-Token"] = session_token
    response = requests.post(f"{server_url}{path}", json=payload, headers=headers, timeout=30)
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError(f"Server returned a non-JSON response for {path}: HTTP {response.status_code}") from None
    if not response.ok:
        raise RuntimeError(data.get("error", f"Request failed: {response.status_code}"))
    return data


def get_json(path: str, session_token: str | None = None, server_url: str = SERVER_URL) -> dict[str, Any]:
    headers: dict[str, str] = {}
    if session_token:
        headers["X-Session-Token"] = session_token
    response = requests.get(f"{server_url}{path}", headers=headers, timeout=30)
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError(f"Server returned a non-JSON response for {path}: HTTP {response.status_code}") from None
    if not response.ok:
        raise RuntimeError(data.get("error", f"Request failed: {response.status_code}"))
    return data


def stop_server_session(session_token: str, server_url: str = SERVER_URL) -> dict[str, Any]:
    return post_json("/game/stop", {}, session_token=session_token, server_url=server_url)


def write_action_response(state: dict[str, Any], response: dict[str, Any]) -> list[Path]:
    previous_level = int(state["current_level"])
    previous_attempt = int(state["current_attempt"])
    previous_attempt_step = int(state["current_attempt_step"])
    action_input = response["frame"].get("action_input") or {}
    action_name = action_input.get("id")
    next_level = current_level_from_frame(response["frame"])

    if action_name == "RESET":
        next_attempt = previous_attempt + 1
        directory = attempt_dir(previous_level, next_attempt)
        created_paths = save_initial_artifacts(directory, response)
        state["current_level"] = previous_level
        state["current_attempt"] = next_attempt
        state["current_attempt_step"] = 0
        return created_paths

    directory = attempt_dir(previous_level, previous_attempt)
    next_attempt_step = previous_attempt_step + 1
    created_paths = save_step_artifacts(directory, response, next_attempt_step)
    state["current_attempt_step"] = next_attempt_step

    if next_level > previous_level:
        next_attempt = 1
        next_directory = attempt_dir(next_level, next_attempt)
        created_paths.extend(save_initial_artifacts(next_directory, response))
        state["current_level"] = next_level
        state["current_attempt"] = next_attempt
        state["current_attempt_step"] = 0

    return created_paths


def client_step_index_from_state(state: dict[str, Any]) -> int:
    metadata_path = metadata_path_for_state(state)
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Missing metadata for current client state: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return int(metadata["step_index"])


def repair_if_needed(state: dict[str, Any]) -> tuple[dict[str, Any] | None, list[Path]]:
    client_step_index = client_step_index_from_state(state)
    response = get_json(
        "/game/last-step",
        session_token=session_token_from_state(state),
        server_url=str(state["server_url"]),
    )
    server_step_index = int(response["frame"]["step_index"])

    if server_step_index < client_step_index:
        raise RuntimeError(
            f"Server is behind the client state: server step {server_step_index}, client step {client_step_index}."
        )
    if server_step_index >= client_step_index + 2:
        raise RuntimeError(
            f"Server is too far ahead to repair safely: server step {server_step_index}, client step {client_step_index}."
        )
    if server_step_index == client_step_index:
        return None, []

    created_paths = write_action_response(state, response)
    write_client_state(state)
    return response, created_paths


def start_command(game_id: str, seed: int) -> None:
    with client_lock():
        if SESSION_DIR.exists():
            raise FileExistsError(f"Session folder already exists: {SESSION_DIR}")
        response = post_json("/game/start", {"game_id": game_id, "seed": seed})
        level_id = current_level_from_frame(response["frame"])
        first_attempt_dir = attempt_dir(level_id, 1)
        created_paths = save_initial_artifacts(first_attempt_dir, response)
        write_client_state(
            {
                "current_level": level_id,
                "current_attempt": 1,
                "current_attempt_step": 0,
                "session_token": response["session"]["session_token"],
                "server_url": SERVER_URL,
            }
        )
    print_step_summary(response, created_paths)


def move_command(action: str, x: int | None, y: int | None, reasoning_json: str | None) -> None:
    canonical = canonical_action(action)
    payload: dict[str, Any] = {"action": canonical}
    if canonical == "ACTION6":
        if x is None or y is None:
            raise ValueError("ACTION6 requires both --x and --y.")
    elif x is not None or y is not None:
        raise ValueError("--x/--y are only valid with ACTION6.")
    if x is not None or y is not None:
        if x is None or y is None:
            raise ValueError("Both --x and --y are required together.")
        payload["data"] = {"x": x, "y": y}
    if reasoning_json:
        payload["reasoning"] = json.loads(reasoning_json)

    with client_lock():
        state = read_client_state()
        repair_response, repair_paths = repair_if_needed(state)
        response = post_json(
            "/game/action",
            payload,
            session_token=session_token_from_state(state),
            server_url=str(state["server_url"]),
        )
        created_paths = write_action_response(state, response)
        state["session_token"] = response["session"]["session_token"]
        write_client_state(state)

    if repair_response is not None:
        print(
            "the previous run of the client was interruputed after it made the move but before it wrote information. "
            "The files have been restored. The information from the previous step"
        )
        print_step_summary(repair_response, repair_paths)
    print_step_summary(response, created_paths)


def status_command() -> None:
    with client_lock():
        state = read_client_state()
        response = get_json(
            "/game/last-step",
            session_token=session_token_from_state(state),
            server_url=str(state["server_url"]),
        )
        created_paths = saved_artifacts_for_state(state, response)
    print("Last step information:")
    print_step_summary(response, created_paths)


def stop_command() -> None:
    with client_lock():
        state = read_client_state()
        response = stop_server_session(session_token_from_state(state), server_url=str(state["server_url"]))
        clear_client_state()
    print(json.dumps({"stopped": response["stopped"], "session": response["session"]}, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CLI client for the local ARC server. One command per move."
    )
    subparsers = parser.add_subparsers(dest="command")

    start_parser = subparsers.add_parser("start", help="Start a new game session.")
    start_parser.add_argument("game_id")
    start_parser.add_argument("--seed", type=int, default=0)

    move_parser = subparsers.add_parser("move", help="Send one action to the active game session.")
    move_parser.add_argument("action")
    move_parser.add_argument("--x", type=int, default=None)
    move_parser.add_argument("--y", type=int, default=None)
    move_parser.add_argument("--reasoning-json", default=None)

    subparsers.add_parser("status", help="Print the active client state and current server state.")
    subparsers.add_parser("stop", help="Stop the active server session and clear the local active state file.")
    return parser


def main() -> int:
    ignore_interrupt_and_term_signals()
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "start":
            start_command(args.game_id, args.seed)
        elif args.command == "move":
            move_command(args.action, args.x, args.y, args.reasoning_json)
        elif args.command == "status":
            status_command()
        elif args.command == "stop":
            stop_command()
        else:
            parser.error("a command is required.")
        return 0
    except requests.exceptions.RequestException as exc:
        print(f"Server request failed: {exc}")
        print("Start the server first: python3 server/server.py")
        return 1
    except FileExistsError as exc:
        print(str(exc))
        return 1
    except FileNotFoundError as exc:
        print(str(exc))
        print("Start a game first: python3 client/client.py start <game_id>")
        return 1
    except RuntimeError as exc:
        print(str(exc))
        return 1
    except ValueError as exc:
        print(f"Invalid command: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
