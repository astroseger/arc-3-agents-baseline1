#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <account_name>" >&2
  exit 2
fi

account_name=$1

if [ -z "$account_name" ]; then
  echo "Error: account name must not be empty" >&2
  exit 2
fi

if ps_output=$(ps -aux | grep -- "$account_name" | grep codex_account | grep -v grep | grep -v "find_and_move_account.sh" || true); then
  :
else
  echo "Error: failed to check running processes for account: $account_name" >&2
  exit 1
fi

if [ -n "$ps_output" ]; then
  echo "Error: account appears to be in use by a codex_account process: $account_name" >&2
  printf '%s\n' "$ps_output" >&2
  exit 1
fi

mapfile -t matches < <(find ~/ -type d -name "$account_name")

if [ "${#matches[@]}" -eq 0 ]; then
  echo "Error: account folder not found under ~/ with name: $account_name" >&2
  exit 1
fi

if [ "${#matches[@]}" -gt 1 ]; then
  echo "Error: multiple account folders found for name: $account_name" >&2
  printf '%s\n' "${matches[@]}" >&2
  exit 1
fi

source_path=${matches[0]}

if [ ! -d "$source_path" ]; then
  echo "Error: found path is not a directory: $source_path" >&2
  exit 1
fi

if [ -e "./$account_name" ]; then
  echo "Error: destination already exists: ./$account_name" >&2
  exit 1
fi

mv -- "$source_path" ./
