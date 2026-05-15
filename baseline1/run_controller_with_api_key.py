#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import run_funs as rf


rf.set_logger_name("arc-runner.api-key")
CHECK_CODEX_API_KEY_SCRIPT = rf.CODEX_ACCOUNTS_DIR / "check_codex_with_api_key.sh"
API_KEY_WARNING = """\
Running with API keys is very expensive. The used version of codex have a picularity that with API key the percentage of input token wich hit the cache is very low (in my test run which cost me 300$ it was <20%), when you run it via ChatGPT PRO subsciption this percentage is much higher >95%.

Because of this what you can run with a weekly limit of a single ChatGPT PRO account, would probably cost you > 10000$ with API key.

So think twice before your run it.

If you are sure. Type continue
"""


@dataclass(frozen=True)
class RunConfig:
    games: list[str]
    tag: str
    competition: bool
    model: str
    reasoning_effort: str


@dataclass
class RunningGame:
    game: str
    container_name: str
    process: subprocess.Popen[bytes]


def parse_run_config(path: Path, competition: bool) -> RunConfig:
    loaded_config = rf.load_run_config(path)
    games = rf.parse_string_list(loaded_config, "games", path)
    tag = rf.parse_tag(loaded_config, path) if competition else str(loaded_config.get("tag", "local"))
    model = rf.parse_optional_string(loaded_config, "model", path, default="gpt-5.5")
    reasoning_effort = rf.parse_optional_string(
        loaded_config,
        "reasoning_effort",
        path,
        default="medium",
    )
    rf.validate_unique_games(games)
    rf.verify_agent_source_dir()
    return RunConfig(
        games=games,
        tag=tag,
        competition=competition,
        model=model,
        reasoning_effort=reasoning_effort,
    )


def copy_game_inputs(game: str, server_url: str) -> Path:
    game_dir = rf.RUN_DIR / game
    agent_run_dir = game_dir / "run"

    game_dir.mkdir()
    shutil.copytree(rf.AGENT_SRC_DIR, agent_run_dir)
    rf.configure_client_server_url(agent_run_dir, server_url)
    return game_dir


def verify_codex_api_key() -> None:
    if not CHECK_CODEX_API_KEY_SCRIPT.is_file():
        raise RuntimeError(f"codex API key check script does not exist: {CHECK_CODEX_API_KEY_SCRIPT}")
    if not os.access(CHECK_CODEX_API_KEY_SCRIPT, os.X_OK):
        raise RuntimeError(f"codex API key check script is not executable: {CHECK_CODEX_API_KEY_SCRIPT}")

    rf.LOGGER.info("checking codex API key with %s", CHECK_CODEX_API_KEY_SCRIPT)
    result = subprocess.run([str(CHECK_CODEX_API_KEY_SCRIPT)], cwd=rf.ROOT, check=False)
    if result.returncode != 0:
        rf.LOGGER.error("codex API key check failed exit_code=%s", result.returncode)
        raise RuntimeError(f"codex API key check failed with exit code {result.returncode}")
    rf.LOGGER.info("codex API key check passed")


def docker_agent_command(
    game: str,
    container_name: str,
    network_name: str,
    model: str,
    reasoning_effort: str,
) -> list[str]:
    game_dir = rf.RUN_DIR / game
    return [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "-e",
        f"CODEX_API_KEY={os.environ['OPENAI_API_KEY']}",
        "--network",
        network_name,
        "-v",
        f"{game_dir / 'run'}:/home/user/run",
        rf.AGENT_IMAGE,
        "bash",
        "-c",
        (
            f"ulimit -v {rf.AGENT_VIRTUAL_MEMORY_LIMIT_KB} "
            '&& exec python3 agent.py --master "$1" --model "$2" --reasoning-effort "$3"'
        ),
        "agent.py",
        game,
        model,
        reasoning_effort,
    ]


