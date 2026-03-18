"""
Security utilities for MCP server.

Provides input validation, sanitization, and security checks.
"""

import re
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Maximum request size (10MB)
MAX_REQUEST_SIZE = 10 * 1024 * 1024

# Maximum JSON depth
MAX_JSON_DEPTH = 20

# Patterns for potentially dangerous content
SQL_INJECTION_PATTERN = re.compile(
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|UNION|SCRIPT)\b|--|;|/\*|\*/)",
    re.IGNORECASE,
)

COMMAND_INJECTION_PATTERN = re.compile(
    r"[;&|`$(){}[\]<>]",
)


def sanitize_error_message(message: str, redact_api_keys: bool = True) -> str:
    """
    Sanitize error messages to prevent information leakage.

    Args:
        message: Error message to sanitize
        redact_api_keys: Whether to redact API keys from messages

    Returns:
        Sanitized error message
    """
    if not message:
        return "An error occurred"

    # Redact API keys (common patterns)
    if redact_api_keys:
        # Redact common API key patterns (api_key: value or api key value)
        message = re.sub(
            r"(api[_\s-]?key|apikey)\s*[:=]\s*['\"]?([a-zA-Z0-9_-]{10,})['\"]?",
            r"\1: [REDACTED]",
            message,
            flags=re.IGNORECASE,
        )
        # Redact API keys mentioned in text (e.g., "API key abc123 is invalid")
        # Match "api key" followed by alphanumeric string
        message = re.sub(
            r"(api[_\s-]?key|apikey)\s+([a-zA-Z0-9_-]{10,})",
            r"\1 [REDACTED]",
            message,
            flags=re.IGNORECASE,
        )
        # Redact long alphanumeric strings that might be keys (32+ chars)
        message = re.sub(
            r"\b([a-zA-Z0-9_-]{32,})\b",
            lambda m: "[REDACTED]" if len(m.group(1)) >= 32 else m.group(1),
            message,
        )

    # Remove file paths (potential information leakage)
    message = re.sub(r"/[^\s]+", "[PATH_REDACTED]", message)

    # Limit message length
    if len(message) > 500:
        message = message[:500] + "..."

    return message


def validate_request_size(body: bytes) -> bool:
    """
    Validate request body size.

    Args:
        body: Request body bytes

    Returns:
        True if size is acceptable, False otherwise
    """
    return len(body) <= MAX_REQUEST_SIZE


def sanitize_input(value: Any) -> Any:
    """
    Sanitize input value to prevent injection attacks.

    Args:
        value: Input value to sanitize

    Returns:
        Sanitized value
    """
    if isinstance(value, str):
        # Check for SQL injection patterns
        if SQL_INJECTION_PATTERN.search(value):
            logger.warning("Potential SQL injection pattern detected in input")
            # Don't reject, but log for monitoring
            # In production, you might want to reject these

        # Check for command injection patterns (be careful not to be too restrictive)
        # Only flag obviously dangerous patterns
        if COMMAND_INJECTION_PATTERN.search(value) and len(value) < 10:
            # Short strings with special chars might be commands
            logger.debug(f"Potential command injection pattern detected: {value[:20]}")

    elif isinstance(value, dict):
        return {k: sanitize_input(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [sanitize_input(item) for item in value]

    return value


def validate_jsonrpc_params(params: Optional[Dict[str, Any]]) -> tuple[bool, Optional[str]]:
    """
    Validate JSON-RPC parameters structure.

    Args:
        params: Parameters dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    if params is None:
        return True, None

    if not isinstance(params, dict):
        return False, "Params must be an object"

    # Check for excessive nesting (prevent DoS)
    def check_depth(obj: Any, depth: int = 0) -> bool:
        if depth > MAX_JSON_DEPTH:
            return False
        if isinstance(obj, dict):
            return all(check_depth(v, depth + 1) for v in obj.values())
        elif isinstance(obj, list):
            return all(check_depth(item, depth + 1) for item in obj)
        return True

    if not check_depth(params):
        return False, f"JSON structure exceeds maximum depth of {MAX_JSON_DEPTH}"

    return True, None


def redact_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Redact sensitive data from dictionaries (for logging).

    Args:
        data: Dictionary potentially containing sensitive data

    Returns:
        Dictionary with sensitive data redacted
    """
    redacted = {}
    sensitive_keys = [
        "api_key",
        "apikey",
        "api-key",
        "password",
        "secret",
        "token",
        "authorization",
        "auth",
    ]

    for key, value in data.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            redacted[key] = redact_sensitive_data(value)
        elif isinstance(value, list):
            redacted[key] = [redact_sensitive_data(item) if isinstance(item, dict) else item for item in value]
        else:
            redacted[key] = value

    return redacted
