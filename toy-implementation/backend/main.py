"""
FastAPI backend for the rapid-prototyping toy.

Endpoints (from the flow diagram):
  POST /features/initialize   create a feature + its CoW workspace (no AI yet)
  POST /features/add          run Codex over the workspace in the background
  POST /features/refine       run a refinement over the workspace in the background
  GET  /features/{id}/status  poll the current status (for the frontend)

Plus two conveniences the single-page UI needs:
  GET  /features              list all features (newest first)
  GET  /features/{id}         full detail for one feature

Everything AI-related runs on a background thread so requests return instantly.
"""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db
import engine
import preview
import workspace_manager

# Load backend/.env so OPENAI_API_KEY is available to the Codex subprocess.
load_dotenv(Path(__file__).parent / ".env")

app = FastAPI(title="Rapid Prototyping Toy")

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


# --- request bodies ---------------------------------------------------------

class InitializeBody(BaseModel):
    feature: str
    parent_id: int | None = None


class IdBody(BaseModel):
    id: int


class RefineBody(BaseModel):
    id: int
    user_request: str


# --- endpoints --------------------------------------------------------------

@app.post("/features/initialize")
def initialize(body: InitializeBody) -> dict:
    """
    Create an empty feature row. The workspace folder name is assigned later, at
    clone time (engine.run_add), so it can carry a per-clone UUID — that keeps the
    copy step create-only (it never has to delete an existing folder).
    """
    if not body.feature.strip():
        raise HTTPException(400, "feature must not be empty")
    return db.create_feature(body.feature.strip(), code_folder_name="pending", parent_id=body.parent_id)


@app.post("/features/add")
def add(body: IdBody, background: BackgroundTasks) -> dict:
    """Kick off the Codex run for a feature in the background."""
    feature = db.get_feature(body.id)
    if not feature:
        raise HTTPException(404, "feature not found")
    background.add_task(engine.run_add, body.id)
    return {"id": body.id, "status": "queued"}


@app.post("/features/refine")
def refine(body: RefineBody, background: BackgroundTasks) -> dict:
    """Kick off a Codex refinement for a feature in the background."""
    feature = db.get_feature(body.id)
    if not feature:
        raise HTTPException(404, "feature not found")
    if not body.user_request.strip():
        raise HTTPException(400, "user_request must not be empty")
    background.add_task(engine.run_refine, body.id, body.user_request.strip())
    return {"id": body.id, "status": "queued"}


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


@app.post("/preview/base")
def preview_base() -> dict:
    """Start (or reuse) a dev server for the pristine base app."""
    return preview.start_preview("base", workspace_manager.BASE_DIR)


@app.post("/features/{feature_id}/preview")
def preview_feature(feature_id: int) -> dict:
    """Start (or reuse) a dev server for a feature's workspace."""
    feature = db.get_feature(feature_id)
    if not feature:
        raise HTTPException(404, "feature not found")
    workspace = workspace_manager.path_for(feature["code_folder_name"])
    if not workspace.exists():
        raise HTTPException(409, "workspace not built yet")
    return preview.start_preview(feature["code_folder_name"], workspace)


@app.get("/features")
def list_all() -> list[dict]:
    return db.list_features()


@app.get("/features/{feature_id}")
def detail(feature_id: int) -> dict:
    feature = db.get_feature(feature_id)
    if not feature:
        raise HTTPException(404, "feature not found")
    return feature
