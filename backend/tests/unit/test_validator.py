"""Unit tests for data validator."""

import pytest
from bot.validator import validate_snapshot


def test_high_quality_snapshot():
    data = {
        "nifty": 22000,
        "banknifty": 47000,
        "sp500": 5500,
        "crude_brent": 80,
        "gold": 2300,
        "usd_inr": 83.5,
        "india_vix": 14,
        "us_10y": 4.5,
        "put_call_ratio": 0.85,
        "nifty_pe": 22,
        "fii_net": -1500,
        "silver": 30,
        "copper": 4.5,
    }
    result = validate_snapshot(data)
    assert result.quality in ("HIGH", "MEDIUM")
    assert result.fresh_count > 0


def test_low_quality_missing_data():
    result = validate_snapshot({})
    assert result.quality == "LOW"
    assert result.fresh_count == 0


def test_out_of_range_nifty():
    data = {"nifty": 100, "fii_net": -1000}  # nifty way out of range
    result = validate_snapshot(data)
    assert any("OUT_OF_RANGE:nifty" in f for f in result.flags)


def test_out_of_range_vix():
    data = {"india_vix": 200, "fii_net": None}  # VIX can't be 200
    result = validate_snapshot(data)
    assert any("OUT_OF_RANGE" in f or "MISSING" in f for f in result.flags)


def test_is_sufficient_threshold():
    # Minimal good data
    good_data = {
        "nifty": 22000, "banknifty": 47000, "sp500": 5500, "nasdaq": 18000,
        "dow": 40000, "nikkei": 38000, "hangseng": 17000, "ftse": 7900,
        "dax": 18000, "crude_brent": 80, "gold": 2300, "silver": 30,
        "usd_inr": 83, "india_vix": 14, "us_10y": 4.5, "put_call_ratio": 0.9,
        "fii_net": -1000, "nifty_pe": 22,
    }
    result = validate_snapshot(good_data)
    # With 18 good fields, should not be sufficient (need 40)
    assert not result.is_sufficient
