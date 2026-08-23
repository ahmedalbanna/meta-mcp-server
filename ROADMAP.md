# ROADMAP — Meta Marketing MCP Server

> **Version:** 1.4.0 (2026-09-18) · 199 tools + 44 resources + 44 prompts · `pyproject.toml:1` — **distributed per-module** (no `resources_prompts` central)
> **Stack:** Python 3.10+, `mcp[cli]==1.29.0`, `facebook-business==26.0.0`, `FastMCP` (`server.py:41`), `FastAPI` (`webhook_server.py:25`)
> **Status:** ✅ Phases 0–5 complete — `ruff` 0, `mypy` 0, 101 tests, Docker `ghcr.io`, MkDocs auto-docs. Next: Hardening → 2.0.

---

## 0. Vision

Build the **most complete, safe, and observable** local-first MCP for Meta Marketing (Facebook / Instagram / WhatsApp) — usable from Claude Desktop, Cursor, and opencode without ever leaking secrets or exceeding ad spend.

**Non-goals (v1.x):** Hosted SaaS, multi-tenant auth, billing UI. Those are v2+.

---

## 1. Where we are (Maturity Assessment) — Updated 2026-09-18

| Area | State | Evidence |
|---|---|---|
| **Coverage** | **Very High** — 22 modules, ~8k LOC (`src/`), 199 tools +44R+44P distributed | `ads:10/1/1`, `instagram:35/2/2`, `catalog:26/2/2`, `pages:25/2/2` — all modules now have 2R+2P per-module |
| **Safety** | **Strong** — 5-guard (`ENABLE_WRITES`, `DRY_RUN` diff, `ADS_ALLOW_ACTIVATE`, budget caps, `CONFIRM_WRITES`), `sanitize_path` to `BASE_DIR`, HMAC, `.dockerignore` | `helpers.py:251` `write_guard`, `config.py:58` `CONFIRM_WRITES` |
| **Reliability** | **High** — global adaptive throttle (`throttle.py:22`), `handle_error` with `code/subcode/correlation_id`, `paginate` unified | `throttle.py:136` `concurrency_limit` + metrics, `pytest -q` 101 passed |
| **DX / Docs** | **Excellent** — `scripts/count_tools.py`, `scripts/generate_docs.py` → `docs/tools.md`, `mkdocs.yml` material, `CONTRIBUTING/SECURITY` | `README.md:5` `199 أداة +44 موارد +44 مطالبات` |
| **Ops** | **Automated** — `docker-compose` volumes, `ci.yml` lint/typecheck/test/inspector/docker/publish, `/metrics` + `/dashboard` | `webhook_server.py:82` `/metrics`, `metrics.py:142` `get_metrics` |

**Completed:** Phases 0–5 (see below). **Next:** 5.6 Hardening → 6 Performance → 7 AI → 8 Enterprise → 9 v2.0.

---

## 2. Principles

1. **Safety first:** writes OFF by default, budget caps (`src/config.py:55`), HMAC verified webhooks (`webhook_server.py:37`).
2. **No network in tests:** keep `tests/conftest.py:12` mock pattern — extend, never weaken.
3. **One breaking change at a time:** Graph API `v26.0` pinned (`src/config.py:48`) — upgrade via `FB_API_VERSION`, deprecation map in `campaigns.py:70`.
4. **Arabic-first DX:** tool descriptions + errors in Arabic, code comments in English.
5. **Per-module ownership:** every module owns its tools + resources + prompts (no central `resources_prompts`).

---

## 3. Phases & Milestones — ✅ Complete vs 🚀 Next

### Phase 0 — Stabilization (Weeks 1–2) · `P0` — ✅ Done `85c575e`

| # | Deliverable | Files | Acceptance |
|---|---|---|---|
| 0.1 | Fix P0 runtime crashes | `src/catalog.py:536` → `_json.loads`, `src/audiences.py:166` → `sanitize_path(csv_path, BASE_DIR)`, `src/helpers.py:1` add `Path` + `from __future__ import annotations` | `bulk_update_products` + `upload_custom_audience_csv` green, `mypy` 0 |
| 0.2 | Secret hygiene | `Dockerfile:16` remove `COPY .env*`, add `.dockerignore`, `docker-compose.yml:9` add missing envs | `docker history` no `.env` |
| 0.3 | Path scoping | `src/ads.py:124` scope to `BASE_DIR` | `ruff F821` 0 |
| 0.4 | CI must be blocking | `ci.yml` lint/typecheck/test blocking | Branch protection |

