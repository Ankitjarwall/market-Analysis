"""
Position sizing calculator.
Always shows MINIMUM (1 lot) and RECOMMENDED (max within configured risk and capital limits).
R:R minimum is enforced and signals below it are blocked.
"""

from typing import Any


LOT_SIZES = {
    "NIFTY50": 25,
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "NIFTYMIDCAP": 50,
}


def get_lot_size(underlying: str) -> int:
    return LOT_SIZES.get(underlying.upper(), 25)


def calculate_position(
    capital: float,
    signal: dict,
    underlying: str = "NIFTY50",
    *,
    max_risk_pct: float = 2.0,
    max_deploy_pct: float = 20.0,
    min_rr_ratio: float = 2.0,
) -> dict[str, Any]:
    """
    Returns minimum AND recommended position sizes.
    MINIMUM = 1 lot always.
    RECOMMENDED = max within configured risk rule and deployment rule.
    Raises ValueError if R:R is below the configured minimum.
    """
    lot_size = get_lot_size(underlying)
    ltp = signal["ltp"]
    sl = signal["stop_loss"]
    t1 = signal["target1"]
    t2 = signal["target2"]

    risk_per_unit = abs(ltp - sl)
    reward_t1 = abs(t1 - ltp)
    reward_t2 = abs(t2 - ltp)

    if risk_per_unit == 0:
        raise ValueError("Risk per unit is zero - invalid stop loss")

    rr = reward_t1 / risk_per_unit
    if rr < min_rr_ratio:
        raise ValueError(f"R:R {rr:.2f} below minimum {min_rr_ratio:.2f} - signal blocked")

    risk_per_lot = risk_per_unit * lot_size
    premium_per_lot = ltp * lot_size

    minimum = {
        "lots": 1,
        "premium": round(premium_per_lot, 2),
        "max_loss": round(risk_per_lot, 2),
        "max_loss_pct": round((risk_per_lot / capital) * 100, 2),
        "capital_deployed_pct": round((premium_per_lot / capital) * 100, 2),
        "profit_t1": round(reward_t1 * lot_size, 2),
        "profit_t2": round(reward_t2 * lot_size, 2),
    }

    max_loss_allowed = capital * (max_risk_pct / 100)
    max_capital_allowed = capital * (max_deploy_pct / 100)
    lots_by_risk = int(max_loss_allowed / risk_per_lot) if risk_per_lot > 0 else 1
    lots_by_capital = int(max_capital_allowed / premium_per_lot) if premium_per_lot > 0 else 1
    dynamic_cap = min(50, max(10, int(capital / 100_000)))
    rec_lots = max(1, min(lots_by_risk, lots_by_capital, dynamic_cap))

    recommended = {
        "lots": rec_lots,
        "premium": round(rec_lots * premium_per_lot, 2),
        "max_loss": round(rec_lots * risk_per_lot, 2),
        "max_loss_pct": round((rec_lots * risk_per_lot / capital) * 100, 2),
        "profit_t1": round(rec_lots * reward_t1 * lot_size, 2),
        "profit_t2": round(rec_lots * reward_t2 * lot_size, 2),
        "capital_deployed_pct": round((rec_lots * premium_per_lot / capital) * 100, 2),
    }

    t1_lots = max(1, int(rec_lots * 0.75))
    t2_lots = rec_lots - t1_lots
    trailing_sl = ltp + (reward_t1 * 0.70)

    partial_plan = {
        "exit_at_t1_lots": t1_lots,
        "hold_to_t2_lots": t2_lots,
        "profit_if_t1_exit": round(t1_lots * reward_t1 * lot_size, 2),
        "profit_if_t2_all": round(
            t1_lots * reward_t1 * lot_size + t2_lots * reward_t2 * lot_size, 2
        ),
        "trailing_sl_after_t1": round(trailing_sl, 0),
    }

    charges = estimate_charges(rec_lots, ltp, lot_size)
    warnings = _build_warnings(capital, minimum, recommended, max_risk_pct, max_deploy_pct)

    return {
        "minimum": minimum,
        "recommended": recommended,
        "partial_exit_plan": partial_plan,
        "rr_ratio": round(rr, 2),
        "charges_estimate": charges,
        "warnings": warnings,
    }


def estimate_charges(lots: int, premium: float, lot_size: int) -> float:
    """
    Rough STT + brokerage + exchange fee estimate.
    For options buy: STT only on sell side = 0.1% of sell turnover.
    Plus brokerage ~ Rs40/order, exchange fee ~ 0.053%.
    """
    turnover = premium * lots * lot_size
    stt = round(turnover * 0.001, 2)
    exchange_fee = round(turnover * 0.00053, 2)
    brokerage = 40.0
    gst = round((brokerage + exchange_fee) * 0.18, 2)
    return round(stt + exchange_fee + brokerage + gst, 2)


def _build_warnings(
    capital: float,
    minimum: dict,
    recommended: dict,
    max_risk_pct: float,
    max_deploy_pct: float,
) -> list[str]:
    warnings = []
    if minimum["max_loss_pct"] > max_risk_pct:
        warnings.append(
            f"Even 1 lot exceeds {max_risk_pct:.1f}% risk ({minimum['max_loss_pct']:.1f}% of capital)"
        )
    if minimum["capital_deployed_pct"] > max_deploy_pct:
        warnings.append(
            f"Even 1 lot deploys {minimum['capital_deployed_pct']:.1f}% of capital, above {max_deploy_pct:.1f}%"
        )
    if recommended["capital_deployed_pct"] > max_deploy_pct:
        warnings.append(
            f"Capital deployment {recommended['capital_deployed_pct']:.1f}% exceeds {max_deploy_pct:.1f}% guideline"
        )
    return warnings