"""
AngelOne SmartStream WebSocket feed — real-time Indian market data via push.

Replaces yfinance polling (^NSEI, ^NSEBANK, ^INDIAVIX) with AngelOne
SmartStream v2 which delivers continuous tick data without polling.

Architecture:
  A daemon thread runs SmartWebSocketV2.connect() (blocking).
  On each tick, _live_prices dict is updated atomically.
  asyncio.run_coroutine_threadsafe() fires an optional async callback
  on the main event loop so scheduler can re-broadcast immediately.

Required .env keys:
  ANGELONE_API_KEY      — from smartapi.angelbroking.com developer portal
  ANGELONE_CLIENT_ID    — your Angel Broking login ID
  ANGELONE_PASSWORD     — your Angel Broking password
  ANGELONE_TOTP_SECRET  — base-32 TOTP secret (shown once in Angel app)

NSE Instrument tokens (stable for index instruments):
  26000 = Nifty 50
  26009 = Bank Nifty
  26017 = India VIX
  26074 = Nifty Midcap 100
  26021 = Nifty IT
  26035 = Nifty Pharma
"""

import asyncio
import logging
import os
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# NSE index token → field name mapping
NSE_INDEX_TOKENS: dict[str, str] = {
    "26000": "nifty",
    "26009": "banknifty",
    "26017": "india_vix",
    "26074": "nifty_midcap",
    "26021": "nifty_it",
    "26035": "nifty_pharma",
}

# Module-level price cache — written by WebSocket thread, read by scheduler/collector
_live_prices: dict[str, Any] = {}
_is_connected: bool = False
_feed_active: bool = False
_ws_thread: Optional[threading.Thread] = None
_main_loop: Optional[asyncio.AbstractEventLoop] = None
_on_tick_callback: Optional[Callable] = None
_sws_ref = None  # reference to active SmartWebSocketV2 for re-subscribe

# Option token subscriptions — token → {strike, option_type, expiry, underlying}
_option_subscriptions: dict[str, dict] = {}
_option_prices: dict[str, float] = {}  # token → LTP (₹)
_opt_lock = threading.Lock()
_needs_resubscribe: bool = False

# Cache for: NFO symbol → token (avoid repeated REST calls)
_option_token_cache: dict[str, str] = {}

# Per-token price-change callbacks — registered by trade_handler for event-driven monitoring.
# _option_price_callbacks[token] = list of async callables(token, ltp)
_option_price_callbacks: dict[str, list] = {}
_cb_lock = threading.Lock()


def register_option_price_callback(token: str, callback: Callable) -> None:
    """
    Register an async callback to be fired on every LTP tick for *token*.
    callback signature: async def cb(token: str, ltp: float) -> None
    Safe to call from any thread.
    """
    with _cb_lock:
        _option_price_callbacks.setdefault(token, [])
        if callback not in _option_price_callbacks[token]:
            _option_price_callbacks[token].append(callback)
            logger.debug(f"Price callback registered for option token {token}")


def unregister_option_price_callback(token: str, callback: Callable) -> None:
    """Remove a previously registered price callback for *token*."""
    with _cb_lock:
        cbs = _option_price_callbacks.get(token, [])
        if callback in cbs:
            cbs.remove(callback)
            logger.debug(f"Price callback unregistered for option token {token}")


def is_active() -> bool:
    """Return True if the AngelOne feed is currently connected."""
    return _is_connected


def get_live_price(field: str) -> Optional[float]:
    """Return latest cached price for a field name like 'nifty', 'banknifty'."""
    return _live_prices.get(field)


def get_all_live_prices() -> dict:
    """Return a snapshot of all cached live prices."""
    return dict(_live_prices)


def get_option_ltp(token: str) -> Optional[float]:
    """Return the latest LTP for a subscribed option token."""
    return _option_prices.get(token)


def subscribe_option_token(token: str, metadata: dict):
    """
    Register an NFO option token for live WebSocket subscription.
    metadata = {"strike": 24500, "option_type": "CE", "expiry": "25APR2025", "underlying": "NIFTY"}
    Safe to call from any thread.
    """
    global _needs_resubscribe
    with _opt_lock:
        if token not in _option_subscriptions:
            _option_subscriptions[token] = metadata
            _needs_resubscribe = True
            logger.info(f"Option token registered: {token} ({metadata})")


