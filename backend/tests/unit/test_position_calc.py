"""Unit tests for position calculator."""

import pytest
from bot.position_calculator import calculate_position, estimate_charges, get_lot_size


@pytest.fixture
def valid_call_signal():
    return {
        "ltp": 200.0,
        "stop_loss": 150.0,
        "target1": 300.0,
        "target2": 400.0,
        "signal_type": "BUY_CALL",
    }


@pytest.fixture
def valid_put_signal():
    return {
        "ltp": 200.0,
        "stop_loss": 150.0,
        "target1": 300.0,
        "target2": 400.0,
        "signal_type": "BUY_PUT",
    }


@pytest.fixture
def low_rr_signal():
    return {
        "ltp": 200.0,
        "stop_loss": 150.0,
        "target1": 240.0,  # R:R = 40/50 = 0.8 — too low
        "target2": 280.0,
        "signal_type": "BUY_CALL",
    }


def test_minimum_is_always_1_lot(valid_call_signal):
    result = calculate_position(capital=200_000, signal=valid_call_signal)
    assert result["minimum"]["lots"] == 1


def test_rr_ratio_calculated_correctly(valid_call_signal):
    # risk = 200 - 150 = 50, reward_t1 = 300 - 200 = 100, rr = 100/50 = 2.0
    result = calculate_position(capital=200_000, signal=valid_call_signal)
    assert result["rr_ratio"] == 2.0


def test_signal_blocked_when_rr_below_2(low_rr_signal):
    with pytest.raises(ValueError, match="R:R"):
        calculate_position(capital=200_000, signal=low_rr_signal)


def test_max_loss_within_2pct(valid_call_signal):
    result = calculate_position(capital=200_000, signal=valid_call_signal)
    assert result["recommended"]["max_loss_pct"] <= 2.0


def test_capital_deployment_within_20pct(valid_call_signal):
    result = calculate_position(capital=200_000, signal=valid_call_signal)
    assert result["recommended"]["capital_deployed_pct"] <= 20.0


def test_partial_exit_plan_sums_to_total_lots(valid_call_signal):
    result = calculate_position(capital=200_000, signal=valid_call_signal)
    plan = result["partial_exit_plan"]
    rec = result["recommended"]
    assert plan["exit_at_t1_lots"] + plan["hold_to_t2_lots"] == rec["lots"]


def test_t1_lots_is_roughly_75pct(valid_call_signal):
    result = calculate_position(capital=200_000, signal=valid_call_signal)
    rec_lots = result["recommended"]["lots"]
    t1_lots = result["partial_exit_plan"]["exit_at_t1_lots"]
    if rec_lots > 1:
        assert t1_lots >= int(rec_lots * 0.70)


def test_minimum_lot_size_nifty():
    assert get_lot_size("NIFTY50") == 25
    assert get_lot_size("BANKNIFTY") == 15


def test_charges_are_positive(valid_call_signal):
    charges = estimate_charges(lots=1, premium=200.0, lot_size=25)
    assert charges > 0


def test_zero_risk_raises_error():
    signal = {"ltp": 200.0, "stop_loss": 200.0, "target1": 300.0, "target2": 400.0, "signal_type": "BUY_CALL"}
    with pytest.raises(ValueError, match="zero"):
        calculate_position(capital=200_000, signal=signal)


def test_warning_when_1_lot_exceeds_2pct():
    # Very small capital — even 1 lot exceeds risk
    signal = {"ltp": 500.0, "stop_loss": 400.0, "target1": 700.0, "target2": 900.0, "signal_type": "BUY_CALL"}
    result = calculate_position(capital=10_000, signal=signal)
    assert any("2%" in w for w in result["warnings"])
