# Contributing

## Quick start

```bash
git clone <repo> && cd meta-mcp-server
cp .env.example .env  # fill FB_* vars
pip install -r requirements-dev.txt
ruff check src/ && mypy src/ && pytest -q
python scripts/validate_config.py
python scripts/count_tools.py
```

## Rules

1. **Writes off by default** — `FB_ENABLE_WRITES=false`. Guard every mutating tool with `@write_guard` (`src/helpers.py:246`) and include `code/subcode`.
2. **No network in tests** — use `tests/conftest.py:62 mock_meta_sdk`. Never add real HTTP calls.
3. **Paginate uniformly** — use `src/utils.py:95 paginate()` for every `list_*` (see `ROADMAP.md:60 1.2`).
4. **Arabic DX** — tool docstrings + user-facing errors in Arabic, code/comments in English, `handle_error` contract `{error, context, code, subcode}`.
5. **Tool count** — after adding/removing a tool, run `python scripts/count_tools.py` to sync `README.md:5` and `pyproject.toml:4`.
6. **Ruff + mypy must be green** — `ruff check src/ && ruff format --check src/ && mypy src/ --ignore-missing-imports`.
7. **Commit hygiene** — `git add` only intended files, never commit `.env`.

## Branch & PR

- Branch from `main`: `feat/<module>-<short>` or `fix/<issue>`.
- CI runs `lint / typecheck / test` (`.github/workflows/ci.yml`). All must pass.
- PR template: what changed, why, how tested, screenshots for dashboard changes.

## Adding a tool

1. Add `@mcp.tool()` inside `def register(mcp):` in `src/<module>.py`.
2. Wrap mutating tools with `@write_guard` (inner) + `@concurrency_limit()` (outer).
3. Use `handle_error(e, "tool_name")` for errors, `json_dumps` for returns.
4. Add smoke test in `tests/test_tools_smoke.py` or dedicated file.

## Security

See `SECURITY.md`. Do not paste tokens in issues/logs. Use `scripts/validate_config.py` which never prints secrets.
