"""Per-user AUTO trading settings helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from config import settings

AUTO_SETTINGS_LIMITS: dict[str, dict[str, Any]] = {
    "enable_nifty_auto": {"type": bool},
    "enable_banknifty_auto": {"type": bool},
    "entry_start_minutes_after_open": {"type": int, "min": 0, "max": 180},
    "entry_stop_minutes_before_close": {"type": int, "min": 0, "max": 180},
    "cooldown_after_sl_minutes": {"type": int, "min": 0, "max": 240},
    "max_daily_entries": {"type": int, "min": 1, "max": 20},
    "max_daily_losses": {"type": int, "min": 1, "max": 10},
    "daily_profit_target": {"type": float, "min": 1000.0, "max": 1000000.0},
    "max_risk_pct": {"type": float, "min": 0.1, "max": 10.0},
    "max_deploy_pct": {"type": float, "min": 1.0, "max": 100.0},
    "max_slippage_pct": {"type": float, "min": 0.1, "max": 20.0},
    "min_rr_ratio": {"type": float, "min": 1.0, "max": 10.0},
    "min_confidence": {"type": int, "min": 0, "max": 100},
    "min_fresh_signals": {"type": int, "min": 1, "max": 47},
    "min_fii_consecutive_days": {"type": int, "min": 1, "max": 10},
    "nifty_put_min_vix": {"type": float, "min": 5.0, "max": 50.0},
    "nifty_call_max_vix": {"type": float, "min": 5.0, "max": 50.0},
    "nifty_put_pcr_max": {"type": float, "min": 0.1, "max": 3.0},
    "nifty_call_pcr_min": {"type": float, "min": 0.1, "max": 3.0},
    "banknifty_put_min_vix": {"type": float, "min": 5.0, "max": 50.0},
    "banknifty_call_max_vix": {"type": float, "min": 5.0, "max": 50.0},
    "banknifty_put_pcr_max": {"type": float, "min": 0.1, "max": 3.0},
    "banknifty_call_pcr_min": {"type": float, "min": 0.1, "max": 3.0},
}

DEFAULT_AUTO_SETTINGS: dict[str, Any] = {
    "enable_nifty_auto": True,
    "enable_banknifty_auto": True,
    "entry_start_minutes_after_open": 30,
    "entry_stop_minutes_before_close": 60,
    "cooldown_after_sl_minutes": settings.signal_cooldown_after_sl,
    "max_daily_entries": settings.max_daily_signals,
    "max_daily_losses": 3,
    "daily_profit_target": 50000.0,
    "max_risk_pct": settings.max_risk_pct,
    "max_deploy_pct": settings.max_deploy_pct,
    "max_slippage_pct": 3.0,
    "min_rr_ratio": settings.min_rr_ratio,
    "min_confidence": settings.min_confidence,
    "min_fresh_signals": settings.min_fresh_signals,
    "min_fii_consecutive_days": settings.min_fii_consecutive_days,
    "nifty_put_min_vix": settings.min_vix_for_put,
    "nifty_call_max_vix": 28.0,
    "nifty_put_pcr_max": 1.30,
    "nifty_call_pcr_min": 0.50,
    "banknifty_put_min_vix": 17.0,
    "banknifty_call_max_vix": 35.0,
    "banknifty_put_pcr_max": 1.30,
    "banknifty_call_pcr_min": 0.50,
}


def get_default_auto_settings() -> dict[str, Any]:
    return deepcopy(DEFAULT_AUTO_SETTINGS)


def _coerce_value(key: str, value: Any) -> Any:
    rules = AUTO_SETTINGS_LIMITS[key]
    expected = rules["type"]

    if expected is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off"}:
                return False
        raise ValueError(f"{key} must be a boolean")

    try:
        cast_value = int(value) if expected is int else float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a valid {expected.__name__}") from exc

    min_value = rules.get("min")
    max_value = rules.get("max")
    if min_value is not None and cast_value < min_value:
        raise ValueError(f"{key} must be >= {min_value}")
    if max_value is not None and cast_value > max_value:
        raise ValueError(f"{key} must be <= {max_value}")
    return cast_value


def validate_auto_settings_patch(patch: dict[str, Any] | None) -> dict[str, Any]:
    if patch is None:
        return {}
    if not isinstance(patch, dict):
        raise ValueError('settings must be an object')

    unknown = sorted(set(patch.keys()) - set(AUTO_SETTINGS_LIMITS.keys()))
    if unknown:
        raise ValueError(f"Unknown settings: {', '.join(unknown)}")

    return {key: _coerce_value(key, value) for key, value in patch.items()}


def build_effective_auto_settings(raw_overrides: dict[str, Any] | None) -> dict[str, Any]:
    effective = get_default_auto_settings()
    if raw_overrides:
        effective.update(validate_auto_settings_patch(raw_overrides))
    return effective


def diff_auto_settings_from_defaults(effective: dict[str, Any]) -> dict[str, Any]:
    defaults = get_default_auto_settings()
    return {key: effective[key] for key in defaults if effective.get(key) != defaults[key]}


def get_user_auto_settings(user: Any) -> dict[str, Any]:
    raw = getattr(user, 'auto_settings', None) if user is not None else None
    return build_effective_auto_settings(raw)