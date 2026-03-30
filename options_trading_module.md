# Options Trading Module — Complete Architecture
## Put/Call Signals · Position Sizing · Trade Journal · Loss Learning

---

## ⚠️ IMPORTANT DISCLAIMER
This system generates signals based on technical and statistical analysis.
Options trading involves significant risk of loss. All signals are for
educational/informational purposes. Never trade more than you can afford to lose.
The system is NOT a SEBI-registered advisor.

---

## 1. SIGNAL STRUCTURE — What Bot Sends

### Telegram + Website Signal Format
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ OPTIONS SIGNAL — 11:47 IST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TYPE      : BUY PUT (Bearish)
UNDERLYING: Nifty 50
EXPIRY    : 03 Apr 2026 (Weekly)

STRIKE    : 22,800 PE
LTP (now) : ₹185.50

🎯 TARGET 1 : ₹240  (+29.4%)
🎯 TARGET 2 : ₹310  (+67.1%)
🛑 STOP LOSS: ₹145  (−21.8%)
🚪 EXIT IF  : Nifty crosses 22,950

SIGNAL BASIS:
• Nifty below VWAP (22,905) since 10:30
• FII net sell ₹1,847cr — 5th day
• VIX rising: 18.2 → 19.1 in 45min
• PCR: 0.82 (bearish)
• S&P futures: −0.4%

CONFIDENCE  : 62%
RISK/REWARD : 1 : 2.4
DATA QUALITY: HIGH (46/47 signals fresh)

⏱ Signal valid for: 90 minutes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 2. POSITION SIZING ENGINE

### How It Works
User enters capital on website → Bot calculates:
- How many lots to buy
- Exact premium to pay
- Max loss in rupees
- Risk % of capital

### Nifty Options Lot Size
- Nifty 50: 1 lot = 25 units
- 1 lot of 22,800 PE at ₹185.50 = 25 × 185.50 = ₹4,637.50 premium

### Position Sizing Rules (Hard-coded safety)
```python
POSITION_SIZING_RULES = {
    # Never risk more than X% of capital per trade
    "max_risk_per_trade_pct": 2.0,      # 2% max
    
    # Never use more than X% of capital at once
    "max_capital_deployed_pct": 20.0,   # 20% max per signal
    
    # Minimum capital to trade
    "minimum_capital": 50000,           # ₹50,000 minimum
    
    # Maximum lots for any signal
    "max_lots": 10,
    
    # Stop loss must always be set
    "sl_mandatory": True,
    
    # Warning if premium > X% of capital
    "premium_warning_pct": 5.0
}
```

### Position Size Calculation
```python
def calculate_position(capital, signal):
    """
    capital = user's entered amount e.g. ₹2,00,000
    signal = {strike, ltp, stop_loss, target1, target2, type}
    """
    # Risk per trade = 2% of capital
    max_risk_rupees = capital * 0.02  # ₹4,000

    # Premium per lot
    lot_size = 25  # Nifty
    premium_per_lot = signal['ltp'] * lot_size  # ₹185.50 × 25 = ₹4,637.50

    # Risk per lot = (LTP - Stop Loss) × lot_size
    risk_per_lot = (signal['ltp'] - signal['stop_loss']) * lot_size
    # = (185.50 - 145) × 25 = ₹1,012.50

    # Max lots based on risk
    max_lots_by_risk = int(max_risk_rupees / risk_per_lot)  # 4000/1012 = 3 lots

    # Max lots based on capital deployment (20%)
    max_capital = capital * 0.20  # ₹40,000
    max_lots_by_capital = int(max_capital / premium_per_lot)  # 40000/4637 = 8 lots

    # Take the lower of both
    recommended_lots = min(max_lots_by_risk, max_lots_by_capital)
    recommended_lots = max(1, min(recommended_lots, RULES['max_lots']))

    return {
        "lots": recommended_lots,
        "premium_per_lot": premium_per_lot,
        "total_premium": recommended_lots * premium_per_lot,
        "max_loss": recommended_lots * risk_per_lot,
        "max_loss_pct": (recommended_lots * risk_per_lot / capital) * 100,
        "target1_profit": recommended_lots * (signal['target1'] - signal['ltp']) * lot_size,
        "target2_profit": recommended_lots * (signal['target2'] - signal['ltp']) * lot_size,
        "capital_deployed_pct": (recommended_lots * premium_per_lot / capital) * 100,
        "risk_reward": (signal['target1'] - signal['ltp']) / (signal['ltp'] - signal['stop_loss'])
    }
```

---

## 3. TRADE JOURNAL DATABASE

