# Metrics & Dashboard

## Prometheus

`webhook_server.py` exposes `GET /metrics`:

```
# HELP mcp_tool_calls_total Total MCP tool invocations
mcp_tool_calls_total{tool="list_campaigns",status="ok"} 42
# HELP mcp_tool_duration_seconds MCP tool duration
mcp_tool_duration_seconds{tool="list_campaigns",quantile="0.5"} 0.042
# HELP meta_api_calls_total Meta Graph API calls
meta_api_calls_total{method="GET"} 120
# HELP meta_rate_limit_total Rate limit hits
# HELP throttle_concurrent Current concurrent Graph API calls
throttle_concurrent 2
# HELP process_uptime_seconds Process uptime
```

Scrape via Prometheus, visualize via Grafana.

## MCP tools

- `get_metrics(format=json|prometheus)` — snapshot
- `get_metrics_prometheus` — exposition
- `reset_metrics` — dev

## Dashboard

`GET /dashboard` — last 20 `reports/webhooks/event_*.json` + metrics badge. Protect with `FB_MCP_TOKEN` Bearer.

## Tracing

`correlation_id` (`src/utils:30`) set per tool via `throttle` wrapper, propagated as `_cid` param and `X-Correlation-ID` header, included in `handle_error` response and webhook `_correlation_id` field. View in logs (`CorrelationFormatter`) and `GET /dashboard`.

## Scale knobs

- `FB_MAX_CONCURRENT` (1–20, default 4) — semaphore `src/throttle:24`
- `FB_ADAPTIVE_THROTTLE=true` — cooldown 5s×attempt on `RATE_LIMIT_CODES` (`src/throttle:36`), `meta_rate_limit_total` metric

Tune via `docker-compose.yml` env or `GET /metrics` → Grafana alert on `rate_limit`.
