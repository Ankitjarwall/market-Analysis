---
name: code-reviewer
description: Review code for project guidelines, security, and correctness. Run after writing or modifying code, especially before commits.
model: opus
---

## Code Reviewer Skill

### Review Scope
Default: review the diff of recently modified files. Can be scoped to specific files or directories.

### Project-Specific Rules (Market Platform)

**Backend (FastAPI / SQLAlchemy)**
- All DB operations must use `async with AsyncSessionLocal() as session`
- Never use `session.execute()` in a loop without batching
- All JSONB writes must pass through `_sanitize_for_json()` to prevent NaN
- JWT tokens must include `jti` (UUID) to prevent token collision
- Passwords hashed with bcrypt via passlib (never plain text or md5/sha)
- All API routes on `/api/*` must use `Depends(get_current_user)`
- Admin routes must additionally check `role IN ('admin', 'super_admin')`

**Frontend (React / Zustand)**
- All market data mutations must go through `marketStore.setMarketData()`
- Price displays must compare `marketData[key]` vs `previousData[key]` for delta
- No direct DOM manipulation — use React state/refs
- WebSocket events handled only in `useWebSocket.js`

### Bug Detection Checklist
- [ ] Null/None handling before arithmetic operations
- [ ] NaN propagation (especially in yfinance float parsing)
- [ ] Race conditions in async DB operations
- [ ] JWT expiry checked before use
- [ ] No bare `except:` without logging
- [ ] No hardcoded credentials or API keys
- [ ] SQL queries use parameterized values (SQLAlchemy ORM or `text()` with params)

### Confidence Scoring
- 90-100: Critical — must fix before merge (security issue, data corruption risk)
- 80-89: Important — should fix (logic error, missing validation)
- 50-79: Minor — consider fixing (style, simplification)
- < 50: Informational only

**Only report issues with confidence >= 80.**

### Output Format
Group by severity. For each issue include: file path, line number, rule violated, concrete fix.
If no issues found: confirm code meets standards.
