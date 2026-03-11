#!/usr/bin/env bash
set -euo pipefail

URL="${1:-https://thr.onewo.com:8443/ierp/?formId=home_page}"

if ! command -v playwright >/dev/null 2>&1; then
  echo "playwright CLI not found. Install with: pip install -r automation/requirements.txt"
  exit 1
fi

playwright codegen --ignore-https-errors "$URL"
