# ROADMAP — Meta Marketing MCP Server

> **Version:** 2.0.0 (2026-09-25) · 201 tools + 44 resources + 44 prompts · `pyproject.toml:1` — **distributed per-module**, `meta-mcp` CLI, `mcp.json` Registry manifest
> **Stack:** Python 3.10+, `mcp[cli]==1.29.0`, `facebook-business>=26,<28`, `FastMCP` (`server.py:41`), `FastAPI` (`webhook_server.py:25`)
> **Status:** ✅ Phases 0–9 complete (`v1.0.0 → v2.0.0`) — `ruff`/`mypy` 0, 101 tests, PyPI/Docker/mike ready. Next: **Phase 10 Release Ops** → live-world hardening.

---

## 0. Vision

Build the **most complete, safe, and observable** local-first MCP for Meta Marketing (Facebook / Instagram / WhatsApp) — usable from Claude Desktop, Cursor, opencode, and any MCP client without ever leaking secrets or exceeding ad spend.

**Non-goals (v2.x):** Hosted SaaS billing UI. Multi-user OAuth arrives in Phase 15 (`v3.0`).

---

## 1. Where we are (Maturity Assessment) — Updated 2026-09-25

| Area | State | Evidence |
|---|---|---|
| **Coverage** | **Very High** — 22 modules, ~9k LOC, 201 tools +44R+44P distributed | `instagram:35/2/2`, `catalog:26/2/2`, `pages:25/2/2`, `ads:10/1/1` |
| **Safety** | **Enterprise** — 7-guard (`ENABLE_WRITES`, `DRY_RUN` diff, `ADS_ALLOW_ACTIVATE`, budget caps, `CONFIRM_WRITES`, RBAC `MCP_ALLOWED_TASKS`, audit `audit.jsonl`) | `helpers.py:389` `_check_rbac`+`_audit_log` |
| **Reliability** | **High** — adaptive throttle, cached insights, chunked batch 1k, multi-account `resolve_ad_account_id` | `throttle.py:22`, `catalog.py:346` chunks 500×2 |
| **Intelligence** | **AI-ready** — LLM creative/vision/targeting/anomaly with template fallback | `src/llm.py`, `creatives.generate_ad_copy source:llm\|template` |
| **Distribution** | **Ready** — `mcp.json` Registry manifest, `meta-mcp` CLI, `mike` versioned docs, PyPI/ghcr CI on tag | `src/cli.py:1`, `ci.yml:108,130` |

---

## 2. Principles

1. **Safety first:** writes OFF by default, 7-guard chain in `write_guard` (`helpers.py:411`).
2. **No network in tests:** mocked SDK pattern (`tests/conftest.py`) — live tests are opt-in only.
3. **One breaking change at a time:** Graph v27 default (`config.GRAPH_VERSION`), deprecation maps.
4. **Arabic-first DX:** Arabic tool docs/errors, English code comments; i18n toggle planned Phase 13.
5. **Per-module ownership:** each module owns its tools/resources/prompts.

---

## 3. Shipped Phases — ✅ `v1.0.0 → v2.0.0`

| Phase | Version | Commit | Summary |
|---|---|---|---|
| 0 Stabilization | `v1.0.x` | `85c575e` | P0 crashes fixed, secret hygiene, path scoping, blocking CI |
| 1 Quality | — | `8b5c4e7` | ruff/mypy→0, paginate unified, error contract, coverage+tests |
| 2 Platform | `v1.1.0` | `ecfa96e` | IG/Pages/Ads/Catalog/Leads/Reports completeness, count_tools script |
| 3 Automation | `v1.2.0` | `4dc6ee1` | webhook automations, scheduler, creative assistant, audience intel, safety v2 |
| 4 Observability | `v1.3.0` | `1f1f97f` | Prometheus metrics, correlation tracing, dashboard, adaptive throttle, rotation |
| 5 Distribution | `v1.4.0` | `408c7d2`+`5944cd1` | packaging, per-module R/P distribution (no central module), docs site, community files |
| 5.6 Hardening | `v1.4.1` | `2ff6f8e` | SDK 27 range, API v27 default, pip-audit, dependabot, pre-commit |
| 6 Performance | `v1.5.0` | `c316e66` | adaptive paginate, cached insights, batch 1k, benchmark+k6 |
| 7 AI | `v1.6.0` | `f7e49c6` | `src/llm.py` OpenAI/Anthropic, LLM ad copy, vision caption, anomaly detect, suggest targeting |
| 8 Enterprise | `v1.7.0` | `14841c9` | multi-account, RBAC, audit.jsonl, APScheduler persistence |
| 9 Ecosystem | `v2.0.0` | `eb96c12` | mcp.json registry manifest, meta-mcp CLI, mike versioned docs, repo URLs |

---

## 4. NEXT — Post 2.0 (`v2.0.x` → `v3.0`)

### Phase 10 — Release Ops (immediate) · `v2.0.0` tag

Activate everything built — nothing is published yet.

| # | Task | Detail | Exit |
|---|---|---|---|
| 10.1 | Tag & publish | `git tag v2.0.0 && git push origin v2.0.0` → CI runs `publish-pypi` + `docs-deploy` + docker push | Package on PyPI, image on ghcr, docs at `ahmedalbanna.github.io/meta-mcp-server` |
| 10.2 | Registry submit | Submit `mcp.json` at registry.modelcontextprotocol.io | Listed in MCP Registry |
| 10.3 | Install smoke | `pipx install meta-mcp-server && meta-mcp doctor && meta-mcp run --transport sse` | doctor ok end-to-end |
| 10.4 | GitHub Release | Changelog from commits `85c575e..eb96c12`, attach wheel/sdist hashes | Release page published |

