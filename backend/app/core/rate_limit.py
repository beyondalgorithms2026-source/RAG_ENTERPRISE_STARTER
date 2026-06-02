import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import HTTPException, Request

from app.core.config import settings


_buckets: dict[str, Deque[float]] = defaultdict(deque)


def _actor_key(request: Request, scope: str) -> str:
    user = getattr(request.state, "user", None)
    if user is not None:
        return f"{scope}:user:{user.user_id}"
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    host = forwarded or (request.client.host if request.client else "unknown")
    return f"{scope}:ip:{host}"


def enforce_rate_limit(request: Request, *, scope: str, limit_per_minute: int) -> None:
    if not settings.RATE_LIMIT_ENABLED or limit_per_minute <= 0:
        return
    now = time.monotonic()
    bucket = _buckets[_actor_key(request, scope)]
    while bucket and now - bucket[0] >= 60:
        bucket.popleft()
    if len(bucket) >= limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limited",
                "message": f"Too many {scope} requests. Please retry shortly.",
                "limit_per_minute": limit_per_minute,
            },
        )
    bucket.append(now)


def rate_limit_ask(request: Request) -> None:
    enforce_rate_limit(request, scope="ask", limit_per_minute=settings.RATE_LIMIT_ASK_PER_MINUTE)


def rate_limit_ask_stream(request: Request) -> None:
    enforce_rate_limit(request, scope="ask_stream", limit_per_minute=settings.RATE_LIMIT_ASK_PER_MINUTE)


def rate_limit_compare(request: Request) -> None:
    enforce_rate_limit(request, scope="compare", limit_per_minute=settings.RATE_LIMIT_ASK_PER_MINUTE)


def rate_limit_search(request: Request) -> None:
    enforce_rate_limit(request, scope="search", limit_per_minute=settings.RATE_LIMIT_SEARCH_PER_MINUTE)


def rate_limit_admin_expensive(request: Request) -> None:
    enforce_rate_limit(request, scope="admin_expensive", limit_per_minute=settings.RATE_LIMIT_ADMIN_EXPENSIVE_PER_MINUTE)
