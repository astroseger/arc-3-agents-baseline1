from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import atexit
import logging
import os
from pathlib import Path
import queue
import signal
import sys
import threading
import time
from typing import Any
from uuid import uuid4

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from arc_agi import Arcade, OperationMode
from arcengine import GameAction

SERVER_HOST = os.environ.get("ARC_SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.environ.get("ARC_SERVER_PORT", "8879"))
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("ARC_COMPETITION_REQUEST_TIMEOUT", "300"))
MAX_REQUESTS_PER_SECOND = 500
MIN_REQUEST_INTERVAL_SECONDS = 1.0 / MAX_REQUESTS_PER_SECOND
SCORECARD_PATH = Path(os.environ.get("ARC_SCORECARD_PATH", "scorecard.txt"))
FINAL_SCORECARD_PATH = Path(os.environ.get("ARC_FINAL_SCORECARD_PATH", "final_scorecard.txt"))
SERVER_LOG_PATH = Path(os.environ.get("ARC_SERVER_LOG_PATH", "server.log"))
SOURCE_URL = os.environ.get("ARC_SCORECARD_SOURCE_URL", "https://github.com/astroseger/arc-3-agents-baseline1")
SCORECARD_TAGS = [
    tag.strip()
    for tag in os.environ.get("ARC_SCORECARD_TAGS", "api-test").split(",")
    if tag.strip()
]

APP = Flask(__name__)
LOGGER = logging.getLogger("arc-server.competition")


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


def get_scorecard_id(scorecard: Any) -> str:
    if isinstance(scorecard, str):
        return scorecard
    if hasattr(scorecard, "card_id"):
        return str(scorecard.card_id)
    if hasattr(scorecard, "id"):
        return str(scorecard.id)
    raise TypeError(f"Cannot extract scorecard id from {scorecard!r}")


def write_text_atomic(path: Path, text: str) -> None:
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


@dataclass
class ServerSession:
    token: str
    env: Any
    requested_game_id: str
    started_at: str
    step_index: int = 0
    last_step_payload: dict[str, Any] | None = None


@dataclass
class CompetitionRequest:
    request_type: str
    payload: dict[str, Any]
    response_queue: queue.Queue[dict[str, Any]] | None = None


class RequestError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


