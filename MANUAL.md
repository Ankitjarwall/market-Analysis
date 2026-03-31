# Market Intelligence Platform — Complete Reference Manual

> AI-powered Nifty 50 / Indian equity market intelligence platform.
> **For educational and tracking purposes only. Not SEBI-registered investment advice.**

---

## Table of Contents

### User Guide
1. [Getting Started — Login](#1-getting-started--login)
2. [Navigation Overview](#2-navigation-overview)
3. [Dashboard](#3-dashboard)
4. [Options & Predictions](#4-options--predictions)
5. [Self-Heal](#5-self-heal)
6. [Admin Panel](#6-admin-panel)
7. [System Monitor](#7-system-monitor)
8. [How the Signal Engine Works](#8-how-the-signal-engine-works)
9. [How the Learning Engine Works](#9-how-the-learning-engine-works)
10. [Roles & Permissions](#10-roles--permissions)
11. [Troubleshooting](#11-troubleshooting)

### Developer Reference
12. [Architecture Overview](#12-architecture-overview)
13. [Repository Structure](#13-repository-structure)
14. [Backend Deep-Dive](#14-backend-deep-dive)
15. [Frontend Deep-Dive](#15-frontend-deep-dive)
16. [Database Schema](#16-database-schema)
17. [API Endpoints Reference](#17-api-endpoints-reference)
18. [WebSocket Protocol](#18-websocket-protocol)
19. [Scheduler Jobs Reference](#19-scheduler-jobs-reference)
20. [Configuration & Environment Variables](#20-configuration--environment-variables)
21. [Running & Deploying](#21-running--deploying)
22. [Testing](#22-testing)
23. [Common Debugging Patterns](#23-common-debugging-patterns)

---

# USER GUIDE

## 1. Getting Started — Login

Open the app at `http://localhost` (or the configured URL).

| Field    | Value                          |
|----------|-------------------------------|
| Email    | `admin@marketplatform.io`     |
| Password | `Admin@123!`                  |

After logging in you land on the **Dashboard**. The sidebar on the left shows only the pages your role can access.

**Mobile:** tap the **☰** menu icon (top-left) to open the sidebar. Tap outside the sidebar or the **✕** button to close it.

---

## 2. Navigation Overview

| Page | Visible to | Purpose |
|------|-----------|---------|
| 📊 Dashboard | Everyone | Live market data, key signals, bot activity |
| ⚡ Options | Analyst + | Trade signals, capital settings, AI predictions |
| 🔧 Heal | Admin + | Self-healing watchdog status |
| 👥 Admin | Admin + | User management |
| 🖥 Monitor | Admin + | System logs, service health, data feed tests |

The **IST clock** at the bottom of the sidebar shows the current Indian Standard Time and two countdowns:
- **Price tick** — next fast-tick price refresh (every 10 seconds on weekdays)
- **Data collect** — next full 47-signal collection (every 1 minute during market hours)

---

## 3. Dashboard

### Market Status Banner

At the top: `● LIVE` (green pulsing dot) or `Market Closed` (grey).

The platform uses **two signals** to determine whether NSE is open:
1. **Time-based:** weekday, between 9:15 AM and 3:30 PM IST
2. **Data freshness:** the last yfinance `^NSEI` candle is < 20 minutes old

Both must be true for the banner to show LIVE. On NSE holidays, yfinance returns stale data from the prior day, so the freshness check fails automatically — no holiday calendar needed.

The backend polls `/api/market/status` every 60 seconds; the frontend never computes market-open status itself.

---

### Live Ticker Strip

A horizontal scrolling ticker showing:

| Symbol | Source |
|--------|--------|
| NIFTY 50 | yfinance `^NSEI` |
| BANK NIFTY | yfinance `^NSEBANK` |
| INDIA VIX | yfinance `^INDIAVIX` |
| S&P 500 | yfinance `^GSPC` |
| NASDAQ | yfinance `^IXIC` |
| Brent Crude | yfinance `BZ=F` |
| Gold | yfinance `GC=F` |
| USD/INR | yfinance `INR=X` |

Green ▲ / Red ▼ arrows show movement vs the previous broadcast snapshot. NSE instruments (Nifty, BankNifty, VIX) show the live/closed dot based on the backend's NSE open status; global instruments use a client-side UTC check for their own market hours.

---

### Key Metrics Row

Six metrics displayed as small cards:

| Metric | What it means | Source |
|--------|--------------|--------|
| India VIX | Market fear gauge | yfinance `^INDIAVIX` |
| PCR | Put-Call Ratio — <0.7 = bullish sentiment, >1.0 = bearish sentiment | NSE Options Chain API |
| FII (₹Cr) | Foreign institutional net flow | NSE FII/DII API |
| Nifty PE | Nifty 50 Price-to-Earnings ratio | NSE Indices API |
| USD/INR | Dollar–Rupee exchange rate | yfinance `INR=X` |
| US 10Y | US 10-year bond yield | yfinance `^TNX` |

Green ▲ / Red ▼ arrows show change vs. the previous broadcast.

---

### Live Market Prices Row

Bank Nifty, Brent Crude, Gold, USD/INR — with real-time updates.

---

### Data Freshness Indicator

`● 42/47 signals fresh` — shows how many of the 47 market signals were successfully collected in the last cycle. Green ≥40, Yellow ≥30, Red <30.

---

### Bot Activity Feed

A scrolling log of everything the bot did: signals generated, trades opened/closed, T1/T2/SL alerts, warnings. The most recent 30 events are shown.

---

## 4. Options & Predictions

> Requires **Analyst** role or higher.

### Capital & Trade Mode

**Capital (₹):** Set your total trading capital. This is used to calculate position sizes.
- Minimum: ₹10,000
- Maximum: ₹1,00,00,000 (₹1 crore)
- The label next to the field shows a human-readable version (e.g. `₹2 lakh`)
- Click **Save** to persist. The backend clamps and rejects values outside the allowed range.

**Trade Mode:**

| Mode | What happens when a signal fires |
|------|--------------------------------|
| ⚡ AUTO | Current market price is fetched from NSE. If price has moved >3% from Claude's expected LTP and the R:R falls below 2.0, the trade is **aborted** (slippage guard). Otherwise the trade is logged at the actual market price — no user action needed. |
| ✋ MANUAL | Signal is broadcast; you fill in entry premium and lots yourself |

---

### Active Signal Card

When the bot generates a signal, a card appears here showing:

| Field | Description |
|-------|-------------|
| BUY CALL / BUY PUT | Direction |
| R:R 1:X | Risk-to-reward ratio (must be ≥ 2.0 to generate) |
| Confidence % | Claude's confidence in this signal |
| STRIKE | Option strike price and type (CE/PE) |
| LTP | Last traded premium at signal time |
| T1 / T2 | Target 1 and Target 2 premiums (+ % gain shown) |
| Stop Loss | Exit if premium falls to this level (– % loss shown) |
| Signal Basis | Up to 4 reasons the signal was generated |

**AUTO mode:** a green banner confirms the trade was logged automatically.

**MANUAL mode:** enter your actual entry premium and number of lots, then click **Log Manual Trade**.

---

### Open Trades

Each open trade shows:
- Strike, option type, number of lots
- Entry premium and R:R
- **Live P&L** (unrealised, updates every 30 seconds via bot monitor)
- **Progress bar** from entry to T1
- After T1 hit: locked profit + trailing stop loss level

**Exit buttons:**

| Button | What it does |
|--------|-------------|
| Exit at T1 | Close at current premium, book T1 profit |
| Exit at T2 | Close entire position at T2 |
| Exit at SL | Close at stop-loss price |
| Manual Exit | Close at whatever the current premium shows |

---

### Trade Journal (Last 30 Days)

A table of all closed trades with:
- Entry date, trade mode (auto/manual), lots
- Entry and exit premiums
- Net P&L in ₹ and %

---

### AI Predictions Section

**30-Day Accuracy:** Overall %, correct count, wrong count — measures how often the AI's daily direction prediction was right.

**Prediction History:** Table of each past prediction:
- Date, direction (UP/DOWN/FLAT), magnitude range, confidence %
- Outcome: ✓ correct, ✗ wrong, — pending

---

## 5. Self-Heal

> Requires **Admin** role or higher.

The watchdog monitors critical services every 30 seconds. If a service is unhealthy, a **HealWarning** banner appears on the Dashboard.

This page shows:
- Active heal warnings with severity and message
- Which service triggered the alert
- Timestamp of last check

No manual action is typically needed — the watchdog attempts automatic recovery.

**Severity levels:**

| Level | Meaning | Auto action |
|-------|---------|-------------|
| 1 | DeprecationWarning, slow response | Log only |
| 2 | ConnectionError, Timeout, crash | Log + attempt restart |
| 3 | SyntaxError, ImportError | Request Claude AI fix |
| 4 | Security breach, DB migration, AuthChange | Alert admin, broadcast HEAL_WARNING to all users |

---

## 6. Admin Panel

> Requires **Admin** role or higher.

Manage all users on the platform:

- **Create** a new user (name, email, password, role)
- **Edit** a user's role, capital, trade mode, or Telegram chat ID
- **Deactivate / Reactivate** users
- **View** last login time and failed login attempts

**Roles you can assign:**

| Role | Access |
|------|--------|
| viewer | Dashboard only |
| analyst | Dashboard + Options |
| admin | + Heal, Admin, Monitor |
| super_admin | Full access |

---

## 7. System Monitor

> Requires **Admin** role or higher.

A live diagnostics panel. The **Monitor** nav link shows a red badge with the error count when there are active errors in the log.

### Service Status

Checks four services in real time:
- **PostgreSQL** — database connection + latency
- **Redis** — cache ping latency
- **Scheduler** — APScheduler running + job count
- **WebSocket** — active connections and users

### Data Feed Test

Click **Test All Feeds** to live-test every external data source:
- yfinance (Nifty, S&P 500, Gold, USD/INR, VIX)
- NSE FII/DII API
- NSE Options Chain (PCR)
- Nifty Indices PE/PB

Each shows: status OK/FAIL, latency in ms, sample data.

### Claude API Test

Click **Test Claude** to verify the Anthropic API key is working. Shows model name, latency, and a sample response.

### System Logs

Real-time log stream from all backend components. Filter by:
- **Source** (fastapi, scheduler, websocket, etc.)
- **Level** (INFO, WARNING, ERROR, CRITICAL)

---

## 8. How the Signal Engine Works

The bot checks for signal conditions every **5 minutes** between 9:45 AM and 2:30 PM IST.

### Gate Checks (all must pass)

#### Timing Gates
1. Must be after **9:45 AM IST** (30 min after open — avoids opening volatility)
2. Must be before **2:30 PM IST** (60 min before close — avoids end-of-day chaos)
3. No **SL cooldown** — if the last signal hit its stop-loss, wait a configured cooldown period before generating a new one
4. Daily signal count must be below the configured maximum

#### Data Quality Gate
- At least `min_fresh_signals` of the 47 market signals must have been collected within the last 5 minutes

#### Direction-Specific Gates

**For BUY_CALL (bullish options signal):**

| Gate | Condition |
|------|-----------|
| VWAP | Nifty spot price must be **above** VWAP |
| VIX | India VIX must be **≤ 28** (not too volatile) |
| FII | Net FII flow must be **positive** (institutional buying) |
| PCR | Must be **≥ 0.50** — blocks if PCR < 0.50 (extreme euphoria: everyone is already long calls, crowded trade) |

**For BUY_PUT (bearish options signal):**

| Gate | Condition |
|------|-----------|
| VWAP | Nifty spot price must be **below** VWAP |
| VIX | India VIX must be **≥ min_vix setting** (enough fear for puts) |
| FII | Net FII flow must be **negative** (institutional selling) |
| PCR | Must be **≤ 1.30** — blocks if PCR > 1.30 (extreme panic: everyone is already long puts, crowded trade) |

> **PCR gate logic (contrarian):** The gates block trades when sentiment is already at an extreme in the signal's direction. A very low PCR (<0.50) means the market is in euphoric bullishness — new call buyers at that point often get caught in a reversal. Similarly, a very high PCR (>1.30) indicates crowded bearishness — new puts at that stage face short-squeeze risk. The PCR gate does **not** require the ratio to be pointing in the trade direction; it only blocks when the trade is joining an already-overcrowded position.

At least 3 of 4 direction-specific gates must pass.

#### Claude AI Confirmation

If the gates pass, all 47 market signals + intraday technicals (RSI, EMA9, EMA21, volume ratio) + the live options chain are sent to Claude. Claude returns:
- `signal_type`: BUY_CALL / BUY_PUT / NONE
- `strike`, `option_type`, `approximate_ltp`
- `target1`, `target2`, `stop_loss`
- `confidence` (0–100)
- `signal_basis` — list of reasons
- `rr_ratio`

If Claude returns NONE, no signal is stored.

### Position Sizing (per trade, per user)

Given the user's `capital` and the signal:

```
risk_per_unit    = |entry_premium – stop_loss|
reward_t1        = |target1 – entry_premium|
R:R ratio        = reward_t1 / risk_per_unit       ← must be ≥ 2.0 (else signal blocked)

risk_per_lot     = risk_per_unit × lot_size (25 for Nifty)
premium_per_lot  = entry_premium × lot_size

lots_by_risk     = floor(capital × 2% / risk_per_lot)
lots_by_capital  = floor(capital × 20% / premium_per_lot)
dynamic_cap      = min(50, max(10, floor(capital / ₹1,00,000)))
recommended_lots = min(lots_by_risk, lots_by_capital, dynamic_cap)
```

**Divide-by-zero protection:** If `risk_per_unit = 0` (stop-loss set at entry), the signal is immediately rejected with a ValueError — the bot never divides by zero.

**Minimum is always 1 lot.** The recommended size respects both:
- **2% max-loss rule** — don't risk more than 2% of capital on one trade
- **20% capital rule** — don't deploy more than 20% of capital in options premium
- **Dynamic cap** — scales with account size. Hard ceiling at 50 lots.

| Capital | Dynamic cap |
|---------|-------------|
| ₹2–10 lakh | 10 lots |
| ₹25 lakh | 25 lots |
| ₹50 lakh | 50 lots |
| ₹1 crore | 50 lots (ceiling) |

**Partial exit plan (recommended):**
- Exit **75%** of position at T1
- Hold **25%** to T2 with a trailing stop
- Trailing SL after T1 = `entry + 70% of T1 move` (protects 70% of T1 profit on both calls and puts, since both profit when option premium rises)

**Charges estimate:** STT (0.1% sell turnover) + exchange fee (0.053%) + brokerage (₹40/order) + GST (18% on brokerage+exchange).

### AUTO Mode Slippage Guard

Before opening any AUTO trade, the bot fetches the **actual current premium** from NSE:
1. If market price has moved >3% from Claude's expected LTP → recalculate R:R
2. If new R:R < 2.0 → **trade aborted**, warning logged
3. If new R:R ≥ 2.0 → trade opens at the real market price (not Claude's stale estimate)

This prevents executing a trade at a deteriorated R:R due to the 3–15 seconds Claude takes to respond.

---

## 9. How the Learning Engine Works

The learning engine runs automatically after every **stop-loss hit** and on a **weekly/monthly/quarterly** schedule.

### After a Stop-Loss Hit

1. The trade monitor detects `current_premium ≤ stop_loss`
2. `process_losing_trade(trade_id)` is called in the background
3. Claude's `analyze_loss` function receives:
   - The trade details (entry/exit premium, P&L, mode)
   - The signal that generated it (type, strike, SL, T1)
   - The market conditions at entry
4. Claude returns:
   - `miss_category`: WHY it lost — e.g. `CORRECT_SETUP_BAD_LUCK`, `WRONG_DIRECTION`, `PREMATURE_SL`, `BAD_TIMING`, `DATA_QUALITY`
   - `root_cause`: plain-English explanation
   - `sl_was_correct`: bool — was the stop-loss level appropriate?
   - `sl_recommendation`: TIGHTER / WIDER / SAME
   - `signal_adjustment`: which parameter to tweak
   - `rule_to_update` + `new_rule_value`: specific rule change proposal
   - `confidence_in_analysis`: 0–100

5. A `TradeLearning` record is saved to the database

6. **Proposed rule change logged.** The `TradeLearning` record stores `rule_change_proposed` with the rule name and new value.

7. **Auto-apply threshold (prevents overfitting):** A rule is only automatically applied when the **same rule change has been independently proposed ≥ 3 times in the past 7 days** with confidence ≥ 75, and `miss_category ≠ CORRECT_SETUP_BAD_LUCK`. A single losing trade never changes a rule — statistically meaningless.

   Once the threshold is met, the rule is written/updated in the `SignalRule` table and used in the next signal generation prompt. The `change_reason` field records how many proposals triggered the change.

   > **Why 3 proposals?** One loss is noise. Three independent losses attributing the same root cause and suggesting the same fix is a pattern. This prevents the AI from "whipsawing" — constantly adjusting parameters based on random market moves.

### Weekly Review (every Sunday 9:00 AM IST)

- Fetches all predictions from the last 7 days
- Computes: `accuracy = correct / total × 100`
- Broadcasts the result to the bot activity feed

### Weekly Options Review (every Sunday 9:30 AM IST)

- Fetches all closed trades from the last 7 days
- Computes:
  - `win_rate = winners / total × 100`
  - `avg_win` = average `net_pnl_pct` of winning trades
  - `avg_loss` = average `net_pnl_pct` of losing trades
  - `expectancy = (win_rate × avg_win) – (loss_rate × avg_loss)`
- A positive expectancy means the system is profitable in expectation

### Monthly Calibration (1st of each month)

Runs both weekly reviews for a monthly performance snapshot.

### Quarterly Review (Jan/Apr/Jul/Oct 1st)

Loads the last 100 learning records from the database and logs the count as a health check.

---

## 10. Roles & Permissions

| Feature | viewer | analyst | admin | super_admin |
|---------|--------|---------|-------|-------------|
| Dashboard | ✓ | ✓ | ✓ | ✓ |
| Options & Predictions | | ✓ | ✓ | ✓ |
| Self-Heal | | | ✓ | ✓ |
| Admin Panel | | | ✓ | ✓ |
| System Monitor | | | ✓ | ✓ |
| Create/edit users | | | ✓ | ✓ |
| Test data feeds | | | ✓ | ✓ |

---

## 11. Troubleshooting

### Website shows "Market Closed" but the clock says market hours

The platform uses **two signals** to determine if NSE is open:
1. **Time-based** — weekday between 9:15 AM and 3:30 PM IST
2. **Data freshness** — the last yfinance Nifty candle is < 20 minutes old

If it's an NSE holiday, the market is **physically closed** even though the clock says 10:30 AM. The freshness check catches this automatically. The "Market Closed" display is correct.

If both conditions are true and it's still showing closed: check System Monitor → Data Feed Test to see if yfinance is returning data at all.

### "42/47 signals" — what are the missing 5?

If fewer than 47 signals are fresh, it means some data sources timed out or returned bad data in the last collection cycle. Common causes:
- NSE APIs return HTML (Cloudflare block) — `fetch_fii_dii`, `fetch_put_call_ratio`, `fetch_nifty_pe`
- yfinance `^INDIAVIX` or `^VIX` has no data on holidays (expected)

Go to Monitor → Test All Feeds to see which source is failing.

### Bot shows "SL cooldown active" — no signals for an hour

After any signal hits its stop-loss, the bot waits `signal_cooldown_after_sl` minutes (default 60) before generating new signals. This is by design to prevent overtrading after a losing trade. The cooldown timer resets each time a new SL is hit.

### MANUAL trade shows wrong P&L

The trade monitor checks premiums every 30 seconds via NSE API. If the options chain data is stale or unavailable (holiday, after-hours), P&L may not update. Check the last monitoring timestamp in the trade card.

---

---

# DEVELOPER REFERENCE

---

## 12. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    DOCKER COMPOSE                           │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Frontend   │  │   Backend    │  │  PostgreSQL   │     │
│  │  nginx:80    │  │ FastAPI:8000 │  │  Port 5432   │     │
│  │  React+Vite  │  │  APScheduler │  │              │     │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘     │
│         │                 │                                  │
│         │    REST + WS    │          ┌──────────────┐       │
│         └─────────────────┘          │    Redis     │       │
│                                      │  Port 6379   │       │
│                                      └──────────────┘       │
└─────────────────────────────────────────────────────────────┘

External APIs:
  - yfinance (Yahoo Finance)    ← price data
  - NSE India APIs              ← FII/DII, PCR, PE
  - Anthropic Claude API        ← signal analysis, briefs
  - NewsAPI                     ← market news
  - Telegram Bot API            ← trade alerts
```

### Data Flow

```
yfinance / NSE APIs
       │
       ▼
bot/collector.py  ──►  bot/scheduler.py  ──►  PostgreSQL (snapshots)
                              │
                              ├──►  websocket/live_feed.py  ──►  Browser WebSocket
                              │
                              └──►  bot/analyzer.py  ──►  Anthropic Claude
                                          │
                                          ▼
                                   bot/options_analyzer.py
                                          │
                                          ├──►  Signal saved to DB
                                          │
                                          └──►  bot/trade_handler.py
                                                       │
                                                       ├──►  Trade saved to DB (AUTO mode)
                                                       └──►  bot/learning_engine.py (on SL)
```

### Request Flow (HTTP)

```
Browser
  │
  ▼
Frontend (nginx) ──proxy──►  Backend FastAPI  ──►  PostgreSQL
                                    │
                                    ├──►  auth/middleware.py (JWT validate)
                                    ├──►  api/trades.py
                                    ├──►  api/signals.py
                                    ├──►  api/predictions.py
                                    ├──►  api/admin.py
                                    ├──►  api/market.py
                                    ├──►  api/system.py
                                    └──►  api/self_heal.py
```

---

## 13. Repository Structure

```
market-Analysis/
├── docker-compose.yml          # Multi-container orchestration
├── requirements.txt            # Python dependencies
├── MANUAL.md                   # This file
│
├── backend/
│   ├── main.py                 # FastAPI app, CORS, middleware, router registration
│   ├── config.py               # All settings via pydantic-settings + .env
│   │
│   ├── auth/
│   │   ├── router.py           # /auth/login, /auth/logout, /auth/refresh, /auth/me
│   │   ├── middleware.py       # get_current_user, RequireAnalyst, RequireAdmin deps
│   │   └── schemas.py          # LoginRequest, TokenResponse, UserOut, ChangeCapitalRequest
│   │
│   ├── api/
│   │   ├── market.py           # /api/market/* — current prices, market status
│   │   ├── signals.py          # /api/signals/* — active/history signal endpoints
│   │   ├── trades.py           # /api/trades/* — open/history/exit/capital/mode
│   │   ├── predictions.py      # /api/predictions/* — daily AI prediction history
│   │   ├── admin.py            # /api/admin/* — user CRUD (admin only)
│   │   ├── self_heal.py        # /api/heal/* — watchdog warnings, error log
│   │   └── system.py           # /api/system/* — logs, health, time endpoint
│   │
│   ├── bot/
│   │   ├── scheduler.py        # APScheduler — all job definitions and timing
│   │   ├── collector.py        # fetch_* functions — all 47 market signals
│   │   ├── analyzer.py         # Claude API calls — briefs, postmortem, loss analysis
│   │   ├── options_analyzer.py # Gate checks, signal generation, Claude signal prompt
│   │   ├── position_calculator.py # Lot sizing, R:R, trailing SL, charges estimate
│   │   ├── trade_handler.py    # AUTO trade open, 30s trade monitor, T1/T2/SL logic
│   │   ├── learning_engine.py  # Loss analysis, rule updates, weekly/monthly reviews
│   │   ├── intraday.py         # RSI, EMA9/21, volume ratio from yfinance 1m bars
│   │   ├── validator.py        # Input validation helpers
│   │   └── telegram_sender.py  # Telegram bot alert helpers
│   │
│   ├── websocket/
│   │   └── live_feed.py        # WS /ws/market endpoint, ConnectionManager, event broadcasts
│   │
│   ├── core/
│   │   └── log_buffer.py       # In-memory circular buffer for system log viewer
│   │
│   ├── healing/
│   │   ├── watchdog.py         # Every-30s service checks, severity routing
│   │   ├── classifier.py       # Maps error strings to severity 1–4
│   │   ├── ai_fixer.py         # Asks Claude to generate a code fix (severity 3)
│   │   ├── deployer.py         # Applies fixes (severity 3 approval flow)
│   │   └── rollback.py         # Git rollback helper
│   │
│   ├── db/
│   │   ├── connection.py       # AsyncEngine, AsyncSessionLocal, Base, get_db dep
│   │   ├── models.py           # All SQLAlchemy ORM models (single source of truth)
│   │   ├── seed.py             # Creates admin user on first run
│   │   ├── backfill_historical.py # One-off script to back-fill old snapshots
│   │   └── migrations/         # Alembic migration environment + version scripts
│   │
│   └── tests/
│       ├── api/test_auth.py    # Login, lockout, JWT tests
│       ├── unit/
│       │   ├── test_position_calc.py   # R:R, lot sizing, divide-by-zero guard
│       │   ├── test_signal_gates.py    # PCR/VIX/FII/VWAP gate logic
│       │   └── test_validator.py       # Input validation edge cases
│       ├── integration/
│       │   └── test_signal_flow.py     # End-to-end: gates → Claude mock → Trade saved
│       └── security/
│           └── test_injection.py       # SQL injection, JWT tampering checks
│
└── frontend/
    ├── Dockerfile              # nginx build: Vite prod build + nginx config
    ├── vite.config.js          # Vite config, proxy /api → backend
    ├── tailwind.config.js      # TailwindCSS config
    │
    └── src/
        ├── main.jsx            # React root, ReactDOM.createRoot
        ├── App.jsx             # Router, sidebar, nav, mobile hamburger
        │
        ├── pages/
        │   ├── Login.jsx       # Email+password form, stores JWT in authStore
        │   ├── Dashboard.jsx   # Live prices, metrics row, bot feed, market status
        │   ├── Options.jsx     # Capital, trade mode, signals, trades, predictions
        │   ├── SystemMonitor.jsx # Service health, logs, feed test, Claude test
        │   └── (Admin/Heal pages in App.jsx inline or lazy-loaded)
        │
        ├── components/
        │   ├── MarketTicker.jsx    # Scrolling price strip, open/close dots
        │   ├── SignalCard.jsx      # Active signal display
        │   ├── TradeCard.jsx       # Open trade with live P&L, exit buttons
        │   └── MarketTooltip.jsx   # Hover tooltip for metric cards
        │
        ├── store/
        │   ├── authStore.js    # Zustand: user, token, login/logout actions
        │   └── marketStore.js  # Zustand: marketData, previousData, activeSignals, openTrades
        │
        ├── hooks/
        │   ├── useAuth.js      # Returns { user, token, isLoggedIn } from authStore
        │   └── useWebSocket.js # WS connect/reconnect, dispatches to marketStore
        │
        └── utils/
            └── timeSync.js     # Fetches IST time from /api/system/time (no external API)
```

---

## 14. Backend Deep-Dive

### `main.py` — Application Entry Point

**What it does:**
- Creates the `FastAPI` app with lifespan context manager
- Starts `APScheduler` and the `watchdog` on startup
- Registers all routers
- Adds CORS middleware (allows frontend URL + localhost:5173)
- Adds HTTP request/response logging middleware (skips `/health`, `/ws/*`)
- Logs every non-trivial HTTP request to the in-memory log buffer

**Key design:** All background tasks (scheduler, watchdog) start in the `lifespan` async context manager, not in global scope. This ensures they shut down cleanly when the process exits.

---

### `config.py` — Settings

All configuration is read from environment variables (`.env` file). Uses `pydantic-settings` `BaseSettings` for type coercion and validation. Cached with `@lru_cache` so `.env` is only read once.

**Trading parameters you can tune via `.env`:**

| Variable | Default | Effect |
|----------|---------|--------|
| `MIN_FRESH_SIGNALS` | 40 | Minimum signals needed before Claude is called |
| `MIN_CONFIDENCE` | 55 | Claude's minimum confidence to accept signal |
| `MIN_RR_RATIO` | 2.0 | Minimum R:R — signals below this are blocked |
| `MAX_DAILY_SIGNALS` | 2 | Max signals per trading day |
| `SIGNAL_COOLDOWN_AFTER_SL` | 60 | Minutes to wait after a stop-loss hit |
| `MIN_VIX_FOR_PUT` | 15.0 | Minimum India VIX to trigger a BUY_PUT signal |
| `MIN_FII_CONSECUTIVE_DAYS` | 2 | FII must be buying/selling for this many days |

---

### `bot/collector.py` — The 47 Signals

Fetches all market data in one async collection run. Called every minute by the scheduler during market hours.

**Data sources:**

| Group | Symbols / API | Timeout |
|-------|--------------|---------|
| Indian indices | yfinance: `^NSEI`, `^NSEBANK`, `^NSMIDCP`, `^CNXIT`, `^CNXPHARMA`, `^CNXMETAL` | yfinance default |
| Global indices | yfinance: `^GSPC`, `^IXIC`, `^DJI`, `^N225`, `^HSI`, `000001.SS`, `^FTSE`, `^GDAXI`, `^FCHI`, `^KS11`, `^TWII` | yfinance default |
| Commodities | yfinance: `BZ=F`, `CL=F`, `NG=F`, `GC=F`, `SI=F`, `HG=F` | yfinance default |
| Currencies | yfinance: `INR=X`, `DX-Y.NYB`, `JPY=X`, `EURUSD=X` | yfinance default |
| Bonds | yfinance: `^TNX`, `^IRX` | yfinance default |
| Volatility | yfinance: `^INDIAVIX`, `^VIX` | yfinance default |
| FII/DII | NSE India API | 8s |
| Nifty PE/PB | NSE Indices API | 8s |
| Put-Call Ratio | NSE Options Chain API | 8s |
| Advance/Decline | NSE Market Breadth API | 8s |
| Market News | NewsAPI.org | 8s |

**Sanity validation:** Every numeric value is checked against `SANITY_RANGES` (e.g. Nifty must be between 10,000–40,000). Values outside range are replaced with `None` rather than stored as garbage data.

**NaN/Inf safety:** All data passes through `_sanitize_for_json()` before being stored in PostgreSQL JSONB columns (which reject JSON NaN).

**Holiday detection:** No hardcoded calendar. Instead: if the last yfinance `^NSEI` candle is > 20 minutes old during scheduled market hours, `nse_market_active = False` is set. The frontend and signal engine both respect this flag.

---

### `bot/scheduler.py` — All Timed Jobs

Uses APScheduler's `AsyncIOScheduler`. All jobs run in the asyncio event loop.

**yfinance logger suppression:** At module import, all `yfinance.*` loggers are set to `CRITICAL` to prevent "possibly delisted" ERROR floods on holidays. Actual download failures are caught by our own `try/except` blocks.

See [Section 19](#19-scheduler-jobs-reference) for the full job table.

---

### `bot/options_analyzer.py` — Signal Gate Logic

**`SIGNAL_GATES` dict:** Central configuration for all gate thresholds. The put/call specific gates live here as Python dicts. Changing a gate threshold requires editing this dict **and** updating `config.py` if you want it to be tunable via `.env`.

**`check_and_generate_signal()`:** The main function called every 5 minutes. Runs all gates in sequence:
1. Timing gates (fast, no I/O)
2. DB checks for daily limit and SL cooldown
3. `collect_all_signals()` — slow, I/O bound
4. `get_intraday_technicals()` + `get_options_chain_summary()`
5. `check_put_gates()` / `check_call_gates()`
6. Claude API call with all data
7. `calculate_position()` to verify R:R is ≥ 2.0
8. Signal saved to DB
9. `handle_new_signal()` dispatched to trade handler

**Important:** Claude is only called if at least 3 of 4 direction-specific gates pass. This prevents burning API tokens on weak setups.

---

### `bot/position_calculator.py` — Lot Sizing

**`calculate_position(capital, signal, underlying)`:**
- Raises `ValueError` immediately if `risk_per_unit == 0` (divide-by-zero guard)
- Raises `ValueError` if `R:R < 2.0`
- Returns `minimum` (1 lot), `recommended` (dynamic sizing), `partial_exit_plan`, `charges_estimate`, `warnings`

**Dynamic lot cap formula:**
```python
dynamic_cap = min(50, max(10, int(capital / 100_000)))
```
So a ₹5L account caps at 10 lots, ₹25L at 25 lots, ₹1Cr at 50 lots.

**Trailing SL:** Always `ltp + (reward_t1 × 0.70)` — works for both calls and puts because both profit when option premium rises. The trailing SL is set above the entry to protect profits.

---

### `bot/trade_handler.py` — Trade Lifecycle

**`handle_new_signal(signal, users)`:**
- Called after every signal generation
- For each active user:
  - Calls `calculate_position()` with the user's capital
  - If AUTO mode: fetches current NSE premium, applies slippage guard (>3% move + R:R check), opens `Trade` record in DB, spawns `monitor_trade()` as asyncio Task
  - If MANUAL mode: broadcasts `SIGNAL_AWAITING_MANUAL_ENTRY` via WebSocket

**`monitor_trade(trade_id)`:**
- Infinite loop, checks every 30 seconds
- Fetches current option premium from NSE options chain API
- Checks T1 → T2 → SL → Trailing SL in order
- On T1 hit: marks `t1_exit_done=True`, status → PARTIAL, broadcasts T1 alert
- On T2 hit: calculates final P&L, status → CLOSED
- On SL hit: calculates loss, status → CLOSED, triggers `_run_loss_learning(trade_id)` in background
- Broadcasts unrealised P&L on every check even if no target hit

**`_get_current_premium(strike, option_type, expiry)`:**
- Hits NSE option chain API with browser-like headers (User-Agent + Referer)
- Returns `None` if NSE is unavailable — monitor silently skips that cycle rather than crashing

---

### `bot/learning_engine.py` — Adaptive Learning

**`process_losing_trade(trade_id)`:**
- Called in background after every SL hit
- Builds context dict with trade + signal data
- Calls `analyze_loss()` from `analyzer.py` (Claude API)
- Saves `TradeLearning` record
- Counts proposals of the same rule in the last 7 days
- If ≥ 3 proposals with confidence ≥ 75 → auto-applies the rule change to `SignalRule` table

**`run_weekly_options_review()`:**
- Computes win_rate, avg_win, avg_loss, expectancy from last 7 days of trades
- Logs to console and broadcasts to WebSocket

**Rule changes are visible** in System Monitor → Logs (source=scheduler, level=INFO: "Rule `rule_name` auto-applied after N proposals").

---

### `auth/router.py` — Authentication

- `/auth/login` POST: validates email/password, returns JWT. Uses constant-time bcrypt verify (dummy hash for unknown emails to prevent timing attacks). Tracks `failed_login_attempts`; locks account for 30 min after 5 failures. Logs every login to `user_audit_log`.
- `/auth/logout` POST: deletes the `Session` record (true server-side logout).
- `/auth/refresh` POST: issues a new JWT, invalidates the old one.
- `/auth/me` GET: returns current user profile.

**JWT structure:** `{ sub: user_id_uuid, exp: unix_ts, iat: unix_ts, jti: uuid }`. Algorithm: HS256. Default expiry: 480 minutes (8 hours). Override via `JWT_EXPIRE_MINUTES` env var.

**`auth/middleware.py`:**
- `get_current_user` dependency: validates JWT, loads user from DB, checks `is_active` and `locked_until`
- `RequireAnalyst` / `RequireAdmin` / `RequireSuperAdmin`: role-check dependencies that raise 403 if insufficient role

---

### `websocket/live_feed.py` — Real-Time Connection

**`ConnectionManager`:** Holds `_connections: dict[str, list[WebSocket]]` — one user can have multiple tabs open, each gets its own WebSocket in the list.

**Authentication:** JWT passed as query param `?token=...` (not in headers, as browsers don't support WS auth headers). Validated on connect; invalid → close with code 4001.

**On connect:** Immediately sends `PRICE_UPDATE` with the current `_latest_market_data` cache so the UI is populated instantly without waiting for the next broadcast cycle.

**Events broadcast by the server:**

| Event type | When | Payload |
|-----------|------|---------|
| `CONNECTED` | On connect | Welcome message |
| `PRICE_UPDATE` | Every 5s (broadcast) + every 10s (fast-tick) | Full market data dict |
| `SIGNAL_GENERATED` | When signal is created | Signal dict |
| `TRADE_OPENED` | When AUTO trade opens | trade_id, message |
| `TRADE_ALERT_T1` | T1 hit | message, trade_id |
| `TRADE_ALERT_T2` | T2 hit | message, trade_id |
| `TRADE_ALERT_SL` | SL hit | message, trade_id |
| `PNL_UPDATE` | Every 30s while trade open | trade_id, current_premium, unrealised_pnl |
| `SIGNAL_AWAITING_MANUAL_ENTRY` | Signal in MANUAL mode | signal dict |
| `BOT_ACTIVITY` | Various bot events | message, level |
| `HEAL_WARNING` | Severity 4 error detected | severity, service, message |
| `LOG_ENTRY` | Every backend log line | Full log entry |

---

### `healing/watchdog.py` — Self-Healing

Runs every 30 seconds. Checks 4 services in parallel (`asyncio.gather`):
- `fastapi` → HTTP GET `/health` with 5s timeout
- `postgres` → `SELECT 1` via asyncpg
- `redis` → PING via redis.asyncio
- `data_feed` → checks age of last `DailyMarketSnapshot` in DB (WARNING if > 10 min old)

Each result is saved to `SystemHealthLog`. Errors are routed by severity:
- **Severity 1:** Log warning only
- **Severity 2:** Log + attempt auto-restart (placeholder — would call `systemctl restart`)
- **Severity 3:** Log error + call `healing/ai_fixer.py` → asks Claude to generate a code patch
- **Severity 4:** Critical log + broadcast `HEAL_WARNING` to all frontend users

**`healing/classifier.py`:** Maps error string patterns to severity levels 1–4.

**`healing/ai_fixer.py`:** Sends the error context to Claude with a "generate a Python code fix" prompt. The fix is stored in the `Error` table but **not automatically deployed** — it requires admin approval via the Self-Heal page.

---

### `core/log_buffer.py` — Log Viewer

An in-memory circular buffer of the last N log entries. `setup_ws_log_handler()` installs a Python `logging.Handler` that captures every log line from every module and:
1. Appends it to the ring buffer
2. Broadcasts it as a `LOG_ENTRY` WebSocket event to all connected clients

This is why the System Monitor shows live logs in real time. The buffer is lost on restart; it's not persisted to DB.

---

## 15. Frontend Deep-Dive

### `App.jsx` — Shell

- Renders the full-page layout: sidebar + main content area
- `useState(sidebarOpen)` controls mobile sidebar visibility
- `NAV_ITEMS` array drives the sidebar links; each entry has `{ path, label, icon, minRole }`
- Role-based nav: items are filtered by comparing `user.role` rank to `minRole`
- React Router `<Routes>` maps paths to page components
- `/predictions` → redirect to `/options` (predictions merged into Options page)

### `store/authStore.js` — Auth State (Zustand)

```
{
  user: null | { id, email, name, role, capital, trade_mode },
  token: null | "Bearer eyJ...",
  login(user, token) → persist to localStorage
  logout() → clear localStorage, redirect
  updateUser(partial) → merge partial into user
}
```

Token is stored in `localStorage` and rehydrated on page load. All `axios` calls use an interceptor that injects `Authorization: Bearer <token>`.

### `store/marketStore.js` — Market Data State (Zustand)

```
{
  marketData: {},          // current snapshot
  previousData: {},        // prior snapshot for delta computation
  activeSignals: [],       // currently OPEN signals
  openTrades: [],          // user's OPEN/PARTIAL trades
  botActivity: [],         // last 30 bot activity messages
  healWarnings: [],        // active HEAL_WARNING events

  setMarketData(data) → moves current to previousData, sets new current
  setActiveSignals(signals)
  setOpenTrades(trades)
  addBotActivity(msg)
  addHealWarning(warning)
}
```

`previousData` is what powers the green/red delta arrows — every time new data arrives, the old snapshot is saved as `previousData` before overwriting.

### `hooks/useWebSocket.js` — WS Connection

- Connects to `ws://backend/ws/market?token=...`
- Reconnects automatically after 3 seconds if disconnected
- Dispatches incoming events to `marketStore`:
  - `PRICE_UPDATE` → `setMarketData()`
  - `SIGNAL_GENERATED` → `setActiveSignals()`
  - `BOT_ACTIVITY` → `addBotActivity()`
  - `HEAL_WARNING` → `addHealWarning()`
  - `LOG_ENTRY` → forwarded to SystemMonitor state
  - Trade events → dispatched to `openTrades` updates

### `pages/Dashboard.jsx`

- Polls `/api/market/status` every 60 seconds (NSE open/closed)
- Renders `MarketTicker`, metric cards, bot activity feed
- `nseOpen` state drives the "LIVE" / "Market Closed" badge
- Market data for the metric cards comes from `marketStore.marketData`
- Delta arrows: `(current.nifty - previous.nifty) / previous.nifty × 100`

### `pages/Options.jsx`

- On mount: parallel fetch of 6 endpoints via `Promise.all`:
  - `/api/trades/history?days=30`
  - `/api/trades/open`
  - `/api/signals/active`
  - `/api/trades/capital`
  - `/api/predictions/history?days=30`
  - `/api/predictions/accuracy?days=30`
- `clampCapital(v)` ensures capital input is always `[10000, 10000000]` range
- `saveCapital()` clamps before sending to backend (backend also clamps and rejects out-of-range)
- Trade journal table shows last 20 closed trades
- Predictions section (merged from former `/predictions` page) shows 30-day accuracy + last 15 predictions

### `components/MarketTicker.jsx`

- NSE instruments (`nifty`, `banknifty`, `india_vix`): open/closed dot uses `nseOpen` from backend poll
- Global instruments: open/closed dot uses UTC-based exchange-hours check
- Scroll animation via CSS `@keyframes scroll` on the ticker strip

### `utils/timeSync.js`

Fetches IST time from `GET /api/system/time` (backend endpoint, no external dependency). Returns `{ ist: "...", unix: 1234567890 }`. Previously used `worldtimeapi.org` which was blocked by browser CORS; replaced with the backend endpoint.

---

## 16. Database Schema

All tables are defined in `backend/db/models.py`. PostgreSQL via asyncpg.

### `users`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | auto-generated |
| email | VARCHAR(255) UNIQUE | login identifier |
| password_hash | TEXT | bcrypt |
| name | VARCHAR(255) | display name |
| role | VARCHAR(20) | CHECK: super_admin/admin/analyst/viewer |
| capital | FLOAT | default 200,000 |
| trade_mode | VARCHAR(10) | CHECK: auto/manual |
| telegram_chat_id | VARCHAR(50) | for Telegram alerts |
| is_active | BOOLEAN | soft delete |
| failed_login_attempts | INTEGER | reset on success |
| locked_until | TIMESTAMPTZ | account lockout expiry |
| last_login | TIMESTAMPTZ | |

### `sessions`

| Column | Type | Notes |
|--------|------|-------|
| token | TEXT PK | JWT string |
| user_id | UUID FK → users | |
| expires_at | TIMESTAMPTZ | |
| ip_address | VARCHAR(45) | |

### `daily_market_snapshots`

Unique constraint on `(date, time_of_day)`. Three snapshots per day: `open` (before 11 AM), `mid` (11 AM–2 PM), `close` (after 2 PM). Stored with `INSERT ... ON CONFLICT DO UPDATE` so repeated runs within the same slot don't fail.

Key columns: `nifty_close`, `banknifty_close`, all global indices, commodities, currencies, bonds, `india_vix`, `us_vix`, `fii_net`, `dii_net`, `nifty_pe`, `put_call_ratio`, `vwap`, `fresh_signals_count`, `all_data` (JSONB — full raw dict).

### `signals`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| signal_type | VARCHAR(10) | CHECK: BUY_CALL/BUY_PUT |
| underlying | VARCHAR(20) | NIFTY50 |
| expiry | DATE | |
| strike | INTEGER | option strike |
| option_type | VARCHAR(2) | CHECK: CE/PE |
| ltp_at_signal | FLOAT | premium when signal fired |
| target1, target2, stop_loss | FLOAT | |
| rr_ratio | FLOAT | |
| confidence | INTEGER | 0–100 |
| valid_until | TIMESTAMPTZ | 90 min after signal |
| signal_basis | JSONB | list of reason strings |
| market_conditions | JSONB | full data dict at time of signal |
| gates_passed | JSONB | which gates passed |
| status | VARCHAR(12) | OPEN/HIT_T1/HIT_T2/HIT_SL/EXPIRED/CANCELLED |
| outcome_time, outcome_premium | | when/where it resolved |

### `trades`

One record per user per signal. Key columns: `signal_id`, `user_id`, `trade_mode`, `capital_at_entry`, `lots`, `entry_premium`, `rr_at_entry`, `premium_total`, `max_loss_calculated`, `target1_profit_calculated`, `target2_profit_calculated`, `partial_t1_lots`, `partial_t2_lots`, `t1_exit_done`, `t1_exit_premium`, `t1_exit_profit`, `trailing_sl_after_t1`, `exit_premium`, `exit_reason`, `gross_pnl`, `charges`, `net_pnl`, `net_pnl_pct`, `status`.

### `trade_learnings`

One record per stop-loss hit. Links to `trades` and `signals`. Key columns: `miss_category`, `root_cause`, `sl_was_correct`, `sl_recommendation` (TIGHTER/WIDER/SAME), `rule_change_proposed`, `rule_change_applied`, `rule_change_date`.

### `signal_rules`

Dynamic rule parameters that Claude can propose and the learning engine can auto-apply. Unique `rule_name`. `rule_value` is JSONB `{"value": ...}`. Tracks `previous_value`, `changed_by` (AI/ADMIN/SYSTEM), `win_rate_before`/`after`.

### `predictions`

Daily market direction predictions. Unique `(date, time_of_day)`. Stores `direction` (UP/DOWN/FLAT), `magnitude_low/high`, `confidence`, `bull_case`, `bear_case`. Post-market: `actual_direction`, `actual_magnitude`, `was_correct`, `miss_category`.

### `errors` / `system_health_log`

Self-healing audit trail. `errors` stores detected issues with fix attempts. `system_health_log` stores every watchdog check result (30s cadence).

---

## 17. API Endpoints Reference

All endpoints require `Authorization: Bearer <token>` header except:
- `POST /auth/login`
- `GET /health`
- `GET /api/system/time` (public — used by timeSync.js)

### Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/login` | None | Returns JWT token |
| POST | `/auth/logout` | Any | Invalidates session |
| POST | `/auth/refresh` | Any | New JWT, old invalidated |
| GET | `/auth/me` | Any | Current user profile |

### Market

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/market/data` | Any | Latest market snapshot |
| GET | `/api/market/status` | Any | NSE open/closed + IST time |
| GET | `/api/market/historical` | Any | Last N daily snapshots |

### Signals

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/signals/active` | Any | OPEN signals within valid_until |
| GET | `/api/signals/history` | Any | All signals, last N days |

### Trades

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/trades/open` | Any | User's OPEN/PARTIAL trades |
| GET | `/api/trades/history` | Any | Closed trades, last 30 days |
| POST | `/api/trades/{id}/exit` | Analyst+ | Manually exit a trade |
| GET | `/api/trades/capital` | Any | User's capital + trade_mode |
| PUT | `/api/trades/capital` | Analyst+ | Update capital (clamped ₹10k–₹1Cr) |
| PUT | `/api/trades/mode` | Analyst+ | Switch auto/manual |
| GET | `/api/trades/pnl-summary` | Any | Daily/weekly/monthly P&L totals |

### Predictions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/predictions/history` | Any | Last N days predictions |
| GET | `/api/predictions/accuracy` | Any | Accuracy stats (correct/total/pct) |
| GET | `/api/predictions/today` | Any | Today's prediction if exists |

### Admin

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/admin/users` | Admin+ | All users list |
| POST | `/api/admin/users` | Admin+ | Create user |
| PUT | `/api/admin/users/{id}` | Admin+ | Update user role/capital/mode |
| DELETE | `/api/admin/users/{id}` | Admin+ | Deactivate user |

### System

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/system/time` | None | IST time (public) |
| GET | `/api/system/logs` | Admin+ | Last N log entries from buffer |
| GET | `/api/system/health` | Admin+ | Service health snapshot |
| POST | `/api/system/test-feeds` | Admin+ | Test all external data sources |
| POST | `/api/system/test-claude` | Admin+ | Test Anthropic API key |

### Self-Heal

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/heal/warnings` | Admin+ | Active HEAL_WARNING events |
| GET | `/api/heal/errors` | Admin+ | Recent Error records |

### WebSocket

| Path | Auth | Protocol |
|------|------|----------|
| `ws://host/ws/market?token=<jwt>` | JWT in query param | JSON events, PING/PONG keepalive |

---

## 18. WebSocket Protocol

### Client → Server

```json
{ "type": "PING" }
```
Server responds: `{ "type": "PONG" }`

No other client-to-server messages are currently used.

### Server → Client

All messages are JSON. Key fields: `type`, `ts` (ISO8601 UTC).

**`PRICE_UPDATE`** (every ~5 seconds):
```json
{
  "type": "PRICE_UPDATE",
  "ts": "2026-03-31T10:00:00Z",
  "data": {
    "nifty": 22340.5,
    "banknifty": 48120.3,
    "india_vix": 16.4,
    "nse_market_active": true,
    "put_call_ratio": 0.88,
    "fii_net": -1200.5,
    "gold": 2315.2,
    "usd_inr": 84.1,
    "fresh_signals_count": 44,
    ...
  }
}
```

**`SIGNAL_GENERATED`**:
```json
{
  "type": "SIGNAL_GENERATED",
  "ts": "...",
  "signal": {
    "signal_type": "BUY_CALL",
    "strike": 22400,
    "option_type": "CE",
    "approximate_ltp": 95.0,
    "target1": 145.0,
    "target2": 190.0,
    "stop_loss": 65.0,
    "confidence": 72,
    "rr_ratio": 2.6,
    "signal_basis": ["Above VWAP", "FII buying", ...]
  }
}
```

**`PNL_UPDATE`**:
```json
{
  "type": "PNL_UPDATE",
  "ts": "...",
  "payload": {
    "trade_id": 42,
    "current_premium": 108.5,
    "unrealised_pnl": 3375.0
  }
}
```

---

## 19. Scheduler Jobs Reference

| Job ID | Function | Schedule | Purpose |
|--------|----------|----------|---------|
| `morning_brief` | `job_morning_brief` | 9:00 AM IST Mon–Fri | Claude generates market brief |
| `collect_live` | `job_collect_live_data` | Every 1 min, 9–15 IST Mon–Fri | All 47 signals → DB + broadcast |
| `options_signals` | `job_check_options_signals` | Every 5 min, 9–14 IST Mon–Fri | Gate checks + Claude signal generation |
| `midday_brief` | `job_midday_brief` | 12:30 IST Mon–Fri | Claude midday update |
| `closing_brief` | `job_closing_brief` | 15:35 IST Mon–Fri | Claude closing summary |
| `daily_postmortem` | `job_daily_postmortem` | 15:45 IST Mon–Fri | Claude EOD analysis |
| `update_historical` | `job_update_historical` | 16:00 IST Mon–Fri | Final EOD snapshot |
| `watchdog` | `job_watchdog_check` | Every 30s (always) | 4-service health checks |
| `broadcast_live` | `job_broadcast_live` | Every 5s (always) | WS broadcast from in-memory cache |
| `fast_tick` | `job_fast_tick_prices` | Every 10s Mon–Fri | yfinance price refresh → cache + WS |
| `weekly_pred_review` | `job_weekly_prediction_review` | Sun 9:00 IST | Prediction accuracy stats |
| `weekly_options_review` | `job_weekly_options_review` | Sun 9:30 IST | Trade win-rate + expectancy |
| `monthly_calibration` | `job_monthly_calibration` | 1st of month 8:00 IST | Monthly performance snapshot |
| `quarterly_review` | `job_quarterly_review` | Jan/Apr/Jul/Oct 1st 8:00 IST | Load 100 learnings from DB |

**`fast_tick` vs `collect_live`:**

| | fast_tick | collect_live |
|--|-----------|-------------|
| Frequency | 10 seconds | 60 seconds |
| Data sources | yfinance only | yfinance + 4 NSE APIs + NewsAPI |
| DB write | No (cache only) | Yes (upsert snapshot) |
| Active hours | All weekdays | 9–15 IST Mon–Fri |
| Purpose | Keep WS fresh | Full 47-signal collection |

---

## 20. Configuration & Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
# Database
DATABASE_URL=postgresql+asyncpg://market_user:market_pass@postgres/market_platform

# Redis
REDIS_URL=redis://redis:6379/0

# Security — CHANGE IN PRODUCTION
JWT_SECRET_KEY=your-long-random-secret-here
JWT_EXPIRE_MINUTES=480

# Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-6

# Telegram (optional)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_IDS=123456789,987654321

# News (optional)
NEWS_API_KEY=

# App
ENVIRONMENT=development
LOG_LEVEL=INFO
FRONTEND_URL=http://localhost

# Trading Parameters (all optional — defaults shown)
MIN_FRESH_SIGNALS=40
MIN_CONFIDENCE=55
MIN_RR_RATIO=2.0
MAX_DAILY_SIGNALS=2
SIGNAL_COOLDOWN_AFTER_SL=60
MIN_VIX_FOR_PUT=15.0
MIN_FII_CONSECUTIVE_DAYS=2
```

**`CLAUDE_MODEL`:** Always use the latest available — `claude-sonnet-4-6` (current default). Briefs, postmortems, and loss analysis all use this model.

---

## 21. Running & Deploying

### Local Development

```bash
# Start all containers
docker compose up -d

# Check all services running
docker compose ps

# Seed the admin user (first time only)
docker compose exec backend python db/seed.py

# View live backend logs
docker compose logs -f backend

# View live frontend logs
docker compose logs -f frontend

# Restart just the backend (pick up code changes)
docker compose restart backend

# Run backend tests
docker compose exec backend pytest

# Open FastAPI docs (development mode only)
open http://localhost:8000/docs
```

### Database Migrations

```bash
# Create a new migration
docker compose exec backend alembic revision --autogenerate -m "description"

# Apply pending migrations
docker compose exec backend alembic upgrade head

# Downgrade one step
docker compose exec backend alembic downgrade -1
```

### Production Checklist

1. Change `JWT_SECRET_KEY` to a cryptographically random 64-char string
2. Change admin password via Admin panel
3. Set `ENVIRONMENT=production` (disables /docs, /redoc)
4. Set `ANTHROPIC_API_KEY` with a real key
5. Point `DATABASE_URL` and `REDIS_URL` to production services
6. Update `FRONTEND_URL` to the production domain for CORS
7. Set `LOG_LEVEL=WARNING` to reduce log volume

---

## 22. Testing

### Test Structure

```
backend/tests/
├── api/
│   └── test_auth.py         # Login, logout, refresh, lockout, JWT validation
├── unit/
│   ├── test_position_calc.py  # R:R enforcement, divide-by-zero, dynamic lot cap
│   ├── test_signal_gates.py   # PCR/VIX/FII/VWAP gate logic
│   └── test_validator.py      # Capital range validation, input sanitization
├── integration/
│   └── test_signal_flow.py    # Full gate → Claude mock → Trade creation
└── security/
    └── test_injection.py      # SQL injection via API params, JWT tampering
```

### Running Tests

```bash
# All tests
docker compose exec backend pytest

# Specific file
docker compose exec backend pytest tests/unit/test_position_calc.py -v

# With coverage
docker compose exec backend pytest --cov=. --cov-report=term-missing
```

---

## 23. Common Debugging Patterns

### ERROR: `^VIX: possibly delisted; no price data found`

**Cause:** CBOE VIX (`^VIX`) or India VIX (`^INDIAVIX`) has no data on this date (NSE/US holiday, weekend). yfinance logs at ERROR level for any missing ticker.

**Fix already applied:** yfinance loggers are set to `CRITICAL` level in `scheduler.py` and `collector.py` so these never appear in the system monitor.

**If still appearing:** yfinance may have added new logger names. Check `logging.Logger.manager.loggerDict` for any `yfinance*` entries not covered by the current suppression list.

---

### WARNING: `job_collect_live_data skipped: maximum number of running instances reached`

**Cause:** The previous run of `job_collect_live_data` took > 60 seconds, so APScheduler skipped the next tick. Expected on NSE holidays (NSE APIs return slow/empty responses even with 8s timeout).

**Not an error.** `coalesce=True` means APScheduler collapses missed runs into one. The job catches up on the next minute.

**If it's happening every minute during live market hours:** Check NSE API response times in Monitor → Test All Feeds. If they're all timing out at 8 seconds, the collective 4×8 = 32s + yfinance download time may exceed 60s on a slow network. Reduce NSE timeouts to 5s or increase the job interval to `*/2` (every 2 minutes).

---

### Frontend shows stale data after backend restart

**Cause:** `_latest_market_data` in-memory cache is lost on restart. On first fast_tick, the cache is seeded from the last DB snapshot.

**Expected recovery time:** 10 seconds (first fast_tick after restart).

**If data doesn't recover:** Check that `DailyMarketSnapshot` table has rows (run `SELECT * FROM daily_market_snapshots ORDER BY created_at DESC LIMIT 1;`).

---

### WebSocket keeps reconnecting

**Symptoms:** Browser console shows repeated `WebSocket connected / disconnected`.

**Diagnosis steps:**
1. Check backend logs for `WebSocket disconnected` — is there an error before it?
2. Check JWT expiry — if the token expired (default 8h), the WS reconnect will fail with code 4001. User needs to re-login.
3. Check if the backend is restarting (APScheduler crash, OOM).

**JWT expiry and WS:** The WS connection is validated once on connect. If the token expires while connected, the connection stays open until the client disconnects or the backend restarts. New connections with expired tokens are rejected immediately.

---

### P&L not updating on open trade

**Cause:** `monitor_trade()` fetches live premium from NSE options chain every 30s. If:
- NSE API is rate-limiting (returns HTML instead of JSON) → `_get_current_premium()` returns `None`, monitor skips silently
- The option has expired or the strike is no longer in the chain → same

**Diagnosis:** In System Monitor → Logs, filter by `source=bot` and look for `Trade monitor error` entries.

**Manual fix:** Use the exit buttons in the Options page to close the trade at any price.

---

### Capital input shows unexpected values

**Clamp logic (frontend):**
```javascript
const clampCapital = (v) => Math.max(10_000, Math.min(10_000_000, Math.round(Number(v) || 200_000)))
```
Applied on: `onBlur`, before `saveCapital()`.

**Backend validation** (`/api/trades/capital` PUT):
```python
clamped = max(10_000, min(10_000_000, int(body.capital)))
if clamped != body.capital:
    raise HTTPException(400, "Capital must be between ₹10,000 and ₹1,00,00,000")
```

If a value like `2e25` somehow gets through, the backend rejects it. The frontend `Number()` conversion will parse `2e25` as a float, which `Math.min(10_000_000, ...)` clamps to ₹1 crore.

---

### Claude API errors in signal generation

**`Claude signal generation failed: ...`** in logs:

1. Check `ANTHROPIC_API_KEY` is set and valid (Monitor → Test Claude)
2. Check Anthropic service status
3. Check rate limits — if generating signals frequently, Claude may throttle

**`LLM hallucination` / missing JSON keys:**

The signal prompt instructs Claude to return strict JSON. If Claude returns malformed JSON or omits required keys (`signal_type`, `strike`, `approximate_ltp`, `target1`, `target2`, `stop_loss`), the `_call_claude_json()` function raises an exception. The `check_and_generate_signal()` function catches this and logs `"Claude signal generation failed"` — no signal is stored and the bot continues normally.

---

### Duplicate key PostgreSQL error

**Symptom:** `asyncpg.exceptions.UniqueViolationError: duplicate key value violates unique constraint "daily_market_snapshots_date_time_of_day_key"`

**This should not happen** — all snapshot writes use `INSERT ... ON CONFLICT DO UPDATE`. If it appears, check if there's a raw `INSERT` anywhere (not using `pg_insert`).

**Previous cause (fixed):** `job_intraday_snapshot` was running concurrently with `job_collect_live_data`, both writing to the same date+time_of_day slot. The duplicate job has been removed. Only `job_collect_live_data` writes snapshots now.

---

### NSE API returns HTML (Cloudflare block)

**Symptom:** `json.JSONDecodeError: Expecting value: line 1 column 1 (char 0)` in `fetch_fii_dii` / `fetch_put_call_ratio` / `fetch_nifty_pe`

**Cause:** NSE India's APIs are protected by Cloudflare. If the backend IP gets flagged, subsequent requests return a Cloudflare challenge HTML page instead of JSON.

**Mitigation already in place:** All NSE fetch functions have `timeout=8` and catch all exceptions, logging them and returning `None` rather than crashing.

**Fix if systematic:** Rotate the backend server IP or add residential proxy support. Long-term, consider using a licensed data provider for FII/DII data.
