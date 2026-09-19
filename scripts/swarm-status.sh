#!/bin/sh
set -eu

STACK_NAME="${1:-vulnverify-tools}"
SERVICE_NAME="${2:-}"

docker stack services "$STACK_NAME"
echo
docker stack ps "$STACK_NAME"

if [ -n "$SERVICE_NAME" ]; then
    echo
    docker service logs --tail 100 -f "${STACK_NAME}_${SERVICE_NAME}"
fi
