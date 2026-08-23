# Security Policy

## Reporting

- Do not open public issues for secrets or vulns.
- Email: `security@example.com` (replace) or use GitHub private security advisory.
- We aim to triage within 72h.

## Secrets

- Never commit `.env`. It is git-ignored and docker-ignored (`.dockerignore`).
- `Dockerfile:13` does not copy `.env`; inject via `docker-compose.yml:10 environment` or `--env-file`.
- Rotate a leaked System User token immediately via Meta Business Settings → System Users → Generate New Token; revoke old.

## Hardening in this repo

- `FB_ENABLE_WRITES=false` default, `FB_ADS_ALLOW_ACTIVATE=false`, budget caps `FB_ADS_MAX_*` (`src/config.py:52`, `src/helpers.py:219`).
- `sanitize_filename` / `sanitize_path` (`src/helpers.py:30,42`) scope file I/O to `BASE_DIR`.
- `verify_signature` HMAC (`webhook_server.py:37`) with `hmac.compare_digest`; skips only when `APP_SECRET` empty (dev) with warning.
- `PII` hashed SHA-256 by default (`src/utils.py:177`, `src/audiences.py:104`).

## Webhook

- `FB_META_WEBHOOK_VERIFY_TOKEN` must match Meta dashboard.
- `/dashboard` is read-only; protect with `FB_MCP_TOKEN` Bearer if exposed.

## Dependency audit

Run `pip-audit` or `pip install -r requirements-dev.txt && pip list --outdated` before release. `openpyxl`, `fastapi` are pinned in `requirements.txt:4`.
