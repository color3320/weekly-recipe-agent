"""HTTP Basic Auth middleware — protects all routes except /health."""

from __future__ import annotations

import base64
import secrets
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from agent.config import BASIC_AUTH_PASS, BASIC_AUTH_USER


def _auth_configured() -> bool:
    return bool(BASIC_AUTH_USER and BASIC_AUTH_PASS)


def _unauthorized() -> Response:
    return Response(
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="Revenue Manager Agent"'},
        content="Authentication required",
    )


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path == "/health":
            return await call_next(request)

        if not _auth_configured():
            return await call_next(request)

        header = request.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return _unauthorized()

        try:
            decoded = base64.b64decode(header[6:]).decode("utf-8")
            username, _, password = decoded.partition(":")
        except (ValueError, UnicodeDecodeError):
            return _unauthorized()

        user_ok = secrets.compare_digest(username, BASIC_AUTH_USER or "")
        pass_ok = secrets.compare_digest(password, BASIC_AUTH_PASS or "")
        if not (user_ok and pass_ok):
            return _unauthorized()

        return await call_next(request)
