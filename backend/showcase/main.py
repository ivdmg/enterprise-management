"""Read-only ASGI entry point for the showcase."""

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .drive import Snapshots

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist-showcase"
snapshots = Snapshots()


def current():
    return snapshots.current(datetime.now(ZoneInfo("Europe/Samara")).date())


def source_status(state):
    return {"source": state.source, "refreshed_at": state.refreshed_at, "issue": state.issue}


@app.get("/health")
def health(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok", **source_status(current())}


@app.get("/api/v1/{endpoint:path}")
def read_demo(endpoint: str, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    state = current()
    collections = {
        "customer-tenders": (state.data["customer-tenders"], {}),
        "dashboard/projects": (state.data["dashboard/projects"], {"risk_level": "risk_level", "status": "status"}),
        "tasks": (state.data["tasks"], {"role": "responsible_role", "source": "source", "status": "status"}),
        "alerts": (state.data["alerts"], {"severity": "severity"}),
        "procurement/items": (state.data["procurement/items"], {"project_name": "project_name", "status": "status"}),
        "dispatch/records": (state.data["dispatch/records"], {"status": "status", "resource_type": "resource_type"}),
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
        today = datetime.now(ZoneInfo("Europe/Samara")).date()
        period = query.get("period")
        start = {"year": today.replace(month=1, day=1),
                 "quarter": today - timedelta(days=89)}.get(period, today.replace(day=1))
        totals = {}
        for payment in state.data["payments"]:
            day = payment["date"]
            if start.isoformat() <= day <= today.isoformat():
                point = totals.setdefault(day, {"date": day, "incoming": 0, "outgoing": 0})
                for field in ("incoming", "outgoing"):
                    point[field] += payment[field]
        incoming = sum(point["incoming"] for point in totals.values())
        outgoing = sum(point["outgoing"] for point in totals.values())
        data = {"dynamics": [totals[day] for day in sorted(totals)], "total_incoming": incoming,
                "total_outgoing": outgoing, "net_cash_flow": incoming - outgoing,
                "top_debtors": [], "top_creditors": []}
    elif endpoint == "engineer-documents":
        data = {"register": state.data[endpoint]}
    elif endpoint == "drive-catalog":
        data = state.catalog
    elif endpoint == "showcase/source":
        data = source_status(state)
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
