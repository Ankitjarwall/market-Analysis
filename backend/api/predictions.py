"""
Predictions API endpoints.
"""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.middleware import get_current_user
from db.connection import get_db
from db.models import Prediction, User

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


@router.get("/today")
async def get_today_prediction(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    result = await db.execute(
        select(Prediction)
        .where(Prediction.date == today)
        .order_by(Prediction.created_at.desc())
        .limit(1)
    )
    prediction = result.scalar_one_or_none()
    if not prediction:
        return {"prediction": None, "message": "No prediction for today yet"}
    return {"prediction": prediction}


@router.get("/history")
async def get_prediction_history(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    since = date.today() - timedelta(days=days)
    result = await db.execute(
        select(Prediction)
        .where(Prediction.date >= since)
        .order_by(Prediction.date.desc(), Prediction.created_at.desc())
    )
    predictions = result.scalars().all()
    return {"predictions": predictions, "count": len(predictions)}


@router.get("/accuracy")
async def get_accuracy(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    since = date.today() - timedelta(days=days)
    result = await db.execute(
        select(Prediction)
        .where(Prediction.date >= since)
        .where(Prediction.was_correct.isnot(None))
    )
    predictions = result.scalars().all()

    if not predictions:
        return {"accuracy": None, "total": 0, "correct": 0, "incorrect": 0}

    correct = sum(1 for p in predictions if p.was_correct)
    total = len(predictions)

    # Break down by direction
    direction_stats: dict[str, dict] = {}
    for p in predictions:
        d = p.direction
        if d not in direction_stats:
            direction_stats[d] = {"total": 0, "correct": 0}
        direction_stats[d]["total"] += 1
        if p.was_correct:
            direction_stats[d]["correct"] += 1

    return {
        "period_days": days,
        "total": total,
        "correct": correct,
        "incorrect": total - correct,
        "accuracy_pct": round((correct / total) * 100, 1),
        "by_direction": direction_stats,
    }


@router.get("/learning-log")
async def get_learning_log(
    days: int = Query(default=90, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all incorrect predictions with their post-mortem analysis."""
    from db.models import PredictionMistake
    since = date.today() - timedelta(days=days)
    result = await db.execute(
        select(PredictionMistake)
        .where(PredictionMistake.date >= since)
        .order_by(PredictionMistake.date.desc())
        .limit(50)
    )
    mistakes = result.scalars().all()
    return {"mistakes": mistakes, "count": len(mistakes)}
