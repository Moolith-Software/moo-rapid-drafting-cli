"""
FastAPI backend for the rapid-prototyping toy.

Endpoints split by what they do to the world.

  /core/*      significant functionality - creating the environment + AI integration

    POST /core/preload_environment   clone + warm an environment ahead of time
    POST /core/add                   build one or many features, claiming warm environments
    POST /core/refine                update a feature that already exists

  /features/*  feature metadata related calls

    GET  /features                   every feature, newest first
    GET  /features/{id}              one feature in full
    GET  /features/{id}/status       just the fields the frontend polls
"""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import db
import guards
import preview
import schemas
from core import errors, pipelines
from core import workspace_manager as workspaces

# Load backend/.env so OPENAI_API_KEY is available to the Codex subprocess.
load_dotenv(Path(__file__).parent / ".env")

# key environment configus
# Production unless ENV is explicitly "development" (or "dev"), so a server that
# forgets or misspells ENV still hides the docs.
ENV = os.environ.get("ENV", "production").lower()
IS_PRODUCTION = ENV not in ("development", "dev")
DEBUG = not IS_PRODUCTION

# Basic Pool config sizes
MAX_CONCURRENT_TURNS = 16
MAX_CONCURRENT_PRELOADS = 8

_FEATURE_POOL = ThreadPoolExecutor(MAX_CONCURRENT_TURNS, thread_name_prefix="feature")
_PRELOAD_POOL = ThreadPoolExecutor(
    MAX_CONCURRENT_PRELOADS, thread_name_prefix="preload"
)


if IS_PRODUCTION:
    app = FastAPI(
        title="Rapid Prototyping Tool",
        debug=DEBUG,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
else:
    app = FastAPI(
        title="Rapid Prototyping Tool",
        debug=DEBUG,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

# The Vue dev server runs on a different port, so allow cross-origin calls.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    db.init_db()

    # clean any leftover open workspaces from last session
    closed = workspaces.sweep()
    if closed:
        print(
            f"[workspaces] closed {closed} left open by a previous run",
            flush=True,
        )
    # Bases are built per project, by the add-project endpoint - not built yet.
    print(f"[workspaces] driver: {workspaces.driver_name()}", flush=True)


@app.on_event("shutdown")
def shutdown() -> None:
    preview.stop_all()  # don't leave orphan dev servers running
    _FEATURE_POOL.shutdown(wait=False, cancel_futures=True)
    _PRELOAD_POOL.shutdown(wait=False, cancel_futures=True)


@app.exception_handler(errors.DatabaseUnavailableError)
def database_unavailable(
    request: Request, exc: errors.DatabaseUnavailableError
) -> JSONResponse:
    """
    Could not reach the database at all, raise this significant exception
    """
    return JSONResponse(status_code=503, content={"detail": exc.status_line()})


# --- endpoints --------------------------------------------------------------


@app.post("/core/preload_environment", status_code=202)
def preload_environment(body: schemas.PreloadEnvironmentBody) -> dict:
    """
    Build environments ahead of the requests that will use them.
    """
    guards.check_parent(body.parent_id)
    for _ in range(body.count):
        _PRELOAD_POOL.submit(pipelines.preload_environment, body.parent_id)
    return {"queued": body.count}


@app.post("/core/add", status_code=202)
def add(body: schemas.AddBody) -> schemas.AddResponse:
    """
    Build a feature, or a batch of them.
    """
    guards.check_parent(body.parent_id)
    reserved = db.reserve_features(body.feature_requests, body.parent_id)
    for feature_id, _ in reserved:
        _FEATURE_POOL.submit(pipelines.run_add, feature_id)
    return schemas.AddResponse(
        features=[
            schemas.QueuedFeature(
                feature_id=feature_id, feature_request=feature_request
            )
            for feature_id, feature_request in reserved
        ]
    )


@app.post("/core/refine", status_code=202)
def refine(body: schemas.RefineBody) -> dict:
    """
    Update a feature in a workspace that already exists.
    """
    if not db.get_feature(body.feature_id):
        raise HTTPException(404, "feature not found")
    guards.check_no_children(body.feature_id)
    if db.claim_for_refine(body.feature_id) is None:
        raise HTTPException(409, "feature is not in a refinable state")
    _FEATURE_POOL.submit(pipelines.run_refine, body.feature_id, body.user_request)
    return {"feature_id": body.feature_id}


@app.get("/features")
def list_all() -> list[schemas.FeatureResponse]:
    return [schemas.FeatureResponse(**feature) for feature in db.list_features()]


@app.get("/features/{feature_id}")
def detail(feature_id: int) -> schemas.FeatureResponse:
    feature = db.get_feature(feature_id)
    if feature is None:
        raise HTTPException(404, "feature not found")
    return schemas.FeatureResponse(**feature)


@app.get("/features/{feature_id}/status")
def status(feature_id: int) -> schemas.FeatureStatusResponse:
    feature = db.get_feature(feature_id)
    if feature is None:
        raise HTTPException(404, "feature not found")
    return schemas.FeatureStatusResponse(**feature)
