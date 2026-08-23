# ROADMAP — Meta Marketing MCP Server

> **Version:** 1.0.0 (2026-08-23) · 168 tools + 3 resources + 2 prompts · `pyproject.toml:1`
> **Stack:** Python 3.10+, `mcp[cli]==1.29.0`, `facebook-business==26.0.0`, `FastMCP` (`server.py:41`), `FastAPI` (`webhook_server.py:25`)
> **Status:** Stable, 84/84 tests pass, but 35 ruff + 15 mypy violations + 2 P0 runtime bugs remain — this roadmap starts there.

---

## 0. Vision

Build the **most complete, safe, and observable** local-first MCP for Meta Marketing (Facebook / Instagram / WhatsApp) — usable from Claude Desktop, Cursor, and opencode without ever leaking secrets or exceeding ad spend.

**Non-goals (v1.x):** Hosted SaaS, multi-tenant auth, billing UI. Those are v2+.

---

## 1. Where we are (Maturity Assessment)

| Area | State | Evidence |
|---|---|---|
| **Coverage** | **High** — 18 modules, ~5.6k LOC (`src/`) | `src/catalog.py` 23 tools, `src/instagram.py` 32 tools, `src/pages.py` 22 tools |
| **Safety** | **Good / leaky** — `FB_ENABLE_WRITES=false` default, `write_guard` (`src/helpers.py:251`), PII SHA-256 (`src/utils.py:172`), but `Dockerfile:16` copies `.env*` into image and `src/ads.py:124` uses `Path.cwd()` | Review 2026-08-23 |
| **Reliability** | **Medium** — global semaphore + retry (`src/throttle.py:23,77`), `handle_error()` (`src/helpers.py:158`), but `bulk_update_products` and `upload_custom_audience_csv` crash (`src/catalog.py:536`, `src/audiences.py:166`) | `pytest -q` 84 passed, mypy 15 errors |
| **DX / Docs** | **Strong** — `README.md:186` structure, `.env.example:29`, `scripts/validate_config.py:1`, CI lint/typecheck/test | Needs tool-count automation |
| **Ops** | **Manual** — `docker-compose.yml:1` missing env pass-through, no volume for `reports/webhooks/`, `opencode.json:4` disabled & name mismatch |  |

**Tech debt backlog (from review):** `src/helpers.py:39` missing `Path` import, `src/audiences.py:166` missing `allowed_root`, `src/catalog.py:536` `json` undefined, `src/instagram.py:3` missing `types-requests`, `src/reports.py:68` float/int.

---

## 2. Principles

1. **Safety first:** writes OFF by default, budget caps (`src/config.py:55`), HMAC verified webhooks (`webhook_server.py:37`).
2. **No network in tests:** keep `tests/conftest.py:12` mock pattern — extend, never weaken.
3. **One breaking change at a time:** Graph API `v26.0` pinned (`src/config.py:48`) — upgrade via `FB_API_VERSION`.
4. **Arabic-first DX:** tool descriptions + errors in Arabic, code comments in English.

---

## 3. Phases & Milestones

### Phase 0 — Stabilization (Weeks 1–2) · `P0`

Goal: make `main` shippable with zero known crashes.

| # | Deliverable | Files | Acceptance |
|---|---|---|---|
| 0.1 | Fix P0 runtime crashes | `src/catalog.py:536` → `_json.loads`, `src/audiences.py:166` → `sanitize_path(csv_path, REPORT_DIR)`, `src/helpers.py:1` add `from pathlib import Path` + `from __future__ import annotations` | `bulk_update_products` + `upload_custom_audience_csv` smoke tests green, `mypy src/` 0 errors for these |
| 0.2 | Secret hygiene | `Dockerfile:16` remove `COPY .env*`, add `.dockerignore`, `docker-compose.yml:9` add missing envs (`FB_WHATSAPP_PHONE_NUMBER_ID`, `FB_BUSINESS_ID`, `FB_COMMERCE_ACCOUNT_ID`, `FB_MAX_CONCURRENT`), rotate token documented | `docker history` shows no `.env`, `docker compose config` passes |
| 0.3 | Path scoping | `src/ads.py:124,160` scope to `BASE_DIR / "media"` not `Path.cwd()`, align with `src/instagram.py:151` | `ruff --select F821` 0 for `Path` |
| 0.4 | CI must be blocking | `.github/workflows/ci.yml` — require `ruff check` + `mypy --ignore-missing-imports src/` pass on PR | Branch protection on `main` |