**Exit:** `ruff` 0, `mypy` 0, 101 tests.

### Phase 1 — Quality & Consistency (Weeks 3–5) — ✅ Done `8b5c4e7`

| # | Deliverable | Detail |
|---|---|---|
| 1.1 | **Lint / types clean** | 35 ruff → 0, 15 mypy → 0, `types-requests`, `ruff format` |
| 1.2 | **Pagination unification** | Wrap `list_campaigns/adsets/ads/ad_creatives/audiences` with `utils.paginate` |
| 1.3 | **Error contract** | `handle_error` → `{error, context, code, subcode, correlation_id}`, `write_guard` → `GUARD_*` |
| 1.4 | **Test coverage** | `conftest _TO_DICT_PATHS` 6→22, `test_phase1_coverage.py` 14 tests — 101 passed |
| 1.5 | **Config DX** | `validate_config.py` `FB_MAX_CONCURRENT` check + hints + `opencode.json` snippet, `README` sync |

### Phase 2 — Platform Completeness (Weeks 6–10) · `v1.1` — ✅ Done `ecfa96e`

| # | Area | New / Improved Tools | Notes |
|---|---|---|---|
| 2.1 | **Instagram** | `list_instagram_comments` (paginate), `get_instagram_reels_insights`, `publish_threads_post` | `instagram.py:35` |
| 2.2 | **Pages** | `publish_page_reel`, `get_page_video_insights`, `list_page_post_reactions` | `pages.py:25` |
| 2.3 | **Ads** | `create_adset` `advantage_audience` toggle, `get_adset_delivery_insights` | `adsets.py:72` |
| 2.4 | **Catalog** | `get_product_feed`, `update_product_feed_schedule`, `get_product_feed_diagnostics` | `catalog.py:26` |
| 2.5 | **Leads** | `subscribe_leadgen_webhook`, `get_lead_field_mapping` | `leads.py:7` |
| 2.6 | **Reports** | `generate_campaign_report` `mode=append`, `export_report_to_google_sheets` (`sheets` extra) | `reports.py:5` |
| 2.7 | **Tool-count automation** | `scripts/count_tools.py` counts 199 tools → `README` + `pyproject` | Fixes 155→199 drift |

### Phase 3 — Automation & Intelligence (Weeks 11–16) · `v1.2` — ✅ Done `4dc6ee1`

| # | Deliverable | Design |
|---|---|---|
| 3.1 | **Webhook automations** | `webhook_automations.py`: `list/create/delete/evaluate/run_webhook_automations` on `comment_keyword/lead_created/message_received` → `reply/hide/send/add_to_audience` (`reports/automations.json`) |
| 3.2 | **Scheduler** | `scheduler.py`: `schedule_task(cron/run_at)`, `list/cancel/get/run_due` on `reports/schedule.json` (APScheduler cron optional) |
| 3.3 | **Creative assistant** | `creatives.py`: `generate_ad_copy` (5 variations, tone/lang) + `generate_caption_from_image` (style stub) |
| 3.4 | **Audience intelligence** | `audiences.py`: `get_audience_overlap`, `estimate_reach` (`reachestimate`), `suggest_lookalike` (heuristics) |
| 3.5 | **Safety rails v2** | `FB_CONFIRM_WRITES` for `delete`, `DRY_RUN` diff preview (`helpers.py:251`), `write_guard` stripping `confirm` |

### Phase 4 — Observability & Scale (Weeks 17–20) · `v1.3` — ✅ Done `1f1f97f`

