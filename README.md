# aw-sync-server

Sync server for [ActivityWatch](https://activitywatch.net) — proof of concept for **self-hosted** use.

This implements a server-side sync endpoint for ActivityWatch, compatible with the existing bucket+event API.

## Privacy / Design Philosophy

> **Important**: This project is designed for **self-hosted, user-controlled infrastructure only.**

ActivityWatch is built on the principle that [you own your data](https://docs.activitywatch.net/en/latest/privacy-policy.html). Raw activity data (app usage, window titles, keystrokes) is deeply personal. The intended use of this sync server:

- **Run it yourself** — on your own machine, VPS, or LAN
- **Sync between your own devices** — not through a third-party service
- **Never send raw data to a hosted service** you do not control

This is **not** intended to be run as a multi-tenant hosted service where a provider holds users's raw activity data. That would contradict ActivityWatch's core privacy model, where sync should be decentralized (via Syncthing, Dropbox, or self-hosted servers), not centralized.

If you want cloud sync, run this server on infrastructure you control — a home server, a private VPS, etc.

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
- [ActivityWatch privacy policy](https://docs.activitywatch.net/en/latest/privacy-policy.html)
- [aw-sync (Rust, decentralized)](https://github.com/ActivityWatch/aw-server-rust/tree/master/aw-sync) — the official approach using file-based sync

