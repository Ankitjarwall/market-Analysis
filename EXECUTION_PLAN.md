# AI Options Trading Platform Execution Plan

## 1. Executive stance

This platform should not ship as a "single FastAPI app that also happens to trade." It should ship as one codebase with clear runtime boundaries:

- `api` service: HTTP APIs, auth, read models, WebSocket fanout.
- `market_worker` service: market ingestion, feature computation, gating, AI decisioning, signal persistence.
- `execution_worker` service: order placement, broker reconciliation, stop management, trade lifecycle monitoring, risk enforcement.
- `postgres`: system of record.
- `redis`: hot cache, distributed locks, event fanout, freshness state.
- `frontend`: React application.

That is the right balance for MVP. Do not introduce microservices, Kafka, or a separate rules engine product early. Do not keep execution logic inside the API process.

The non-negotiable operating principle is:

`AI proposes. Deterministic policy decides. Broker adapter executes. Audit trail records every step.`

## 2. Current repo assessment

The current repository already has useful foundations:

- FastAPI app with auth, admin, market, signals, trades, and WebSocket routes.
- APScheduler-based timed jobs.
- AngelOne SmartStream integration.
- Signal generation, position sizing, trade monitoring, and Telegram notifications.
- React dashboard with Zustand store and live WebSocket updates.
- PostgreSQL models and Alembic migrations.

The current implementation is not yet safe enough for production AUTO trading because:

- scheduler, AI calls, market ingestion, execution logic, and WebSocket state currently live inside one backend runtime;
- live state is partly in memory, which is not restart-safe or horizontally safe;
- trade execution is represented as local trade creation, not a broker-grade order state machine;
- monitoring uses per-trade in-process loops instead of a durable execution queue or reconciler;
- order idempotency, fill reconciliation, broker order audit, and kill-switch semantics are not first-class;
- WebSocket fanout is in-memory and not backed by Redis pub/sub or an outbox;
- production Docker Compose still uses `uvicorn --reload`;
- AI output is too close to execution without a strict approval and validation envelope.

## 3. Product boundary

This is an intraday long-options platform for Indian index options. It is not a multi-strategy OMS, not a social trading app, and not a generic AI chat wrapper.

Production scope is:

- collect 47 market signals from live and polled sources;
- compute deterministic gates;
- ask Claude for a constrained directional decision;
- create either `BUY_CALL`, `BUY_PUT`, or `NONE`;
- in `MANUAL` mode notify and wait for user entry;
- in `AUTO` mode simulate the trade lifecycle automatically today; when live broker execution is enabled later, the same deterministic risk, freshness, and broker checks must gate every order;
- monitor positions until T1, T2, SL, expiry, manual intervention, or daily/global halt;
- stream trustworthy real-time state to the UI;
- preserve a full operational and trading audit trail.

## 4. Exact MVP scope

The MVP must be narrower than the long-term vision. The correct production MVP is:

- One broker: AngelOne only.
- Paper AUTO can run for both `NIFTY` and `BANKNIFTY` because it does not place live broker orders today.
- If and when live broker execution is introduced later, launch it on `NIFTY` first and keep `BANKNIFTY` in paper mode until operational stability is proven.
- One strategy family: intraday long `CE` or `PE` only.
- One live account per user.
- One open AUTO position per user at a time.
- One open signal per underlying at a time.
- Entry via marketable limit order with slippage cap. Do not use pure market orders for entry.
- Immediate protective stop placement after fill.
- Partial exit at T1, remaining runner to T2, trailing stop after T1.
- No overnight carry.
- No multi-leg spreads.
- No averaging down.
- No AI-driven parameter changes in production without admin approval.
- Web UI focused on trust, state clarity, and operator control rather than broad analytics.

MVP keeps the 47-signal market intelligence layer because it is core to signal quality. MVP does not attempt multi-broker, multi-account netting, backtesting UI, strategy marketplace, mobile app, or autonomous self-healing code changes.

