#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)

docker build --build-arg USER_ID="$(id -u)" --build-arg GROUP_ID="$(id -g)" -t codex-agent-sequence-exactly-ws-v-1-3 -f "$script_dir/Dockerfile.agent" "$script_dir"
docker build --build-arg USER_ID="$(id -u)" --build-arg GROUP_ID="$(id -g)" -t game-server-sequence-exactly-ws-v-1-3 -f "$script_dir/Dockerfile.server" "$script_dir"
docker build -t openai-proxy-sequence-exactly-ws-v-1-3 -f "$script_dir/Dockerfile.proxy" "$script_dir"