### Phase 11 — Live Validation (2w) · `v2.0.1`

Tests are fully mocked today — validate against real Graph v27.

| # | Task | Detail |
|---|---|---|
| 11.1 | Integration suite | `tests/integration/` gated by `FB_LIVE_TESTS=true` + sandbox account: list/create/update/delete happy paths for campaigns/adsets/ads/catalog |
| 11.2 | Drift fixes | Fix whatever real v27 responses break (field renames, permission errors) |
| 11.3 | Coverage ↑ | 54% → 70% via integration-informed unit tests |

### Phase 12 — New Meta Surfaces (4w) · `v2.1.0`

| # | Task | Detail |
|---|---|---|
| 12.1 | Conversions API | `src/capi.py`: `send_capi_event` (Pixel CAPI server-side, hashed PII reuse from `utils.normalize_pii`) |
| 12.2 | Offline conversions | `upload_offline_events` dataset API |
| 12.3 | Attribution | `get_attribution_windows_report` wrapper |
| 12.4 | Ads bulk | `create_ads_bulk` (bulk API endpoint, CSV read/write) |
| 12.5 | Threads GA | Revisit `publish_threads_post` when API GA; WhatsApp flows templates |

### Phase 13 — UX & i18n (3w) · `v2.2.0`

| # | Task | Detail |
|---|---|---|
| 13.1 | Bilingual tools | `FB_LANG=en\|ar` toggles tool descriptions/errors at registration time |
| 13.2 | Dashboard v2 | Charts (metrics history), audit.jsonl viewer, automation rules manager in `/dashboard` |
| 13.3 | Grafana export | Ship `grafana/meta-mcp-dashboard.json` scraping `/metrics` |

### Phase 14 — Plugin Ecosystem (3w) · `v2.3.0`

| # | Task | Detail |
|---|---|---|
| 14.1 | Plugin loader | `server.py` auto-discovers `plugins/*.py` exposing `register(mcp)` |
| 14.2 | Template marketplace | Community automation/prompt templates dir + loader, docs page |
| 14.3 | Module spec | Documented contract for third-party modules (tool/R/P naming, guard usage) |

### Phase 15 — OAuth Multi-user (4w) · `v3.0`

Was out-of-scope for v1/v2 — first breaking change of v3.

| # | Task | Detail |
|---|---|---|
| 15.1 | Meta OAuth login flow | Per-user user tokens vs System User token, token store encrypted |
| 15.2 | Tenant isolation | Per-user `AD_ACCOUNT_IDS`, RBAC per user, audit rows keyed by user |
| 15.3 | Hosted mode | Optional multi-tenant `streamable-http` deployment profile |

**Timeline:**

```
Sep 2026        Oct           Nov           Dec
├─10(now)─┤─11(2w)──────┤─12(4w)────────┤─13(3w)────┤─14(3w)────┤─15(4w)──► v3.0
v2.0.0 ──► v2.0.1 ─────► v2.1.0 ────────► v2.2.0 ────► v2.3.0
     ▲ tag+publish   ▲ live e2e    ▲ CAPI       ▲ bilingual ▲ plugins
```

---

## 5. Dependencies & Risks

| Risk | Mitigation |
|---|---|
| PyPI name collision on publish | Verify `meta-mcp-server` availability before tag; fallback name documented |
| Graph v27 field drift breaks tools | Phase 11 integration suite catches early; `handle_error` contract surfaces code/subcode |
| LLM key leakage | Keys only via env (`OPENAI_API_KEY`), never logged; `_audit_log` strips `*token*` params |
| Tool explosion discoverability | Per-module R/P shortcuts, `docs/tools.md` search, CLI `meta-mcp count-tools` |
| openpyxl/fastapi CVEs | dependabot weekly + pip-audit CI job (Phase 5.6) |

---

## 6. Metrics

* **Quality:** `ruff` 0, `mypy` 0, cov ≥70% (Phase 11), `pytest -q` <12s.
* **Safety:** 0 guard bypasses, 100% HMAC webhooks, audit.jsonl row on every write.
* **Observability:** `/metrics` p95 scrape <100ms, throttle_concurrent < MAX_CONCURRENT.
* **Adoption:** PyPI downloads ≥100/mo post-release, ≥98% publish success rate.

---

## 7. Out of Scope (until Phase 15)

* Multi-user OAuth — arrives `v3.0` (Phase 15).
* Payment method create/delete — Meta disallows (`finance.py`).
* Instagram caption edit in-place — workaround `update_instagram_media_caption`.

---

## 8. How to Contribute

1. Pick an item from **Phase 10–15** → open PR with `Fixes #...`.
2. `pip install -r requirements-dev.txt && ruff check src/ scripts/ && mypy src/ --ignore-missing-imports && pytest -q`.
3. If tools changed: `python scripts/count_tools.py && python scripts/generate_docs.py`.
4. Live tests require explicit opt-in: `FB_LIVE_TESTS=true pytest tests/integration/`.

See `.github/workflows/ci.yml` for required checks.

---

*Last updated: 2026-09-25 · v2.0.0 (201+44+44 distributed) · Next: Phase 10 Release Ops — tag `v2.0.0` and ship.*
