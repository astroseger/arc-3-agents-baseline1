#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)

docker build --build-arg USER_ID="$(id -u)" --build-arg GROUP_ID="$(id -g)" -t codex-agent_sequence-no-executable-v1.2 -f "$script_dir/Dockerfile.agent" "$script_dir"
docker build --build-arg USER_ID="$(id -u)" --build-arg GROUP_ID="$(id -g)" -t game-server_sequence-no-executable-v1.2 -f "$script_dir/Dockerfile.server" "$script_dir"
docker build -t openai-proxy_sequence-no-executable-v1.2 -f "$script_dir/Dockerfile.proxy" "$script_dir"
