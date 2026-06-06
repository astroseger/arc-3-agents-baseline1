#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <codex-home-path>" >&2
  exit 2
fi

codex_home=$1

if [ -e "$codex_home" ]; then
  echo "Error: path already exists: $codex_home" >&2
  exit 1
fi

mkdir -p "$codex_home"
codex_home_abs=$(cd "$codex_home" && pwd -P)

docker run --rm -it -v "$codex_home_abs:/home/user/.codex" --network host codex-agent codex login --device-auth
