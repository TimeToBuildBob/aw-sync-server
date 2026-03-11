"""Tests for aw-sync-server endpoints."""

import pytest
from fastapi.testclient import TestClient

from aw_sync_server.db import create_user, get_conn, init_db
from aw_sync_server.main import app, get_db

DB_PATH = ":memory:"
API_KEY = "test-api-key-abc123"
BUCKET_ID = "aw-window_testhost"


@pytest.fixture(autouse=True)
def db():
    conn = get_conn(DB_PATH)
    init_db(conn)
    create_user(conn, "testuser", API_KEY)

    app.dependency_overrides[get_db] = lambda: conn
    yield conn
    app.dependency_overrides.clear()
    conn.close()


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def auth(client):
    return {"Authorization": f"Bearer {API_KEY}"}


# --- Info ---

def test_info(client):
    r = client.get("/api/0/info")
    assert r.status_code == 200
    assert r.json()["sync"] is True


# --- Auth ---

def test_requires_auth(client):
    r = client.get("/api/0/sync/status")
    assert r.status_code == 401


def test_rejects_bad_key(client):
    r = client.get("/api/0/sync/status", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


# --- Buckets ---

def test_bucket_upsert_and_list(client, auth):
    r = client.post(
        f"/api/0/buckets/{BUCKET_ID}",
        json={"type": "currentwindow", "client": "aw-watcher-window", "hostname": "testhost"},
        headers=auth,
    )
    assert r.status_code == 200

    r = client.get("/api/0/buckets", headers=auth)
    assert r.status_code == 200
    assert BUCKET_ID in r.json()


# --- Events ---

SAMPLE_EVENTS = [
    {"timestamp": "2026-03-11T10:00:00+00:00", "duration": 30.0, "data": {"app": "firefox", "title": "GitHub"}},
    {"timestamp": "2026-03-11T10:00:30+00:00", "duration": 45.0, "data": {"app": "code", "title": "main.py"}},
    {"timestamp": "2026-03-11T10:01:15+00:00", "duration": 60.0, "data": {"app": "terminal", "title": "bash"}},
]


def test_upload_events(client, auth):
    r = client.post(f"/api/0/buckets/{BUCKET_ID}/events", json=SAMPLE_EVENTS, headers=auth)
    assert r.status_code == 200
    assert r.json()["inserted"] == 3


def test_download_events(client, auth):
    client.post(f"/api/0/buckets/{BUCKET_ID}/events", json=SAMPLE_EVENTS, headers=auth)

    r = client.get(f"/api/0/buckets/{BUCKET_ID}/events", headers=auth)
    assert r.status_code == 200
    events = r.json()
    assert len(events) == 3
    assert events[0]["data"]["app"] == "firefox"


def test_time_range_filter(client, auth):
    client.post(f"/api/0/buckets/{BUCKET_ID}/events", json=SAMPLE_EVENTS, headers=auth)

    r = client.get(
        f"/api/0/buckets/{BUCKET_ID}/events",
        params={"start": "2026-03-11T10:00:30+00:00"},
        headers=auth,
    )
    assert r.status_code == 200
    events = r.json()
    assert len(events) == 2
    assert events[0]["data"]["app"] == "code"


def test_events_isolated_per_user(client, db, auth):
    """Events from one user should not be visible to another."""
    from aw_sync_server.db import create_user

    other_key = "other-user-key"
    create_user(db, "other", other_key)
    other_auth = {"Authorization": f"Bearer {other_key}"}

    client.post(f"/api/0/buckets/{BUCKET_ID}/events", json=SAMPLE_EVENTS, headers=auth)

    r = client.get(f"/api/0/buckets/{BUCKET_ID}/events", headers=other_auth)
    assert r.status_code == 200
    assert len(r.json()) == 0


# --- Sync status ---

def test_sync_status(client, auth):
    client.post(
        f"/api/0/buckets/{BUCKET_ID}",
        json={"type": "currentwindow", "client": "aw-watcher-window", "hostname": "testhost"},
        headers=auth,
    )
    client.post(f"/api/0/buckets/{BUCKET_ID}/events", json=SAMPLE_EVENTS, headers=auth)

    r = client.get("/api/0/sync/status", headers=auth)
    assert r.status_code == 200
    status = r.json()
    assert BUCKET_ID in status
    assert status[BUCKET_ID]["event_count"] == 3
    assert status[BUCKET_ID]["last_synced"] is not None
