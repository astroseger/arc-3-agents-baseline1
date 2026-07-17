from __future__ import annotations

import logging
import os
import re
import subprocess
import time
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import yaml


ROOT = Path(__file__).resolve().parent
RUN_CONFIG = ROOT / "run_config.yaml"
RUN_DIR = ROOT / "run"
RUNNER_LOG_PATH = RUN_DIR / "runner.log"
SERVER_DATA_DIR = RUN_DIR / "server"
AGENT_SRC_DIR = ROOT / "src" / "agent"
CODEX_ACCOUNTS_DIR = ROOT / "codex_accounts"
BUILD_DOCKERS_SCRIPT = ROOT / "src" / "build_dockers.sh"

SERVER_IMAGE = "game-server-sequence-no-exactly-v-1-2"
AGENT_IMAGE = "codex-agent-sequence-no-exactly-v-1-2"
PROXY_IMAGE = "openai-proxy-sequence-no-exactly-v-1-2"
SERVER_PORT = 8879
PROXY_PORT = 3128
AGENT_VIRTUAL_MEMORY_LIMIT_KB = 6_000_000
LOGGER = logging.getLogger("arc-runner")
CLIENT_SERVER_URL_TEMPLATE_LINE = 'SERVER_URL = os.environ.get("GAME_SERVER_URL", "http://127.0.0.1:8879")'


@dataclass(frozen=True)
class ContainerNames:
    internal_network: str
    internet_network: str
    proxy: str
    server: str
    games: dict[str, str]


@dataclass
class RunningServer:
    container_name: str
    process: subprocess.Popen[bytes]


def set_logger_name(name: str) -> None:
    global LOGGER
    LOGGER = logging.getLogger(name)


def setup_runner_logging() -> None:
    if RUNNER_LOG_PATH.exists():
        raise RuntimeError(f"runner log already exists: {RUNNER_LOG_PATH}")

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    file_handler = logging.FileHandler(RUNNER_LOG_PATH, mode="x", encoding="utf-8")
    file_handler.setFormatter(formatter)

    LOGGER.handlers.clear()
    LOGGER.setLevel(logging.INFO)
    LOGGER.addHandler(file_handler)
    LOGGER.propagate = False


def log_info(message: str, *args: object) -> None:
    text = message % args if args else message
    print(text, flush=True)
    LOGGER.info(message, *args)


def load_run_config(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise RuntimeError(f"run config does not exist: {path}")

    with path.open("r", encoding="utf-8") as config_file:
        loaded_config = yaml.safe_load(config_file)

    if not isinstance(loaded_config, dict):
        raise RuntimeError(f"{path} must contain a YAML mapping")

    return loaded_config


def parse_string_list(config: dict[str, object], key: str, path: Path) -> list[str]:
    value = config.get(key)
    if not isinstance(value, list) or not value:
        raise RuntimeError(f"{key} in {path} must be a non-empty list")
    if not all(isinstance(item, str) and item for item in value):
        raise RuntimeError(f"{key} in {path} must contain only non-empty strings")
    return value


def parse_optional_string(
    config: dict[str, object],
    key: str,
    path: Path,
    *,
    default: str,
) -> str:
    value = config.get(key, default)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{key} in {path} must be a non-empty string")
    return value


def parse_tag(config: dict[str, object], path: Path) -> str:
    tag = config.get("tag")
    if not isinstance(tag, str) or not tag:
        raise RuntimeError(f"tag in {path} must be a non-empty string")
    return tag


def validate_unique_games(games: list[str]) -> None:
    seen_games: set[str] = set()
    duplicate_games: list[str] = []
    for game in games:
        if game in seen_games:
            duplicate_games.append(game)
        seen_games.add(game)
    if duplicate_games:
        duplicates = " ".join(sorted(set(duplicate_games)))
        raise RuntimeError(f"games must be unique; duplicates: {duplicates}")


def prepare_run_root() -> None:
    if RUN_DIR.exists():
        raise RuntimeError(f"run folder already exists: {RUN_DIR}")
    SERVER_DATA_DIR.mkdir(parents=True)


def verify_agent_source_dir() -> None:
    if not AGENT_SRC_DIR.is_dir():
        raise RuntimeError(f"agent source folder does not exist: {AGENT_SRC_DIR}")


def configure_client_server_url(agent_run_dir: Path, server_url: str) -> None:
    client_path = agent_run_dir / "workspace_init" / "client" / "client.py"
    if not client_path.is_file():
        raise RuntimeError(f"client script does not exist in copied agent source: {client_path}")

    lines = client_path.read_text(encoding="utf-8").splitlines()
    matching_line_count = sum(line == CLIENT_SERVER_URL_TEMPLATE_LINE for line in lines)
    if matching_line_count != 1:
        raise RuntimeError(
            f"expected exactly one client SERVER_URL template line in {client_path}; "
            f"found {matching_line_count}"
        )

    replacement_line = f"SERVER_URL = {json.dumps(server_url)}"
    updated_lines = [
        replacement_line if line == CLIENT_SERVER_URL_TEMPLATE_LINE else line
        for line in lines
    ]
    client_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")


def docker_name(prefix: str, name: str) -> str:
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "-", name).strip("-")
    if not safe_name:
        safe_name = "container"
    return f"{prefix}-{os.getpid()}-{safe_name}"


