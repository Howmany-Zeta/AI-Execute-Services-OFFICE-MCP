#!/usr/bin/env bash
# Build and publish aiecs-office-mcp to Google Artifact Registry.
#
# Tag scheme (all pushed on release):
#   <version>              — semver from pyproject.toml [project].version (immutable release)
#   <version>-<git-sha>    — semver + short commit (recommended for prod pin)
#   <git-sha>              — short commit only (immutable build id)
#   latest                 — rolling pointer to most recent release (optional, use --no-latest)
#
# Usage:
#   ./scripts/publish_artifact_registry.sh              # build + push all tags
#   ./scripts/publish_artifact_registry.sh --dry-run    # print tags only
#   ./scripts/publish_artifact_registry.sh --no-latest  # skip :latest push
#   ./scripts/publish_artifact_registry.sh --push-only  # skip build, push existing local tags

set -euo pipefail

REGISTRY="us-central1-docker.pkg.dev/ca-biz-kjmsdw-y59m/aiecs-mcp-servers"
IMAGE_NAME="aiecs-office-mcp"
DOCKERFILE="Dockerfile.mcp"
TARGET="production"

DRY_RUN=false
PUSH_LATEST=true
PUSH_ONLY=false

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --no-latest) PUSH_LATEST=false ;;
    --push-only) PUSH_ONLY=true ;;
    -h|--help)
      sed -n '2,15p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: must run from git checkout" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "WARNING: working tree has uncommitted changes; image tags will still use HEAD commit." >&2
fi

APP_VERSION="$(awk '/^\[project\]/{p=1;next} /^\[/{p=0} p && /^version = /{gsub(/version = "|"/,""); print; exit}' pyproject.toml)"
GIT_SHA="$(git rev-parse --short HEAD)"
BUILD_DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}"

TAGS=(
  "${APP_VERSION}"
  "${APP_VERSION}-${GIT_SHA}"
  "${GIT_SHA}"
)
if [[ "$PUSH_LATEST" == "true" ]]; then
  TAGS+=("latest")
fi

echo "=========================================="
echo "aiecs-office-mcp Artifact Registry publish"
echo "=========================================="
echo "Registry : ${REGISTRY}"
echo "Image    : ${IMAGE_NAME}"
echo "Version  : ${APP_VERSION}"
echo "Git SHA  : ${GIT_SHA}"
echo "Built at : ${BUILD_DATE}"
echo "Tags     : ${TAGS[*]}"
echo

if [[ "$DRY_RUN" == "true" ]]; then
  echo "[dry-run] skipping build and push"
  exit 0
fi

if [[ "$PUSH_ONLY" != "true" ]]; then
  BUILD_ARGS=(
    --file "${DOCKERFILE}"
    --target "${TARGET}"
    --build-arg "APP_VERSION=${APP_VERSION}"
    --build-arg "GIT_SHA=${GIT_SHA}"
    --build-arg "BUILD_DATE=${BUILD_DATE}"
  )
  for tag in "${TAGS[@]}"; do
    BUILD_ARGS+=(--tag "${FULL_IMAGE}:${tag}")
  done
  BUILD_ARGS+=(.)

  echo "[1/3] Building production image..."
  docker build "${BUILD_ARGS[@]}"
fi

echo "[2/3] Authenticating Docker to Artifact Registry..."
gcloud auth configure-docker us-central1-docker.pkg.dev --quiet

echo "[3/3] Pushing tags..."
for tag in "${TAGS[@]}"; do
  echo "  -> ${FULL_IMAGE}:${tag}"
  docker push "${FULL_IMAGE}:${tag}"
done

echo
echo "Publish complete."
echo "Recommended prod pin: ${FULL_IMAGE}:${APP_VERSION}-${GIT_SHA}"
echo "Rolling tag         : ${FULL_IMAGE}:latest"