## 5. Delivery philosophy

Build this in four phases:

- Phase 0: harden architecture and observability before real broker execution.
- Phase 1: manual intelligence platform with trusted real-time UI and full audit.
- Phase 2: guarded paper AUTO execution across supported underlyings.
- Phase 3: operational maturity and staged live-broker rollout.

Do not skip Phase 1. A trading UI that users do not trust will fail even if the model is good.

## 6. Target runtime architecture

### 6.1 Services

`api`

- FastAPI REST APIs.
- JWT auth and RBAC.
- WebSocket gateway.
- Read-only aggregation endpoints.
- Admin APIs for risk state, config, incidents, audits.
- Never places broker orders directly.

`market_worker`

- Owns APScheduler.
- Owns SmartStream subscription orchestration.
- Polls non-streaming sources like NSE and news APIs.
- Produces feature snapshots.
- Runs deterministic gate evaluation.
- Builds AI prompt context.
- Persists `signal_evaluation` and `ai_decision`.
- Emits `signal_created` or `signal_rejected` domain events.

`execution_worker`

- Subscribes to signal events.
- Evaluates trade mode, risk limits, and broker readiness.
- Creates execution intents.
- Places, modifies, cancels, and reconciles broker orders.
- Monitors open trades and exit rules.
- Emits `order_update`, `trade_update`, `risk_update`, and `halt_update` events.

`postgres`

- Durable store for users, config, snapshots, signals, decisions, orders, trades, audit logs, incidents, and outbox events.

`redis`

- Live market cache.
- UI fanout channel.
- distributed locks for scheduler and execution singleton tasks.
- stale-data markers and short-retention intraday price cache.

### 6.2 Bounded modules inside the backend codebase

Recommended package structure:

- `app/auth`
- `app/api`
- `app/market_data`
- `app/features`
- `app/signal_engine`
- `app/ai_decision`
- `app/execution`
- `app/risk`
- `app/notifications`
- `app/realtime`
- `app/admin`
- `app/persistence`
- `app/observability`

The important part is not folder names. The important part is that signal generation, execution, and WebSocket presentation stop sharing hidden in-memory state.

## 7. Core domain flow

### 7.1 Signal generation flow

1. Collect SmartStream ticks and polled external signals.
2. Build a `feature_snapshot` with freshness metadata for all 47 signals.
3. Run deterministic gates first.
4. If gates fail, persist rejection reason and stop.
5. If gates pass, ask Claude for `BUY_CALL`, `BUY_PUT`, or `NONE` using constrained JSON.
6. Validate AI output against hard rules:
   - allowed underlying;
   - valid expiry;
   - valid strike proximity;
   - min R:R;
   - entry, T1, T2, SL numeric sanity;
   - session timing;
   - no duplicate active signal.
7. Persist:
   - `signal_evaluation`;
   - `ai_decision`;
   - `signal`;
   - `audit_event`.
8. Publish a `signal_created` event.

### 7.2 AUTO execution flow

1. Receive `signal_created`.
2. Build `execution_intent`.
3. Run pre-trade risk policy:
   - auto armed;
   - broker connected;
   - market session open;
   - market data freshness within limit;
   - no global halt;
   - no per-user halt;
   - no daily loss breach;
   - no consecutive loss breach;
   - no open auto trade for user;
   - capital and quantity within config;
   - spread and slippage within cap;
   - signal still valid.
4. If any check fails, mark intent rejected and notify.
5. Create client order idempotency key.
6. Place entry order using marketable limit price.
7. Wait for broker acknowledgment.
8. Reconcile order book until filled, cancelled, or expired.
9. If filled, immediately place protective stop.
10. Begin trade lifecycle monitoring.

### 7.3 MANUAL execution flow

1. Receive `signal_created`.
2. Notify user with entry plan and validity window.
3. User confirms entry from UI or Telegram-linked action.
4. Same execution engine places order.
5. Same lifecycle engine manages exits.