| # | Deliverable | Detail |
|---|---|---|
| 4.1 | **Metrics** | `src/metrics.py` in-memory Prometheus: `mcp_tool_calls_total`, `mcp_tool_duration_seconds`, `meta_api_calls_total`, `meta_rate_limit_total`, `webhook_events_total` + `get_metrics`/`get_metrics_prometheus`/`reset_metrics` |
| 4.2 | **Tracing** | `correlation_id` (`utils.py:30`) via `throttle` wrapper → `helpers.api_call` `_cid`+`X-Correlation-ID` → `handle_error` + webhook `_correlation_id` |
| 4.3 | **Dashboard** | `webhook_server.py:108` `GET /dashboard` (queue, throttle, tools, adaptive badge, Bearer `FB_MCP_TOKEN`) + `GET /metrics` merges `metrics.render_prometheus` + `GET /health` |
| 4.4 | **Scale knobs** | `FB_MAX_CONCURRENT` (1–20) + `FB_ADAPTIVE_THROTTLE=true` (cooldown 5s×attempt on `RATE_LIMIT_CODES`), `throttle.concurrent_count` gauge |
| 4.5 | **Persistence** | `reports/webhooks/event_*.json` rotation 500, `docker-compose` volumes `reports/`+`media/`, `config.ADAPTIVE_THROTTLE`/`AUTO_RUN` |

### Phase 5 — Distribution & Ecosystem (Weeks 21–24) · `v1.4` — ✅ Done `408c7d2` + `5944cd1`

| # | Deliverable | Detail |
|---|---|---|
| 5.1 | **Packaging** | `pyproject 1.3→1.4.0` authors/urls/scripts (`meta-mcp-server`, `meta-webhook`), `Dockerfile` labels/healthcheck/`pip install -e .`, `ci.yml` `docker`/`publish-pypi` on tag |
| 5.2 | **Opencode / Claude** | `opencode.json` `enabled:true` `meta-marketing-pro`, `ci.yml` `inspector` job (tool count ≥190) |
| 5.3 | **Graph v27 prep** | `config.SUPPORTED_API_VERSIONS` v24–v27, `campaigns._DEPRECATED_OBJECTIVES` map with warning, `facebook-business` 26→27 ready |
| 5.4 | **Docs site** | `mkdocs.yml` material, `docs/index/getting-started/webhooks/metrics` + `scripts/generate_docs.py` → `docs/tools.md` (199 tools) |
| 5.5 | **Community** | `CONTRIBUTING.md`, `SECURITY.md`, `CODEOWNERS`, `ISSUE_TEMPLATE/*`, `pull_request_template.md` |
| 5.6 | **Per-module distribution** | `resources_prompts` (10+10 central) → 22 modules ×2R+2P each = **44R+44P distributed**, `server.py`/`conftest.py` updated, `5944cd1` |

---

## 3b. NEXT — What’s Next (Post 1.4.0 → 2.0)

### Phase 5.6 — Hardening (1w) · `v1.4.1`

| # | Task | File | Acceptance |
|---|---|---|---|
| 5.6.1 | SDK 27 + API v27 smoke | `pyproject` `facebook-business==27.0`, `config.GRAPH_VERSION` default `v27.0`, `campaigns` objectives e2e | `pytest` green on `v27` |
| 5.6.2 | Security audit | `pip-audit`, `dependabot.yml`, `pre-commit` (ruff/mypy) | 0 CVEs |
| 5.6.3 | `pre-commit` + `git hooks` | `.pre-commit-config.yaml` | `git commit` runs `count_tools`+`generate_docs` |

### Phase 6 — Performance (3w) · `v1.5.0`

| # | Task | Detail |
|---|---|---|
| 6.1 | Adaptive paginate | `utils.paginate` `max_pages` adaptive (stop on `after==null`), `cached(ttl)` on `get_*_insights` |
| 6.2 | Batch Catalog 1k | `catalog.batch_create_products` 100→1000 items, chunked `Batch API` |
| 6.3 | Benchmark | `pytest --cov 85%`, `throttle` p95 <200ms, `list_*` p95 <400ms, `k6` load 20 concurrent |

### Phase 7 — AI Intelligence (4w) · `v1.6.0`

| # | Task | Detail |
|---|---|---|
| 7.1 | LLM creative | `creatives.generate_ad_copy` → real LLM (`LLM_API_KEY`, `OPENAI_API_KEY`) fallback to template |
| 7.2 | Vision caption | `generate_caption_from_image` → Vision (`gpt-4o`/`claude-vision`) |
| 7.3 | Insights anomaly | `insights:anomaly_detect` (CTR drop >20%), `audience:suggest_targeting` LLM |

