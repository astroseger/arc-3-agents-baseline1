#!/usr/bin/env bash
set -euo pipefail

INPUT_FILE="${1:-scorecard_id.txt}"

SCORECARD_ID="$(tr -d '[:space:]' < "$INPUT_FILE")"
URL="https://arcprize.org/api/v3/scorecards/${SCORECARD_ID}"

wget -qO- "$URL" | python3 -m json.tool