Manual and auto must share the same execution pipeline after the decision point. Do not build a separate manual trade path.

## 8. Safe AUTO execution design

AUTO mode is the highest-risk area. It must be designed as a state machine, not as "if signal then place trade."

### 8.1 Hard rules

- AI never calls the broker adapter directly.
- AI does not determine quantity.
- Quantity is deterministic from capital, max risk per trade, and lot size.
- Every broker action has an idempotency key and stored raw request/response.
- Every execution state change is durable before the next action.
- Entry order must have timeout and cancel path.
- Protective stop must exist as soon as the entry is confirmed.
- If stop placement fails, the platform halts new entries and raises a critical alert.
- If broker or data feed becomes stale, new entries stop immediately.

### 8.2 Order policy

Use a marketable limit order for entry:

- buy `limit_price = min(ask + configured_buffer, max_allowed_slippage_price)`;
- reject if bid/ask spread exceeds configured percent;
- reject if live premium has drifted beyond allowed slippage from signal LTP;
- reject if recalculated R:R falls below threshold.

Entry order timeout:

- if not fully filled within `N` seconds, cancel;
- if partially filled, either complete within timeout or reduce stop size to actual fill;
- never assume the local state is correct without broker reconciliation.

Exit policy:

- T1 partial exit by sell order for configured partial quantity;
- after T1 fill, stop is modified for remaining quantity;
- T2 closes remainder;
- stop loss or trailing stop closes remainder immediately;
- hard session exit closes any remaining open position before the cutoff time.

### 8.3 Execution state machine

Recommended states:

- `SIGNAL_CREATED`
- `INTENT_PENDING`
- `INTENT_REJECTED`
- `ENTRY_SUBMITTING`
- `ENTRY_ACKED`
- `ENTRY_PARTIAL`
- `ENTRY_FILLED`
- `STOP_SUBMITTING`
- `STOP_ACTIVE`
- `MONITORING`
- `T1_TRIGGERED`
- `T1_FILLED`
- `STOP_TRAILED`
- `T2_TRIGGERED`
- `EXIT_PENDING`
- `EXIT_FILLED`
- `STOP_HIT`
- `CANCELLED`
- `EXPIRED`
- `RECONCILIATION_REQUIRED`
- `HALTED`

The frontend should render these states directly. Never flatten them into a vague `OPEN` badge.

## 9. Trade lifecycle design

Use `trade` as the business object and `order` as the broker object.

Recommended lifecycle:

1. `signal` created.
2. `execution_intent` created.
3. `entry_order` submitted.
4. `trade` created only after first fill, not at intent creation.
5. `position` becomes live.
6. protective `stop_order` active.
7. `price_monitor` evaluates T1, T2, SL, trailing SL, session cutoff.
8. partial exit creates `trade_exit` record.
9. final exit closes trade.
10. P&L, charges, slippage, latency, and outcome metrics computed.
11. loss analysis queued if stop or adverse exit.
12. end-of-day reconciliation confirms broker and platform match.

Recommended trade tables for lifecycle depth:

- `trades`
- `trade_exits`
- `orders`
- `order_events`
- `fills`
- `execution_intents`
- `position_snapshots`
- `trade_state_transitions`

## 10. Risk controls

Risk controls must be layered.

### 10.1 Pre-trade controls

- session timing window;
- freshness threshold for each required market signal;
- broker connectivity heartbeat;
- SmartStream heartbeat;
- allowed underlying and expiry filter;
- min R:R;
- max spread;
- max slippage;
- max capital deployed per trade;
- max risk per trade;
- cooldown after stop loss;
- max trades per day;
- max one open auto position per user;
- symbol-level lock if previous execution is unresolved.

### 10.2 In-trade controls

- protective stop on broker side;
- T1 partial profit locking;
- trailing stop after T1;
- max holding time;
- mandatory square-off cutoff;
- no averaging down;
- no re-entry for configured cooldown period after stop.