class CompetitionController:
    def __init__(self) -> None:
        self._requests: queue.Queue[CompetitionRequest] = queue.Queue()
        self._ready: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)
        self._thread: threading.Thread | None = None
        self._shutdown_lock = threading.Lock()
        self._shutdown_complete = threading.Event()
        self._shutdown_started = False

    def start(self) -> None:
        if SCORECARD_PATH.exists():
            raise FileExistsError(f"Refusing to start because scorecard file already exists: {SCORECARD_PATH}")

        LOGGER.info("starting competition controller")
        self._thread = threading.Thread(target=self._run, name="competition-arcade-owner", daemon=False)
        self._thread.start()
        ready = self._ready.get(timeout=REQUEST_TIMEOUT_SECONDS)
        if not ready["ok"]:
            raise RuntimeError(ready["error"])

    def call(self, request_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        response_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)
        with self._shutdown_lock:
            if self._shutdown_started:
                return {"ok": False, "status": 503, "error": "Server is shutting down."}
            self._requests.put(CompetitionRequest(request_type, payload, response_queue))
        try:
            return response_queue.get(timeout=REQUEST_TIMEOUT_SECONDS)
        except queue.Empty:
            LOGGER.error("timed out waiting for serialized competition request: %s", request_type)
            return {
                "ok": False,
                "status": 504,
                "error": f"Timed out waiting for serialized competition request: {request_type}",
            }

    def shutdown(self, timeout: float = 60.0) -> None:
        if self._thread is None:
            self._shutdown_complete.set()
            return

        with self._shutdown_lock:
            if self._shutdown_started:
                pass
            else:
                self._shutdown_started = True
                self._requests.put(CompetitionRequest("shutdown", {}))

        self._shutdown_complete.wait(timeout=timeout)
        if self._thread is not None and self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=0.1)

    def _run(self) -> None:
        arc: Arcade | None = None
        scorecard_id: str | None = None
        sessions: dict[str, ServerSession] = {}
        last_request_at = 0.0

        try:
            arc = Arcade(operation_mode=OperationMode.COMPETITION)
            scorecard = arc.create_scorecard(source_url=SOURCE_URL, tags=SCORECARD_TAGS)
            scorecard_id = get_scorecard_id(scorecard)
            if SCORECARD_PATH.exists():
                raise FileExistsError(f"Refusing to start because scorecard file already exists: {SCORECARD_PATH}")
            write_text_atomic(SCORECARD_PATH, scorecard_id + "\n")
            LOGGER.info("opened scorecard: %s", scorecard_id)
            self._ready.put({"ok": True})
        except Exception as exc:
            LOGGER.exception("failed to initialize competition controller")
            if arc is not None and scorecard_id is not None:
                self._close_scorecard(arc, scorecard_id)
            self._ready.put({"ok": False, "error": repr(exc)})
            self._shutdown_complete.set()
            return

        try:
            while True:
                competition_request = self._requests.get()
                now = time.monotonic()
                wait_seconds = MIN_REQUEST_INTERVAL_SECONDS - (now - last_request_at)
                if wait_seconds > 0:
                    time.sleep(wait_seconds)
                last_request_at = time.monotonic()

                if competition_request.request_type == "shutdown":
                    LOGGER.info("competition controller received shutdown request")
                    break

                response = self._handle_request(arc, scorecard_id, sessions, competition_request)
                if competition_request.response_queue is not None:
                    competition_request.response_queue.put(response)
                if response.get("fatal_shutdown"):
                    LOGGER.error("fatal competition condition: %s", response.get("error"))
                    break
        finally:
            self._close_sessions(sessions)
            if arc is not None and scorecard_id is not None:
                self._close_scorecard(arc, scorecard_id)
            self._shutdown_complete.set()
            LOGGER.info("competition controller stopped")

    def _handle_request(
        self,
        arc: Arcade,
        scorecard_id: str,
        sessions: dict[str, ServerSession],
        competition_request: CompetitionRequest,
    ) -> dict[str, Any]:
        try:
            request_type = competition_request.request_type
            payload = competition_request.payload

            if request_type == "start":
                return self._start_session(arc, scorecard_id, sessions, payload)
            if request_type == "action":
                return self._apply_action(sessions, payload)
            if request_type == "last-step":
                return self._last_step(sessions, payload)
            if request_type == "current":
                return self._current(sessions, payload)
            if request_type == "stop":
                return self._stop_session(sessions, payload)
            raise RuntimeError(f"Unknown serialized request type: {request_type}")
        except RequestError as exc:
            LOGGER.warning("request %s rejected: %s", competition_request.request_type, exc)
            return {"ok": False, "status": exc.status, "error": str(exc)}
        except Exception as exc:
            LOGGER.exception("request %s failed", competition_request.request_type)
            return {"ok": False, "status": 500, "error": repr(exc)}

    def _session_payload(self, session: ServerSession) -> dict[str, Any]:
        info = session.env.info
        return {
            "session_token": session.token,
            "requested_game_id": session.requested_game_id,
            "resolved_game_id": info.game_id,
            "title": info.title,
            "started_at": session.started_at,
            "server_step_index": session.step_index,
        }

    def _require_session(self, sessions: dict[str, ServerSession], session_token: str) -> ServerSession:
        if not session_token:
            raise RequestError(400, "session_token is required. Start a session first.")
        session = sessions.get(session_token)
        if session is None:
            raise RequestError(400, "Unknown session_token. The server session may be gone.")
        return session

    def _start_session(
        self, arc: Arcade, scorecard_id: str, sessions: dict[str, ServerSession], payload: dict[str, Any]
    ) -> dict[str, Any]:
        game_id = str(payload.get("game_id", "")).strip()
        if not game_id:
            LOGGER.warning("rejecting start request without game_id")
            return {"ok": False, "status": 400, "error": "game_id is required"}
        for session in sessions.values():
            if session.requested_game_id == game_id:
                LOGGER.warning("rejecting duplicate session for game_id=%s", game_id)
                return {"ok": False, "status": 409, "error": f"game already has an active session: {game_id}"}

        seed = int(payload.get("seed", 0))
        LOGGER.info("starting competition game_id=%s seed=%s scorecard=%s", game_id, seed, scorecard_id)
        env = arc.make(game_id, seed=seed, scorecard_id=scorecard_id)
        if env is None or env.observation_space is None:
            LOGGER.error("failed to create environment for game_id=%s seed=%s", game_id, seed)
            return {"ok": False, "status": 500, "error": f"failed to create environment for {game_id}"}

        token = uuid4().hex
        session = ServerSession(
            token=token,
            env=env,
            requested_game_id=game_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        sessions[token] = session
        LOGGER.info("started session token=%s requested_game_id=%s", token, game_id)
        response_payload = {
            "session": self._session_payload(session),
            "frame": serialize_frame(env.observation_space, step_index=0),
        }
        session.last_step_payload = deepcopy(response_payload)
        return {"ok": True, "payload": response_payload}

    def _apply_action(self, sessions: dict[str, ServerSession], payload: dict[str, Any]) -> dict[str, Any]:
        session = self._require_session(sessions, str(payload.get("session_token", "")).strip())

        action_name = payload.get("action")
        if not action_name:
            LOGGER.warning("rejecting action request without action for session=%s", session.token)
            return {"ok": False, "status": 400, "error": "action is required"}

        action = GameAction[str(action_name)] if not isinstance(action_name, int) else GameAction.from_id(action_name)
        data = payload.get("data")
        reasoning = payload.get("reasoning")
        if data is not None and not isinstance(data, dict):
            return {"ok": False, "status": 400, "error": "data must be an object"}
        if reasoning is not None and not isinstance(reasoning, dict):
            return {"ok": False, "status": 400, "error": "reasoning must be an object"}

        if action == GameAction.RESET:
            frame_data = session.env.reset()
        else:
            frame_data = session.env.step(action, data=data, reasoning=reasoning)

        if frame_data is None:
            error = (
                f"action failed after Arcade returned no frame for {action.name}; "
                "the competition scorecard may have been closed by the ARC server"
            )
            LOGGER.error("%s", error)
            return {"ok": False, "status": 503, "error": error, "fatal_shutdown": True}

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
            "session": self._session_payload(session),
            "frame": serialized_frame,
        }
        session.last_step_payload = deepcopy(response_payload)
        return {"ok": True, "payload": response_payload}

    def _last_step(self, sessions: dict[str, ServerSession], payload: dict[str, Any]) -> dict[str, Any]:
        session = self._require_session(sessions, str(payload.get("session_token", "")).strip())
        if session.last_step_payload is None:
            LOGGER.error("last-step payload unavailable for session=%s", session.token)
            return {"ok": False, "status": 500, "error": "No last-step payload available"}
        return {"ok": True, "payload": deepcopy(session.last_step_payload)}

    def _current(self, sessions: dict[str, ServerSession], payload: dict[str, Any]) -> dict[str, Any]:
        session = self._require_session(sessions, str(payload.get("session_token", "")).strip())
        observation = session.env.observation_space
        if observation is None:
            LOGGER.error("observation unavailable for session=%s", session.token)
            return {"ok": False, "status": 500, "error": "No observation available"}
        return {
            "ok": True,
            "payload": {
                "session": self._session_payload(session),
                "frame": serialize_frame(observation, step_index=session.step_index),
            },
        }

    def _stop_session(self, sessions: dict[str, ServerSession], payload: dict[str, Any]) -> dict[str, Any]:
        session_token = str(payload.get("session_token", "")).strip()
        if not session_token:
            LOGGER.warning("rejecting stop request without session_token")
            return {"ok": False, "status": 400, "error": "session_token is required. Start a session first."}

        session = sessions.pop(session_token, None)
        if session is None:
            LOGGER.warning("rejecting stop request for unknown session=%s", session_token)
            return {"ok": False, "status": 400, "error": "Unknown session_token. The server session may be gone."}

        response_payload = {"stopped": True, "session": self._session_payload(session)}
        try:
            close = getattr(session.env, "close", None)
            if close is not None:
                close()
        except Exception as exc:
            LOGGER.exception("env.close failed for %s", session.requested_game_id)
        LOGGER.info("stopped session token=%s requested_game_id=%s", session.token, session.requested_game_id)
        return {"ok": True, "payload": response_payload}

    def _close_sessions(self, sessions: dict[str, ServerSession]) -> None:
        LOGGER.info("closing envs")
        for session_token, session in list(sessions.items()):
            try:
                close = getattr(session.env, "close", None)
                if close is not None:
                    close()
            except Exception as exc:
                LOGGER.exception("env.close failed for %s/%s", session.requested_game_id, session_token)
        sessions.clear()

    def _close_scorecard(self, arc: Arcade, scorecard_id: str) -> None:
        LOGGER.info("closing scorecard: %s", scorecard_id)
        try:
            final_scorecard = arc.close_scorecard(scorecard_id)
            write_text_atomic(FINAL_SCORECARD_PATH, str(final_scorecard))
            LOGGER.info("final scorecard written: %s", FINAL_SCORECARD_PATH)
        except Exception as exc:
            LOGGER.exception("close_scorecard failed")
            LOGGER.error("scorecard id is saved in %s", SCORECARD_PATH)