```sql
-- Every signal the bot generates
CREATE TABLE signals (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP,
    signal_type TEXT,          -- 'BUY_CALL', 'BUY_PUT'
    underlying TEXT,           -- 'NIFTY50', 'BANKNIFTY'
    expiry DATE,
    strike INTEGER,
    option_type TEXT,          -- 'CE', 'PE'
    ltp_at_signal REAL,        -- premium when signal was given
    target1 REAL,
    target2 REAL,
    stop_loss REAL,
    exit_condition TEXT,       -- "Nifty crosses 22,950"
    confidence INTEGER,
    risk_reward REAL,
    signal_basis JSONB,        -- what data drove this signal
    valid_until TIMESTAMP,
    status TEXT DEFAULT 'OPEN' -- OPEN, HIT_T1, HIT_T2, HIT_SL, EXPIRED, MANUAL_EXIT
);

-- Each user's trade based on a signal
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    signal_id INTEGER REFERENCES signals(id),
    user_id UUID REFERENCES users(id),
    capital_entered REAL,       -- what user entered
    lots INTEGER,
    entry_premium REAL,         -- actual premium paid
    entry_time TIMESTAMP,
    entry_nifty_level REAL,

    -- Exit
    exit_premium REAL,
    exit_time TIMESTAMP,
    exit_nifty_level REAL,
    exit_reason TEXT,           -- 'TARGET1', 'TARGET2', 'STOP_LOSS', 'MANUAL', 'EXPIRED'

    -- P&L
    gross_pnl REAL,             -- before charges
    charges REAL,               -- brokerage + STT + GST estimate
    net_pnl REAL,               -- after charges
    net_pnl_pct REAL,           -- % of capital
    
    status TEXT DEFAULT 'OPEN'
);

-- What the bot learned from each loss
CREATE TABLE trade_learnings (
    id SERIAL PRIMARY KEY,
    trade_id INTEGER REFERENCES trades(id),
    signal_id INTEGER REFERENCES signals(id),
    trade_date DATE,
    loss_amount REAL,
    loss_pct REAL,
    
    -- Analysis
    what_signal_said TEXT,
    what_actually_happened TEXT,
    miss_category TEXT,         -- same taxonomy as market predictions
    root_cause TEXT,            -- Claude's analysis
    
    -- What to change
    signal_adjustment TEXT,     -- e.g. "Require VIX > 20 for PUT signals"
    sl_was_correct BOOLEAN,
    sl_recommendation TEXT,     -- tighter/wider/same
    
    -- Did we apply this learning?
    learning_applied BOOLEAN DEFAULT false,
    learning_applied_date DATE,
    improvement_result TEXT,    -- did it help?
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Running performance stats per signal type
CREATE TABLE signal_performance (
    signal_type TEXT,           -- 'BUY_PUT', 'BUY_CALL'
    total_signals INTEGER,
    winning_signals INTEGER,
    losing_signals INTEGER,
    win_rate REAL,
    avg_win_pct REAL,
    avg_loss_pct REAL,
    expectancy REAL,            -- (win_rate × avg_win) - (loss_rate × avg_loss)
    best_conditions JSONB,      -- market conditions when wins happen
    worst_conditions JSONB,     -- market conditions when losses happen
    updated_at TIMESTAMP
);
```

---

## 4. LOSS LEARNING ENGINE

### When a Trade Hits Stop Loss
```python
def analyze_loss(trade, signal):
    """
    Called automatically when stop loss is hit.
    Claude analyzes why and what to change.
    """
    
    # Gather all context at time of signal
    context = {
        "signal_data": signal.signal_basis,
        "entry_market": get_snapshot_at(signal.timestamp),
        "exit_market": get_snapshot_at(trade.exit_time),
        "what_happened_between": get_intraday_data(signal.timestamp, trade.exit_time),
        "news_between": get_news_between(signal.timestamp, trade.exit_time),
        "past_similar_losses": find_similar_losses(signal),
    }
    
    # Ask Claude to analyze
    analysis = claude_analyze_loss(context)
    
    # Save structured learning
    learning = TradeLearning(
        trade_id=trade.id,
        signal_id=signal.id,
        loss_amount=trade.net_pnl,
        loss_pct=trade.net_pnl_pct,
        what_signal_said=signal.signal_basis,
        what_actually_happened=analysis.actual_outcome,
        miss_category=analysis.category,
        root_cause=analysis.root_cause,
        signal_adjustment=analysis.recommendation,
        sl_was_correct=analysis.sl_assessment,
        sl_recommendation=analysis.sl_recommendation,
    )
    
    # Update signal filter rules automatically
    update_signal_filters(analysis)
    
    return learning


def update_signal_filters(analysis):
    """
    Automatically tightens signal rules after losses.
    Examples:
    - If 5 consecutive PUT losses when PCR > 0.9 → require PCR < 0.85 for PUT signals
    - If SL hit 7/10 times when VIX < 15 → don't give PUT signals when VIX < 15
    - If losses cluster on F&O expiry day → reduce lot size by 50% on expiry
    """
    
    # These are stored in signal_rules.json and loaded at startup
    rules = load_signal_rules()
    
    if analysis.category == 'LOW_VIX_PUT_SIGNAL':
        rules['put_min_vix'] = max(rules.get('put_min_vix', 12), 15)
        
    if analysis.category == 'EXPIRY_DAY_LOSS':
        rules['expiry_day_lot_multiplier'] = 0.5
        
    if analysis.category == 'FII_REVERSAL':
        rules['require_fii_sell_streak'] = 3  # need 3 consecutive sell days
    
    save_signal_rules(rules)
    log_rule_change(analysis, rules)
```