### 10.3 Daily and account controls

- daily realized loss limit;
- consecutive loss halt;
- optional daily profit lock;
- max daily broker rejects before halt;
- max cumulative slippage breach count before halt;
- manual kill switch per user;
- global kill switch;
- admin-only AUTO arm/disarm.

### 10.4 Operational controls

- if AI response invalid, no trade;
- if AI latency breaches threshold, signal may downgrade to manual or expire;
- if data sources disagree materially, no trade;
- if order reconciliation fails, halt new entries;
- if Redis unavailable, UI degrades but execution must continue only if broker and DB remain healthy;
- if Postgres unavailable, execution worker must stop placing new orders.

## 11. Database plan

Use PostgreSQL as the source of truth for every durable domain event. Use Redis only for speed.

### 11.1 Keep and extend the current schema

Retain and evolve:

- `users`
- `sessions`
- `signals`
- `trades`
- `signal_rules`
- `system_health_log`
- `errors`

Add the following first-class tables:

- `broker_accounts`
- `broker_sessions`
- `feature_snapshots`
- `signal_evaluations`
- `ai_decisions`
- `execution_intents`
- `orders`
- `order_events`
- `fills`
- `trade_exits`
- `trade_state_transitions`
- `risk_limits`
- `risk_halts`
- `kill_switch_events`
- `config_changes`
- `audit_events`
- `notification_log`
- `outbox_events`

### 11.2 Data modeling rules

- store timestamps in UTC only;
- add `created_at`, `updated_at`, and `created_by` where applicable;
- store raw broker payloads as JSONB;
- store raw AI prompt, response, model name, latency, and parse result;
- use explicit status enums or checked text values;
- add uniqueness constraints for idempotency keys and broker order ids;
- keep all mutable risk and execution configs versioned.

### 11.3 What not to store in Postgres early

Do not persist every market tick to Postgres in MVP. That is operationally expensive and not needed for the first production release.

Persist instead:

- 47-signal feature snapshots on schedule and at signal time;
- traded instrument price samples while a trade is open;
- order and trade events;
- UI audit events.

Use Redis for sub-second hot state.

## 12. API plan

Use `/api/v1` versioning from the start.

### 12.1 Auth

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

### 12.2 Market and signal read APIs

- `GET /api/v1/market/snapshot`
- `GET /api/v1/market/freshness`
- `GET /api/v1/market/news`
- `GET /api/v1/signals/active`
- `GET /api/v1/signals/history`
- `GET /api/v1/signals/{signal_id}`
- `GET /api/v1/feature-snapshots/latest`

### 12.3 Trade and execution APIs

- `GET /api/v1/trades/open`
- `GET /api/v1/trades/history`
- `GET /api/v1/trades/{trade_id}`
- `POST /api/v1/trades/{trade_id}/manual-exit`
- `POST /api/v1/signals/{signal_id}/confirm-entry`
- `GET /api/v1/execution/orders/{order_id}`
- `GET /api/v1/execution/status`

### 12.4 Risk and control APIs

- `GET /api/v1/risk/status`
- `GET /api/v1/risk/limits`
- `PUT /api/v1/risk/limits`
- `POST /api/v1/risk/kill-switch`
- `DELETE /api/v1/risk/kill-switch`
- `POST /api/v1/execution/auto/arm`
- `POST /api/v1/execution/auto/disarm`

### 12.5 Admin and audit APIs

- `GET /api/v1/admin/health`
- `GET /api/v1/admin/jobs`
- `GET /api/v1/admin/incidents`
- `GET /api/v1/admin/audit/events`
- `GET /api/v1/admin/audit/orders`
- `GET /api/v1/admin/config`
- `PUT /api/v1/admin/config`

Rules for mutating APIs:

- require RBAC;
- require audit actor;
- support idempotency key on dangerous actions;
- write audit event inside the same transaction.

