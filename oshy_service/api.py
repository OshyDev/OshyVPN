"""Production-minded task and VPN profile API (SQLite-backed)."""
from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from .version import APP_NAME, AUTHOR, VERSION

DB_PATH = Path(os.getenv("API_DATABASE", "./data/service.db"))
API_KEY = os.getenv("API_KEY")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    return db


@asynccontextmanager
async def lifespan(_: FastAPI):
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT,
          completed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS vpn_profiles (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, endpoint TEXT NOT NULL,
          public_key TEXT NOT NULL, created_at TEXT NOT NULL
        );
        """)
    yield


app = FastAPI(title=APP_NAME, version=VERSION, lifespan=lifespan)


async def authorize(x_api_key: Optional[str] = Header(default=None)) -> None:
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Ugyldig API-nøgle")


class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    completed: bool = False


class TaskUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    completed: Optional[bool] = None


class VpnProfileCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    endpoint: str = Field(min_length=3, max_length=255)
    public_key: str = Field(min_length=20, max_length=128)


def task_dict(row: sqlite3.Row) -> dict:
    result = dict(row)
    result["completed"] = bool(result["completed"])
    return result


@app.middleware("http")
async def request_id_and_security_headers(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/health", tags=["System"])
def health():
    try:
        with connect() as db:
            db.execute("SELECT 1")
        return {"status": "ok", "database": "ok", "timestamp": now()}
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@app.get("/version", tags=["System"])
def version():
    return {"name": APP_NAME, "author": AUTHOR, "version": VERSION, "channel": "beta"}


@app.get("/api/tasks", tags=["Tasks"], dependencies=[Depends(authorize)])
def list_tasks(completed: Optional[bool] = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    sql, args = "SELECT * FROM tasks", []
    if completed is not None:
        sql += " WHERE completed=?"
        args.append(int(completed))
    sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    args.extend((limit, offset))
    with connect() as db:
        return [task_dict(row) for row in db.execute(sql, args)]


@app.post("/api/tasks", status_code=201, tags=["Tasks"], dependencies=[Depends(authorize)])
def create_task(payload: TaskCreate):
    task = {"id": str(uuid.uuid4()), **payload.model_dump(), "created_at": now(), "updated_at": now()}
    with connect() as db:
        db.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)", (task["id"], task["title"], task["description"], int(task["completed"]), task["created_at"], task["updated_at"]))
    return task


@app.get("/api/tasks/{task_id}", tags=["Tasks"], dependencies=[Depends(authorize)])
def get_task(task_id: str):
    with connect() as db:
        row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Opgave ikke fundet")
    return task_dict(row)


@app.patch("/api/tasks/{task_id}", tags=["Tasks"], dependencies=[Depends(authorize)])
def update_task(task_id: str, payload: TaskUpdate):
    changes = payload.model_dump(exclude_unset=True)
    with connect() as db:
        row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Opgave ikke fundet")
        if changes:
            columns = [f"{key}=?" for key in changes]
            values = [int(v) if key == "completed" and v is not None else v for key, v in changes.items()]
            db.execute(f"UPDATE tasks SET {', '.join(columns)}, updated_at=? WHERE id=?", (*values, now(), task_id))
        updated = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    return task_dict(updated)


@app.delete("/api/tasks/{task_id}", status_code=204, tags=["Tasks"], dependencies=[Depends(authorize)])
def delete_task(task_id: str):
    with connect() as db:
        cursor = db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    if not cursor.rowcount:
        raise HTTPException(404, "Opgave ikke fundet")
    return Response(status_code=204)


@app.get("/api/vpn/status", tags=["VPN"], dependencies=[Depends(authorize)])
def vpn_status():
    # This API manages profiles only. Connecting requires a separately installed
    # and privileged WireGuard adapter; never claim a tunnel is active here.
    with connect() as db:
        count = db.execute("SELECT COUNT(*) FROM vpn_profiles").fetchone()[0]
    return {"provider": "wireguard", "state": "not_configured", "profiles": count}


@app.get("/api/vpn/profiles", tags=["VPN"], dependencies=[Depends(authorize)])
def list_vpn_profiles():
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT * FROM vpn_profiles ORDER BY created_at DESC")]


@app.post("/api/vpn/profiles", status_code=201, tags=["VPN"], dependencies=[Depends(authorize)])
def create_vpn_profile(payload: VpnProfileCreate):
    profile = {"id": str(uuid.uuid4()), **payload.model_dump(), "created_at": now()}
    with connect() as db:
        db.execute("INSERT INTO vpn_profiles VALUES (?, ?, ?, ?, ?)", tuple(profile.values()))
    return profile


@app.delete("/api/vpn/profiles/{profile_id}", status_code=204, tags=["VPN"], dependencies=[Depends(authorize)])
def delete_vpn_profile(profile_id: str):
    with connect() as db:
        cursor = db.execute("DELETE FROM vpn_profiles WHERE id=?", (profile_id,))
    if not cursor.rowcount:
        raise HTTPException(404, "VPN-profil ikke fundet")
    return Response(status_code=204)