### Phase 8 — Enterprise (4w) · `v1.7.0`

| # | Task | Detail |
|---|---|---|
| 8.1 | Multi-account | `FB_AD_ACCOUNT_IDS=act_1,act_2` (`config`) + per-tool `ad_account_id` override, `AD_ACCOUNT_ID` fallback |
| 8.2 | RBAC + Audit | `FB_MCP_TOKEN` per-tool `tasks` (ADVERTISE/ANALYZE), `reports/audit.jsonl` append on every `write_guard` |
| 8.3 | Scheduler persistence | `apscheduler` `SQLAlchemy` `reports/scheduler.db`, `run_due` daemon in `webhook_server` |

### Phase 9 — v2.0 Ecosystem (2w) · `v2.0`

| # | Task | Detail |
|---|---|---|
| 9.1 | Registry | `mcp-remote` SSE, `mcp publish` to MCP Registry, `pipx` stable |
| 9.2 | CLI | `meta-mcp --help`, `meta-mcp doctor`, `meta-mcp count-tools` entry points |
| 9.3 | Docs versioned | `mike` `gh-pages` versioned `1.4`/`2.0`, `ROADMAP` archived |

**Timeline next:**

```
Sep 18 2026   Oct          Nov          Dec          Jan 2027 → 2.0
├─5.6(1w)─┤─6(3w)──────┤─7(4w)────────┤─8(4w)────────┤─9(2w)─┤
v1.4.0 ─→ v1.4.1 → v1.5.0 → v1.6.0 → v1.7.0 → v2.0
     ▲ dependabot   ▲ p95<400ms   ▲ LLM    ▲ multi-acct ▲ registry
```

**Immediate next (pick one):**
- **6 Performance** — fastest ROI for large catalogs.
- **7 AI** — biggest demo impact if `LLM_API_KEY` available.

---

## 4. Dependencies & Risks

| Risk | Mitigation |
|---|---|
| Meta deprecates `product_catalog` / `ad_rules` edges (`catalog.py`, `automation.py`) | Pin SDK, `validate_config` API version check, feature-flag |
| `FB_ACCESS_TOKEN` expiry | `debug_access_token` + System User token docs |
| Webhook HMAC bypass if `APP_SECRET` empty | `webhook_server` warn + `FB_MCP_TOKEN` auth |
| Tool explosion (199) discoverability | Per-module R/P (2 each) as shortcuts, `server.py` module tags, `docs/tools.md` search |
| `openpyxl` CVE | `dependabot` + `pip-audit` in `ci.yml` (Phase 5.6) |

---

## 5. Metrics — How we know it works

* **Quality:** `ruff` 0, `mypy` 0, `cov ≥85%`, `pytest -q` <6s, `mcp dev` <2s.
* **Safety:** 0 `write_guard` bypass in tests, `reports/webhooks/` 100% HMAC, no `.env` in image.
* **Observability:** `/metrics` scrape `mcp_tool_calls_total`, `throttle_concurrent` p95 <`MAX_CONCURRENT`, `save_webhook_event` p95 <100ms.
* **Adoption:** `generate_*_report` ≥10×/week, `publish_instagram_*` ≥98% success.

---

## 6. Out of Scope (v1.x)

* Multi-workspace / OAuth login — System User token only (`config.py:35`). → **v1.7**
* Payment method create/delete — Meta disallows (`finance.py:105`). 
* Instagram caption edit in-place — Graph limitation (`README.md:171`). → workaround `update_instagram_media_caption`.

---

## 7. How to Contribute

1. Pick an item from **Next** → open PR with `Fixes #...`.
2. Run `pip install -r requirements-dev.txt && ruff check src/ && mypy src/ && pytest -q`.
3. Run `python scripts/count_tools.py && python scripts/generate_docs.py` if tools changed.

See `.github/workflows/ci.yml` for required checks.

---

*Last updated: 2026-09-18 · 1.4.0 (199+44+44 distributed) · Maintainer: `helpers.write_guard` — safe by default.*