async def lookup_and_subscribe_option(
    strike: int,
    option_type: str,
    expiry: str,
    underlying: str = "NIFTY",
) -> Optional[str]:
    """
    Look up the AngelOne NFO token for a specific option contract via REST.
    Returns the token string if found, else None.

    expiry format: "25APR2025" (as returned by AngelOne)
    option_type: "CE" or "PE"
    """
    symbol_key = f"{underlying}{expiry}{strike}{option_type}"
    if symbol_key in _option_token_cache:
        return _option_token_cache[symbol_key]

    api_key = os.environ.get("ANGELONE_API_KEY", "")
    client_code = os.environ.get("ANGELONE_CLIENT_ID", "")
    password = os.environ.get("ANGELONE_PASSWORD", "")
    totp_secret = os.environ.get("ANGELONE_TOTP_SECRET", "")
    if not all([api_key, client_code, password, totp_secret]):
        return None

    try:
        import pyotp
        from SmartApi import SmartConnect

        loop = asyncio.get_event_loop()

        def _search():
            totp = pyotp.TOTP(totp_secret).now()
            api = SmartConnect(api_key=api_key)
            session = api.generateSession(client_code, password, totp)
            if not session or not session.get("status"):
                return None
            result = api.searchScrip("NFO", symbol_key[:20])
            return result

        data = await loop.run_in_executor(None, _search)
        if data and data.get("status") and data.get("data"):
            for item in data["data"]:
                if (
                    str(item.get("tradingsymbol", "")).startswith(symbol_key[:15])
                    and item.get("exch_seg") == "NFO"
                ):
                    token = str(item["symboltoken"])
                    _option_token_cache[symbol_key] = token
                    subscribe_option_token(token, {
                        "strike": strike,
                        "option_type": option_type,
                        "expiry": expiry,
                        "underlying": underlying,
                    })
                    return token
    except Exception as exc:
        logger.debug(f"Option token lookup failed for {symbol_key}: {exc}")

    return None


async def start_feed(on_tick: Optional[Callable] = None) -> bool:
    """
    Authenticate with AngelOne and start the SmartStream WebSocket in a daemon thread.
    on_tick(field, price, raw_message) is called on the main asyncio event loop per tick.
    Returns True if started, False if credentials missing or already running.
    """
    global _feed_active, _ws_thread, _main_loop, _on_tick_callback

    api_key = os.environ.get("ANGELONE_API_KEY", "")
    if not api_key:
        logger.warning(
            "AngelOne SmartStream not started — ANGELONE_API_KEY not set. "
            "Set ANGELONE_API_KEY in .env to enable live Indian market prices."
        )
        return False

    # Guard against double-start (e.g. uvicorn hot-reload fires lifespan twice)
    if _feed_active and _ws_thread and _ws_thread.is_alive():
        logger.info("AngelOne feed already running — skipping duplicate start")
        return True

    _main_loop = asyncio.get_event_loop()
    _on_tick_callback = on_tick
    _feed_active = True

    _ws_thread = threading.Thread(
        target=_feed_loop,
        name="angelone-smartstream",
        daemon=True,
    )
    _ws_thread.start()
    logger.info("AngelOne SmartStream feed thread started")
    return True


def stop_feed():
    """Signal the feed thread to stop. The daemon thread will exit on disconnect."""
    global _feed_active, _is_connected
    _feed_active = False
    _is_connected = False
    logger.info("AngelOne feed stop requested")


