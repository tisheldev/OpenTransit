import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.staticfiles import StaticFiles

from opentransit.api.schemas import (
    Coverage,
    JourneyData,
    JourneyRequest,
    JourneyResponse,
    Metadata,
    Problem,
)
from opentransit.config import Settings
from opentransit.core.generation import Generation
from opentransit.motis import EngineFailure, MotisClient

LOG = logging.getLogger("opentransit.requests")
LOG.setLevel(logging.INFO)
if not LOG.handlers:
    LOG.addHandler(logging.StreamHandler())


def problem(request: Request, status: int, code: str, detail: str, errors=None) -> JSONResponse:
    payload = Problem(
        type=f"urn:opentransit:problem:{code.lower().replace('_', '-')}",
        title=code.replace("_", " ").capitalize(),
        status=status,
        code=code,
        detail=detail,
        requestId=request.state.request_id,
        errors=errors,
    )
    return JSONResponse(
        payload.model_dump(exclude_none=True),
        status_code=status,
        media_type="application/problem+json",
    )


class SafeRequests(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.request_id = uuid4().hex
        started = time.perf_counter()
        if request.method == "POST":
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 16_384:
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


def create_app(settings: Settings | None = None, transport=None, clock=None) -> FastAPI:
    settings = settings or Settings.from_env()
    clock = clock or (lambda: datetime.now(UTC))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            generation = Generation.load(settings.manifest_path)
        except OSError, ValueError, KeyError, TypeError:
            generation = None
            LOG.warning("generation_unavailable")
        app.state.generation = generation
        async with httpx.AsyncClient(
            base_url=settings.motis_url,
            timeout=settings.engine_timeout_seconds,
            transport=transport,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            app.state.motis = MotisClient(client)
            yield

    app = FastAPI(title="OpenTransit — local schedule preview", version="0.1.0", lifespan=lifespan)
    app.add_middleware(SafeRequests)
    if settings.playground_enabled:
        app.mount(
            "/playground",
            StaticFiles(directory=Path(__file__).with_name("playground"), html=True),
            name="playground",
        )

    @app.exception_handler(RequestValidationError)
    async def validation(request: Request, exc: RequestValidationError):
        # Error contexts and rejected values can contain precise passenger data.
        # Report declared schema paths only; unknown field names are redacted.
        allowed = {"body", "from", "to", "kind", "latitude", "longitude", "departAt"}
        fields = [
            {
                "field": ".".join(str(p) if p in allowed else "field" for p in e["loc"]),
                "reason": "Invalid or unsupported field",
            }
            for e in exc.errors()
        ]
        return problem(request, 422, "INVALID_REQUEST", "Check the declared input fields.", fields)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return problem(request, exc.status_code, "HTTP_ERROR", "The request cannot be served.")

    @app.get("/healthz")
    async def health():
        return {"status": "alive"}

    @app.post(
        "/v1/journeys",
        response_model=JourneyResponse,
        responses={
            status: {
                "content": {"application/problem+json": {"schema": Problem.model_json_schema()}}
            }
            for status in (413, 422, 503, 504)
        },
    )
    async def plan(query: JourneyRequest, request: Request):
        generation = app.state.generation  # Capture once; fixed for M1.
        now = clock()
        if generation is None:
            return problem(request, 503, "DATA_UNAVAILABLE", "No verified graph is configured.")
        freshness = generation.freshness(now)
        if now >= generation.coverage_until or freshness == "expired":
            return problem(request, 503, "FEED_EXPIRED", "The graph requires a fresh build.")
        if not generation.contains(query.depart_at):
            return problem(request, 422, "OUTSIDE_SERVICE_WINDOW", "Choose a time inside coverage.")
        try:
            async with asyncio.timeout(settings.journey_deadline_seconds):
                journeys = await app.state.motis.plan(query, generation)
        except (EngineFailure, TimeoutError) as exc:
            code = exc.code if isinstance(exc, EngineFailure) else "ENGINE_TIMEOUT"
            status = exc.status if isinstance(exc, EngineFailure) else 504
            return problem(request, status, code, "Scheduled planning is temporarily unavailable.")
        return JourneyResponse(
            data=JourneyData(outcome="routes_found" if journeys else "no_route", journeys=journeys),
            meta=Metadata(
                requestId=request.state.request_id,
                generationId=generation.id,
                generatedAt=now,
                dataBuiltAt=generation.built_at,
                mode=generation.mode,
                coverage=Coverage(start=generation.coverage_from, until=generation.coverage_until),
                freshness=freshness,
                warnings=[] if freshness == "current" else ["STATIC_DATA_AGING"],
            ),
        )

    return app