def start_game(
    game: str,
    container_name: str,
    network_name: str,
    server_container_name: str,
    model: str,
    reasoning_effort: str,
) -> RunningGame:
    server_url = f"http://{server_container_name}:{rf.SERVER_PORT}"
    copy_game_inputs(game, server_url)
    command = docker_agent_command(game, container_name, network_name, model, reasoning_effort)
    rf.log_info("starting game %s with API key; container: %s", game, container_name)
    rf.LOGGER.info("agent command game=%s container=%s contains CODEX_API_KEY; command not logged", game, container_name)
    process = subprocess.Popen(
        command,
        cwd=rf.ROOT,
        stdin=subprocess.DEVNULL,
    )
    return RunningGame(
        game=game,
        container_name=container_name,
        process=process,
    )


def run_scheduler(config: RunConfig, container_names: rf.ContainerNames) -> int:
    running: dict[str, RunningGame] = {}
    server: rf.RunningServer | None = None
    stopping = False

    def handle_signal(signum: int, _frame: object) -> None:
        nonlocal stopping
        rf.LOGGER.warning("received signal %s; stopping containers", signum)
        rf.log_info("received signal %s; stopping containers", signum)
        stopping = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        rf.create_network(container_names.network)
        server = rf.start_server(
            container_names.server,
            container_names.network,
            config.tag,
            competition=config.competition,
        )
        server_start_failure = rf.wait_for_server_health(server, lambda: stopping)
        if server_start_failure is not None:
            return server_start_failure

        while not stopping:
            if server is None:
                raise RuntimeError("server was not started")
            server_return_code = server.process.poll()
            if server_return_code is not None:
                rf.LOGGER.error("server stopped exit_code=%s; stopping games", server_return_code)
                rf.log_info("server stopped with exit code %s; stopping games", server_return_code)
                rf.stop_all(None, running)
                return server_return_code or 1

            if not running:
                for game in config.games:
                    running[game] = start_game(
                        game,
                        container_names.games[game],
                        container_names.network,
                        container_names.server,
                        config.model,
                        config.reasoning_effort,
                    )

            for game, running_game in list(running.items()):
                return_code = running_game.process.poll()
                if return_code is None:
                    continue
                rf.log_info("game %s stopped with exit code %s", running_game.game, return_code)
                del running[game]

            if not running:
                rf.log_info("all games completed; stopping server")
                rf.stop_container(server.container_name, server.process, "server")
                return 0

            time.sleep(1.0)

        rf.stop_all(server, running)
        return 130
    finally:
        rf.stop_all(server, running)
        rf.remove_network(container_names.network)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ARC games in parallel with CODEX_API_KEY from OPENAI_API_KEY.")
    parser.add_argument(
        "--run-config",
        type=Path,
        default=rf.RUN_CONFIG,
        help=f"run config to read; default: {rf.RUN_CONFIG}",
    )
    parser.add_argument(
        "--competition",
        action="store_true",
        help="run the competition server instead of the default local server",
    )
    return parser.parse_args(argv)


def confirm_api_key_run() -> None:
    print(API_KEY_WARNING, flush=True)
    if input("> ") != "continue":
        raise RuntimeError("aborted")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        confirm_api_key_run()
        if not os.environ.get("ARC_API_KEY"):
            raise RuntimeError("ARC_API_KEY is not set in the environment")
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set in the environment")
        run_config = args.run_config.resolve()
        config = parse_run_config(run_config, competition=args.competition)
        container_names = rf.build_container_names(config.games)
        rf.verify_container_names_available(container_names)
        rf.verify_network_name_available(container_names.network)
        rf.prepare_run_root()
        rf.setup_runner_logging()
        rf.LOGGER.info("runner log started: %s", rf.RUNNER_LOG_PATH)
        rf.LOGGER.info(
            "run config=%s games=%s tag=%s competition=%s",
            run_config,
            config.games,
            config.tag,
            config.competition,
        )
        rf.LOGGER.info(
            "agent parameters model=%s reasoning_effort=%s",
            config.model,
            config.reasoning_effort,
        )
        rf.LOGGER.info(
            "docker names network=%s server=%s games=%s",
            container_names.network,
            container_names.server,
            container_names.games,
        )
        rf.build_dockers()
        verify_codex_api_key()
        exit_code = run_scheduler(config, container_names)
        rf.LOGGER.info("runner finished exit_code=%s", exit_code)
        return exit_code
    except Exception as exc:
        if rf.LOGGER.handlers:
            rf.LOGGER.exception("runner failed")
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