### Weekly Loss Review
```python
def weekly_loss_review():
    """
    Every Sunday — comprehensive loss analysis.
    Updates signal generation thresholds.
    """
    
    week_trades = get_week_trades()
    losses = [t for t in week_trades if t.net_pnl < 0]
    
    if not losses:
        return  # Good week, no changes needed
    
    # Find patterns in losses
    loss_conditions = [get_conditions_at(t.signal.timestamp) for t in losses]
    
    # Ask Claude to find common patterns
    patterns = claude_find_loss_patterns(loss_conditions, losses)
    
    # Generate updated signal rules
    new_rules = claude_generate_updated_rules(
        current_rules=load_signal_rules(),
        loss_patterns=patterns,
        win_patterns=get_win_patterns(),
        history=get_all_learnings()
    )
    
    # Show on dashboard for admin approval before applying
    notify_dashboard('RULE_UPDATE_PROPOSAL', {
        'proposed_rules': new_rules,
        'reason': patterns,
        'expected_improvement': new_rules.expected_improvement
    })
```

---

## 5. BROKERAGE CHARGES CALCULATOR

```python
def calculate_charges(lots, premium, option_type):
    """
    Realistic P&L after all charges.
    Based on Zerodha/typical discount broker rates.
    """
    lot_size = 25
    total_units = lots * lot_size
    turnover = total_units * premium

    charges = {
        # Brokerage: ₹20 per order (Zerodha flat fee) × 2 (entry + exit)
        'brokerage': 40,

        # STT: 0.0125% on sell side (options)
        'stt': turnover * 0.000125,

        # Exchange transaction charge: 0.053%
        'exchange_charge': turnover * 0.00053,

        # GST: 18% on (brokerage + exchange charge)
        'gst': (40 + turnover * 0.00053) * 0.18,

        # SEBI charge: ₹10 per crore
        'sebi': (turnover / 10000000) * 10,

        # Stamp duty: 0.003% on buy side
        'stamp_duty': turnover * 0.00003,
    }

    charges['total'] = sum(charges.values())
    return charges
```

---

## 6. SIGNAL QUALITY GATES

### A signal is only sent if ALL of these pass:
```python
SIGNAL_GATES = {
    # Data quality
    "min_fresh_signals": 40,        # need 40/47 signals fresh
    "max_data_age_minutes": 5,      # no signal data older than 5 min

    # Market conditions for PUT signal
    "put_signal_gates": {
        "nifty_below_vwap": True,
        "min_vix": 15,              # learned: low VIX = bad for puts
        "fii_direction": "SELL",
        "pcr_max": 0.95,            # above 0.95 = puts expensive
        "min_time_in_session": 30,  # wait 30 min after open
        "max_time_before_close": 60,# no new signals in last 60 min
        "not_expiry_day": False,    # flag on expiry (reduce size)
    },

    # Market conditions for CALL signal
    "call_signal_gates": {
        "nifty_above_vwap": True,
        "max_vix": 28,              # high VIX = calls too expensive
        "fii_direction": "BUY",
        "pcr_min": 0.70,
        "min_time_in_session": 30,
        "max_time_before_close": 60,
    },

    # Risk gates
    "min_risk_reward": 1.5,         # no signal if R:R < 1.5
    "min_confidence": 55,           # no signal below 55% confidence
    "max_daily_signals": 2,         # max 2 signals per day
    "no_signal_after_sl_hit": 60,   # 60 min cooldown after SL hit
}
```

---

## 7. TEST CASES FOR OPTIONS MODULE