CONTROLLER = CompetitionController()


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


def flask_response(controller_response: dict[str, Any]) -> Any:
    should_stop_server = bool(controller_response.get("fatal_shutdown"))
    if controller_response.get("ok"):
        response = jsonify(controller_response["payload"])
        if should_stop_server:
            request_server_stop("fatal competition response")
        return response
    status = int(controller_response.get("status", 500))
    response = jsonify({"error": controller_response.get("error", "request failed")})
    if should_stop_server:
        request_server_stop(str(controller_response.get("error", "fatal competition response")))
    return response, status


def request_server_stop(reason: str) -> None:
    LOGGER.error("stopping server: %s", reason)
    shutdown = request.environ.get("werkzeug.server.shutdown")
    if callable(shutdown):
        shutdown()
        return

    def terminate_process() -> None:
        LOGGER.error("terminating process after shutdown hook was unavailable")
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Timer(2.0, terminate_process).start()


@APP.get("/health")
def health() -> Any:
    return jsonify({"status": "ok", "server_started": datetime.now(timezone.utc).isoformat()})


@APP.post("/game/start")
def start_game() -> Any:
    payload = request.get_json(silent=True) or {}
    return flask_response(CONTROLLER.call("start", payload))


@APP.post("/game/action")
def apply_action() -> Any:
    payload = request.get_json(silent=True) or {}
    payload["session_token"] = session_token_from_request(payload)
    return flask_response(CONTROLLER.call("action", payload))


