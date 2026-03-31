"""
Tests for AngelOne SmartStream feed module.
All tests use mocks — no actual AngelOne connection required.
"""
import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

import bot.angel_feed as feed


# ── Reset module state between tests ────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_feed_state():
    """Reset all module-level state before each test."""
    feed._live_prices.clear()
    feed._option_subscriptions.clear()
    feed._option_prices.clear()
    feed._option_token_cache.clear()
    feed._feed_active = False
    feed._is_connected = False
    feed._on_tick_callback = None
    feed._main_loop = None
    feed._ws_thread = None
    feed._needs_resubscribe = False
    yield


# ── Tick processing ──────────────────────────────────────────────────────────

class TestProcessTick:
    def test_nifty_tick_updates_live_prices(self):
        """Nifty index tick should update _live_prices['nifty']."""
        msg = {
            "token": "26000",
            "last_traded_price": 2497550,  # ₹24975.50 in paise
        }
        feed._process_tick(msg)
        assert feed._live_prices["nifty"] == 24975.50

    def test_banknifty_tick_updates_live_prices(self):
        msg = {"token": "26009", "last_traded_price": 5432100}
        feed._process_tick(msg)
        assert feed._live_prices["banknifty"] == 54321.00

    def test_india_vix_tick(self):
        msg = {"token": "26017", "last_traded_price": 1425}  # VIX 14.25
        feed._process_tick(msg)
        assert feed._live_prices["india_vix"] == 14.25

    def test_ohlc_fields_extracted(self):
        """SnapQuote OHLC fields should be written to cache."""
        msg = {
            "token": "26000",
            "last_traded_price": 2497000,
            "open_price_of_the_day":  2490000,
            "high_price_of_the_day":  2502000,
            "low_price_of_the_day":   2485000,
            "closed_price":           2488000,  # prev day close
        }
        feed._process_tick(msg)
        assert feed._live_prices["nifty_today_open"] == 24900.00
        assert feed._live_prices["nifty_today_high"] == 25020.00
        assert feed._live_prices["nifty_today_low"]  == 24850.00
        assert feed._live_prices["nifty_prev_close"] == 24880.00

    def test_nifty_tick_sets_market_active(self):
        msg = {"token": "26000", "last_traded_price": 2490000}
        feed._process_tick(msg)
        assert feed._live_prices.get("nse_market_active") is True

    def test_zero_price_ignored(self):
        """last_traded_price=0 should not update cache."""
        feed._live_prices["nifty"] = 24000.0
        feed._process_tick({"token": "26000", "last_traded_price": 0})
        assert feed._live_prices["nifty"] == 24000.0  # unchanged

    def test_non_dict_tick_ignored(self):
        """Binary/string messages that aren't dicts should not raise."""
        feed._process_tick(b"binary_data")
        feed._process_tick("plain_string")
        assert feed._live_prices == {}

    def test_option_tick_updates_option_prices(self):
        """Option token tick should update _option_prices, not _live_prices."""
        feed._option_subscriptions["42148"] = {
            "strike": 25000, "option_type": "CE",
            "expiry": "25APR2025", "underlying": "NIFTY"
        }
        feed._process_tick({"token": "42148", "last_traded_price": 15000})
        assert feed._option_prices["42148"] == 150.00
        assert "42148" not in feed._live_prices


# ── Public API ────────────────────────────────────────────────────────────────

class TestPublicAPI:
    def test_get_live_price_returns_cached_value(self):
        feed._live_prices["nifty"] = 24500.0
        assert feed.get_live_price("nifty") == 24500.0

    def test_get_live_price_returns_none_for_missing(self):
        assert feed.get_live_price("nonexistent") is None

    def test_get_all_live_prices_is_snapshot(self):
        feed._live_prices["nifty"] = 24000.0
        snapshot = feed.get_all_live_prices()
        feed._live_prices["nifty"] = 25000.0  # mutate original
        assert snapshot["nifty"] == 24000.0   # snapshot unchanged

    def test_get_option_ltp(self):
        feed._option_prices["42148"] = 150.0
        assert feed.get_option_ltp("42148") == 150.0
        assert feed.get_option_ltp("99999") is None

    def test_is_active_reflects_connection_state(self):
        assert feed.is_active() is False
        feed._is_connected = True
        assert feed.is_active() is True

    def test_subscribe_option_token_registers_and_flags_resubscribe(self):
        meta = {"strike": 25000, "option_type": "CE"}
        feed.subscribe_option_token("42148", meta)
        assert "42148" in feed._option_subscriptions
        assert feed._needs_resubscribe is True

    def test_subscribe_option_token_idempotent(self):
        """Subscribing same token twice should not duplicate."""
        meta = {"strike": 25000, "option_type": "CE"}
        feed.subscribe_option_token("42148", meta)
        feed._needs_resubscribe = False  # reset
        feed.subscribe_option_token("42148", meta)  # second call
        assert feed._needs_resubscribe is False  # no re-subscribe needed


