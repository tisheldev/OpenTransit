"""Request middleware: request ids, body bound, cache headers and safe route logging."""

import time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from opentransit.api.log import LOG
from opentransit.api.responses import problem

MAX_BODY_BYTES = 16_384  # 16 KiB; larger POST bodies get 413 before parsing.


class SafeRequests(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.request_id = uuid4().hex
        started = time.perf_counter()
        if request.method == "POST":
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
        LOG.info(
            "request_id=%s route=%s status=%s duration_ms=%.1f",
            request.state.request_id,
            route.path if route else "unmatched",
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        return response