## 13. WebSocket plan

The current in-memory connection manager must move to a Redis-backed event model.

### 13.1 Connection model

- one authenticated WebSocket per browser session;
- initial payload contains authoritative snapshot;
- subsequent events are deltas;
- heartbeat every 10 to 20 seconds;
- server includes connection status and data freshness state.

### 13.2 Event envelope

Every event should include:

- `event_id`
- `type`
- `ts`
- `seq`
- `entity_type`
- `entity_id`
- `source`
- `payload`

### 13.3 Event types

- `market.snapshot`
- `market.tick`
- `market.freshness`
- `signal.created`
- `signal.rejected`
- `decision.created`
- `execution.intent`
- `order.updated`
- `trade.updated`
- `risk.updated`
- `system.alert`
- `system.health`
- `audit.event`

### 13.4 UI trust rules

The UI must expose:

- market data age;
- broker connection age;
- last successful order sync time;
- whether displayed order state is broker-confirmed or locally pending;
- why AUTO is armed, blocked, or halted;
- AI rationale separate from deterministic gate reasons.

If data is stale, the UI should show a clear stale banner and mute confidence styling. Never show a green `LIVE` badge when the feed is stale.

## 14. Scheduler plan

APScheduler is acceptable for MVP, but only in `market_worker` and `execution_worker`, never in the API service.

### 14.1 Scheduler ownership

- exactly one scheduler leader for market jobs;
- exactly one scheduler leader for execution reconciliation jobs;
- use Redis lock or Postgres advisory lock to prevent duplicate leaders.

### 14.2 Market worker jobs

- pre-open health and broker readiness;
- feature snapshot refresh every 30 to 60 seconds;
- signal evaluation every 5 minutes within allowed trading window;
- stale-source watchdog every 15 seconds;
- news refresh every 60 seconds;
- end-of-day reconciliation and report jobs;
- weekly performance rollups.

### 14.3 Execution worker jobs

- open-order reconciliation every 1 second;
- open-position monitor every 1 second;
- stop order verification every 2 seconds;
- risk halt evaluation every 5 seconds;
- end-of-session forced square-off job;
- broker session renewal job.

Do not spawn one unmanaged background loop per trade. Replace that with a single monitored reconciliation loop that iterates open positions.

## 15. Frontend plan

The frontend should optimize for operator trust, not aesthetics alone.

### 15.1 Main views

- login and session state;
- live dashboard;
- active signal panel;
- open trades panel;
- order timeline panel;
- risk and halt center;
- audit and incidents view;
- admin control panel;
- system monitor.

### 15.2 Dashboard priorities

Top row should show:

- market status and freshness;
- AUTO state;
- broker state;
- daily risk state;
- open position summary.

Then show:

- current signal candidate and gate pass/fail reasons;
- AI rationale card;
- order/trade lifecycle timeline;
- unrealized and realized P&L;
- active alerts and incidents.

### 15.3 Zustand store design

Split the store by domain:

- `authStore`
- `marketStore`
- `signalStore`
- `tradeStore`
- `riskStore`
- `systemStore`

Do not keep everything in one generic market store once execution events become more complex.

### 15.4 Real-time clarity rules

- color only after authoritative state is confirmed;
- every price and trade card shows last update time;
- blocked auto trades must show explicit reason;
- manual action buttons must reflect current broker and risk state;
- timeline must show `Submitted`, `Acknowledged`, `Filled`, `Stop Active`, `T1`, `Trail`, `Closed`.

## 16. Admin and monitoring plan

Monitoring should be split into three layers:

### 16.1 Operator controls

- arm/disarm AUTO;
- trigger kill switch;
- view active halts;
- inspect broker health;
- inspect open orders and trades;
- inspect stale data sources;
- force reconcile a trade;
- view config versions and change history.

### 16.2 Alerts

Telegram alerts for:

