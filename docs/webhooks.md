# Webhooks & Automations

## Receiver

`webhook_server.py` — FastAPI `:8080`

> Query params use dotted names (`hub.mode`, `hub.verify_token`, `hub.challenge`) — mapped via `Query(alias=...)`; underscore args alone would never populate.

- `GET /webhook/meta?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...` — handshake
- `POST /webhook/meta` — ingest, verify `X-Hub-Signature-256`, save to `reports/webhooks/event_*.json` (500 rotation), push to `src/events` queue
- `GET /metrics` — Prometheus (`webhook_events_total`, `throttle_concurrent`)
- `GET /dashboard` — HTML last 20 events + metrics (Bearer `FB_MCP_TOKEN` if set)
- `GET /health` — liveness

```bash
FB_META_WEBHOOK_VERIFY_TOKEN=my_secret python webhook_server.py
curl http://localhost:8080/metrics

# Docker: receiver runs alongside the MCP server; host port mapping in docker-compose.yml
docker compose up -d --build   # MCP -> :18000, Webhooks -> :18080
```

## Automations (Phase 3.1)

`src/webhook_automations.py` — persisted `reports/automations.json`

- `list_webhook_automations`
- `create_webhook_automation(trigger, keyword, action_type, action_params_json)` — `comment_keyword|lead_created|message_received`
- `evaluate_webhook_automations(event_json)` — dry-run
- `run_webhook_automations(event_json, dry_run)` — executes `reply_comment/hide_comment/send_message/add_to_audience`

Auto-run: `FB_AUTO_RUN_WEBHOOK_AUTOMATIONS=true` logs would-run at ingest (execution via MCP for safety).
