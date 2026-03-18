#!/bin/bash
# MCP Endpoint Testing Script
# Tests Office MCP protocol endpoints with sample requests

set -e

BASE_URL="${1:-http://localhost:5040}"
MCP_URL="${BASE_URL}/mcp/v1/"
HEALTH_URL="${BASE_URL}/health"
CURL_OPTS="-s -L --connect-timeout 5 --max-time 30"

echo "=========================================="
echo "Office MCP Server Endpoint Testing"
echo "=========================================="
echo "Base URL: ${BASE_URL}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test health endpoint
echo -e "\n${YELLOW}[Test] Health Check Endpoint${NC}"
HEALTH_RESPONSE=$(curl ${CURL_OPTS} ${HEALTH_URL}) || {
    echo -e "${RED}✗ Cannot connect to ${HEALTH_URL}${NC}"
    echo "  Is the MCP server running? Try: python -m aiecs.main_mcp"
    echo "  Or with docker-compose: docker-compose -f docker-compose.mcp.yml up -d"
    exit 1
}
if echo ${HEALTH_RESPONSE} | grep -q "status"; then
    echo -e "${GREEN}✓ Health endpoint working${NC}"
    if echo ${HEALTH_RESPONSE} | grep -q "office_mcp"; then
        echo -e "${GREEN}✓ Server type: office_mcp${NC}"
    fi
    echo "${HEALTH_RESPONSE}" | python3 -m json.tool 2>/dev/null || echo "${HEALTH_RESPONSE}"
else
    echo -e "${RED}✗ Health endpoint failed${NC}"
    exit 1
fi

# Test initialize (MCP requires params: protocolVersion, capabilities, clientInfo)
echo -e "\n${YELLOW}[Test] Initialize Method${NC}"
INIT_RESPONSE=$(curl ${CURL_OPTS} -X POST ${MCP_URL} \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"}
        },
        "id": "init-1"
    }')
if echo ${INIT_RESPONSE} | grep -q "result"; then
    echo -e "${GREEN}✓ Initialize method working${NC}"
    echo "${INIT_RESPONSE}" | python3 -m json.tool 2>/dev/null || echo "${INIT_RESPONSE}"
else
    echo -e "${RED}✗ Initialize method failed${NC}"
    echo "${INIT_RESPONSE}"
    exit 1
fi

# Test tools/list
echo -e "\n${YELLOW}[Test] Tools/List Method${NC}"
TOOLS_RESPONSE=$(curl ${CURL_OPTS} -X POST ${MCP_URL} \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": "tools-list-1"
    }')
if echo ${TOOLS_RESPONSE} | grep -q "result"; then
    echo -e "${GREEN}✓ Tools/list method working${NC}"
    TOOL_COUNT=$(echo ${TOOLS_RESPONSE} | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('result', {}).get('tools', [])))" 2>/dev/null || echo "0")
    echo "Found ${TOOL_COUNT} tools"
    if echo ${TOOLS_RESPONSE} | grep -q "office_execute_builder"; then
        echo -e "${GREEN}✓ office_execute_builder tool present${NC}"
    else
        echo -e "${YELLOW}⚠ office_execute_builder not found in tools list${NC}"
    fi
    echo "${TOOLS_RESPONSE}" | python3 -m json.tool 2>/dev/null | head -30 || echo "${TOOLS_RESPONSE}" | head -30
else
    echo -e "${RED}✗ Tools/list method failed${NC}"
    echo "${TOOLS_RESPONSE}"
    exit 1
fi

# Test tools/call with office_execute_builder
echo -e "\n${YELLOW}[Test] Tools/Call Method (office_execute_builder)${NC}"
CALL_RESPONSE=$(curl ${CURL_OPTS} -X POST ${MCP_URL} \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "office_execute_builder",
            "arguments": {
                "script": "builder.CreateFile(\"docx\");"
            }
        },
        "id": "tools-call-1"
    }')
if echo ${CALL_RESPONSE} | grep -q "result"; then
    echo -e "${GREEN}✓ Tools/call method working${NC}"
    echo "${CALL_RESPONSE}" | python3 -m json.tool 2>/dev/null | head -40 || echo "${CALL_RESPONSE}" | head -40
else
    echo -e "${RED}✗ Tools/call method failed${NC}"
    echo "${CALL_RESPONSE}"
    exit 1
fi

# Test invalid method
echo -e "\n${YELLOW}[Test] Invalid Method (Error Handling)${NC}"
ERROR_RESPONSE=$(curl ${CURL_OPTS} -X POST ${MCP_URL} \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{
        "jsonrpc": "2.0",
        "method": "invalid/method",
        "id": "error-test-1"
    }')
if echo ${ERROR_RESPONSE} | grep -q "error"; then
    echo -e "${GREEN}✓ Error handling working${NC}"
    echo "${ERROR_RESPONSE}" | python3 -m json.tool 2>/dev/null || echo "${ERROR_RESPONSE}"
else
    echo -e "${RED}✗ Error handling failed${NC}"
    echo "${ERROR_RESPONSE}"
    exit 1
fi

# Test invalid JSON
echo -e "\n${YELLOW}[Test] Invalid JSON (Parse Error)${NC}"
PARSE_ERROR=$(curl ${CURL_OPTS} -X POST ${MCP_URL} \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d 'invalid json')
if echo ${PARSE_ERROR} | grep -q "error"; then
    echo -e "${GREEN}✓ Parse error handling working${NC}"
    echo "${PARSE_ERROR}" | python3 -m json.tool 2>/dev/null || echo "${PARSE_ERROR}"
else
    echo -e "${RED}✗ Parse error handling failed${NC}"
    echo "${PARSE_ERROR}"
    exit 1
fi

echo -e "\n${GREEN}=========================================="
echo "All endpoint tests passed!"
echo "==========================================${NC}"