- broker disconnect;
- SmartStream disconnect;
- stale market data;
- failed stop placement;
- order rejection;
- unresolved reconciliation;
- kill switch activation;
- daily risk halt;
- entry fill;
- T1, T2, SL;
- end-of-day unmatched broker/platform state.

### 16.3 Observability

Minimum:

- structured JSON logs;
- request ids and correlation ids;
- domain event ids;
- health endpoints;
- persistent incident records.

Before AUTO production:

- Prometheus metrics;
- Grafana dashboards;
- Loki or equivalent centralized logs;
- container health dashboards;
- Postgres and Redis health alerts.

Recommended metrics:

- market data freshness;
- AI latency and parse failures;
- signal count and reject reasons;
- order submit latency;
- broker reject rate;
- fill latency;
- slippage by trade;
- open reconciliation exceptions;
- WebSocket connected clients;
- API p95 latency.

## 17. Security and audit plan

This platform is not just another internal app. Treat it like a financial control surface.

- short-lived JWT access tokens and refresh flow;
- hashed passwords only;
- RBAC with `viewer`, `analyst`, `admin`, `super_admin`;
- admin-only AUTO arm/disarm unless explicit product policy says otherwise;
- secrets via environment or Docker secrets, not committed `.env`;
- audit every login, config change, mode switch, manual exit, kill switch, and broker action;
- mask sensitive broker tokens and secrets in logs;
- keep full raw broker payloads in audit tables, but encrypt or tightly restrict access if needed.

## 18. Phased roadmap

### Phase 0: architecture hardening

Goal:

- separate `api`, `market_worker`, and `execution_worker`;
- move live fanout to Redis-backed model;
- add order and audit tables;
- remove `--reload` and establish production Compose profiles;
- make observability first-class.

Exit criteria:

- no trading logic runs in the API process;
- all critical actions generate audit records;
- restart tests show no loss of durable state.

### Phase 1: trusted manual platform

Goal:

- collect live data and 47-signal snapshots reliably;
- generate signals and AI rationale;
- expose trustworthy real-time dashboard;
- allow manual confirmation and shared execution pipeline.

Exit criteria:

- users can follow signal to fill to exit from the UI;
- broker order lifecycle is visible and reconciled;
- manual mode stable for at least two trading weeks.

### Phase 2: guarded paper AUTO beta

Goal:

- enable paper AUTO for supported underlyings without broker placement;
- enforce all risk controls;
- run daily halts, kill switch, slippage checks, stop placement, and reconciliation;
- keep one-open-trade rule.

Exit criteria:

- zero unreconciled orders after soak tests;
- all stop placements verified;
- platform survives restart with open trades;
- at least two weeks of shadow or paper validation before live AUTO.

### Phase 3: operational maturity and live rollout

Goal:

- refine risk analytics and operator tooling;
- keep paper AUTO broad, but stage any future live broker rollout starting with NIFTY;
- improve incident tooling and reporting;
- add limited performance dashboards and deeper audit exports.

Exit criteria:

- operational incidents are diagnosable within minutes;
- no unresolved data-freshness blind spots;
- banknifty rollout approved only after NIFTY AUTO stability.

## 19. Sprint-by-sprint implementation order

Assume 10 one-week sprints or 5 two-week sprints with the same sequence.

### Sprint 1: repo and runtime separation

- split backend runtime commands into `api`, `market_worker`, `execution_worker`;
- create shared settings and app bootstrap;
- add production Compose services;
- introduce structured logging and correlation ids.

### Sprint 2: durable domain schema

- add `feature_snapshots`, `signal_evaluations`, `ai_decisions`;
- add `execution_intents`, `orders`, `order_events`, `fills`, `trade_exits`;
- add `risk_limits`, `risk_halts`, `audit_events`, `outbox_events`;
- write migrations and seed defaults.

### Sprint 3: market data and freshness layer

- move live market cache into Redis;
- normalize 47-signal collection and freshness model;
- expose freshness API and UI badges;
- add stale-source watchdogs.

