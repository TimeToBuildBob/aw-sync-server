"""aw-sync-server — Cloud sync API for ActivityWatch.

Proof-of-concept implementation of the cloud sync layer described in the
ActivityWatch monetization design:
    knowledge/technical-designs/activitywatch-monetization-design.md

API mirrors aw-server's bucket/event endpoints so existing AW clients can
point at this server with minimal changes.

Endpoints:
    GET  /api/0/info                         — server info
    GET  /api/0/sync/status                  — per-bucket sync status for authed user
    GET  /api/0/buckets                      — list buckets for authed user
    POST /api/0/buckets/{bucket_id}          — create/update bucket
    GET  /api/0/buckets/{bucket_id}/events   — fetch events (with time range filter)
    POST /api/0/buckets/{bucket_id}/events   — upload events

Auth: Bearer token (API key) in Authorization header.
"""

import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated, Any

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import (
    create_user,
    get_events,
    get_sync_status,
    get_user_by_key,
    init_db,
    insert_events,
    list_buckets,
    upsert_bucket,
)

DB_PATH = os.environ.get("AW_SYNC_DB", "aw-sync.db")
_conn: sqlite3.Connection | None = None


def get_db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        raise RuntimeError("DB not initialised")
    return _conn


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _conn
    _conn = __import__("aw_sync_server.db", fromlist=["get_conn"]).get_conn(DB_PATH)
    init_db(_conn)
    # Seed a demo user if none exist
    row = _conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if row == 0:
        demo_key = os.environ.get("AW_SYNC_DEMO_KEY", secrets.token_urlsafe(32))
        uid = create_user(_conn, "demo", demo_key)
        print(f"[aw-sync-server] Demo user created (id={uid}), API key: {demo_key}")
    yield
    _conn.close()
    _conn = None


app = FastAPI(
    title="aw-sync-server",
    description="Cloud sync backend for ActivityWatch (proof-of-concept)",
    version="0.1.0",
    lifespan=lifespan,
)

bearer_scheme = HTTPBearer(auto_error=False)


def require_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    conn: Annotated[sqlite3.Connection, Depends(get_db)],
) -> sqlite3.Row:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing Authorization header")
    user = get_user_by_key(conn, creds.credentials)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
    return user


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/0/info")
def info() -> dict[str, Any]:
    return {
        "hostname": os.uname().nodename,
        "version": "0.1.0",
        "device_id": "aw-sync-server",
        "sync": True,
    }


@app.get("/api/0/sync/status")
def sync_status(
    user: Annotated[sqlite3.Row, Depends(require_user)],
    conn: Annotated[sqlite3.Connection, Depends(get_db)],
) -> dict:
    return get_sync_status(conn, user["id"])


@app.get("/api/0/buckets")
def buckets_list(
    user: Annotated[sqlite3.Row, Depends(require_user)],
    conn: Annotated[sqlite3.Connection, Depends(get_db)],
) -> dict:
    rows = list_buckets(conn, user["id"])
    return {r["id"]: r for r in rows}


@app.post("/api/0/buckets/{bucket_id}", status_code=status.HTTP_200_OK)
def bucket_upsert(
    bucket_id: str,
    body: dict,
    user: Annotated[sqlite3.Row, Depends(require_user)],
    conn: Annotated[sqlite3.Connection, Depends(get_db)],
) -> dict:
    upsert_bucket(
        conn,
        user_id=user["id"],
        bucket_id=bucket_id,
        bucket_type=body.get("type", "unknown"),
        client=body.get("client", "unknown"),
        hostname=body.get("hostname", "unknown"),
    )
    return {"status": "ok", "bucket_id": bucket_id}


@app.get("/api/0/buckets/{bucket_id}/events")
def events_get(
    bucket_id: str,
    start: str | None = None,
    end: str | None = None,
    limit: int = 10000,
    user: sqlite3.Row = Depends(require_user),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    return get_events(conn, user["id"], bucket_id, start, end, limit)


@app.post("/api/0/buckets/{bucket_id}/events", status_code=status.HTTP_200_OK)
def events_post(
    bucket_id: str,
    events: list[dict],
    user: Annotated[sqlite3.Row, Depends(require_user)],
    conn: Annotated[sqlite3.Connection, Depends(get_db)],
) -> dict:
    # Auto-create bucket if it doesn't exist yet
    upsert_bucket(conn, user["id"], bucket_id, "unknown", "aw-sync", "unknown")
    n = insert_events(conn, user["id"], bucket_id, events)
    return {"inserted": n}


def run() -> None:
    host = os.environ.get("AW_SYNC_HOST", "127.0.0.1")
    port = int(os.environ.get("AW_SYNC_PORT", "5667"))
    uvicorn.run("aw_sync_server.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
