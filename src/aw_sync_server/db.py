"""SQLite persistence layer for aw-sync-server."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def get_conn(db_path: str = "aw-sync.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key TEXT NOT NULL UNIQUE,
            name    TEXT NOT NULL,
            created TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS buckets (
            id          TEXT NOT NULL,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            type        TEXT NOT NULL,
            client      TEXT NOT NULL,
            hostname    TEXT NOT NULL,
            created     TEXT NOT NULL,
            PRIMARY KEY (id, user_id)
        );

        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            bucket_id   TEXT NOT NULL,
            user_id     INTEGER NOT NULL,
            timestamp   TEXT NOT NULL,
            duration    REAL NOT NULL,
            data        TEXT NOT NULL,
            FOREIGN KEY (bucket_id, user_id) REFERENCES buckets(id, user_id)
        );

        CREATE INDEX IF NOT EXISTS idx_events_bucket_ts
            ON events (user_id, bucket_id, timestamp);
    """)
    conn.commit()


def create_user(conn: sqlite3.Connection, name: str, api_key: str) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO users (api_key, name, created) VALUES (?, ?, ?)",
        (api_key, name, now),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def get_user_by_key(conn: sqlite3.Connection, api_key: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM users WHERE api_key = ?", (api_key,)
    ).fetchone()


def upsert_bucket(
    conn: sqlite3.Connection,
    user_id: int,
    bucket_id: str,
    bucket_type: str,
    client: str,
    hostname: str,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO buckets (id, user_id, type, client, hostname, created)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id, user_id) DO UPDATE SET
            type=excluded.type,
            client=excluded.client,
            hostname=excluded.hostname
        """,
        (bucket_id, user_id, bucket_type, client, hostname, now),
    )
    conn.commit()


def list_buckets(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM buckets WHERE user_id = ? ORDER BY id", (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def insert_events(
    conn: sqlite3.Connection,
    user_id: int,
    bucket_id: str,
    events: list[dict],
) -> int:
    """Bulk-insert events; returns count inserted."""
    rows = [
        (bucket_id, user_id, e["timestamp"], e["duration"], json.dumps(e["data"]))
        for e in events
    ]
    conn.executemany(
        "INSERT INTO events (bucket_id, user_id, timestamp, duration, data) VALUES (?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return len(rows)


def get_events(
    conn: sqlite3.Connection,
    user_id: int,
    bucket_id: str,
    start: str | None = None,
    end: str | None = None,
    limit: int = 10000,
) -> list[dict]:
    query = "SELECT * FROM events WHERE user_id=? AND bucket_id=?"
    params: list = [user_id, bucket_id]
    if start:
        query += " AND timestamp >= ?"
        params.append(start)
    if end:
        query += " AND timestamp <= ?"
        params.append(end)
    query += " ORDER BY timestamp ASC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [
        {
            "id": r["id"],
            "timestamp": r["timestamp"],
            "duration": r["duration"],
            "data": json.loads(r["data"]),
        }
        for r in rows
    ]


def get_sync_status(conn: sqlite3.Connection, user_id: int) -> dict:
    buckets = list_buckets(conn, user_id)
    result = {}
    for b in buckets:
        row = conn.execute(
            "SELECT COUNT(*) as cnt, MAX(timestamp) as last_ts FROM events WHERE user_id=? AND bucket_id=?",
            (user_id, b["id"]),
        ).fetchone()
        result[b["id"]] = {
            "event_count": row["cnt"],
            "last_synced": row["last_ts"],
            "hostname": b["hostname"],
            "type": b["type"],
        }
    return result