**Exit criteria:** `ruff check src/ == 0`, `mypy src/ == 0` (or allow-listed), 84/84 tests + 2 new regression tests.

### Phase 1 — Quality & Consistency (Weeks 3–5)

| # | Deliverable | Detail |
|---|---|---|
| 1.1 | **Lint / types clean** | Fix 35 ruff (`pyproject.toml:22` — `E,W,F,I,B,UP,SIM,RUF`): `UP035` `typing.Dict→dict`, `UP007` `X|Y`, `I001` imports (`src/breakdowns.py:3`, `src/reports.py:258`), `SIM105` (`src/events.py:42`), `F401` (`src/audiences.py:164`). Add `types-requests` to `requirements-dev.txt:4`, fix `src/reports.py:68` float/int, `src/adsets.py:101` int→str. Run `ruff check --fix` then `ruff format`. |
| 1.2 | **Pagination unification** | Wrap all `*.get_campaigns` / `*.get_ads` with `src/utils.py:94 paginate()` (currently mixed: `src/campaigns.py:21` direct, `src/catalog.py:71` paginated). Ensures consistent `limit` + `max_pages` + cursor. |
| 1.3 | **Error contract** | Standardize `handle_error()` return shape: `{error, context, code?, subcode?, retry_after?}` — update `src/helpers.py:158` + docs. Add `code/subcode` to every `write_guard` rejection (`src/helpers.py:227`). |
| 1.4 | **Test coverage 90%+** | Extend `tests/conftest.py:51` `_TO_DICT_PATHS` to cover all 18 modules (currently 6), add `test_reports_excel`, `test_audience_hashing`, `test_webhook_signature_negative`, `test_sanitize_path_traversal`. Target `pytest --cov=src --cov-fail-under=80`. |
| 1.5 | **Config DX** | `scripts/validate_config.py:1` — add `FB_MAX_CONCURRENT` check, warn if `PAGE_ID`/`AD_ACCOUNT_ID` not discovered via `list_pages`/`list_ad_accounts`, auto-generate `opencode.json` snippet. Sync `README.md:54` table with `src/config.py:34-46`. |

### Phase 2 — Platform Completeness (Weeks 6–10) · `v1.1`

Fills gaps vs Graph API v26 and user requests. No breaking changes.

| # | Area | New / Improved Tools | Notes |
|---|---|---|---|
| 2.1 | **Instagram** | `publish_instagram_story` link sticker, `get_instagram_reels_insights`, `list_instagram_comments` pagination, Threads cross-post (if API GA) | Requires `instagram_content_publish` re-consent |
| 2.2 | **Pages** | `publish_page_reel`, `get_page_video_insights`, `list_page_post_reactions` | Uses page token (`src/helpers.py:93`) |
| 2.3 | **Ads** | `create_ad` Advantage+ audience toggle (`targeting_automation`), `get_adset_delivery_insights` | Align `src/adsets.py:88` default `targeting_automation` with API 2026 defaults |
| 2.4 | **Catalog** | `update_product_feed_schedule`, `get_product_feed_diagnostics`, `batch_update_products` via Batch API (fix of 0.1) | `src/catalog.py:360` |
| 2.5 | **Leads** | `subscribe_leadgen_webhook`, `get_lead_field_mapping` | Bridges `webhook_server.py:76` → `src/events.py:22` |
| 2.6 | **Reports** | `generate_campaign_report` incremental (append not overwrite), Google Sheets export (deferred from `README.md:184`) | Add `gspread` optional dep |
| 2.7 | **Tool-count automation** | Script `scripts/count_tools.py` counts `@mcp.tool` per `src/` and updates `README.md:5` + `pyproject.toml:4` description | Fixes 155 vs 168 drift |

