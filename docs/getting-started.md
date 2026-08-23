# Getting Started

## Install

```bash
pip install meta-mcp-server  # from PyPI (tag v1.4.0+)
# or
pipx install meta-mcp-server
# or dev
git clone https://github.com/ahmedalbanna/meta-mcp-server && cd meta-mcp-server
pip install -r requirements-dev.txt
```

## Configure

```bash
cp .env.example .env
# edit FB_ACCESS_TOKEN, FB_PAGE_ID, FB_AD_ACCOUNT_ID, FB_IG_USER_ID
python scripts/validate_config.py
```

Env table — see `README.md#متغيرات-.env`.

## Run

```bash
# MCP stdio (Claude/opencode)
python server.py
# inspector
mcp dev server.py
# webhook receiver
FB_META_WEBHOOK_VERIFY_TOKEN=secret python webhook_server.py  # :8080
# metrics
curl http://localhost:8080/metrics
# dashboard
open http://localhost:8080/dashboard
```

## opencode / Claude

`opencode.json`:

```json
{
  "mcp": {
    "meta-marketing-pro": {
      "type": "local",
      "command": ["python", "server.py"],
      "enabled": true
    }
  }
}
```

`claude_desktop_config.json`: see `README.md#الربط-مع-Claude-Desktop`.

## Validate

```bash
ruff check src/ && mypy src/ --ignore-missing-imports && pytest -q
python scripts/count_tools.py
```
