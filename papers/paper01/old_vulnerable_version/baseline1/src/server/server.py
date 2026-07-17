from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import sys
from threading import RLock
from typing import Any
from uuid import uuid4

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from arc_agi import Arcade
from arcengine import GameAction

SERVER_HOST = os.environ.get("ARC_SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.environ.get("ARC_SERVER_PORT", "8878"))
SERVER_LOG_PATH = Path(os.environ.get("ARC_SERVER_LOG_PATH", "server.log"))

APP = Flask(__name__)
LOGGER = logging.getLogger("arc-server")


def setup_logging(log_path: Path) -> None:
    if log_path.exists():
        raise FileExistsError(f"Refusing to start because log file already exists: {log_path}")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    file_handler = logging.FileHandler(log_path, mode="x", encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    APP.logger.handlers.clear()
    APP.logger.propagate = True
    logging.getLogger("werkzeug").setLevel(logging.INFO)


@APP.before_request
def log_request() -> None:
    LOGGER.info("%s %s from %s", request.method, request.path, request.remote_addr)


@APP.after_request
def log_response(response: Any) -> Any:
    if response.status_code >= 500:
        LOGGER.error("%s %s -> %s", request.method, request.path, response.status)
    elif response.status_code >= 400:
        LOGGER.warning("%s %s -> %s", request.method, request.path, response.status)
    return response


@APP.errorhandler(Exception)
def log_unhandled_exception(exc: Exception) -> Any:
    if isinstance(exc, HTTPException):
        return exc
    LOGGER.exception("Unhandled exception while handling %s %s", request.method, request.path)
    return jsonify({"error": repr(exc)}), 500


def serialize_action_input(frame_data: Any) -> dict[str, Any] | None:
    if frame_data.action_input is None:
        return None
    return {
        "id": frame_data.action_input.id.name
        if hasattr(frame_data.action_input.id, "name")
        else str(frame_data.action_input.id),
        "data": frame_data.action_input.data,
        "reasoning": frame_data.action_input.reasoning,
    }


def serialize_frame(frame_data: Any, step_index: int) -> dict[str, Any]:
    frame_layers = []
    for frame in frame_data.frame:
        frame_layers.append(frame.tolist() if hasattr(frame, "tolist") else frame)

    return {
        "step_index": step_index,
        "game_id": frame_data.game_id,
        "guid": frame_data.guid,
        "state": frame_data.state.name if hasattr(frame_data.state, "name") else str(frame_data.state),
        "levels_completed": frame_data.levels_completed,
        "win_levels": frame_data.win_levels,
        "available_actions": frame_data.available_actions,
        "full_reset": getattr(frame_data, "full_reset", False),
        "action_input": serialize_action_input(frame_data),
        "frame": frame_layers,
    }


@dataclass
class ServerSession:
    token: str
    arcade: Arcade
    env: Any
    requested_game_id: str
    started_at: str
    step_index: int = 0
    last_step_payload: dict[str, Any] | None = None
    lock: RLock | None = None


SESSIONS: dict[str, ServerSession] = {}
SESSIONS_LOCK = RLock()


def session_token_from_request(payload: dict[str, Any] | None = None) -> str:
    header_token = request.headers.get("X-Session-Token")
    if header_token:
        return header_token.strip()
    if payload is not None:
        body_token = payload.get("session_token")
        if body_token is not None:
            return str(body_token).strip()
    query_token = request.args.get("session_token", "").strip()
    return query_token


def require_session(session_token: str) -> ServerSession:
    if not session_token:
        raise RuntimeError("session_token is required. Start a session first.")
    with SESSIONS_LOCK:
        session = SESSIONS.get(session_token)
    if session is None:
        raise RuntimeError("Unknown session_token. The server session may be gone.")
    return session


def session_payload(session: ServerSession) -> dict[str, Any]:
    info = session.env.info
    return {
        "session_token": session.token,
        "requested_game_id": session.requested_game_id,
        "resolved_game_id": info.game_id,
        "title": info.title,
        "started_at": session.started_at,
        "server_step_index": session.step_index,
    }


@APP.get("/health")
def health() -> Any:
    return jsonify({"status": "ok", "server_started": datetime.now(timezone.utc).isoformat()})


@APP.post("/game/start")
def start_game() -> Any:
    payload = request.get_json(silent=True) or {}
    game_id = str(payload.get("game_id", "")).strip()
    if not game_id:
        LOGGER.warning("rejecting start request without game_id")
        return jsonify({"error": "game_id is required"}), 400

    seed = int(payload.get("seed", 0))
    LOGGER.info("starting game_id=%s seed=%s", game_id, seed)
    arcade = Arcade()
    env = arcade.make(game_id, seed=seed)
    if env is None or env.observation_space is None:
        LOGGER.error("failed to create environment for game_id=%s seed=%s", game_id, seed)
        return jsonify({"error": f"failed to create environment for {game_id}"}), 500

    token = uuid4().hex
    session = ServerSession(
        token=token,
        arcade=arcade,
        env=env,
        requested_game_id=game_id,
        started_at=datetime.now(timezone.utc).isoformat(),
        step_index=0,
        lock=RLock(),
    )
    with SESSIONS_LOCK:
        SESSIONS[token] = session
    LOGGER.info("started session token=%s requested_game_id=%s", token, game_id)
    response_payload = {
        "session": session_payload(session),
        "frame": serialize_frame(env.observation_space, step_index=0),
    }
    with session.lock or RLock():
        session.last_step_payload = deepcopy(response_payload)
    return jsonify(response_payload)


@APP.post("/game/action")
def apply_action() -> Any:
    payload = request.get_json(silent=True) or {}
    try:
        session = require_session(session_token_from_request(payload))
    except RuntimeError as exc:
        LOGGER.warning("rejecting action request: %s", exc)
        return jsonify({"error": str(exc)}), 400

    action_name = payload.get("action")
    if not action_name:
        LOGGER.warning("rejecting action request without action")
        return jsonify({"error": "action is required"}), 400

    action = GameAction[str(action_name)] if not isinstance(action_name, int) else GameAction.from_id(action_name)
    data = payload.get("data")
    reasoning = payload.get("reasoning")
    if data is not None and not isinstance(data, dict):
        return jsonify({"error": "data must be an object"}), 400
    if reasoning is not None and not isinstance(reasoning, dict):
        return jsonify({"error": "reasoning must be an object"}), 400

    with session.lock or RLock():
        if action == GameAction.RESET:
            frame_data = session.env.reset()
        else:
            frame_data = session.env.step(action, data=data, reasoning=reasoning)

        if frame_data is None:
            LOGGER.error("action failed for session=%s action=%s", session.token, action.name)
            return jsonify({"error": f"action failed: {action.name}"}), 500

        session.step_index += 1
        LOGGER.info(
            "applied action session=%s action=%s step_index=%s",
            session.token,
            action.name,
            session.step_index,
        )
        serialized_frame = serialize_frame(frame_data, step_index=session.step_index)
        if serialized_frame["action_input"] is None:
            serialized_frame["action_input"] = {
                "id": action.name,
                "data": data,
                "reasoning": reasoning,
            }
        response_payload = {
            "session": session_payload(session),
            "frame": serialized_frame,
        }
        session.last_step_payload = deepcopy(response_payload)
    return jsonify(response_payload)


@APP.get("/game/last-step")
def last_step() -> Any:
    payload = request.get_json(silent=True) or {}
    try:
        session = require_session(session_token_from_request(payload))
    except RuntimeError as exc:
        LOGGER.warning("rejecting last-step request: %s", exc)
        return jsonify({"error": str(exc)}), 400

    with session.lock or RLock():
        if session.last_step_payload is None:
            LOGGER.error("last-step payload unavailable for session=%s", session.token)
            return jsonify({"error": "No last-step payload available"}), 500
        return jsonify(deepcopy(session.last_step_payload))


@APP.get("/game/current")
def current_game() -> Any:
    payload = request.get_json(silent=True) or {}
    try:
        session = require_session(session_token_from_request(payload))
    except RuntimeError as exc:
        LOGGER.warning("rejecting current-game request: %s", exc)
        return jsonify({"error": str(exc)}), 400

    with session.lock or RLock():
        observation = session.env.observation_space
        if observation is None:
            LOGGER.error("observation unavailable for session=%s", session.token)
            return jsonify({"error": "No observation available"}), 500

    return jsonify(
        {
            "session": session_payload(session),
            "frame": serialize_frame(observation, step_index=session.step_index),
        }
    )


@APP.post("/game/stop")
def stop_game() -> Any:
    payload = request.get_json(silent=True) or {}
    session_token = session_token_from_request(payload)
    if not session_token:
        LOGGER.warning("rejecting stop request without session_token")
        return jsonify({"error": "session_token is required. Start a session first."}), 400

    with SESSIONS_LOCK:
        session = SESSIONS.pop(session_token, None)
    if session is None:
        LOGGER.warning("rejecting stop request for unknown session=%s", session_token)
        return jsonify({"error": "Unknown session_token. The server session may be gone."}), 400

    LOGGER.info("stopped session token=%s requested_game_id=%s", session.token, session.requested_game_id)
    return jsonify({"stopped": True, "session": session_payload(session)})


def main() -> int:
    try:
        setup_logging(SERVER_LOG_PATH)
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr, flush=True)
        return 1

    LOGGER.info("starting server host=%s port=%s log=%s", SERVER_HOST, SERVER_PORT, SERVER_LOG_PATH)
    try:
        APP.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, threaded=True)
    except Exception:
        LOGGER.exception("server stopped because APP.run raised")
        return 1
    LOGGER.info("server stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
