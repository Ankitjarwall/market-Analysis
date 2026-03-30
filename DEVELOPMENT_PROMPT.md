# MARKET INTELLIGENCE PLATFORM — COMPLETE DEVELOPMENT PROMPT
## Full Stack · Self-Healing · Options Trading · AI-Powered · Telegram Bot

---

## DOCUMENT PURPOSE
This is a complete, detailed development specification for building a
Market Intelligence Platform from scratch. Every feature, rule, database
schema, API endpoint, UI component, and test case is described here.
Read this entire document before writing a single line of code.

---

## TECH STACK (NON-NEGOTIABLE)

### Backend
- Language: Python 3.11+
- Web Framework: FastAPI
- Database: PostgreSQL (main) + Redis (cache + real-time)
- ORM: SQLAlchemy 2.0 + Alembic (migrations)
- Task Scheduler: APScheduler
- WebSocket: FastAPI native WebSocket
- Authentication: JWT (python-jose) + bcrypt (passlib)
- AI: Anthropic Claude API (claude-sonnet-4-6)
- Telegram: python-telegram-bot v21+

### Frontend
- Framework: React 18 + Vite
- Styling: TailwindCSS
- State: Zustand
- Real-time: native WebSocket hook
- Charts: Recharts
- HTTP: Axios
- Forms: React Hook Form

### Data Sources (all free unless noted)
- yfinance — global market data + historical
- NSE India API (unofficial) — FII/DII, Nifty PE, options chain
- NewsAPI.org — financial news (free tier)
- RSS feeds — Economic Times, Moneycontrol, Reuters
- investing.com scraping — economic calendar events

### Infrastructure
- Server: Ubuntu 22.04 VPS (min 2 vCPU, 4GB RAM)
- Reverse proxy: Nginx
- Process manager: Supervisor or systemd
- SSL: Let's Encrypt (certbot)
- Version control: Git (every change committed before deploy)

---

## PROJECT STRUCTURE

```
market-platform/
├── backend/
│   ├── main.py                      # FastAPI app entry point
│   ├── config.py                    # env vars, constants
│   ├── auth/
│   │   ├── router.py                # /auth/login, /auth/logout, /auth/refresh
│   │   ├── models.py                # User, Session SQLAlchemy models
│   │   ├── schemas.py               # Pydantic schemas
│   │   └── middleware.py            # JWT validation middleware
│   ├── api/
│   │   ├── market.py                # /api/market/* live data endpoints
│   │   ├── signals.py               # /api/signals/* options signals
│   │   ├── trades.py                # /api/trades/* trade journal
│   │   ├── predictions.py           # /api/predictions/*
│   │   ├── admin.py                 # /api/admin/* user management
│   │   └── self_heal.py             # /api/heal/* healing status + controls
│   ├── bot/
│   │   ├── scheduler.py             # APScheduler — all timed jobs
│   │   ├── collector.py             # all data fetching (47 signals)
│   │   ├── validator.py             # data freshness + sanity checks
│   │   ├── intraday.py              # intraday technical analysis
│   │   ├── options_analyzer.py      # put/call signal generation
│   │   ├── position_calculator.py   # lot sizing + R:R calculation
│   │   ├── analyzer.py              # Claude API calls for predictions
│   │   ├── learning_engine.py       # mistake DB + pattern matching
│   │   └── telegram_sender.py       # message formatting + sending
│   ├── healing/
│   │   ├── watchdog.py              # process monitor (runs independently)
│   │   ├── classifier.py            # error severity classification
│   │   ├── ai_fixer.py              # Claude fix requests
│   │   ├── deployer.py              # safe deployment with tests
│   │   └── rollback.py              # git-based rollback
│   ├── websocket/
│   │   └── live_feed.py             # WebSocket server + broadcast
│   ├── db/
│   │   ├── connection.py            # DB connection pool
│   │   ├── models.py                # ALL SQLAlchemy models
│   │   └── migrations/              # Alembic migration files
│   └── tests/
│       ├── unit/
│       ├── integration/
│       ├── api/
│       ├── security/
│       └── ui/                      # Playwright tests
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Login.jsx
│   │   │   ├── Dashboard.jsx        # live market overview
│   │   │   ├── Options.jsx          # put/call signals + trade tracking
│   │   │   ├── BotFeed.jsx          # real-time bot activity log
│   │   │   ├── Predictions.jsx      # accuracy tracker
│   │   │   ├── SelfHeal.jsx         # healing monitor + controls
│   │   │   ├── Admin.jsx            # user management
│   │   │   └── Reports.jsx          # weekly/monthly reports
│   │   ├── components/
│   │   │   ├── MarketTicker.jsx     # live price strip
│   │   │   ├── SignalCard.jsx       # options signal display
│   │   │   ├── TradeCard.jsx        # open trade tracking
│   │   │   ├── HealWarning.jsx      # self-heal alert overlay
│   │   │   ├── PredictionCard.jsx   # daily prediction
│   │   │   ├── TradeJournal.jsx     # trade history table
│   │   │   ├── LearningPanel.jsx    # loss learnings display
│   │   │   └── RoleGuard.jsx        # permission wrapper
│   │   ├── hooks/
│   │   │   ├── useWebSocket.js      # live data subscription
│   │   │   └── useAuth.js           # auth state + token refresh
│   │   └── store/
│   │       ├── authStore.js         # Zustand auth state
│   │       └── marketStore.js       # Zustand market data state
│   └── tests/
│       └── (Playwright UI tests)
│
├── data/
│   ├── historical/                  # 30 years CSV files
│   ├── daily_snapshots/             # JSON per day
│   ├── news_archive/                # JSON per day
│   └── signal_rules.json            # live signal gates (auto-updated)
│
├── db/
│   ├── market_bot.db                # SQLite for local dev
│   └── backups/
│
├── logs/
│   ├── bot.log
│   ├── errors.log
│   ├── heal.log
│   └── trades.log
│
├── reports/
│   ├── weekly/
│   ├── monthly/
│   └── quarterly/
│
├── .env                             # secrets (never commit)
├── .env.example
├── docker-compose.yml
├── requirements.txt
├── Makefile                         # dev commands
└── README.md
```

---

## ENVIRONMENT VARIABLES (.env)

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost/market_platform
REDIS_URL=redis://localhost:6379/0

# Auth
JWT_SECRET_KEY=your-very-long-random-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=480

