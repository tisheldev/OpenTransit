"""Response helpers shared by every route area."""

from datetime import datetime

from fastapi import Request
from fastapi.responses import JSONResponse

from opentransit.api.schemas import Coverage, Metadata, Problem


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


def metadata(request: Request, snapshot, now: datetime) -> Metadata:
    generation = snapshot.generation
    freshness = generation.freshness(now)
    return Metadata(
        requestId=request.state.request_id,
        generationId=generation.id,
        generatedAt=now,
        dataBuiltAt=generation.built_at,
        mode=generation.mode,
        coverage=Coverage(start=generation.coverage_from, until=generation.coverage_until),
        freshness=freshness,
        warnings=[] if freshness == "current" else ["STATIC_DATA_AGING"],
    )
