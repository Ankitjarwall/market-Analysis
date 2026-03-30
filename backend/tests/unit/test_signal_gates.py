"""Unit tests for signal gate checks."""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from bot.options_analyzer import check_timing_gates, check_put_gates, check_call_gates

IST = ZoneInfo("Asia/Kolkata")


def ist_time(hour, minute):
    return datetime.now(tz=IST).replace(hour=hour, minute=minute, second=0, microsecond=0)


# ── Timing gates ──────────────────────────────────────────────────────────────

def test_too_early_blocked():
    result = check_timing_gates(ist_time(9, 30))  # 9:30 — before 9:45
    assert not result.all_passed
    assert "timing_open" in result.failed


def test_valid_trading_time():
    result = check_timing_gates(ist_time(11, 0))
    assert result.all_passed


def test_too_late_blocked():
    result = check_timing_gates(ist_time(14, 45))  # after 2:30 PM
    assert not result.all_passed
    assert "timing_close" in result.failed


def test_border_9_45_passes():
    result = check_timing_gates(ist_time(9, 45))
    assert "timing_open" in result.passed


# ── PUT gates ─────────────────────────────────────────────────────────────────

def test_put_gate_passes_all():
    data = {
        "india_vix": 18,
        "nifty": 21900,
        "vwap": 22000,  # below VWAP ✓
        "fii_net": -2000,  # selling ✓
        "put_call_ratio": 0.80,  # < 0.95 ✓
    }
    result = check_put_gates(data)
    assert result.all_passed


def test_put_blocked_low_vix():
    data = {
        "india_vix": 12,  # below 15 ✗
        "nifty": 21900,
        "vwap": 22000,
        "fii_net": -2000,
        "put_call_ratio": 0.80,
    }
    result = check_put_gates(data)
    assert "vix" in result.failed


def test_put_blocked_nifty_above_vwap():
    data = {
        "india_vix": 18,
        "nifty": 22100,  # above VWAP ✗
        "vwap": 22000,
        "fii_net": -2000,
        "put_call_ratio": 0.80,
    }
    result = check_put_gates(data)
    assert "vwap" in result.failed


def test_put_blocked_fii_buying():
    data = {
        "india_vix": 18,
        "nifty": 21900,
        "vwap": 22000,
        "fii_net": 3000,  # buying ✗
        "put_call_ratio": 0.80,
    }
    result = check_put_gates(data)
    assert "fii" in result.failed


# ── CALL gates ────────────────────────────────────────────────────────────────

def test_call_gate_passes_all():
    data = {
        "india_vix": 14,  # < 28 ✓
        "nifty": 22100,
        "vwap": 22000,  # above VWAP ✓
        "fii_net": 3000,  # buying ✓
        "put_call_ratio": 0.85,  # > 0.70 ✓
    }
    result = check_call_gates(data)
    assert result.all_passed


def test_call_blocked_high_vix():
    data = {
        "india_vix": 30,  # > 28 ✗
        "nifty": 22100,
        "vwap": 22000,
        "fii_net": 3000,
        "put_call_ratio": 0.85,
    }
    result = check_call_gates(data)
    assert "vix" in result.failed
