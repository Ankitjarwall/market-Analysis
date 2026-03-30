"""
Self-healing API endpoints.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.middleware import RequireAdmin, get_current_user
from db.connection import get_db
from db.models import Error, SystemHealthLog, User

router = APIRouter(prefix="/api/heal", tags=["self-heal"])


@router.get("/status")
async def get_health_status(
    current_user: User = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """Return current health of all monitored services."""
    result = await db.execute(
        select(SystemHealthLog)
        .order_by(SystemHealthLog.timestamp.desc())
        .limit(50)
    )
    recent_logs = result.scalars().all()

    # Get latest status per service
    services: dict[str, dict] = {}
    for log in recent_logs:
        if log.service not in services:
            services[log.service] = {
                "service": log.service,
                "status": log.status,
                "last_checked": log.timestamp,
                "response_time_ms": log.response_time_ms,
                "details": log.details,
            }

    # Count pending errors
    error_result = await db.execute(
        select(Error)
        .where(Error.fix_attempted == False)
        .where(Error.severity >= 3)
        .order_by(Error.timestamp.desc())
    )
    pending_errors = error_result.scalars().all()

    return {
        "services": list(services.values()),
        "pending_fixes": len(pending_errors),
        "critical_errors": [e for e in pending_errors if e.severity == 4],
    }


@router.get("/errors")
async def get_errors(
    limit: int = Query(default=20, ge=1, le=100),
    severity: int | None = Query(default=None, ge=1, le=4),
    current_user: User = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    query = select(Error).order_by(Error.timestamp.desc()).limit(limit)
    if severity:
        query = query.where(Error.severity == severity)
    result = await db.execute(query)
    errors = result.scalars().all()
    return {"errors": errors}


@router.post("/approve/{error_id}")
async def approve_fix(
    error_id: int,
    current_user: User = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Error).where(Error.id == error_id))
    error = result.scalar_one_or_none()
    if not error:
        raise HTTPException(status_code=404, detail="Error record not found")
    if error.severity == 4:
        raise HTTPException(
            status_code=403,
            detail="Severity 4 errors require super_admin approval and manual deployment",
        )
    if not error.fix_code:
        raise HTTPException(status_code=400, detail="No fix code available to approve")

    error.fix_approved_by = current_user.id
    error.fix_timestamp = datetime.now(timezone.utc)
    await db.commit()

    # Trigger deployment in background
    from healing.deployer import deploy_fix_async
    import asyncio
    asyncio.create_task(deploy_fix_async(error_id))

    return {"message": f"Fix approved for error {error_id}. Deployment started."}


@router.post("/reject/{error_id}")
async def reject_fix(
    error_id: int,
    current_user: User = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Error).where(Error.id == error_id))
    error = result.scalar_one_or_none()
    if not error:
        raise HTTPException(status_code=404, detail="Error record not found")

    error.fix_code = None
    error.fix_explanation = None
    error.fix_source = "HUMAN"
    error.prevention_note = f"Fix rejected by {current_user.email} at {datetime.now(timezone.utc).isoformat()}"
    await db.commit()
    return {"message": "Fix rejected. Manual intervention required."}


@router.post("/restart/{service}")
async def restart_service(
    service: str,
    current_user: User = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    allowed = {"scheduler", "data_feed", "telegram"}
    if service not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Service must be one of {allowed}. Core services cannot be restarted via API.",
        )
    # Log the restart request
    log = SystemHealthLog(
        service=service,
        status="WARNING",
        details={"action": "manual_restart", "requested_by": str(current_user.id)},
    )
    db.add(log)
    await db.commit()

    return {"message": f"Restart requested for {service}"}


@router.post("/rollback")
async def rollback(
    current_user: User = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """Rollback to the last known good git commit."""
    from healing.rollback import perform_rollback
    result = await perform_rollback()
    return result
