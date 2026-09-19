#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

ENV_FILE="${1:-$ROOT_DIR/.env.swarm}"

if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

: "${STACK_NAME:=vulnverify-tools}"
: "${IMAGE_NAMESPACE:=vulnverify}"
: "${IMAGE_NAME:=vulnverify-tools}"
: "${IMAGE_TAG:=latest}"
: "${DEPLOY_MODE:=replicated}"
: "${SERVICE_REPLICAS:=3}"
: "${PUBLISHED_PORT:=8001}"
: "${LOG_LEVEL:=INFO}"

case "$DEPLOY_MODE" in
    global)
        STACK_FILE="${STACK_FILE:-$ROOT_DIR/docker-stack-global.yml}"
        ;;
    replicated)
        STACK_FILE="${STACK_FILE:-$ROOT_DIR/docker-stack-replicated.yml}"
        ;;
    *)
        echo "Unsupported DEPLOY_MODE: $DEPLOY_MODE. Use global or replicated." >&2
        exit 1
        ;;
esac

if [ -z "${IMAGE_REGISTRY:-}" ]; then
    echo "IMAGE_REGISTRY is required. Set it in $ENV_FILE or export it before running." >&2
    exit 1
fi

if [ -z "${TOOL_TOKEN:-}" ]; then
    echo "TOOL_TOKEN is required. Set it in $ENV_FILE or export it before running." >&2
    exit 1
fi

if [ ! -f "$STACK_FILE" ]; then
    echo "Stack file not found: $STACK_FILE" >&2
    exit 1
fi

FULL_IMAGE="${IMAGE_REGISTRY}/${IMAGE_NAMESPACE}/${IMAGE_NAME}:${IMAGE_TAG}"

echo "Deploying stack: $STACK_NAME"
echo "Using image: $FULL_IMAGE"
echo "Deploy mode: $DEPLOY_MODE"
if [ "$DEPLOY_MODE" = "replicated" ]; then
    echo "Replicas: $SERVICE_REPLICAS"
fi
echo "Published port: $PUBLISHED_PORT"

docker stack deploy --with-registry-auth -c "$STACK_FILE" "$STACK_NAME"

echo
echo "Current stack services:"
docker stack services "$STACK_NAME"

echo
echo "Current tasks:"
docker stack ps --no-trunc "$STACK_NAME"
