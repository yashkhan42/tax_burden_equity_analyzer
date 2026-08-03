"""FastAPI application for the standalone website."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

import model_interface as mi

from .artifacts import ArtifactSource, bootstrap_artifact
from .presentation import contribution, percentile, predict, twin, warm_model
from .schemas import (
    ContributionResponse,
    HealthResponse,
    PercentileResponse,
    PredictResponse,
    ProfileRequest,
    TwinRequest,
    TwinResponse,
)


logger = logging.getLogger(__name__)


class InvalidProfileError(ValueError):
    """A semantically invalid profile reached the public model boundary."""


@dataclass(frozen=True)
class ReadinessSnapshot:
    ready: bool
    artifact_source: ArtifactSource | None


class Readiness:
    """A small synchronized state shared by startup, health, and worker threads."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._snapshot = ReadinessSnapshot(False, None)

    def set(self, ready: bool, source: ArtifactSource | None) -> None:
        with self._lock:
            self._snapshot = ReadinessSnapshot(ready, source)

    def get(self) -> ReadinessSnapshot:
        with self._lock:
            return self._snapshot


def _cors_origins() -> list[str]:
    configured = os.environ.get("TAX_API_CORS_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


def _safe_model_error() -> dict:
    return {
        "detail": {
            "code": "model_unavailable",
            "message": "The analysis service is not ready yet.",
        }
    }


def create_app(*, warm_on_startup: bool = True) -> FastAPI:
    readiness = Readiness()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if warm_on_startup:
            source: ArtifactSource | None = None
            try:
                source = await run_in_threadpool(bootstrap_artifact)
                if source is not None:
                    await run_in_threadpool(warm_model)
                    readiness.set(True, source)
            except Exception:
                logger.exception("The analysis model did not become ready.")
                readiness.set(False, source)
        yield

    app = FastAPI(
        title="Tax burden equity analyzer",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.readiness = readiness
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        del request, error
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "detail": {
                    "code": "invalid_profile",
                    "message": "Some profile details are invalid.",
                }
            },
        )

    @app.exception_handler(InvalidProfileError)
    async def invalid_model_profile(
        request: Request, error: InvalidProfileError
    ) -> JSONResponse:
        del request, error
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "detail": {
                    "code": "invalid_profile",
                    "message": "Some profile details are invalid.",
                }
            },
        )

    @app.exception_handler(mi.ModelArtifactUnavailable)
    @app.exception_handler(mi.ModelContractError)
    async def model_not_ready(request: Request, error: Exception) -> JSONResponse:
        del request
        logger.warning("A model request was unavailable: %s", type(error).__name__)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_safe_model_error(),
        )

    def require_ready(request: Request) -> None:
        if not request.app.state.readiness.get().ready:
            raise mi.ModelArtifactUnavailable("The model is not warm.")

    def invoke(function, *args):
        try:
            return function(*args)
        except ValueError as error:
            raise InvalidProfileError from error

    @app.get("/healthz", response_model=HealthResponse)
    def healthz(request: Request):
        snapshot = request.app.state.readiness.get()
        body = HealthResponse(
            status="ready" if snapshot.ready else "degraded",
            modelReady=snapshot.ready,
            artifactSource=snapshot.artifact_source,
        )
        if snapshot.ready:
            return body
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=body.model_dump(),
        )

    @app.post("/api/v1/predict", response_model=PredictResponse)
    def predict_endpoint(
        body: ProfileRequest, _: None = Depends(require_ready)
    ) -> PredictResponse:
        return invoke(predict, body.profile)

    @app.post("/api/v1/percentile", response_model=PercentileResponse)
    def percentile_endpoint(
        body: ProfileRequest, _: None = Depends(require_ready)
    ) -> PercentileResponse:
        return invoke(percentile, body.profile)

    @app.post("/api/v1/contribution", response_model=ContributionResponse)
    def contribution_endpoint(
        body: ProfileRequest, _: None = Depends(require_ready)
    ) -> ContributionResponse:
        return invoke(contribution, body.profile)

    @app.post("/api/v1/twin", response_model=TwinResponse)
    def twin_endpoint(
        body: TwinRequest, _: None = Depends(require_ready)
    ) -> TwinResponse:
        return invoke(twin, body.profile, body.comparison)

    # The exported Next.js site, served from this same process when it has been
    # built. Same origin as the API, so the browser needs no CORS grant and
    # there is no HTTP/HTTPS mixed-content edge to get wrong. Mounted last so
    # the API routes above always win the match; absent in a bare API
    # deployment, where this is simply skipped.
    web_root = Path(
        os.environ.get("TAX_WEB_DIR")
        or Path(__file__).resolve().parent.parent / "frontend" / "out"
    )
    if (web_root / "index.html").is_file():
        app.mount("/", StaticFiles(directory=web_root, html=True), name="web")
        logger.info("Serving the exported web UI from %s", web_root)
    else:
        logger.info("No exported web UI at %s; serving the API only.", web_root)

    return app


app = create_app()