def build_game_id_mapping(games: list[str]) -> dict[str, str]:
    return {uuid4().hex: game for game in games}


def build_container_names(games: list[str]) -> ContainerNames:
    return ContainerNames(
        internal_network=docker_name("arc-internal-network", "competition"),
        internet_network=docker_name("arc-internet-network", "competition"),
        proxy=docker_name("arc-proxy", "competition"),
        server=docker_name("arc-server", "competition"),
        games={game: docker_name("arc-agent", game) for game in games},
    )


def container_exists(container_name: str) -> bool:
    result = subprocess.run(
        ["docker", "container", "inspect", container_name],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def verify_container_names_available(container_names: ContainerNames) -> None:
    all_names = [container_names.proxy, container_names.server, *container_names.games.values()]
    existing_names = [name for name in all_names if container_exists(name)]
    if existing_names:
        names = " ".join(existing_names)
        raise RuntimeError(f"docker container name already exists: {names}")


def network_exists(network_name: str) -> bool:
    result = subprocess.run(
        ["docker", "network", "inspect", network_name],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def verify_network_name_available(network_name: str) -> None:
    if network_exists(network_name):
        raise RuntimeError(f"docker network name already exists: {network_name}")


def verify_network_names_available(container_names: ContainerNames) -> None:
    verify_network_name_available(container_names.internal_network)
    verify_network_name_available(container_names.internet_network)


def build_dockers() -> None:
    if not BUILD_DOCKERS_SCRIPT.is_file():
        raise RuntimeError(f"docker build script does not exist: {BUILD_DOCKERS_SCRIPT}")

    log_info("building docker images with %s", BUILD_DOCKERS_SCRIPT)
    result = subprocess.run(["bash", str(BUILD_DOCKERS_SCRIPT)], cwd=ROOT, check=False)
    if result.returncode != 0:
        LOGGER.error("docker build failed exit_code=%s", result.returncode)
        raise RuntimeError(f"docker build failed with exit code {result.returncode}")
    LOGGER.info("docker build completed")


def create_network(network_name: str, *, internal: bool = False) -> None:
    internal_label = " internal" if internal else ""
    log_info("creating%s docker network: %s", internal_label, network_name)
    command = ["docker", "network", "create"]
    if internal:
        command.append("--internal")
    command.append(network_name)
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        LOGGER.error("docker network create failed network=%s exit_code=%s", network_name, result.returncode)
        raise RuntimeError(f"docker network create failed for {network_name} with exit code {result.returncode}")


def remove_network(network_name: str) -> None:
    if not network_exists(network_name):
        return

    log_info("removing docker network: %s", network_name)
    result = subprocess.run(
        ["docker", "network", "rm", network_name],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        LOGGER.error("docker network rm failed network=%s exit_code=%s", network_name, result.returncode)
        log_info("docker network removal failed for %s with exit code %s", network_name, result.returncode)


def connect_network(network_name: str, container_name: str) -> None:
    log_info("connecting container %s to docker network: %s", container_name, network_name)
    result = subprocess.run(
        ["docker", "network", "connect", network_name, container_name],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        LOGGER.error(
            "docker network connect failed network=%s container=%s exit_code=%s",
            network_name,
            container_name,
            result.returncode,
        )
        raise RuntimeError(
            f"docker network connect failed for {container_name} to {network_name} "
            f"with exit code {result.returncode}"
        )


def wait_for_container_created(
    container_name: str,
    process: subprocess.Popen[bytes],
    name: str,
    wait_seconds: float = 10.0,
) -> None:
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(f"{name} container exited before startup with exit code {return_code}")
        if container_exists(container_name):
            return
        time.sleep(0.1)
    raise RuntimeError(f"timed out waiting for {name} container to be created: {container_name}")


def docker_proxy_command(container_name: str, network_name: str) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "--network",
        network_name,
        PROXY_IMAGE,
    ]


def start_proxy(container_name: str, internet_network: str, internal_network: str) -> RunningServer:
    command = docker_proxy_command(container_name, internet_network)
    log_info("starting proxy; container: %s", container_name)
    LOGGER.info("proxy command: %s", command)
    process = subprocess.Popen(command, cwd=ROOT)
    wait_for_container_created(container_name, process, "proxy")
    connect_network(internal_network, container_name)
    return RunningServer(container_name=container_name, process=process)


def proxy_env_args(proxy_container_name: str, server_container_name: str) -> list[str]:
    proxy_url = f"http://{proxy_container_name}:{PROXY_PORT}"
    no_proxy = f"{server_container_name},{server_container_name}:{SERVER_PORT},localhost,127.0.0.1,::1"
    return [
        "-e",
        f"HTTP_PROXY={proxy_url}",
        "-e",
        f"HTTPS_PROXY={proxy_url}",
        "-e",
        f"ALL_PROXY={proxy_url}",
        "-e",
        f"http_proxy={proxy_url}",
        "-e",
        f"https_proxy={proxy_url}",
        "-e",
        f"all_proxy={proxy_url}",
        "-e",
        f"NO_PROXY={no_proxy}",
        "-e",
        f"no_proxy={no_proxy}",
    ]


def docker_server_command(
    container_name: str,
    network_name: str,
    tag: str,
    competition: bool,
    game_id_mapping: dict[str, str],
) -> list[str]:
    command = [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "--network",
        network_name,
        "-e",
        "ARC_SERVER_HOST=0.0.0.0",
        "-e",
        f"ARC_SERVER_PORT={SERVER_PORT}",
        "-e",
        "ARC_API_KEY",
        "-e",
        f"GAME_ID_MAPPING_JSON={json.dumps(game_id_mapping, separators=(',', ':'))}",
        "-v",
        f"{SERVER_DATA_DIR}:/data",
    ]

    command.extend([
        SERVER_IMAGE,
        "python",
    ])
    if competition:
        command.extend(["server/server_competition.py", "--tag", tag])
    else:
        command.append("server/server.py")
    return command


def start_server(
    container_name: str,
    network_name: str,
    tag: str,
    competition: bool = False,
    extra_network_name: str | None = None,
    game_id_mapping: dict[str, str] | None = None,
) -> RunningServer:
    if game_id_mapping is None:
        raise RuntimeError("game_id_mapping is required to start the server")
    command = docker_server_command(container_name, network_name, tag, competition, game_id_mapping)
    mode = "competition" if competition else "local"
    log_info("starting %s server; data dir: %s; tag: %s; container: %s", mode, SERVER_DATA_DIR, tag, container_name)
    LOGGER.info("server command: %s", command)
    process = subprocess.Popen(command, cwd=ROOT)
    server = RunningServer(container_name=container_name, process=process)
    if extra_network_name is not None:
        wait_for_container_created(container_name, process, "server")
        connect_network(extra_network_name, container_name)
    return server


def health_check_ok(server: RunningServer) -> bool:
    result = subprocess.run(
        [
            "docker",
            "exec",
            server.container_name,
            "python",
            "-c",
            (
                "import sys, urllib.request; "
                f"response = urllib.request.urlopen('http://127.0.0.1:{SERVER_PORT}/health', timeout=5.0); "
                "sys.exit(0 if 200 <= response.status < 300 else 1)"
            ),
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def wait_for_server_health(
    server: RunningServer,
    should_stop: Callable[[], bool],
    wait_seconds: float = 30.0,
) -> int | None:
    while True:
        log_info("waiting %.0fs before server health check", wait_seconds)
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            if should_stop():
                return 130

            server_return_code = server.process.poll()
            if server_return_code is not None:
                LOGGER.error("server stopped before becoming healthy exit_code=%s", server_return_code)
                log_info("server stopped before becoming healthy with exit code %s", server_return_code)
                return server_return_code or 1

            time.sleep(min(1.0, deadline - time.monotonic()))

        server_return_code = server.process.poll()
        if server_return_code is not None:
            LOGGER.error("server stopped before becoming healthy exit_code=%s", server_return_code)
            log_info("server stopped before becoming healthy with exit code %s", server_return_code)
            return server_return_code or 1

        health_url = f"docker exec {server.container_name} http://127.0.0.1:{SERVER_PORT}/health"
        if health_check_ok(server):
            log_info("server health check passed: %s", health_url)
            return None

        LOGGER.warning("server health check failed url=%s", health_url)
        log_info("server health check failed: %s", health_url)


def stop_container(
    container_name: str,
    process: subprocess.Popen[bytes],
    name: str,
    timeout: int = 20,
) -> None:
    if process.poll() is not None:
        return

    log_info("stopping %s", name)
    stop_result = subprocess.run(
        ["docker", "stop", "--timeout", str(timeout), container_name],
        cwd=ROOT,
        check=False,
    )
    if stop_result.returncode != 0 and process.poll() is None:
        LOGGER.error("docker stop failed for %s exit_code=%s; killing container", name, stop_result.returncode)
        subprocess.run(["docker", "kill", container_name], cwd=ROOT, check=False)

    try:
        process.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        LOGGER.error("killing docker client for %s after timeout", name)
        log_info("killing docker client for %s after timeout", name)
        process.kill()
        process.wait()


def stop_all(
    server: RunningServer | None,
    running: dict[str, Any],
    proxy: RunningServer | None = None,
) -> None:
    for running_game in list(running.values()):
        stop_container(
            running_game.container_name,
            running_game.process,
            f"game {running_game.game}",
        )
    running.clear()

    if server is not None:
        stop_container(server.container_name, server.process, "server")
    if proxy is not None:
        stop_container(proxy.container_name, proxy.process, "proxy")
