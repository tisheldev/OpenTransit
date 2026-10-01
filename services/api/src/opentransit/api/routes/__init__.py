"""Per-area route modules and their wiring.

Each area owns one module exposing a router factory; add new areas here only.
"""

from fastapi import FastAPI

from opentransit.api.responses import problem
from opentransit.api.routes.health import health_router
from opentransit.api.routes.journeys import journeys_router
from opentransit.api.routes.places import places_router
from opentransit.api.routes.reference import reference_router
from opentransit.api.routes.timetable import timetable_router
from opentransit.config import Settings


def include_routes(app: FastAPI, settings: Settings, clock) -> None:
    app.include_router(reference_router(clock, problem))
    app.include_router(timetable_router(clock, problem))
    app.include_router(places_router(clock, problem))
    app.include_router(health_router(settings, clock, problem))
    app.include_router(journeys_router(settings, clock, problem))
