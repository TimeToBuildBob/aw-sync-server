# aw-sync-server

Cloud sync server for [ActivityWatch](https://activitywatch.net) — proof of concept.

This implements the server-side half of ActivityWatch cloud sync (#1 community-requested feature with 169 reactions).

## API

```
GET  /api/0/info                         — server info
GET  /api/0/sync/status                  — per-bucket sync status
GET  /api/0/buckets                      — list buckets
POST /api/0/buckets/{bucket_id}          — create/update bucket
GET  /api/0/buckets/{bucket_id}/events   — fetch events (with time range filter)
POST /api/0/buckets/{bucket_id}/events   — upload events
```

Auth: `Authorization: Bearer <api-key>` header.

## Quickstart

```bash
pip install aw-sync-server
aw-sync-server
```

## Config

| Env var          | Default        | Description          |
|------------------|----------------|----------------------|
| `AW_SYNC_DB`     | `aw-sync.db`   | SQLite database path |
| `AW_SYNC_HOST`   | `127.0.0.1`    | Bind address         |
| `AW_SYNC_PORT`   | `5667`         | Port                 |
| `AW_SYNC_DEMO_KEY` | (random)     | Demo user API key    |

## Related

- [ActivityWatch cloud sync issue](https://github.com/ActivityWatch/activitywatch/issues/35) (169 reactions)
- [AW monetization design](https://github.com/TimeToBuildBob/bob/blob/master/knowledge/technical-designs/activitywatch-monetization-design.md)
