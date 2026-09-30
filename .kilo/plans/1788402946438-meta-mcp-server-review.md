# Review Plan — Meta Marketing MCP Server

## Scope
Review the `meta-mcp-server` codebase (v2.0.0) for correctness, security, reliability, and functional completeness. No source edits; produce findings + prioritized remediation plan.

## Current State Summary
- **201 tools + 44 resources + 44 prompts** across 22 modules
- **Safety-first**: writes OFF by default, 7-guard chain, dry-run, budget caps, RBAC, audit logging
- **Tests**: 100% mocked SDK, no live Graph API integration tests
- **CI**: lint, typecheck, security audit, tests, docker, pypi publish, docs deploy
- **Architecture**: per-module registration, FastMCP stdio/HTTP, FastAPI webhook receiver

## Findings (Prioritized)

### P0 — Functional Blockers
1. **Scheduler does not execute tasks** (`src/scheduler.py:228-234`): `run_due_tasks` marks tasks as "done" without dispatching to actual MCP tools. APScheduler jobs are `lambda: None` no-ops. This makes scheduled task execution non-functional.
2. **Async throttle semaphore leak** (`src/throttle.py:221-255`): `async_concurrency_limit` wrapper never calls `_release_slot()`. Under async tool load, the semaphore is acquired but never released, eventually deadlocking all async API calls.

### P1 — Security
3. **Incomplete audit-log PII stripping** (`src/helpers.py:391`): `_audit_log` strips params containing `"token"` but misses `"secret"`, `"password"`, `"api_key"`, `"app_secret"`. Sensitive fields may leak to `audit.jsonl`.
4. **Webhook server CORS missing** (`webhook_server.py`): No CORS headers on `/webhook/meta` or `/metrics`. Browsers may block legitimate cross-origin Meta webhook deliveries.
5. **Deprecated FastAPI startup hook** (`webhook_server.py:33`): `@app.on_event("startup")` is deprecated in FastAPI 0.100+ and will be removed. Should use lifespan events.

### P2 — Reliability
6. **Webhook metrics not thread-safe** (`webhook_server.py:28`): `_metrics` dict uses plain `+=` without locks. Concurrent webhook POSTs can lose/corrupt event counters.
7. **Blocking `time.sleep` in async-capable paths** (`src/instagram.py:953`, `src/yemen_bundle.py:179,211,216`, `src/pages.py:155`): `time.sleep()` blocks the thread. In async contexts (webhook server, FastAPI) this starves the event loop.
8. **Zero live integration tests**: All 101 tests use mocked SDK. Graph API v27 drift, field renames, and permission errors will only surface in production.
9. **Prometheus summary format incorrect** (`src/metrics.py:90-97`): Exports `tool_duration_seconds` as `TYPE summary` but emits only a single quantile (0.5) + count/sum. Prometheus clients expect either `histogram` (with explicit buckets) or a proper `summary` with multiple quantiles.

### P3 — Design / Maintainability
10. **`evaluate_guard` `spend_cap` dead parameter** (`src/helpers.py:355-379`): Accepts `spend_cap` but there is no `FB_ADS_MAX_SPEND_CAP` env var. The parameter is never enforced.
11. **RBAC heuristic matching** (`src/helpers.py:406-417`): `_check_rbac` uses substring matching on tool names (`"create"`, `"update"`, etc.) to infer required tasks. This is fragile and will misclassify tools like `create_webhook_automation` (requires MANAGE, not ADVERTISE).
12. **`_fetch_page_access_token` at startup** (`src/helpers.py:73-92`): Called during `init_page_api()` / `get_page_api()`. If `me/accounts` fails (network, permissions), it crashes the first page-token request rather than failing fast at startup.
13. **Dead code**: `async_api_call` and `async_page_api_call` (`src/helpers.py:313-347`) are defined but not used by any module.
14. **Instagram carousel product-tagging distribution logic** (`src/instagram.py:376-394`): Complex round-robin with multiple modulo operations and edge-case branches. High risk of assigning wrong products to wrong slides or exceeding the 5-per-slide limit.

## Validation Plan
1. Run `pytest -q` (blocked by permissions; verify after environment fix)
2. Run `ruff check src/` and `mypy src/`
3. Manually verify scheduler task dispatch with a live due task
4. Load-test webhook endpoint with 50 concurrent POSTs and verify `_metrics` counters
5. Audit `audit.jsonl` for leaked secrets after running a write-guarded tool

## Open Questions
- Should scheduler execution dispatch via actual MCP tool invocation (requires MCP client context), or remain as dry-run simulation?
- Should `FB_ADS_MAX_SPEND_CAP` be added to enforce the `spend_cap` parameter in `evaluate_guard`?
- Should live integration tests be gated behind `FB_LIVE_TESTS=true` per Phase 11, or added to CI with a sandbox account?

## Recommended Execution Order
1. Fix P0-1 (async throttle leak) — 30 min
2. Fix P0-2 (scheduler execution) — 2h
3. Fix P1-3 (audit PII stripping) — 15 min
4. Fix P1-4 (webhook CORS) — 10 min
5. Fix P1-5 (FastAPI lifespan) — 20 min
6. Fix P2-6 (webhook metrics thread-safety) — 20 min
7. Fix P2-7 (blocking sleep → async) — 1h
8. Add P2-8 (integration test scaffold) — 3h
9. Fix P2-9 (Prometheus format) — 30 min
10. Address P3 items — 2h
