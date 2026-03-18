#!/bin/bash
# Deployment Validation Script for MCP Server
# Validates Docker build, health checks, and basic functionality

set -e

echo "=========================================="
echo "MCP Server Deployment Validation"
echo "=========================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="aiecs-office-mcp:latest"
CONTAINER_NAME="aiecs-office-mcp-test"
PORT=5055
HEALTH_URL="http://localhost:${PORT}/health"
MCP_URL="http://localhost:${PORT}/mcp/v1"

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"
    docker stop ${CONTAINER_NAME} 2>/dev/null || true
    docker rm ${CONTAINER_NAME} 2>/dev/null || true
}
trap cleanup EXIT

# Test 1: Build Docker image
echo -e "\n${YELLOW}[Test 1/10] Building Docker image...${NC}"
if docker build -f Dockerfile.mcp -t ${IMAGE_NAME} .; then
    echo -e "${GREEN}✓ Docker image built successfully${NC}"
else
    echo -e "${RED}✗ Docker build failed${NC}"
    exit 1
fi

# Test 2: Start container
echo -e "\n${YELLOW}[Test 2/10] Starting container...${NC}"
docker run -d \
    --name ${CONTAINER_NAME} \
    -p ${PORT}:5055 \
    -e MCP_PORT=5055 \
    -e MCP_LOG_LEVEL=info \
    ${IMAGE_NAME}

# Wait for container to start
echo "Waiting for container to start..."
sleep 5

# Check if container is running
if docker ps | grep -q ${CONTAINER_NAME}; then
    echo -e "${GREEN}✓ Container started successfully${NC}"
else
    echo -e "${RED}✗ Container failed to start${NC}"
    docker logs ${CONTAINER_NAME}
    exit 1
fi

# Test 3: Health check endpoint
echo -e "\n${YELLOW}[Test 3/10] Testing health check endpoint...${NC}"
for i in {1..30}; do
    if curl -s -f ${HEALTH_URL} > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Health check endpoint responding${NC}"
        HEALTH_RESPONSE=$(curl -s ${HEALTH_URL})
        echo "Response: ${HEALTH_RESPONSE}" | head -c 200
        echo ""
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ Health check endpoint not responding after 30 attempts${NC}"
        docker logs ${CONTAINER_NAME}
        exit 1
    fi
    sleep 1
done

# Test 4: MCP initialize endpoint
echo -e "\n${YELLOW}[Test 4/10] Testing MCP initialize endpoint...${NC}"
INIT_RESPONSE=$(curl -s -X POST ${MCP_URL} \
    -H "Content-Type: application/json" \
    -d '{
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": "test-1"
    }')

if echo ${INIT_RESPONSE} | grep -q "result"; then
    echo -e "${GREEN}✓ Initialize endpoint working${NC}"
    echo "Response: ${INIT_RESPONSE}" | head -c 200
    echo ""
else
    echo -e "${RED}✗ Initialize endpoint failed${NC}"
    echo "Response: ${INIT_RESPONSE}"
    exit 1
fi

# Test 5: MCP tools/list endpoint
echo -e "\n${YELLOW}[Test 5/10] Testing MCP tools/list endpoint...${NC}"
TOOLS_RESPONSE=$(curl -s -X POST ${MCP_URL} \
    -H "Content-Type: application/json" \
    -d '{
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": "test-2"
    }')

if echo ${TOOLS_RESPONSE} | grep -q "result"; then
    echo -e "${GREEN}✓ Tools/list endpoint working${NC}"
    TOOL_COUNT=$(echo ${TOOLS_RESPONSE} | grep -o '"name"' | wc -l)
    echo "Found ${TOOL_COUNT} tools"
else
    echo -e "${RED}✗ Tools/list endpoint failed${NC}"
    echo "Response: ${TOOLS_RESPONSE}"
    exit 1
fi

# Test 6: Invalid JSON-RPC request
echo -e "\n${YELLOW}[Test 6/10] Testing error handling (invalid request)...${NC}"
ERROR_RESPONSE=$(curl -s -X POST ${MCP_URL} \
    -H "Content-Type: application/json" \
    -d '{"invalid": "json"}')

if echo ${ERROR_RESPONSE} | grep -q "error"; then
    echo -e "${GREEN}✓ Error handling working correctly${NC}"
else
    echo -e "${RED}✗ Error handling failed${NC}"
    echo "Response: ${ERROR_RESPONSE}"
    exit 1
fi

# Test 7: Container logs check
echo -e "\n${YELLOW}[Test 7/10] Checking container logs...${NC}"
LOGS=$(docker logs ${CONTAINER_NAME} 2>&1 | tail -20)
if echo "${LOGS}" | grep -q -i "error\|exception\|traceback"; then
    echo -e "${YELLOW}⚠ Warnings/errors found in logs (may be expected):${NC}"
    echo "${LOGS}" | grep -i "error\|exception\|traceback" | head -5
else
    echo -e "${GREEN}✓ No critical errors in logs${NC}"
fi

# Test 8: Container resource usage
echo -e "\n${YELLOW}[Test 8/10] Checking container resource usage...${NC}"
STATS=$(docker stats --no-stream ${CONTAINER_NAME} --format "CPU: {{.CPUPerc}}, Memory: {{.MemUsage}}")
echo "${STATS}"

# Test 9: Environment variable configuration
echo -e "\n${YELLOW}[Test 9/10] Testing environment variable configuration...${NC}"
ENV_TEST=$(docker exec ${CONTAINER_NAME} python -c "from aiecs.mcp.config import get_server_config; config = get_server_config(); print(f'Port: {config.port}, Host: {config.host}')" 2>&1)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Environment configuration working${NC}"
    echo "${ENV_TEST}"
else
    echo -e "${RED}✗ Environment configuration failed${NC}"
    echo "${ENV_TEST}"
    exit 1
fi

# Test 10: Container health check
echo -e "\n${YELLOW}[Test 10/10] Checking container health status...${NC}"
HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' ${CONTAINER_NAME} 2>/dev/null || echo "no-healthcheck")
if [ "${HEALTH_STATUS}" = "healthy" ] || [ "${HEALTH_STATUS}" = "no-healthcheck" ]; then
    echo -e "${GREEN}✓ Container health status: ${HEALTH_STATUS}${NC}"
else
    echo -e "${RED}✗ Container health status: ${HEALTH_STATUS}${NC}"
    exit 1
fi

echo -e "\n${GREEN}=========================================="
echo "All deployment validation tests passed!"
echo "==========================================${NC}"
