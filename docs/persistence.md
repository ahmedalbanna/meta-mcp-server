# Persistence — `src/persistence.py`

> SQLite persistence for analytics facts and competitor snapshots. Central store so
> reports are reproducible across runs instead of being overwritten in CSV/Excel files.
> Uses WAL mode for safe concurrent access from multiple MCP processes.

## Schema

| Table | Primary key | Description |
|---|---|---|
| `schema_version` | `version` | Migration version (currently `1`). |
| `daily_facts` | `(account_id, level, entity_id, metric_date, metric)` | One row per account/level/entity/date/metric. |
| `monthly_snapshots` | `(account_id, level, entity_id, year, month, metric)` | Monthly rollups computed from daily facts. |
| `competitor_snapshots` | `(platform, handle, snapshot_date)` | Historical competitor snapshots. |

## Functions

| Function | Description |
|---|---|
| `init_db()` | Create schema (idempotent). Safe to call repeatedly. |
| `get_conn()` | Thread-local SQLite connection with WAL + `busy_timeout`. |
| `transaction()` | Context manager yielding a connection with commit/rollback. |
| `upsert_daily_fact(...)` | Insert or replace a daily fact row. |
| `query_daily_facts(account_id, level, entity_id, start_date, end_date, metric=None)` | Query daily facts for one entity in a date range. |
| `query_daily_facts_all_entities(account_id, level, start_date, end_date)` | Query daily facts for all entities in a date range. |
| `upsert_monthly_snapshot(...)` | Insert or replace a monthly snapshot row. |
| `query_monthly_snapshots(account_id, level, entity_id, year, month)` | Query monthly snapshots. |
| `upsert_competitor_snapshot(platform, handle, snapshot_date, payload)` | Insert or replace a competitor snapshot. |
| `query_competitor_snapshots(platform, handle, limit=30)` | Query competitor snapshots (newest first). |
| `prune_old_facts(days=ANALYTICS_RETENTION_DAYS)` | Delete `daily_facts` older than `days`. Returns deleted row count. |
| `close()` | Close the thread-local connection. |

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `FB_ANALYTICS_DB_URL` | `sqlite:///reports/analytics.db` | SQLite database URL. |
| `FB_ANALYTICS_RETENTION_DAYS` | `1110` | Days of daily facts to retain (used by `prune_old_facts`). |
| `FB_TZ` | `Asia/Aden` | Default timezone. |

## WAL mode

Connections are opened with `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000`,
so multiple MCP processes (or a webhook server + MCP server) can read/write the same
database concurrently without locking errors.
