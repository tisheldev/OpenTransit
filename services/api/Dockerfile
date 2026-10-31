FROM ghcr.io/astral-sh/uv:0.11.26@sha256:3d868e555f8f1dbc324afa005066cd11e1053fc4743b9808ca8025283e65efa5 AS uv
FROM python:3.14.6-slim-bookworm@sha256:4c92ffcde4dd6f1ff72a24518f49fd4990b27134987dfa31a733badde66df9f8
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=0
COPY pyproject.toml uv.lock .python-version ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable
RUN useradd --uid 10001 --create-home api
USER 10001
# Keep idle client connections open longer than a load balancer's idle timeout (ALB default
# 60 s), so the proxy never reuses a connection uvicorn already closed (sporadic 502s). The
# uvicorn CLI reads it, so it also applies to commands that replace CMD (ECS task definitions).
ENV UVICORN_TIMEOUT_KEEP_ALIVE=75
CMD ["/app/.venv/bin/uvicorn", "opentransit.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--log-level", "info"]
