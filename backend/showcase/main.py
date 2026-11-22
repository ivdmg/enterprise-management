"""Read-only ASGI entry point for the showcase."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .data import finance, snapshot

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist-showcase"


@app.get("/health")
def health():
    return {"status": "ok", "source": "synthetic"}


@app.get("/api/v1/{endpoint:path}")
def read_demo(endpoint: str, request: Request):
    today, projects, registry, tasks, alerts, procurement, dispatch = snapshot()
    collections = {
        "customer-tenders": (registry, {}),
        "dashboard/projects": (projects, {"risk_level": "risk_level", "status": "status"}),
        "tasks": (tasks, {"role": "responsible_role", "source": "source", "status": "status"}),
        "alerts": (alerts, {"severity": "severity"}),
        "procurement/items": (procurement, {"project_name": "project_name", "status": "status"}),
        "dispatch/records": (dispatch, {"status": "status", "resource_type": "resource_type"}),
    }
    query = request.query_params
    if endpoint in collections:
        rows, filters = collections[endpoint]
        data = [
            row for row in rows
            if all(not query.get(name) or row.get(field) == query[name] for name, field in filters.items())
        ]
        if endpoint == "tasks" and query.get("urgent") == "true":
            data = [row for row in data if row["is_urgent"]]
        if endpoint == "alerts":
            resolved = query.get("is_resolved") == "true"
            data = [row for row in data if row["is_resolved"] == resolved]
    elif endpoint == "dashboard/finance":
        data = finance(today, query.get("period"))
    elif endpoint == "sync/status":
        data = {"status": "idle", "drive_mode": "mock", "synced_files_count": 0,
                "target_folders_count": 0, "last_synced_at": None}
    else:
        raise HTTPException(status_code=404)
    return {"success": True, "data": data, "error": None}


@app.get("/")
def homepage():
    if not (DIST / "index.html").is_file():
        raise HTTPException(status_code=503, detail="Build the showcase frontend first.")
    return FileResponse(DIST / "index.html")


@app.get("/enterprise-hub-orange.svg", include_in_schema=False)
def favicon():
    return FileResponse(DIST / "enterprise-hub-orange.svg")


app.mount("/assets", StaticFiles(directory=DIST / "assets", check_dir=False), name="assets")
