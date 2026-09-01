"""
FastAPI backend for the rapid-prototyping toy.

Endpoints split by what they do to the world.

  /core/*      significant functionality - creating the environment + AI integration

    POST /core/preload_environment   clone + warm an environment ahead of time
    POST /core/add                  build a feature, claiming a warm environment if available
    POST /core/refine                update a feature that already exists

  /features/*  feature metadata related calls

    GET  /features                   every feature, newest first
    GET  /features/{id}              one feature in full
    GET  /features/{id}/status       just the fields the frontend polls
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import db
import preview
import schemas
from core import pipelines, statuses

# Load backend/.env so OPENAI_API_KEY is available to the Codex subprocess.
load_dotenv(Path(__file__).parent / ".env")

# Basic Pool config sizes
MAX_CONCURRENT_TURNS = 16
MAX_CONCURRENT_PRELOADS = 8

_FEATURE_POOL = ThreadPoolExecutor(MAX_CONCURRENT_TURNS, thread_name_prefix="feature")
_PRELOAD_POOL = ThreadPoolExecutor(
    MAX_CONCURRENT_PRELOADS, thread_name_prefix="preload"
)


app = FastAPI(title="Rapid Prototyping Tool")

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


@app.on_event("shutdown")
def shutdown() -> None:
    preview.stop_all()  # don't leave orphan dev servers running
    _FEATURE_POOL.shutdown(wait=False, cancel_futures=True)
    _PRELOAD_POOL.shutdown(wait=False, cancel_futures=True)


# --- endpoints --------------------------------------------------------------


@app.post("/core/preload_environment", status_code=202)
def preload_environment(body: schemas.PreloadEnvironmentBody) -> dict:
    """
    Build environments ahead of the requests that will use them.
    """
    for _ in range(body.count):
        _PRELOAD_POOL.submit(pipelines.preload_environment, body.parent_id)
    return {"queued": body.count}


@app.post("/core/add", status_code=202)
def add(body: schemas.AddBody) -> dict:
    """
    Build a feature. Claims a preloaded environment if one is waiting, or
    creates an empty claimed db row otherwise, both return a feature id
    """
    feature_id = db.claim_ready(
        body.feature_request, body.parent_id
    ) or db.create_feature(
        feature_request=body.feature_request,
        parent_id=body.parent_id,
        status=statuses.QUEUED,
    )
    _FEATURE_POOL.submit(pipelines.run_add, feature_id)
    return {"feature_id": feature_id, "status": statuses.QUEUED}


@app.post("/core/refine", status_code=202)
def refine(body: schemas.RefineBody) -> dict:
    """
    Update a feature in a workspace that already exists.
    """
    if not db.get_feature(body.feature_id):
        raise HTTPException(404, "feature not found")
    if db.claim_for_refine(body.feature_id) is None:
        raise HTTPException(409, "feature is not in a refinable state")
    _FEATURE_POOL.submit(pipelines.run_refine, body.feature_id, body.user_request)
    return {"feature_id": body.feature_id, "status": statuses.QUEUED}


@app.get("/features")
def list_all() -> list[dict]:
    return db.list_features()


@app.get("/features/{feature_id}")
def detail(feature_id: int) -> dict:
    feature = db.get_feature(feature_id)
    if not feature:
        raise HTTPException(404, "feature not found")
    return feature


@app.get("/features/{feature_id}/status")
def status(feature_id: int) -> dict:
    feature = db.get_feature(feature_id)
    if not feature:
        raise HTTPException(404, "feature not found")
    return {
        "id": feature["id"],
        "status": feature["status"],
        "progress": feature["progress"],
    }
