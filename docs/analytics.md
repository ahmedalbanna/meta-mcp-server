# Analytics — `src/analytics.py`

> **Phase 1 of the analytics roadmap.** Stores daily/monthly analytics facts in SQLite
> (`src/persistence`) so reports are reproducible and backfillable across runs instead of
> being overwritten in CSV/Excel files.

## Tools

| Tool | Description |
|---|---|
| `ingest_daily_facts` | Ingest one day of Graph API insights into SQLite for a given entity (account/campaign/adset/ad). |
| `ingest_daily_facts_range` | Ingest a date range of insights into SQLite. |
| `build_monthly_report` | Build a monthly snapshot from `daily_facts` (additive sum; reach approximated). |
| `zero_fill_check` | Return a daily series with zero-fill for a metric over a date range. |
| `backfill_daily` | Backfill a date range (delegates to `ingest_daily_facts_range`). |
| `prune_analytics` | Prune `daily_facts` older than `retention_days` (default from `FB_ANALYTICS_RETENTION_DAYS`). |
| `analytics_db_status` | Report the analytics DB path, row counts per table, schema version, and timezone. |

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `FB_ANALYTICS_DB_URL` | `sqlite:///reports/analytics.db` | SQLite database URL. |
| `FB_ANALYTICS_RETENTION_DAYS` | `1110` | Days of daily facts to retain. |
| `FB_TZ` | `Asia/Aden` | Timezone for date windows. |
| `FB_CURRENCY_DEFAULT` | `YER` | Default currency when none returned by the API. |
| `FB_AD_ACCOUNT_ID` | — | Default ad account id (used when `account_id` is omitted). |
| `FB_AD_ACCOUNT_IDS` | — | Comma-separated list of ad account ids. |

## Pure helpers (testable offline)

- `normalize_date_range(preset, tz_name)` → `(start_iso, end_iso)` — converts a `date_preset` into ISO dates.
- `zero_fill_daily(series, start, end)` → one row per day, filling missing days with `0.0`.
- `ADDITIVE_METRICS` — `{"spend", "impressions", "clicks", "reach", "frequency"}`.
- `NON_ADDITIVE` — `{"ctr", "cpc", "cpm"}` (derived from additive metrics).

## Persistence layer

Facts are stored via `src.persistence` (SQLite, WAL mode):

| Table | Primary key |
|---|---|
| `daily_facts` | `(account_id, level, entity_id, metric_date, metric)` |
| `monthly_snapshots` | `(account_id, level, entity_id, year, month, metric)` |
| `competitor_snapshots` | `(platform, handle, snapshot_date)` |

See [Persistence](persistence.md) for the full store reference.
