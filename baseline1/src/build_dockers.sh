#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)

docker build --build-arg USER_ID="$(id -u)" --build-arg GROUP_ID="$(id -g)" -t codex-agent -f "$script_dir/Dockerfile.agent" "$script_dir"
docker build --build-arg USER_ID="$(id -u)" --build-arg GROUP_ID="$(id -g)" -t arc-server-competition -f "$script_dir/Dockerfile.server" "$script_dir"
