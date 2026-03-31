---
name: valyu-best-practices
description: General engineering best practices for the market analysis platform. Apply to all code.
---

## Valyu Best Practices

### Security
- Secrets live ONLY in `.env` (never committed)
- `DATABASE_URL`, `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `NEWS_API_KEY` — env only
- All API endpoints validate JWT before processing
- Admin endpoints check `role` claim in addition to JWT validity

### Data Integrity
- Market data flows: yfinance/NSE API → `collect_all_signals()` → `_sanitize_for_json()` → DB + WebSocket
- Never write raw Python `float('nan')` to PostgreSQL JSONB
- Always validate yfinance return values with `if val == val` (NaN check)

### Async Best Practices
- All DB operations: `async with AsyncSessionLocal() as session`
- All yfinance calls: `await loop.run_in_executor(None, lambda: yf.download(...))`
- Never block the event loop with synchronous I/O

### Logging
- Use `logging.getLogger(__name__)` in every module
- Info: normal operations (`logger.info("Collection complete: {n}/{total} fresh")`)
- Warning: expected failures (`logger.warning("FII fetch failed: {exc}")`)
- Error: unexpected failures with traceback (`logger.error("...", exc_info=True)`)
- Debug: verbose details (`logger.debug("...")`)

### Dependencies
- All Python deps pinned in `requirements.txt`
- `yfinance>=1.0.0` required (Yahoo changed API in 2024 — older versions return empty)
- `bcrypt==4.0.1` required (bcrypt 5.x broke passlib 1.7.4 compatibility)
- `anthropic>=0.40.0` required for current API

### Testing
- Integration tests use `httpx.AsyncClient` against the live backend
- No SQLite in tests (JSONB is PostgreSQL-only)
- Test credentials: `admin@marketplatform.io` / `Admin@123!`
- Run tests: `docker compose exec backend pytest`
