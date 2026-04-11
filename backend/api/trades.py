"""Trade journal and AUTO settings API endpoints."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth.middleware import RequireAnalyst, get_current_user
from auth.schemas import ChangeCapitalRequest, ChangeTradeModeRequest
from config import settings
from db.connection import get_db
from db.models import Trade, User
from trading.auto_settings import (
    diff_auto_settings_from_defaults,
    get_default_auto_settings,
    get_user_auto_settings,
    validate_auto_settings_patch,
)

_IST = ZoneInfo("Asia/Kolkata")

router = APIRouter(prefix="/api/trades", tags=["trades"])


class ExitTradeRequest(BaseModel):
    exit_premium: float
    exit_reason: str


class UpdateAutoSettingsRequest(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)


def _trade_dict(trade: Trade) -> dict:
    sig = trade.signal
    return {
        "id": trade.id,
        "signal_id": trade.signal_id,
        "trade_mode": trade.trade_mode,
        "status": trade.status,
        "lots": trade.lots,
        "entry_premium": trade.entry_premium,
        "entry_time": trade.entry_time.isoformat() if trade.entry_time else None,
        "entry_nifty_level": trade.entry_nifty_level,
        "rr_at_entry": trade.rr_at_entry,
        "premium_total": trade.premium_total,
        "max_loss_calculated": trade.max_loss_calculated,
        "target1_profit_calculated": trade.target1_profit_calculated,
        "target2_profit_calculated": trade.target2_profit_calculated,
        "t1_exit_done": trade.t1_exit_done,
        "t1_exit_premium": trade.t1_exit_premium,
        "t1_exit_profit": trade.t1_exit_profit,
        "trailing_sl_after_t1": trade.trailing_sl_after_t1,
        "exit_premium": trade.exit_premium,
        "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
        "exit_reason": trade.exit_reason,
        "gross_pnl": trade.gross_pnl,
        "charges": trade.charges,
        "net_pnl": trade.net_pnl,
        "net_pnl_pct": trade.net_pnl_pct,
        "current_premium": None,
        "signal": {
            "id": sig.id if sig else None,
            "signal_type": sig.signal_type if sig else None,
            "underlying": sig.underlying if sig else None,
            "strike": sig.strike if sig else None,
            "option_type": sig.option_type if sig else None,
            "expiry": sig.expiry if sig else None,
            "stop_loss": sig.stop_loss if sig else None,
            "target1": sig.target1 if sig else None,
            "target2": sig.target2 if sig else None,
            "ltp_at_signal": sig.ltp_at_signal if sig else None,
        } if sig is not None else None,
    }


@router.get("/open")
async def get_open_trades(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Trade)
        .options(selectinload(Trade.signal))
        .where(Trade.user_id == current_user.id)
        .where(Trade.status.in_(["OPEN", "PARTIAL"]))
        .order_by(Trade.entry_time.desc())
    )
    trades = result.scalars().all()
    return {"trades": [_trade_dict(t) for t in trades]}


@router.get("/history")
async def get_trade_history(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(Trade)
        .options(selectinload(Trade.signal))
        .where(Trade.user_id == current_user.id)
        .where(Trade.created_at >= since)
        .order_by(Trade.created_at.desc())
    )
    trades = result.scalars().all()
    return {"trades": [_trade_dict(t) for t in trades], "count": len(trades)}


@router.post("/{trade_id}/exit")
async def exit_trade(
    trade_id: int,
    body: ExitTradeRequest,
    current_user: User = Depends(RequireAnalyst),
    db: AsyncSession = Depends(get_db),
):
    valid_reasons = {"TARGET1", "TARGET2", "STOP_LOSS", "MANUAL", "EXPIRED"}
    if body.exit_reason not in valid_reasons:
        raise HTTPException(status_code=400, detail=f"exit_reason must be one of {valid_reasons}")

    result = await db.execute(
        select(Trade).options(selectinload(Trade.signal)).where(Trade.id == trade_id, Trade.user_id == current_user.id)
    )
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade.status not in ("OPEN", "PARTIAL"):
        raise HTTPException(status_code=400, detail=f"Trade is already {trade.status}")

    lot_size = 15 if trade.signal and trade.signal.underlying == "BANKNIFTY" else 25
    gross_pnl = (body.exit_premium - trade.entry_premium) * trade.lots * lot_size
    charges = _estimate_charges(trade.lots, trade.entry_premium, body.exit_premium, lot_size)
    net_pnl = gross_pnl - charges
    net_pnl_pct = (net_pnl / trade.capital_at_entry) * 100

    trade.exit_premium = body.exit_premium
    trade.exit_time = datetime.now(timezone.utc)
    trade.exit_reason = body.exit_reason
    trade.gross_pnl = round(gross_pnl, 2)
    trade.charges = round(charges, 2)
    trade.net_pnl = round(net_pnl, 2)
    trade.net_pnl_pct = round(net_pnl_pct, 2)
    trade.status = "CLOSED"
    trade.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(trade)
    return {"trade": trade, "net_pnl": trade.net_pnl, "net_pnl_pct": trade.net_pnl_pct}


@router.get("/pnl-summary")
async def pnl_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    async def _sum_pnl(since: datetime) -> dict:
        result = await db.execute(
            select(
                func.count(Trade.id).label("trades"),
                func.sum(Trade.net_pnl).label("net_pnl"),
                func.sum(Trade.gross_pnl).label("gross_pnl"),
                func.sum(Trade.charges).label("charges"),
            )
            .where(Trade.user_id == current_user.id)
            .where(Trade.status == "CLOSED")
            .where(Trade.exit_time >= since)
        )
        row = result.one()
        return {
            "trades": row.trades or 0,
            "gross_pnl": round(row.gross_pnl or 0, 2),
            "charges": round(row.charges or 0, 2),
            "net_pnl": round(row.net_pnl or 0, 2),
        }

    daily = await _sum_pnl(now - timedelta(days=1))
    weekly = await _sum_pnl(now - timedelta(days=7))
    monthly = await _sum_pnl(now - timedelta(days=30))

    return {
        "capital": current_user.capital,
        "daily": daily,
        "weekly": weekly,
        "monthly": monthly,
    }


@router.get("/auto-status")
async def get_auto_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_settings = get_user_auto_settings(current_user)
    daily_target = float(user_settings["daily_profit_target"])
    max_losses = int(user_settings["max_daily_losses"])

    now_ist = datetime.now(_IST)
    today_start = datetime(now_ist.year, now_ist.month, now_ist.day, 0, 0, 0, tzinfo=_IST)

    pnl_q = await db.execute(
        select(func.coalesce(func.sum(Trade.net_pnl), 0))
        .where(Trade.user_id == current_user.id)
        .where(Trade.trade_mode == "auto")
        .where(Trade.status == "CLOSED")
        .where(Trade.entry_time >= today_start)
    )
    daily_pnl = float(pnl_q.scalar() or 0)

    loss_q = await db.execute(
        select(func.count(Trade.id))
        .where(Trade.user_id == current_user.id)
        .where(Trade.trade_mode == "auto")
        .where(Trade.status == "CLOSED")
        .where(Trade.net_pnl < 0)
        .where(Trade.entry_time >= today_start)
    )
    loss_count = int(loss_q.scalar() or 0)

    open_q = await db.execute(
        select(func.count(Trade.id))
        .where(Trade.user_id == current_user.id)
        .where(Trade.status.in_(["OPEN", "PARTIAL"]))
    )
    open_count = int(open_q.scalar() or 0)

    halted = loss_count >= max_losses
    target_met = daily_pnl >= daily_target

    if halted:
        status = "HALTED"
        waiting_reason = f"{max_losses} losses today - auto halted for the day to protect capital"
    elif target_met:
        status = "TARGET_MET"
        waiting_reason = f"Daily target Rs{daily_target:,.0f} achieved! Profit today: Rs{daily_pnl:,.0f}"
    elif open_count > 0:
        status = "ACTIVE"
        waiting_reason = "Trade open - monitoring for T1 / T2 / SL"
    else:
        status = "ACTIVE"
        waiting_reason = "Scanning for entry signals - monitoring market conditions..."

    return {
        "trade_mode": current_user.trade_mode,
        "execution_mode": settings.execution_mode,
        "daily_pnl": daily_pnl,
        "daily_target": daily_target,
        "target_met": target_met,
        "loss_count": loss_count,
        "max_losses": max_losses,
        "halted": halted,
        "open_count": open_count,
        "waiting_reason": waiting_reason,
        "status": status,
    }


@router.get("/auto-settings")
async def get_auto_settings(current_user: User = Depends(get_current_user)):
    defaults = get_default_auto_settings()
    effective = get_user_auto_settings(current_user)
    overrides = diff_auto_settings_from_defaults(effective)
    return {
        "defaults": defaults,
        "overrides": overrides,
        "effective": effective,
        "trade_mode": current_user.trade_mode,
        "capital": current_user.capital,
    }


@router.put("/auto-settings")
async def update_auto_settings(
    body: UpdateAutoSettingsRequest,
    current_user: User = Depends(RequireAnalyst),
    db: AsyncSession = Depends(get_db),
):
    try:
        patch = validate_auto_settings_patch(body.settings)
        effective = get_user_auto_settings(current_user)
        effective.update(patch)
        current_user.auto_settings = diff_auto_settings_from_defaults(effective) or None
        current_user.updated_at = datetime.now(timezone.utc)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "defaults": get_default_auto_settings(),
        "overrides": current_user.auto_settings or {},
        "effective": get_user_auto_settings(current_user),
    }


@router.get("/capital")
async def get_capital(current_user: User = Depends(get_current_user)):
    return {
        "capital": current_user.capital,
        "trade_mode": current_user.trade_mode,
        "auto_settings": get_user_auto_settings(current_user),
    }


@router.put("/capital")
async def update_capital(
    body: ChangeCapitalRequest,
    current_user: User = Depends(RequireAnalyst),
    db: AsyncSession = Depends(get_db),
):
    clamped = max(10_000, min(10_000_000, int(body.capital)))
    if clamped != body.capital:
        raise HTTPException(
            status_code=400,
            detail=f"Capital must be between Rs10,000 and Rs1,00,00,000. Got: {body.capital}",
        )
    current_user.capital = clamped
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"capital": current_user.capital}


@router.put("/mode")
async def update_trade_mode(
    body: ChangeTradeModeRequest,
    current_user: User = Depends(RequireAnalyst),
    db: AsyncSession = Depends(get_db),
):
    current_user.trade_mode = body.mode
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"trade_mode": current_user.trade_mode}


def _estimate_charges(lots: int, entry: float, exit_val: float, lot_size: int) -> float:
    turnover = (entry + exit_val) * lots * lot_size
    return round(turnover * 0.0005, 2)