### Phase 3 — Automation & Intelligence (Weeks 11–16) · `v1.2`

Theme: from **manual MCP** to **event-driven agent**.

| # | Deliverable | Design |
|---|---|---|
| 3.1 | **Webhook automations** | `webhook_server.py:54` `save_webhook_event()` → `src/events.py:22 push_webhook_event()` → new `src/automations_webhook.py`: rules `on_comment(keyword) → reply/hide`, `on_lead → add_to_audience`, `on_message → auto-reply` (opt-in, `FB_ENABLE_WRITES` gated). Persist rules in `reports/automations.json`. |
| 3.2 | **Scheduler** | MCP tool `schedule_task(cron, tool_name, params)` using APScheduler, stored in `reports/schedule.json`, executed via `src/throttle.py:23` semaphore. |
| 3.3 | **Creative assistant** | Enhance `src/creatives.py:1` + `src/resources_prompts.py:120` — `generate_ad_copy` (LLM prompt) + `generate_creative_template` now returns `primary_text/headline/description/cta` tested via `tests/test_tools_smoke.py:38`. Add `upload_image` → `generate_caption` chain. |
| 3.4 | **Audience intelligence** | `get_audience_overlap`, `estimate_reach` (Meta Reach Estimate API), `suggest_lookalike` — wraps `src/audiences.py:244` with validation `LOOKALIKE_TYPES` + `RETENTION_SECONDS_90D`. |
| 3.5 | **Safety rails v2** | Per-tool `spend_cap` check before `api_call`, `DRY_RUN` diff preview (show JSON diff), `ADS_ALLOW_ACTIVATE=false` still blocks `status=ACTIVE` (`src/helpers.py:232`). Add `FB_CONFIRM_WRITES` interactive confirm for `DELETE` tools. |

### Phase 4 — Observability & Scale (Weeks 17–20) · `v1.3`

| # | Deliverable | Detail |
|---|---|---|
| 4.1 | **Metrics** | Prometheus `/metrics` on `webhook_server.py:25` — counters `mcp_tool_calls_total{tool,status}`, histogram `mcp_tool_duration_seconds`, gauge `throttle.concurrent` (`src/throttle.py:48`). |
| 4.2 | **Tracing** | Propagate `correlation_id` (`src/utils.py:30`) through `api_call`/`page_api_call` + `CorrelationFormatter` (`src/utils.py:42`) — include in every `handle_error` + webhook log. Add `X-Correlation-ID` header to Graph calls. |
| 4.3 | **Rate-limit dashboard** | `reports/webhooks/` + `src/events.py:12` queue size → Grafana / small FastAPI `GET /dashboard` (idea from `README.md:182` “لوحة تحكم ويب”). Read-only, `FB_MCP_TOKEN` auth (`src/config.py:58`). |
| 4.4 | **Scale knobs** | `FB_MAX_CONCURRENT` env (`src/throttle.py:24`) → adaptive semaphore (backoff on `RATE_LIMIT_CODES` `src/throttle.py:36`), `async_concurrency_limit` for `resources_prompts.py:18` async resources. Document tuning in `README.md:71`. |
| 4.5 | **Persistence** | `REPORT_DIR` (`src/config.py:49`) volume mount in `docker-compose.yml:20`, rotation `reports/webhooks/event_*.json` (max 500, like `src/events.py:19` queue). |

### Phase 5 — Distribution & Ecosystem (Weeks 21–24) · `v1.4` / `v2.0`

