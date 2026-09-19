#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

BASE_URL="${BASE_URL:-http://localhost:8001}"
TOKEN="${TOKEN:-unified-tools-token-12345}"
MODE="${MODE:-burp}"
TARGET_URL="${TARGET_URL:-http://localhost:8001/health}"
REQUESTS="${REQUESTS:-50}"
CONCURRENCY="${CONCURRENCY:-5}"
TIMEOUT="${TIMEOUT:-60}"
INTERVAL="${INTERVAL:-0}"
INCLUDE_SCREENSHOT_BASE64="${INCLUDE_SCREENSHOT_BASE64:-false}"

ARGS="
--base-url $BASE_URL
--token $TOKEN
--mode $MODE
--target-url $TARGET_URL
--requests $REQUESTS
--concurrency $CONCURRENCY
--timeout $TIMEOUT
--interval $INTERVAL
"

if [ "$INCLUDE_SCREENSHOT_BASE64" = "true" ]; then
    ARGS="$ARGS --include-screenshot-base64"
fi

# shellcheck disable=SC2086
python3 "$ROOT_DIR/scripts/load_test_screenshot.py" $ARGS