# Anthropic
ANTHROPIC_API_KEY=your-anthropic-api-key
CLAUDE_MODEL=claude-sonnet-4-6

# Telegram
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_IDS=123456789,987654321

# News
NEWS_API_KEY=your-newsapi-key

# App
ENVIRONMENT=production
LOG_LEVEL=INFO
FRONTEND_URL=https://yourdomain.com
BACKEND_URL=https://api.yourdomain.com

# Trading
DEFAULT_CAPITAL=200000
MAX_RISK_PCT=2.0
MAX_DEPLOY_PCT=20.0
MIN_RR_RATIO=2.0
NIFTY_LOT_SIZE=25
BANKNIFTY_LOT_SIZE=15
MIN_FRESH_SIGNALS=40
MIN_CONFIDENCE=55
MAX_DAILY_SIGNALS=2
SIGNAL_COOLDOWN_AFTER_SL=60
MIN_VIX_FOR_PUT=15
MIN_FII_CONSECUTIVE_DAYS=2
```

---

## DATABASE SCHEMAS (ALL TABLES)

```sql
-- ═══ AUTH ═══

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('super_admin','admin','analyst','viewer')),
    added_by UUID REFERENCES users(id),
    capital REAL DEFAULT 200000,
    trade_mode TEXT DEFAULT 'auto' CHECK(trade_mode IN ('auto','manual')),
    telegram_chat_id TEXT,
    is_active BOOLEAN DEFAULT true,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE sessions (
    token TEXT PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMP NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE user_audit_log (
    id SERIAL PRIMARY KEY,
    actor_id UUID REFERENCES users(id),
    action TEXT NOT NULL,
    target_user_id UUID REFERENCES users(id),
    details JSONB,
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ═══ MARKET DATA ═══

CREATE TABLE daily_market_snapshots (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    time_of_day TEXT NOT NULL CHECK(time_of_day IN ('open','mid','close')),
    nifty_open REAL,
    nifty_high REAL,
    nifty_low REAL,
    nifty_close REAL,
    nifty_volume BIGINT,
    banknifty_close REAL,
    sp500_close REAL,
    nasdaq_close REAL,
    nikkei_close REAL,
    hangseng_close REAL,
    shanghai_close REAL,
    ftse_close REAL,
    dax_close REAL,
    gift_nifty REAL,
    crude_brent REAL,
    crude_wti REAL,
    gold REAL,
    silver REAL,
    natural_gas REAL,
    copper REAL,
    usd_inr REAL,
    dxy REAL,
    usd_jpy REAL,
    us_10y_yield REAL,
    india_10y_yield REAL,
    india_vix REAL,
    us_vix REAL,
    fii_net REAL,
    dii_net REAL,
    nifty_pe REAL,
    nifty_pb REAL,
    nifty_dividend_yield REAL,
    advance_decline_ratio REAL,
    put_call_ratio REAL,
    nifty_vs_200dma REAL,
    vwap REAL,
    fresh_signals_count INTEGER,
    all_data JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(date, time_of_day)
);

-- ═══ PREDICTIONS ═══

CREATE TABLE predictions (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    time_of_day TEXT NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('UP','DOWN','FLAT')),
    magnitude_low REAL,
    magnitude_high REAL,
    confidence INTEGER CHECK(confidence BETWEEN 0 AND 100),
    confidence_reason TEXT,
    bull_case TEXT,
    bear_case TEXT,
    key_trigger TEXT,
    data_quality TEXT CHECK(data_quality IN ('HIGH','MEDIUM','LOW')),
    similar_days_found INTEGER,
    prediction_basis JSONB,
    market_conditions_at_time JSONB,
    actual_direction TEXT,
    actual_magnitude REAL,
    was_correct BOOLEAN,
    error_size REAL,
    miss_category TEXT,
    post_mortem TEXT,
    telegram_sent BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(date, time_of_day)
);

-- ═══ OPTIONS SIGNALS ═══

CREATE TABLE signals (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    signal_type TEXT NOT NULL CHECK(signal_type IN ('BUY_CALL','BUY_PUT')),
    underlying TEXT NOT NULL DEFAULT 'NIFTY50',
    expiry DATE NOT NULL,
    strike INTEGER NOT NULL,
    option_type TEXT NOT NULL CHECK(option_type IN ('CE','PE')),
    ltp_at_signal REAL NOT NULL,
    target1 REAL NOT NULL,
    target2 REAL NOT NULL,
    stop_loss REAL NOT NULL,
    exit_condition TEXT,
    rr_ratio REAL NOT NULL,
    confidence INTEGER NOT NULL,
    valid_until TIMESTAMP NOT NULL,
    signal_basis JSONB NOT NULL,
    market_conditions JSONB NOT NULL,
    gates_passed JSONB,
    status TEXT DEFAULT 'OPEN'
        CHECK(status IN ('OPEN','HIT_T1','HIT_T2','HIT_SL','EXPIRED','CANCELLED')),
    outcome_time TIMESTAMP,
    outcome_premium REAL,
    blocked_reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ═══ TRADES ═══

CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    signal_id INTEGER REFERENCES signals(id),
    user_id UUID REFERENCES users(id),

    -- Mode
    trade_mode TEXT NOT NULL CHECK(trade_mode IN ('auto','manual')),
    -- AUTO: entry_premium = signal LTP, no user confirmation needed
    -- MANUAL: user entered different price/qty

    -- Entry
    capital_at_entry REAL NOT NULL,
    lots INTEGER NOT NULL,
    entry_premium REAL NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    entry_nifty_level REAL,
    manual_entry_deviation_pct REAL,
    rr_at_entry REAL NOT NULL,
    rr_warning_acknowledged BOOLEAN DEFAULT false,

    -- Position sizing
    premium_total REAL NOT NULL,
    max_loss_calculated REAL NOT NULL,
    max_loss_pct REAL NOT NULL,
    target1_profit_calculated REAL NOT NULL,
    target2_profit_calculated REAL NOT NULL,

    -- Partial exit plan
    partial_t1_lots INTEGER,
    partial_t2_lots INTEGER,
    t1_exit_done BOOLEAN DEFAULT false,
    t1_exit_premium REAL,
    t1_exit_time TIMESTAMP,
    t1_exit_profit REAL,
    trailing_sl_after_t1 REAL,

    -- Final exit
    exit_premium REAL,
    exit_time TIMESTAMP,
    exit_nifty_level REAL,
    exit_reason TEXT
        CHECK(exit_reason IN ('TARGET1','TARGET2','STOP_LOSS','MANUAL','EXPIRED','PARTIAL')),

    -- P&L
    gross_pnl REAL,
    charges REAL,
    net_pnl REAL,
    net_pnl_pct REAL,

    status TEXT DEFAULT 'OPEN'
        CHECK(status IN ('OPEN','CLOSED','PARTIAL')),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ═══ LEARNING ENGINE ═══

CREATE TABLE trade_learnings (
    id SERIAL PRIMARY KEY,
    trade_id INTEGER REFERENCES trades(id),
    signal_id INTEGER REFERENCES signals(id),
    trade_date DATE NOT NULL,
    loss_amount REAL NOT NULL,
    loss_pct REAL NOT NULL,
    miss_category TEXT NOT NULL,
    what_signal_said TEXT,
    what_actually_happened TEXT,
    root_cause TEXT,
    signal_conditions_at_time JSONB,
    news_between_entry_exit TEXT,
    sl_was_correct BOOLEAN,
    sl_recommendation TEXT CHECK(sl_recommendation IN ('TIGHTER','WIDER','SAME')),
    signal_adjustment TEXT,
    rule_change_proposed TEXT,
    rule_change_applied BOOLEAN DEFAULT false,
    rule_change_date DATE,
    improvement_result TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE signal_rules (
    id SERIAL PRIMARY KEY,
    rule_name TEXT UNIQUE NOT NULL,
    rule_value JSONB NOT NULL,
    previous_value JSONB,
    changed_by TEXT CHECK(changed_by IN ('AI','ADMIN','SYSTEM')),
    change_reason TEXT,
    trades_since_change INTEGER DEFAULT 0,
    win_rate_before REAL,
    win_rate_after REAL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE signal_performance (
    id SERIAL PRIMARY KEY,
    signal_type TEXT NOT NULL,
    period TEXT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    total_signals INTEGER DEFAULT 0,
    winning_signals INTEGER DEFAULT 0,
    losing_signals INTEGER DEFAULT 0,
    win_rate REAL,
    avg_win_pct REAL,
    avg_loss_pct REAL,
    expectancy REAL,
    best_conditions JSONB,
    worst_conditions JSONB,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ═══ SELF-HEALING ═══

CREATE TABLE errors (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    service TEXT NOT NULL,
    error_type TEXT NOT NULL,
    severity INTEGER NOT NULL CHECK(severity BETWEEN 1 AND 4),
    traceback TEXT,
    log_context TEXT,
    system_state JSONB,
    fix_attempted BOOLEAN DEFAULT false,
    fix_source TEXT CHECK(fix_source IN ('AUTO_RESTART','CLAUDE','HUMAN','SIMILAR_PAST')),
    fix_code TEXT,
    fix_explanation TEXT,
    fix_test_cases TEXT,
    fix_test_results TEXT,
    fix_worked BOOLEAN,
    fix_timestamp TIMESTAMP,
    fix_approved_by UUID REFERENCES users(id),
    similar_error_ids INTEGER[],
    root_cause TEXT,
    prevention_note TEXT,
    git_commit_hash TEXT
);

CREATE TABLE system_health_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    service TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('OK','WARNING','ERROR','CRASHED')),
    response_time_ms INTEGER,
    memory_mb REAL,
    cpu_pct REAL,
    details JSONB
);

-- ═══ MISTAKES DATABASE (for market predictions) ═══

CREATE TABLE prediction_mistakes (
    id SERIAL PRIMARY KEY,
    prediction_id INTEGER REFERENCES predictions(id),
    date DATE NOT NULL,
    prediction_direction TEXT NOT NULL,
    actual_direction TEXT NOT NULL,
    error_size REAL NOT NULL,
    market_conditions JSONB NOT NULL,
    miss_category TEXT NOT NULL,
    what_was_missed TEXT,
    lesson_extracted TEXT,
    similar_past_miss_ids INTEGER[],
    confidence_given INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## DATA COLLECTION — 47 SIGNALS

Build `backend/bot/collector.py` to fetch ALL of these.
Every signal must have a timestamp and pass validation.

### Global Indices (via yfinance)
```
^NSEI      Nifty 50
^NSEBANK   Nifty Bank
^NSMIDCP   Nifty Midcap
^NSIT      Nifty IT
^CNXPHARMA Nifty Pharma
^CNXMETAL  Nifty Metal
^GSPC      S&P 500
^IXIC      Nasdaq 100
^DJI       Dow Jones
^N225      Nikkei 225
^HSI       Hang Seng
000001.SS  Shanghai
^FTSE      FTSE 100
^GDAXI     DAX
^FCHI      CAC 40
^KS11      KOSPI (Korea)
^TWII      Taiwan
```

### Commodities (via yfinance)
```
BZ=F   Brent Crude Oil
CL=F   WTI Crude Oil
NG=F   Natural Gas
GC=F   Gold
SI=F   Silver
HG=F   Copper
```

### Currencies & Bonds (via yfinance)
```
INR=X        USD/INR
DX-Y.NYB     DXY Dollar Index
JPY=X        USD/JPY
EURUSD=X     EUR/USD
^TNX         US 10Y Treasury yield
^IRX         US 13W T-Bill
```

### India-Specific (NSE API)
```
India VIX (^INDIAVIX via yfinance)
FII net buy/sell (NSE data endpoint)
DII net buy/sell (NSE data endpoint)
Nifty PE ratio (scrape from niftyindices.com or screener.in)
Nifty PB ratio
Nifty Dividend Yield
Advance/Decline ratio (NSE)
Put/Call Ratio (NSE options chain)
GIFT Nifty futures (if available)
VWAP (calculate from intraday OHLCV)
```

### Data Validation Rules
```python
SANITY_RANGES = {
    'nifty_price':    (15000, 40000),
    'banknifty':      (35000, 80000),
    'sp500':          (3000, 10000),
    'crude_brent':    (30, 250),
    'gold':           (1000, 5000),
    'usd_inr':        (60, 120),
    'vix':            (5, 100),
    'us_10y_yield':   (0.1, 15),
    'nifty_pe':       (10, 50),
    'put_call_ratio': (0.3, 3.0),
}

MAX_DATA_AGE_MINUTES = {
    'live_prices':  5,
    'fii_data':     60,    # NSE updates FII hourly
    'news':         120,
    'pe_ratio':     60,
}
```

---

## BOT SCHEDULER — ALL JOBS

```python
# backend/bot/scheduler.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# ── MARKET HOURS (weekdays, NSE open) ──

# Pre-market (runs once per day at 9:00 AM IST)
scheduler.add_job(send_morning_brief,    'cron', hour=9,  minute=0,  day_of_week='mon-fri')

# Data collection every minute during market hours
scheduler.add_job(collect_live_data,     'cron', minute='*/1',
                  hour='9-15', day_of_week='mon-fri')

# Intraday snapshots
scheduler.add_job(intraday_snapshot,     'cron', minute='*/15',
                  hour='9-15', day_of_week='mon-fri')

# Options signal check every 5 minutes (not in first 30min or last 60min)
scheduler.add_job(check_options_signals, 'cron', minute='*/5',
                  hour='9-14', day_of_week='mon-fri')

# Midday brief
scheduler.add_job(send_midday_brief,     'cron', hour=12, minute=30, day_of_week='mon-fri')

# End of day
scheduler.add_job(send_closing_brief,    'cron', hour=15, minute=35, day_of_week='mon-fri')
scheduler.add_job(run_daily_postmortem,  'cron', hour=15, minute=45, day_of_week='mon-fri')
scheduler.add_job(update_historical_data,'cron', hour=16, minute=0,  day_of_week='mon-fri')

# ── ALWAYS RUNNING ──

# Watchdog checks every 30 seconds
scheduler.add_job(watchdog_check,        'interval', seconds=30)

# WebSocket broadcast every 5 seconds during market
scheduler.add_job(broadcast_live_data,   'interval', seconds=5)

# ── WEEKLY/MONTHLY REVIEWS ──

scheduler.add_job(weekly_prediction_review,  'cron', day_of_week='sun', hour=9,  minute=0)
scheduler.add_job(weekly_options_review,     'cron', day_of_week='sun', hour=9,  minute=30)
scheduler.add_job(monthly_calibration,       'cron', day=1,             hour=8,  minute=0)
scheduler.add_job(quarterly_learning_review, 'cron', month='1,4,7,10',  day=1,   hour=8)
```

---

## OPTIONS SIGNAL ENGINE (COMPLETE LOGIC)

### Signal Gate Checks (ALL must pass)
```python
# backend/bot/options_analyzer.py

SIGNAL_GATES = {
    'data_quality': {
        'min_fresh_signals': 40,          # of 47 signals
        'max_data_age_minutes': 5,
    },
    'timing': {
        'not_before_minutes_after_open': 30,     # no signal before 9:45 AM
        'not_after_minutes_before_close': 60,    # no signal after 2:30 PM
        'cooldown_after_sl_minutes': 60,         # wait 60min after any SL hit
    },
    'min_quality': {
        'min_confidence': 55,
        'min_rr_ratio': 2.0,              # HARD MINIMUM — no exceptions
        'max_daily_signals': 2,
    },
    'put_specific': {
        'nifty_must_be_below_vwap': True,
        'min_vix': 15.0,
        'fii_direction': 'SELL',
        'min_fii_consecutive_sell_days': 2,
        'pcr_max': 0.95,
    },
    'call_specific': {
        'nifty_must_be_above_vwap': True,
        'max_vix': 28.0,
        'fii_direction': 'BUY',
        'min_fii_consecutive_buy_days': 2,
        'pcr_min': 0.70,
    }
}
```

### Position Calculator
```python
def calculate_position(capital: float, signal: dict) -> dict:
    """
    Returns minimum AND recommended position sizes.
    Both always shown to user.
    MINIMUM = 1 lot always
    RECOMMENDED = max within 2% risk rule
    """
    lot_size = 25  # Nifty — adjust for BankNifty (15)
    ltp = signal['ltp']
    sl = signal['stop_loss']
    t1 = signal['target1']
    t2 = signal['target2']

    risk_per_unit = abs(ltp - sl)
    reward_t1 = abs(t1 - ltp)
    reward_t2 = abs(t2 - ltp)
    rr = reward_t1 / risk_per_unit  # must be >= 2.0

    if rr < 2.0:
        raise ValueError(f"R:R {rr:.2f} below minimum 2.0 — signal blocked")

    risk_per_lot = risk_per_unit * lot_size
    premium_per_lot = ltp * lot_size

    # MINIMUM (1 lot)
    minimum = {
        "lots": 1,
        "premium": round(premium_per_lot, 2),
        "max_loss": round(risk_per_lot, 2),
        "max_loss_pct": round((risk_per_lot / capital) * 100, 2),
        "profit_t1": round(reward_t1 * lot_size, 2),
        "profit_t2": round(reward_t2 * lot_size, 2),
    }

    # RECOMMENDED (within 2% risk + 20% capital rules)
    max_loss_allowed = capital * 0.02
    max_capital_allowed = capital * 0.20
    lots_by_risk = int(max_loss_allowed / risk_per_lot)
    lots_by_capital = int(max_capital_allowed / premium_per_lot)
    rec_lots = max(1, min(lots_by_risk, lots_by_capital, 10))

    recommended = {
        "lots": rec_lots,
        "premium": round(rec_lots * premium_per_lot, 2),
        "max_loss": round(rec_lots * risk_per_lot, 2),
        "max_loss_pct": round((rec_lots * risk_per_lot / capital) * 100, 2),
        "profit_t1": round(rec_lots * reward_t1 * lot_size, 2),
        "profit_t2": round(rec_lots * reward_t2 * lot_size, 2),
        "capital_deployed_pct": round((rec_lots * premium_per_lot / capital) * 100, 2),
    }

    # PARTIAL EXIT PLAN (max profit strategy)
    t1_lots = max(1, int(rec_lots * 0.75))
    t2_lots = rec_lots - t1_lots
    trailing_sl = ltp + (reward_t1 * 0.70) if signal['signal_type'] == 'BUY_PUT' \
                  else ltp - (reward_t1 * 0.70)

    partial_plan = {
        "exit_at_t1_lots": t1_lots,
        "hold_to_t2_lots": t2_lots,
        "profit_if_t1_exit": round(t1_lots * reward_t1 * lot_size, 2),
        "profit_if_t2_all": round(
            t1_lots * reward_t1 * lot_size + t2_lots * reward_t2 * lot_size, 2),
        "trailing_sl_after_t1": round(trailing_sl, 0),
    }

    charges = estimate_charges(rec_lots, ltp, lot_size)

    return {
        "minimum": minimum,
        "recommended": recommended,
        "partial_exit_plan": partial_plan,
        "rr_ratio": round(rr, 2),
        "charges_estimate": charges,
        "warnings": build_warnings(capital, minimum, recommended),
    }
```

### AUTO Mode — No Confirmation Required
```python
async def handle_new_signal(signal: dict, users: list):
    """
    AUTO mode: Trade is logged immediately when signal fires.
    No user action required. No confirmation button.
    Bot assumes trade is taken at signal LTP.
    """
    for user in users:
        if user.trade_mode == 'auto' and user.is_active:
            position = calculate_position(user.capital, signal)

            # Log trade immediately — no waiting
            trade = Trade(
                signal_id=signal['id'],
                user_id=user.id,
                trade_mode='auto',
                capital_at_entry=user.capital,
                lots=position['recommended']['lots'],
                entry_premium=signal['ltp'],
                entry_time=datetime.now(),
                rr_at_entry=position['rr_ratio'],
                premium_total=position['recommended']['premium'],
                max_loss_calculated=position['recommended']['max_loss'],
                max_loss_pct=position['recommended']['max_loss_pct'],
                target1_profit_calculated=position['recommended']['profit_t1'],
                target2_profit_calculated=position['recommended']['profit_t2'],
                partial_t1_lots=position['partial_exit_plan']['exit_at_t1_lots'],
                partial_t2_lots=position['partial_exit_plan']['hold_to_t2_lots'],
                trailing_sl_after_t1=position['partial_exit_plan']['trailing_sl_after_t1'],
                status='OPEN'
            )
            await db.save(trade)

            # Start monitoring
            await start_trade_monitoring(trade, signal)

            # Notify (informational — not asking for confirmation)
            await send_telegram_notification(user, {
                "type": "AUTO_TRADE_OPEN",
                "message": f"⚡ AUTO TRADE OPENED\n"
                           f"{signal['strike']} {signal['option_type']} "
                           f"· ₹{signal['ltp']} · {trade.lots} lots\n"
                           f"T1: ₹{signal['target1']} | T2: ₹{signal['target2']} "
                           f"| SL: ₹{signal['stop_loss']}\n"
                           f"Max loss: ₹{trade.max_loss_calculated:,.0f} "
                           f"({trade.max_loss_pct:.2f}% of capital)\n"
                           f"Bot is monitoring every 30 seconds."
            })
            await broadcast_to_websocket(user.id, {"type": "TRADE_OPENED", "trade": trade})

        elif user.trade_mode == 'manual':
            # Signal shown on website — user fills in their own price/qty
            await broadcast_to_websocket(user.id, {
                "type": "SIGNAL_AWAITING_MANUAL_ENTRY",
                "signal": signal
            })
```

### Trade Monitoring
```python
async def monitor_trade(trade_id: int):
    """
    Runs every 30 seconds for each open trade.
    Checks T1, T2, SL, exit condition.
    """
    trade = await db.get_trade(trade_id)
    signal = await db.get_signal(trade.signal_id)

    if trade.status != 'OPEN':
        return  # already closed

    current_premium = await get_current_premium(
        signal['strike'], signal['option_type'], signal['expiry']
    )

    if current_premium is None:
        return  # data unavailable, try next cycle

    # Check T1
    if current_premium >= signal['target1'] and not trade.t1_exit_done:
        await handle_t1_hit(trade, signal, current_premium)

    # Check T2 (on remaining lots after T1)
    elif current_premium >= signal['target2'] and trade.t1_exit_done:
        await handle_t2_hit(trade, signal, current_premium)

    # Check SL
    elif current_premium <= signal['stop_loss']:
        await handle_sl_hit(trade, signal, current_premium)

    # Check trailing SL (if T1 already hit)
    elif trade.t1_exit_done and trade.trailing_sl_after_t1:
        if current_premium <= trade.trailing_sl_after_t1:
            await handle_trailing_sl_hit(trade, signal, current_premium)

    # Check exit condition (Nifty level)
    nifty_price = await get_nifty_price()
    if violates_exit_condition(nifty_price, signal['exit_condition']):
        await handle_condition_exit(trade, signal, current_premium)

    # Update unrealised P&L on websocket
    unrealised = (current_premium - trade.entry_premium) * trade.lots * 25
    await broadcast_pnl_update(trade.user_id, trade_id, unrealised, current_premium)
```

---

## CLAUDE API PROMPT TEMPLATES

### Morning Brief Prompt
```python
MORNING_PROMPT = """
You are a professional Indian equity market analyst.
Your job is to write a morning market brief for Nifty 50 traders.

STRICT RULES:
1. NEVER generate or invent numbers — only use numbers provided below
2. Output must be valid JSON matching the schema at the end
3. Confidence must be 0-100 integer, reflecting genuine uncertainty
4. If data quality is LOW, confidence must be below 50
5. Always provide both bull and bear case
6. Keep telegram_message under 400 words

TODAY: {date}
TIME: {time} IST (market opens in {minutes_to_open} minutes)

═══ LIVE DATA (all verified, fetched at {fetch_time}) ═══
GIFT Nifty:     {gift_nifty} ({gift_nifty_change:+.2f}% vs yesterday close)
Nifty prev:     {nifty_prev_close}
S&P 500:        {sp500_close} ({sp500_change:+.2f}%)
Nasdaq:         {nasdaq_change:+.2f}%
Nikkei:         {nikkei_change:+.2f}%
Hang Seng:      {hangseng_change:+.2f}%
Shanghai:       {shanghai_change:+.2f}%

Crude Brent:    ${crude} ({crude_change:+.2f}%)
Gold:           ${gold} ({gold_change:+.2f}%)
USD/INR:        ₹{usd_inr} ({usd_inr_change:+.2f}%)
DXY:            {dxy} ({dxy_change:+.2f}%)
US 10Y Yield:   {us_10y}% ({us_10y_change:+.0f}bps)

India VIX:      {vix} ({vix_change:+.1f})
Nifty PE:       {pe} | PB: {pb} | Div Yield: {div_yield}%
FII yesterday:  ₹{fii_net:,.0f}cr ({fii_direction})
FII streak:     {fii_consecutive_days} consecutive {fii_direction} days
PCR:            {pcr}
Drawdown/ATH:   {drawdown_from_ath:.1f}%

═══ DATA FLAGS ═══
{data_flags}

═══ TODAY'S EVENTS ═══
{economic_events}

═══ TOP NEWS (last 12 hours) ═══
{news_items}

═══ HISTORICAL PATTERN MATCH ═══
{pattern_match_summary}

═══ YOUR PREVIOUS PREDICTIONS THIS WEEK ═══
{recent_predictions}

═══ ACTIVE SIGNAL RULES (learned from losses) ═══
{signal_rules}

OUTPUT THIS EXACT JSON:
{{
  "direction": "UP|DOWN|FLAT",
  "magnitude_low": -0.8,
  "magnitude_high": -0.3,
  "confidence": 62,
  "confidence_reason": "...",
  "bull_case": "...",
  "bear_case": "...",
  "key_trigger_to_watch": "...",
  "data_quality": "HIGH|MEDIUM|LOW",
  "similar_days_found": 6,
  "prediction_basis": ["GIFT_NIFTY", "FII", "CRUDE"],
  "telegram_message": "Full formatted message for Telegram here"
}}
"""
```

### Options Signal Prompt
```python
OPTIONS_SIGNAL_PROMPT = """
You are an expert Nifty 50 options trader.
Analyze the data and determine if a PUT or CALL signal should be generated.

STRICT RULES:
1. NEVER generate numbers — all price levels come from the options chain data provided
2. R:R must be minimum 1:2 — if you cannot achieve this, output signal_type: "NONE"
3. Stop loss must be a meaningful technical level, not arbitrary
4. Targets must be realistic resistance/support from the options chain
5. Confidence reflects how many gates are strongly met
6. Output ONLY valid JSON

DATA AT {time}:
Nifty Price:    {nifty_price}
VWAP:           {vwap}
Nifty vs VWAP:  {nifty_vs_vwap:+.2f}%
VIX:            {vix}
PCR:            {pcr}
FII today:      ₹{fii_net:,.0f}cr ({fii_direction})
FII streak:     {fii_consecutive} consecutive days
India VIX trend: {vix_trend} (last 1hr)

Technical (5-min chart):
RSI:            {rsi_5m}
9 EMA:          {ema9}
21 EMA:         {ema21}
Volume vs avg:  {volume_ratio:.1f}x

Options Chain data:
{options_chain_relevant_strikes}

Active signal rules:
{signal_rules}

Gates that MUST pass:
- Min VIX for PUT: {min_vix_put}
- FII consecutive days: {min_fii_days}
- Not within first 30min: {time_check}
- Not within last 60min: {time_check_close}
- Data fresh: {data_quality}
- Cooldown after last SL: {cooldown_ok}

OUTPUT:
{{
  "signal_type": "BUY_PUT|BUY_CALL|NONE",
  "reason_if_none": "...",
  "strike": 22800,
  "option_type": "PE|CE",
  "suggested_expiry": "03-Apr-2026",
  "approximate_ltp": 185.5,
  "stop_loss": 145.0,
  "target1": 240.0,
  "target2": 310.0,
  "exit_condition": "Exit if Nifty crosses 22950",
  "rr_ratio": 2.4,
  "confidence": 62,
  "signal_basis": ["below_vwap", "fii_5_sell_days", "vix_rising", "pcr_bearish"],
  "gates_passed": {{"vix": true, "fii": true, "timing": true, "data": true}}
}}
"""
```

### Loss Analysis Prompt
```python
LOSS_ANALYSIS_PROMPT = """
You are analyzing a losing options trade to extract learning.

TRADE:
Signal type:    {signal_type}
Strike:         {strike}
Entry premium:  ₹{entry_premium}
Stop loss:      ₹{stop_loss}
Target 1:       ₹{target1}
Entry time:     {entry_time}
Exit premium:   ₹{exit_premium} (SL hit)
Exit time:      {exit_time}
Loss:           ₹{loss_amount} ({loss_pct:.2f}% of capital)
Trade mode:     {trade_mode}

MARKET AT ENTRY:
{conditions_at_entry}

MARKET AT EXIT:
{conditions_at_exit}

WHAT HAPPENED BETWEEN (key movements):
{intraday_movement_summary}

NEWS BETWEEN ENTRY AND EXIT:
{news_items}

PAST SIMILAR LOSSES IN DATABASE:
{similar_losses}

CURRENT SIGNAL RULES:
{current_rules}

Analyze this loss and output JSON:
{{
  "miss_category": "one of: FII_REVERSAL|RR_DEGRADED_MANUAL|SL_TOO_TIGHT|
                    LOW_VIX_PUT|EARLY_SESSION|EXPIRY_DAY|NEWS_SHOCK|
                    GLOBAL_DISCONNECT|CORRECT_SETUP_BAD_LUCK|OVER_LEVERAGED",
  "root_cause": "clear explanation of why the trade failed",
  "sl_was_correct": true|false,
  "sl_recommendation": "TIGHTER|WIDER|SAME",
  "signal_adjustment": "specific rule change to apply",
  "rule_to_update": "exact field name in signal_rules.json",
  "new_rule_value": "new value",
  "expected_improvement": "what this should prevent in future",
  "confidence_in_analysis": 75
}}
"""
```

---

## API ENDPOINTS (ALL)

### Authentication
```
POST   /auth/login              body: {email, password}
POST   /auth/logout             header: Bearer token
POST   /auth/refresh            header: Bearer token
GET    /auth/me                 header: Bearer token
```

### Market Data
```
GET    /api/market/live         all 47 signals (WebSocket preferred)
GET    /api/market/snapshot/{date}/{time}
GET    /api/market/historical/{symbol}?days=365
GET    /api/market/nifty-pe
GET    /api/market/fii-dii
```

### Signals & Trades
```
GET    /api/signals/active      current open signals
GET    /api/signals/history?days=30
POST   /api/signals/{id}/manual-entry   body: {entry_premium, lots, entry_time}
                                         (manual mode only)
GET    /api/trades/open         open trades for current user
GET    /api/trades/history?days=30
POST   /api/trades/{id}/exit    body: {exit_premium, exit_reason}
GET    /api/trades/pnl-summary  daily/weekly/monthly P&L
GET    /api/trades/capital      get user's capital setting
PUT    /api/trades/capital      body: {capital}
PUT    /api/trades/mode         body: {mode: "auto"|"manual"}
```

### Predictions
```
GET    /api/predictions/today
GET    /api/predictions/history?days=30
GET    /api/predictions/accuracy?days=30
GET    /api/predictions/learning-log
```

### Admin (admin/super_admin only)
```
GET    /api/admin/users
POST   /api/admin/users         body: {email, name, role, password}
PUT    /api/admin/users/{id}    body: {role, is_active}
DELETE /api/admin/users/{id}
GET    /api/admin/audit-log
GET    /api/admin/signal-rules
PUT    /api/admin/signal-rules  body: {rule_name, value, reason}
```

### Self-Heal
```
GET    /api/heal/status         current system health
GET    /api/heal/errors?limit=20
POST   /api/heal/approve/{error_id}  approve AI fix
POST   /api/heal/reject/{error_id}   reject AI fix, trigger manual
POST   /api/heal/restart/{service}
POST   /api/heal/rollback
```

### WebSocket
```
WS     /ws/market              broadcasts every 5s during market hours
       Events: PRICE_UPDATE, SIGNAL_GENERATED, TRADE_OPENED,
               TRADE_ALERT_T1, TRADE_ALERT_T2, TRADE_ALERT_SL,
               BOT_ACTIVITY, HEAL_WARNING, PNL_UPDATE
```

---

## ROLE-BASED ACCESS CONTROL

```python
PERMISSIONS = {
    'super_admin': ['*'],    # everything
    'admin': [
        'view_dashboard', 'view_signals', 'view_trades', 'view_predictions',
        'view_bot_feed', 'view_self_heal', 'view_reports', 'view_admin',
        'manage_users',      # add/remove analyst and viewer only
        'configure_bot',     # change signal rules, capital
        'approve_heal',      # approve/reject AI fixes
        'restart_services',
    ],
    'analyst': [
        'view_dashboard', 'view_signals', 'view_trades', 'view_predictions',
        'view_bot_feed', 'view_reports',
        'enter_manual_trade',
        'exit_trade',
        'set_capital',       # their own capital only
    ],
    'viewer': [
        'view_dashboard',    # live market only
    ]
}
```

---

## SELF-HEALING ENGINE

### Watchdog (runs every 30 seconds)
```python
SERVICES_TO_MONITOR = [
    {'name': 'fastapi',    'port': 8000, 'path': '/health'},
    {'name': 'scheduler',  'type': 'process', 'name': 'apscheduler'},
    {'name': 'websocket',  'port': 8001},
    {'name': 'postgres',   'type': 'db'},
    {'name': 'redis',      'type': 'redis'},
    {'name': 'telegram',   'type': 'custom', 'check': check_telegram_bot},
    {'name': 'data_feed',  'type': 'custom', 'check': check_data_freshness},
]

SEVERITY_RULES = {
    1: ['DeprecationWarning', 'slowresponse'],     # log only
    2: ['ConnectionError', 'Timeout', 'ProcessCrashed'],  # auto-restart
    3: ['SyntaxError', 'ImportError', 'AttributeError'],  # AI fix
    4: ['PermissionError', 'SecurityError', 'DBMigration', 'AuthChange'],  # human only
}
```

### AI Fix Request to Claude
```python
HEAL_PROMPT = """
A production error occurred. Analyze it and provide a fix.

ERROR:
Service:   {service}
Type:      {error_type}
Severity:  {severity}
Traceback:
{traceback}

Last 50 log lines:
{log_context}

Relevant source code:
{source_code}

Similar past errors fixed:
{similar_fixes}

Rules:
- Fix must be minimal — change as little as possible
- Fix must not touch authentication or security code
- Fix must include test cases
- Fix must not change database schema without migration
- If you cannot safely fix this, say so clearly

Output JSON:
{{
  "can_fix": true|false,
  "reason_if_cannot": "...",
  "file_to_change": "backend/bot/collector.py",
  "original_code": "exact code to replace",
  "fixed_code": "replacement code",
  "explanation": "what was wrong and what the fix does",
  "test_cases": [
    {{"name": "test_name", "code": "def test(): ...", "expected": "passes"}}
  ],
  "risk_level": "LOW|MEDIUM|HIGH",
  "requires_restart": true|false
}}
"""
```

---

## TESTING RULES (NON-NEGOTIABLE)

```
RULE 1:  No code deploys without all tests passing
RULE 2:  Tests run in isolated environment — never against production DB
RULE 3:  AI-generated fixes need minimum 3 passing test cases
RULE 4:  Any fix touching auth/security = SEVERITY 4 = human only
RULE 5:  Database migrations = human approval required always
RULE 6:  Test failures are logged permanently — never hidden or skipped
RULE 7:  Rollback must always work — git revert before every deploy
RULE 8:  Production data never in tests — use anonymized fixtures only
RULE 9:  All tests must complete in under 60 seconds total
RULE 10: Flaky tests (pass <80% of time) treated as failures
```

### Test Files to Create
```
tests/unit/test_validator.py         data validation rules
tests/unit/test_position_calc.py     position sizing logic
tests/unit/test_rr_check.py          R:R ratio enforcement
tests/unit/test_signal_gates.py      all signal gate logic
tests/unit/test_pnl_calc.py          P&L and charges calculation
tests/unit/test_pattern_matcher.py   historical pattern matching
tests/integration/test_data_pipeline.py   full data fetch flow
tests/integration/test_signal_flow.py     signal → trade flow
tests/integration/test_websocket.py       live data broadcast
tests/api/test_auth.py               all auth endpoints
tests/api/test_signals.py            signal endpoints
tests/api/test_trades.py             trade endpoints
tests/api/test_admin.py              admin endpoints + RBAC
tests/security/test_injection.py     SQL injection, XSS, JWT forgery
tests/security/test_rate_limit.py    brute force protection
tests/ui/test_login.py               Playwright — login flow
tests/ui/test_dashboard.py           Playwright — live data display
tests/ui/test_signal_card.py         Playwright — signal interaction
tests/ui/test_trade_journal.py       Playwright — journal display
tests/ui/test_heal_warning.py        Playwright — heal UI flow
tests/ui/test_rbac_ui.py             Playwright — role-based visibility
```

---

## TELEGRAM MESSAGE FORMATS

### Morning Brief
```
🌅 MORNING BRIEF — {date} | {time} IST
━━━━━━━━━━━━━━━━━━━━━
📊 DATA ({freshness}/47 signals fresh)
┌ GIFT Nifty: {gift} ({gift_chg:+.2f}%)
├ S&P 500:    {sp500_chg:+.2f}%
├ Nikkei:     {nikkei_chg:+.2f}%
├ Crude:      ${crude} ({crude_chg:+.2f}%)
├ USD/INR:    ₹{inr}
├ India VIX:  {vix}
├ FII:        ₹{fii:,.0f}cr — Day {streak} of {direction}
└ Nifty PE:   {pe} ({pe_zone})

⚠️ FLAGS: {flags}
📅 TODAY: {events}

🔍 PATTERN: {pattern_summary}

🤖 PREDICTION: {direction} ({mag_low} to {mag_high}%)
   Confidence: {confidence}% | Data: {quality}
   Bull: {bull_case}
   Bear: {bear_case}
   Watch: {key_trigger}
━━━━━━━━━━━━━━━━━━━━━
```

### Options Signal
```
━━━━━━━━━━━━━━━━━━━━━
⚡ OPTIONS SIGNAL | {time}
━━━━━━━━━━━━━━━━━━━━━
TYPE   : {BUY PUT / BUY CALL}
STRIKE : {strike} {CE/PE}
EXPIRY : {expiry}
LTP    : ₹{ltp}

🎯 T1  : ₹{t1} (+{t1_pct:.1f}%)
🎯 T2  : ₹{t2} (+{t2_pct:.1f}%)
🛑 SL  : ₹{sl} (-{sl_pct:.1f}%)
📊 R:R : 1:{rr:.1f} ✓

💰 FOR ₹{capital:,.0f}:
  Rec: {lots} lots | Premium ₹{premium:,.0f}
  Max loss: ₹{max_loss:,.0f} ({loss_pct:.1f}%)
  T1 profit: +₹{t1_profit:,.0f}
  Smart: Book {t1_lots} at T1, hold {t2_lots} to T2

📌 {basis_1}
   {basis_2}
   {basis_3}

🔢 Confidence: {confidence}% | {fresh}/47 fresh
⏱ Valid: 90 min
━━━━━━━━━━━━━━━━━━━━━
[AUTO MODE: Trade logged]
```

### T1 Hit Alert
```
🎯 TARGET 1 HIT! | {time}
{strike} {type} reached ₹{t1}

Trade: {entry} → {t1} (+{pct:.1f}%)
{t1_lots} lots: +₹{t1_profit:,.0f} locked

Remaining {t2_lots} lots riding to T2 (₹{t2})
Trailing SL now: ₹{trailing_sl}

Your call: Book all / Hold remainder
```

### Stop Loss Hit Alert
```
🛑 STOP LOSS HIT | {time}
{strike} {type} dropped to ₹{sl}

Trade: ₹{entry} → ₹{sl}
Loss: ₹{loss:,.0f} ({loss_pct:.1f}% of capital)

Bot running loss analysis now.
Learning engine will update signal rules.
```

---

## WEBSITE UI REQUIREMENTS

### Login Page
- Email + password fields
- Error message for wrong credentials
- Lockout message after 5 failed attempts
- No "forgot password" needed for V1

### Dashboard Page (live, all roles can see basics)
- Topbar: Nifty price, VIX, PCR, market open/close status, live time
- Ticker strip: all major indices scrolling
- Hero cards: Nifty live, drawdown from ATH, FII today, today's prediction
- Self-heal warning banner (if any active)
- Bot activity feed (real-time log of everything bot does)
- Key signals grid (PE, PCR, VIX, VWAP, etc.)
- System status sidebar

### Options Page (analyst + above)
- Capital input at top (persisted to DB per user)
- Trade mode toggle: AUTO / MANUAL
  - AUTO: no confirm button — signal fires = trade logged automatically
  - MANUAL: shows entry price, lots, time input fields
- Active signal card (PUT or CALL)
  - Strike, LTP, T1, T2, SL with percentages
  - R:R badge (green if ≥ 1:2, red if blocked)
  - Minimum quantity box
  - Recommended position box
  - Signal basis list
  - Confidence bar
  - In AUTO: shows "● Trade auto-logged at ₹X · Y lots"
  - In MANUAL: shows input fields + confirm button
- Open trade card (live tracking)
  - Live premium with colour
  - Live P&L in rupees and % of capital
  - Progress bar: entry → T1
  - Exit buttons: T1, T2, SL, Manual
  - Bot notes section
- Trade journal table (entry, exit, mode, lots, gross, charges, net, R:R)
- Loss learning panel

### Self-Heal Page (admin + above)
- System health grid (all services with green/amber/red dots)
- Active warnings (if any) with Allow/Stop/Restart/View Code buttons
- Error history table
- Recent fixes applied

### Admin Page (admin + above)
- User list with role badges
- Add user form
- Edit role dropdown
- Deactivate user toggle
- Audit log table

---

## IMPLEMENTATION PRIORITY ORDER

1. Database setup (Alembic + all schemas)
2. Auth system (JWT + RBAC)
3. Data collector (all 47 signals)
4. Historical data download (30 years)
5. WebSocket server
6. Bot scheduler (basic)
7. Morning/mid/close briefs (Claude integration)
8. REST API endpoints
9. Frontend: Login + Dashboard
10. Options signal engine
11. Trade tracking (auto mode first, then manual)
12. Frontend: Options page
13. Loss learning engine
14. Self-healing watchdog
15. Frontend: Self-heal page + Admin page
16. Test suite (all categories)
17. Telegram bot integration
18. Deploy + Nginx config

---

## IMPORTANT CONSTRAINTS

1. Options signals — PUT requires VIX ≥ 15 and ≥ 2 consecutive FII sell days. Hard rules.
2. R:R minimum 1:2 — any signal below this is blocked and never reaches the user.
3. AUTO mode — no confirmation button. Signal generated = trade immediately logged.
4. MANUAL mode — user enters their actual price. R:R is recalculated from their price. Warning if below 1:2.
5. Max risk per trade = 2% of user's capital. Max deployment = 20%.
6. Minimum 1 lot always shown even if it exceeds risk rule (with warning).
7. Partial exit plan always calculated: 75% exit at T1, 25% hold to T2 with trailing SL.
8. Self-heal never touches auth/security code — always severity 4 (human required).
9. Every code change (AI or human) is committed to git before deployment.
10. All data points have timestamps — Claude never invents market numbers.

---

## DISCLAIMER TO SHOW ON ALL TRADING PAGES

```
⚠️ IMPORTANT: This system generates technical analysis signals for
educational and tracking purposes only. Options trading carries
significant risk of loss. This is NOT SEBI-registered investment advice.
Never trade more than you can afford to lose. Always verify with your
own broker. Past signal performance does not guarantee future results.
```