def _feed_loop():
    """
    Outer reconnect loop running in daemon thread.
    Re-authenticates and reconnects on every disconnect.
    """
    backoff = 5
    while _feed_active:
        try:
            _connect_and_run()
            backoff = 5  # reset on clean exit
        except Exception as exc:
            logger.error(f"AngelOne feed error: {exc}", exc_info=True)
        if _feed_active:
            logger.info(f"AngelOne feed: reconnecting in {backoff}s...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)


def _connect_and_run():
    """
    Single connection lifetime: authenticate → connect → run until disconnect.
    Raises on auth failure so the outer loop can retry.
    """
    global _is_connected, _sws_ref

    try:
        import pyotp
        from SmartApi import SmartConnect
        from SmartApi.smartWebSocketV2 import SmartWebSocketV2
    except ImportError as exc:
        logger.error(
            f"smartapi-python not installed: {exc}. "
            "Run: pip install smartapi-python pyotp"
        )
        time.sleep(60)
        return

    api_key = os.environ.get("ANGELONE_API_KEY")
    client_code = os.environ.get("ANGELONE_CLIENT_ID")
    password = os.environ.get("ANGELONE_PASSWORD")
    totp_secret = os.environ.get("ANGELONE_TOTP_SECRET")

    if not all([api_key, client_code, password, totp_secret]):
        logger.warning("AngelOne credentials incomplete — feed not starting")
        time.sleep(60)
        return

    # Authenticate
    totp = pyotp.TOTP(totp_secret).now()
    api = SmartConnect(api_key=api_key)
    session = api.generateSession(client_code, password, totp)

    if not session or not session.get("status"):
        raise RuntimeError(f"AngelOne auth failed: {session}")

    jwt_token = session["data"]["jwtToken"]
    feed_token = session["data"]["feedToken"]
    logger.info(f"AngelOne authenticated (client: {client_code})")

    sws = SmartWebSocketV2(
        jwt_token, api_key, client_code, feed_token,
        max_retry_attempt=5,
        retry_delay=5,
    )
    _sws_ref = sws

    def on_open(wsapp):
        global _is_connected
        _is_connected = True
        logger.info("AngelOne SmartStream CONNECTED — subscribing instruments")
        _do_subscribe(sws)

    def on_data(wsapp, message):
        _process_tick(message)
        # Re-subscribe if new option tokens were registered
        global _needs_resubscribe
        if _needs_resubscribe:
            _needs_resubscribe = False
            _do_subscribe(sws)

    def on_error(*args):
        logger.error(f"AngelOne WS error: {args}")

    def on_close(wsapp):
        global _is_connected
        _is_connected = False
        logger.info("AngelOne WS closed")

    # v1.5.5 uses lowercase instance-attribute overrides, not On_open / On_message
    sws.on_open = on_open
    sws.on_data = on_data   # on_data receives parsed tick dicts
    sws.on_error = on_error
    sws.on_close = on_close
    sws.connect()  # blocks until SmartWebSocketV2 exhausts retries


def _do_subscribe(sws):
    """Build and send subscription for all index + option tokens."""
    token_list = [
        {"exchangeType": 1, "tokens": list(NSE_INDEX_TOKENS.keys())},  # NSE
    ]
    with _opt_lock:
        if _option_subscriptions:
            token_list.append({
                "exchangeType": 2,  # NFO
                "tokens": list(_option_subscriptions.keys()),
            })
    try:
        sws.subscribe("market_feed", 3, token_list)  # mode 3 = SnapQuote (OHLC + LTP)
        logger.info(
            f"Subscribed: {len(NSE_INDEX_TOKENS)} indices, "
            f"{len(_option_subscriptions)} options"
        )
    except Exception as exc:
        logger.error(f"AngelOne subscribe failed: {exc}")


def _process_tick(message: Any):
    """Parse SmartStream binary-decoded tick dict and update price caches."""
    global _live_prices
    try:
        if not isinstance(message, dict):
            return

        token = str(message.get("token", ""))
        raw_ltp = message.get("last_traded_price", 0)
        if not raw_ltp:
            return

        # SmartStream sends prices in paise (1/100 rupee)
        ltp = round(raw_ltp / 100.0, 2)

        # Index prices
        field = NSE_INDEX_TOKENS.get(token)
        if field:
            _live_prices[field] = ltp

            # OHLC + VWAP from SnapQuote (all values in paise)
            ohlc: dict[str, float] = {}
            for msg_key, cache_key in [
                ("open_price_of_the_day",  f"{field}_today_open"),
                ("high_price_of_the_day",  f"{field}_today_high"),
                ("low_price_of_the_day",   f"{field}_today_low"),
                ("closed_price",           f"{field}_prev_close"),
                # average_traded_price = intraday VWAP (AngelOne computes it server-side)
                ("average_traded_price",   f"{field}_vwap"),
            ]:
                raw = message.get(msg_key)
                if raw:
                    val = round(raw / 100.0, 2)
                    _live_prices[cache_key] = val
                    ohlc[msg_key] = val

            # Expose Nifty VWAP at top-level key "vwap" for options_analyzer
            if field == "nifty" and f"{field}_vwap" in _live_prices:
                _live_prices["vwap"] = _live_prices["nifty_vwap"]

            if field == "nifty":
                _live_prices["nse_market_active"] = True
            logger.debug(f"AngelOne tick: {field} ₹{ltp}")

            # Feed live 5-minute candle buffer for NIFTY / BANKNIFTY
            if field in ("nifty", "banknifty"):
                try:
                    from bot import intraday as _intraday
                    _intraday.update_live_candle(field.upper(), ltp, ohlc or None)
                except Exception as _ce:
                    logger.debug(f"update_live_candle error: {_ce}")

        # Option prices — update cache and fire per-token price callbacks
        elif token in _option_subscriptions:
            _option_prices[token] = ltp

            # Fire registered async price-change callbacks (event-driven trade monitoring)
            with _cb_lock:
                cbs = list(_option_price_callbacks.get(token, []))
            if cbs and _main_loop and not _main_loop.is_closed():
                for cb in cbs:
                    asyncio.run_coroutine_threadsafe(
                        _safe_option_callback(cb, token, ltp),
                        _main_loop,
                    )

        # Fire the global tick callback on main event loop (thread-safe)
        if _on_tick_callback and _main_loop and not _main_loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                _safe_tick_callback(field or token, ltp, message),
                _main_loop,
            )

    except Exception as exc:
        logger.debug(f"AngelOne tick parse error: {exc}")


async def _safe_tick_callback(field: str, price: float, message: dict):
    try:
        if _on_tick_callback:
            await _on_tick_callback(field, price, message)
    except Exception as exc:
        logger.debug(f"AngelOne tick callback error: {exc}")


async def _safe_option_callback(cb: Callable, token: str, ltp: float):
    """Safely invoke a single per-token price callback, swallowing exceptions."""
    try:
        await cb(token, ltp)
    except Exception as exc:
        logger.debug(f"Option price callback error (token={token}): {exc}")
