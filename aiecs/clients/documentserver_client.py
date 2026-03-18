"""
DocumentServer (ONLYOFFICE) API client.

Uses httpx.AsyncClient for async HTTP calls. Supports Builder API, Conversion API,
Command API, and health check. JWT signing: Builder uses header; Conversion/Command
use body token when JWT_IN_BODY=true.
"""

import logging
import time
from functools import lru_cache
from typing import Any, Dict, Optional

import httpx
import jwt

logger = logging.getLogger(__name__)

# Timeouts (seconds)
BUILDER_TIMEOUT = 120
CONVERT_TIMEOUT = 60
COMMAND_TIMEOUT = 10
HEALTHCHECK_TIMEOUT = 5.0


def build_jwt(payload: dict, secret: str) -> str:
    """
    Sign payload with JWT. Does not modify the original payload.

    Args:
        payload: Request payload to sign
        secret: JWT secret key

    Returns:
        JWT token string
    """
    signed = {**payload, "iat": int(time.time())}
    return jwt.encode(signed, secret, algorithm="HS256")


def _get_config() -> Dict[str, Any]:
    """Load DocumentServer config from environment."""
    from aiecs.config import get_documentserver_config

    cfg = get_documentserver_config()
    return {
        "url": cfg.url.rstrip("/"),
        "jwt_secret": cfg.jwt_secret,
        "jwt_in_body": cfg.jwt_in_body,
    }


class DocumentServerClient:
    """
    Async client for ONLYOFFICE DocumentServer APIs.

    - Builder API: POST /docbuilder (JWT in Authorization header)
    - Conversion API: POST ConversionService.ashx (JWT in body when JWT_IN_BODY=true)
    - Command API: POST CommandService.ashx (JWT in body when JWT_IN_BODY=true)
    - Health: GET /healthcheck (returns "true" string)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        jwt_secret: Optional[str] = None,
        jwt_in_body: Optional[bool] = None,
    ):
        config = _get_config()
        self.base_url = (base_url or config["url"]).rstrip("/")
        self.jwt_secret = jwt_secret if jwt_secret is not None else config["jwt_secret"]
        self.jwt_in_body = jwt_in_body if jwt_in_body is not None else config["jwt_in_body"]

    async def execute_builder(
        self,
        url: str,
        argument: Optional[Dict[str, Any]] = None,
        async_mode: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute Builder via POST /docbuilder.

        Document Server requires script in .docbuilder file, specified by url.
        Supported params: url (required), async, key, token, argument.

        Args:
            url: Absolute URL to .docbuilder file (script in that file)
            argument: Optional params for script (builder.GetArgument etc.)
            async_mode: Whether async request (default False)

        Returns:
            Response with fileUrl (or urls dict) and fileType
        """
        payload: Dict[str, Any] = {"async": async_mode, "url": url}
        if argument:
            payload["argument"] = argument
        body = dict(payload)
        if self.jwt_in_body and self.jwt_secret:
            body["token"] = build_jwt(payload, self.jwt_secret)
        token = (
            build_jwt(payload, self.jwt_secret)
            if self.jwt_secret and not self.jwt_in_body
            else None
        )

        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # Log request shape for debugging (token in body vs header)
        if self.jwt_in_body and "token" in body:
            logger.info("Builder request: JWT in body (token key present), body keys=%s", list(body.keys()))
        elif token:
            logger.info("Builder request: JWT in Authorization header")

        async with httpx.AsyncClient(timeout=BUILDER_TIMEOUT) as client:
            response = await client.post(
                f"{self.base_url}/docbuilder",
                json=body,
                headers=headers or None,
            )
            response.raise_for_status()
            result = response.json()
            logger.debug("DocumentServer /docbuilder raw response: %s", result)

        # Normalize response: design expects fileUrl; API may return urls dict
        if "fileUrl" not in result and "urls" in result:
            urls = result["urls"]
            first_key = next(iter(urls)) if urls else None
            if first_key:
                result["fileUrl"] = urls[first_key]
                result["fileType"] = first_key.split(".")[-1] if "." in first_key else "docx"

        return result

    async def convert(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call Conversion API: POST ConversionService.ashx.

        Args:
            params: Convert params (url, filetype, outputtype, key, etc.)

        Returns:
            API response JSON
        """
        return await self._post_with_jwt_body(
            f"{self.base_url}/ConvertService.ashx",
            params,
            timeout=CONVERT_TIMEOUT,
            headers={"Accept": "application/json"},
        )

    async def command(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call Command API: POST CommandService.ashx.

        Args:
            params: Command params (c, key, etc.)

        Returns:
            API response JSON
        """
        return await self._post_with_jwt_body(
            f"{self.base_url}/CommandService.ashx",
            params,
            timeout=COMMAND_TIMEOUT,
        )

    async def _post_with_jwt_body(
        self,
        url: str,
        payload: Dict[str, Any],
        timeout: float = CONVERT_TIMEOUT,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """POST with JWT in body when jwt_in_body is True."""
        body = dict(payload)
        if self.jwt_in_body and self.jwt_secret:
            body["token"] = build_jwt(payload, self.jwt_secret)

        req_headers = dict(headers) if headers else {}
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=body, headers=req_headers or None)
            response.raise_for_status()
            return response.json()

    async def healthcheck(self) -> bool:
        """
        Check DocumentServer health: GET /healthcheck.

        Returns:
            True if response body is "true" (string), False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=HEALTHCHECK_TIMEOUT) as client:
                response = await client.get(f"{self.base_url}/healthcheck")
                return response.text.strip() == "true"
        except Exception as e:
            logger.warning(f"DocumentServer healthcheck failed: {e}")
            return False


@lru_cache()
def get_documentserver_client(
    base_url: Optional[str] = None,
    jwt_secret: Optional[str] = None,
    jwt_in_body: Optional[bool] = None,
) -> DocumentServerClient:
    """Get cached DocumentServerClient instance."""
    return DocumentServerClient(
        base_url=base_url,
        jwt_secret=jwt_secret,
        jwt_in_body=jwt_in_body,
    )
