"""Request middleware: request ids, rate limits, body bound, cache headers and safe logging."""

import time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from opentransit.api.log import LOG
from opentransit.api.rate_limit import classify, client_identity
from opentransit.api.responses import problem

MAX_BODY_BYTES = 16_384  # 16 KiB; larger POST bodies get 413 before parsing.


def _rate_limited(request: Request):
    """429 problem when this client's bucket for the request class is empty, else None."""
    limiter = getattr(request.app.state, "rate_limiter", None)
    bucket_class = classify(request.method, request.url.path)
    if limiter is None or bucket_class is None:
        return None
    identity = client_identity(
        request.client.host if request.client else None,
        request.headers.get("x-forwarded-for"),
        request.app.state.trusted_proxies,
    )
    decision = limiter.check(bucket_class, identity)
    if decision.allowed:
        return None
    response = problem(
        request,
        429,
        "RATE_LIMITED",
        "Too many requests from this client; retry after the Retry-After interval.",
    )
    response.headers["Retry-After"] = str(decision.retry_after)
    request.state.log_route = f"rate_limit:{bucket_class}"
    return response


class SafeRequests(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.request_id = uuid4().hex
        started = time.perf_counter()
        # Rejected before the body is read, so an over-limit client cannot cost parsing.
        limited = _rate_limited(request)
        if limited is not None:
            response = limited
        elif request.method == "POST":
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > MAX_BODY_BYTES:
                    response = problem(request, 413, "BODY_TOO_LARGE", "Body limit is 16 KiB.")
                    break
            else:
                request._body = bytes(body)
                response = await call_next(request)
        else:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        route = request.scope.get("route")
        label = getattr(request.state, "log_route", None)
        LOG.info(
            "request_id=%s route=%s status=%s duration_ms=%.1f",
            request.state.request_id,
            label or (route.path if route else "unmatched"),
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        return response
