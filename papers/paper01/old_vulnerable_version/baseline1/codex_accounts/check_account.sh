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

if login_status=$(docker run --rm -v "$codex_home_abs:/home/user/.codex" codex-agent codex login status 2>&1); then
  :
else
  status=$?
  echo "Error: codex login status command failed with exit code $status" >&2
  printf '%s\n' "$login_status" >&2
  exit "$status"
fi
if ! printf '%s\n' "$login_status" | grep -q "Logged in using ChatGPT"; then
  echo "Error: login status did not report ChatGPT login" >&2
  printf '%s\n' "$login_status" >&2
  exit 1
fi

if exec_output=$(docker run --rm -v "$codex_home_abs:/home/user/.codex" codex-agent codex exec --skip-git-repo-check "Respond with exactly: PING" 2>&1); then
  :
else
  status=$?
  echo "Error: codex exec PING command failed with exit code $status" >&2
  printf '%s\n' "$exec_output" >&2
  exit "$status"
fi
if ! printf '%s\n' "$exec_output" | grep -q '^PING$'; then
  echo "Error: codex exec did not return PING" >&2
  printf '%s\n' "$exec_output" >&2
  exit 1
fi

echo "Account OK: $codex_home"