### Sprint 4: deterministic gate engine

- refactor signal gates into explicit policy module;
- persist gate pass/fail with reasons;
- build signal candidate timeline in UI;
- validate that no AI call happens unless gates pass.

### Sprint 5: AI decision and manual workflow

- formalize Claude request and response auditing;
- persist model latency, prompt, response, and parse status;
- create manual signal confirmation path using execution intent;
- send Telegram and UI alerts from the same event model.

### Sprint 6: broker adapter and order state machine

- implement AngelOne order placement adapter;
- add idempotency keys and raw payload storage;
- implement order polling and reconciliation;
- surface broker-confirmed order states in UI.

### Sprint 7: position monitoring and exits

- implement protective stop placement;
- implement T1 partial exit, T2 exit, and trailing stop logic;
- replace per-trade async loops with central open-position monitor;
- compute realized and unrealized P&L from broker-confirmed fills.

### Sprint 8: AUTO risk engine

- implement AUTO arm/disarm;
- global and per-user kill switch;
- daily loss halt, consecutive loss halt, stale-feed halt, broker-health halt;
- one-open-trade rule;
- slippage and spread guards.

### Sprint 9: operator UX and observability

- complete risk center, audit views, and system monitor;
- add Redis-backed WebSocket fanout;
- add Prometheus and dashboards if not already added;
- run restart, disconnect, and reconciliation drills.

### Sprint 10: shadow mode, soak, and launch gate

- run shadow AUTO without live orders;
- compare intended vs executable trades;
- run production incident playbooks;
- approve paper AUTO broadly after launch checks, while keeping any future live broker AUTO rollout gated to NIFTY first.

## 20. Production readiness checklist

### Infrastructure

- separate Compose files for dev and prod;
- no hot reload in production;
- restart policies set;
- healthchecks on all services;
- database backups and restore test completed;
- clock sync verified on host;
- log rotation configured;
- HTTPS and reverse proxy configured.

### Data and execution safety

- all broker orders have idempotency keys;
- all order transitions durable;
- open trades survive service restart;
- broker reconciliation tested under partial fill and reject scenarios;
- protective stop verified after every fill;
- stale data blocks new entries.

### Security

- production secrets not stored in repo;
- JWT expiry and refresh implemented;
- RBAC enforced on admin and execution endpoints;
- audit trail enabled for all control actions;
- rate limiting and login lockouts enabled.

### Testing

- unit tests for gates, risk rules, sizing, and order state transitions;
- integration tests for broker adapter mock flows;
- failure-injection tests for Redis, Postgres, broker, and feed outages;
- replay tests from recorded market sessions;
- end-to-end manual mode test;
- end-to-end AUTO dry-run test.

### Operational readiness

- runbook for broker disconnect;
- runbook for SmartStream disconnect;
- runbook for stale data halt;
- runbook for unmatched order state;
- runbook for emergency kill switch;
- clear owner for market-open and market-close checks.

### Launch gate

- manual mode stable for at least two weeks;
- AUTO shadow mode stable for at least one week;
- no critical reconciliation bugs open;
- no stop-placement bug open;
- operator dashboards complete;
- user-facing state clarity signed off.

## 21. What to defer

Do not build these before the MVP is stable:

- multi-broker abstraction;
- mobile app;
- strategy marketplace;
- per-tick historical warehouse;
- autonomous self-healing code changes in production;
- model fine-tuning pipeline;
- advanced portfolio margining;
- social features or user communities;
- multi-leg options spreads.

## 22. Final recommendation

The right build order is:

1. harden runtime boundaries;
2. make state durable and auditable;
3. make the UI trustworthy;
4. make manual execution robust;
5. only then enable guarded AUTO for one narrow product slice.

If you do that, the platform can become production-grade without overbuilding. If you skip those steps and go straight from AI signal generation to broker execution inside one app process, you will accumulate invisible operational risk faster than trading edge.

