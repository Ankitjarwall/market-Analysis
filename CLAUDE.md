# Market Analysis Platform — Claude Code Guidelines

## Project Overview
AI-powered Nifty 50 / Indian equity market intelligence platform.
- **Backend**: FastAPI + SQLAlchemy async + PostgreSQL + Redis
- **Frontend**: React 19 + Vite + TailwindCSS + Zustand + WebSocket
- **AI**: Anthropic Claude for market briefs and signal analysis
- **Data**: yfinance (live prices), NSE India APIs (FII/DII, PCR), NewsAPI

## Skill Assignments by Task

### Frontend / UI Tasks → `frontend-design`
Apply for: React components, TailwindCSS styling, dashboard layout,
live price display, green/red color indicators, WebSocket-driven UI updates.
- All files in `frontend/src/`
- Prioritize: dark-mode consistency, real-time data presentation
- Color convention: `text-green-400` = price up, `text-red-400` = price down

### Code Review / Quality → `code-reviewer`
Apply for: PR reviews, audit of new code, checking for bugs before commit.
- Review checklist: async/await correctness, SQL injection prevention,
  JWT token handling, error boundary coverage
- Flag: any hardcoded credentials, missing input validation, bare except clauses

### Simplification / Refactoring → `simplify`
Apply for: reducing duplication, extracting reusable hooks/utils,
simplifying complex functions.
- Target files: `bot/collector.py`, `bot/analyzer.py`, `bot/scheduler.py`
- Rule: prefer explicit over clever; no premature abstraction

### General Best Practices → `valyu-best-practices`
Apply for: all code in this project. Key rules:
- Never store secrets in code — use `.env` (already configured)
- All market data mutations go through `marketStore.setMarketData()`
- All DB writes use `async with AsyncSessionLocal() as session`
- Sanitize NaN/Inf before JSONB writes (`_sanitize_for_json()` in scheduler.py)

### Security Testing → `shannon`
Apply for: API endpoint security review, WebSocket auth, JWT validation.
- Run `/shannon http://localhost:8000 backend-api` for pentest
- Key endpoints to test: `/auth/login`, `/ws/market`, `/api/admin/*`
- Authentication: JWT Bearer token required on all `/api/*` routes

### Database / PlanetScale → `planetscale`
Not applicable — this project uses PostgreSQL (not PlanetScale).
The DB connection is via `asyncpg` to a local Docker PostgreSQL container.

## Architecture Rules

### Backend
- Data collection: `bot/collector.py` → `bot/scheduler.py` → DB + WebSocket
- WebSocket broadcasts: every 2 seconds via `job_broadcast_live`
- Fast-tick prices: every 30 seconds via `job_fast_tick_prices`
- NaN safety: always call `_sanitize_for_json(data)` before JSONB writes

### Frontend
- All market data flows through `marketStore.js` (Zustand)
- `previousData` tracks prior snapshot for green/red delta computation
- Market-open detection: UTC-based, computed in `MarketTicker.jsx`
- WebSocket reconnects automatically with 3-second backoff

### Live Data Latency
- WebSocket broadcast: every 2 seconds
- yfinance fast-tick: every 30 seconds (during market hours)
- Scheduler full-collect: every 1 minute (IST market hours only)
- Target end-to-end latency: < 3 seconds from price change to UI update

## Key Files
| File | Purpose | Skill |
|------|---------|-------|
| `frontend/src/components/MarketTicker.jsx` | Live ticker with market-open dots | frontend-design |
| `frontend/src/pages/Dashboard.jsx` | Main dashboard with green/red prices | frontend-design |
| `frontend/src/store/marketStore.js` | Zustand state + previousData delta | frontend-design |
| `backend/bot/collector.py` | Market data collection (47 signals) | simplify |
| `backend/bot/scheduler.py` | APScheduler jobs, WebSocket broadcast | simplify |
| `backend/bot/analyzer.py` | Claude API integration for briefs | valyu-best-practices |
| `backend/auth/router.py` | JWT auth endpoints | code-reviewer + shannon |
| `backend/db/models.py` | SQLAlchemy ORM models | code-reviewer |

## Running the Project
```bash
docker compose up -d                    # Start all services
docker compose exec backend python db/seed.py    # Seed admin user
docker compose exec backend pytest      # Run tests
```

Admin credentials: `admin@marketplatform.io` / `Admin@123!` (change in production)
