from collections import deque
from threading import Lock
from time import monotonic

from fastapi import Request

from app.config import (
    CHAT_RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    UPLOAD_RATE_LIMIT_REQUESTS,
)
from app.exceptions.custom_exceptions import RateLimitExceededError
from app.logger import log_event


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._requests: dict[tuple[str, str], deque[float]] = {}
        self._lock = Lock()
        self._last_cleanup = 0.0

    def allow(
        self,
        *,
        bucket: str,
        client_id: str,
        limit: int,
        window_seconds: float,
        now: float | None = None,
    ) -> bool:
        current_time = monotonic() if now is None else now
        cutoff = current_time - window_seconds
        key = (bucket, client_id)

        with self._lock:
            self._cleanup_expired(cutoff, current_time, window_seconds)
            timestamps = self._requests.setdefault(key, deque())

            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if len(timestamps) >= limit:
                return False

            timestamps.append(current_time)
            return True

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()
            self._last_cleanup = 0.0

    def _cleanup_expired(
        self,
        cutoff: float,
        current_time: float,
        window_seconds: float,
    ) -> None:
        if current_time - self._last_cleanup < window_seconds:
            return

        for key, timestamps in list(self._requests.items()):
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if not timestamps:
                del self._requests[key]

        self._last_cleanup = current_time


rate_limiter = SlidingWindowRateLimiter()


def enforce_expensive_endpoint_rate_limit(request: Request) -> None:
    endpoint = request.url.path

    if endpoint == "/upload":
        bucket = "upload"
        limit = UPLOAD_RATE_LIMIT_REQUESTS
    else:
        bucket = "chat"
        limit = CHAT_RATE_LIMIT_REQUESTS

    client_id = request.client.host if request.client is not None else "unknown"
    allowed = rate_limiter.allow(
        bucket=bucket,
        client_id=client_id,
        limit=limit,
        window_seconds=RATE_LIMIT_WINDOW_SECONDS,
    )

    if allowed:
        return

    log_event(
        "request_rejected",
        endpoint=endpoint,
        reason="rate_limit",
    )
    raise RateLimitExceededError(
        "Se excedió el límite de solicitudes. Inténtalo más tarde."
    )
