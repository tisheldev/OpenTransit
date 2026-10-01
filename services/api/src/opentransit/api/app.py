"""App construction: middleware, exception handlers, routes and the managed lifespan."""

import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

from opentransit.api.lifecycle import make_lifespan
from opentransit.api.middleware import SafeRequests
from opentransit.api.rate_limit import (
    EXPENSIVE,
    STANDARD,
    BucketPolicy,
    RateLimiter,
    classify,
    parse_trusted_proxies,
)
from opentransit.api.responses import problem
from opentransit.api.routes import include_routes
from opentransit.api.schemas import Problem
from opentransit.config import Settings

RATE_LIMITED_RESPONSE = {
    "description": "Per-client rate limit exceeded (`RATE_LIMITED`)",
    "headers": {
        "Retry-After": {
            "description": "Whole seconds until this client may retry",
            "schema": {"type": "integer", "minimum": 1},
        }
    },
    "content": {"application/problem+json": {"schema": Problem.model_json_schema()}},
}


def _rate_limiter(settings: Settings, clock) -> RateLimiter | None:
    if not settings.rate_limit_enabled:
        return None
    policies = {
        STANDARD: BucketPolicy(
            settings.rate_limit_standard_per_minute, settings.rate_limit_standard_burst
        ),
        EXPENSIVE: BucketPolicy(
            settings.rate_limit_expensive_per_minute, settings.rate_limit_expensive_burst
        ),
    }
    return RateLimiter(
        policies, clock=clock or time.monotonic, max_clients=settings.rate_limit_max_clients
    )


def _document_rate_limits(app: FastAPI) -> None:
    """Add the 429 problem to every rate-limited operation in the generated schema."""
    generate = app.openapi

    def openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = generate()
        for path, operations in schema.get("paths", {}).items():
            for method, operation in operations.items():
                if classify(method, path) is not None:
                    operation.setdefault("responses", {}).setdefault("429", RATE_LIMITED_RESPONSE)
        return schema

    app.openapi = openapi


def create_app(
    settings: Settings | None = None,
    transport=None,
    clock=None,
    signal_installer=None,
    rate_limit_clock=None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    clock = clock or (lambda: datetime.now(UTC))

    app = FastAPI(
        title="OpenTransit — local schedule preview",
        version="0.1.0",
        lifespan=make_lifespan(settings, transport, clock, signal_installer),
    )
    app.state.rate_limiter = _rate_limiter(settings, rate_limit_clock)
    app.state.trusted_proxies = parse_trusted_proxies(settings.trusted_proxies)
    app.add_middleware(SafeRequests)
    include_routes(app, settings, clock)
    _document_rate_limits(app)
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
        allowed = {
            "body",
            "from",
            "to",
            "kind",
            "latitude",
            "longitude",
            "stopId",
            "placeRef",
            "departAt",
            "arriveBy",
            "modes",
            "results",
            "lang",
            "maxAccessWalkMinutes",
            "maxEgressWalkMinutes",
            "maxDirectWalkMinutes",
        }
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

    return app
