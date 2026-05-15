#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <codex-home-path> [codex-args...]" >&2
  exit 2
fi

codex_home=$1
shift

if [ ! -d "$codex_home" ]; then
  echo "Error: folder does not exist: $codex_home" >&2
  exit 1
fi

codex_home_abs=$(cd "$codex_home" && pwd -P)
run_dir_abs=$(pwd -P)

if [ "$#" -eq 0 ]; then
  set -- codex
else
  set -- codex "$@"
fi

docker run --rm -it \
  -v "$codex_home_abs:/home/user/.codex" \
  -v "$run_dir_abs:/home/user/run" \
  codex-agent \
  "$@"
