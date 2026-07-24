#!/usr/bin/env bash
# Production image validation for aiecs-office-mcp.
# Validates build, runtime imports, MCP endpoints, and image metadata.
# DocumentServer reachability is checked separately when infra is available.

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

IMAGE="${1:-aiecs-office-mcp:prod-test}"
CONTAINER="aiecs-office-mcp-prod-test"
PORT="${VALIDATE_PORT:-15040}"
HEALTH_URL="http://localhost:${PORT}/health"
MCP_URL="http://localhost:${PORT}/mcp/v1/"
MCP_HEADERS=(-H "Content-Type: application/json" -H "Accept: application/json, text/event-stream")

parse_mcp_response() {
  local body="$1"
  local content_type="$2"
  if [[ "${content_type}" == *"application/json"* ]]; then
    echo "${body}"
    return
  fi
  while IFS= read -r line; do
    if [[ "${line}" == data:\ * ]]; then
      echo "${line#data: }"
      return
    fi
  done <<< "${body}"
  echo "${body}"
}

mcp_post() {
  local payload="$1"
  local headers_file body_file code content_type
  headers_file="$(mktemp)"
  body_file="$(mktemp)"
  code="$(curl -sS -D "${headers_file}" -o "${body_file}" -w "%{http_code}" -X POST "${MCP_URL}" \
    "${MCP_HEADERS[@]}" \
    -d "${payload}")"
  content_type="$(awk -F': ' 'tolower($1)=="content-type"{print $2; exit}' "${headers_file}" | tr -d '\r')"
  if [[ "${code}" != "200" ]]; then
    echo "HTTP ${code}: $(cat "${body_file}")" >&2
    rm -f "${headers_file}" "${body_file}"
    return 1
  fi
  parse_mcp_response "$(cat "${body_file}")" "${content_type}"
  rm -f "${headers_file}" "${body_file}"
}

cleanup() {
  docker stop "${CONTAINER}" >/dev/null 2>&1 || true
  docker rm "${CONTAINER}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

pass() { echo -e "${GREEN}✓${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; exit 1; }
warn() { echo -e "${YELLOW}!${NC} $1"; }

echo "=========================================="
echo "Production image validation"
echo "Image: ${IMAGE}"
echo "=========================================="

echo
echo "[1/8] Building production image..."
docker build \
  -f Dockerfile.mcp \
  --target production \
  --build-arg APP_VERSION="$(awk '/^\[project\]/{p=1;next} /^\[/{p=0} p && /^version = /{gsub(/version = "|"/,""); print; exit}' pyproject.toml)" \
  --build-arg GIT_SHA="$(git rev-parse --short HEAD)" \
  --build-arg BUILD_DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
  -t "${IMAGE}" \
  . || fail "docker build failed"
pass "Image built"

echo
echo "[2/8] Checking image runs as non-root..."
USER_ID="$(docker run --rm --entrypoint id "${IMAGE}" -u)"
[[ "${USER_ID}" == "1000" || "${USER_ID}" == uid=1000* ]] || fail "expected uid 1000, got ${USER_ID}"
pass "Non-root user uid=${USER_ID}"

echo
echo "[3/8] Checking runtime imports..."
docker run --rm "${IMAGE}" python -c "
import fastapi, fastmcp, httpx, jwt, boto3, redis, bs4, google.cloud.storage
from aiecs.mcp.office_tool_adapter import OfficeToolAdapter
from aiecs.tools.office_tool import office_execute_builder
print('imports_ok')
" || fail "runtime import check failed"
pass "All runtime imports OK"

echo
echo "[4/8] Checking no build toolchain in image..."
docker run --rm --entrypoint sh "${IMAGE}" -c "! command -v gcc && ! command -v g++" \
  || fail "build toolchain should not be present in production image"
pass "No gcc/g++ in production image"

echo
echo "[5/8] Starting container..."
docker run -d \
  --name "${CONTAINER}" \
  -p "${PORT}:${PORT}" \
  -e MCP_HOST=0.0.0.0 \
  -e MCP_PORT="${PORT}" \
  -e MCP_LOG_LEVEL=info \
  -e DOCUMENTSERVER_URL=http://127.0.0.1:1 \
  -e DOCUMENTSERVER_JWT_SECRET=test-secret \
  "${IMAGE}" >/dev/null

for i in $(seq 1 30); do
  if curl -sf "${HEALTH_URL}" >/dev/null 2>&1; then
    break
  fi
  if [[ "$i" -eq 30 ]]; then
    docker logs "${CONTAINER}" 2>&1 | tail -30
    fail "health endpoint did not respond"
  fi
  sleep 1
done
pass "Container started, /health responding"

echo
echo "[6/8] MCP initialize..."
INIT_RESPONSE="$(mcp_post '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"validate","version":"1.0"}},"id":"test-1"}')" \
  || fail "initialize failed"
echo "${INIT_RESPONSE}" | grep -q '"result"' || fail "initialize failed: ${INIT_RESPONSE}"
pass "MCP initialize OK"

echo
echo "[7/8] MCP tools/list..."
TOOLS_RESPONSE="$(mcp_post '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":"test-2"}')" \
  || fail "tools/list failed"
echo "${TOOLS_RESPONSE}" | grep -q '"result"' || fail "tools/list failed: ${TOOLS_RESPONSE}"
TOOL_COUNT="$(echo "${TOOLS_RESPONSE}" | grep -o '"name"' | wc -l | tr -d ' ')"
[[ "${TOOL_COUNT}" -ge 1 ]] || fail "expected >=1 tools, got ${TOOL_COUNT}"
pass "tools/list OK (${TOOL_COUNT} tools)"

echo
echo "[8/8] Health payload check..."
HEALTH_JSON="$(curl -sf "${HEALTH_URL}")"
echo "${HEALTH_JSON}" | grep -q '"server_type"' || fail "unexpected health payload"
if echo "${HEALTH_JSON}" | grep -q '"documentserver_reachable": true'; then
  pass "DocumentServer reachable (full stack check passed)"
else
  warn "DocumentServer not reachable in isolated test (expected without infra)"
  pass "Health endpoint structure OK"
fi

echo
echo -e "${GREEN}=========================================="
echo "Production validation passed"
echo "==========================================${NC}"
