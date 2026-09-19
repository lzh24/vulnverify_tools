#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

REGISTRY="${REGISTRY:-${IMAGE_REGISTRY:-}}"
IMAGE_NAMESPACE="${IMAGE_NAMESPACE:-vulnverify}"
IMAGE_NAME="${IMAGE_NAME:-vulnverify-tools}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
PUSH_LATEST="${PUSH_LATEST:-false}"

if [ -z "$REGISTRY" ]; then
    echo "REGISTRY or IMAGE_REGISTRY is required, for example: 192.168.10.20:5000" >&2
    exit 1
fi

FULL_IMAGE="${REGISTRY}/${IMAGE_NAMESPACE}/${IMAGE_NAME}:${IMAGE_TAG}"
LATEST_IMAGE="${REGISTRY}/${IMAGE_NAMESPACE}/${IMAGE_NAME}:latest"

if [ -n "${REGISTRY_USERNAME:-}" ] && [ -n "${REGISTRY_PASSWORD:-}" ]; then
    printf '%s' "$REGISTRY_PASSWORD" | docker login "$REGISTRY" --username "$REGISTRY_USERNAME" --password-stdin
fi

echo "Building image: $FULL_IMAGE"
docker build -t "$FULL_IMAGE" -f "$ROOT_DIR/Dockerfile" "$ROOT_DIR"

echo "Pushing image: $FULL_IMAGE"
docker push "$FULL_IMAGE"

if [ "$PUSH_LATEST" = "true" ]; then
    echo "Tagging and pushing: $LATEST_IMAGE"
    docker tag "$FULL_IMAGE" "$LATEST_IMAGE"
    docker push "$LATEST_IMAGE"
fi

echo "Image published successfully."
echo "IMAGE_REGISTRY=$REGISTRY"
echo "IMAGE_NAMESPACE=$IMAGE_NAMESPACE"
echo "IMAGE_NAME=$IMAGE_NAME"
echo "IMAGE_TAG=$IMAGE_TAG"
