---
name: Bug report
about: Create a report to help us improve
labels: bug
---

**Describe the bug**

**To Reproduce**
```bash
python scripts/validate_config.py
pytest -q
```

**Expected behavior**

**Logs**
- `FB_API_VERSION`:
- `mcp_tool` name:
- `correlation_id`:

**Checklist**
- [ ] `ruff check src/` passes
- [ ] `mypy src/ --ignore-missing-imports` passes
- [ ] No secrets in logs