@APP.get("/game/last-step")
def last_step() -> Any:
    payload = request.get_json(silent=True) or {}
    payload["session_token"] = session_token_from_request(payload)
    return flask_response(CONTROLLER.call("last-step", payload))


@APP.get("/game/current")
def current_game() -> Any:
    payload = request.get_json(silent=True) or {}
    payload["session_token"] = session_token_from_request(payload)
    return flask_response(CONTROLLER.call("current", payload))


@APP.post("/game/stop")
def stop_game() -> Any:
    payload = request.get_json(silent=True) or {}
    payload["session_token"] = session_token_from_request(payload)
    return flask_response(CONTROLLER.call("stop", payload))


def shutdown_controller() -> None:
    CONTROLLER.shutdown()


def install_signal_handlers() -> None:
    previous_handlers: dict[int, Any] = {}

    def handle_signal(signum: int, _frame: Any) -> None:
        LOGGER.error("signal %s received", signum)
        CONTROLLER.shutdown()
        previous_handler = previous_handlers.get(signum)
        if callable(previous_handler):
            previous_handler(signum, _frame)
        raise SystemExit(128 + signum)

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, handle_signal)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serialized ARC competition server.")
    parser.add_argument("--host", default=SERVER_HOST)
    parser.add_argument("--port", type=int, default=SERVER_PORT)
    parser.add_argument("--source-url", default=SOURCE_URL)
    parser.add_argument(
        "--tag",
        action="append",
        dest="tags",
        default=None,
        help="Scorecard tag. Repeat for multiple tags. Defaults to api-test.",
    )
    parser.add_argument("--scorecard-path", type=Path, default=SCORECARD_PATH)
    parser.add_argument("--final-scorecard-path", type=Path, default=FINAL_SCORECARD_PATH)
    parser.add_argument("--log-path", type=Path, default=SERVER_LOG_PATH)
    return parser


def main() -> int:
    global SERVER_HOST, SERVER_PORT, SOURCE_URL, SCORECARD_TAGS, SCORECARD_PATH, FINAL_SCORECARD_PATH, SERVER_LOG_PATH

    args = build_parser().parse_args()
    SERVER_HOST = args.host
    SERVER_PORT = args.port
    SOURCE_URL = args.source_url
    SCORECARD_TAGS = args.tags if args.tags is not None else SCORECARD_TAGS
    SCORECARD_PATH = args.scorecard_path
    FINAL_SCORECARD_PATH = args.final_scorecard_path
    SERVER_LOG_PATH = args.log_path

    try:
        setup_logging(SERVER_LOG_PATH)
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr, flush=True)
        return 1

    atexit.register(shutdown_controller)
    install_signal_handlers()
    try:
        CONTROLLER.start()
    except Exception as exc:
        LOGGER.exception("failed to start competition server")
        return 1

    LOGGER.info(
        "starting competition server host=%s port=%s log=%s scorecard=%s final_scorecard=%s",
        SERVER_HOST,
        SERVER_PORT,
        SERVER_LOG_PATH,
        SCORECARD_PATH,
        FINAL_SCORECARD_PATH,
    )
    try:
        APP.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, threaded=True)
    except Exception:
        LOGGER.exception("competition server stopped because APP.run raised")
        return 1
    CONTROLLER.shutdown()
    LOGGER.info("competition server stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
