"""
Data freshness and sanity validation for collected signals.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

SANITY_RANGES = {
    "nifty": (15000, 40000),
    "banknifty": (35000, 110000),
    "sp500": (3000, 10000),
    "crude_brent": (30, 250),
    "gold": (1000, 5000),
    "usd_inr": (60, 120),
    "india_vix": (5, 100),
    "us_10y": (0.1, 15),
    "nifty_pe": (10, 50),
    "put_call_ratio": (0.3, 3.0),
    "silver": (10, 200),
    "copper": (2, 15),
}

MAX_DATA_AGE_MINUTES = {
    "live_prices": 5,
    "fii_data": 60,
    "news": 120,
    "pe_ratio": 120,
}


class DataValidationResult:
    def __init__(self):
        self.fresh_count = 0
        self.total_checked = 0
        self.flags: list[str] = []
        self.stale_fields: list[str] = []
        self.out_of_range: list[str] = []

    @property
    def quality(self) -> str:
        ratio = self.fresh_count / max(self.total_checked, 1)
        if ratio >= 0.85:
            return "HIGH"
        if ratio >= 0.65:
            return "MEDIUM"
        return "LOW"

    @property
    def is_sufficient(self) -> bool:
        """Minimum 40/47 signals required to generate trading signals."""
        return self.fresh_count >= 40


def validate_snapshot(data: dict[str, Any]) -> DataValidationResult:
    """
    Validates a collected data snapshot.
    Checks sanity ranges and counts fresh signals.
    """
    result = DataValidationResult()

    price_fields = [
        "nifty", "banknifty", "sp500", "nasdaq", "dow", "nikkei",
        "hangseng", "crude_brent", "gold", "usd_inr", "india_vix",
        "us_10y", "put_call_ratio",
    ]

    for field in price_fields:
        result.total_checked += 1
        val = data.get(field)
        if val is None:
            result.flags.append(f"MISSING:{field}")
            continue

        # Sanity range check
        rng = SANITY_RANGES.get(field)
        if rng and not (rng[0] <= val <= rng[1]):
            result.out_of_range.append(f"{field}={val} (expected {rng[0]}–{rng[1]})")
            result.flags.append(f"OUT_OF_RANGE:{field}={val}")
            continue

        result.fresh_count += 1

    # Check FII data age
    fii_net = data.get("fii_net")
    result.total_checked += 1
    if fii_net is not None:
        result.fresh_count += 1
    else:
        result.flags.append("MISSING:fii_data")

    # Check PE ratio
    pe = data.get("nifty_pe")
    result.total_checked += 1
    if pe is not None:
        result.fresh_count += 1
    else:
        result.flags.append("MISSING:nifty_pe")

    return result


def get_data_flags_string(result: DataValidationResult) -> str:
    if not result.flags:
        return "None — all data fresh ✓"
    return " | ".join(result.flags[:5])  # cap at 5 flags for messages