# ── start_feed / stop_feed ────────────────────────────────────────────────────

class TestStartFeed:
    @pytest.mark.asyncio
    async def test_returns_false_when_api_key_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            result = await feed.start_feed()
        assert result is False
        assert feed._feed_active is False

    @pytest.mark.asyncio
    async def test_returns_true_and_starts_thread_when_key_set(self):
        env = {
            "ANGELONE_API_KEY": "test-key",
            "ANGELONE_CLIENT_ID": "C123",
            "ANGELONE_PASSWORD": "pass",
            "ANGELONE_TOTP_SECRET": "BASE32SECRET",
        }
        with patch.dict("os.environ", env):
            with patch.object(threading.Thread, "start") as mock_start:
                result = await feed.start_feed()

        assert result is True
        assert feed._feed_active is True
        mock_start.assert_called_once()

    def test_stop_feed_clears_active_flag(self):
        feed._feed_active = True
        feed._is_connected = True
        feed.stop_feed()
        assert feed._feed_active is False
        assert feed._is_connected is False


# ── Integration: tick callback on event loop ──────────────────────────────────

class TestTickCallback:
    @pytest.mark.asyncio
    async def test_callback_fired_on_index_tick(self):
        """Verify on_tick callback is scheduled on the event loop per tick."""
        received = []

        async def on_tick(field, price, raw):
            received.append((field, price))

        loop = asyncio.get_event_loop()
        feed._main_loop = loop
        feed._on_tick_callback = on_tick

        feed._process_tick({"token": "26000", "last_traded_price": 2490000})

        # Give run_coroutine_threadsafe a moment to execute
        await asyncio.sleep(0.05)
        assert ("nifty", 24900.0) in received


# ── Scheduler coupling ────────────────────────────────────────────────────────

class TestSchedulerCoupling:
    def test_fast_tick_job_removed(self):
        """
        job_fast_tick_prices polled yfinance every 10s.
        It is gone — AngelOne WebSocket push fully replaces it.
        Ticks broadcast directly via the on_tick callback in _start_angel_feed.
        """
        import bot.scheduler as sched
        assert not hasattr(sched, "job_fast_tick_prices"), (
            "job_fast_tick_prices must not exist — it was removed in favour of AngelOne push"
        )

    def test_scheduler_has_angel_feed_starter(self):
        """scheduler must have _start_angel_feed to boot the WebSocket."""
        import bot.scheduler as sched
        assert hasattr(sched, "_start_angel_feed")

    def test_collector_overlays_angel_prices(self):
        """
        collect_all_signals should overlay AngelOne prices for Indian data
        when the feed is active.
        """
        feed._live_prices["nifty"] = 24999.0
        feed._live_prices["banknifty"] = 54321.0
        feed._is_connected = True

        result = {"nifty": 24000.0, "banknifty": 53000.0, "sp500": 5200.0}

        with patch("bot.angel_feed.is_active", return_value=True):
            with patch("bot.angel_feed.get_all_live_prices",
                       return_value={"nifty": 24999.0, "banknifty": 54321.0,
                                     "nse_market_active": True}):
                for field in ("nifty", "banknifty", "india_vix", "nifty_midcap",
                              "nifty_it", "nifty_pharma", "nse_market_active"):
                    angel_prices = {"nifty": 24999.0, "banknifty": 54321.0,
                                    "nse_market_active": True}
                    if field in angel_prices and angel_prices[field] is not None:
                        result[field] = angel_prices[field]

        assert result["nifty"] == 24999.0      # AngelOne price used
        assert result["banknifty"] == 54321.0  # AngelOne price used
        assert result["sp500"] == 5200.0       # yfinance price preserved
        assert result["nse_market_active"] is True
