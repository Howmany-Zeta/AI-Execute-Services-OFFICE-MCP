"""
Security tests for MCP server.

Tests input validation, error message sanitization, API key protection, and security features.
"""

import pytest
from aiecs.mcp.security import (
    sanitize_error_message,
    validate_request_size,
    sanitize_input,
    validate_jsonrpc_params,
    redact_sensitive_data,
    MAX_REQUEST_SIZE,
)


class TestErrorMessageSanitization:
    """Test error message sanitization."""

    def test_sanitize_api_key_in_message(self):
        """Test that API keys are redacted from error messages."""
        message = "API key abc123def456ghi789 is invalid"
        sanitized = sanitize_error_message(message)
        assert "abc123def456ghi789" not in sanitized
        assert "[REDACTED]" in sanitized or "API key" in sanitized

    def test_sanitize_long_api_key(self):
        """Test that long alphanumeric strings are redacted."""
        message = "Error with key: abcdefghijklmnopqrstuvwxyz1234567890abcdefghijklmnop"
        sanitized = sanitize_error_message(message)
        assert len(sanitized) <= 500
        assert "[REDACTED]" in sanitized

    def test_sanitize_file_paths(self):
        """Test that file paths are redacted."""
        message = "Error reading file /home/user/secrets/api_key.txt"
        sanitized = sanitize_error_message(message)
        assert "/home/user/secrets/api_key.txt" not in sanitized
        assert "[PATH_REDACTED]" in sanitized

    def test_sanitize_message_length(self):
        """Test that messages are truncated if too long."""
        long_message = "A" * 1000
        sanitized = sanitize_error_message(long_message)
        assert len(sanitized) <= 503  # 500 + "..."

    def test_sanitize_empty_message(self):
        """Test handling of empty messages."""
        sanitized = sanitize_error_message("")
        assert sanitized == "An error occurred"


class TestRequestSizeValidation:
    """Test request size validation."""

    def test_validate_request_size_acceptable(self):
        """Test that acceptable request sizes pass validation."""
        small_body = b"x" * 1000
        assert validate_request_size(small_body) is True

    def test_validate_request_size_too_large(self):
        """Test that oversized requests fail validation."""
        large_body = b"x" * (MAX_REQUEST_SIZE + 1)
        assert validate_request_size(large_body) is False

    def test_validate_request_size_at_limit(self):
        """Test request size at the limit."""
        limit_body = b"x" * MAX_REQUEST_SIZE
        assert validate_request_size(limit_body) is True


class TestInputSanitization:
    """Test input sanitization."""

    def test_sanitize_string_input(self):
        """Test sanitizing string input."""
        # Should not modify normal strings
        normal_string = "normal text"
        assert sanitize_input(normal_string) == normal_string

    def test_sanitize_dict_input(self):
        """Test sanitizing dictionary input."""
        data = {"key": "value", "nested": {"inner": "data"}}
        sanitized = sanitize_input(data)
        assert sanitized == data

    def test_sanitize_list_input(self):
        """Test sanitizing list input."""
        data = ["item1", "item2", {"key": "value"}]
        sanitized = sanitize_input(data)
        assert sanitized == data


class TestJSONRPCParamsValidation:
    """Test JSON-RPC parameter validation."""

    def test_validate_none_params(self):
        """Test validation of None params."""
        is_valid, error = validate_jsonrpc_params(None)
        assert is_valid is True
        assert error is None

    def test_validate_dict_params(self):
        """Test validation of dict params."""
        params = {"name": "test", "arguments": {}}
        is_valid, error = validate_jsonrpc_params(params)
        assert is_valid is True
        assert error is None

    def test_validate_non_dict_params(self):
        """Test validation of non-dict params."""
        is_valid, error = validate_jsonrpc_params("not a dict")
        assert is_valid is False
        assert error is not None

    def test_validate_deeply_nested_params(self):
        """Test validation of deeply nested params."""
        # Create deeply nested structure (exceeds MAX_JSON_DEPTH of 20)
        def create_nested(depth):
            if depth == 0:
                return "value"
            return {"level": create_nested(depth - 1)}

        params = create_nested(25)  # Exceeds limit
        is_valid, error = validate_jsonrpc_params(params)
        assert is_valid is False
        assert "depth" in error.lower()


class TestSensitiveDataRedaction:
    """Test sensitive data redaction."""

    def test_redact_api_key(self):
        """Test redacting API keys."""
        data = {"api_key": "secret123", "other": "data"}
        redacted = redact_sensitive_data(data)
        assert redacted["api_key"] == "[REDACTED]"
        assert redacted["other"] == "data"

    def test_redact_password(self):
        """Test redacting passwords."""
        data = {"username": "user", "password": "secret"}
        redacted = redact_sensitive_data(data)
        assert redacted["password"] == "[REDACTED]"
        assert redacted["username"] == "user"

    def test_redact_nested_data(self):
        """Test redacting nested sensitive data."""
        data = {"config": {"api_key": "secret", "public": "value"}}
        redacted = redact_sensitive_data(data)
        assert redacted["config"]["api_key"] == "[REDACTED]"
        assert redacted["config"]["public"] == "value"

    def test_redact_multiple_sensitive_keys(self):
        """Test redacting multiple sensitive keys."""
        data = {
            "api_key": "key1",
            "password": "pass1",
            "token": "token1",
            "secret": "secret1",
            "normal": "value",
        }
        redacted = redact_sensitive_data(data)
        assert all(redacted[k] == "[REDACTED]" for k in ["api_key", "password", "token", "secret"])
        assert redacted["normal"] == "value"