```python
# test_options.py

def test_position_size_respects_max_risk():
    capital = 200000  # ₹2 lakh
    signal = {'ltp': 185.50, 'stop_loss': 145, 'target1': 240}
    pos = calculate_position(capital, signal)
    max_loss = pos['lots'] * (185.50 - 145) * 25
    assert max_loss <= capital * 0.02  # never lose more than 2%

def test_minimum_capital_enforced():
    with pytest.raises(ValueError, match="minimum capital"):
        calculate_position(30000, mock_signal())  # below ₹50K minimum

def test_signal_not_sent_in_last_hour():
    signal_time = datetime(2026, 3, 30, 15, 0)  # 3 PM
    result = check_signal_gates(signal_time, mock_conditions())
    assert result['blocked'] == True
    assert result['reason'] == 'TOO_CLOSE_TO_CLOSE'

def test_no_signal_when_data_stale():
    stale_conditions = get_mock_conditions()
    stale_conditions['fresh_count'] = 35  # only 35/47 fresh
    result = check_signal_gates(datetime.now(), stale_conditions)
    assert result['blocked'] == True

def test_pnl_calculation_correct():
    trade = {
        'lots': 3, 'entry_premium': 185.50,
        'exit_premium': 240, 'lot_size': 25
    }
    charges = calculate_charges(3, 240, 'PE')
    gross_pnl = 3 * (240 - 185.50) * 25  # ₹4,087.50
    net_pnl = gross_pnl - charges['total']
    assert net_pnl > 0
    assert net_pnl < gross_pnl  # charges must reduce profit

def test_loss_learning_saves_to_db():
    trade = create_test_loss_trade()
    learning = analyze_loss(trade, trade.signal)
    assert learning.id is not None
    assert learning.miss_category is not None
    assert learning.sl_recommendation in ['TIGHTER', 'WIDER', 'SAME']

def test_signal_rules_update_after_losses():
    # Simulate 5 PUT losses with VIX < 15
    for _ in range(5):
        create_test_loss(signal_type='BUY_PUT', vix=14)
    weekly_loss_review()
    rules = load_signal_rules()
    assert rules['put_min_vix'] >= 15

def test_signal_cooldown_after_sl():
    hit_stop_loss_at(datetime.now())
    signal_attempt = attempt_signal(datetime.now() + timedelta(minutes=30))
    assert signal_attempt['blocked'] == True  # within 60 min cooldown

def test_user_cannot_enter_zero_capital():
    r = client.post('/api/trade/calculate',
                    headers={'Authorization': analyst_token},
                    json={'capital': 0, 'signal_id': 1})
    assert r.status_code == 422

def test_trade_journal_shows_all_trades():
    r = client.get('/api/trades/history',
                   headers={'Authorization': analyst_token})
    assert r.status_code == 200
    assert isinstance(r.json()['trades'], list)
```

---

## 8. COMPLETE FLOW — End to End

```
11:47 AM
Bot detects bearish conditions (all gates pass)
        ↓
Signal generated with strike, SL, target, confidence
        ↓
Telegram message sent + Website notification
        ↓
User opens website → sees signal card
        ↓
User enters capital: ₹2,00,000
        ↓
Bot calculates: 3 lots, ₹13,912 premium, max loss ₹3,037
        ↓
User clicks "I TOOK THIS TRADE" → trade logged as OPEN
        ↓
Bot monitors Nifty + Premium every minute
        ↓
SCENARIO A — Target 1 hit at 12:30 PM
  Premium reaches ₹240 → Bot sends alert
  "🎯 TARGET 1 HIT — Consider booking profit"
  P&L shown: +₹4,087 gross / +₹3,900 net
  User clicks "BOOKED" → trade logged as CLOSED
        ↓
SCENARIO B — Stop Loss hit at 12:15 PM
  Premium falls to ₹145 → Bot sends alert
  "🛑 STOP LOSS HIT — Exit now"
  P&L shown: −₹3,037 gross / −₹3,200 net (with charges)
  Trade auto-logged as CLOSED (or user confirms)
  Loss learning engine runs automatically
  Admin sees: "New learning recorded — see dashboard"
        ↓
3:35 PM End of day
  Full trade summary sent to Telegram
  All open positions flagged if any
  Daily P&L shown on website
```

---

## 9. CHARGES DISCLAIMER IN EVERY MESSAGE

```
Note on charges:
Brokerage + STT + Exchange + GST ≈ ₹150-300 per trade round trip
(varies by broker). Shown P&L is estimated. Actual may differ.
Always confirm with your broker's statement.
```
