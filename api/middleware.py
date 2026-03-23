"""Security middleware for the PBD Toolkit API."""

from __future__ import annotations

import hmac
import logging
import threading
import time
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validate ``Authorization: Bearer <key>`` on every request.

    The health endpoint is exempt so load-balancers can probe without credentials.
    """

    # Paths that do not require authentication.
    _PUBLIC_PATHS = frozenset({"/api/v1/health", "/docs", "/openapi.json", "/redoc"})

    def __init__(self, app: Callable, api_key: str) -> None:  # type: ignore[override]
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self._PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Missing or malformed API key. Use 'Authorization: Bearer <key>'."
                },
            )

        token = auth_header[len("Bearer ") :]
        if not hmac.compare_digest(token, self.api_key):
            return JSONResponse(status_code=403, content={"detail": "Invalid API key"})

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory sliding-window rate limiter keyed by client IP."""

    def __init__(
        self,
        app: Callable,  # type: ignore[override]
        requests_per_minute: int = 60,
        scan_requests_per_minute: int = 5,
    ) -> None:
        super().__init__(app)
        self.general_limit = requests_per_minute
        self.scan_limit = scan_requests_per_minute
        self._general_counts: dict[str, list[float]] = {}
        self._scan_counts: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _is_rate_limited(
        self, bucket: dict[str, list[float]], key: str, limit: int
    ) -> tuple[bool, int]:
        """Check if *key* exceeds *limit* requests in the last 60 seconds.

        Returns ``(is_limited, retry_after_seconds)``.
        """
        now = time.monotonic()
        window_start = now - 60.0

        with self._lock:
            timestamps = bucket.get(key, [])
            # Prune old entries
            timestamps = [t for t in timestamps if t > window_start]
            bucket[key] = timestamps

            if len(timestamps) >= limit:
                retry_after = int(timestamps[0] - window_start) + 1
                return True, max(retry_after, 1)

            timestamps.append(now)
            return False, 0

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"

        # Stricter limit for scan creation
        if request.method == "POST" and request.url.path.rstrip("/") == "/api/v1/scans":
            limited, retry_after = self._is_rate_limited(
                self._scan_counts, client_ip, self.scan_limit
            )
            if limited:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Scan rate limit exceeded"},
                    headers={"Retry-After": str(retry_after)},
                )

        # General limit for all requests
        limited, retry_after = self._is_rate_limited(
            self._general_counts, client_ip, self.general_limit
        )
        if limited:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
