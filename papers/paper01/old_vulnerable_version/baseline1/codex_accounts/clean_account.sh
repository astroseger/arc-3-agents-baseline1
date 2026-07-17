#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <codex-home-path>" >&2
  exit 2
fi

codex_home=$1

if [ ! -d "$codex_home" ]; then
  echo "Error: folder does not exist: $codex_home" >&2
  exit 1
fi

codex_home_abs=$(cd "$codex_home" && pwd -P)

if [ "$codex_home_abs" = "/" ]; then
  echo "Error: refusing to clean root directory" >&2
  exit 1
fi

if [ ! -f "$codex_home_abs/auth.json" ]; then
  echo "Error: auth.json does not exist in account folder: $codex_home_abs" >&2
  exit 1
fi

find "$codex_home_abs" -mindepth 1 -maxdepth 1 ! -name auth.json -exec rm -rf -- {} +
