## What changed & why

## How tested
- [ ] `ruff check src/ && ruff format --check src/`
- [ ] `mypy src/ --ignore-missing-imports`
- [ ] `pytest -q` ( 101 passed )
- [ ] `python scripts/count_tools.py`
- [ ] `python scripts/generate_docs.py` (if tools changed)

## Checklist
- [ ] No `.env` committed
- [ ] `FB_ENABLE_WRITES` considered
- [ ] Docs updated (`docs/tools.md` if needed)
