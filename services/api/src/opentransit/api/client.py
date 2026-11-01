"""The built web test client, served at /app/ when OPENTRANSIT_CLIENT_DIR is set (S8).

Off by default and outside the API contract: nothing here appears in OpenAPI. Same origin
as the API, so the client calls /v1 without CORS. The client routes with the URL hash
(`#/compare`), so the server only ever sees /app/ and real files; unknown paths are 404
and no SPA fallback exists. Directories are never listed, and Starlette's lookup refuses
any path that resolves outside the directory.
"""

import os
import posixpath
from pathlib import Path

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import FileResponse, PlainTextResponse, RedirectResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

MOUNT_PATH = "/app"

# Fixed for the client at /app/ (coordinator contract). Map tiles and their style come
# from OpenFreeMap; MapLibre needs blob: workers and data:/blob: images.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data: blob: https://tiles.openfreemap.org; font-src 'self'; "
    "connect-src 'self' https://tiles.openfreemap.org; worker-src 'self' blob:; "
    "manifest-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; "
    "frame-ancestors 'none'"
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Content-Type-Options": "nosniff",
}
# Vite content-hashes everything under assets/, so a name never changes meaning.
IMMUTABLE = "public, max-age=31536000, immutable"
# index.html names the current hashed assets: never reuse a stored copy.
NO_STORE = "no-store"
# icon.svg and manifest.webmanifest keep their names across builds: a browser may keep
# them but must revalidate (ETag, 304) before each use, so it never shows a stale one.
REVALIDATE = "no-cache"

# Explicit types: under nosniff a wrong guess (the host's MIME registry, notably on
# Windows) would stop scripts or styles from loading. Unknown types are opaque bytes.
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".webmanifest": "application/manifest+json",
    ".json": "application/json",
    ".map": "application/json",
    ".png": "image/png",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
    ".wasm": "application/wasm",
}
FALLBACK_CONTENT_TYPE = "application/octet-stream"


def validate_client_dir(path: Path) -> Path:
    """The directory to serve, or a clear startup error (missing, not a dir, no index)."""
    if not path.is_dir():
        raise ValueError(f"OPENTRANSIT_CLIENT_DIR is not a directory: {path}")
    if not (path / "index.html").is_file():
        raise ValueError(
            f"OPENTRANSIT_CLIENT_DIR has no index.html (expected the built web client): {path}"
        )
    return path


def cache_control(path: str, status_code: int) -> str:
    """Cache rule for a mount-relative path (as normalised by StaticFiles)."""
    if status_code not in (200, 304):
        return NO_STORE
    relative = path.replace("\\", "/")
    if relative.startswith("assets/"):
        return IMMUTABLE
    if relative.endswith(".html"):
        return NO_STORE
    return REVALIDATE


class ClientFiles(StaticFiles):
    """StaticFiles with fixed headers, explicit content types and no directory handling."""

    def __init__(self, directory: Path) -> None:
        super().__init__(directory=directory, html=False, follow_symlink=False)

    async def get_response(self, path: str, scope: Scope) -> Response:
        if path in ("", "."):
            path = "index.html"
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            response = PlainTextResponse(str(exc.detail), exc.status_code, headers=exc.headers)
        except OSError:
            # Names the host filesystem cannot represent (for example ":" on Windows).
            response = PlainTextResponse("Not Found", 404)
        response.headers.update(SECURITY_HEADERS)
        response.headers["Cache-Control"] = cache_control(path, response.status_code)
        return response

    def file_response(self, full_path, stat_result, scope, status_code=200) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        if isinstance(response, FileResponse):
            suffix = posixpath.splitext(os.fspath(full_path))[1].lower()
            response.headers["Content-Type"] = CONTENT_TYPES.get(suffix, FALLBACK_CONTENT_TYPE)
        return response


def mount_client(app: FastAPI, directory: Path) -> None:
    async def to_directory(request: Request) -> Response:
        # Relative Location: behind TLS-terminating proxies an absolute http:// URL would
        # downgrade the scheme.
        response = RedirectResponse(MOUNT_PATH + "/", status_code=307)
        response.headers.update(SECURITY_HEADERS)
        return response

    app.router.add_route(MOUNT_PATH, to_directory, methods=["GET", "HEAD"], include_in_schema=False)
    app.mount(MOUNT_PATH, ClientFiles(validate_client_dir(directory)), name="client")
