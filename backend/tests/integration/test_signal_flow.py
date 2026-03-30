"""Integration tests for signal gate → position calculation flow."""

import pytest
from bot.options_analyzer import check_put_gates, check_call_gates, check_timing_gates
from bot.position_calculator import calculate_position
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def make_market_data(
    nifty=22000, vwap=22100, vix=18, fii_net=-2000, pcr=0.85
):
    return {
        "nifty": nifty, "vwap": vwap, "india_vix": vix,
        "fii_net": fii_net, "put_call_ratio": pcr,
    }


def test_full_put_signal_flow():
    """End-to-end: market data → gates pass → position calculated."""
    data = make_market_data(nifty=21900, vwap=22000, vix=18, fii_net=-3000, pcr=0.80)

    # Gate check
    gates = check_put_gates(data)
    assert gates.all_passed, f"Failed gates: {gates.failed}"

    # Timing check
    now = datetime.now(tz=IST).replace(hour=11, minute=0)
    timing = check_timing_gates(now)
    assert timing.all_passed

    # Position calculation
    signal = {
        "ltp": 180, "stop_loss": 130, "target1": 280, "target2": 380,
        "signal_type": "BUY_PUT",
    }
    position = calculate_position(capital=200_000, signal=signal)

    assert position["rr_ratio"] >= 2.0
    assert position["recommended"]["lots"] >= 1
    assert position["recommended"]["max_loss_pct"] <= 2.0
    assert position["minimum"]["lots"] == 1


def test_full_call_signal_flow():
    """End-to-end: call signal conditions → valid position."""
    data = make_market_data(nifty=22100, vwap=22000, vix=14, fii_net=3000, pcr=0.85)

    gates = check_call_gates(data)
    assert gates.all_passed, f"Failed gates: {gates.failed}"

    signal = {
        "ltp": 150, "stop_loss": 100, "target1": 250, "target2": 350,
        "signal_type": "BUY_CALL",
    }
    position = calculate_position(capital=200_000, signal=signal)
    assert position["rr_ratio"] == 2.0


def test_signal_blocked_when_gates_fail():
    """When gates fail, no signal should be generated."""
    # Low VIX for PUT — should fail
    data = make_market_data(vix=10, fii_net=-2000)
    gates = check_put_gates(data)
    assert not gates.all_passed


def test_signal_blocked_when_rr_fails():
    """Low R:R should block signal regardless of gates."""
    signal = {
        "ltp": 200, "stop_loss": 180, "target1": 220, "target2": 240,
        "signal_type": "BUY_CALL",
    }
    # R:R = (220-200)/(200-180) = 20/20 = 1.0 — too low
    with pytest.raises(ValueError, match="R:R"):
        calculate_position(capital=200_000, signal=signal)
