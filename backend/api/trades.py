"""
Trade journal API endpoints.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.middleware import RequireAnalyst, get_current_user
from auth.schemas import ChangeCapitalRequest, ChangeTradeModeRequest
from db.connection import get_db
from db.models import Trade, User

router = APIRouter(prefix="/api/trades", tags=["trades"])


class ExitTradeRequest(BaseModel):
    exit_premium: float
    exit_reason: str  # TARGET1|TARGET2|STOP_LOSS|MANUAL|EXPIRED


@router.get("/open")
async def get_open_trades(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Trade)
        .where(Trade.user_id == current_user.id)
        .where(Trade.status.in_(["OPEN", "PARTIAL"]))
        .order_by(Trade.entry_time.desc())
    )
    trades = result.scalars().all()
    return {"trades": trades}


@router.get("/history")
async def get_trade_history(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(Trade)
        .where(Trade.user_id == current_user.id)
        .where(Trade.created_at >= since)
        .order_by(Trade.created_at.desc())
    )
    trades = result.scalars().all()
    return {"trades": trades, "count": len(trades)}


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
        select(Trade).where(Trade.id == trade_id, Trade.user_id == current_user.id)
    )
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade.status not in ("OPEN", "PARTIAL"):
        raise HTTPException(status_code=400, detail=f"Trade is already {trade.status}")

    lot_size = 25  # Nifty
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
    """Return daily/weekly/monthly P&L summary for the current user."""
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


@router.get("/capital")
async def get_capital(current_user: User = Depends(get_current_user)):
    return {"capital": current_user.capital, "trade_mode": current_user.trade_mode}


@router.put("/capital")
async def update_capital(
    body: ChangeCapitalRequest,
    current_user: User = Depends(RequireAnalyst),
    db: AsyncSession = Depends(get_db),
):
    # Clamp to prevent absurdly large values (e.g. scientific-notation input)
    clamped = max(10_000, min(10_000_000, int(body.capital)))
    if clamped != body.capital:
        raise HTTPException(
            status_code=400,
            detail=f"Capital must be between ₹10,000 and ₹1,00,00,000. Got: {body.capital}"
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
    """Rough estimate: STT + brokerage + exchange fees ~ 0.05% of turnover."""
    turnover = (entry + exit_val) * lots * lot_size
    return round(turnover * 0.0005, 2)
