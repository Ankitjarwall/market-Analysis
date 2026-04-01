"""
Options signals API endpoints.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.middleware import RequireAnalyst, get_current_user
from db.connection import get_db
from db.models import Signal, Trade, User

router = APIRouter(prefix="/api/signals", tags=["signals"])


class ManualEntryRequest(BaseModel):
    entry_premium: float
    lots: int
    entry_time: datetime | None = None


@router.get("/active")
async def get_active_signals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Signal)
        .where(Signal.status == "OPEN")
        .where(Signal.valid_until >= datetime.now(timezone.utc))
        .order_by(Signal.timestamp.desc())
    )
    signals = result.scalars().all()
    return {"signals": signals}


@router.get("/history")
async def get_signal_history(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import timedelta
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(Signal)
        .where(Signal.timestamp >= since)
        .order_by(Signal.timestamp.desc())
    )
    signals = result.scalars().all()
    return {"signals": signals, "count": len(signals)}


@router.post("/{signal_id}/manual-entry")
async def manual_entry(
    signal_id: int,
    body: ManualEntryRequest,
    current_user: User = Depends(RequireAnalyst),
    db: AsyncSession = Depends(get_db),
):
    """Log a manual trade entry for a given signal. Only for MANUAL mode users."""
    if current_user.trade_mode != "manual":
        raise HTTPException(
            status_code=400,
            detail="Your account is in AUTO mode. Switch to MANUAL to use this endpoint.",
        )

    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    if signal.status not in ("OPEN",):
        raise HTTPException(status_code=400, detail=f"Signal is {signal.status}, not OPEN")

    # Calculate position for the manually entered price
    from bot.position_calculator import calculate_position, estimate_charges

    entry_premium = body.entry_premium
    lots = body.lots

    # Recalculate R:R from manual entry price
    risk_per_unit = abs(entry_premium - signal.stop_loss)
    reward_t1 = abs(signal.target1 - entry_premium)
    if risk_per_unit == 0:
        raise HTTPException(status_code=400, detail="Risk per unit is zero — invalid entry price")

    rr = reward_t1 / risk_per_unit
    from bot.position_calculator import get_lot_size
    lot_size = get_lot_size(signal.underlying or "NIFTY50")
    premium_total = entry_premium * lots * lot_size
    max_loss = risk_per_unit * lots * lot_size
    max_loss_pct = (max_loss / current_user.capital) * 100

    rr_warning = rr < 2.0

    trade = Trade(
        signal_id=signal.id,
        user_id=current_user.id,
        trade_mode="manual",
        capital_at_entry=current_user.capital,
        lots=lots,
        entry_premium=entry_premium,
        entry_time=body.entry_time or datetime.now(timezone.utc),
        rr_at_entry=round(rr, 2),
        rr_warning_acknowledged=rr_warning,
        manual_entry_deviation_pct=round(
            ((entry_premium - signal.ltp_at_signal) / signal.ltp_at_signal) * 100, 2
        ),
        premium_total=round(premium_total, 2),
        max_loss_calculated=round(max_loss, 2),
        max_loss_pct=round(max_loss_pct, 2),
        target1_profit_calculated=round(reward_t1 * lots * lot_size, 2),
        target2_profit_calculated=round(
            abs(signal.target2 - entry_premium) * lots * lot_size, 2
        ),
        partial_t1_lots=max(1, int(lots * 0.75)),
        partial_t2_lots=lots - max(1, int(lots * 0.75)),
        status="OPEN",
    )
    db.add(trade)
    await db.commit()
    await db.refresh(trade)

    return {
        "trade": trade,
        "rr_warning": rr_warning,
        "message": f"Manual trade logged. R:R = 1:{rr:.2f}"
        + (" ⚠️ Below minimum 1:2" if rr_warning else ""),
    }
