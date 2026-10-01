"""App construction: middleware, exception handlers, routes and the managed lifespan."""

from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

from opentransit.api.lifecycle import make_lifespan
from opentransit.api.middleware import SafeRequests
from opentransit.api.responses import problem
from opentransit.api.routes import include_routes
from opentransit.config import Settings


def create_app(
    settings: Settings | None = None,
    transport=None,
    clock=None,
    signal_installer=None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    clock = clock or (lambda: datetime.now(UTC))

    app = FastAPI(
        title="OpenTransit — local schedule preview",
        version="0.1.0",
        lifespan=make_lifespan(settings, transport, clock, signal_installer),
    )
    app.add_middleware(SafeRequests)
    include_routes(app, settings, clock)
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