| # | Deliverable | Detail |
|---|---|---|
| 5.1 | **Packaging** | Publish to PyPI `meta-mcp-server` (from `pyproject.toml:1`), `pipx install`, Docker Hub `ghcr.io/.../meta-mcp-server:latest` via CI. Semver. |
| 5.2 | **Opencode / Claude first-class** | Fix `opencode.json:4` (`enabled:true`, name `meta-marketing-pro` per `README.md:146`), add MCP Inspector test in CI (`mcp dev server.py` health). |
| 5.3 | **Graph API v27 prep** | Bump `FB_API_VERSION` default (`src/config.py:48`) + `facebook-business` SDK, deprecation watch for `campaign.objective` enum changes (`src/campaigns.py:72`). |
| 5.4 | **Docs site** | MkDocs with auto-generated tool reference from docstrings (`grep @mcp.tool`), Arabic + English. Replace manual `README.md:8` table. |
| 5.5 | **Community** | Issue templates, `CONTRIBUTING.md`, `SECURITY.md` (secret reporting), `CODEOWNERS`. |

---

## 4. Timeline (Gantt-ish)

```
Aug 23 2026  Sep          Oct          Nov          Dec  → Jan 2027
├─P0───────┤ P1────────┤ P2──────────────────┤ P3────────────────┤ P4──────────┤ P5──────────┤
v1.0.0 ──► v1.0.1 (hotfix) → v1.0.2 → v1.1.0 → v1.2.0 → v1.3.0 → v1.4.0 / v2.0
                      ▲ CI blocking     ▲ Sheets export    ▲ metrics    ▲ PyPI
```

**Today (2026-08-23) → P0 by 2026-09-06, P1 by 2026-09-27, P2 by 2026-10-25, P3 by 2026-11-30, P4 by 2026-12-20, P5 by 2027-01-31.**

---

## 5. Dependencies & Risks

| Risk | Mitigation |
|---|---|
| Meta deprecates `product_catalog` / `ad_rules` edges (`src/catalog.py:1`, `src/automation.py:12`) | Pin SDK, add `scripts/validate_config.py` API version check, feature-flag new edges |
| `FB_ACCESS_TOKEN` long-lived expiry | `discovery.py:87 debug_access_token` (`APP_ID|APP_SECRET`) + docs to rotate via System User token |
| Webhook HMAC bypass if `APP_SECRET` empty (`webhook_server.py:43`) | Fail-closed in prod: `if not APP_SECRET: log.error` + `WEBHOOK_REQUIRE_HMAC=true` env in Phase 1 |
| Excel generation `openpyxl==3.1.5` CVE | Dependabot + `pip-audit` in CI Phase 1 |
| Tool explosion (>200) hurts discoverability | Group via `server.py:67` module tags, generate `resources_prompts.py:120` prompts as shortcuts |

---

## 6. Metrics — How we know it works

* **Quality:** ruff 0, mypy 0, cov ≥80%, `pytest -q` <6s, `mcp dev server.py` starts <2s.
* **Safety:** zero `write_guard` bypass in tests, `reports/webhooks/` 100% HMAC-verified, no `.env` in image.
* **Usage:** `throttle.concurrent_count()` p95 < `MAX_CONCURRENT`, webhook `save_webhook_event` p95 <100ms.
* **Adoption:** `generate_*_report` used ≥10×/week, `publish_instagram_*` success rate ≥98%.

---

## 7. Out of Scope (v1.x)

* Multi-workspace / OAuth login — System User token only (`src/config.py:35`).
* Payment method create/delete — Meta disallows via API (`src/finance.py:105` note).
* Instagram caption edit in-place — Graph API limitation (`README.md:171`).

---

## 8. How to Contribute

1. Pick an item from Phase 0 → open PR with `Fixes #...`.
2. Run `pip install -r requirements-dev.txt && ruff check src/ && mypy src/ && pytest -q`.
3. Update `README.md:5` tool count via `scripts/count_tools.py` (Phase 2.7).

See `.github/workflows/ci.yml` for required checks.

---

*Last updated: 2026-08-23 · Maintainer: review via `src/helpers.py:251 write_guard` — safe by default.*
