# Market Intelligence Platform

A full-stack, AI-powered market intelligence system for Nifty 50 options trading. Features real-time data collection, AI-generated market briefs, automated options signal generation, trade tracking, self-healing infrastructure, and a Telegram bot.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic |
| Database | PostgreSQL + Redis |
| AI | Anthropic Claude (claude-sonnet-4-6) |
| Scheduler | APScheduler |
| Real-time | FastAPI WebSocket |
| Telegram | python-telegram-bot v21 |
| Frontend | React 18, Vite, TailwindCSS, Zustand, Recharts |
| Data | yfinance, NSE India, NewsAPI, RSS feeds |

## Quick Start

```bash
# 1. Clone and configure
git clone <repo>
cp .env.example .env
# Fill in your API keys in .env

# 2. Start all services
make dev

# 3. Run migrations
make migrate

# 4. Seed admin user
make seed

# 5. Open dashboard
open http://localhost:5173
```

## Development

```bash
make test          # Run all tests
make test-unit     # Unit tests only
make test-api      # API tests only
make logs          # Tail service logs
make db-shell      # PostgreSQL shell
make redis-cli     # Redis CLI
```

## Project Structure

```
market-Analysis/
├── backend/          # FastAPI application
│   ├── auth/         # JWT auth + RBAC
│   ├── api/          # REST endpoints
│   ├── bot/          # Data collector, scheduler, signal engine
│   ├── healing/      # Self-healing watchdog
│   ├── websocket/    # WebSocket server
│   ├── db/           # SQLAlchemy models + migrations
│   └── tests/        # All test suites
├── frontend/         # React + Vite application
│   └── src/
│       ├── pages/    # Route pages
│       ├── components/
│       ├── hooks/
│       └── store/    # Zustand state
├── data/             # Market data storage
├── logs/             # Application logs
└── reports/          # Generated reports
```

## Roles

| Role | Access |
|------|--------|
| super_admin | Everything |
| admin | All views + user management + bot config |
| analyst | Dashboard + signals + trades + manual entry |
| viewer | Live dashboard only |

## Disclaimer

⚠️ This system generates technical analysis signals for educational and tracking purposes only. Options trading carries significant risk. This is NOT SEBI-registered investment advice. Never trade more than you can afford to lose.
