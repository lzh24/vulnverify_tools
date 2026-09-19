#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

URL="${1:-http://203.0.113.10:8883/}"
REQUESTS="${REQUESTS:-100}"
CONCURRENCY="${CONCURRENCY:-10}"
TIMEOUT="${TIMEOUT:-5}"
INTERVAL="${INTERVAL:-0}"
EXPECTED_STATUS="${EXPECTED_STATUS:-200}"
JSON_OUTPUT="${JSON_OUTPUT:-0}"

set -- \
    --url "$URL" \
    --requests "$REQUESTS" \
    --concurrency "$CONCURRENCY" \
    --timeout "$TIMEOUT" \
    --interval "$INTERVAL" \
    --expected-status "$EXPECTED_STATUS"

if [ "$JSON_OUTPUT" = "1" ]; then
    set -- "$@" --json
fi

python3 "$ROOT_DIR/scripts/check_endpoint_stability.py" "$@"
